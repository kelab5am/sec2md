# sec2md XLSX Header Detection Design

Date: 2026-10-11 (revision 5); revision 6 on 2026-10-12

Status: Draft for review. Revision 5 is implemented on branch
`fix/xlsx-header-detection` (not merged); revision 6 adds the period-row guard.
Implementation plan: `../plans/2026-10-11-sec2md-xlsx-header-detection.md`.

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

**Accuracy comes before coverage.** The balance sheet, income statement and cash
flow statement must be correct at all cost: every exported number must sit under
the period it belongs to. When the exporter cannot establish a header with
evidence, the table stays `source_text_only`. Falling back is the safe failure;
a wrong header or a data row swallowed into a header is not acceptable.

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
above alone makes the `Notes` column numeric. This design neither causes nor
fixes that (see "Known remaining gaps").

**Revision 2 → 3** (user request: recover revision 1's coverage without losing
revision 2's safety; the user needs the tables correct and accurate).

Revision 2's check 5 required every heading to be wider than every data cell
beneath it. That rejected 96 vault tables whose real headings sit over equally
wide cells: interest rates (`3.50%`), maturity years (`2027`), remaining lives
(`4.2`), share counts and full-width nil dashes. A trace showed check 5 was the
only blocker for all 96. Revision 1 exported them with correct headers, but it
also pulled about 30 exhibit-list entries into headers.

| Change | Why |
|---|---|
| Check 5 split in two. Per row: no heading may be narrower than an amount beneath it. Per header: the header ends at the last accepted row that has span evidence (a heading wider than an amount beneath it); rows accepted after it are dropped. | The row directly above the data must prove it is a heading. Rows above it may repeat widths or be spanning captions. |
| Only digit-bearing data cells count as amounts for check 5. | A full-width text cell (`Level 1`) or nil dash says nothing about the heading above it. |
| New check 4b: a labelled row may not repeat the width of the heading above it, except for a currency caption. | Closes a hole found while testing the change: `Alpha \| Foo \| Bar`, with each cell as wide as the year above it, carried span evidence. Real lower header rows subdivide (`Shares` under `Class A`). |

**Round 2** (Codex on gpt-6-astra, revision 3 → 4). Codex ran each
counterexample against the prototype; each was reproduced again before it was
accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: a labelled row of year-shaped or leading-dot amounts (`Revenue \| 2024 \| 2025`, `Basic EPS \| .75 \| .50`) under a wider heading became a header, silently. | Confirmed | Leading-dot numbers are data cells. Check 7b: a labelled row may hold year headings only when its label is a unit or period caption. Both examples now fall back, as today. |
| 2. High: a heading straddling two parent periods (`Debt` across `December 31, 2024` and `December 31, 2023`) put the 2023 amount under a 2024 header. | Confirmed | Check 4c: every heading must lie entirely under one parent heading. The example keeps today's output, with each amount under its own date. |
| 3. High: a labelled text row narrower than the heading above (`Alpha \| Foo \| Bar` under `December 31, 2025`) was swallowed. | Confirmed | Check 3b: a labelled row joins the header only if its label is a unit or period caption or a column-heading word (`Description`, `Exhibit Number`, `Period`, …). Layout cannot tell `Description \| Cash \| Debt` from `Alpha \| Foo \| Bar`; the label's meaning can. |
| 4. High: identifier and period in one cell (`CUSIP as of December 31, 2024`) cleared the identifier. | Confirmed | Rule 3 removes the period wording from a part and tests the remainder for identifier meaning. |
| 5. Medium: acceptance could pass correct values under wrong headers, and text rows swallowed into headers. | Confirmed | Acceptance adds an XBRL period cross-check of every primary-statement number and a review of every promoted row, text-only rows included. |
| 6. Medium: the prototype's note-reference pattern missed `Notes 2(a)`. | Confirmed | Prototype aligned with the spec. |

**Revision 3 → 4, also:** the XBRL cross-check found NVDA's FY2024 10-Q headers
reading `July 30,` without the year, because `2023` sat under an equally wide
`July 30,` and check 8 required a wider heading. Check 8 now also accepts a year
under an equally wide period heading that has no year of its own.

**Round 3** (Codex on gpt-6.1-sol, reviewing the implementation plan; revision
4 → 5). Each finding was reproduced before it was accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: a line item containing period wording (`Revenue for year ended December 31, 2025 \| 2024 \| 2025`, `Cash as of December 31, 2025`) counted as a caption label, so its year-shaped amounts became headings and the row was swallowed. | Confirmed | A caption label must be a whole caption (definition below). Both rows now fall back to source text. |
| 2. High: the wrapped-heading join cleared independent identifiers: `Notes — Cash` turned note reference `7` into a number; `CUSIP — Shares` and `Notes — Amount` also cleared. | Confirmed | A part is exempt for quantity words only in its own text. The join with the next part counts only for `number of` and `grant date fair value`. |
| 3. High: the XBRL check matched digits anywhere in the filing, so an amount could pass on an unrelated fact. | Confirmed | Acceptance validates each number against the fact inside its own source cell: value, sign and period. |
| 4. High: instant and duration facts could stand in for each other. | Confirmed | Balance sheets need instants; income statements need durations of the stated length; cash flow statements need durations, except opening and closing balances. |
| 5. High: skipped cells (no period, no conversion, zero) left the counters at zero. | Confirmed | Every fact in a statement gets a verdict; failures are counted by reason. |
| 6. High: cash flow arithmetic skipped non-numeric operands. | Confirmed | A missing or non-numeric operand fails. Arithmetic uses Decimal. |
| 7. High: an exported summary could stand in for a primary statement that fell back. | Confirmed | Statements are identified from their source rows and XBRL fact count, independent of the export result; a fallback statement fails. |
| 8. Medium: removing checks 4b, 5 or 7 left all tests passing. | Partly confirmed | Tests added so checks 1, 3, 3b, 4b, 4c, 6, 7b and 8, the evidence cut-off and each Rule 3 exemption are each the only blocker in some test; a mutation run disables each safeguard in turn and a test fails. Checks 2 (its unit-declaration half), 4, 5 and 7 cannot fail alone: 2 is covered by checks 3 and 4, 4 by 4c, 7 by 3b, and 5's layout already falls back on the unresolved-span check. They stay as defence in depth. A byte-level fingerprint test pins `_header_count` and `_PERIOD`. |
| 9. Medium: tables present in one run only were not compared. | Confirmed | The comparison pairs tables by ordinal and source cells and reports missing or added tables. |
| 10. Medium: structural cells (`$`) were counted as numeric cells. | Confirmed | Only digit-bearing source cells are counted, cell by cell. |
| 11. Medium: promoted rows were truncated and listed only for vault filings. | Confirmed | Every promoted row is listed in full, with digit-bearing rows marked, for every filing. |
| 12. Medium: the plan said the harness was committed when it was not; documents on `main` conflict with a branch-and-PR workflow. | Partly confirmed | The harness is committed with the plan. Documents stay on `main` by the user's standing instruction. |
| 13. Low: expected loss totals disagreed with revision 4's evidence. | Confirmed | The numbers come from one rerun of the revised harness and are recorded in the audit. |

Also from this round: the Rule 2 change to `_numeric_role` was dead code (the
identifier rule already treats footnoted-year headers as periods), so it is
dropped.

**Acceptance run of revision 5** (revision 5 → 6). The implementation of
revision 5 reproduced every expected number in the plan. A code review of the
implementation and an extra check in the acceptance run found two defects that
the stated checks could not see. Each was reproduced before it was accepted.

| Finding | Verdict | Change |
|---|---|---|
| D1. Critical: stacked period blocks. 21 vault statements of stockholders' equity (9 META 10-Qs, 12 RDDT 10-Qs) put a second period block under its own caption row inside the same table. The extended header takes the first block's caption, so the second block's 906 numbers (852 XBRL facts) sit under the first block's period. RDDT's Q1 2025 net income `26,158` sits under `Three months ended March 31, 2024 — Total Stockholders' Equity (Deficit)`. The tables are `needs_review`, but the issue names the caption row, not the header. On `main` 20 are `source_text_only` and 1 is `needs_review`. | Confirmed (found by an extra check of every XBRL fact in every exported table) | Period-row guard (Rule 1). Acceptance checks every fact in every exported table, not only the primary statements. Giving each block its own header on one sheet is a separate follow-up spec. |
| I1. High: a stranded period row. A row the scan accepts after the last evidenced row stays in the body. When that row holds the years or dates, the headers lack them: TSM 20-F #105 exports with `Measurement Date` twice, its dates in the first body row and 4 tagged rates turned to unflagged text. No primary statement is affected. | Confirmed (code review) | The same period-row guard. |
| I2. Medium: a table-wide caption such as `(In millions, except per share and percentage data)` makes `_numeric_role` read plain amounts as percents (`16,169` → `161.69`). | Confirmed, existing behaviour | No change: value conversion is unchanged by this spec. It occurs 0 times in the 60 filings, because they write the plural `except percentages`, which `_UNIT_DECLARATION` does not match. Recorded as a known gap. |

**Round 4** (Codex on gpt-6.1-sol, reviewing the revision 6 draft). Each finding
was checked against the code before it was accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: a second caption sharing its row with column headings (`Three Months Ended June 30, 2025 \| Common Stock \| …`), or a stranded date row labelled `Date`, was not a period row, so the guard missed it. | Confirmed | A period row needs only one period-text origin and no data cell. Tests for both. |
| 2. High: period text missed `Three Months Ended June 30, 2025 and 2024`, `Three Months Ended June 30, 2025 (1)` and `December 31, 2025 (1)` (verified: the draft's pattern union returns False for all three). | Confirmed | Period text is defined by vocabulary: footnotes removed, nothing but period words, dates and years left. |
| 3. High: "returning `base` restores today's output" is false. Rule 3 still applies, so a header `main` vetoes as an identifier (`Year Ended December 31, 2024`: `_IDENTIFIER` matches, `_PERIOD` does not fully match) holds numbers, which a table-wide percent caption can then divide by 100. | Confirmed | The claim is narrowed to "today's header rows", and the interaction is a known gap. 0 such cells in the corpus. |
| 4. High: the all-table check accepted a duration starting the day after any header date and did not read `Quarter ended` as 3 months; skipped facts were uncounted. | Confirmed (the day-after rule is unconditional in the script) | Acceptance 3b states the duration rules, counts every verdict, lists yearless period headers, and requires tests of the script's blind spots. |
| 5. Medium: "Vault filings: 0 mismatches" contradicts 19 checker-limit mismatches already present on `main`. | Confirmed | 0 real misattributions in both cohorts; checker limits are classified. |
| 6. Medium: a statement with a repeated date section label falls back under the guard. | Confirmed as the stated trade-off; none in the 126 vault statements | Test 12i pins it; Acceptance 3 still requires every vault statement to export. |

The other filings' lost cells were also classified (audit README): 41 fixes and 52
regressions. The regressions are TSM #105 (I1, fixed by the guard), NTRA #8
(`Less Than` / `1 Year`), TSM #150–#152 (`Other Changes (Note)`) and TSM #19/#20
(known since revision 1). See "Known remaining gaps".

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
  matches the body-number pattern `[$(\d+−.-][\d,.() $%+−-]*` (the existing pattern, also
  accepting a leading dot as in `.75`); or a
  nil token.
- **Digit data cell (amount):** a data cell whose text contains a digit, or an
  `is_numeric_fact` cell.
- **Data row:** the first row at or after `base` containing a digit data cell.
- **Amounts beneath a heading:** the digit data cells of the data row that lie
  in the heading's columns.
- **Span evidence:** a heading spanning more columns than some amount beneath
  it.
- **Heading above a cell:** scanning upward from the row above, the first
  origin with text covering any of the cell's columns.
- **Period heading:** text that fully matches `_EXPORT_PERIOD` (below) or an
  instant caption `(as of |as at )?<month> <day>,?`, or contains a period phrase
  (`(?:years?|months?|quarters?|weeks?|periods?) ended`) or a full date
  `<month> <day>, <year>`.
- **Currency caption:** `$`, `US$`, `NT$`, `HK$`, `RMB`, `€`, `£` or `¥`,
  optionally in parentheses.
- **Caption label:** the whole label is a caption, nothing else: a unit
  declaration (`_UNIT_DECLARATION`, full match), a parenthesised scale such as
  `(Dollars in millions)`, `As of` / `As at`, or a period caption, optionally
  followed by a parenthesised scale. Period captions are `<month> <day>,` with or
  without a year, and `<three|six|nine|twelve> months ended`, `(fiscal) year(s)
  ended` or `quarter(s) ended`, optionally followed by a date and optionally
  preceded by `As of`, `As at`, `As of or for the` or `For the`. So
  `December 31, (in millions)` and `As of or for the year ended December 31,` are
  captions; `Cash as of December 31, 2025` and a bare `2026` are not.
- **Heading-like label:** a caption label, or a column-heading word fully
  matching one of: `Description`, `Exhibit`, `Exhibit Number`, `Exhibit No.`,
  `Period`, `Issuance`, `Issuance Period`, `Name`, `Name/Title`,
  `Name of <words>`, `Record Date`, `Payment Date`, `Plan category`,
  `Instrument`, `Fiscal Year`, `Investment Type`, `Pricing Category`,
  `Range of Exercise Prices`, `Type`, `Category`, `Item`, `Class`, `Security`,
  or `Date…`, optionally followed by a footnote marker such as `(1)`. The list
  comes from every labelled header row in the 60-filing evidence set; a label
  outside it stops the extension, which is the safe direction.
- **Period text:** text made only of period vocabulary that names a period.
  Remove footnote markers (`(1)`, `*`), then dates (`<month> <day>`), four-digit
  years (`(?:19|20)\d{2}`), the words `three`, `six`, `nine`, `twelve`, `fiscal`,
  `month(s)`, `year(s)`, `quarter(s)`, `week(s)`, `period(s)`, `ended`,
  `ending`, `as`, `of`, `at`, `for`, `the`, `and`, `through`, `to`, and the
  punctuation `,` `.` `-` `–` `—`. The text is period text when nothing
  remains and the original contained a date, a year or `ended`. Period text:
  `Three months ended March 31, 2025`, `Three Months Ended June 30, 2025 and
  2024`, `December 31, 2025 (1)`, `Six Months Ended`, `December 31,`,
  `2023 (2)`, `As of December 31, 2024`. Not period text:
  `Balance as of December 31, 2024`, `2024 vs 2023 % change`, `Common Stock`,
  `Fiscal Year`.
- **Period row:** a row with no data cell in which at least one origin, label
  included, is period text. Other origins may be column headings
  (`Three Months Ended June 30, 2025 | Common Stock | Retained Earnings`) or a
  heading-word label (`Date | December 31, 2023 | December 31, 2024`).

### Rule 1: header extension (`_export_header_count`)

Let `base = _header_count(grid)`. If there is no data row, return `base`. This
leaves text-only tables (signatures, power of attorney, audit matters) exactly
as today.

Otherwise scan each row from `base` up to, not including, the data row. Skip
rows with no origins. A row is accepted only if every check passes. The first
row that fails a check ends the scan.

| # | Check | Rejects, for example |
|---|---|---|
| 1 | The row has no data cell. Data cells include leading-dot numbers (`.75`) | `Alpha \| N/A`, `Bob \| -`, `Basic EPS \| .75` |
| 2 | The row has headings, and they are not all unit declarations (`_UNIT_DECLARATION`) | `Assets`, `Inventories: \| (In millions)` |
| 3 | If the row has a label, it has at least two headings | `Alice \| CEO` |
| 3b | If the row has a label, the label is heading-like | `Alpha \| Foo \| Bar`, `Revenue \| …` |
| 4 | No heading spans more columns than its heading above (headers narrow downward) | `(unaudited)` across every period under the years |
| 4b | If the row has a label, each heading with a heading above is strictly narrower than it, unless it is a currency caption | `Description \| Foo \| Bar` with each cell as wide as the year above it |
| 4c | Each heading lies entirely under one parent heading: in the nearest row above that has any heading over its columns, every one of its columns is covered by the same non-empty cell | `Debt` spanning the edge between `December 31, 2024` and `December 31, 2023` |
| 5 | No heading is narrower than an amount beneath it | A heading over part of a wider amount |
| 6 | A currency caption is not narrower than its heading above | `NT$` over only the `$` and amount cells of `December 31, 2023` |
| 7 | The label is not a year token | `2026 \| 2000` |
| 7b | If the row has a label and any year-token heading, the label is a caption label | `Revenue \| 2024 \| 2025` |
| 8 | Every year-token heading lies inside a period heading above it that is wider, or equally wide and without a year of its own | `2024` under `Amount`; allows `2023` under an equally wide `July 30,` |

Checks 2 (its unit-declaration half), 4, 5 and 7 are implied by other checks
(2 by 3 and 4, 4 by 4c, 7 by 3b) or reach the same result through the existing
unresolved-span fallback (5). They stay as defence in depth; tests cannot make
them the only blocker.

**The header ends at the last accepted row with span evidence.** Return the
index after that row, or `base` if no accepted row has evidence. Accepted rows
below the last evidenced row are not header rows; they stay in the body.

Span evidence is the affirmative test. In SEC tables the heading directly above
the data spans the `$`, amount and padding cells beneath it
(`December 31, 2024` spans `$` and `2,750`). A body row in the same position
does not: its cells are the amounts' width or narrower, so it carries no
evidence, and it is dropped from the header if it is the last accepted row.
Other headings may be as wide as the cells beneath them when the evidence comes
from their own row or a row below. In META's debt table, `Maturity` and
`Stated Interest Rate` sit over `2027` and `3.50%` in the same row as
`December 31, 2024`. In NVDA's, `Expected Remaining Term (years)` sits one row
above the evidenced dates.

**Period-row guard (revision 6).** When the evidenced count is greater than
`base`, scan every row from the evidenced count to the end of the table. If any
of them is a period row, return `base`: the table keeps `_header_count`'s
header rows. A period row in the body means one of two things, and neither can
be exported safely under one header:

- a second period block stacked under the first (D1): its caption row
  (`Three months ended March 31, 2025`) would leave its numbers under the first
  block's period;
- an accepted period row stranded below the evidenced row (I1): its years or
  dates would be missing from the column headers.

The guard only ever returns `base`, so it restores today's header rows. The
rest of the table is then prepared as revision 5 prepares any table whose
extension adds nothing: Rule 3 still applies, so the output can differ from
`main` exactly where Rule 3 differs from today's `_IDENTIFIER` test (see
"Table-wide percent captions" under Known remaining gaps). A period row that is
a legitimate section label also returns `base`, which costs coverage: a
statement with a repeated `December 31, 2025` section label falls back to
today's output. Rows of amounts are unaffected, because they contain data cells
(`Balance as of December 31, 2024 | $ 2,130,749`). A labelled row of
year-shaped values with no other data (`Revenue | 2024 | 2025`) is a period row
and returns `base`, the safe direction for a row that checks 7b and 8 already
treat as data.

### Rule 2: footnoted years are periods in the export

`2023 (2)` is a year heading: the year token allows a footnote marker. Add an
XLSX-only pattern, `_EXPORT_PERIOD`, equal to `_PERIOD` plus the alternative
`(?:19|20)\d{2} \(\d{1,2}\)`, and use it in the period-heading definition.
`_numeric_role` keeps `_PERIOD`: Rule 3 already treats a footnoted-year header
as a period. Do not change `_PERIOD`, because `_header_count` uses it and must
stay unchanged.

### Rule 3: identifier columns

Add `_identifier_column(header)`. Split the fused header on ` — ` into parts. The
column is an identifier column if any part matches `_IDENTIFIER` and that part
is not exempt. A part is exempt when any of these holds:

- It is a note reference such as `(Note 3)` or `Notes 2(a)`, fully matching
  `\(?notes? \d+[a-z]?(?:\([a-z]\))?\)?`.
- It is a maturity bucket (`Less than 1 year`, `1-3 years`,
  `5 years or more`).
- After removing its period wording (`<three|six|…> months ended`,
  `year(s) ended`, `for the`, `as of`, dates and four-digit years), the rest of
  the part no longer matches `_IDENTIFIER`. So `Year ended March 31,` is exempt,
  while `CUSIP as of December 31, 2024` and
  `Notes for year ended December 31, 2024` stay identifiers.
- The part itself matches `_VALUE` or `_ROW_UNIT`, or contains `number of`,
  `to date` or `per share` (`Number of Shares`, `Plan to Date`).
- The part joined with the next one contains `number of` or
  `grant date fair value`: a heading wrapped over two rows (`Number — of RSUs`,
  `grant date — fair value`). Other value words in the next part do not count,
  so `Notes — Cash`, `CUSIP — Shares` and `Notes — Amount` stay identifiers.

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

The figures below are revision 4's prototype evidence. The implemented revision
5 measurements, the classification of every lost and changed cell, and, after
the rerun, revision 6's measurements are in
`../audits/2026-10-11-xlsx-header-detection/README.md`, which supersedes them.

A prototype of revision 4 (monkeypatched, outside the repo) was measured on 60
filings: 18 META, 14 NVDA and 10 RDDT 10-K/10-Q filings from the RCQ vault, plus
the 18 filings in `outputs/table-completeness-corpus` (US 10-K/10-Q, banks and
three 20-F filers). The comparison is by source coordinate. Numbers count
digit-bearing source cells converted to numbers. "Balanced" counts columns
whose `Total assets` equals `Total liabilities and … equity` as numbers,
compared by value.

| Group | Fallback tables before → after | Numeric cells before → after | Balanced columns before → after |
|---|---|---|---|
| META (18) | 408 → 57 | 8,309 → 16,091 | 28 → 36 |
| NVDA (14) | 270 → 8 | 6,550 → 13,084 | 22 → 28 |
| RDDT (10) | 174 → 10 | 6,092 → 9,407 | 16 → 20 |
| Others (18) | 1,004 → 619 | 9,511 → 21,173 | 23 → 37 |

Comparison of the revisions on the vault filings:

| | Rev 1 | Rev 2 | Rev 3 | Rev 4 |
|---|---|---|---|---|
| Fallback tables, META / NVDA / RDDT | 57 / 7 / 10 | 96 / 37 / 78 | 57 / 7 / 10 | 57 / 8 / 10 |
| Numeric cells lost or changed | 0 | 0 | 0 | 0 |
| Codex round 2 counterexamples handled safely | no | no | no | yes |
| Rows promoted into headers that are not headings | about 30 exhibit entries | 0 | 0 | 0 |

**Primary statements (vault).** The balance sheet, income statement and cash
flow statement were found and exported in all 42 vault filings (126
statements, none falling back). Every number in them was cross-checked
against the filing's inline XBRL: for each cell, a fact with the same digits
must exist for the period named by its column header (instants for balance
sheets and opening and closing cash; durations of the stated length for the
rest). Non-dimensional facts are matched first; a dimensional fact for the
right period is accepted as a second tier (RDDT's per-class common stock,
META's share-based compensation lines).

| | Cells checked | Matched the column's period | Matched via a dimensional fact | Mismatched | No tagged fact |
|---|---|---|---|---|---|
| META | 3,216 | 3,216 | 97 | 0 | 0 |
| NVDA | 2,545 | 2,545 | 0 | 0 | 0 |
| RDDT | 1,877 | 1,877 | 36 | 0 | 0 |

The cross-check also found the one defect revision 3 had on these statements:
NVDA's FY2024 10-Q headers read `July 30,` without the year (see Round 2).
Revision 4 fixes it. Separately, the balance identity holds in every vault
balance sheet column.

**Rows promoted into headers (vault).** All 241 distinct promoted rows were
listed and reviewed, including text-only rows. Every one is a column heading:
period and date rows, `% change` / `$ Change` columns, fair value levels,
equity statement column headings, debt maturity and rate headings, exhibit
index headings and group captions such as `Plan to Date`.

**Counterexamples.** Every counterexample from Codex rounds 1 and 2, and the
adversarial rows in tests 12a and 12b, either keeps today's output or falls
back to source text. All 249 existing XLSX tests pass with the prototype.

**Other filings.** 93 digit-bearing cells in 10 tables are no longer numbers,
and 14 cells in 3 tables changed value.

- TSM's two statements of financial position (20): note references (`7`,
  `8`, …) now sit under a `Notes` header as text. A fix.
- MSFT "Long-term Debt" (21): maturity years such as `2039` under
  `Maturities (calendar year)` are now flagged text. Likely a fix.
- JPM regulatory capital (9 changed): `12.3 | %` now converts to `0.123`
  instead of `12.3`. A fix (see the mixed-scale gap below).
- TSM "Share Ownership" (26): ownership percentages are now flagged text
  ("Conflicting explicit units"). A visible regression in a 20-F filer.
- Not yet classified: 26 cells in TSM and NTRA tables, and 5 changed cells in
  TSM's customer table.

In the other filings' primary statements, 1,719 cells matched their period. The
8 mismatches are limits of the checker, not of the export: Micron's opening
cash under bare-date headers, and a TSM percent-of-revenue table picked as the
income statement. 28 primary statements were not checked: some still fall back
(CRM, KO, MSFT, JPM, BAC; see "Period caption in the label column"), and the
checker did not recognise the others (CAT, NVO and several income statements).

## Known remaining gaps (out of scope)

- **Period caption in the label column.** Banks and some industrials (JPM, BAC,
  KO, CAT, MSFT, CRM) put `Year ended December 31` or
  `(In millions, except percentages)` in column 0, with the years to their right
  and no wider heading above. Check 8 rejects those years, so some of these
  companies' primary statements still export as source text. That is safe, but
  it is the most valuable follow-up for US filers outside the vault.
- **Heading-word list.** Check 3b accepts labelled header rows only for the
  listed column-heading words and captions. A filing with another heading word
  in the label column keeps today's output for that table. Extending the list is
  safe only with the same review of promoted rows.
- **No runtime XBRL guard.** The XBRL period cross-check runs in acceptance, not
  in the exporter. A follow-up could run it inside `export_xlsx()` and mark a
  table for review when a tagged amount's period disagrees with its column
  header, protecting filings never swept here.
- **Tables with no header row**, such as META's `Thereafter` and
  `Contractual Commitments` maturity tables, where only body spans show how the
  `$` and amount cells pair up.
- **Headers with no span evidence.** A header whose last row is no wider than
  the amounts beneath it is not extended, so simple tables built from 1-column
  cells keep today's behaviour. This includes Codex's `Item | Notes | Amount`
  example, where the `Notes` column is already numeric today.
- **Unlabelled full-width text rows are headings.** Check 4b applies only to
  labelled rows, so that wrapped headings over several rows
  (`Weighted-` / `average` / `grant date fair value`) still work. An unlabelled
  text row as wide as the heading above it therefore joins the header. In
  filings such rows are headings (`As Reported | As Adjusted`); no amount is
  moved either way.
- **Mixed scale in a percent column.** When only the first row of a column shows
  `%` (JPM: `12.3 | %`, then `13.8`), the first value converts to `0.123` and
  the rest stay `13.8`. This is existing value-conversion behaviour that the new
  headers expose, not something this change introduces.
- **Currency rows narrowing a column (20-F).** Check 6 keeps TSM's `NT$` rows out
  of the header, so those tables keep today's output instead of splitting
  `(82.7 | )`. Using them as headers needs a `_column_groups` change.
- **Review flag for identifier columns holding amounts.** An identifier column's
  numbers are still unflagged text. Flagging them is a separate change.
- **Stacked period blocks (revision 6).** The period-row guard keeps today's
  output for tables that stack two period blocks, such as the META and RDDT
  10-Q equity statements. The follow-up is a separate spec: keep the statement
  on one sheet and give each block its own header row, so the 2025 block sits
  beneath the 2024 block under its own period.
- **Table-wide percent captions.** `_numeric_role` reads plain amounts as
  percents when the table's unit caption says `except per share and percentage
  data` (I2). Not seen in the 60 filings; a value-conversion change, out of
  scope. Rule 3 can also expose it without any header extension: `main` vetoes
  a header such as `Year Ended December 31, 2024` as an identifier (it is not a
  full `_PERIOD` match), so the column stays text; Rule 3 exempts the period
  wording, so the column's plain amounts reach the percent rule. Revision 5's
  corpus run, which includes Rule 3, found 0 such cells.
- **Rule 3 misreads in wrapped or annotated headings.** `Less Than` / `1 Year`
  (NTRA #8, 4 amounts) and `Other Changes (Note)` (TSM #150–#152, 13 tagged
  amounts) read as identifier columns, so their amounts become unflagged text
  where `main` converted them. `Year-over-Year Change` (NVDA), `Full Year 2024`
  (CAT), `Within 1 year` (JPM), `At Prior Year Rates` (AMZN) and
  `credit-related notes` (JPM) do the same in 154 cells of tables that used to
  fall back; those were text on `main` too. Regressions listed in the audit
  need the user's acceptance.
- **Mixed percent scale in newly exported tables.** BAC #127, CRM #60, KO #56
  and JPM #64, #73, #210, #281 and #282 expose the existing mixed-scale
  behaviour described above.
- **TSM #48** heads its US$ column `December 31, 2024`, like the NT$ column; the
  `US$` caption is dropped on both `main` and the branch.

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
5a. Headings as wide as the cells beneath them, in the evidenced row: the META
    debt layout `Maturity | Stated Interest Rate | December 31, 2024` over
    `2027 | 3.50% | $ 2,750`. All three become headers; the carrying value is a
    `Decimal`.
5b. Equal-width headings one row above the evidenced row: the NVDA layout
    `Expected Remaining Term (years) | Effective Interest Rate` over
    `<date> | <date>`.
5c. A full-width text cell or nil dash in the data row under a heading
    (`Level 1`, `—`) does not block the header.

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
12a. Check 4b and the evidence rule: under `December 31,` / `2024 | 2023`
     (each year spanning 3), insert a labelled row whose cells are as wide as
     the years: `Alpha | Foo | Bar`, `Alpha | N/A | NM` and
     `Alpha | March 31, 2025 | June 30, 2025`. Each stays a body row with its
     text, and the amounts below stay `Decimal`. With `Alpha | 2027 - 2062 |
     3.50% - 4.65%`, the table falls back to source text, as today.
12b. An unlabelled text row as the last row before the data. With cells as wide
     as the amounts, it carries no evidence and stays in the body. With cells as
     wide as the years (`As Reported | As Adjusted`), it joins the header as a
     wrapped heading (see "Known remaining gaps"). Both cases are pinned.
12c. Codex round 2, each asserting today's output or a fallback:
     `Revenue | 2024 | 2025` and `Basic EPS | .75 | .50` under a wider heading
     (checks 1 and 7b); `Description | Cash | Debt | Other` with `Debt`
     straddling `December 31, 2024` and `December 31, 2023`, where each amount
     must keep its own date (check 4c); `Alpha | Foo | Bar` narrower than
     `December 31, 2025` (check 3b).
12d. A labelled header row with a heading-like label joins the header:
     `Description | December 31, 2024 | Quoted Prices…` (fair value) and
     `Pricing Category | <date> | <date>` (NVDA), each above an evidenced row.
12e. The NVDA FY2024 10-Q layout: `July 30,` above an equally wide `2023`. The
     header reads `July 30, — 2023`, and amounts are `Decimal`.

"Today's header rows" below means the result of `prepare_table` with
`_export_header_count` replaced by `_header_count`; each guard case asserts
equality with it.

12f. Period-row guard, stacked blocks (D1): a table with `Three months ended
     March 31, 2024` over column headings over `$`/amount rows, then an
     unlabelled `Three months ended March 31, 2025` row, its own column
     headings and amounts. The output equals today's header rows, and no column
     header names 2024 over the 2025 amounts. Variants: the second caption
     shares its row with the column headings; it reads
     `Three Months Ended June 30, 2025 and 2024`; it carries a footnote
     (`Three Months Ended June 30, 2025 (1)`); it sits in the label column.
12g. Period-row guard, stranded rows (I1): `December 31,` (colspan 4) over a
     1-column `2024 | 2023` row over `$`/amount pairs; an unlabelled
     `December 31, 2023 | December 31, 2024` row under `Measurement Date`; and
     the same row labelled `Date`. Each gives today's header rows.
12h. The guard does not fire on rows with amounts: a body row
     `Balance as of December 31, 2024 | $ | 2,130,749` leaves the extended
     header in place. A body row `Revenue | 2024 | 2025` is a period row and
     gives today's header rows.
12i. The guard's cost, pinned: a balance sheet (`December 31,` over `2025 |
     2024`, `$`/amount rows) with a repeated `December 31, 2025` section label
     in the body gives today's header rows.
12j. Period text, directly: each example of period text and of non-period text
     in the definition.

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
    `2024 — Exhibit Number`, `CUSIP — RMB`, `Filing Date — December 31, 2024`,
    `CUSIP as of December 31, 2024`, `Notes for year ended December 31, 2024`.
    Not an identifier: `Notes 2(a)` (a note reference).
    In table form, their numbers stay text, including when the cell is an
    `ix:nonFraction` fact.
16. `Plan to Date` with no units, `$` cells or value words: the value stays text
    with "Numeric role unresolved".

Sole-blocker cases (revision 5). In each, only one safeguard stops a wrong
result, so removing that safeguard fails a test:
- an unlabelled `N/A | NM` or `.75 | .50` row (check 1);
- `Description | Foo` with one narrower heading (check 3);
- `Description | Foo | Bar` as wide as the years (check 4b);
- `Description | 2024 | 2023` under `December 31,` (check 7b);
- unlabelled years under `Amount` (check 8);
- line items that mention a period (`Revenue for year ended December 31, 2025`,
  `Cash as of December 31, 2025`) holding year-shaped amounts (caption labels
  must be whole);
- identifier columns in tables (`Notes`, `CUSIP`, `Exhibit Number`,
  `Notes — Cash`, `CUSIP — Shares`) beside measured columns that hold numbers
  (`Number of Shares`, `Number — of RSUs (iii)`, `Plan to Date — Severance`).

- the period-row guard: case 12f fails when the guard is removed.

A heading over part of a wider amount (check 5) falls back to source text.

Unchanged-behaviour guards:

17. `_header_count` and `_PERIOD` are byte-identical to today's (a SHA-256
    fingerprint of `_header_count`'s source and of `_PERIOD`'s pattern), so the
    completeness check is unaffected.
18. The full test suite passes, including `tests/test_table_completeness*.py`,
    `tests/test_quality.py`, `tests/test_parser.py` and the accuracy tests.

## Acceptance

1. All tests pass.
2. Commit the harness to
   `docs/superpowers/audits/2026-10-11-xlsx-header-detection/` and run it on the
   same 60 filings with the implementation. For each table it compares old and
   new output by source coordinate and records:
   - digit-bearing source cells that were numbers and no longer are, or whose
     value changed;
   - every row promoted from the body into the header, text-only rows included,
     listed in full (for a table that used to fall back, all its new header
     rows);
   - tables present in one run only;
   - balanced columns, by value.
3. **Primary statements, vault filings (META, NVDA, RDDT):** each statement is
   identified from its source rows and XBRL fact count, independent of the
   export result. In every filing the balance sheet, income statement and cash
   flow statement are exported, not source text, and every value column has a
   period header including its year. Every inline XBRL fact in them gets a
   verdict from the fact inside its own source cell, and every verdict is ok:
   the copy cell is a number equal to the displayed amount, with the displayed
   sign, under a header naming the fact's period (instants for balance sheets
   and opening and closing cash; durations of the stated length otherwise).
   No number in them lacks a fact, apart from a repeated total equal to a
   tagged number in its column (META's FY2023 10-K repeats closing cash as an
   untagged `Total cash, cash equivalents, and restricted cash` line). The balance identity holds in every balance
   sheet column, and opening cash plus net change (with or without the
   exchange-rate effect) equals closing cash; a missing operand fails. Any
   failure blocks the merge.
3b. **Every exported table, every filing (revision 6):** a committed harness
   script checks every inline XBRL fact in every table that is not
   `source_text_only` against the period its column header names, on `main`
   and on the branch:
   - instants: at or near the header date, or at the start of a stated
     period (opening balances);
   - durations: ending at or near the header date, with the stated length
     (`Three months` and `Quarter` are 3 months, `Six months` 6, `Nine months`
     9, `Year` and `Twelve months` 12); a duration starting the day after the
     header date is accepted only under a header that states no length;
   - every fact gets a verdict: ok, mismatch, no header date, or not placed
     (no copy cell); the counts of each are reported per group;
   - every table whose column headers carry period wording without a year is
     listed (a yearless period header).

   The script's own tests cover a 6-month fact under a `Three Months Ended`
   header, a fact starting the day after a `Three Months Ended` header date,
   and a 6-month fact under `Quarter ended`; each must be a mismatch.
   Acceptance, for vault and other filings alike: 0 real misattributions. Each
   mismatch is classified as a real misattribution or a checker limit (such as
   NVDA's opening deferred revenue under a bare date, present on `main`), with
   its source cells. Mismatches and yearless period headers present on `main`
   are listed as existing; new ones are classified one by one. None of the 21
   D1 tables may export a number under another block's period. Any real
   misattribution blocks the merge.
4. Vault filings, all tables: no lost or changed numeric cell, no balanced
   column lost, and every promoted row is reviewed as a real column heading.
5. Other filings: every lost or changed cell and every promoted row with digits
   is classified as a fix or a regression, with the source cells shown.
   Regressions block the merge unless the user accepts them. No balanced column
   may be lost. Any XBRL mismatch in an exported primary statement is
   investigated; a real misattribution blocks the merge.
6. Spot-check against the filings: the META FY2024 10-K balance sheet, its
   revenue MD&A table and Basic EPS, the META Q1 2025 10-Q income statement, an
   NVDA FY2024 10-Q balance sheet, and one RDDT 10-Q results-of-operations
   table.
7. Add a CHANGELOG entry under the unreleased version describing the export
   change and noting that Markdown output is unchanged.

## Rollout

After merge, re-export the RCQ vault workbooks with the `xbrl-to-excel` skill's
`--reextract`. Existing workbooks, including the META FY2024 10-K and Q1 2025
10-Q workbooks generated on 2026-10-11, were built before this change.
