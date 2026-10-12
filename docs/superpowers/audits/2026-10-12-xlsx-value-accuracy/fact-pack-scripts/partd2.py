"""Part D classification and base comparison."""
import collections, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
D = r'C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection'
TRUE_PARTS = {
    'Incorporated by Reference': 'exhibit index (form, exhibit no., file no., filing date)',
    'Exhibit Description': 'exhibit description text',
    'Notes': 'note references',
    'Maturities (calendar year)': 'maturity years used as labels',
    'Issue date': 'dates', 'Earliest redemption date(b)': 'dates', 'Issuance Date': 'dates', 'Maturity Date': 'dates',
    'Payment Date': 'dates', 'Contractual Maturity Date': 'dates', 'Transaction Date': 'dates',
    'Date of Issuance': 'dates', 'Grant Date': 'dates',
}
d = json.load(open('ident-new6.json', encoding='utf-8'))
base = {}
for n in os.listdir(os.path.join(D, 'base')):
    for t in json.load(open(os.path.join(D, 'base', n), encoding='utf-8'))['tables']:
        base[(n, t['ordinal'])] = t
AMOUNT = re.compile(r'\$|\d,\d{3}|%|^\(?[\d.]+\)?$')
odd = []
summary = collections.Counter()
mis = []
for x in d:
    part = re.sub(r'\s+', ' ', x['part'])
    true = part in TRUE_PARTS
    if true:
        for c in x['cells']:
            if re.search(r'\$|\d,\d{3}|%', c['orig']):
                odd.append((x['file'][:25], x['ordinal'], x['header'], c['label'][:30], c['orig']))
    b = base.get((x['file'], x['ordinal']))
    fates = collections.Counter()
    for c in x['cells']:
        if b is None:
            fates['absent'] += 1
        elif b['status'] == 'source_text_only':
            fates['base source_text_only'] += 1
        else:
            found = [cc for row in b['rows'] if (row[0][2] or '') == c['label'] for cc in row[1:] if cc[2] == c['orig']]
            fates['base ' + ('/'.join(sorted({cc[0] for cc in found})) if found else 'not found')] += 1
    key = 'true' if true else 'misread'
    n = len(x['cells'])
    summary[(x['group'], key, 'cols')] += 1
    summary[(x['group'], key, 'cells')] += n
    summary[(x['group'], key, 'facts')] += sum(bool(c['fact']) for c in x['cells'])
    summary[(x['group'], key, 'flagged_table')] += x['status'] == 'needs_review'
    if not true:
        mis.append((x, fates))
for g in ('META', 'NVDA', 'RDDT', 'Others'):
    for k in ('true', 'misread'):
        if summary[(g, k, 'cols')]:
            tabs = {(x['file'], x['ordinal']) for x in d if x['group'] == g and ((re.sub(r'\s+', ' ', x['part']) in TRUE_PARTS) == (k == 'true'))}
            print(f'{g:6} {k:8} cols={summary[(g, k, "cols")]} tables={len(tabs)} cells={summary[(g, k, "cells")]} '
                  f'cells_with_facts={summary[(g, k, "facts")]} cols_in_needs_review_tables={summary[(g, k, "flagged_table")]}')
print('true-identifier cells that look like amounts/percents:', len(odd))
for o in odd[:20]:
    print('   ', o)
print('\n## misread columns')
for x, fates in mis:
    print(f'{x["group"]:6} {x["file"][:44]} #{x["ordinal"]} [{x["status"]}] {x["title"][:50]!r}')
    print(f'       H={x["header"]!r} part={x["part"]!r} word={x["word"]!r} cells={len(x["cells"])} '
          f'facts={sum(bool(c["fact"]) for c in x["cells"])} base={dict(fates)}')
    print('       ' + ' | '.join(f'{c["label"][:28]}={c["orig"]}' for c in x['cells'][:8]))
