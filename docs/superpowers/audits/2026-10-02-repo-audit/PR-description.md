Title: Fix audit-found chunking, section, quality and XLSX bugs; design a table completeness check

## Summary

This PR fixes bugs found by the 2026-10-02 repository audit, re-checked against
the RCQ META and RDDT filings, and adds a design spec for review. It is ready
for review, not for release: the version is bumped to `0.1.22+rcq.3` and the
CHANGELOG marks it unreleased.

**Fixes (commit 1a3c489)**
- **`chunk_section()` leaked neighbouring sections.**
  - Before: AAPL Item 1B ("None.", 41 chars) chunked to 6,483 chars of Risk
    Factors text; on META/RDDT the worst section was 25×–143× its own text.
  - Now: the worst section is at most 1.19× on META/RDDT, with each section's
    elements scoped to its slice.
- **META 10-Qs returned 0 sections.** `PART I—FINANCIAL INFORMATION` (no space
  around the dash) is now detected; each META 10-Q yields its 9 items.
- **XLSX statements exported as text.** "Three Months Ended March 31," above a
  year row is now a period header.
  - Exported tables across 20 META/RDDT filings rose from about 89 to 384 of 918.
  - All 10,544 exported numbers match a number in their own source table.
  - META and RDDT Q1 2026 income statements now export with correct headers,
    units and values.
- **Chunking:**
  - overlap no longer skips short blocks
  - split tables keep caption, units and header rows
  - the extra separator column is gone
  - `Chunk.tags` order is stable
- **Sections and enums:** `get_section()` accepts `Item8K`, and Item 9C gets its
  correct name with the old member kept as an alias.
- **Quality:**
  - ordered lists pass strict
  - `ParseQualityError` pickles
  - an invalid `quality_policy` is rejected before fetching
- **`export_xlsx()`:**
  - fails fast, before parsing, on an unwritable folder; previously it could
    retry about 2³¹ times on Windows
  - a staging-cleanup failure no longer fails a completed publish
- **Hygiene:**
  - tests import this checkout's `src`, and a guard refuses another tree
  - CI runs Python 3.11
  - install docs point at this fork
  - docs read local files as bytes
  - `requirements.txt` mirrors `pyproject.toml`
  - `outputs/` is untracked and ignored

**Spec for review (commit d99bb56):**
`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`

- Strict quality only checks output→source, so it misses lost values.
- The spec adds a per-table source→output check.
- Prototype results: 11 of 290 fixture tables and 103 of 1,037 META/RDDT
  tables flagged, and every inspected flag was a genuine loss. Default strict
  passes all of these today.
- Decisions D1–D5 need reviewer input. D1 (when strict starts enforcing) is
  the main one.

## Review notes
- Merging untracks `outputs/rddt-export-diagnosis/`, so git deletes it from a
  checkout's disk on merge. Restore with
  `git restore --source=305906c --worktree outputs/rddt-export-diagnosis`.
- The period-header fix changes which tables export as numbers. Because of
  that, the before/after comparison and the value check above were run on
  real filings, not only the NVDA fixtures.
- Still open, and out of scope here:
  - 373 RCQ tables remain text-only ("Unresolved value span")
  - the Markdown table losses the spec describes (column-merge row 0, period
    headers)
  - the remaining audit findings

## Test plan
- [x] `python -m pytest -q`: 594 passed, 14 deselected (integration), on Python 3.12, Windows
- [x] `python -m ruff check src tests`: clean
- [x] Each new regression test watched failing before its fix
- [x] Read-only before/after runs over 20 META/RDDT 10-K/10-Q filings (sections, chunk sizes, XLSX statuses, value check)
- [ ] CI on Linux 3.10/3.11/3.12 and Windows 3.12

🤖 Generated with [Claude Code](https://claude.com/claude-code)
