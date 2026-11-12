#!/usr/bin/env python3
"""
Look up a serial number in the WWII Army Hospital Admission Card Files
(Record Group 112, National Archives series NAID 570973).

The public-use data files are on the National Archives Catalog:
  1944: file unit NAID 235111183  .../rg-112/HOSAD/SGOHOSAD1944.zip
  1945: file unit NAID 235111208  .../rg-112/HOSAD/SGOHOSAD1945.zip
Codebook (scanned): .../rg-112/HOSAD/480_1DP.pdf  (1945 layout on PDF page 60)

usage: hosad1945.py EXTRACTED_ZIP_DIR SERIAL
Prints the raw 1945 record split into fields and translates the fields that
use the long code lists shipped in CodeLists/.  The short coded fields are
translated by SGO_SHTLST45_PU.txt (a dBase program); read it for those.
"""
import sys
from pathlib import Path

LAYOUT = [("Service Number", 1, 9), ("Service Number", 10, 17), ("Sample", 18, 18),
          ("Rank", 19, 19), ("Age", 20, 21), ("Race", 22, 22), ("Length of Service", 23, 23),
          ("Arm of Service", 24, 25), ("AAF Status", 26, 26), ("Station/Day of Admission", 27, 30),
          ("Month of Admission", 31, 31), ("Year of Admission", 32, 32),
          ("Last Treatment Facility", 33, 33), ("Special Class of Case", 34, 34),
          ("Type of Case", 35, 35), ("Type of Admission", 36, 36),
          ("1st Diagnosis", 37, 40, "SGO_DIAGNO45_PU.txt"), ("1st Anatomical Location", 41, 44, "SGO.HOSAD.ANATM45.txt"),
          ("1st Operation", 45, 47, "SGO_OPERAT45_PU.txt"), ("2nd Diagnosis", 48, 51, "SGO_DIAGNO45_PU.txt"),
          ("2nd Anatomical Location", 52, 55, "SGO.HOSAD.ANATM45.txt"), ("2nd Operation", 56, 58, "SGO_OPERAT45_PU.txt"),
          ("3rd Diagnosis", 59, 62, "SGO_DIAGNO45_PU.txt"), ("Causative Agent", 63, 65, "SGO.HOSAD.CAUSGNT.txt"),
          ("Circumstances", 66, 66), ("Final Result", 67, 69, "SGO.HOSAD.FNRSL45.txt"),
          ("Total Days (non-effective)", 70, 72), ("Overseas Days", 73, 75),
          ("Type of Disposition", 76, 76), ("Field of Cause of Disposition", 77, 77),
          ("Month of Disposition", 78, 78), ("Year of Disposition", 79, 79),
          ("Hospital Days", 80, 82), ("Unit Number/Days in last Gen or Conval Hosp", 83, 85),
          ("Specialized Treatment", 86, 87), ("General and Convalescent Hospital", 88, 89)]


def load_codes(path):
    codes = {}
    for line in path.read_text(encoding="latin1").splitlines():
        if "\t" in line:
            k, v = line.split("\t", 1)
            codes[k.strip()] = v.strip()
    return codes


def main():
    d, serial = Path(sys.argv[1]), sys.argv[2]
    data = d / "SGO.1945.PU.txt"
    recs = [l.decode("latin1").rstrip("\r\n") for l in open(data, "rb") if serial.encode() in l[:17]]
    print(f"{len(recs)} record(s) for {serial} in {data.name}")
    for rec in recs:
        print("\nRAW:", repr(rec))
        for f in LAYOUT:
            name, a, b = f[:3]
            val = rec[a - 1:b]
            meaning = ""
            if len(f) == 4 and val.strip(" -"):
                meaning = load_codes(d / "CodeLists" / f[3]).get(val.strip(), "(code not in list)")
            print(f"  {name:45} {a:>2}-{b:<2} [{val}] {meaning}")


if __name__ == "__main__":
    main()
