"""Build the value-accuracy manifest from the baseline export.

    python -I manifest.py EXPORT_DIR --out manifest.json [--src <main checkout>/src]

EXPORT_DIR is the baseline: main's src exported with the extended export_tables.py of the
header-detection audit. --src must be that same src; it supplies convert_cell and the
header-detection patterns, and defaults to the src of the checkout holding this script.

Each entry is {filing, ordinal, source_row, source_column, kind, displayed, baseline_value}:
- filing and ordinal name the export table; source_row and source_column are the value
  origin of the copy cell: the cell_sources origin whose source text holds a digit, or,
  for a cell without digits (such as '$ -'), the first origin with text that is not a
  structural marker;
- displayed is the copy cell's original text in the baseline (the joined text of its
  origins; a split '%' stays in the next copy cell);
- baseline_value is the baseline copy cell's value (a decimal string for a number).

The kinds are adapted from the fact pack's scripts in fact-pack-scripts/:
- percent_row_joined (classify.py, partb.py): a plain cell of a mixed column, classed as a
  percent row and exported as an unscaled number. A mixed column is a value column (not
  column 0) of a table that is not source_text_only, holding a number whose original has
  '%' and a plain number (no '%', no '$', a complete token). classify.py's signals decide
  each plain cell, first decisive one wins: year-heading, fact, label, section, magnitude,
  row, header, title; then the block pass (nearest decided cell above, else below,
  crossing only neutral section rows, with a magnitude limit), else outsized or unclear.
  Unscaled: a number that is neither 0 nor the displayed number / 100.
- percent_row_split (partb.py): a digit cell without '%' whose right neighbour copy cell is
  only a '%' or ')%' marker, exported as an unscaled number.
- identifier_misread / identifier_true (partd.py, partd2.py): every nonempty cell of a value
  column of a table that is not source_text_only, whose header makes _identifier_column
  true and is not a period header, and that holds at least one digit cell. The column is
  true when its identifier header part (whitespace collapsed) is one of partd2.py's
  TRUE_PARTS, and misread otherwise.
"""

import argparse
import collections
import json
import os
import re
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))

# classify.py
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

# partb.py
SPLIT = re.compile(r'^\)?\s*%\s*\)?$')

# partd2.py
TRUE_PARTS = {'Incorporated by Reference', 'Exhibit Description', 'Notes', 'Maturities (calendar year)', 'Issue date',
              'Earliest redemption date(b)', 'Issuance Date', 'Maturity Date', 'Payment Date', 'Contractual Maturity Date',
              'Transaction Date', 'Date of Issuance', 'Grant Date'}

MARKERS = {'$', '(', ')', '%', ')%'}
KINDS = ('percent_row_joined', 'percent_row_split', 'identifier_misread', 'identifier_true')
GROUPS = ('META', 'NVDA', 'RDDT', 'Others')


def group(name):
    company = name.split('__')[0]
    return company if company in GROUPS[:3] else 'Others'


def digits(text):
    return bool(text and re.search(r'\d', text))


def concept_class(concepts):
    specific = [x.split(':')[-1] for x in concepts if not GENERIC_CONCEPT.search(x)]
    if not specific:
        return None
    return 'pct' if any(re.search(r'To[A-Z]\w*Assets$', x) or
                        (x.startswith('EffectiveIncomeTaxRate') and not x.endswith('Amount')) or
                        (PCT_CONCEPT.search(x) and not AMT_CONCEPT.search(x))
                        for x in specific) else 'amt'


