# Spec B fact pack: per-block header rows for stacked period tables (XLSX, one sheet)

Date: 2026-10-12. Read-only investigation on `main` at `172f428` (src identical to merged PR #11 plus `1c0ac51`, the
"or" in `_PERIOD_VOCABULARY`). No export_tables.py or corpus export was run; no repo file other than this one was
written.

## Method

- **Guard trace with main's code, without the Parser.** For each of the 60 filings in
  `docs/superpowers/audits/2026-10-11-xlsx-header-detection/filings.txt`, the filing HTML was parsed with
  BeautifulSoup (lxml) and every `<table>` snapshotted with main's `snapshot_html_table` (note targets computed once).
  Each new6 JSON table was matched to its raw snapshot by its source-cell signature (as export_tables.py does):
  3,701 of 3,702 matched (BABA #18 unmatched; its guard did not fire in task-7's trace either). For every matched
  table, main's `prepare_table` reproduces new6's status and headers exactly (0 differences), so the snapshots are
  faithful. `_export_header_count` was run with the guard and with `_period_row` forced to `False`.
- **Result: the guard fires in the same 169 tables as `task-7/guard.json`** (at `5f779c0`); `1c0ac51` changes no
  corpus table.
- **Block starts.** A body period row (main's `_period_row`, at or below the unguarded extended header) starts a
  later block when at least one data row (`_is_data_cell(digits=True)`) lies between the extended header (or the
  previous block start) and it, and at least one data row follows it. Contiguous heading rows just above it that are
  not data and have no label-column cell are pulled into the new block. A period row with no data row above it is
  "stranded"; with no data row below it, "trailing".
- **Manual classification** of every table with a block start, by reading the source grids and XBRL contexts
  (below). Scripts: `fact-pack-scripts/` beside this file, run from a session scratchpad (paths need adjusting;
  raw outputs not kept)
  (`scan.py`, `classify.py`, `refine.py`, `probe2.py`, `yearcheck.py`, `inventory.py`, `show.py`; `classify.json`,
  `probe2.json`, `refine.txt`, `inv_stacked.md`).

## A. Inventory

### The 169 guard-fired tables by kind

| Kind | META | NVDA | RDDT | Others | Total |
|---|---|---|---|---|---|
| **Stacked period blocks, later blocks repeat column headings** | 9 | 0 | 12 | 5 | **26** |
| **Stacked period blocks, caption only (headings once at the top)** | 0 | 17 | 0 | 19 | **36** |
| Year section labels over dated records (META dividends) | 4 | 0 | 0 | 0 | 4 |
| Section split, same period(s) repeated (not a period change) | 0 | 0 | 0 | 5 | 5 |
| Exhibit indexes (dated record rows) | 0 | 0 | 6 | 2 | 8 |
| Stranded period row, one block only | 0 | 0 | 0 | 90 | 90 |
| **Total** | 13 | 17 | 18 | 121 | **169** |

**True stacked tables: 62** (META 9, NVDA 17, RDDT 12, Others 24). Status on `main` (new6):

| Group | source_text_only | needs_review | exported |
|---|---|---|---|
| META (9) | 9 | 0 | 0 |
| NVDA (17) | 7 | 10 (`Column N` headers) | 0 |
| RDDT (12) | 11 | 1 (2024-Q2 #8, `Column N` headers) | 0 |
| Others (24) | 19 | 5 (JPM #159, MSFT #39, TSM #156, TSM #157, UNH #31) | 0 |
| **Total** | **46** | **16** | **0** |

Others = JPM #158, #159, #161, #194, #241, #290; KO #33, #34, #36, #42, #50, #76, #91, #92; UNH #27, #29, #30, #31,
#55; MSFT #39; TSM #156, #157; BAC #113; MU #38.

### How the kinds were told apart

1. **Exhibit indexes** (RDDT 10-Q 2024-Q1 #48, 10-K FY2024 #63 and #64, 10-K FY2025 #62 and #63, 10-Q 2026-Q2 #47,
   MSFT #80, CRM #79): the "period rows" are record rows (`10.2(a)# | 2017 Equity Incentive … | S-1 | 2/22/2024`)
   whose only period text is a numeric filing date in a non-label column; the rows carry exhibit numbers and
   descriptions and no XBRL facts. Five of them have data rows (file numbers) around such rows, so the mechanical
   block-start rule matched them; they are not blocks.
2. **Stranded (90, all Others)**: every period row lies above the first data row, so the table has one block. Shapes:
   years or dates beside a unit caption or a yearless heading (`(Millions of dollars) | 2024 | 2023`,
   `December 31, (in millions) | 2024 | 2023`: CAT, JPM, UNH, KO, BAC #18/#134, NTRA #43, UNH #52, TSM #105, SPCX
   #51); one caption under the column headings for a single-period table (MSFT #32-#36, #38, KO #83, #85, #96, #98,
   TSM #155, BAC #92/#93, BABA #40/#65, NTRA #32, JPM #215-#220 which are year-paired tables); heading rows that
   contain dates (TSM #59, #78, #108-#110, TSLA #35, KO #40/#41/#44, GOOGL #41). The full list is in the appendix.
3. **Section split, same period** (JPM #137, #138, #139; TSM #165; UNH #38): a second header block follows data, but it
   names the **same** period(s) as the first (JPM Level 3 roll-forwards: `Year ended December 31, 2024` over assets,
   then again over liabilities, with an extra `Issuances` column; UNH #38: `Net Incurred Medical Costs` then `Net
   Cumulative Medical Payments`, both `2023 | 2024`; TSM #165: sections b./c. repeat `Years Ended December 31 — 2022 |
   2023 | 2024`, section d. switches to `December 31, 2023 | December 31, 2024` instants). Each block's own header is
   right for its rows, so they behave like stacked blocks structurally, but the guard is not protecting a period
   misattribution there. The facts confirm it: JPM #137-#139 blocks share one duration context.
4. **Year section labels (META dividends: 10-Q 2025-Q1 #22, 2025-Q2 #22, 2025-Q3 #25, 10-K FY2025 #50)**: `2025` and
   `2024` label-column rows group dividend records. The columns (`Record Date | Payment Date | Dividend Per Share |
   Class A | Class B | Total`) carry no period; each row carries its own dates and quarterly XBRL context (all inside
   the label's year). A one-header export with the year rows left in the body misattributes nothing. Classed apart;
   structurally they are caption-only blocks.
5. **True stacked period blocks (62)**: a later block's caption names a **different** period from the block above, and
   the column headings (repeated or not) mean the same thing in every block, so the block's period must reach its
   column headers. Confirmed by XBRL (C below): in every block, the facts match the block's own caption and not the
   other block's.

### Stacked tables in detail

"Block rows" = `header-rows-start - last-header-row → last block row` (source rows; block 1's header includes the
column headings). Position: `own row` = a caption row by itself spanning the value columns (`x2 column groups` = one
caption per side-by-side group); `label column (own row)` = caption alone in column 0; `label column beside headings`
= caption in column 0 on a row that also holds column headings. "Per-block prepare" and "Single-sheet sim" are
explained in C. "Later blocks repeat headings" compares the non-period heading cells (text, column, span) of each
later block with block 1 (`full`, `partial` = some texts differ or spans differ, `none` = caption only); section B
gives the exact differences.

#### Later blocks repeat the column headings (26)

| Filing | # | Title | Main | Blocks | Block rows (header rows → last row) | Captions (row, position, text) | Later blocks repeat headings | Same amount cells | Per-block prepare | Single-sheet sim |
|---|---|---|---|---|---|---|---|---|---|---|
| META 10-Q 2022-Q2 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→12, 13-15→23 | B1 r1 own row x2 column groups: `Three Months Ended June 30, 2022 | Three Months Ended June 30, 2021`<br>B2 r13 own row x2 column groups: `Six Months Ended June 30, 2022 | Six Months Ended June 30, 2021` | full | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 104} other issues=0 |
| META 10-Q 2022-Q3 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→12, 13-15→23 | B1 r1 own row x2 column groups: `Three Months Ended September 30, 2022 | Three Months Ended September 30, 2021`<br>B2 r13 own row x2 column groups: `Nine Months Ended September 30, 2022 | Nine Months Ended September 30, 2021` | full | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 104} other issues=0 |
| META 10-Q 2023-Q2 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→12, 13-15→23 | B1 r1 own row x2 column groups: `Three Months Ended June 30, 2023 | Three Months Ended June 30, 2022`<br>B2 r13 own row x2 column groups: `Six Months Ended June 30, 2023 | Six Months Ended June 30, 2022` | partial | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 104} other issues=0 |
| META 10-Q 2023-Q3 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→12, 13-15→23 | B1 r1 own row x2 column groups: `Three Months Ended September 30, 2023 | Three Months Ended September 30, 2022`<br>B2 r13 own row x2 column groups: `Nine Months Ended September 30, 2023 | Nine Months Ended September 30, 2022` | full | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 104} other issues=0 |
| META 10-Q 2024-Q2 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→13, 14-16→25 | B1 r1 own row x2 column groups: `Three Months Ended June 30, 2024 | Three Months Ended June 30, 2023`<br>B2 r14 own row x2 column groups: `Six Months Ended June 30, 2024 | Six Months Ended June 30, 2023` | full | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 108, 'label column': 2} other issues=0 |
| META 10-Q 2024-Q3 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→14, 15-17→27 | B1 r1 own row x2 column groups: `Three Months Ended September 30, 2024 | Three Months Ended September 30, 2023`<br>B2 r15 own row x2 column groups: `Nine Months Ended September 30, 2024 | Nine Months Ended September 30, 2023` | full | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 112, 'label column': 2} other issues=0 |
| META 10-Q 2025-Q2 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→14, 15-17→27 | B1 r1 own row x2 column groups: `Three Months Ended June 30, 2025 | Three Months Ended June 30, 2024`<br>B2 r15 own row x2 column groups: `Six Months Ended June 30, 2025 | Six Months Ended June 30, 2024` | full | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 116} other issues=0 |
| META 10-Q 2025-Q3 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→14, 15-17→27 | B1 r1 own row x2 column groups: `Three Months Ended September 30, 2025 | Three Months Ended September 30, 2024`<br>B2 r15 own row x2 column groups: `Nine Months Ended September 30, 2025 | Nine Months Ended September 30, 2024` | partial | True | B1 export hc=4 cols=15 names; B2 export hc=3 cols=15 names | needs_ cols=15 facts={'ok': 125} other issues=0 |
| META 10-Q 2026-Q2 | 9 | CONDENSED CONSOLIDATED STATEMENTS OF STO | source_text_only | 2 | 0-3→14, 15-17→27 | B1 r1 own row x2 column groups: `Three Months Ended June 30, 2026 | Three Months Ended June 30, 2025`<br>B2 r15 own row x2 column groups: `Six Months Ended June 30, 2026 | Six Months Ended June 30, 2025` | partial | True | B1 export hc=4 cols=11 names; B2 export hc=3 cols=11 names | needs_ cols=11 facts={'ok': 102, 'label column': 2} other issues=0 |
| RDDT 10-Q 2024-Q2 | 8 | Consolidated Statements of Convertible P | needs_review | 2 | 0-4→13, 14-17→28 | B1 r1 own row: `Three months ended June 30, 2023`<br>B2 r14 own row: `Three months ended June 30, 2024` | full | True | B1 export hc=4 cols=11 names; B2 export hc=3 cols=11 names | needs_ cols=11 facts={'ok': 72} other issues=0 |
| RDDT 10-Q 2024-Q2 | 9 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→13, 14-18→29 | B1 r1 own row: `Six months ended June 30, 2023`<br>B2 r14 own row: `Six months ended June 30, 2024` | full | False | B1 export hc=5 cols=12 names; B2 export hc=4 cols=11 names | needs_ cols=11 facts={'ok': 87} other issues=0 |
| RDDT 10-Q 2024-Q3 | 8 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→13, 14-17→29 | B1 r1 own row: `Three months ended September 30, 2023`<br>B2 r14 own row: `Three months ended September 30, 2024` | full | False | B1 export hc=5 cols=12 names; B2 export hc=4 cols=12 names | needs_ cols=11 facts={'ok': 74} other issues=0 |
| RDDT 10-Q 2024-Q3 | 9 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→13, 14-18→30 | B1 r1 own row: `Nine months ended September 30, 2023`<br>B2 r14 own row: `Nine months ended September 30, 2024` | full | False | B1 export hc=5 cols=12 names; B2 export hc=4 cols=11 names | needs_ cols=11 facts={'ok': 90} other issues=0 |
| RDDT 10-Q 2025-Q1 | 8 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→16, 17-20→32 | B1 r1 own row: `Three months ended March 31, 2024`<br>B2 r17 own row: `Three months ended March 31, 2025` | full | False | B1 export hc=5 cols=11 names; B2 export hc=4 cols=12 names | needs_ cols=11 facts={'ok': 82} other issues=0 |
| RDDT 10-Q 2025-Q2 | 8 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→16, 17-20→32 | B1 r1 own row: `Three months ended June 30, 2024`<br>B2 r17 own row: `Three months ended June 30, 2025` | full | False | B1 export hc=5 cols=9 names; B2 export hc=4 cols=9 names | needs_ cols=9 facts={'ok': 71} other issues=0 |
| RDDT 10-Q 2025-Q2 | 9 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→16, 17-20→28 | B1 r1 own row: `Six months ended June 30, 2024`<br>B2 r17 own row: `Six months ended June 30, 2025` | full | False | B1 export hc=5 cols=11 names; B2 export hc=4 cols=12 names | needs_ cols=11 facts={'ok': 94} other issues=0 |
| RDDT 10-Q 2025-Q3 | 8 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→16, 17-20→32 | B1 r1 own row: `Three months ended September 30, 2024`<br>B2 r17 own row: `Three months ended September 30, 2025` | full | False | B1 export hc=5 cols=9 names; B2 export hc=4 cols=9 names | needs_ cols=9 facts={'ok': 72} other issues=0 |
| RDDT 10-Q 2025-Q3 | 9 | Consolidated Statements of Convertible P | source_text_only | 2 | 0-4→17, 18-21→29 | B1 r1 own row: `Nine months ended September 30, 2024`<br>B2 r18 own row: `Nine months ended September 30, 2025` | full | False | B1 export hc=5 cols=11 names; B2 export hc=4 cols=12 names | needs_ cols=11 facts={'ok': 94} other issues=0 |
| RDDT 10-Q 2026-Q1 | 8 | Consolidated Statements of Stockholders’ | source_text_only | 2 | 0-4→14, 15-18→29 | B1 r1 own row: `Three months ended March 31, 2025`<br>B2 r15 own row: `Three months ended March 31, 2026` | full | False | B1 export hc=5 cols=9 names; B2 export hc=4 cols=9 names | needs_ cols=9 facts={'ok': 68} other issues=0 |
| RDDT 10-Q 2026-Q2 | 8 | Consolidated Statements of Stockholders’ | source_text_only | 2 | 0-4→14, 15-18→29 | B1 r1 own row: `Three months ended June 30, 2025`<br>B2 r15 own row: `Three months ended June 30, 2026` | full | False | B1 export hc=5 cols=9 names; B2 export hc=4 cols=9 names | needs_ cols=9 facts={'ok': 68} other issues=0 |
| RDDT 10-Q 2026-Q2 | 9 | Consolidated Statements of Stockholders’ | source_text_only | 2 | 0-4→13, 14-17→26 | B1 r1 own row: `Six months ended June 30, 2025`<br>B2 r14 own row: `Six months ended June 30, 2026` | full | False | B1 export hc=5 cols=9 names; B2 export hc=4 cols=9 names | needs_ cols=9 facts={'ok': 68} other issues=0 |
| JPM-10-K-2025-02-14 | 158 | Fair value hedge gains and losses | source_text_only | 3 | 0-3→8, 9-11→16, 17-19→23 | B1 r2 label column beside headings: `Year ended December 31, 2024 (in millions)`<br>B2 r10 label column beside headings: `Year ended December 31, 2023 (in millions)`<br>B3 r18 label column beside headings: `Year ended December 31, 2022 (in millions)` | full | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | source_text_only: Unresolved value span at (5, 3); review colum |
| JPM-10-K-2025-02-14 | 159 | December 31, 2024 (in millions) | needs_review | 2 | 0-3→8, 9-11→15 | B1 r2 label column beside headings: `December 31, 2024 (in millions)`<br>B2 r10 label column beside headings: `December 31, 2023 (in millions)` | full | True | B1 needs_ hc=3 cols=6 names; B2 needs_ hc=2 cols=6 names | needs_ cols=6 facts={'ok': 24} other issues=1 |
| JPM-10-K-2025-02-14 | 161 | Year ended December 31, 2023 (in million | source_text_only | 2 | 0-3→7, 8-10→13 | B1 r2 label column beside headings: `Year ended December 31, 2023 (in millions)`<br>B2 r9 label column beside headings: `Year ended December 31, 2022 (in millions)` | full | True | B1 export hc=3 cols=4 names; B2 export hc=2 cols=4 names | export cols=4 facts={'ok': 18} other issues=0 |
| JPM-10-K-2025-02-14 | 194 | Retained | source_text_only | 2 | 0-2→7, 8-9→13 | B1 r1 label column beside headings: `December 31, 2024`<br>B2 r8 label column beside headings: `December 31, 2023` | partial | True | B1 export hc=3 cols=5 names; B2 export hc=2 cols=5 names | export cols=5 facts={'ok': 32} other issues=0 |
| JPM-10-K-2025-02-14 | 241 | Consolidated VIE assets and liabilities | source_text_only | 2 | 0-3→10, 11-13→19 | B1 r2 label column beside headings: `December 31, 2024 (in millions)`<br>B2 r12 label column beside headings: `December 31, 2023 (in millions)` | full | True | B1 export hc=3 cols=9 names; B2 export hc=2 cols=8 names | export cols=9 facts={'ok': 84} other issues=0 |

#### Caption only (36)

| Filing | # | Title | Main | Blocks | Block rows (header rows → last row) | Captions (row, position, text) | Later blocks repeat headings | Same amount cells | Per-block prepare | Single-sheet sim |
|---|---|---|---|---|---|---|---|---|---|---|
| NVDA 10-Q 2024-Q1 | 31 | Note 15 - Segment Information | needs_review | 2 | 0-4→8, 9-9→12 | B1 r4 label column (own row): `Three Months Ended April 30, 2023`<br>B2 r9 label column (own row): `Three Months Ended May 1, 2022` | none | True | B1 needs_ hc=0 cols=6; B2 needs_ hc=0 cols=6 | export cols=5 facts={'ok': 16} other issues=0 |
| NVDA 10-Q 2024-Q2 | 32 | Note 15 - Segment Information | needs_review | 4 | 0-4→8, 9-9→13, 14-14→18, 19-19→22 | B1 r4 label column (own row): `Three Months Ended July 30, 2023`<br>B2 r9 label column (own row): `Three Months Ended July 31, 2022`<br>B3 r14 label column (own row): `Six Months Ended July 30, 2023`<br>B4 r19 label column (own row): `Six Months Ended July 31, 2022` | none | True | B1 needs_ hc=0 cols=6; B2 needs_ hc=0 cols=6; B3 needs_ hc=0 cols=6; B4 needs_ hc=0 cols=6 | export cols=5 facts={'ok': 32} other issues=0 |
| NVDA 10-Q 2024-Q3 | 32 | Note 15 - Segment Information | needs_review | 4 | 0-4→8, 9-9→13, 14-14→18, 19-19→22 | B1 r4 label column (own row): `Three Months Ended October 29, 2023`<br>B2 r9 label column (own row): `Three Months Ended October 30, 2022`<br>B3 r14 label column (own row): `Nine Months Ended October 29, 2023`<br>B4 r19 label column (own row): `Nine Months Ended October 30, 2022` | none | True | B1 needs_ hc=0 cols=6; B2 needs_ hc=0 cols=6; B3 needs_ hc=0 cols=6; B4 needs_ hc=0 cols=6 | export cols=5 facts={'ok': 32} other issues=0 |
| NVDA 10-K 2024-FY | 54 | Note 17 - Segment Information | needs_review | 3 | 0-4→8, 9-9→13, 14-14→17 | B1 r4 label column (own row): `Year Ended Jan 28, 2024:`<br>B2 r9 label column (own row): `Year Ended Jan 29, 2023:`<br>B3 r14 label column (own row): `Year Ended Jan 30, 2022:` | none | True | B1 needs_ hc=0 cols=6; B2 needs_ hc=0 cols=6; B3 needs_ hc=0 cols=6 | export cols=5 facts={'ok': 24} other issues=0 |
| NVDA 10-K 2024-FY | 59 | Schedule II – Valuation and Qualifying A | needs_review | 3 | 0-4→7, 8-8→11, 12-12→15 | B1 r4 label column (own row): `Fiscal year 2024`<br>B2 r8 label column (own row): `Fiscal year 2023`<br>B3 r12 label column (own row): `Fiscal year 2022` | none | True | B1 needs_ hc=0 cols=9; B2 needs_ hc=0 cols=9; B3 needs_ hc=0 cols=9 | needs_ cols=7 facts={'no header date': 36} other issues=18 |
| NVDA 10-Q 2025-Q1 | 33 | Note 14 - Segment Information | needs_review | 2 | 0-4→8, 9-9→12 | B1 r4 label column (own row): `Three Months Ended Apr 28, 2024`<br>B2 r9 label column (own row): `Three Months Ended Apr 30, 2023` | none | True | B1 needs_ hc=0 cols=6; B2 needs_ hc=0 cols=6 | export cols=5 facts={'ok': 16} other issues=0 |
| NVDA 10-Q 2025-Q2 | 33 | Note 14 - Segment Information | needs_review | 4 | 0-4→8, 9-9→13, 14-14→18, 19-19→22 | B1 r4 label column (own row): `Three Months Ended Jul 28, 2024`<br>B2 r9 label column (own row): `Three Months Ended Jul 30, 2023`<br>B3 r14 label column (own row): `Six Months Ended Jul 28, 2024`<br>B4 r19 label column (own row): `Six Months Ended Jul 30, 2023` | none | True | B1 needs_ hc=0 cols=6; B2 needs_ hc=0 cols=6; B3 needs_ hc=0 cols=6; B4 needs_ hc=0 cols=6 | export cols=5 facts={'ok': 32} other issues=0 |
| NVDA 10-Q 2025-Q3 | 33 | Note 14 - Segment Information | needs_review | 4 | 0-4→8, 9-9→13, 14-14→18, 19-19→22 | B1 r4 label column (own row): `Three Months Ended Oct 27, 2024`<br>B2 r9 label column (own row): `Three Months Ended Oct 29, 2023`<br>B3 r14 label column (own row): `Nine Months Ended Oct 27, 2024`<br>B4 r19 label column (own row): `Nine Months Ended Oct 29, 2023` | none | True | B1 needs_ hc=0 cols=6; B2 needs_ hc=0 cols=6; B3 needs_ hc=0 cols=6; B4 needs_ hc=0 cols=6 | export cols=5 facts={'ok': 32} other issues=0 |
| NVDA 10-K 2025-FY | 53 | Note 16 - Segment Information | source_text_only | 3 | 0-4→8, 9-9→13, 14-14→17 | B1 r4 label column (own row): `Year Ended Jan 26, 2025`<br>B2 r9 label column (own row): `Year Ended Jan 28, 2024`<br>B3 r14 label column (own row): `Year Ended Jan 29, 2023` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | export cols=5 facts={'ok': 30} other issues=0 |
| NVDA 10-K 2025-FY | 61 | Schedule II – Valuation and Qualifying A | needs_review | 3 | 0-4→7, 8-8→11, 12-12→15 | B1 r4 label column (own row): `Fiscal year 2025`<br>B2 r8 label column (own row): `Fiscal year 2024`<br>B3 r12 label column (own row): `Fiscal year 2023` | none | True | B1 needs_ hc=0 cols=9; B2 needs_ hc=0 cols=9; B3 needs_ hc=0 cols=9 | needs_ cols=7 facts={'no header date': 36} other issues=18 |
| NVDA 10-Q 2026-Q1 | 29 | Note 13 - Segment Information | source_text_only | 2 | 0-4→8, 9-9→12 | B1 r4 label column (own row): `Three Months Ended Apr 27, 2025`<br>B2 r9 label column (own row): `Three Months Ended Apr 28, 2024` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=5 facts={'ok': 20} other issues=0 |
| NVDA 10-Q 2026-Q2 | 29 | Note 13 - Segment Information | source_text_only | 4 | 0-4→8, 9-9→13, 14-14→18, 19-19→22 | B1 r4 label column (own row): `Three Months Ended Jul 27, 2025`<br>B2 r9 label column (own row): `Three Months Ended Jul 28, 2024`<br>B3 r14 label column (own row): `Six Months Ended Jul 27, 2025`<br>B4 r19 label column (own row): `Six Months Ended Jul 28, 2024` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres; B4 source hc=0 cols=0 unres | export cols=4 facts={'ok': 36} other issues=0 |
| NVDA 10-Q 2026-Q3 | 28 | Note 13 - Segment Information | source_text_only | 4 | 0-4→8, 9-9→13, 14-14→18, 19-19→22 | B1 r4 label column (own row): `Three Months Ended Oct 26, 2025`<br>B2 r9 label column (own row): `Three Months Ended Oct 27, 2024`<br>B3 r14 label column (own row): `Nine Months Ended Oct 26, 2025`<br>B4 r19 label column (own row): `Nine Months Ended Oct 27, 2024` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres; B4 source hc=0 cols=0 unres | export cols=4 facts={'ok': 36} other issues=0 |
| NVDA 10-K 2026-FY | 50 | Note 16 - Segment Information | source_text_only | 3 | 0-4→8, 9-9→13, 14-14→17 | B1 r4 label column (own row): `Year Ended Jan 25, 2026`<br>B2 r9 label column (own row): `Year Ended Jan 26, 2025`<br>B3 r14 label column (own row): `Year Ended Jan 28, 2024` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | export cols=4 facts={'ok': 27} other issues=0 |
| NVDA 10-K 2026-FY | 57 | Schedule II – Valuation and Qualifying A | needs_review | 3 | 0-4→7, 8-8→11, 12-12→15 | B1 r4 label column (own row): `Fiscal year 2026`<br>B2 r8 label column (own row): `Fiscal year 2025`<br>B3 r12 label column (own row): `Fiscal year 2024` | none | True | B1 needs_ hc=0 cols=9; B2 needs_ hc=0 cols=9; B3 needs_ hc=0 cols=9 | needs_ cols=7 facts={'no header date': 36} other issues=20 |
| NVDA 10-Q 2027-Q1 | 26 | Note 13 - Segment Information | source_text_only | 2 | 0-4→8, 9-9→12 | B1 r4 label column (own row): `Three Months Ended Apr 26, 2026`<br>B2 r9 label column (own row): `Three Months Ended Apr 27, 2025` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=4 facts={'ok': 18} other issues=0 |
| NVDA 10-Q 2027-Q2 | 29 | Note 13 - Segment Information | source_text_only | 4 | 0-4→8, 9-9→13, 14-14→18, 19-19→22 | B1 r4 label column (own row): `Three Months Ended Jul 26, 2026`<br>B2 r9 label column (own row): `Three Months Ended Jul 27, 2025`<br>B3 r14 label column (own row): `Six Months Ended Jul 26, 2026`<br>B4 r19 label column (own row): `Six Months Ended Jul 27, 2025` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres; B4 source hc=0 cols=0 unres | export cols=4 facts={'ok': 36} other issues=0 |
| BAC-10-K-2025-02-25 | 113 | (Dollars in millions) | source_text_only | 3 | 0-41→54, 55-55→70, 71-71→83 | B1 r39 beside column headings: `2024`<br>B2 r55 own row: `2023`<br>B3 r71 own row: `2022` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=1 cols=0 unres; B3 source hc=1 cols=0 unres | source_text_only: Unresolved value span at (39, 3); review colu |
| JPM-10-K-2025-02-14 | 290 | Note 31 – International operations | source_text_only | 3 | 0-2→9, 10-10→17, 18-18→24 | B1 r1 label column beside headings: `As of or for the year ended December 31, (in millions)`; r2 label column (own row): `2024`<br>B2 r10 label column (own row): `2023`<br>B3 r18 label column (own row): `2022` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | needs_ cols=7 facts={'no header date': 90} other issues=1 |
| KO-10-K-2025-02-20 | 33 | Net operating revenues disaggregated bet | source_text_only | 3 | 0-2→5, 6-6→9, 10-10→13 | B1 r2 label column (own row): `Year Ended December 31, 2024`<br>B2 r6 label column (own row): `Year Ended December 31, 2023`<br>B3 r10 label column (own row): `Year Ended December 31, 2022` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | export cols=4 facts={'ok': 27} other issues=0 |
| KO-10-K-2025-02-20 | 34 | Equity Securities | source_text_only | 2 | 0-2→6, 7-7→11 | B1 r2 label column (own row): `December 31, 2024`<br>B2 r7 label column (own row): `December 31, 2023` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=3 facts={'ok': 12} other issues=0 |
| KO-10-K-2025-02-20 | 36 | Debt Securities | source_text_only | 2 | 0-3→6, 7-7→10 | B1 r3 label column (own row): `December 31, 2024`<br>B2 r7 label column (own row): `December 31, 2023` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=5 facts={'ok': 24} other issues=0 |
| KO-10-K-2025-02-20 | 42 | Pretax impact that changes in the fair v | source_text_only | 3 | 0-2→9, 10-10→17, 18-18→25 | B1 r2 label column (own row): `2024`<br>B2 r10 label column (own row): `2023`<br>B3 r18 label column (own row): `2022` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | export cols=4 facts={'no header date': 38} other issues=0 |
| KO-10-K-2025-02-20 | 50 | NOTE 7: GOODWILL | source_text_only | 2 | 0-2→9, 10-10→17 | B1 r2 label column (own row): `2023`<br>B2 r10 label column (own row): `2024` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=8 facts={'no header date': 63} other issues=0 |
| KO-10-K-2025-02-20 | 76 | Income taxes | source_text_only | 3 | 0-2→4, 5-5→7, 8-8→10 | B1 r2 label column (own row): `2024`<br>B2 r5 label column (own row): `2023`<br>B3 r8 label column (own row): `2022` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | export cols=5 facts={'no header date': 24} other issues=0 |
| KO-10-K-2025-02-20 | 91 | The following table provides a reconcili | source_text_only | 2 | 0-2→11, 12-12→21 | B1 r2 label column (own row): `2023`<br>B2 r12 label column (own row): `2024` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=5 facts={'no header date': 44} other issues=0 |
| KO-10-K-2025-02-20 | 92 | Productivity and Reinvestment Program | source_text_only | 3 | 0-2→7, 8-8→13, 14-14→19 | B1 r2 label column (own row): `2022`<br>B2 r8 label column (own row): `2023`<br>B3 r14 label column (own row): `2024` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | export cols=5 facts={'no header date': 56} other issues=0 |
| MSFT-10-K-2025-07-30 | 39 | Fair value of our derivatives instrument | needs_review | 2 | 0-5→8, 9-10→13 | B1 r4 label column (own row): `June 30, 2025`<br>B2 r9 label column (own row): `June 30, 2024` | none | True | B1 needs_ hc=0 cols=12; B2 needs_ hc=0 cols=8 | needs_ cols=8 facts={'ok': 16} other issues=5 |
| MU-10-K-2025-10-03 | 38 | Note 17. Derivative Instruments | source_text_only | 2 | 0-5→13, 14-15→23 | B1 r4 label column (own row): `As of August 28, 2025`<br>B2 r14 label column (own row): `As of August 29, 2024` | partial | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=4 facts={'ok': 31} other issues=0 |
| TSM-20-F-2025-04-17 | 156 | Derivative financial instruments | needs_review | 2 | 0-6→16, 17-20→41 | B1 (none in table)<br>B2 r17 label column (own row): `December 31, 2024` | different | True | B1 export hc=2 cols=6; B2 needs_ hc=0 cols=11 | export cols=6 facts={'no header date': 11, 'ok': 40} other issues=0 |
| TSM-20-F-2025-04-17 | 157 | Lease liabilities | needs_review | 2 | 0-6→9, 10-11→13 | B1 r5 label column (own row): `December 31, 2023`<br>B2 r10 label column (own row): `December 31, 2024` | none | True | B1 needs_ hc=0 cols=16; B2 needs_ hc=0 cols=11 | export cols=6 facts={'ok': 10} other issues=0 |
| UNH-10-K-2025-02-27 | 27 | 3. Investments | source_text_only | 2 | 0-3→15, 16-17→29 | B1 r2 label column (own row): `December 31, 2024`<br>B2 r16 label column (own row): `December 31, 2023` | partial | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=5 facts={'ok': 88} other issues=0 |
| UNH-10-K-2025-02-27 | 29 | The fair value of available-for-sale deb | source_text_only | 2 | 0-3→9, 10-10→16 | B1 r3 label column (own row): `December 31, 2024`<br>B2 r10 label column (own row): `December 31, 2023` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=7 facts={'ok': 72} other issues=0 |
| UNH-10-K-2025-02-27 | 30 | A summary of fair value measurements by  | source_text_only | 2 | 0-2→13, 14-14→26 | B1 r2 label column (own row): `December 31, 2024`<br>B2 r14 label column (own row): `December 31, 2023` | none | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres | export cols=5 facts={'ok': 76} other issues=0 |
| UNH-10-K-2025-02-27 | 31 | A summary of fair value measurements by  | needs_review | 2 | 0-2→4, 5-5→7 | B1 r2 label column (own row): `December 31, 2024`<br>B2 r5 label column (own row): `December 31, 2023` | none | True | B1 needs_ hc=0 cols=8; B2 needs_ hc=0 cols=8 | export cols=7 facts={'ok': 20} other issues=0 |
| UNH-10-K-2025-02-27 | 55 | Reportable segment financial information | source_text_only | 3 | 0-4→19, 20-21→35, 36-37→51 | B1 r3 label column (own row): `2024`<br>B2 r20 label column (own row): `2023`<br>B3 r36 label column (own row): `2022` | partial | True | B1 source hc=0 cols=0 unres; B2 source hc=0 cols=0 unres; B3 source hc=0 cols=0 unres | export cols=9 facts={'no header date': 344} other issues=0 |

### Other guard firings

#### Year section labels (4)

- META 10-Q 2025-Q1 #22 `Dividend` (needs_review): period rows r2 `2025`; r8 `2024`, block starts [8]
- META 10-Q 2025-Q2 #22 `Dividend` (needs_review): period rows r2 `2025`; r7 `2024`, block starts [7]
- META 10-Q 2025-Q3 #25 `Dividend` (needs_review): period rows r2 `2025`; r7 `2024`, block starts [7]
- META 10-K 2025-FY #50 `Dividend` (needs_review): period rows r2 `2025`; r7 `2024`, block starts [7]

#### Section split, same period (5)

- JPM-10-K-2025-02-14 #137 `Year ended December 31, 2024 (in millions)` (source_text_only): period rows r40 `Year ended December 31, 2024 (in mi | Fair value at Jan. 1, 2024 | Total realized/unrealized (gains)/l`; r41 `Year ended December 31, 2024 (in mi | Fair value at Jan. 1, 2024 | Total realized/unrealized (gains)/l`, block starts [39]
- JPM-10-K-2025-02-14 #138 `Notes to consolidated financial statements` (source_text_only): period rows r40 `Year ended December 31, 2023 (in mi | Fair value at Jan. 1, 2023 | Total realized/unrealized (gains)/l`; r41 `Year ended December 31, 2023 (in mi | Fair value at Jan. 1, 2023 | Total realized/unrealized (gains)/l`, block starts [39]
- JPM-10-K-2025-02-14 #139 `Year ended December 31, 2022 (in millions)` (source_text_only): period rows r40 `Year ended December 31, 2022 (in mi | Fair value at Jan. 1, 2022 | Total realized/unrealized (gains)/l`; r41 `Year ended December 31, 2022 (in mi | Fair value at Jan. 1, 2022 | Total realized/unrealized (gains)/l`, block starts [39]
- TSM-20-F-2025-04-17 #165 `Item` (needs_review): period rows r11 `Years Ended December 31`; r12 `2022 | 2023 | 2024`, block starts [11, 20]
- UNH-10-K-2025-02-27 #38 `The following` (source_text_only): period rows r2 `(in millions) | For the Years Ended December 31,`; r3 `Year | 2023 | 2024`, block starts [8]

#### Exhibit indexes (8)

- RDDT 10-Q 2024-Q1 #48 `Item 6. Exhibits` (needs_review): period rows r10 `10.2(a)# | 2017 Equity Incentive and Grant Pla | S-1`; r11 `10.2(b)# | Form of Early Exercise Incentive St | S-1`, block starts [10, 14]
- RDDT 10-K 2024-FY #63 `Item 15. Exhibits and Financial Statement Sch` (needs_review): period rows r15 `10.5(a)# | 2012 Stock Option and Grant Plan, a | S-1`; r16 `10.5(b)# | Form of Incentive Stock Option Gran | S-1`
- RDDT 10-K 2024-FY #64 `Exhibit Number` (needs_review): period rows r2 `10.5(f)# | Form of Restricted Stock Award Gran | S-1`; r3 `10.6(a)# | 2017 Equity Incentive and Grant Pla | S-1`, block starts [7]
- RDDT 10-K 2025-FY #62 `Item 15. Exhibits and Financial Statement Sch` (needs_review): period rows r12 `10.4(a)# | 2012 Stock Option and Grant Plan, a | S-1`; r13 `10.5(b)# | Form of Incentive Stock Option Gran | S-1`
- RDDT 10-K 2025-FY #63 `Exhibit Number` (needs_review): period rows r2 `10.12(c)# | Form of Restricted Stock Unit Award | S-1`; r4 `10.14(b)# | Form of Stock Option Grant Notice a | S-1`, block starts [4]
- RDDT 10-Q 2026-Q2 #47 `Item 6. Exhibits` (needs_review): period rows r9 `10.1# | Amended and Restated Employment Off | 10-Q`; r10 `10.2# | Amended and Restated Employment Off | 10-Q`, block starts [9]
- CRM-10-K-2025-03-05 #79 `Exhibit No.` (needs_review): period rows r22 `10.26* | Amendment to Transition Agreement,  | X`
- MSFT-10-K-2025-07-30 #80 `Exhibit Number` (needs_review): period rows r19 `10.2* | Microsoft Corporation Employee Stoc | DEF14A`; r23 `10.4* | Microsoft Corporation 2017 Stock Pl | DEF14A`, block starts [19, 23]

## B. Shapes

**Repeated headings vs caption only.** 26 of 62 (42%) repeat headings; 36 (58%) are caption only.

- **Full repeat, same texts and spans (META 6 of 9, RDDT 12, JPM #158, #159, #161, #241).** RDDT: caption row
  `Three months ended …` (own row, `3:60` or `3:45`) then the three heading rows `Total Convertible Preferred Stock |
  Common Stock | APIC | AOCI | Accumulated Deficit | Total Stockholders' Equity (Deficit)` / `Class A | Class B` /
  `Shares | Amount`, repeated verbatim with the same spans. META: one row with two side-by-side captions (current
  year over columns 3-35, prior year over 39-71), then `Class A and Class B Common Stock | APIC | AOCI | Retained
  Earnings | Total Stockholders' Equity` and `Shares | Par Value`, repeated. JPM: the caption sits in the label column
  on the leaf heading row (`Year ended December 31, 2023 (in millions) | Amounts reclassified from AOCI to income |
  …`), with a group heading row above and a `Contract type` row below, all repeated.
- **Repeat with text differences (META 3: 2023-Q2, 2025-Q3, 2026-Q2 #9).** One heading differs between blocks:
  `Accumulated Other Comprehensive Loss` vs `… Income` vs `… Income (Loss)` (the sign of AOCI changed between the
  periods). Spans are the same.
- **Same texts, different spans (JPM #194).** Block 1 `Credit card` spans `12:9`, block 2 `15:3`; `Wholesale` and
  `Total(a)(b)` likewise. The amount cells are at the same positions.
- **Caption only (36).** NVDA segment tables (14) and Schedule II (3), KO (8), UNH #27, #29, #30, #31, #55, MSFT #39,
  TSM #157, JPM #290, MU #38: caption alone in the label column, with headings once at the top and the first caption
  directly under them (it is the "stranded" row that fires the guard in block 1). BAC #113: the caption is an own row
  spanning the value columns (`3:21`), beside `(Dollars in millions)` in the label column for block 1 only. TSM #156:
  block 1 has **no caption in its own table**; its caption `December 31, 2023` is in TSM #155, which the parser split
  off; block 2 has `December 31, 2024`. UNH #27/#55 and MU #38 also repeat a label-column section label
  (`Debt securities - available-for-sale:`, `Revenues - unaffiliated customers:`, `Derivative instruments with hedge
  accounting designation`) below each caption.

**Column structures.** All 62 have one grid width (one table). Amount cell positions (column, colspan of data cells)
are identical across blocks in 51 of 62. They differ only in the RDDT equity statements (11 of 12: block 2 uses
colspan 3 where block 1 uses 2, or places `$` differently). Prepared block by block, the column count differs between blocks, or from the whole-table grouping, in 6 RDDT
tables and 4 others:

| Table | Columns, block 1 / block 2, prepared separately | Whole table (one grouping) |
|---|---|---|
| RDDT 10-Q 2024-Q2 #9, 2024-Q3 #9 | 12 / 11 | 11 |
| RDDT 10-Q 2025-Q1 #8, 2025-Q2 #9, 2025-Q3 #9 | 11 / 12 | 11 |
| RDDT 10-Q 2024-Q3 #8 | 12 / 12 | 11 |
| JPM #241 | 9 / 8 (block 1 keeps an empty `Assets` spacer column) | 9 |
| MSFT #39 | 12 / 8 | 8 |
| TSM #157 | 16 / 11 | 6 |
| TSM #156 | 6 / 11 | 6 |

Separately prepared blocks can produce duplicate leaf columns (`… Class A — Amount` twice) where a block lacks the
consolidating `$`/amount evidence the other block has.

**Different column sets.** None of the 62 true stacked tables changes its column set between blocks. The section
splits do: JPM #137-#139 (liabilities add `Issuances`), TSM #165 (section d. drops the 2022 column and changes to
instants).

**Sub-captions and cross-block totals.** No total spans blocks: each block closes with its own balance or total row
(RDDT `Balance as of March 31, 2025`, KO `Total`). Sub-captions inside blocks are label-column section labels with no
period (`Net operating revenues:`, `Other segment information:`, `Revenues - unaffiliated customers:`, `Derivative
instruments with hedge accounting designation` / `… without …`, `Assets:`/`Liabilities:`); none is a period row.
JPM #290's block 1 caption is two-part: the header label `As of or for the year ended December 31, (in millions)`
(row 1, label column) plus `2024` (row 2); later blocks have only `2023`, `2022`.

## C. Feasibility probe (in memory, main's code via sys.path)

Three probes per stacked table.

**C1. Each block prepared separately** (block rows re-based to row 0 as a synthetic `TableSnapshot`, then
`prepare_table`; no spans cross a block boundary in any of the 62).

- **Repeated headings (26):** 25 of 26 tables work. Every block of META (9), RDDT (12) and JPM #159, #161, #194,
  #241 gets a header that names its own period and is `exported` (JPM #159 `needs_review` only for its
  pre-existing `Missing source header for Column 3`), with no unresolved span. Block 1 takes 4-5 header rows, later
  blocks 3-4 (no blank leading row). Header examples: `Six Months Ended June 30, 2022 — Class A and Class B Common
  Stock — Shares`, `Three months ended March 31, 2025 — Total Convertible Preferred Stock — Amount`. For JPM the period
  is only in the label column's header (`Year ended December 31, 2022 (in millions)` as header 0); value headers are
  `Derivatives gains/(losses) … — Amounts reclassified from AOCI to income`, so all_facts.py's per-column check reads
  them as "no header date". **JPM #158 fails**: inside each block, Rule 1 check 4b rejects the caption row (the
  labelled leaf row has a heading as wide as its parent, `Derivatives - Gains/(losses) recorded in OCI` under `OCI
  impact`), so the caption row is stranded, the guard fires inside the block, and the block falls back with an
  unresolved value span (it was source text on revision 5 too).
- **Caption only (36):** separate preparation does **not** work. Block 1's caption under the headings is itself a
  stranded period row, so the guard returns `base = 0`; later blocks have no headings at all (`_header_count` 0). All
  get `Column N` headers; in 22 of 36 tables the blocks are `source_text_only` (`Unresolved value span`, because without a leaf header
  `$` and amount are not grouped). Reusing block 1's heading rows above a later block's caption and data gives the
  same result (header count 0, guard fires on the caption).

**C2. Single-sheet simulation** (the closest model of spec B). `prepare_table` on the whole table with `_period_row`
forced to `False` (revision 5's extended header from block 1, one column grouping for the whole table); then each
block's header labels are rebuilt over those same columns: from the block's own heading rows when they repeat,
otherwise block 1's headings; the block's caption is prefixed when it is in the label column. Every XBRL fact in the
block is then checked with all_facts.py's `period_verdict` against its block's label.

| Group | Tables | Whole-table status (block header rows still in the body) | Facts vs per-block labels |
|---|---|---|---|
| META #9 | 9 | needs_review only because block 2's caption and heading rows sit in the body as data (2 issues, "Not a complete supported US numeric token"); 0 other issues | 979 ok, 0 mismatch (6 in the label column) |
| RDDT #8/#9 | 12 | needs_review, 1 issue each, the same cause; 0 other issues | 940 ok, 0 mismatch |
| NVDA segment | 14 | exported, 0 issues | 387 ok, 0 mismatch |
| NVDA Schedule II | 3 | needs_review, 18-20 pre-existing issues (`Missing source header`, footnote marker columns) | 108 year-only captions, all consistent (see C3) |
| JPM #159, #161, #194, #241 | 4 | exported (#159: 1 pre-existing issue) | 158 ok, 0 mismatch |
| JPM #290 | 1 | needs_review, 1 pre-existing issue | 90 year-only, consistent |
| KO (8), UNH (5), MSFT #39, MU #38, TSM #156/#157 | 17 | exported, 0 issues (MSFT #39: 5 pre-existing `Missing source header`) | 416 ok, 0 mismatch; 569 under year-only captions, consistent; TSM #156 block 1: 11 facts with no caption in its table |
| JPM #158, BAC #113 | 2 | **source_text_only even without the guard** (`Unresolved value span` at (5, 3) and (39, 3)); unchanged from revision 5 | not checkable |

So 60 of 62 tables can export with one column grouping and per-block labels, and **no fact in any block disagrees
with its block's label**. No amount sits in a block's header rows (0 in all 62), so lifting those rows out of the
body loses no value. The 2 failures are a pre-existing column-alignment fallback, not this feature.

**C3. XBRL against the captions (independent of the export).** Each fact was checked against the caption over its
column in its own block (side-by-side captions for META; label-column caption otherwise):

- Dated captions: every fact `ok` (instants at the end date or at the start of the stated length as opening
  balances; durations of the stated length) in all 62 tables; 0 mismatches. RDDT 2025-Q1 #8 block 2: `Net income
  (loss) 26,158` has context 2025-01-01..2025-03-31, under `Three months ended March 31, 2025`.
- Year-only captions (`2024`, `Fiscal year 2024`; KO #42, #50, #76, #91, #92, UNH #55, JPM #290, BAC #113, NVDA
  Schedule II, META dividends): checked by year. Durations end in the caption year (NVDA fiscal years end in late
  January of the named year), instants at its end or at the prior year end (opening balances): all consistent, 0
  mismatches.
- Section splits (JPM #137-#139, UNH #38, TSM #165): both blocks carry the same periods; no period change.

## D. Writer and consumers: what assumes one header row per table

`PreparedTable` (`src/sec2md/xlsx_tables.py:371-383`) holds one flat `headers` tuple; `rows` and `cell_sources` are
body rows only, aligned 1:1, with no row-kind marker; `original_rows` is the full source grid. It is not exported from
the package (`src/sec2md/__init__.py:15-17` exports only `export_xlsx`, `XlsxExportResult`, `XlsxTableResult` and the
two errors). No Markdown code path and no other repo uses it (rcq-wealth has no reference to `export_xlsx`,
`PreparedTable` or the named ranges).

**Production consumers**

| File:line | What it assumes |
|---|---|
| `src/sec2md/xlsx_tables.py:745-867` `prepare_table` | One `header_count` (`:780`) for the whole grid; `first_body_row` and grid-level unit capture (`:784-789`) use it; `_column_groups(grid, original, header_count)` (`:790`, def `:710`) takes leaf headings from rows `< header_count` and scans evidence from `header_count` to the end (later blocks' header rows count as body); the value-span veto (`:797-804`) skips only rows `< header_count`; structural actions run on `raw[header_count:]` (`:807-817`) and are vetoed by header cells of rows `< header_count` (`:811-814`); one `headers` list built from rows `< header_count` (`:819-830`); every body row's role/units/percent use `headers[index]` (`:843-857`); `financial` reads labels from `original[header_count:]` (`:834`). |
| `src/sec2md/xlsx_tables.py:548-636` `_export_header_count` | Returns one count; the guard (`:634-635`) is the only stacked-block handling. |
| `src/sec2md/xlsx_writer.py:12, 41` | Imports `PreparedTable`; `render_workbook(tables: Sequence[PreparedTable])`. |
| `src/sec2md/xlsx_writer.py:136` | Sheet width = `max(len(headers), max row length)`. |
| `src/sec2md/xlsx_writer.py:146-160` | Row 1 title, row 2 units, **row 3 = the one header row** (`heading=True` style), body from row 4; `Column N` headers blanked (`:151`); `copy_range = A2:{last col}{last body row}` (`:158`) and named range `CopyTable` (`:159`). |
| `src/sec2md/xlsx_writer.py:160-188` | Two blank rows, the `Original table` heading row, then `original_rows` with source merges; named range `OriginalTable` (`:187-188`). Unaffected by header shape. |
| `src/sec2md/xlsx_writer.py:19-26, 203-204` | `WorksheetResult(ordinal, worksheet_name, status, issues, copy_range, original_range)`: one copy range per sheet. |
| `src/sec2md/xlsx.py:16, 162` | `prepare_table` per selected snapshot; one sheet per table. |
| `src/sec2md/xlsx.py:163-166, 186` | Strict and the result list read `table.issues` (per table). |
| `src/sec2md/xlsx.py:180-185` | Completeness findings joined to worksheets by snapshot ordinal (`f.snapshot_ordinal` = `w.ordinal`). One sheet per table keeps this valid; findings are Markdown-vs-source and use `_header_count` (`src/sec2md/table_completeness.py:23, 412-421, 628-646`), which must not change. |
| `src/sec2md/table_parser.py:50, 996` | Docstrings: `prepare_table` relies on `TableParser._safe_structural_actions` / `_validated_structural_actions` (LEGACY policy) through `object.__new__(TableParser)`. |
| `docs/usage/xlsx-export.md:90-96, 98-99` | States that a stacked table "gets no extended header when the exporter recognises the second block's caption"; documents `CopyTable` / `OriginalTable`. |

**Tests that pin one header row or the guard**

| File:line | Assumption |
|---|---|
| `tests/accuracy/test_xlsx_accuracy.py:66-67` | `copy_bounds` from `CopyTable`. |
| `tests/accuracy/test_xlsx_accuracy.py:168-180` | `body_row` maps a source row to a `cell_sources` index; `copy_cell` = `top + 2 + row` (units row, one header row, then body). |
| `tests/accuracy/test_xlsx_accuracy.py:190-196` | `prepared.headers[1:] == expected`; width = `len(headers)`; the header row is `top + 1`. |
| `tests/accuracy/test_xlsx_accuracy.py:210, 228-231, 274, 307, 367-369` | Body rows at `top + 2 + i`. |
| `tests/test_xlsx_writer.py:8, 19, 44-45, 166-167, 196` | `prepare_table` output rendered; every header appears; `CopyTable` equals `copy_range`; `copy_range is None` for source text. |
| `tests/test_xlsx_header_detection.py:372-389` | `todays()` (guard outcome = today's), `outcome()`, `headers_over_amounts()` (one header per column, label column header heads every row). |
| `tests/test_xlsx_header_detection.py:392-470` | `test_guard_stacked_period_blocks`: 15 stacked layouts (caption row, caption beside headings, label-column caption, footnoted, JPM unit captions, `As of or for the`) must equal today's output. Spec B changes these by design. |
| `tests/test_xlsx_header_detection.py:473-495, 528-535` | Stranded rows and the `December 31, 2025` repeated section label keep today's output (guard cost pinned). |
| `tests/test_xlsx_tables.py`, `tests/test_xlsx.py:32-43`, `tests/test_xlsx_clean.py:8, 45, 84`, `tests/test_table_merge_headers.py:134-142` | Flat `headers`, `cell_sources[i]` indexing, `original_rows`. |

**Audit tooling that reads one header per column** (affects re-acceptance, not the product):
`docs/superpowers/audits/2026-10-11-xlsx-header-detection/export_tables.py:96-106` (serialises `headers`, `rows`,
`cell_sources`); `all_facts.py:164-212` (`period_verdict(context, table['headers'][ci])` for every row); 
`primary_statements.py:130-246`; `compare.py:42-53`; the value-accuracy fact-pack scripts
(`docs/superpowers/audits/2026-10-12-xlsx-value-accuracy/fact-pack-scripts/classify.py:72-100`, `mixed.py:41-64`,
`partb.py:135-148`). A per-block header needs either a per-row header lookup in the JSON (e.g. a block index per body
row and `headers` per block) or these scripts misjudge every block after the first.

## E. Observations and risks

1. **Scope is 62 tables, 46 of them source text today.** Repeated-heading blocks (26: META and RDDT equity
   statements, five JPM tables) are the D1 tables plus JPM; caption-only blocks (36: NVDA segment and Schedule II,
   KO, UNH, MSFT, TSM, BAC, JPM #290, MU) are the larger group and the one where the existing detection gives
   nothing: per block it yields `Column N` headers or source text.
2. **One column grouping for the whole table is required.** Prepared separately, RDDT blocks get 11 vs 12 columns
   and JPM #241 9 vs 8, with duplicate leaf columns. Revision 5's whole-table grouping (block 1's leaf headings,
   evidence from every body row) yields one consistent layout, and per-block labels over it put every fact under its
   own period (C2). A design that recomputes groups per block cannot share one CopyTable layout.
3. **Block header rows currently count as body evidence.** `_column_groups`, the value-span veto and the structural
   actions all treat later blocks' heading/caption rows as body. Removing them from the body (or adding them to
   the header veto) can change grouping and structural moves; C2 kept them in the body. Needs a test that the
   column count and `cell_sources` do not change when block header rows leave the body.
4. **Caption-only blocks need a new header source.** The caption is a label-column row (or an own row) under the
   shared headings. A per-block header must be composed (caption + block 1 headings); `_export_header_count`'s
   rules reject it as a labelled row with no headings. Year-only captions (`2024`, `Fiscal year 2024`) carry no
   month/day, so the resulting header passes no automated period check (all_facts "no header date"); the year check
   in C3 is the only XBRL evidence for them.
5. **Block 1's first caption is the guard's "stranded row".** In all 36 caption-only tables the guard fires on
   block 1's own caption, not on a later block. A block-aware design must treat "caption directly under the
   headings, followed by data, followed by another caption" as block 1's caption, while a single caption with no
   later block (MSFT #32-#36, KO #96/#98, TSM #155, 90 stranded tables) stays as today or becomes the same
   one-block case. The two must not be confused with I1 stranded year rows (TSM #105, NTRA #43, UNH #52).
6. **Period lives in the label column for JPM.** In JPM #159, #161, #194, #241 the period is in column 0's header
   only. Per-block headers there change header 0 per block; value-column headers carry no date. A reader (and
   all_facts.py) looking only at the value header sees no period unless the design copies the caption into the value
   headers.
7. **Two-part and cross-table captions.** JPM #290's block 1 period is `As of or for the year ended December 31,` +
   `2024` across two rows, later blocks only `2023`. TSM #156's block 1 has no caption at all (it is in TSM #155,
   split off by the parser); a design that requires a caption per block must leave TSM #156's block 1 headed as
   today, or take the caption from the previous table.
8. **False block starts.** Exhibit indexes (8) have dated record rows with numeric file numbers around them; META
   dividends (4) have year labels over self-dated rows; section splits (5) repeat the same period. A block rule
   keyed only on "period row after data" would split all of these. Distinguishing signals seen here: the period text
   is a numeric date in a non-label column (exhibits); the later block names the same period as the earlier one
   (section splits); the columns name no period-dependent quantity and each row has its own dates (dividends).
9. **Pre-existing failures stay.** JPM #158 (check 4b rejects the labelled leaf row, so the caption is stranded even
   inside a block) and BAC #113 (unresolved value span at (39, 3)) fall back with or without the guard; JPM #137-#139
   and UNH #38 likewise. Spec B alone does not export them.
10. **Writer and result contract.** `render_workbook` writes one heading row and `CopyTable = A2:…` spanning units,
    header and body. Per-block header rows inside the body change: the heading style of body-area rows, `CopyTable`
    meaning (one range containing several header rows, or one range per block), `WorksheetResult.copy_range` (one
    string), the accuracy test's `top + 2 + row` arithmetic, and every audit script that reads `headers[ci]` for
    every row. `XlsxTableResult` and completeness findings stay keyed by ordinal and are unaffected if the table
    stays one sheet.
11. **Interaction with the in-flight value-accuracy spec** (`docs/superpowers/specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md`,
    revision 2): its percent and identifier decisions read `headers[index]` per column (`_numeric_role`,
    `_identifier_column`). With per-block headers the role must be decided per block, or a heading that differs
    between blocks (META's AOCI `Loss`/`Income`) is read from block 1 only. The untracked draft
    `docs/superpowers/specs/2026-10-12-sec2md-xlsx-period-rows-design.md` (revision 1, layered on revision 5) also
    claims "never put a second period block under the first block's header" as its goal 3; the two specs overlap.
12. **Unrecognised captions are not covered.** The guard (and any block rule built on `_period_row`) misses captions
    such as `Q1 2025` or `FY2024` (documented in `docs/usage/xlsx-export.md:93-95`); a stacked table with such
    captions is not in this inventory and would still sit under block 1's header if the extension accepted it.

## Appendix: other guard firings

#### Stranded, one block (90)

- BABA-20-F-2025-06-26 #40 (needs_review): r4 `For the year ending March 31,`
- BABA-20-F-2025-06-26 #65 (needs_review): r4 `For the year ending March 31,`
- BAC-10-K-2025-02-25 #18 (source_text_only): r4 `(Dollars in millions) | 2024 | 2023`
- BAC-10-K-2025-02-25 #92 (source_text_only): r3 `(Dollars in millions) | December 31, 2024`
- BAC-10-K-2025-02-25 #93 (source_text_only): r3 `(Dollars in millions) | December 31, 2023`
- BAC-10-K-2025-02-25 #134 (source_text_only): r4 `(Dollars in millions) | 2024 | 2023`
- CAT-10-K-2025-02-14 #19 (source_text_only): r3 `2024 | 2023 | 2022`
- CAT-10-K-2025-02-14 #36 (source_text_only): r3 `2024 | 2023 | 2022`
- CAT-10-K-2025-02-14 #49 (source_text_only): r2 `(Millions of dollars) | 2024 | 2023`
- CAT-10-K-2025-02-14 #60 (source_text_only): r2 `(Millions of dollars) | 2024 | 2023`
- CAT-10-K-2025-02-14 #61 (source_text_only): r2 `(Millions of dollars) | Useful Lives (Years) | 2024`
- CAT-10-K-2025-02-14 #70 (source_text_only): r2 `(Millions of dollars) | 2024 | 2023`
- CAT-10-K-2025-02-14 #72 (source_text_only): r2 `(Millions of dollars) | 2024 | 2023`
- CAT-10-K-2025-02-14 #73 (source_text_only): r2 `(Millions of dollars) | 2024 | 2023`
- CAT-10-K-2025-02-14 #82 (source_text_only): r2 `(Millions of dollars) | 2024 | 2023`
- CAT-10-K-2025-02-14 #84 (source_text_only): r2 `(Millions of dollars) | Effective Yield to Maturity 1 | 2024`
- CAT-10-K-2025-02-14 #85 (source_text_only): r2 `(Millions of dollars) | 2025 | 2026`
- CAT-10-K-2025-02-14 #97 (source_text_only): r3 `(Millions of dollars) | 2024 | 2023`
- GOOGL-10-Q-2025-10-30 #41 (source_text_only): r3 `AOCI Components | Location | 2024`
- JPM-10-K-2025-02-14 #37 (source_text_only): r2 `(in millions, except ratios) | 2024 | 2023`
- JPM-10-K-2025-02-14 #38 (source_text_only): r2 `(in millions, except ratios) | 2024 | 2023`
- JPM-10-K-2025-02-14 #81 (source_text_only): r2 `(in millions, except interest  | 2024 | 2023`
- JPM-10-K-2025-02-14 #90 (source_text_only): r3 `(in millions, except ratios) | 2024 | 2023`
- JPM-10-K-2025-02-14 #106 (source_text_only): r3 `(in millions, except ratios) | 2024 | 2023`
- JPM-10-K-2025-02-14 #152 (source_text_only): r2 `December 31, (in billions) | 2024 | 2023`
- JPM-10-K-2025-02-14 #163 (source_text_only): r2 `Year ended December 31, (in mi | 2024 | 2023`
- JPM-10-K-2025-02-14 #190 (source_text_only): r2 `2024 | 2023`
- JPM-10-K-2025-02-14 #205 (source_text_only): r3 `(in millions, except ratios) | 2024 | 2023`
- JPM-10-K-2025-02-14 #206 (source_text_only): r3 `(in millions, except ratios) | 2023 | 2022`
- JPM-10-K-2025-02-14 #212 (source_text_only): r3 `Year ended December 31, (in mi | 2024 | 2023`
- JPM-10-K-2025-02-14 #214 (source_text_only): r2 `December 31, (in millions, exc | 2024 | 2023`
- JPM-10-K-2025-02-14 #215 (source_text_only): r2 `(in millions) | December 31, 2024`
- JPM-10-K-2025-02-14 #216 (source_text_only): r2 `(in millions) | December 31, 2023`
- JPM-10-K-2025-02-14 #217 (source_text_only): r2 `(in millions) | December 31, 2024`
- JPM-10-K-2025-02-14 #218 (source_text_only): r2 `(in millions) | December 31, 2023`
- JPM-10-K-2025-02-14 #219 (source_text_only): r2 `(in millions) | December 31, 2024`
- JPM-10-K-2025-02-14 #220 (source_text_only): r2 `(in millions) | December 31, 2023`
- JPM-10-K-2025-02-14 #221 (source_text_only): r2 `December 31, (in millions, exc | 2024 | 2023`
- JPM-10-K-2025-02-14 #222 (source_text_only): r2 `December 31, (in millions) | 2024 | 2023`
- JPM-10-K-2025-02-14 #223 (source_text_only): r2 `December 31, (in millions) | 2024 | 2023`
- JPM-10-K-2025-02-14 #230 (source_text_only): r3 `(in millions) | Year ended December 31, 2024 | Year ended December 31, 2023`
- JPM-10-K-2025-02-14 #231 (source_text_only): r3 `(in millions) | Year ended December 31, 2024 | Year ended December 31, 2023`
- JPM-10-K-2025-02-14 #247 (source_text_only): r2 `As of or for the year ended De | 2024 | 2023`
- JPM-10-K-2025-02-14 #296 (source_text_only): r2 `(in millions) | Fair value purchase price allo`
- KO-10-K-2025-02-20 #40 (source_text_only): r2 `Derivatives Designated as Hedg | Financial Statement Line Item  | December 31, 2024`
- KO-10-K-2025-02-20 #41 (source_text_only): r2 `Derivatives Not Designated as  | Financial Statement Line Item  | December 31, 2024`
- KO-10-K-2025-02-20 #44 (source_text_only): r3 `Balance Sheet Location of Hedg | December 31, 2024 | December 31, 2023`
- KO-10-K-2025-02-20 #63 (source_text_only): r2 `Year Ended December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #64 (source_text_only): r2 `December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #67 (source_text_only): r2 `December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #68 (source_text_only): r2 `Year Ended December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #69 (source_text_only): r2 `Year Ended December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #70 (source_text_only): r2 `December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #71 (source_text_only): r2 `December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #72 (source_text_only): r2 `Year Ended December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #83 (source_text_only): r2 `2024`
- KO-10-K-2025-02-20 #85 (source_text_only): r2 `2022`
- KO-10-K-2025-02-20 #89 (source_text_only): r2 `Year Ended December 31, | 2024 | 2023`
- KO-10-K-2025-02-20 #96 (source_text_only): r2 `Year Ended December 31, 2024`
- KO-10-K-2025-02-20 #98 (source_text_only): r2 `Year Ended December 31, 2022`
- MSFT-10-K-2025-07-30 #32 (needs_review): r4 `June 30, 2025`
- MSFT-10-K-2025-07-30 #33 (needs_review): r4 `June 30, 2024`
- MSFT-10-K-2025-07-30 #34 (needs_review): r7 `June 30, 2025`
- MSFT-10-K-2025-07-30 #35 (needs_review): r7 `June 30, 2024`
- MSFT-10-K-2025-07-30 #36 (needs_review): r4 `June 30, 2025`
- MSFT-10-K-2025-07-30 #38 (needs_review): r5 `June 30, 2025 | June 30, 2024`
- MSFT-10-K-2025-07-30 #47 (source_text_only): r4 `June 30, | 2025 | 2024`
- MSFT-10-K-2025-07-30 #48 (source_text_only): r4 `Year Ended June 30, | 2025 | 2024`
- MSFT-10-K-2025-07-30 #64 (source_text_only): r4 `Year Ended June 30, | 2025 | 2024`
- NTRA-10-K-2025-02-28 #32 (needs_review): r3 `Year ending December 31:`
- NTRA-10-K-2025-02-28 #43 (needs_review): r2 `2024 | 2023 | 2022`
- SPCX-10-Q-2026-08-04 #51 (needs_review): r4 `(in gigawatts) | June 30, 2026 | June 30, 2025`
- TSLA-10-K-2025-01-30 #35 (source_text_only): r2 `Consolidated Balance Sheets (u | March 31, 2024 | June 30, 2024`
- TSM-20-F-2025-04-17 #29 (source_text_only): r2 `Function | 2022 | 2023`
- TSM-20-F-2025-04-17 #30 (source_text_only): r2 `Location of Facility and Princ | 2022 | 2023`
- TSM-20-F-2025-04-17 #59 (needs_review): r2 `Name of Investor | Name of Investee | Main Businesses and Products`
- TSM-20-F-2025-04-17 #72 (source_text_only): r3 `Hedging Instruments/Hedged Ite | 2023 | 2024`
- TSM-20-F-2025-04-17 #78 (needs_review): r2 `Name of Associate | Principal Activities | Incorporation and Operation`
- TSM-20-F-2025-04-17 #105 (needs_review): r2 `December 31, 2023 | December 31, 2024`
- TSM-20-F-2025-04-17 #108 (needs_review): r7 `Resolution date of TSMC’s Boar | May 10, 2022 | August 9, 2022`
- TSM-20-F-2025-04-17 #109 (needs_review): r7 `Resolution date of TSMC’s Boar | May 9, 2023 | August 8, 2023`
- TSM-20-F-2025-04-17 #110 (needs_review): r7 `Resolution date of TSMC’s Boar | May 10, 2024 | August 13, 2024`
- TSM-20-F-2025-04-17 #155 (needs_review): r5 `December 31, 2023`
- UNH-10-K-2025-02-27 #9 (source_text_only): r2 `(in millions, except percentag | 2024 | 2023`
- UNH-10-K-2025-02-27 #10 (source_text_only): r2 `(in millions, except percentag | 2024 | 2023`
- UNH-10-K-2025-02-27 #11 (source_text_only): r2 `(in millions, except percentag | 2024 | 2023`
- UNH-10-K-2025-02-27 #12 (needs_review): r2 `(in thousands, except percenta | 2024 | 2023`
- UNH-10-K-2025-02-27 #13 (source_text_only): r2 `(in millions) | 2024 | 2023`
- UNH-10-K-2025-02-27 #39 (source_text_only): r2 `(in millions, except percentag | 2024 | 2023`
- UNH-10-K-2025-02-27 #52 (needs_review): r2 `2024 | 2023 | 2022`
