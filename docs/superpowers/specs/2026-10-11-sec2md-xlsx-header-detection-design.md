# sec2md XLSX Header Detection Design

Date: 2026-10-11 (revision 1)

Status: Draft for review. Not implemented.

Scope: `src/sec2md/xlsx_tables.py` only. The Markdown renderer, strict's numeric
trace and the table completeness check must not change.

## Purpose

Make `export_xlsx()` read the header rows of ordinary SEC financial tables, so
their amounts reach the workbook as numbers instead of a source-text grid.

Today many primary statements and MD&A tables export as `source_text_only`. On
META's FY2024 10-K, 31 of 64 tables fall back, including the consolidated
balance sheet and every MD&A results table. The user copies these tables into
Google Sheets, where text cells cannot be summed. US 10-K and 10-Q filings
matter most. The rules below also hold on the 20-F filers tested, so one rule
set serves every filer; no separate foreign-filer path is proposed.

## Root cause

`prepare_table()` calls `_header_count(grid)` to find the header rows, builds
column groups from the deepest header cell over each column
(`_column_groups`), and then refuses any body cell whose span crosses two groups:

```
Unresolved value span at (r, c); review column alignment.  -> source_text_only
```

`_header_count` accepts a row only if it is all `<th>`, a period row (`_PERIOD`
or `_UNITS` text, under narrow layout conditions), or a unit row. It stops at
the first other row. SEC filings rarely use `<th>`, so it stops early on common
layouts, and the years row lands in the body. A year such as `2024` usually
spans the `$` and amount columns (`colspan=3`), so it crosses two groups and the
whole table falls back.

Layouts that stop it, all seen on META, NVDA and RDDT filings:

| Layout | Example | Effect |
|---|---|---|
| Bare instant date over years | `December 31,` (colspan 9) over `2024 \| 2023` | Header count 0. Balance sheet falls back. |
| A non-period column beside the years | `2024 \| 2023 \| 2022 \| 2024 vs 2023 % change` | Years row ends the header. MD&A tables fall back. |
| Footnoted year | `2023 (2)` | The year reads as a number; the row ends the header. |
| Ordinary `<td>` column headings | `Description \| Quoted Prices in Active Markets…`, `Less than 12 months \| 12 months or greater` | Header ends above them. Fair value and unrealized-loss tables fall back. |

A second, independent cause turns values into text without a review flag.
`_numeric_role` returns `text` when the column header matches `_IDENTIFIER`
(`number`, `date`, `year`, `notes`, …) and the header is not entirely period
parts. Line 622 then suppresses the "Numeric role unresolved" review reason for
any `_IDENTIFIER` header. Once headers are read correctly, this catches columns
such as `Number of Shares`, `Weighted-Average Grant Date Fair Value`,
`Plan to Date — Severance`, `Year ended March 31, — 2023 — RMB` and
`December 31, 2024 — US$ — (Note 3)`. Their values become unflagged text.

## Design

### Approach

Three approaches were considered:

1. **Extend `_header_count` in place.** Rejected. `table_completeness.py`
   imports `_header_count` to decide which source rows are header rows
   (`placed_header_rows`). Changing it would change the completeness check's
   row roles and its row-structure check, outside this spec's scope.
2. **A separate exporter for foreign filers.** Rejected. The same rules fixed
   the 20-F tables tested (BABA, TSM), and the user prefers one configuration.
3. **Recommended: an XLSX-only extension layered on the unchanged rule.** Keep
   `_header_count` and `_PERIOD` byte-identical. Add `_export_header_count(grid)`,
   which starts from `_header_count(grid)` and may only extend it downward.
   `prepare_table()` calls the new function. The completeness check keeps
   calling `_header_count`.

### Rule 1: header extension (`_export_header_count`)

Let `base = _header_count(grid)`. Scan rows from `base` downward. For each row,
consider its distinct non-empty origin cells. The *label* is the row's column-0
origin when it has text.

Definitions:

- **Numeric cell:** `is_numeric_fact`, or its stripped text fully matches the
  existing body-number pattern `[$(\d+−-][\d,.() $%+−-]*` and is not a year
  token.
- **Year token:** text fully matching `(?:19|20)\d{2}(?:\s*\(\d{1,2}\))?`, for
  example `2024` or `2023 (2)`. An `is_numeric_fact` cell is never a year token.
- **Text heading above a cell:** scanning upward from the row above, the first
  origin cell with text that covers any of this cell's columns.

A row is decided by the first rule that applies:

| # | Condition | Result |
|---|---|---|
| a | No non-empty cell | Skip the row. It joins the header only if a later row joins. |
| b | A non-label cell spans more columns than its text heading above (headers narrow downward) | Stop. Examples: `(unaudited)` or `(in thousands)` across all periods. |
| c | The row has a numeric cell | Stop. This row is data. |
| d | The label is a year token, or a year token cell does not sit strictly inside a wider text heading above it | Stop. The years are values (for example `2026 \| 2000`, or `2026` under an equally wide `Amount`). |
| e | Every non-empty cell is the label or a unit declaration (`_UNIT_DECLARATION`) | Stop. This is a body label such as `Assets` or `Inventories: \| (In millions)`. |
| f | Otherwise | The row joins the header. |

After stopping at row `s`, keep the extension only if row `s` or a later row is
numeric under the same definition. Otherwise return `base`. This leaves
text-only tables (signatures, power of attorney, audit matters) exactly as
today. If the scan reaches the end without stopping, also return `base`.

The prototype returned the extended count on stops (b) and (d) without
checking for numbers below. That is the only intended difference from the
prototype measured in "Evidence", and the acceptance sweep must be re-run on
the implementation.

### Rule 2: footnoted years are periods in the export

`2023 (2)` is a period when the export decides header roles. Add an XLSX-only
pattern, `_EXPORT_PERIOD`, equal to `_PERIOD` plus the alternative
`(?:19|20)\d{2} \(\d{1,2}\)`. Use it in `_numeric_role`'s `period_header`
test and in Rule 1's year token. Do not change `_PERIOD`, because
`_header_count` uses it and must stay unchanged.

### Rule 3: identifier columns

A header is an identifier column only if `_IDENTIFIER` matches it **and** none
of the following holds:

- **Period evidence.** Split the header on ` — `. Any part fully matches
  `_EXPORT_PERIOD`, or the header contains a period phrase:
  `(?:years?|months?|quarters?|weeks?|periods?) ended`, or a full date
  `<month> <day>, <year>`.
- **Currency evidence.** A whitespace-delimited part is a currency marker:
  `$`, `US$`, `NT$`, `HK$`, `RMB`, `€`, `£`, `¥`.
- **Quantity evidence.** With ` — ` replaced by a space, the header matches
  `_VALUE` or `_ROW_UNIT`, or contains `number of`, `to date` or `per share`.

Put this test in one helper, `_identifier_column(header)`, and use it in both
places that read `_IDENTIFIER` today: the role decision in `_numeric_role` and
the review-reason suppression in `prepare_table()`. Columns such as
`Exhibit Number`, `CUSIP`, `Notes`, `Date` and `Filing Date` remain identifiers,
and their numbers remain text.

Split the header on ` — ` *before* normalizing separators for the quantity
check. The prototype normalized first, which disabled the per-part period test.

### Unchanged behaviour

- `_header_count`, `_PERIOD` and every caller in `table_completeness.py`.
- Markdown output, strict's numeric trace, `table_report` and
  `table_completeness_failures`.
- `_column_groups`, the unresolved-span fallback and value conversion. They now
  receive more header rows; their rules do not change.
- Table detection and table count. Table sheets per workbook stay the same.

## Evidence

A prototype (monkeypatched, outside the repo) was measured on 60 filings: 18
META, 14 NVDA and 10 RDDT 10-K/10-Q filings from the RCQ vault, plus the 18
filings in `outputs/table-completeness-corpus` (US 10-K/10-Q, banks and three
20-F filers). "Balance identity" counts columns where `Total assets` equals
`Total liabilities and … equity` as numbers.

| Group | Fallback tables before → after | Numeric cells before → after | Balance identity columns before → after |
|---|---|---|---|
| META (18) | 408 → 57 | 8,309 → 16,091 | 28 → 36 of 36 |
| NVDA (14) | 270 → 7 | 6,550 → 13,211 | 22 → 28 of 28 |
| RDDT (10) | 174 → 10 | 6,092 → 9,401 | 16 → 20 of 20 |
| Others (18) | 1,004 → 475 | 9,511 → 26,043 | 23 → 41 of 41 |

- No META, NVDA or RDDT table lost a numeric cell.
- 13 tables elsewhere have fewer numeric cells. Two TSM balance sheets lose
  note references (`7`, `8`, …) that were wrongly numeric before and now sit
  under a `Notes` header; that is a fix. The other 11 are unclassified: BAC
  "Allowance for Credit Losses" (4 → 0), CAT "Expected volatility" (2 → 0), CRDO
  "4. Revenue Recognition" (4 → 0), MSFT "Long-term Debt" (65 → 44), NTRA
  "Operating leases" (14 → 10), UNH "Number of individuals served" (55 → 52) and
  five TSM notes.
