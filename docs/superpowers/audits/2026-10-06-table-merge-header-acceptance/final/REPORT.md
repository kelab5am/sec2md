# Table merge and header rules: final acceptance run

Date: 2026-10-06. Plan Task 11.

- **Candidate:** `feat/table-merge-header` at `3cff45f` (worktree `.worktrees/tmh-proto`), the implementation branch after the plan's review fixes. Clean before and after the run.
- **Baseline:** `c674828`, from a fresh `git archive` tree. Its 10 fixture files are byte-identical to the worktree's.
- **Python:** the worktree venv (3.12.10), with `PYTHONIOENCODING=utf-8`. Every run's `sec2md.__file__` was checked.
- **Population:** the Phase A corpus, 109 documents. The hash check passes for 109/109 documents and 18/18 EDGAR files.
- **Modes:** normal and capture, with checks on.
- **Comparison:** each file in `final/` against the round-5 file of the same name in this folder.
- **Run hygiene:** every script exited 0. Nothing reached the network and nothing was installed. The 130 files already in this folder were SHA-256-checked before and after the run and are unchanged.

## Verdict

**The run reproduces round 5 apart from timings, and every criterion is met.** Since round 5, review fixes on the branch changed three pieces of rendering logic:
- R4's label column is never a currency-marker column for a marker other than `$`.
- R6 writes a header cell at most once per output column.
- The R6a header record counts each source node once.

None of the three changes any result on the corpus.

Two process points came up during the run. The user decided both on 2026-10-06:

1. **The review sample.** The plan's command for `review_sample.py` left out `--lines 9`, which round 5 used, so the first run cut each excerpt to the script's default of 7 lines. Rerun with `--lines 9`, `review_sample.txt` is byte-identical to round 5's. The rerun is the file in `final/`.
2. **Criterion 5's count.** Criterion 5 expected `display_page` changes in 9 snapshots. The data holds 8, in round 5 as well: `xlsx.json` and `xlsx_detail.json` are byte-identical to round 5's. Round 1's report listed the same 8 snapshot ordinals but its text said 9, and that figure was repeated afterwards. The spec (revision 17), the plan and the task briefs now say 8.

## Result files against round 5

- **Byte-identical:** `alignment.json`, `alignment_losses.json`, `check1.json`, `class8.json`, `findings.json`, `header_departures.json`, `limitations.json`, `modes.json`, `moved_rows.json`, `retention.json`, `sections.json`, `strict.json`, `summary.json`, `xlsx.json`, `shifted_tables.json`, `xlsx_detail.json` and `review_sample.txt` (the `--lines 9` run).
- **Identical apart from timing, path or gzip-header fields:**
  - `alignment_values.tsv.gz`: only the gzip header's mtime differs; the decompressed contents are identical.
  - `assignment.json`: `merges_summary.seconds` and the baseline's `sec2md_file` path.
  - `run_check.json`: `runs.*.wall_seconds` and the baseline's `sec2md_file` path.
  - `overhead.json`: the per-run timings and the baseline's `sec2md` path. Its keys and structure are identical.

## Criteria

| # | Criterion | Result | Verdict |
|---|---|---|---|
| 1 | Check 1 | `TableParser` value failures 305 → 13. All 294 class-1 tables fixed. Page furniture 573, unchanged. | Met, identical |
| 2 | Other findings | F7 gone. New findings only F9, F10 (15 tables) and F11 (4 tables). Tables with findings 937 → 633. | Met, identical |
| 3 | Strict | 0 new failures in either mode. `header_accounting_misses` 0. The same 14 trace failures on both sides. | Met, identical |
| 4 | Sections | 872/872 identical. | Met, identical |
| 5 | XLSX | 3,707 prepared tables identical, apart from `display_page` in 8 snapshots on 4 pages (the accepted S3 exception). | Met, identical (count corrected from 9) |
| 6 | Modes | 109/109 agree. | Met, identical |
| 7 | Alignment | 52,954 values evaluated, all aligned, 0 findings. 0 identities lost against `main`, 3,295 gained. | Met, identical |
| 8 | Assignment audit | 6,616/6,616. | Met, identical |
| 9 | Header retention | Values 54,986/54,990 (the 4 misses are MSFT 69). Header cells 19,594/19,594. Header-only columns 733/733. | Met, identical |
| 10 | Known shifted tables | 34/34 (`main` 1/34). | Met, identical |
| 11 | Class 8 | 75/80 fixed. TSM 79, 80, 82, 83 and 84 remain. | As expected, identical |
| 12 | Named limitations | 0 / 2 / 0 / 0. | Met, identical |
| 13 | Review sample | 42 tables, text identical to round 5, so its verdicts carry over: 35 correct, 6 with a note, 1 wrong (MSFT 69). | Met, identical |
| 14 | Overhead | 1.0904 (median of run totals over 9 runs, each in its own process). | Met (≤ 1.10) |
| 15 | Moved rows | 2,270 rows in 1,609 tables. 0 failures of the independent header-like check. 45 sparse-row-only rows. | Met, identical |

