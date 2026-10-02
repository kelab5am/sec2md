# Revision 2 evidence for the table completeness check spec

These scripts implement exactly the definitions in revision 2 of
`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`.
They supersede `../proto_tables.py` and `../proto_rows_body.py`; the revision 1
spec's evidence came from those older scripts.

Run from a sec2md checkout root, with that checkout importable (`PYTHONPATH=src`
or `pip install -e ".[xlsx]"`), passing this folder as the first argument:

- `python <this folder>/review_cases.py <this folder>`: the review cases, run with both revision 1 and revision 2
- `python <this folder>/corpus_v2.py <this folder> <out.json>`: the 7 fixtures, the 20 RCQ filings in `E:\RCQWealth`, and both AAPL mutations
- `python <this folder>/inspect_v2.py <this folder> <fixture or RCQ name prefix> <table ordinals>`: one table's source rows and output segment

`evidence.json` holds the results the spec cites.
