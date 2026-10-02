"""Show one table's revision 3 view: source data rows and the output segment's body lines."""
import glob
import gzip
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])  # this folder
import completeness_v6 as v3
from bs4 import Tag
from sec2md.encoding import decode_html
from sec2md.parser import Parser

name, ordinals = sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
try:
    html = decode_html(gzip.open(f"tests/fixtures/sec/{name}.html.gz", "rb").read())[0]
except FileNotFoundError:
    html = decode_html(open(glob.glob(f"E:/RCQWealth/*/Originals/SEC/*/{name}*.htm")[0], "rb").read())[0]

parser = Parser(html)
segments = {}
original = parser._process_element


def recording(element):
    out = original(element)
    if isinstance(element, Tag) and element.name == "table" and element.find_parent("table") is None:
        segments[id(element)] = out
    return out


parser._process_element = recording
parser.get_pages(include_images=False)
snapshots = v3._snapshot_metadata(html)
hid = v3.hidden_ids(parser.soup)
units = v3._units(parser.soup, hid)
for ordinal in ordinals:
    table = units[ordinal - 1]
    snap = snapshots[ordinal - 1]
    header_rows = v3._header_rows(snap)
    print(f"===== table {ordinal} (snapshot {snap.ordinal if snap else None}), header rows {header_rows}")
    own_rows = [tr for tr in table.find_all("tr") if id(tr) not in hid and tr.find_parent("table") is table]
    for i, tr in enumerate(own_rows[:16]):
        texts = [v3.cell_text(c, hid)[0] for c in tr.find_all(["td", "th"], recursive=False) if id(c) not in hid]
        cells = v3.merge_split_negatives(texts)
        if cells:
            tokens = [t for c in cells for t, _ in v3.classify_cell(c)]
            print(f"   src{i:2}{'H' if i < header_rows else ' '} {cells[:7]} -> {tokens}")
    print("   OUTPUT:")
    for line in segments.get(id(table), "").split("\n")[:18]:
        print("     ", line[:160])
