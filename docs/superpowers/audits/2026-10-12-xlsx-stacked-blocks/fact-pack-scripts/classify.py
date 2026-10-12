"""Classify every guard-fired table (main's code) and probe per-block header detection in memory.

python -I classify.py MAIN_SRC AUDIT_DIR NEW6_DIR SCAN_PKL OUT_JSON
"""
import collections
import dataclasses
import json
import os
import pickle
import re
import sys
import warnings

src, audit_dir, new6, scan_pkl, out_json = sys.argv[1:]
sys.path.insert(0, src)
sys.path.insert(0, audit_dir)
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
import sec2md  # noqa: E402
from sec2md import xlsx_tables as xt  # noqa: E402
from all_facts import period_verdict, header_period  # noqa: E402

assert os.path.realpath(sec2md.__file__).startswith(os.path.realpath(src))
scan = pickle.load(open(scan_pkl, 'rb'))


def group(name):
    c = name.split('__')[0]
    return c if c in ('META', 'NVDA', 'RDDT') else 'Others'


def grid_of(cells):
    height = max((c.row + max(c.rowspan, 1) for c in cells), default=0)
    width = max((c.column + max(c.colspan, 1) for c in cells), default=0)
    grid = [[None] * width for _ in range(height)]
    for c in cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                grid[r][k] = c
    return grid


def is_data_row(row):
    return any(xt._is_data_cell(c, digits=True) for c in xt._row_origins(row))


def nonblank(row):
    return bool(xt._row_origins(row))


def caption_cells(grid, r):
    """Period-text origins of row r (origins starting on row r or covering it)."""
    return [c for c in xt._row_origins(grid[r]) if xt._period_text(c.text) or
            (c.column > 0 and (xt._PERIOD_PHRASE.search(c.text) or xt._NUMERIC_DATE.search(c.text)))]


def position(grid, r, caps):
    origins = xt._row_origins(grid[r])
    others = [c for c in origins if c not in caps]
    if any(c.column == 0 for c in caps):
        return 'label column' + (' beside headings' if others else ' (own row)')
    if others:
        return 'beside column headings'
    return 'own row' + (f' x{len(caps)} column groups' if len(caps) > 1 else '')


def sub_snapshot(snapshot, start, stop, prefix_rows=()):
    """Cells of rows [start, stop) shifted to row 0 (after prefix rows from elsewhere). Spans crossing stop are clipped."""
    cells, clipped = [], []
    rows = list(prefix_rows) + list(range(start, stop))
    index = {r: i for i, r in enumerate(rows)}
    for c in snapshot.source_cells:
        covered = [r for r in range(c.row, c.row + max(c.rowspan, 1)) if r in index]
        if not covered:
            continue
        if c.row not in index:
            clipped.append((c.row, c.column, c.text[:30]))
            continue
        span = len(covered)
        if span != c.rowspan:
            clipped.append((c.row, c.column, c.text[:30]))
        cells.append(dataclasses.replace(c, row=index[c.row], rowspan=max(span, 1)))
    return dataclasses.replace(snapshot, source_cells=tuple(cells)), rows, clipped


def fact_checks(prepared, rows_map, facts, contexts):
    """Place each fact (original row, col) via cell_sources; verdict against the block's prepared header."""
    where = {}
    for ri, sources in enumerate(prepared.cell_sources):
        for ci, cs in enumerate(sources):
            for s in cs:
                where[(rows_map[s[0]], s[1])] = (ri, ci)
    counts = collections.Counter()
    bad = []
    for row, col, ctx, concept, text, sign in facts:
        p = where.get((row, col))
        if col == 0 or (p and p[1] == 0):
            v = 'label column'
        elif p is None:
            v = 'not placed'
        else:
            v = period_verdict(contexts.get(ctx), prepared.headers[p[1]])
            if v == 'mismatch':
                bad.append([row, col, text, contexts.get(ctx), prepared.headers[p[1]]])
        counts[v] += 1
    return dict(counts), bad[:5]


