# Changelog

## 0.1.22+rcq.3 (unreleased, pending review)

- Added XLSX table export: `export_xlsx()` and the `sec2md[xlsx]` extra
  (pull requests #1 and #2).
- `chunk_section()` no longer returns neighbouring sections' text, element IDs
  and tags when sections share a page. An element that straddles a section
  boundary contributes only its own part to each section.
- Chunk overlap stays contiguous; short trailing blocks are no longer skipped.
- Split tables repeat their caption, units and header rows in every part, and
  table minification no longer adds a separator column or overwrites line 2.
- `Chunk.tags` is in first-seen order instead of depending on the hash seed.
- `get_section()` accepts `Item8K` members.
- PART headings joined by a dash or colon (`PART I—FINANCIAL INFORMATION`) are
  detected. Every META 10-Q previously returned no sections.
- XLSX export recognises period headers such as "Three Months Ended March 31,"
  above a year row. Income, comprehensive-income, equity and cash-flow
  statements in META and RDDT filings previously exported as text only.
- Added `Item10K.FOREIGN_JURISDICTION_INSPECTIONS` for Item 9C;
  `Item10K.CYBERSECURITY_DISCLOSURES` remains as a deprecated alias of it.
- Strict quality no longer rejects documents with ordered lists.
  `ParseQualityError` survives pickling, and an invalid `quality_policy` is
  rejected before any fetch.
- `export_xlsx()` checks that the destination folder is writable before parsing
  and fails within a few attempts instead of retrying for days on Windows. A
  failed staging-file cleanup no longer fails a completed publish.
- Tests always import this checkout's `src`, and fixture checks no longer depend
  on the working directory. CI also runs Python 3.11.
- Docs install this fork rather than the upstream PyPI package, and read local
  files as bytes.

## 0.1.22+rcq.2 (2026-08-29)

- Added keyword-only `base_url` link-resolution context for retained HTML text
  and bytes without network acquisition.
- Added compatibility, no-fetch, validation, image-isolation, and quality-policy tests.
- Updated API documentation and package version declarations.

## 0.1.22+rcq.1 (2026-08-29)

- Deterministic decoding.
- Strict quality checks.
- Table and link fixes.
- Provenance checks.
- Offline fixtures.
- Continuous integration.
