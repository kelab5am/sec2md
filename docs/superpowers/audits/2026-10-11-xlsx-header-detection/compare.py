"""Compare two export_tables.py runs table by table, by source coordinate.

    python -I compare.py BASE_DIR NEW_DIR --report compare.md --details compare.json

Records, per filing group (META, NVDA, RDDT, others):
- tables present in one run only (by ordinal) and a mismatch in filing sets;
- fallback tables and numeric source cells before and after;
- lost cells: a digit-bearing source cell that fed a number and no longer does;
- changed cells: a digit-bearing source cell whose number changed;
- promoted rows: every source row that was in the body and is now in the
  header (text-only rows included). For a table that used to fall back, every
  header row of the new table is listed, since it has no old body;
- balanced columns: values where Total assets equals Total liabilities and
  equity, compared by value.
The report lists every lost and changed cell and every promoted row in full.
"""

import argparse
import collections
import json
import os
import re
import sys

VAULT = ('META', 'NVDA', 'RDDT')
LIABILITIES_AND_EQUITY = re.compile(r"total liabilities(,| and)? .*(stockholders|shareholders|equity).*")


def group(name):
    company = name.split('__')[0]
    return company if company in VAULT else 'Others'


def texts_by_coordinate(table):
    return {(c[0], c[1]): c[4] for c in table['source_cells']}


def numbers(table):
    """{(row, column): value} for each digit-bearing source cell that feeds a numeric copy cell."""
    texts = texts_by_coordinate(table)
    out = {}
    for row, sources in zip(table['rows'], table['cell_sources']):
        for (kind, value, _), cell_sources in zip(row, sources):
            if kind != 'number':
                continue
            for source in cell_sources:
                if re.search(r'\d', texts.get(tuple(source), '')):
                    out[tuple(source)] = value
    return out


def body_rows(table):
    return {sources[0][0] for row in table['cell_sources'] for sources in row if sources}


def row_cells(table, row):
    return [[c[1], c[4]] for c in table['source_cells'] if c[0] == row and c[4].strip()]


def balanced(table):
    rows = {}
    for row in table['rows']:
        label = re.sub(r'\s+', ' ', str(row[0][1] or '')).strip().lower()
        if label == 'total assets':
            rows.setdefault('assets', row)
        elif LIABILITIES_AND_EQUITY.fullmatch(label):
            rows.setdefault('le', row)
    if len(rows) < 2:
        return set()
    return {a[1] for a, b in zip(rows['assets'][1:], rows['le'][1:])
            if a[0] == 'number' and b[0] == 'number' and a[1] == b[1]}


