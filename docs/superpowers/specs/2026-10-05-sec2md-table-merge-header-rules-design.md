# sec2md Table Merge and Header Rules Design

Date: 2026-10-05 (revision 1)

Status: Proposed, for Astra's review

Evidence: `../audits/2026-10-04-table-merge-header-evidence/REPORT.md`

## Purpose

Make the Markdown table renderer keep every source value and put each value
under the header its source column carries. Today `TableParser` silently drops
row-0 text when it merges columns and places spanning headers over the wrong
column. The table completeness checks (spec 2026-10-02, Phase A) report the
first problem and cannot see the second.

This spec is the prerequisite that the completeness spec's Phase B and Astra's
Round 6 ruling name: "the table-merge and header-rules work". It changes
Markdown rendering on purpose, and adds a report-only header-alignment check.
It does not enable strict enforcement of any table check.

## Decisions taken in design (user, 2026-10-04)

| Question | Decision |
|---|---|
| Scope | The Markdown renderer only: `TableParser` and the one-row path in `Parser`. The XLSX grid keeps its own logic. |
| Layout stability | Readers are LLMs and RAG chunking; nothing parses tables by column position. Layout may change wherever it keeps every value and puts it under the right header. CHANGELOG entry and minor version bump. |
| Currency cells | Merged into the amount, as `$` is today: `€ 1,234`, `RMB 941,168`. |
| Multi-row headers | Fused per output column into one header line, top to bottom, joined with ` — `. |
| Header-alignment check | Built in this work, report-only. |
| Approach | Repair the existing pipeline using span identity, rather than a new renderer. The current merge is right about body values in 6,616 measured cases and wrong in one. |

## Background

The evidence report replays `TableParser` stage by stage over the Phase A corpus
(109 documents; 3,707 tables rendered by `TableParser`, 1,042 one-row tables)
and reproduces its Markdown exactly for every table. Its findings:

| Class | Tables / documents | What goes wrong |
|---|---|---|
| 1. Legacy merge drops row-0 text | 469 / 47 | `_merge_grid` keeps only the left column's row 0 (`merged = [current_col[0]]`). This is the cause of every genuine check-1 value loss in `TableParser` output: 294 tables, including all 10 pinned fixture failures. |
| 2. Columns under different headers fused | 1 value fusion (TSM 248); 37 non-amount fusions | A note column fused with 2022's amounts; exhibit-index X marks fused into "Number". |
| 3. Spanning header off its values | 138 / 10 with an empty first slot; 107 / 8 shifted over another span's values | A spanning header's text lives only in its first grid column. When that column is empty in the body it merges left and carries the header with it (BABA 24, TSM 79/312, JPM 482, BAC, RDDT, MSFT). 43 more tables put a header over a separate `$` column. |
| 4. Non-`$` currency columns | 1 / 1 | No per-row `€`, `£`, `RMB`, `NT$` or `DKK` columns exist in the corpus. They appear only as header labels. |
| 5. Header rows | 29 / 19 data rows swallowed; 244 / 27 rows k ≥ 3 left in the body; 129 / 32 second header rows left in the body | `_process_headers` always uses row 0 and fuses row 1 when row 0 looks sparse. |
| 6. Header-only columns dropped | 37 / 30 | `_clean_empty_rows_and_cols` drops a column with header text and an empty body: signature dates, exhibit-index columns, `(a)`. |
| 7. One-row PART branch | 1 (CAT 7) | `_one_row_table_to_text` returns "PART III" and drops the other cell. |
| 8. Split negatives left split | 80 / 4 (50 misaligned) | `(29 \| )` stays in two columns when the marker column has one negative, uses `)%`, or the careful pass rejects the whole column. |
| Other | 48 / 1 (NTRA) | U+200B cells count as content and block every merge. Leading-dot decimals (`.75`) and a year in a `$` column also block the careful merge. |

## Definitions

- **Source cell:** one `td` or `th`, read by `_extract_cells` into a `Cell`.
- **Slot:** one position of the expanded grid. `GridCell.cell` identifies the
  source cell covering the slot; every slot a spanning cell covers points to the
  same `Cell` object. This identity is the span. No new data model is needed.
- **Visible cell text:** the extracted text with zero-width and format
  characters removed: U+200B, U+200C, U+200D, U+2060 and U+FEFF. Every rule
  below reads visible text, and the rendered Markdown carries it.
- **Data cell:** a cell whose whole visible text is a standalone number, or a
  nil dash, but not a bare year.
  - A standalone number may have a currency marker (see "Currency markers"),
    parentheses, a sign, digits with thousands separators or a leading-dot
    decimal (`.75`), and a trailing `%`. Examples: `9,943`, `(29)`, `36.5 %`,
    `$ 1,234`, `3.1`, `9`.
  - A nil dash is a cell that is only `—`, `–`, `-` or `−`.
  - A bare year is four digits from 1900 to 2099 with nothing else. It is never
    a data cell.
