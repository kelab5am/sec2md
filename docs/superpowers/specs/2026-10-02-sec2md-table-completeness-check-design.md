# sec2md Table Completeness Check Design

Date: 2026-10-02 (revision 6, same day)

Status: Proposed, for review

Review record: `../reviews/2026-10-02-sec2md-table-completeness-check-review.md`

## Purpose

Make the quality gate detect financial numbers that the parser loses or reorders
inside tables. Today `quality_policy="strict"` can pass a document whose tables
have lost real values, because every check runs in one direction: numbers in the
output must exist in the source, but numbers in the source are never required to
reach the output.

This spec covers the Markdown/page output of `convert_to_markdown()` and
`parse_filing()`. It also defines the per-table source extraction that the XLSX
value-rules spec will reuse. It does not change how tables are parsed. Fixing the
losses it reveals belongs to the table-merge and header-rules spec.

## Review history

Both review rounds are recorded in full, with reproductions, in the review record.

**Round 1** (revision 1 → 2):

| Finding | Change |
|---|---|
| 1. Nearby prose can conceal a lost value | Each table is compared only with its own output segment. Link destinations are stripped. |
| 2. Source text inherits numeric corruption | DOM-aware cell text; hidden descendants skipped; `€` and `£` normalized. |
| 3. Single-digit values treated as minor | Context classes replace digit count. |
| 4. Nested-table ownership and numbering | Outermost-table units; snapshot ordinal reported alongside. |
| 5. Row-order prototype did not match the spec | Check 2 redefined and evidence regenerated. |
| 6. XLSX results drop the new fields | New defaulted fields on the XLSX result types. |

**Round 2** (revision 2 → 3):

| Finding | Change |
|---|---|
| 1. A matching row exempted its financial amounts | Classification is per token. Only the identifier itself (`1` in `Note 1`) and date cells in signature rows are references. The amount in `Note 1 Revenue \| $ \| 9,943` is enforced. |
| 2. Split accounting negatives became unchecked | Split negatives such as `(29` + `)` are rebuilt across adjacent cells, on both the source and output sides. Deleting the amount is reported as `-29` missing. |
| 3. Row rearrangements passed both checks | Check 2 also reports source rows that appear before an earlier row, and rows whose values remain in the table but in different rows. It is restricted to data rows, so undetected header rows cannot cause false alarms. |
| 4. The prototype changed the rendering mode | The checks evaluate the rendering mode the caller used. Snapshot metadata comes from a read-only computation that never changes rendering. Evidence is given for both modes. |

**Round 3** (revision 3 → 4):

| Finding | Change |
|---|---|
| 1. A surviving reference or footnote could stand in for a lost value | Matching now uses occurrence positions. A value can only be matched by an output number in a compatible position: a numeric cell, a text cell, a header line or text rendering, never an identifier. References and markers claim first, so `Note 9` or `<sup>9</sup>` can no longer cover a lost amount `9`. A value shortfall that shared positions with a reference or marker is still reported, labelled *ambiguous*. |
| 2. The bare-year filter excluded real amounts | Period rows are decided by context: header rows, period text and period captions. `Revenue \| 2000 \| 1900` is a data row, so swapping its values is reported. |

**Round 4** (revision 4 → 5):

| Finding | Change |
|---|---|
| 1. A marker that is a whole cell (`<td><sup>9</sup></td>`) renders as a numeric cell. It was reported missing even when preserved, and it covered a deleted amount `9`. | A marker that is its cell's only content gets its own position, *standalone marker*, which matches numeric cells. Matching first pairs each source row with its own output line by row label (*row provenance*), so the footnote row's `9` and the amount row's `9` cannot cover for each other. Only numbers whose row cannot be paired fall back to table-wide matching, where competition between a value and a reference or marker produces an *ambiguous* value finding. Preserved, amount-deleted and marker-deleted variants are all correct in both modes. |

**Round 5** (revision 5 → 6):

| Finding | Change |
|---|---|
| 1. Row labels were reduced to letters, so `Note 1` and `Note 2` both became `note`, and two `Total` rows shared a key. Deleting the `Note 1` row paired its amount `9` with the surviving `Note 2` footnote. Deleting one `Total` row hid the loss. | Label keys keep identifier numbers (`note#1`, `note#2`). A pairing is proven only when its key is unique among both the source rows and the output body lines. Duplicate or uncertain labels go to the table-wide pass, where a value shortfall competing with a marker or reference is labelled *ambiguous*. Deleting the `Note 1` row now reports the value `9` missing. Deleting one of two `Total` rows reports it missing and ambiguous. |

