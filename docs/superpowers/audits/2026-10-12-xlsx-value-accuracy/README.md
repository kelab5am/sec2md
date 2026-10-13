# XLSX value accuracy: acceptance record

This records the acceptance run for:
- the XLSX value accuracy spec ([`../../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md`](../../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md), revision 2, "Acceptance" items 3–8);
- Task 6 of its plan ([`../../plans/2026-10-12-sec2md-xlsx-value-accuracy.md`](../../plans/2026-10-12-sec2md-xlsx-value-accuracy.md)).

**Inputs:**
- **Candidate:** branch `fix/xlsx-value-accuracy` at **`be2afea`**, its final commit, in the worktree `.worktrees/xlsx-value-accuracy`.
- **Runs:** this is the sixth acceptance run.
  - The first run, on `7484006`, was blocked (below).
  - The second run, on `732544d`, passed every gate, including fix round 1 of the review. The figures below hold for both the second and the third run unless a section marks a difference.
  - The third run, on `ecc5990`, is the rerun after Rulings 21–27. It differs from `732544d` in 13 text cells only ("Final rerun on `ecc5990`" below).
  - The fourth run, on `b7bd072`, came after Rulings 28–30. Its export is byte-identical to `ecc5990`'s ("Final acceptance on `b7bd072`" below).
  - The fifth run, on `39a71d2`, came after Ruling 31. Its export is byte-identical to `b7bd072`'s ("Acceptance on `39a71d2`" below).
  - The sixth run, on `be2afea`, is the acceptance after Rulings 32 and 33. Its export is byte-identical to `39a71d2`'s ("Acceptance on `be2afea`" below).
- **Baseline:** `outputs/xlsx-value-accuracy/base`. It is `main`'s `src` exported by Task 1; `src` on `main` is unchanged since `1c0ac51`.
- **Manifest:** [`manifest.json`](manifest.json), with 4,048 entries built from that baseline by [`manifest.py`](manifest.py).
- **Corpus:** the 60 filings of the header-detection audit (`../2026-10-11-xlsx-header-detection/filings.txt`).
  - 42 vault filings: 18 META, 14 NVDA and 10 RDDT.
  - 18 other filings.
  - 3,702 tables on each side.
- **Run date:** 2026-10-13.

The decisions this record judges by:
- the spec's Rule P and Rule I;
- the rulings and user decisions of the plan's ledger, Rulings 3–27 and the user decisions of 2026-10-13 (footnote marks and the TSM split-`%` fix). They are committed verbatim in [`rulings.md`](rulings.md) and restated in the spec's "Revision 3: amendments during implementation".

## First run on `7484006`: blocked, then fixed

The first acceptance run exported the branch at `7484006`. It failed the disposition gate (Acceptance 3) on **31 `percent_row_split` cells in TSM 20-F #8–#12**. They were still unflagged numbers in percentage points.

- **Example, TSM #8 `Net revenue | 100.0 | % | 100.0 | % | 100.0 %`.** The 2022 and 2023 columns exported the number `100.0`, while 2024 exported `1.000`.
- **Cause: Ruling 5.** The ruling refused a `%` whose leaf heading differs from the value's. TSM's markers sit under the spanning `For the year ended December 31,`, not under the year cells. Nothing else proved or flagged the values.

The user decided the fix (user decision of 2026-10-13 and Rulings 13–18a in [`rulings.md`](rulings.md)). The branch implements it in `bcdfe4f`, `dc53e06`, `1466b39`, `ad816e0` and `732544d`.
- **When a split `%` attaches:** it may attach through a heading that spans its value's column, but only when:
  - it sits directly beside the value (Ruling 16);
  - its columns hold nothing else in any other body row, with `)` / `%)` fragments and unit-caption rows aside (Rulings 18, 18a).
- **Safety net:** any value whose marker is refused becomes text with the P4 reason (Ruling 13), whatever its other proofs. A zero still converts, and a token the converter rejects keeps the converter's reason.

The earlier exports are kept as `outputs/xlsx-value-accuracy/new-7484006`, `new-732544d`, `new-ecc5990`, `new-b7bd072` and `new-39a71d2` (all git-ignored).

## Acceptance on `be2afea` (Rulings 32 and 33)

**The rulings.**
- **Ruling 32** replaces the currency keep-value exception of Rulings 29–31. Under a table-wide percent declaration, any currency symbol anywhere in a row or header label makes the cell conflict text, and no currency label keeps a displayed value there. Word units (`_ROW_UNIT`: `per share`, `dollars` …) keep spec P3, and nothing changes outside table-wide declarations.
- **Ruling 33** completes it. The 21 listed ISO 4217 codes (USD, EUR, GBP, JPY, CNY, RMB, TWD, NTD, HKD, CHF, CAD, AUD, INR, KRW, SGD, BRL, MXN, SEK, NOK, DKK, ZAR) count as currencies too, as whole, case-sensitive, upper-case words. `CEO`, `EPS` and `USDA` do not.

**The export.** `be2afea`'s `src` was exported into `outputs/xlsx-value-accuracy/new`, with 60 JSONs and 3,702 tables.
- It ran from 13:12:53 to 13:24:17, 11m23s, at Idle priority with 3 workers, and exited 0. No other export was running, and none of its processes were left.
- **It is byte-identical to the `39a71d2` export in all 60 files.** `rerun_diff.py new-39a71d2 new` finds 0 tables and 0 cells that differ.

**Gates.** Every gate was rerun and passes, the all-cells sweep included.
- The `dispositions.py` and `changes.py` logs are identical to the `39a71d2` run's.
- The primary-statement details are identical to base.
- `unmodelled_scan.py` again finds 0 / 0 / 0.
- The four mutation tests fail as before.

**Rulings 32 and 33 in the checker.** They are encoded from the spec's text, and they replace the checker's Rulings 29–31 currency encoding: the unit-position and closing-token reading and Ruling 31's amount test are removed.
- **The rule:** under an in-table table-wide caption, a row or header label holding a currency is a conflict. A currency is a symbol (`$`, `€`, `£`, `¥`, so `US$`, `NT$`, `HK$` too) anywhere in the label, or one of the 21 codes as a whole upper-case word. No currency label is a non-percent unit any longer, and `_ROW_UNIT` words keep P3.
- **Affected cells: none.**
  - The corpus has no in-table table-wide caption.
  - On all 42,395 distinct corpus labels the checker's currency test equals the branch's `_CURRENCY_MARK`: 541 labels hold a currency on both sides, with 0 disagreements. 27 of those labels hold only an ISO code, such as `(in millions of RMB)` and `Average Price Paid per Share in DKK (b)`.

**The glued-scale difference is resolved.** In the `39a71d2` run the checker and the branch read `Loans 5m $`, `Bonds 500mm US$` and `Notes 2bn €` differently (see "Acceptance on `39a71d2`"). Ruling 32 no longer tells a currency unit from an amount, so both now read every one of these labels as a currency, and under a table-wide caption the cell is conflict text.

## Acceptance on `39a71d2` (Ruling 31)

**Ruling 31 (amends Ruling 30).** A closing currency token that directly follows a digit or a scale word (`thousand(s)`, `million(s)`, `billion(s)`, `trillion(s)`, `bn`, `m`, `mm`, `k`), optionally after whitespace, is an amount, not a unit position. Examples are `3.8 billion $` and `Bonds of 500 million €`. Under a table-wide declaration such a cell is conflict text, while `Price, US$` and `Notes due 2030, $` keep their displayed value.

**The export.** `39a71d2`'s `src` was exported into `outputs/xlsx-value-accuracy/new`, with 60 JSONs and 3,702 tables.
- It ran from 12:41:05 to 12:52:27, 11m22s, at Idle priority with 3 workers, and exited 0. No other export was running, and none of its processes were left.
- **It is byte-identical to the `b7bd072` export in all 60 files.** `rerun_diff.py new-b7bd072 new` finds 0 tables and 0 cells that differ.

