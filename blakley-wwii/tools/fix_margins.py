#!/usr/bin/env python3
"""
fix_margins.py - give every page of a Word (.docx) file the same margins.

Useful when margins jump around from page to page, which usually happens
after converting a PDF to Word or pasting from other documents (each
section can carry its own margins).  The original file is never changed.

Install once:   pip install python-docx
Usage:
  python3 fix_margins.py "Letters to Ludie v2.docx" -o "Letters to Ludie v3.docx"
  python3 fix_margins.py book.docx --margins 1        # 1 inch on every side
  python3 fix_margins.py book.docx --margins auto     # most common margins (default)
  python3 fix_margins.py book.docx --report           # list margins per section only
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Inches
except ImportError:
    sys.exit("Needs one library:  pip install python-docx")

EMU_PER_IN = 914400


def inch(x):
    return round((x or 0) / EMU_PER_IN, 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path)
    ap.add_argument("-o", "--output", type=Path, help='output file (default: "<name> (margins fixed).docx")')
    ap.add_argument("--margins", default="auto",
                    help='"auto" (default) or inches on all sides, e.g. 1 or 0.75')
    ap.add_argument("--report", action="store_true", help="only show the current margins")
    a = ap.parse_args()

    doc = Document(str(a.docx))
    secs = doc.sections
    rows = [(inch(s.top_margin), inch(s.bottom_margin), inch(s.left_margin), inch(s.right_margin)) for s in secs]
    distinct = Counter(rows)
    print(f"{a.docx.name}: {len(secs)} section(s), {len(distinct)} different margin setting(s)")
    for m, n in distinct.most_common():
        print(f"  top {m[0]}  bottom {m[1]}  left {m[2]}  right {m[3]} (inches): {n} section(s)")
    if a.report:
        return

    if a.margins == "auto":
        clamp = lambda v: min(1.5, max(0.5, round(v * 20) / 20))
        side = clamp(Counter(r[2] for r in rows).most_common(1)[0][0])
        tb = clamp(Counter(r[0] for r in rows).most_common(1)[0][0])
    else:
        try:
            side = tb = float(a.margins)
            if not 0 <= side <= 3:
                raise ValueError
        except ValueError:
            sys.exit('--margins must be "auto" or inches between 0 and 3.')
    for s in secs:
        s.top_margin = s.bottom_margin = Inches(tb)
        s.left_margin = s.right_margin = Inches(side)

    out = a.output or a.docx.with_name(a.docx.stem + " (margins fixed).docx")
    if out.resolve() == a.docx.resolve():
        sys.exit("Choose a different output name; the original is never overwritten.")
    doc.save(str(out))
    print(f"wrote {out}: top/bottom {tb}in, left/right {side}in on all {len(secs)} section(s)")


if __name__ == "__main__":
    main()
