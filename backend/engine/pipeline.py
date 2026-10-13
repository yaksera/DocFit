"""Target-size search: find the best quality that still fits under the limit."""
from __future__ import annotations

import os
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import pymupdf
from PIL import Image

from .levels import LEVELS, Level
from .pdfwriter import PdfAssembler
from .raster import (ANALYSIS_DPI, MAX_WORK_DPI, Analysis, Layer, analyze, color_plan, encode_page,
                     jpeg, prepare)
from .sources import MUPDF_LOCK, SourcePage, load_pages
from .types import CompressOptions, CompressResult, EngineError, ProgressFn

SAMPLE_PAGES = 5
DIRECT_SEARCH_MAX_PAGES = 6
WORK_CACHE_SIZE = 6  # ~25 MB per A4 colour page at 300 dpi
THREADS = max(1, int(os.environ.get("DOCFIT_THREADS", min(4, os.cpu_count() or 1))))


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    return f"{max(1, round(n / 1000))} KB"


class _Progress:
    def __init__(self, fn: Optional[ProgressFn], expected: float) -> None:
        self.fn, self.expected, self.done = fn, max(expected, 1.0), 0.0

    def step(self, msg: str, amount: float = 1.0) -> None:
        self.done += amount
        if self.fn:
            self.fn(min(0.95, 0.05 + 0.9 * self.done / self.expected), msg)

    def grow(self, extra: float) -> None:
        self.expected += extra


class _PdfJob:
    def __init__(self, paths: list[str], pages: list[SourcePage], opts: CompressOptions,
                 progress: _Progress) -> None:
        self.paths, self.pages, self.opts, self.progress = paths, pages, opts, progress
        self._analysis: dict[int, Analysis] = {}
        self._digital: dict[tuple[str, int], pymupdf.Document] = {}
        self._work: dict[tuple[int, bool, bool], tuple[float, Image.Image]] = {}
        self.results: dict[tuple[int, bool], bytes] = {}
        self._lock = threading.Lock()

    # ---- per-page work (runs in worker threads)
    def analysis(self, i: int) -> Analysis:
        with self._lock:
            if i in self._analysis:
                return self._analysis[i]
        an = analyze(self.pages[i].render(ANALYSIS_DPI))
        with self._lock:
            self._analysis[i] = an
        return an

    def work_image(self, i: int, an: Analysis, tc: bool, pc: bool) -> tuple[float, Image.Image]:
        """Rendered + cleaned page, cached across quality levels (small LRU)."""
        key = (i, tc, pc)
        with self._lock:
            if key in self._work:
                self._work[key] = self._work.pop(key)  # mark as recently used
                return self._work[key]
        p = self.pages[i]
        dpi = min(MAX_WORK_DPI, p.native_dpi)
        work = prepare(p.render(dpi), an, self.opts.color_mode, self.opts.clean_background, tc, pc)
        with self._lock:
            self._work[key] = (dpi, work)
            while len(self._work) > WORK_CACHE_SIZE:
                self._work.pop(next(iter(self._work)))
        return dpi, work

    def encode_raster(self, i: int, lv: Level) -> list[Layer]:
        p = self.pages[i]
        an = self.analysis(i)
        tc, pc = color_plan(an, lv, self.opts.color_mode)
        dpi, work = self.work_image(i, an, tc, pc)
        return encode_page(work, dpi, (p.width_in, p.height_in), an, lv, self.opts.color_mode, tc, pc)

    def digital_doc(self, page: SourcePage, lv: Level) -> pymupdf.Document:
        key = (page.pdf_key, lv.index)
        if key not in self._digital:
            doc = pymupdf.open(page.pdf_key)
            if doc.needs_pass:
                doc.authenticate(self.opts.password or "")
            try:
                doc.rewrite_images(dpi_threshold=int(lv.img_dpi * 1.2), dpi_target=lv.img_dpi,
                                   quality=lv.img_q, set_to_gray=lv.force_gray)
            except Exception:
                pass  # unusual image types: keep them as they are
            try:
                doc.subset_fonts()
            except Exception:
                pass
            self._digital[key] = doc
        return self._digital[key]

    # ---- assembly (main thread; every MuPDF call is serialised by MUPDF_LOCK)
    def build(self, li: int, subset: list[int], rasterize_all: bool) -> bytes:
        lv = LEVELS[li]
        raster = [i for i in subset if rasterize_all or not self.pages[i].is_digital]
        with ThreadPoolExecutor(min(THREADS, max(1, len(raster)))) as pool:
            futures = {i: pool.submit(self.encode_raster, i, lv) for i in raster}
            with MUPDF_LOCK:
                asm = PdfAssembler()
            try:
                for i in subset:
                    p = self.pages[i]
                    if i in futures:
                        layers = futures[i].result()
                        with MUPDF_LOCK:
                            asm.add_layers_page(p.width_in, p.height_in, layers)
                    else:
                        with MUPDF_LOCK:
                            asm.add_pdf_page(self.digital_doc(p, lv), p.pno)
                    self.progress.step(f"Optimising page {i + 1} of {len(self.pages)}")
                with MUPDF_LOCK:
                    return asm.tobytes()
            except BaseException:
                for f in futures.values():
                    f.cancel()
                raise
            finally:
                with MUPDF_LOCK:
                    asm.close()

    def full(self, li: int, ra: bool) -> bytes:
        key = (li, ra)
        if key not in self.results:
            self.results[key] = self.build(li, list(range(len(self.pages))), ra)
        return self.results[key]

    # ---- search
    def search(self, ra: bool) -> Optional[int]:
        n, budget = len(self.pages), self.opts.budget
        if n <= DIRECT_SEARCH_MAX_PAGES:
            lo, hi, best = 0, len(LEVELS) - 1, None
            while lo <= hi:
                mid = (lo + hi) // 2
                if len(self.full(mid, ra)) <= budget:
                    best, hi = mid, mid - 1
                else:
                    lo = mid + 1
            return best

        # Large documents: estimate from a few sample pages, then confirm with full builds.
        sample = sorted({round(k * (n - 1) / (SAMPLE_PAGES - 1)) for k in range(SAMPLE_PAGES)})
        lo, hi, pred = 0, len(LEVELS) - 1, len(LEVELS) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            est = len(self.build(mid, sample, ra)) * n / len(sample)
            if est <= budget * 0.95:
                pred, hi = mid, mid - 1
            else:
                lo = mid + 1
        li = pred
        while True:
            size = len(self.full(li, ra))
            if size <= budget:
                if li > 0 and size < 0.7 * budget:
                    self.progress.grow(n)
                    if len(self.full(li - 1, ra)) <= budget:
                        return li - 1
                return li
            if li == len(LEVELS) - 1:
                return None
            self.progress.grow(n)
            li += 1

    def close(self) -> None:
        with MUPDF_LOCK:
            for d in self._digital.values():
                d.close()