## Background

The 2026-10-02 repository audit (`../audits/2026-10-02-repo-audit/REPORT.md`)
reproduced these failures. All of them pass default strict today:

| Failure | Example |
|---|---|
| Column merge discards row-0 values | AAPL 10-K: `74,427`, `9,943`, `4,258` absent; rows render `\| 2024 \| $ \|` |
| Whole data row lost | NVDA EX-99.1/99.2: operating cash-flow row (24,077 / 50,344 / 15,365 / 74,421 / 42,779) |
| Every table blanked (mutation test) | AAPL with `TableParser.md` returning `""`: 3,307 table pipes become 0 |
| Numeric cells reversed (mutation test) | `\| Total net sales \| $ 365,817 \| 8 % \| $ 394,328 \| …` |
| Header lost | AAPL repurchase table: "Approximate Dollar Value of Shares … (1)" column header |

The 2026-08-29 hardening design deliberately limited strict mode to a
catastrophic-loss ratio. It reasoned that "navigation, hidden XBRL, and repeated
headers make a universal runtime threshold unreliable." This design keeps that
ratio and does not add a document-wide recall threshold. Instead it compares
**each source table only with the output the parser produced for that table**,
excluding hidden nodes. Navigation text and neighbouring prose never enter the
comparison.

## Definitions

- **Table unit:** a visible outermost `<table>`, meaning one with no `table`
  ancestor and neither it nor any ancestor hidden.
  - Hidden follows `quality._is_hidden_tag`, plus `script`, `style`, `template`
    and `noscript`.
  - A nested table belongs to its outermost table; it is not a separate unit.
  - Positioned-div "tables" are out of scope (see Deferred).
- **Ordinal:** the 1-based document order of table units, including one-row
  tables.
  - Findings also give the unit's `TableSnapshot.ordinal` when one exists, plus
    the parser page.
  - The two numberings differ by design: snapshots exist only for HTML tables
    with more than one effective row, plus positioned groups.
- **Rendering mode:** the checks evaluate the rendering the caller actually
  got.
  - `convert_to_markdown()` and `parse_filing()` render with
    `capture_tables=False`. `export_xlsx()` renders with `capture_tables=True`,
    where tables with structural issues fall back to their original text.
  - Snapshot metadata (header-row count and snapshot ordinal) comes from a
    read-only computation over the same nodes. In non-capture mode it must never
    register tables as unreliable or otherwise change rendering.
- **Source rows:** every visible `tr` inside the unit, including rows of nested
  tables. Each row's cells are the visible `td`/`th` children of that `tr`, so
  every cell is counted exactly once.
- **Cell text:** visible text built by walking the cell's DOM.
  - Text nodes are concatenated. A space is inserted only at block boundaries
    (`p`, `div`, `br`, `li`, headings) and around footnote markers.
  - Comments, declarations and hidden descendants are skipped.
  - A nested `table` inside a cell is skipped, because its rows are counted as
    source rows of the unit.
- **Footnote marker:** text inside `<sup>`, or inside an element styled
  `vertical-align: super`. Also the full text of an in-document link (`href`
  starting with `#`) when that text is `(n)`, `[n]` or asterisks.
  - Relative positioning is not a marker signal. NVDA uses it to kern single
    digits.
  - A bare digit in a fragment link is not a marker either. NVDA splits dates
    across such links (`January 2` + `5` + `, 202` + `6`).
- **Output segment:** the exact string the parser emitted for that unit in the
  page stream.
  - That string is the value of `_process_element(root)` for the table in
    `_stream_pages`, or the retained original text for an unreliable table.
  - Before tokenizing, Markdown link and image destinations are removed and
    only their visible text is kept.
- **Split accounting negatives:** within one row, adjacent non-empty cells are
  merged before tokenizing in two shapes:
  - an opening amount (`(29`, `$ (29`, `(3.2`) followed by a closing cell (`)` or
    `)%`)
  - an opening cell (`(` or `$ (`) followed by a plain amount and a closing cell.

  The rule applies to source cells and, after splitting on `|`, to output lines.
  `(29 | )` and `( 29 )` therefore both yield `-29`.
