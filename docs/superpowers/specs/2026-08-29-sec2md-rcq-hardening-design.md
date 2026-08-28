# sec2md RCQ Hardening Design

Date: 2026-08-29

Status: Proposed for implementation

## Purpose

Maintain `kelab5am/sec2md` as an internally controlled fork of upstream `lucasastorian/sec2md` and make it safe enough to serve as RCQ Wealth's SEC HTML-to-Markdown derivative engine.

The fork starts from upstream commit `a243bd782cd9d20a6e0f69c04bc484ea069d0e51`, published as `sec2md 0.1.22`. The first internal release will use Python package version `0.1.22+rcq.1` and Git tag `v0.1.22-rcq.1`.

## Scope Boundary

The `sec2md` repository owns:

- deterministic HTML byte decoding and legacy character normalization;
- conversion of one supplied HTML document into Markdown, pages, elements, sections, links, and parser diagnostics;
- table reconstruction, including accounting-number fidelity;
- source-node provenance for generated elements;
- fail-closed quality checks for empty, severely truncated, corrupt, or untraceable output;
- offline regression fixtures and accuracy gates for representative SEC documents;
- CI, internal versioning, fork documentation, and upstream-sync policy.

The `rcq-wealth` repository owns:

- SEC CIK/accession discovery and complete accession inventory retrieval;
- downloading the primary filing, exhibits, amendments, inline XBRL resources, and filing index;
- immutable original storage, hashes, capture manifests, and complete/partial/failed capture status;
- orchestration of `sec2md` over every supported HTML document in an accession;
- downstream research ingestion and source-authority policy.

`sec2md` will preserve and expose exhibit links, but it will not recursively fetch a filing package. It will not become a general EDGAR crawler, archive, XBRL calculation engine, PDF parser, OCR system, or research-analysis system.

## Confirmed Evidence

The pre-change `0.1.22` benchmark covered seven HTML documents:

1. Apple 2023 10-K.
2. NVIDIA 2026 10-K.
3. NVIDIA 2002 legacy 10-K.
4. NVIDIA fiscal 2027 second-quarter 10-Q.
5. NVIDIA 2026-08-26 8-K primary document.
6. NVIDIA EX-99.1 earnings release.
7. NVIDIA EX-99.2 CFO commentary.

Modern 10-K and 10-Q output preserved the audited major-statement values and exceeded 99% unique financial-row recall. The primary 8-K preserved Items 2.02 and 9.01 but did not fetch or retain actionable URLs for its substantive exhibits. Separately fetched exhibits parsed accurately.

The legacy NVIDIA 2002 filing exposed two production blockers:

- 629 C1 control characters survived into Markdown;
- accounting negatives were split across Markdown cells, for example `(16,173 | )`.

The 8-K exposed adjacent-link fragmentation such as `Augu st 2 6` and `Se cond`. Apple exposed two merged-block provenance-accounting anomalies. Upstream issue 4 also demonstrates that positioned filings can silently return zero or near-zero output.

## Compatibility and Versioning

- Retain the import package name `sec2md`.
- Retain the MIT license and original upstream attribution.
- Change project URLs and issue links to `https://github.com/kelab5am/sec2md` and add an explicit upstream-project URL.
- Document the repository as an RCQ-maintained fork.
- Use PEP 440 local versions while behavior remains based on upstream 0.1.22: `0.1.22+rcq.1`, `0.1.22+rcq.2`, and so on.
- Tag releases as `v0.1.22-rcq.1`, `v0.1.22-rcq.2`, and so on.
- Declare Python 3.10 through 3.12 support. Upstream's current source already uses Python 3.10-only union syntax despite advertising Python 3.9, so the fork will correct the metadata rather than promise an untested interpreter.
- Pin production consumers to an exact Git tag and resolved commit.
- Add an `upstream` remote in developer setup documentation. Upstream changes are reviewed and cherry-picked or merged deliberately; they are never auto-merged.

The existing public functions remain available. New quality-policy parameters will be keyword-only, so existing positional call sites do not break.

## Input Resolution and Character Normalization

### Byte decoding

Add a single deterministic decoder used for direct byte input and HTTP responses. URL fetching must use `response.content`; it must not rely on `response.text`. Direct byte input must not use `errors="ignore"`.

The decoder applies this precedence:

1. Unicode BOM when present.
2. Explicit HTTP `charset` parameter when present and recognized.
3. HTML/XML encoding declaration found in the first 8 KiB.
4. Strict UTF-8.
5. Windows-1252 fallback.

An unrecognized explicit encoding raises an input error instead of silently substituting data. The decoder returns both decoded text and structured decoding diagnostics containing the selected encoding and selection reason.

### Legacy numeric entities and controls

Before DOM parsing, numeric character references in the range 128-159 are converted through the Windows-1252 mapping. This converts legacy references such as `&#151;` into an em dash rather than a C1 control.

After text extraction, any remaining C1 characters are normalized through the same mapping. Undefined Windows-1252 bytes or surviving replacement characters are quality failures in strict mode.

Normalization must preserve ordinary Unicode punctuation and must not rewrite valid financial minus signs or em dashes used as blank-value markers.

## Parser Diagnostics and Fail-Closed Policy

Introduce immutable models:

- `DecodeDiagnostics(encoding: str, reason: str)`
- `ParseDiagnostics(source_visible_chars: int, output_visible_chars: int, output_ratio: float, replacement_characters: int, c1_control_characters: int, pages: int, elements: int, mapped_elements: int, trace_numeric_failures: tuple[str, ...], warnings: tuple[str, ...])`
- `ParseQualityError(ValueError)` carrying `ParseDiagnostics`.

Add keyword-only `quality_policy` to `convert_to_markdown` and `parse_filing`:

- `"strict"` is the default and raises `ParseQualityError` on a hard failure.
- `"warn"` returns output and records/logs warnings.
- `"off"` preserves low-level parser experimentation without quality enforcement.

Hard failures in strict mode are:

- source visible text is at least 1,000 characters and output is empty;
- source visible text is at least 10,000 characters and output/source visible-character ratio is below 0.10;
- output contains U+FFFD replacement characters;
- output contains C1 control characters;
- any element lacks a source-node mapping when elements were requested;
- a normalized numeric token appears in an element but cannot be traced to its mapped source nodes.

The ratio is a catastrophic-loss guard, not an accuracy score. Higher-fidelity recall thresholds belong to the offline fixture audit because navigation, hidden XBRL, and repeated headers make a universal runtime threshold unreliable.

`Parser` exposes its latest diagnostics. Convenience APIs enforce the selected quality policy after page and element construction.

## Table Fidelity

### Inline text extraction

Replace unconditional `get_text(separator=" ")` cell extraction with a DOM-aware renderer that:

- preserves literal whitespace already present in text nodes;
- concatenates adjacent inline fragments when the source contains no separating whitespace;
- inserts separators for block-level descendants;
- coalesces adjacent anchors with the same resolved `href` into one Markdown link;
- escapes Markdown table delimiters without changing link destinations.

This must convert the fragmented 8-K anchor sequence into one readable linked description rather than `Augu st 2 6`.

### Accounting columns

The table grid merger recognizes structural columns whose cells are consistently currency markers, opening parentheses, closing parentheses, percent signs, or blanks. These structural fragments merge with the related numeric column only when the column-wide pattern is safe.

An accounting negative must render within one Markdown cell, such as `$ (16,173)`, and its normalized numeric value must be `-16173`. Standalone em dashes remain blank-value markers, not negative numbers.

Header colspan semantics remain intact. Upstream PR 3 may be used as design evidence, but it will not be cherry-picked wholesale because it changes broad heuristics without an accompanying regression suite.

## Links and 8-K Exhibits

Add optional `url: str | None` to `Exhibit`. The 8-K section extractor parses Markdown links in Item 9.01 exhibit rows and retains their resolved URL while preserving the human-readable description.

When the caller provides a source URL, relative links resolve against that document URL. When the caller supplies raw HTML without a base URL, relative `href` values remain relative and are not guessed.

Documentation must state precisely:

- “exhibit parsing” means extracting exhibit entries and preserving their links;
- `sec2md` does not download those exhibits automatically;
- complete accession capture is the caller's responsibility.

## Provenance and XBRL Boundary

Every emitted element must map to at least one annotated source node. Segment merging must carry the union of all contributing nodes, including repeated proxy-reference paragraphs and generated headings derived from table content.

Numeric trace comparison normalizes commas, currency markers, percentages, Unicode minus signs, and accounting parentheses before comparison. Formatting transformations are permitted; invented or untraceable numeric values are not.

