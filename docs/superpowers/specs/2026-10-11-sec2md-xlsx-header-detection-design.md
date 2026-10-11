# sec2md XLSX Header Detection Design

Date: 2026-10-11 (revision 2, same day)

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
matter most. One rule set serves every filer; no separate foreign-filer path is
proposed.

## Review history

**Round 1** (Codex, revision 1 → 2). Each finding was reproduced against the
prototype before it was accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: any remaining text row joined the header when numbers followed. `Alpha \| N/A` above `Beta \| 10` became a header. | Confirmed | Rule 1 now needs affirmative header evidence: each heading cell must be wider than the data cells beneath it, and a row with a label needs at least two headings. Nil tokens (`N/A`, `NM`, dashes) are data. |
| 2. High: a wider `Amount` heading let year-shaped amounts (`2024 \| 2025`) become a header. | Confirmed | Years are headings only under a heading with period meaning. The span-evidence rule also rejects this case. |
| 3. High: period, currency or quantity text in an ancestor heading cleared identifier meaning, so `December 31, 2024 — Notes` and `— CUSIP` columns became numbers. | Confirmed | Rule 3 judges each header part separately. A part with identifier meaning keeps the column an identifier, whatever its ancestors say. |
| 4. Medium: the numeric-row test accepted bare `-`, `$` and `(`, so a dash made a text-only table look numeric. | Confirmed | The data row that licenses an extension must contain a digit. Nil tokens still stop the scan. |
| 5. Medium: test case 6 asked to keep `(in thousands)` out of the header, but `_header_count` already counts that row. | Confirmed | Case 6 now asserts what matters: neither caption becomes a column's deepest heading, and the table exports. `_header_count`'s unit-row behaviour is unchanged. |
| 6. Medium: acceptance counted numeric cells, which can hide offsetting losses, column swaps and body rows lost to the header. | Confirmed | The sweep now compares by source coordinate: lost and changed digit-bearing cells, body rows with digits that moved into a header, and balance identity by value. |
| 7. Medium: removing identifier meaning does not make a column numeric; test case 12 lacked context. | Confirmed | Rule 3 only removes the identifier veto. Case 12's fixtures include the context (`$` cells or a units caption) that makes the role numeric. |

Codex's finding 3 example also shows a limitation that exists today: when the
`Item | Notes | Amount` row is not recognised as a header, the period heading
above alone makes the `Notes` column numeric. Revision 2 neither causes nor
fixes that (see "Known remaining gaps").

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
2. **A separate exporter for foreign filers.** Rejected. The same rules hold on
   the 20-F filers tested (BABA, TSM, NVO), and the user prefers one
   configuration.
3. **Recommended: an XLSX-only extension layered on the unchanged rule.** Keep
   `_header_count` and `_PERIOD` byte-identical. Add `_export_header_count(grid)`,
   which starts from `_header_count(grid)` and may only extend it downward.
   `prepare_table()` calls the new function. The completeness check keeps
   calling `_header_count`.

### Definitions

- **Origins of a row:** its distinct non-empty origin cells.
- **Label:** the row's column-0 origin when it has text. **Headings:** the
  row's other origins.
- **Year token:** text fully matching `(?:19|20)\d{2}(?:\s*\(\d{1,2}\))?`, such
  as `2024` or `2023 (2)`. An `is_numeric_fact` cell is never a year token.
- **Nil token:** text fully matching a dash run (`-`, `–`, `—`), `N/A`, `n.a.`,
  `NM`, `n/m`, `not meaningful` or a run of `*`.
- **Data cell:** `is_numeric_fact`; or text, not a year token, that fully
  matches the existing body-number pattern `[$(\d+−-][\d,.() $%+−-]*`; or a
  nil token.
- **Digit data cell:** a data cell whose text contains a digit, or an
  `is_numeric_fact` cell.
- **Data row:** the first row at or after `base` containing a digit data cell.
- **Heading above a cell:** scanning upward from the row above, the first
  origin with text covering any of the cell's columns.