- **Numeric tokens:** produced by `quality._normalized_numbers` on each cell
  separately (after the merge above) with two more rules:
  - `€` and `£` are treated like `$`. This change goes into
    `normalize_numeric_token` itself, which also makes the existing numeric trace
    stricter.
  - A hyphen or en dash between a digit or `%` and a following number is a range
    separator, not a minus sign: `3.5%-4.3%` gives `3.5` and `4.3`.

  Tokenizing never crosses a cell boundary.
- **Identifier:** `Item`, `Note`, `Exhibit`, `Part` or `Schedule` followed by its
  number (`Note 9`, `Exhibit 2.1`, `Item 1A.`), found anywhere in a cell. The
  same rule applies on the source and output sides.
- **Occurrence position:** every source and output number has one.
  - **reference:** the number of an identifier; any number in a reference cell
    (see Token classes); and on the output side, every number of an
    exhibit-index unit.
  - **numeric cell:** a number in a cell with no letters, such as `$ 9`,
    `( 1,865 )`, `71.1 %` or `100 999`. On the output side, a trailing marker such
    as `1,234 (1)` is split off first, and only when a number remains (`$ (96)` is
    a negative, not a marker).
  - **text cell:** a number in a cell with letters (`Impairment 9`,
    `Up 65%`).
  - **standalone marker** (source only): a footnote marker that is its cell's
    only content (`<td><sup>9</sup></td>`). It renders as a numeric cell, so it
    matches numeric cells. A marker beside text or an amount
    (`Impairment<sup>9</sup>`, `1,234<sup>(1)</sup>`) is an ordinary marker.
  - **header line** (output only): a number in a line before the Markdown
    separator, where header fusion mixes text and numbers.
  - **text rendering** (output only): a number in a unit rendered without a
    separator, where cells cannot be told apart.
- **Period row:** a header or period row, decided by context and never by the
  shape of its numbers. A row is a period row when either:
  - it is before the snapshot's header-row count, or
  - every non-empty cell is period text or a bare year, and the row has some
    period text or consists only of bare years.

  Period text covers duration words (`year`, `quarter`, `months`, `ended`,
  `ending`, `as of`, `fiscal`, `calendar`, `maturity`) and month-day dates.
  `Three Months Ended June 30, 2025 | … 2024`, `Maturities (calendar year) | 2023 |
  2022` and `| 2023 | 2022` are period rows. `Revenue | 2000 | 1900` is not.
- **Row pairing:** a source row of the unit is paired with an output body line
  only when the pairing is proven.
  - **Label key:** the lowercased letters of the row's first non-empty cell,
    plus the numbers of any identifiers in it. `Note 1` and `Note 2` give
    `note#1` and `note#2`; `Impairment` gives `impairment`. The output line's key
    is built the same way from its first cell. Other digits are dropped, so a
    marker glued to a label in the output (`Revenue (1)`) still matches the
    source label `Revenue`.
  - **Proven:** a pairing holds only when its key occurs exactly once among the
    unit's source rows and exactly once among its output body lines.
  - **Unpaired:** rows with an empty key (a bare number or blank label), a
    duplicate key (`Total` twice) or no matching line. Their occurrences go to
    the table-wide pass, where shared provenance makes a value shortfall
    ambiguous.

## Token classes

Every source token gets a class from its own source context. Digit count is never
used, and a class never spreads from one cell to the rest of its row.

| Class | Rule | Treatment |
|---|---|---|
| **marker** | Token from footnote-marker text | Reported, never enforced |
| **reference** | **(a)** The number of an identifier anywhere in a cell (the `1` in `Note 1 Revenue`, the `2.1` in "Previously filed as Exhibit 2.1"). Other tokens in the cell keep their own class. **(b)** Every token of a cell that starts with `Date:`/`Dated:` or contains `/s/`. **(c)** A date-shaped cell (`January 29, 2025`, `5/7/2024`) in a signature row, meaning a row with a `/s/` cell or a bare `Date:` cell. **(d)** Every token of an exhibit-index unit: one whose first three rows include a cell starting "Exhibit" and a cell containing "Description". Exhibit indexes list exhibit numbers, form codes, dates and note titles, not amounts. | Reported, never enforced |
| **value** | Everything else, including a single-digit amount such as `$9` and the amount in a row labelled `Note 1` | Enforced once D1 allows |

