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

## Fix Round 1: Attribute-Aware Meta Declaration Detection

### Finding addressed

The original declaration matcher searched raw bytes across the entire meta
tag, so `charset=` inside descriptive `content` and `data-charset` could be
mistaken for an encoding declaration. This could select Windows-1252 for a
UTF-8 document and produce mojibake. Meta attributes are now parsed
quote-aware; only a real `charset` attribute or a `content` charset paired
with `http-equiv="Content-Type"` is accepted.

### RED verification

Added regressions for descriptive content and `data-charset`, plus coverage
for valid direct `charset` and valid `http-equiv` content-type forms. Against
the pre-fix implementation:

```powershell
.\.venv\Scripts\python -m pytest tests/test_encoding.py -k "meta_declarations or descriptive_meta" -v
```

Result:

```text
2 failed, 2 passed, 11 deselected, 2 warnings in 0.35s
```

The two failures were the expected false-positive declaration cases; both
valid declaration forms already passed.

### GREEN verification

Focused declaration regressions:

```powershell
.\.venv\Scripts\python -m pytest tests/test_encoding.py -k "meta_declarations or descriptive_meta" -v
```

Result:

```text
4 passed, 11 deselected, 1 warning in 0.27s
```

Required focused command:

```powershell
.\.venv\Scripts\python -m pytest tests/test_encoding.py tests/test_utils.py tests/test_core.py -v
```

Result:

```text
41 passed, 1 warning in 0.33s
```

Full suite:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Result:

```text
262 passed, 14 deselected, 3 xfailed, 1 warning in 55.89s
```

Lint and whitespace checks:

```powershell
.\.venv\Scripts\ruff.exe check src tests
git diff --check
```

Result: Ruff passed and no whitespace errors were reported.

### Self-review

- Meta tags are located and terminated with quote-aware scanning, and their
  attributes are parsed without decoding arbitrary source bytes.
- `charset` is accepted only as the exact attribute name; content-based
  charset declarations require a case-insensitive `Content-Type` http-equiv.
- Valid direct charset and valid HTTP-equiv declarations remain covered.
- Descriptive content and data attributes cannot override strict UTF-8.
- The deferred UTF-16/32 BOM coverage and the controller ruling on U+FFFD
  quality-policy behavior were left unchanged.
- No files outside the encoding implementation and its focused tests changed
  in this fix round.

## Fix Round 1 Commit

Committed as:

`fix: parse meta encoding declarations accurately`
