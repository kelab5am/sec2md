# sec2md XLSX Stacked Period Blocks Design

Date: 2026-10-12 (revision 2)

Status: Draft for review. Not implemented. To be implemented after the value-accuracy spec
(`2026-10-12-sec2md-xlsx-value-accuracy-design.md`) merges.

**Scope:**
- Production code changes are limited to `src/sec2md/xlsx_tables.py` and `src/sec2md/xlsx_writer.py`. Tests and the
  audit harness change too.
- These must not change:
  - the Markdown renderer;
  - strict's numeric trace;
  - the table completeness check;
  - `table_parser.py`;
  - `_header_count`, `_PERIOD` and `_UNIT_DECLARATION`.

**Evidence:** [`../audits/2026-10-12-xlsx-stacked-blocks/fact-pack.md`](../audits/2026-10-12-xlsx-stacked-blocks/fact-pack.md),
measured on `main` at `172f428`. That commit's `src` is identical to merged PR #11. The corpus is the 60 filings of
the header-detection acceptance.

## Purpose

Some tables stack two or more period blocks, each under its own caption:
- 10-Q statements of stockholders' equity, with a three-month block over a six-month block;
- NVDA's segment note, with one block per period;
- KO's and UNH's investment tables, with one block per year-end.

The header-detection spec's period-row guard keeps these tables as they were before PR #11, mostly as source text. One
header would put the second block's numbers under the first block's period.

The user's goal: highlight the amounts and copy them, with every number a true number, in the right row, under the
right period, so formulas work.

This design gives each block its own header row on the same sheet. The period in each header comes from the block's
own caption. Any doubt keeps today's output. The user's principle applies: convert on proof only.

**The corpus.** There are 62 such tables, all source text or `needs_review` today: META 9, NVDA 17, RDDT 12 and
Others 24. Of these, 26 repeat their column headings in each block, and 36 have a caption only. A probe with one
column grouping for the whole table and a header per block exports 60 of them. In each, every inline XBRL fact
matches its own block's period. This revision's stricter rules export fewer: see Acceptance 2.

## Review history

