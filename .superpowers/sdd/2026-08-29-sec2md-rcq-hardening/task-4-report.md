# Task 4 Report: Deterministic SEC HTML Decoding

## Result

Implemented deterministic byte decoding, Windows-1252 legacy-character
normalization, and lossless HTTP response handling. Direct bytes and fetched
HTTP content now use the same decoder; raw string input is normalized before
BeautifulSoup parsing. Parser instances retain the selected decode diagnostics
without changing `ParseDiagnostics`.

## RED verification

After adding the decoder and routing tests, before implementation the required
focused command was run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_encoding.py tests/test_utils.py tests/test_core.py -v
```

Result: collection failed as expected:

```text
ModuleNotFoundError: No module named 'sec2md.encoding'
```

## Implementation

- Added frozen `DecodeDiagnostics`, deterministic BOM/HTTP declaration/strict
  UTF-8/Windows-1252 fallback selection, and explicit unknown-codec errors in
  `src/sec2md/encoding.py`.
- Preserved undefined Windows-1252 bytes as their C1 code points so
  normalization raises a precise `ValueError` rather than dropping or
  replacing data.
- Converted Windows-1252 numeric references in the 128–159 range and literal
  C1 characters through the Windows-1252 mapping while preserving valid
  Unicode punctuation, minus signs, and em dashes.
- Changed `fetch` to return frozen `FetchedHtml` with `response.content` and
  the parsed `Content-Type` charset; `response.text` is no longer used.
- Routed direct bytes and HTTP bytes through `decode_html`, preserved the PDF
  guard before decoding, normalized string input, and passed decode
  diagnostics into `Parser`.
- Updated the offline accuracy harness to normalize the source corpus through
  the same decoder before comparing rows and visible text. This keeps the
  accounting defect XFAIL meaningful after legacy labels are correctly
  normalized.
- Removed only the legacy C1 XFAIL; the accounting, 8-K link, and Apple trace
  XFAILs remain.
- Updated the fixture manifest with the decoder's final reason vocabulary and
  exported `DecodeDiagnostics` from the package root.

## GREEN verification

Focused encoding/core/utils command:

```powershell
.\.venv\Scripts\python -m pytest tests/test_encoding.py tests/test_utils.py tests/test_core.py -v
```

Result:

```text
37 passed, 1 warning in 0.31s
```

The warning is the linked-worktree pytest cache permission warning.

Required legacy subset:

```powershell
.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py -k "nvda_2002 or character" -v
```

Result:

```text
1 passed, 37 deselected, 1 warning in 15.94s
```

The legacy output contains zero U+FFFD replacement characters and zero
U+0080–U+009F C1 controls. The accounting defect remains the expected XFAIL.

Full accuracy command:

```powershell
.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py -q
```

Result:

```text
35 passed, 3 xfailed, 1 warning in 55.92s
```

Full suite:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Result:

```text
258 passed, 14 deselected, 3 xfailed, 1 warning in 56.89s
```

Lint and whitespace checks:

```powershell
.\.venv\Scripts\ruff.exe check src tests
git diff --check
git diff --cached --check
```

Result: Ruff passed and both whitespace checks reported no errors.

## Self-review

- Decoder precedence has one return path per required level: BOM, explicit
  HTTP charset, document declaration within the first 8 KiB, strict UTF-8,
  then Windows-1252 fallback.
- Codec labels for explicit declarations are resolved with `codecs.lookup`;
  unknown explicit codecs raise `ValueError`.
- No `errors="ignore"` or `errors="replace"` decoding remains in the changed
  input path.
- PDF detection remains before decoding for direct bytes and fetched content.
- `ParseDiagnostics` fields are unchanged; decode metadata is retained on
  `Parser.decode_diagnostics`.
- The required legacy character, HTTP-content, declaration-boundary, BOM,
  fallback, unknown-codec, and punctuation-preservation regressions are
  covered.
- No secrets, SEC fixtures, remotes, tags, or `rcq-wealth` files were touched.

## Files changed

- `.superpowers/sdd/2026-08-29-sec2md-rcq-hardening/task-4-report.md`
- `src/sec2md/__init__.py`
- `src/sec2md/core.py`
- `src/sec2md/encoding.py`
- `src/sec2md/parser.py`
- `src/sec2md/utils.py`
- `tests/accuracy/metrics.py`
- `tests/accuracy/test_sec_accuracy.py`
- `tests/fixtures/sec/manifest.json`
- `tests/test_core.py`
- `tests/test_encoding.py`
- `tests/test_utils.py`

## Commit

Committed as:

`feat: decode SEC HTML deterministically`
