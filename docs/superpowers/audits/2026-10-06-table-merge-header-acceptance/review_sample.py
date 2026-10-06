"""Criterion 13: print the review sample's source rows and both renderings (research only).

    PYTHONPATH=<worktree>/src python review_sample.py --fixtures-root <checkout> --edgar-cache <cache> \
        --main-dir <main dumps> --candidate-dir <candidate dumps> --out review_sample.txt

The sample is fixed below: at least one changed table per evidence class (1, 2, 3, 3e, 4,
5, 6, 7, 8, U+200B), the classes round 1 found (display:none cells, body rows promoted
into the header zone, the years-row limitation, value spans over a header column), F7,
round 2's cases (revision 11's header-like rows and years rows, stacked titles,
column-heading second rows) and round 3's (revision 12: label-only rows, main's sparse-row
fusion, and the rows it fuses that main kept in its body). Round 3 leaves out 8 tables whose
rendering is unchanged since round 2, where they were correct, and whose class stays covered:
TSLA 38, BAC 88, RDDT 10-Q t17, MSFT 65, CAT 34, KO 110, BAC 46, JPM 543. Round 4 (revision
13) keeps the same 42 tables and relabels the three S9 cases. For each table: the checker's placed source grid (origin cells, colspans, R0 role per
row: H header zone, D data row, . other), main's Markdown and the candidate's Markdown
(normal mode), each cut to a few lines. The verdicts are in REPORT.md.
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402

E = "edgar:"
SAMPLE = [
    ("1 header row 0 (1a)", "rcq:NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm", 18),
    ("1 caption (1b)", E + "CRM-10-K-2025-03-05.htm", 26),
    ("1 data row 0, G2 (1c)", E + "JPM-10-K-2025-02-14.htm", 109),
    ("2 sibling value fusion (2a)", E + "TSM-20-F-2025-04-17.htm", 248),
    ("2 X marks (2b)", "rcq:RDDT__10-Q__2024-Q2__c-63xzxqtyzzhgyhto__s-000171344524000054.htm", 52),
    ("3 $ column and year (3a)", E + "MSFT-10-K-2025-07-30.htm", 24),
    ("3 leading-dot decimals", "fixture:nvda-2002-10k", 138),
    ("3e empty-slot shift (3b)", E + "BABA-20-F-2025-06-26.htm", 24),
    ("3e TSM 79", E + "TSM-20-F-2025-04-17.htm", 79),
    ("3e footnote column (3c)", E + "JPM-10-K-2025-02-14.htm", 482),
    ("4 US$ data cell (4b)", E + "TSM-20-F-2025-04-17.htm", 344),
    ("5 fusion swallows data (5a)", "fixture:aapl-2023-10k", 18),
    ("5 fusion swallows data (5b)", "rcq:META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm", 4),
    ("5 header rows k>=3 (5c)", "fixture:nvda-2026-10k", 17),
    ("5 second header row (5c)", "fixture:nvda-2026-10k", 36),
    ("6 signature date (6a)", E + "GOOGL-10-Q-2025-10-30.htm", 89),
    ("6 exhibit-index columns (6b)", "fixture:aapl-2023-10k", 64),
    ("7 one-row PART (7a)", E + "CAT-10-K-2025-02-14.htm", 7),
    ("8 single negative (8b)", E + "BABA-20-F-2025-06-26.htm", 69),
    ("8 ) column shares $ (8c)", E + "MSFT-10-K-2025-07-30.htm", 43),
    ("8 dedicated split (8a)", "fixture:nvda-2002-10k", 157),
    ("U+200B cells", E + "NTRA-10-K-2025-02-28.htm", 141),
    ("new: display:none cells, value split", E + "BAC-10-K-2025-02-25.htm", 336),
    ("new: body rows promoted (text values)", "fixture:aapl-2023-10k", 8),
    ("new: body rows promoted (values with units)", "rcq:META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm", 44),
    ("named limitation: years row", E + "TSM-20-F-2025-04-17.htm", 136),
    ("F7 headerless continuation", E + "CAT-10-K-2025-02-14.htm", 143),
    ("new: value span over the header column", E + "MSFT-10-K-2025-07-30.htm", 69),
    # Round 2 (spec revision 11).
    ("r2: S1 exhibit pair with different links", "rcq:META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm", 39),
    ("r2: stacked titles end the zone (S7)", "fixture:nvda-2026-ex99-1", 5),
    ("r2: stacked titles end the zone (S7), outlook", "fixture:nvda-2026-ex99-1", 11),
    ("r2: column-heading second row holding dates", "rcq:META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm", 37),
    ("r2: statement-title label beside dates", E + "TSLA-10-K-2025-01-30.htm", 40),
    ("r2: section label beside a unit caption", "fixture:nvda-2026-10k", 38),
    # Round 3 (spec revision 12).
    ("r3: stacked titles over period rows (S7)", "fixture:nvda-2026-ex99-1", 6),
    ("r3: label-only rows above headings, corpus (S7)", E + "CAT-10-K-2025-02-14.htm", 139),
    ("r3: exhibit index headings under a caption span (S8)", "fixture:aapl-2023-10k", 61),
    ("r3: column headings and a caption row (S8)", E + "TSM-20-F-2025-04-17.htm", 89),
    ("r3: fused, main kept in body: performance graph headings", E + "NTRA-10-K-2025-02-28.htm", 123),
    ("r4: marker columns leave the count, values row stays body (S9)", E + "AMZN-10-Q-2025-10-31.htm", 21),
    ("r4: accepted source-grid fusion: enumerated item", E + "TSM-20-F-2025-04-17.htm", 216),
    ("r4: headings fuse without marker columns (S9 mirror)", E + "JPM-10-K-2025-02-14.htm", 207),
]


def compact(cells):
    out, empties = [], 0
    for text, span in cells:
        if not text and span == 1:
            empties += 1
            continue
        if empties:
            out.append(f"·×{empties}" if empties > 1 else "·")
            empties = 0
        out.append((text[:48] + ("…" if len(text) > 48 else "")) + (f" [cs{span}]" if span > 1 else ""))
    if empties:
        out.append(f"·×{empties}" if empties > 1 else "·")
    return " | ".join(out)


def source_rows(table, grid_hidden, limit):
    from sec2md.table_alignment import SourceAnalysis, source_grid
    from sec2md.table_completeness import place_unit, unit_rows

    grid = source_grid(place_unit(table, unit_rows(table), grid_hidden))
    if grid is None:
        return ["(placement unreliable)"]
    analysis = SourceAnalysis(grid)
    lines = []
    for r, row in enumerate(grid.slots):
        shown, k = [], 0
        while k < len(row):
            cell = row[k]
            if cell is not None and (cell.row, cell.column) == (r, k):
                shown.append((cell.text, cell.colspan))
                k += cell.colspan
            else:
                shown.append(("^" if cell is not None else "", 1))
                k += 1
        if not any(t and t != "^" for t, _ in shown):
            continue
        role = "H" if r in analysis.roles.header_rows else ("D" if r in analysis.roles.data_rows else ".")
        lines.append(f"{role} r{r}: {compact(shown)}")
    return lines[:limit]


def main():
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fixtures-root", required=True)
    ap.add_argument("--edgar-cache", required=True)
    ap.add_argument("--main-dir", required=True)
    ap.add_argument("--candidate-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lines", type=int, default=7)
    args = ap.parse_args()
    from sec2md.encoding import decode_html
    from sec2md.parser import Parser
    from sec2md.table_completeness import hidden_sets

    docs, _ = acc_common.load_documents(args.edgar_cache, args.fixtures_root)
    raw = {d: r for d, _, r in docs}
    parsed = {}
    out = []
    for number, (label, doc, unit) in enumerate(SAMPLE, 1):
        if doc not in parsed:
            parser = Parser(decode_html(raw[doc])[0])
            parser.get_pages(include_images=False)
            outermost, hidden, grid_hidden = hidden_sets(parser.soup)
            parsed[doc] = ([t for t in outermost if id(t) not in hidden], grid_hidden)
        units, grid_hidden = parsed[doc]
        table = units[unit - 1]
        hidden_cells = sum(1 for td in table.find_all(["td", "th"]) if id(td) in grid_hidden)
        out.append(f"===== {number}. {label}: {doc} table {unit} (display:none cells: {hidden_cells})")
        out.append("-- source (checker's placed grid; H header zone, D data row)")
        out.extend("   " + line for line in source_rows(table, grid_hidden, 12))
        for side, directory in (("main", args.main_dir), ("candidate", args.candidate_dir)):
            dump = acc_common.read_json_gz(os.path.join(directory, acc_common.safe_name(doc)))
            segment = dump["modes"]["normal"]["units"][unit - 1]["output"] or "(no output)"
            out.append(f"-- {side}")
            out.extend("   " + (line if len(line) <= 400 else line[:400] + " …")
                       for line in segment.split("\n")[: args.lines])
        out.append("")
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out))
    print(f"{len(SAMPLE)} tables written to {args.out}")


if __name__ == "__main__":
    main()
