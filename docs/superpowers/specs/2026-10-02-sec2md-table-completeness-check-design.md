# sec2md Table Completeness Check Design

Date: 2026-10-02 (revision 6, same day; Phase A corpus run and Round 6 rulings
recorded 2026-10-04)

Status: Phase A implemented (PR #4) and reviewed in Round 6 (2026-10-04) as a
report-only milestone. Phase B enforcement is gated on the prerequisites in
"Phase A corpus run > Round 6 rulings".

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

**Exception: euro and pound** (accepted in Round 6, 2026-10-04; implementation
note (a)). Treating `€` and `£` like `$` goes into `normalize_numeric_token` (see
Numeric tokens), which rendering and strict's numeric trace also use. That has
two narrow effects beyond the checks:

- **Rendering.** Split euro and pound negatives merge as `$` ones already did:
  `(€567` + `)` renders as one cell, `(€567)`.
- **Strict's numeric trace.** A euro or pound sign in its own cell (`€ | 1,234`)
  no longer fails strict falsely. Rare split layouts that already fail for `$`
  now fail for `€` and `£` too, such as `(€567 | )` with the `)` under its own
  `<th>`.

Rendering with the checks on and off stays byte-identical, because the
normalizer applies either way.

## Review history

Review rounds 1–6 are recorded in full, with reproductions, in the review
record. The Phase A corpus run is recorded in this spec and in
`../audits/2026-10-03-table-completeness-corpus/classification.md`, not in the
review record. Round 6 reviewed that corpus record; its rulings are summarised
in "Phase A corpus run > Round 6 rulings".

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

**Phase A corpus run** (2026-10-04; definitions unchanged; reviewed in Round 6):

| Recorded | Section |
|---|---|
| Corpus of 109 documents and 55 filings, with summary figures for the offline and EDGAR parts | Phase A corpus run |
| Every false positive: 21 tables (20 false positive, 1 mixed), with no observed drift from the v6 prototype. First recorded as "all definition cases; 0 implementation defects"; Round 6 found contract defects shared with v6 among them (see False positives) | Phase A corpus run |
| Definition questions (page header and footer tables, CAT 7) and a detection gap (the BABA/TSM header shift) | Phase A corpus run |
| D3 measurement (40% noise) and a recommendation | Phase A corpus run |
| Overhead: Phase A accepts up to +25% on the fixtures in total; the 10% target moves to Phase B | Phase A corpus run, Evidence > Overhead, "Where it runs", Acceptance criteria |
| Implementation review notes (a)–(g) for decision | Phase A corpus run |
| Pointers to the record | Evidence (check 2 note), Policy and rollout, D1, D3 |

**Round 6** (Phase A corpus record, 2026-10-04; reviewed `main` at `8bf0c1e`):
Phase A is complete as a report-only milestone, but this is not approval to
enable Phase B enforcement. The review record holds the findings, from
"# Round 6 (Phase A corpus record)". This revision reconciles the spec the same
day and changes no recorded figure.

| Finding | Change |
|---|---|
| 1. A marker after a short negative can conceal a deleted amount | Note (c), and note (b)'s marker joining, are code fixes before Phase B |
| 2. Source tokenization leaves some quantities unchecked (`Nbps`, `RMB8,400`, `due 2029)`) | A code fix before Phase B; named as blind spots in False positives |
| 3. Passing strict and both checks does not establish header alignment | Regressions and a report-only alignment diagnostic in the table-merge and header work; the caveat stays |
| 4. A checker failure must not become a successful Phase B gate | Phase A behaviour documented in Diagnostics and API; Phase B must tell disabled, zero-table and failed checks apart |
| 5. Prototype parity does not resolve the identifier contract violation | "Implementation defects: 0" narrowed to no observed drift from v6; the shared contract defects are named |
| 6. Check 2 reuses rows and mistakes a promoted data row for a loss | F6, F7 and note (d) in the Phase B diagnostic revision; check 2 stays report-only |
| 7. Documentation overstates logging and error propagation | In this spec: logging scope, checker failure, the euro/pound exception, the check-3 normalizer and recall limit, and the metadata wording corrected. README, the usage documents and the CHANGELOG are addressed on branch `docs/table-completeness-round6` (`aaca4f2`, `1a3f1dc`, `095888f`, `ef0e727`), pending merge |
| Decisions 1–9 | Phase A corpus run > Round 6 rulings; outcomes beside D1–D5 |

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

Compute numeric recall with `quality._normalized_numbers()` over the visible
source text and the visible Markdown text that `build_diagnostics()` already
computes (wording decided in Round 6, note (g)). Recall is the share of source
tokens, counted with multiplicity, that the output also contains. Record it in
diagnostics and never enforce it. Its job is to show losses outside tables to
whoever reads the diagnostics. Making it a pass/fail gate is the threshold the
2026-08-29 design rejected.

**Known limitation** (Round 6, note (f)). `_visible_markdown_text` strips a
number shaped like an ordered-list marker at the start of an output line. For
`2. ` the source side keeps that number, so recall can read low. (`2) ` is
stripped too, but the source tokenizer also drops `2)`, so it does not lower
recall.) Astra reproduced a lossless
`2. Summary of 100 and 200 and 300` giving 0.75. The Phase B follow-up tells
real source numbering apart from generated Markdown list syntax, rather than
counting every list bullet as a source number. Recall stays diagnostic only.

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

Check 2 had 0 findings on the revision 6 corpus (the Phase A run found 11
tables, all false positives) only because of the data-row restriction.
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
metadata in the same parse. The 10% target now applies from Phase B; Phase A
accepts up to +25% against unchanged `main` (see Phase A corpus run, Overhead).

## Phase A corpus run

Recorded 2026-10-04 from plan Task 11, on the implementation (branch
`feat/table-completeness`, `f3639c0`). Phase A was to be complete only after
Astra's review. Round 6 (2026-10-04) completes that review for a report-only
release; it does not approve Phase B enforcement. Its rulings and corrections
are dated 2026-10-04 and sit beside the figures, which stay as recorded. They
are summarised in "Round 6 rulings" at the end of this section.

- **Detail:** the per-table verdicts, the reported-only scan and the D3 sample
  are in `../audits/2026-10-03-table-completeness-corpus/classification.md`.
- **Source of the figures:** every figure comes from that folder's
  `results.json`.

### Corpus

| Part | Documents | Distinct filings |
|---|---|---|
| Fixtures | 7 | 5 |
| RCQ primary 10-Ks and 10-Qs (META 10, RDDT 10, NVDA 12) | 32 | 32 |
| RCQ exhibits with at least two tables | 52 | (exhibits of the filings above) |
| **Offline** | **91** | **37** |
| EDGAR, new issuers | 18 | 18 |
| **Total** | **109** | **55** |

- **EDGAR manifest:**
  `../audits/2026-10-03-table-completeness-corpus/edgar_manifest.json`. It
  records the CIK, form, dates, accession, URL, size and SHA-256 of each
  document.
- **Issuers.** The user replaced the plan's 16 issuers on 2026-10-03.
  - Dropped: XOM, BRK, PFE, WMT, JNJ, PRU and HD.
  - Kept: JPM, KO, MSFT, TSLA, CAT, BAC, UNH, AMZN and GOOGL.
  - Added: MU, NTRA, NFLX, CRM, CRDO, TSM, BABA, NVO and SPCX.
- **Forms:**
  - 10-Ks filed in 2025 for 12 issuers;
  - 20-Fs filed in 2025 for TSM, BABA and NVO, which are foreign private
    issuers;
  - 10-Qs filed in 2025 for AMZN and GOOGL;
  - for SPCX, the 10-Q filed in 2026, because it listed in 2026 and has no
    10-K yet.
- **Fetch.** All 18 documents were fetched, and no issuer had to be replaced.
  JPM's and BAC's 10-Ks had dropped out of EDGAR's recent-filings list, so
  `fetch_edgar.py` was extended, with the user's approval, to read the
  older-filings pages.
- **Duplicates.** Two RCQ NVDA primaries are the same filings as fixtures and
  are skipped.

### Summary figures

| Measure | Offline 91 | EDGAR 18 | Corpus 109 |
|---|---|---|---|
| Tables checked | 2,131 | 2,489 | 4,620 |
| Check 1: tables with value failures | 141 | 739 | 880 |
| Check 1: value tokens | 185 | 1,486 | 1,671 |
| … header role | 102 | 159 | 261 |
| … label role | 38 | 824 | 862 |
| … body role | 45 | 503 | 548 |
| Reported tokens: reference | 41 | 60 | 101 |
| Reported tokens: marker | 0 | 14 | 14 |
| Ambiguous tokens | 0 | 0 | 0 |
| Check 2: tables with findings | 0 | 11 | 11 |
| Tables without output | 21 | 552 | 573 |
| Documents whose two rendering modes disagree | 0 | 0 | 0 |

- **No-output tables inside check 1:** the 573 tables without output and their
  1,208 tokens are part of the 880 tables and 1,671 tokens. Without them,
  check 1 has 307 tables and 463 tokens corpus-wide: 120 and 139 offline, 187
  and 324 for EDGAR.
- **Mode agreement:** normal and capture mode give identical findings in all
  109 documents.
- **Preview:** the 91 offline documents reproduce the plan's preview figures
  exactly, including the D3 counts (178 tables with word losses, 54 of them
  without a check-1 failure).
- **Spread:** value failures occur in 44 of the 109 documents (32 offline, 12
  EDGAR).
- **Check 2:** the 11 check-2 tables hold 37 row findings. They are the first
  check-2 findings on real data.

### Classification

The 7 fixtures and 20 META/RDDT primaries were reviewed in revision 6.
`parity_impl.py` confirms that their findings are unchanged: 27 documents, 0
finding mismatches, 0 header-row mismatches. Every other flagged table was
classified: 775 tables in 82 documents.

| Verdict | Tables | Value tokens |
|---|---|---|
| Genuine loss | 754 | 1,519 |
| False positive | 20 | 22 |
| Mixed: BABA 75, one genuine token and four false positive | 1 | (included above) |
| **Total** | **775** | **1,541** |

Genuine losses by cause (BABA 75 included):

| Cause | Tables | Value tokens |
|---|---|---|
| Page header or footer table discarded on purpose (`parser.py:_is_footer_element`) | 573 | 1,208 |
| Column merge drops a row-0 cell (`TableParser._merge_grid`): captions, period and column headers, paragraph cells, first-row amounts | 180 | 308 |
| One-row PART normalization drops cells (`_one_row_table_to_text`, CAT 7) | 1 | 2 |
| A space inserted in "March 31" at an inline-run boundary (`_one_row_table_to_text`) | 1 | 1 |

The column-merge losses are the deferred defect from Background. They include
amounts a reader needs: JPM's reported noninterest revenue (84,973 / 68,837 /
61,985), opening balances in SPCX, TSLA and CRM, a first maturity bucket in
SPCX, and CAT 33's first-row U.S. GAAP figures.

