"""Mixed percent scale columns (B). python -I mixed.py DIR OUT_JSON

A value column (not column 0) of a non-source_text_only table holding at least one number whose
original text has '%' and at least one plain number (no '%', no '$'). Every plain cell is classified.
"""
import json, os, re, sys
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
from sec2md.xlsx_values import convert_cell

src_dir, out_json = sys.argv[1:3]

PCT_CONCEPT = re.compile(r'Ratio|Percent|Percentage|Margin|Yield|Rate(?!.*(?:Amount|Expense|Benefit|Cost))', re.I)
PCT_LABEL = re.compile(r'%|\bpercent|\bratio\b|\bratios\b|\brate\b|\brates\b|\bmargin\b|\byield\b|\bgrowth\b'
                       r'|\bchange\b|\bas a % of\b|\bof (?:total )?(?:net )?revenues?\b|\brate of\b|\bROE\b|\bROTCE\b|\bROA\b', re.I)
AMT_LABEL = re.compile(r'\$|\bdollars?\b|\bamount|\bshares\b|\bper share\b|\bin (?:thousands|millions|billions)\b'
                       r'|\bnumber of\b|\bheadcount\b|\bemployees\b|\bcount\b|\bunits\b|\(in [a-z]+\)', re.I)
PCT_HEADER = re.compile(r'%|\bpercent|\bratio|\brate\b|\brates\b|\bmargin|\byield|\bgrowth|\bchange\b', re.I)


def group(name):
    c = name.split('__')[0]
    return c if c in ('META', 'NVDA', 'RDDT') else 'Others'


def parse(original):
    v = convert_cell(original.strip(), role='number')
    return v.value if isinstance(v.value, Decimal) else None


out = []
for name in sorted(os.listdir(src_dir)):
    data = json.load(open(os.path.join(src_dir, name), encoding='utf-8'))
    for t in data['tables']:
        if t['status'] == 'source_text_only' or not t['rows']:
            continue
        facts = {}
        for f in t['facts']:
            facts.setdefault((f[0], f[1]), []).append(f[3])
        width = len(t['headers'])
        for ci in range(1, width):
            col = [(ri, row[ci]) for ri, row in enumerate(t['rows']) if ci < len(row)]
            pct = [(ri, c) for ri, c in col if c[2] and '%' in c[2] and re.search(r'\d', c[2])]
            plain = [(ri, c) for ri, c in col if c[2] and re.search(r'\d', c[2]) and '%' not in c[2]
                     and '$' not in c[2] and parse(c[2]) is not None]
            if not pct or not plain:
                continue
            pct_rows = {ri for ri, _ in pct}
            pct_mag = [abs(parse(c[2].replace('%', '')) or 0) for _, c in pct]
            cells = []
            for ri, c in col:
                if not (c[2] and re.search(r'\d', c[2])):
                    continue
                srcs = t['cell_sources'][ri][ci]
                concepts = [x for s in srcs for x in facts.get(tuple(s), [])]
                label = t['rows'][ri][0][2] or ''
                row_others = [r[2] for k, r in enumerate(t['rows'][ri]) if k not in (0, ci) and r[2]]
                cells.append(dict(r=ri, kind=c[0], value=c[1], orig=c[2], label=label, concepts=concepts,
                                  has_pct='%' in c[2], plain=(ri, c) in plain,
                                  row_pct=sum('%' in x for x in row_others), row_dollar=sum('$' in x for x in row_others),
                                  row_n=len([x for x in row_others if re.search(r'\d', x)])))
            out.append(dict(file=name, group=group(name), ordinal=t['ordinal'], title=t['title'], status=t['status'],
                            header=t['headers'][ci], col=ci, n_pct=len(pct), n_plain=len(plain),
                            pct_first_row=min(pct_rows) == min(ri for ri, c in col if c[2] and re.search(r'\d', c[2])),
                            pct_max=str(max(pct_mag)) if pct_mag else None, cells=cells))
json.dump(out, open(out_json, 'w', encoding='utf-8'), indent=0)
print(len(out), 'columns')
