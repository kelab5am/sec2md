# Table merge and header rules: acceptance run (prototype, round 2)

Date: 2026-10-06. Spec revision 11, "Acceptance criteria", including the new "Moved rows" criterion and the widened body-row guard. Round 1: `REPORT.md` (its result files now carry a `round1-` prefix). How to rerun: `README.md`.

- **Baseline:** `c674828`, as a `git archive` tree. Its `src` and fixtures were checked file by file against the commit (33 files, all identical). `sec2md.__file__` pointed at that tree in every run.
- **Candidate:** `proto/table-merge-header` at `2cb0f0e`, imported from the worktree's `src` with a clean worktree. The dumps and analysis of `2cb0f0e` are identical to those of `6a1cd75` (0 of 109 documents differ), and `summary.json` is unchanged.
- **Population:** the Phase A corpus, 109 documents: 7 fixtures, 32 RCQ primaries, 52 RCQ exhibits and 18 EDGAR documents, loaded by `corpus_phase_a.documents()`.
  - SHA-256 matches `results.json` for 109 of 109 documents.
  - The 18 EDGAR files match `edgar_manifest.json` (`run_check.json`).
- **Modes:** normal and capture, with table checks on.

## Stop conditions reached

Every measurement was completed. No rule was changed to work around any of them.

| # | Condition | What happens | Where |
|---|---|---|---|
| S7 | NOT MET for a spec-rule reason (header-like rule) | A second title row in the label column ends the header zone; the first title is then a trailing label-only row, so the zone is empty. The period rows render in the body under an empty header line. 4 tables, all fixtures: nvda-2026-ex99-1 units 5, 6 and 11, nvda-2026-ex99-2 unit 12. Round 1 had their dates in the header line; main had them in the body. | Criterion 13; fixture coverage |
| S8 | NOT MET for a spec-rule reason (header-like rule) | A column-heading second row ends the zone, and the spec says main renders that row in the body too. For 82 rows in 80 tables main fused it into its header line, so its column names leave the header line. Breakdown: 23 exhibit-index heading rows (including fixtures aapl-2023-10k tables 61–63, nvda-2026-10k table 61 and nvda-2026-q2-10q table 51), 14 fair-value heading rows with dates, 18 other heading rows with dates and 27 other heading rows. | Criterion 13; "Rows leaving main's header line" |
| F11 | Not covered by the spec: a check-side false positive | Check 2 reads a unit-captioned years row ("(Dollars in millions) \| 2024 \| 2023") as a data row. The candidate writes the row into the header line, so check 2 pairs it with a later stacked block's years row and flags every row below. 4 BAC tables: 260, 293, 336, 338. The renderings are correct. | Criterion 2 |
| S5 | NOT MET for a spec-rule reason (R2), residual | MSFT 69: each year sits over the last column of the value cell to its left, so R2 keeps it apart and it heads the next period's value. | Criteria 9, 13 |
| S3 | XLSX workbook output changes (unchanged) | 9 snapshots in 2 documents differ only in `display_page`, which the contents sheet prints. Detail byte-identical to round 1. | Criterion 5 |

Round 1's S1, S2 and S4 are resolved; round 1's S6 is now the spec's F9.

## Summary