def compare(base, new):
    result = dict(fallback=[0, 0], numbers=[0, 0], balanced=[0, 0], lost=[], changed=[], promoted=[],
                  balance_lost=[], missing_tables=[], added_tables=[])
    old = {t['ordinal']: t for t in base['tables']}
    now = {t['ordinal']: t for t in new['tables']}
    result['missing_tables'] = sorted(set(old) - set(now))
    result['added_tables'] = sorted(set(now) - set(old))
    for ordinal in sorted(set(old) & set(now)):
        a, b = old[ordinal], now[ordinal]
        if [c[:5] for c in a['source_cells']] != [c[:5] for c in b['source_cells']]:
            result['missing_tables'].append(ordinal)  # same ordinal, different source table
            continue
        where = dict(file=base['file'], ordinal=ordinal, title=b['title'][:60])
        result['fallback'][0] += a['status'] == 'source_text_only'
        result['fallback'][1] += b['status'] == 'source_text_only'
        na, nb = numbers(a), numbers(b)
        result['numbers'][0] += len(na)
        result['numbers'][1] += len(nb)
        texts = texts_by_coordinate(a)
        for source, value in sorted(na.items()):
            if source not in nb:
                result['lost'].append(dict(where, source=list(source), text=texts[source], value=value,
                                           new_status=b['status']))
            elif nb[source] != value:
                result['changed'].append(dict(where, source=list(source), text=texts[source], before=value,
                                              after=nb[source]))
        if b['status'] != 'source_text_only':
            if a['status'] != 'source_text_only':
                promoted = body_rows(a) - body_rows(b)
            else:
                first_body = min(body_rows(b), default=0)
                promoted = {c[0] for c in b['source_cells'] if c[0] < first_body and c[4].strip()}
            for row in sorted(promoted):
                cells = row_cells(b, row)
                result['promoted'].append(dict(where, row=row, cells=cells,
                                               digits=any(re.search(r'\d', text) for _, text in cells[1:])))
        ba, bb = balanced(a), balanced(b)
        result['balanced'][0] += len(ba)
        result['balanced'][1] += len(bb)
        if ba - bb:
            result['balance_lost'].append(dict(where, values=sorted(ba - bb)))
    return result


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('base')
    parser.add_argument('new')
    parser.add_argument('--report', required=True)
    parser.add_argument('--details', required=True)
    args = parser.parse_args()
    names = sorted(set(os.listdir(args.base)) | set(os.listdir(args.new)))
    one_side = [n for n in names if not (os.path.exists(os.path.join(args.base, n))
                                         and os.path.exists(os.path.join(args.new, n)))]
    totals = collections.OrderedDict((g, collections.Counter()) for g in (*VAULT, 'Others'))
    details = []
    for name in names:
        if name in one_side:
            continue
        base = json.load(open(os.path.join(args.base, name), encoding='utf-8'))
        new = json.load(open(os.path.join(args.new, name), encoding='utf-8'))
        result = compare(base, new)
        details.append(dict(file=base['file'], **result))
        total = totals[group(base['file'])]
        for key in ('fallback', 'numbers', 'balanced'):
            total[key + '_before'] += result[key][0]
            total[key + '_after'] += result[key][1]
        for key in ('lost', 'changed', 'promoted', 'balance_lost', 'missing_tables', 'added_tables'):
            total[key] += len(result[key])
        total['files'] += 1
    with open(args.details, 'w', encoding='utf-8') as handle:
        json.dump(details, handle, indent=1)
    lines = [f'Filings in one run only: {one_side}', '',
             '| Group | Files | Fallback tables | Numeric cells | Balanced columns | Lost | Changed | '
             'Promoted rows | Balanced lost | Tables missing / added |', '|---|---|---|---|---|---|---|---|---|---|']
    for name, t in totals.items():
        if t['files']:
            lines.append(f"| {name} | {t['files']} | {t['fallback_before']} → {t['fallback_after']} | "
                         f"{t['numbers_before']:,} → {t['numbers_after']:,} | {t['balanced_before']} → "
                         f"{t['balanced_after']} | {t['lost']} | {t['changed']} | {t['promoted']} | "
                         f"{t['balance_lost']} | {t['missing_tables']} / {t['added_tables']} |")
    for key in ('missing_tables', 'added_tables', 'balance_lost', 'lost', 'changed'):
        lines += ['', f'## {key}', '']
        for d in details:
            items = d[key]
            if key.endswith('_tables') and items:
                lines.append(f"- {d['file']}: {items}")
            elif not key.endswith('_tables'):
                for item in items:
                    rest = {k: v for k, v in item.items() if k not in ('file', 'ordinal', 'title')}
                    lines.append(f"- {item['file']} #{item['ordinal']} {item['title']}: "
                                 + json.dumps(rest, ensure_ascii=False))
    lines += ['', '## promoted rows', '',
              'Every promoted row, in full: [column, text] for each non-empty source cell.', '']
    for d in details:
        for item in d['promoted']:
            lines.append(f"- {group(item['file'])} {'DIGITS ' if item['digits'] else ''}{item['file']} "
                         f"#{item['ordinal']} row {item['row']}: " + json.dumps(item['cells'], ensure_ascii=False))
    with open(args.report, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print('\n'.join(lines[:8]))


if __name__ == '__main__':
    main()
