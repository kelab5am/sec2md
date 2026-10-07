# Revision 18 acceptance: nested and wrapped tables under strict

Date: 2026-10-07. This is Task 4 of the plan [`2026-10-07-sec2md-table-merge-strict-structure`](../../plans/2026-10-07-sec2md-table-merge-strict-structure.md).

- **Candidate:** branch `fix/table-merge-strict-structure` (worktree `.worktrees/strict-structure`).
  - Its `src` tree is `471e18e`. That tree is the same at `f84d103` and at the head, `2f19e5f`; the commits after `f84d103` change only tests and docs.
  - The candidate holds the merged table-merge work plus revision 18's two changes. It does not hold the strict-emphasis fix (PR #7) or the display-page fix (PR #8).
- **Baseline:** a fresh `git archive c674828`, the baseline every earlier run used.
- **Python:** the worktree venv. Each run recorded `sec2md.__file__` on each side.

## Verdict

**Revision 18 changes no corpus figure, and overhead stays within budget.** The reason is that neither corpus holds a wrapped or nested table. The prevalence detectors and an independent scan both counted 0 in 179 documents.

## Phase A (109 documents): rerun of the table merge plan's Task 11, Steps 1–2

Every result file equals `final/`, apart from timings, `sec2md` paths and the gzip header's mtime.

| Files | Result |
|---|---|
| `alignment.json`, `alignment_losses.json`, `check1.json`, `class8.json`, `findings.json`, `header_departures.json`, `limitations.json`, `modes.json`, `moved_rows.json`, `retention.json`, `review_sample.txt` (`--lines 9`), `sections.json`, `shifted_tables.json`, `strict.json`, `summary.json`, `xlsx.json`, `xlsx_detail.json` | Byte-identical |
| `alignment_values.tsv.gz` | Identical once decompressed; only the gzip mtime differs |
| `assignment.json`, `run_check.json` | Only paths and seconds differ |

The raw per-document dumps also equal those of the reproduction at `1252c45`: 109 of 109 documents on each side, in both modes.

## Recent filings corpus (70 documents)

Each result equals the first run's (`../2026-10-06-recent-filings-corpus/`), apart from timings and paths.

- **Strict:**
  - `main` passes 122 cases and fails 18; so does the candidate.
  - 0 new failures. The same 18 pre-existing failures remain: the cover-page telephone numbers, which PR #7 fixes separately.
- **Prevalence:** `sub_label_currency` 2/2/2/2, as recorded, and every other detector 0. Phase A is 0 for every detector.
- **Acceptance (`--corpus recent`):**
  - 0 alignment identities lost, 2,119 gained.
  - Sections: 560 of 560 identical.
  - XLSX: the same 42 `display_page` changes. PR #8 removes them.
  - 15 result files are byte-identical; the rest differ only in timing, path or gzip fields.

## Overhead (7 fixtures, normal mode, checks on, 9 runs, each in its own process)

Median of the run totals: `main` 4.4054 s, candidate 4.7553 s, ratio **1.0794**. The limit is 1.10. PR #6 measured 1.0904.

The controller ran this on its own after the corpus runs. An earlier agent may have still had background work running, which would affect both sides alike.

## Tests

- Full suite on the candidate: 1881 passed, 14 deselected, and `ruff check src tests` passes.
- Revision 18 adds:
  - Task 1 (C1): 41 tests;
  - Task 2 (C2): 168 tests;
  - Task 3: 12 review pins.
- Each Task 3 pin fails under the mutant it targets.
- A fuzz run of 15,000 tables (C1) found 0 values lost against `1252c45`, and every table without an outside-cell nested table is byte-identical.
