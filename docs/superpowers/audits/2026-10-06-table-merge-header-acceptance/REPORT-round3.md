# Table merge and header rules: acceptance run (prototype, round 3)

Date: 2026-10-06. Spec revision 12, "Acceptance criteria". Round 1: `REPORT.md` (`round1-` result files). Round 2: `REPORT-round2.md` (`round2-` result files). How to rerun: `README.md`.

- **Baseline:** `c674828`, as the same `git archive` tree as rounds 1 and 2. Its `src` and fixtures were checked file by file against the commit again (33 files, all identical). `sec2md.__file__` pointed at that tree in every run. Main's dumps are identical to round 2's on 109 of 109 documents.
- **Candidate:** `proto/table-merge-header` at `358f41e`, imported from the worktree's `src` with a clean worktree.
- **Population:** the Phase A corpus, 109 documents (7 fixtures, 32 RCQ primaries, 52 RCQ exhibits, 18 EDGAR documents). SHA-256 matches `results.json` for 109 of 109; the 18 EDGAR files match `edgar_manifest.json` (`run_check.json`).
- **Modes:** normal and capture, with table checks on.
- **What changed since round 2:** 122 tables in 37 documents. 117 have a second row kept in the header zone only by main's sparse-row fusion (S8); 5 by label-only rows (S7: nvda-2026-ex99-1 units 5, 6 and 11, nvda-2026-ex99-2 unit 12, CAT 139). Nothing else changed.

## Stop conditions reached

Every measurement was completed. No rule was changed to work around any of them.

| # | Condition | What happens | Where |
|---|---|---|---|
| S9 | NOT MET for a spec-rule reason (the sparse-row fusion), new | The fusion counts n over every column with origin text, so `%` and `$` marker columns raise n where `main`, which counted its merged columns, did not. AMZN 10-Q 2025-10-31 table 21: the body row "Weighted-average remaining lease term – operating leases \| 10.6 years \| 10.0 years" is fused into the header line ("December 31, 2024 — 10.6 years"); `main` kept it in the body. It is the shape of the S1 control "Finance leases \| 15.1 years", which stays body only because its table has no marker column. TSM 216 fuses list item (b) into the header line with item (a). The mirror case, JPM 207, keeps a heading row that `main` fused out of the header line. | Criteria 13, 15 |
| S5 | Documented residual (Deferred) | MSFT 69, unchanged. | Criteria 9, 13 |
| S3 | XLSX workbook output changes (unchanged) | 9 snapshots in 2 documents differ only in `display_page`. Detail byte-identical to rounds 1 and 2. | Criterion 5 |

Round 2's S7 and S8 are resolved (details below). F11 is now in the spec, so criterion 2 is met.

## Summary

