"""ix:nonFraction attributes (scale, unitRef, format, decimals) per concept, from raw filing HTML (regex, read-only)."""
import collections, html, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = r'C:\Users\einstein\kelab5am\sec2md'
files = [l.strip() for l in open(os.path.join(ROOT, r'docs\superpowers\audits\2026-10-11-xlsx-header-detection\filings.txt'),
                                 encoding='utf-8') if l.strip()]
TAG = re.compile(r'<ix:nonfraction\b([^>]*)>', re.I)
ATTR = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
cls = json.load(open('cls-new6.json', encoding='utf-8'))
want = collections.defaultdict(set)   # concepts on category (i) cells and on % cells, by file
for x in cls:
    for e in x['cells']:
        for c in e['concepts']:
            want[x['file']].add((c, e['cls']))
by_unit = collections.Counter()
pct_concepts = collections.Counter()
per_concept = collections.defaultdict(collections.Counter)
for f in files:
    path = f if ':' in f else os.path.join(ROOT, f)
    raw = open(path, 'rb').read().decode('utf-8', 'replace')
    name = os.path.basename(path) + '.json'
    for m in TAG.finditer(raw):
        a = {k.lower(): v for k, v in ATTR.findall(m.group(1))}
        unit = a.get('unitref', '').lower()
        scale = a.get('scale', '')
        by_unit[(('pure/number' if re.search(r'pure|number|percent', unit) else 'usd' if 'usd' in unit else 'shares' if 'share' in unit else 'other'), scale)] += 1
        concept = a.get('name', '')
        for c, k in want.get(name, ()):
            if c == concept:
                per_concept[(concept.split(':')[-1][:70], k)][(unit[:20], scale, a.get('format', '')[:25])] += 1
print('## all ix:nonFraction in 60 filings by unit kind and scale')
for k, v in sorted(by_unit.items(), key=lambda kv: -kv[1])[:25]:
    print('  ', k, v)
print('## concepts on mixed-column plain cells: (unitRef, scale, format) counts')
for k, v in sorted(per_concept.items()):
    print('  ', k, dict(v))
