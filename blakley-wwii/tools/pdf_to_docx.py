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

What to expect
  - Text made in Word/Google Docs and exported to PDF converts well.
  - Photos come back as pictures.  If the PDF was shrunk with shrink_pdf.py
    the photos stay at the smaller size.
  - Pages that are only a scanned picture (no selectable text) come back as
    a picture, not as editable text.  The tool lists those pages so you know.
  - Complex layouts (text wrapped around photos, captions in text boxes,
    multi-column pages) may need some tidying by hand afterwards.
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--pages", help="pages to convert, e.g. 1-10 or 1-3,8 (default: all)")
    ap.add_argument("--check", action="store_true", help="only report what is in the PDF")
    a = ap.parse_args()

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
    print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
