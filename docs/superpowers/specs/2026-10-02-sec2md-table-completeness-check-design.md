# sec2md Table Completeness Check Design

Date: 2026-10-02

Status: Proposed, for review

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

## Background

The 2026-10-02 repository audit (`outputs/repo-audit-2026-10-02/REPORT.md`, local)
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
**each source table only with the output elements mapped to that table**. That
comparison excludes hidden nodes and never compares navigation text against
tables, so the noise sources cited in 2026-08-29 do not enter it.

### Prototype evidence

A prototype of check 1 below ran over all seven fixtures on branch
`fix/audit-2026-10-02`, using exactly the definitions in this spec:

- 290 visible top-level tables containing at least one number, holding 8,099
  source numeric tokens.
- 11 tables flagged, 22 tokens missing. All 11 are genuine losses:
  - the three AAPL column-merge values and the AAPL repurchase-table header (4 tables)
  - the NVDA operating cash-flow row in EX-99.1 and EX-99.2 (2)
  - the `$3.5` guarantees row in the 10-Q and EX-99.2 (2)
  - the nvda-2002 period headers ("Month Ended January 31, 1998") (1)
  - the nvda-2002 `ITEM 8.` and `ITEM 9.` headings dropped from element text (2)
- No false positives on the fixtures.

A prototype of check 2 below flagged 3 AAPL rows (the same value losses) and 5
header rows that ended up in the table body, 4 of them nvda-2002 period-header
defects. In 56 tables (51 in nvda-2002) the output had no separator row, so
check 2 did not apply to them and check 1 covered them alone.

### Corpus run: RCQ META and RDDT filings

The same check ran, read-only, over the 20 primary 10-K and 10-Q documents for
META and RDDT in `E:\RCQWealth` (fiscal 2024 to 2026 Q2):

- **Volume:** 1,037 tables checked, 103 flagged, 115 material and 6 minor tokens
  missing. Default strict passed all 20 documents.
- **Most flags are lost period headers.** "Three Months Ended March 31," above a
  `2026 | 2025` row renders as `|  | 2026 | 2025 |`. Q1 statements are flagged on
  nearly every table (15–16 per META and RDDT Q1 10-Q).
- **Value rows are lost too:**
  - META commitments: `The remainder of 2024 | $ | 10,563` renders as
    `| The remainder of 2024 | $ |`.
  - META 10-K lease and debt maturities: `2025 | $ | 26,335` loses its value.
  - The META 10-K ARPP table: 9 values become 3.
- **Other losses:** an RDDT 10-K exhibit-index header fused with its first
  exhibit, which drops three columns, and signature dates in signature tables.
- **Accuracy:** every flag inspected was a genuine loss. None were false
  positives.

Check 2 reported no differences on these documents.

The unoptimized prototype added 16–23% to parse time (AAPL 0.17 s on 0.77 s;
nvda-2002 0.28 s on 1.78 s). Most of that cost is a repeated walk up each cell's
parent chain to test visibility.

## Definitions

- **Source table:** a visible `<table>` element in the parsed DOM. A table is
  visible if neither it nor any ancestor is hidden according to
  `quality._is_hidden_tag` (the rule the size ratio already uses). Nested tables
  are separate source tables.
- **Source cells:** the visible `td`/`th` cells whose nearest `table` ancestor is
  that table.
- **Source row text:** the row's visible cell texts, each taken with
  `get_text(" ", strip=True)`, joined with single spaces. Joining per row keeps
  split accounting negatives such as `(29` + `)` together.
- **Numeric tokens:** `quality._normalized_numbers` applied to the row text (for
  output, after replacing `|` with a space). For example, `$1,234` becomes `1234`
  and `(565)` becomes `-565`.
- **Mapped elements:** the elements whose `block_nodes_map` nodes include the
  table or any of its descendants. The parser already builds this map for the
  numeric trace.

## Checks

### 1. Table numeric completeness (enforceable)

For each source table with at least one numeric token:

```text
missing = Counter(source tokens of the table) - Counter(tokens of all mapped elements' content)
```

- **A table with no mapped elements** is reported as
  `table <n> produced no output (<k> numbers)`.
