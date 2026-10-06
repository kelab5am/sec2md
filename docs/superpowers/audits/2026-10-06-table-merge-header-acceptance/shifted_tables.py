"""Criterion 10: the known shifted tables, asserted header over value (research only).

    python shifted_tables.py --main-dir <main dumps> --candidate-dir <candidate dumps> --out shifted_tables.json

Independent of the header-alignment checker: each assertion names a source row label, the
exact text of one output cell and the header that cell must carry. The expected headers
were written from the source grids (evidence report, examples 3b and 3c, and
inspect_unit.py), as R6 writes a faithful header: the header-zone cells over the value's
column, top to bottom, joined with " — ". The output line is the one body line whose first
cell is the label (exactly one), the cell is the one cell with that text (exactly one), and
the header is the header line's cell at the same index. Both runs' normal-mode Markdown
are checked; main is expected to fail.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402

BABA = "edgar:BABA-20-F-2025-06-26.htm"
TSM = "edgar:TSM-20-F-2025-04-17.htm"
JPM = "edgar:JPM-10-K-2025-02-14.htm"
MSFT = "edgar:MSFT-10-K-2025-07-30.htm"
RDDT = "rcq:RDDT__10-Q__2024-Q2__c-63xzxqtyzzhgyhto__s-000171344524000054.htm"
YE = "Year ended March 31,"
MIL = "(in millions, except per share data)"
TSM_Y = "For the year ended December 31,"
TSM_312 = "Years Ended December 31"
RD3, RD6 = "Three months ended June 30,", "Six months ended June 30,"
RDC = "(in thousands, except share and per share data)"

# (document, unit, row label, output cell text, expected header)
ASSERTIONS = [
    (BABA, 24, "Revenue", "868,687", f"{YE} — 2023 — RMB — {MIL}"),
    (BABA, 24, "Revenue", "941,168", f"{YE} — 2024 — RMB — {MIL}"),
    (BABA, 24, "Revenue", "996,347", f"{YE} — 2025 — RMB — {MIL}"),
    (BABA, 24, "Revenue", "137,300", f"{YE} — 2025 — US$ — (Note 2(a)) — {MIL}"),
    (TSM, 79, "Gross profit", "59.6", f"{TSM_Y} — 2022"),
    (TSM, 79, "Gross profit", "54.4", f"{TSM_Y} — 2023"),
    (TSM, 79, "Gross profit", "56.1", f"{TSM_Y} — 2024"),
    (TSM, 312, "Balance, beginning of year", "$ 347.0", f"{TSM_312} — 2022 — NT$ — (In Millions)"),
    (TSM, 312, "Balance, beginning of year", "$ 331.6", f"{TSM_312} — 2023 — NT$ — (In Millions)"),
    (TSM, 312, "Balance, beginning of year", "$ 531.5", f"{TSM_312} — 2024 — NT$ — (In Millions)"),
    (TSM, 312, "Provision (Reversal)", "199.9", f"{TSM_312} — 2023 — NT$ — (In Millions)"),
    (JPM, 482, "Purchases", "$ 647", "2024 — Consumer, excluding credit card"),
    (JPM, 482, "Purchases", "$ —", "2024 — Credit card"),
    (JPM, 482, "Purchases", "$ 1,432", "2024 — Wholesale"),
    (JPM, 482, "Purchases", "$ 2,079", "2024 — Total"),
    (JPM, 482, "Sales", "45,147", "2024 — Wholesale"),
    (JPM, 482, "Sales", "55,587", "2024 — Total"),
    (MSFT, 24, "Total revenue", "281,724", "2025"),
    (MSFT, 24, "Total revenue", "245,122", "2024"),
    (MSFT, 24, "Total revenue", "211,915", "2023"),
    (MSFT, 65, "First Quarter", "7", "Shares — 2025"),
    (MSFT, 65, "First Quarter", "$ 2,800", "Amount — 2025"),
    (MSFT, 65, "First Quarter", "11", "Shares — 2024"),
    (MSFT, 65, "First Quarter", "$ 3,560", "Amount — 2024"),
    (MSFT, 65, "First Quarter", "17", "Shares — 2023"),
    (MSFT, 65, "First Quarter", "$ 4,600", "Amount — 2023"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "49,386,912", f"{RD3} — 2024 — Class A — {RDC}"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "114,995,824", f"{RD3} — 2024 — Class B — {RDC}"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "7,047,807", f"{RD3} — 2023 — Class A — {RDC}"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "51,460,350", f"{RD3} — 2023 — Class B — {RDC}"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "30,317,800", f"{RD6} — 2024 — Class A — {RDC}"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "86,993,814", f"{RD6} — 2024 — Class B — {RDC}"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "6,873,912", f"{RD6} — 2023 — Class A — {RDC}"),
    (RDDT, 17, "Basic weighted-average common shares outstanding", "51,438,626", f"{RD6} — 2023 — Class B — {RDC}"),
]


def cells(line):
    inner = line.strip()
    inner = inner[2:] if inner.startswith("| ") else inner.lstrip("|")
    inner = inner[:-2] if inner.endswith(" |") else inner.rstrip("|")
    return [" ".join(c.split()) for c in re.split(r"(?<!\\) \| ", inner)]


def check(segment, label, value, expected):
    lines = (segment or "").split("\n")
    if len(lines) < 3:
        return {"ok": False, "why": "no table"}
    header = cells(lines[0])
    body = [cells(line) for line in lines[2:]]
    rows = [c for c in body if c and c[0] == label]
    if len(rows) != 1:
        return {"ok": False, "why": f"{len(rows)} lines labelled {label!r}"}
    hits = [i for i, c in enumerate(rows[0]) if c == value]
    if len(hits) != 1:
        return {"ok": False, "why": f"{len(hits)} cells reading {value!r}", "line": " | ".join(rows[0])[:300]}
    got = header[hits[0]] if hits[0] < len(header) else ""
    return {"ok": got == expected, "header": got, "column": hits[0]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--main-dir", required=True)
    ap.add_argument("--candidate-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    dumps, results = {}, []
    for doc, unit, label, value, expected in ASSERTIONS:
        entry = {"doc": doc, "unit": unit, "label": label, "value": value, "expected": expected}
        for side, directory in (("main", args.main_dir), ("candidate", args.candidate_dir)):
            key = (side, doc)
            if key not in dumps:
                dumps[key] = acc_common.read_json_gz(os.path.join(directory, acc_common.safe_name(doc)))
            segment = dumps[key]["modes"]["normal"]["units"][unit - 1]["output"]
            entry[side] = check(segment, label, value, expected)
        results.append(entry)
    summary = {side: {"passed": sum(r[side]["ok"] for r in results), "total": len(results)}
               for side in ("main", "candidate")}
    by_table = {}
    for r in results:
        by_table.setdefault(f"{r['doc']} {r['unit']}", []).append(r["candidate"]["ok"])
    summary["candidate_tables_all_passing"] = {k: all(v) for k, v in by_table.items()}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "assertions": results}, handle, ensure_ascii=False, indent=1)
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    for r in results:
        if not r["candidate"]["ok"]:
            print("CANDIDATE FAIL:", r["doc"], r["unit"], r["label"], r["value"], "expected", repr(r["expected"]),
                  "got", r["candidate"])


if __name__ == "__main__":
    main()
