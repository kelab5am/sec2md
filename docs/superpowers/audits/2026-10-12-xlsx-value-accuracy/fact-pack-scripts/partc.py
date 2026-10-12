"""Part C: table-wide percent captions (units) on new6."""
import collections, json, os, re, sys
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
import sec2md.xlsx_tables as m
from sec2md.xlsx_values import convert_cell

D = r'C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection\new6'
PCTW = re.compile(r'%|\bpercent\w*', re.I)
SCALE = re.compile(r'\b(?:thousands|millions|billions)\b', re.I)


def group(name):
    c = name.split('__')[0]
    return c if c in ('META', 'NVDA', 'RDDT') else 'Others'


recon = {(r['file'], r['ordinal']): r for r in json.load(open('recon.json', encoding='utf-8'))}
tables = {}
for n in sorted(os.listdir(D)):
    data = json.load(open(os.path.join(D, n), encoding='utf-8'))
    for t in data['tables']:
        tables[(data['file'], t['ordinal'])] = (n, t)

# 1. tables whose units mention percent
print('## units mentioning percent (main, reconstructed)')
unit_rows = []
for key, r in recon.items():
    if r['units'] and PCTW.search(r['units']):
        n, t = tables[key]
        units_cells = [c for c in r['cells'] if c['why'] == 'units']
        unit_rows.append((group(n), key, r['units'], len(units_cells), t['status']))
for row in sorted(unit_rows):
    print(' ', row[0], row[1][0][:40], '#%d' % row[1][1], row[4], repr(row[2][:120]), 'cells_from_units=%d' % row[3])
print('  tables:', collections.Counter(r[0] for r in unit_rows), 'cells from units:',
      {g: sum(r[3] for r in unit_rows if r[0] == g) for g in ('META', 'NVDA', 'RDDT', 'Others')})

# verify "role percent only from units": value == number/100, no % in cell, header or label
print('\n## cells with role percent from units: check value/100 and no % in cell/header/label')
bad = 0
for key, r in recon.items():
    for c in r['cells']:
        if c['why'] != 'units':
            continue
        n, t = tables[key]
        kind, value, orig = t['rows'][c['r']][c['c']]
        label = t['rows'][c['r']][0][2] or ''
        hdr = t['headers'][c['c']]
        p = convert_cell(orig.strip(), role='number').value if orig else None
        ok = (kind == 'number' and isinstance(p, Decimal) and Decimal(value) == p / 100
              and '%' not in orig and not PCTW.search(hdr) and not PCTW.search(label))
        bad += not ok
print('  non-conforming:', bad)

# 2. percent captions inside tables (source cells) of every table, any status
print('\n## in-table caption cells mentioning percent and a scale word (all statuses)')
cap = collections.defaultdict(list)
for key, (n, t) in tables.items():
    for row, col, rs, cs, text, fact in t['source_cells']:
        tx = ' '.join(text.split())
        if PCTW.search(tx) and SCALE.search(tx) and len(tx) < 200:
            cap[tx].append((group(n), n, t['ordinal'], t['status'], row, col, cs))
for tx, uses in sorted(cap.items(), key=lambda kv: -len(kv[1])):
    full = bool(m._UNIT_DECLARATION.fullmatch(tx.strip()))
    exc = bool(re.search(r'\bexcept\b[^)]*\bpercent', tx, re.I))
    print(f'  {len(uses):3} full={full} except_clause={exc} {tx!r} groups={dict(collections.Counter(u[0] for u in uses))}'
          f' statuses={dict(collections.Counter(u[3] for u in uses))}')

# 3. percent-of-revenue context sentences reaching units
print('\n## would the plural captions reach units if _UNIT_DECLARATION accepted them?')
plural = re.compile(r'\(?(?:amounts? )?in (?:thousands|millions|billions),? except (?:for )?[a-z ,]*percentages[a-z ,]*\)?', re.I)
reach = collections.Counter()
detail = collections.defaultdict(list)
for key, (n, t) in tables.items():
    if t['status'] == 'source_text_only':
        continue
    cells = t['source_cells']
    width = max(c[1] + c[3] for c in cells)
    for row, col, rs, cs, text, fact in cells:
        tx = ' '.join(text.split())
        if plural.fullmatch(tx):
            spans = col + cs == width and cs > 1
            reach[(group(n), 'spans to last column' if spans else 'does not span')] += 1
            detail[(group(n), spans)].append(f'{n[:24]}#{t["ordinal"]}')
print(' ', dict(reach))
for k, v in detail.items():
    print('  ', k, len(v), sorted(set(v))[:12])