**Round 1** (Codex on gpt-6.1-sol, revision 1 → 2). The findings were checked against the fact pack and the source
grids (JPM #241, NVDA 10-Q 2025-Q2 #33) before they were accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: the year-shaped amounts row `Revenue \| 2024 \| 2025` met the block-start rule, because `Revenue` equalled a heading text. | Confirmed | A block's caption row must reproduce block 1's caption row structure. Its label cell must be empty or the caption itself. |
| 2. High: one valid block let other unexplained period rows through. `FY2024` captions are not period text at all. | Confirmed | Every period row below block 1's region must be a proven block caption; otherwise the table is not stacked. `FY2024` is a gap that exists today on `main`, recorded in Known remaining gaps. |
| 3. High: containment inside a column group does not prove one heading meaning (`Amount` over columns 1-2 in block 1, `% \| Amount` in block 2). | Confirmed | A later block's repeated headings must occupy exactly the same cells (column and span) as block 1's. Only their wording may differ. |
| 4. High: caption scope allowed overlaps, uncovered columns and multi-period captions. | Confirmed | The caption is one label-column origin covering every value column, or own-row origins covering every value column exactly once. Each caption names exactly one period. |
| 5. High: a caption's unit (`(percentage of revenue)`) could leak into table-wide `units` and make another block's amounts percents. | Confirmed | Caption units never enter `units`. All blocks must carry the same caption unit, or none. |
| 6. High: block-1 caption undefined for real shapes. JPM #290 has a yearless stem in the header and a year below it. NVDA #33 has a blank row and `(In millions)` between the headings and the first caption. | Confirmed (both checked in the source) | A block's header region is defined, with permitted blank and unit-caption rows. A caption split over two rows (JPM #290) is not stacked. |
| 7. Medium: "different period" had no defined comparison. | Confirmed | Each caption parses to a period identity (kind, length, end date). An unparsable caption is not stacked. Equal identities written differently are the same period. |
| 8. Medium: headings before the caption (JPM #159, #241 repeat `Assets \| Liabilities` above the caption row) and section labels below it were not handled. | Confirmed (JPM #241 checked) | A region is the whole run of rows without data cells between blocks, compared row by row with block 1's. Label-only rows below the caption are body rows in every block. |
| 9. Medium: rewriting all 15 guard cases contradicts the rules. Some cases (`, as restated`, a separate `(1)` cell, `2025 and 2024`) are not provable. | Confirmed | Only cases meeting the new rules are rewritten. The rest stay as fallback tests. |
| 10. Medium: acceptance checked periods, not values. The probe kept later header rows as body evidence. | Confirmed | Acceptance checks a source-coordinate manifest of every amount: value, numeric type and workbook cell. |
| 11. Medium: the baseline and evidence revision were inconsistent, and the scope wording was too narrow. | Confirmed | The evidence revision is now correct. The baseline is `main` after value accuracy merges. The scope applies to production code. |

## The sheet

The layout stays as it is: title, units, copy area, original table. For a stacked table the copy area holds:
- block 1's header row, then block 1's body rows;
- one blank row;
- block 2's header row, then block 2's body rows;
- and so on.

`CopyTable` covers the whole copy area, as today. No other named ranges are added.

## Definitions

- **Terms from the header-detection spec (revision 6):** extended header, data row, data cell, period row, period
  text, footnote marker and unit caption, as defined there.
- **Body evidence row:** a row holding at least one digit data cell (a data row).
- **Header region of block 1:** the source rows from row 0 up to block 1's first data row. These are header rows; they
  hold no data cells.
- **Header region of block k (k ≥ 2):** the maximal run of rows without data cells that follows block k−1's last data
  row and ends before block k's first data row.
- **Region rows.** Inside a region, each row is classified as one of:
  - **blank:** no origin with text;
  - **unit row:** its only text origin, in the label column or spanning the value columns, fully matches
    `_UNIT_DECLARATION`;
  - **label-only row:** its only text origin is in the label column and is not period text. A label-only row below
    the caption row is a **body row**: a section label such as UNH's `Debt securities — available-for-sale:` or JPM's
    `VIE program type`. It belongs to the block's rows, not its header.
  - **caption row:** a row holding period text (see Caption);
  - **heading row:** any other row without data cells.
- **Caption.** A region's caption row holds its period text in exactly one of two forms:
  1. **Label column.** One period-text origin in the label column. It covers every value column. The row's other
     origins are heading cells (JPM) or empty.
  2. **Own row.** One or more period-text origins outside the label column. Together they cover every value column
     exactly once, with no gaps and no overlap. The label cell is empty. Example: META's two side-by-side captions.

  In addition:
  - Each caption origin, without footnote markers and without a trailing parenthesised unit caption, must parse to
    exactly one period identity. A caption naming two periods (`2025 and 2024`) does not parse.
  - A region has exactly one caption row.
- **Period identity:** `(kind, length, end)`, where the parts are:
  - **kind:** instant (`December 31, 2024`, `As of December 31, 2024`, `12/31/2024`), duration (`Three months ended
    March 31, 2025`, `Quarter ended …`, `Year ended …`, `Fiscal year 2024`) or year (`2024`);
  - **length:** in months, for durations; `Quarter` = 3, `Year` and `Fiscal year` = 12;
  - **end:** the end date, or the year alone for kind year.

  Different wordings of one identity are the same period. A caption that does not parse to an identity is not a
  caption.
- **Caption unit:** a parenthesised unit caption trailing a caption, such as `(in millions)`.
- **Stacked table:** a table where every condition below holds. Any failure means the table is not stacked and keeps
  today's output through the guard.
  1. **Block 1's region** holds a caption row, which is block 1's caption. Its rows above the caption row and its
     caption row's heading cells are block 1's heading structure.
  2. **There is at least one later block.** Every period row below block 1's region is the caption row of a later
     block's region.
  3. **Each later region** matches block 1's region in one of two templates:
     - **Full repeat:** the same non-blank rows, in the same order and with the same row kinds, apart from unit rows
       and label-only rows. Each corresponding pair of rows has origins at the same columns with the same column
       spans. Heading and caption texts may differ; positions may not. The caption keeps the same form (label column
       or own row) and the same spans.
     - **Caption only:** the region's only non-blank row is a caption row in the same form and spans as block 1's
       caption.
  4. **Each block's caption identity** differs from the caption identity of the block above, compared column by
     column for own-row captions.
  5. **Every block's caption carries the same caption unit,** or none does.
  6. **One column grouping** (S2) covers the whole table, with no unresolved value span.

## Rules

### S1. Block headers

For block k and each value column, the header label joins these parts with ` — `:
1. **The block's caption covering the column,** without footnote markers or caption unit.
2. **The column's heading labels.** In a full-repeat region they come from block k's own heading rows. In a
   caption-only region they come from block 1's heading structure. In each case they are flattened exactly as
   `prepare_table` flattens a header today: unit lines are excluded, and labels are read from the same source column
   as block 1.

Two further rules:
- **Column 0** gets block 1's label-column header cells above or in the caption row, without the caption, for every
  block.
- **The caption unit** is dropped from the header. It does not enter `units`.

### S2. One column grouping

- `_column_groups` runs once, on the whole grid. Its leaf headings come from block 1's heading structure.
- Later blocks' header regions are excluded from:
  - body evidence;
  - the structural actions;
  - `financial`;
  - unit capture.

  Label-only body rows stay body rows.
- The unresolved-span check runs over every body row of every block.
- Because later regions match block 1's cells exactly (template 3), each later heading sits over the same groups as
  block 1's.

### S3. Cell roles

- Each body cell takes its role from its own block's header label for its column. This includes the value-accuracy
  rules and every header test in `_numeric_role`.
- `percent_headers` and the header-level unit tests are computed per block.
- Table-wide percent declarations (value-accuracy P1.5) come only from the table's context and its block-1 unit
  rows, never from captions.

### S4. PreparedTable

`PreparedTable` gains two fields:
- `block_headers: tuple[tuple[str, ...], ...]`: one header tuple per block;
- `row_blocks: tuple[int, ...]`: the block index of each body row, aligned with `rows` and `cell_sources`.

`headers` remains `block_headers[0]`. A table that is not stacked has one block, with `row_blocks` all zero.

Later blocks' header regions leave `rows`. Their source rows remain in `original_rows` and in the original table.

### S5. Writer

- `render_workbook` writes each block's header row, with `Column N` blanked as today, and then the block's rows.
- Blocks are separated by one blank row.
- `CopyTable` and `copy_range` span the whole copy area.
- Other tables are unchanged.

### S6. The guard

The period-row guard stays. It decides every table that is not a stacked table.

## Unchanged behaviour

- Tables that are not stacked, including:
  - same-period section splits (JPM #137–#139, UNH #38, TSM #165);
  - exhibit indexes;
  - JPM #194 (different spans);
  - JPM #290 (split caption);
  - TSM #156 (block 1's caption in the previous table).
- `_header_count`, `_PERIOD`, `_UNIT_DECLARATION` and `table_completeness.py`.
- Markdown, strict and `table_parser.py`.
- The `OriginalTable` range and the original grid.

## Testing

Write the tests first, in `tests/test_xlsx_stacked_blocks.py`, with SEC-style spans. Each stacked case asserts:
- every block header;
- `row_blocks`;
- every body value, numeric with its value;
- `cell_sources`;
- the rendered workbook cells (the header rows, the blank row, and numbers read back as numbers).

**Stacked:**
1. **RDDT shape:** an own-row caption and three repeated heading rows. The 2025 net income sits under a 2025 header.
2. **META shape:** two side-by-side captions per block, and one heading that differs in wording at the same position.
3. **JPM #241 shape:** a heading row before a label-column caption row with headings beside it, and `(in millions)`.
   The period reaches every value header. The unit is dropped and kept out of `units`. `VIE program type` is a body
   row.
4. **NVDA segment shape:** headings at the top, a blank row, `(In millions)`, a label-column caption, and four
   caption-only blocks.
5. **KO shape:** instant captions per year-end. UNH shape: a section label below each caption, kept as a body row.

**Not stacked** (today's output):

6. **Year-shaped amounts row** after data: `Revenue | 2024 | 2025` (Codex finding 1).
7. **Unexplained extra period row:** two valid blocks, then `Year ended December 31, 2025 | Updated presentation`.
8. **Heading cells moved:** block 2's headings at different spans (`% | Amount` against `Amount` over two columns),
   and the JPM #194 shape.
9. **Caption scope:** overlapping captions, a column not covered, and a label-column caption beside own-row
   captions.
10. **Captions naming two periods, or unparsable:** `2025 and 2024`; `, as restated`; `FY2024`.
11. **Same identity:** `December 31, 2024` then `As of December 31, 2024` (JPM #137 shape).
12. **Caption units differ:** `(in millions)`, then `(percentage of revenue)`.
13. **Split caption** (JPM #290 shape).
14. **Block 1 without a caption** (TSM #156 shape).
15. **Exhibit-index rows** with filing dates.
16. **An unresolved span** in block 2.

**Roles:**

17. **A percent header in block 2 only** (value-accuracy P1.3) applies only to block 2's cells. A caption unit never
    makes a percent.

**Existing tests:**

18. **The 15 cases of `test_guard_stacked_period_blocks`.** Cases meeting these rules are rewritten to assert
    per-block headers and keep their assertion that no header names another block's period over an amount. Cases
    these rules reject (unparenthesised `, as restated`, a separate `(1)` or `*` cell, multi-period captions) stay as
    fallback tests, unchanged. The plan lists each case and its outcome.
19. **Other tests assuming one header row** (the accuracy tests' `top + 2 + row`, the writer tests) are listed in the
    plan, with how each changes.

## Acceptance

All runs use the same 60 filings, one export at a time, at most 3 workers and low priority. The baseline is `main`
after the value-accuracy spec merges, re-exported once with the extended harness.

The harness is extended first:
- `export_tables.py` records `block_headers` and `row_blocks`;
- `all_facts.py` checks each fact against its own row's block header;
- `compare.py` pairs cells by source coordinate.

1. **Tests:** all pass.
2. **Manifest.** Before implementation, from the fact pack's inventory, build a manifest. For each of the 62 tables
   it records:
   - whether these rules make it stacked, with the reason when they do not;
   - for each stacked table, every body digit cell by source coordinate, with its block and expected value.

   The manifest is committed with the audit. In the new output, every manifest cell of a stacked table must be:
   - a number equal to its expected value;
   - in the expected block;
   - in the workbook cell the writer reports.

   Tables the rules reject must equal the baseline.
3. **XBRL periods.**
   - Every inline XBRL fact in a stacked table's body matches its own block's header period: 0 mismatches. Facts
     under year-only captions are checked by year.
   - Every `not placed`, `no header date` and `unparsed length` verdict in a stacked table is listed and explained.
4. **Vault primary statements:**
   - all 126 are unchanged;
   - every fact still verifies (META 3,322, NVDA 2,662, RDDT 2,056).
5. **Every other changed table** compared with the baseline is listed and classified. A number under the wrong period
   blocks the merge.
6. **Spot checks against the filings:**
   - RDDT 10-Q 2025-Q1 #8: `Net income (loss) 26,158` under `Three months ended March 31, 2025`;
   - META 10-Q 2024-Q2 #9, block 2;
   - NVDA 10-Q 2025-Q2 #33, all four blocks;
   - KO #34;
   - JPM #241.

## Known remaining gaps

- **Tables that stay as text.** JPM #158 and BAC #113 fail column alignment even without the guard. JPM #194, JPM
  #290 and TSM #156 are not provable under these rules. All keep today's output.
- **Unrecognised caption forms (a gap that exists on `main` today).** A stacked table whose captions period text does
  not recognise (`FY2024`, `Q1 2025`) has no period rows. So neither the guard nor this spec sees it. Today such a
  table can export with block 1's header over every block (header-detection revision 6, Known remaining gaps). No case
  is known in the 60 filings. Closing it needs either a wider period vocabulary or the runtime XBRL guard.
- **Year-only captions** (`2024`) give headers with the year only, as the filing does.
