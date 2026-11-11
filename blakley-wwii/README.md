# WWII morning reports: Pvt. Melbourne R. Blakley, Co. L, 16th Infantry

Research into my grandfather's WWII service using U.S. Army morning reports in the National
Archives Catalog (Series NAID **85713825**, "Morning Reports", Record Group 64 at NARA St. Louis).

**Start with [NARRATIVE.md](NARRATIVE.md)**, the readable story, with documented facts kept
separate from historical context.

## Key findings

| | |
|---|---|
| Army serial number | **34864047** (found in the morning reports, Step 1) |
| Unit confirmed | **Company "L", 16th Infantry**. SO 105, Hq 16th Inf, 23 Nov 1944, effective 21 Nov 1944 |
| Path | Fort Bragg Reception Center (23 May 44) → IRTC Camp Croft, S.C. (Co C 36th ITB, then Co C 33rd ITB) → AGF Repl Depot #1, Fort Meade (Oct 44) → shipment GK-555(a), Inf Co "E" → 11th, 17th and 3rd Replacement Depots → Co L, 16th Inf, near Heistern, Germany |
| Family story check | He was **not** a Normandy/D-Day replacement. He was still a recruit in May 1944 and joined the regiment in Germany on 21 Nov 1944 |
| Nov–Dec 1944 | No entry naming him after joining, which normally means he stayed on duty. Company was in the Hürtgen/Langerwehe fighting, then the northern shoulder of the Bulge at Weywertz, Belgium |
| 1945 | Not online. Needs NPRC (see next steps in the narrative) |

## Files

| File | What it is |
|---|---|
| [`NARRATIVE.md`](NARRATIVE.md) | The story (Step 4) |
| [`research_log.csv`](research_log.csv) | Every document that names him: date, exact wording as read, roll, image number, NAIDs, confidence, how it was verified, and a full citation (Step 3) |
| [`company_L_events_1944.csv`](company_L_events_1944.csv) | Company L's daily "Record of Events", 23 Nov – 31 Dec 1944 (context) |
| [`ocr_hits_all.csv`](ocr_hits_all.csv) | All 44 catalog pages whose OCR text contains his name or serial, with OCR context and citation |
| [`manifest_key_pages.csv`](manifest_key_pages.csv) | The 90 page images downloaded: key orders plus every Co L page for 23 Nov – 31 Dec 1944 |
| [`reocr_company_L_check.csv`](reocr_company_L_check.csv) | Results of the second, independent OCR pass over the Company L pages |
| [`evidence/`](evidence/) | Reduced-size, contrast-enhanced copies of the 15 key pages (the full-resolution TIFFs are about 15 MB each and are not committed) |
| [`nara_mr.py`](nara_mr.py) | Search, read and download tool (Step 2) |
| [`tools/dump.py`](tools/dump.py) | Prints the catalog OCR text of a range of images in a roll |
| [`tools/reocr.py`](tools/reocr.py) | Second-opinion OCR with fuzzy name and serial matching for faint pages |

## How the catalog was searched

Morning-report rolls are "file units" holding 1,000–4,000 page images each. They are not
indexed by unit, but **NARA has machine-OCR'd every page**. The catalog web site uses public
JSON endpoints that `nara_mr.py` calls:

| Endpoint | Returns |
|---|---|
| `/proxy/v3/records/search?ancestorNaId=85713825&q=…` | rolls whose OCR text matches |
| `/proxy/metadata/naid-availability/naid/<roll>?q=…` | the exact pages in a roll that match |
| `/proxy/extractedText/<roll>?objectId=<page>` | the OCR text of one page |

Page images (TIFF) come from each roll's `digitalObjects[].objectUrl`.

```bash
pip install requests pillow            # rapidocr-onnxruntime too, for tools/reocr.py
python3 nara_mr.py --out data find 34864047 '"Blakley Melbourne"'      # every page naming him
python3 nara_mr.py --out data pages 574546313 34864047                 # pages in one roll
python3 nara_mr.py --out data unit '"16th Infantry"' --month 1944-12 \
        --pattern 'Company\W+"?L"?\W+16th'                             # Co L pages for a month
python3 nara_mr.py --out data download manifest_key_pages.csv --jpeg   # images + enhanced JPEGs
python3 tools/dump.py data 579416335 718-768                           # read OCR of a range
python3 tools/reocr.py data/images/<roll dir> --name BLAKLEY --serial 34864047
```

- Requests are rate-limited (`--delay`, 1 s by default), retried with backoff, and cached
  under `--out`. Re-running a command resumes where it stopped.
- `download` appends to `data/download_log.csv` (roll, image number, object ID, local file,
  URL, citation) and skips files it already has.
- `--jpeg` writes an auto-contrast + unsharp-mask JPEG next to each TIFF for faint frames.
- OCR is a finding aid only. Every positive finding in `research_log.csv` says whether it was
  read on the image or relies on OCR from several matching copies.

### Where the unit is in the rolls

| Month | Roll | File unit NAID | Company L images |
|---|---|---|---|
| Nov 1944 | Roll 176 | 574546313 | about 1010–1111 (SO 105 copy for Co L at 1090–1094) |
| Dec 1944 | Roll 664 | 579416335 | 718–768 (a second copy of the roll is NAID 579420665) |

June–October 1944 Company L pages were **not** downloaded. The documents show he was in
training in the United States until October 1944, so those months cannot mention him. The
`unit` command will fetch them if they are wanted for regimental history.

## Limitations

- **Step 1 (AAD enlistment record) was not completed here.** aad.archives.gov returned
  HTTP 403 to automated requests from this environment. The serial number was found in the
  morning reports instead. Search AAD by hand for 34864047.
- The National Archives Catalog has no 1945 morning reports online.
- A missing entry in a morning report is not proof. Several December 1944 frames are faint
  or water-damaged.
