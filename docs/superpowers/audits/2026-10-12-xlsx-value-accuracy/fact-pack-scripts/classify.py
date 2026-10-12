"""Classify plain cells of mixed percent columns. python -I classify.py EXPORT_DIR OUT_JSON

A mixed column: a value column (not column 0) of a non-source_text_only table holding at least one
number whose original text has '%' and at least one plain number (no '%', no '$', a complete number).
Each plain cell gets a class: pct (a percent row), amt (amount, count, duration, year: not a percent)
or unclear, and the signal that decided it. Signals, first decisive one wins:
  year-heading  a bare year under a blank label -> amt (a stranded header year)
  fact      XBRL concept on the cell: ratio/percent/rate/margin/yield names -> pct; other specific concept -> amt
  label     row label: amount/unit/duration words -> amt; percent words -> pct
  section   nearest label-only row above: percent words -> pct; amount words -> amt
  row       other value cells of the row carry '%' and none '$' -> pct
  header    column header percent words -> pct
  title     table title says 'as a percentage of' / '% of' -> pct
  magnitude a thousands separator while every % cell in the column is < 1000 -> amt
  block     (second pass) class of the nearest decided cell above, crossing only neutral section rows;
            else the nearest decided cell below
Outcome: number exported unscaled (value == displayed number), scaled (value == number/100) or text.
"""
import json, os, re, sys
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
from sec2md.xlsx_values import convert_cell

src_dir, out_json = sys.argv[1:3]
GENERIC_CONCEPT = re.compile(r'MeasurementInput|ValuationTechnique')
PCT_CONCEPT = re.compile(r'To[A-Z]\w*Assets$|Ratio|Percent|Percentage|Margin|Yield|Rate')
AMT_CONCEPT = re.compile(r'Amount$|^IncomeTaxReconciliation|Expense$|Benefit$|Revenues?$|Assets$|Liabilities$|Shares$|Price$')
PCT_WORDS = re.compile(r'%|\bpercent|\bratios?\b|\brates?\b|\bmargins?\b|\byields?\b|\bgrowth\b|\bchange\b'
                       r'|\bmix\b|\bROE\b|\bROTCE\b|\bROA\b|\bvolatility\b', re.I)
AMT_WORDS = re.compile(r'\$|\bdollars?\b|\bamounts?\b|\bshares\b|\bper share\b|\bin (?:thousands|millions|billions)\b'
                       r'|\bnumber of\b|\bheadcount\b|\bemployees\b|\byears?\)|\bin years\b|\(years\)|\bterm\b|\bprice\b'
                       r'|\bfair value\b|\bDAUq?\b|\busers\b|\bARPU\b|\bunits?\b|\bRWA\b|\brisk-weighted assets\b'
                       r'|\bexposure\b|\bdays\b|\bmonths\b', re.I)
TITLE_PCT = re.compile(r'\bpercentages? of\b|\bpercent of\b|% of\b|\bas a percentage\b', re.I)
PCT_HEADER = re.compile(r'%|\bpercent|\bratio|\brates?\b|\bmargin|\byield|\bgrowth|\bchange\b', re.I)


def group(name):
    c = name.split('__')[0]
    return c if c in ('META', 'NVDA', 'RDDT') else 'Others'


def num(text):
    v = convert_cell(text.strip(), role='number')
    return v.value if isinstance(v.value, Decimal) else None


def digits(text):
    return bool(text and re.search(r'\d', text))


def concept_class(concepts):
    specific = [x.split(':')[-1] for x in concepts if not GENERIC_CONCEPT.search(x)]
    if not specific:
        return None
    return 'pct' if any(re.search(r'To[A-Z]\w*Assets$', x) or
                        (x.startswith('EffectiveIncomeTaxRate') and not x.endswith('Amount')) or (PCT_CONCEPT.search(x) and not AMT_CONCEPT.search(x))
                        for x in specific) else 'amt'


