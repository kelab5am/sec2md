"""Every changed cell outside the manifest, the coverage cost, and the header-detection checks
(spec Acceptance 5, 7 and 8).

    python -I changes.py BASE_DIR NEW_DIR --manifest manifest.json --src <branch checkout>/src
                         [--details changes.json]
                         [--all-facts BASE_ALL_FACTS.json NEW_ALL_FACTS.json]
                         [--stacked-scan <header-detection outputs>/task-7/stacked_scan.py]

Run it from the checkout root (the export JSONs name their filings by paths relative to it).
BASE_DIR is main's export and NEW_DIR the branch's (export_tables.py). --src is the branch's
src; dispositions.py, beside this script, supplies the Rule P and Rule I evidence, the nested
facts and the split-% audit (see its docstring), so a changed cell is judged by the same reading
of the spec as a manifest entry (dispositions.expected_outcome).

Matching. A copy cell is keyed by its value origin, as the manifest is: the cell_sources origin
whose source text holds a digit, else the first origin whose text is not a structural marker
($ ( ) % )%), else the first origin with text. Empty copy cells have no key. Keys are unique per
table (asserted). A base cell and a new cell with the same key, filing and table are the same
cell. A cell changed when its type, value, original text, format or review reason differs, or
when it has a key on one side only. Manifest entries are left out: dispositions.py checks them.
Tables whose status or headers changed are listed too.

Classes. Each changed cell gets the first class whose rule holds:
- marker joined to its neighbour: a base cell whose text is only '%' or ')%', whose origin now
  sits in its neighbour's copy cell (spec P4 attachment, or column grouping under one leaf); the
  neighbour's own disposition is checked where it is listed (manifest or changed cell).
- number to flagged text: a base number, now text with a review reason. The reason must be the
  one the spec's rules give the cell (dispositions.rule_p, or Rule I under an identifier heading).
- number rescaled: a base number, now a different number. It must be a proven percent equal to
  D / 100 (D, the displayed number) with the proof named. Each is listed.
- text to number: a base text cell, now a number. It must be D / 100 with a percent proof, or D
  with a quantity or non-percent proof. Each is listed.
- format or reason only: the same type and value, with another format or reason. A number's
  format must be the one its token and proof give; a reason must be the spec's.
- other: anything else, listed in full.
Every new number must also sit under its own heading: its copy column's header must be the
header above its value origin's source column (header_ok). A new number that fails its class's
expectation or this check is not as the spec gives: the gate fails.

Coverage cost (Acceptance 7): every cell, manifest entries included, that is a base number and a
new text cell with a review reason, counted per group, per manifest kind (or 'outside the
manifest') and per table.

Header-detection checks (Acceptance 8):
- --all-facts: all_facts.py's --details JSON on each export. Every mismatch on NEW_DIR must be a
  mismatch on BASE_DIR (filing, ordinal and source cell).
- --stacked-scan: the gate 6 scans of the header-detection audit (scan_a and scan_b, imported
  unchanged from the given file) on both exports. Every hit table on NEW_DIR must be a hit on
  BASE_DIR.

Exit status 1 when any gate fails.
"""

import argparse
import collections
import importlib.util
import json
import os
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
MARKERS = {'$', '(', ')', '%', ')%'}
GROUPS = ('META', 'NVDA', 'RDDT', 'Others')
FIELDS = ('type', 'value', 'original', 'format', 'reason')


def group(name):
    company = name.split('__')[0]
    return company if company in GROUPS[:3] else 'Others'


def keyed(table):
    """{value origin: (row, column)} for every copy cell with text (see Matching)."""
    out = {}
    text_at = table.text_at
    for ri, row in enumerate(table.t['cell_sources']):
        for ci, sources in enumerate(row):
            origins = [tuple(s) for s in sources]
            digits = [o for o in origins if D.has_digit(text_at.get(o))]
            texts = [o for o in origins if (text_at.get(o) or '').strip()]
            values = [o for o in texts if text_at[o].strip() not in MARKERS]
            key = (digits or values or texts or [None])[0]
            if key is None:
                continue
            assert key not in out, (table.filing, table.ordinal, key)
            out[key] = (ri, ci)
    return out


