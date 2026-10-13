import io

import pymupdf
import pytest

from tests import samples


@pytest.fixture(scope="session")
def scan_pdf(tmp_path_factory) -> str:
    """Two-page colour scan at 150 dpi stored losslessly (~5 MB)."""
    path = tmp_path_factory.mktemp("s") / "scan.pdf"
    doc = pymupdf.open()
    for i in range(2):
        img = samples.scan_page(i, dpi=150, photo=i == 1)
        buf = io.BytesIO()
        img.save(buf, "PNG", compress_level=1)
        page = doc.new_page(width=595.3, height=841.9)
        page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(path)
    return str(path)


@pytest.fixture(scope="session")
def digital_pdf(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("d") / "statement.pdf"
    samples.write_digital_pdf(str(path), pages=2)
    return str(path)


@pytest.fixture(scope="session")
def phone_jpg(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("p") / "photo.jpg"
    samples.phone_photo(3).save(path, quality=92)
    return str(path)


@pytest.fixture(scope="session")
def locked_pdf(tmp_path_factory, digital_pdf) -> str:
    path = tmp_path_factory.mktemp("l") / "locked.pdf"
    doc = pymupdf.open(digital_pdf)
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="1234", owner_pw="owner")
    return str(path)


@pytest.fixture(autouse=True)
def _storage(settings, tmp_path):
    settings.DOCFIT_STORAGE = tmp_path / "storage"
    from django.core.cache import cache

    cache.clear()  # rate-limit counters
