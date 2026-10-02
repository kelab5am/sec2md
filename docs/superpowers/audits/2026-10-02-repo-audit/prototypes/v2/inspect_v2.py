"""Show one table's v2 view: header rows, source data rows, and the parser's output segment."""
import gzip
import glob
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
import completeness_v2 as v2
from bs4 import Tag
from sec2md.encoding import decode_html
from sec2md.parser import Parser

name, ordinals = sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
try:
    html = decode_html(gzip.open(f"tests/fixtures/sec/{name}.html.gz", "rb").read())[0]
except FileNotFoundError:
    html = decode_html(open(glob.glob(f"E:/RCQWealth/*/Originals/SEC/*/{name}*.htm")[0], "rb").read())[0]

parser = Parser(html, capture_tables=True)
segments = {}
orig = parser._process_element
def rec(el):
    out = orig(el)
    if isinstance(el, Tag) and el.name == "table" and el.find_parent("table") is None:
        segments[id(el)] = out
    return out
parser._process_element = rec
parser.get_pages(include_images=False)
snaps = {id(n[0]): s for s, n in zip(parser.table_snapshots, parser._snapshot_nodes) if len(n) == 1}
hid = v2.hidden_ids(parser.soup)
tables = [t for t in parser.soup.find_all("table") if id(t) not in hid and t.find_parent("table") is None]
for o in ordinals:
    t = tables[o - 1]
    snap = snaps.get(id(t))
    hr = v2._snapshot_header_rows(snap)
    print(f"===== table {o}: snapshot {snap.ordinal if snap else None}, header_rows={hr}")
    rows = [tr for tr in t.find_all("tr") if id(tr) not in hid and tr.find_parent("table") is t]
    for i, tr in enumerate(rows[:14]):
        texts = [v2.cell_text(c, hid) for c in tr.find_all(["td", "th"], recursive=False) if id(c) not in hid]
        vals = [v for v, m in texts if v]
        if vals:
            print(f"   src{i:2}{'H' if i < hr else ' '} {vals[:7]}  marks={[m for v, m in texts if m][:3]}")
    print("   OUTPUT:")
    for line in segments.get(id(t), "").split("\n")[:16]:
        print("     ", line[:150])