- **Period heading:** text that fully matches `_EXPORT_PERIOD` (below) or an
  instant caption `(as of |as at )?<month> <day>,?`, or contains a period phrase
  (`(?:years?|months?|quarters?|weeks?|periods?) ended`) or a full date
  `<month> <day>, <year>`.
- **Currency caption:** `$`, `US$`, `NT$`, `HK$`, `RMB`, `€`, `£` or `¥`,
  optionally in parentheses.

### Rule 1: header extension (`_export_header_count`)

Let `base = _header_count(grid)`. If there is no data row, return `base`. This
leaves text-only tables (signatures, power of attorney, audit matters) exactly
as today.

Otherwise scan each row from `base` up to, not including, the data row. Skip
rows with no origins. A row joins the header only if every check passes. The
first row that fails a check ends the scan, and the count so far is returned.

| # | Check | Rejects, for example |
|---|---|---|
| 1 | The row has no data cell | `Alpha \| N/A`, `Bob \| -` |
| 2 | The row has headings, and they are not all unit declarations (`_UNIT_DECLARATION`) | `Assets`, `Inventories: \| (In millions)` |
| 3 | If the row has a label, it has at least two headings | `Alice \| CEO` |
| 4 | No heading spans more columns than its heading above (headers narrow downward) | `(unaudited)` across every period under the years |
| 5 | Each heading spans more columns than every data-row origin beneath it | `Revenue \| 2024 \| 2025` above `Cost \| 100 \| 150` (equal widths) |
| 6 | A currency caption is not narrower than its heading above | `NT$` over only the `$` and amount cells of `December 31, 2023` |
| 7 | The label is not a year token | `2026 \| 2000` |
| 8 | Every year-token heading sits strictly inside a wider period heading above it | `2024` under `Amount` |

Check 5 is the affirmative evidence. In SEC tables a column heading spans the
`$`, amount and padding cells beneath it (`2024` spans 3), while a body cell in
the same column does not.

### Rule 2: footnoted years are periods in the export

`2023 (2)` is a period when the export decides header roles. Add an XLSX-only
pattern, `_EXPORT_PERIOD`, equal to `_PERIOD` plus the alternative
`(?:19|20)\d{2} \(\d{1,2}\)`. Use it in `_numeric_role`'s `period_header` test
and in the period-heading definition. Do not change `_PERIOD`, because
`_header_count` uses it and must stay unchanged.

### Rule 3: identifier columns

Add `_identifier_column(header)`. Split the fused header on ` — ` into parts. The
column is an identifier column if any part matches `_IDENTIFIER` and that part
is not exempt. A part is exempt when any of these holds:

- It is a note reference such as `(Note 3)` or `Notes 2(a)`, fully matching
  `\(?notes? \d+[a-z]?(?:\([a-z]\))?\)?`.
- It is a period heading, or a maturity bucket (`Less than 1 year`,
  `1-3 years`, `5 years or more`).
- The part, or the part joined with the next one, matches `_VALUE` or
  `_ROW_UNIT`, or contains `number of`, `to date` or `per share`. The join
  handles wrapped headings such as `Number — of RSUs` and
  `grant date — fair value`.

Ancestor parts never exempt another part. So `December 31, 2024 — Notes`,
`December 31, 2024 — CUSIP`, `2024 — Exhibit Number`, `CUSIP — RMB` and
`Filing Date — December 31, 2024` stay identifiers.

Use the helper in both places that read `_IDENTIFIER` today: the role decision
in `_numeric_role` and the review-reason suppression in `prepare_table()`.

The helper only removes the identifier veto. The column's role still comes from
the existing `_numeric_role` evidence (units, `$` cells, numeric facts, value
words). Without such evidence, a value stays text and gets the existing
"Numeric role unresolved" review reason.

### Unchanged behaviour

- `_header_count`, `_PERIOD` and every caller in `table_completeness.py`.
- Markdown output, strict's numeric trace, `table_report` and
  `table_completeness_failures`.
- `_column_groups`, the unresolved-span fallback and value conversion. They now
  receive more header rows; their rules do not change.
