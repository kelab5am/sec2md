# Table merge and header rules: acceptance run (prototype, round 1)

Date: 2026-10-06. Spec revision 10, "Acceptance criteria". How to rerun: `README.md`.

- **Baseline:** `c674828`, as a `git archive` tree. `sec2md.__file__` pointed at that tree in every run.
- **Candidate:** `proto/table-merge-header` at `1deab77`, imported from the worktree's `src` with a clean worktree.
- **Population:** the Phase A corpus, 109 documents: 7 fixtures, 32 RCQ primaries, 52 RCQ exhibits and 18 EDGAR documents, loaded by `corpus_phase_a.documents()`.
  - SHA-256 matches `results.json` for 109 of 109 documents.
  - The 18 EDGAR files match `edgar_manifest.json` (`run_check.json`).
- **Modes:** normal and capture, with table checks on.

## Stop conditions reached

Every measurement was still completed, and no code was changed to work around any of them.

| # | Condition | What happens | Where |
|---|---|---|---|
| S1 | NOT MET for a spec-rule reason (R0, R5) | Body rows before the first row with a complete number become header zone, and R5 fuses them into the header line. This covers text values, values with units, and exhibit numbers that are not complete numbers. At least 35 tables are affected, including fixture aapl-2023-10k t8. In META 10-Q 2026-Q1 t39, R6 suppression then drops a link. | Criteria 1, 2, 13; "Findings beyond the criteria" |
| S2 | Not covered by the spec: `display:none` cells | The renderer's grid includes CSS-hidden cells; the checker's placed grid and the visible table do not. Spanning headers then land over the wrong columns, and one table splits a value column. 1,075 rendered tables have such cells. | Criteria 7, 8, 9, 10 |
| S3 | XLSX output changes (workbook only) | Prepared tables are identical. The display-page heuristic reads Markdown table lines, so 4 pages in 2 documents change `display_page`, which the contents sheet prints for 9 tables. | Criterion 5 |
| S4 | Overhead > 1.10 | 1.139 (`get_pages` only). It is 1.0996 with the untimed construction added. | Criterion 14 |

Two smaller gaps: S5 (MSFT 69, a value colspan over its year header) and S6 (check 1 reading `US$ 1,250.0` as a text cell, TSM 344).

## Summary

