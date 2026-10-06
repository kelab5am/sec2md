# Table-merge and header-rules evidence

Date: 2026-10-04. Evidence for the "table-merge and header-rules" spec, which will fix the Markdown table renderer `src/sec2md/table_parser.py` (`TableParser`). This report measures and catalogues; it does not design the fix.

- **Code measured:** the main checkout at `2f039c4`, unchanged. Nothing under `src/` or `tests/` was edited. `TableParser` is instrumented from a script (a recording subclass swapped into `sec2md.parser`).
- **Corpus:** the Phase A corpus, 109 documents, loaded with `documents()` from [`../2026-10-03-table-completeness-corpus/corpus_phase_a.py`](../2026-10-03-table-completeness-corpus/corpus_phase_a.py):
  - 7 fixtures;
  - 32 RCQ primaries and 52 RCQ exhibits from `E:\RCQWealth` (read-only);
  - 18 EDGAR documents from `outputs/table-completeness-corpus`.

  Normal rendering mode.
- **Table numbers** are `check_tables` unit ordinals (visible outermost tables in document order), the same numbers as `results.json` and `classification.md`.
- **Background:** the 2026-10-02 audit (findings #1, #8, #9, the split-negative bullet), the completeness spec ("Phase A corpus run", "Round 6 rulings") and the Phase A [`classification.md`](../2026-10-03-table-completeness-corpus/classification.md) (G1, G2, G5, the BABA/TSM shift).

| File | What it is |
|---|---|
| `trace_merge.py` | The recording `TableParser` subclass and `shadow()`, a stage-by-stage replay of `TableParser` that tracks where every source cell's text goes. |
| `corpus.py` | Loads the corpus through `corpus_phase_a.documents()` and traces one document: one record per unit, with `header_row_count`. |
| `measure.py` | The detectors for classes 1–8. Writes `events.json`. |
| `summarize.py` | Prints every figure in this report from `events.json`, `results.json` and `classification.md`. |
| `inspect_table.py` | Shows one table's raw grid (with colspans), each stage's result and its Markdown. |
| `events.json` | Per-unit events from the run behind this report (3.5 MB, regenerable). |

Run from the repository root. On a Windows console, set `PYTHONIOENCODING=utf-8`.

```bash
python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/measure.py --edgar-cache outputs/table-completeness-corpus --out docs/superpowers/audits/2026-10-04-table-merge-header-evidence/events.json
python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/summarize.py --events docs/superpowers/audits/2026-10-04-table-merge-header-evidence/events.json --examples
python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/inspect_table.py "edgar:BABA-20-F-2025-06-26.htm" 24
```

## Summary

**Tables.** The 109 documents hold 5,332 units:

- **3,707 rendered by `TableParser`** in 104 documents. This report is about these.
- **1,042 rendered by `Parser._one_row_table_to_text`** in 65 documents (class 7).
- **583 with no output.** These are page headers and footers that the parser discards before rendering (Phase A cause G4). They are out of scope.

**Validation.**

- The replay reproduces the parser's Markdown exactly for all 3,707 tables.
- The run's check-1 value findings equal `results.json` in 109 of 109 documents, so this is the Phase A baseline.
- Only two `TableParser` stages drop source text in this corpus: the legacy merge's row-0 rule (class 1, 609 cells) and `_clean_empty_rows_and_cols` (class 6, 75 cells). The structural pass drops nothing.

In the table, **check-1** is the number of the class's tables that have a Phase A check-1 value failure with output.

| Class | Tables | Docs | Check-1 | Headline |
|---|---|---|---|---|
| 1 Legacy merge drops row-0 text | **469** | 47 | 294 | 609 cells, 369 of them with digits. Header row by `header_row_count`: 183 tables / 21 docs. Not a header row: 286 / 44. Of those, row 0 holds an amount in 25 / 15 (G2). |
| 2 Complementary value columns fused (different sibling headers) | **1** | 1 | 1 | TSM 248 only. Non-amount columns fused across different headers: 37 / 22 (mostly exhibit-index X marks). Headerless cases that cannot be judged: 43 / 19 (the reviewed ones were legitimate). |
| 3 Spanning header on a marker column, not over its amount | **43** | 4 | 1 | The only marker first column in the corpus is `$`: 142 header cells. None shifts over another span's values. NTRA's 32 tables come from U+200B cells. |
| 3, empty-slot variant (BABA/TSM shape) | **138** | 10 | 103 | The span's first grid column has no body content. Over another span's values: **107 / 8**. Not only BABA and TSM: also JPM, BAC, RDDT and MSFT. |
| 4 Non-`$` currency column separate from its amounts | **1** | 1 | 0 | No per-row €, £, RMB, NT$ or DKK columns exist. Those currencies appear only as header-row labels. `$` columns left separate: 48 / 4. |
| 5 Header fusion swallows a data row | **29** | 19 | 2 | 1,962 tables fuse rows 0 and 1. |
| 5 Header rows k ≥ 3 rendered as body | **244** | 27 | 10 | 249 rows: 241 unit lines, 8 period rows. |
| 5 Second header row rendered as body (no fusion) | **129** | 32 | 2 | 94 unit lines, 32 period rows, 3 other. |
| 6 Header-only column dropped | **37** | 30 | 0 | 63 header strings: 19 signature blocks, 14 exhibit-index columns, 3 `(a)` heads, 1 TSM value header. |
| 7 One-row tables: PART branch drops cells | **1** | 1 | 1 | CAT 7. Of the 1,042 one-row units: join 888, ITEM 45 (none drop a cell), PART 1, empty 108. 23 tables / 19 docs flatten 2 or more amounts into one unlabelled line. |
| 8 Split negatives left split | **80** | 4 | 36 | 180 cells. In 50 tables / 4 docs, the `)` column also holds another period's `$` or sits under another period's header. |
| (extra) U+200B-only cells treated as content | 48 | 1 | 0 | NTRA. They block every merge. |

## Notation

**Source rows** list `TableParser`'s cells for one row, left to right:

- `[csN]` is a colspan of N.
- `·` is an empty cell; `·×N` is N empty single cells.
- `rN` is the raw-grid row.

**Output** is an excerpt of the table's Markdown as `Parser` emits it today. Long links are shortened with `…`.

## 1. Legacy merge drops row-0 text

**What is counted.** In the greedy pass of `_merge_grid`, the column being absorbed loses its non-empty row-0 cell (`merged = [current_col[0]]`, line 629). Row 0 is the first non-empty row after `_clean_grid`.

**Counts.** 469 tables in 47 documents, 609 dropped cells. 369 of the cells contain digits; 240 hold words only.

| Row 0 is… | Tables / docs | Cells | Dropped kinds |
|---|---|---|---|
| a header row (`header_row_count` ≥ 1) | 183 / 21 | 208 | 206 period headers ("Jan 26, 2025", "Year ended March 31,"); 2 U+200B |
| not a header row, and holds an amount (the data split) | 25 / 15 | 42 | 41 amounts, 1 `$` |
| not a header row, and holds no amount | 261 / 43 | 359 | 94 period captions, 252 text, 5 dashes, 2 amounts, 6 U+200B |

**Why the third row is large.** `header_row_count` is 0 for 2,137 of the 3,707 tables, so many genuine captions and period headers fall outside "header". Examples: BAC's "Table N \| caption" rows, TSM 79's "For the year ended December 31,", and CRM's "Fiscal Year Ended January 31,". The third row also holds:

- signature lines ("/s/ Ernst & Young LLP" in NFLX 27, "/s/ Christopher Zaetta" in UNH 74);
- column headers ("Filed Herewith"; AAPL 13's "Approximate Dollar Value of Shares…");
- whole paragraph cells (two META award-agreement exhibits).

**Where.** TSM 101 tables, META 79, BABA 61, RDDT 59, BAC 48, MSFT 27, CRM 22, TSLA 12, JPM 10, with smaller counts elsewhere.

**Example 1a: the row is a header row.** `rcq:NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm`, table 18 (`header_row_count` 2, Phase A G1). "Jan 26, 2025" is dropped, and the second "Less than 12 Months" moves one column left.

```
source r1 |  [cs3] | Apr 27, 2025 [cs9] |  [cs3] | Jan 26, 2025 [cs9]
source r2 |  [cs3] | Less than 12 Months [cs9] |  [cs3] | … | Less than 12 Months [cs9] | …
source r3 |  [cs3] | Estimated Fair Value [cs3] |  [cs3] | Gross Unrealized Loss [cs3] | … | Estimated Fair Value [cs3] | … | Gross Unrealized Loss [cs3] | …
output    |  | Apr 27, 2025 — Less than 12 Months | Less than 12 Months |  |  |
          | --- | --- | --- | --- | --- |
          |  | Estimated Fair Value | Gross Unrealized Loss | Estimated Fair Value | Gross Unrealized Loss |
          | Debt securities issued by the U.S. Treasury | $ 6,854 | $ ( 4 ) | $ 6,315 | $ ( 22 ) |
```

**Example 1b: the row is not a header row; a caption is lost.** `edgar:CRM-10-K-2025-03-05.htm`, table 26 (`header_row_count` 0, G1).

```
source r1 | 4 [cs3] |  [cs3] |  [cs3] | Fiscal Year Ended January 31, [cs15]
source r2 |  [cs3] | … | 2025 [cs3] |  [cs3] | 2024 [cs3] |  [cs3] | 2023 [cs3]
output    | 4 | 2025 | 2024 | 2023 |
```

`edgar:BAC-10-K-2025-02-25.htm` table 88 is the caption form. "Table 10 \| Bank of America Corporation Regulatory Capital under Basel 3 [cs12]" keeps only "Table 10".

**Example 1c: row 0 is data, and its amounts are lost (G2).** `edgar:JPM-10-K-2025-02-14.htm`, table 109.

```
source r1 | Noninterest revenue – reported (c) [cs3] | $ | 84,973 | · | $ | 68,837 | · |  [cs3] | $ | 61,985 | · |  [cs3]
output    | Noninterest revenue –  reported (c) | $ | $ | $ |
          | --- | --- | --- | --- |
          | Fully taxable-equivalent adjustments (c) | 2,560 | 3,782 | 3,148 |
```

`edgar:TSLA-10-K-2025-01-30.htm` table 38 is the smallest case: "Beginning balance at fair value [cs3] \| $ \| 487" renders as `| Beginning balance at fair value | $ |`.

**A correct rendering would preserve** every row-0 cell's text in the output column or columns its span covers: a caption or period header stays over the columns it spans, and a first-row amount stays in its row beside its `$`.

## 2. Complementary value columns fused

**What is counted.** A legacy merge step joins column B into group A when, in the body rows (below the header zone), A and B each hold content in rows where the other is empty.

- **Kinds.** A step is "value+value" when both sides hold only amounts, dashes or fragments, with at least one amount each.
- **Header evidence.** Each side's columns get the lowest header-zone cell with header-like text whose span covers them. The keys are:
  - *same header*: the two sides share a key;
  - *sibling headers*: different cells in one header row, such as "2024" and "2023", or "Debit" and "Credit";
  - *nested*: different cells at different depths;
  - *no header*: at least one side has no key.

**Counts.** 7,512 merge steps join columns with complementary body content. 6,616 of them are value+value under the **same header** (in more than 1,800 tables). These steps are correct: the source puts a `$` row's amount one grid column right of the other rows' amounts, or offsets a few rows (AAPL 15, BAC 336, KO 18, KO 100, CRM 64).

| Bucket | Tables / docs | Verdict |
|---|---|---|
| value+value under sibling headers | **1 / 1** (TSM 248) | harmful: confirmed |
| value+value with no or nested header evidence | 43 / 19 | Not decidable mechanically. 7 reviewed (AAPL 32, CRM 64, KO 100, JPM 109, BAC 336, CAT 92, CAT 97): all were the same logical column. 21 of the 43 are the headerless `$`-row-offset tables that also lose a row-0 amount (class 1, G2). |
| non-amount content under different headers | 37 / 22 | 24 exhibit indexes whose X marks fuse into "Number", "Filing Date" or "Form" (RDDT 13, META 7, CRM 2, MU 1, NFLX 1); 4 RDDT equity statements whose mid-table "Class B" and "Amount" sub-headers land in value columns; 3 JPM footnote-marker columns ("(c)", "(g)") fused with amounts; 3 stacked-section labels (BAC 232, 237; JPM 373); BAC 336 (a source offset, legitimate); MSFT 6 (contents page); TSM 487 (repeated stacked headers) |

The audit's #9 Debit/Credit example was a synthetic repro. No period-versus-period amount fusion occurs in this corpus.

**Example 2a: a note reference lands in an amount column.** `edgar:TSM-20-F-2025-04-17.htm`, table 248 (`header_row_count` 0, G1). The Notes column fuses with the 2022 amounts. The "2022" header itself is dropped (class 1).

```
source r1  | ·×2 | Notes | · | 2022 [cs2] | ·×2 | 2023 [cs2] | ·×2 | 2024 [cs6] | ·
source r2  | ·×4 | NT$ [cs2] | ·×2 | NT$ [cs2] | ·×2 | NT$ [cs2] | ·×2 | US$ [cs2] | ·
source r5  | Gain (loss) on hedging instruments | ·×3 | $ | 1,329.2 | ·×2 | $ | ( 74.7 | ) | · | $ | ( 80.2 | ) | · | $ | ( 2.4 | )
source r35 | EARNINGS PER SHARE | · | 27 | ·×16
output     |  | Notes — NT$ | 2023 — NT$ | 2024 — NT$ | US$ |
           | Gain (loss) on hedging instruments | $ 1,329.2 | $ ( 74.7) | $ ( 80.2) | $ ( 2.4) |
           | EARNINGS PER SHARE | 27 |  |  |  |
```

**Example 2b: X marks fuse into another column.** `rcq:RDDT__10-Q__2024-Q2__c-63xzxqtyzzhgyhto__s-000171344524000054.htm`, table 52 (D3 sample #5). The header "Filed Herewith" is dropped (class 1), and its X marks merge into "Number".

```
source r1 | Exhibit Number [cs3] |  [cs3] | Exhibit Description [cs3] |  [cs3] | Incorporated by Reference [cs15] |  [cs3] | Filed Herewith [cs3]
source r2 |  [cs3] | … | Form [cs3] |  [cs3] | Filing Date [cs3] |  [cs3] | Number [cs3] | …
source r9 | 31.1 [cs3] |  [cs3] | [Certification of Principal Executive Officer …] [cs3] | … |  [cs3] | X [cs3]
output    | Exhibit Number | Exhibit Description | Incorporated by Reference — Form | Filing Date | Number |
          | 4.3 | [Form of Class B Common Stock Certificate](…) | S-8 | 3/21/2024 | 4.6 |
          | 31.1 | [Certification of Principal Executive Officer …](exhibit311q224.htm) |  |  | X |
```

**Contrast 2c: a legitimate fusion.** `fixture:aapl-2023-10k`, table 15.

- In the "$" rows, the amount sits in grid column 4 beside a `$` in column 3.
- In the other rows, it is `94,294 [cs2]` from column 3.
- Both are under "2023 [cs3]". The merged `| Americas | $ 162,560 |` and `| Europe | 94,294 |` are right.

**A correct rendering would preserve** two source columns that sit under different headers as separate output columns, so that no value, note number or X mark is read under a sibling column's header.

## 3. Spanning header on a marker or currency column

**What is counted.** For every header-zone cell with header-like text over value columns, the detector compares:

- the output column its text lands in, with
- the output columns that hold the body values of its own span.

The statuses are:

- **aligned**: the header is over its own values.
- **detached**: it is over a column with no values at all, such as a `$`, `)` or label column.
- **shifted**: it is over another span's values.
- **caption moved**: it spans every value column and lands in the label column; this is benign.
- **dropped**: class 1 or 6 removed it.

The **first slot** is the body content of the span's first grid column.

| First slot of a spanning header | Header cells | aligned | detached | shifted | caption moved | dropped |
|---|---|---|---|---|---|---|
| `$` marker column | 2,177 | 1,991 | **142** | 0 | 38 | 6 |
| any non-`$` currency column | 1 (US$) | 0 | 0 | 0 | 0 | 1 |
| empty in the body (currency slot or spacer) | 1,053 | 87 | **216** | **272** | 66 | 412 |
| a value column | 12,873 | 12,872 | 0 | 0 | 0 | 1 |

Single-column headers over values (368) are never misplaced.

**Class 3 as defined:** spanning header on a marker column, not over its amount.

- **Counts.** 43 tables in 4 documents: NTRA 32, MSFT 5, TSM 5 and nvda-2002 138.
- **Every case is a `$` column.** The corpus has no €, £, RMB, NT$, US$ or DKK per-row marker column (class 4).
- **None is shifted.** The header always sits over the `$` cell, with its amount one column right under a blank header.
- **NTRA's 32 come from U+200B cells** (see "Further findings").

The other cases have two causes:

- **A year in the `$` column** (MSFT 24, TSM 312). `_body_start` stops at the first row with a numeric fragment, and a bare year counts as one. The year cell then sits in the body of the `$` column, so `_classify_structural_column` rejects that column. The legacy pass then attaches the `$` to the previous period's group.
- **Leading-dot decimals** (nvda-2002 138). The per-share values `.75` and `.62` fail `_is_numeric_fragment`, so the structural pass rejects every `$` column of the table.

**The BABA 24 / TSM 79 / TSM 312 shape is the empty-slot variant, not a marker column.**

- **Mechanism.** The year spans two grid columns, and the first is empty in the body. In BABA, a currency slot that only a header-row "RMB" uses; in TSM 312, a spacer. That slot merges left into the previous group (labels, "Notes", or the previous period's `%` or `)` column) and carries the year with it.
- **Counts.** 138 tables in 10 documents have a header not over its own values. 107 tables in 8 documents have one over another span's values (shifted).

| Document | Detached or shifted | Shifted |
|---|---|---|
| BABA | 58 | 51 |
| TSM | 56 | 43 |
| JPM | 8 | 3 |
| BAC | 7 | 4 |
| RDDT | 4 | 4 |
| MSFT | 3 | 2 |
| GOOGL | 1 | 0 |
| NTRA | 1 | 0 |

**Visibility to the checks.**

- Check 1 flags 103 of the 138 tables, and only for the lost caption (`31`). The other 35 have no check-1 finding.
- Across all 178 tables with any header off its values, 75 have no check-1 value finding.

**Example 3a: `$` first slot, header detached (the income statement).** `edgar:MSFT-10-K-2025-07-30.htm`, table 24. FY2024 and FY2023 revenue sit under blank headers, and "2024" heads a column that is empty except for `$`.

```
source r4 | Year Ended June 30, | · | 2025 [cs2] | ·×2 | 2024 [cs2] | ·×2 | 2023 [cs2] | ·
source r7 | Product | · | $ | 63,946 | ·×2 | $ | 64,773 | ·×2 | $ | 64,699 | ·
source r8 | Service and other | ·×2 | 217,778 | ·×3 | 180,349 | ·×3 | 147,216 | ·
output    | (In millions, except per share amounts) — Year Ended June 30, | 2025 | 2024 |  | 2023 |  |
          | --- | --- | --- | --- | --- | --- |
          | Product | $ 63,946 | $ | 64,773 | $ | 64,699 |
          | Service and other | 217,778 |  | 180,349 |  | 147,216 |
```

**Example 3b: empty first slot, shifted (the BABA 24 shape).** `edgar:BABA-20-F-2025-06-26.htm`, table 24. FY2023 revenue sits under "2024", FY2024 under "2025", and FY2025's 996,347 under a blank header.

```
source r1 | ·×3 | Year ended March 31, [cs14] | ·
source r2 | ·×3 | 2023 [cs2] | ·×2 | 2024 [cs2] | ·×2 | 2025 [cs6] | ·
source r3 | ·×3 | RMB [cs2] | ·×2 | RMB [cs2] | ·×2 | RMB [cs2] | ·×2 | US$ [cs2] | ·
source r7 | Revenue | 5, 24 | ·×2 | 868,687 | ·×3 | 941,168 | ·×3 | 996,347 | ·×3 | 137,300 | ·
output    |  | 2023 | 2024 | 2025 |  |  |
          | --- | --- | --- | --- | --- | --- |
          |  | RMB | RMB | RMB | US$ |  |
          | Revenue | 5, 24 | 868,687 | 941,168 | 996,347 | 137,300 |
```

**Example 3c: the same shift outside BABA and TSM.** `edgar:JPM-10-K-2025-02-14.htm`, table 482.

- A "(b)(c)" footnote cell takes its own output column, and each later segment header shifts one column left of its values.
- "Wholesale" sits over credit card's `$ —`, and "Total" over wholesale's 1,432.
- The total, 2,079, has no header.

```
source r2 | Year ended December 31, (in millions) [cs3] |  [cs3] | Consumer, excluding credit card [cs9] | Credit card [cs9] | Wholesale [cs9] | Total [cs6]
source r3 | Purchases [cs3] |  [cs3] |  [cs3] | $ | 647 | · | (b)(c) [cs3] |  [cs3] | $ | — | · |  [cs3] |  [cs3] | $ | 1,432 | · |  [cs3] |  [cs3] | $ | 2,079 | ·
output    | Year ended December 31, (in millions) | Consumer, excluding credit card | Credit card | Wholesale | Total |  |
          | --- | --- | --- | --- | --- | --- |
          | Purchases | $ 647 | (b)(c) | $ — | $ 1,432 | $ 2,079 |
```

The same shift occurs in:

- `rcq:RDDT__10-Q__2024-Q2__…` table 17: "2023" over 2024's Class B share counts;
- MSFT 65: "2024" over FY2025's repurchase amounts;
- TSM 79: "2022" over the row labels and "2023" over 2022's `%` column.

**A correct rendering would preserve** each spanning header over the output columns that hold its own span's values. A `$` or currency marker joins its amount instead of taking the header.

## 4. Non-`$` currency columns

**What is counted.** A data-zone grid column whose non-empty body cells are all currency markers. For each marker, the detector checks whether it lands in the same output cell as the next value to its right. The inventory counts every standalone currency cell.

**Inventory of standalone currency cells** (all 3,707 tables):

| Marker | Data rows | Header rows |
|---|---|---|
| `$` | 24,000 | 28 |
| `NT$` | 0 | 256 |
| `RMB` | 0 | 199 |
| `US$` | 1 | 27 |
| `HK$` | 0 | 2 |
| €, £, ¥, DKK, other ISO codes | 0 | 0 |

- **How the foreign issuers present currency.** TSM, BABA and NVO put the currency in a header row ("NT$", "RMB", "US$"), or in a caption ("DKK million"), never in a per-row marker column. Such a header-row label spans the amount column. Its first grid column is the empty slot of class 3.
- **Unknown short tokens.** Short tokens directly left of an amount that are not recognized as markers were inventoried too: dashes, U+200B (847, NTRA), "NA", "XML", "NM", ")%", "*", "AWS", "OTC" and segment codes. None is a currency.

**Counts.**

- **Non-`$` currency columns kept separate from their amounts:** 1 column in 1 table, TSM 344. There, a headerless bond table's first row is data, and its single "US$" cell stays in its own column.
- **`$` marker columns, for comparison:** 1,598. 1,479 join their amounts (514 tables, 52 docs). 119 stay separate (48 tables, 4 docs: NTRA 32, TSM 7, MSFT 6, nvda-2002 3). The causes are those in class 3: U+200B cells, a year in the `$` column, and leading-dot decimals.

**Example 4a: a `$` column left separate.** `fixture:nvda-2002-10k`, table 19.

```
source r0 | ·×2 | Year Ended [cs11] | ·×2 | Month Ended January 31, 1998 [cs2] | ·×2 | Year Ended December 31, 1997 [cs2] | ·
source r6 | Product | · | $ | 1,369,471 | · | $ | 735,264 | · | $ | 374,505 | · | $ | 151,413 | ·×2 | $ | 11,420 | ·×2 | $ | 27,280 | ·
output    | Product | $ 1,369,471 | $ 735,264 | $ 374,505 | $ 151,413 | $ | 11,420 | $ | 27,280 |  |
```

The two period headers over the last two `$` columns are also dropped (class 1, a pinned failure).

**Example 4b: the only non-`$` case.** `edgar:TSM-20-F-2025-04-17.htm`, table 344. A single data cell "US$" stays in its own column. Round 6's regression case, "euro and amount cells under spanning 2025/2024 headers", has no real instance in this corpus. It has to be synthetic.

**A correct rendering would preserve** the pairing of any currency marker, symbol or ISO code, with its amount in one output cell, in the same way as `$`, and put a header-row currency label over the amount column it spans.

## 5. Header row structure

**`header_row_count`** over the 3,707 tables. The second row of the table counts the non-empty header rows that remain after `_clean_grid`.

| Header rows | 0 | 1 | 2 | 3 | ≥ 4 |
|---|---|---|---|---|---|
| `header_row_count` | 2,137 | 72 | 696 | 472 | 330 |
| non-empty after `_clean_grid` | 2,137 | 786 | 540 | 240 | 4 |

**Fusion of rows 0 and 1.** 1,962 tables fuse them.

- 655 fuse two `header_row_count` header rows.
- 1,307 fuse a row 1 that `header_row_count` does not call a header (mostly tables where it is 0).
- **Fusion swallows a data row: 29 tables in 19 documents.** These are fused tables whose row 1 holds an amount: META 9, TSM 6, MU 4, JPM 2, MSFT 2, AAPL 1, nvda-2026-ex99-1 1, RDDT 1, CAT 1, KO 1, UNH 1.
- None of the 29 has a `header_row_count` header as row 1.
- check_tables' looser `is_data_row` would give 321. It calls header rows such as "2023 \| Change \| 2022" data, because bare years match its amount pattern.

**Header rows rendered as body rows.**

- **Rows k ≥ 3:** 244 tables in 27 documents, 249 rows: 241 unit lines ("(In millions)") and 8 period rows. By document: NVDA RCQ 102, RDDT 100, NFLX 13, nvda-2026-10k 11, nvda-2026-q2-10q 11, NTRA 6, CRDO 1.
- **The second header row, when fusion does not fire:** 129 tables in 32 documents: 94 unit lines, 32 period rows and 3 other.
- **Not counted here.** Tables whose header rows `header_row_count` misses (the 2,137 with 0, such as TSM 79) add nothing to either figure.

**Example 5a: fusion swallows a data row.** `fixture:aapl-2023-10k`, table 18 (the audit's #8).

```
source r1 | Gross margin percentage: [cs3] |  [cs3] | …
source r2 | Products [cs3] | 36.5 [cs2] | % |  [cs3] | 36.3 [cs2] | % |  [cs3] | 35.3 [cs2] | %
output    | Gross margin percentage: — Products | 36.5 % | 36.3 % | 35.3 % |
          | --- | --- | --- | --- |
          | Services | 70.8 % | 71.7 % | 69.7 % |
```

**Example 5b: fusion swallows a data row.** `rcq:META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm`, table 4. Class A's share count becomes part of the header line.

```
source r1 | Class [cs6] | Number of Shares Outstanding [cs6]
source r2 | Class A Common Stock [cs3] | $0.000006 par value [cs3] | 2,191,446,233 [cs2] | · | shares outstanding as of April 19, 2024 [cs3]
output    | Class — Class A Common Stock | $0.000006 par value | Number of Shares Outstanding — 2,191,446,233 | shares outstanding as of April 19, 2024 |
          | --- | --- | --- | --- |
          | Class B Common Stock | $0.000006 par value | 345,087,958 | shares outstanding as of April 19, 2024 |
```

**Example 5c: header rows in the body.** `fixture:nvda-2026-10k`, table 36 (`header_row_count` 4): the second header row is in the body. Table 17 is the k = 3 case: `| | Year Ended — Jan 25, 2026 | Jan 26, 2025 |`, then `| | (In millions) | |` as the first body row.

```
source r1 |  [cs3] | Jan 25, 2026 [cs3]
source r2 |  [cs3] | (In millions) [cs3]
output    |  | Jan 25, 2026 |
          | --- | --- |
          |  | (In millions) |
          | Less than one year | $ 20,427 |
```

**A correct rendering would preserve** the split between header rows and data rows. Every source header row stays in, or is marked as, the header, and no data row's values are promoted into the header line.

## 6. Header-only columns dropped

**What is counted.** `_clean_empty_rows_and_cols` removes a column that has no body content but has header-line text.

**Counts.** 37 tables in 30 documents. 63 header strings are lost, from 75 source cells. By kind: 37 text, 23 period, 3 footnote; 20 contain digits. All 37 tables are fused.

| Shape | Tables | Examples |
|---|---|---|
| Signature block | 19 | Header fusion pulls "Dated: May 7, 2024" or "October 29, 2025", and "By:", into the header, and their column has no body. META 2, RDDT 10, META exhibit 1, BABA 22, CRDO 61, GOOGL 89 and 90, MU 71, SPCX 70. |
| Exhibit-index column with no entries in this segment | 14 | "Incorporated by Reference — Form", "File No.", "Exhibit", "Filed Herewith", "Period Ending", "Notes" (AAPL 64, META ×5, RDDT 70, BAC 358, CRDO 59, GOOGL 87, MSFT 77–80) |
| `(a)` over a financial-statement index | 3 | nvda-2026-10k 20, NVDA RCQ 10-K 2024 t19 and 2025 t21 |
| Value-column header | 1 | TSM 344: "Total Issue Amount US$ (In Millions) — US$" |

**The audit's example is absent.** "A year over a blank spacer column" does not occur here. Such years are taken earlier, by the legacy merge (class 1 or class 3).

**Example 6a: a signature date is dropped.** `edgar:GOOGL-10-Q-2025-10-30.htm`, table 89.

```
source r1 |  [cs3] |  [cs3] | ALPHABET INC. [cs3]
source r2 | October 29, 2025 [cs3] | By: [cs3] | /s/    ANAT ASHKENAZI [cs3]
source r3 |  [cs3] |  [cs3] | Anat Ashkenazi [cs3]
output    | ALPHABET INC. — /s/    ANAT ASHKENAZI |
          | --- |
          | Anat Ashkenazi |
          | Senior Vice President, Chief Financial Officer |
```

**Example 6b: exhibit-index headers are dropped.** `fixture:aapl-2023-10k`, table 64. "Incorporated by Reference — Form", "Exhibit" and "Filing Date/ Period End Date" are dropped, because exhibit 104 has no entries under them.

```
source r1 |  [cs9] |  [cs3] | Incorporated by Reference [cs15]
source r2 | Exhibit Number [cs3] |  [cs3] | Exhibit Description [cs3] |  [cs3] | Form [cs3] |  [cs3] | Exhibit [cs3] |  [cs3] | Filing Date/ Period End Date [cs3]
output    | Exhibit Number | Exhibit Description |
          | --- | --- |
          | 104** | Inline XBRL for the cover page of this Annual Report on Form 10-K, included in the Exhibit 101 Inline XBRL Document Set. |
```

**A correct rendering would preserve** header text whose column is empty in the body, either as its own column or attached to the content it labels. A signature date stays in the output.

## 7. One-row tables

**How they are rendered.** `Parser._render_table` sends a table with at most one effective row (the rows with any text, `_effective_rows`) to `_one_row_table_to_text`, not to `TableParser`. It returns one line:

- **ITEM branch.** The first cell matches `^Item N.$`, and the method returns "ITEM N. <first non-empty later cell>". Further cells are dropped.
- **PART branch.** The first cell matches `^Part IV$`, and the method returns "PART IV". Every other cell is dropped.
- **Otherwise** it joins the non-empty cells with spaces. The column structure is lost; no text is.

**Counts.** 1,042 one-row units in 65 documents.

| Branch | Units | Units dropping a cell | Cells dropped |
|---|---|---|---|
| join | 888 | 0 | 0 |
| ITEM | 45 | 0 | 0 |
| PART | 1 | **1 (CAT 7)** | 1 (holds `2025` and `120`) |
| no text (0 effective rows) | 108 | 0 | 0 |

- **Cell counts.** 296 units have 2 cells, 306 have 3, 196 have 4, 2 have 5, and 51 have 6 or more.
- **Flattened data rows.** In 23 join tables in 19 documents, two or more amounts are flattened into one line with no column labels. Examples: META's "ARPP: $9.57 $9.87 …" and RDDT's "WAUq YoY Growth: (8)% (5)% …".
- **Phase A's other one-row loss.** The `get_text(" ")` inline-run split is G3, "March 3 1" (META exhibit a-5q6r23ydgpjcersy t26). It is a text-extraction issue, not a branch.

**Example 7a: PART drops a cell (G5).** `edgar:CAT-10-K-2025-02-14.htm`, table 7.

```
source  | Part III | 2025 Annual Meeting Proxy Statement (Proxy Statement) to be filed with the Securities and Exchange Commission (SEC) within 120 days after the end of the fiscal year.
output  PART III
```

**Example 7b: ITEM keeps its title.** `edgar:AMZN-10-Q-2025-10-31.htm`, table 9: "Item 1. \| Financial Statements" renders as "ITEM 1. Financial Statements".

**Example 7c: join flattens a data row.** `rcq:META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm`, table 33. "ARPP: \| $9.57 \| $9.87 \| …" renders as `ARPP: $9.57 $9.87 $9.44 $10.68 $9.47 $10.42 $10.93 $12.33 $11.20`.

**A correct rendering would preserve** every non-empty cell of a one-row table. The PART branch would keep the cells after "PART III", as the ITEM branch keeps the title.

## 8. Split accounting negatives

**What is counted.** An output body cell that holds an open-parenthesis amount ("(29", "( 72,818"), when the next source cell, ")" or ")%", ended up in a different output cell.

- **dedicated**: the `)` column holds only `)`, `)%` or `%` in its data rows.
- **shared**: it also holds other data, such as the next period's `$`.
- **headed**: another span's header text lands over it.

**Counts.** 180 cells in 80 tables in 4 documents.

- **By document:** TSM 35 tables, BABA 23, MSFT 13, nvda-2002 9.
- **None** is non-adjacent or dropped. `merge_split_negatives` re-joins all of them for check 1, so a split never produces a check-1 finding by itself.

| Kind | Cells | Tables |
|---|---|---|
| dedicated, unheaded (`(29 \| )`) | 89 | 61 |
| dedicated, under another period's header | 67 | 32 |
| shared (the `)` column also holds the next period's `$` ×22 or `—` ×2) | 5 | 3 |
| shared and under another period's header | 19 | 15 |

**Misaligned:** 50 tables in 4 documents (TSM 20, BABA 19, MSFT 8, nvda-2002 3) have a shared or headed `)` column.

**Why the `)` columns stay split.**

- `_classify_structural_column` needs at least two markers, so a column with one negative stays split (BABA 69).
- `)%` is not a structural marker (TSM 79).
- The class-3 causes reject the whole column: a year in the `$` column, leading-dot decimals, and U+200B.

**Example 8a: a dedicated split.** `fixture:nvda-2002-10k`, table 157.

```
source r1 | ·×2 | (in thousands) [cs6]
source r2 | Net operating loss carryforwards | · | $ | 141,882 | ·×2 | $ | 3,216
output    |  | January 27, 2002 |  | January 28, 2001 |
          | --- | --- | --- | --- |
          | Net operating loss carryforwards | $ 141,882 |  | $ 3,216 |
          | Less valuation allowance | (104,036 | ) | — |
```

**Example 8b: the `)` column under the next period's header.** `edgar:BABA-20-F-2025-06-26.htm`, table 69. There is one negative per column, so the structural pass skips it. 2024's `)` sits under "2025", and 2025's values sit under a blank header.

```
source r2 | ·×2 | 2024 [cs2] | ·×2 | 2025 [cs2] | ·
source r8 | Less: current portion | ·×2 | ( 72,818 | ) | ·×2 | ( 68,335 | )
output    | 2024 |  | 2025 |  |  |
          | --- | --- | --- | --- | --- |
          | Deferred revenue | 37,142 |  | 44,138 |  |
          | Less: current portion | ( 72,818 | ) | ( 68,335 | ) |
```

**Example 8c: the `)` column shares 2024's `$`.** `edgar:MSFT-10-K-2025-07-30.htm`, table 43.

```
source r4 | June 30, | · | 2025 [cs2] | ·×2 | 2024 [cs2] | ·
output    | (In millions) — June 30, | 2025 | 2024 |  |  |
          | Land | $ 9,338 | $ | 8,163 |  |
          | Accumulated depreciation | ( 93,653 | ) | ( 76,421 | ) |
```

**A correct rendering would preserve** each negative as one cell ("(29)" or "(3.2)%") in its amount's column. No other period's marker or header would share that column.

## Overlap between classes

Counts are tables in both classes. Classes 1h, 1d and 1-amount split class 1 by row 0. 3e is class 3's empty-slot variant. M is "any header not over its own values". 4$ is "`$` column left separate". 5u is "second header row in the body". Z is U+200B.

| Pair | Tables | Reading |
|---|---|---|
| 1 & 3e | 118 of 138 | The empty-slot shift nearly always comes with a dropped row-0 caption, which is the only thing check 1 sees. |
| 1 & 8 | 46 of 80 | The same TSM, BABA and MSFT statements. |
| 3e & 8 | 42 | |
| 3 & 4$ | 43 of 43 | Every class-3 table has a separate `$` column (same cause). |
| 3 & Z | 32 | The NTRA tables. |
| 1-amount & 2 (no header) | 21 of 25 | G2 tables are headerless `$`-row-offset tables. |
| 1d & 2 (non-amount) | 25 | Exhibit indexes: "Filed Herewith" dropped and its X marks fused. |
| 1d & 5f | 10 | |
| 1d & 6 | 12 | |
| 6 & 5f | 2 | |
| Z & 5u / Z & 5x | 12 / 6 | U+200B rows make extra header rows. |
| 2 (sibling) & 1d | 1 | TSM 248 |

## Mapping to the Phase A check-1 findings

There are 307 check-1 value tables with output in `results.json`. For the fixtures and the 20 META and RDDT primaries, classification.md has no per-table cause. The revision 6 evidence describes them as period headers and first-row values.

| Phase A cause | Tables | This report |
|---|---|---|
| G1, column merge drops row-0 text | 171 | **class 1: 171**. 85 have a header row 0 and 86 do not. 103 also show the class-3 empty-slot shift, 35 class 8, 2 class 5f, 1 class 3. |
| G2, column merge drops a first-row amount | 9 | **class 1 with an amount in row 0: 9** |
| Revision 6 review (fixtures, META, RDDT) | 114 | **class 1: 114.** 96 have a header row 0; 18 do not, 16 of them with an amount in row 0. |
| G3, inline-run space | 1 | one-row path (class 7, join) |
| G5, one-row PART | 1 | **class 7: CAT 7** |
| F1, F3, F5, F8 (false positives) | 11 | none of the classes |
| **Total** | **307** | |

**Coverage.** Class 1 accounts for every genuine check-1 value loss in `TableParser` output: 294 tables. The other 175 class-1 tables have no check-1 value finding. Their dropped text has no digits (240 cells hold words only), or its digits recur elsewhere in the table.

**Reported-only findings.**

- Class 6 explains the 40 absent reported references: 36 signature dates in 18 blocks, and RDDT 10-K 2024 t70's exhibit metadata.
- Class 1 explains the 14 absent TSM markers (108–130, "Bonus (2)" and similar).
- Of the 54 tables with reported tokens, 26 are in class 6 and 26 in class 1 (the two can overlap).

**What check 1 cannot see.**

- **Class 3 shifts:** 35 of the 138 empty-slot tables have no check-1 finding, and the other 103 are flagged only for the caption.
- **Class 5 fusion and header rows in the body:** a value on the header line counts as present, and check 2 skips header lines.
- **Class 8 splits:** they are re-joined on both sides.
- **Non-amount fusions** (class 2) and **class 6 drops:** class 6 drops are reported references at most.

## Fixtures affected

Changing any of these tables changes fixture Markdown. That affects:

- `tests/accuracy` (word, numeric and financial-row recall);
- `PINNED_FAILURES` and `TABLES_CHECKED` in `tests/test_table_completeness_fixtures.py`;
- `tests/golden/aapl_10k` (that suite skips without its cached HTML).

`tests/accuracy`' representative rows sit in unaffected tables, with one exception:

- nvda-2002's "Revenue" row is in table 19, which is affected. It also appears in the unaffected tables 130, 141 and 158.
- The nvda-2026-q2-10q "Revenue" row is also in tables 35 and 36, which are class 5 only.

| Fixture | Class 1 | Pinned failures (all class 1) | Other classes |
|---|---|---|---|
| aapl-2023-10k | 13, 32, 49, 53, 65 | 13 (header with plain-text "(1)"), 32, 49, 53 (row-0 amounts) | 5f: 18. 6: 64 (exhibit index). The class 2 no-header bucket, 32, 49, 53, is the G2 shape. 65 drops "Apple Inc." (signature). |
| nvda-2002-10k | 19, 131 | 19 ("Month Ended January 31, 1998", "Year Ended December 31, 1997") | 131 drops "Other Comprehensive Income/(Loss)". 3: 138. 4$: 19, 131, 138. 8: 19, 129, 131, 138, 139, 145, 152, 153, 157 (misaligned: 19, 131, 138). 5u: 153, 157. One-row: 123 join, 2 ITEM, none dropping. |
| nvda-2026-10k | none | none | 5x: 17, 26, 27, 30, 37, 45, 46, 47, 50, 54, 59. 5u: 16, 18, 36, 42, 43, 48, 50, 51, 52. 6: 20. One-row: 3 join. |
| nvda-2026-q2-10q | 31 | 31 (`$3.5` guarantees row, row-0 amount) | 5x: 14, 16, 21, 25, 26, 32, 34, 35, 36, 38, 47. 5u: 27, 46, 48. One-row: 3 join, 1 empty. |
| nvda-2026-08-26-8k | none | none | One-row: 1 join. |
| nvda-2026-ex99-1 | 8, 9 | 9 (operating cash-flow row, row-0 amounts) | 5f: 7. 8 drops "NVIDIA CORPORATION". |
| nvda-2026-ex99-2 | 7, 9, 10 | 7 (`$3.5`), 10 (operating cash-flow row) | 9 drops "NVIDIA CORPORATION". |

- **Where the shift and currency evidence is.** No fixture has the class-3 empty-slot shift, a non-`$` currency, or U+200B. The BABA, TSM, JPM, MSFT and NTRA evidence exists only in the EDGAR cache, which is not a test fixture.
- **Pinned failures.** All 10 pinned value failures are class 1. A row-0 fix would empty `PINNED_FAILURES` only if it restores those cells. aapl-2023-10k 13's `-1` is the plain-text "(1)" in the dropped header.

## Further findings (not in the eight classes)

1. **U+200B cells are content to `TableParser`.**
   - **Where.** NTRA, 48 tables, 847 cells next to amounts.
   - **Cause.** Python's `str.strip()` does not strip U+200B, so `GridCell.__bool__`, `_clean_grid` and `_should_merge_cells` treat those cells as text.
   - **Effect.** No column merges. `$` stays apart from its amount, and headers sit over the `$`. Rows of U+200B become a header line of invisible cells (NTRA 141).
2. **A bare year counts as body for the structural pass.** `_body_start` stops at the first row with a numeric fragment, and "2025" is one. When a year header starts on the `$` column, the column fails the uniform-marker test (MSFT 24 income statement, TSM 312).
3. **Leading-dot decimals block the structural `$` merge.** `.75` fails `_is_numeric_fragment`, which rejects the column for every row (nvda-2002 138).
4. **Single markers stay split.** `_classify_structural_column` needs two or more markers, so a column with one negative is never merged (BABA 69).
5. **The legacy merge is mostly right about values.** It correctly realigns 6,616 value-column pairs whose source cells are offset by colspan. The damage is to row 0 (class 1) and to header placement (class 3), not to body values. The one exception is TSM 248.

## Method and limits

**Replay.**

- `trace_merge.shadow()` replays `_clean_grid`, `_merge_structural_columns`, the greedy pass, `_process_headers`, `_clean_empty_rows_and_cols` and the Markdown writer.
- It calls `TableParser`'s own decision methods, and gives each raw-grid cell with text an origin. The final place of every origin is a header column, a body cell, or "dropped" with the stage that dropped it.
- **Validation.** For each table, the replayed Markdown is compared with the text the parser emitted: 3,707 of 3,707 equal. A change to `table_parser.py` would show up as mismatches before any count is trusted.
- **What it covers.** `TableParser` instances are matched to units by element identity. The citation-only `TableParser` renders of anchor-stripped copies in `_element_segment_content` are ignored.

**Header rows.**

- `header_row_count` comes from `sec2md.table_completeness`, over `unit_rows` and `grid_hidden`, as `check_tables` computes it. Its header rows are mapped to `TableParser` rows through the `tr` elements.
- `TableParser` reads rows from `find_all('tr')`, including hidden and nested rows. Those are never header rows.
- Where the count is 0 (2,137 tables, including any table with a nested table), "not a header row" includes real header rows. Class 1's third bucket and the class-5 figures inherit this.

**The body start.**

- **The rule.** The detectors' body (data zone) starts at the first raw-grid row with:
  - a cell holding an amount that is not a bare year and has two or more digits or a decimal point; or
  - a nil dash.
- **Why not `is_data_row`.** check_tables' `is_data_row` was too loose: it calls "2023 \| Change \| 2022" data.
- **Limits.** The body starts too late in a table whose first data rows hold only one-digit amounts or years. It starts too early when a header row carries such an amount.
- **What uses it.** The header-zone and data-zone split in classes 2, 3, 4 and 8, and "holds an amount" in classes 1 and 5.

**Visible text.** U+200B and U+FEFF are removed before the detectors classify text. The renderer does not remove them.

**Each class.**

- **Class 1** is exact: every legacy merge whose absorbed row-0 cell has text. A cell is counted as dropped even if the same text survives elsewhere, as a repeated caption can. Kinds come from cell text: period wording or a bare year, amount, dash, marker, or text.
- **Class 2** is judged by header keys.
  - "Sibling" requires both sides' keys to be distinct cells in one header row.
  - Tables without header cells over the value columns (43) cannot be decided. Only 7 were reviewed by hand.
  - Stacked tables with mid-table header rows are keyed against the top header zone only, so their fusions land in "nested" or "non-amount".
  - "Non-amount" means a side holds text, X marks or footnote references.
- **Class 3** checks header-zone cells with header-like text whose span holds body values.
  - **Skipped:** cells whose span includes a label column, a column whose body is text only; markers; footnote marks; non-year amounts.
  - **Values** are amounts, dashes and fragments, so a label column of years counts as values (BABA 67).
  - **"Caption moved"** is a span that covers every value column. It is reported but not counted.
  - **Mid-table headers in stacked tables** are not checked, so section-level shifts are under-counted.
- **Class 4** counts only standalone marker cells.
  - A glued "RMB8,400" is not standalone (Phase A F2).
  - ISO codes come from a closed list. Unknown short tokens next to amounts were inventoried, and none was a currency.
- **Class 5.** "Swallows a data row" means fusion fired and row 1 holds an amount under the body-start rule. Header rows in the body are `header_row_count` rows that survive `_clean_grid` beyond the one or two rows the header line uses. Their kind (unit line, period, other) comes from regular expressions.
- **Class 6** is exact: a column dropped by `_clean_empty_rows_and_cols` whose header text is non-empty.
- **Class 7** replays `_one_row_table_to_text`'s branch logic on `Parser._effective_rows`. A unit is one-row when it has an output entry and no `TableParser` instance. "Flattens two or more amounts" counts from the first 6 non-empty cells.
- **Class 8** counts an open-amount output cell whose source `)` or `)%` sits in the next non-empty raw-grid cell of the same row, and is placed elsewhere.
  - Not counted: three-cell splits ("(" \| "29" \| ")"), whose digits are not in the "(" cell, and negatives the structural pass already joined.
  - "Shared" and "headed" are judged on data-zone and header-zone cells, respectively.

**Scope.**

- Normal mode only. Capture mode replaces `TableParser` output only for unreliable snapshots, and Phase A found the two modes identical.
- Positioned-div tables, page furniture (G4) and `AbsolutelyPositionedTableParser` are out of scope.
- The XLSX path does not render through `TableParser`, but it does reuse its
  structural helpers.
  - **Correction (2026-10-05, Astra round 1, finding 2).** This bullet originally
    said XLSX uses only `_join_structural_text`. That is wrong.
    `xlsx_tables.prepare_table()` also builds a bare `TableParser`
    (`object.__new__`) and calls `_safe_structural_actions()` and
    `_validated_structural_actions()`. Those helpers depend on `_body_start`,
    `_classify_structural_column` and `_is_numeric_fragment`.
  - The design keeps XLSX on today's rules through a structural policy (spec
    revision 2, R9).
