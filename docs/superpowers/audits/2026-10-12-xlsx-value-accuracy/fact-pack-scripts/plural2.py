"""Counterfactual for C: if _UNIT_DECLARATION accepted plural 'percentages', what would change on new6?
Rebuilds prepare_table from new6 JSON twice (main as is; patched pattern) and diffs cell values."""
import collections, json, os, re, sys
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
import sec2md.xlsx_tables as m
from sec2md.xlsx_tables import SourceCell, TableSnapshot, prepare_table

OUT = r'C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection'
NEW6 = os.path.join(OUT, 'new6')
INSTR = json.load(open(os.path.join(OUT, 'investigation-1', 'instr-new.json'), encoding='utf-8'))
INSTR = {r['file']: {t['ordinal']: t for t in r['tables']} for r in INSTR}
ORIG = m._UNIT_DECLARATION
m._PERCENT = re.compile(r'%|\bpercent(?:age)?s?\b', re.I)  # variant: _PERCENT also reads the plural
PATCHED = re.compile(ORIG.pattern.replace('percent(?:age)?)', 'percent(?:age)?s?)')
                     .replace(r'(?:, except (?:for )?', r'(?:,? except (?:for )?'), re.I)
assert PATCHED.pattern != ORIG.pattern
assert PATCHED.fullmatch('(in millions, except percentages)') and PATCHED.fullmatch('(In millions, except percentages and per share amounts)')


def group(name):
    c = name.split('__')[0]
    return c if c in ('META', 'NVDA', 'RDDT') else 'Others'


def build(t, ctx_lines):
    cells = tuple(SourceCell(text, r, c, rs, cs, (), False, bool(f)) for r, c, rs, cs, text, f in t['source_cells'])
    texts = {c.text for c in cells}
    ctx = tuple(l for l in ctx_lines if l and l not in texts)
    return prepare_table(TableSnapshot(t['ordinal'], 1, None, None, None, cells, '', 'html', ctx, (), ()))


changes = collections.Counter()
tables_changed = collections.defaultdict(set)
examples = collections.defaultdict(list)
unit_tables = collections.Counter()
for name in sorted(os.listdir(NEW6)):
    data = json.load(open(os.path.join(NEW6, name), encoding='utf-8'))
    instr = INSTR[data['file']]
    for t in data['tables']:
        if t['status'] == 'source_text_only':
            continue
        ctx = (instr[t['ordinal']]['units'] or '').split('\n')
        m._UNIT_DECLARATION = ORIG
        a = build(t, ctx)
        m._UNIT_DECLARATION = PATCHED
        b = build(t, ctx)
        m._UNIT_DECLARATION = ORIG
        g = group(name)
        if re.search(r'percent', b.units, re.I) and not re.search(r'percent', a.units, re.I):
            unit_tables[g] += 1
        if a.headers != b.headers or len(a.rows) != len(b.rows):
            changes[(g, 'header/rows changed')] += 1
            tables_changed[(g, 'header/rows changed')].add((name, t['ordinal']))
            continue
        for ra, rb in zip(a.rows, b.rows):
            for ca, cb in zip(ra, rb):
                if ca.value == cb.value and ca.review_reason == cb.review_reason:
                    continue
                if isinstance(ca.value, Decimal) and isinstance(cb.value, Decimal) and cb.value * 100 == ca.value:
                    kind = 'number -> /100' + (' ($ cell)' if '$' in ca.original else '')
                elif isinstance(ca.value, Decimal) and not isinstance(cb.value, Decimal):
                    kind = 'number -> text (' + str(cb.review_reason)[:40] + ')'
                else:
                    kind = 'other'
                changes[(g, kind)] += 1
                tables_changed[(g, kind)].add((name, t['ordinal']))
                if len(examples[(g, kind)]) < 6:
                    examples[(g, kind)].append(f'{name[:24]}#{t["ordinal"]} {ra[0].original[:30]!r}: {ca.original!r} {ca.value} -> {cb.value}')
print('tables whose units gain a percent caption:', dict(unit_tables))
for k in sorted(changes):
    print(k, 'cells' if 'header' not in k[1] else 'tables', changes[k], 'tables', len(tables_changed[k]))
    for e in examples[k]:
        print('    ', e)
