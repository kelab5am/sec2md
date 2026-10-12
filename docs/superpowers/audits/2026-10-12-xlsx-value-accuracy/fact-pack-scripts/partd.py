"""Part D: identifier-column headers (Rule 3) with digit-bearing cells. python -I partd.py DIR OUT_JSON"""
import collections, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
import sec2md.xlsx_tables as m

src, out_json = sys.argv[1:3]


def group(name):
    c = name.split('__')[0]
    return c if c in ('META', 'NVDA', 'RDDT') else 'Others'


def ident(header):
    parts = [p.strip() for p in header.split(' — ') if p.strip()]
    for i, part in enumerate(parts):
        if not m._IDENTIFIER.search(part):
            continue
        if m._NOTE_REF.fullmatch(part) or m._MATURITY_BUCKET.fullmatch(part):
            continue
        rest = m._PERIOD_WORDS.sub(' ', part)
        if not m._IDENTIFIER.search(rest):
            continue
        if any(p.search(part) for p in (m._VALUE, m._ROW_UNIT, m._QUANTITY)):
            continue
        if m._WRAPPED_QUANTITY.search(' '.join(parts[i:i + 2])):
            continue
        return part, m._IDENTIFIER.search(rest).group(0)
    return None


out = []
for name in sorted(os.listdir(src)):
    data = json.load(open(os.path.join(src, name), encoding='utf-8'))
    for t in data['tables']:
        if t['status'] == 'source_text_only':
            continue
        facts = {(f[0], f[1]): f[3] for f in t['facts']}
        for ci, h in enumerate(t['headers']):
            if ci == 0:
                continue
            period_header = all(m._PERIOD.fullmatch(p) for p in h.split(' — '))
            if not m._identifier_column(h) or period_header:
                continue
            assert ident(h)
            part, word = ident(h)
            cells = []
            for ri, row in enumerate(t['rows']):
                if ci >= len(row):
                    continue
                kind, value, orig = row[ci]
                if orig and re.search(r'\d', orig):
                    srcs = t['cell_sources'][ri][ci]
                    fact = next((facts[tuple(s)] for s in srcs if tuple(s) in facts), None)
                    numeric = any(sc[5] for sc in t['source_cells'] if [sc[0], sc[1]] in srcs)
                    cells.append(dict(r=ri, label=row[0][2] or '', orig=orig, kind=kind, fact=fact, nonfraction=numeric))
            if cells:
                out.append(dict(file=name, group=group(name), ordinal=t['ordinal'], title=t['title'], status=t['status'],
                                header=h, part=part, word=word, col=ci, cells=cells))
json.dump(out, open(out_json, 'w', encoding='utf-8'), indent=0)
print(len(out), 'columns', len({(x['file'], x['ordinal']) for x in out}), 'tables', sum(len(x['cells']) for x in out), 'cells')
for x in out:
    fx = sum(bool(c['fact']) for c in x['cells'])
    nf = sum(c['nonfraction'] for c in x['cells'])
    sample = ' | '.join(f'{c["label"][:22]}={c["orig"]}' for c in x['cells'][:4])
    print(f'{x["group"]:6} {x["file"][:30]:30} #{x["ordinal"]:<4} {x["status"][:3]} c{x["col"]} H={x["header"][:70]!r} '
          f'part={x["part"][:40]!r} word={x["word"]!r} n={len(x["cells"])} facts={fx} ixnf={nf} :: {sample[:150]}')
