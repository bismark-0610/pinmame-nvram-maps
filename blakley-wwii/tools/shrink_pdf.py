#!/usr/bin/env python3
"""
shrink_pdf.py - make a PDF smaller by downsampling photos that have more
resolution than the page needs, and re-compressing them as JPEG.

How it works
  1. Reads every page's drawing instructions to find how large (in inches)
     each image is actually printed on the page.
  2. If an image has more pixels than that size needs at --dpi, it is
     resized down to exactly what is needed.
  3. Photos are re-saved as JPEG at --quality, and the new version is kept
     only if it is really smaller.
  4. Text, vector graphics, fonts, links and bookmarks are left untouched.

Images it deliberately leaves alone: black-and-white (1-bit) scans, palette
images, CMYK images, masks and anything with an unusual color setup.  Those
are rare in photo books and easy to damage.

Install once:   pip install pikepdf pillow
Usage:
  python3 shrink_pdf.py book.pdf                      # writes book.small.pdf
  python3 shrink_pdf.py book.pdf -o book_web.pdf --dpi 150 --quality 75
  python3 shrink_pdf.py book.pdf --dry-run            # report only

Suggested settings
  --dpi 300 --quality 85   home or professional printing (photo books)
  --dpi 200 --quality 80   default: good on screen and fine for most printing
  --dpi 150 --quality 75   email / sharing on screen
"""
import argparse
import io
import math
import sys
import zlib
from pathlib import Path

try:
    import pikepdf
    from pikepdf import Name, PdfImage
    from PIL import Image
except ImportError:
    sys.exit("Needs two libraries:  pip install pikepdf pillow")


def mat_mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
            e * A + f * C + E, e * B + f * D + F)


def find_image_sizes(pdf):
    """Map image object id -> largest printed (width_in, height_in) on any page."""
    sizes = {}

    def walk(stream_owner, resources, ctm, depth=0):
        if depth > 10 or resources is None:
            return
        xobjs = resources.get("/XObject", {})
        stack = []
        try:
            ops = pikepdf.parse_content_stream(stream_owner)
        except Exception:
            return
        for operands, op in ops:
            op = str(op)
            if op == "q":
                stack.append(ctm)
            elif op == "Q":
                ctm = stack.pop() if stack else ctm
            elif op == "cm" and len(operands) == 6:
                ctm = mat_mul(tuple(float(x) for x in operands), ctm)
            elif op == "Do" and operands:
                xo = xobjs.get(operands[0]) if xobjs else None
                if xo is None:
                    continue
                sub = xo.get("/Subtype")
                if sub == "/Image":
                    a, b, c, d = ctm[:4]
                    w_in = math.hypot(a, b) / 72.0
                    h_in = math.hypot(c, d) / 72.0
                    key = xo.objgen
                    ow, oh = sizes.get(key, (0, 0))
                    sizes[key] = (max(ow, w_in), max(oh, h_in))
                elif sub == "/Form":
                    m = tuple(float(x) for x in xo.get("/Matrix", [1, 0, 0, 1, 0, 0]))
                    walk(xo, xo.get("/Resources", resources), mat_mul(m, ctm), depth + 1)

    for page in pdf.pages:
        walk(page, page.obj.get("/Resources"), (1, 0, 0, 1, 0, 0))
    return sizes


def jpeg_bytes(im, quality):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=False)
    return buf.getvalue()


