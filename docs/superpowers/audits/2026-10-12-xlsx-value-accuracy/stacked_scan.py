"""Gate 6 scans for stacked period blocks in export output, on several sides.

python -I stacked_scan.py SIDE [SIDE ...]   (directories under outputs/xlsx-header-detection)

Scan A is the audit reviewer's stacked2.py rule, unchanged: an exported table whose headers (any column, the label
column included) name a year, with a body row holding no number whose text is a dated caption, and numbers below.

Scan B is broader. The header condition: any header cell, the label column's included, names a year, a month and
day, or a period phrase (ended/ending/as of). The body-row condition: no number cell, and some cell (label or
heading) under 120 characters carries a year, a month and day, a numeric date, Q1-Q4 or FY with a year, or a
period phrase (`… ended`, `… ending`, `as of`, `as at`, `through`). Numbers must follow below it.

Prints per side the hit count and writes stacked-<side>.json with every hit.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
O = r'C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection'
MON = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?'
# Scan A, from the reviewer's stacked2.py.
DATED = re.compile(rf'^\s*(?:fiscal\s+)?(?:19|20)\d\d\s*(?:\(\w\))?:?\s*$|\b{MON}\s+\d{{1,2}},?\s+(?:19|20)\d\d\b'
                   rf'|\b(?:ended|ending|as of|as at)\b.*\b(?:19|20)\d\d\b|\b(?:fiscal|fy|year)\s*(?:19|20)\d\d\b', re.I)
YEAR = re.compile(r'\b(?:19|20)\d\d\b')
# Scan B.
HEADER_PERIOD = re.compile(rf'\b(?:19|20)\d\d\b|\b{MON}\s+\d{{1,2}}\b|\b(?:ended|ending|as of|as at)\b', re.I)
ROW_PERIOD = re.compile(rf'\b(?:19|20)\d\d\b|\b{MON}\s+\d{{1,2}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b'
                        rf'|\bq[1-4]\b|\bfy\s*\d{{2,4}}\b|\b(?:ended|ending|as of|as at|through)\b', re.I)


def scan_a(t):
    hy = [h for h in t['headers'] if YEAR.search(h)]
    if not hy:
        return None
    rows = t['rows']
    for i, row in enumerate(rows):
        if any(k == 'number' for k, v, o in row):
            continue
        texts = [(o or '') for k, v, o in row]
        cap = [x for x in texts if DATED.search(x) and len(x) < 90]
        if not cap:
            continue
        below = sum(1 for r in rows[i + 1:] for k, v, o in r if k == 'number')
        if below == 0:
            continue
        return dict(row=i, caption=[c[:70] for c in cap[:3]], below=below, headers=[h[:60] for h in hy[:3]])
    return None


def scan_b(t):
    hp = [h for h in t['headers'] if HEADER_PERIOD.search(h)]
    if not hp:
        return None
    rows = t['rows']
    hits = []
    for i, row in enumerate(rows):
        if any(k == 'number' for k, v, o in row):
            continue
        texts = [str(o or '') for k, v, o in row]
        cap = [x for x in texts if x.strip() and len(x) < 120 and ROW_PERIOD.search(x)]
        if not cap:
            continue
        below = sum(1 for r in rows[i + 1:] for k, v, o in r if k == 'number')
        if below == 0:
            continue
        hits.append(dict(row=i, caption=[c[:70] for c in cap[:4]], below=below))
    if not hits:
        return None
    return dict(first=hits[0], rows=len(hits), headers=[h[:60] for h in hp[:3]])


def main():
    for side in sys.argv[1:]:
        out = []
        for name in sorted(os.listdir(os.path.join(O, side))):
            d = json.load(open(os.path.join(O, side, name), encoding='utf-8'))
            for t in d['tables']:
                if t['status'] == 'source_text_only':
                    continue
                a, b = scan_a(t), scan_b(t)
                if a or b:
                    out.append(dict(file=d['file'], ordinal=t['ordinal'], title=t['title'][:60], status=t['status'],
                                    a=a, b=b))
        json.dump(out, open(os.path.join(O, 'task-7', f'stacked-{side}.json'), 'w', encoding='utf-8'), indent=1,
                  ensure_ascii=False)
        print(side, 'scan A', sum(1 for x in out if x['a']), 'scan B', sum(1 for x in out if x['b']))


if __name__ == '__main__':
    main()