### False positives

**No observed drift from the v6 prototype.** For every false positive, the v6
prototype reports the same finding. Across all 82 documents, v6 agrees with the
implementation on every finding. The one difference is a row-role label on TSM
487, a genuine loss, where v6's row indexing is wrong.

**Correction (Round 6, 2026-10-04).** This record first read that agreement as
"Implementation defects: 0", with every false positive a definition case
awaiting decision. Agreement with v6 proves only that the implementation did
not drift from that prototype. It is not zero defects against this spec. The
implementation followed the plan's triage, but Round 6 does not accept that
triage as a correctness proof. These contract defects are shared by the code
and v6:

- **F4, identifier asymmetry.** Source cells have their identifiers extracted
  (`classify_cell()`), but output exhibit-index cells, header lines and check-2
  lines are tokenized by whole cell, against Definitions' symmetric rule.
- **Note (b), marker joining.** `<sup>1<span>0</span></sup>` gives markers `1`
  and `0`, not `10`.
- **F5, incomplete multipart identifier syntax.** On top of F4's asymmetry,
  `Exhibit 10.11.2` is recognized only as `10.11`, leaving `2` enforceable.
- **Note (c), a marker after a short negative** (Round 6 finding 1). In
  `(96) (1)` the marker stays a numeric `-1`, so it can conceal a deleted
  amount `-1`, against the value-protection rule.

