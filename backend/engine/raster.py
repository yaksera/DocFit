"""Scanned-page processing.

A scanned page is split into layers, the way professional scanners build
small, sharp PDFs (mixed raster content):

* text mask: 1-bit, high resolution, CCITT G4 compressed. Keeps text crisp.
* text colour: tiny JPEG holding the colour of the ink (blue pen, red stamp).
* background: low resolution JPEG of the paper with the text removed.
* photos: separate JPEGs at photo resolution (passport photos, ID pictures).

Each layer is compressed with the method that suits it, so the result is far
smaller than one big JPEG while staying more readable.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageFilter

from .levels import Level

ANALYSIS_DPI = 100
_CELL = 8  # analysis grid cell, in pixels at ANALYSIS_DPI


# --------------------------------------------------------------------------- helpers

def box_mean(a: np.ndarray, r: int) -> np.ndarray:
    """Mean over a (2r+1)^2 window with clamped edges (2-D float array)."""
    a = a.astype(np.float32, copy=False)
    if r <= 0:
        return a
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge").astype(np.float64)
    c = np.cumsum(p, axis=0)
    c = np.vstack([np.zeros((1, c.shape[1])), c])
    v = c[k:] - c[:-k]
    c = np.cumsum(v, axis=1)
    c = np.hstack([np.zeros((c.shape[0], 1)), c])
    return ((c[:, k:] - c[:, :-k]) / (k * k)).astype(np.float32)


def _f(a: np.ndarray) -> Image.Image:
    return Image.fromarray(np.ascontiguousarray(a, dtype=np.float32), "F")


def fill_holes(values: np.ndarray, known: np.ndarray, default) -> np.ndarray:
    """Fill pixels where `known` is False from nearby known pixels.

    `values` is HxW or HxWxC. Normalised convolution over an image pyramid:
    smooth fills that JPEG compresses well, computed with fast C resizes.
    """
    vals = values.astype(np.float32)
    chans = [vals] if vals.ndim == 2 else [vals[..., i] for i in range(vals.shape[2])]
    h, w = known.shape
    wt = known.astype(np.float32)
    out = [c.copy() for c in chans]
    todo = ~known
    weighted = [_f(c * wt) for c in chans]
    wimg = _f(wt)
    scale = 4
    while todo.any() and scale <= 2 * max(h, w):
        small = (max(1, w // scale), max(1, h // scale))
        den_s = wimg.resize(small, Image.Resampling.BOX)
        den = np.asarray(den_s.resize((w, h), Image.Resampling.BILINEAR))
        ok = todo & (den > 1e-3)
        if ok.any():
            for o, wc in zip(out, weighted):
                num = np.asarray(wc.resize(small, Image.Resampling.BOX).resize((w, h), Image.Resampling.BILINEAR))
                o[ok] = num[ok] / den[ok]
            todo &= ~ok
        scale *= 3
    if todo.any():
        d = default if isinstance(default, (tuple, list)) else (default,) * len(out)
        for o, dv in zip(out, d):
            o[todo] = dv
    res = out[0] if vals.ndim == 2 else np.stack(out, axis=2)
    return np.clip(res, 0, 255).astype(np.uint8)


def resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    if img.size == size:
        return img
    shrinking = size[0] < img.size[0]
    return img.resize(size, Image.Resampling.BOX if shrinking else Image.Resampling.BICUBIC,
                      reducing_gap=3.0 if shrinking else None)


def jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=int(quality), optimize=True, progressive=True)
    return buf.getvalue()


def ccitt_g4(ink: np.ndarray) -> bytes:
    """Encode a boolean ink mask (True = ink) as a raw CCITT G4 stream."""
    im = Image.fromarray(~ink)  # mode "1": ink -> 0
    buf = io.BytesIO()
    im.save(buf, "TIFF", compression="group4", tiffinfo={278: im.height})
    t = Image.open(io.BytesIO(buf.getvalue()))
    offsets, counts = t.tag_v2[273], t.tag_v2[279]
    if isinstance(offsets, int):
        offsets, counts = (offsets,), (counts,)
    if len(offsets) != 1:
        raise RuntimeError("expected a single TIFF strip")
    raw = buf.getvalue()
    return raw[offsets[0]: offsets[0] + counts[0]]


def ink_mask(gray: np.ndarray, dpi: int) -> np.ndarray:
    """Adaptive threshold: pixels clearly darker than their surroundings."""
    r = max(2, round(dpi * 0.2))
    local = np.asarray(Image.fromarray(gray).filter(ImageFilter.BoxBlur(r)), dtype=np.int16)
    g = gray.astype(np.int16)
    return (g * 100 < local * 90) & (local - g > 20)


def despeckle(ink: np.ndarray) -> np.ndarray:
    """Drop isolated single pixels (scanner dust); they bloat the text layer."""
    counts = np.asarray(
        Image.fromarray(ink.astype(np.uint8) * 255).filter(ImageFilter.BoxBlur(1)),
        dtype=np.uint8,
    )
    return ink & (counts >= 50)


def min3x3(a: np.ndarray) -> np.ndarray:
    """3x3 minimum filter (separable; far faster than PIL's generic rank filter)."""
    p = np.pad(a, ((1, 1), (1, 1)) + ((0, 0),) * (a.ndim - 2), mode="edge")
    rows = np.minimum(np.minimum(p[:-2], p[1:-1]), p[2:])
    return np.minimum(np.minimum(rows[:, :-2], rows[:, 1:-1]), rows[:, 2:])


def dilate(mask: np.ndarray, r: int = 1) -> np.ndarray:
    im = Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * r + 1))
    return np.asarray(im) > 0