def _compress_pdf(paths, pages, docs, base_path, opts, progress, original) -> CompressResult:
    n = len(pages)
    expected = n * 4 if n <= DIRECT_SEARCH_MAX_PAGES else SAMPLE_PAGES * 4 + n * 1.3
    prog = _Progress(progress, expected)
    job = _PdfJob(paths, pages, opts, prog)
    warnings: list[str] = []
    try:
        has_digital = any(p.is_digital for p in pages)
        ra = False
        best = job.search(False)
        if best is None and has_digital:
            prog.grow(n * 3)
            ra, best = True, job.search(True)
            if best is not None:
                warnings.append("Some pages were converted to images to fit the limit, "
                                "so their text can no longer be selected or searched.")
        met = best is not None
        if met:
            data, level = job.results[(best, ra)], best
        else:
            (level, ra), data = min(job.results.items(), key=lambda kv: len(kv[1]))
            warnings.append(
                f"Could not get under {human(opts.target_bytes)} while keeping the text readable. "
                f"This is the smallest readable version ({human(len(data))}). "
                "Try splitting the document or using Black & White mode.")
    finally:
        job.close()

    # Never hand back something worse than what the user uploaded.
    single_plain_pdf = (len(paths) == 1 and docs and not docs[0].is_encrypted
                        and not docs[0].needs_pass)
    if single_plain_pdf and original <= opts.budget and original <= len(data):
        with open(paths[0], "rb") as f:
            data = f.read()
        met, level = True, 0
        warnings = ["This file was already well optimised and under the limit, so it was left unchanged."]

    if met and LEVELS[level].text_quality == "fair":
        warnings.append("Small print may look slightly soft. Zoom in to check before submitting.")

    out = base_path + ".pdf"
    with open(out, "wb") as f:
        f.write(data)
    return CompressResult(output_path=out, original_bytes=original, output_bytes=len(data),
                          pages=n, met_target=met, level=level,
                          text_quality=LEVELS[level].text_quality,
                          content_type="application/pdf", warnings=warnings)


