# Table merge and header rules: acceptance run (prototype, round 5)

Date: 2026-10-06. Spec revision 14. Earlier rounds: `REPORT.md` and `REPORT-round2.md` to `REPORT-round4.md`, with result files prefixed `round1-` to `round4-`. Deltas from round 4: `round5_deltas.json`.

- **Baseline:** `c674828`, the same archive as before. It was re-checked file by file (33 files identical), and main's dumps are identical to round 4's on 109 of 109 documents.
- **Candidate:** `proto/table-merge-header` at `9703b9c`, worktree clean.
- **Population:** the Phase A corpus, 109 documents; the hash check passes for 109 of 109 and for 18 of 18 EDGAR files.
- **Modes:** normal and capture, checks on.
- **What changed since round 4:** revision 14's complete number (one currency marker, thousands in groups of three, one `%`), `judge`'s global early stop, new tests, release text, and an independent rule check that now applies the tightened complete-number definition.
- **Corpus effect:** 3 tables in 2 documents. All three change because of footnote-reference cells such as "1,2" that the old pattern read as numbers.

## Stop conditions

None. The open items are the documented residuals: S3, S5, class 8, F9–F11, and the 45 listed source-grid fusions.

## Summary

| # | Criterion | Verdict | Round 4 → round 5 |
|---|---|---|---|
| 1 | Check 1 | MET | Identical (305 → 13; furniture 573 unchanged). |
| 2 | Other findings | MET | Identical (F9, F10, F11). |
| 3 | Strict | MET | Identical (0 new, 0 misses). |
| 4 | Sections | MET | Identical (872/872). |
| 5 | XLSX | NEEDS REVIEW (S3) | Identical. |
| 6 | Modes | MET | Identical (109/109). |
| 7 | Alignment | MET | Candidate evaluated 52,955 → 52,954, all aligned; misaligned 0; lost 0; gained 3,299 → 3,295; values listed 99,097 → 99,084. |
| 8 | Assignment audit | MET | 6,616/6,616. |
| 9 | Header retention | MET | Values 54,986/54,990, misses MSFT 69 only (round 4: 54,987/54,991). Header cells 19,591 → 19,594, all represented. Header-only columns 733/733. |
| 10 | Known shifted tables | MET | Identical (34/34). |
| 11 | Class 8 | NEEDS REVIEW (allowed) | Identical (75/80). |
| 12 | Named limitations | MET | Identical. |
| 13 | Review sample | MET apart from S5 | The 42 tables render identically to round 4: 35 correct, 6 with a note, 1 wrong (MSFT 69). |
| 14 | Overhead | MET | 1.086 → 1.090 (a repeat measurement gave 1.085). |
| 15 | Moved rows | MET | Identical: 2,270 rows; 0 rule failures; 45 sparse-row-only rows (the accepted list). |
| — | Fixture body-row guard | MET (suite) | Unchanged: 172 moves. |

## Every change from round 4

Main's dumps are identical. Two candidate documents differ: KO 10-K and CAT 10-K. Every changed per-value identity is in KO unit 14 or CAT units 37 and 39.

1. **KO 10-K unit 14: rendering changed, in both modes.**
   - Source: row 1 `| Percent Change 2024 versus 2023 [span] |`; row 2 `| Unit Cases | 1,2 | Concentrate Sales |`, where "1,2" are footnote references; then data rows such as `Worldwide | 1 % | | 1 % | 4`.
   - Main: `|  | Percent Change 2024 versus 2023 — Unit Cases | 1,2 | Concentrate Sales |  |`.
   - Round 4: header `|  | Percent Change 2024 versus 2023 | Percent Change 2024 versus 2023 | Percent Change 2024 versus 2023 |  |`, with `|  | Unit Cases | 1,2 | Concentrate Sales |  |` as the first body row. Round 4 read "1,2" as a number, which made row 2 a data row.
   - Round 5: `|  | Percent Change 2024 versus 2023 — Unit Cases | Percent Change 2024 versus 2023 — 1,2 | Percent Change 2024 versus 2023 — Concentrate Sales |  |`, with the same body rows as main.
   - **Verdict: correct.** Round 4 was worse than main here. The row was one of round 4's 178 "data rows main swallowed", which are now 177.
   - Main's alignment of KO 14: 3 values move from ambiguous-header to aligned. Strict and check 1 are unchanged.