| # | Criterion | Verdict | Key numbers (round 2 → round 3) |
|---|---|---|---|
| 1 | Check 1 | MET | `TableParser` value failures 305 → 13, unchanged from round 2: the 12 Phase A false-positive tables and TSM 344 (F9). 294 class-1 tables fixed. Page furniture (573) unchanged. |
| 2 | Other findings | MET (round 2: NEEDS REVIEW) | Identical to round 2: new value tokens TSM 344 (F9); new reported tokens 15 tables (F10); new check-2 BAC 260, 293, 336, 338 (F11, now documented). F7 gone. Tables with findings 937 → 633. |
| 3 | Strict | MET | 0 new failures; misses 0; the same 14 pre-existing trace failures on both sides. |
| 4 | Sections | MET | 872 of 872 identical; 110 of 110 own-type. |
| 5 | XLSX | NEEDS REVIEW (S3) | 3,707 prepared tables identical apart from `display_page` in 9 snapshots. |
| 6 | Modes | MET | 109 of 109 agree. |
| 7 | Alignment | MET | Candidate evaluated 52,656 → 52,937, all aligned; misaligned 0; ambiguous headers 0; identities lost 0; gained 3,351 → 3,299; identities hold. |
| 8 | Assignment audit | MET | 6,616 of 6,616; 0 contradictions. |
| 9 | Header retention | MET (round 2: NOT MET) | Values 54,811/54,815 → 54,987/54,991; the 4 misses are MSFT 69, the documented residual. Header cells 19,077 → 19,590, all represented. Header-only columns 703 → 733, all rendered. |
| 10 | Known shifted tables | MET | 34/34 (main 1/34). |
| 11 | Class 8 | NEEDS REVIEW (allowed) | 75 of 80 fixed; the same 5 TSM tables remain. |
| 12 | Named limitations | MET | Years rows read as data 0; year runs followed by no data row 2 (CAT 27, KO 76); year-run data rows 0; T8 caption numbers 0. |
| 13 | Review sample | NOT MET (S5, S9) | 42 tables: 33 correct, 5 with a note, 4 wrong (round 2: 30, 7, 5). 4 of round 2's 5 wrong tables are now right; the 3 new wrong tables are S9. |
| 14 | Overhead | MET | 1.088 → 1.081 (main 4.3824 s, candidate 4.739 s). |
| 15 | Moved rows | NOT MET (S9) (round 2: MET) | 2,201 → 2,271 rows; 1,558 → 1,610 tables. The independent check finds 0 failures, but the content review finds a body row: AMZN 10-Q table 21. |
| — | Fixture body-row guard | MET (suite) | 147 → 172 listed header-zone moves account for every lost count. |

## 1. Check 1

`check1.json` is identical to round 2's.

| | Main | Candidate |
|---|---|---|
| `TableParser` output | 305 (294 class 1 + 11 Phase A false positives) | 13 |
| One-row output | 2 (G3; G5 CAT 7) | 1 (G3) |
| No output (G4 page furniture) | 573 | 573: same tables, same tokens |

- 293 of the 294 class-1 tables have no value failure. BABA 75 keeps only its F2 tokens.
- TSM 344, token `1250.0`, is F9: the rendering `US$ 1,250.0` is correct.

**Verdict: MET.**

## 2. Other findings

`findings.json` is identical to round 2's.

- Tables with findings 937 → 633. F7 (CAT 143) disappears; F2 BABA 75 loses token `31`; the other F tables are identical.
- New check-1 value tokens: TSM 344 only (F9).
- New reported tokens: 15 tables (F10): nvda-2002-10k tables 19, 20, 22, 129, 130, 133, 144, 146 (token `2`) and TSM tables 244, 245, 247, 248, 253, 254, 255 (token `3`).
- New check-2 findings: BAC 260, 293, 336, 338 (F11). The renderings are correct.

Every new finding is now a documented check-side false positive (F9, F10, F11).

**Verdict: MET.**

## 3. Strict

New strict failures: 0 in either mode. The 14 pre-existing trace failures are identical on both sides. `header_accounting_misses`: 0 everywhere.

**Verdict: MET.**

## 4. Sections

872 of 872 comparisons identical; 110 of 110 for each primary's own type. The 4 `pages_differences` are S3's display pages.

**Verdict: MET.**

## 5. XLSX

3,707 snapshots compared. 9 snapshots in 2 documents (NTRA, TSM) differ, only in `source.display_page`. `xlsx_detail.json` is byte-identical to rounds 1 and 2. `Parser._extract_page_number_from_content` is unchanged, pending the user's decision.

**Verdict: NEEDS REVIEW (S3).**

## 6. Modes

109 of 109 documents agree across modes on findings, alignment findings and coverage, strict results, sections and outputs. Main agrees too.

**Verdict: MET.**

## 7. Alignment

The re-parse reproduced the candidate's outputs, summed coverage equals production's, and the identities hold per document and in total.