Element-level XBRL tags continue to describe concepts present in visible mapped nodes. They are not advertised as a complete filing-wide XBRL inventory. Hidden facts and complete fact/context/unit extraction remain outside this repository and must be handled by the RCQ accession/XBRL layer.

## Regression Corpus

Store the seven audited authoritative HTML documents as gzip-compressed offline fixtures under `tests/fixtures/sec/`. A manifest records:

- stable fixture ID;
- CIK, accession number, form, report date, and SEC archive URL;
- document role: primary, exhibit, or attachment;
- uncompressed SHA-256;
- expected encoding path;
- fixture-specific minimum text, numeric, and financial-row recall;
- expected sections and representative statement rows.

The fixture loader verifies SHA-256 before parsing. Tests never mutate fixture files.

Add a small synthetic positioned-HTML fixture reproducing upstream issue 4's CSS custom-property, `pt` coordinate, and nested positioned-leaf structure. CI must at minimum prove that catastrophic-loss validation rejects a silent empty result. Supporting full reading-order reconstruction is implemented only when backed by focused layout tests.

Accuracy tests cover:

- two-run byte determinism for Markdown, serialized pages, and annotated HTML;
- visible word and numeric recall against fixture-specific floors;
- representative financial rows and signs;
- consistent Markdown table widths;
- absence of replacement and C1 characters;
- unique element IDs and complete source-node mappings;
- zero untraceable normalized numeric tokens;
- expected 10-K, 10-Q, and 8-K sections;
- preserved 8-K exhibit URLs;
- valid visible-node XBRL concept tags.

## CI and Development Gates

Add GitHub Actions with these required jobs:

- unit and accuracy tests on Ubuntu with Python 3.10 and 3.12;
- unit and accuracy tests on Windows with Python 3.12;
- Ruff checks on source and tests;
- package build and metadata inspection on Python 3.12.

CI uses only committed offline fixtures and makes no SEC network requests. Existing tests marked `integration` remain optional developer checks.

Required local verification before release:

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m build
```

The development extra adds `build>=1.2` for the package-build gate.

## Documentation

Update README and package metadata to include:

- maintained-fork status and upstream attribution;
- internal version semantics;
- strict/warn/off quality behavior;
- encoding guarantees and remaining supported-input boundary;
- precise 8-K exhibit-link behavior;
- complete-accession responsibility;
- instructions for adding and reviewing an upstream remote;
- instructions for reproducing the offline accuracy suite.

Add `CHANGELOG.md` with an entry for `0.1.22+rcq.1` and `docs/maintenance/upstream-sync.md` describing review, testing, and release-tag rules.

## Commit and Review Strategy

Implementation is divided into independently reviewable commits:

1. Fork ownership, version metadata, CI skeleton, and maintenance documentation.
2. Audited compressed fixtures, manifest, loader, and unchanged-baseline accuracy report.
3. Parse diagnostics and catastrophic-loss fail-closed behavior.
4. Deterministic byte decoding and legacy character normalization.
5. Accounting-column reconstruction.
6. Inline-link rendering and structured exhibit URLs.
7. Provenance trace enforcement and Apple anomaly repair.
8. Full accuracy-gate refresh and release documentation.

Each behavior commit follows red-green TDD and runs focused tests before the complete suite. No parser fix is accepted solely because aggregate recall improved; representative statement values and source traceability must also pass.

## Release Acceptance Criteria

`v0.1.22-rcq.1` is releasable only when:

- all existing unit tests pass;
- all seven offline filing fixtures pass their accuracy contracts twice deterministically;
- the legacy fixture contains no replacement or C1 characters in output;
- inspected legacy accounting negatives occupy one Markdown cell and normalize to the correct sign;
- the 8-K exhibit descriptions are readable and EX-99.1/EX-99.2 URLs are retained;
- catastrophic positioned-document loss raises `ParseQualityError` in strict mode;
- every output element has a source mapping and zero normalized numeric trace failures;
- Ruff and package-build gates pass;
- GitHub Actions passes on the declared Linux/Windows Python matrix;
- the built distribution reports version `0.1.22+rcq.1` and points to the maintained fork;
- the release commit receives an independent committed-state review before tagging.

## Deferred Work

- RCQ accession acquisition and immutable-storage integration.
- Full XBRL fact/context/unit inventory.
- Complete reading-order support for every positioned SEC layout beyond the tested issue-4 pattern.
- PDF, OCR, Datalab, and multimodal extraction changes.
- Publishing to public PyPI.