- **A table with any missing tokens** is reported as
  `table <n> (<element ids>): missing <token>×<count>, …`. The list is
  truncated to the first 10 tokens, and the record always gives the total count.

`<n>` is the 1-based document order of the table, which matches
`TableSnapshot.ordinal` where one exists. Output can contain extra numbers (from
repeated headers or overlap); only missing tokens count.

### 2. Table row order (report only, see decision D1)

This check applies to each mapped element whose content contains a Markdown
separator row:

1. Take the output body rows (lines after the separator) that contain numbers.
2. Take the same number of source rows that contain numbers, counted from the end
   of the table. Header rows are excluded because the parser legitimately fuses
   them.
3. Compare the two lists of per-row token tuples.

Report each table where they differ as `table <n>: row order differs at body row
<i>`. This catches column swaps and values shifted between rows, which check 1
cannot see.

### 3. Document numeric recall (diagnostic only)

Compute numeric recall over visible source text, the same way as the accuracy
suite's `normalize_numbers`. Record it in diagnostics and never enforce it. Its
job is to show losses outside tables to whoever reads the diagnostics. Making it
a pass/fail gate is the threshold the 2026-08-29 design rejected.

## Token rules

- **Weight.** Tokens with at least two digits, or with a decimal point or
  grouping separator, are *material*. Single-digit integers are *minor*: footnote
  markers `(1)`, item numbers, list markers. Both are reported; only material
  tokens can fail strict (decision D4). Of the 22 missing fixture tokens, 3 are
  minor: `-1` (the AAPL header's footnote marker), `8` and `9`.
- **Footnote markers** in `<sup>` or `vertical-align: super` spans are source
  tokens like any other. If the parser renders a marker glued to a word
  (`Programs1`), the token goes missing. That is reported, as a minor token.
- **Hidden source content** (iXBRL headers, `display:none`, `visibility:hidden`,
  the `hidden` attribute) is excluded. If the parser outputs hidden text, that
  adds extra output, which the check ignores. The hidden-content leak itself is
  tracked separately as an audit finding.
- **Generated numbers** never appear in source tables, so ordered-list markers
  need no special handling here.

## Diagnostics and API

Add fields with defaults at the end of the frozen `ParseDiagnostics`, so existing
construction and pickling keep working:

```python
table_completeness_failures: tuple[str, ...] = ()   # check 1, material tokens
table_completeness_minor: tuple[str, ...] = ()      # check 1, minor tokens only
table_order_differences: tuple[str, ...] = ()       # check 2
tables_checked: int = 0
numeric_recall: float | None = None                 # check 3
```

`warnings` gains one summary message per failing table for check 1 (material
tokens) once enforcement is on (decision D1). Until then these failures appear
only in the new fields and in `warn`-level log lines.

Callers currently cannot retrieve diagnostics from `convert_to_markdown()` or
`parse_filing()`, because both discard the value `enforce_quality()` returns.
Decision D2 picks how to expose them.

The checks run inside `Parser.get_pages()` right after the numeric trace, reusing
`block_nodes_map`. Visibility is computed once per document as a set of hidden
node ids, not by walking parents per cell. Target overhead: at most 10% of parse
time on the fixtures, measured in the implementation PR.

## Policy and rollout

1. **Phase A (this implementation).** Compute all three checks under every
   policy except `off`. Strict does not raise on them yet.
   - Expose the results according to D2.
   - Add a fixture test that pins the current failures as an explicit expected
     list. It fails when a new loss appears, and also when a listed loss
     disappears without the list being updated.
   - Run the checks on a wider corpus of at least 50 filings and record any false
    positives in this spec. The 7 fixtures and 20 RCQ META/RDDT filings above
    count toward that total.
2. **Phase B (after the table-merge and header-rules spec lands).**
   - Strict raises `ParseQualityError` on material check-1 failures.
   - The expected-failure list should then be empty, or contain only entries this
     spec explicitly accepts.
   - Ship as a minor RCQ version bump with a CHANGELOG entry, because some
     filings that pass strict today will start to fail.

`export_xlsx()` uses the same parser, so its diagnostics gain the same fields.
XLSX cell-value fidelity (scale, percent and sign) is out of scope here. The
XLSX value-rules spec should reuse the source-table token extraction defined
above.

## Testing

Unit tests on synthetic HTML, one behavior each:

- A value dropped from row 0 when a `$` column merges (the minimal audit repro)
  is reported.
- A table whose element is missing entirely is reported as producing no output.
- Swapped numeric columns pass check 1 and are reported by check 2.
- These pass with no findings:
  - split accounting negatives `(29` + `)`
  - a hidden cell or row
  - a nested table
  - a one-row table rendered as text
  - a header-only table
- A footnote marker glued to a word is reported as minor, not material.

Fixture tests:

- Each of the seven fixtures has a pinned expected-failure list. Today that is
  the 11 tables listed above.
- The two audit mutations (blank `TableParser.md`; reversed numeric cells)
  must produce check-1 and check-2 findings respectively on the AAPL fixture.
- Overhead is measured and reported in the PR. A test enforces it only if
  timing proves stable in CI.

## Acceptance criteria

- On the fixtures, check 1 reports exactly the pinned failures. Each pinned
  failure can be traced to a parser defect named in the audit.
- Both audit mutations are detected.
- No new strict failures in Phase A: the existing suite passes unchanged.
- Diagnostics remain picklable, and existing `ParseDiagnostics` construction
  still works.
- Parse-time overhead is 10% or less on the fixtures.
- README and `docs/usage/direct-conversion.md` describe what strict does and does
  not check, including the size thresholds and that `include_elements=False`
  skips the element-based checks (decision D5).

## Decisions for review

- **D1. Enforcement timing.**
  - Recommended: report-only now, enforce material check-1 failures in strict in
    Phase B.
  - Alternative: enforce now. That makes the AAPL 10-K, both NVDA exhibits and
    all 20 RCQ META/RDDT filings fail strict immediately, which breaks callers
    until the parser fixes land.
  - Check 2 stays report-only either way until a corpus run shows its
    header-row noise is understood.
- **D2. Diagnostics API.**
  - Recommended: add `convert_with_diagnostics(source, **kwargs) ->
    tuple[str | list[Page], ParseDiagnostics]` and leave the existing functions'
    return types unchanged.
  - Alternatives: a keyword-only `diagnostics=` out-parameter, or documenting
    `Parser.diagnostics` as the supported route.
- **D3. Text completeness.** The lost AAPL header was caught only through its
  `(1)` marker. A per-table word-multiset check would catch header text
  directly, at the cost of more noise from header fusion.
  - Recommended: measure it in the Phase A corpus run before deciding.
- **D4. Minor tokens.**
  - Recommended: single-digit integers never fail strict; they are reported.
  - Alternative: zero tolerance for every token.
  - Related: on RCQ data most material tokens are day numbers from lost period
    headers (`31` in "March 31,"). Losing a period label is serious for anyone
    comparing periods, so this spec keeps them material. Splitting header-row
    tokens from body-row tokens in the report would let reviewers see which
    failures are value losses.
- **D5. `include_elements=False`.** Without elements there is no mapping.
  - Recommended: skip checks 1 and 2, record `tables_checked=0`, and document
    that strict is weaker in this mode.
  - Alternative: build elements internally for the check, which costs the
    speed this option exists for.

## Deferred

- Fixing the losses: column-merge row 0, complementary-column fusion, header
  fusion, and one-row-table element text. These belong to the table-merge and
  header-rules spec.
- XLSX cell-value checks: these belong to the XLSX value-rules spec.
  - Context from the RCQ run: before this branch, only about 89 of 918 RCQ
    tables exported as numbers, because "Three Months Ended March 31," was not
    recognised as a period header.
  - With the period-header fix on this branch, 384 export as numbers, and all
    10,544 exported values match a number in their source table.
  - 373 tables are still text-only, mostly "Unresolved value span", and that
    spec should start from them.
- Completeness of non-table prose beyond the document recall diagnostic.
- Positioned-div "tables" (`absolute_table_parser`): these have no `<table>`
  element, so they need their own source definition.
