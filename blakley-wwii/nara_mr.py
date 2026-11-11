#!/usr/bin/env python3
"""
nara_mr.py - find, read and download WWII U.S. Army morning reports from the
National Archives Catalog (series NAID 85713825, "Morning Reports").

The catalog holds each microfilm roll as a "file unit" with thousands of page
images (TIFF).  NARA has machine-OCR'd every page, and the catalog's public
web front end exposes three JSON endpoints that this tool uses:

  /proxy/v3/records/search?ancestorNaId=85713825&q=...   -> matching rolls
  /proxy/metadata/naid-availability/naid/<roll>?q=...    -> matching pages in a roll
  /proxy/extractedText/<roll>?objectId=<page>            -> OCR text of one page

Images are then fetched from the objectUrl given in each roll's record.

Sub-commands
------------
  search   TERM [TERM ...]        list rolls whose OCR text matches any term
  pages    ROLL_NAID TERM [...]   list pages in one roll that match, with OCR
  find     TERM [TERM ...]        search + pages for all rolls; writes hits.csv
                                  and saves OCR text of every hit page
  unit     --month 1944-07 --pattern REGEX TERM [...]
                                  find pages of a given unit in the rolls of a
                                  month: candidate pages are those matching the
                                  search TERMs, kept only if their OCR text
                                  matches REGEX (e.g. "CO L.{0,6}16TH INF")
  download MANIFEST.csv           download the page images listed in a CSV
                                  (columns roll_naid, object_id) with resume,
                                  rate limiting and a citation log

Everything is cached under --out (default ./data) so an interrupted run can be
restarted with the same command and will skip work already done.

OCR is imperfect: a page that is faint or blurred may not be found by text
search at all.  Use the "unit" command plus visual review of neighbouring
pages to cover gaps.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

BASE = "https://catalog.archives.gov"
SERIES_NAID = 85713825  # Morning Reports (WWII), Record Group 64 St. Louis
UA = "nara-morning-report-research/1.0 (personal genealogy research)"

session = requests.Session()
session.headers["User-Agent"] = UA
_last_call = [0.0]
DELAY = 1.0  # seconds between requests (be polite to NARA)


def _get(url, params=None, stream=False, tries=5):
    for attempt in range(tries):
        wait = DELAY - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            r = session.get(url, params=params, timeout=120, stream=stream)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            if attempt == tries - 1:
                raise
            back = 2 ** (attempt + 1)
            print(f"  ! {e}; retrying in {back}s", file=sys.stderr)
            time.sleep(back)


def _cache_json(path: Path, fetch):
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


# ---------------------------------------------------------------- catalog API
def search_rolls(term, out: Path, extra=None, limit=100):
    """Return list of (roll_naid, title) for rolls whose text matches term."""
    results, page = [], 1
    while True:
        params = {"ancestorNaId": SERIES_NAID, "q": term, "limit": limit, "page": page}
        if extra:
            params.update(extra)
        key = urllib.parse.urlencode(sorted(params.items()))
        cache = out / "cache" / "search" / (re.sub(r"[^\w.=&-]", "_", key)[:200] + ".json")
        body = _cache_json(cache, lambda: _get(f"{BASE}/proxy/v3/records/search", params).json()["body"])
        hits = body["hits"]["hits"]
        for h in hits:
            r = h["_source"]["record"]
            results.append((str(r["naId"]), r["title"]))
        total = body["hits"]["total"]["value"]
        if page * limit >= total or not hits:
            return results
        page += 1


def roll_record(roll, out: Path):
    cache = out / "cache" / "rolls" / f"{roll}.json"
    def fetch():
        b = _get(f"{BASE}/proxy/v3/records/search", {"naId": roll}).json()["body"]
        return b["hits"]["hits"][0]["_source"]["record"]
    return _cache_json(cache, fetch)


def roll_objects(roll, out: Path):
    """Ordered list of page dicts with image_no (1-based), objectId, url."""
    rec = roll_record(roll, out)
    objs = []
    for i, o in enumerate(rec.get("digitalObjects", []), 1):
        objs.append({"image_no": i, "object_id": str(o["objectId"]),
                     "filename": o.get("objectFilename", ""), "url": o["objectUrl"]})
    return rec["title"], objs


def matching_pages(roll, term, out: Path):
    params = {"q": term}
    cache = out / "cache" / "match" / roll / (re.sub(r"[^\w-]", "_", term)[:100] + ".json")
    data = _cache_json(cache, lambda: _get(
        f"{BASE}/proxy/metadata/naid-availability/naid/{roll}", params).json())
    return [str(i) for i in data.get("ids", [])]


def ocr_text(roll, object_id, out: Path):
    path = out / "ocr" / roll / f"{object_id}.txt"
    if path.exists():
        return path.read_text()
    d = _get(f"{BASE}/proxy/extractedText/{roll}", {"objectId": object_id}).json()
    objs = d.get("digitalObjects") or [{}]
    text = objs[0].get("extractedText") or ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


def citation(title, roll, image_no, object_id):
    return (f'"{title}," image {image_no}, Morning Reports, Series NAID {SERIES_NAID}, '
            f"Records of the National Archives and Records Administration; "
            f"National Archives Catalog, File Unit NAID {roll}, object {object_id}, "
            f"{BASE}/id/{roll}?objectPage={image_no}")


def context_lines(text, pattern, width=4):
    lines = text.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if re.search(pattern, ln, re.I):
            out.append(" | ".join(lines[max(0, i - width): i + width + 1]))
    return out


# ------------------------------------------------------------------ commands
def cmd_search(a):
    seen = {}
    for t in a.terms:
        for roll, title in search_rolls(t, a.out):
            seen.setdefault(roll, (title, set()))[1].add(t)
    for roll, (title, terms) in sorted(seen.items(), key=lambda kv: kv[1][0]):
        print(f"{roll}\t{title}\t{', '.join(sorted(terms))}")


def cmd_pages(a):
    title, objs = roll_objects(a.roll, a.out)
    idx = {o["object_id"]: o for o in objs}
    for t in a.terms:
        for oid in matching_pages(a.roll, t, a.out):
            o = idx.get(oid, {"image_no": "?"})
            text = ocr_text(a.roll, oid, a.out)
            print(f"\n== {title} image {o['image_no']} (object {oid}) term {t}")
            for c in context_lines(text, a.highlight or re.escape(t.strip('"').split()[0])):
                print("   ", c)


def cmd_find(a):
    hl = a.highlight or "|".join(re.escape(t.strip('"').split()[0]) for t in a.terms)
    rows, rolls = [], {}
    for t in a.terms:
        for roll, title in search_rolls(t, a.out):
            rolls.setdefault(roll, title)
    print(f"{len(rolls)} candidate rolls", file=sys.stderr)
    for roll, title in sorted(rolls.items(), key=lambda kv: kv[1]):
        _, objs = roll_objects(roll, a.out)
        idx = {o["object_id"]: o for o in objs}
        pages = set()
        for t in a.terms:
            pages.update(matching_pages(roll, t, a.out))
        for oid in sorted(pages, key=lambda x: idx.get(x, {}).get("image_no", 0)):
            o = idx.get(oid)
            if not o:
                continue
            text = ocr_text(roll, oid, a.out)
            ctx = context_lines(text, hl, width=a.width)
            rows.append({"roll_naid": roll, "roll_title": title, "image_no": o["image_no"],
                         "object_id": oid, "filename": o["filename"], "url": o["url"],
                         "ocr_context": " || ".join(ctx),
                         "citation": citation(title, roll, o["image_no"], oid)})
            print(f"{title} | img {o['image_no']} | {' || '.join(ctx)[:300]}", file=sys.stderr)
    write_csv(a.out / a.csv, rows)
    print(f"wrote {len(rows)} rows to {a.out / a.csv}", file=sys.stderr)


def cmd_unit(a):
    """Pages of one unit for one month: search candidate terms, filter by regex."""
    y, m = a.month.split("-")
    month_name = time.strftime("%B", time.strptime(m, "%m"))
    prefix = f"Morning Reports for {month_name} {y}"
    rx = re.compile(a.pattern, re.I | re.S)
    rows, rolls = [], {}
    for t in a.terms:
        for roll, title in search_rolls(t, a.out):
            if title.startswith(prefix):
                rolls.setdefault(roll, title)
    print(f"{len(rolls)} {prefix} rolls mention {a.terms}", file=sys.stderr)
    for roll, title in sorted(rolls.items(), key=lambda kv: kv[1]):
        _, objs = roll_objects(roll, a.out)
        idx = {o["object_id"]: o for o in objs}
        pages = set()
        for t in a.terms:
            pages.update(matching_pages(roll, t, a.out))
        keep = []
        for oid in pages:
            if oid in idx and rx.search(ocr_text(roll, oid, a.out)):
                keep.append(idx[oid]["image_no"])
        # include neighbouring images: continuation sheets often lack the header
        nos = sorted({n + d for n in keep for d in range(-a.neighbors, a.neighbors + 1)
                      if 1 <= n + d <= len(objs)})
        for n in nos:
            o = objs[n - 1]
            rows.append({"roll_naid": roll, "roll_title": title, "image_no": n,
                         "object_id": o["object_id"], "filename": o["filename"], "url": o["url"],
                         "matched_header": "yes" if n in keep else "neighbor",
                         "citation": citation(title, roll, n, o["object_id"])})
        print(f"  {title}: {len(keep)} header pages, {len(nos)} incl. neighbors", file=sys.stderr)
    write_csv(a.out / a.csv, rows)
    print(f"wrote {len(rows)} rows to {a.out / a.csv}", file=sys.stderr)


def cmd_download(a):
    rows = list(csv.DictReader(open(a.manifest, newline="")))
    log_path = a.out / "download_log.csv"
    done = set()
    if log_path.exists():
        done = {r["object_id"] for r in csv.DictReader(open(log_path, newline=""))}
    new_log = not log_path.exists()
    with open(log_path, "a", newline="") as lf:
        w = csv.DictWriter(lf, fieldnames=["roll_naid", "roll_title", "image_no", "object_id",
                                           "local_file", "url", "bytes", "citation"])
        if new_log:
            w.writeheader()
        for r in rows:
            roll, oid = r["roll_naid"], r["object_id"]
            if oid in done:
                continue
            title, objs = roll_objects(roll, a.out)
            o = next(x for x in objs if x["object_id"] == oid)
            slug = re.sub(r"[^\w]+", "_", title).strip("_")
            dest = a.out / "images" / slug / f"img{o['image_no']:05d}_{oid}.tif"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                tmp = dest.with_suffix(".part")
                resp = _get(o["url"], stream=True)
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(1 << 16):
                        f.write(chunk)
                tmp.rename(dest)
            if a.jpeg:
                to_jpeg(dest)
            w.writerow({"roll_naid": roll, "roll_title": title, "image_no": o["image_no"],
                        "object_id": oid, "local_file": str(dest), "url": o["url"],
                        "bytes": dest.stat().st_size,
                        "citation": citation(title, roll, o["image_no"], oid)})
            lf.flush()
            print(f"  {title} img {o['image_no']} -> {dest.name}", file=sys.stderr)


def to_jpeg(tif: Path):
    """Write an enhanced (auto-contrast + sharpen) JPEG next to the TIFF."""
    from PIL import Image, ImageFilter, ImageOps
    jpg = tif.with_suffix(".enh.jpg")
    if jpg.exists():
        return jpg
    im = Image.open(tif).convert("L")
    im = ImageOps.autocontrast(im, cutoff=1)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    im.save(jpg, quality=88)
    return jpg


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("data"))
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("search"); s.add_argument("terms", nargs="+"); s.set_defaults(f=cmd_search)
    s = sp.add_parser("pages"); s.add_argument("roll"); s.add_argument("terms", nargs="+")
    s.add_argument("--highlight"); s.set_defaults(f=cmd_pages)
    s = sp.add_parser("find"); s.add_argument("terms", nargs="+"); s.add_argument("--highlight")
    s.add_argument("--width", type=int, default=4); s.add_argument("--csv", default="hits.csv")
    s.set_defaults(f=cmd_find)
    s = sp.add_parser("unit"); s.add_argument("terms", nargs="+"); s.add_argument("--month", required=True)
    s.add_argument("--pattern", required=True); s.add_argument("--neighbors", type=int, default=1)
    s.add_argument("--csv", default=None); s.set_defaults(f=cmd_unit)
    s = sp.add_parser("download"); s.add_argument("manifest"); s.add_argument("--jpeg", action="store_true")
    s.set_defaults(f=cmd_download)

    a = p.parse_args()
    global DELAY
    DELAY = a.delay
    if getattr(a, "csv", "x") is None:
        a.csv = f"unit_{a.month}.csv"
    a.f(a)


if __name__ == "__main__":
    main()