- Table detection and table count. Table sheets per workbook stay the same.

## Evidence

A prototype of revision 2 (monkeypatched, outside the repo) was measured on 60
filings: 18 META, 14 NVDA and 10 RDDT 10-K/10-Q filings from the RCQ vault, plus
the 18 filings in `outputs/table-completeness-corpus` (US 10-K/10-Q, banks and
three 20-F filers). Numbers count digit-bearing source cells converted to
numbers. "Balanced" counts columns whose `Total assets` equals `Total
liabilities and … equity` as numbers, compared by value.

| Group | Fallback tables before → after | Numeric cells before → after | Balanced columns before → after |
|---|---|---|---|
| META (18) | 408 → 96 | 8,309 → 14,876 | 28 → 36 |
| NVDA (14) | 270 → 37 | 6,550 → 12,229 | 22 → 28 |
| RDDT (10) | 174 → 78 | 6,092 → 7,323 | 16 → 20 |
| Others (18) | 1,004 → 623 | 9,511 → 21,012 | 23 → 37 |

- **Vault filings:** no numeric cell lost or changed, and no balanced column
  lost. 29 body rows with digits moved into headers; all are real column
  headings (footnoted repurchase headings such as
  `Total Number of Shares Purchased (1)`, stock-performance chart dates, and
  RDDT vesting-schedule headings).