out = []
for name in sorted(os.listdir(src_dir)):
    data = json.load(open(os.path.join(src_dir, name), encoding='utf-8'))
    for t in data['tables']:
        if t['status'] == 'source_text_only' or not t['rows']:
            continue
        facts = {}
        for f in t['facts']:
            facts.setdefault((f[0], f[1]), []).append(f[3])
        rows = t['rows']
        width = len(t['headers'])
        labels = [(r[0][2] or '').strip() for r in rows]
        label_only = [bool(labels[i]) and not any(digits(c[2]) for c in r[1:]) for i, r in enumerate(rows)]
        neutral = [label_only[i] and not PCT_WORDS.search(labels[i]) and not AMT_WORDS.search(labels[i])
                   for i in range(len(rows))]
        for ci in range(1, width):
            col = [(ri, rows[ri][ci]) for ri in range(len(rows)) if ci < len(rows[ri])]
            pct = [(ri, c) for ri, c in col if digits(c[2]) and '%' in c[2]]
            plain = [(ri, c) for ri, c in col if digits(c[2]) and '%' not in c[2] and '$' not in c[2]
                     and num(c[2]) is not None]
            if not pct or not plain:
                continue
            pct_vals = [abs(num(c[2].replace('%', '')) or 0) for _, c in pct]
            header = t['headers'][ci]
            decided = {}
            cells = []
            for ri, c in col:
                if not digits(c[2]):
                    continue
                if '%' in c[2]:
                    decided[ri] = 'pct'
                    continue
                if '$' in c[2]:
                    decided[ri] = 'amt'
                    continue
                if num(c[2]) is None:
                    continue
                label = labels[ri]
                concepts = [x for s in t['cell_sources'][ri][ci] for x in facts.get(tuple(s), [])]
                section = next((labels[k] for k in range(ri - 1, -1, -1) if label_only[k]), '')
                others = [r[2] for k, r in enumerate(rows[ri]) if k not in (0, ci) and digits(r[2])]
                fact_cls = concept_class(concepts)
                cls = why = None
                if not label and re.fullmatch(r'(?:19|20)\d{2}', c[2].strip()):
                    cls, why = 'amt', 'year-heading'
                elif fact_cls:
                    cls, why = fact_cls, 'fact'
                elif AMT_WORDS.search(label):
                    cls, why = 'amt', 'label'
                elif PCT_WORDS.search(label):
                    cls, why = 'pct', 'label'
                elif section and PCT_WORDS.search(section) and not AMT_WORDS.search(section):
                    cls, why = 'pct', 'section'
                elif section and AMT_WORDS.search(section):
                    cls, why = 'amt', 'section'
                elif ',' in c[2] and all(v < 1000 for v in pct_vals):
                    cls, why = 'amt', 'magnitude'
                elif others and 2 * sum('%' in x for x in others) >= len(others) and not any('$' in x for x in others):
                    cls, why = 'pct', 'row'
                elif PCT_HEADER.search(header):
                    cls, why = 'pct', 'header'
                elif TITLE_PCT.search(t['title'] or ''):
                    cls, why = 'pct', 'title'
                if cls:
                    decided[ri] = cls
                value = Decimal(c[1]) if c[0] == 'number' and c[1] is not None else None
                parsed = num(c[2])
                outcome = ('text' if c[0] != 'number' else
                           'zero' if value is not None and value == 0 else 'scaled' if value is not None and parsed is not None and value == parsed / 100 else 'unscaled')
                cells.append(dict(r=ri, label=label, section=section, orig=c[2], kind=c[0], value=c[1],
                                  concepts=concepts, cls=cls, why=why, outcome=outcome))
            # second pass: neighbours
            for e in cells:
                if e['cls']:
                    continue
                ri = e['r']
                cls = None
                limit = max([Decimal(100)] + [2 * v for v in pct_vals])
                for k in range(ri - 1, -1, -1):
                    if label_only[k] and not neutral[k]:
                        break
                    if k in decided:
                        # a percent block does not take a value larger than any percent in the column
                        cls = decided[k] if decided[k] != 'pct' or abs(num(e['orig'])) <= limit else None
                        break
                if cls is None:
                    for k in range(ri + 1, len(rows)):
                        if label_only[k] and not neutral[k]:
                            break
                        if k in decided:
                            cls = decided[k] if decided[k] != 'pct' or abs(num(e['orig'])) <= limit else None
                            break
                if cls:
                    e['cls'], e['why'] = cls, 'block'
                elif abs(num(e['orig'])) > limit:
                    e['cls'], e['why'] = 'amt', 'outsized'
                else:
                    e['cls'], e['why'] = 'unclear', None
            digit_rows = [ri for ri, c in col if digits(c[2])]
            out.append(dict(file=name, group=group(name), ordinal=t['ordinal'], title=t['title'], status=t['status'],
                            issues=len(t['issues']), header=header, col=ci, n_pct=len(pct), n_plain=len(plain),
                            pct_rows=[ri for ri, _ in pct], digit_rows=digit_rows, cells=cells))
json.dump(out, open(out_json, 'w', encoding='utf-8'), indent=0)
print(len(out), 'columns')
