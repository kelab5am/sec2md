# Table merge and header rules: acceptance run (prototype, round 4)

Date: 2026-10-06. Spec revision 13, "Acceptance criteria". Earlier rounds: `REPORT.md`, `REPORT-round2.md`, `REPORT-round3.md` (result files prefixed `round1-`, `round2-`, `round3-`). How to rerun: `README.md`. Deltas: `round4_deltas.json`.

- **Baseline:** `c674828`, the same `git archive` tree as before. It was re-checked file by file (33 files identical), and `sec2md.__file__` pointed at it in every run. Main's dumps are identical to round 3's on 109 of 109 documents.
- **Candidate:** `proto/table-merge-header` at `ddfcaa9`, worktree clean.
- **Population:** the Phase A corpus, 109 documents. The hash check passes for 109 of 109, and for the 18 EDGAR files against the manifest.
- **Modes:** normal and capture, checks on.
- **What changed since round 3:** S9's P1 in R0. The sparse-row fusion's n and both rows' counts leave out marker-only columns. Exactly 2 tables change, both in both modes: AMZN 10-Q 2025-10-31 table 21 and JPM 10-K table 207. Nothing else changed.

## Stop conditions

None new. The open items are the documented residuals: S3 (XLSX display page), S5 (MSFT 69), class 8 (5 TSM tables), F9–F11 (check-side), and the 45 listed source-grid fusions.

## Summary

| # | Criterion | Verdict | Round 3 → round 4 |
|---|---|---|---|
| 1 | Check 1 | MET | Identical: `TableParser` value failures 305 → 13 (12 Phase A false positives + TSM 344, F9); 294 class-1 tables fixed; page furniture 573 unchanged. |
| 2 | Other findings | MET | Identical: F9 (TSM 344), F10 (15 tables), F11 (BAC 260, 293, 336, 338); tables with findings 937 → 633. |
| 3 | Strict | MET | Identical: 0 new failures, 0 misses. |
| 4 | Sections | MET | Identical: 872/872. |
| 5 | XLSX | NEEDS REVIEW (S3) | Identical; `xlsx_detail.json` byte-identical. |
| 6 | Modes | MET | Identical: 109/109. |
| 7 | Alignment | MET | Candidate evaluated 52,937 → 52,955, all aligned; misaligned 0; lost 0; gained 3,299; identities hold. |
| 8 | Assignment audit | MET | 6,616/6,616 (identical apart from timing). |
| 9 | Header retention | MET | Values 54,987/54,991 (MSFT 69 only, the documented residual). Header cells 19,590 → 19,591, all represented. Header-only columns 733/733. |
| 10 | Known shifted tables | MET | Identical: 34/34. |
| 11 | Class 8 | NEEDS REVIEW (allowed) | Identical: 75/80. |
| 12 | Named limitations | MET | Identical. |
| 13 | Review sample | MET, apart from the documented S5 residual (round 3: NOT MET) | 42 tables: 33 → 35 correct, 5 → 6 with a note, 4 → 1 wrong (MSFT 69, S5). |
| 14 | Overhead | MET | 1.081 → 1.086 (median of run totals 1.082). |
| 15 | Moved rows | MET (round 3: NOT MET) | 2,271 → 2,270 rows; 0 rule failures. AMZN 21 is gone. The 45 sparse-row-only rows are the spec's accepted list. |
| — | Fixture body-row guard | MET (suite) | 172 listed moves, unchanged. |

## Deltas, criterion by criterion

- **Unchanged result files.** check1, findings, strict, sections, xlsx, xlsx_detail, modes, class8, limitations, alignment_losses and shifted_tables are identical to round 3's. assignment and run_check differ only in timing fields.
- **Changed result files.** summary, alignment, retention, moved_rows and header_departures. Every per-value identity that changed belongs to AMZN 21 or JPM 207.
- **Alignment (7).**

  | | Main | Candidate |
  |---|---|---|
  | `value_no_discriminating_header` | 2,075 → 2,057 | 2,106 → 2,088 |
  | `values_evaluated` | 49,638 → 49,656 | 52,937 → 52,955 |
  | `values_aligned` | 26,584 → 26,606 | 52,937 → 52,955 |
  | `values_misaligned` | 23,054 → 23,050 | 0 |

  JPM 207's 18 values now sit under date headings that discriminate. Evaluated on main but not on the candidate: 0. Findings: 0.
