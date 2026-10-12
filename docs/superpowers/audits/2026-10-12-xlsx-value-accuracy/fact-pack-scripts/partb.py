"""Part B tallies: mixed columns (cls-new6.json / cls-base.json) + split-% scan, new-vs-base lookup."""
import collections, json, os, re, sys
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
from sec2md.xlsx_values import convert_cell

D = r'C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection'
GROUPS = ['META', 'NVDA', 'RDDT', 'Others']


def group(name):
    c = name.split('__')[0]
    return c if c in GROUPS[:3] else 'Others'


def num(text):
    v = convert_cell(text.strip(), role='number')
    return v.value if isinstance(v.value, Decimal) else None


def load(sub):
    out = {}
    for n in os.listdir(os.path.join(D, sub)):
        data = json.load(open(os.path.join(D, sub, n), encoding='utf-8'))
        for t in data['tables']:
            out[(n, t['ordinal'])] = t
    return out


new6, base = load('new6'), load('base')


def base_fate(key, label, orig):
    t = base.get(key)
    if t is None:
        return 'table absent on base'
    if t['status'] == 'source_text_only':
        return 'NEW: table was source_text_only on base'
    found = [c for row in t['rows'] if (row[0][2] or '').strip() == label for c in row[1:] if c[2] == orig]
    if not found:
        return 'NEW: cell not in base copy rows'
    p = num(orig)
    kinds = set()
    for c in found:
        if c[0] != 'number':
            kinds.add('text')
        elif Decimal(c[1]) == p:
            kinds.add('unscaled')
        else:
            kinds.add('scaled')
    if 'unscaled' in kinds:
        return 'also on base (unscaled number)'
    return 'NEW: base had ' + '/'.join(sorted(kinds))


cls = json.load(open('cls-new6.json', encoding='utf-8'))
cls_base = json.load(open('cls-base.json', encoding='utf-8'))

# counts per group and status
def tally(data):
    c = collections.Counter()
    cols = collections.Counter()
    for x in data:
        cols[(x['group'], x['status'])] += 1
        for e in x['cells']:
            c[(x['group'], x['status'], e['cls'], e['outcome'])] += 1
    return c, cols

for label, data in (('new6', cls), ('base', cls_base)):
    c, cols = tally(data)
    print(f'## {label}: mixed columns per group/status')
    for g in GROUPS:
        for st in ('exported', 'needs_review'):
            if cols[(g, st)]:
                parts = {k[2] + '-' + k[3]: v for k, v in c.items() if k[0] == g and k[1] == st}
                print(f'  {g} {st}: columns={cols[(g, st)]} cells={sum(parts.values())} {dict(sorted(parts.items()))}')

# category (i) unscaled numbers, per table, with base fate
print('\n## new6 category (i) cells exported as unscaled numbers')
tables = collections.OrderedDict()
for x in cls:
    for e in x['cells']:
        if e['cls'] == 'pct' and e['outcome'] == 'unscaled':
            key = (x['file'], x['ordinal'])
            fate = base_fate(key, e['label'], e['orig'])
            tables.setdefault(key, dict(group=x['group'], status=x['status'], title=x['title'], cols={}))
            tables[key]['cols'].setdefault(x['header'], []).append((e, fate, x['pct_rows'], x['digit_rows']))
summary = collections.Counter()
tabcount = collections.Counter()
for key, info in tables.items():
    fates = collections.Counter(f for cells in info['cols'].values() for _, f, _, _ in cells)
    n = sum(fates.values())
    newn = sum(v for k, v in fates.items() if k.startswith('NEW'))
    summary[(info['group'], info['status'], 'cells')] += n
    summary[(info['group'], info['status'], 'new_cells')] += newn
    tabcount[(info['group'], info['status'])] += 1
    tabcount[(info['group'], info['status'], 'new')] += bool(newn)
    print(f'=T {key[0]} #{key[1]} [{info["status"]}] {info["title"][:80]!r} cells={n} new={newn} fates={dict(fates)}')
    for h, cells in info['cols'].items():
        pr, dr = cells[0][2], cells[0][3]
        print(f'   H={h!r} %rows={pr} digit_rows={dr}')
        print('      ' + ' | '.join(f'{e["label"][:38]}: {e["orig"]} -> {e["value"]} ({e["why"]})' for e, _, _, _ in cells))
print('\n## summary (i) unscaled')
for g in GROUPS:
    for st in ('exported', 'needs_review'):
        if tabcount[(g, st)]:
            print(f'  {g} {st}: tables={tabcount[(g, st)]} (new {tabcount[(g, st, "new")]}) cells={summary[(g, st, "cells")]} (new {summary[(g, st, "new_cells")]})')

# (i) cells kept as text
print('\n## new6 category (i) cells exported as text (flagged)')
c = collections.Counter()
for x in cls:
    for e in x['cells']:
        if e['cls'] == 'pct' and e['outcome'] == 'text':
            c[(x['group'], x['file'], x['ordinal'], x['status'])] += 1
for k, v in c.items():
    print(' ', k, v)

# split-% scan: a value cell without % whose right neighbour copy cell holds only a % marker
print('\n## split % (the % sign in its own copy column)')
SPLIT = re.compile(r'^\)?\s*%\s*\)?$')
split = collections.defaultdict(list)
for label, data in (('new6', new6), ('base', base)):
    for key, t in data.items():
        if t['status'] == 'source_text_only':
            continue
        for ri, row in enumerate(t['rows']):
            for ci in range(1, len(row) - 1):
                c, right = row[ci], row[ci + 1]
                if right[2] and SPLIT.match(right[2].strip()) and c[2] and re.search(r'\d', c[2]) and '%' not in c[2]:
                    p = num(c[2] + (')' if right[2].strip().startswith(')') else ''))
                    outcome = 'text' if c[0] != 'number' else ('zero' if Decimal(c[1]) == 0 else
                               'scaled' if p is not None and Decimal(c[1]) == p / 100 else 'unscaled')
                    split[label].append((group(key[0]), key[0], key[1], t['status'], t['headers'][ci], (row[0][2] or ''),
                                         c[2], right[2], c[0], c[1], outcome))
for label in ('new6', 'base'):
    cc = collections.Counter((s[0], s[3], s[10]) for s in split[label])
    tt = collections.Counter((s[0], s[3]) for s in {(s[0], s[1], s[2], s[3]) for s in split[label]})
    print(f'  {label}: cells {dict(sorted(cc.items()))}; tables {dict(sorted(tt.items()))}')
base_split = {(s[1], s[2], s[5], s[6]) for s in split['base'] if s[10] == 'unscaled'}
by_table = collections.OrderedDict()
for s in split['new6']:
    by_table.setdefault((s[0], s[1], s[2], s[3]), []).append(s)
for k, v in by_table.items():
    unsc = [s for s in v if s[10] == 'unscaled']
    newc = sum((s[1], s[2], s[5], s[6]) not in base_split for s in unsc)
    print(f'=S {k[1]} #{k[2]} [{k[3]}] cells={len(v)} unscaled={len(unsc)} new_vs_base={newc} headers={sorted({s[4] for s in v})[:4]}')
    print('      ' + ' | '.join(f'{s[5][:30]}: {s[6]}{s[7]} -> {s[9]} ({s[10]})' for s in v[:6]))
json.dump({'split_new6': split['new6'], 'split_base': split['base']}, open('split.json', 'w', encoding='utf-8'))