- **Data row:** a row of the cleaned grid with at least one data cell, in any
  column.
- **Header zone:** the rows of the cleaned grid before the first data row.
  - When no row is a data row, the header zone is row 0 alone.
  - When row 0 is a data row, the header zone is empty.
- **Header cell of a slot in a header row:** the slot's source cell, when that
  cell has visible text.
- **Group:** an output column under construction during the column merge: a
  run of adjacent grid columns.
- **Currency markers:** `$`, `€`, `£`, `¥`, the prefixed dollars `US$`,
  `NT$`, `HK$`, `A$`, `C$`, `S$`, and the ISO codes `USD`, `EUR`, `GBP`,
  `JPY`, `CNY`, `RMB`, `CHF`, `DKK`, `SEK`, `NOK`, `HKD`, `TWD`, `CAD`, `AUD`,
  `INR`, `KRW`, `SGD`. The list is closed. A cell is a currency marker cell only
  when its whole visible text is one of them.

## Rendering rules

### R1. Merges never discard text

When the legacy pass merges column B into a group, every row is combined, row 0
included.

- A slot whose source cell is the same as the group's slot in that row counts
  once.
- Otherwise the two texts are joined with a space, as body rows are today.

This rule alone restores the 294 tables' lost values: JPM 109's `$ 84,973`,
TSLA 38's `$ 487`, AAPL's `9,943`, and the pinned fixture losses.

### R2. The header guard

Column B may merge into the group on its left only when both hold:

- **Body:** the existing `_should_merge_cells` test passes for every row below
  the header zone. When the header zone is empty, it covers every row.
- **Header:** in every header-zone row, B's slot has no header cell, or its
  header cell is the same source cell as the group's header cell in that row.
  The group's header cell in a row is the header cell of the group's first slot
  that has one. When the group has none in a row and B has one, B does not
  merge.
- **Marker exception:** a group with no header cells whose body slots hold only
  currency markers or `(` may take column B whatever B's header cells are. The
  merged group then carries B's header. A marker attaches to the amount on its
  right, so a `$` outside the year span must not split from its amount.

Effects:

