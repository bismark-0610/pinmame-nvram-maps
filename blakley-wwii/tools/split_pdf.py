#!/usr/bin/env python3
"""
split_pdf.py - split a large PDF into parts small enough to upload to Claude.

Each part is cut at page boundaries and kept under BOTH a page limit and a
file-size limit.  Part files are named so they sort in order and say which
original pages they hold, e.g.

  Letters to Ludie.part01-of-04 (p1-100).pdf
  Letters to Ludie.part02-of-04 (p101-187).pdf

Install once:   pip install pikepdf
Usage:
  python3 split_pdf.py book.pdf                         # defaults: 100 pages / 25 MB
  python3 split_pdf.py book.pdf --max-pages 50 --max-mb 10
  python3 split_pdf.py book.pdf --out-dir parts/
  python3 split_pdf.py book.pdf --dry-run               # show the plan only

Defaults are deliberately conservative so every part works for full
(page-image + text) reading in the Claude apps and the API.  Documented API
limits at the time of writing are 32 MB per request and up to 600 pages per
PDF (100 pages for some models); the Claude apps have their own upload size
cap, so if an upload is refused, lower --max-mb.

Tip: if parts come out with very few pages because of big photos, run
shrink_pdf.py first - it usually cuts the size 70-95% without visible loss.
When you upload several parts to one chat, say "this is part 2 of 4, pages
101-187" so page references stay correct.
"""
import argparse
import io
import sys
from pathlib import Path

try:
    import pikepdf
except ImportError:
    sys.exit("Needs one library:  pip install pikepdf")


def build(src, start, end):
    """Return bytes of a PDF containing pages [start, end) of src."""
    out = pikepdf.new()
    out.pages.extend(src.pages[start:end])
    buf = io.BytesIO()
    out.remove_unreferenced_resources()
    out.save(buf, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return buf.getvalue()


def plan(src, max_pages, max_bytes):
    """Greedy split: as many pages as fit both limits; binary search on size."""
    n, parts, start = len(src.pages), [], 0
    while start < n:
        hi = min(n, start + max_pages)
        data = build(src, start, hi)
        if len(data) > max_bytes:
            lo_ok, lo, top = start + 1, start + 1, hi - 1
            best = None
            while lo <= top:  # largest end with size <= limit
                mid = (lo + top) // 2
                d = build(src, start, mid)
                if len(d) <= max_bytes:
                    best, lo_ok, lo = d, mid, mid + 1
                else:
                    top = mid - 1
            if best is None:  # a single page is over the limit: keep it alone
                hi, data = start + 1, build(src, start, start + 1)
                print(f"  warning: page {start+1} alone is {len(data)/1e6:.1f} MB "
                      f"(over the limit) - run shrink_pdf.py first", file=sys.stderr)
            else:
                hi, data = lo_ok, best
        parts.append((start, hi, data))
        start = hi
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--max-pages", type=int, default=100, help="pages per part (default 100)")
    ap.add_argument("--max-mb", type=float, default=25, help="MB per part (default 25)")
    ap.add_argument("--out-dir", type=Path, help="folder for the parts (default: next to the PDF)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; write nothing")
    a = ap.parse_args()
    if a.max_pages < 1 or a.max_mb <= 0:
        sys.exit("--max-pages and --max-mb must be positive.")

    src = pikepdf.open(a.pdf)
    n = len(src.pages)
    size = a.pdf.stat().st_size
    print(f"{a.pdf.name}: {n} pages, {size/1e6:.1f} MB; limits {a.max_pages} pages / {a.max_mb:g} MB per part")
    if n <= a.max_pages and size <= a.max_mb * 1e6:
        print("Already within both limits - no split needed.")
        return
    parts = plan(src, a.max_pages, int(a.max_mb * 1e6))
    out_dir = a.out_dir or a.pdf.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    k = len(parts)
    w = max(2, len(str(k)))
    for i, (s, e, data) in enumerate(parts, 1):
        pages = f"p{s+1}" if e - s == 1 else f"p{s+1}-{e}"
        name = f"{a.pdf.stem}.part{i:0{w}d}-of-{k:0{w}d} ({pages}).pdf"
        print(f"  {name}: {e-s} pages, {len(data)/1e6:.1f} MB")
        if not a.dry_run:
            (out_dir / name).write_bytes(data)
    print(f"{k} parts" + (" (dry run, nothing written)" if a.dry_run else f" written to {out_dir}"))


if __name__ == "__main__":
    main()
