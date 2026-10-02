"""Every numeric copy-grid value in exported tables must equal a number in its own source table."""
import glob, os, sys, warnings
from collections import Counter
from decimal import Decimal
warnings.filterwarnings("ignore")
from sec2md.parser import Parser
from sec2md.encoding import decode_html
from sec2md.quality import _normalized_numbers
from sec2md.xlsx_tables import prepare_table, select_export_tables
tot = Counter(); bad_examples = []
for path in sorted(f for co in ("META", "RDDT") for f in glob.glob(f"E:/RCQWealth/{co}/Originals/SEC/*/*.htm")):
    name = os.path.basename(path)[:26]
    p = Parser(decode_html(open(path, "rb").read())[0], capture_tables=True); p.get_pages(include_images=False)
    doc = Counter()
    for snap in select_export_tables(p.table_snapshots):
        t = prepare_table(snap)
        if t.status == "source_text_only": continue
        source = Counter(Decimal(x) for x in _normalized_numbers(" ".join(c.text for c in snap.source_cells)))
        for row in t.rows:
            for cell in row:
                v = cell.value
                if not isinstance(v, Decimal): continue
                doc["numeric"] += 1
                candidates = {v, v * 100}
                if any(c in source for c in candidates):
                    doc["matched"] += 1
                else:
                    doc["unmatched"] += 1
                    if len(bad_examples) < 12:
                        bad_examples.append((name, t.title[:30], [str(c.value) for c in row][:5], str(v)))
    tot.update(doc)
    print(f"{name}  numeric={doc['numeric']:5} matched={doc['matched']:5} unmatched={doc['unmatched']}")
print(dict(tot))
for b in bad_examples: print("  UNMATCHED", b)
