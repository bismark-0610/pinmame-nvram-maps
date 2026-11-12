#!/usr/bin/env python3
"""
pdf_to_docx.py - turn a PDF back into an editable Word (.docx) document.

It rebuilds paragraphs, fonts, bold/italic, tables and images from the PDF
using the pdf2docx library, and keeps the page layout as close as it can.

Install once:   pip install pdf2docx
Usage:
  python3 pdf_to_docx.py book.pdf                  # writes book.docx
  python3 pdf_to_docx.py book.pdf -o edited.docx
  python3 pdf_to_docx.py book.pdf --pages 1-20     # only some pages (1-based)
  python3 pdf_to_docx.py book.pdf --check          # report only, write nothing
  python3 pdf_to_docx.py book.pdf --margins 1      # 1-inch margins on every page

What to expect
  - Text made in Word/Google Docs and exported to PDF converts well.
  - Photos come back as pictures.  If the PDF was shrunk with shrink_pdf.py
    the photos stay at the smaller size.
  - Pages that are only a scanned picture (no selectable text) come back as
    a picture, not as editable text.  The tool lists those pages so you know.
  - Complex layouts (text wrapped around photos, captions in text boxes,
    multi-column pages) may need some tidying by hand afterwards.
  - pdf2docx guesses margins page by page, so they can differ from page to
    page.  By default this tool then gives every page the same (most common)
    margins; use --margins 1 to choose them, or --margins keep to skip this.
  - Always keep your original .docx if you still have it: converting
    Word -> PDF -> Word is never perfectly lossless.
"""
import argparse
import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import fitz  # PyMuPDF, installed with pdf2docx
    from pdf2docx import Converter
except ImportError:
    sys.exit("Needs one library:  pip install pdf2docx")


def parse_pages(spec, n):
    """'1-3,7' -> [0,1,2,6] (0-based), checked against the page count."""
    pages = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        lo, hi = int(a), int(b or a)
        if not (1 <= lo <= hi <= n):
            sys.exit(f"Page range '{part}' is outside 1-{n}.")
        pages.extend(range(lo - 1, hi))
    return pages


def survey(pdf_path, pages):
    doc = fitz.open(pdf_path)
    scanned, images, words = [], 0, 0
    for i in pages:
        p = doc[i]
        w = len(p.get_text("words"))
        words += w
        images += len(p.get_images(full=True))
        if w < 5 and p.get_images():
            scanned.append(i + 1)
    return words, images, scanned


def even_margins(docx_path, how):
    """Give every section (pdf2docx makes one per page) the same margins.

    how = "auto": most common left and top margins, mirrored, kept to 0.5-1.5in
    how = a number: that many inches on all four sides
    """
    from collections import Counter
    from docx import Document
    from docx.shared import Inches

    doc = Document(str(docx_path))
    secs = doc.sections
    if how == "auto":
        # pdf2docx's per-page guesses are noisy (e.g. a right margin of 0), so use
        # the most common left and top margins, mirrored to right and bottom,
        # and keep them within 0.5-1.5 inches.
        def r(x):  # EMU -> inches rounded to 0.05
            return round((x or 0) / 914400 * 20) / 20
        def clamp(v):
            return min(1.5, max(0.5, v))
        side = clamp(Counter(r(s.left_margin) for s in secs).most_common(1)[0][0])
        tb = clamp(Counter(r(s.top_margin) for s in secs).most_common(1)[0][0])
        top = bottom = Inches(tb)
        left = right = Inches(side)
        label = f"top/bottom {tb}in, left/right {side}in"
    else:
        top = bottom = left = right = Inches(float(how))
        label = f"{float(how)}in on all sides"
    for s in secs:
        s.top_margin, s.bottom_margin, s.left_margin, s.right_margin = top, bottom, left, right
    doc.save(str(docx_path))
    return len(secs), label


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--pages", help="pages to convert, e.g. 1-10 or 1-3,8 (default: all)")
    ap.add_argument("--check", action="store_true", help="only report what is in the PDF")
    ap.add_argument("--margins", default="auto",
                    help='"auto" (default): same margins on every page, using the most common ones; '
                         'a number such as 1 or 0.75: that many inches on all sides; '
                         '"keep": leave the per-page margins pdf2docx guessed')
    a = ap.parse_args()

    if a.margins not in ("auto", "keep"):
        try:
            if not 0 <= float(a.margins) <= 3:
                raise ValueError
        except ValueError:
            sys.exit('--margins must be "auto", "keep", or inches between 0 and 3 (e.g. 1 or 0.75).')
    if not a.pdf.exists():
        sys.exit(f"Not found: {a.pdf}")
    with fitz.open(a.pdf) as d:
        n = d.page_count
        if d.needs_pass:
            sys.exit("This PDF is password-protected; remove the password first.")
    pages = parse_pages(a.pages, n) if a.pages else list(range(n))
    words, images, scanned = survey(a.pdf, pages)
    print(f"{a.pdf.name}: {len(pages)} of {n} pages, ~{words} words, {images} images")
    if scanned:
        print(f"  pages with no selectable text (will come back as pictures, not text): "
              f"{', '.join(map(str, scanned))}")
    if a.check:
        return

    out = a.output or a.pdf.with_suffix(".docx")
    if out.resolve() == a.pdf.resolve():
        sys.exit("Output must be a different file.")
    logging.disable(logging.WARNING)  # pdf2docx is chatty
    print("converting... (about 1-2 seconds per page)")
    cv = Converter(str(a.pdf))
    try:
        cv.convert(str(out), pages=pages)
    finally:
        cv.close()
    if a.margins != "keep":
        n_sec, label = even_margins(out, a.margins)
        print(f"margins made the same on all {n_sec} page section(s): {label}")
    print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