| # | Criterion | Verdict | Key numbers (round 1 → round 2) |
|---|---|---|---|
| 1 | Check 1 | MET | 294 class-1 tables fixed. `TableParser` value failures 305 → 13 (round 1: 15): the 12 Phase A false-positive tables and TSM 344 (F9). Page furniture (573) unchanged. |
| 2 | Other findings | NEEDS REVIEW (F11) | F7 gone; F2 BABA 75 improved. New value tokens: TSM 344 (F9). New reported tokens: 15 tables (F10; round 1: 18). New check-2: 4 BAC tables (F11; round 1: 0). Tables with findings 937 → 633. |
| 3 | Strict | MET | 0 new failures; misses 0; the same 14 pre-existing trace failures on both sides. |
| 4 | Sections | MET | 872 of 872 identical; 110 of 110 own-type. |
| 5 | XLSX | NEEDS REVIEW (S3) | 3,707 prepared tables identical apart from `display_page` in 9 snapshots, as round 1. |
| 6 | Modes | MET | 109 of 109 agree. |
| 7 | Alignment | MET | Misaligned 646 → 0; ambiguous headers 170 → 0; identities lost 170 → 0; 3,351 gained; identities hold. |
| 8 | Assignment audit | MET | 6,427 → 6,616 of 6,616; 0 contradictions. |
| 9 | Header retention | NOT MET (S5) | Values 52,817/54,308 → 54,811/54,815 (4 misses: MSFT 69). Header cells 18,958/19,213 → 19,077/19,077. Header-only columns 703/703. |
| 10 | Known shifted tables | MET | 29/34 → 34/34; main 1/34. |
| 11 | Class 8 | NEEDS REVIEW | 75 of 80 fixed; the same 5 TSM tables remain. |
| 12 | Named limitations | MET | Years rows read as data 106 → 0. Year runs followed by no data row: 2 (CAT 27, KO 76), rendering unchanged. Year runs that are data rows: 0. T8 caption numbers: 0. |
| 13 | Review sample | NOT MET (S5, S7, S8) | 42 tables: 30 correct, 7 correct with a note, 5 wrong; 11 of round 1's 12 wrong tables now right. |
| 14 | Overhead | MET | 1.088 (main 4.2416 s, candidate 4.6149 s; round 1: 1.139). |
| 15 | Moved rows (new) | MET | 2,201 rows in 1,558 tables (fixtures 140 rows in 106 tables); independent header-like check: 0 failures; content review found no body row. |
| — | Fixture body-row guard (widened) | MET (suite) | 2,492 rows main rendered as body rows; 147 listed header-zone moves account for every lost count; aapl 0 (S1 fixed). |

## 1. Check 1

`check1.json`, normal mode.

| | Main | Candidate |
|---|---|---|
| `TableParser` output | 305 (294 class 1 + 11 Phase A false positives) | 13 |
| One-row output | 2 (G3; G5 CAT 7) | 1 (G3) |
| No output (G4 page furniture) | 573 | 573: same tables, same tokens |