- **Kept:** the 6,616 measured merges that realign values offset under one
  header (for example a `$` row's amount one grid column right of the other
  rows' amounts). Trailing `)`, `%` and spacer columns without header text are
  still absorbed.
- **Blocked:** a column that starts a new period's span no longer merges into
  the previous period or the label column. That removes the class-3 shift.
- **Blocked:** columns under different header cells, such as TSM 248's "Notes"
  and "2022", or RDDT's "Filed Herewith" and "Number".

### R3. The careful marker merge, extended

`_merge_structural_columns` keeps its validation: a merge happens only when the
rebuilt token is a valid number. It changes in four ways.

1. **Visible text.** Zero-width characters are whitespace (NTRA).
2. **Body start.** `_body_start` returns the end of the header zone, so a row of
   bare years or period text is not body (MSFT 24, TSM 312).
3. **Leading-dot decimals.** The renderer's numeric tests accept `.75` and
   `(.62`. This is local to `TableParser`: `quality.normalize_numeric_token` does
   not change, because it also drives strict's numeric trace.
4. **Single and percent negatives.** A marker column with one non-empty marker
   may merge, and `)%` is a closing marker, when the rebuilt token validates
   (BABA 69, TSM 79).

### R4. Currency markers

Every marker in the list behaves as `$` does in the careful merge: a currency
marker column merges into the amount on its right, written `€ 1,234` or
`RMB 941,168`.

- Validation strips the marker before calling `normalize_numeric_token`, again
  locally.
- The legacy pass's `_should_merge_cells` treats every currency marker as it
  treats `$` today.
- A header-row currency label ("RMB" over an amount) is header text, assembled
  by R6. It is not a marker column.
- The corpus has no per-row non-`$` currency column, so these cases are tested
  synthetically.

### R5. The header zone

`_process_headers` uses the header zone (Definitions) instead of "row 0, plus
row 1 when row 0 is sparse".

- Every header-zone row contributes to the header line, so third and later
  header rows leave the body (244 tables).
- No data row is promoted into the header (29 tables), since the zone ends at
  the first data row.
- When the zone is empty, the header line is written with empty cells and every
  row is body. Example: a headerless table whose first row is
  `Noninterest revenue – reported | $ 84,973 | …`.
- When no row is a data row (text tables, signature blocks), row 0 alone is the
  header. Row 1 is not fused into it.

### R6. Header assembly

For each output column, the header line text is built from the header zone, top
to bottom:

1. In each header-zone row, take the header cell covering the column's slots.
   R2 guarantees at most one distinct header cell per row in a merged group. If
   the careful merge combined two, join their texts with a space.
2. Join the rows' texts with ` — `, skipping empty texts and a text equal to the
   one before it.

A header cell that spans several output columns appears in each of them:
`Year ended March 31, — 2024 — RMB`. A table-wide title therefore repeats in
every column header, for example BAC's "Table 10 | …Regulatory Capital under
Basel 3". This is the user's choice: every column keeps its full context.

### R7. Empty-column cleanup

`_clean_empty_rows_and_cols` removes a column only when it has neither header
text nor body text. Header-only columns stay, including signature dates,
exhibit-index columns with no entries and `(a)` heads (37 tables). Empty rows
are still removed.

### R8. One-row PART tables

The PART branch of `Parser._one_row_table_to_text` keeps every cell after
normalizing the label, as the ITEM branch keeps its title:

> `PART III 2025 Annual Meeting Proxy Statement (Proxy Statement) to be filed
> with the Securities and Exchange Commission (SEC) within 120 days after the
> end of the fiscal year.`

The line still starts with `PART III` followed by whitespace, so the section
extractor's `PART_PATTERN` matches it exactly as before. The ITEM branch and the
plain join are unchanged.

### What does not change

- `TableParser.md()`, `to_markdown()` and `to_matrix()` keep their signatures.
- List tables, unreliable-table fallback text (capture mode), nested tables and
  positioned-div tables render as today.
- Cell text extraction is unchanged apart from removing zero-width characters.

## Header-alignment check

A report-only check that each value sits under the header its source column
carries. It compares the source HTML with the Markdown text, like check 1, and
never reads the renderer's internals, so it also catches a later renderer
regression and can measure today's `main`.

### Definition

For each table unit with an output segment that has a Markdown separator:

1. **Source grid.** Place the unit's own visible rows with the snapshot
   builder's placement rules, as `table_completeness.header_row_count` does.
   Skip the unit when placement is unreliable (a bad span, an overlap, a nested
   table or an oversized grid).
2. **Header zone.** Compute it with the same data-cell test as the renderer,
   from one shared helper. Skip the unit when the zone is empty or no row is a
   data row.
3. **Value columns.** These are the grid columns that hold a data cell in some
   data row. A header cell is **discriminating** when the value columns it
   covers are a non-empty proper subset of all value columns. Captions that
   span every value column ("Year ended March 31,", a table title) are not
   discriminating and are never required.
4. **Pairing.** Use check 1's rule: a source data row pairs with an output body
   line only when its label key is unique among the unit's source rows and its
   output body lines.
5. **Each value.** For each data cell in a paired source row, other than its
   label:
   - **Expected headers:** the visible texts of the discriminating header cells
     whose span covers the value cell's columns.
   - **Output column:** the output cell of the paired line that holds the
     value's tokens (`numbers()` after `merge_split_negatives`). When no cell or
     more than one cell holds them, the value is not evaluated.
   - **Aligned** when every expected header text is a substring of that output
     column's header text. Both sides are compared with whitespace collapsed,
     case folded, and Markdown link destinations removed.

### Findings

```
table 24 (snapshot 19, page 41): "Revenue" 941168 under "2025 — RMB"; expected "2024"
```

- One finding per misaligned value, at most 10 listed per table, with the total.
- `ParseDiagnostics` gains a trailing defaulted field,
  `table_header_alignment: tuple[str, ...] = ()`.
- The check runs inside the guarded `check_tables()` call. Policy `off` skips
  it, like checks 1–3, and a failure in it is isolated with checks 1–2.
- It is not logged in this work, like check 2.
- It is not added to `XlsxTableResult.completeness`, because the workbook has
  its own grid.
- It never makes strict raise. Any enforcement needs a separate decision.

### Limits

The check skips rather than guesses, so it errs toward missed findings:

- rows with empty or duplicate labels;
- tables with no header zone;
- values that appear in more than one output cell;
- mid-table repeated header rows in stacked tables. Values below them are
  compared column by column against the top header zone.

A header row that the data-cell test misclassifies affects the renderer and the
check alike, because they share the test. The fixture and corpus measurements
below are the guard against that.

## Interaction with the completeness checks

- **Pinned failures.** All 10 pinned value failures in
  `tests/test_table_completeness_fixtures.py` are class 1, so `PINNED_FAILURES`
  is expected to become empty. Each removal is recorded with its cause.
  `TABLES_CHECKED` does not change, because units and their numbering do not
  change.
- **Check 2.** Check 2 skips header lines. R5 moves only header-zone rows into
  the header line. Headerless tables get an empty header line, so their first
  data row stays in the body. That removes Phase A false positive F7 (CAT 143).
- **Check 1's header role** keeps using `header_row_count`. This spec does not
  change check 1, check 2 or check 3.
- **Mutations.** The three Phase A mutations must still be detected.

## Testing

Tests are written before the code they cover.

- **One test per class**, each built from a minimal copy of a real table in the
  evidence report:
  - JPM 109 (row-0 amounts) and CRM 26 (row-0 caption);
  - TSM 248 (Notes and 2022) and RDDT 52 (X marks);
  - MSFT 24 (`$` column and year) and BABA 24 (empty-slot shift);
  - JPM 482 (footnote column inside a segment span);
  - AAPL 18 and META 4 (swallowed data rows);
  - nvda-2026-10k 17 (third header row);
  - GOOGL 89 (signature date) and AAPL 64 (exhibit-index columns);
  - CAT 7 (PART);
  - BABA 69 and MSFT 43 (split negatives).
- **Synthetic cases:** a per-row euro column under spanning 2025/2024 headers,
  with the alignment of its amounts asserted; a U+200B cell beside an amount;
  `.75` per-share values; a single-digit first data row; and a text table with
  no data row.
- **Parser-level cases** run in both rendering modes.
- **Alignment check:** a shifted header is reported; an aligned table is
  silent; each skip rule holds; a non-discriminating caption is never required.
- **Regression guards:** the existing suite passes, apart from deliberately
  updated pins and golden files. `TableParser` tests that pin today's merging
  are updated only where this spec changes the behaviour, each with a reason.

## Acceptance criteria

- **Fixtures:**
  - `PINNED_FAILURES` is empty, or holds only explained residuals;
  - check 2 reports nothing;
  - the three mutations are still detected;
  - rendering is identical with checks on and off.
- **Accuracy suite:** no fixture's words, numbers or financial-rows score drops.
  Markdown and page hashes change, as expected.
- **Phase A corpus**, 109 documents in both rendering modes:
  - check-1 value failures in `TableParser` output fall from 294 tables to 0,
    apart from classified residuals;
  - page-furniture tables (573) and the definition false positives F1–F8 are
    unaffected and reported separately;
  - no new check-1 or check-2 finding, unless classified;
  - header-alignment findings fall from the baseline measured on unchanged
    `main` to 0, apart from classified residuals;
  - all 109 documents agree across the two modes;
  - a stratified sample of about 30 changed tables is reviewed by eye, covering
    every class.
- **Overhead:** at most +10% in total over unchanged `main` on the 7 fixtures,
  for the renderer changes and the alignment check together.
- **Release:** a CHANGELOG entry lists each rendering change. The RCQ version
  gets a minor bump. README and `docs/usage/direct-conversion.md` describe the
  header line and the new diagnostics field, and the header-shift caveat is
  updated to say what the alignment check now covers.

## Decisions for review

- **T1. Repeating spanning headers.** Every output column carries every header
  cell that spans it, so a table-wide title repeats in each column. The
  alternative places a header cell that spans every column only once, in the
  first column.
- **T2. The data-cell test.** Any standalone number except a bare year counts,
  including single digits and exhibit numbers.
  - Risk: a header row that holds a standalone number, such as a standalone
    "(1)", ends the header zone early.
  - Risk: a first data row of bare years only (a label column of years with no
    other values) is read as a header.
  - The single shared helper keeps the renderer and the check consistent, and
    the corpus run measures the effect.
- **T3. Tables without a data row.** Row 0 alone is the header, with no fusion.
  The alternative is an empty header line.
- **T4. Headerless tables.** The header line is written with empty cells. The
  alternative keeps row 0 as the header, which puts data in the header line.
- **T5. The alignment check's scope.** It covers discriminating headers only,
  with the skip rules above, and substring matching.
- **T6. Currency markers.** The closed list above.
- **T7. Overhead.** +10% in total over unchanged `main` for this work. The
  completeness spec's own Phase B target is unaffected.

## Deferred

- **The XLSX grid** (`xlsx_tables.py`), including its own dropped sub-headers
  (audit #5).
- **Inline-run spacing in cell text** ("March 3 1", `1,2 34`). This is a
  text-extraction change with wide effects.
- **Nested tables.**
- **One-row tables that flatten a data row into one line** (23 tables). They
  lose column labels, not values.
- **Footnote-marker columns** such as JPM's "(b)(c)", which stay their own
  column under the right header rather than merging into the amount.
- **Positioned-div tables.**
- **Page-furniture tables.** These belong to the completeness spec's Phase B.
- **Enforcement of the header-alignment check.**
