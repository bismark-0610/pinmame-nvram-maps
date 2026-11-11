#!/usr/bin/env python3
"""
Second-opinion OCR for faint morning-report pages.

NARA's own OCR misses names on faint or damaged frames.  This runs an
independent engine (RapidOCR) on the auto-contrast/sharpened JPEGs that
`nara_mr.py download --jpeg` writes, then fuzzy-matches a surname and serial
number so near-misses ("Blaklev", "3486404?") are still flagged for a human
to look at.  It never decides anything by itself: every flag must be checked
against the image.

usage: reocr.py IMAGE_DIR [IMAGE_DIR ...] --name BLAKLEY --serial 34864047 [--out reocr.csv]
"""
import argparse
import csv
import difflib
import re
from pathlib import Path

from PIL import Image


def serial_distance(token, serial):
    digits = re.sub(r"\D", "", token)
    if abs(len(digits) - len(serial)) > 1 or len(digits) < 6:
        return 99
    return sum(a != b for a, b in zip(digits.ljust(len(serial)), serial)) + abs(len(digits) - len(serial))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--serial", required=True)
    ap.add_argument("--out", type=Path, default=Path("reocr.csv"))
    ap.add_argument("--min-ratio", type=float, default=0.72)
    a = ap.parse_args()

    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    name = a.name.upper()
    rows = []
    for d in a.dirs:
        for jpg in sorted(d.glob("*.enh.jpg")):
            txt_path = jpg.with_suffix(".reocr.txt")
            if txt_path.exists():
                lines = txt_path.read_text().splitlines()
            else:
                im = Image.open(jpg)
                if max(im.size) > 3200:
                    im.thumbnail((3200, 3200))
                    tmp = jpg.with_suffix(".tmp.jpg")
                    im.save(tmp, quality=90)
                    result, _ = engine(str(tmp))
                    tmp.unlink()
                else:
                    result, _ = engine(str(jpg))
                lines = [r[1] for r in (result or [])]
                txt_path.write_text("\n".join(lines))
            flags = []
            for ln in lines:
                for tok in re.findall(r"[A-Za-z]{4,}", ln):
                    r = difflib.SequenceMatcher(None, tok.upper(), name).ratio()
                    if r >= a.min_ratio:
                        flags.append(f"name~{tok}({r:.2f}): {ln}")
                for tok in re.findall(r"[\d ,.]{7,12}", ln):
                    if serial_distance(tok, a.serial) <= 2:
                        flags.append(f"serial~{tok.strip()}: {ln}")
            rows.append({"image": str(jpg), "lines": len(lines), "flags": " || ".join(flags)})
            print(f"{jpg.name}: {len(lines)} lines, {len(flags)} flags", flush=True)
            for f in flags:
                print("    ", f)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "lines", "flags"])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
