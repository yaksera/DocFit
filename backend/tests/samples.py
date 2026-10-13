"""Synthetic but realistic test documents (noisy scans, phone photos, digital PDFs)."""
from __future__ import annotations

import io
import math
import os
import random

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONT_DIRS = [r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF",
              "/Library/Fonts"]
_FONT_FILES = {"regular": ["arial.ttf", "DejaVuSans.ttf"], "bold": ["arialbd.ttf", "DejaVuSans-Bold.ttf"],
               "serif": ["times.ttf", "DejaVuSerif.ttf"]}

WORDS = ("the of and to in student semester credit grade university faculty examination board "
         "record certified science management total marks obtained division first second passed "
         "registration number campus programme bachelor master year subject theory practical").split()


def font(kind: str, px: int) -> ImageFont.FreeTypeFont:
    for d in _FONT_DIRS:
        for name in _FONT_FILES[kind]:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return ImageFont.truetype(p, px)
    return ImageFont.load_default(size=px)


def _portrait(w: int, h: int, rnd: np.random.Generator) -> Image.Image:
    base = rnd.random((max(2, h // 40), max(2, w // 40), 3)) * 80 + 90
    img = Image.fromarray(base.astype(np.uint8)).resize((w, h), Image.Resampling.BICUBIC)
    d = ImageDraw.Draw(img)
    d.ellipse([w * 0.2, h * 0.08, w * 0.8, h * 0.62], fill=(205, 160, 130))  # face
    d.pieslice([w * 0.15, h * 0.0, w * 0.85, h * 0.5], 180, 360, fill=(40, 30, 25))  # hair
    d.ellipse([w * 0.05, h * 0.6, w * 0.95, h * 1.3], fill=(30, 50, 110))  # shirt
    arr = np.asarray(img.filter(ImageFilter.GaussianBlur(w / 120)), dtype=np.float32)
    arr += rnd.normal(0, 7, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def scan_page(seed: int = 0, dpi: int = 300, photo: bool = False, size_in=(8.27, 11.69)) -> Image.Image:
    """A colour scan of a transcript-like page: tinted noisy paper, text, table,
    blue signature, red stamp, optional passport photo."""
    rng = random.Random(seed)
    rnd = np.random.default_rng(seed)
    W, H = round(size_in[0] * dpi), round(size_in[1] * dpi)
    s = dpi / 300
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_title, f_head = font("bold", int(64 * s)), font("bold", int(42 * s))
    f_body, f_small = font("serif", int(40 * s)), font("regular", int(30 * s))
    m = int(170 * s)
    d.ellipse([m, m, m + 220 * s, m + 220 * s], outline=(150, 20, 30), width=int(10 * s))  # logo
    d.text((m + 270 * s, m + 30 * s), "TRIBHUVAN UNIVERSITY", font=f_title, fill=(20, 20, 20))
    d.text((m + 270 * s, m + 120 * s), "Office of the Controller of Examinations",
           font=f_head, fill=(30, 30, 30))
    y = m + 330 * s
    if photo:
        ph = _portrait(int(413 * s), int(531 * s), rnd)
        img.paste(ph, (W - m - ph.width, int(y)))
    d.text((m, y), "TRANSCRIPT OF ACADEMIC RECORD", font=f_head, fill=(20, 20, 20))
    y += 90 * s
    for label in ("Name: Sita Kumari Shrestha", f"Registration No: 5-2-{rng.randint(100, 999)}-"
                  f"{rng.randint(10, 99)}-2019", "Programme: Bachelor of Business Studies"):
        d.text((m, y), label, font=f_body, fill=(25, 25, 25))
        y += 62 * s
    y += 30 * s
    # table
    cols = [m, m + 260 * s, m + 1250 * s, m + 1550 * s, W - m]
    d.rectangle([m, y, W - m, y + 66 * s], fill=(210, 210, 210))
    for x, t in zip(cols, ("Code", "Subject", "Credit", "Grade")):
        d.text((x + 16 * s, y + 12 * s), t, font=f_body, fill=(10, 10, 10))
    rows = 13 if not photo else 10
    for r in range(rows + 1):
        yy = y + 66 * s * (r + 1)
        d.line([m, yy, W - m, yy], fill=(40, 40, 40), width=max(1, int(3 * s)))
        if r < rows:
            subj = " ".join(rng.choice(WORDS).title() for _ in range(rng.randint(2, 4)))
            for x, t in zip(cols, (f"MGT{rng.randint(201, 499)}", subj, str(rng.choice([3, 3, 2])),
                                   rng.choice(["A", "A-", "B+", "B", "B-"]))):
                d.text((x + 16 * s, yy + 12 * s), t, font=f_body, fill=(25, 25, 25))
    for x in cols:
        d.line([x, y, x, y + 66 * s * (rows + 1)], fill=(40, 40, 40), width=max(1, int(3 * s)))
    y += 66 * s * (rows + 1) + 60 * s
    while y < H - 700 * s:
        line = " ".join(rng.choice(WORDS) for _ in range(14)).capitalize() + "."
        d.text((m, y), line, font=f_small, fill=(35, 35, 35))
        y += 46 * s
    # blue signature and red stamp
    sx, sy = W - m - 520 * s, H - 560 * s
    pts = [(sx + t * 4.5 * s, sy + 60 * s * math.sin(t / 9) + 25 * s * math.sin(t / 2.3)) for t in range(110)]
    d.line(pts, fill=(25, 45, 160), width=int(6 * s), joint="curve")
    d.text((sx, sy + 120 * s), "Controller of Examinations", font=f_small, fill=(25, 25, 25))
    cx, cy, r = m + 260 * s, H - 470 * s, 190 * s
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(190, 30, 40), width=int(9 * s))
    d.ellipse([cx - r * .72, cy - r * .72, cx + r * .72, cy + r * .72], outline=(190, 30, 40), width=int(5 * s))
    d.text((cx - 120 * s, cy - 20 * s), "VERIFIED", font=f_head, fill=(190, 30, 40))

    # scanner look: slight blur, tinted paper, uneven light, noise
    img = img.filter(ImageFilter.GaussianBlur(0.9 * s))
    arr = np.asarray(img, dtype=np.float32) / 255
    paper = np.array([246, 238, 220], np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    light = 1 - 0.10 * (xx / W) - 0.06 * ((yy - H / 2) / H) ** 2
    out = arr * paper * light[..., None]
    out += rnd.normal(0, 5, out.shape).astype(np.float32)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def phone_photo(seed: int = 0) -> Image.Image:
    """A 4000x3000 phone photo of a document lying on a table, with a shadow."""
    page = scan_page(seed, dpi=330, photo=False)
    W, H = 3000, 4000
    table = np.zeros((H, W, 3), np.float32) + np.array([120, 85, 60], np.float32)
    rnd = np.random.default_rng(seed)
    table += rnd.normal(0, 10, table.shape)
    canvas = Image.fromarray(np.clip(table, 0, 255).astype(np.uint8))
    page = page.resize((2700, round(2700 * page.height / page.width)))
    canvas.paste(page, (150, 120))
    arr = np.asarray(canvas, np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    shadow = 1 - 0.35 * np.clip((xx + yy * 0.6 - 2600) / 1400, 0, 1)
    arr *= shadow[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def write_scan_pdf(path: str, pages: int = 4, dpi: int = 300, photo_on=(1,)) -> None:
    doc = pymupdf.open()
    for i in range(pages):
        img = scan_page(i, dpi=dpi, photo=i in photo_on)
        buf = io.BytesIO()
        img.save(buf, "PNG", compress_level=1)
        page = doc.new_page(width=595.3, height=841.9)
        page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(path)


def write_digital_pdf(path: str, pages: int = 3) -> None:
    rnd = np.random.default_rng(3)
    logo = Image.fromarray((rnd.random((1000, 3000, 3)) * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(3))
    buf = io.BytesIO()
    logo.save(buf, "PNG")
    doc = pymupdf.open()
    for p in range(pages):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(40, 30, 300, 117), stream=buf.getvalue())
        page.insert_text((40, 150), f"ACCOUNT STATEMENT - page {p + 1}", fontsize=16, fontname="helv")
        y = 180
        for r in range(40):
            page.draw_line((40, y + 4), (555, y + 4), color=(0.7, 0.7, 0.7), width=0.5)
            page.insert_text((40, y), f"2026-0{1 + r % 9}-{10 + r % 18}   Transfer ref {100000 + r * 37}"
                             f"      NPR {r * 1234.5:>12,.2f}", fontsize=9, fontname="cour")
            y += 15
    doc.save(path)


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "samples"
    os.makedirs(out, exist_ok=True)
    write_scan_pdf(os.path.join(out, "transcript_scan.pdf"), pages=4)
    phone_photo(7).save(os.path.join(out, "phone_photo.jpg"), quality=95)
    write_digital_pdf(os.path.join(out, "bank_statement.pdf"))
    p = _portrait(1200, 1500, np.random.default_rng(1))
    p.save(os.path.join(out, "passport_photo.jpg"), quality=97, dpi=(300, 300))
    for f in sorted(os.listdir(out)):
        print(f, os.path.getsize(os.path.join(out, f)) // 1000, "KB")
