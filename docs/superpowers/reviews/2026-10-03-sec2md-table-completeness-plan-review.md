# Review: sec2md Table Completeness Check Implementation Plan

- **Plan:** `../plans/2026-10-03-sec2md-table-completeness-check.md`
- **Spec:** `../specs/2026-10-02-sec2md-table-completeness-check-design.md` (revision 6)
- **Reviewer:** Astra
- **Round 1:** reviewed the first draft (2026-10-03); resolved in the revised plan the same day

Each finding was reproduced on the scratch implementation the plan was built from. The
fixes were then made there, and the plan's code was taken from the fixed version and
re-run:

- **Full suite:** 790 tests passed, 594 of them the existing suite.
- **Ruff:** passes.
- **Finding parity:** 0 mismatches against the v6 prototype on all 27 documents, in both modes.
- **Header-row parity:** 0 mismatches.

# Round 1 (first draft)

## Findings and resolutions

### 1. [P2] Header optimization introduces false structure findings

**Finding.** Header rows were counted only when a table had missing values or year-only
rows. An unchanged table with `<th>` headings `Denomination | €1 | €2` above
`Issued | 2 | 1` reported "values out of order" in both modes, while v6 reports nothing.

**Verified.** Reproduced in normal and capture mode.
- **The rule's wrong premise:** `_header_count()` stops at the first row holding a number. The shortcut assumed the same rule decides what counts as a number.
- **Why that fails:** `_header_count()`'s number pattern does not accept a leading `€`, so the `<th>` row is a header row.
- **What happened:** with header rows assumed to be 0, that header row became a check-2 data row. Its values `1, 2` then appeared reversed against `2, 1`.

**Resolution.** Header rows are now computed for every table that contains digits, exactly
as v6 does. To limit the cost, header-cell text and the numeric-fact flag are computed
only when `_header_count()` reads them. Regression tests:

- `test_check_tables_excludes_header_rows_from_row_structure` (Task 5);
- the review case "<th> header row with euro amounts, output unchanged", in both modes (Task 6).

Both fail on the first draft and pass on the revision.

### 2. [P2] The performance baseline includes new overhead even with checks disabled

**Finding.** Task 6 added an `_effective_rows()` traversal at the table site for every
table, even with the checks off. The on/off benchmark therefore missed part of the
feature's cost.

**Verified.** On the AAPL fixture, `main` calls `_effective_rows()` 66 times. The first draft
called it 132 times, with the checks off or on.

**Resolution.**
- **Guard:** the table site does metadata work only when capture or the checks need it.
- **Reuse:** when it does, it keeps the rows it computed in `_root_table_rows`, and `_render_table()` uses them.
- **Result:** every configuration now traverses each table once. That is 66 calls on AAPL, as on `main`; in capture mode it is fewer than `main`'s.
- **Regression test:** `test_effective_rows_runs_once_per_table`, over capture and checks on and off (Task 6).

Overhead is now measured against an unchanged `main` checkout, each side in its own
process: `prototypes/v6/overhead_vs_main.py`. `parity_impl.py` no longer times anything.
With both fixes applied:

| Fixture | Overhead |
|---|---|
| AAPL 10-K | +24.0% |
| NVDA 10-K | +20.1% |
| NVDA 2002 10-K | +18.5% |
| NVDA 10-Q | +21.9% |
| NVDA 8-K | +15.1% |
| EX-99.1 | +23.4% |
| EX-99.2 | +23.0% |
| **Total** | **+20.6%** |

**Decision (user, 2026-10-03).** Parse-time overhead of up to +25% against unchanged `main`
on the fixtures is accepted for Phase A, and the 10% target moves to Phase B. This settles
O1 and the target part of this finding. The plan's Task 11 records the decision in the spec.

### 3. [P2] Required corpus validation moves outside the implementation plan

**Finding.** The draft deferred the ≥50-filing corpus run and the D3 measurement until after
merge. The reviewed design puts both in Phase A.

**Verified.** Spec, "Policy and rollout", Phase A, and decision D3.

**Resolution (scope chosen by the user).** New Task 11 runs the corpus before Phase A can be
called complete.

- **The corpus:**
  - the 7 fixtures;
  - 32 RCQ primaries, with 2 more skipped as the same filings as fixtures;
  - 52 RCQ exhibits;
  - 16 EDGAR filings from new issuers.

  That makes 107 documents and 53 distinct filings.
- **The task classifies:**
  - every new finding, as a genuine loss or a false positive;
  - false positives, resolved either as implementation defects (fixed test-first) or as definition cases left for decision;
  - a D3 sample of 30 tables flagged only by words.

  It records all of this in the spec.
- **The tooling,** on `main` in `../audits/2026-10-03-table-completeness-corpus/`:
  - `fetch_edgar.py`, which needs the user's approval and User-Agent when it runs;
  - `corpus_phase_a.py`.
- **An offline preview** over the 91 documents available without the network is quoted in Task 11. Two newly flagged exhibit tables were inspected, and both are genuine renderer losses.

## Before and after the round 1 fixes

The user asked for before/after runs. The draft code and the fixed code were compared on
the same measures:

| Measure | Draft | Fixed |
|---|---|---|
| Regression tests (7) | all fail | all pass |
| `_effective_rows()` calls on AAPL, checks off (`main`: 66) | 132 | 66 |
| Findings on the 91-document corpus (2,131 tables) | identical | identical (0 tables differ) |
| Overhead against unchanged `main`, 7 fixtures in total | +19.6% | +19.5% |
| Accuracy suite against `main` (words, numbers, financial rows; Markdown and page hashes) | not run | identical on all 7 fixtures |

The header fix changes no finding in this corpus: it prevents false alarms like the
`€1 | €2` case, which the corpus does not contain. The two cost changes cancel out. Not
re-scanning table rows saves about what computing header rows for every table adds.

The content comparison is now a plan step: Task 12, Step 6, `prototypes/v6/accuracy_vs_main.py`.
