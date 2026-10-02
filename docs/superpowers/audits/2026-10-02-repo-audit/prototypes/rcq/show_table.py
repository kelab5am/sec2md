import glob, sys, warnings
warnings.filterwarnings("ignore")
from sec2md.parser import Parser
from sec2md.encoding import decode_html
from sec2md.quality import _is_hidden_tag
path = glob.glob(f"E:/RCQWealth/*/Originals/SEC/*/{sys.argv[1]}*.htm")[0]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 6
p = Parser(decode_html(open(path, "rb").read())[0]); pages = p.get_pages()
elements = {e.id: e for pg in pages for e in (pg.elements or [])}
by_node = {}
for eid, nodes in p.block_nodes_map.items():
    for n in nodes: by_node.setdefault(id(n), set()).add(eid)
hid = set()
for tag in p.soup.find_all(True):
    if _is_hidden_tag(tag): hid.add(id(tag)); hid.update(id(d) for d in tag.find_all(True))
tables = [t for t in p.soup.find_all("table") if id(t) not in hid]
for ordinal in map(int, sys.argv[2].split(",")):
    t = tables[ordinal - 1]
    print(f"===== table {ordinal} SOURCE:")
    shown = 0
    for tr in t.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"]) if c.get_text(strip=True)]
        if cells and shown < limit: print("   ", cells[:9]); shown += 1
    eids = set()
    for node in [t] + t.find_all(True): eids |= by_node.get(id(node), set())
    print("  OUTPUT table lines:")
    for e in sorted(eids):
        rows = [l for l in elements[e].content.split("\n") if l.lstrip().startswith("|")]
        for line in rows[:limit + 1]: print("   ", line[:180])
