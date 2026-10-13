import os
import zipfile

import numpy as np
import pymupdf
import pytest
from PIL import Image

from engine import CompressOptions, EngineError, PasswordRequired, compress, parse_size
from engine.raster import ccitt_g4


def _render(path, page=0, dpi=100):
    doc = pymupdf.open(path)
    pix = doc[page].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)


def test_parse_size():
    assert parse_size("4MB") == 4_000_000
    assert parse_size("500 kb") == 500_000
    assert parse_size("1.5M") == 1_500_000
    with pytest.raises(ValueError):
        parse_size("lots")


def test_ccitt_mask_paints_ink_not_background(tmp_path):
    """Guards the bit polarity of the text layer: ink must be dark, paper white."""
    from engine.pdfwriter import PdfAssembler
    from engine.raster import Layer

    ink = np.zeros((200, 300), bool)
    ink[50:150, 100:200] = True
    asm = PdfAssembler()
    asm.add_layers_page(3, 2, [Layer("stencil", (0, 0, 3, 2), mask=ccitt_g4(ink), mask_size=(300, 200),
                                     fill=(0.0,))])
    out = tmp_path / "m.pdf"
    out.write_bytes(asm.tobytes())
    g = _render(out, dpi=100)
    assert g[100, 150] < 30  # ink
    assert g[10, 10] > 240  # paper


@pytest.mark.parametrize("target", ["1MB", "250KB", "120KB"])
def test_scan_fits_target_and_stays_readable(scan_pdf, tmp_path, target):
    r = compress([scan_pdf], str(tmp_path / "out"), CompressOptions(target_bytes=parse_size(target)))
    assert r.met_target
    assert os.path.getsize(r.output_path) == r.output_bytes <= parse_size(target)
    assert r.pages == 2
    # Text survives where it was: dark pixels overlap the original's text well.
    src, out = _render(scan_pdf) < 128, _render(r.output_path) < 128
    assert (src & out).sum() / (src | out).sum() > 0.45
    assert np.median(_render(r.output_path)) > 235  # paper cleaned to white


def test_impossible_target_reports_failure(scan_pdf, tmp_path):
    r = compress([scan_pdf], str(tmp_path / "out"), CompressOptions(target_bytes=20_000))
    assert not r.met_target
    assert r.warnings and "Could not get under" in r.warnings[0]
    assert os.path.exists(r.output_path)


def test_digital_pdf_keeps_text(digital_pdf, tmp_path):
    r = compress([digital_pdf], str(tmp_path / "out"), CompressOptions(target_bytes=300_000))
    assert r.met_target
    text = pymupdf.open(r.output_path)[0].get_text()
    assert "ACCOUNT STATEMENT" in text  # still real, selectable text


def test_phone_photo_is_cropped_and_cleaned(phone_jpg, tmp_path):
    r = compress([phone_jpg], str(tmp_path / "out"), CompressOptions(target_bytes=400_000))
    assert r.met_target
    page = pymupdf.open(r.output_path)[0]
    assert abs(page.rect.height / page.rect.width - 1.414) < 0.05  # A4 shape, table cropped away
    g = _render(r.output_path, dpi=40)
    assert np.percentile(g, 50) > 230  # shadow removed, paper white


def test_merge_multiple_inputs(scan_pdf, digital_pdf, phone_jpg, tmp_path):
    r = compress([scan_pdf, digital_pdf, phone_jpg], str(tmp_path / "out"),
                 CompressOptions(target_bytes=2_000_000))
    assert r.pages == 5 and r.met_target


def test_jpg_output_single_and_zip(phone_jpg, scan_pdf, tmp_path):
    r = compress([phone_jpg], str(tmp_path / "one"), CompressOptions(target_bytes=150_000, output_format="jpg"))
    assert r.output_path.endswith(".jpg") and r.output_bytes <= 150_000
    Image.open(r.output_path).verify()
    r = compress([scan_pdf], str(tmp_path / "many"), CompressOptions(target_bytes=150_000, output_format="jpg"))
    assert r.output_path.endswith(".zip")
    with zipfile.ZipFile(r.output_path) as z:
        assert len(z.namelist()) == 2
        assert all(i.file_size <= 150_000 for i in z.infolist())


def test_password_protected(locked_pdf, tmp_path):
    with pytest.raises(PasswordRequired):
        compress([locked_pdf], str(tmp_path / "o"), CompressOptions())
    r = compress([locked_pdf], str(tmp_path / "o"), CompressOptions(password="1234", target_bytes=500_000))
    assert r.met_target
    assert not pymupdf.open(r.output_path).needs_pass  # portals reject encrypted PDFs


def test_bw_and_gray_modes(scan_pdf, tmp_path):
    bw = compress([scan_pdf], str(tmp_path / "bw"), CompressOptions(target_bytes=1_000_000, color_mode="bw"))
    gray = compress([scan_pdf], str(tmp_path / "g"), CompressOptions(target_bytes=1_000_000, color_mode="gray"))
    assert bw.met_target and gray.met_target
    assert bw.output_bytes < gray.output_bytes


def test_rejects_garbage(tmp_path):
    bad = tmp_path / "x.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(EngineError):
        compress([str(bad)], str(tmp_path / "o"), CompressOptions())


def test_max_pages(scan_pdf, tmp_path):
    with pytest.raises(EngineError, match="allows up to 1 pages"):
        compress([scan_pdf], str(tmp_path / "o"), CompressOptions(max_pages=1))
