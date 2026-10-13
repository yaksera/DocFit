from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

ColorMode = Literal["auto", "color", "gray", "bw"]
OutputFormat = Literal["pdf", "jpg"]
ProgressFn = Callable[[float, str], None]


class EngineError(Exception):
    """An error whose message is safe to show to the end user."""


class PasswordRequired(EngineError):
    pass


@dataclass
class CompressOptions:
    target_bytes: int = 4 * 1024 * 1024
    color_mode: ColorMode = "auto"
    output_format: OutputFormat = "pdf"
    clean_background: bool = True  # whiten paper, remove yellow tint and shadows
    password: Optional[str] = None
    max_pages: Optional[int] = None
    # Safety margin so files land a little under the portal limit, not exactly on it.
    margin: float = 0.97

    @property
    def budget(self) -> int:
        return int(self.target_bytes * self.margin)


@dataclass
class CompressResult:
    output_path: str
    original_bytes: int
    output_bytes: int
    pages: int
    met_target: bool
    level: Optional[int]
    text_quality: str
    content_type: str
    warnings: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.original_bytes / max(self.output_bytes, 1)