Value findings carry a row role so reviewers can tell value losses from label
losses:

- **header:** rows before `xlsx_tables._header_count` of the unit's snapshot grid.
- **label:** the row's first non-empty cell.
- **body:** everything else.

The role is used only for reporting.

## Checks

### 1. Table numeric completeness (enforceable)

For each table unit with at least one source token, match source occurrences to
output occurrences of the same number, using positions:

| Source occurrence | May claim output positions, in this order |
|---|---|
| reference | reference, text cell, text rendering, header line |
| marker | text cell, text rendering, header line |
| standalone marker | numeric cell, header line, text rendering |
| value in a numeric cell | numeric cell, header line, text rendering |
| value in a text cell | text cell, numeric cell, header line, text rendering |

1. **Claim order.** References claim first, then markers, then standalone
   markers, then values in numeric cells, then values in text cells. Each claims
   the first available compatible output occurrence.
2. **Pass 1, row provenance.** Each paired source row claims only from its own
   output line.
3. **Pass 2, table-wide.** The occurrences still unclaimed are matched against
   everything left over: unclaimed numbers on any body line, header lines and
   text rendering. This keeps values that moved to another row from being
   reported missing; check 2 reports the move.
4. **Positions are binding.** A value can never claim an identifier's number. A
   value from a numeric cell can never claim a number in an output text cell,
   unless the unit is rendered as text. So a surviving `Note 9` or `Impairment 9`
   (from `<sup>9</sup>`) cannot stand in for a lost amount `9`. With row pairing,
   a surviving `<td><sup>9</sup></td>` in a footnote row cannot either.
5. A source occurrence left unclaimed is missing.
6. **Ambiguous shortfalls.** When a value goes missing in pass 2, and a
   reference or marker of the same number claimed in pass 2 a position the
   value could also have used, provenance cannot decide which survived. The
   shortfall is a value finding labelled `ambiguous`. Claims made in pass 1 are
   backed by row provenance, so they never make a shortfall ambiguous.

This is Astra's "potentially material" treatment: the check never assumes that
the financial occurrence is the one that survived.

Findings:

- `table <n> (snapshot <s>, page <p>): missing <token>×<count> [<role>], …` for
  value tokens, with `ambiguous` added to any token whose provenance was shared.
  The list is truncated to the first 10 tokens, and the record always gives the
  total count.
- The same format, under a separate field, for marker and reference tokens.
- A unit with source tokens but an empty output segment is reported as
  `table <n> produced no output (<k> numbers)`.

Extra output tokens never count.

### 2. Table row structure (report only, see decision D1)

For each unit whose output segment contains a Markdown separator row:

1. **Output body lines** are the lines after the first separator, tokenized per
   cell. Header lines before the separator are excluded, because header fusion
   legitimately reorders header tokens ("Year ended December 31," over "2024 vs.
   2023" becomes "Year ended December 31, — 2024 | … | 2024 vs. 2023 — $ Change").
2. **Data rows** are the unit's own rows (not nested) that:
   - are not period rows (see Definitions)
   - have two or more value or reference tokens, and
   - have at least one cell that is a standalone amount: an optional currency
     symbol and parentheses around a number, optionally `%`. Unformatted amounts
     such as `2000` count.

   This keeps out undetected header rows, such as "Three Months Ended June 30,
   2025" or "Maturities (calendar year) | 2023 | 2022". Their tokens can recur in a
   stacked table's repeated headers or in body labels. Because the exclusion is
   decided by context, not by numeric shape, `Revenue | 2000 | 1900` stays a data
   row.
3. **Matching** keeps a pointer that starts at the first body line. For each data
   row in source order, the first matching case decides the outcome:
   - **In order.** A body line at or after the pointer contains all the row's
     tokens as a multiset. Project that line onto the row's tokens, keeping the
     output's left-to-right order. If the projection differs from the source
     order, report *values out of order within the row*. Then move the pointer to
     that line.
   - **Rows out of order.** A body line before the pointer contains all the
     tokens: report *row appears before an earlier source row*.
   - **Values split across rows.** The body as a whole still contains all the
     tokens, but no single line does: report *values present but split across
     output rows*.
   - **Otherwise** skip the row. Its values are missing, and check 1 reports
     them.

Findings use the form `table <n>: source row <i>: <kind>`. This catches swapped
columns, swapped rows and values moved between rows, none of which check 1 can
see. Text-rendered tables (no separator) are not checked.

### 3. Document numeric recall (diagnostic only)

Compute numeric recall over visible source text, the same way as the accuracy
suite's `normalize_numbers`. Record it in diagnostics and never enforce it. Its
job is to show losses outside tables to whoever reads the diagnostics. Making it
a pass/fail gate is the threshold the 2026-08-29 design rejected.

## Evidence (revision 6 definitions)

A prototype implementing exactly the definitions above is in
`../audits/2026-10-02-repo-audit/prototypes/v6/`, with a README covering how to
run it, its raw results (`evidence.json`) and the review-case output. The
revision 1–5 prototypes and figures are superseded. Revisions 5 and 6 change no
corpus figure: every fixture and RCQ table has exactly the same findings as
under revision 4.

### Review cases (both rendering modes)

| Case | Result (revision 6) |
|---|---|
| Lost `9,943` with the same number in nearby prose | value `9943` missing |
| `1,2<span>34</span>` rendered as `1,2 34` | value `1234` missing |
| `100<span style="display:none">999</span>` | `999` excluded from the source |
| `€123`, `£456` | checked, present |
| Lost single-digit `$9` | value `9` missing, enforced |
| `<sup>(1)</sup>` rendered as `(1)` | no finding |
| Nested table | normal mode: value `12` missing, as the normal Markdown loses it. Capture mode: no finding, as fallback text keeps it. |
| One-row table before a multi-row table | ordinal 2, snapshot 1 |
| All numeric cells reversed | check 2: values out of order within the row |
| `Note 1 Revenue \| $ \| 9,943`, amount lost | value `9943` missing, enforced |
| Split negative `(29` + `)` preserved | no finding |
| Split negative deleted | value `-29` missing |
| Two body rows swapped | check 2: rows out of order |
| Values moved between rows | check 2: values split across output rows |
| Fused two-level header | no finding |
| Signature date lost (`Date: \| January 29, 2025 \| /s/ …`) | reported as reference, not enforced |
| Stacked statement with repeated section headers | no finding |
| `Note 9` kept, amount `9` deleted | value `9` missing, enforced |
| `<sup>9</sup>` kept, amount `9` deleted | value `9` missing, enforced |
| Amount kept, `Note 9` identifier lost | reported as reference only |
| Amount kept, `<sup>9</sup>` marker lost | reported as marker only |
| Marker glued to the amount in the output (`1,234 (1)`) | no finding |
| `Revenue \| 2000 \| 1900` values swapped | check 2: values out of order within the row |
| Year-only header row (`\| 2023 \| 2022`) | not a data row; no finding |
| `<td><sup>9</sup></td>` footnote row beside an amount `9`, output unchanged | no finding |
| … footnote kept, amount `9` deleted | value `9` missing, enforced (row provenance, not ambiguous) |
| … amount kept, footnote deleted | reported as a standalone marker only |
| Same layout without row labels, amount deleted | value `9` missing, labelled `ambiguous` |
| `Note 1 \| 9` and `Note 2 \| <sup>9</sup>` rows, output unchanged | no finding |
| … `Note 1` row deleted | value `9` missing, enforced (not ambiguous); reference `1` reported |
| … `Note 2` footnote row deleted | reference `2` and standalone marker reported only |
| Two `Total` rows (`9` and `<sup>9</sup>`), output unchanged | no finding |
| … first `Total` row deleted | value `9` missing, labelled `ambiguous` (duplicate label) |

### Fixtures (7 documents)

- **Volume:** 382 table units, 290 of them with source tokens.
- **Check 1: 9 units flagged across 5 documents, 20 value tokens missing.** All
  are genuine losses:
  - the three AAPL column-merge values (`74,427`, `9,943`, `4,258`)
  - the AAPL repurchase-table header, via its plain-text `(1)`
  - the NVDA operating cash-flow row in EX-99.1 and EX-99.2
  - the `$3.5` guarantees row in the 10-Q and EX-99.2
  - the nvda-2002 period headers
- **Reported only:** 1 reference token.
- **Ambiguous value shortfalls:** none.
- **Check 2: 0 findings.**
- **Modes:** results are identical in normal and capture mode.

### RCQ META and RDDT filings (20 documents)

The run covered the 20 primary 10-K and 10-Q documents in `E:\RCQWealth`
(fiscal 2024 to 2026 Q2), read-only.

- **Volume:** 1,083 table units, 1,037 of them with source tokens. Default strict
  passes all 20 today.
- **Check 1: 105 units flagged across 18 of the 20 filings.** META 10-Q 2025 Q2
  and 2026 Q2 have none.
  - **96 header-row values.** These are period headers lost from the Markdown.
    "Three Months Ended March 31," above `2026 | 2025` renders as
    `|  | 2026 | 2025 |`, which is why Q1 10-Qs flag 8–20 tables each.
  - **14 body values**, all in META filings:
    - commitments `10,563`, `14,452` and `11,321` (first-row "remainder of
      year" values in the 2024 Q1–Q3 10-Qs)
    - 10-K maturities `205`, `26,335`, `1,259` and `30,634`
    - `257` in the 2025 Q3 10-Q
    - six 10-K ARPP values

  The header/body split differs slightly from revision 3, because occurrence
  positions now decide which of two equal numbers is the missing one.
- **Reported only:** 38 reference tokens. These come from exhibit-index columns,
  signature dates and identifiers in text such as "Previously filed as Exhibit
  2.1".
- **Ambiguous value shortfalls:** none.
- **Check 2: 0 findings.**
- **Modes:** results are identical in normal and capture mode.

Two prototype mistakes during revision 4 show which rules are load-bearing:

- **Identifier detection must be the same on both sides.** It first ran anywhere
  in output text but only at the start of source cells. That produced 28 false
  value losses in nvda-2002 exhibit footnotes ("Previously filed as Exhibit
  2.1").
- **A trailing `(n)` is split off as a marker only when a number remains.**
  Without that condition, `$ (96)` lost its negative.

Check 2 has 0 findings on real data only because of the data-row restriction.
Without it, a stacked META equity statement's first-section period row matched
the second section's repeated header line. Every later row then looked out of
order (19 tables, 272 rows). AAPL's undetected `Maturities | 2023 | 2022` header
row also looked "split across rows".

### Mutations (AAPL fixture, normal mode)

| Mutation | Result |
|---|---|
| `TableParser.md` returns `""` | 50 of 57 units with tokens flagged. The other 7 are 6 reference-only units (3 exhibit indexes, 3 signature blocks), whose losses are reported, and one one-row table rendered as text. |
| Numeric cells reversed in every row | Check 2 reports 50 of 57 units (values out of order within the row). |
| First two multi-token body rows swapped | Check 2 reports 48 of 57 units (rows out of order). |

### Overhead

The revision 1 prototype added 16–23% to parse time, mostly from a per-cell
parent walk for visibility. Revisions 2–4 compute hidden nodes once per
document. The revision 6 prototype parses a second time to get snapshot
metadata, so its timing is not representative; the implementation computes that
metadata in the same parse. The 10% target below stands.

## Diagnostics and API

Add fields with defaults at the end of the frozen `ParseDiagnostics`, so existing
construction and pickling keep working:

```python
table_completeness_failures: tuple[str, ...] = ()   # check 1, value class
table_completeness_reported: tuple[str, ...] = ()   # check 1, marker and reference classes
table_structure_differences: tuple[str, ...] = ()   # check 2
tables_checked: int = 0
numeric_recall: float | None = None                 # check 3
```

- **Warnings.** `warnings` gains one summary message per table with value-class
  failures once enforcement is on (decision D1). Until then the findings appear
  only in the new fields and in `warn`-level log lines.
- **Diagnostics access.** `convert_to_markdown()` and `parse_filing()` currently
  discard the value `enforce_quality()` returns, so callers can't get
  diagnostics. Decision D2 picks how to expose them.
- **XLSX.** `XlsxExportResult.diagnostics` is a tuple of message strings, so it
  cannot carry the new fields. Both frozen dataclasses gain trailing defaulted
  fields, which keeps positional construction working:

  ```python
  # XlsxExportResult
  parse_diagnostics: ParseDiagnostics | None = None
  # XlsxTableResult
  completeness: tuple[str, ...] = ()   # this table's check 1 and check 2 findings
  ```

  - Findings are matched to sheets by snapshot ordinal.
  - In Phase A neither field changes `status`, `issues` or `diagnostics`, so
    existing callers see identical results.
  - In Phase B, value-class failures are also appended to the table's `issues`.
    That makes the table `needs_review`, and strict XLSX raises
    `XlsxQualityError`, as for any other issue.
- **Where it runs.** `_stream_pages` records the output segment of each table
  unit (`self.table_outputs`, keyed by node) where it calls
  `_process_element(root)` for a table. It also records the unit's snapshot
  metadata.
  - In capture mode that metadata is the snapshot itself.
  - In non-capture mode it comes from calling `snapshot_html_table()` for
    metadata only. That call must not add the table to `_unreliable_tables` or
    `table_snapshots`.
  - The checks run in `Parser.get_pages()` after page assembly. They need no
    elements, so they also run with `include_elements=False`.
  - Hidden nodes are computed once per document.
  - Target overhead is at most 10% of parse time on the fixtures, measured in
    the implementation PR.

## Policy and rollout

1. **Phase A (this implementation).** Compute all three checks under every
   policy except `off`. Strict does not raise on them yet.
   - Expose the results according to D2 and the XLSX fields above.
   - Add a fixture test that pins the current failures as an explicit expected
     list. It fails when a new loss appears, and also when a listed loss
     disappears without the list being updated.
   - Run the checks on a wider corpus of at least 50 filings and record any false
     positives in this spec. The 7 fixtures and 20 RCQ filings above count
     toward that total.
2. **Phase B (after the table-merge and header-rules spec lands).**
   - Strict raises `ParseQualityError` on value-class check-1 failures.
   - The expected-failure list should then be empty, or contain only entries this
     spec explicitly accepts.
   - Ship as a minor RCQ version bump with a CHANGELOG entry, because some
     filings that pass strict today will start to fail.

## Testing

Unit tests on synthetic HTML, one behavior each. Every review case above becomes
a test, run in both rendering modes where the outcome can differ:

- **Reported as missing:**
  - a value lost while nearby prose repeats it
  - an inline-split number
  - a lost single-digit `$9`
  - a lost `€` value
  - a lost amount in a `Note 1` row
  - a deleted split negative
  - a table with an empty output segment
  - a lost amount `9` while `Note 9` survives
  - a lost amount `9` while `<sup>9</sup>` survives
  - a value shortfall with shared provenance, labelled `ambiguous` (unlabelled
    rows with a standalone `<sup>9</sup>` cell and a deleted amount `9`)
  - a lost amount `9` while a standalone `<td><sup>9</sup></td>` footnote row
    survives (not ambiguous: row provenance)
  - a deleted `Note 1 | 9` row beside a surviving `Note 2 | <sup>9</sup>` row
    (not ambiguous: identifier numbers keep the labels distinct)
  - a deleted row among two `Total` rows (`9` and `<sup>9</sup>`), labelled
    `ambiguous`: a duplicate label proves no pairing
- **Excluded from the source:** a hidden descendant inside a visible cell.
- **No findings:**
  - `<sup>(1)</sup>` rendered as `(1)`
  - a preserved split negative
  - a percentage range `3.5%-4.3%`
  - NVDA-style kerned or link-split digits
  - a one-row table rendered as text
  - a header-only table
  - a fused two-level header
  - a stacked statement with repeated section headers
- **Rendering mode:** the nested table reports its lost `12` in normal mode and
  nothing in capture mode.
- **Check 2:**
  - reversed numeric cells: values out of order within the row
  - swapped body rows: rows out of order
  - values moved between rows: values split across output rows
- **Numbering:** a one-row table before a multi-row table yields ordinal 2 with
  snapshot 1.
- **Reported only, not enforced:**
  - a lost footnote marker
  - a lost exhibit-index identifier
  - a lost signature date
  - a lost `Note 9` or `<sup>9</sup>` while the amount `9` survives
  - a lost standalone `<td><sup>9</sup></td>` footnote while the amount `9`
    survives
- **Standalone marker preserved:** an unchanged table with a standalone
  `<td><sup>9</sup></td>` footnote row reports nothing.
- **Period rows:** `Revenue | 2000 | 1900` is a data row, so a swap of its values
  is reported. `| 2023 | 2022 |` and "Maturities (calendar year) | 2023 | 2022"
  are period rows.
- **Output positions:** a marker glued to an amount (`1,234 (1)`) and an
  accounting negative beside a currency cell (`$ (96)`) are matched as numeric
  cells. A hidden value leaked into a numeric cell (`100 999`) does not hide
  the `100`.
- **Metadata leaves rendering alone:** computing snapshot metadata in non-capture
  mode does not change `convert_to_markdown()` output for any fixture.

Fixture tests:

- Each fixture has a pinned expected-failure list, matching the 9 units above.
- The three mutations above must be detected on the AAPL fixture.
- **XLSX:** `XlsxExportResult.parse_diagnostics` and `XlsxTableResult.completeness`
  are populated, while `status`, `issues` and `diagnostics` stay unchanged in
  Phase A.
- Overhead is measured and reported in the PR. A test enforces it only if timing
  proves stable in CI.

## Acceptance criteria

- On the fixtures, check 1 reports exactly the pinned failures, and check 2
  reports none. Each pinned failure can be traced to a parser defect named in
  the audit.
- All three mutations are detected.
- Non-capture rendering is byte-identical with and without the checks enabled.
- No new strict failures in Phase A: the existing suite passes unchanged.
- Diagnostics and XLSX results remain picklable, and existing positional
  construction of `ParseDiagnostics`, `XlsxExportResult` and `XlsxTableResult`
  still works.
- Parse-time overhead is 10% or less on the fixtures.
- README and `docs/usage/direct-conversion.md` describe what strict does and does
  not check, including the size thresholds.

## Decisions for review

- **D1. Enforcement timing.**
  - Recommended: report-only now, and enforce value-class check-1 failures in
    strict in Phase B.
  - Alternative: enforce now. That makes 5 of the 7 fixtures (the AAPL 10-K,
    nvda-2002, the NVDA 10-Q and both NVDA exhibits) fail strict immediately.
    It would also fail 18 of the 20 RCQ META/RDDT filings, breaking callers
    until the parser fixes land.
  - Check 2 stays report-only either way until the wider corpus run.
- **D2. Diagnostics API.**
  - Recommended: add `convert_with_diagnostics(source, **kwargs) ->
    tuple[str | list[Page], ParseDiagnostics]` and leave the existing functions'
    return types unchanged.
  - Alternatives: a keyword-only `diagnostics=` out-parameter, or documenting
    `Parser.diagnostics` as the supported route.
- **D3. Text completeness.** The lost AAPL header was caught only through its
  plain-text `(1)`. A per-table word-multiset check would catch header text
  directly, at the cost of more noise from header fusion.
  - Recommended: measure it in the Phase A corpus run before deciding.
- **D4. Token classes.**
  - Recommended: the per-token context classes above. Markers and references
    are reported, and every other token is enforced regardless of digit count.
    Period-header tokens (`31` in "March 31,") stay enforced and appear under
    the `header` role. Ambiguous value shortfalls are enforced too, labelled so
    a reviewer can see that provenance was shared. There were none in the corpus.
  - Alternative: also enforce marker and reference tokens. That would fail
    tables over a lost footnote marker, exhibit-index column or signature date.
- **D5. `include_elements=False`.** Resolved in revision 2: the checks use output
  segments, not elements, so they run in this mode too.

## Deferred

- Fixing the losses: column-merge row 0, complementary-column fusion, header
  fusion and period headers. These belong to the table-merge and header-rules
  spec.
- Element content diverging from page content: `Element.content` for tables with
  links or one row (for example nvda-2002 `ITEM 8.` missing from element text).
  The chunker uses element text, so this matters for RAG, but it is a separate
  check on elements.
- XLSX cell-value checks: these belong to the XLSX value-rules spec.
  - Context from the RCQ run: before the period-header fix in pull request #3,
    only about 89 of 918 RCQ tables exported as numbers. After it, 384 export,
    and all 10,544 exported values match a number in their source table.
  - 373 tables are still text-only, mostly "Unresolved value span", and that
    spec should start from them.
- Completeness of non-table prose beyond the document recall diagnostic.
- Positioned-div "tables" (`absolute_table_parser`): these have no `<table>`
  element, so they need their own unit and source definition.
