# convert_to_markdown

Convert SEC filing HTML to Markdown.

## Signature

```python
def convert_to_markdown(
    source: str | bytes,
    *,
    user_agent: str | None = None,
    return_pages: bool = False,
    quality_policy: Literal["strict", "warn", "off"] = "strict",
) -> str | List[Page]
```

`quality_policy` is keyword-only and defaults to `"strict"`. The same
keyword-only option is available on `parse_filing()`.

## Parameters

**`source`** *(str | bytes)*
: URL or HTML string/bytes to convert

**`user_agent`** *(str | None)*
: User agent for EDGAR requests (required for `sec.gov` URLs)
: Format: `"Your Name <you@example.com>"`

**`return_pages`** *(bool)*
: If `True`, returns `List[Page]` instead of markdown string
: Default: `False`

**`quality_policy`** *(`"strict"` | `"warn"` | `"off"`)*
: Quality enforcement mode; default: `"strict"`
: `"strict"` raises `ParseQualityError` on catastrophic loss, replacement or
  C1 characters, missing source-node mappings, or untraceable normalized
  numeric values.
: `"warn"` returns the output and records warnings; `"off"` disables quality
  enforcement for parser experimentation.
: Strict failures expose the immutable `ParseQualityError.diagnostics` object.

## Returns

**`str`** (when `return_pages=False`)
: Full document as markdown string

**`List[Page]`** (when `return_pages=True`)
: List of Page objects with `.number` and `.content` attributes

## Raises

**`ValueError`**
: - If source is PDF content
: - If EDGAR URL accessed without `user_agent`

**`requests.RequestException`**
: If URL fetch fails

The supported input boundary is one supplied HTML document as text or bytes,
or a URL for one HTML document. Decoding is deterministic: Unicode BOM, then a
recognized HTTP `charset`, an HTML/XML declaration in the first 8 KiB, strict
UTF-8, and Windows-1252 fallback. An unrecognized explicit encoding raises an
input error.

When a source URL is supplied, relative links resolve against that document
URL. With raw HTML and no base URL, relative `href` values remain relative.
Exhibit parsing extracts exhibit entries and preserves their links; sec2md does not download those exhibits automatically. Complete accession capture is the caller's responsibility.

## Examples

### Basic Conversion

```python
import sec2md

# From URL
md = sec2md.convert_to_markdown(
    "https://www.sec.gov/Archives/edgar/data/.../10k.htm",
    user_agent="John Doe <john@example.com>"
)
```

### From HTML File

```python
with open("10k.html") as f:
    html = f.read()

md = sec2md.convert_to_markdown(html)
```

### Get Pages for Section Extraction

```python
pages = sec2md.convert_to_markdown(
    html,
    return_pages=True  # Returns List[Page]
)

# Each page has number and content
for page in pages:
    print(f"Page {page.number}: {page.content[:100]}...")
```

## Notes

- **User-Agent Requirement**: The SEC requires a user-agent header for all requests. Always provide your name and email when fetching from `sec.gov` URLs.

- **Token Usage**: Use `return_pages=True` when you need page tracking for citations or section extraction.

- **PDF Detection**: The function automatically detects and rejects PDF content with a helpful error message.

## See Also

- [extract_sections](extract_sections.md) - Extract specific sections from pages
- [chunk_pages](chunk.md) - Split pages into chunks for embeddings
