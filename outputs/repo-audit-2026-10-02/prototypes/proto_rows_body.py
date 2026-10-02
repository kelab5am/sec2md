"""Prototype: ordered per-row numeric sequence check (catches column swaps)."""
import gzip, sys, warnings
from collections import Counter
warnings.filterwarnings("ignore")
exec(open(sys.argv[1], encoding="utf-8").read().split("ids = [")[0])
from sec2md.encoding import decode_html
from sec2md.parser import Parser
from sec2md.chunker.blocks import is_separator_row

def src_rows(table):
    rows = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table or hidden(tr): continue
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"]) if c.find_parent("table") is table and not hidden(c)]
        nums = tuple(_normalized_numbers(" ".join(cells)))
        if nums: rows.append(nums)
    return rows

def out_rows(text):
    rows = []
    for line in text.split("\n"):
        if not line.lstrip().startswith("|") or is_separator_row(line): continue
        nums = tuple(_normalized_numbers(line.replace("|", " ")))
        if nums: rows.append(nums)
    return rows

ids = ["aapl-2023-10k","nvda-2026-10k","nvda-2002-10k","nvda-2026-q2-10q","nvda-2026-08-26-8k","nvda-2026-ex99-1","nvda-2026-ex99-2"]
tot = Counter()
for fid in ids:
    p = Parser(decode_html(gzip.open(f"tests/fixtures/sec/{fid}.html.gz", "rb").read())[0]); pages = p.get_pages()
    elements = {e.id: e for pg in pages for e in (pg.elements or [])}
    by_node = {}
    for eid, nodes in p.block_nodes_map.items():
        for n in nodes: by_node.setdefault(id(n), set()).add(eid)
    kinds = Counter(); ex = []
    for t in [t for t in p.soup.find_all("table") if not hidden(t) and t.find_parent("table") is None]:
        s = src_rows(t)
        if not s: continue
        eids = set()
        for node in [t] + t.find_all(True): eids |= by_node.get(id(node), set())
        o = [r for e in sorted(eids) for r in out_rows(elements[e].content)]
        if not o: kinds["no_body_rows"] += 1; continue
        if len(o) > len(s): kinds["more_output_rows"] += 1; continue
        if s[-len(o):] == o: kinds["equal"] += 1; continue
        tail = s[-len(o):]
        if Counter(x for r in tail for x in r) - Counter(x for r in o for x in r):
            kinds["missing_values"] += 1
            if len(ex) < 3: ex.append(("missing", [r for r in tail if r not in o][:2], [r for r in o if r not in tail][:2]))
            continue
        if [x for r in tail for x in r] == [x for r in o for x in r]:
            kinds["same_order_different_row_breaks"] += 1
            if len(ex) < 2: ex.append(("rowbreak", s[:3], o[:3]))
            continue
        kinds["reordered_or_extra"] += 1
        if len(ex) < 4: ex.append(("reorder", [r for r in tail if r not in o][:2], [r for r in o if r not in tail][:2]))
    tot.update(kinds)
    print(fid, dict(kinds)); [print("   ", e) for e in ex]
print(dict(tot))
