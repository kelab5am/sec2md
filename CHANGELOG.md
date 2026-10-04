# Changelog

## 0.1.22+rcq.3 (unreleased, pending review)

- Table completeness checks, report-only: each visible table's Markdown is
  compared with its source table.
  - `ParseDiagnostics` gains `table_completeness_failures`,
    `table_completeness_reported`, `table_structure_differences`,
    `tables_checked` and `numeric_recall`.
  - Under `strict` and `warn`, each document with missing table values logs one
    summary warning and each value failure at INFO level; lost markers,
    references and row-order findings are not logged. Nothing raises yet.
    `quality_policy="off"` and `Parser(table_checks=False)` skip the checks.
  - If the missing-value and row-order checks (`check_tables()`) fail, the
    error is logged and the conversion continues without a table report, as if
    the checks were off. An error in `numeric_recall` still propagates.
  - `convert_with_diagnostics()` returns the output with its diagnostics.
  - `export_xlsx()` results gain `parse_diagnostics` and a per-table
    `completeness`.
- Quality checks normalize euro and pound amounts like dollar amounts. Because
  table merging uses the same normalizer, a split euro or pound negative such
  as `(€567` + `)` now merges into one cell, as dollar amounts already did.
  Strict's numeric trace changes the same way: a euro or pound amount whose
  currency sign sits in its own cell (`€ | 1,234`) no longer fails strict as
  untraceable, and the rare split layouts that already fail for dollars now
  fail for euros and pounds too.
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
