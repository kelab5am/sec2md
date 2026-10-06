# Direct Conversion

Convert different types of SEC documents to Markdown.

## Full Filings (10-K, 10-Q)

```python
import sec2md

# Convert entire 10-K filing
md = sec2md.convert_to_markdown(
    "https://www.sec.gov/Archives/edgar/data/.../10k.htm",
    user_agent="Your Name <you@example.com>"
)
```

### Quality policy and supported input

`convert_to_markdown()` and `parse_filing()` accept one supplied HTML document
as text or bytes, or a URL for one HTML document. `quality_policy` is
keyword-only and defaults to `"strict"`; use `"warn"` to return output while
recording diagnostics, or `"off"` for parser experimentation. Strict failures
raise `ParseQualityError`, whose `.diagnostics` attribute contains the
structured quality evidence.

Strict raises when a source with at least 1,000 visible characters produces
empty output, or when one with at least 10,000 keeps less than 10% of them. It
also raises on replacement or C1 control characters, on elements without a
source-node mapping, and on numbers in an element that cannot be traced to its
source.

It does not yet fail when a table loses a number. Table completeness findings are
reported in the diagnostics. Of these, only missing table values are logged: one
summary warning per document, then each value failure at INFO level. Lost
markers, references and row-order findings are not logged yet. If the
missing-value and row-order checks (`check_tables()`) fail, the error is logged
and the conversion continues without a table report, so the diagnostics look as
they do with the checks off; an error in the `numeric_recall` computation still
propagates.
`numeric_recall` can read low when an output line starts with a number shaped
like a list marker (`2. Summary …`).

```python
from sec2md import convert_with_diagnostics

markdown, diagnostics = convert_with_diagnostics(html_bytes)
for failure in diagnostics.table_completeness_failures:
    print(failure)  # table 49 (snapshot 41, page 46): missing 9943 x1 [body] (total 1)
print(diagnostics.tables_checked, diagnostics.numeric_recall)
```

### Table header lines

Each Markdown table has one header line. When the source table has several
header rows, each column's header rows are joined top to bottom with ` — `, a
text equal to the one above it is written once, and a header cell that spans
several columns repeats in each column it spans:

```markdown
|  | Year Ended June 30, — 2025 | Year Ended June 30, — 2024 |
| --- | --- | --- |
| Revenue | $ 1,234 | $ 1,100 |
| Operating income | 456 | 412 |
```