**Gates.** Every gate was rerun and passes, the all-cells sweep included.
- The `dispositions.py` and `changes.py` logs are identical to the `b7bd072` run's.
- The primary-statement details are identical to base.
- `unmodelled_scan.py` again finds 0 / 0 / 0.
- The four mutation tests fail as before.

**Ruling 31 in the checker.** It is encoded from the spec's text.
- **The rule:** a closing currency token directly after a digit or a scale word, whitespace allowed, is no unit position. The label's currency symbol then counts as "elsewhere", which under a table-wide caption is a conflict.
- **Affected cells: none.** The corpus has no in-table table-wide caption. On all 514 distinct corpus labels holding a currency symbol, the checker's reading (unit position, or elsewhere) equals the branch's.
- **One edge differed on constructed probes (resolved by Ruling 32, see "Acceptance on `be2afea`").** The checker reads the ruling's "a scale word" literally, so a scale word glued to its number counts too: in `Loans 5m $`, `Bonds 500mm US$` and `Notes 2bn €` the token is an amount, so under a table-wide caption these are conflict text. The branch's pattern needs a word boundary before the scale word, so it reads those three as unit positions and keeps the displayed value. No corpus label has this shape. Under an in-table caption the difference would fail the gates rather than pass, since the checker would expect conflict text where the branch keeps a number.

## Final acceptance on `b7bd072` (Rulings 28–30)

Rulings 28–30 ([`rulings.md`](rulings.md); spec Revision 3) followed the `ecc5990` run:
- **Ruling 28:** a sign disagreement between display and fact is not flagged (a known gap).
- **Ruling 29:** under a table-wide declaration a currency label is a local non-percent unit, and a `pp` glued to a number is a points unit, while `PP&E` is not.
- **Ruling 30:** under a table-wide declaration only a unit-position currency symbol keeps the displayed value; any other currency symbol in a label gives conflict text.

**The export.** `b7bd072`'s `src` was exported into `outputs/xlsx-value-accuracy/new`, with 60 JSONs and 3,702 tables.
- It ran from 12:07:59 to 12:19:44, 11m44s, at Idle priority with 3 workers, and exited 0. No other export was running, and none of its processes were left.
- **It is byte-identical to the `ecc5990` export in all 60 files.** `rerun_diff.py new-ecc5990 new` reports 0 tables and 0 cells, and the reviewer's whole-file `deepdiff.py` reports 0 differences.
- So no number, NVDA cell or statement-table cell changed, and there is no cell for a ruling to explain.

**Gates.** Every gate passes on `base` against the new export.

| Gate | Result |
|---|---|
| Dispositions | 0 invalid |
| Split audit | 0 disagreements; Ruling 19: 144 / 144 / 144 |
| Percent facts | 789 equal, 0 differ |
| Primary statements | 126 vault statements with the same OK counts, identical to base |
| Changed cells | 1,764, all as the spec gives; 948 numbers, 0 unproven |
| Axes and removed columns | 0 axis changes; 54 of 54 tables explained |
| Statement tables | 167, untouched |
| `all_facts.py` | 0 new mismatches |
| Stacked-block scans | 0 new hits |
| All-cells sweep (new) | Pass, below |

The `changes.py` log is identical to the `ecc5990` run's.

**Checker changes in this run.** Each was made before the final gate run, and every affected cell is listed.

1. **Rulings 29 and 30, encoded from the spec's text** (their currency part is superseded in the checker by Rulings 32 and 33; see "Acceptance on `be2afea`").
   - Under an in-table table-wide caption, a currency symbol (`$`, `US$`, `NT$`, `€`, `£`, `¥`) in a row or header label in unit position (`($)`, `(in $)`, `(US$ in millions)`, or a closing token such as `Price, US$`) is a non-percent unit.
   - Any other currency symbol there is a conflict, and so is a local percent claim beside any currency label.
   - The corpus has **0 tables with an in-table table-wide caption**, so these rules decide no cell. NVDA's context-line declarations are not in the export JSON; the sweep below holds NVDA's cells to the baseline.
2. **Ruling 29's `pp`.** The checker's vocabulary now counts a bare `pp` only when no letter or `&` stands beside it. `Change 25pp` and `+25pp` count, while `PP&E` does not; `PP & E`, with spaces, still counts, as Ruling 24's known gap says. On all 18,638 distinct corpus labels the checker and the branch now agree on unit naming, percent-named headings and percent declarations: 0 disagreements.
3. **Ruling 28 needs no encoding.** A sign-mismatched fact is no percent-fact proof in the checker either (spec P1.2), and it is not contrary evidence. The displayed token decides, as in the branch.
4. **A precision fix found by the new all-cells sweep (3 cells).** The checker read a token such as `$(1,732)` or `$ (11.0)` held in one source cell as a complete number. The exporter converts `$ (x)` only when the `$` is a standalone fragment origin (the structural join). The checker now requires that. This affects 3 cells, all identical to base and all text with the converter's `Not a complete supported US numeric token`:
   - JPM 10-K #162 [1, 4] `$(1,732)`, under `2023`, label `Foreign exchange derivatives`;
   - JPM 10-K #162 [1, 5] `$(123)`, under `2022`;
   - TSM 20-F #68 [9, 2] `$ (11.0)`, `Financial assets at FVTOCI`.

   The same change makes a non-percent proof over a token the converter rejects expect the converter's own reason; the checker had expected nothing there. This affects 113 cells, all identical to base. The 3 cells above are among them.

**The all-cells sweep (new gate, in `dispositions.py`).** Every digit copy cell of the export (column 0 aside, every table that is not source text), 65,441 cells, manifest entries or not, is held against the checker's expectation:
- **55,711 match it.**
- **9,235 are "today's behaviour".** The checker finds no proof and no percent column, so each must be identical to its baseline cell. Every one is: 5,408 text cells and 3,827 numbers. The checker does not model `main`'s role rules (`Numeric role unresolved`, footnote-marker reasons), so here `main`'s own output is the expectation, and a no-proof cell may not even equal its displayed number unless it is unchanged.
- **495 are NVDA's percent-of-revenue values.** Their table-wide declaration sits in the context lines, which the export JSON does not hold. Each must be an NVDA number equal to the displayed number / 100, identical to base, in a table with no in-table caption, and the gate requires exactly 495, the spec's count.
- **0 mismatches.**

Two mutation tests check the sweep on scratch copies:
- mutation 4 changes NVDA 10-K FY2024 #8 `Cost of revenue 27.3` from 0.273 to 27.3. The sweep reports 1 mismatch, the NVDA count drops to 494, and the gate fails;
- the reviewer's mutation 1 (GOOGL `73,943` made a number) now also fails the sweep, besides `changes.py`.

