# sec2md

This is the RCQ-maintained fork of [`lucasastorian/sec2md`](https://github.com/lucasastorian/sec2md). `sec2md` parses one supplied HTML document; it does not download a complete accession. Consumers should pin an independently reviewed commit and require distribution version `0.1.22+rcq.4` for reproducible use.

[![PyPI](https://img.shields.io/pypi/v/sec2md.svg)](https://pypi.org/project/sec2md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-readthedocs-blue.svg)](https://sec2md.readthedocs.io)

Transform messy SEC filings into clean, structured Markdown.
**Built for AI. Optimized for retrieval. Traceable to the source.**

![Before and After Comparison](comparison.png)
*Apple 10-K: Raw SEC HTML (left) vs. sec2md output (right)*

---

## The Problem

SEC filings are the worst documents you'll ever feed to an LLM — 200 pages of nested HTML, XBRL tags, invisible elements, and tables-within-tables. Standard parsers break tables into garbled text, collapse sections into a single wall of prose, and lose the formatting cues that LLMs need to reason over structured content.

But even the converters that handle the HTML well still throw away **provenance**. You get clean text with no way to trace an answer back to where it came from in the original filing. For production RAG on regulated documents, that's a dealbreaker.

## The Solution

`sec2md` rebuilds SEC filings as clean, semantic Markdown — preserving structure, tables, and pagination. Unlike generic converters, it also preserves the **full citation chain** from every piece of output back to the source HTML, and extracts **iXBRL tags** so you can filter by the accounting taxonomy itself.

---

## Usage

### Export tables to Excel

Install this fork with `python -m pip install ".[xlsx]"`, then export one supplied
filing to an editable workbook:

```python
from pathlib import Path
from sec2md import export_xlsx

result = export_xlsx(Path("filing.htm").read_bytes(), Path("tables.xlsx"))
print(result.path, result.status)
```

Contents links to every parser-recognized table, including nonfinancial tables.
Copy ranges retain complete headers, units and static numeric values; visible
originals and review notes preserve uncertainty. No rows are frozen (only the
first label column). Existing files require `overwrite=True`.
See [XLSX usage and limitations](docs/usage/xlsx-export.md).

### 1. Convert a Filing to Markdown

```python
import sec2md

pages = sec2md.parse_filing(
    "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
    user_agent="Your Name <you@example.com>"
)

pages[0]
# Page(number=1, tokens=412, elements=8, preview='**FORM 10-K** ...')
#   .content    → Clean markdown text
#   .elements   → [Element(id='sec2md-p1-s0-...', kind='section', ...), ...]
#   .tokens     → 412

# 60 pages | 293 citable elements | 46,238 tokens
```

### 2. Extract Sections

A 10-K is modular — Business, Risk Factors, MD&A, Financial Statements. sec2md detects PART and ITEM boundaries automatically, so you can pull exactly the section you need instead of processing 200 pages:

```python
from sec2md import Item10K

sections = sec2md.extract_sections(pages, filing_type="10-K")
risk = sec2md.get_section(sections, Item10K.RISK_FACTORS)

risk
# Section(item='ITEM 1A', title='Risk Factors', pages=7-19, tokens=11474)
#   .markdown()   → Full section as markdown string
#   .page_range   → (7, 19)
#   .pages        → [Page(...), Page(...), ...]
```

### 3. Chunk for RAG

Page-aware, token-budgeted chunks — each one carrying page numbers, element IDs, XBRL tags, and display pages from the filing footer:

```python
chunks = sec2md.chunk_pages(pages, chunk_size=512)

chunks[5]
# Chunk[5](pages=12-13, display_pages=45-46, blocks=4, tokens=487)
#   .content         → Clean markdown text
#   .page_range      → (12, 13)
#   .element_ids     → ['sec2md-p12-t3-a1b2c3d4', 'sec2md-p12-p4-e5f6g7h8', ...]
#   .tags            → ['us-gaap:Assets', 'us-gaap:Liabilities', ...]
#   .has_table       → True
```

You can also chunk individual sections or XBRL TextBlocks. Large tables are automatically split across chunks with headers preserved.

---

## Supported Filings

sec2md works with any SEC filing served as HTML. For filings with standardized structure, it also extracts individual sections automatically:

| Filing Type | Section Extraction |
|---|---|
| **10-K** | 18 items (ITEM 1–16), full PART/ITEM detection |
| **10-Q** | 11 items (Parts I & II) |
| **8-K** | 41 items (1.01–9.01), exhibit parsing |
| **20-F** | Items 1–19, 16A–16I |
| **SC 13D** | 7 items (Items 1–7) |
| **SC 13G** | 10 items (Items 1–10) |

All other filing types — S-1, S-3, S-4, F-1, 424B, 6-K, DEF 14A, DEFA14A, 40-F, N-CSR, SC TO-T, and any HTML exhibit or attachment — are parsed as clean Markdown with full traceability.

### Input, quality, and exhibit links

The public `convert_to_markdown()` and `parse_filing()` convenience functions
accept one supplied HTML document as text or bytes, or a URL for one HTML
document. They do not acquire a complete accession, fetch exhibits, parse
PDF/OCR input, or build a filing-wide XBRL inventory.

Both functions expose the keyword-only `quality_policy` argument. It defaults
to `"strict"`, which raises `ParseQualityError` when catastrophic output loss,
replacement/C1 characters, missing source mappings, or untraceable normalized
numbers are detected. `"warn"` returns the output and records quality warnings;
`"off"` disables quality enforcement for parser experimentation. A strict
failure exposes the immutable `ParseQualityError.diagnostics` object.

Strict raises in these cases:

- a source with at least 1,000 visible characters produces empty output
- a source with at least 10,000 visible characters keeps less than 10% of them
- the output contains replacement (U+FFFD) or C1 control characters
- an element lacks a source-node mapping
- a number in an element cannot be traced to its source nodes

A table's header line is traced on its own against the numbers its header cells
supply, so a number repeated because a header cell spans several columns does
not raise. This holds for a table inside a list item or bold or italic text too.
When a header line cannot be matched to its own table, for example when the same
table text occurs twice in one element or a link in the surrounding text runs
into the table, the miss is listed in `Parser.header_accounting_misses` and the
line is traced like any other text, so a repeated header number can raise.

Strict does not check that every source number reached the output. Table
completeness checks do that for each table, and a header-alignment check tests
that each value sits under the header its source column carries. They are
reported but not enforced yet. Their findings appear in these
`ParseDiagnostics` fields:

- `table_completeness_failures`: numbers missing from a table's output
- `table_completeness_reported`: lost footnote markers and references such as
  `Note 9`, which are never enforced
- `table_structure_differences`: rows or values that changed order
- `numeric_recall`: the share of visible source numbers present in the output.
  A number that starts an output line like a list marker (`2. Summary …`) is
  not counted on the output side, so recall can read low.
- `table_header_alignment`: values whose output column header does not match
  the header cells above their source column, at most 10 per table plus a total:
  `table 24 (snapshot 19, page 41): "Revenue" 941168 under "2025 — RMB"; expected "2024"`
- `table_header_alignment_coverage`: how many tables, rows and values the
  alignment check evaluated, and how many it skipped and why, as (key, count)
  pairs. A completed run always lists the same 21 keys in the same order, with
  zeros where nothing applied; an empty tuple means the check did not run.

No alignment findings means no misplaced value among the values the check
evaluated; `values_evaluated` says how many that was. It skips, and counts:
tables with no Markdown output, tables it cannot place reliably (nested tables,
broken spans), tables without header rows or without data rows, one-row and
plain-text renderings, rows below a header repeated mid-table, rows whose label
is not unique in the table, nil values such as `—`, values with no header cell
that tells their column apart from the others (a caption over every column is
never required), values missing from the output (check 1 reports those), values
found in more than one output cell, headers it cannot read unambiguously, and
header searches that reach their work bound. It judges numbers only: text
cells, years and header-only columns are not evaluated. It is not logged, never
makes strict raise, and is not applied to XLSX output, whose workbook has its
own grid.

Each document with missing table values logs one summary warning, and each of
those value failures is logged at INFO level. Lost markers, references and
row-order findings are not logged yet. If the missing-value and row-order
checks (`check_tables()`) fail, the error is logged and the conversion
continues without a table report, so the diagnostics look as if the checks were
off. Errors elsewhere, such as in the `numeric_recall` computation, still
propagate. Use `convert_with_diagnostics()` to get the output together with its
diagnostics. `quality_policy="off"` skips these checks.

Byte decoding is deterministic: a Unicode BOM wins, followed by a recognized
HTTP `charset`, an HTML/XML declaration in the first 8 KiB, strict UTF-8, and
finally Windows-1252 fallback. Unsupported explicit encodings fail rather than
silently substituting data.

When a source URL is provided, relative links resolve against that document
URL. With raw HTML and no base URL, relative `href` values remain relative.
Exhibit parsing extracts exhibit entries and preserves their links; sec2md does not download those exhibits automatically. Complete accession capture is the caller's responsibility.

Callers holding exact retained HTML bytes can supply a validated `base_url` for
link resolution without giving sec2md an acquisition job:

```python
pages = sec2md.convert_to_markdown(
    retained_html_bytes,
    base_url="https://www.sec.gov/Archives/edgar/data/1/2/primary.htm",
    return_pages=True,
    embed_images=False,
    quality_policy="strict",
)
```

`base_url` resolves relative links only. It does not fetch the document or
attachments, and image embedding is not performed for raw text or bytes even
when `embed_images=True`. It must be an absolute HTTPS URL with a non-empty
host and no username, password, or fragment; its path and query are preserved
for joining. For URL input, an explicitly supplied `base_url` must exactly
match the source URL or conversion raises `ValueError` before fetching.

## Complex Table Handling

SEC tables are notoriously complex — rowspans, colspans, merged cells, currency symbols in separate columns. Some filings don't even use `<table>` tags, building tables from absolutely-positioned CSS divs instead.

sec2md handles both:

```markdown
| Product Category | Revenue (millions) |
|------------------|-------------------|
| iPhone           | $200,583          |
| Mac              | $29,357           |
| iPad             | $28,300           |
```

Merging columns no longer drops source values, and each value sits under the
header its source column carries. Cells that rowspans from earlier rows push
past a table's widest row are still dropped, as before; a dropped number is
reported in `table_completeness_failures`. A table with several header rows gets
one header line: each column's header rows are joined top to bottom with ` — `,
and a header cell that spans several columns repeats in each of them. Currency
markers in their own column join the amount, as `$` does:

```markdown
|  | Year Ended June 30, — 2025 | Year Ended June 30, — 2024 |
| --- | --- | --- |
| Revenue | $ 1,234 | $ 1,100 |
| Operating income | 456 | 412 |
```

Header rows are the rows before the first data row, as long as each row after
the first looks like a header row: an empty label cell, a period or unit caption
or a year in the label cell, a row of years, a row of `th` cells, or a row with
text in its label cell only, such as a second title line. A second row of column
headings under a mostly empty first row also stays, as before; columns holding only
currency markers, `%`, `)`, `)%` or `(` are not counted. A row with any other
label, such as `Common Stock | AAPL`, stays in the body, and so do label-only rows
at the end of the header, such as `Accounts Receivable:` just before the data. A
table whose first row is already data gets a header line of empty cells, so no
data row is mistaken for a header. Hidden rows and cells (`display:none`) are
left out. A `<table>` placed in a row of another table but outside every cell
(malformed markup) is read once, as cells of that row, except that in a one-row
table such a table with no `<tr>` of its own is still dropped, as before; a table
nested inside a cell is flattened into the outer table as before. XLSX export
keeps its own column rules, so its prepared tables do not change. The page
number on its contents sheet, like `Page.display_page`, comes from absolutely
positioned page footers when a document has them, and is otherwise guessed from
the Markdown page text with its table rows and divider lines left out. So the
new table layout does not move it, except through the first line of a table
inside a list item or bold or italic text, which also holds the list marker or
emphasis marks and is still read (no page moves on the review corpus or the
recent filings corpus).

## Multimodal: Image Extraction

Charts, performance graphs, and segment breakdowns are extracted as first-class elements — same page tracking, same element IDs, same citation chain as every paragraph and table:

```python
chunks = sec2md.chunk_pages(pages)

image_chunks = [c for c in chunks if c.has_image]
image_chunks[0]
# Chunk[12](pages=5, blocks=2, tokens=156)
#   .images      → [Element(id='sec2md-p5-i0-...', kind='image', ...)]
#   .has_image   → True

# Self-contained HTML — no broken image links
pages = sec2md.parse_filing(url, user_agent="...", embed_images=True)
```

Feed image chunks to a vision model, text chunks to a text model. Every image stays traceable back to the source filing.

## Traceability

Every paragraph, table, and heading gets a **stable element ID** that maps directly to a DOM node in the original filing HTML. From chunk to element to source — the chain is unbroken.

The parser injects these IDs directly into the HTML via `parser.html()` — so every element in your Markdown output has a corresponding tagged node in the source. You can store that annotated HTML yourself, and given any chunk's `element_ids`, locate and highlight the exact source nodes in the original filing.

```python
parser = sec2md.Parser(filing_html)
pages = parser.get_pages()
chunks = sec2md.chunk_pages(pages)

# The annotated HTML has element IDs injected into the DOM
annotated_html = parser.html()

# See exactly where a chunk comes from in the original filing
chunk = chunks[5]
chunk.visualize(annotated_html)

# Or drill down to a single element
chunk.elements[0].visualize(annotated_html)
```

![Traceability](examples/tracability.png)
*`element.visualize()` opens the original filing HTML, scrolls to the source element, and highlights it.*

When your LLM says "revenue was $394B" and compliance asks *show me* — you can point to the exact location in the filing. Not the chunk. Not the Markdown. The source.

## iXBRL Tag Extraction

iXBRL filings embed structured financial facts directly in the HTML. sec2md extracts the XBRL concept names and attaches them to elements and chunks — giving you a metadata filter for retrieval. Instead of relying on semantic search alone, you can scope your query to only chunks tagged with the exact XBRL concepts you care about.

```python
pages = sec2md.parse_filing(url, user_agent="...")
chunks = sec2md.chunk_pages(pages)

# Store chunk.tags as metadata in your vector DB, then filter at query time:
# "What was Apple's revenue?" + metadata filter: tags contains 'us-gaap:Revenue*'

# Or filter in code — find the balance sheet
[e for p in pages for e in (p.elements or []) if e.tags and 'us-gaap:Assets' in e.tags]

# All revenue-tagged chunks
[c for c in chunks if any('Revenue' in t for t in c.tags)]
```

On a real Apple 10-K: 76 of 293 elements carry XBRL tags across 330 distinct concepts. The Income Statement table alone carries 15 tags, the Balance Sheet 32, Cash Flows 29. Cover page elements get `dei:*` tags, and notes get their TextBlock concept names.

---

## Installation

```bash
pip install "sec2md[xlsx] @ git+https://github.com/kelab5am/sec2md@<reviewed-commit>"
```

This fork is not published to PyPI: `pip install sec2md` installs the upstream
package, which lacks `quality_policy`, `base_url` and XLSX export. Drop `[xlsx]`
if you do not need Excel export.

## Getting Started

Try the [Getting Started notebook](examples/getting_started.ipynb) — parse a real 10-K, extract sections, chunk for RAG, and visualize traceability in under a minute.

### Works with edgartools

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
pages = sec2md.parse_filing(filing.html())
```

## Documentation

Full documentation: [sec2md.readthedocs.io](https://sec2md.readthedocs.io)

- [Quickstart Guide](https://sec2md.readthedocs.io/quickstart)
- [Convert Filings](https://sec2md.readthedocs.io/usage/direct-conversion)
- [Extract Sections](https://sec2md.readthedocs.io/usage/sections)
- [Chunking for RAG](https://sec2md.readthedocs.io/usage/chunking)
- [EdgarTools Integration](https://sec2md.readthedocs.io/usage/edgartools)
- [API Reference](https://sec2md.readthedocs.io/api/convert_to_markdown)

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT © 2025
