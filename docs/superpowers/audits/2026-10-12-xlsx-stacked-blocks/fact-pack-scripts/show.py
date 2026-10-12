"""python -I show.py NEW6_DIR FILE_PREFIX ORDINAL [MAXROWS]: print source rows as origins (col:span text), facts per row."""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
d, prefix, ordinal = sys.argv[1], sys.argv[2], int(sys.argv[3])
maxrows = int(sys.argv[4]) if len(sys.argv) > 4 else 999
name = next(n for n in sorted(os.listdir(d)) if n.startswith(prefix))
data = json.load(open(os.path.join(d, name), encoding='utf-8'))
t = next(t for t in data['tables'] if t['ordinal'] == ordinal)
print(name, '#', ordinal, t['status'], t['title'][:60])
print('headers:', t['headers'])
ctx = data['contexts']
facts = {}
for f in t['facts']:
    facts.setdefault(f[0], []).append(f)
rows = {}
for r, c, rs, cs, text, num in t['source_cells']:
    if text:
        rows.setdefault(r, []).append((c, rs, cs, text, num))
height = max((r + rs for r, c, rs, cs, *_ in t['source_cells']), default=0)
for r in range(min(height, maxrows)):
    cells = sorted(rows.get(r, []))
    s = ' | '.join(f"{c}{'' if cs == 1 else ':' + str(cs)}{'' if rs == 1 else 'r' + str(rs)} {text[:40]}{'*' if num else ''}"
                   for c, rs, cs, text, num in cells)
    per = sorted({tuple(ctx.get(f[2], [None, None, None])[:3]) for f in facts.get(r, [])}, key=str)
    print(f'r{r}: {s}' + (f'   ctx={per}' if per else ''))