results = []
for name, tables in scan.items():
    export = json.load(open(os.path.join(new6, name + '.json'), encoding='utf-8'))
    by_ord = {t['ordinal']: t for t in export['tables']}
    contexts = export['contexts']
    for rec in tables:
        if not rec.get('fired'):
            continue
        snap = rec['snapshot']
        grid = grid_of(snap.source_cells)
        H = rec['without']
        base = rec['base']
        height = len(grid)
        data_rows = [r for r in range(height) if is_data_row(grid[r])]
        body_period = [r for r in range(H, height) if xt._period_row(grid[r])]
        # Block starts: the first period row after a data row, with data below.
        starts = []
        for r in body_period:
            above = [d for d in data_rows if (starts[-1] if starts else H) <= d < r]
            below = [d for d in data_rows if d > r]
            if above and below:
                # walk up over contiguous non-data heading rows that belong to the new block's header
                s = r
                while s - 1 > (starts[-1] if starts else H) and not is_data_row(grid[s - 1]) and nonblank(grid[s - 1]) \
                        and not any(c.column == 0 for c in xt._row_origins(grid[s - 1])):
                    s -= 1
                starts.append(r if s == r else s)
        stranded = [r for r in body_period if not [d for d in data_rows if H <= d < r]]
        trailing = [r for r in body_period if not [d for d in data_rows if d > r]]
        t6 = by_ord[rec['ordinal']]
        item = dict(file=name, group=group(name), ordinal=rec['ordinal'], title=rec['title'][:70],
                    status_main=rec['status_main'], base=base, extended=H, height=height,
                    period_rows=[[r, [c.text[:60] for c in xt._row_origins(grid[r])]] for r in body_period],
                    stranded=stranded, trailing=trailing, block_starts=starts)
        if starts:
            bounds = [0] + starts + [height]
            blocks = []
            first_data = [next((d for d in data_rows if bounds[i] <= d < bounds[i + 1]), None) for i in range(len(bounds) - 1)]
            for i in range(len(bounds) - 1):
                b0, b1 = bounds[i], bounds[i + 1]
                fd = first_data[i]
                head_rows = [r for r in range(b0, fd) if nonblank(grid[r])] if fd is not None else []
                caps = []
                for r in head_rows + [r for r in body_period if b0 <= r < b1 and r not in head_rows]:
                    cc = caption_cells(grid, r)
                    if cc:
                        caps.append(dict(row=r, position=position(grid, r, cc),
                                         texts=[f'{c.text[:70]} @c{c.column}:{c.colspan}' for c in cc]))
                # heading cells of the block's header rows, excluding captions
                heads = sorted({(c.text, c.column, c.colspan, c.rowspan) for r in head_rows for c in xt._row_origins(grid[r])
                                if c.row == r and not (xt._period_text(c.text))})
                data_shape = sorted({(c.column, c.colspan, c.text == '$') for r in range(b0, b1) if is_data_row(grid[r])
                                     for c in xt._row_origins(grid[r]) if c.row == r and c.column > 0
                                     and (xt._is_data_cell(c, digits=True) or c.text == '$')})
                in_block = [f for f in t6['facts'] if b0 <= f[0] < b1]
                blocks.append(dict(rows=[b0, b1 - 1], header_rows=head_rows, first_data=fd, captions=caps,
                                   heads=heads, data_shape=data_shape, facts=len(in_block),
                                   fact_periods=sorted({tuple(contexts.get(f[2], ['?', None, None])[:3]) for f in in_block}, key=str)[:8]))
            item['blocks'] = blocks
            # Shapes vs block 1
            h1 = set(blocks[0]['heads'])
            for b in blocks[1:]:
                hk = set(b['heads'])
                b['repeat'] = ('full' if hk == h1 and hk else 'none' if not hk else
                               'superset' if hk > h1 else 'partial' if hk & h1 else 'different')
                cols1 = {(c, s) for c, s, d in blocks[0]['data_shape'] if not d}
                colsk = {(c, s) for c, s, d in b['data_shape'] if not d}
                b['same_amount_cells'] = colsk == cols1
                b['amount_cols_only_here'] = sorted(colsk - cols1)[:10]
                b['amount_cols_missing_here'] = sorted(cols1 - colsk)[:10]
                b['amount_starts_same'] = {c for c, s in colsk} <= {c for c, s in cols1} or {c for c, s in cols1} <= {c for c, s in colsk}
            # Feasibility probe: prepare each block separately.
            probes = []
            for i, b in enumerate(blocks):
                b0, b1 = b['rows'][0], b['rows'][1] + 1
                s, rows_map, clipped = sub_snapshot(snap, b0, b1)
                sg = grid_of(s.source_cells)
                p = xt.prepare_table(s)
                hc = xt._export_header_count(sg) if s.source_cells else 0
                orig = xt._period_row
                xt._period_row = lambda row: False
                try:
                    hc_noguard = xt._export_header_count(sg) if s.source_cells else 0
                finally:
                    xt._period_row = orig
                fc, bad = fact_checks(p, rows_map, [f for f in t6['facts'] if b0 <= f[0] < b1], contexts) if p.status != 'source_text_only' else ({}, [])
                cap_texts = [t.split(' @c')[0] for c in b['captions'] for t in c['texts']]
                names_period = bool(p.headers) and any(any(re.sub(r'\s+', ' ', ct).strip()[:25] in h for h in p.headers) for ct in cap_texts)
                probe = dict(block=i + 1, header_count=hc, header_count_noguard=hc_noguard, base=xt._header_count(sg),
                             status=p.status, headers=list(p.headers)[:8], n_headers=len(p.headers),
                             issues=[x for x in p.issues][:4], n_issues=len(p.issues),
                             unresolved_span=any('Unresolved value span' in x for x in p.issues),
                             header_names_caption=names_period, facts=fc, mismatches=bad, clipped=clipped[:5])
                # Reuse block 1's heading rows for a caption-only block
                if i > 0 and b.get('repeat') == 'none':
                    pre = [r for r in blocks[0]['header_rows'] if not caption_cells(grid, r)]
                    s2, rows_map2, clipped2 = sub_snapshot(snap, b0, b1, prefix_rows=pre)
                    p2 = xt.prepare_table(s2)
                    fc2, bad2 = fact_checks(p2, rows_map2, [f for f in t6['facts'] if b0 <= f[0] < b1], contexts) if p2.status != 'source_text_only' else ({}, [])
                    probe['reuse_block1_headings'] = dict(prefix_rows=pre, status=p2.status, headers=list(p2.headers)[:8],
                                                          header_count=xt._export_header_count(grid_of(s2.source_cells)),
                                                          n_issues=len(p2.issues), issues=list(p2.issues)[:3],
                                                          facts=fc2, mismatches=bad2,
                                                          header_names_caption=any(any(ct[:25] in h for h in p2.headers) for ct in cap_texts))
                probes.append(probe)
            item['probes'] = probes
            # Caption-vs-facts check (independent of export): each fact vs the caption over its column in its block.
            cap_check = collections.Counter()
            cap_bad = []
            for b in blocks:
                caps = b['captions']
                for f in [f for f in t6['facts'] if b['rows'][0] <= f[0] <= b['rows'][1]]:
                    col = f[1]
                    text = None
                    for c in caps:
                        for t in c['texts']:
                            body, where = t.rsplit(' @c', 1)
                            c0, cs = map(int, where.split(':'))
                            if c0 == 0 and text is None:
                                text = body
                            elif c0 <= col < c0 + cs:
                                text = body
                    v = period_verdict(contexts.get(f[2]), text) if text else 'no caption'
                    cap_check[v] += 1
                    if v == 'mismatch' and len(cap_bad) < 5:
                        cap_bad.append([f[0], f[1], f[4], contexts.get(f[2]), text])
            item['caption_vs_facts'] = dict(cap_check)
            item['caption_mismatch_examples'] = cap_bad
        results.append(item)

json.dump(results, open(out_json, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
c = collections.Counter((r['group'], bool(r['block_starts'])) for r in results)
print(len(results), 'fired tables;', dict(c))