# --------------------------------------------------------------------------- analysis

@dataclass
class Analysis:
    text_color: bool  # coloured ink outside photos (signatures, stamps, logos)
    photo_color: bool
    is_photo: bool  # the whole page is a photo: encode as a single JPEG
    paper_lum: float
    photo_boxes: list[tuple[float, float, float, float]] = field(default_factory=list)  # inches


def _components(grid: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Bounding boxes (y0, x0, y1, x1) of 4-connected True regions."""
    h, w = grid.shape
    seen = np.zeros_like(grid, dtype=bool)
    boxes = []
    for y in range(h):
        for x in range(w):
            if not grid[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            y0 = y1 = y
            x0 = x1 = x
            while stack:
                cy, cx = stack.pop()
                y0, y1, x0, x1 = min(y0, cy), max(y1, cy), min(x0, cx), max(x1, cx)
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and grid[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            boxes.append((y0, x0, y1 + 1, x1 + 1))
    return boxes


def analyze(img: Image.Image) -> Analysis:
    """Classify a page rendered at ANALYSIS_DPI."""
    img = img.convert("RGB")
    raw_gray = np.asarray(img.convert("L"))
    raw_ink = ink_mask(raw_gray, ANALYSIS_DPI)
    paperish = raw_gray[(~raw_ink) & (raw_gray > 120)]
    paper_lum = float(np.median(paperish)) if paperish.size > 0.2 * raw_gray.size else 255.0
    # Judge content on an evenly lit copy, so shadows on phone photos are not
    # mistaken for photo content.
    if paper_lum > 140:
        img = flatten(img, paper_lum)
    rgb = np.asarray(img)
    gray = np.asarray(img.convert("L"))
    h, w = gray.shape
    w_in, h_in = w / ANALYSIS_DPI, h / ANALYSIS_DPI

    # Photo regions: areas dominated by mid-tones that are not part of (or next
    # to) a text stroke. Text is paper plus strokes, so even small dense print
    # has a low density once stroke pixels are excluded.
    ink = ink_mask(gray, ANALYSIS_DPI)
    mid = (gray > 50) & (gray < 205) & ~dilate(ink, 1)
    gh, gw = h // _CELL, w // _CELL
    boxes_in: list[tuple[float, float, float, float]] = []
    if gh and gw:
        def cells(a: np.ndarray) -> np.ndarray:
            return a[: gh * _CELL, : gw * _CELL].reshape(gh, _CELL, gw, _CELL).mean(axis=(1, 3))

        dens = cells(mid)
        # Flat fills (shaded table rows, colour bands) are mid-tone too, but
        # photos have texture: require some tonal variation around each cell.
        g = gray.astype(np.float32)
        mean, sq = box_mean(cells(g), 1), box_mean(cells(g * g), 1)
        std = np.sqrt(np.maximum(sq - mean * mean, 0))
        cand = (dens > 0.45) & (std > 6)
        cand = box_mean(cand.astype(np.float32), 1) > 0.01  # close small gaps
        cand = box_mean(cand.astype(np.float32), 1) > 0.99
        cell_in = _CELL / ANALYSIS_DPI
        for y0, x0, y1, x1 in _components(cand):
            bw, bh = (x1 - x0) * cell_in, (y1 - y0) * cell_in
            if bw * bh >= 0.6 and min(bw, bh) >= 0.5:
                pad = 0.04
                boxes_in.append((
                    max(0.0, x0 * cell_in - pad), max(0.0, y0 * cell_in - pad),
                    min(w_in, x1 * cell_in + pad), min(h_in, y1 * cell_in + pad),
                ))

    photo_area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in boxes_in)
    is_photo = photo_area > 0.55 * w_in * h_in or mid.mean() > 0.5

    in_photo = np.zeros_like(gray, dtype=bool)
    for x0, y0, x1, y1 in boxes_in:
        in_photo[int(y0 * ANALYSIS_DPI): int(y1 * ANALYSIS_DPI) + 1,
                 int(x0 * ANALYSIS_DPI): int(x1 * ANALYSIS_DPI) + 1] = True

    chroma = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2)
    colored = chroma > 48
    outside = ~in_photo
    text_color = bool(outside.any() and colored[outside].mean() > 0.0008)
    photo_color = bool(in_photo.any() and colored[in_photo].mean() > 0.02) or (
        is_photo and colored.mean() > 0.02)

    return Analysis(text_color=text_color, photo_color=photo_color, is_photo=is_photo,
                    paper_lum=paper_lum, photo_boxes=[] if is_photo else boxes_in)


def _longest_run(flags: np.ndarray) -> tuple[int, int]:
    best, start, cur = (0, 0), None, 0
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best


def find_paper(img: Image.Image) -> tuple[float, float, float, float] | None:
    """For a phone photo of a document lying on a darker or coloured surface,
    the paper's box as fractions (x0, y0, x1, y1). None when unsure."""
    small = img.convert("RGB")
    small.thumbnail((400, 400))
    a = np.asarray(small, dtype=np.int16)
    lum = a.mean(axis=2)
    chroma = a.max(axis=2) - a.min(axis=2)
    paper = (lum > 0.55 * np.percentile(lum, 95)) & (chroma < 45)
    h, w = paper.shape
    x0, x1 = _longest_run(paper.mean(axis=0) > 0.6)
    y0, y1 = _longest_run(paper.mean(axis=1) > 0.6)
    area = (x1 - x0) * (y1 - y0) / (w * h)
    if not 0.3 <= area <= 0.93:
        return None
    inside = paper[y0:y1, x0:x1].mean()
    outside_mask = np.ones_like(paper)
    outside_mask[y0:y1, x0:x1] = False
    if inside < 0.85 or paper[outside_mask].mean() > 0.25:
        return None
    m = 0.004  # trim the paper edge itself
    return (x0 / w + m, y0 / h + m, x1 / w - m, y1 / h - m)


# --------------------------------------------------------------------------- cleaning

_V = np.arange(256, dtype=np.float32)
_WHITEN = np.clip(np.where(_V < 215, _V, 215 + (_V - 215) * 40 / 31), 0, 255).astype(np.uint8)
_WHITEN[246:] = 255


def _poly_terms(x: np.ndarray, y: np.ndarray, deg: int = 3) -> np.ndarray:
    return np.stack([x ** i * y ** j for i in range(deg + 1) for j in range(deg + 1 - i)], axis=-1)


def flatten(work: Image.Image, paper_lum: float) -> Image.Image:
    """Even out lighting and whiten the paper (removes phone-photo shadows,
    yellow paper tint and scanner noise) while keeping ink and colours.

    Lighting is modelled as a smooth surface fitted to the paper, so shaded
    table rows and grey boxes are kept instead of being bleached away."""
    w, h = work.size
    small = resize(work, (max(8, w // 6), max(8, h // 6))).filter(ImageFilter.MaxFilter(5))
    small = resize(small, (max(4, w // 15), max(4, h // 15)))
    arr = np.asarray(small, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[..., None]
    sh, sw, nc = arr.shape
    paperish = (arr.mean(axis=2) > paper_lum * 0.8) & ((arr.max(axis=2) - arr.min(axis=2)) < 40)
    if paperish.mean() < 0.15:
        return work
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    terms = _poly_terms(xx / sw * 2 - 1, yy / sh * 2 - 1)
    illum = np.empty_like(arr)
    for c in range(nc):
        chan, sel = arr[..., c], paperish
        for _ in range(3):
            if sel.sum() < terms.shape[-1] * 4:
                break
            coef = np.linalg.lstsq(terms[sel], chan[sel], rcond=None)[0]
            fit = terms @ coef
            sel = paperish & (chan > fit * 0.94)  # ignore shaded boxes and smudges
        illum[..., c] = fit
    illum = np.clip(illum, 85, 255).astype(np.uint8)  # gain capped at 3x
    illum_img = Image.fromarray(illum[..., 0] if nc == 1 else illum)
    illum_up = np.asarray(illum_img.resize((w, h), Image.Resampling.BILINEAR))

    src = np.asarray(work)
    out = np.empty_like(src)
    if src.ndim == 2:
        out[:] = np.minimum(src.astype(np.uint16) * 255 // illum_up, 255)
    else:
        for c in range(src.shape[2]):
            out[..., c] = np.minimum(src[..., c].astype(np.uint16) * 255 // illum_up[..., c], 255)
    return Image.fromarray(_WHITEN[out])


# --------------------------------------------------------------------------- encoding

@dataclass
class Layer:
    kind: str  # "image" | "masked" | "stencil"
    rect: tuple[float, float, float, float]  # inches, top-left origin
    jpeg: bytes | None = None
    size: tuple[int, int] | None = None
    gray: bool = False
    mask: bytes | None = None
    mask_size: tuple[int, int] | None = None
    fill: tuple[float, ...] | None = None


def _px(w_in: float, h_in: float, dpi: float) -> tuple[int, int]:
    return max(1, round(w_in * dpi)), max(1, round(h_in * dpi))


MAX_WORK_DPI = 300  # nothing in the ladder needs more


def color_plan(an: Analysis, lv: Level, color_mode: str) -> tuple[bool, bool]:
    """(text in colour?, photos in colour?)"""
    if color_mode in ("gray", "bw"):
        return False, False
    if color_mode == "color":
        return True, True
    return an.text_color and not lv.force_gray, an.photo_color and not lv.force_gray


def prepare(src: Image.Image, an: Analysis, color_mode: str, clean: bool,
            text_color: bool, photo_color: bool) -> Image.Image:
    """Colour conversion + background cleaning. Independent of the quality
    level, so the result can be reused while searching for the right level."""
    if an.is_photo:
        im = src if photo_color else src.convert("L")
        return flatten(im, an.paper_lum) if clean and color_mode == "bw" else im
    work = src if (text_color or photo_color) else src.convert("L")
    if clean and an.paper_lum > 140:
        work = flatten(work, an.paper_lum)
    return work


def encode_page(work: Image.Image, dpi: float, page_in: tuple[float, float], an: Analysis,
                lv: Level, color_mode: str, text_color: bool, photo_color: bool) -> list[Layer]:
    """Encode a prepared page image (at `dpi`) into PDF layers for level `lv`."""
    w_in, h_in = page_in
    full = (0.0, 0.0, w_in, h_in)

    if an.is_photo:
        pdpi = min(lv.photo_dpi, dpi)
        im = resize(work, _px(w_in, h_in, pdpi))
        return [Layer("image", full, jpeg=jpeg(im, lv.photo_q), size=im.size, gray=im.mode == "L")]

    # ---- text mask
    # Low-res scans: threshold an upscaled copy for smooth (not jagged) letter edges.
    mdpi = min(lv.mask_dpi, dpi * 2)
    msize = _px(w_in, h_in, mdpi)
    work_m = resize(work, msize)
    gray_m = np.asarray(work_m if work_m.mode == "L" else work_m.convert("L"))
    ink = ink_mask(gray_m, mdpi)
    for x0, y0, x1, y1 in an.photo_boxes:
        ink[int(y0 * mdpi): int(y1 * mdpi) + 1, int(x0 * mdpi): int(x1 * mdpi) + 1] = False
    ink = despeckle(ink)

    layers: list[Layer] = []
    fdpi = min(lv.fg_dpi, mdpi)
    fsize = _px(w_in, h_in, fdpi)
    fh, fw = fsize[1], fsize[0]

    # ---- text colour: average colour of the ink pixels in each low-res cell.
    # A min filter first spreads each stroke's dark core over its soft edges,
    # so thin print comes out solid instead of washed-out grey.
    ink_img = Image.fromarray(ink.astype(np.uint8) * 255)
    den = np.asarray(ink_img.resize(fsize, Image.Resampling.BOX), dtype=np.float32) / 255
    has = den > 0

    def ink_average(img: Image.Image) -> np.ndarray:
        img = Image.fromarray(min3x3(np.asarray(img)))
        only_ink = Image.composite(img, Image.new(img.mode, img.size, 0), ink_img)
        num = np.asarray(only_ink.resize(fsize, Image.Resampling.BOX), dtype=np.float32)
        d = np.maximum(den, 1e-6)
        return np.clip(num / (d[..., None] if num.ndim == 3 else d), 0, 255)

    stencil_ink = ink
    use_fg_image = text_color
    ink_gray = None
    if not text_color and ink.any():
        ink_gray = ink_average(Image.fromarray(gray_m))
        light = has & (ink_gray > 150)
        light_share = float(den[light].sum() / max(den[has].sum(), 1e-6))
        if light_share > 0.03:
            use_fg_image = True  # grey labels / watermarks: keep their real tone
        else:
            up = np.asarray(Image.fromarray(light).resize(msize, Image.Resampling.NEAREST))
            stencil_ink = ink & ~up  # faint marks stay in the background layer

    mask_bytes = ccitt_g4(stencil_ink) if stencil_ink.any() else None
    if mask_bytes is not None:
        if use_fg_image:
            if text_color:
                fg = ink_average(work_m.convert("RGB"))
                lum = fg.mean(axis=2)
                neutral_dark = (fg.max(axis=2) - fg.min(axis=2) < 35) & (lum < 130)
                fg[neutral_dark] *= 0.7  # print-black text reads better slightly darker
                fill = tuple(float(np.median(fg[has][..., c])) if has.any() else 0 for c in range(3))
                fg_img = Image.fromarray(fill_holes(fg, has, fill), "RGB")
            else:
                if ink_gray is None:
                    ink_gray = ink_average(Image.fromarray(gray_m))
                fg = np.where(ink_gray < 130, ink_gray * 0.7, ink_gray)
                fg_img = Image.fromarray(fill_holes(fg, has, 0), "L")
            layers_fg = Layer("masked", full, jpeg=jpeg(fg_img, lv.fg_q), size=(fw, fh),
                              gray=fg_img.mode == "L", mask=mask_bytes, mask_size=msize)
        else:
            dark = gray_m[stencil_ink]
            tone = float(np.percentile(dark, 30)) * 0.6 / 255 if dark.size else 0.0
            layers_fg = Layer("stencil", full, mask=mask_bytes, mask_size=msize, fill=(tone,))
    else:
        layers_fg = None

    # ---- background
    if color_mode != "bw":
        bdpi = min(lv.bg_dpi, mdpi)
        bsize = _px(w_in, h_in, bdpi)
        bg_src = work if text_color else (work if work.mode == "L" else work.convert("L"))
        bg = np.asarray(resize(bg_src, bsize))
        cover = np.asarray(Image.fromarray(stencil_ink.astype(np.float32), "F").resize(
            bsize, Image.Resampling.BOX)) > 0.02
        cover = dilate(cover, 1)
        for x0, y0, x1, y1 in an.photo_boxes:
            cover[int(y0 * bdpi): int(y1 * bdpi) + 1, int(x0 * bdpi): int(x1 * bdpi) + 1] = True
        default = (255, 255, 255) if bg.ndim == 3 else 255
        filled = fill_holes(bg, ~cover, default)
        if not (filled >= 250).mean() > 0.995:
            bg_img = Image.fromarray(filled)
            layers.append(Layer("image", full, jpeg=jpeg(bg_img, lv.bg_q), size=bg_img.size,
                                gray=bg_img.mode == "L"))

    # ---- photos
    pdpi = min(lv.photo_dpi, dpi)
    photo_src = work if (photo_color or work.mode == "L") else work.convert("L")
    if color_mode == "bw" or not photo_color:
        photo_src = photo_src.convert("L") if photo_src.mode != "L" else photo_src
    for x0, y0, x1, y1 in an.photo_boxes:
        crop = photo_src.crop((round(x0 * dpi), round(y0 * dpi), round(x1 * dpi), round(y1 * dpi)))
        crop = resize(crop, _px(x1 - x0, y1 - y0, pdpi))
        q = lv.photo_q if color_mode != "bw" else max(30, lv.photo_q - 15)
        layers.append(Layer("image", (x0, y0, x1, y1), jpeg=jpeg(crop, q), size=crop.size,
                            gray=crop.mode == "L"))

    if layers_fg is not None:
        if color_mode == "bw" and layers_fg.kind == "masked":
            layers_fg = Layer("stencil", full, mask=ccitt_g4(ink), mask_size=msize, fill=(0.0,))
        layers.append(layers_fg)
    return layers