- **The 294 class-1 tables.** 293 have no value failure. BABA 75 keeps only the F2 tokens `000`, `100`, `400` and `500`; its token `31` survives.
- **The candidate's 13.** The 12 Phase A false-positive tables (all unchanged except BABA 75), plus TSM 344.
- **TSM 344, token `1250.0` (F9).** The rendering `US$ 1,250.0` is correct. Check 1 will not let a `value_numeric` source token claim a text cell. Phase B fixes the compatibility table.
- KO 110 and KO 111 (round 1's S1 failures) have no new token.

**Verdict: MET.**

## 2. Other findings

`findings.json`.

- **Totals.** Tables with findings 937 → 633. Removed: 440 value tokens, 54 reported tokens, 1 check-2 row.
- **F tables.** F7 (CAT 143) disappears; F2 BABA 75 lost token `31`; the other 19 are identical.
- **New check-1 value tokens.** TSM 344 only (F9).
- **New reported tokens: 15 tables (F10).**
  - nvda-2002-10k tables 19, 20, 22, 129, 130, 133, 144 and 146 (token `2`).
  - TSM tables 244, 245, 247, 248, 253, 254 and 255 (token `3`).
  - These are identifier references that R5 correctly moves into the header line.
  - Round 1's S1 tables (KO 110, KO 111, META 10-Q 2026 Q1 table 39) are gone; META table 39 keeps both links.
- **New check-2 findings: 4 tables (F11),** BAC 260, 293, 336 and 338 (5, 9, 11 and 17 rows). Mechanism:
  - Check 2's source row 1 is "(Dollars in millions) | 2024 | 2023 [| 2022 …]". The snapshot header count is 0, and Phase A's period-row test needs every cell to be period text or a bare year, so the years make it a data row.
  - Main writes the row as body line 1; the candidate writes it into the header line.
  - Check 2 then pairs it with a later stacked block's years row (BAC 293: body line 12; BAC 336: lines 13 and 27), and every following row "appears before an earlier source row".
  - The renderings are correct. Phase B consequence: check 2 should take its header rows from R0.
- **Round 1's BAC 320/322 and JPM 606.** These changes came from rowspans over a row of hidden cells; they were fixed before this report (see Code changes).

**Verdict: NEEDS REVIEW.** The spec names F9 and F10 but not F11.

## 3. Strict

New strict failures: 0 in either mode. The 14 pre-existing trace failures are identical on both sides. `header_accounting_misses`: 0 everywhere.

**Verdict: MET.**

## 4. Sections

872 of 872 comparisons identical; 110 of 110 for each primary's own type. The 4 `pages_differences` are S3's display pages (NTRA and TSM, each mode). Page numbers and section boundaries are identical.

**Verdict: MET.**

## 5. XLSX

- 3,707 snapshots compared.
- 9 snapshots in 2 documents differ, and only in `source.display_page`.
- `xlsx_detail.json` is byte-identical to `round1-xlsx_detail.json` (NTRA page 76; TSM pages 47, 146, 160).
- `_extract_page_number_from_content` is left unchanged pending the user's decision.

**Verdict: NEEDS REVIEW (S3).**

## 6. Modes

109 of 109 documents agree across modes on findings, alignment findings and coverage, strict results, sections and outputs. Main also agrees on 109 of 109.

**Verdict: MET.**

## 7. Alignment

Method as round 1. The re-parse reproduced the candidate's outputs, summed coverage equals production's, and the identities hold per document and in total.

| Key | Main | Candidate |
|---|---|---|
| tables_total / evaluated | 5,332 / 3,183 [round 1: 3,155] | same |
| no_output / no_separator / unreliable / no_header / no_data | 691 / 934 / 0 / 193 [222] / 331 [330] | same |
| rows_data / below_repeated / unpaired / paired | 28,212 / 1,613 / 6,942 / 19,657 | 28,212 / 1,613 / 6,899 / 19,700 |
| values_total | 65,802 | 65,881 |
| nil / no_disc / missing / amb_position | 5,881 / 2,335 / 0 / 4,962 | 5,881 / 2,366 / 0 / 4,978 |
| amb_header / budget | 3,319 / 0 | 0 [170] / 0 |
| evaluated / aligned / misaligned | 49,305 / 26,426 / 22,879 | 52,656 / 52,656 / 0 [51,508 / 50,862 / 646] |

Main's figures moved too, because the checker shares R0.

- **Findings:** 0.
- **Per-value identities:** 99,097 listed; 49,305 evaluated on main and 52,656 on the candidate.
- 0 identities are evaluated on main but not on the candidate (round 1: 170).
- 3,351 are gained: 3,319 ambiguous-header values and 32 unpaired-row values became aligned.

**Verdict: MET.**

## 8. Assignment audit

6,616 of 6,616 steps pass (round 1: 6,427), with 0 contradictions. BAC 336 renders "Compensation and benefits (3) | 40,182 | 38,330 | 36,447 | 6,422 | …" under its years.

**Verdict: MET.**

## 9. Header retention

- **Values:** 54,815 checked; 54,811 exact. The 4 misses are MSFT 69 (columns 10 and 16: headers 2025 and 2024 over empty paths, S5).
- **Header cells:** 19,077 of 19,077 represented.
- **Header-only columns:** 703 of 703 rendered.
- **Required cases:** word-only paths 7,539 values, literal ` — ` labels 16 values; 0 mismatches in either.

**Verdict: NOT MET (S5 only).**

## 10. Known shifted tables

| Table | Candidate | Main |
|---|---|---|
| BABA 24 | 4/4 | 0/4 |
| TSM 79 | 3/3 | 0/3 |
| TSM 312 | 4/4 | 0/4 |
| JPM 482 | 6/6 | 0/6 |
| MSFT 24 | 3/3 | 1/3 |
| MSFT 65 | 6/6 | 0/6 |
| RDDT 10-Q 2024 Q2 t17 | 8/8 (round 1: 3/8) | 0/8 |

**Verdict: MET.**

## 11. Class 8

75 of 80 tables fixed. The same 5 TSM tables remain (79, 80, 82, 83, 84; 39 cells, mixed `)`, `%` and `)%` marker columns), with headers over the right values.

**Verdict: NEEDS REVIEW** (allowed by the spec's residual sentence).

## 12. Named limitations

- **Years rows read as data:** 106 → 0. TSM 136 has its years in the header line again.
- **Year runs followed by no data row: 2.** CAT 27 row 17 ("Year that the cost trend rate reaches ultimate rate | 2030 | 2030 | 2030") and KO 76 row 4 ("… | 2029 | 2029"). Both are trailing body rows, so rendering is unchanged, and years are never alignment values.
- **Year runs that are data rows:** 0.
- **T8 caption numbers:** 0 (the same 21 exhibit continuations as round 1).

**Verdict: MET.**

## 13. Review sample

`review_sample.txt` (42 tables).

| # | Table | Verdict |
|---|---|---|
| 1 | NVDA 10-Q 2026 Q1 t18 | Correct (round 1: wrong, S2). |
| 2 | CRM 26 | Correct (round 1: caption misplaced, S2). |
| 3 | JPM 109 | Correct. |
| 4 | TSLA 38 | Correct. |
| 5 | BAC 88 | Values right; note: a header-only column where the title span starts inside the label span (R2, R7). |
| 6 | TSM 248 | Correct. |
| 7 | RDDT 10-Q 2024 Q2 t52 | Correct. |
| 8 | MSFT 24 | Correct. |
| 9 | nvda-2002 138 | Correct. |
| 10 | BABA 24 | Correct. |
| 11 | TSM 79 | Headers correct; note: class-8 split remains. |
| 12 | JPM 482 | Correct; note: header-only column (R7). |
| 13 | RDDT t17 | Correct (round 1: wrong, S2). |
| 14 | MSFT 65 | Correct. |
| 15 | TSM 344 | Correct (check-1 report is F9). |
| 16 | aapl 18 | Correct. |
| 17 | META 10-Q 2024 Q1 t4 | Correct. |
| 18 | nvda-2026-10k 17 | Correct. |
| 19 | nvda-2026-10k 36 | Correct. |
| 20 | GOOGL 89 | Correct. |
| 21 | aapl 64 | Note: no data row, so the headings land in the body (T3). |
| 22 | CAT 7 | Correct. |
| 23 | BABA 69 | Correct. |
| 24 | MSFT 43 | Correct. |
| 25 | nvda-2002 157 | Correct. |
| 26 | NTRA 141 | Correct. |
| 27 | CAT 34 | Correct (round 1: wrong, S2). |
| 28 | BAC 336 | Correct (round 1: wrong, S2); its check-2 report is F11. |
| 29 | aapl 8 | Correct (round 1: wrong, S1). |
| 30 | META 10-K 2025 t44 | Correct (round 1: wrong, S1). |
| 31 | KO 110 | Correct (round 1: wrong, S1); the first exhibit row stays the header line, as in main. |
| 32 | TSM 136 | Correct (round 1: wrong, years row). |
| 33 | CAT 143 | Correct. |
| 34 | MSFT 69 | Wrong (S5). |
| 35 | META 10-Q 2026 Q1 t39 | Correct: both linked descriptions kept, X marks in their own column. |
| 36 | BAC 46 | Years in the header line; note: header-only column from the title span. |
| 37 | JPM 543 | Note: years join the header line; the column-heading row stays in the body, as in main. |
| 38 | nvda-2026-ex99-1 t5 | Wrong (S7): empty header line; titles, caption and dates in the body. |
| 39 | nvda-2026-ex99-1 t11 | Wrong (S7). |
| 40 | META 10-K 2025 t37 | Worse than main (S8): "Description \| December 31, 2024 \| Quoted Prices …" leaves main's header line. |
| 41 | TSLA 40 | Worse than main (S8): the date row leaves main's header line. |
| 42 | nvda-2026-10k 38 | Note: "Inventories: \| (In millions)" stays in the body, as in main. |

**Verdict: NOT MET.** 30 correct, 7 with a note, 5 wrong; all 5 follow from spec rules.

## 14. Overhead

Median of 9 runs per side, one process per run, rounds alternating which side runs first; `get_pages` time only.

| Fixture | Main (s) | Candidate (s) | Ratio |
|---|---|---|---|
| aapl-2023-10k | 0.7215 | 0.7950 | 1.102 |
| nvda-2002-10k | 1.5358 | 1.6296 | 1.061 |
| nvda-2026-08-26-8k | 0.0162 | 0.0173 | 1.068 |
| nvda-2026-10k | 0.8892 | 1.0662 | 1.199 |
| nvda-2026-ex99-1 | 0.2034 | 0.2200 | 1.082 |
| nvda-2026-ex99-2 | 0.2017 | 0.1625 | 0.806 |
| nvda-2026-q2-10q | 0.6738 | 0.7243 | 1.075 |
| **Total** | **4.2416** | **4.6149** | **1.088** |

- The median of run totals gives 1.0884. No run is more than 15% from its fixture's median.
- The untimed construction totals 1.2387 s on main and 1.2231 s on the candidate.
- Before this round's optimizations the figure was 1.185; an earlier 9-run measurement read 1.0901.
- The optimizations are behaviour-preserving: `run_side` dumps were identical on 109 of 109 documents in both modes.

**Verdict: MET.**

## 15. Moved rows (new criterion)

`moved_rows.json`.

- 2,201 rows in 1,558 tables (fixtures: 140 rows in 106 tables); 39 are the first row of their header zone.
- **Independent rule check.** `analyze_candidate.py` implements revision 11's header-like rule itself and never imports `table_roles`. 0 failures. Reasons: empty label cell 1,983; year run 225; unit-text label 167; period-text label 44; year-like label 3.
- **Signals.**
  - Links, 14 rows: the "Part I" heading of NVDA tables of contents (empty label cell; text and link kept).
  - Values with units, 5 rows: column headings such as "Less than 12 months | 12 months or more | Total".
  - Words in value cells, 490 rows in 375 tables: a sample of 20 are all column headings.
  - Identifier labels: 0.
- The guard's count (147) differs because it counts rows per document by text signature, including nested rows.

**Verdict: MET.**

## Rows leaving main's header line (S7, S8)

`header_departures.json`.

- 294 rows in 282 tables leave main's header line; 178 of them are data rows main had swallowed (the intended class-5 fix).
- 116 non-data rows in 109 tables:
  - 34 label-only rows;
  - 82 rows with value-column text in 80 tables (S8): exhibit headings 23, fair-value headings with dates 14, other dated headings 18, other headings 27.
- Zone cuts by a label-only row with value-text rows below it: 11 tables.
  - 6 are intended: the lease-term title above "Finance leases | 13.7 years".
  - CAT 139.
  - The 4 S7 fixture tables.

## Fixture body-row guard (widened)

- The guard now covers every fixture source row with visible text, counted per text signature.
- Baseline from `c674828`: 2,492 body-rendered rows of 2,946 rows with text.
- 147 listed moves account for every lost count: nvda-2026-10k 39, nvda-2002 29, q2 33, ex99-1 7, ex99-2 8, aapl 0, 8-K 0. Each is an R0 header-zone row present in a candidate header line.
- On round 1's code the guard fails five fixtures, and on aapl it reports exactly the "Common Stock … | AAPL | …" row.

## S5: MSFT 69

- **Source.** Each year sits over the last column of the value cell to its left; the value's origin column has no header cell.
- **Renderer.** R2 blocks the year column's merge (the group has no header cell in that row, the year column has one). The year column then takes the next period's `$` and value. This is the spec's rule as written, not a prototype bug.
- **Checker.** It rates the values by their origin column's empty path.
- **Shape count:** 2 tables, 9 values (MSFT 69; JPM 145, whose rendering is reasonable).
- **Proposed rule, not implemented.** "R2, span continuation: column B merges into the group on its left, whatever its header cells, when in every body row B's slot is empty or covered by the span of a value cell (a complete number) whose origin is the group's slot in that row, with at least one such slot. The merged column carries B's header cells."
  - Simulated over 4,706 corpus tables: 1 table changes, MSFT 69, to "| Year Ended June 30, | 2025 | 2024 | 2023 |" over its values.
  - Without the value-cell condition: 51 tables change, and R6's one-cell invariant breaks.
  - It also needs a checker step-6 rule.

## Code changes

Fixes were written test first and folded into their task commits; trees are identical before and after each rebase. Final SHAs: T1 `a1db0a4`, T2 `f61f2a2`, T3 `461d06c`, T4 `876c24e`, T5 `53f7a6a`, T6 `1eb3b70`, T7 `e039479`, T8 `a1b9e66`, T9 `8914b9e`, T10 `2cb0f0e`. Full suite at `2cb0f0e`: 1502 passed, 14 deselected; ruff clean.

- T1: header-like rows, year runs, R0's unit and audit captions; performance changes.
- T4: grid-hidden rows and cells left out before placement; a row whose cells are all hidden stays as an empty row (found by this run: JPM 606, BAC 320/322); performance changes.
- T5: link-aware R6 suppression; rendering tests.
- T8: link-aware emitted path; `has_descendant` performance.
- T9: the checker reuses the render's link-free cell texts; coverage pins.
- T10: body-row guard over every row with visible text (counted), regenerated baseline, 147 listed moves; release notes.

Tooling: round 1's date pattern contained literal backspace characters where `\b` was meant, so its date signal never matched; fixed in round 2.
