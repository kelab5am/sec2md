# Revision 5 evidence for the table completeness check spec

> Superseded by `../v6/` (spec revision 6). Kept as the evidence for revision 5.

These scripts implement exactly the definitions in revision 5 of
`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`.
They supersede the evidence for earlier revisions:

| Folder or files | Revision |
|---|---|
| `../v4/` | 4 |
| `../v3/` | 3 |
| `../v2/` | 2 |
| `../proto_tables.py`, `../proto_rows_body.py` | 1 |

What each later revision added:

- **Revision 4: occurrence positions.** Each number is tagged as an identifier,
  in a numeric cell, in a text cell, in a header line, or in text rendering. A
  value may only claim a compatible output position, and references and markers
  claim first.
- **Revision 4: period rows decided by context**, not by the numeric shape of a
  value.
- **Revision 5: standalone markers.** A `<td><sup>9</sup></td>` footnote cell
  renders as a numeric cell, so it has its own position, which may claim
  numeric cells.
- **Revision 5: row provenance.** Pass 1 pairs each source row with its own
  output line by row label and matches only within that line. Pass 2 matches
  the rest table-wide, and only pass-2 competition between a value and a
  reference or marker makes a value shortfall ambiguous.

Run them from the sec2md checkout root, with that checkout importable
(`PYTHONPATH=src` or `pip install -e ".[xlsx]"`). Pass this folder as the first
argument:

| Command | What it does |
|---|---|
| `python <this folder>/review_cases_v5.py <this folder>` | Runs every review case from rounds 1–4 in normal and capture rendering modes. The last run is saved in `review_cases_output.txt`. |
| `python <this folder>/corpus_v5.py <this folder> <out.json>` | Runs the 7 fixtures and the 20 RCQ filings in `E:\RCQWealth`, in both modes, plus three AAPL mutations. The spec's figures are in `evidence.json`. |
| `python <this folder>/inspect_v5.py <this folder> <fixture or RCQ name prefix> <table ordinals>` | Shows one table's source data rows and output segment. |

The prototype gets snapshot metadata from a second, capture-mode parse. That
keeps the checked rendering unchanged, but it makes the prototype's timing
unrepresentative.