- **Retention (9).** Header cells 19,590 → 19,591: JPM 207 gains 4 header-zone cells and AMZN 21 loses 3. Word-only values 7,328 → 7,310. Value misses: 4, all MSFT 69.
- **Moved rows (15).**
  - 2,271 → 2,270 rows; 1,610 → 1,609 tables; 0 new.
  - The one row gone is AMZN 21 row 2 ("operating leases | 10.6 years | 10.0 years").
  - Independent rule check: 0 failures. It now implements P1 in `analyze_candidate.py`, with its own copy of the spec's currency list plus `%`, `)`, `)%` and `(`.
  - Reason counts: sparse-row fusion 115 → 113.
  - Sparse-row-only rows: 46 → 45. They are 43 NVDA unit-caption rows, NTRA 123 and TSM 216, the spec's accepted list.
  - Signals: values with units 6 → 5. The 5 left are round 2's column headings ("Less than 12 months | 12 months or more"). Links 14, unchanged. Words in value cells 501 → 500.
- **Rows leaving main's header line.**
  - 221 → 220 rows; 215 → 214 tables.
  - Non-data rows with value-column text: 19 → 18 rows, 18 → 17 tables. JPM 207 is gone.
  - Of round 2's 82 S8 rows: 63 (was 62) are header rows again. 18 still leave main's header line, and all are R5 cases: 16 rows in 15 tables with no data row, plus CAT 4 and UNH 4, whose first row is a data row. UNH 20 row 8 (a repeated heading) is no longer listed.
  - Zone cuts 88 → 87, none by a label-only row and none inconsistent.
- **Fixture guard.** The suite's guard asserts that the lost counts equal the listed moves exactly. It passes unchanged with 172 moves; no fixture table changed.

## 13. Review sample

The same 42 tables as round 3. Tables 1–39 render exactly as in round 3 and keep its verdicts: 33 correct, 5 with a note, and MSFT 69 wrong (S5). The three S9 tables were re-judged:

| # | Table | Verdict |
|---|---|---|
| 40 | AMZN 10-Q 2025-10-31 t21 | Correct (round 3: wrong, S9). It is identical to main: `\|  \| December 31, 2024 \| September 30, 2025 \|`, with the lease-term rows in the body. |
| 41 | TSM 216 | Note: the spec's accepted source-grid fusion (list item (b) with item (a); no value lost). |
| 42 | JPM 207 | Correct (round 3: worse than main). `\| Average amount (in millions) \| Three months ended — December 31, 2024 \| Three months ended — September 30, 2024 \| Three months ended — December 31, 2023 \|` over the HQLA rows, with every value in its period column. |

Totals: 35 correct, 6 with a note, 1 wrong (MSFT 69, the documented S5 residual).

**Verdict: MET apart from the documented residual.**

## 14. Overhead

Median of 9 runs per side, one process per run, alternating which side runs first, run alone; `get_pages` time only.

| Fixture | Main (s) | Candidate (s) | Ratio | Round 3 |
|---|---|---|---|---|
| aapl-2023-10k | 0.7476 | 0.8200 | 1.097 | 1.090 |
| nvda-2002-10k | 1.5914 | 1.6593 | 1.043 | 1.037 |
| nvda-2026-08-26-8k | 0.0165 | 0.0179 | 1.085 | 1.085 |
| nvda-2026-10k | 0.9121 | 1.0602 | 1.162 | 1.148 |
| nvda-2026-ex99-1 | 0.2089 | 0.2807 | 1.344 | 1.329 |
| nvda-2026-ex99-2 | 0.2156 | 0.1677 | 0.778 | 0.798 |
| nvda-2026-q2-10q | 0.6933 | 0.7576 | 1.093 | 1.096 |
| **Total** | **4.3854** | **4.7634** | **1.086** | 1.081 |

- The median of run totals gives 1.082.
- One run outlier: ex99-2, candidate run 4, at 0.201 s against a 0.168 s median.
- Untimed construction: 1.2943 s on main, 1.3005 s on the candidate.
- The ex99-1 per-fixture ratio is explained in round 3. P1 runs only for a second row that no per-row rule keeps, so it adds no measurable cost.

**Verdict: MET.**

## Spec note

Revision 13 says "The corpus has 46 such rows. 43 are NVDA …, NTRA 123 …, TSM 216 …", but 43 + 1 + 1 = 45. Round 3's 46 included AMZN 21, which P1 removes. The accepted list on the corpus is 45 rows.

## Code changes (round 4)

T1 and T5 fixups, written test first. The autosquash rebase had no conflicts, and the tree is identical before and after (`efda670c…`).

New SHAs: T1 `cb2291e`, T2 `13f88f0`, T3 `70d4c1e`, T4 `e3a84d2`, T5 `def17ce`, T6 `7edff64`, T7 `06e9055`, T8 `543be31`, T9 `28298ff`, T10 `ddfcaa9`. Full suite at `ddfcaa9`: 1556 passed, 14 deselected; ruff clean. Each commit's failure list is identical to round 3's.

- **T1.** `fuses_like_main(grid)` and the code `row_roles` calls leave out marker-only columns. Marker texts are compared without spaces. Role tests: the S9 reproduction, the JPM 207 shape, the `$`-column control, and 15 grid-form predicate cases.
- **T5.** Three rendering cases.
- **T9, T10.** No pin or listed move changed.
