"""Revision 3 evidence: fixtures and RCQ filings in normal and capture modes, plus AAPL mutations."""
import glob
import gzip
import json
import os
import re
import sys
import warnings
from collections import Counter

warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])  # this folder
import completeness_v6 as v3
from sec2md import table_parser
from sec2md.encoding import decode_html

FIXTURES = ["aapl-2023-10k", "nvda-2026-10k", "nvda-2002-10k", "nvda-2026-q2-10q",
            "nvda-2026-08-26-8k", "nvda-2026-ex99-1", "nvda-2026-ex99-2"]
docs = [(f, decode_html(gzip.open(f"tests/fixtures/sec/{f}.html.gz", "rb").read())[0]) for f in FIXTURES]
rcq = sorted(f for co in ("META", "RDDT") for f in glob.glob(f"E:/RCQWealth/{co}/Originals/SEC/*/*.htm"))
docs += [(os.path.basename(f)[:26], decode_html(open(f, "rb").read())[0]) for f in rcq]

report = {}
for mode, capture in (("normal", False), ("capture", True)):
    for group, items in (("fixtures", docs[:7]), ("rcq", docs[7:])):
        total, flagged_docs = Counter(), 0
        for name, html in items:
            results = v3.analyze(html, capture=capture)
            s = v3.summarize(results)
            total.update(s)
            flagged_docs += bool(s["flagged"])
            report[f"{mode}/{name}"] = {
                "summary": dict(s),
                "missing": [(r.ordinal, r.snapshot_ordinal, r.missing_tokens[:6]) for r in results if r.missing],
                "order": [(r.ordinal, r.snapshot_ordinal, r.order[:3]) for r in results if r.order],
            }
            for r in results:
                if r.order:
                    print(f"   {mode} {name} table {r.ordinal}: {r.order[:2]}")
        total["documents_with_flags"] = flagged_docs
        report[f"TOTAL {mode} {group}"] = dict(total)
        print(f"TOTAL {mode} {group}: {dict(total)}")

aapl = docs[0][1]
original_md = table_parser.TableParser.md
table_parser.TableParser.md = lambda self, *a, **k: ""
blank = v3.summarize(v3.analyze(aapl))
table_parser.TableParser.md = original_md


def reverse_numeric_cells(segment):
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        for i, value in zip(idx, [cells[i] for i in idx][::-1]):
            cells[i] = value
        out.append("|".join(cells))
    return "\n".join(out)


def swap_first_body_rows(segment):
    """Swap the first two distinct body lines that each carry two or more tokens."""
    from sec2md.chunker.blocks import is_separator_row
    lines = segment.split("\n")
    sep = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    if sep is None:
        return segment
    rows = [i for i in range(sep + 1, len(lines)) if len(v3.output_numbers(lines[i])) >= 2]
    pair = next(((a, b) for a, b in zip(rows, rows[1:]) if lines[a] != lines[b]), None)
    if pair:
        a, b = pair
        lines[a], lines[b] = lines[b], lines[a]
    return "\n".join(lines)


mutations = {
    "blank_tableparser": dict(blank),
    "reversed_cells": dict(v3.summarize(v3.analyze(aapl, mutate=reverse_numeric_cells))),
    "swapped_first_body_rows": dict(v3.summarize(v3.analyze(aapl, mutate=swap_first_body_rows))),
}
for k, v in mutations.items():
    print(f"mutation {k}: {v}")
report["mutations (AAPL, normal mode)"] = mutations
json.dump(report, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
