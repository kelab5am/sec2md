# Revision 3 evidence for the table completeness check spec

> Superseded by `../v4/` (spec revision 4). Kept as the evidence for revision 3.

These scripts implement exactly the definitions in revision 3 of
`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`.
They supersede `../v2/` (revision 2) and `../proto_tables.py` / `../proto_rows_body.py`
(revision 1).

Run them from the sec2md checkout root, with that checkout importable
(`PYTHONPATH=src` or `pip install -e ".[xlsx]"`). Pass this folder as the first
argument:

| Command | What it does |
|---|---|
| `python <this folder>/review_cases_v3.py <this folder>` | Runs every review case from rounds 1–3 in normal and capture rendering modes. The last run is saved in `review_cases_output.txt`. |
| `python <this folder>/corpus_v3.py <this folder> <out.json>` | Runs the 7 fixtures and the 20 RCQ filings in `E:\RCQWealth`, in both modes, plus three AAPL mutations. The spec's figures are in `evidence.json`. |
| `python <this folder>/inspect_v3.py <this folder> <fixture or RCQ name prefix> <table ordinals>` | Shows one table's source data rows and output segment. |

The prototype gets snapshot metadata from a second, capture-mode parse. That
keeps the checked rendering unchanged, but its timing is not representative.