**The three unmodelled outcomes, measured.** [`unmodelled_scan.py`](unmodelled_scan.py) (adapted from the reviewer's `scan_unmodelled.py`) counts the corpus cells that the three outcomes of Rulings 21–23 the checker does not model could decide, and finds:
- (i) other digit cells of a `$` or amount-fact column under a percent declaration or caption: 0;
- (ii) digit cells under an amount heading with a table-wide caption: 0;
- (iii) `%` / `)%` cells spanning two body rows: 0.

**Vocabulary edges.** The unit vocabularies agree on every corpus label, and differ on 5 of the reviewer's 58 constructed probes:
- **The checker names no unit where the branch does** in `Weighted average months to maturity` (the spec names only `years to maturity`), `Years 1, - 5` and `Months 1.-3` (the checker's bucket exemption reads digits with commas and dots).
- **The checker names a unit where the branch does not** in `Change; years` (the checker also takes `;` as a closing separator) and `Rate (x.)`.

On a cell with a percent claim, either kind of difference would make the checker and the branch disagree, so the gates would fail rather than pass. None occurs in the corpus.

**The 24 KO #12 cells reattributed in the `ecc5990` run.** These were already P4 text in `732544d`, are unchanged since, and are now attributed to the percent-named heading (Ruling 21). Their headers all start `Percent Change 2024 versus 2023 —`.

| Copy cell | Row | Header part | Text | Kind |
|---|---|---|---|---|
| [1, 1] | Europe, Middle East & Africa | Volume1 | `(1)` | changed cell |
| [2, 1] | Latin America | Volume1 | `3` | changed cell |
| [3, 1] | North America | Volume1 | `1` | changed cell |
| [4, 1] | Asia Pacific | Volume1 | `2` | changed cell |
| [5, 1] | Global Ventures | Volume1 | `4` | changed cell |
| [6, 1] | Bottling Investments | Volume1 | `5` | changed cell |
| [1, 2] | Europe, Middle East & Africa | Price, Product & Geographic Mix | `17` | changed cell |
| [2, 2] | Latin America | Price, Product & Geographic Mix | `21` | changed cell |
| [3, 2] | North America | Price, Product & Geographic Mix | `10` | changed cell |
| [4, 2] | Asia Pacific | Price, Product & Geographic Mix | `2` | changed cell |
| [5, 2] | Global Ventures | Price, Product & Geographic Mix | `(3)` | changed cell |
| [6, 2] | Bottling Investments | Price, Product & Geographic Mix | `5` | changed cell |
| [1, 3] | Europe, Middle East & Africa | Foreign Currency Exchange Rate Fluctuations | `(16)` | changed cell |
| [2, 3] | Latin America | Foreign Currency Exchange Rate Fluctuations | `(14)` | changed cell |
| [4, 3] | Asia Pacific | Foreign Currency Exchange Rate Fluctuations | `(3)` | changed cell |
| [5, 3] | Global Ventures | Foreign Currency Exchange Rate Fluctuations | `2` | changed cell |
| [6, 3] | Bottling Investments | Foreign Currency Exchange Rate Fluctuations | `(2)` | changed cell |
| [6, 4] | Bottling Investments | Acquisitions & Divestitures2 | `(28)` | changed cell |
| [1, 5] | Europe, Middle East & Africa | Total | `1` | manifest `percent_row_joined` |
| [2, 5] | Latin America | Total | `11` | manifest `percent_row_joined` |
| [3, 5] | North America | Total | `11` | manifest `percent_row_joined` |
| [4, 5] | Asia Pacific | Total | `2` | manifest `percent_row_joined` |
| [5, 5] | Global Ventures | Total | `2` | manifest `percent_row_joined` |
| [6, 5] | Bottling Investments | Total | `(21)` | manifest `percent_row_joined` |

## Final rerun on `ecc5990` (Rulings 21–27)

The final review added Rulings 21–27 ([`rulings.md`](rulings.md); spec Revision 3).
- **Export.** `ecc5990`'s `src` was exported into `outputs/xlsx-value-accuracy/new`, with 60 JSONs and 3,702 tables.
  - It ran from 11:17:43 to 11:29:28, 11m44s, at Idle priority with 3 workers. No other export was running, and none of the export's processes were left.
  - The export exited 0, and this time the wrapper passes the exit status through.
- **Gates.** Every gate was rerun on `base` against the new export, and every gate passes.
- **Diff against the `732544d` export.** [`rerun_diff.py`](rerun_diff.py) compares `new-732544d` with `new` field by field. It finds:
  - **0 number changes**, 0 text-to-number or number-to-text changes and 0 format changes;
  - **0 NVDA cells** changed, and 0 cells in any statement table;
  - no table whose status, headers or shape changed;
  - 2 tables whose issue lists changed, KO #11 and TSM #139.

  **13 cells differ, all text before and after; only their review reason changed:**

  | Table | Cell (copy row, column), label | Text | `732544d` reason → `ecc5990` reason | Ruling |
  |---|---|---|---|---|
  | KO 10-K #11, header `Percent Change 2024 versus 2023` | [2, 4] Europe, Middle East & Africa | `(1)` | Numeric role unresolved → P4 | 21: a heading naming a percent without declaring one; the cell has no proof of its own |
  | ditto | [3, 1], [3, 4] Latin America | `3`, `3` | Numeric role unresolved → P4 | 21 |
  | ditto | [4, 4] North America | `1` | Numeric role unresolved → P4 | 21 |
  | ditto | [5, 1], [5, 4] Asia Pacific | `1`, `3` | Numeric role unresolved → P4 | 21 |
  | ditto | [6, 1], [6, 4] Global Ventures | `2`, `4` | Numeric role unresolved → P4 | 21 |
  | ditto | [7, 1], [7, 3] Bottling Investments | `(23)`, `3` | Numeric role unresolved → P4 | 21 |
  | ditto | [0, 3], the header row left in the body (`Unit Cases \| 1,2 \| Concentrate Sales`) | `1,2` (footnote marks) | Numeric role unresolved → the converter's `Not a complete supported US numeric token` | 21, with Ruling 9: the converter rejects the token, so its own reason stays |
  | TSM 20-F #139, `Ratio of Shares to be Vested` | [2, 1] `Above the Index by X percentage points` | `50% + X * 2.5%, with the maximum of 100%` | the converter's `Not a complete …` → `Conflicting explicit units` | 26: a percentage-points unit in the row label is contrary evidence to the cell's `%` |
  | ditto | [4, 1] `Below the Index by X percentage points` | `50% - X * 2.5%, with the minimum of 0%` | the converter's `Not a complete …` → `Conflicting explicit units` | 26 |

  **Verification against the source cells.** I checked each cell against its source cells.
  - **KO #11.** The source row 1 heading `Percent Change 2024 versus 2023` spans columns 3–11. The values are the percent changes the filing prints without a `%` on most rows; only `Worldwide 1 | %` carries one, and those two are refused split cells (P4 text already in `732544d`). The cells under the positional `Column 7` (`4`, `5`) keep `Numeric role unresolved`, as the rule gives.
  - **TSM #139.** Its row labels are `Above/Below the Index by X percentage points`. `Equal to the Index | 50%` has no points label and is unchanged (0.50, own `%`).
- **Not every predicted change occurred.** The implementer's read-only scan also predicted that JPM #266 `Series X` would take the conflict reason. It did not change. That row holds no percent claim: its rate cell is `SOFR + 3.33`, converter text, and its amounts carry no `%`. So nothing there is contrary to a claim.

**Disclosure: the checker was updated after this rerun failed.** The first gate run on `ecc5990` passed every gate but one. The changed-cells gate failed on exactly these 13 cells, because `dispositions.py` did not yet know the outcomes of Ruling 21 (percent-named headings) and Rulings 24–27 (points units as contrary evidence). I encoded those rulings from the spec's Revision 3 text. I had already read the branch's diff before writing the unit vocabulary, so that vocabulary follows the same rulings closely and is less independent of the branch than the rest of the checker. The encoded rules are:
- **Contrary facts.** A fact that is neither pure at scale -2 nor an amount fact conflicts with every percent claim, a table-wide caption included.
- **Labels naming another unit.** A row or header label naming another unit (`OTHER_UNIT`: parenthesised, `in`, closing-separator and leading forms, a trailing ` x`, `duration`, `years to maturity`, and any points unit, glued to a number too) conflicts the same way. Period wording is stripped first, and a leading bucket over a digit range is exempt.
- **Covering row label.** The row label is now the source cell covering column 0.
- **Percent-named headings.** Under a heading that names a percent without declaring one, a cell without a proof of its own (own `%` or `$`, a percent fact or an amount fact) is P4 text: the converter's reason if it rejects the token, and a zero converts. Under an identifier heading this ranks below the conflict and points reasons and above I2.

After the update every gate passes. The update has these effects:
- **The 13 cells above** are now as the rules give.
- **6 manifest entries and 18 changed cells are reattributed.** They are in KO #12, under `Percent Change 2024 versus 2023 — …`. They were already P4 text in `732544d` and are unchanged in `ecc5990`, and they are now attributed to the percent-named rule instead of "unproven in a percent column".
- **No other expectation moved.** The disposition and changed-cell counts are otherwise identical to `732544d`'s.

Three outcomes of Rulings 21–23 are not modelled:
- a copy column holding a `$` or amount fact withholding its percent heading and a table-wide declaration;
- an amount heading under a table-wide declaration flagging its unproven cells (Ruling 8 as amended);
- a `%` spanning two rows never joining a value.

If the branch applied one of them to a cell, the gates would fail, because the checker still expects the earlier outcome. If the branch failed to apply one, the gates would not notice. `unmodelled_scan.py` finds 0 corpus cells of the shapes they decide ("Final acceptance on `b7bd072`" above), so neither case arises here. The three mutation tests of fix round 1 still fail on the `ecc5990` export (below).

## Result in one paragraph

Every gate passes on `be2afea`, whose export equals the exports of `39a71d2`, `b7bd072` and `ecc5990` (and passed on `732544d`).
- **Dispositions (Acceptance 3).** All 4,048 manifest entries have a valid disposition:
  - 338 proven percents, each with its proof named;
  - 47 proven quantities;
  - 988 flagged text cells with the expected reason;
  - 2,658 true identifier cells unchanged;
  - 17 non-digit misread cells unchanged.

  No manifest cell is an unflagged number at the wrong scale.
- **Primary statements (Acceptance 4).** The 126 vault primary statements export, with the same verified fact counts (META 3,322, NVDA 2,662, RDDT 2,056) and 0 failures. The whole `primary_statements.py` result is identical to the baseline's.
- **Other changed cells (Acceptance 5).** Every changed cell outside the manifest is classified: 1,764 cells on `ecc5990`, the 1,751 of `732544d` plus the 13 reason changes above, and 164 tables whose status or headers changed. **0 numbers are wrong.**
  - Each of the 12 numbers whose value changed from one number to another was checked individually. Each is a rate proven by its own inline XBRL percent fact.
  - Every one of the 948 numbers in changed cells carries a named proof and sits under its own heading.
  - No cell's header path or row label changed. Each of the 54 header changes only removes a `%` or `pts` column joined into its neighbour.
- **Percent facts (Acceptance 6).** Every cell proven by a percent fact (789) equals the fact / 100 with its sign.
- **Coverage cost (Acceptance 7):** 1,127 numbers became flagged text, in 74 tables. None is in a primary statement.
- **Header-detection checks (Acceptance 8).** `all_facts.py` and the stacked-block scans find nothing new.

## How to rerun

Run from the checkout root (the export JSONs name their filings by paths relative to it), in PowerShell. Every python run goes through `low`, which runs it at Idle priority. `start /b /wait` alone always returns 0, so `& call exit %^errorlevel%` passes the script's own exit status back. The export uses 3 workers; run only one export at a time.

```powershell
Set-Location C:\Users\einstein\kelab5am\sec2md
$PY = '.worktrees\xlsx-export\.venv\Scripts\python.exe'
function low { cmd /c "start `"`" /low /b /wait $PY $args & call exit %^errorlevel%" }
$H = 'docs/superpowers/audits/2026-10-11-xlsx-header-detection'
$A = 'docs/superpowers/audits/2026-10-12-xlsx-value-accuracy'
$O = 'outputs/xlsx-value-accuracy'
$SRC = '.worktrees/xlsx-value-accuracy/src'     # the branch at be2afea
$F = (Get-Content $H/filings.txt) -join ' '   # the 60 filings, one argument string
low -I $H/export_tables.py --src $SRC --out $O/new --workers 3 $F
low -I $A/dispositions.py $O/base $O/new --manifest $A/manifest.json --src $SRC --details $O/dispositions.json > $O/dispositions.log
low -I $H/primary_statements.py $O/base --report $O/statements-base.md --details $O/statements-base.json --workers 3
low -I $H/primary_statements.py $O/new --report $O/statements-new.md --details $O/statements-new.json --workers 3
low -I $H/all_facts.py $O/base --report $O/all-facts-base.md --details $O/all-facts-base.json --workers 3
low -I $H/all_facts.py $O/new --report $O/all-facts-new.md --details $O/all-facts-new.json --workers 3
low -I $A/changes.py $O/base $O/new --manifest $A/manifest.json --src $SRC --details $O/changes.json --statements $O/statements-base.json $O/statements-new.json --all-facts $O/all-facts-base.json $O/all-facts-new.json --stacked-scan $A/stacked_scan.py > $O/changes.log
low -I $A/rerun_diff.py $O/new-39a71d2 $O/new --details $O/rerun-diff.json > $O/rerun-diff.log   # the previous run's export against this one
low -I $A/unmodelled_scan.py $O/new --src $SRC > $O/unmodelled-scan.log
```

| Step | Duration |
|---|---|
| Export, 60 filings | 11m23s on `be2afea` (13:12:53–13:24:17); 11m22s on `39a71d2`; 11m44s on `b7bd072` and on `ecc5990`; 11m12s on `732544d` |
| `dispositions.py` (with the all-cells sweep) | about 18 s |
| `primary_statements.py`, each side | 0.6 s |
| `all_facts.py`, each side | 0.6 s |
| `changes.py` | about 9 s |
| `rerun_diff.py` | about 2 s |

On `ecc5990` every command was run as written above, with the `primary_statements.py` and `all_facts.py` printouts also redirected to logs. Every script exits 0, and two runs of each gave byte-identical JSON and logs.

Notes on the inputs:
- **The stacked-block scan.** [`stacked_scan.py`](stacked_scan.py) is a byte-identical copy (sha256 `563cc154…57808`) of the header-detection audit's gate 6 script, which lives in that audit's git-ignored `outputs/xlsx-header-detection/task-7/`. `changes.py` imports only its `scan_a` and `scan_b`, unchanged. Its `main()` writes into that audit's outputs, so do not run it.
- **Outputs:** all outputs are in `outputs/xlsx-value-accuracy/` (git-ignored), with each script's printout in a `.log` beside its JSON.

### The two scripts

**[`dispositions.py`](dispositions.py)** covers Acceptance 3 and 6.
- **How far it is independent of the branch.** It is not independent of the branch's code as a whole. What it writes again from the spec and the rulings ([`rulings.md`](rulings.md)) are the value-accuracy decisions:
  - proofs, conflicts and percent columns;
  - the attachment rules and the safety net;
  - the dispositions.

  A disagreement with the branch on any of these shows up as a failure.
- **What it takes from the branch.** It shares the following with the branch. A defect in any of them is outside what it can catch on its own.
  - **From the branch's `src`:**
    - the patterns the spec calls today's (`_ROW_UNIT`, `_PERCENT`, `_PERCENT_UNIT`, `_FOOTNOTE_MARK`, `_UNIT_LINE`, `_VALUE`);
    - the header-detection helpers `_identifier_heading`, `_period_row` and `_period_text`, which the branch leaves unchanged;
    - `convert_cell`, for the converter's own review reasons.
  - **From the branch's export:** the headers, the joined copy text and `cell_sources`, which are the evidence it judges.
- **What covers the shared parts.** `changes.py`'s axis gate compares every header path and row label with the baseline. The primary-statement and `all_facts.py` checks verify facts against the headers.
- **What it does:**
  - **Locates each manifest entry.** It finds the copy cell whose `cell_sources` hold the entry's source coordinates. It asserts that coordinates are unique per table on both sides, and they are.
  - **Gathers the proofs.** For each entry it collects the evidence: own `%`, own `$`, percent fact, amount fact, percent header (withheld in shared leaves, Rulings 7, 10 and 11), percent row label, in-table table-wide caption, non-percent unit and conflicts.
  - **Sets the expected outcome and compares.** It derives the expected disposition and compares the value, format and reason.
  - **Audits every split `%` marker** the attachment pass reaches, against the attachment rules.
  - **Lists every percent-fact cell.**
- **Nested facts.** `export_tables.py` loses a fact nested inside another fact, because marking the outer fact clears the inner one. So `dispositions.py` reads each filing's own `ix:nonFraction` tags to restore the count, which matters because Ruling 3 counts a nested fact as a second fact. The corpus holds 1,068 nested facts: META 229, NVDA 118, RDDT 261 and Others 460.

**[`rerun_diff.py`](rerun_diff.py)** compares two exports of the same corpus by the same harness, field by field and cell by cell. A table whose shape changed is compared by value origin. The final rerun uses it to list every `new-732544d` → `new` difference.

**[`changes.py`](changes.py)** covers Acceptance 5, 7 and 8.
- **Matching cells.** It keys every copy cell by its value origin, as the manifest does, and lists each cell whose type, value, original, format or review reason differs from `base`, outside the manifest.
- **Classes.** It classifies each changed cell by a stated rule (below) and checks the new cell against the expectation `dispositions.py` gives for it.
- **Proof for every new number.** Every number in a changed cell must carry a named proof (`dispositions.named_proof`). The proofs are:
  - own `%` or `$`;
  - a percent or amount fact;
  - a percent header or row label;
  - a table-wide caption;
  - a non-percent unit;
  - under an identifier heading, the cell's own quantity proof.

  A number without one fails. A base number that becomes text with no reason also fails.
- **Headings.** It checks that every new number sits under its own heading: its copy column's header must be the header above its value origin's source column.
- **Axes.** Every cell that exists on both sides, changed or not, must keep the baseline's copy-column header path and row label.
  - Where a table's headers changed, the new headers must be the baseline's with removed columns only.
  - A column may be removed only when every non-empty cell in it is a split-percent or points fragment (`%`, `)%`, `)`, `%)`, `pts`, `pt`, `points`) that now sits in a neighbour's copy cell.
- **Statement tables.** Given `primary_statements.py`'s details for both sides, it requires the two to be identical. It also requires the tables they identify as primary statements to hold no differing cell, no status or header change and no axis change.
- **Coverage cost.** It counts the coverage cost.
- **Header-detection checks.** It compares the `all_facts.py` mismatches and the stacked-block scan hits of the two exports.

## Gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Export | **Pass** | `be2afea`: 60 JSONs, 3,702 tables, exit 0, byte-identical to the `39a71d2`, `b7bd072` and `ecc5990` exports. Run at Idle priority with 3 workers; no workers left over. |
| 2. Dispositions (Acc. 3) | **Pass** | 0 of 4,048 entries without a valid disposition. All-cells sweep: 65,441 digit cells, 0 mismatches (55,711 as expected, 9,235 identical to base with no proof, 495 NVDA context-declared). `identifier_true`: 2,658 of 2,658 unchanged in value, type, format and reason. Split-`%` audit: 0 disagreements. |
| 3. Primary statements (Acc. 4) | **Pass** | All 126 vault statements export (META 54, NVDA 42, RDDT 30). OK facts: META 3,322, NVDA 2,662, RDDT 2,056. Failures 0, arithmetic failures 0. `statements-new.json` is identical to `statements-base.json`. |
| 4. Changed cells (Acc. 5) | **Pass** | 1,764 changed cells, all as the spec gives. 0 wrong numbers. 948 numbers in changed cells, 0 without a named proof and 0 outside their own heading. Axes: 0 cells whose header path or row label changed. 54 tables whose headers changed, all only by removed columns. Statement tables: 167 (126 vault), with 0 differing cells, 0 table changes and 0 axis changes. |
| 5. Percent facts (Acc. 6) | **Pass** | 789 numbers equal the fact / 100 with its sign; 0 differ. |
| 6. Coverage and header checks (Acc. 7, 8) | **Pass** | Coverage cost: 1,127 cells in 74 tables, counted per group and table below. `all_facts.py`: 104 mismatches on both sides, 0 new. Stacked-block scan A: 1 and 1 hits, 0 new. Scan B: 9 and 9 hits, 0 new. |

## Dispositions (Acceptance 3)

| Kind | Entries | Disposition | Cells | Proof named |
|---|---|---|---|---|
| `percent_row_joined` | 1,072 | proven percent | 170 | percent fact 109; fact + header 3; header 58 |
| | | text, P4 reason | 902 | 896 unproven in a percent column; 6 under KO #12's percent-named heading `Percent Change 2024 versus 2023 — Total` (Ruling 21) |
| `percent_row_split` | 123 | proven percent | 103 | own % 62; own % + fact 10; own % + header 28; own % + row label 3 |
| | | text, conflict reason | 17 | TSM #9–#11 under `% Change in NT$ from …` (a `$` in the header, Ruling 9) |
| | | text, P4 reason (refused `%`) | 3 | CRDO #25, #26 and KO #54 (Ruling 18: a heading left in the body shares the `%` column) |
| `identifier_misread` | 195 | proven percent | 65 | own % (NVDA `Year-over-Year Change` after attachment) |
| | | proven quantity | 47 | amount fact 10; own `$` 27; own `$` + amount fact 6; own `$` + non-percent unit 4 |
| | | text, `Identifier heading over quantities` | 55 | (another cell of the column proves a quantity) |
| | | text, points reason | 11 | NVDA `pts` cells (Ruling 4) |
| | | unchanged (no digits) | 17 | em dashes, `$ -` nil facts, `(In Millions)` captions |
| `identifier_true` | 2,658 | unchanged | 2,658 | |

**By group:**
- **Joined percent rows:**
  - META: 38 proven, 554 P4 text;
  - RDDT: 28 proven, 266 P4 text;
  - Others: 104 proven, 82 P4 text.
- **Split percent cells:**
  - META 15, NVDA 24 and RDDT 8, all proven;
  - Others: 56 proven, 17 conflict, 3 refused.
  - All 57 TSM split cells are valid: 40 proven and 17 conflict.

No misread column lacks quantity evidence, so the I2 `amount-formatted` reason does not occur in the corpus.

Against the first run, 42 split entries changed:
- 23 TSM cells went from unflagged numbers to proven percents;
- 8 went from unflagged numbers to conflict text;
- 6 proven percents are unchanged in disposition but differ in output;
- 3 went from proven percent to refused P4 text (CRDO #25, #26 and KO #54);
- 2 went from P4 text to proven percents.

### Split `%` markers (user decision of 2026-10-13, Rulings 13–18a)

The attachment pass reaches 2,673 markers.

| Outcome | Markers | What it means |
|---|---|---|
| Joined on `main` too | 2,323 | Column grouping already joined them in the baseline. Unchanged. |
| Attached | 198 | The rules allow it: adjacent, heading the value's or spanning it, and marker-only. META 73, RDDT 4, Others 121. |
| Joined by column grouping under one leaf | 144 | The attachment rules refuse these markers, because another row's value spans the marker's column. But value and marker sit under the same leaf heading, and `_column_groups` merged that leaf's columns, as `main` does whenever every row converts. Spec P4 now lets `(x) %` rows pass that test. META 84, NVDA 46, RDDT 14. Example: META 10-K FY2025 #5 `Operating margin 52 \| %` under `2025`, where `$ 198,759` spans the same columns. See the disclosure below. |
| Refused | 8 | Every one fails the marker-only rule, and every value is P4 text. They are BAC #4 (3), CRDO #25, #26, KO #11 (2) and KO #54. |
| Branch and rules disagree | **0** | |

**Disclosure: the grouping outcome was added after the audit failed.** The first form of the split-`%` audit had no such outcome. On this run it reported these 144 markers as "joined against the rules", so the gate failed.

- **Why the outcome was added.** I investigated and found these joins are not the attachment pass at all. They come from `_column_groups`' same-leaf merge, the pre-existing join mechanism the spec keeps ("`_column_groups` refuses to merge them as today"). That merge now succeeds because spec P4 lets `(x) %` rows convert cleanly. I then added the outcome.
- **Review and Ruling 19.** The task review flagged that this change after a failure was undisclosed. The controller's Ruling 19 keeps the outcome, on two conditions:
  - it is tightened to its exact conditions;
  - it is disclosed, here and in the `dispositions.py` docstring.
- **The exact conditions.** A marker keeps this outcome only when all of these hold; otherwise it is "JOINED AGAINST THE RULES" and the gate fails:
  - the value and the marker share a leaf heading;
  - the value is the only digit origin in its row under that leaf;
  - the joined token is one complete number ending in its own `%`;
  - the cell is a valid proven percent by its own `%`.
- **Independent verification.** The reviewer verified all 144 independently. `dispositions.py` now prints the checks: 144 have one digit origin, 144 have their own `%` and 144 are valid.
- **Mutation test.** Removing the `%` from the META FY2025 #5 `52 %` cell in a scratch copy makes the audit report 1 marker "JOINED AGAINST THE RULES", and the gate fails.

### Percent facts (Acceptance 6)

There are 869 digit cells whose only fact is pure, at scale -2, in a plain format, with digits and sign that agree with the cell.

- **789 numbers.** Each equals the fact's displayed number / 100 with the fact's sign: META 178, NVDA 125, RDDT 46, Others 440. **0 differ.**
- **43 text cells:**
  - **MSFT #50 (40):** conflict, because the row labels hold `$` (`2009 issuance of $3.8 billion`, Ruling 9); this is the same as the baseline;
  - **CRDO #25, #26 and KO #54 (3):** refused split `%`, so P4 text under the literal safety net (Ruling 13).
- **37 cells where a nested fact means there is no proof (Ruling 3):**
  - JPM #279/#280, BABA #48/#73, TSM #139 and UNH #52;
  - those with their own `%` convert by own-`%` proof;
  - JPM's plain `8.5`, `10.5`, `8.0`, `10.0`, `5.0` and `6.0` are P4 text.

## Primary statements (Acceptance 4)

| Group | Statements | Exported | Facts | OK | Failures | Arithmetic |
|---|---|---|---|---|---|---|
| META | 54 | 54 | 3,448 | **3,322** | 0 | 0 |
| NVDA | 42 | 42 | 2,683 | **2,662** | 0 | 0 |
| RDDT | 30 | 30 | 2,228 | **2,056** | 0 | 0 |
| Others | 54 | 29 | 3,242 | 2,099 | 978, as on `main` | 0 |

`statements-new.json` and `statements-base.json` are identical, and so are the two reports. `changes.py`'s statement gate (`--statements`) prints: 167 statement tables (126 vault); details identical; 0 differing cells in them (manifest entries included); 0 status or header changes; 0 axis changes; 0 manifest entries in them.

## Changed cells outside the manifest (Acceptance 5)

There are 1,764 changed cells outside the manifest on `ecc5990`: 1,751 on `732544d` plus the 13 reason changes of the final rerun. Separately, 164 tables changed status or headers (see "Tables" below). Each class below has a stated rule, and `changes.py` checks every cell against the spec's expectation for it: value, format, reason and heading. All 1,764 hold.

| Class | Cells | Rule | Inspection |
|---|---|---|---|
| Number rescaled | **12** | A base number, now a different number. It must be a proven percent equal to D / 100. | Each one checked against its cell and fact (below). |
| Text to number | 370 | A base text cell, now a number: D / 100 with a percent proof, or D with a quantity proof. | Two parts, below. |
| New only | 705 | Cells in 20 META tables that were `source_text_only` on `main`. | Below. |
| Number to flagged text | 205 | A base number, now text with the reason the rules give: P4 200, points 4, conflict 1. | All 28 tables, first 3 cells each. This is coverage cost, below. |
| Format or reason only | 206 (193 on `732544d`) | Text on both sides; only the reason changed. | Every table group (46 tables), below, and the 13 of the final rerun, one by one. |
| Marker joined to its neighbour | 232 | A base `%` / `)%` cell whose origin now sits in its neighbour's copy cell. The neighbour is checked where it is listed. | Below. |
| Other | 26 | Every cell listed. | Below. |
| Other, base only | 8 | NVDA `pts` unit cells, now inside their value's points text (P4). | All 8. |

**Number rescaled: 12 cells.** Each one was checked against its cell and its fact. Each is an interest or dividend rate in a column with `%` on other rows. Its cell holds a single `xbrli:pure`, `scale="-2"` fact whose digits equal the cell's.
- BAC #127 `Floating 5.65` (`LongTermDebtPercentageBearingVariableInterestRate`) → 0.0565.
- BAC #127 `Subordinated notes 6.00` (`DebtInstrumentInterestRateStatedPercentage`) → 0.0600.
- JPM #266, the preferred-stock `Contractual rate in effect`, Series DD, EE, GG, JJ, LL, MM, HH, II, KK and NN (`PreferredStockDividendRatePercentage`): 5.750, 6.000, 4.750, 4.550, 4.625, 4.200, 4.600, 4.000, 3.650 and 6.875 become 0.05750 … 0.06875, format `0.000%`.

**Text to number: 370 cells.**
- **What they are.** These are negative percents that `main`'s converter rejected and that now convert, and values that gained an attached `%`. All are proven percents: own % 123, own % + fact 27, own % + fact + header 1, own % + header 219.
- **Token shapes.**

  | Base token | New token | Cells |
  |---|---|---|
  | `(N) %` | `(N) %` | 231 |
  | `(N)%` | `(N)%` | 70 |
  | `(N)` | `(N) %` | 41 |
  | `(N` | `(N)%` | 20 (TSM #8) |
  | `N` | `N %` | 8 |

- **Inspection.** I read all 100 Others and NVDA cells, and the first cell of each of the 103 META and RDDT tables. This is a stated sample for a homogeneous class. Every cell was also checked mechanically. Examples:
  - CRDO #45 `Foreign rate differential (34) %` → −0.34;
  - NFLX #7 `DVD revenues (100) %` → −1.00;
  - NVDA 10-Q 2024-Q3 #40 `Compute & Networking 446 | %` → 4.46;
  - TSM #8 `Cost of revenue (40.4 | )%` → −0.404.

**New only: 705 cells.**
- **Which tables.** There are 20 META tables that `main` exported as `source_text_only` because of an "Unresolved value span". In each, a value spanning `$`, amount and `%` columns crossed `main`'s split column groups. The tables are:
  - the 18 "Consolidated and segment results" tables (Family of Apps, Reality Labs and Total);
  - two "Provision for income taxes" tables (10-Q 2026-Q1 #35 and 2026-Q2 #38).
- **What they hold.**
  - 282 `$` amounts, equal to D;
  - 276 proven percents;
  - 48 P4 text cells, the plain `Costs and expenses` amounts beside `%` rows;
  - 99 cells without digits.
- **Headings.** Every number sits under its own heading.
- **Inspection.** I read four tables in full against the source:
  - 10-K FY2024 #5, where Family of Apps revenue is $162,355 and $133,006 with `22%`, Reality Labs `$ (17,729)`, and operating margin `(826) %` → −8.26;
  - 10-Q 2022-Q1 #33;
  - 10-Q 2026-Q1 #35;
  - 10-Q 2026-Q2 #38.

  The other 16 have the same shape and pass the same checks.

**Number to flagged text: 205 cells.**
- **P4 (200).** Unproven numbers in columns whose other rows carry `%`. This is spec P4, "amount and percent rows alike". They are:
  - amounts in JPM #32/#36/#64/#69/#77/#121/#201, AMZN #33, GOOGL #57, NFLX #7 and TSM #9/#10/#12;
  - NVDA's operating-expense amounts (`Sales, general and administrative`, `Acquisition termination cost`);
  - terms in years: MU #29 lease terms (the `(in years)` section label proves nothing) and CRDO #27 warrant term (a `utr:Y` fact is not an amount fact).
- **Points (4).** NVDA `Gross margin` quarter-over-quarter changes, now joined to their `pts`.
- **Conflict (1).** NVDA 10-K FY2024 #26 `Dividend yield 0.1%`. Its fact is pure with no `scale`, which disagrees with the displayed `%` (spec P3); the next two years carry scale -2 and convert.

**Format or reason only: 206 cells.** These were text on `main` and are still text. Only the reason changed. On `ecc5990` they are:
- the 193 cells of `732544d` (below);
- the 13 of the final rerun: 10 P4, 1 converter and 2 conflict, listed above.

28 cells are now attributed to the percent-named rule (Ruling 21): KO #11's 10 and 18 KO #12 cells that were already P4 text. The breakdown of the 193 cells of `732544d`:
- `Numeric role unresolved` → the converter's `Not a complete supported US numeric token` (84): lease terms such as `14.4 years`, ranges such as `0.1-2.0`, and dates;
- `Numeric role unresolved` → the P4 reason (101), including 5 refused split values;
- `Not a complete supported US numeric token` → the points reason (8).

**Marker joined to its neighbour: 232 cells.**
- **Into a value (226).** The marker now sits inside a value's copy cell, and that value is checked elsewhere: 140 are manifest entries and 86 are changed cells checked above.
- **Into a dash (6).** The marker joined a dash through column grouping, giving `— %`, which is text: CRDO #45 (2), GOOGL #56, META 10-Q 2024-Q3 #44, NVDA #38 and NVDA #40.

**Other: 26 cells.**
- **Dash text (6).** The same 6 `—` cells, now `— %` text.
- **A range (1).** BAC #127 `0.25 - 8.05` gained its `%` and is text with the converter's reason.
- **Zeros (8).** CRM #11 `0` (3) is a proven percent 0, format `0%`. TSM #8 `0.0 | %` (5) becomes 0 with `0.0%`.
- **Conflicts (11).** TSM #9–#12 `(4.5 | )%` and similar cells under `% Change in NT$ …` (a `$` in the header): converter-rejected text before, conflict text now.

**Tables.**
- **Status changes (164 tables):**
  - exported → `needs_review`: 55 (new P4 flags);
  - `needs_review` → exported: 70 (negative percents now convert);
  - `source_text_only` → exported or `needs_review`: 20 (the META tables above);
  - header changes only, no status change: 19.
- **Header changes in tables exported on both sides (54).** `changes.py`'s removed-columns gate prints: 54 tables, all explained by removed columns only, with 71 columns removed.
  - Each removed column repeats the header on its left.
  - Their contents are `%` in all 71 columns and `pts` in 8 of them.
  - Each such cell now sits in its neighbour's copy cell.
  - No other cell's header path or row label changed (axis gate: 0).

## Coverage cost (Acceptance 7)

A cell counts when it was a base number and is now text with a review reason. There are **1,127 such cells in 74 tables**.

| Group | Cells | Tables | By kind |
|---|---|---|---|
| META | 554 | 25 | `percent_row_joined` 554 |
| NVDA | 33 | 13 | outside the manifest 33: SG&A amounts beside `%` rows, `pts`, one dividend-yield conflict |
| RDDT | 266 | 12 | `percent_row_joined` 266 |
| Others | 274 | 24 | outside the manifest 172; `percent_row_joined` 82; `percent_row_split` 20 |

Per table:

| Table | Cells | Kinds |
|---|---|---|
| AMZN 10-Q #33 | 59 | outside 20, joined 39 |
| CRDO 10-K #25, #26 | 1, 1 | split 1, split 1 |
| CRDO 10-K #27 | 1 | outside 1 |
| GOOGL 10-Q #57 | 4 | outside 4 |
| JPM 10-K #32, #36 | 48, 9 | outside |
| JPM 10-K #64 | 24 | outside 12, joined 12 |
| JPM 10-K #69, #77, #121, #201 | 8, 3, 9, 2 | outside |
| JPM 10-K #73, #279, #280 | 8, 7, 3 | joined |
| KO 10-K #12 | 6 | joined 6 |
| KO 10-K #54 | 1 | split 1 |
| META 10-K FY2022 #9, #59 | 25, 10 | joined |
| META 10-K FY2023 #10, #62 | 25, 9 | joined |
| META 10-K FY2024 #8, #57 | 26, 6 | joined |
| META 10-K FY2025 #7, #57 | 27, 4 | joined |
| META 10-Q 2022-Q1 #37, #39 | 17, 5 | joined |
| META 10-Q 2022-Q2 #37, #39 | 34, 12 | joined |
| META 10-Q 2022-Q3 #39, #41 | 32, 12 | joined |
| META 10-Q 2023-Q1 #46; 2023-Q2 #46; 2023-Q3 #46 | 17; 33; 33 | joined |
| META 10-Q 2024-Q1 #33; 2024-Q2 #35; 2024-Q3 #37 | 17; 34; 35 | joined |
| META 10-Q 2025-Q1 #28; 2025-Q2 #28; 2025-Q3 #31 | 18; 35; 36 | joined |
| META 10-Q 2026-Q1 #27; 2026-Q2 #30 | 18; 34 | joined |
| MU 10-K #29 | 4 | outside 4 |
| NFLX 10-K #7 | 11 | outside 11 |
| NVDA 10-K FY2024 #11, #26; FY2025 #12 | 3, 1; 2 | outside |
| NVDA 10-Q 2024-Q1 #38; 2024-Q2 #39; 2024-Q3 #39 | 3; 5; 5 | outside |
| NVDA 10-Q 2025-Q1 #42; 2025-Q2 #43; 2025-Q3 #43 | 2; 4; 4 | outside |
| NVDA 10-Q 2026-Q1 #35; 2026-Q2 #35; 2026-Q3 #34; 2027-Q1 #32 | 1 each | outside (points) |
| RDDT 10-K FY2024 #16, #57; FY2025 #16, #56 | 24, 3; 24, 2 | joined |
| RDDT 10-Q 2024-Q1 #38; 2024-Q2 #38; 2024-Q3 #38 | 17; 34; 33 | joined |
| RDDT 10-Q 2025-Q1 #40; 2025-Q2 #41; 2025-Q3 #41 | 16; 32; 32 | joined |
| RDDT 10-Q 2026-Q1 #36; 2026-Q2 #37 | 16; 33 | joined |
| TSM 20-F #9 | 13 | outside 12, split 1 |
| TSM 20-F #10 | 30 | outside 21, split 9 |
| TSM 20-F #11 | 7 | split 7 |
| TSM 20-F #12 | 8 | outside 8 |
| UNH 10-K #12 | 7 | joined 7 |

There are also coverage gains:
- the 20 META tables that now export (558 new numbers);
- 370 text cells that are now proven numbers;
- 12 rates now in their proven scale.

## Header-detection checks (Acceptance 8)

- **`all_facts.py`.**
  - Base and new have the same verdict counts per group. Each has 104 mismatched facts (NVDA 25, Others 79) in 25 tables, all the same, so **0 are new**.
  - The new export has 20 more META tables that are not source text: the 20 tables above. They hold no inline XBRL facts, so no verdict count moves.
- **Stacked-block scan A** (the reviewer's rule): 1 hit on each side (TSM #165), **0 new**.
- **Stacked-block scan B** (broader): 9 hits on each side, **0 new**.

## Spot checks

- **META 10-K FY2024 #8, "Consolidated statements of income data (as a percentage of revenue)":**
  - `Revenue 100 %` → 1.00 and `Net income 38 % / 29 % / 20 %` → 0.38, 0.29 and 0.20;
  - the 26 plain cells between them (`Cost of revenue 18 …`, `Provision for income taxes 5 …`) are text with `Percent sign on other rows of this column; verify the scale.`;
  - the title's `(as a percentage of revenue)(1)` is not a whole table-wide declaration, so it proves nothing.
- **RDDT 10-Q 2024-Q2 #36 `% Change`.** The header proves the column: `54 %` → 0.54, `(75)` → −0.75, `(212)` → −2.12, `474` → 4.74 and `(158)` → −1.58. The `$ Change` column stays dollars: `$ 98,153` and `31,010`.
- **JPM 10-K #279, regulatory capital ratios:**
  - the `%` rows convert: `12.3 %` → 0.123;
  - `Tier 1 capital 13.8` and `13.0`, and `Total capital 15.8` and `15.0`, convert by their own percent facts (0.138 and so on);
  - the IDI and well-capitalized `8.5`, `10.5`, `8.0` and `10.0` hold nested facts (two contexts in one cell), so they are not percent-fact proof (Ruling 3). They are P4 text.
- **TSM 20-F #150, `Other Changes (Note)`.** Under the identifier header, the facts convert (I1, I3): `$ (589.3)` → −589.3 (TWD fact, `sign="-"`) and `303.4` → 303.4. `$ -` stays the nil text. `(2,372.0 | )` in the foreign-exchange column stays text with the converter's reason, as on `main`.
- **CAT 10-K #12, `Full Year 2024` / `Full Year 2023`:**
  - the `$` rows convert: `$ 13,373`, `$ 22.05`, `$ 13,578`, `$ 21.90` and so on;
  - the plain rows `164`, `0.22`, `195`, `(154)`, `(0.23)`, `586` and `1.14` stay text with `Identifier heading over quantities; verify the column.`;
  - dashes stay dashes.
- **TSM 20-F #8 (the first run's blocker).**
  - Every year now converts: `Net revenue` → 1.000 in 2022, 2023 and 2024, `Cost of revenue (40.4 | )%` → −0.404, and `Gross profit 59.6 | %` → 0.596.
  - The emptied marker columns keep their headers (`For the year ended December 31,`) with no text.

## Fix round 1 (task review of `edbedc8`)

The review confirmed every count and found no wrong number and no change in any statement table. It found gaps in the checks and the record. All were fixed on the existing outputs; there was no new export.

1. **Unproven new numbers could pass.** `changes.py` accepted a text-to-number or new-only number with no proof as "D, today's behaviour". The reviewer's mutation, GOOGL #56 EMEA `73,943` made a plain number, passed.
   - **Fix:** every number in a changed cell must now carry a named proof, and a base number may not become unflagged text.
   - **Result:** 948 numbers, 0 without a named proof.
2. **The grouping outcome was undisclosed (Ruling 19).** It is now tightened and disclosed; see "Split `%` markers".
3. **Headers and row labels were not compared.**
   - **Fix:** `changes.py` now has an axis gate (header path and row label of every cell keyed on both sides) and a removed-columns gate. It also has a statement-table gate, which produces the "167 statement tables untouched" figure, and it produces the "54 header changes only remove columns" figure.
   - **Result:** 0, 54 of 54 and pass.
4. **The README overstated `dispositions.py`'s independence.** It now states exactly what the script shares with the branch.
5. **Unflagged text could pass for a manifest cell.** `dispositions.py` would have accepted a percent row, or a misread amount, under an identifier heading as unflagged text (I2's "no reason" case). That is now invalid for every manifest digit cell, per Acceptance 3. No entry took that path before or after.
6. **The rerun commands lacked the low-priority wrapper and depended on a git-ignored file.**
   - **Fix:** the commands now carry the wrapper, and the stacked-block scan is committed as a byte-identical copy.
   - **A side finding.** The wrapper used for the exports (Task 1's and this one) was `start /b /wait` without `call exit`, so their logged `exit: 0` carries no information. The evidence for both exports is 60 JSON files, 60 log lines and 3,702 tables on each side.

**Mutation tests.** These ran on scratch copies of `outputs/xlsx-value-accuracy/new`, never on the real outputs, with the commands above. They ran on the `732544d` export, on the `ecc5990` export, and on the `b7bd072` export after the final checker update. The results were the same each time, except that on `b7bd072` the all-cells sweep fails mutation 1 too, and mutation 4 is new.

| Test | Mutation | Result |
|---|---|---|
| Reviewer 1 | GOOGL 10-Q #56 EMEA `73,943` (text on both sides) becomes the number 73943 | `changes.py` exits 1: `UNPROVEN … '73,943' -> 73943 [no proof outside a percent column]`; gates `changes` and `unproven_numbers` FAIL. |
| Reviewer 2 | AMZN 10-Q #8 (the balance sheet) column 1 relabelled `December 31, 2023` | `changes.py` exits 1. Axes: 25 cells moved. Removed columns: AMZN #8 not explained. Statements: 1 header change and 25 axis changes. `all_facts.py`: 26 new mismatches. Gates `axes`, `removed_columns`, `statements` and `all_facts` FAIL. |
| Ruling 19 | META 10-K FY2025 #5 `52 %` loses its own `%` | `dispositions.py` exits 1: 1 marker "JOINED AGAINST THE RULES" (own % 143 of 144, valid 143 of 144). |
| Sweep (mutation 4) | NVDA 10-K FY2024 #8 `Cost of revenue 27.3`, 0.273 on base, becomes the number 27.3 | `dispositions.py` exits 1: 1 sweep mismatch, NVDA context-declaration cells 494, not the spec's 495. |

## Concerns (none blocks the merge)

1. **Coverage cost is large in MD&A tables.**
   - 1,127 numbers became flagged text, mostly META's and RDDT's percent-of-revenue rows (820).
   - The spec also asks for amount rows in percent columns to be flagged, for example JPM #32 (48) and TSM #9, #10 and #12 (41). That includes TSM's `Net revenue 2,263,891`, which sits in a column whose other rows carry an attached `%`.
   - These are text, never wrong numbers, and no primary statement is affected.
2. **The literal safety net flags three cells that carry their own percent fact**, CRDO #25 and #26 and KO #54 (Ruling 13). Each heading was left in the body: `May 3, 2025` and `8 years` span the `%` column.
3. **The harness drops nested facts.** `export_tables.py` drops facts nested in facts (1,068 in the corpus). So `primary_statements.py` and `all_facts.py` never check the inner facts either; JPM's inner `c-2025` contexts are one example. `dispositions.py` restores the count from the filings for Ruling 3, but the period check does not.
4. **The table-wide percent declaration in the context lines is not in the export JSON.** `dispositions.py` sees only in-table spanning captions. No entry or changed cell needed the context proof in this run. Such a cell would have appeared as invalid and been checked by hand.
5. **Emptied split-`%` columns keep their header.** For example, TSM #8 keeps two blank `For the year ended December 31,` columns. This is cosmetic.