def percent_rows(table, num):
    """classify.py on one table: yields (row, column, cls, outcome) for each plain cell of each mixed column."""
    facts = {}
    for f in table['facts']:
        facts.setdefault((f[0], f[1]), []).append(f[3])
    rows = table['rows']
    width = len(table['headers'])
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
        header = table['headers'][ci]
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
            concepts = [x for s in table['cell_sources'][ri][ci] for x in facts.get(tuple(s), [])]
            section = next((labels[k] for k in range(ri - 1, -1, -1) if label_only[k]), '')
            others = [r[2] for k, r in enumerate(rows[ri]) if k not in (0, ci) and digits(r[2])]
            fact_cls = concept_class(concepts)
            cls = None
            if not label and re.fullmatch(r'(?:19|20)\d{2}', c[2].strip()):
                cls = 'amt'
            elif fact_cls:
                cls = fact_cls
            elif AMT_WORDS.search(label):
                cls = 'amt'
            elif PCT_WORDS.search(label):
                cls = 'pct'
            elif section and PCT_WORDS.search(section) and not AMT_WORDS.search(section):
                cls = 'pct'
            elif section and AMT_WORDS.search(section):
                cls = 'amt'
            elif ',' in c[2] and all(v < 1000 for v in pct_vals):
                cls = 'amt'
            elif others and 2 * sum('%' in x for x in others) >= len(others) and not any('$' in x for x in others):
                cls = 'pct'
            elif PCT_HEADER.search(header):
                cls = 'pct'
            elif TITLE_PCT.search(table['title'] or ''):
                cls = 'pct'
            if cls:
                decided[ri] = cls
            value = Decimal(c[1]) if c[0] == 'number' and c[1] is not None else None
            parsed = num(c[2])
            outcome = ('text' if c[0] != 'number' else
                       'zero' if value is not None and value == 0 else
                       'scaled' if value is not None and parsed is not None and value == parsed / 100 else 'unscaled')
            cells.append(dict(r=ri, orig=c[2], cls=cls, outcome=outcome))
        # second pass: neighbours
        limit = max([Decimal(100)] + [2 * v for v in pct_vals])
        for e in cells:
            if e['cls']:
                continue
            ri = e['r']
            cls = None
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
                e['cls'] = cls
            elif abs(num(e['orig'])) > limit:
                e['cls'] = 'amt'
            else:
                e['cls'] = 'unclear'
        for e in cells:
            yield e['r'], ci, e['cls'], e['outcome']


def split_rows(table, num):
    """partb.py's split-% scan on one table: yields (row, column, outcome)."""
    for ri, row in enumerate(table['rows']):
        for ci in range(1, len(row) - 1):
            c, right = row[ci], row[ci + 1]
            if right[2] and SPLIT.match(right[2].strip()) and c[2] and re.search(r'\d', c[2]) and '%' not in c[2]:
                p = num(c[2] + (')' if right[2].strip().startswith(')') else ''))
                outcome = 'text' if c[0] != 'number' else ('zero' if Decimal(c[1]) == 0 else
                           'scaled' if p is not None and Decimal(c[1]) == p / 100 else 'unscaled')
                yield ri, ci, outcome


def identifier_columns(table, m):
    """partd.py and partd2.py on one table: yields (column, kind) for each identifier column with digit cells."""
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
            return part
        return None

    for ci, h in enumerate(table['headers']):
        if ci == 0:
            continue
        period_header = all(m._PERIOD.fullmatch(p) for p in h.split(' — '))
        if not m._identifier_column(h) or period_header:
            continue
        part = ident(h)
        assert part, (table['ordinal'], h)
        if any(ci < len(row) and digits(row[ci][2]) for row in table['rows']):
            kind = 'identifier_true' if re.sub(r'\s+', ' ', part) in TRUE_PARTS else 'identifier_misread'
            yield ci, kind


def value_origin(table, ri, ci, text_at):
    """The origin holding the digits; for a cell without digits, the first origin with text that is not
    a structural marker ($, (, ), %), else the first origin with text."""
    origins = [tuple(s) for s in table['cell_sources'][ri][ci]]
    with_digits = [o for o in origins if digits(text_at.get(o))]
    if with_digits:
        return with_digits[0], len(with_digits)
    with_text = [o for o in origins if (text_at.get(o) or '').strip()]
    values = [o for o in with_text if text_at[o].strip() not in MARKERS]
    return (values or with_text or origins)[0], 0


