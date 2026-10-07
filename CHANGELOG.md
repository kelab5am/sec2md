# Changelog

## 0.1.22+rcq.4 (unreleased, pending review)

- Merging columns no longer discards source values, and each value is put under the
  header its source column carries. Table layout changes wherever that needed it;
  code that reads Markdown tables by column position should be re-checked.
  - Merging columns no longer discards text. Amounts and labels in a table's first
    row that the old merge dropped are kept, such as `$ 9,943` in a row whose `$`
    and amount sat in separate columns, or a whole row of operating cash flows.
  - Header rows are the rows before the first data row, through header-like rows
    only. Past the first row, a row stays in the header when its label cell is empty
    or holds a period or unit caption (`Year Ended June 30,`, `(Dollars in millions)`,
    `(Unaudited)`) or a year, when it is a row of years such as
    `Function | 2022 | 2023 | 2024`, when it is a row of `th` cells, or when it has
    text in its label cell only, such as a second title line. The second row also
    stays when the old renderer fused it into the header. Counting the n columns that
    hold text, except columns holding only currency markers, `%`, `)`, `)%` or `(`
    (which the old renderer merged before it counted), the first row must be empty in
    at least max(2, n // 2) of those n columns, and the second row must have text in
    at least max(2, n // 2) of them. An example is an `Exhibit Index` title over
    `Exhibit Number | Description | Filed Herewith`. A row
    with any other label, such as `Common Stock | AAPL` under the column headings,
    ends the header, and it and the rows below stay in the body. So third and later header
    rows no longer appear in the body, and a data row is no longer pulled into the
    header. A table whose first row is data gets a header line of empty cells. A
    label-only row right before the data, such as `Accounts Receivable:`, stays in
    the body.
  - Multi-row headers are fused into one header line, each column's header rows
    joined top to bottom with ` — `, for example
    `Year Ended — January 28, 2001 — (As restated – see Note 2)`. A text equal to
    the one above it, ignoring case and spacing, is written once, unless the two link
    to different places. A
    header cell that spans several columns repeats in each of them, so a table-wide
    title or a unit line such as `(In millions)` can appear in every column header.
  - Rows and cells hidden with `display:none`, `visibility:hidden` or the `hidden`
    attribute are left out of the table before its columns are laid out, so a
    spanning header sits over the columns a reader sees and their text is not
    written.
  - Columns under different headers are no longer merged, and a spanning header no
    longer slides onto the neighbouring period's values.
  - A currency marker in its own column merges into the amount beside it, as `$`
    already did: `€ 1,234`, `RMB 941,168`, `NT$ (1,234)`. Only a closed list of
    symbols and ISO codes counts; other codes stay separate.
  - Zero-width characters, leading-dot decimals (`.75`), a column with a single
    split negative and a `)%` closing marker no longer block the merge that rebuilds
    a split value such as `(29` + `)`. A marker column that also holds a nil value
    (`—`) still stays separate.
  - A column with header text and an empty body, such as a signature date or an
    empty exhibit-index column, is kept.
  - A one-row PART table keeps every cell after the label:
    `PART III 2025 Annual Meeting Proxy Statement … within 120 days …`.
  - A `<table>` placed in a row of another table but outside every cell, directly in
    the `<tr>` or in a `<div>` there (malformed markup), is read once: its cells stay
    cells of that outer row, and its own rows are no longer also written as rows of
    the outer table. A one-row table holding such a `<table>` with no `<tr>` of its
    own, such as `<table><tr><td>A</td><td>1</td><table><td>987</td></table></tr></table>`,
    still renders `A 1` and drops that table's text, as before; neither strict nor
    `table_completeness_failures` reports it, and fixing that is a separate task.
    Otherwise each cell of such a table is written once, so strict finds no second
    copy to report, in a header row or a body row. Unless every row of the inner
    table is hidden, or it has no cells, the outer table places a cell that
    rowspans from earlier rows push to the right rather than dropping it, and it
    stays a table rather than becoming a bullet-list line, which would keep only a
    row's last cell.
  - Other nested tables are flattened into the outer table as before, so their output
    can change too, for example keeping an outer cell's value that was dropped. A
    table nested inside a cell is still read more than once: its text appears in that
    cell's text and again as cells and rows of the outer table, so strict can report
    its numbers as untraceable, as before. With `Parser(capture_tables=True)` the outer
    table is written as its source text instead, unless it sits inside a list item or
    bold or italic text, where it is written as Markdown in both modes. A table
    holding both kinds places every cell (see above), so it can show such extra
    copies where a narrower grid would drop them, and strict then fails on them:
    this fails closed, and no value is lost.
  - XLSX export keeps its own merge rules, so its prepared tables are unchanged:
    values, column groups, source coordinates, headers and issues. The page number on
    the contents sheet (`display_page`, the same guess as `Page.display_page`) is now
    guessed with table lines left out (see the display page item below), so the table
    changes in this release no longer move it, except through the first line of a
    table inside a list item or bold or italic text, which is still read. On the
    review corpus and the recent filings corpus they move it on no page.
- Strict's numeric trace accounts for each table's header line on its own. A number
  repeated in the header line because its header cell spans several columns no
  longer fails strict, while a header number with no header cell to supply it still
  does. Header-cell numbers no longer vouch for the same number in the table body or
  nearby text. When a table's header line cannot be matched to its table, the miss
  is recorded in `Parser.header_accounting_misses`, and that table's header line
  gets no accounting of its own: its numbers are traced as in the ordinary trace,
  which gives no credit for repeated header numbers, and strict still raises on any
  number it cannot trace (see the next item).
- The header-line accounting also covers a table rendered inside a list item or
  inside bold or italic text (`<li>`, `<b>`, `<strong>`, `<i>`, `<em>`, an inline
  element such as a `<span>` styled bold or italic, or a `<div>` inside one of
  these), with or without `Parser(capture_tables=True)`. Such a table has no
  Markdown segment of its own: its header line is found inside the wrapper's text,
  where a list marker, emphasis marks or words around the table may share its
  first and last lines. So `Year Ended December 31,` spanning `2025 | 2024`, which
  writes `31` twice from one source occurrence, passes strict there too. The
  header line is matched only when no link reduction in the wrapper's text crosses
  the table's boundary, the wrapper's final text still holds the table's own copy
  intact, and that copy occurs once in the element. Otherwise the miss is recorded
  in `Parser.header_accounting_misses` as `<element id>:missing` or
  `<element id>:ambiguous`, the table's header line gets no accounting, as in the
  ordinary trace, and a number it repeats can fail strict. These misses remain:
  - a link reduction crossing the table's boundary: Markdown link syntax in the
    wrapper's text that starts before the table and ends inside it, or starts
    inside it and ends after it, such as a list item reading `See [note` before a
    table with a link;
  - a padded link label in the table, such as `<a href="#n"> 2025 </a>`: the
    element keeps ` 2025 `, while the table's own segment has `2025`;
  - identical tables in one element, such as two in one list or one bold run, or a
    wrapped table beside an identical table (`ambiguous`, or `missing` when a link
    reduction also damages one copy);
  - a damaged copy: text merged into the wrapper's Markdown after the table was
    rendered changes or replaces the table's copy, as when a later bold run
    completes a link that the table's text opened, or when a later inline-block
    table with a link merges into it.
- Strict no longer fails a number in parentheses whose parentheses and digits are
  separate bold or italic runs, as in cover-page telephone numbers whose area code
  is tagged apart from its parentheses. The source reads `( 650 )`, an accounting
  negative, but the output's `**(** **650** **)**` read as 650, so 9 of the 70
  annual reports in the recent filings corpus (MSFT, NTRA and TSLA 10-Ks) failed
  default strict. Only the trace's reading of the output changes: one number
  between `(` and `)` whose gaps hold only whitespace and emphasis marks reads as
  `(650)` does. The Markdown and the source side are unchanged, and all other text
  reads as before. The rule is narrow:
  - a number split across runs, such as `**(** **1** **.25** **)**` or
    `**(** **1** **,234** **)**`, a `$` or `%` between a parenthesis and the number,
    such as `**( $** **1,234** **)**`, and parentheses glued to a word, such as
    `**USD(** **650** **)**`, still fail strict, as before;
  - a literal asterisk beside whitespace in such a gap, such as `(125 *)` or
    `( 5* )`, now reads as a negative number the source does not hold, so strict
    fails where it passed before. A star with no whitespace, as in the footnote
    `(125*)`, reads as before.
- The display page guess (`Page.display_page`, and the page number on the XLSX
  contents sheet) leaves Markdown table lines out: lines that start with `|`, and
  divider lines such as `| --- | --- |` or `:--- | ---:`. A table cell is no longer
  read as the page number (`| 304 | 1,234 |` gave 304, `| Total | 509,711 |` gave
  711), and table lines no longer take the places of the page's first and last
  three lines, which are the lines the guess reads, so a number such as `74` on the
  line after a table is read. Page numbers found in absolutely positioned page
  footers still take precedence, and a footer line that holds pipes but does not
  start with one, such as `Apple Inc. | Form 10-K | 23`, is still read. A table
  inside a list item or bold or italic text shares its first line with the list
  marker or emphasis marks (`- | Item | 304 |`, `**| Item | 304 |`), so that line
  is still read and a number in it can still be taken as the page number.
  Compared with the previous version, `display_page` changes on 216 pages in 17
  documents of the recent filings corpus and on 57 pages in 5 documents of the
  review corpus, the same with and without `Parser(capture_tables=True)`. Of the
  changed pages whose printed page number could be read, 110 and 28 now show it in
  place of a wrong number, and 8 and 4 lose a wrong number taken from a table cell
  (their printed number is a single digit, which the guess does not take); none
  showed it before. The other 98 and 25, whose printed labels could not be read
  automatically (such as `F-47`), lose their number.
- Known limitation, as in the previous release: when rowspans from the rows above
  push a row's cells right, cells past the table's widest row are dropped from the
  Markdown table: `<td rowspan="2">A</td><td>1,111</td>` over
  `<td>B</td><td>2,222</td>` renders `|  | B |` and loses `2,222`.
  `table_completeness_failures` reports a dropped number (`missing 2222 x1 [body]`);
  strict does not, and a dropped text cell is not reported. With
  `Parser(capture_tables=True)` such a table is written as its source text, which
  keeps the cells, unless it sits inside a list item or bold or italic text. A table
  holding a `<table>` outside every cell places these cells (see above). Fixing this
  is a separate task.
- Known limitation: a zero-width character (U+200B, U+200C, U+200D, U+2060 or
  U+FEFF) inside a table number is now removed from the rendered cell, so `1,2`, a
  U+200B and `34` render as `1,234`. Strict still splits the source number at the
  zero-width character, so strict reports that number as untraceable. For the same
  reason the report-only table completeness check can report the split parts as
  missing values, here `missing 12 x1 [body], 34 x1 [body]`. Fixing strict's source
  pool is a separate task, expected to cover these false completeness findings too.
- Known limitation: currency codes that change from row to row in a column beside
  the row labels, such as `EUR` and `JPY` under a `Forward contracts` section
  label, look the same as a column of currency markers. They are joined to the
  first period's amounts, so a row renders `EUR 1,234 | 987` where the old renderer
  wrote `EUR | 1,234 | 987`. No value is lost, but the report-only completeness
  check reports the joined amounts as missing, as for any amount joined to a
  currency code (see below): rows `EUR 1,234` and `JPY 2,345` give
  `missing 1234 x1 [body], 2345 x1 [body]`. Codes in the row-label column itself
  keep their own column. A rule for this case is a separate task.
- Known limitation: a one-row PART table now keeps its other cells, so it no longer
  renders as a bare `PART II` line. A running page header such as
  `Part II | Annual Report 2024` over a bare `Item 7` line is therefore no longer
  removed from the top of each page, and the section extractor reads it as a new
  part. A continuation page of Item 7 becomes a `PART II` section without an item,
  and on a page where the next item's heading follows, the Item 7 text before that
  heading falls out of every section. The old renderer kept Item 7 running across
  those pages. Likewise, a PART line of more than 80 characters at the end of a
  page is kept as a section without an item, so `get_section("PART III")` returns it
  instead of `ITEM 10`. The review corpus has no such running header, and its one
  PART table (CAT) gives the same sections as before.
- A report-only header-alignment check: each table value is compared with the header
  path its source column carries. Two `ParseDiagnostics` fields hold the results:
  - `table_header_alignment`: one finding per misaligned value, at most 10 listed per
    table, then the total, for example
    `table 24 (snapshot 19, page 41): "Revenue" 941168 under "2025 — RMB"; expected "2024"`.
  - `table_header_alignment_coverage`: (key, count) pairs that always list the same
    21 keys in a fixed order, from `tables_total` to `values_misaligned`, so that a
    clean result can be told apart from one where nothing was checked. An empty
    tuple means the check did not run (`quality_policy="off"`,
    `Parser(table_checks=False)`, or a failure in `check_tables()`).

  The check is not logged, never makes strict raise, and is not part of the XLSX
  export's per-table `completeness`.
- The report-only table completeness findings change with the rendering, and so
  does each `XlsxTableResult.completeness`, which lists them per table:
  - Values the old merge dropped are kept, so they are no longer reported missing.
    On the review corpus, rendered tables with value failures fall from 305 to 13
    (page header and footer tables, which the parser removes, are reported as
    before), and the 10 pinned fixture failures are gone. A headerless table's
    first data row is no longer written as the header line, so check 2's false
    finding on it (CAT 143) is gone too.
  - Check 1 reads an output cell that holds letters as text, so an amount joined
    to an ISO code or a lettered dollar prefix (`RMB 941,168`, `US$ 1,250.0`) is
    reported missing although it is in the output (TSM 344 on the review corpus).
    Amounts joined to `$`, `€`, `£` or `¥` are read correctly.
  - Identifier references that now sit in the header line, such as `2` in
    `(As restated – see Note 2)` or `3` in `(Note 3)`, are reported missing in
    `table_completeness_reported` (15 tables on the review corpus).
  - Check 2 reads a years row with a unit caption, such as
    `(Dollars in millions) | 2024 | 2023`, as a data row. That row is now in the
    header line, so check 2 pairs it with a later block's years row and reports
    the rows below as out of order (4 BAC tables, whose rendering is correct).

  These check-side false findings are left to a later task.
- API additions:
  - `Parser.element_header_records(element_id)` returns the header records bound
    to an element's tables, as `quality.ElementHeaderRecord` values (`segment`,
    `header_line`, `header_source`, `header_capacity`, `header_cells`, `wrapped`).
    For a list or an inline wrapper mapped to the element, it also returns the
    records bound for the tables rendered inside it, which have `wrapped=True`.
    `TableParser.header_record` holds the last render's record as a
    `table_parser.TableHeaderRecord`, with the same fields apart from `segment`
    and `wrapped`. `header_cells` lists each header-zone cell with text as (text,
    number of output columns it heads), for consumers with their own tokenizer.
  - `quality.trace_numeric_failures()` takes `header_records=`; without it the
    trace is unchanged.
  - `table_completeness.check_tables()` takes keyword-only `cell_texts=` and
    `base_url=`, and `TableCompletenessReport` gains `alignment` and
    `alignment_coverage`, which fill the two `ParseDiagnostics` fields above.

## 0.1.22+rcq.3 (unreleased, pending review)

- Table completeness checks, report-only: each visible table's Markdown is
  compared with its source table.
  - `ParseDiagnostics` gains `table_completeness_failures`,
    `table_completeness_reported`, `table_structure_differences`,
    `tables_checked` and `numeric_recall`.
  - Under `strict` and `warn`, each document with missing table values logs one
    summary warning and each value failure at INFO level; lost markers,
    references and row-order findings are not logged. Nothing raises yet.
    `quality_policy="off"` and `Parser(table_checks=False)` skip the checks.
  - If the missing-value and row-order checks (`check_tables()`) fail, the
    error is logged and the conversion continues without a table report, as if
    the checks were off. An error in `numeric_recall` still propagates.
  - `convert_with_diagnostics()` returns the output with its diagnostics.
  - `export_xlsx()` results gain `parse_diagnostics` and a per-table
    `completeness`.
- Quality checks normalize euro and pound amounts like dollar amounts. Because
  table merging uses the same normalizer, a split euro or pound negative such
  as `(€567` + `)` now merges into one cell, as dollar amounts already did.
  Strict's numeric trace changes the same way: a euro or pound amount whose
  currency sign sits in its own cell (`€ | 1,234`) no longer fails strict as
  untraceable, and the rare split layouts that already fail for dollars now
  fail for euros and pounds too.
- Added XLSX table export: `export_xlsx()` and the `sec2md[xlsx]` extra
  (pull requests #1 and #2).
- `chunk_section()` no longer returns neighbouring sections' text, element IDs
  and tags when sections share a page. An element that straddles a section
  boundary contributes only its own part to each section.
- Chunk overlap stays contiguous; short trailing blocks are no longer skipped.
- Split tables repeat their caption, units and header rows in every part, and
  table minification no longer adds a separator column or overwrites line 2.
- `Chunk.tags` is in first-seen order instead of depending on the hash seed.
- `get_section()` accepts `Item8K` members.
- PART headings joined by a dash or colon (`PART I—FINANCIAL INFORMATION`) are
  detected. Every META 10-Q previously returned no sections.
- XLSX export recognises period headers such as "Three Months Ended March 31,"
  above a year row. Income, comprehensive-income, equity and cash-flow
  statements in META and RDDT filings previously exported as text only.
- Added `Item10K.FOREIGN_JURISDICTION_INSPECTIONS` for Item 9C;
  `Item10K.CYBERSECURITY_DISCLOSURES` remains as a deprecated alias of it.
- Strict quality no longer rejects documents with ordered lists.
  `ParseQualityError` survives pickling, and an invalid `quality_policy` is
  rejected before any fetch.
- `export_xlsx()` checks that the destination folder is writable before parsing
  and fails within a few attempts instead of retrying for days on Windows. A
  failed staging-file cleanup no longer fails a completed publish.
- Tests always import this checkout's `src`, and fixture checks no longer depend
  on the working directory. CI also runs Python 3.11.
- Docs install this fork rather than the upstream PyPI package, and read local
  files as bytes.

## 0.1.22+rcq.2 (2026-08-29)

- Added keyword-only `base_url` link-resolution context for retained HTML text
  and bytes without network acquisition.
- Added compatibility, no-fetch, validation, image-isolation, and quality-policy tests.
- Updated API documentation and package version declarations.

## 0.1.22+rcq.1 (2026-08-29)

- Deterministic decoding.
- Strict quality checks.
- Table and link fixes.
- Provenance checks.
- Offline fixtures.
- Continuous integration.