def shrink(src, dst, dpi, quality, dry_run, verbose):
    pdf = pikepdf.open(src)
    sizes = find_image_sizes(pdf)
    stats = {"seen": 0, "resized": 0, "recompressed": 0, "skipped": 0, "saved": 0}
    done = set()
    for page in pdf.pages:
        imgs = page.get_images() if hasattr(page, "get_images") else page.images
        for _, raw in imgs.items():
            key = raw.objgen
            if key in done:
                continue
            done.add(key)
            stats["seen"] += 1
            reason = None
            if raw.get("/ImageMask") or "/Mask" in raw or "/Decode" in raw:
                reason = "mask/decode"
            elif int(raw.get("/BitsPerComponent", 8)) != 8:
                reason = "not 8-bit"
            if reason is None:
                try:
                    im = PdfImage(raw).as_pil_image()
                except Exception as e:
                    reason = f"cannot decode ({type(e).__name__})"
            if reason is None and im.mode in ("RGBA", "LA") and "/SMask" in raw:
                im = im.convert("RGB" if im.mode == "RGBA" else "L")  # alpha handled via SMask below
            if reason is None and im.mode not in ("RGB", "L"):
                reason = f"color mode {im.mode}"
            if reason:
                stats["skipped"] += 1
                if verbose:
                    print(f"  skip {key}: {reason}")
                continue

            old_len = len(raw.read_raw_bytes())
            w, h = im.size
            if key in sizes and sizes[key][0] > 0 and sizes[key][1] > 0:
                tw = math.ceil(sizes[key][0] * dpi)
                th = math.ceil(sizes[key][1] * dpi)
            else:  # placement unknown: never exceed the page size at this dpi
                box = page.mediabox
                tw = th = math.ceil(max(float(box[2]) - float(box[0]), float(box[3]) - float(box[1])) / 72 * dpi)
            scale = min(tw / w, th / h, 1.0)
            new = im
            if scale < 0.9:  # only resize when it is worth it
                new = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)

            smask = raw.get("/SMask")
            new_mask = None
            if smask is not None:
                try:
                    m = PdfImage(smask).as_pil_image().convert("L")
                    if new.size != im.size:
                        m = m.resize(new.size, Image.LANCZOS)
                    new_mask = m
                except Exception:
                    stats["skipped"] += 1
                    if verbose:
                        print(f"  skip {key}: unreadable transparency mask")
                    continue

            data = jpeg_bytes(new, quality)
            if new is im and len(data) > 0.9 * old_len:
                if verbose:
                    print(f"  keep {key}: {w}x{h}, already efficient")
                continue
            if new is not im and len(data) >= old_len:
                if verbose:
                    print(f"  keep {key}: resized version not smaller")
                continue

            stats["resized" if new is not im else "recompressed"] += 1
            stats["saved"] += old_len - len(data)
            if verbose:
                print(f"  {key}: {w}x{h} -> {new.size[0]}x{new.size[1]}  "
                      f"{old_len/1e6:.2f} MB -> {len(data)/1e6:.2f} MB")
            if dry_run:
                continue
            cs = raw.get("/ColorSpace")
            keep_cs = isinstance(cs, pikepdf.Array) and len(cs) == 2 and cs[0] == "/ICCBased" \
                and int(cs[1].get("/N", 0)) == (3 if new.mode == "RGB" else 1)
            raw.write(data, filter=Name.DCTDecode)
            raw.Width, raw.Height = new.size
            raw.BitsPerComponent = 8
            raw.ColorSpace = cs if keep_cs else Name("/DeviceRGB" if new.mode == "RGB" else "/DeviceGray")
            for k in ("/DecodeParms", "/Intent"):
                if k in raw:
                    del raw[k]
            if new_mask is not None:
                smask.write(zlib.compress(new_mask.tobytes(), 9), filter=Name.FlateDecode)
                smask.Width, smask.Height = new_mask.size
                smask.BitsPerComponent = 8
                smask.ColorSpace = Name.DeviceGray
                if "/DecodeParms" in smask:
                    del smask["/DecodeParms"]

    if not dry_run:
        pdf.remove_unreferenced_resources()
        pdf.save(dst, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 recompress_flate=True)
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--dpi", type=int, default=200, help="resolution to keep, at printed size (default 200)")
    ap.add_argument("--quality", type=int, default=80, help="JPEG quality 1-95 (default 80)")
    ap.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    dst = a.output or a.pdf.with_name(a.pdf.stem + ".small.pdf")
    if not a.dry_run and dst.resolve() == a.pdf.resolve():
        sys.exit("Refusing to overwrite the original; choose another --output name.")
    before = a.pdf.stat().st_size
    s = shrink(a.pdf, dst, a.dpi, a.quality, a.dry_run, not a.quiet)
    print(f"\nimages: {s['seen']} found, {s['resized']} downsampled, "
          f"{s['recompressed']} recompressed only, {s['skipped']} left alone")
    if a.dry_run:
        print(f"estimated saving: {s['saved']/1e6:.1f} MB of {before/1e6:.1f} MB")
    else:
        after = dst.stat().st_size
        print(f"{a.pdf.name}: {before/1e6:.1f} MB -> {dst.name}: {after/1e6:.1f} MB "
              f"({100*(1-after/before):.0f}% smaller)")


if __name__ == "__main__":
    main()