2. **CAT 10-K units 37 and 39: alignment coverage only; rendering identical.**
   - The consolidating-adjustment footnote columns hold "1,2" (unit 37, rows 8 and 16), "6,7" (row 29), "4,8" (row 34), "2,3" (unit 39, row 17) and "1,5" (row 6). Each sits at two columns.
   - These 12 cells were values skipped as ambiguous-position or no-discriminating-header. They are no longer values.
   - The rows stay data rows through their amounts.
   - **Verdict: correct.**

## Deltas, criterion by criterion

- **Unchanged result files.** check1, findings, strict, sections, xlsx, xlsx_detail, modes, class8, limitations, alignment_losses, moved_rows, shifted_tables and review_sample.txt are identical to round 4's. assignment and run_check differ only in timing.
- **Alignment coverage.**

  | | Main | Candidate |
  |---|---|---|
  | `values_total` | 65,986 → 65,974 | 66,065 → 66,052 |
  | `value_no_discriminating_header` | 2,057 → 2,051 | 2,088 → 2,082 |
  | `value_ambiguous_position` | 5,121 → 5,115 | 5,137 → 5,131 |
  | `value_ambiguous_header` | 3,267 → 3,264 | 0 |
  | `values_aligned` | 26,606 → 26,609 | 52,955 → 52,954 |
  | `rows_data` | 28,298 → 28,297 | 28,298 → 28,297 |

  The other keys are unchanged; `rows_paired` is 19,777 → 19,776 on the candidate. The budget is still 0 in both runs, so the global early stop changes no corpus verdict.
- **Departures.** 220 → 219 rows; data rows 178 → 177 (KO 14). Non-data departures are unchanged: 42 rows, 18 of them with value-column text.
- **Independent rule check.** It now uses revision 14's complete number, written in `analyze_candidate.py` with its own currency list. It agrees with the spec's examples and with the 14 newly rejected strings. Moved rows: 0 failures, identical to round 4.

## 14. Overhead

Median of 9 runs per side, separate processes, run alone; `get_pages` only.

| Fixture | Main (s) | Candidate (s) | Ratio | Round 4 |
|---|---|---|---|---|
| aapl-2023-10k | 0.7393 | 0.8130 | 1.100 | 1.097 |
| nvda-2002-10k | 1.5574 | 1.6401 | 1.053 | 1.043 |
| nvda-2026-08-26-8k | 0.0165 | 0.0176 | 1.067 | 1.085 |
| nvda-2026-10k | 0.9000 | 1.0327 | 1.147 | 1.162 |
| nvda-2026-ex99-1 | 0.2067 | 0.2752 | 1.331 | 1.344 |
| nvda-2026-ex99-2 | 0.2063 | 0.1664 | 0.807 | 0.778 |
| nvda-2026-q2-10q | 0.6815 | 0.7493 | 1.100 | 1.093 |
| **Total** | **4.3077** | **4.6943** | **1.090** | 1.086 |

- The median of run totals gives 1.088.
- No run outlier.
- Untimed construction: 1.2774 s on main, 1.2733 s on the candidate.
- A repeat 9-run measurement right after gave 1.085 (median of run totals 1.076). The change from round 4 is within run-to-run variation.

**Verdict: MET.**

## Code changes (round 5)

Written test first and folded into the owning commits. The autosquash had no conflicts, and the tree is identical before and after (`3aa815dd…`).

SHAs: T1 `bd43897`, T2 `7be36c4`, T3 `ad8a9c1`, T4 `a8012b9`, T5 `73a2cf9`, T6 `a3ec603`, T7 `77e3023`, T8 `1dcf4ad`, T9 `8f4991e`, T10 `9703b9c`. Full suite at `9703b9c`: 1604 passed, 14 deselected; ruff clean. Each commit's failure list is identical to round 4's.

- **T1.** `_NUMBER` takes thousands in groups of three or plain digits. `_STANDALONE` takes one currency marker (before or inside the parentheses), optional parentheses and sign, and one `%` (inside or after the parentheses). The split-negative pieces share `_NUMBER`. 14 rejected strings, 17 kept forms and a split-negative test are pinned; no existing test changed.
- **T9.**
  - `judge` stops as soon as both verdicts have been seen anywhere; the now-unreachable per-frame branches are removed.
  - Probe case: 15 siblings take 17,991 → 10,269 states. 19 siblings went from budget (170,625 states) to ambiguous at 97,250, under the 100,000 bound.
  - A differential check of 20,000 random cases against the round-4 judge found no verdict change, and the new judge never used more states.
  - New tests: the header-retention audit on the 6 matching controls, with a suppression case and two loss cases; and `header_row_count` next to R0 on 6 named shapes.
- **T10.** Release text: marker-only columns are left out of the fusion count, and equal header texts compare ignoring case and spacing.
