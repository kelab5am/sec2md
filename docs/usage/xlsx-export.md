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
`completeness`. That last field holds the table's completeness findings: numbers
its Markdown lost and rows that changed order. Completeness findings do not
change `status` or `issues` yet. `quality_policy="off"` skips the checks and
leaves `completeness` empty.
Overall status is `complete`, `needs_review`, or `no_tables`; table status is
`exported`, `needs_review`, or `source_text_only`.

- `warn` (default): retain recoverable issues in the API/CLI report.
- `strict`: reject parser-quality failures (`ParseQualityError`) or table/writer
  reliability failures (`XlsxQualityError`, with `.issues`) before publication.
- `off`: bypass parser-quality enforcement while retaining diagnostics and all
  spreadsheet conversion safeguards.

`XlsxDependencyError` explains how to install the missing optional dependency.
Unexpected parsing/programming errors and filesystem failures propagate, with
one exception: an error inside the table completeness checks is logged and does
not propagate, and `completeness` is then empty.
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