| # | Criterion | Verdict | Key numbers |
|---|---|---|---|
| 1 | Check 1 | **NOT MET** | All 294 class-1 tables are fixed; BABA 75 keeps only F2 false-positive tokens. Page furniture (573 tables) is unchanged. New value failures in KO 110 and KO 111 (S1) and TSM 344 (S6). |
| 2 | Other findings | **NOT MET** | F7 disappears; 0 new check-2 findings. New check-1 findings: 3 tables with value tokens, 18 tables with reported tokens (15 are a header-line tokenizer definition case, 3 come from S1, including META 39's lost link). Removed: 440 value tokens, 54 reported tokens, 1 check-2 row. |
| 3 | Strict | **MET** | 0 new strict failures in either mode; `header_accounting_misses` is 0 everywhere. Main and candidate share the same 14 pre-existing trace failures. |
| 4 | Sections | **MET** | 872 of 872 comparisons identical (109 documents × 4 filing types × 2 modes). Page numbers are identical. |
| 5 | XLSX | **NEEDS REVIEW** (S3) | 3,707 of 3,707 prepared tables identical in values, column groups, source coordinates, headers and issues. 9 snapshots differ only in `display_page`, which the workbook prints. |
| 6 | Modes | **MET** | 109 of 109 documents agree on findings, alignment findings and coverage, strict results, sections and outputs. |
| 7 | Alignment | **NOT MET** (S2) | Both runs completed and the coverage identities hold. Misaligned values fall from 22,479 to 646 (74 tables, all with hidden cells, all misaligned on main too). 170 values evaluated on main are not evaluated on the candidate; 3,545 are gained. |
| 8 | Assignment audit | **NOT MET** (S2) | 6,616 merge steps regenerated; 6,427 pass. 189 fail, all in hidden-cell tables. BAC 336 is a value regression the checker cannot see, because all its rows are unpaired. |
| 9 | Header retention | **NOT MET** (S2, S5) | Values: 52,817 of 54,308 match their header path exactly. Header cells: 18,958 of 19,213 represented. Header-only columns: 739 of 739. |
| 10 | Known shifted tables | **NOT MET** (S2) | 6 of 7 tables pass every assertion (29 of 34 assertions). RDDT 10-Q 2024 Q2 table 17 fails 5 of 8. Main passes 1 of 34. |
| 11 | Class 8 | **NEEDS REVIEW** | 75 of 80 tables fixed. 5 TSM tables remain, with `)`, `%` and `)%` mixed in one marker column. |
| 12 | Named limitations | **NEEDS REVIEW** | The years row occurs in 106 tables; in 99 the label is a unit caption ("(Dollars in millions)") that the spec's unit-text pattern misses. T8's caption-number case: 0 tables. |
| 13 | Review sample | **NOT MET** | 34 tables reviewed: 19 correct, 3 correct with a note, 12 wrong. |
| 14 | Overhead | **NOT MET** (S4) | 1.139 (main 4.3225 s, candidate 4.9248 s). |

## 1. Check 1

Population: check-1 value failures in normal mode, by how each unit was rendered (`check1.json`).

| | Main | Candidate |
|---|---|---|
| `TableParser` output | 305 (294 class 1 + 11 Phase A false positives) | 15 |
| One-row output | 2 (G3; G5 CAT 7) | 1 (G3, a text-extraction issue) |
| No output (G4 page furniture) | 573 | 573: same tables, same tokens |

**The 294 class-1 tables:**
- 293 have no value failure on the candidate.
- BABA 75 keeps only `000`, `100`, `400` and `500`. These are F2 false positives: `RMB8,400` is glued in the source.
- BABA 75's class-1 token `31` now survives.

**The candidate's 15:**
- 12 are Phase A false-positive tables: F1 ×8, F2 BABA 75, F3 UNH 68, F5 KO 112 and F8 JPM 367. All except BABA 75 are unchanged.
- 3 are new:
  - **KO 110** (an F5 table), new tokens `29`, `30`, `31`. Cause: S1. The `10.5.22` … `10.5.33` exhibit rows are not complete numbers, while `10.6` and `10.7` are. So the `10.5.x` rows become header zone and fuse into one header line, and check 1 does not split three-part numbers in header lines (F5).
  - **KO 111**, new tokens `6`, `9`. Same cause: rows `10.7.4` to `10.7.9` are promoted.
  - **TSM 344**, new token `1250.0`. Cause: S6. The rendering is correct (`US$ 1,250.0`, R4), but check 1's `_COMPATIBLE` does not let a `value_numeric` source token match a `text_cell` output position.

**Verdict: NOT MET.** S1 creates new value failures.

## 2. Other findings

Normal mode; `findings.json`.
- **Totals:** tables with findings fell from 937 to 630. Removed: 440 value tokens, 54 reported tokens, 1 check-2 row.
- **Check 2:** no new findings. F7 (CAT 143) disappears.
- **F-table changes:**
  - F2 BABA 75 lost token `31` (an improvement).
  - F5 KO 110 gained value tokens (S1).
  - The 19 other F tables are identical.

**New reported tokens:** 18 tables, 26 tokens.
- **15 tables are a check-1 definition case.** nvda-2002-10k tables 19, 20, 22, 129, 130, 133, 144 and 146 (token `2`); TSM tables 244, 245, 247, 248, 253, 254 and 255 (token `3`).
  - R5 correctly moves "(As restated – see Note 2)" and "(Note 3)" into the header line.
  - Check 1 reads header-line cells with `numbers()` only, so it misses the identifier references it splits out of the same source cells.
  - Phase B fix: use the same identifier tokenization on header lines as on body cells (like F4 and F5).
- **KO 110 and KO 111 (S1):** exhibit identifiers `10.5` ×3, `10.6` and `10.8`, now inside the header line.
- **META 10-Q 2026-Q1 t39, `2025` (S1 plus a content loss).**
  - Exhibits `10.1+` and `10.2+` are promoted into the header line.
  - Their descriptions have the same text, so R6 writes only one.
  - The link `meta03312026-ex102.htm` is gone; main keeps both.

**Verdict: NOT MET.**

## 3. Strict

`strict.json`.
- **New strict failures: 0**, in either mode.
- **Pre-existing on both sides, identical:** 14 document-mode pairs with "untraceable normalized number" warnings:
  - MSFT 10-K;
  - NTRA 10-K;
  - the RCQ exhibits META 10-Q 2024 Q3 `a-x3jpybaorqx5lnom` and NVDA 10-K 2024 `a-2o5zcv34qhnrdt2l`;
  - NVDA 10-Q 2025 Q1 `a-6lttyfnyid5zsaok` and `a-b3bixfk3aduv2665`;
  - RDDT 10-K 2025 `a-y56cvz7iuqtqvlcr`.
- **Trace failures:** 14 on each side.
- **`header_accounting_misses`:** 0 everywhere.

**Verdict: MET.**

## 4. Sections

`sections.json`.
- `extract_sections` ran for 10-K, 10-Q, 20-F and 8-K on every document, in both modes.
- Each comparison covers `(part, item, item_title, pages)`.
- **Results:** 872 of 872 identical; for each primary's own filing type, 110 of 110. Page numbers are identical, and R8 changes no boundary.

**Verdict: MET.**

## 5. XLSX

`xlsx.json`, `xlsx_detail.json`.
- **Method:** capture mode; each full `PreparedTable` compared, ignoring the snapshot's `element_id` (it hashes element content, which rendering changes).
- **Result:** 3,707 snapshots compared; 9 snapshots in 2 documents differ, and only in `source.display_page`.

| Document | Page | `display_page` main → candidate | Snapshot ordinals | Note |
|---|---|---|---|---|
| NTRA 10-K | 76 | 76 → 587 | 7 | regression |
| TSM 20-F | 47 | 957 → 43 | 20, 21 | now correct |
| TSM 20-F | 146 | 4 → 8 | 131–133 | wrong both times |
| TSM 20-F | 160 | 1 → None | 159, 160 | wrong both times; the workbook falls back to page 160 |

**Cause.** `Parser._extract_page_number_from_content` scans the first and last three lines of each page and skips lines over 100 characters. In the remaining lines it matches `\b(\d{1,4})\s*\|` or `\|\s*(\d{1,4})\b`, so Markdown table lines can supply page numbers, and table rendering changes those lines:
- NTRA's line `… | $ 945,587 | …` is now under 100 characters, so it yields 587.
- On main, TSM page 46 already reads 118 from `2,608,118 |`.

**Effect.** `xlsx_writer.py:207` prints `display_page` in the contents sheet, so the workbook output changes.

**Verdict: NEEDS REVIEW.** This is a stop condition. The spec's identity fields all hold.

## 6. Modes

On all 109 documents, the candidate's normal and capture runs agree on:
- findings (snapshot ordinals removed);
- alignment findings and coverage;
- strict warnings, trace tokens and misses;
- sections;
- outputs, apart from unreliable-capture units.

Main also agrees on 109 of 109.

**Verdict: MET.**

## 7. Alignment

**Method.** The candidate's checker ran on main's Markdown and on the candidate's, unit by unit, with `check_tables`' inputs, recording per-value outcomes with `TableAlignment.outcomes`.

**Completeness.**
- All runs completed with full 21-key coverage.
- The four identities hold per document and in total.
- Summed coverage equals production's: `ParseDiagnostics` for the candidate, `check_tables` on main's outputs.
- The analysis re-parse reproduced the candidate's outputs exactly.

**Coverage, normal mode** (capture mode is identical on each side):

| Key | Main | Candidate |
|---|---|---|
| tables_total / evaluated | 5,332 / 3,155 | same |
| no_output / no_separator / unreliable / no_header / no_data | 691 / 934 / 0 / 222 / 330 | same |
| rows_data / below_repeated / unpaired / paired | 27,998 / 1,567 / 6,885 / 19,546 | 27,998 / 1,567 / 6,809 / 19,622 |
| values_total | 65,268 | 65,347 |
| nil / no_disc / missing / amb_position | 5,860 / 2,676 / 0 / 5,086 | 5,860 / 2,707 / 0 / 5,102 |
| amb_header / budget | 3,513 / 0 | 170 / 0 |
| evaluated / aligned / misaligned | 48,133 / 25,654 / **22,479** | 51,508 / 50,862 / **646** |

**Findings.**
- The candidate has 646 misaligned values (330 lines) in 74 tables across 17 documents: BAC, JPM, CRM, GOOGL, META 10-Q ×3, RDDT 10-Q ×7, NVDA 10-Q ×3.
- **All 74 tables have `display:none` cells.**
- No value went from aligned on main to misaligned on the candidate; all 646 were misaligned on main too.
- Example: BAC 75, "Advisory" 1504 under "Total Corporation"; expected "Investment Banking Fees — Global Banking".

**Per-value identities.** 99,097 values are listed in `alignment_values.tsv.gz`. 48,133 are evaluated on main and 51,508 on the candidate.

**170 are evaluated on main but not on the candidate.**
- 147 went from aligned and 23 from misaligned to `value_ambiguous_header`.
- They sit in 33 tables in 11 documents (RDDT 10-Q ×9, BAC, JPM, META 10-Q 2026 Q1), all with `display:none` cells.
- Each is listed in `alignment_losses.json` with main's header, the candidate's line and header line, and the expected path.
- **Rendering consequence:** the period caption does not reach the second period's column. For example: `| Three months ended March 31, | Three months ended March 31, — 2024 — (in thousands) | 2023 — (in thousands) |`.
- **Phase B consequence:** these values stay unevaluated until S2 is decided.

**3,545 are gained:** 3,513 ambiguous-header values and 32 unpaired-row values became aligned.

**Verdict: NOT MET** (S2).

## 8. Assignment audit

**Population.** The evidence tracer on `c674828` replays 3,707 of 3,707 tables and gives exactly 6,616 value+value same-header steps, in 2,040 tables.

**Method.** For every value cell:
- its output column from the candidate renderer's membership;
- independently, its output column from its tokens in the output line, found by an ordered label-and-token pairing;
- its column's header compared with the shared emitted path, computed on the placed grid.

**Results.**
- **6,427 pass:** both sides share one column, and the header matches the path exactly, case included.
- 49,113 values were located by token, with 0 contradictions to the membership. The rest: 5,784 nil values, 5,284 ambiguous positions, 82 non-values (mid-table year cells).
- **189 fail, in 145 tables, all with `display:none` cells.**
  - **186 header mismatches.** The values share one column, but its header lacks a level. Example: CAT 34's header reads "2023"; the path is "Twelve Months Ended December 31, — 2023".
  - **BAC 200, 2 steps.** Mid-table year cells (which the evidence's measure counts as values) land in a separate column under the table title. The amounts are right.
  - **BAC 336, step 10: a value regression.**
    - Consumer Banking's 2023 values are split across two output columns.
    - "Compensation and benefits (3)", "Other noninterest expense" and "Total noninterest expense" are shifted one column left, so 36,447 sits under a blank header and 6,422 under "Consumer Banking — 2022".
    - Main had these values right.
    - Every row of BAC 336 is unpaired, so the checker is blind to this.

**Verdict: NOT MET** (S2).

## 9. Header retention

`retention.json`.

**Values.**
- 54,308 uniquely located values in paired rows of evaluated tables, including those without a discriminating header.
- 52,817 headers render their path exactly (all case-exact).
- 1,491 mismatch, in 179 tables:
  - 178 of the tables have `display:none` cells;
  - MSFT 69 is S5.
- The checker rates 573 of the mismatched values aligned, because a caption over every value column is not required.

**Header cells.** 19,213 checked; 18,958 represented. 255 misses, in 176 tables, all with `display:none` cells.

**Header-only columns.** 739, all rendered.

**Required cases.**
- Word-only paths: 8,865 values, 224 mismatches (all S2).
- Literal ` — ` labels: 16 values in 25 header cells, 0 mismatches.

**Verdict: NOT MET.**

## 10. Known shifted tables

`shifted_tables.py` and `shifted_tables.json`. The script works independently of the checker:
- Each assertion names the row label, the exact cell text and the expected header.
- The expected headers were written from the source grids.

| Table | Assertions (value → expected header) | Candidate | Main |
|---|---|---|---|
| BABA 24 | Revenue: 868,687 → "Year ended March 31, — 2023 — RMB — (in millions, except per share data)"; 941,168 → "… 2024 — RMB …"; 996,347 → "… 2025 — RMB …"; 137,300 → "… — 2025 — US$ — (Note 2(a)) — …" | 4/4 | 0/4 |
| TSM 79 | Gross profit: 59.6 / 54.4 / 56.1 → "For the year ended December 31, — 2022 / 2023 / 2024" | 3/3 | 0/3 |
| TSM 312 | $ 347.0 / $ 331.6 / $ 531.5 → "Years Ended December 31 — 2022 / 2023 / 2024 — NT$ — (In Millions)"; 199.9 → the 2023 path | 4/4 | 0/4 |
| JPM 482 | $ 647 → "2024 — Consumer, excluding credit card"; $ — → "2024 — Credit card"; $ 1,432 and 45,147 → "2024 — Wholesale"; $ 2,079 and 55,587 → "2024 — Total" | 6/6 | 0/6 |
| MSFT 24 | Total revenue: 281,724 / 245,122 / 211,915 → "2025" / "2024" / "2023" | 3/3 | 1/3 |
| MSFT 65 | First Quarter: 7, $ 2,800, 11, $ 3,560, 17, $ 4,600 → "Shares/Amount — 2025/2024/2023" | 6/6 | 0/6 |
| RDDT 10-Q 2024 Q2 t17 | Basic weighted-average shares: 8 values → "Three/Six months ended June 30, — 2024/2023 — Class A/B — (in thousands, except share and per share data)" | **3/8** | 0/8 |

RDDT 17 has 65 `display:none` cells. The candidate renders 12 columns, some headers lack the year or the class, and there are empty columns. Example: 51,460,350 sits under "Six months ended June 30, — Class B — …".

**Verdict: NOT MET** (S2).

## 11. Class 8

`class8.json`.
- Of the evidence's 80 tables (TSM 35, BABA 23, MSFT 13, nvda-2002 9), **75 are fixed.**
- **5 TSM tables remain** (39 cells). Whole-column validation rejects mixed marker classes, as the spec's residual sentence allows:
  - **TSM 79** (20 cells): `%` and `)%` in one column.
  - **TSM 80** (6): `)` and `%` (percentage rows); `)%` in the change column.
  - **TSM 82** (4): the same, plus a `(750.8 | %)` close.
  - **TSM 83** (5): `)%` and `%`.
  - **TSM 84** (4): `)` and `%`; 3 of its 7 cells are now joined.
- In all 5, the headers are over the right values.
- No split exists outside the 80. Corpus-wide, split cells fall from 180 in 80 tables to 39 in 5.

**Verdict: NEEDS REVIEW.**

## 12. Named limitations

**The years row: 106 tables.** 29 have an empty header zone and 77 have one. All of them are header rows; none is real data.
- **99 tables have a unit-caption label.** "(Dollars in millions)" ×67, "(Millions of dollars)" ×24, "(Dollars in billions)" ×3, plus 5 tables with "(Dollars in millions, …)" variants. They are in BAC (72), CAT (26) and TSLA (1).
  - `_UNIT_LINE` (`^\(?(?:amounts? )?in (?:thousands|millions|billions)`) matches none of these labels.
  - Main also had these years in the body, so this is no regression.
- **7 others:**
  - JPM 543, 664 and 668: `2023 | 2022` with the first year in the label column;
  - JPM 662: `(Unaudited) | 2024`;
  - TSM 136, 137 and 308: the canonical `Function | 2022 | 2023 | 2024`.
- **TSM 136 is a regression:** main had the years in its header line.
- **Effect:** the years are missing from the header line, and the checker cannot see it.
- **Decision needed:** widen the unit-text rule, or accept the limitation explicitly.

**T8 caption numbers: 0 tables.** The 21 tables whose first row is data only through an identifier number are all genuine exhibit continuations: CAT 143–146, CRDO 60, JPM 56/57/59/60/62/63/65, KO 106/107/108/115, MU 66, TSM 217–219 and UNH 62.

**Verdict: NEEDS REVIEW.**

## 13. Review sample

The full source and both renderings for each table are in `review_sample.txt`.

| # | Table | Verdict |
|---|---|---|
| 1 | NVDA 10-Q 2026 Q1 t18 | **Wrong (S2):** the Jan 26, 2025 values are under headers without their date; 2 empty columns are added. |
| 2 | CRM 26 | Values right. **Caption misplaced (S2).** |
| 3 | JPM 109 | Correct. |
| 4 | TSLA 38 | Correct. |
| 5 | BAC 88 | Values right. **Table title misplaced (S2).** |
| 6 | TSM 248 | Correct. |
| 7 | RDDT 10-Q 2024 Q2 t52 | Correct. |
| 8 | MSFT 24 | Correct. |
| 9 | nvda-2002 138 | Correct. |
| 10 | BABA 24 | Correct. |
| 11 | TSM 79 | Headers correct; the class-8 split remains. |
| 12 | JPM 482 | Correct, with an extra empty header-only column (R7). |
| 13 | RDDT t17 | **Wrong (S2).** |
| 14 | MSFT 65 | Correct. |
| 15 | TSM 344 | Correct (the check-1 report is S6). |
| 16 | aapl 18 | Correct. |
| 17 | META 4 | Correct. |
| 18 | nvda-2026-10k 17 | Correct. |
| 19 | nvda-2026-10k 36 | Correct. |
| 20 | GOOGL 89 | Correct. |
| 21 | aapl 64 | Note: with no data row, the column headings land in the body (T3, as designed). |
| 22 | CAT 7 | Correct. |
| 23 | BABA 69 | Correct. |
| 24 | MSFT 43 | Correct; the caption repeats in every header (R6). |
| 25 | nvda-2002 157 | Correct. |
| 26 | NTRA 141 | Correct. |
| 27 | CAT 34 | **Wrong (S2).** |
| 28 | BAC 336 | **Wrong (S2), a regression.** |
| 29 | aapl 8 | **Wrong (S1).** |
| 30 | META 10-K 2025 t44 | **Wrong (S1).** |
| 31 | KO 110 | **Wrong (S1).** |
| 32 | TSM 136 | **Wrong (the years-row limitation).** |
| 33 | CAT 143 | Correct. |
| 34 | MSFT 69 | **Wrong (S5).** |

**Verdict: NOT MET.** 19 correct, 3 correct with a note, 12 wrong (counting #11 only for its residual).

## 14. Overhead

Each figure is the median of 9 runs per side, one process per run, rounds alternating which side runs first; `get_pages` time only.

| Fixture | Main (s) | Candidate (s) | Ratio |
|---|---|---|---|
| aapl-2023-10k | 0.7377 | 0.8659 | 1.174 |
| nvda-2002-10k | 1.5711 | 1.7191 | 1.094 |
| nvda-2026-08-26-8k | 0.0164 | 0.0181 | 1.104 |
| nvda-2026-10k | 0.8992 | 1.1285 | 1.255 |
| nvda-2026-ex99-1 | 0.2082 | 0.2409 | 1.157 |
| nvda-2026-ex99-2 | 0.2075 | 0.1774 | 0.855 |
| nvda-2026-q2-10q | 0.6824 | 0.7749 | 1.136 |
| **Total** | **4.3225** | **4.9248** | **1.139** |

- **Contract:** `Parser(html)` defaults; `get_pages(include_images=False)` timed; the same fixture bytes on both sides; 9 runs per side, each in its own process, with rounds alternating which side runs first.
- The median of per-run totals gives the same ratio (4.3311 against 4.9311).
- No run is more than 15% from its fixture's median.
- **Construction:** the untimed construction totals 1.266 s on main and 1.220 s on the candidate.
- **Profile:** most of the extra time is the alignment check: `check_tables` 1.85 s against 3.17 s, of which `align_table` is 1.68 s. The renderer itself costs about the same on both sides (1.79 s against 1.82 s).

**Verdict: NOT MET** (S4).

## Findings beyond the criteria

### S1. Body rows promoted into the header line

R0 needs a complete number or a nil value to call a row data. R5 writes the whole header zone (every row before the first data row) into the header line. Minimal reproductions, candidate output first, with main's in brackets:

```
<tr><td>Title of each class</td><td>Trading symbol(s)</td></tr><tr><td>Common Stock</td><td>AAPL</td></tr><tr><td>1.375% Notes due 2024</td><td>—</td></tr>
→ | Title of each class — Common Stock | Trading symbol(s) — AAPL |      [main: Common Stock is a body row]
<tr><td></td><td>2025</td><td>2024</td></tr><tr><td>Finance leases</td><td>15.1 years</td><td>13.7 years</td></tr><tr><td>Discount rate</td><td>4.1 %</td><td>3.6 %</td></tr>
→ | Finance leases | 2025 — 15.1 years | 2024 — 13.7 years |
<tr><td>10.5.22</td><td>Plan A</td></tr><tr><td>10.5.23</td><td>Plan B</td></tr><tr><td>10.6</td><td>Plan C</td></tr><tr><td>10.7</td><td>Plan D</td></tr>
→ | 10.5.22 — 10.5.23 | Plan A — Plan B |
```

**Corpus** (`moved_rows.json`):
- 2,333 rows that main wrote in its body sit in the candidate's header line, in 1,632 tables. Most are intended moves.
- Content signals flagged 152 rows for review. Review confirmed **35 tables**:
  - fixtures aapl 8 and nvda-q2 7;
  - NVDA 10-Q table 7 in 10 RCQ filings (TOC "Item 1.");
  - META 10-K 2024 t45 and 2025 t44;
  - META 10-Q 2025 Q1 t41, 2025 Q2 t41 and 2026 Q1 t39;
  - NVDA 10-Q 2025 Q3 t53 and 2026 Q2 t50;
  - the RDDT exhibit `a-y56cvz7iuqtqvlcr` t2;
  - AMZN 21; BABA 6 and 27; BAC 233; CRM 58; GOOGL 5 and 52; KO 110, 111 and 113; NVO 34; TSLA 53; TSM 216 and 422; UNH 65.
- 35 is a lower bound.
- T10's body-row guard only covers rows with two or more numbers, which is why it missed these.

### S2. `display:none` cells

`_extract_cells` reads hidden `td`s, while the checker places only the visible cells. Minimal reproduction (H = `style="display:none"`):

```
<tr><td>Millions of dollars</td><td H></td><td colspan=2>Twelve Months Ended December 31,</td></tr>
<tr><td></td><td H></td><td H></td><td>2024</td><td>2023</td></tr>
<tr><td>Free cash flow</td><td H></td><td H></td><td>9,449</td><td>10,025</td></tr>
→ | Millions of dollars | Twelve Months Ended December 31, | Twelve Months Ended December 31, — 2024 | 2023 |
  | Free cash flow |  | 9,449 | 10,025 |        [main: | Millions of dollars | 2024 | 2023 |]
```

- The checker rates this table aligned, because the caption is not required. Only the retention audit catches it.
- **Decision needed:** either the renderer skips grid-hidden cells, as the snapshot builder does, or the checker places them.

### S5. MSFT 69

- **Source:** `Year Ended June 30, | ·×4 | 2025 | …` over `Dividends | · | $ | 0.75 – 0.83 [cs3]`. The year sits inside the value's colspan, not over its origin column.
- **Candidate output:** `| Year Ended June 30, |  | 2025 | 2024 | 2023 |` over `| Dividends … | $ 0.75 – 0.83 | $ 0.68 – 0.75 | $ 0.62 – 0.68 |  |`, so each year heads the next year's value.
- **Checker:** skips these values as `value_no_discriminating_header`.
- **Main:** dropped the years instead.

### S6. TSM 344

Check 1's `value_numeric` tokens cannot match a `text_cell` output position, and R4's `US$ 1,250.0` makes the cell a text cell (criterion 1).

## Code changes

`TableAlignment.outcomes` and `ValueOutcome` were folded into T9, with 4 tests. New SHAs: T9 `5215e3d`, T10 `1deab77`. Suites: 1322 passed / 17 failed (16 known + 1 environment effect) and 1390 passed / 14 deselected. Ruff is clean. No rendering code changed.