Round 6 also requires fixing, before Phase B, source-tokenization blind spots
that the current definitions themselves produce (finding 2): glued unit
suffixes and currency codes (`1,097bps`, `RMB8,400`) and a number before an
unmatched ")" (`due 2029)`). See "Glued text" and "Tokenizer blind spot" below.
A quantity that never enters the source tokens cannot be protected by check 1.

Each subset was compared by running `completeness_v6.analyze(html,
capture=False)` on the whole document and comparing every table that either
side flags: value tokens and roles, reported classes and check-2 messages.

- **JPM and BAC:** every finding is identical (341 of 341 and 195 of 195).
- **The other 12 EDGAR documents with flagged tables (Part B):** every finding
  is identical, except for the TSM 487 role label.
- **The 64 offline documents** (12 NVDA primaries, 52 RCQ exhibits): 0
  mismatches.
- **CRDO, GOOGL, NFLX and NTRA:** these have no flagged table. They were compared
  in the record's fix round: 0 differences, and the same counts of tables with
  numbers (57, 70, 79 and 83).

`parity_impl.py` covers the other 27 documents.

**Every check-2 finding in the corpus is a false positive: all 11 tables, 37
rows.** None of them is a real reordering.

| Cause | Tables | Value tokens | Check-2 rows | Reported tokens | Candidate definition change |
|---|---|---|---|---|---|
| F1. Relative-positioned superscript glued to the digits or letters beside it ("Statement 11", "20341") | 8: KO 32, 43, 44, 50, 59, 63; NVO 34; CAT 61 | 14 | 0 | 0 | 4 tokens: see "Glued text"; 10 tokens: see "Raised digits" |
| F2. Currency code glued (`RMB8,400` gives `400`) | 1: BABA 75 | 4 | 1 | 0 | See "Glued text" below |
| F3. Prose dash glued ("par value -10") | 1: UNH 68 | 1 | 0 | 0 | See "Glued dash" below |
| F4. Exhibit-index output tokenized by whole cell: "(See Exhibit 4.1)" gives `4.1)`, which is rejected | 5: BAC 358, AMZN 52, BABA 19, MU 68, MU 69 | 0 | 30 | 32 | Split identifiers on the output side in every mode, or treat an unmatched trailing ")" as punctuation |
| F5. Three-part exhibit number ("Exhibit 10.11.2") split on the source side only | 2: KO 110, 112 | 1 | 1 | 1 | The same, plus an identifier pattern that takes three-part numbers |
| F6. Check-2 pointer is inclusive, so a row matches the previous row's line again | 2: CAT 25, SPCX 41 | 0 | 2 | 0 | Search strictly after the pointer first |
| F7. A headerless table's first data row became the header line, which check 2 skips | 1: CAT 143 | 0 | 1 | 0 | None proposed yet |
| F8. Unit suffix glued (`1,097bps` gives `1`) | 1: JPM 367 | 2 | 2 | 0 | See "Glued text" below |
| **Total** | **21** (BABA 75 included) | **22** | **37** | **33** | |

The keys F1–F8 are classification.md's. The candidates in the table come from
Parts A and B of the classification. The exception is the three-part identifier
pattern, which is the record writer's. The option sets under "Raised digits" and
"Glued dash" below give their own sources.

Cell text joins inline nodes without a space, while TableParser joins them with
one. The cases differ by the kind of boundary, so they need separate decisions.

- **Glued text** (letter and digit meet at an element boundary): F2 (BABA 75),
  F8 (JPM 367) and 4 of the 14 superscript tokens. Those 4 are KO 32, 43 and
  44 ("equivalents1,2" and "Fair Value1,2" give `2`) and KO 59's `5`
  ("Total4,5").
  - Candidates (Part A): insert a space where an inline-element boundary
    separates a digit from a letter, or let the tokenizer accept a number
    followed by a unit suffix (F8 only).
  - Either must keep NVDA's kerned digits (`1,2<span>34</span>`) concatenated,
    which is a review case.
  - The same mechanism also hides values: 12 of JPM 367's 15 "Nbps" cells
    yield no source token at all, so those values are never checked.
  - **Decided (Round 6):** separate a letter and a digit where an
    inline-element boundary divides them, on both sides, for F2, F8 and these 4
    F1 tokens. Kerned digit joins and sign and decimal boundaries stay intact.
    A narrow supported-unit tokenizer may supplement it for F8; a generic
    "digits inside any word" rule is not approved. A code fix before Phase B,
    tested on the full quantities (8400, 1097, 2717 and the twelve unchecked
    cells), not just on the old false positives disappearing.
