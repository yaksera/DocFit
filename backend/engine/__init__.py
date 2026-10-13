"""DocFit compression engine (framework independent).

    from engine import compress, CompressOptions
    result = compress(["scan.pdf"], "out/scan-small", CompressOptions(target_bytes=4_000_000))
"""
import re

from .pipeline import compress, human
from .types import CompressOptions, CompressResult, EngineError, PasswordRequired

__all__ = ["compress", "human", "parse_size", "CompressOptions", "CompressResult", "EngineError",
           "PasswordRequired"]

_UNITS = {"": 1, "b": 1, "kb": 1000, "k": 1000, "mb": 1_000_000, "m": 1_000_000}


def parse_size(text: str) -> int:
    """'4MB' -> 4_000_000. Decimal units, the stricter reading of portal limits."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*", text)
    if not m or m.group(2).lower() not in _UNITS:
        raise ValueError(f"Invalid size: {text!r} (use e.g. 500KB or 4MB)")
    return int(float(m.group(1)) * _UNITS[m.group(2).lower()])
