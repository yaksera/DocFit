"""Page previews for the before/after comparison view."""
import io
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

from engine.sources import MUPDF_LOCK

MAX_WIDTH = 1800


class PreviewUnavailable(Exception):
    pass


def _encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _render_pdf(path: Path, index: int, width: int) -> tuple[bytes | None, int]:
    """Returns (jpeg or None if index is past the end, page_count)."""
    with MUPDF_LOCK:
        doc = pymupdf.open(path)
        try:
            if doc.needs_pass:
                raise PreviewUnavailable("Preview is not available for password-protected files.")
            n = doc.page_count
            if index >= n:
                return None, n
            page = doc[index]
            zoom = min(width, MAX_WIDTH) / max(page.rect.width, 1)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False, colorspace=pymupdf.csRGB)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        finally:
            doc.close()
    return _encode(img), n


def _render_image(src, index: int, width: int) -> tuple[bytes | None, int]:
    with Image.open(src) as im:
        n = getattr(im, "n_frames", 1)
        if index >= n:
            return None, n
        if index:
            im.seek(index)
        img = ImageOps.exif_transpose(im) if index == 0 else im.copy()
        img = img.convert("RGB")
    img.thumbnail((min(width, MAX_WIDTH), min(width, MAX_WIDTH) * 3))
    return _encode(img), n


def _is_pdf(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"


def render_sequence(paths: list[Path], page: int, width: int) -> bytes:
    """Render page `page` (0-based) counting across all files in order."""
    index = page
    for path in paths:
        data, n = (_render_pdf if _is_pdf(path) else _render_image)(path, index, width)
        if data is not None:
            return data
        index -= n
    raise PreviewUnavailable("Page not found.")


def render_output(path: Path, page: int, width: int) -> bytes:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            names = sorted(z.namelist())
            if page >= len(names):
                raise PreviewUnavailable("Page not found.")
            data, _ = _render_image(io.BytesIO(z.read(names[page])), 0, width)
            return data
    return render_sequence([path], page, width)
