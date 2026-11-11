"""Print OCR text of roll images: dump.py OUT ROLL IMG[-IMG] [...]"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import nara_mr as m
out = pathlib.Path(sys.argv[1]); roll = sys.argv[2]
m.DELAY = 0.4
title, objs = m.roll_objects(roll, out)
for spec in sys.argv[3:]:
    a, _, b = spec.partition('-'); b = b or a
    for n in range(int(a), int(b) + 1):
        o = objs[n - 1]
        t = m.ocr_text(roll, o['object_id'], out)
        print(f"\n######## {title} img {n} obj {o['object_id']}\n" + t.replace('\n', ' | ')[:int(__import__('os').environ.get('MAXC', '3000'))])
