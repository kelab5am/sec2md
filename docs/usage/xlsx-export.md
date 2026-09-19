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

The frozen `XlsxExportResult` contains `path`, `status`, `tables` and `diagnostics`.
Each `XlsxTableResult` contains `ordinal`, `sheet_name`, `status` and `issues`.
Overall status is `complete`, `needs_review`, or `no_tables`; table status is
`exported`, `needs_review`, or `source_text_only`.

- `warn` (default): preserve recoverable problems as visible review items.
- `strict`: reject parser-quality failures (`ParseQualityError`) or table/writer
  reliability failures (`XlsxQualityError`, with `.issues`) before publication.
- `off`: bypass parser-quality enforcement while retaining diagnostics and all
  spreadsheet conversion safeguards.

`XlsxDependencyError` explains how to install the missing optional dependency.
Unexpected parsing/programming errors and filesystem failures propagate.
Existing Markdown defaults are unchanged.

## Workbook contents and copying

Contents links to every table worksheet in source traversal order, including
nonfinancial disclosures, exhibits and trading plans. Separate continuation
fragments remain separate sheets. The inventory follows the existing parser's
recognized tabular content: a single-row layout table emitted as prose is outside
this inventory. It does not promise a sheet for every raw HTML `table` node.

Each worksheet shows source information, units, a labeled copy range, notes and
review items, and visible originals with source coordinates and spans. Copy the
stated range to include units and complete period headings. Copy grids contain no
merged cells or audit columns. All cells are static values: no formulas, filters,
calculations or cross-filing links are generated.

**No rows are frozen.** Table sheets freeze only the first label column (`B1`);
Contents has no frozen panes. Source identity and headers scroll away normally.
Parser pages and detected printed pages are shown separately. Printed pages are
omitted when source evidence is unavailable; generated element IDs are local
references, not fabricated SEC URL anchors.

## Numbers, originals and uncertainty

Displayed magnitude is retained: `215,938` reported in millions becomes numeric
`215938`, with the units preserved. Per-share exceptions keep their own displayed
scale. Percentages become fractions with percentage formatting (`12.3%` becomes
`0.123`). Dates, identifiers and numeric-looking labels stay text. Explicit zero
stays zero, blank stays blank, and a reported dash stays the exact text dash.

Conversion requires a complete supported numeric token and source-supported role.
Ambiguous mixed text, conflicting units, unsupported formats or numbers exceeding
Excel's reliable precision stay text with review items. Source strings beginning
with formula characters are stored as text. A table with an unreliable mapping
receives a source-text worksheet and explicit status instead of disappearing.

Original source cell strings, structural symbols, header levels, spans and
references remain visible. Whitespace normalization applies; this is not a pixel
reproduction of the filing. Long strings may be shown in labeled chunks and
require concatenation without separators. Excel limit violations receive an
explicit fallback or unavailable-in-full warning. Retained HTML remains the
ultimate source for visual layout.

Notes are retained from explicit targets and bounded nearby context. Nearby prose
is labeled as context, not asserted to resolve an accounting footnote. Missing or
ambiguous linked targets are flagged. Full financial-statement note sections are
not automatically expanded. External references remain links.

Contents records a SHA-256 and its scope: exact bytes for byte input, supplied
UTF-8 text for strings, or normalized HTML UTF-8 for URL input.

## Validation scope

Offline acceptance covers the retained NVIDIA annual and quarterly filings:
61/48 table worksheets plus Contents, six primary statements (162 source rows,
389 displayed numbers), 477 sampled numbers, 16 dash positions and two blanks,
plus inventories, percentage tables, exhibits, trading plans, source notes and
links. Expectations are independently reviewed source evidence stored with tests.

XLSX reopening, XML structure checks and rendered images are separate from native
Excel/LibreOffice scrolling and Google Sheets import/clipboard behavior. Rendering
does not establish those application behaviors. Google Sheets locale and paste
mode can affect interpretation; no online workbook is created by this API.