- All 249 existing XLSX tests passed with the prototype, including the NVDA
  fixture counts and the year-as-data cases.

## Known remaining gaps (out of scope)

- **Period caption in the label column.** Banks and some industrials (JPM, BAC,
  KO, CAT, MSFT) put `Year ended December 31` or
  `(In millions, except percentages)` in column 0, with the years to its right
  and no wider heading above them. Rule 1(d) treats those years as values. About
  550 fallback tables remain in this group.
- **Currency row narrowing a column group (20-F).** TSM places `NT$` over only
  the `$` and amount cells. That becomes the deepest header, so a closing `)`
  falls outside the group and splits off, as in `(82.7 | )`.
- **Review flag for identifier columns that hold amounts.** Rule 3 narrows
  which headers are identifiers, but an identifier column's numbers are still
  unflagged text. Flagging them is a separate change.

## Testing

Write the tests first, in `tests/test_xlsx_tables.py`, using the existing
`prepared(html)` helper. Each case asserts headers, typed values and
`cell_sources`.

Rule 1, positive cases:

1. `December 31,` (colspan over both years) above `2024 | 2023` with `$`/amount
   cell pairs: headers `December 31, — 2024` and `December 31, — 2023`; values
   are `Decimal`; status `exported`.
2. `Year Ended December 31,` above `2024 | 2023 | 2024 vs 2023 % change`: the
   change column gets its own header, and the years get period headers.
3. `<td>` column headings with a filled label (`Description | Level 1 | …`)
   above amounts: headings become headers.
4. A three-level `<td>` header (`December 31, 2024` / `Less than 12 months` /
   `Fair Value`) above amounts.

Rule 1, negative cases:

5. Existing year-as-data tests stay green unchanged.
6. `(unaudited)` and `(in thousands)` spanning all periods below the years: they
   stay out of the header, and the table exports (the RDDT 10-Q pattern).
7. `Inventories: | (In millions)` stays a body row (the NVDA pattern).
8. A signature table (`Signature | Title | Date` then signer rows, no numbers):
   output identical to today's.
9. A text-only two-column table: output identical to today's.
10. Header rows above a label-only row with no numbers below: count stays at
    `base`.

Rule 2:

11. `Year Ended December 31,` above `2024 | 2023 (2) | 2022 (2)`: all three
    columns are numeric.

Rule 3:

12. `Number of Shares`, `Weighted-Average Grant Date Fair Value`,
    `Plan to Date — Severance`, `Year ended March 31, — 2023 — RMB`,
    `For the year ended December 31, 2024 — NT$` and
    `December 31, 2024 — US$ — (Note 3)` columns hold numbers.
13. `Exhibit Number`, `CUSIP`, `Notes`, `Date` and `Filing Date` columns keep
    numeric-looking text as text.

Unchanged-behaviour guards:

14. `_header_count` returns today's values on the new test grids (direct
    assertion), so the completeness check is unaffected.
15. The full test suite passes, including `tests/test_table_completeness*`,
    `tests/test_quality.py`, `tests/test_parser.py` and the accuracy tests.

## Acceptance

1. All tests pass.
2. Commit the sweep harness to
   `docs/superpowers/audits/2026-10-11-xlsx-header-detection/` and re-run it on
   the same 60 filings with the implementation, not the prototype. Record the
   per-file results there.
3. Balance identity holds on every balance column the sweep finds. The
   prototype found 125 such columns and the identity held on all 125.
4. No META, NVDA or RDDT table loses a numeric cell.
5. Classify every table elsewhere that loses numeric cells as a fix (a wrongly
   numeric value now correctly text) or a regression, with the source cells
   shown. Regressions block the merge unless the user accepts them.
6. Spot-check against the filings: the META FY2024 10-K balance sheet, the
   revenue MD&A table and Basic EPS, the META Q1 2025 10-Q income statement, and
   one RDDT 10-Q results-of-operations table.
7. Add a CHANGELOG entry under the unreleased version describing the export
   change and noting that Markdown output is unchanged.

## Rollout

After merge, re-export the RCQ vault workbooks with the `xbrl-to-excel` skill's
`--reextract`. Existing workbooks, including the META FY2024 10-K and Q1 2025
10-Q workbooks generated on 2026-10-11, were built before this change.
