# Export tables to XLSX

Install the optional spreadsheet dependency from this reviewed fork checkout:

```bash
python -m pip install ".[xlsx]"
```

For a distribution containing this feature, the extra is `sec2md[xlsx]`.
Markdown import and conversion do not require openpyxl.

```python
from pathlib import Path
from sec2md import export_xlsx

result = export_xlsx(
    Path("nvda-20260726.htm").read_bytes(),
    Path("NVDA_10-Q_2026-07-26_tables.xlsx"),
    base_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/nvda-20260726.htm",
)
print(result.path, result.status)
for table in result.tables:
    print(table.ordinal, table.sheet_name, table.status, table.issues)
```

The destination's parent directory must already exist. By default an existing
file raises `FileExistsError`. Set `overwrite=True` to explicitly replace it.
Publication validates a temporary sibling workbook first. No-overwrite publication
requires filesystem hard-link support; unsupported filesystems raise `OSError`.

## API and quality

```python
export_xlsx(source, destination, *, base_url=None, user_agent=None,
            quality_policy="warn", overwrite=False)
```

`source` accepts HTML text, bytes, or one URL. Read local files as bytes yourself.
Bytes/text are offline; `base_url` resolves links without fetching them. URL input
fetches only that document, using `user_agent` when supplied. Linked images,
exhibits and related filings are not fetched.

The frozen `XlsxExportResult` contains `path`, `status`, `tables`, `diagnostics`
and `parse_diagnostics`, the parser's full `ParseDiagnostics`. Each
`XlsxTableResult` contains `ordinal`, `sheet_name`, `status`, `issues` and
`completeness`. That last field holds the table's completeness findings:
numbers, footnote markers and references its Markdown lost, and rows that
changed order. Completeness findings do not change `status` or `issues` yet.
`quality_policy="off"` skips the checks and leaves `completeness` empty.
Overall status is `complete`, `needs_review`, or `no_tables`; table status is
`exported`, `needs_review`, or `source_text_only`.

- `warn` (default): retain recoverable issues in the API/CLI report.
- `strict`: reject parser-quality failures (`ParseQualityError`) or table/writer
  reliability failures (`XlsxQualityError`, with `.issues`) before publication.
- `off`: bypass parser-quality enforcement while retaining diagnostics and all
  spreadsheet conversion safeguards.

`XlsxDependencyError` explains how to install the missing optional dependency.
Unexpected parsing/programming errors and filesystem failures propagate, with
one exception: an error inside the missing-value and row-order checks
(`check_tables()`) is logged and does not propagate, and `completeness` is then
empty. An error in the `numeric_recall` computation still propagates.
Existing Markdown defaults are unchanged.

## Workbook contents and copying

Contents lists table titles and pages with links to the worksheets. Filing front
matter is excluded only when a contents table is positively identified from its
heading and linked index rows. Without that evidence, early tables are retained.
This filter applies only to Excel; Markdown output is unchanged.

Titles come from captions, nearby headings (including bold/italic SEC text blocks),
or a short subject extracted from introductory text. A descriptive source row label
is the fallback, followed by a numbered name only when no useful source label exists.
Full titles remain in Contents and at the top of each sheet; tab names respect
Excel's 31-character limit and receive suffixes when needed.

Each worksheet contains the title, reported units, headers and values, followed by
an original table reference. When numeric columns cannot be safely consolidated,
only the source grid is shown, preserving source spans and text. Notes, nearby
prose, review sections, cell-coordinate ledgers and extracted-text dumps are omitted.
They remain available in internal extraction records and API/CLI diagnostics.

Header rows are read from the table's own layout. Besides `<th>` rows and period
rows, the header can take in rows that read as headings, but only with span
evidence: the last header row must have a heading wider than an amount beneath
it, as `December 31, 2024` spans its `$` and amount cells. Each column header
joins its levels with ` — `, such as `December 31, — 2024` or
`Year Ended December 31, — 2024 vs 2023 % change`. Rows that might be data stay
in the body. A table that stacks period blocks, each under its own caption row,
gets no extended header when the exporter recognises the second block's
caption. Captions such as `Q1 2025` or `FY2024` are not recognised, so a block
under one of them can still sit under the first block's period. When a header
cannot be established, the table keeps its original grid instead.

**No rows or columns are frozen.** Prepared copy grids are unmerged; original
references preserve source merges. Local named ranges `CopyTable` and `OriginalTable`
identify the available areas without visible instructions. Cells contain static
values, with no generated formulas, filters, calculations or cross-filing links.

The inventory follows the parser's recognized tabular content; single-row layout
tables emitted as prose do not get worksheets. Separate continuation fragments
remain separate sheets. Page numbers use detected printed pages when available,
otherwise parser pages.

## Numbers, originals and uncertainty

