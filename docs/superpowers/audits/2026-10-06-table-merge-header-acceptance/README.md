# Table merge and header rules: acceptance tooling

Tooling and result files for the acceptance run of the table merge and header rules spec
([`../../specs/2026-10-05-sec2md-table-merge-header-rules-design.md`](../../specs/2026-10-05-sec2md-table-merge-header-rules-design.md),
revisions 10 to 14, "Acceptance criteria"). Baseline: unchanged `main` at `c674828`. Candidate: the prototype
branch `proto/table-merge-header`. Round 1 (spec revision 10) is reported in `REPORT.md` and its result files
carry a `round1-` prefix; round 2 (spec revision 11) is reported in `REPORT-round2.md` and its result files carry
a `round2-` prefix; round 3 (spec revision 12) is reported in `REPORT-round3.md` and its result files carry a
`round3-` prefix; round 4 (spec revision 13) is reported in `REPORT-round4.md` and its result files carry a
`round4-` prefix; round 5 (spec revision 14) is reported in `REPORT-round5.md` and writes the unprefixed result
files. Corpus: the Phase A corpus (109 documents), loaded by
[`../2026-10-03-table-completeness-corpus/corpus_phase_a.py`](../2026-10-03-table-completeness-corpus/corpus_phase_a.py)
`documents()`.

The `round1-` to `round4-` result files stay in the local checkout only (about 11 MB, ignored by this folder's
`.gitignore`); each round's report records its numbers. `plan-checks/` holds the checks made while the plan was
drafted: the pin evidence for the emptied `PINNED_FAILURES`, the `judge` early-stop probe and differential check,
and the random check of the complete-number pattern.

## Scripts

| File | Side | What it does |
|---|---|---|
| `acc_common.py` | both | Corpus loading (importlib, as the evidence scripts do), the document hash check against `results.json` and `edgar_manifest.json`, `sec2md.__file__` check, dump helpers. |
| `run_side.py` | both | Parses every document in normal and capture mode and dumps, per document: unit outputs and render paths, check 1/2 findings, strict warnings and trace failures, `header_accounting_misses`, alignment findings and coverage (candidate), pages and display pages, sections for 10-K/10-Q/20-F/8-K, and (capture) a hash of every prepared XLSX table. |
| `merges_main.py` | baseline | Replays main's `TableParser` with the evidence tracer and regenerates the 6,616 same-header value merges with their source cells. |
| `analyze_candidate.py` | candidate | Per document: the candidate's alignment checker on main's and the candidate's Markdown with per-value outcomes (`TableAlignment.outcomes`), the header retention audit, the assignment audit, split negatives, named limitations (round 2 adds year runs followed by no data row), rows moved from main's body into the candidate's header line (each checked against the header-like rule by an implementation in this file that never imports `table_roles`, with content signals; round 3: revision 12's rule, with label-only rows, main's sparse-row fusion for the second row and the trailing label-only rule; round 4: revision 13, the fusion's n and counts without marker-only columns; round 5: revision 14's complete number, one currency marker, thousands in groups of three, one `%`), rows leaving main's header line, and the zone cuts. Round 3 also records each unit's header rows (`header_row_list`). |
| `report.py` | none (reads dumps) | Aggregates everything into the result files below and prints `summary.json`. |
| `shifted_tables.py` | none (reads dumps) | Criterion 10: header-over-value assertions on the known shifted tables, independent of the checker. |
| `review_sample.py` | candidate | Criterion 13: source grid, main's and the candidate's Markdown for the review sample (`review_sample.txt`): round 3's 42 tables: round 1's and round 2's minus 8 unchanged since round 2, plus 8 round-3 cases. |
| `round4_deltas.py` | none (reads results) | Deltas from an earlier round's `<prefix>-*` files (`--previous`, default `round3`) to the current ones: round 3 -> round 4 (`round4_deltas.json`) and, with `--previous round4`, round 4 -> round 5 (`round5_deltas.json`): which result files are identical, changed `summary.json` leaves, alignment coverage and transitions, retention counts, moved rows and departures that appear or disappear. |
| `round3_deltas.py` | none (reads results) | Round 2 -> round 3 deltas (`round3_deltas.json`): round 2's S8 rows that left main's header line and their round-3 status, round 3's remaining departures, round 2's S7 zone cuts, moved rows new and gone. |
| `overhead.py` | both | Criterion 14: `get_pages(include_images=False)` on the 7 fixtures, one process per run, rounds alternating the first side. |
| `xlsx_detail.py` | both | Field-by-field XLSX and display-page comparison for the documents whose prepared-table hash differs. |
| `inspect_unit.py` | either | Shows one unit: checker grid with R0 roles, renderer grid and membership (candidate), Markdown. |

## Result files

`summary.json` (the printed summary), `check1.json`, `findings.json`, `strict.json`, `sections.json`, `xlsx.json`,
`xlsx_detail.json`, `modes.json`, `alignment.json` (coverage, transitions, residual findings),
`alignment_losses.json` (every identity evaluated on main but not on the candidate),
`alignment_values.tsv.gz` (every value identity and its outcome in both runs; document index into `run_check.json`),
`round5_deltas.json` and `round4_deltas.json` (`round4_deltas.py`), `round3_deltas.json` (round 3, `round3_deltas.py`), `header_departures.json` (round 2: rows main had in its header line that the candidate keeps in its body, and the
zone cuts by label-only rows),
`assignment.json`, `retention.json`, `class8.json`, `limitations.json`, `moved_rows.json`, `shifted_tables.json`,
`review_sample.txt`, `overhead.json`, `run_check.json` (document list, hash check, `sec2md.__file__` of every run).

