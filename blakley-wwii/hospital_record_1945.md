# 1945 hospital admission record: serial 34864047

**Source:** WWII Army Hospital Admission Card Files, Records of the Office of the Surgeon
General (Army), Record Group 112, series NAID 570973. Public-use data file `SGO.1945.PU.txt`
(file unit NAID 235111208, `SGOHOSAD1945.zip` in the National Archives Catalog), line 1,081,970.
These files have no names, only the Army serial number. Exactly **one** 1945 record and
**no** 1944 record match 34864047.

Raw record:
```
03486404734864047522514300-9104570400110493949201153983113-   2069-  0370376-55037016-
```

Decoded with the 1945 record layout (codebook `480_1DP.pdf`, p. 60) and the code lists in
the zip. `tools/hosad1945.py` reproduces this.

| Field | Code | Meaning |
|---|---|---|
| Rank | 2 | Enlisted man |
| Age | 25 | 25 |
| Length of service | 4 | 6–12 months (matches induction in May 1944) |
| Arm of service | 30 | Infantry |
| **Month / year admitted** | 4 / 5 | **April 1945** (the day is not given) |
| Station of admission | -910 | Overseas station. The "-" prefix code is **not translated** by the public code lists |
| Type of case | 4 | **Battle casualty** |
| Circumstances | 9 | Battle casualty / battle injury |
| **1st diagnosis** | 0110 | **Penetrating wound** (entrance only), no nerve or artery involvement |
| 1st location | 4939 | **Thorax (chest), generally** |
| 1st treatment | 492 | Penicillin therapy |
| **2nd diagnosis** | 0115 | **Perforating wound** (entrance and exit), no nerve or artery involvement |
| 2nd location | 3983 | **Fingers, generally** |
| 2nd treatment | 113 | Delayed closure / secondary suture of wound |
| **Cause** | 206 | **Artillery shell: blast, fragments, debris** |
| Last treatment facility | 7 | General hospital |
| Last general hospital, unit no. | 016 | **16th General Hospital** (unit number, per the overseas-station rule in SHTLST45) |
| Days lost / overseas days / hospital days | 037 / 037 / 037 | **37 days** |
| **Disposition** | 6 | **Returned to duty** |
| Month / year of disposition | 5 / 5 | **May 1945** |

Not used: the sample code "5" is not defined in the code list.

## What it means

- He was **wounded by artillery shell fragments in April 1945**, with a wound to the chest
  and a through-and-through wound of the fingers. Neither wound involved a nerve or artery.
- He was treated with penicillin, and the wound was closed later (the standard method for
  shell-fragment wounds then). He ended up in the **16th General Hospital**.
- After **37 days** he was **returned to duty in May 1945**. Since the admission was in
  April, 37 days later falls in May, so he was admitted between about 1 and 24 April.

## Fit with the family story ("wounded in Czechoslovakia")

[CONTEXT] In April 1945 the 1st Infantry Division was fighting in central Germany, mainly in
the Harz Mountains (roughly 11–21 April). It crossed into Czechoslovakia in early May 1945,
around Cheb, shortly before the war in Europe ended on 8 May. An April admission therefore
places this wound **in Germany, not Czechoslovakia**.

Possible explanations, none confirmed:
1. The family memory merged the wound with where the war ended for him. He was returned to
   duty in May 1945, possibly rejoining the division in or near Czechoslovakia.
2. He had a second, lighter wound in Czechoslovakia that was treated at the aid station
   without hospital admission ("LWA, not evacuated"). Such wounds appear in company morning
   reports but not in these hospital files.

The Company L morning reports for April–May 1945 (only at NPRC, St. Louis) would settle
this. They would give the exact date and place he was wounded, the "LWA/SWA" entry, and the
date he rejoined.

## Caveats

- These are statistical punch-card data keyed from hospital admission cards. Codes can be
  mis-keyed, and the file is not a complete record of every admission.
- The specific overseas station of admission ("-910") could not be translated from the
  public code lists. NARA St. Louis provides individual look-ups of these files and can
  interpret it.
- [CONTEXT, not from the record] The 16th General Hospital served in Liège, Belgium, in
  1944–45. Its location in April–May 1945 should be checked.