Header rows are the rows before the first data row: the first row with an amount
or a nil dash (`—`) in a value column, or with a number in the row-label column
when that column is an identifier column (one holding a number in at least two
rows, such as exhibit or item numbers). An amount may carry footnote markers
(`3,984 *`, `2.1(1)`) or be a range (`0.2 - 1.0`). Years count as amounts only
beside a row label that is not a period caption, a unit caption (`(In millions)`,
`(Dollars in millions)`, `(Unaudited)`) or a year, and never in a row of years
within one of each other, such as `Function | 2022 | 2023 | 2024`. A row of `th`
cells is never a data row. Past the first row, the header continues only
through rows like these: an empty label cell, a caption or a year in the label
cell, a row of years, a row of `th` cells, or a row with text in its label cell
only, such as a second title line. The second row also continues the header when
the previous renderer fused it into the header. Let n be the number of columns that
hold text, leaving out marker-only columns: columns whose every text is a currency
marker, `%`, `)`, `)%` or `(`, which the previous renderer merged before it counted.
The first row must be empty in at least max(2, n // 2) of those columns, and the
second row must have text in at least max(2, n // 2) of them. An example is an
`Exhibit Index` title over `Exhibit Number | Description | Filed Herewith`. A row
with any other
label, such as `Common Stock | AAPL` under the column headings, ends the header
and stays in the body. A table whose first row is data gets a header line of empty cells. A
label-only row just before the data, such as `Accounts Receivable:`, stays in the
body. Equal header texts, ignoring case and spacing, are written once unless they
link to different places.
Rows and cells hidden with `display:none`, `visibility:hidden` or the `hidden`
attribute are left out of the table. Strict's numeric trace checks each
header line on its own against the numbers its header cells supply, so a year
repeated over several columns does not fail strict, but cannot vouch for the
same year written in the body.

### Header alignment

A report-only check compares every table's output with its source and reports
values that sit under the wrong header. Two `ParseDiagnostics` fields carry it:

- `table_header_alignment`: one line per misaligned value, at most 10 per table
  plus the total, for example
  `table 7 (snapshot 5, page 12): "Product" 63946 under "2025 — 2024"; expected "2025", conflicting "2024"`.
- `table_header_alignment_coverage`: (key, count) pairs with the same 21 keys
  in the same order on every completed run: tables, data rows and values in
  total, each skip reason, then `values_evaluated`, `values_aligned` and
  `values_misaligned`. An empty tuple means the check did not run, because
  `quality_policy="off"`, `Parser(table_checks=False)`, or `check_tables()`
  failed; it never means zero findings.

```python
markdown, diagnostics = convert_with_diagnostics(html_bytes)
coverage = dict(diagnostics.table_header_alignment_coverage)
print(coverage["values_evaluated"], coverage["values_misaligned"])
for finding in diagnostics.table_header_alignment:
    print(finding)
```

What the check does not cover:

- Values it skips, each counted under its key: tables with no Markdown output
  (`table_no_output`), tables it cannot place reliably
  (`table_unreliable_grid`, such as nested tables or broken spans), tables
  without header rows or data rows, one-row and plain-text renderings
  (`table_no_separator`), rows below a header repeated mid-table, rows whose
  label is not unique (`row_unpaired`), nil values such as `—` (`value_nil`),
  values with no header cell that tells their column apart
  (`value_no_discriminating_header`), values missing from the output
  (`value_missing_in_output`; check 1 reports those), values found in more
  than one output cell, headers it cannot read unambiguously
  (`value_ambiguous_header`), and searches that hit their work bound
  (`value_unevaluated_budget`).
- Anything but numbers: text cells, years and header-only columns are not
  evaluated.
- Enforcement: findings are not logged, never make strict raise, and are not
  part of the XLSX export's per-table `completeness`, because the workbook has
  its own grid.

Decoding follows a deterministic precedence: Unicode BOM, recognized HTTP
`charset`, HTML/XML declaration in the first 8 KiB, strict UTF-8, then
Windows-1252 fallback. Explicitly unsupported encodings fail. A URL gives
relative links the document URL as their base; raw HTML without a base URL
keeps relative `href` values relative.

Exhibit parsing extracts exhibit entries and preserves their links; sec2md does not download those exhibits automatically. Complete accession capture is the caller's responsibility.

### Retained HTML bytes and link context

When an upstream workflow already retained the exact HTML bytes, pass the
validated item URL as `base_url` to resolve relative links without fetching the
document or attachments:

```python
pages = sec2md.convert_to_markdown(
    retained_html_bytes,
    base_url="https://www.sec.gov/Archives/edgar/data/1/2/primary.htm",
    return_pages=True,
    embed_images=False,
    quality_policy="strict",
)
```

`base_url` is link-resolution context only. It must be an absolute HTTPS URL
with a non-empty host and no username, password, or fragment; its path and
query are preserved for joining. Raw text and bytes never fetch or embed
images merely because `base_url` is present. For URL input, a supplied
`base_url` must exactly match the source URL or conversion raises `ValueError`
before the document is fetched. The same keyword-only option is available on
`parse_filing()`.

## Financial Statements

Financial statements are already well-structured - convert them directly:

```python
from pathlib import Path

# Balance sheet, income statement, cash flow (read as bytes so encoding is detected)
statement_html = Path("balance_sheet.html").read_bytes()
md = sec2md.convert_to_markdown(statement_html)
```

**Output preserves table structure:**
```markdown
| Assets                          | 2024      | 2023      |
|---------------------------------|-----------|-----------|
| Current assets:                 |           |           |
| Cash and cash equivalents       | $29,943   | $24,977   |
| Marketable securities           | $31,590   | $31,590   |
...
```

## Notes to Financial Statements

Notes are wrapped in outer table elements. Use `flatten_note()` to unwrap:

```python
import sec2md

# Notes need flattening first
# flatten_note() takes text, so name the file's encoding explicitly
note_html = open("revenue_note.html", encoding="utf-8").read()
flattened = sec2md.flatten_note(note_html)
md = sec2md.convert_to_markdown(flattened)
```

## Press Releases (8-K Exhibits)

```python
# 8-K press releases convert directly
press_release_html = Path("earnings_release.html").read_bytes()
md = sec2md.convert_to_markdown(press_release_html)
```

## Other Exhibits

Merger agreements, contracts, and other exhibits:

```python
# Exhibits (contracts, agreements, etc.)
exhibit_html = Path("merger_agreement.html").read_bytes()
md = sec2md.convert_to_markdown(exhibit_html)
```

## Best Practices

**When to use `flatten_note()`:**
- ✅ Notes to financial statements
- ✅ Accounting policy disclosures
- ❌ Financial statements (already structured)
- ❌ Full filings (no outer wrapper)

**User-Agent Requirements:**

The SEC requires a user-agent for all requests:

```python
# ✅ Good
md = sec2md.convert_to_markdown(url, user_agent="John Doe john@example.com")

# ❌ Will raise ValueError
md = sec2md.convert_to_markdown(url)
```

## Next Steps

- [Extract specific sections](sections.md) - Pull just Risk Factors or MD&A
- [Work with EdgarTools](edgartools.md) - Automate filing downloads
- [Chunk for embeddings](chunking.md) - Prepare for RAG pipelines