### Details

**1. Check 1.**
- The 13 remaining value-failure tables:
  - F1: CAT 61; KO 32, 43, 44, 50, 59 and 63; NVO 34.
  - F2: BABA 75.
  - F3: UNH 68.
  - F5: KO 112.
  - F8: JPM 367.
  - F9: TSM 344.
- BABA 75 keeps only its F2 false-positive tokens (000, 100, 400 and 500); token 31 is restored, as in rounds 2 to 5.
- One-row output: 2 → 1.

**2. Other findings.**
- New value tokens: TSM 344 (F9).
- New reported tokens (F10, 15 tables): nvda-2002-10k 19, 20, 22, 129, 130, 133, 144 and 146; TSM 244, 245, 247, 248, 253, 254 and 255.
- New check-2 findings (F11): BAC 260, 293, 336 and 338.
- F7 (CAT 143) has no candidate finding. The other 19 F tables are unchanged.

**3. Strict.**
- 0 new failures and 0 misses. `header_accounting_misses` is present on all 218 candidate runs.
- The 14 trace failures are the same multiset on both sides once element ids are removed: MSFT 425, NTRA 650, 2024 in four META and NVDA exhibits, and 2026 in the RDDT exhibit, each in both modes.

**4. Sections.**
- 872/872 comparisons are identical, and 110/110 for each document's own type.
- The 4 page differences are S3's display pages.

**5. XLSX.** `display_page` per page, `main` → candidate:

| Document | Page | `main` | Candidate | Snapshots |
|---|---|---|---|---|
| NTRA | 76 | 76 | 587 | 7 |
| TSM | 47 | 957 | 43 | 20, 21 |
| TSM | 146 | 4 | 8 | 131–133 |
| TSM | 160 | 1 | None | 159, 160 |

`only_display_page_differs` is true for both documents (49 and 172 tables).

**7. Alignment.**
- `identities_hold`, `production_match` and `deterministic_candidate_outputs` are all true.
- Candidate: 0 ambiguous-header values and 0 budget values.
- `main`: 49,659 values evaluated, 26,609 aligned.
- 99,084 values listed.

**8. Assignment audit.** 0 contradictions; replay ok for 3,707.

**9. Header retention.** The 4 value misses are MSFT 69, rows 5–6 × columns 10 and 16.

**11. Class 8.**
- TSM 79, 80, 82, 83 and 84 keep 20, 6, 4, 5 and 4 split cells, with their headers over the right values.
- Corpus split cells: 180 cells in 80 tables → 39 in 5.

**12. Named limitations.**
- Years rows read as data: 0.
- Year runs followed by no data row: 2 (CAT 27, KO 76).
- Year-run data rows: 0.
- T8 caption numbers: 0. The 21 identifier-caption tables are the same exhibit continuations.

**14. Overhead.**
- Total `Parser.get_pages(include_images=False)` time on the 7 fixtures, normal mode with checks on.
- Median of the run totals: `main` 4.5928 s, candidate 5.0079 s, ratio **1.0904**.
- Ratio of the total of per-fixture medians: 1.0881.
- Round 5 recorded 1.090, and 1.085 on a repeat run.

**15. Moved rows.**
- The 45 sparse-row-only rows are 43 NVDA section labels over a unit caption, plus NTRA 123 and TSM 216, as in the spec's accepted list.
- Departures: 219 rows, 177 of them data rows.

## Commands and durations

The commands are the plan's Task 11 Steps 1–3, plus `--lines 9` for `review_sample.py`.

| Command | Wall time |
|---|---|
| `run_side.py` main / candidate | 49 s / 52 s |
| `merges_main.py` | 18 s |
| `analyze_candidate.py` | 29 s |
| `report.py`, `shifted_tables.py` | 2 s, under 1 s |
| `review_sample.py` | 74 s |
| `xlsx_detail.py` dumps (main / candidate), compare | 25 s / 26 s, 1 s |
| `overhead.py --runs 9` (run alone) | 122 s |
