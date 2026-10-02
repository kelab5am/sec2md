"""Prototype: per-table source->output numeric completeness on the fixtures."""
import gzip, json, sys, warnings
from collections import Counter
warnings.filterwarnings("ignore")
from sec2md.parser import Parser
from sec2md.encoding import decode_html
from sec2md.quality import _normalized_numbers, _is_hidden_tag

def hidden(tag):
    return _is_hidden_tag(tag) or any(_is_hidden_tag(p) for p in tag.parents if getattr(p, "attrs", None) is not None)

def row_numbers(table):
    out = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table or hidden(tr):
            continue
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"]) if c.find_parent("table") is table and not hidden(c)]
        out.extend(_normalized_numbers(" ".join(cells)))
    return out

def output_numbers(text):
    return list(_normalized_numbers(text.replace("|", " ")))

ids = [l.strip() for l in open("tests/fixtures/sec/manifest.json", encoding="utf-8").read().split('"fixture_id": "')[1:]]
ids = [i.split('"')[0] for i in ids]
total = {"tables": 0, "with_missing": 0, "missing_tokens": 0, "source_tokens": 0}
for fid in ids:
    raw = gzip.open(f"tests/fixtures/sec/{fid}.html.gz", "rb").read()
    text, _ = decode_html(raw)
    p = Parser(text)
    pages = p.get_pages()
    elements = {e.id: e for pg in pages for e in (pg.elements or [])}
    by_node = {}
    for eid, nodes in p.block_nodes_map.items():
        for n in nodes:
            by_node.setdefault(id(n), set()).add(eid)
    tables = [t for t in p.soup.find_all("table") if not hidden(t) and t.find_parent("table") is None]
    n_missing_tables = 0; examples = []
    for t in tables:
        src = Counter(row_numbers(t))
        if not src:
            continue
        eids = set()
        for node in [t] + t.find_all(True):
            eids |= by_node.get(id(node), set())
        out = Counter()
        for eid in eids:
            out.update(output_numbers(elements[eid].content))
        missing = src - out
        total["tables"] += 1; total["source_tokens"] += sum(src.values())
        if missing:
            n_missing_tables += 1; total["missing_tokens"] += sum(missing.values())
            if len(examples) < 4:
                examples.append((sorted(missing.elements())[:6], "mapped" if eids else "UNMAPPED"))
    total["with_missing"] += n_missing_tables
    print(f"{fid}: tables={len(tables)} with_missing={n_missing_tables} e.g. {examples}")
print(total)