def build(export_dir, num, m):
    entries, extra = [], collections.Counter()
    for name in sorted(os.listdir(export_dir)):
        data = json.load(open(os.path.join(export_dir, name), encoding='utf-8'))
        for table in data['tables']:
            if table['status'] == 'source_text_only' or not table['rows']:
                continue
            text_at = {(c[0], c[1]): c[4] for c in table['source_cells']}
            cells = []
            for ri, ci, cls, outcome in percent_rows(table, num):
                if cls == 'pct' and outcome == 'unscaled':
                    cells.append((ri, ci, 'percent_row_joined'))
            for ri, ci, outcome in split_rows(table, num):
                if outcome == 'unscaled':
                    cells.append((ri, ci, 'percent_row_split'))
            for ci, kind in identifier_columns(table, m):
                for ri, row in enumerate(table['rows']):
                    if ci < len(row) and (row[ci][2] or '').strip():
                        cells.append((ri, ci, kind))
            for ri, ci, kind in cells:
                kind_, value, original = table['rows'][ri][ci]
                (sr, sc), digit_origins = value_origin(table, ri, ci, text_at)
                extra['several digit origins'] += digit_origins > 1
                entries.append(dict(filing=data['file'], ordinal=table['ordinal'], source_row=sr, source_column=sc,
                                    kind=kind, displayed=original, baseline_value=value,
                                    _copy=(ri, ci), _type=kind_, _facts=sum(
                                        1 for f in table['facts'] if [f[0], f[1]] in table['cell_sources'][ri][ci])))
    return entries, extra


def summary(entries):
    lines = []
    for kind in KINDS:
        chosen = [e for e in entries if e['kind'] == kind]
        tables = {(e['filing'], e['ordinal']) for e in chosen}
        columns = {(e['filing'], e['ordinal'], e['_copy'][1]) for e in chosen}
        with_digits = sum(digits(e['displayed']) for e in chosen)
        lines.append(f'{kind}: cells={len(chosen)} digit_cells={with_digits} tables={len(tables)} '
                     f'columns={len(columns)} cells_with_facts={sum(bool(e["_facts"]) for e in chosen)}')
        for g in GROUPS:
            part = [e for e in chosen if group(e['filing']) == g]
            if part:
                lines.append(f'    {g}: cells={len(part)} digit_cells={sum(digits(e["displayed"]) for e in part)} '
                             f'tables={len({(e["filing"], e["ordinal"]) for e in part})} '
                             f'columns={len({(e["filing"], e["ordinal"], e["_copy"][1]) for e in part})} '
                             f'baseline_types={dict(collections.Counter(e["_type"] for e in part))}')
    return lines


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('export_dir')
    parser.add_argument('--out', required=True)
    parser.add_argument('--src', default=os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', 'src')))
    args = parser.parse_args()
    sys.path.insert(0, os.path.abspath(args.src))
    import sec2md.xlsx_tables as m
    from sec2md.xlsx_values import convert_cell
    assert os.path.realpath(m.__file__).startswith(os.path.realpath(args.src)), m.__file__

    def num(text):
        v = convert_cell(text.strip(), role='number')
        return v.value if isinstance(v.value, Decimal) else None

    entries, extra = build(args.export_dir, num, m)
    keys = collections.Counter((e['filing'], e['ordinal'], e['source_row'], e['source_column']) for e in entries)
    shared = {k for k, v in keys.items() if v > 1}
    for line in summary(entries):
        print(line)
    print(f'entries={len(entries)} coordinates shared by two entries={len(shared)} '
          f'cells with several digit origins={extra["several digit origins"]}')
    for k in sorted(shared):
        print('   shared:', k, [e['kind'] for e in entries if (e['filing'], e['ordinal'], e['source_row'], e['source_column']) == k])
    entries.sort(key=lambda e: (e['filing'], e['ordinal'], e['source_row'], e['source_column'], KINDS.index(e['kind'])))
    fields = ('filing', 'ordinal', 'source_row', 'source_column', 'kind', 'displayed', 'baseline_value')
    with open(args.out, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('[\n' + ',\n'.join(json.dumps({f: e[f] for f in fields}, ensure_ascii=False) for e in entries) + '\n]\n')


if __name__ == '__main__':
    main()
