"""Every difference between two exports of the same corpus by the same harness.

    python -I rerun_diff.py OLD_DIR NEW_DIR [--details diff.json]

Used to compare the branch export at one commit with the export at a later commit
(outputs/xlsx-value-accuracy/new-732544d against new). Table by table it compares status,
issues, headers, title and provenance, and cell by cell, at the same copy position, the type,
value, original text, number format, review reason and cell_sources. A table whose shape (row
or column count) differs is reported as a shape change, with its cells compared by value
origin (the cell_sources origin holding a digit, else the first origin with text). Every
difference is printed, with the row label and header of the cell, and a summary counts them
per kind of change, per group and per table.
"""

import argparse
import collections
import json
import os
import re
import sys

GROUPS = ('META', 'NVDA', 'RDDT', 'Others')
TABLE_FIELDS = ('status', 'title', 'provenance', 'headers', 'issues', 'facts', 'fact_attributes', 'source_cells')


def group(name):
    company = name.split('__')[0]
    return company if company in GROUPS[:3] else 'Others'


def cells(t):
    """{(row, column): (type, value, original, format, reason, sources)} of a table's copy cells."""
    out = {}
    for ri, row in enumerate(t['rows']):
        for ci, (kind, value, original) in enumerate(row):
            out[ri, ci] = (kind, value, original, t['cell_formats'][ri][ci], t['cell_reasons'][ri][ci],
                           [tuple(s) for s in t['cell_sources'][ri][ci]])
    return out


def by_origin(t):
    text_at = {(c[0], c[1]): c[4] for c in t['source_cells']}
    out = {}
    for (ri, ci), cell in cells(t).items():
        origins = cell[5]
        digit = [o for o in origins if re.search(r'\d', text_at.get(o) or '')]
        texts = [o for o in origins if (text_at.get(o) or '').strip()]
        key = (digit or texts or [None])[0]
        if key is not None:
            out[key] = (ri, ci), cell
    return out


def kind_of(old, new):
    if old is None or new is None:
        return 'cell on one side only'
    if old[0] == 'number' and new[0] == 'number' and old[1] != new[1]:
        return 'number value changed'
    if old[0] != new[0]:
        return f'{old[0]} to {new[0]}'
    if old[0] == 'number':
        return 'number format, reason or sources changed' if old[1:] != new[1:] else 'same'
    if old[2] != new[2]:
        return 'text changed'
    if old[4] != new[4]:
        return 'text reason changed'
    return 'text format or sources changed'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('old')
    parser.add_argument('new')
    parser.add_argument('--details')
    args = parser.parse_args()
    names = sorted(os.listdir(args.new))
    assert names == sorted(os.listdir(args.old)), 'the two exports hold different filings'
    diffs, tables = [], []
    for name in names:
        old = {t['ordinal']: t for t in json.load(open(os.path.join(args.old, name), encoding='utf-8'))['tables']}
        new = {t['ordinal']: t for t in json.load(open(os.path.join(args.new, name), encoding='utf-8'))['tables']}
        assert sorted(old) == sorted(new), name
        filing = name[:-5]
        for ordinal in sorted(new):
            o, n = old[ordinal], new[ordinal]
            fields = [f for f in TABLE_FIELDS if o[f] != n[f]]
            shape = (len(o['rows']), len(o['headers'])) != (len(n['rows']), len(n['headers']))
            if fields or shape:
                tables.append(dict(filing=filing, ordinal=ordinal, fields=fields, shape=shape,
                                   old_status=o['status'], new_status=n['status']))
            if shape:
                oc, nc = by_origin(o), by_origin(n)
                pairs = [(k, oc.get(k), nc.get(k)) for k in sorted(set(oc) | set(nc))]
                pairs = [(k, a and a[1], b and b[1], (b or a)[0]) for k, a, b in pairs]
            else:
                oc, nc = cells(o), cells(n)
                pairs = [(k, oc[k], nc[k], k) for k in sorted(nc)]
            for key, a, b, (ri, ci) in pairs:
                if a == b:
                    continue
                t = n if b is not None else o
                diffs.append(dict(filing=filing, ordinal=ordinal, copy=[ri, ci], kind=kind_of(a, b),
                                  label=t['rows'][ri][0][2] if t['rows'] else None, header=t['headers'][ci],
                                  old=a and list(a[:5]), new=b and list(b[:5]),
                                  old_sources=a and a[5], new_sources=b and b[5]))
    print(f'Tables with any table-level difference: {len(tables)}')
    for t in tables:
        print(f"  {t['filing']} #{t['ordinal']}: {t['old_status']} -> {t['new_status']}; fields {t['fields']}"
              + ('; SHAPE CHANGED' if t['shape'] else ''))
    print(f'\nCells that differ: {len(diffs)}')
    for k, v in sorted(collections.Counter(d['kind'] for d in diffs).items()):
        print(f'  {k}: {v}')
    for k, v in sorted(collections.Counter(group(d['filing']) for d in diffs).items()):
        print(f'  group {k}: {v}')
    for d in diffs:
        print(f"  {d['filing']} #{d['ordinal']} {d['copy']} [{d['kind']}] label {d['label']!r} header {d['header']!r}"
              f"\n      old {d['old']} sources {d['old_sources']}\n      new {d['new']} sources {d['new_sources']}")
    if args.details:
        with open(args.details, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(dict(tables=tables, cells=diffs), handle, ensure_ascii=False, indent=1, default=str)


if __name__ == '__main__':
    main()
