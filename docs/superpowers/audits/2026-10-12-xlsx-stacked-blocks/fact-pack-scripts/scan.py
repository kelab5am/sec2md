"""Guard trace with main's code, from raw-tag snapshots matched to new6 tables (no Parser run).

python -I scan.py MAIN_SRC NEW6_DIR OUT_PICKLE FILE [FILE ...]
Sequential, one process.
"""
import dataclasses
import json
import os
import pickle
import sys
import time
import warnings

src, new6, out, *files = sys.argv[1:]
sys.path.insert(0, src)
warnings.filterwarnings('ignore')
from bs4 import BeautifulSoup  # noqa: E402
import sec2md  # noqa: E402
from sec2md import xlsx_tables as xt  # noqa: E402

assert os.path.realpath(sec2md.__file__).startswith(os.path.realpath(src)), sec2md.__file__
sys.stdout.reconfigure(encoding='utf-8')


def sig(cells):
    return tuple((c[0], c[1], c[2], c[3], c[4]) for c in cells)


def grid_of(cells):
    height = max((c.row + max(c.rowspan, 1) for c in cells), default=0)
    width = max((c.column + max(c.colspan, 1) for c in cells), default=0)
    grid = [[None] * width for _ in range(height)]
    for c in cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                grid[r][k] = c
    return grid


result = {}
for path in files:
    t0 = time.time()
    name = os.path.basename(path)
    export = json.load(open(os.path.join(new6, name + '.json'), encoding='utf-8'))
    html = open(path, 'rb').read().decode('utf-8', 'replace')
    part = os.path.join(os.path.dirname(out), 'parts', name + '.pkl')
    if os.path.exists(part):
        result[name] = pickle.load(open(part, 'rb'))
        print('cached', name, flush=True)
        continue
    soup = BeautifulSoup(html, 'lxml')
    _, targets = xt.native_metadata(soup)
    snaps = {}
    for tag in soup.find_all('table'):
        try:
            s = xt.snapshot_html_table(tag, ordinal=0, page=1, source_url=None, note_targets=targets)
        except Exception:
            continue
        key = tuple((c.row, c.column, c.rowspan, c.colspan, c.text) for c in s.source_cells)
        snaps.setdefault(key, s)
    tables = []
    for t in export['tables']:
        s = snaps.get(sig(t['source_cells']))
        rec = dict(ordinal=t['ordinal'], title=t['title'], status6=t['status'], headers6=t['headers'],
                   matched=s is not None)
        if s is None:
            tables.append(rec)
            continue
        s = dataclasses.replace(s, ordinal=t['ordinal'])
        cells = s.source_cells
        if s.issues or not cells:
            rec.update(fired=False, base=None)
            tables.append(rec)
            continue
        height = max(c.row + max(c.rowspan, 1) for c in cells)
        width = max(c.column + max(c.colspan, 1) for c in cells)
        if height * width > 1_000_000:
            tables.append(rec)
            continue
        grid = grid_of(cells)
        base = xt._header_count(grid)
        with_guard = xt._export_header_count(grid)
        orig = xt._period_row
        xt._period_row = lambda row: False
        try:
            without = xt._export_header_count(grid)
        finally:
            xt._period_row = orig
        fired = with_guard != without
        prepared = xt.prepare_table(s)
        rec.update(base=base, with_guard=with_guard, without=without, fired=fired,
                   status_main=prepared.status, headers_main=list(prepared.headers),
                   same_as_new6=(prepared.status == t['status'] and list(prepared.headers) == t['headers']))
        if fired:
            rec['period_rows'] = [[r, [c.text for c in xt._row_origins(grid[r])]]
                                  for r in range(len(grid)) if xt._period_row(grid[r])]
            rec['snapshot'] = s
        tables.append(rec)
    result[name] = tables
    pickle.dump(tables, open(part, 'wb'))
    nf = sum(1 for t in tables if t.get('fired'))
    nm = sum(1 for t in tables if not t['matched'])
    nd = sum(1 for t in tables if t.get('same_as_new6') is False)
    print(f'{time.time()-t0:6.1f}s {len(tables):4} tables fired {nf:3} unmatched {nm} diff-vs-new6 {nd}  {name}', flush=True)
with open(out, 'wb') as fh:
    pickle.dump(result, fh)