def describe(table, ri, ci):
    cell = table.cell(ri, ci)
    return dict({k: cell[k] for k in FIELDS}, copy=[ri, ci], header=table.t['headers'][ci],
                label=table.row_label(ri), sources=[[*s, table.text_at.get(s)] for s in cell['sources']])


def source_header(table, col):
    """The flattened header above one source column, as prepare_table builds a copy column's:
    the distinct header cells with text, unit lines excluded, joined by ' — '."""
    cells = list(dict.fromkeys(table.grid[r][col] for r in range(table.header_count)))
    return ' — '.join(c.text for c in cells if c is not None and c.text and not D.M._UNIT_LINE.search(c.text))


def header_ok(table, ri, ci):
    """A number sits under its own heading: the copy column's header is the header above the
    column of the cell's value origin (a positional 'Column N' header has nothing to compare)."""
    origins = table.digit_origins(ri, ci)
    header = table.t['headers'][ci]
    own = {source_header(table, o[1]) for o in origins}
    return not origins or own == {header} or (own == {''} and header.startswith('Column '))


def classify(name, ordinal, key, base, new, b, n):
    """One changed cell: its class, the spec's expectation for the new cell, and whether it holds."""
    item = dict(filing=name, ordinal=ordinal, origin=list(key), base=b and describe(base, *b),
                new=n and describe(new, *n))
    if b and n is None:
        bc = item['base']
        if bc['original'].strip() in ('%', ')%') and key in new.where:
            host = describe(new, *new.where[key])
            # The marker moved into its neighbour's copy cell; the neighbour is checked where it is listed.
            item.update(cls='marker joined to its neighbour', host=host, valid=bc['original'].strip() in host['original'])
        else:
            item.update(cls='other: base only', valid=bc['type'] != 'number')
        return item
    if n is None or b is None:
        nc = item['new']
        item.update(cls='other: new only', valid=nc['type'] != 'number')
        if nc['type'] == 'number' or D.has_digit(nc['original']):
            disposition, expected, proofs = D.expected_outcome(new, *n)
            item.update(disposition=disposition, proofs=proofs, valid=D.matches(new.cell(*n), expected))
        if nc['type'] == 'number':
            item['header_ok'] = header_ok(new, *n)
            item['valid'] = item['valid'] and item['header_ok']
        return item
    bc, nc = item['base'], item['new']
    digit = D.has_digit(nc['original'])
    disposition, expected, proofs = D.expected_outcome(new, *n) if digit else (None, None, [])
    holds = D.matches(new.cell(*n), expected) if digit else None
    if bc['type'] == 'number' and nc['type'] == 'text' and nc['reason']:
        cls = 'number to flagged text'
    elif bc['type'] == 'number' and nc['type'] == 'number' and Decimal(bc['value']) != Decimal(nc['value']):
        cls = 'number rescaled'
    elif bc['type'] == 'text' and nc['type'] == 'number':
        cls = 'text to number'
    elif bc['type'] == nc['type'] and bc['value'] == nc['value'] and bc['original'] == nc['original']:
        cls = 'format or reason only'
    else:
        cls = 'other'
    if cls == 'number rescaled':
        holds = holds and disposition == 'proven percent'
    if not digit:
        holds = nc['type'] != 'number'
    if nc['type'] == 'number':
        item['header_ok'] = header_ok(new, *n)
        holds = holds and item['header_ok']
    item.update(cls=cls, disposition=disposition, proofs=proofs, valid=bool(holds),
                expected=None if expected is None else {k: (sorted(v, key=str) if isinstance(v, set) else str(v))
                                                        for k, v in expected.items()})
    return item


def stacked(scan, directory):
    hits = {}
    for name in sorted(os.listdir(directory)):
        data = json.load(open(os.path.join(directory, name), encoding='utf-8'))
        for t in data['tables']:
            if t['status'] == 'source_text_only':
                continue
            a, b = scan.scan_a(t), scan.scan_b(t)
            if a or b:
                hits[(data['file'], t['ordinal'])] = dict(a=bool(a), b=bool(b), status=t['status'], title=t['title'][:60])
    return hits