def jpeg_under(img: Image.Image, budget: int) -> tuple[bytes, bool, int]:
    """Largest/best JPEG under `budget`. Returns (data, fits, quality)."""
    if max(img.size) > 3500:
        s = 3500 / max(img.size)
        img = img.resize((round(img.width * s), round(img.height * s)), Image.Resampling.LANCZOS)
    first_fit = None
    smallest = None
    scales = (1.0, 0.85, 0.72, 0.6, 0.5, 0.42, 0.35, 0.28, 0.22, 0.17)
    for s in scales:
        im = img if s == 1.0 else img.resize(
            (max(1, round(img.width * s)), max(1, round(img.height * s))), Image.Resampling.LANCZOS)
        lo, hi, found = 30, 92, None
        while lo <= hi:
            q = (lo + hi) // 2
            data = jpeg(im, q)
            if smallest is None or len(data) < len(smallest[0]):
                smallest = (data, q)
            if len(data) <= budget:
                found, lo = (data, q), q + 1
            else:
                hi = q - 1
        if found:
            if found[1] >= 60:
                return found[0], True, found[1]
            first_fit = first_fit or found
    if first_fit:
        return first_fit[0], True, first_fit[1]
    return smallest[0], False, smallest[1]


def _compress_jpg(pages, base_path, opts, progress, original) -> CompressResult:
    prog = _Progress(progress, len(pages))
    outputs, all_fit, worst_q = [], True, 100
    for i, p in enumerate(pages):
        img = p.render(min(p.native_dpi, 300))
        if opts.color_mode in ("gray", "bw"):
            img = img.convert("L")
        data, fits, q = jpeg_under(img, opts.budget)
        outputs.append(data)
        all_fit &= fits
        worst_q = min(worst_q, q)
        prog.step(f"Optimising image {i + 1} of {len(pages)}")
    warnings = []
    if not all_fit:
        warnings.append(f"Could not get every image under {human(opts.target_bytes)}.")
    if len(outputs) == 1:
        out, ctype, size = base_path + ".jpg", "image/jpeg", len(outputs[0])
        with open(out, "wb") as f:
            f.write(outputs[0])
    else:
        out, ctype = base_path + ".zip", "application/zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
            for i, data in enumerate(outputs, 1):
                z.writestr(f"page-{i:02d}.jpg", data)
        size = os.path.getsize(out)
        warnings.append("Each page was saved as a separate JPG (bundled in a ZIP); "
                        f"each one is under {human(opts.target_bytes)}.")
    quality = "excellent" if worst_q >= 75 else "very good" if worst_q >= 60 else "good"
    return CompressResult(output_path=out, original_bytes=original, output_bytes=size,
                          pages=len(pages), met_target=all_fit, level=None, text_quality=quality,
                          content_type=ctype, warnings=warnings)


def compress(paths: list[str], base_output_path: str, opts: CompressOptions,
             progress: Optional[ProgressFn] = None) -> CompressResult:
    """Compress one or more input files into a single output.

    `base_output_path` has no extension; the right one is added (.pdf/.jpg/.zip).
    Multiple inputs are merged into one PDF in the given order.
    """
    if not paths:
        raise EngineError("No files to process.")
    if opts.target_bytes < 20_000:
        raise EngineError("The size limit must be at least 20 KB.")
    original = sum(os.path.getsize(p) for p in paths)
    if progress:
        progress(0.02, "Reading files")
    pages, docs = load_pages(paths, opts.password)
    try:
        if opts.max_pages and len(pages) > opts.max_pages:
            raise EngineError(f"This job has {len(pages)} pages; your plan allows up to "
                              f"{opts.max_pages} pages per job. Split the file or upgrade your plan.")
        if opts.output_format == "jpg":
            result = _compress_jpg(pages, base_output_path, opts, progress, original)
        else:
            result = _compress_pdf(paths, pages, docs, base_output_path, opts, progress, original)
    finally:
        with MUPDF_LOCK:
            for d in docs:
                d.close()
    if progress:
        progress(1.0, "Done")
    return result
