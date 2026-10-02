# Table completeness Phase A corpus run

This folder holds the tooling and, once Task 11 of the implementation plan is done, the
record of the Phase A corpus run for the table completeness checks. The spec puts the
run inside Phase A: at least 50 filings, every false positive recorded in the spec, and
the D3 word-completeness measurement.

- **Spec:** [`../../specs/2026-10-02-sec2md-table-completeness-check-design.md`](../../specs/2026-10-02-sec2md-table-completeness-check-design.md)
- **Plan, Task 11:** [`../../plans/2026-10-03-sec2md-table-completeness-check.md`](../../plans/2026-10-03-sec2md-table-completeness-check.md)

| File | What it is |
|---|---|
| `fetch_edgar.py` | Downloads one primary document per filing for 16 new issuers from EDGAR and writes `edgar_manifest.json`: CIK, form, dates, accession, URL, size and SHA-256. Needs a User-Agent with the user's name and email. |
| `corpus_phase_a.py` | Runs the implementation over the corpus in both rendering modes, and writes `results.json` with every finding and each table's missing words. Prints the summary. `--inspect <document> <table>` shows one table's source rows and output for review. |
| `results.json` | The run's results (written in Task 11). |
| `edgar_manifest.json` | The EDGAR documents used (written in Task 11). |
| `classification.md` | The verdict on every new finding, and the D3 sample (written in Task 11). |

## Corpus

| Part | Documents | Filings |
|---|---|---|
| Fixtures (`tests/fixtures/sec`) | 7 | 5 |
| RCQ primary 10-Ks and 10-Qs in `E:\RCQWealth`, read-only: META 10, RDDT 10, NVDA 12 | 32 | 32 |
| RCQ exhibits with at least two tables | 52 | (exhibits of RCQ filings) |
| EDGAR: 10-Ks filed in 2025 by JPM, XOM, BRK, KO, PFE, WMT, MSFT, TSLA, JNJ, CAT, PRU, BAC, HD and UNH; 10-Qs filed in 2025 by AMZN and GOOGL | 16 | 16 |
| **Total** | **107** | **53** |

Two RCQ NVDA primaries are the same filings as fixtures: the FY2026 10-K, and the 10-Q for the 2026 Q2 quarter. `corpus_phase_a.py` skips them and lists them under `duplicates_skipped`.

## Running

Run from the implementation checkout root, with that checkout importable:

```bash
python <this folder>/fetch_edgar.py --user-agent "<name> <email>" --cache <main checkout>/outputs/table-completeness-corpus --manifest <this folder>/edgar_manifest.json
python <this folder>/corpus_phase_a.py --edgar-cache <main checkout>/outputs/table-completeness-corpus --out <this folder>/results.json
python <this folder>/corpus_phase_a.py --edgar-cache <main checkout>/outputs/table-completeness-corpus --inspect "<document id>" <table>
```

The cache stays in the ignored `outputs/` folder. Never write into `E:\RCQWealth`.

## D3 word measurement

For each table, the source words are the visible cell text check 1 uses, reduced to
letters only, lowercased, and kept when at least two letters long. They are compared as a
multiset with the words of the table's output segment, with link destinations stripped.
`word_losses` lists each table with missing words, and says whether check 1 also flagged
it. The tables flagged by words alone are what a D3 check would add.
