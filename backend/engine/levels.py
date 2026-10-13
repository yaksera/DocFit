"""Quality ladder used by the target-size search.

Level 0 is the best quality. Each later level trades a little quality for a
smaller file. The search picks the best level whose output still fits the
user's size limit.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    index: int
    mask_dpi: int  # resolution of the 1-bit text layer (what keeps text sharp)
    bg_dpi: int  # paper / background layer
    bg_q: int
    fg_dpi: int  # colour of the text (blue pen, red stamp, ...)
    fg_q: int
    photo_dpi: int  # photos inside documents, and photo-like pages
    photo_q: int
    img_dpi: int  # images embedded in digital (non-scanned) PDFs
    img_q: int
    force_gray: bool = False

    @property
    def text_quality(self) -> str:
        if self.mask_dpi >= 250:
            return "excellent"
        if self.mask_dpi >= 200:
            return "very good"
        if self.mask_dpi >= 150:
            return "good"
        return "fair"


LEVELS: list[Level] = [
    Level(0, 300, 150, 72, 100, 70, 220, 84, 220, 85),
    Level(1, 300, 120, 64, 75, 62, 180, 78, 180, 78),
    Level(2, 300, 100, 56, 60, 55, 150, 72, 150, 72),
    Level(3, 250, 85, 50, 50, 50, 130, 65, 130, 66),
    Level(4, 200, 72, 44, 45, 45, 115, 58, 110, 58),
    Level(5, 200, 60, 38, 40, 40, 96, 50, 96, 50),
    Level(6, 150, 50, 34, 30, 36, 80, 42, 80, 42),
    Level(7, 150, 40, 30, 25, 32, 68, 36, 72, 36, force_gray=True),
    Level(8, 120, 32, 26, 20, 30, 56, 30, 60, 30, force_gray=True),
]