def main():
    global D
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('base')
    parser.add_argument('new')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--src', required=True)
    parser.add_argument('--details')
    parser.add_argument('--all-facts', nargs=2, metavar=('BASE_JSON', 'NEW_JSON'))
    parser.add_argument('--stacked-scan')
    args = parser.parse_args()
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.abspath(args.src))
    import dispositions as D
    import sec2md.xlsx_tables as M
    from sec2md.xlsx_values import convert_cell
    assert os.path.realpath(M.__file__).startswith(os.path.realpath(args.src)), M.__file__
    D.M, D.convert_cell = M, convert_cell

    manifest = json.load(open(args.manifest, encoding='utf-8'))
    kinds = {(e['filing'], e['ordinal'], e['source_row'], e['source_column']): e['kind'] for e in manifest}
    names = sorted(n[:-5] for n in os.listdir(args.new))
    assert names == sorted(n[:-5] for n in os.listdir(args.base))
    changed, tables, cost = [], [], collections.Counter()
    for name in names:
        base_tables = {t['ordinal']: t for t in json.load(open(os.path.join(args.base, name + '.json'), encoding='utf-8'))['tables']}
        new_tables = {t['ordinal']: t for t in json.load(open(os.path.join(args.new, name + '.json'), encoding='utf-8'))['tables']}
        assert sorted(base_tables) == sorted(new_tables), name
        nested = D.nested_facts(json.load(open(os.path.join(args.new, name + '.json'), encoding='utf-8'))['path'])
        for ordinal in sorted(new_tables):
            bt, nt = base_tables[ordinal], new_tables[ordinal]
            if (bt['status'], bt['headers']) != (nt['status'], nt['headers']):
                tables.append(dict(filing=name, ordinal=ordinal, base_status=bt['status'], new_status=nt['status'],
                                   base_headers=bt['headers'], new_headers=nt['headers']))
            base, new = D.Table(name, bt, nested), D.Table(name, nt, nested)
            if nt['status'] != 'source_text_only':
                D.audit_splits(base, new)  # marks the values whose split '%' was refused
            bk, nk = keyed(base), keyed(new)
            for key in sorted(set(bk) | set(nk), key=lambda k: (k is None, k)):
                b, n = bk.get(key), nk.get(key)
                if b and n:
                    if all(base.cell(*b)[f] == new.cell(*n)[f] for f in FIELDS):
                        continue
                    bc, nc = base.cell(*b), new.cell(*n)
                    if bc['type'] == 'number' and nc['type'] == 'text' and nc['reason']:
                        kind = kinds.get((name, ordinal, *key), 'outside the manifest')
                        cost[(group(name), kind, name, ordinal)] += 1
                if (name, ordinal, *key) in kinds:
                    continue
                changed.append(classify(name, ordinal, key, base, new, b, n))

    print(f'Tables whose status or headers changed: {len(tables)}')
    for t in tables:
        print(f"  {t['filing']} #{t['ordinal']}: {t['base_status']} -> {t['new_status']}")
        if t['base_headers'] != t['new_headers']:
            print(f"    headers {t['base_headers']}\n         -> {t['new_headers']}")
    print(f'\nChanged cells outside the manifest: {len(changed)}')
    for cls, n in sorted(collections.Counter(c['cls'] for c in changed).items()):
        valid = sum(c['valid'] for c in changed if c['cls'] == cls)
        print(f'  {cls}: {n} (as the spec gives: {valid})')
        for k, m in sorted(collections.Counter((c.get('disposition') or '-', ' + '.join(c.get('proofs') or []))
                                               for c in changed if c['cls'] == cls).items()):
            print(f'      {k[0]}' + (f' [{k[1]}]' if k[1] else '') + f': {m}')
    print('\nPer group and class:')
    for g in GROUPS:
        counts = collections.Counter(c['cls'] for c in changed if group(c['filing']) == g)
        if counts:
            print(f'  {g}: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    wrong = [c for c in changed if not c['valid']]
    numbers = [c for c in wrong if c['new'] and c['new']['type'] == 'number']
    print(f'\nChanged cells not as the spec gives: {len(wrong)}, of which new numbers: {len(numbers)}')
    for c in wrong:
        print(f"  [{c['cls']}] {c['filing']} #{c['ordinal']} {c['origin']} base {c['base'] and {k: c['base'][k] for k in FIELDS}}"
              f"\n      new {c['new'] and {k: c['new'][k] for k in FIELDS}} [{c.get('disposition')}] expected {c.get('expected')}"
              f"\n      header {c['new'] and c['new']['header']!r} label {c['new'] and c['new']['label']!r}")
    print('\nEvery number rescaled or turned from text, one by one:')
    for c in changed:
        if c['cls'] in ('number rescaled', 'text to number') or (c['cls'].startswith('other') and c['new']
                                                                  and c['new']['type'] == 'number'):
            print(f"  {c['filing']} #{c['ordinal']} {c['origin']} {c['new']['label'][:40]!r} | {c['new']['header'][:50]!r}: "
                  f"{c['base']['original'] if c['base'] else None!r} {c['base']['value'] if c['base'] else None} -> "
                  f"{c['new']['original']!r} {c['new']['value']} {c['new']['format']} [{c.get('disposition')}: "
                  f"{' + '.join(c.get('proofs') or [])}] {'ok' if c['valid'] else 'NOT AS THE SPEC GIVES'}")

    print('\nCoverage cost, number -> flagged text (Acceptance 7):')
    per_group = collections.Counter()
    for (g, kind, name, ordinal), n in cost.items():
        per_group[(g, kind)] += n
    for g in GROUPS:
        for kind in sorted({k for gg, k in per_group if gg == g}):
            print(f'  {g} {kind}: {per_group[(g, kind)]} cells in '
                  f'{len({(nm, o) for (gg, k, nm, o) in cost if gg == g and k == kind})} tables')
    print(f'  total: {sum(cost.values())} cells in {len({(nm, o) for (_, _, nm, o) in cost})} tables')
    per_table = collections.Counter()
    for (g, kind, name, ordinal), n in cost.items():
        per_table[(name, ordinal)] += n
    for (name, ordinal), n in sorted(per_table.items()):
        kinds_here = {k: m for (g, k, nm, o), m in cost.items() if (nm, o) == (name, ordinal)}
        print(f'    {name} #{ordinal}: {n} {kinds_here}')

    gates = dict(changes=not numbers and not wrong)
    if args.all_facts:
        def mismatches(path):
            return {(r['file'], m['ordinal'], tuple(m['cell'])) for r in json.load(open(path, encoding='utf-8'))
                    for m in r['mismatches']}
        base_m, new_m = mismatches(args.all_facts[0]), mismatches(args.all_facts[1])
        print(f'\nall_facts.py mismatches: base {len(base_m)}, new {len(new_m)}, new and not on base {len(new_m - base_m)}, '
              f'on base and not new {len(base_m - new_m)}')
        for m in sorted(new_m - base_m):
            print('  new mismatch:', m)
        gates['all_facts'] = not (new_m - base_m)
    if args.stacked_scan:
        spec = importlib.util.spec_from_file_location('stacked_scan', args.stacked_scan)
        scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scan)
        base_s, new_s = stacked(scan, args.base), stacked(scan, args.new)
        for label, part in (('scan A', 'a'), ('scan B', 'b')):
            bs = {k for k, v in base_s.items() if v[part]}
            ns = {k for k, v in new_s.items() if v[part]}
            print(f'\nstacked-block {label}: base {len(bs)}, new {len(ns)}, new and not on base {len(ns - bs)}')
            for k in sorted(ns - bs):
                print('  new hit:', k, new_s[k])
            gates[f'stacked {label}'] = not (ns - bs)
    print('\nGATES: ' + ', '.join(f'{k} {"pass" if v else "FAIL"}' for k, v in gates.items()))
    if args.details:
        with open(args.details, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(dict(tables=tables, changed=changed,
                           cost=[dict(group=g, kind=k, filing=nm, ordinal=o, cells=n) for (g, k, nm, o), n in sorted(cost.items())]),
                      handle, ensure_ascii=False, indent=1, default=str)
    sys.exit(0 if all(gates.values()) else 1)


if __name__ == '__main__':
    main()
