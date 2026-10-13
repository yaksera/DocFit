"""Loads input files (PDF, JPG, PNG, HEIC, TIFF, WebP, ...) into a flat list of pages."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Optional

import pymupdf
from PIL import Image, ImageOps, ImageSequence

from .raster import find_paper
from .types import EngineError, PasswordRequired

try:  # iPhone photos
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass

Image.MAX_IMAGE_PIXELS = 400_000_000  # big scans are legitimate input

A4_LONG_IN = 11.69
# MuPDF's global context is not thread-safe: every PyMuPDF call goes through this lock.
MUPDF_LOCK = threading.RLock()
PDF_EXT = {".pdf"}


@dataclass
class SourcePage:
    width_in: float
    height_in: float
    native_dpi: float
    is_digital: bool  # real text/vectors: keep as-is instead of rasterising
    pdf: Optional[pymupdf.Document] = None
    pdf_key: Optional[str] = None
    pno: int = 0
    image_path: Optional[str] = None
    frame: int = 0
    crop: Optional[tuple[float, float, float, float]] = None  # fractions of the image

    def render(self, dpi: float) -> Image.Image:
        """RGB image of the page at `dpi` (never upsampled past the native resolution)."""
        dpi = min(dpi, self.native_dpi) if self.native_dpi else dpi
        size = (max(1, round(self.width_in * dpi)), max(1, round(self.height_in * dpi)))
        if self.pdf is not None:
            with MUPDF_LOCK:
                pix = self.pdf[self.pno].get_pixmap(dpi=max(1, round(dpi)), alpha=False,
                                                    colorspace=pymupdf.csRGB)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            return img if img.size == size else img.resize(size, Image.Resampling.LANCZOS)
        cx0, cy0, cx1, cy1 = self.crop or (0.0, 0.0, 1.0, 1.0)
        want = (round(size[0] / (cx1 - cx0)), round(size[1] / (cy1 - cy0)))
        img = _open_frame(self.image_path, self.frame, want)
        if self.crop:
            x0, y0, x1, y1 = self.crop
            img = img.crop((round(x0 * img.width), round(y0 * img.height),
                            round(x1 * img.width), round(y1 * img.height)))
        if img.size != size:
            img = img.resize(size, Image.Resampling.LANCZOS, reducing_gap=3.0)
        return img


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.getchannel("A"))
        return bg
    if img.mode in ("I;16", "I;16B", "I;16L", "I"):
        img = img.point(lambda v: v / 256).convert("L")
    return img.convert("RGB")


def _open_frame(path: str, frame: int, want: Optional[tuple[int, int]] = None) -> Image.Image:
    with Image.open(path) as im:
        if frame:
            im.seek(frame)
        elif want and im.format == "JPEG":
            # Decode big phone photos at reduced size directly (much faster).
            if im.getexif().get(0x0112, 1) in (5, 6, 7, 8):
                want = (want[1], want[0])
            im.draft("RGB", want)
        img = ImageOps.exif_transpose(im) if frame == 0 else im.copy()
        return _flatten_to_rgb(img)


def _image_pages(path: str) -> list[SourcePage]:
    try:
        im = Image.open(path)
    except Exception as exc:
        raise EngineError(f"{os.path.basename(path)} is not a supported image or PDF.") from exc
    pages = []
    with im:
        n = getattr(im, "n_frames", 1)
        for i, frame in enumerate(ImageSequence.Iterator(im)):
            if i >= n:
                break
            w, h = frame.size
            orientation = frame.getexif().get(0x0112, 1) if i == 0 else 1
            if orientation in (5, 6, 7, 8):
                w, h = h, w
            dpi = frame.info.get("dpi", (0, 0))[0] or 0
            try:
                dpi = float(dpi)
            except (TypeError, ValueError):
                dpi = 0.0
            crop = None
            # Phone photos and screenshots carry meaningless DPI (72/96): crop to
            # the paper if it was photographed on a table, then fit to A4.
            if not (100 <= dpi <= 1200):
                if i == 0 and min(w, h) >= 600:
                    thumb = frame.copy()
                    thumb.thumbnail((800, 800))
                    crop = find_paper(_flatten_to_rgb(ImageOps.exif_transpose(thumb)))
                    if crop:
                        w, h = round(w * (crop[2] - crop[0])), round(h * (crop[3] - crop[1]))
                dpi = max(w, h) / A4_LONG_IN
            pages.append(SourcePage(width_in=w / dpi, height_in=h / dpi, native_dpi=dpi,
                                    is_digital=False, image_path=path, frame=i, crop=crop))
    return pages


def _pdf_pages(path: str, password: Optional[str]) -> tuple[pymupdf.Document, list[SourcePage]]:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise EngineError(f"{os.path.basename(path)} is damaged or not a real PDF.") from exc
    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            raise PasswordRequired(
                f"{os.path.basename(path)} is password-protected. Enter its password and try again.")
    if doc.page_count == 0:
        raise EngineError(f"{os.path.basename(path)} has no pages.")
    pages = []
    for page in doc:
        rect = page.rect
        area = max(rect.width * rect.height, 1.0)
        biggest, native = 0.0, 0.0
        for info in page.get_image_info():
            bbox = pymupdf.Rect(info["bbox"]) & rect
            if bbox.is_empty:
                continue
            cover = bbox.width * bbox.height / area
            if cover > biggest:
                biggest = cover
                native = max(info["width"] / (bbox.width / 72), info["height"] / (bbox.height / 72))
        scanned = biggest >= 0.6
        pages.append(SourcePage(
            width_in=rect.width / 72, height_in=rect.height / 72,
            native_dpi=max(72.0, min(native, 600.0)) if scanned else 300.0,
            is_digital=not scanned, pdf=doc, pdf_key=path, pno=page.number))
    return doc, pages


def load_pages(paths: list[str], password: Optional[str] = None) -> tuple[list[SourcePage], list]:
    """Return (pages, open_documents). Callers must close the documents."""
    pages: list[SourcePage] = []
    docs = []
    for path in paths:
        if os.path.splitext(path)[1].lower() in PDF_EXT or _is_pdf(path):
            with MUPDF_LOCK:
                doc, p = _pdf_pages(path, password)
            docs.append(doc)
            pages.extend(p)
        else:
            pages.extend(_image_pages(path))
    if not pages:
        raise EngineError("No pages found in the uploaded files.")
    return pages, docs


def _is_pdf(path: str) -> bool:
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"
