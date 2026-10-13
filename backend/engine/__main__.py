"""Command line: python -m engine scan.pdf -t 4MB -o scan-small"""
import argparse
import os
import sys
import time

from . import CompressOptions, EngineError, compress, human, parse_size


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m engine",
                                 description="Shrink documents under an upload size limit.")
    ap.add_argument("inputs", nargs="+", help="PDF or image files (merged in this order)")
    ap.add_argument("-t", "--target", default="4MB", help="size limit, e.g. 500KB, 2MB (default 4MB)")
    ap.add_argument("-o", "--output", help="output path without extension")
    ap.add_argument("-m", "--mode", choices=["auto", "color", "gray", "bw"], default="auto")
    ap.add_argument("-f", "--format", choices=["pdf", "jpg"], default="pdf")
    ap.add_argument("--keep-background", action="store_true", help="don't whiten the paper")
    ap.add_argument("--password", help="password for protected PDFs")
    a = ap.parse_args()

    base = a.output or os.path.splitext(a.inputs[0])[0] + "-docfit"
    opts = CompressOptions(target_bytes=parse_size(a.target), color_mode=a.mode,
                           output_format=a.format, clean_background=not a.keep_background,
                           password=a.password)
    t0 = time.time()

    def progress(frac: float, msg: str) -> None:
        print(f"\r[{frac * 100:5.1f}%] {msg:<40}", end="", file=sys.stderr, flush=True)

    try:
        r = compress(a.inputs, base, opts, progress)
    except EngineError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    print(file=sys.stderr)
    print(f"{r.output_path}\n  {human(r.original_bytes)} -> {human(r.output_bytes)} "
          f"({r.ratio:.1f}x smaller), {r.pages} page(s), text quality: {r.text_quality}, "
          f"level {r.level}, {'fits' if r.met_target else 'DOES NOT FIT'}, {time.time() - t0:.1f}s")
    for w in r.warnings:
        print(f"  ! {w}")
    return 0 if r.met_target else 2


if __name__ == "__main__":
    sys.exit(main())
