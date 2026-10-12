"""Cells holding an ix:nonFraction with scale=-2 (percent facts): how are they exported on new6/base?
Matches facts in export JSON (row, col, context, concept, text) to raw HTML tags by (contextref, name, text)."""
import collections, html, json, os, re, sys
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
from sec2md.xlsx_values import convert_cell
ROOT = r'C:\Users\einstein\kelab5am\sec2md'
D = os.path.join(ROOT, r'outputs\xlsx-header-detection')
files = [l.strip() for l in open(os.path.join(ROOT, r'docs\superpowers\audits\2026-10-11-xlsx-header-detection\filings.txt'),
                                 encoding='utf-8') if l.strip()]
TAG = re.compile(r'<ix:nonfraction\b([^>]*)>(.*?)</ix:nonfraction>', re.I | re.S)
ATTR = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')


def group(name):
    c = name.split('__')[0]
    return c if c in ('META', 'NVDA', 'RDDT') else 'Others'


def num(text):
    v = convert_cell(text.strip(), role='number').value
    return v if isinstance(v, Decimal) else None


scales = {}
for f in files:
    path = f if ':' in f else os.path.join(ROOT, f)
    raw = open(path, 'rb').read().decode('utf-8', 'replace')
    name = os.path.basename(path) + '.json'
    s = {}
    for m in TAG.finditer(raw):
        a = {k.lower(): v for k, v in ATTR.findall(m.group(1))}
        text = ' '.join(html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).split())
        s[(a.get('contextref'), a.get('name'), text)] = a.get('scale', '')
    scales[name] = s

for sub in ('new6', 'base'):
    res = collections.Counter()
    tabs = collections.defaultdict(set)
    examples = collections.defaultdict(list)
    for n in sorted(os.listdir(os.path.join(D, sub))):
        data = json.load(open(os.path.join(D, sub, n), encoding='utf-8'))
        sc = scales[n]
        for t in data['tables']:
            if t['status'] == 'source_text_only':
                continue
            where = {}
            for ri, row in enumerate(t['cell_sources']):
                for ci, srcs in enumerate(row):
                    for s in srcs:
                        where[tuple(s)] = (ri, ci)
            for f in t['facts']:
                scale = sc.get((f[2], f[3], ' '.join(f[4].split())))
                if scale != '-2':
                    continue
                pos = where.get((f[0], f[1]))
                if pos is None:
                    res[(group(n), 'fact not in copy rows')] += 1
                    continue
                kind, value, orig = t['rows'][pos[0]][pos[1]]
                p = num(orig.replace('%', '')) if orig else None
                if kind != 'number':
                    out = 'text'
                elif p is not None and Decimal(value) == p / 100:
                    out = 'fraction (correct)' if p != 0 else 'zero'
                elif p is not None and Decimal(value) == p:
                    out = 'percentage points (unscaled)'
                else:
                    out = 'other'
                key = (group(n), t['status'], out + (' [% in cell]' if '%' in (orig or '') else ''))
                res[key] += 1
                tabs[key].add((n, t['ordinal']))
                if len(examples[key]) < 4:
                    examples[key].append(f'{n[:22]}#{t["ordinal"]} {t["rows"][pos[0]][0][2][:30]!r} {orig!r}->{value}')
    print('##', sub)
    for k in sorted(res):
        print('  ', k, res[k], 'tables', len(tabs.get(k, ())), examples.get(k, [])[:2])