- **Raised digits** (the other 10 superscript tokens). These join a digit or a
  comma to a digit, so the candidates above do not apply.
  - The cases: KO 50 ("31," + "1" gives `311`), KO 59 ("2098" + "2"), KO 63
    ("2024" + "2"), NVO 34 (six patent years such as "2034" + "1") and CAT 61
    ("Statement 1" + "1").
  - Each superscript is a relative-positioned span with a negative `top`
    (-2.44 to -3.15 pt). Definitions deliberately do not treat relative
    positioning as a marker, because NVDA kerns digits with it.
  - In the six NVDA fixtures, the 126 relative-positioned digit spans carry no
    `top` (checked in the record's fix round).
  - Options: (a) and (b) are the record writer's; (c) traces to Part B's note 6.
    - (a) treat a relative-positioned digit span with a negative `top` as a
      footnote marker, after checking NVDA's kerning on more filings;
    - (b) accept these as known false positives;
    - (c) read them literally as genuine losses, since the fused source token
      (`20341`) is absent from the output. classification.md calls this "Two
      readings".
  - **Decided (Round 6): (a)**, only for a relative-positioned, marker-like
    digit span with a genuinely negative `top`. Ordinary relative positioning
    stays insufficient. Astra checked all 38 NVDA documents in the corpus: none
    of their 793 relative-positioned digit spans has a negative `top`. (b) is
    rejected as the permanent remedy, and so is (c)'s reading of `20341` as a
    genuine loss. Pin the raised cases and no-`top` kerning controls, including
    loss of the real adjacent year or amount, before enforcement relies on it.
- **Glued dash** (F3, UNH 68). In
  "par value -`<ix:nonfraction>10</ix:nonfraction>`" the dash ends one text
  node and the number sits in the next element. Cell text reads -10, but the
  XBRL fact is +10, and the output "par value - 10" gives 10. None of the
  candidates above applies.
  - Options (the record writer's):
    - (a) read a dash as a minus sign only when it touches the digits within
      one text node. A real minus sign written outside its XBRL element would
      then read as positive.
    - (b) accept it as a known false positive (1 token in the corpus);
    - (c) read it literally as a genuine loss of `-10`.
  - **Decided (Round 6): (b).** UNH 68's single `-10` stays a documented known
    false positive, the only check-1 false positive Round 6 accepts as
    permanent. Phase B strict rejects it unless a separately reviewed narrow
    exception is approved. (a) is rejected, because a genuine minus sign may sit
    outside its XBRL element, and so is (c). DOM text-node boundaries do not
    decide sign.
- **Identifier wording.** Definitions say the identifier rule "applies on the
  source and output sides". The implementation and v6 do not apply it to
  exhibit-index output cells, header lines or check-2 lines. Either the wording
  or the definition should change.
  - **Decided (Round 6):** keep the symmetric wording and fix the code (F4,
    F5). Apply the same identifier extraction in every mode, output context and
    check-2 line, recognize complete dotted identifiers, and keep identifier
    occurrences unavailable to values. Protect genuine values in the same cell
    or row and the earlier Note 1 / Note 2 regressions, and include adjacent
    genuine amounts in the deletion tests. Excusing the asymmetry in the
    wording is rejected. A code fix before Phase B.
- **Reported references.** 61 of the 101 reported references are also false
  positives, from the same identifier asymmetry. 33 of them are the reported
  tokens in the F4/F5 rows above. They are reported only. None of the 115
  reported tokens is a real value in a reported class.
  - **Round 6:** these need correcting too. Their report-only class does not
    justify asymmetric extraction.
- **Tokenizer blind spot.** A number followed by an unmatched ")" ("due 2029)")
  is dropped on both sides, so its loss goes undetected.
  - **Round 6 (finding 2):** a code fix before Phase B. Recognize unmatched
    closing prose punctuation without dropping the number before it or turning
    balanced accounting negatives positive. Any shared-normalizer change needs
    numeric-trace and rendering regressions, as the euro change showed.

### Definition questions from deliberate parser behaviour

These recommendations were for Astra and the user. Each one says where it comes
from. Part B of the classification raised both questions without proposing
options. Parts A and C also raised question 1, with options. Round 6 decided
both on 2026-10-04; each recommendation below is kept, marked with its outcome.

**1. Page header and footer tables.** All 573 tables without output are page
furniture that the parser removes on purpose.
`_process_absolutely_positioned_container` passes an absolutely positioned
`bottom:0; width:100%` child to `_is_footer_element`, then only reads a page
number from it.

- **Where:** JPM 334, BAC 180, NVO 38 (a running page header) and the NVDA
  exhibits 21, with 1,208 value tokens in all.
- **Task 6 watch item:** no HTML table inside a positioned container was
  falsely reported as "no output". Every no-output table is a page header or
  footer that the parser deliberately discards.
- **Content:** page numbers and running titles in JPM, BAC and NVO. In three
  NVDA policy exhibits, the footer is the only statement of the effective or
  last-updated date.
- **Scope:** these are HTML tables, so the positioned-div deferral does not
  cover them.
- **Phase B effect:** strict enforcement would fail JPM, BAC, NVO and the three
  NVDA exhibits on these tables. NVO and the three exhibits have no other
  genuine value loss, so they would keep failing after the table-merge fixes
  land.
- **Options:** (a) and (b) come from Parts A and C; (c) is the record writer's.
  - (a) Keep them as enforced findings. Phase B then fails these filings until
    the parser keeps footer text or the expected-failure list accepts them.
  - (b) Exclude table units inside elements that `_is_footer_element`
    classifies as page furniture, as hidden nodes are excluded.
  - (c) Keep the units, but report their tokens only, as a page-furniture class
    beside marker and reference. The class is decided by the parser's own
    `_is_footer_element` test.
- **Recommendation: (c).** This is the record writer's synthesis; Parts A and C
  gave options without choosing.
  - Strict stays usable on filings with table-based page footers, and the
    check follows the parser's own decision.
  - The NVDA effective-date losses stay visible in diagnostics.
  - Whether the parser should keep footer text is a parser question for a
    separate spec. A footer `<div>` without a table loses the same text and
    produces no finding (an NVDA exhibit shows this).
- **Decided (Round 6): (c)**, keyed on the parser's actual discard.
  - Classify as report-only page furniture only the tokens in the subtree the
    parser actually discards, recorded from its `_is_footer_element` decision.
    Do not infer the class from an empty output, and do not reclassify a
    similarly styled ancestor the parser did not discard.
  - Keep the units, ordinals and missing-token and no-output visibility,
    including the NVDA effective and updated dates. Other unexplained
    no-output tables stay value failures.
  - Moving exactly the 573 tables / 1,208 tokens to the new class leaves 307
    check-1 value tables / 463 tokens, before other fixes. The new counts go in
    a later run; the figures here stay as recorded.

**2. CAT 7, a one-row PART table.** The PART branch of
`_one_row_table_to_text` renders "Part III | 2025 Annual Meeting Proxy Statement
… within 120 days …" as "PART III" only, losing `2025` and `120`. The ITEM
branch keeps its title.

- **Options** (the record writer's):
  - (a) Keep it as a genuine finding, and have the PART branch keep the other
    cells, in the table-merge and header-rules spec.
  - (b) Treat the normalization as intended, and exclude one-row PART heading
    tables from the units.
- **Recommendation: (a).** This is the record writer's synthesis. The dropped
  cell says where Part III's information comes from. One table in 109 documents
  can sit on the expected-failure list until the parser change lands.
- **Decided (Round 6): (a).** The missing `2025` and `120` are genuine losses.
  Fix the PART branch in the table-merge and header work; do not exclude
  one-row PART tables. The loss stays on the development expected-failure list
  until fixed, which does not exempt it from strict.

### A detection gap: the BABA/TSM header shift

This is not deliberate parser behaviour. It is a loss that neither check
detects, caused by the deferred column-merge defect. Part B of the
classification found it and rated it its most material finding for trading
use, but did not propose options.

The `_merge_grid` merge that drops captions also merges a header-only column
into the column on its left. Year and currency headers then stand one column
left of their values.

- **Example, BABA 24 (income statement):** FY2023 revenue sits under "2024",
  FY2024's 941,168 under "2025", and FY2025's RMB 996,347 under a blank header.
  A reader would take 941,168 as FY2025 revenue.
- **Extent:** a rough heuristic flags 66 tables (36 BABA, 30 TSM; not each one
  verified), and it misses some, such as BABA 8 and 24.
- **Detection:** check 1 flags these tables only for the lost caption token
  (`31`). Check 2 excludes header lines by design.
- **Options** (the record writer's):
  - (a) Leave it to the table-merge and header-rules spec, with BABA 24 and TSM
    79 and 312 as regression cases.
  - (b) Add a report-only header-alignment check that compares each source
    header cell's column span with the output column its text lands in.
  - (c) Record it as a known limit only.
- **Recommendation: (a) with (b).** This is the record writer's synthesis.
  - Make it a first case of the table-merge and header-rules spec, and define
    the alignment check there, since no Phase A check can see it.
  - Until then, passing check 1 and check 2 is not proof that a value sits
    under its correct period. `README.md` and `docs/usage/direct-conversion.md`,
    where they describe what strict does not check, should say so.
- **Decided (Round 6): (a) plus (b).** (c) alone is rejected: the caveat is
  needed now and must remain, but it is not the remedy.
  - BABA 24, TSM 79 and 312, and a separate-currency layout (euro and amount
    cells under spanning 2025/2024 headers) become regression cases in the
    table-merge and header work. They assert each amount's period and currency,
    not just token presence or a passing strict conversion.
  - That work also defines the report-only alignment diagnostic, from
    source-to-output column provenance, allowing legitimate span and
    currency-column merges.
  - Numeric completeness and correct period attribution stay separate claims.
    The rough 66-table count is not an enforcement rule.

### D3 measurement

- **Population:** 212 tables lose words but have no check-1 failure, with 1,020
  missing words. That is out of 999 tables with any word loss.
- **Sample:** every 7th table from index 3 in document order (k = 7, offset 3).
  That gives 30 of the 212, covering all four groups that have such tables.
- **Result:** 18 genuine text losses and 12 noise, a **noise rate of 40%**
  (95% Wilson interval about 25–58%).
  - Genuine: column headers and table titles dropped by the column merge (12);
    "Filed Herewith" X marks fused into another column (3); signature dates
    dropped (3).
  - Noise: the header of an all-empty column removed with the column (8);
    words split at inline-run boundaries (4).
  - Header-fusion reordering, the expected noise, caused none.
- **Top missing words:**
  - All 999 tables: form 331, jpmorgan 286, chase 286, co 286, of 250, ended
    186, bank 183, america 183, march 140, december 99. These come from page
    header and footer tables and from lost period headers, which already fail
    check 1.
  - The 212 word-only tables: herewith 47, filed 46, by 31, date 21.
- **Examples:**
  - Genuine: TSM's executive-compensation headers ("Salary", "Bonus", …) are
    lost, leaving five amounts unlabelled.
  - Genuine: RDDT's "Filed Herewith" X marks now sit under the exhibit
    "Number" column.
  - Noise: MSFT's "None" is rendered "N one".
  - Noise: META's empty "Filed Herewith" column is removed with its header.
- **Recommendation (from Part C of the classification), for Astra and the
  user:**
  - Do not add an enforced word check. 40% noise is too high for a gate, and D1
    and D4 enforce values only.
  - Add a per-table word-multiset measure as a report-only diagnostic in Phase
    B, with two noise filters. One joins intra-word splits and tokenizes
    Unicode letters. The other ignores header words over columns with no body
    content.
  - Re-measure on this corpus before adopting it, with a target below 10%
    noise.
  - Fixing the column-merge and empty-column rules in the table-merge spec
    removes most genuine word losses. The measure then serves mainly as a
    regression net.
- **Decided (Round 6, decision 5):** no enforced word check. The 40% figure
  stands; the recorded 30 tables match `word_only_tables[3::7]`, and the Wilson
  range is descriptive for this issuer-clustered sample.
  - The filtered report-only diagnostic is a Phase B candidate. The filters are
    approved with limits: join only proven fragments of one source word and
    tokenize Unicode letters, and ignore a header only when its entire source
    column span has no nonempty body content (zero and X marks count as
    content). Do not globally remove whitespace or join arbitrary adjacent
    words. Spanning titles and nonempty "Filed Herewith" columns must survive.
  - Re-measure after the filters and the page-furniture and renderer changes,
    with preserved and deleted header controls and newly sampled residuals.
    It is adopted, as report-only, only below 10% noise. The projected
    elimination of 11–12 noise cases is not measured acceptance evidence.

### Overhead

- **Decision.** Phase A accepts up to +25% parse time against unchanged `main`
  on the fixtures in total, by the user's decision of 2026-10-03. The 10% target
  moves to Phase B. "Where it runs" and the acceptance criteria now say this.
- **Corpus timing (indicative).** 18 EDGAR documents, normal mode, best of two
  runs:
  - `get_pages()` in total: 51.4 s with the checks off and 59.8 s with them on,
    +16.4% (from the unrounded totals);
  - `check_tables()`: 6.7 s in total, the slowest 1.14 s (BAC);
  - the longest table output: 68 lines (JPM).

  Other jobs shared the machine. The baseline is the branch with the checks
  off, not unchanged `main`, so this is not the acceptance measure.
- **Fixtures.** Plan Task 12 measures the overhead against unchanged `main` on
  the fixtures and reports it in the PR.
- **Confirmed (Round 6, decision 7).** Up to +25% in total for Phase A, with
  the 10% target from Phase B. Round 6 checked the measurement PR #4 records,
  about +20.5% in total, but did not rerun a benchmark. Phase B measures
  against an identified unchanged pre-feature baseline again, not against
  Phase A, includes any adopted new diagnostics, and records per-fixture and
  total figures. Still open: correct the timing helper's stale docstring when
  it is next updated.

### Implementation review notes for decision

These come from the per-task code reviews and are recorded for Astra. Round 6
decided each one; its ruling and timing follow each note. Following the plan
and matching v6 show no drift; they do not make (b) or (c) correct (see False
positives).

- **The plan's code.** In each case the implementation is the plan's code as
  written, so it follows the plan.
- **v6.** For (b) to (e), the plan's code also matches the v6 prototype, which
  behaves identically. v6 has no check 3, so (f) and (g) have no v6
  counterpart.
- **v6 and (a).** v6 applies its `€`/`£` translation only inside its own
  tokenizer, so the rendering effect in (a) could not arise there. The plan
  follows this spec, which puts the change into `normalize_numeric_token`.

The notes:

- **(a) User decision, Task 1: euro and pound rendering.** The `€`/`£` change to
  `normalize_numeric_token` also changes Markdown rendering, because
  `table_parser` uses that function to merge split numeric cells.
  - `(€567` + `)` now renders as one cell, `(€567)`, as `$` already did.
  - A TableParser test pins it, and the user accepted it on 2026-10-03.
  - **Strict's numeric trace changes too.** `normalize_numeric_token` also
    feeds strict's numeric trace (`trace_numeric_failures`), so strict
    pass/fail changes the same way.
    - A euro or pound amount whose currency sign sits in its own cell under a
      spanning header (`€ | 1,234`, `€ | (567 | )`, `£ | (567 | )`) falsely
      failed strict as "untraceable" on `main`. It now passes.
    - Rare split layouts that already fail for `$` now fail for `€` and `£`
      too: those where the `)` cell sits under its own `<th>`, such as
      `(€567 | )` and `(£5.6 | )%`.
    - No corpus document changed: 111 documents gave identical strict warnings
      on `main` and on the branch.
    - A strict test now pins the common layout, and the CHANGELOG discloses
      the change. The user decided this on 2026-10-04.
  - The spec's statement that rendering is unchanged should carry this
    carve-out. The nearest sentence is the Purpose's "It does not change how
    tables are parsed."
  - The acceptance criterion on identical rendering with the checks on and off
    is unaffected, because the normalizer applies either way.
  - **Round 6:** both side effects accepted. Wording now: the Purpose and the
    acceptance criteria state the narrow exception (done 2026-10-04). The
    checks-on/off rendering criterion stays unchanged. The strict currency
    test's output-content assertions are addressed on branch
    `docs/table-completeness-round6` (`0787eb1`, `11707e3`), pending merge.
    Header alignment, with its alignment assertions, is fixed in the
    prerequisite parser work; do not revert currency support to hide the gap.
- **(b) Footnote markers that span inline nodes.** `<sup>1<span>0</span></sup>`
  yields the marker tokens `1` and `0`, not `10`, because marker pieces are
  joined with a space. The spec says text nodes are concatenated.
  - Marker tokens are report-only. In rare cases a split digit could claim a
    position a value needed.
  - None of the corpus false positives comes from it.
  - **Round 6 timing: code fix before Phase B** (finding 1). Keep the
    concatenation rule: join inline pieces within one marker, keep boundaries
    between distinct markers, and never let invented marker digits consume a
    genuine amount's occurrence.
- **(c) A trailing marker after a short negative.** In `(96) (1)` the marker
  is not split off, so `(1)` stays a numeric `-1`; `(196) (1)` splits correctly.
  A surviving marker is then reported missing, and its `-1` can cover a lost
  value `-1` in pass 2.
  - **Round 6 timing: code fix before Phase B** (finding 1, reproduced in both
    modes). Keep the initial accounting negative and split off later markers
    whatever their digit count. Deletion tests must prove a surviving marker
    cannot satisfy the missing amount. Pin the unchanged, amount-deleted and
    marker-deleted variants in both modes, including duplicate or unpaired
    labels and split accounting cells. No wording relaxation.
- **(d) Check-2 row numbers.** "source row <i>" counts data rows, not source
  rows as Definitions has it: JPM 367's data rows 9 and 29 are table rows 12
  and 35. Either the spec wording or the numbering should change.
  - **Round 6 timing: Phase B code.** Keep "source row" as documented and
    number actual one-based source rows within the unit, counting skipped and
    header rows.
- **(e) Check-2 search cost.** The search is quadratic on very large lossy
  tables: 8 s for a synthetic 2,000-row table in which every row lost a column.
  The corpus timing shows no quadratic blowup on real filings (slowest
  `check_tables()` 1.14 s, longest table 68 lines), so a parity-preserving
  optimization is proposed as a Phase B follow-up.
  - **Round 6 timing: Phase B code,** alongside the F6 and F7 changes,
    preserving multiplicities and genuine ordering detection. Verify a large
    lossy table and corpus parity under the revised definitions. Correction:
    ordinary corpus timings do not rule out quadratic behaviour. Round 6 did not
    retime the 8 s measurement.
- **(f) `numeric_recall` and list markers.** Recall comes out low when an
  output line starts with "N. " ("2. Summary of …"), because
  `_visible_markdown_text` strips list-marker-shaped numbers. A lossless probe
  gave 0.75. Recall is diagnostic only.
  - **Round 6 timing: Phase B code;** Round 6 reproduced the 0.75. The
    limitation is documented now under Check 3.
- **(g) Check 3's normalizer** (plan reviewer note 2). The accuracy suite's
  `normalize_numbers` lives in `tests/` and cannot be imported from `src/`.
  The check-3 sentence "the same way as the accuracy suite's
  `normalize_numbers`" should change to `quality._normalized_numbers()` over
  the visible source and Markdown text that `build_diagnostics()` already
  computes.
  - **Round 6 timing: wording now.** Done 2026-10-04 in Check 3. This does not
    excuse (f)'s extraction mismatch.

### Round 6 rulings

Astra's Round 6 (2026-10-04) is in the review record, from "# Round 6 (Phase A
corpus record)". It recomputed the summary figures and the classification counts
from `results.json`, and reran `corpus_phase_a.py` and `parity_impl.py` with
identical results. The figures above stay as recorded; new counts go in a later
run.

- **Outcome.** Phase A is complete as a report-only release, with the known
  limits recorded here. It is not a clean correctness review, and not approval
  to enable Phase B enforcement.
- **Accepted:** the 18-issuer replacement, the logging levels (with the scope
  corrected in Diagnostics and API), checker-error isolation for Phase A only,
  the header-shift caveat, and the overhead decision.

Definition questions:

| Question | Ruling |
|---|---|
| 1. Page header and footer tables | (c): a report-only page-furniture class, keyed on the parser's actual `_is_footer_element` discard. Other no-output tables stay value failures. |
| 2. CAT 7 | (a): a genuine loss, fixed in the table-merge and header work. |
| BABA/TSM header shift | (a) plus (b): renderer regressions and a report-only alignment diagnostic in the table-merge and header work. (c) alone is rejected; the caveat stays. |

F1–F8 (all 11 check-2 tables and 37 rows stay accepted false positives in this
baseline):

| Cause | Ruling |
|---|---|
| F1, glued or raised markers | Letter/digit DOM-boundary rule, plus Raised digits (a) for marker-like spans with a negative `top`. (b) is rejected as the permanent remedy, and (c)'s genuine-loss reading is rejected. |
| F2, glued currency code | Inline-boundary letter/digit split on both sides: 8400, not 400. |
| F3, glued dash | Glued dash (b): UNH 68's single `-10` stays a documented known false positive, the only check-1 false positive Round 6 accepts as permanent. Phase B strict rejects it unless a separately reviewed narrow exception is approved. |
| F4, identifier asymmetry | Fix the code: symmetric identifier extraction in every output context and check-2 line, plus unmatched-prose-punctuation repair. A wording excuse is rejected. |
| F5, multipart identifiers | Complete dotted identifiers, identical on both sides, wholly report-only. Protect genuine values in the same cell or row and the Note 1 / Note 2 regressions; include adjacent genuine amounts in deletion tests. |
| F6, inclusive pointer | Search strictly after the previous match first, with row consumption and provenance. Keep the row/column-swap mutation tests. |
| F7, first data row in header | Keep the promoted row's identity, or mark it unevaluable. |
| F8, glued unit suffix | The F2 boundary rule, recovering the full 1097, 2717 and the twelve unchecked cells. No generic digits-in-words rule. |

All 21 F1–F8 tables, including BABA 75 with its genuine caption `31`, go into
regression evidence. The 61 falsely reported references need correcting too.

Before enabling Phase B enforcement (Round 6's prerequisites):

1. Reconcile the spec, this record and the public documentation with these
   decisions: the narrower parity claim, the currency exception, logging,
   checker-failure semantics, metadata and recall. The spec and
   classification.md parts are done in this revision (2026-10-04). README, the
   usage documents and the CHANGELOG are addressed on branch
   `docs/table-completeness-round6` (`aaca4f2`, `1a3f1dc`, `095888f`,
   `ef0e727`), pending merge.
2. Land the prerequisite table-merge and header fixes and regressions: CAT 7,
   BABA/TSM, separate currency columns and genuine word and header losses.
   Define the report-only alignment diagnostic there.
3. Fix the marker and source-token blind spots and symmetric identifiers, and
   implement page furniture as an explicit reported class. Genuine numeric
   losses and ambiguous shortfalls stay enforced whatever their digit count.
   UNH 68's single `-10` stays a documented known false positive, the only
   check-1 false positive Round 6 accepts as permanent; Phase B strict rejects
   it unless a separately reviewed narrow exception is approved.
4. Make failed required checks visible and fatal to Phase B strict. Revise
   check-2 matching and numbering without enforcing check 2. Address the
   search-cost and recall follow-ups, and re-measure any proposed D3
   diagnostic.
5. Re-run the full suite, both rendering modes and this corpus under the
   revised definitions. Classify changed and new findings, keep the deletion
   mutations, update expected failures only with explanations, and meet the
   Phase B 10% overhead target. Land the minor RCQ version bump and CHANGELOG
   entry when check-1 enforcement is enabled.

The expected-failure list is a development baseline, not a runtime exemption.
At the enforcement decision it must be empty or hold only explicitly reviewed
residuals.

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
  only in the new fields and, for check-1 value failures, in the log.
- **Logging** (scope corrected in Round 6, 2026-10-04). Under `warn` and
  `strict`, `enforce_quality()` logs one WARNING summary per document that has
  check-1 value failures, and each table's value-failure finding at INFO.
  - Reported marker and reference tokens and check-2 findings are not logged in
    Phase A. A document with only those emits no completeness log line.
  - Round 6 decided that the Phase B update logs them at INFO too, keeping the
    WARNING summary for value failures only.
- **Checker failure** (Phase A behaviour, documented in Round 6, 2026-10-04).
  An exception raised by `check_tables()` (checks 1 and 2) does not fail the
  conversion: `get_pages()` logs it at ERROR and continues with
  `table_report = None`. Only that call is guarded. Check 3 (`_numeric_recall()`
  in `build_diagnostics()`) and the per-table recording in `_stream_pages()` and
  `_process_element()` run outside the guard, so an exception there propagates.
  - After a `check_tables()` failure, apart from its log line, the diagnostics
    are indistinguishable from policy `off`: empty findings, `tables_checked` 0,
    `numeric_recall` None, nothing added to `warnings`, and empty XLSX
    `completeness`. Round 6 accepts this for Phase A only.
  - **Phase B requirement:** a structured distinction between disabled checks,
    a completed check with zero eligible tables, and a failed check. Phase B
    strict must reject a failed required check; warn may return output with the
    failure recorded. Tests cover the Markdown, pages and XLSX entry points,
    including a failure before any finding was collected. A successful
    zero-table result cannot be inferred from an exception.
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
- **Where it runs.** `_process_element()` records the output segment of each
  outermost table (`self.table_outputs`, keyed by node), as rendered by
  `_render_table()`. The `_stream_pages` table site records the unit's page
  and snapshot ordinal. (Wording corrected on 2026-10-04, after Round 6.)
  - **Snapshot ordinals** come from one counter shared by every mode, the one
    that numbers snapshots in capture mode, so findings name the same snapshot
    either way.
  - **Header rows** come from `table_completeness.header_row_count()` in every
    mode. It applies the snapshot builder's placement rules and
    `xlsx_tables._header_count()` without building a snapshot. Normal mode does
    not call `snapshot_html_table()` per table, and the checks never add a table
    to `_unreliable_tables` or `table_snapshots`.
  - The checks run in `Parser.get_pages()` after page assembly. They need no
    elements, so they also run with `include_elements=False`.
  - Hidden nodes are computed once per document.
  - Overhead against unchanged `main` on the fixtures in total is at most +25%
    of parse time in Phase A, by the user's decision of 2026-10-03, measured in
    the implementation PR. The 10% target applies from Phase B.

## Policy and rollout

1. **Phase A (this implementation).** Compute all three checks under every
   policy except `off`. Strict does not raise on them yet.
   - Expose the results according to D2 and the XLSX fields above.
   - Add a fixture test that pins the current failures as an explicit expected
     list. It fails when a new loss appears, and also when a listed loss
     disappears without the list being updated.
   - Run the checks on a wider corpus of at least 50 filings and record any false
     positives in this spec. The 7 fixtures and 20 RCQ filings above count
     toward that total. Done: see "Phase A corpus run" (109 documents, 55
     filings), which Astra reviewed in Round 6 on 2026-10-04.
2. **Phase B (after the table-merge and header-rules spec lands).**
   - It is also gated on Round 6's prerequisites (see "Phase A corpus run >
     Round 6 rulings").
   - Strict raises `ParseQualityError` on value-class check-1 failures,
     including ambiguous shortfalls. Tokens in the report-only page-furniture
     class that Round 6 approved are not value-class.
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
- No new strict failures in Phase A: the existing suite passes unchanged. One
  narrow exception was accepted in Round 6 (2026-10-04): the euro/pound
  normalizer change (see Purpose), which also merges split euro and pound
  negatives in rendering. It changes strict's numeric trace: an own-cell
  `€ | 1,234` no longer fails falsely, and rare split layouts that already fail
  for `$` now fail for `€` and `£` too.
- Diagnostics and XLSX results remain picklable, and existing positional
  construction of `ParseDiagnostics`, `XlsxExportResult` and `XlsxTableResult`
  still works.
- Parse-time overhead against unchanged `main` is +25% or less on the fixtures
  in total in Phase A, by the user's decision of 2026-10-03. The 10% target
  moves to Phase B.
- README and `docs/usage/direct-conversion.md` describe what strict does and does
  not check, including the size thresholds.

## Decisions for review

All five now have outcomes. Round 6 (2026-10-04) decided D1 and D3 and
confirmed D4; D2 shipped as recommended in PR #4, as the plan assumed; D5 was
resolved in revision 2. The recommendations are kept as they went to review,
with each outcome beside them.

- **D1. Enforcement timing.**
  - Recommended: report-only now, and enforce value-class check-1 failures in
    strict in Phase B.
  - Alternative: enforce now. That makes 5 of the 7 fixtures (the AAPL 10-K,
    nvda-2002, the NVDA 10-Q and both NVDA exhibits) fail strict immediately.
    It would also fail 18 of the 20 RCQ META/RDDT filings, breaking callers
    until the parser fixes land.
  - Check 2 stays report-only either way until the wider corpus run.
  - Phase A corpus run: all 37 check-2 rows (11 tables) are false positives,
    so check 2 stays report-only until their causes are decided. F4–F7 cause
    34 of the rows, and the glued-text cases F2 and F8 cause 3.
  - **Decided (Round 6):** report-only now. Phase B enforces check-1 value
    loss only, including ambiguous shortfalls, subject to the page-furniture
    class. Check 2 stays report-only until a separate review of its real-data
    accuracy; passing the synthetic mutation tests is not enough. Check 3 and
    D3 stay diagnostic only.
- **D2. Diagnostics API.**
  - Recommended: add `convert_with_diagnostics(source, **kwargs) ->
    tuple[str | list[Page], ParseDiagnostics]` and leave the existing functions'
    return types unchanged.
  - Alternatives: a keyword-only `diagnostics=` out-parameter, or documenting
    `Parser.diagnostics` as the supported route.
  - **Resolved:** `convert_with_diagnostics`, as recommended, shipped in
    Phase A (PR #4).
- **D3. Text completeness.** The lost AAPL header was caught only through its
  plain-text `(1)`. A per-table word-multiset check would catch header text
  directly, at the cost of more noise from header fusion.
  - Recommended: measure it in the Phase A corpus run before deciding.
  - Measured: see "Phase A corpus run", D3 measurement (40% noise in a sample
    of 30), with a recommendation.
  - **Decided (Round 6):** no enforced word check. A filtered report-only word
    diagnostic is a Phase B candidate, adopted only if it measures below 10%
    noise on this corpus, and even then not enforced (see D3 measurement).
- **D4. Token classes.**
  - Recommended: the per-token context classes above. Markers and references
    are reported, and every other token is enforced regardless of digit count.
    Period-header tokens (`31` in "March 31,") stay enforced and appear under
    the `header` role. Ambiguous value shortfalls are enforced too, labelled so
    a reviewer can see that provenance was shared. There were none in the corpus.
  - Alternative: also enforce marker and reference tokens. That would fail
    tables over a lost footnote marker, exhibit-index column or signature date.
  - **Confirmed (Round 6),** with one addition to implement before Phase B: a
    report-only page-furniture class beside marker and reference (see "Round 6
    rulings"). UNH 68's single `-10` (F3) stays a documented known false
    positive, the only check-1 false positive Round 6 accepts as permanent;
    Phase B strict rejects it unless a separately reviewed narrow exception is
    approved.
- **D5. `include_elements=False`.** Resolved in revision 2: the checks use output
  segments, not elements, so they run in this mode too.
  - **Outcome:** resolved; Round 6 reopened nothing here.

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
