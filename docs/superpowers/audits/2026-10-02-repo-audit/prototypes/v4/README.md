# Revision 4 evidence for the table completeness check spec

> Superseded by `../v5/` (spec revision 5). Kept as the evidence for revision 4.

These scripts implement exactly the definitions in revision 4 of
`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`.
They supersede `../v3/` (revision 3), `../v2/` (revision 2), and
`../proto_tables.py` / `../proto_rows_body.py` (revision 1).

Revision 4 adds two things:

- **Occurrence positions.** Each number is tagged as an identifier, in a numeric
  cell, in a text cell, in a header line, or in text rendering. A value can only
  claim a compatible output position, and non-value occurrences claim first, so
  a surviving `Note 9` or `<sup>9</sup>` can't stand in for a lost amount 9.
  Shortfalls with shared provenance are labelled ambiguous.
- **Period rows decided by context**, not by the numeric shape of a value.

Run them from the sec2md checkout root, with that checkout importable
(`PYTHONPATH=src` or `pip install -e ".[xlsx]"`). Pass this folder as the first
argument:

| Command | What it does |
|---|---|
| `python <this folder>/review_cases_v4.py <this folder>` | Runs every review case from rounds 1–3, in normal and capture rendering modes. The last run is saved in `review_cases_output.txt`. |
| `python <this folder>/corpus_v4.py <this folder> <out.json>` | Runs the 7 fixtures and the 20 RCQ filings in `E:\RCQWealth`, in both modes, plus three AAPL mutations. The spec's figures are in `evidence.json`. |
| `python <this folder>/inspect_v4.py <this folder> <fixture or RCQ name prefix> <table ordinals>` | Shows one table's source data rows and output segment. |

The prototype gets snapshot metadata from a second, capture-mode parse. That
keeps the checked rendering unchanged, but it makes the prototype's timing
unrepresentative.
