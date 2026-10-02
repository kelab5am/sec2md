# Revision 6 evidence for the table completeness check spec

These scripts implement exactly the definitions in revision 6 of
`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`.
They supersede the evidence for earlier revisions:

| Folder or files | Revision |
|---|---|
| `../v5/` | 5 |
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
- **Revision 5: standalone markers.** A `<td><sup>9</sup></td>` footnote cell may
  claim numeric cells.
- **Revision 5: row provenance.** Pass 1 matches each paired source row only
  within its own output line.
- **Revision 6: label keys keep identifier numbers** (`note#1`, `note#2`).
- **Revision 6: proven pairings only.** A pairing holds only when the key is
  unique among the source rows and among the output body lines. Duplicate or
  uncertain labels go to pass 2, the table-wide pass. There, competition between
  a value and a reference or marker makes a value shortfall ambiguous.

Run them from the sec2md checkout root, with that checkout importable
(`PYTHONPATH=src` or `pip install -e ".[xlsx]"`). Pass this folder as the first
argument:

| Command | What it does |
|---|---|
| `python <this folder>/review_cases_v6.py <this folder>` | Runs every review case from rounds 1–5 in normal and capture rendering modes. The last run is saved in `review_cases_output.txt`. |
| `python <this folder>/corpus_v6.py <this folder> <out.json>` | Runs the 7 fixtures and the 20 RCQ filings in `E:\RCQWealth`, in both modes, plus three AAPL mutations. The spec's figures are in `evidence.json`. |
| `python <this folder>/inspect_v6.py <this folder> <fixture or RCQ name prefix> <table ordinals>` | Shows one table's source data rows and output segment. |

The prototype gets snapshot metadata from a second, capture-mode parse. That
keeps the checked rendering unchanged, but it makes the prototype's timing
unrepresentative.
