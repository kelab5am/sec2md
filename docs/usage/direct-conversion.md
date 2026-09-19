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
# Balance sheet, income statement, cash flow
statement_html = open("balance_sheet.html").read()
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
note_html = open("revenue_note.html").read()
flattened = sec2md.flatten_note(note_html)
md = sec2md.convert_to_markdown(flattened)
```

## Press Releases (8-K Exhibits)

```python
# 8-K press releases convert directly
press_release_html = open("earnings_release.html").read()
md = sec2md.convert_to_markdown(press_release_html)
```

## Other Exhibits

Merger agreements, contracts, and other exhibits:

```python
# Exhibits (contracts, agreements, etc.)
exhibit_html = open("merger_agreement.html").read()
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