Displayed magnitude is retained: `215,938` reported in millions becomes numeric
`215938`, with the units preserved. Per-share exceptions keep their own displayed
scale. Percentages become fractions with percentage formatting (`12.3%` becomes
`0.123`). Dates, identifiers and numeric-looking labels stay text. Explicit zero
stays zero, blank stays blank, and a reported dash stays the exact text dash.

A number becomes a fraction only on proof that it is a percent: its own `%`, an
inline XBRL percent fact in the cell, a percent heading such as `% Change`, a
percent row label, or a table-wide percent caption. A heading or caption over
two values in one row proves neither of them. A percent proof never overrides
contrary evidence: a heading or caption proves nothing in a column that holds a
`$` amount or an amount fact, and a caption proves nothing under an amount
heading such as `Total`. A `%` in the next column counts as the number's own
only when it spans one row, sits directly beside the number and its column holds
nothing else; negative percents such as `(29) %` become `-0.29`. A percent word
in an `except` caption proves nothing, as in
`(In millions, except per share and percentage data)`. Under an identifier-like
heading, a cell converts only with its own `$`, `%` or inline XBRL fact. Numbers
that need proof and lack it stay source text. When one of the cases below
applies, the export report gives the reason and the table becomes
`needs_review`; other text, such as a note reference under `Notes`, stays
unflagged as before.

- `Percent sign on other rows of this column; verify the scale.`
  A number without proof in a column where another row has its own `%`, a
  percent fact or a percent row label. This includes amounts:
  `Tier 1 capital 294,881` below `$ 275,513` is flagged although the number is
  right. It also applies to a number under a percent heading or caption that
  proves nothing in its column (over two values in one row, or withheld by
  contrary evidence), to a number without its own `%`, `$` or fact under a
  heading that names a percent without declaring one (`Percent Change 2024
  versus 2023`, identifier-like headings included), and to a number whose
  separate `%` could not be attached safely. That `%` can still reach the number
  as before, through column grouping under one heading over both or the merge of
  a column of `%` signs; the number then converts with it. A `%` spanning several
  rows never reaches any number: each number beside it is flagged. Zeros still
  convert.
- `Percentage points; verify the unit.`
  A change such as `26.6 pts`.
- `Identifier heading over quantities; verify the column.`
  A plain number under an identifier-like heading such as `Full Year 2024`,
  where another cell of the column proves a quantity.
- `Identifier heading over amount-formatted values; verify the column.`
  A comma-grouped or parenthesised number under such a heading when no cell
  proves a quantity. Footnote marks such as `(1)` are not amounts and stay
  unflagged.
- `Conflicting explicit units; verify the row, column and displayed value units.`
  A `$` together with a percent proof, such as a `$` amount under a percent
  heading or a `$` in the heading of a percent column (`% Change in NT$`). Also
  a pure inline XBRL fact whose scale is not -2 under any percent proof, a
  table-wide caption included; a fact in another unit, such as years, under any
  percent proof; and a percent proof on a row or column whose label names
  another unit (`Expected term (in years)`, `Days in inventory`, `(x)`,
  `bps change`, `Change (pp)`, `Duration`, a bare `Years` heading). A row label
  spanning two rows counts for both. Period headings, maturity buckets such as
  `1-3 years`, signed scenarios such as `+100 basis points` and labels such as
  `Years 1-5` name no unit.

Conversion requires a complete supported numeric token and source-supported role.
Ambiguous mixed text, conflicting units, unsupported formats or numbers exceeding
Excel's reliable precision stay text with issues in the export report. Source strings beginning
with formula characters are stored as text. A table with an unreliable mapping
uses its original grid when source geometry is valid. Unsupported source geometry
raises `ValueError` before publication, leaving any existing destination intact.

Original source cell strings, structural symbols, header levels, spans and cell
links remain in the original grid. Whitespace normalization applies; this is not
a pixel reproduction of the filing. Long strings stay in their cells; values over
Excel's 32,767-character limit or tables exceeding its dimensions cause an explicit
error before publication rather than truncation or diagnostic text chunks.

Contents retains hidden source-identity rows for folder-export duplicate detection:
SHA-256 of exact bytes for byte input, supplied UTF-8 text for strings, or normalized
HTML UTF-8 for URL input. These rows are not part of the visible Contents list.

## Validation scope

Offline acceptance covers the retained NVIDIA annual and quarterly filings:
58/45 post-contents table worksheets plus Contents, six primary statements (162 source rows,
389 displayed numbers), 477 sampled numbers, 16 dash positions and two blanks,
plus inventories, percentage tables, exhibits, trading plans, source notes and
links. Expectations are independently reviewed source evidence stored with tests.

XLSX reopening, XML structure checks and rendered images are separate from native
Excel/LibreOffice scrolling and Google Sheets import/clipboard behavior. Rendering
does not establish those application behaviors. Google Sheets locale and paste
mode can affect interpretation; no online workbook is created by this API.
