# sec2md Table Merge: Nested and Wrapped Tables Under Strict — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Withdraw two of the table merge work's named limitations: read a table nested in a row (outside every cell) once, and bind R6a header records for tables rendered inside list items and inline wrappers. PR #6 merged before this work could join it, so it lands on its own branch and PR, `fix/table-merge-strict-structure`, off `main` (decided by the user on 2026-10-07).

**Architecture:**
- **C1** (`table_parser.py`): a table nested in a row but outside every cell keeps its cells in the outer row, and its own rows are no longer also enumerated as rows of the outer table.
- **C2** (`parser.py`, `quality.py`):
  - The wrapper path records each table it renders, binds the record by R6a's existing step-2 rule, and marks it wrapped.
  - `locate_header_lines` relaxes only the first and last line boundaries for wrapped records, after checking that the table's own copy survived in the wrapper's final segment and that no link reduction crosses its boundaries.
  - The accuracy harness's independent locator gets the same rule.
- No output byte changes for any table that is neither nested outside a cell nor wrapped.

**Tech Stack:** Python 3.12 (the `tmh-proto` worktree venv), BeautifulSoup with lxml, pytest, ruff.

**Spec:** [`../specs/2026-10-05-sec2md-table-merge-header-rules-design.md`](../specs/2026-10-05-sec2md-table-merge-header-rules-design.md), revision 18: Source cell, "What does not change", R6a steps 2–3, Testing ("Revision 18") and Acceptance ("Revision 18", "Release"). The design evidence and prototype are in [`.superpowers/sdd/c2-investigation.md`](../../../.superpowers/sdd/c2-investigation.md) (workspace, not committed).

## Global Constraints

- **Where the work goes.** Branch `fix/table-merge-strict-structure`, created from `main` after PR #6's merge, one commit per task. Task 1's commit (`1e969c7`, first made on the merged `feat/table-merge-header`) is cherry-picked onto it.
  - Never push; the user pushes and opens the PR.
- **Python.** Use only that worktree's venv. No pip installs, nothing that downloads, and never run the 14 EDGAR `integration` tests.
- **Strict is never relaxed.** No change may let strict credit a number the source does not hold. Every wrapped-record association miss keeps the ordinary trace.
- **No value is lost.** C1 must keep every nested value exactly once.
- **No unrelated output change.** Element and page bytes stay the same except for tables nested outside a cell.
- **Overhead:** at most 1.10 × `main`, measured as in the table merge plan's Task 11.
- **Version** stays `0.1.22+rcq.4`. CHANGELOG changes stay within its section.
- **Read-only:** `E:\RCQWealth`. Design documents stay in the main checkout's `docs/superpowers/`.

## Task 1: C1 — a table nested outside a cell is read once

- **Files:** `src/sec2md/table_parser.py` (row enumeration in `_extract_cells` / `_create_grid`), `tests/test_table_merge_headers.py`.
- **Interfaces:** no public change.
- **Tests first** (spec Testing, "Revision 18", C1), in both modes where `Parser` is involved:
  - a `<table>` directly in a header `tr`, directly in a body `tr`, and in a `<div>` in a first row of `td` cells. Each passes strict, and every nested value appears exactly once;
  - value preservation: the no-inner-`tr` case (`987`), and outer `rowspan="2"` cells over a nested row (`987`);
  - a table nested inside a cell renders byte-for-byte as before.
- **Update the pins for the withdrawn limitation:** the `<tr>`-direct and `<div>`-wrapped tests in `test_table_merge_headers.py` and `test_quality.py` (Task 5/7 review rounds) become positive assertions. The nested-in-cell over-count tests stay as they are.
- [x] Tests (RED), implementation (GREEN), full suite (1660 + new), ruff. Commit `fix: read a table nested outside a cell once`.

## Task 2: C2 — bind and locate header records for wrapped tables

- **Files:**
  - `src/sec2md/parser.py`: the wrapper branches, `_render_table` collector, `element_header_records`, `_unbound_header_tables`.
  - `src/sec2md/quality.py`: `ElementHeaderRecord.wrapped` (trailing, default `False`) and `locate_header_lines`.
  - `tests/accuracy/metrics.py`: `_oracle_header_line_spans`.
  - Tests: `tests/test_parser.py` and `tests/test_quality.py`, plus a parity test in `tests/accuracy/test_sec_accuracy.py`.
- **Rules (spec R6a steps 2–3, revision 18):**
  - **Binding.** Bind by the step-2 rule from the wrapper path.
  - **Own copy.** Before locating, verify the record's own copy appears in the wrapper's final segment, and that no link reduction crosses the table's boundaries in the wrapper. If either check fails, the record is a miss.
  - **Location.** For wrapped records only, accept a prefix on the first line and a suffix on the last line. Everything else is unchanged: exactly one occurrence, the first line equals the header line, the span is the header line only, and the claims check applies.
- **Tests first:** the full spec matrix ("Revision 18", C2):
  - positives per wrapper (13 shapes) and links;
  - misses that keep the ordinary trace: duplicates, a wrapped table with a standalone twin, a link reduction crossing a boundary, a padded label, and **Codex's counterexample**;
  - cases where strict still fails;
  - locator unit tests;
  - oracle parity.
- **Pin updates:** `TestWrappedTableHeaderLimitation` and `test_table_rendered_inside_other_content_is_a_missing_association` become positive. Update the reset test's counts.
- **Prototype:** `scratchpad\c2-investigation\proto_inline.py`. Promote it test-first; do not copy it blindly.
- [x] Tests (RED), implementation (GREEN), full suite, ruff. Commit `feat: bind header records for tables rendered inside list items and inline wrappers (R6a)`.

## Task 3: Release text

- [x] Update `CHANGELOG.md`, `README.md` and `docs/usage/direct-conversion.md`:
  - replace the two known-limitation bullets: a table inside a header row, and wrapped tables;
  - state the C1 behaviour;
  - name the remaining association misses, which keep the ordinary trace.
- [x] Commit `docs: release notes for nested and wrapped tables under strict`.

## Task 4: Acceptance

- [x] **Phase A.** Rerun the table merge plan's Task 11 Steps 1–3 (with `--lines 9`) at the new head into scratch.
  - Every result file must equal `final/` apart from timings, the baseline path and the gzip mtime.
  - Overhead must be at most 1.10.
- [x] **Recent corpus.**
  - Rerun `strict_compare.py`: 0 new failures, with the same 18 pre-existing failures.
  - Rerun `prevalence.py`: same counts.
  - Rerun the acceptance tooling with `--corpus recent`: the three verdicts and figures equal Task 6's.
- [x] Record the results in the main checkout's `docs/superpowers/audits/2026-10-06-table-merge-header-acceptance/rev18.md`. Ask the user before committing to `main`.
- [x] Hand over the push command for the updated PR branch. Never push.

## Result (2026-10-07)

Branch `fix/table-merge-strict-structure`: `5bf488f` (C1), `f84d103` (C2), `2252046` and `0463ed1` (test pins), `2f19e5f` and `d7a92b7` (release text and docstrings). Every task was reviewed; C1 needed two fix rounds (values lost under rowspans, and an all-hidden-cells row). Full suite 1885 passed, ruff clean. Acceptance: [`rev18.md`](../audits/2026-10-06-table-merge-header-acceptance/rev18.md) — no corpus figure changes, overhead 1.0794. The final whole-branch review found the branch ready to merge.
