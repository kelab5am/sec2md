import json, sys, collections, re
sys.stdout.reconfigure(encoding='utf-8')
C = json.load(open('classify.json', encoding='utf-8'))
P2 = {(p['file'], p['ordinal']): p for p in json.load(open('probe2.json', encoding='utf-8'))}
def key(item):
    f = item['file']; o = item['ordinal']
    short = f.split('__c-')[0].replace('.htm', '') if '__' in f else f.split('-20')[0] + '-' + f.split('-')[1] if False else f.replace('.htm', '')
    return short
REPEATED = {('META', 9), ('RDDT', 8), ('RDDT', 9), ('JPM', 158), ('JPM', 159), ('JPM', 161), ('JPM', 194), ('JPM', 241)}
SECTION_LABEL = lambda f, o: f.startswith('META') and o in (22, 25, 50)
SPLIT = {('JPM', 137), ('JPM', 138), ('JPM', 139), ('TSM', 165), ('UNH', 38)}
EXHIBIT = {('RDDT__10-Q__2024-Q1', 48), ('RDDT__10-K__2024-FY', 64), ('RDDT__10-K__2025-FY', 63), ('RDDT__10-Q__2026-Q2', 47), ('MSFT', 80),
           ('RDDT__10-K__2024-FY', 63), ('RDDT__10-K__2025-FY', 62), ('CRM', 79)}
def match(S, f, o):
    return any(f.startswith(p) and o == q for p, q in S)
def cat(item):
    f, o = item['file'], item['ordinal']
    if match(EXHIBIT, f, o): return 'exhibit'
    if not item['block_starts']: return 'stranded'
    if SECTION_LABEL(f, o): return 'section-label'
    if match(SPLIT, f, o): return 'section-split'
    if match(REPEATED, f, o): return 'stacked-repeated'
    return 'stacked-caption'
def grp(f):
    c = f.split('__')[0]; return c if c in ('META', 'NVDA', 'RDDT') else 'Others'
def name(f):
    if '__' in f:
        p = f.split('__'); return f'{p[0]} {p[1]} {p[2]}'
    return f.replace('.htm', '')
counts = collections.Counter(); stat = collections.Counter()
rows = collections.defaultdict(list)
for it in C:
    c = cat(it); counts[(grp(it['file']), c)] += 1
    if c.startswith('stacked'): stat[(grp(it['file']), it['status_main'])] += 1
    rows[c].append(it)
print(dict(counts)); print(dict(stat))
def capdesc(b):
    out = []
    for c in b['captions']:
        texts = [t.split(' @c')[0] for t in c['texts']]
        out.append(f"r{c['row']} {c['position']}: `" + ' | '.join(dict.fromkeys(texts))[:90] + '`')
    return '; '.join(dict.fromkeys(out)) or '(none in table)'
with open('inv_stacked.md', 'w', encoding='utf-8') as fh:
    for c in ('stacked-repeated', 'stacked-caption'):
        fh.write(f'\n#### {c}\n\n| Filing | # | Title | Main | Blocks | Block rows (header rows → last row) | Captions (row, position, text) | Later blocks repeat headings | Same amount cells | Per-block prepare | Single-sheet sim |\n|---|---|---|---|---|---|---|---|---|---|---|\n')
        for it in rows[c]:
            bl = it['blocks']
            ranges = ', '.join(f"{b['rows'][0]}-{b['first_data']-1}→{b['rows'][1]}" for b in bl)
            caps = '<br>'.join(f'B{i+1} ' + capdesc(b) for i, b in enumerate(bl))
            rep = ', '.join(sorted({b.get('repeat', '') for b in bl[1:]}))
            same = all(b.get('same_amount_cells') for b in bl[1:])
            pr = it['probes']
            pb = '; '.join(f"B{p['block']} {p['status'][:6]} hc={p['header_count']} cols={p['n_headers']}" + (' unres' if p['unresolved_span'] else '') + (' names' if p['header_names_caption'] else '') for p in pr)
            s = P2.get((it['file'], it['ordinal']))
            sim = '' if not s else (f"{s['whole_status'][:6]} cols={s.get('columns')} facts={s.get('facts')} other issues={s.get('issues_outside_block_headers')}" if s.get('columns') else f"{s['whole_status']}: {s['whole_issues'][0][:45]}")
            fh.write(f"| {name(it['file'])} | {it['ordinal']} | {it['title'][:40]} | {it['status_main']} | {len(bl)} | {ranges} | {caps} | {rep} | {same} | {pb} | {sim} |\n")
    for c in ('section-label', 'section-split', 'exhibit'):
        fh.write(f'\n#### {c}\n\n')
        for it in rows[c]:
            pr = it['period_rows'][:2]
            fh.write(f"- {name(it['file'])} #{it['ordinal']} `{it['title'][:45]}` ({it['status_main']}): period rows " + '; '.join(f"r{p[0]} `" + ' | '.join(t[:35] for t in p[1][:3]) + '`' for p in pr) + (f", block starts {it['block_starts']}" if it['block_starts'] else '') + '\n')
    fh.write('\n#### stranded\n\n')
    for it in rows['stranded']:
        pr = it['period_rows'][:1]
        fh.write(f"- {name(it['file'])} #{it['ordinal']} ({it['status_main']}): " + '; '.join(f"r{p[0]} `" + ' | '.join(t[:30] for t in p[1][:3]) + '`' for p in pr) + '\n')