## Running

From any directory, with the prototype worktree's venv (never pip-install) and `PYTHONIOENCODING=utf-8`.
`<main>` is a `git archive c674828` tree (it also supplies `tests/fixtures/sec`, identical on both sides),
`<wt>` the prototype worktree, `<cache>` the main checkout's `outputs/table-completeness-corpus`, `<s>` a scratch folder.

```bash
git -C <main checkout> archive c674828 | tar -x -C <main>
PY=<wt>/venv/Scripts/python
PYTHONPATH=<main>/src $PY run_side.py --side main --expect-src <main>/src --fixtures-root <main> --edgar-cache <cache> --out-dir <s>/side-main --workers 7
PYTHONPATH=<wt>/src $PY run_side.py --side candidate --expect-src <wt>/src --fixtures-root <main> --edgar-cache <cache> --out-dir <s>/side-candidate --workers 7
PYTHONPATH=<main>/src $PY merges_main.py --expect-src <main>/src --fixtures-root <main> --edgar-cache <cache> --out <s>/merges.json.gz --workers 10
PYTHONPATH=<wt>/src $PY analyze_candidate.py --expect-src <wt>/src --fixtures-root <main> --edgar-cache <cache> --main-dir <s>/side-main --candidate-dir <s>/side-candidate --merges <s>/merges.json.gz --out-dir <s>/analysis --workers 10
$PY report.py --main-dir <s>/side-main --candidate-dir <s>/side-candidate --analysis-dir <s>/analysis --merges <s>/merges.json.gz --out-dir .
$PY shifted_tables.py --main-dir <s>/side-main --candidate-dir <s>/side-candidate --out shifted_tables.json
PYTHONPATH=<wt>/src $PY review_sample.py --fixtures-root <main> --edgar-cache <cache> --main-dir <s>/side-main --candidate-dir <s>/side-candidate --out review_sample.txt
PYTHONIOENCODING=utf-8 $PY round4_deltas.py --previous round4 --out round5_deltas.json
$PY overhead.py --main-src <main>/src --candidate-src <wt>/src --fixtures-root <main> --runs 9 --out overhead.json
PYTHONPATH=<main>/src $PY xlsx_detail.py dump --fixtures-root <main> --edgar-cache <cache> --out <s>/xd_main.json edgar:NTRA-10-K-2025-02-28.htm edgar:TSM-20-F-2025-04-17.htm
PYTHONPATH=<wt>/src $PY xlsx_detail.py dump --fixtures-root <main> --edgar-cache <cache> --out <s>/xd_cand.json edgar:NTRA-10-K-2025-02-28.htm edgar:TSM-20-F-2025-04-17.htm
$PY xlsx_detail.py compare <s>/xd_main.json <s>/xd_cand.json --out xlsx_detail.json
```

Measured wall times (32 logical CPUs): `run_side.py` 60 s per side (7 workers), `merges_main.py` 16 s,
`analyze_candidate.py` 27 s (10 workers), `report.py` about 10 s, `overhead.py` about 3 minutes (9 runs per side;
run it alone on a quiet machine), `review_sample.py` about 1 minute. Raw dumps (about 60 MB per side, gzip) stay
in the scratch folder; only aggregated results are kept here. `E:\RCQWealth` and the EDGAR cache are read only.

The candidate needs `TableAlignment.outcomes` (prototype T9 from `5215e3d` on). `analyze_candidate.py`
re-parses the candidate and checks that its outputs equal the candidate dump's, and that its summed coverage
equals production's (`ParseDiagnostics` for the candidate, `check_tables` on main's Markdown for main).

## Corpus

Each script that loads documents (`run_side.py`, `merges_main.py`, `analyze_candidate.py`, `xlsx_detail.py dump`,
`inspect_unit.py`, `review_sample.py`) takes `--corpus {phase-a,recent}`:

- `phase-a`, the default, reads the Phase A corpus from `--fixtures-root` and `--edgar-cache`, as above. Every
  result file is as before the switch, and none records a corpus.
- `recent` reads the recent filings corpus
  ([`../2026-10-06-recent-filings-corpus/corpus_recent.py`](../2026-10-06-recent-filings-corpus/corpus_recent.py))
  from `--recent-cache` (the main checkout's `outputs/recent-filings-corpus`), in place of `--fixtures-root` and
  `--edgar-cache`. Each document's SHA-256 is checked against that folder's `manifest.json`, whose own count is
  required. `_run.json`, the merges summary, `run_check.json` and `summary.json` record `"corpus": "recent"`.
  `report.py` takes `--corpus recent` as well, and stops if any input was made with another corpus.

Phase A content stays Phase A only. `shifted_tables.py`, `review_sample.py` and `overhead.py` refuse
`--corpus recent`. Under it, `report.py` writes as not applicable class 8's table list (with its fixed and remaining
counts; `class8.json` lists every candidate split table instead), check 1's class-1 tables and Phase A's false
positives (so `residual_genuine` lists every candidate `TableParser` value failure with output).
