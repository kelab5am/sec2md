"""Regenerate spec evidence with the revised (v2) definitions over fixtures and RCQ filings."""
import glob
import gzip
import json
import os
import re
import sys
import warnings
from collections import Counter

warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
import completeness_v2 as v2
from sec2md.encoding import decode_html
from sec2md import table_parser

FIXTURES = ["aapl-2023-10k", "nvda-2026-10k", "nvda-2002-10k", "nvda-2026-q2-10q",
            "nvda-2026-08-26-8k", "nvda-2026-ex99-1", "nvda-2026-ex99-2"]
docs = [(f, decode_html(gzip.open(f"tests/fixtures/sec/{f}.html.gz", "rb").read())[0]) for f in FIXTURES]
rcq = sorted(f for co in ("META", "RDDT") for f in glob.glob(f"E:/RCQWealth/{co}/Originals/SEC/*/*.htm"))
docs += [(os.path.basename(f)[:26], decode_html(open(f, "rb").read())[0]) for f in rcq]

report = {}
for group, items in (("fixtures", docs[:7]), ("rcq", docs[7:])):
    total = Counter()
    for name, html in items:
        results = v2.analyze(html)
        s = v2.summarize(results)
        total.update(s)
        examples = [(r.ordinal, r.snapshot_ordinal, r.missing_tokens[:4]) for r in results if r.missing][:5]
        orders = [(r.ordinal, r.order) for r in results if r.order]
        report[name] = {"summary": dict(s), "examples": examples, "order": orders}
        print(f"{name:26} {dict(s)}")
        for o in orders:
            print("      check2:", o)
    print(f"TOTAL {group}: {dict(total)}\n")
    report[f"TOTAL {group}"] = dict(total)

aapl = docs[0][1]
original_md = table_parser.TableParser.md
table_parser.TableParser.md = lambda self, *a, **k: ""
blank = v2.summarize(v2.analyze(aapl))
table_parser.TableParser.md = original_md
print("mutation, blank TableParser.md (AAPL):", dict(blank))


def reverse_numeric_cells(segment):
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        for i, value in zip(idx, [cells[i] for i in idx][::-1]):
            cells[i] = value
        out.append("|".join(cells))
    return "\n".join(out)


reversed_ = v2.summarize(v2.analyze(aapl, mutate=reverse_numeric_cells))
print("mutation, reversed numeric cells (AAPL):", dict(reversed_))
report["mutations"] = {"blank_tableparser": dict(blank), "reversed_cells": dict(reversed_)}
json.dump(report, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
