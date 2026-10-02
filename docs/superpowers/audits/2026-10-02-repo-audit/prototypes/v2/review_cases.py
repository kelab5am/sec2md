"""Astra's review cases, run through the original (v1) and revised (v2) check definitions."""
import sys
import warnings
from collections import Counter

warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])  # scratchpad holding completeness_v2.py

import completeness_v2 as v2
from sec2md.parser import Parser
from sec2md.quality import _is_hidden_tag, _normalized_numbers


def v1(html):
    """The original spec: get_text(" ") source rows vs all mapped elements' content."""
    p = Parser(html)
    pages = p.get_pages()
    elements = {e.id: e for pg in pages for e in (pg.elements or [])}
    by_node = {}
    for eid, nodes in p.block_nodes_map.items():
        for n in nodes:
            by_node.setdefault(id(n), set()).add(eid)
    out = []
    for t in p.soup.find_all("table"):
        if _is_hidden_tag(t):
            continue
        src = Counter()
        for tr in t.find_all("tr"):
            if tr.find_parent("table") is not t:
                continue
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"]) if c.find_parent("table") is t]
            src.update(_normalized_numbers(" ".join(cells)))
        if not src:
            continue
        eids = set()
        for node in [t] + t.find_all(True):
            eids |= by_node.get(id(node), set())
        got = Counter()
        for e in eids:
            got.update(_normalized_numbers(elements[e].content.replace("|", " ")))
        out.append((dict(src - got), "mapped" if eids else "NO MAPPED ELEMENT"))
    return out


MERGE_LOSS = ("<table><tr><td>2024</td><td>$</td><td>9,943</td></tr>"
              "<tr><td>2025</td><td></td><td>10,775</td></tr><tr><td>Total</td><td>$</td><td>20,718</td></tr></table>")
CASES = {
    "1 prose supplies the lost value": "<p>Commitments include $9,943 million due in 2024.</p>" + MERGE_LOSS,
    "2a split inline number": ("<table><tr><td>Item</td><td>2026</td></tr>"
                               "<tr><td>Revenue</td><td>1,2<span>34</span></td></tr></table>"),
    "2b hidden descendant in a visible cell": ("<table><tr><td>Item</td><td>2026</td></tr>"
                                               "<tr><td>Revenue</td><td>100<span style=\"display:none\">999</span></td></tr></table>"),
    "2c euro and pound values": ("<table><tr><td>Item</td><td>2026</td></tr>"
                                 "<tr><td>Revenue</td><td>€123</td></tr><tr><td>Cost</td><td>£456</td></tr></table>"),
    "3 single-digit financial value lost": ("<table><tr><td>Impairment</td><td>$</td><td>9</td></tr>"
                                            "<tr><td>Other</td><td></td><td>12</td></tr>"
                                            "<tr><td>Total</td><td>$</td><td>21</td></tr></table>"),
    "3b footnote marker lost": ("<table><tr><th>Item</th><th>2026</th></tr>"
                                "<tr><td>Revenue<sup>(1)</sup></td><td>120</td></tr></table>"),
    "4a nested table value preserved": ("<table><tr><td>Outer<table><tr><td>Inner</td><td>77</td></tr>"
                                        "<tr><td>B</td><td>88</td></tr></table></td><td>12</td></tr>"
                                        "<tr><td>Outer B</td><td>34</td></tr></table>"),
    "4b one-row table shifts snapshot ordinals": ("<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table>"
                                                  "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>"),
}

for name, html in CASES.items():
    print(f"== {name}")
    print("   v1:", v1(html))
    for r in v2.analyze(html):
        print(f"   v2: table {r.ordinal} (snapshot {r.snapshot_ordinal}) enforced missing={dict(r.missing)} "
              f"{r.missing_tokens} reported={dict(r.reported)} order={r.order}")

print("== 5 mutation: numeric cells reversed in every body row")
import re
def reverse_numeric_cells(segment):
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        vals = [cells[i] for i in idx][::-1]
        for i, v in zip(idx, vals):
            cells[i] = v
        out.append("|".join(cells))
    return "\n".join(out)
html = ("<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>120</td><td>100</td></tr><tr><td>Cost</td><td>50</td><td>40</td></tr></table>")
for r in v2.analyze(html, mutate=reverse_numeric_cells):
    print(f"   v2: enforced missing={dict(r.missing)} order={r.order}")