| Key | Main | Candidate |
|---|---|---|
| tables_total / evaluated | 5,332 / 3,193 [round 2: 3,183] | same |
| no_output / no_separator / unreliable / no_header / no_data | 691 / 934 / 0 / 183 [193] / 331 | same |
| rows_data / below_repeated / unpaired / paired | 28,298 / 1,613 / 6,951 / 19,734 | 28,298 / 1,613 / 6,908 / 19,777 |
| values_total | 65,986 | 66,065 |
| nil / no_disc / missing / amb_position | 5,885 / 2,075 / 0 / 5,121 | 5,885 / 2,106 / 0 / 5,137 |
| amb_header / budget | 3,267 / 0 | 0 / 0 |
| evaluated / aligned / misaligned | 49,638 / 26,584 / 23,054 | 52,937 / 52,937 / 0 [52,656 / 52,656 / 0] |

Main's figures moved too, because the checker shares R0: the stacked-title and fused-heading tables have header zones again.

- Findings: 0.
- Per-value identities: 99,097 listed; 49,638 evaluated on main and 52,937 on the candidate.
- 0 identities are evaluated on main but not on the candidate.
- 3,299 are gained: 3,267 ambiguous-header values and 32 unpaired-row values became aligned.

**Verdict: MET.**

## 8. Assignment audit

6,616 of 6,616 steps pass, with 0 contradictions (unchanged).

**Verdict: MET.**

## 9. Header retention

- Values: 54,991 checked; 54,987 exact. The 4 misses are MSFT 69 (rows 5 and 6, columns 10 and 16: headers 2025 and 2024 over empty paths). Revision 12 names it as the one documented residual.
- Header cells: 19,590 of 19,590 represented (round 2: 19,077 of 19,077).
- Header-only columns: 733 of 733 rendered (round 2: 703).
- Word-only paths: 7,328 values; literal ` — ` labels: 16 values; 0 mismatches in either.

**Verdict: MET.**

## 10. Known shifted tables

`shifted_tables.json` is identical to round 2's: BABA 24 4/4, TSM 79 3/3, TSM 312 4/4, JPM 482 6/6, MSFT 24 3/3, MSFT 65 6/6, RDDT 10-Q 2024 Q2 t17 8/8. Main: 1/34.

**Verdict: MET.**

## 11. Class 8

75 of 80 tables fixed. The same 5 TSM tables remain (79, 80, 82, 83, 84; 39 cells, mixed `)`, `%` and `)%` marker columns), with headers over the right values.

