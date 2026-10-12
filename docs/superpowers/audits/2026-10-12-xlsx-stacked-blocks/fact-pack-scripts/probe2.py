"""Single-sheet simulation: whole-table columns (prepare_table without the guard), per-block header labels.

python -I probe2.py MAIN_SRC AUDIT_DIR NEW6_DIR SCAN_PKL CLASSIFY_JSON OUT_JSON
"""
import collections
import json
import os
import pickle
import re
import sys
import warnings

src, audit_dir, new6, scan_pkl, cls_json, out_json = sys.argv[1:]
sys.path.insert(0, src)
sys.path.insert(0, audit_dir)
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
from sec2md import xlsx_tables as xt  # noqa: E402
from all_facts import period_verdict  # noqa: E402

scan = pickle.load(open(scan_pkl, 'rb'))
C = json.load(open(cls_json, encoding='utf-8'))
EXCLUDE = {('RDDT__10-Q__2024-Q1', 48), ('RDDT__10-K__2024-FY', 64), ('RDDT__10-K__2025-FY', 63),
           ('RDDT__10-Q__2026-Q2', 47), ('MSFT-10-K', 80)}


def grid_of(cells):
    h = max(c.row + max(c.rowspan, 1) for c in cells)
    w = max(c.column + max(c.colspan, 1) for c in cells)
    g = [[None] * w for _ in range(h)]
    for c in cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                g[r][k] = c
    return g


out = []
for item in C:
    if not item['block_starts'] or any(item['file'].startswith(p) and item['ordinal'] == o for p, o in EXCLUDE):
        continue
    rec = next(t for t in scan[item['file']] if t['ordinal'] == item['ordinal'])
    snap = rec['snapshot']
    export = json.load(open(os.path.join(new6, item['file'] + '.json'), encoding='utf-8'))
    t6 = next(t for t in export['tables'] if t['ordinal'] == item['ordinal'])
    contexts = export['contexts']
    grid = grid_of(snap.source_cells)
    orig = xt._period_row
    xt._period_row = lambda row: False
    try:
        P = xt.prepare_table(snap)
    finally:
        xt._period_row = orig
    blocks = item['blocks']
    if P.status == 'source_text_only':
        out.append(dict(file=item['file'], ordinal=item['ordinal'], whole_status=P.status, whole_issues=list(P.issues)[:3]))
        continue
    H = item['extended']
    # source column per kept column: the most frequent origin column holding digits
    colsrc = []
    for ci in range(len(P.headers)):
        cnt = collections.Counter()
        for row in P.cell_sources:
            for (r, c) in row[ci]:
                cell = grid[r][c]
                if cell is not None and re.search(r'\d', cell.text):
                    cnt[c] += 1
        if not cnt:
            for row in P.cell_sources:
                for (r, c) in row[ci]:
                    cnt[c] += 1
        colsrc.append(cnt.most_common(1)[0][0] if cnt else None)

    def caption_of(rows):
        for r in rows:
            c0 = grid[r][0]
            if c0 is not None and c0.text.strip() and xt._period_text(c0.text):
                return c0.text
        return None

    def labels_for(rows, fallback_rows=()):
        labels = []
        for ci, c in enumerate(colsrc):
            if c is None:
                labels.append('')
                continue
            texts = []
            for r in list(fallback_rows) + list(rows):
                cell = grid[r][c]
                if cell is not None and cell.text.strip() and not xt._UNIT_LINE.search(cell.text) and cell.text not in texts:
                    texts.append(cell.text)
            labels.append(' — '.join(texts))
        return labels

    first_rows = blocks[0]['header_rows']
    heading_rows_1 = [r for r in range(0, blocks[0]['first_data'])
                      if any(c.row == r for c in xt._row_origins(grid[r])) and not (
                          grid[r][0] is not None and grid[r][0].text.strip() and xt._period_text(grid[r][0].text)
                          and all(c is grid[r][0] for c in xt._row_origins(grid[r])))]
    per_block = []
    total = collections.Counter()
    bad = []
    removed_amounts = 0
    for i, b in enumerate(blocks):
        b0, b1 = b['rows']
        fd = b['first_data']
        hdr_rows = list(range(b0, fd))
        repeated = any(c.column > 0 and not xt._period_text(c.text) for r in hdr_rows for c in xt._row_origins(grid[r]))
        if i == 0 or repeated:
            labels = labels_for(hdr_rows if i else list(range(0, fd)))
        else:
            labels = labels_for(hdr_rows, fallback_rows=heading_rows_1)
        cap = caption_of(hdr_rows if i else list(range(0, fd)))
        full = [((cap + ' — ') if cap and cap not in l else '') + l for l in labels]
        # body rows of the block in P: rows whose label-column source row is in [fd, b1]
        counts = collections.Counter()
        where = {}
        for ri, row in enumerate(P.cell_sources):
            for ci, cs in enumerate(row):
                for s in cs:
                    where[tuple(s)] = (ri, ci)
        for f in t6['facts']:
            if not (fd <= f[0] <= b1):
                continue
            p = where.get((f[0], f[1]))
            if f[1] == 0 or (p and p[1] == 0):
                v = 'label column'
            elif p is None:
                v = 'not placed'
            else:
                v = period_verdict(contexts.get(f[2]), full[p[1]])
                if v == 'mismatch' and len(bad) < 4:
                    bad.append([f[0], f[1], f[4], contexts.get(f[2]), full[p[1]]])
            counts[v] += 1
        total.update(counts)
        # amounts sitting in the block's header rows (would be lost if those rows leave the body)
        for r in hdr_rows:
            for c in xt._row_origins(grid[r]):
                if c.row == r and xt._is_data_cell(c, digits=True):
                    removed_amounts += 1
        per_block.append(dict(block=i + 1, header_rows=[b0, fd - 1], caption=cap, sample=full[1:3], facts=dict(counts)))
    issues_other = [x for x in P.issues if not any(f'Source row {r},' in x for b in blocks for r in range(b['rows'][0], b['first_data']))]
    out.append(dict(file=item['file'], ordinal=item['ordinal'], whole_status=P.status, columns=len(P.headers),
                    issues_total=len(P.issues), issues_outside_block_headers=len(issues_other),
                    issues_outside_sample=issues_other[:3], facts=dict(total), mismatches=bad,
                    amounts_in_block_header_rows=removed_amounts, blocks=per_block))
json.dump(out, open(out_json, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
for o in out:
    print(o['file'][:22], o['ordinal'], o['whole_status'], o.get('columns'), 'issues', o.get('issues_total'), '->', o.get('issues_outside_block_headers'),
          'facts', o.get('facts'), 'amtsInHdr', o.get('amounts_in_block_header_rows'), (o.get('mismatches') or '')[:1], o.get('whole_issues', ''))
