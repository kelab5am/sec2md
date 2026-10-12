"""Rebuild main's prepare_table from new6 export JSON (source cells + units from instr-new.json), recording
why each value cell got its role. Writes recon.json: per table, per cell, role reason and identifier part.

python -I recon.py
"""
import json, os, re, sys
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
import sec2md.xlsx_tables as m
from sec2md.xlsx_tables import SourceCell, TableSnapshot, prepare_table

OUT = r'C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection'
NEW6 = os.path.join(OUT, 'new6')
INSTR = json.load(open(os.path.join(OUT, 'investigation-1', 'instr-new.json'), encoding='utf-8'))
INSTR = {r['file']: {t['ordinal']: t for t in r['tables']} for r in INSTR}

LOG = []


def identifier_part(header):
    parts = [part.strip() for part in header.split(' — ') if part.strip()]
    for index, part in enumerate(parts):
        if not m._IDENTIFIER.search(part):
            continue
        if m._NOTE_REF.fullmatch(part) or m._MATURITY_BUCKET.fullmatch(part):
            continue
        if not m._IDENTIFIER.search(m._PERIOD_WORDS.sub(' ', part)):
            continue
        if any(p.search(part) for p in (m._VALUE, m._ROW_UNIT, m._QUANTITY)):
            continue
        if m._WRAPPED_QUANTITY.search(' '.join(parts[index:index + 2])):
            continue
        return part, m._IDENTIFIER.search(m._PERIOD_WORDS.sub(' ', part)).group(0)
    return None


def numeric_role(text, header, label, cells, units, financial, percent_header):
    period_header = all(m._PERIOD.fullmatch(part) for part in header.split(' — '))
    if m._identifier_column(header) and not period_header:
        role, why = 'text', 'identifier'
    elif percent_header:
        role, why = 'percent', 'percent_header'
    elif m._PERCENT_UNIT.fullmatch(label.strip()):
        role, why = 'percent', 'percent_label'
    elif m._VALUE.search(header) or m._ROW_UNIT.search(header) or m._ROW_UNIT.search(label):
        role, why = 'number', 'value_or_unit_word'
    elif m._PERCENT.search(units):
        role, why = 'percent', 'units'
    elif any(c.is_numeric_fact for c in cells) or '$' in text or '%' in text:
        role, why = 'number', 'fact_or_symbol'
    elif units or m._VALUE.search(label) or financial:
        role, why = 'number', 'units_label_financial'
    else:
        role, why = 'text', 'default_text'
    LOG.append(dict(text=text, header=header, label=label, role=role, why=why, units=units,
                    origins=[(c.row, c.column) for c in cells], ident=identifier_part(header)))
    return role


m._numeric_role = numeric_role


def val(v):
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        return ['number', str(v)]
    return ['text', None if v is None else str(v)]


result = []
mismatch_tables = 0
for name in sorted(os.listdir(NEW6)):
    data = json.load(open(os.path.join(NEW6, name), encoding='utf-8'))
    instr = INSTR[data['file']]
    for t in data['tables']:
        if t['status'] == 'source_text_only':
            continue
        cells = tuple(SourceCell(text, r, c, rs, cs, (), False, bool(f)) for r, c, rs, cs, text, f in t['source_cells'])
        texts = {c.text for c in cells}
        ctx = tuple(line for line in (instr[t['ordinal']]['units'] or '').split('\n') if line and line not in texts)
        snap = TableSnapshot(t['ordinal'], 1, None, None, None, cells, '', 'html', ctx, (), ())
        LOG.clear()
        p = prepare_table(snap)
        rows = [[[*val(c.value), c.original] for c in row] for row in p.rows]
        same = rows == t['rows'] and list(p.headers) == t['headers']
        if not same:
            mismatch_tables += 1
        # map the role log onto output positions by origin coordinates
        by_origin = {}
        for e in LOG:
            by_origin[tuple(map(tuple, e['origins']))] = e
        cellinfo = []
        for ri, row in enumerate(p.cell_sources):
            for ci, srcs in enumerate(row):
                e = by_origin.get(tuple(tuple(s) for s in srcs))
                if e and ci > 0:
                    cellinfo.append(dict(r=ri, c=ci, why=e['why'], role=e['role'], ident=e['ident']))
        result.append(dict(file=data['file'], ordinal=t['ordinal'], same=same, units=p.units,
                           headers=list(p.headers), cells=cellinfo,
                           diff=None if same else [list(p.headers), t['headers']][:2]))
print('tables', len(result), 'mismatch', mismatch_tables)
json.dump(result, open('recon.json', 'w', encoding='utf-8'))