**Verdict: NEEDS REVIEW** (allowed by the spec's residual sentence).

## 12. Named limitations

`limitations.json` is identical to round 2's.

- Years rows read as data: 0.
- Year runs followed by no data row: 2, CAT 27 row 17 and KO 76 row 4. Both are trailing body rows, so rendering is unchanged.
- Year runs that are data rows: 0.
- T8 caption numbers: 0 (the same 21 exhibit continuations).

**Verdict: MET.**

## 13. Review sample

`review_sample.txt`, 42 tables. Round 3 leaves out 8 tables that are unchanged since round 2, where they were correct, and whose classes stay covered: TSLA 38, BAC 88, RDDT 10-Q t17, MSFT 65, CAT 34, KO 110, BAC 46 and JPM 543. It adds 8 round-3 cases. Tables 1–29 render exactly as in round 2, so they keep round 2's verdicts.

| # | Table | Verdict |
|---|---|---|
| 1 | NVDA 10-Q 2026 Q1 t18 | Correct. |
| 2 | CRM 26 | Correct. |
| 3 | JPM 109 | Correct. |
| 4 | TSM 248 | Correct. |
| 5 | RDDT 10-Q 2024 Q2 t52 | Correct. |
| 6 | MSFT 24 | Correct. |
| 7 | nvda-2002 138 | Correct. |
| 8 | BABA 24 | Correct. |
| 9 | TSM 79 | Headers correct; note: class-8 split remains. |
| 10 | JPM 482 | Correct; note: header-only column (R7). |
| 11 | TSM 344 | Correct (check-1 report is F9). |
| 12 | aapl 18 | Correct. |
| 13 | META 10-Q 2024 Q1 t4 | Correct. |
| 14 | nvda-2026-10k 17 | Correct. |
| 15 | nvda-2026-10k 36 | Correct. |
| 16 | GOOGL 89 | Correct. |
| 17 | aapl 64 | Note: no data row, so the headings land in the body (T3). |
| 18 | CAT 7 | Correct. |
| 19 | BABA 69 | Correct. |
| 20 | MSFT 43 | Correct. |
| 21 | nvda-2002 157 | Correct. |
| 22 | NTRA 141 | Correct. |
| 23 | BAC 336 | Correct; its check-2 report is F11. |
| 24 | aapl 8 | Correct. |
| 25 | META 10-K 2025 t44 | Correct: the lease-term title and "Finance leases \| 15.1 years" stay in the body. |
| 26 | TSM 136 | Correct. |
| 27 | CAT 143 | Correct. |
| 28 | MSFT 69 | Wrong (S5, documented residual). |
| 29 | META 10-Q 2026 Q1 t39 | Correct. |
| 30 | nvda-2026-ex99-1 t5 | Correct (round 2: wrong, S7): `NVIDIA CORPORATION — CONDENSED CONSOLIDATED BALANCE SHEETS — (In millions) — (Unaudited) — July 26, — 2026` over 22,443; ASSETS and Current assets: stay in the body. |
| 31 | nvda-2026-ex99-1 t11 | Correct (round 2: wrong, S7). |
| 32 | META 10-K 2025 t37 | Correct (round 2: worse than main, S8): the headings are in the header line, as in main, and the measurement caption repeats over each level. |
| 33 | TSLA 40 | Correct (round 2: worse than main, S8). |
| 34 | nvda-2026-10k 38 | Correct; note: "Inventories: \| (In millions)" now joins the header line (`Jan 25, 2026 — (In millions)`). Main kept it in its body; see S9. |
| 35 | nvda-2026-ex99-1 t6 | Correct (S7). |
| 36 | CAT 139 | Correct values (S7); note: the partial title spans repeat only over the columns they span in the source. |
| 37 | aapl 61 | Correct (S8): exhibit headings in the header line, as in main. |
| 38 | TSM 89 | Correct (S8): the column headings and the `(in NT$ millions)` caption are in the header line; main left the caption in its body. |
| 39 | NTRA 123 | Correct, and better than main, whose header line held zero-width cells. Main kept "Trade Date \| Natera, Inc. \| …" in its body. |
| 40 | AMZN 10-Q 2025-10-31 t21 | Wrong (S9): the operating-lease row's "10.6 years" and "10.0 years" are in the header line. |
| 41 | TSM 216 | Worse than main (S9): list item (b) is fused with item (a) into the header line. No value lost. |
| 42 | JPM 207 | Worse than main (S9 mirror): "Average amount (in millions) \| December 31, 2024 \| …" stays in the body, under "Three months ended" alone. |

**Verdict: NOT MET.** 33 correct, 5 with a note, 4 wrong: MSFT 69 (S5) and the three S9 tables.

## 14. Overhead

Median of 9 runs per side, one process per run, rounds alternating which side runs first; `get_pages` time only.

| Fixture | Main (s) | Candidate (s) | Ratio | Round 2 |
|---|---|---|---|---|
| aapl-2023-10k | 0.7543 | 0.8222 | 1.090 | 1.102 |
| nvda-2002-10k | 1.5858 | 1.6451 | 1.037 | 1.061 |
| nvda-2026-08-26-8k | 0.0165 | 0.0179 | 1.085 | 1.068 |
| nvda-2026-10k | 0.9144 | 1.0496 | 1.148 | 1.199 |
| nvda-2026-ex99-1 | 0.2110 | 0.2804 | 1.329 | 1.082 |
| nvda-2026-ex99-2 | 0.2114 | 0.1687 | 0.798 | 0.806 |
| nvda-2026-q2-10q | 0.6890 | 0.7551 | 1.096 | 1.075 |
| **Total** | **4.3824** | **4.739** | **1.081** | 1.088 |

- The median of run totals gives 1.082. No run is more than 15% from its fixture's median.
- Untimed construction: 1.3026 s on main, 1.2964 s on the candidate.
- **Per-fixture outlier: ex99-1, 1.329.** Measured in one process, round 2's HEAD takes 0.223 s on it and round 3's 0.243 s (+9%). The three regained header zones add 8 ms of alignment work; the longer header lines add the rest. The harness's per-fixture ratios also carry order effects, as ex99-2's 0.80 shows. The contract is on the total.

**Verdict: MET.**

## 15. Moved rows

`moved_rows.json`; deltas in `round3_deltas.json`.

- 2,271 rows in 1,610 tables (fixtures: 165 rows in 118 tables); 39 are the first row of their header zone.
- **Independent rule check** (revision 12, in `analyze_candidate.py`, which never imports `table_roles`): 0 failures. The check now covers label-only rows, the sparse-row fusion for the second row, the zone starting at the first row with origin text, and the rule that trailing label-only rows leave the zone. Reasons: empty label cell 1,997; year run 227; unit-text label 172; sparse-row fusion 115; period-text label 44; label-only 37; year-like label 3.
- **New since round 2: 70 rows in 53 tables; 0 gone.**
  - 24 come from label-only continuation: the S7 tables, CAT 139, and the rows below them. All are titles, captions, period and date rows.
  - 46 rows in 46 tables are in the zone only through the sparse-row fusion, and `main` kept them in its body:
    - 43 NVDA rows such as "Inventories: \| (In millions)" (5 in nvda-2026-10k, 3 in nvda-2026-q2-10q, 35 in RCQ NVDA filings). They render as `Inventories: | Jan 25, 2026 — (In millions) | …`, a section label over the labels and the unit over each value column.
    - NTRA 123: better than main.
    - **AMZN 10-Q table 21: a body row with values and units moved into the header line (S9).**
    - TSM 216: list item (b) moved into the header line (S9).
- **Signals.** Values with units, 6 rows: AMZN 21, plus round 2's 5 column headings ("Less than 12 months \| 12 months or more"). Links, 14 rows: the NVDA "Part I" headings, as round 2. Words in value cells: 501 rows in 384 tables (round 2: 490 in 375). The 11 added rows are among the 70 reviewed one by one above.

**Verdict: NOT MET (S9).** No row fails the rule as written. The content review finds one body row (AMZN 10-Q t21) and one list item (TSM 216) that the rule moves into the header line.

## Rows leaving main's header line (S7, S8)

`header_departures.json`, `round3_deltas.json`.

- 221 rows in 215 tables leave main's header line (round 2: 294 in 282). 178 of them are data rows main had swallowed, the intended class-5 fix (unchanged).
- 43 non-data rows in 42 tables (round 2: 116 in 109):
  - 24 label-only rows (round 2: 34). They are a first title or caption directly above the data, such as MSFT's "(In millions)", which the trailing label-only rule keeps in the body; aapl 18 "Gross margin percentage:"; ex99-1 t7 "Cash flows from financing activities:".
  - 19 rows with value-column text, in 18 tables (round 2: 82 rows in 80 tables).
- **S8: of round 2's 82 rows, 62 (in 62 tables) are header rows again.** The 19 rows still leaving main's header line, in 18 tables:
  - 16 rows in 15 tables have no data row, so R5's rule applies: the first row alone is the header and row 1 is not fused. These are signature blocks (META 69 and 71, CAT 148, GOOGL 89 and 90, NFLX 80, NVO 93), cover-page tables (MSFT 4, NVO 3, SPCX 7, MU 4) and text tables (JPM 221, 326, 328, UNH 17).
  - 2 tables have a data row as their first row, so the zone is empty: CAT 4 and UNH 4, cover pages.
  - 1 is JPM 207, where two `%` marker columns raise n to 10 (S9's mirror).
  - UNH 20 row 8 is no longer listed: it repeats the table's headings under the first block, and its text is now in the header line through row 2.
- **S7:** all 4 fixture tables and CAT 139 have their dates and captions in the header line. The 6 lease-term tables (META 45 and 44, BAC 233, CRM 58, GOOGL 52, TSLA 53) keep "Finance leases \| 13.7 years" in the body, as intended.
- Zone cuts: 88. None is made by a label-only row, and none is inconsistent with the candidate's zone.

## Fixture body-row guard

147 → 172 listed moves, generated so that the header-zone positions account for every lost count exactly. The 25 added:

- 17 S7 rows: ex99-1 14 and ex99-2 3 (titles, captions, period and date rows).
- 8 S8 rows that `main` did not fuse: nvda-2026-10k source tables 37–40 and 56, nvda-2026-q2-10q 21–23 ("Inventories: \| (In millions)" and the like).

aapl, nvda-2026-08-26-8k: 0 moves.

## S9: the sparse-row fusion counts marker columns

- **Rule as written.** "Let n be the number of columns with origin text. The first row must have no origin text in at least max(2, n // 2) columns, and the second row must have origin text in at least max(2, n // 2) columns."
- **Minimal reproduction.**

  ```html
  <table>
  <tr><td></td><td colspan="2">December 31, 2024</td><td colspan="2">September 30, 2025</td></tr>
  <tr><td>Remaining lease term, operating leases</td><td colspan="2">10.6 years</td><td colspan="2">10.0 years</td></tr>
  <tr><td>Remaining lease term, finance leases</td><td colspan="2">11.9 years</td><td colspan="2">12.1 years</td></tr>
  <tr><td>Discount rate, operating leases</td><td>3.5</td><td>%</td><td>3.6</td><td>%</td></tr>
  </table>
  ```

  - `main`: `|  | December 31, 2024 | September 30, 2025 |`, with the 10.6-years row in the body.
  - Candidate: `| Remaining lease term, operating leases | December 31, 2024 — 10.6 years | September 30, 2025 — 10.0 years |`.
  - The two `%` columns hold origin text, so n = 5 and the threshold is 2. The date row has no origin text in 3 columns; the lease row has origin text in 3. `main` measured its 3 merged columns (threshold 2; the date row has 1 empty column) and did not fuse.
- **Corpus.** 117 rows are in the zone only through the fusion. `main` fused 71 of them too, and kept 46 in its body (Moved rows above).
- **Simulated alternatives** (`s8_variants.py`; not implemented, because the spec's rule is explicit):

  | Alternative | Corpus effect |
  |---|---|
  | **P1.** n and both rows' counts leave out marker-only columns: columns whose every origin text is a currency marker, `%`, `)`, `)%` or `(`. `main` merges these before it counts. | Exactly 2 rows change: AMZN 10-Q t21 goes back to the body, and JPM 207's heading row joins the header line. Both now match `main`. |
  | **P2.** No fusion when a value cell of the second row is a number with a unit word (`10.6 years`). | AMZN 21 only. |

  Neither changes the 43 NVDA rows, NTRA 123 or TSM 216.

## Code changes (round 3)

The fixes were written test first and folded into their task commits. The tree is identical before and after the rebase, with no conflicts.

Final SHAs: T1 `ed08a86`, T2 `34054f3`, T3 `c7b906d`, T4 `4323687`, T5 `8ec495d`, T6 `a6eca60`, T7 `a332714`, T8 `b365729`, T9 `dc66b85`, T10 `358f41e`. Full suite at `358f41e`: 1541 passed, 14 deselected; ruff clean. Each commit's failure list is identical to round 2's.

| Commit | Change |
|---|---|
| T1 | Label-only rows continue the zone. Main's sparse-row fusion keeps the second row: `fuses_like_main`, with n counted over the columns holding origin text, so the placed and cleaned grids agree. New `is_label_only`. |
| T5 | Rendering cases: stacked titles, the exhibit title, META t37 and TSLA 40 shapes, controls. |
| T9 | Link-aware equality with the same base URL: `check_tables(..., base_url=)` through `align_table` and `source_grid` to `extract_cell_text`, with the Parser passing its `source_url`. Coverage pins for ex99-1 and ex99-2. |
| T10 | 172 listed moves; release notes. |

Tooling: `analyze_candidate.py` implements revision 12's rule independently. `report.py` gains counts. `review_sample.py` gains the round-3 sample. New `round3_deltas.py`.
