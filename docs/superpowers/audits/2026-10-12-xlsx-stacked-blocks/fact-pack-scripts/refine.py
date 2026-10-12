import json, sys
sys.stdout.reconfigure(encoding='utf-8')
R = json.load(open('classify.json', encoding='utf-8'))
for r in R:
    if not r['block_starts']:
        continue
    print(f"== {r['file'][:24]} #{r['ordinal']} {r['status_main']}")
    b1 = r['blocks'][0]
    def heads(b):
        return {(t, c, cs, rs) for t, c, cs, rs in b['heads'] if c > 0 or not t.strip() == ''}
    h1 = {(t, c, cs) for t, c, cs, rs in b1['heads'] if c > 0}
    l1 = {t for t, c, cs, rs in b1['heads'] if c == 0}
    for i, b in enumerate(r['blocks'][1:], 2):
        hk = {(t, c, cs) for t, c, cs, rs in b['heads'] if c > 0}
        lk = {t for t, c, cs, rs in b['heads'] if c == 0}
        t1 = {t for t, c, cs in h1}; tk = {t for t, c, cs in hk}
        if not hk:
            rep = 'none (caption only)'
        elif hk == h1:
            rep = 'full (same texts and spans)'
        elif tk == t1:
            rep = 'same texts, different spans'
        elif tk & t1:
            rep = f'partial: only-in-1={sorted(t1-tk)[:4]} only-in-k={sorted(tk-t1)[:4]}'
        else:
            rep = f'different: {sorted(tk)[:4]}'
        print(f"   blk{i} {rep} | label-col heads 1={sorted(l1)[:3]} k={sorted(lk)[:3]} | same amount cells={b['same_amount_cells']} only-here={b['amount_cols_only_here'][:4]} missing={b['amount_cols_missing_here'][:4]}")
    for p in r['probes']:
        extra = ''
        if 'reuse_block1_headings' in p:
            q = p['reuse_block1_headings']
            extra = f" || reuse: {q['status']} hc={q['header_count']} names={q['header_names_caption']} facts={q['facts']} hdr={[h[:40] for h in q['headers'][1:3]]}"
        print(f"   probe{p['block']}: {p['status']} hc={p['header_count']}/{p['header_count_noguard']} base={p['base']} names={p['header_names_caption']} unres={p['unresolved_span']} nis={p['n_issues']} facts={p['facts']} clip={p['clipped'][:2]} hdr={[h[:50] for h in p['headers'][1:3]]}{extra}")
        if p['mismatches']:
            print('      MISMATCH', p['mismatches'][:2])
    print('   caption_vs_facts', r['caption_vs_facts'], r['caption_mismatch_examples'][:2])