- **Other filings:** 78 digit-bearing cells in 10 tables are no longer numbers,
  and 7 cells in 3 tables changed value. Examples:
  - MSFT "Long-term Debt" (21): maturity years such as `2039` under
    `Maturities (calendar year)` are now flagged text. Likely a fix.
  - TSM "Share Ownership" (26): ownership percentages under
    `Percentage of Outstanding Common Shares` are now flagged text ("Conflicting
    explicit units"). A visible regression.
  - The rest, in TSM, NTRA and UNH (31 cells), and the 7 changed cells in TSM
    and CRDO, are not yet classified.
- All 249 existing XLSX tests pass with the prototype, including the NVDA
  fixture counts and the year-as-data cases.

Revision 1's looser rules converted more tables (META 408 → 57 fallbacks), but
Codex's findings 1, 2 and 4 showed they could swallow body rows. Revision 2
trades some of those gains for that safety.

## Known remaining gaps (out of scope)

- **Period caption in the label column.** Banks and some industrials (JPM, BAC,
  KO, CAT, MSFT) put `Year ended December 31` or
  `(In millions, except percentages)` in column 0, with the years to their right
  and no wider heading above. Check 8 rejects those years.
- **Tables with no header row**, such as META's `Thereafter` and
  `Contractual Commitments` maturity tables, where only body spans show how the
  `$` and amount cells pair up.
- **Column headings no wider than the data cells.** Check 5 rejects them, so
  simple tables built from 1-column cells keep today's behaviour. This includes
  Codex's `Item | Notes | Amount` example, where the `Notes` column is already
  numeric today.
- **Currency rows narrowing a column (20-F).** Check 6 keeps TSM's `NT$` rows out
  of the header, so those tables keep today's output instead of splitting
  `(82.7 | )`. Using them as headers needs a `_column_groups` change.
- **Review flag for identifier columns holding amounts.** An identifier column's
  numbers are still unflagged text. Flagging them is a separate change.

## Testing

Write the tests first, in `tests/test_xlsx_tables.py`, using the existing
`prepared(html)` helper. Each case asserts headers, typed values, retained body
rows and `cell_sources`. Use SEC-style spans: headings spanning the `$`, amount
and padding cells, as in the evidence filings.

Rule 1, positive cases:

1. `December 31,` (colspan over both years) above `2024 | 2023`, then
   `$`/amount pairs: headers `December 31, — 2024` and `December 31, — 2023`;
   values are `Decimal`; status `exported`.
2. `Year Ended December 31,` above `2024 | 2023 | 2024 vs 2023 % change`: the
   change column gets its own header, and the years get period headers.
3. Labelled `<td>` headings (`Description | Level 1 | Level 2`, each spanning
   two cells) above amounts: the headings become headers.
4. A three-level `<td>` header (`December 31, 2024` / `Less than 12 months` /
   `Fair Value`) above amounts.

Rule 1, negative cases (each asserts the output equals today's):

5. Existing year-as-data tests, unchanged.
6. `(unaudited)` and `(in thousands)` each spanning all periods under the years
   (the RDDT 10-Q pattern): neither becomes any column's deepest heading, and the
   table exports with period headers. Test each caption alone and both together.
7. `Inventories: | (In millions)` stays a body row (the NVDA pattern).
8. Codex's finding 1: `Item | Amount` (th), `Alpha | N/A`, `Beta | 10`. Also with
   `NM`, `—`, a date (`March 31, 2025`) and a range (`2027 - 2062`) in place of
   `N/A`.
9. Codex's finding 2: `Item | Amount (colspan 2)`, `Revenue | 2024 | 2025`,
   `Cost | 100 | 150`. Revenue stays a body row with `Decimal` values.
10. Codex's finding 4: `Name | Title`, `Alice | CEO`, `Bob | -`.
11. A signature table and a two-column text table.
12. `NT$` spanning only the `$` and amount cells under `December 31, 2023`
    (the TSM pattern).

Rule 2:

13. `Year Ended December 31,` above `2024 | 2023 (2) | 2022 (2)`: all three
    columns are numeric.

Rule 3 (direct tests of `_identifier_column`, plus table cases with `$` cells
or a units caption):

14. Not identifiers: `Number of Shares`, `Number — of RSUs (iii)`,
    `Weighted- — average — grant date — fair value — US$`,
    `Plan to Date — Severance`, `Year ended March 31, — 2023 — RMB`,
    `For the year ended December 31, 2024 — NT$`, `Less Than 1 Year — NT$`,
    `December 31, 2024 — US$ — (Note 3)`.
15. Identifiers: `Exhibit Number`, `CUSIP`, `Notes`, `Date`, `Filing Date`,
    `December 31, 2024 — Notes`, `December 31, 2024 — CUSIP`,
    `2024 — Exhibit Number`, `CUSIP — RMB`, `Filing Date — December 31, 2024`.
    In table form, their numbers stay text, including when the cell is an
    `ix:nonFraction` fact.
16. `Plan to Date` with no units, `$` cells or value words: the value stays text
    with "Numeric role unresolved".

Unchanged-behaviour guards:

17. `_header_count` returns today's values on every new test grid (direct
    assertion), so the completeness check is unaffected.
18. The full test suite passes, including `tests/test_table_completeness*.py`,
    `tests/test_quality.py`, `tests/test_parser.py` and the accuracy tests.

## Acceptance

1. All tests pass.
2. Commit the sweep harness to
   `docs/superpowers/audits/2026-10-11-xlsx-header-detection/` and run it on the
   same 60 filings with the implementation. For each table it compares old and
   new output by source coordinate and records:
   - digit-bearing source cells that were numbers and no longer are, or whose
     value changed;
   - body rows containing digits that moved into the header;
   - balanced columns, by value.
3. Vault filings (META, NVDA, RDDT): no lost or changed numeric cell, no
   balanced column lost, and every moved row is a real column heading.
4. Other filings: every lost or changed cell and every moved row is classified
   as a fix or a regression, with the source cells shown. Regressions block the
   merge unless the user accepts them. No balanced column may be lost.
5. Spot-check against the filings: the META FY2024 10-K balance sheet, its
   revenue MD&A table and Basic EPS, the META Q1 2025 10-Q income statement, and
   one RDDT 10-Q results-of-operations table.
6. Add a CHANGELOG entry under the unreleased version describing the export
   change and noting that Markdown output is unchanged.

## Rollout

After merge, re-export the RCQ vault workbooks with the `xbrl-to-excel` skill's
`--reextract`. Existing workbooks, including the META FY2024 10-K and Q1 2025
10-Q workbooks generated on 2026-10-11, were built before this change.
