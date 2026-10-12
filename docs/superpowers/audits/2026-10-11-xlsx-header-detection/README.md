# XLSX header detection: acceptance record

Acceptance run for the XLSX header detection spec
([`../../specs/2026-10-11-sec2md-xlsx-header-detection-design.md`](../../specs/2026-10-11-sec2md-xlsx-header-detection-design.md),
revision 5, "Acceptance" 1-6) and Task 3 of its plan
([`../../plans/2026-10-11-sec2md-xlsx-header-detection.md`](../../plans/2026-10-11-sec2md-xlsx-header-detection.md)).

- Candidate: branch `fix/xlsx-header-detection` at `ad131b0` (worktree `.worktrees/xlsx-header-detection`;
  `4373afd` Rule 3, `ad131b0` Rules 1-2).
- Baseline: the main checkout's `src` at `e478717`, which still has the unchanged code.
- Corpus: the 60 filings in `filings.txt`: 42 vault 10-K/10-Q filings (18 META, 14 NVDA, 10 RDDT) and the 18 filings
  in `outputs/table-completeness-corpus`.
- Run on 2026-10-12. Both export directories hold 60 JSON files (3,702 tables each).

**Revision 6.** The rerun for spec revision 6 (the period-row guard, final branch commit `5f779c0`, after the audit
review) is recorded in "Revision 6: acceptance rerun" at the end of this file. It resolves D1 and TSM #105 (items 1 and 2 below).
`compare.md` and `all-facts.md` now hold that run; `statements.md` is unchanged by it. The revision 5 record that
follows is kept as it was.

## Result in one paragraph

The harness reproduces the plan's expected numbers exactly. Acceptance criteria 1-4 and 6 pass as written: the 126
vault primary statements are all exported with every XBRL fact `ok`, the vault has 0 lost or changed cells, every
promoted row is a column heading, and the spot checks match the filings. Criterion 5's classification is complete: in
the other filings, 41 lost cells and all 14 changed cells are fixes, and the other 52 lost cells are regressions in 7
tables (NTRA, TSM) that await the user's acceptance. An extra check against inline XBRL, covering every table and not
only the three primary statements, found one defect the stated checks do not cover: in **21 vault statements of
stockholders' equity** (META and RDDT 10-Qs), the second period block sits under the first block's period header.
See "Needs the user's acceptance".

## Needs the user's acceptance

Nothing below has been accepted. Each item blocks the merge until the user decides.

1. **Defect D1: second period block under the first block's period header, 21 vault tables.** These are the
   statements of stockholders' equity in META's Q2 and Q3 10-Qs (9 tables) and in RDDT's 10-Qs (12 tables). The filing
   stacks two blocks in one table, each under its own caption row (`Three Months Ended June 30, 2022`, then
   `Six Months Ended June 30, 2022`). The header extension reads the first caption into every column header. The
   second caption row stays in the body, so the second block's numbers sit under the first block's period. For RDDT,
   the first block is the prior year, so **the current quarter's figures sit under the prior-year header**. Example:
   RDDT Q1 2025 10-Q #8, `Net income (loss)` 26,158 (XBRL context 2025-01-01 to 2025-03-31) is exported under
   `Three months ended March 31, 2024 — Total Stockholders' Equity (Deficit)`. Another example: META Q2 2022 10-Q #9,
   the six-month block's opening `Retained Earnings` 69,761 (instant 2021-12-31) sits under
   `Three Months Ended June 30, 2022 — Retained Earnings`. In total, 906 numbers sit below the second caption, and
   852 XBRL facts conflict with their column's period (META 383, RDDT 469). All 21 tables are `needs_review`. Their
   only issue names the second caption row ("Not a complete supported US numeric token"), not the wrong header. On
   `main`, 20 of the 21 were `source_text_only` and one (RDDT Q2 2024 10-Q #8) was `needs_review` with `Column N`
   headers. None is a balance sheet, income statement or cash flow statement. The full list is under "Defect D1" below. A possible guard, not
   implemented: keep `_header_count`'s result when a body row below the data repeats a period caption row of the
   extended header.
2. **TSM 20-F #105 (actuarial assumptions), 4 cells: regression (review finding I1).** See "I1 and I2" below.
3. **NTRA 10-K #8 (contractual obligations), 4 cells: regression.** `Less Than 1 Year` wraps over two header rows,
   so Rule 3 sees the part `1 Year`, which matches `_IDENTIFIER` (`year`), and no exemption applies. The amounts
   80,000, 362, 113,818 and 194,180 become unflagged text, and the table goes from `needs_review` to `exported` with no
   issues.
4. **TSM 20-F #150, #151, #152 (financing liabilities roll-forwards), 13 cells: regression.** The column heading
   `Other Changes (Note)` carries a bare footnote marker. `(Note)` matches `_IDENTIFIER` (`note`), and the
   note-reference exemption needs a note number. Thirteen XBRL-tagged amounts
   (`IncreaseDecreaseThroughOtherChangesLiabilitiesArisingFromFinancingActivities`) become unflagged text. #152 goes
   from `needs_review` to `exported` with no issues.
5. **TSM 20-F #19 and #20 (share ownership), 31 cells: regression, known from the spec.** The ownership percentages
   become text flagged "Conflicting explicit units". The header `Percentage of Outstanding Common Shares(2)` has both
   `%` and `shares` meaning. This is visible and flagged. The share counts beside them become numbers.

Concerns that need no decision to merge are listed under "Concerns".

## How to rerun

```bash
cd /c/Users/einstein/kelab5am/sec2md
PY=/c/Users/einstein/kelab5am/sec2md/.worktrees/xlsx-export/.venv/Scripts/python.exe
A=docs/superpowers/audits/2026-10-11-xlsx-header-detection
O=outputs/xlsx-header-detection
$PY -I $A/export_tables.py --src src --out $O/base $(cat $A/filings.txt) | tail -1
$PY -I $A/export_tables.py --src .worktrees/xlsx-header-detection/src --out $O/new $(cat $A/filings.txt) | tail -1
ls $O/base | wc -l; ls $O/new | wc -l      # 60 and 60
$PY -I $A/compare.py $O/base $O/new --report $A/compare.md --details $O/compare.json
$PY -I $A/primary_statements.py $O/new --report $A/statements.md --details $O/statements.json
(cd .worktrees/xlsx-header-detection && $PY -I ../../$A/mutation_check.py . $PY)
```

The first export runs were killed at 11m19s with BAC, JPM and TSM unfinished, so those three were exported again on
both sides with `--workers 3`. Each filing's JSON is written on its own, so the other 57 were unaffected. The scripts
for the extra checks in this record (the all-table XBRL period check, the stacked-block scan and the silent-text
scan) and their outputs are in `outputs/xlsx-header-detection/task-3/` (git-ignored). Review findings I1 and I2 are
covered by `outputs/xlsx-header-detection/investigation-1/`.

## Numbers against the plan

`compare.md` (identical to the scratch preview run):

| Group | Files | Fallback tables | Numeric cells | Balanced columns | Lost | Changed | Promoted rows | Balanced lost | Tables missing / added |
|---|---|---|---|---|---|---|---|---|---|
| META | 18 | 408 → 57 | 8,309 → 16,091 | 28 → 36 | 0 | 0 | 810 | 0 | 0 / 0 |
| NVDA | 14 | 270 → 8 | 6,550 → 13,084 | 22 → 28 | 0 | 0 | 677 | 0 | 0 / 0 |
| RDDT | 10 | 174 → 10 | 6,092 → 9,407 | 16 → 20 | 0 | 0 | 417 | 0 | 0 / 0 |
| Others | 18 | 1004 → 626 | 9,511 → 20,887 | 23 → 37 | 93 | 14 | 1314 | 0 | 0 / 0 |

Every figure the plan expects matches.

`statements.md` totals: facts 11,601, ok 10,139, failures 978, untagged 10, repeated 3, yearless 1, arithmetic 0,
ambiguous 1, not found 13. By group (from `statements.json`):

| | Statements | Exported | XBRL facts | OK | Label-column facts | Failures | Untagged | Repeated | Yearless | Arithmetic | Ambiguous | Not found |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| META | 54 | 54 | 3,448 | 3,322 | 126 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| NVDA | 42 | 42 | 2,683 | 2,662 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| RDDT | 30 | 30 | 2,228 | 2,056 | 172 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Others | 41 found | 26 (+3 needs_review, 12 source_text_only) | 3,242 | 2,099 | | 976 fallback, 2 not numeric | 10 | 0 | 1 | 0 | 1 | 13 |

In the vault, OK plus label-column facts equals all facts in every group, so every fact outside the label column is
`ok`. The 3 `repeated` cells are META's FY2023 10-K cash flow statement, as expected.

## Acceptance criteria

| Spec | Criterion | Result |
|---|---|---|
| 1 | All tests pass | Pass. Task 2 ran the full suite on `ad131b0`: 2,057 passed, 1 failed. The failure is the known environmental `test_internal_version_matches_distribution`. |
| 2 | Harness committed and run on the 60 filings | Pass. The harness has been on `main` since `e478717`. Both runs have 60 filings and 3,702 tables, and no table is missing or added. |
| 3 | Primary statements, vault | Pass. All 126 statements are exported, and 8,040 facts are `ok` (META 3,322, NVDA 2,662, RDDT 2,056). The other 319 facts sit in row labels. There are 0 failures, 0 untagged, 0 yearless, 0 arithmetic problems and 0 ambiguous. META's FY2023 10-K cash flow statement has 3 `repeated` cells. |
| 4 | Vault, all tables | Pass as written: 0 lost, 0 changed, 0 balanced columns lost, 0 / 0 tables. All 1,904 promoted rows were read, and every one is a column heading (see below). **Defect D1 is outside these checks.** |
| 5 | Other filings | Every lost and changed cell, and every promoted row with digits, is classified below with its source cells. 52 lost cells are regressions that need the user's acceptance. 0 balanced columns are lost. No XBRL period mismatch was found in any exported primary statement. |
| 6 | Spot checks | Pass (see below). |

## Promoted rows

**Vault (1,904 rows: META 810, NVDA 677, RDDT 417).** Every row was read, grouped by distinct cell texts: 161 META,
152 NVDA and 72 RDDT. 134 rows are blank spacer rows (META 50, NVDA 57, RDDT 27). Every other row is a column heading:

- period and date rows: years, `December 31,`, `Three Months Ended June 30,`, `Jan 28, 2024`, `July 30,`,
  `2023 (2)`, `March 31, 2024` over `(unaudited)`;
- change columns: `% change`, `$ Change`, `2024 vs 2023 % change`, `Quarter-over-Quarter Change`;
- fair value and investment headings: `Description`, the Level 1-3 captions, `Fair Value Measurement at Reporting Date
  Using`, `Less than 12 months`, `12 months or greater`, `Fair Value`, `Unrealized Losses`, `Amortized Cost`,
  `Reported as`, `Pricing Category`;
- equity statement headings: `Class A and Class B Common Stock`, `Shares`, `Par Value`, `Amount`, `Additional Paid-In
  Capital`;
- debt and lease headings: `Maturity`, `Stated Interest Rate`, `Effective Interest Rate`, `Expected Remaining Term
  (years)`, `Operating Leases`, `Finance Leases`;
- share repurchase and award headings: `Total Number of Shares Purchased (1)`, `Number of Shares`,
  `Weighted-Average Grant Date Fair Value Per Share`, `Record Date`, `Payment Date`, `Dividend Per Share`;
- exhibit index headings: `Exhibit`, `Exhibit Number`, `Incorporated by Reference`, `Filed Herewith`;
- group captions: `Plan to Date`, `Severance Liabilities`, `Pro Forma (Unaudited)`, `Commitments`, `Family of Apps`;
- NVDA's stock performance graph dates (`1/27/2019` … `1/28/2024`).

No promoted row is a data row or a line item.

**Other filings, rows with digits (355 rows, 141 distinct).** Every one is a column-heading row. They hold years,
dates, period captions (`Full Year 2024`, `2Q25`, `12/19`), footnote markers (`(1)`, `Rate1`), bucket headings
(`30-59 Days Past Due (1)`, `1-5 years`, `Less Than 1 Year`) or a caption in the label column
(`(in millions)`, `December 31, 2024 (in millions)`). None is a data row. The consequences that matter come from Rule 3
reading some of these headings (NTRA #8, TSM #150-#152) and are classified with the lost cells below.

## Mutation check

Rerun on `ad131b0` (`mutation_check.py`, exit 0):

```
caught   1 data cell                 caught   7b caption for years
survived 2 unit-declaration rows     caught   8 year under period
caught   3 two headings              caught   8 equal-width yearless
caught   3b heading-like label       caught   evidence cut-off
survived 4 narrow downward           caught   data row needs digits
caught   4b labelled subdivides      caught   caption label whole
caught   4c straddle                 caught   R2 footnoted year token
survived 5 narrower than amount      caught   R3 note reference
caught   6 currency narrows          caught   R3 maturity bucket
survived 7 year label                caught   R3 period words
                                     caught   R3 own quantity
                                     caught   R3 wrapped quantity
                                     caught   R3 wrapped join too broad
all mutants behaved as expected
```

The survivors are the expected set: check 2's unit half, and checks 4, 5 and 7. `xlsx_tables.py` was byte-identical
after the run (same SHA-256 before and after), and the worktree stayed clean.

## Other filings: every lost and changed cell

Source cells are `(row, column)` in the filing's table grid. Each was checked in the filing's HTML.

| Filing / table | Cells | Source cells | Before → after | Verdict |
|---|---|---|---|---|
| MSFT 10-K #50 Long-term Debt | 21 lost | Column 5, rows 4-16: `2039 2040 2041 2042 2043 2033 2055 2056 2057 2060 2062 2050 2050`. Column 3, rows 9-16: `2028 2025 2026 2026 2030 2052 2026 2026`. Row 4 reads `2009 issuance of $3.8 billion \| 2039 \| 5.20% \| 5.24% \| $ 520 \| $ 520`. | Numbers under `Column N` (`needs_review`, no headers) → text under `Maturities (calendar year)`. The table is still `needs_review` because of the rate cells. | **Fix.** These are calendar maturity years, not amounts. The carrying values (520 …) are now under `June 30, 2025` and `June 30, 2024`. |
| NTRA 10-K #8 Operating leases (contractual obligations) | 4 lost | (5,6) `80,000`, (6,6) `362`, (7,6) `113,818`, (8,6) `194,180`. The heading rows are `Less Than` / `1 Year`. | Numbers → unflagged text. The table goes from `needs_review` to `exported` with no issues. | **Regression** (item 3). |
| TSM 20-F #19 Share Ownership | 26 lost | Column 7 of rows 2-4, 11-17 and 19-34, for example `C.C. Wei … \| 6,392,834 \| 0.02 \| %` | `0.0002` → text `0.02 %`, flagged "Conflicting explicit units". The table stays `needs_review`. | **Regression**, known from the spec (item 5). |
| TSM 20-F #20 (the same table continued, titled `Table of Contents`) | 5 lost | Column 7 of rows 2-6, `0.00 %` | As #19 | **Regression** (item 5). |
| TSM 20-F #48 Statement of financial position (assets) | 12 lost | Column 2, rows 8-15 and 25-28: note numbers `7 8 9 10 11 12 34 34 8 9 10 14` under `Notes` | Numbers → text under `Notes`. The table goes from `needs_review` to `exported`. | **Fix.** These are note references. See concern C3 about this table's US$ column. |
| TSM 20-F #49 Statement of financial position (liabilities) | 8 lost | Column 2: (8) `8`, (11) `34`, (13) `29`, (15) `21`, (29) `20`, (31) `22`, (41) `21`, (45) `21` | Numbers → text under `Notes`. The table stays `needs_review`. | **Fix.** |
| TSM 20-F #105 Actuarial assumptions | 4 lost | (4,2) `1.40%`, (4,4) `1.60%`, (5,2) `4.00%`, (5,4) `4.00%`, XBRL-tagged (`ActuarialAssumptionOfDiscountRates`, scale -2) | `0.0140` etc. → unflagged text. The table goes from `needs_review` to `exported`. | **Regression** (item 2, I1). |
| TSM 20-F #150 Short-term loans roll-forward | 5 lost | Column 35: (6) `(589.3`, (7) `303.4`, (8) `(5.2`, (9) `267.1`, (12) `(24.0` under `Other Changes (Note)` | Numbers → unflagged text. The table stays `needs_review` for another cell. | **Regression** (item 4). |
| TSM 20-F #151 Hedging liabilities roll-forward | 4 lost | Column 35: `362.1`, `11.6`, `382.0`, `755.7` | As #150 | **Regression** (item 4). |
| TSM 20-F #152 Hedging liabilities roll-forward | 4 lost | Column 35: `387.8`, `18.0`, `373.4`, `779.2` | As #150. The table goes from `needs_review` to `exported`. | **Regression** (item 4). |
| JPM 10-K #279 Regulatory capital | 6 changed | (4,3) `12.3 \| %` and the other first-row cells `7.0`, `11.5`, `7.0`, `6.5`, plus (5,15) `6.0 \| %` | `12.3` → `0.123` | **Fix.** The XBRL fact has `scale="-2"`, so its value is 0.123. The column now mixes scales, though: `13.8` below stays 13.8. This is a known gap; see concern C2. The table goes from `needs_review` to `exported`. |
| JPM 10-K #280 Leverage-based capital ratios | 3 changed | (4,6) `4.0 \| %`, (4,9) `4.0 \| %`, (4,18) `5.0 \| %` | `4.0` → `0.040` | **Fix**, with the same mixed-scale caveat (SLR `5.0` stays 5.0). |
| TSM 20-F #172 Customer A | 5 changed | (7,16) `23`, (7,30) `25`, (7,44) `22`, (8,44) `12`, (9,30) `11` under `Years Ended December 31 — 2022 — %` | `23` → `0.23` | **Fix.** The XBRL fact `PercentageOfEntitysRevenue` has `scale="-2"`, and the whole `%` column is now consistent. |

Totals: 93 lost cells, of which 41 are fixes and 52 are regressions. All 14 changed cells are fixes.

## I1 and I2 (review findings from Task 2, parked by the controller)

**I1: an accepted row stranded below the evidence cut-off.** Scope and method are in
`.superpowers/sdd/2026-10-11-sec2md-xlsx-header-detection/investigation-1-report.md`. The tables that change status:

| Table | Base → new | What the user sees | Verdict |
|---|---|---|---|
| TSM 20-F #105 Actuarial assumptions | `needs_review` → `exported` | The headers are `Measurement Date` ×2, and the first body row is `December 31, 2023 \| December 31, 2024`. Rule 3 reads `Measurement Date` as an identifier, so the 4 XBRL-tagged rates become unflagged text. | **Regression; needs the user's acceptance** (item 2). |
| RDDT exhibit indexes: 10-K FY2024 #63, FY2025 #62; 10-Q 2024-Q1 #48, 2024-Q2 #47, 2024-Q3 #47, 2025-Q1 #49, 2025-Q2 #50, 2025-Q3 #50, 2026-Q1 #46, 2026-Q2 #47 | `needs_review` → `exported` | The headers are `Exhibit Number \| Exhibit Description \| Incorporated by Reference ×3 \| Filed Herewith`. `Form \| Filing Date \| Number` stays as the first body row. | **Acceptable.** Every cell is text on both sides, and no value changes. The header is less specific than it could be, and the "No explicit headers" flag is gone. |
| NFLX 10-K #74, #75 exhibit indexes | `needs_review` → `exported` | The same, with `Form \| File No. \| Exhibit \| Filing Date` in the first body row | **Acceptable**, for the same reasons. |
| NTRA 10-K #43, UNH 10-K #52 | `needs_review` on both sides | The years stay text and are flagged "Numeric role unresolved". | No change in what is flagged. |

A follow-up guard is **offered to the user, not implemented**: return `base` when an accepted row that falls below
the last evidenced row holds a year token or a period heading. It would put TSM #105 back to `main`'s output, with 4
numeric rates and `needs_review`. It would also restore `main`'s headers for NTRA #43, UNH #52 and TSM #59, which
are `needs_review` on both sides. It would not change the exhibit indexes, because no cell in their stranded row
(`Form`, `Filing Date`, `Number`) is a year token or a period heading.

**I2: table-wide percent units.** A caption such as `(In millions, except per share and percentage data)` that
enters `units` makes `_numeric_role` treat plain amounts as percents. This is pre-existing, and it occurs 0 times in
`base` or `new` across the 60 filings. Every percent caption in the corpus is plural (`except percentages`), which
`_UNIT_DECLARATION` does not match. It is a **latent risk**: 24 branch tables (RDDT 17, Others 7) carry a plural
caption where it would enter `units` if the pattern accepted the plural. On `main`, 0 tables do.

## Defect D1: the 21 tables

Found by checking every XBRL fact in every exported table against its column header's period
(`task-3/allfacts.py`), then confirmed by a structural scan for a body row that repeats a period caption
(`task-3/blocks.py`). The only other table with that shape is TSM #165, which is unchanged from `main`.

| Filing | Table | Header names | Second block (in the body) | Numbers below | XBRL facts off-period |
|---|---|---|---|---|---|
| META 10-Q 2022-Q2 | #9 | Three Months Ended June 30, 2022 / 2021 | Six Months Ended … | 48 | 40 |
| META 10-Q 2022-Q3 | #9 | Three Months Ended September 30, 2022 / 2021 | Nine Months Ended … | 48 | 40 |
| META 10-Q 2023-Q2 | #9 | Three Months Ended June 30, 2023 / 2022 | Six Months Ended … | 48 | 40 |
| META 10-Q 2023-Q3 | #9 | Three Months Ended September 30, 2023 / 2022 | Nine Months Ended … | 48 | 40 |
| META 10-Q 2024-Q2 | #9 | Three Months Ended June 30, 2024 / 2023 | Six Months Ended … | 50 | 42 |
| META 10-Q 2024-Q3 | #9 | Three Months Ended September 30, 2024 / 2023 | Nine Months Ended … | 52 | 44 |
| META 10-Q 2025-Q2 | #9 | Three Months Ended June 30, 2025 / 2024 | Six Months Ended … | 54 | 46 |
| META 10-Q 2025-Q3 | #9 | Three Months Ended September 30, 2025 / 2024 | Nine Months Ended … | 58 | 50 |
| META 10-Q 2026-Q2 | #9 | Three Months Ended June 30, 2026 / 2025 | Six Months Ended … | 51 | 41 |
| RDDT 10-Q 2024-Q2 | #8 | Three months ended June 30, 2023 | Three months ended June 30, 2024 | 37 | 40 |
| RDDT 10-Q 2024-Q2 | #9 | Six months ended June 30, 2023 | Six months ended June 30, 2024 | 50 | 52 |
| RDDT 10-Q 2024-Q3 | #8 | Three months ended September 30, 2023 | … 2024 | 39 | 42 |
| RDDT 10-Q 2024-Q3 | #9 | Nine months ended September 30, 2023 | … 2024 | 53 | 55 |
| RDDT 10-Q 2025-Q1 | #8 | Three months ended March 31, 2024 | … 2025 | 33 | 33 |
| RDDT 10-Q 2025-Q2 | #8 | Three months ended June 30, 2024 | … 2025 | 32 | 33 |
| RDDT 10-Q 2025-Q2 | #9 | Six months ended June 30, 2024 | … 2025 | 33 | 40 |
| RDDT 10-Q 2025-Q3 | #8 | Three months ended September 30, 2024 | … 2025 | 33 | 32 |
| RDDT 10-Q 2025-Q3 | #9 | Nine months ended September 30, 2024 | … 2025 | 34 | 37 |
| RDDT 10-Q 2026-Q1 | #8 | Three months ended March 31, 2025 | … 2026 | 35 | 35 |
| RDDT 10-Q 2026-Q2 | #8 | Three months ended June 30, 2025 | … 2026 | 35 | 35 |
| RDDT 10-Q 2026-Q2 | #9 | Six months ended June 30, 2025 | … 2026 | 35 | 35 |

All 852 off-period facts are in the second block. "Numbers below" counts numeric copy cells below the second
caption, untagged ones included. "Off-period" counts tagged facts, including nil facts shown as `—`, and leaves out
the second block's closing balances, which share the header's end date. Every table is `needs_review` on the branch.
On `main`, every table was `source_text_only` apart from RDDT 2024-Q2 #8 (`needs_review`, `Column N` headers).

The same all-table check found no other new misattribution. Every other new mismatch is the checker's own limit:

- maturity schedules whose headers name future years (AMZN #19, #23);
- JPM's First Republic purchase price allocation, which JPM tags at the reporting date (#296, #297);
- opening balances in roll-forwards under the period's date: MU #22 opening cash (MU's cash flow statement, which
  fell back on `main`), NFLX #70, NTRA #15, #16, #21, #26, #30 and #42, and NVDA's 10-Q deferred revenue.

`main` has the same pattern in 11 tables.

## Spot checks (spec Acceptance 6)

Each was read from the `new` JSON and compared with the filing's HTML.

| Table | Result |
|---|---|
| META FY2024 10-K balance sheet (#22, `exported`) | Headers `December 31, — 2024` and `December 31, — 2023`. `Total assets` 276054 and 229623. The filing's row 15 reads `Total assets \| $ 276,054 \| $ 229,623` under `December 31,` / `2024 \| 2023`. **Pass.** |
| META FY2024 10-K revenue MD&A (#9, `needs_review` for the `(12) \| %` cell) | `Total revenue` 164501, 134902, 116609, with `% change` 0.22 and 0.16, under `Year Ended December 31, — 2024/2023/2022`. The filing shows `$ 164,501 \| $ 134,902 \| $ 116,609 \| 22 % \| 16 %`. **Pass.** |
| META FY2024 10-K Basic EPS | Income statement #23: `Basic` 24.61, 15.19, 8.63. Basic EPS table #33: `Basic EPS` 24.61, 15.19, 8.63 under `Year Ended December 31, — 2024`, `— 2023 (2)`, `— 2022 (2)`. **Pass.** |
| META Q1 2025 10-Q income statement (#7, `exported`) | `Revenue` 42314 and 36455. `Net income` 16644 and 12369. Headers `Three Months Ended March 31, — 2025` and `— 2024`. **Pass.** |
| NVDA FY2024 Q2 10-Q balance sheet (#6, `exported`) | Headers `July 30, — 2023` and `January 29, — 2023`. `Total assets` and `Total liabilities and shareholders' equity` are both 49555 and 41182. **Pass.** |
| RDDT Q2 2025 10-Q results of operations (#39, `exported`) | Headers `Three months ended June 30, — 2025` and `— 2024`, `$ Change`, `% Change`, then the same for six months. `Revenue` 499627, 281184, 218443, 0.78, 891988, 524147, 367841, 0.70. `Net income (loss)` 89297, -10099, 99396, `NM`. All amounts are numbers. **Pass.** |

## Other filings' primary statements, read one by one

- **12 fall back** (976 facts, `fallback`): BAC BS, CAT BS and CF, CRM IS and CF, JPM BS and IS, KO BS and CF, MSFT BS
  and IS, and TSM IS. These export as source text, so no number can sit under a wrong period.
- **2 not numeric**: BABA's parent-only condensed balance sheet (#81), `Treasury shares, at cost`, `(27,684` and
  `(36,329`. The closing `)` sits in the next cell. The cells are text and flagged ("Not a complete supported US
  numeric token"). This was `source_text_only` on `main`.
- **10 untagged, 1 yearless**: BABA's income statement (#22). These are note references (`24`, `17`, `7`, `9`) under a
  headerless `Column 2` Notes column. The output is identical on `main`.
- **1 ambiguous**: NFLX's income statement. The checker chose #29 (45 of 45 facts `ok`) over the segment note #72.
  The choice is correct.
- **13 not found**:
  - BAC IS and CF, CAT IS, JPM CF, KO IS and MSFT CF still fall back.
  - NVO's financial statements are not in the 20-F document; the filing has 2 facts in all.
  - NTRA CF (#14: 112 of 112 facts match their column's period), TSM BS (#48: 72 of 72; #49: 92 of 93, with 1 flagged
    text cell) and UNH CF (#24: 123 of 123) export with every number under its own period.
  - TSM CF (#54-#56) is unchanged from `main` (`needs_review`, headers `2022 / 2023 / 2024`).
- In the 26 exported statements the checker found, every fact outside the label column is `ok`.

No exported primary statement in the other filings has a number under the wrong period or with the wrong value.

## Concerns

- **C1. Rule 3 false positives leave amounts as unflagged text in tables that now export.** These cells were source
  text on `main` too, because their tables fell back, so no number is lost. But 12 of the 21 tables are now
  `exported` with no issues, so nothing signals that a column of amounts is text. In total, 154 cells are affected:
  - `year`, 136 cells in 20 tables:
    - NVDA's 10-Q `Year-over-Year Change` columns: 69 cells in 13 tables, 6 of them `exported`. The
      `Quarter-over-Quarter Change` columns beside them are numbers.
    - CAT #12 `Full Year 2024 / 2023`: 22 cells, `exported`.
    - JPM maturity buckets `Within 1 year(a)`, `1 year or less(b)`, `After 1 year through 5 years` and `<1 year`:
      #91, #96, #97, #105 and #166, 33 cells.
    - AMZN #36 `At Prior Year Rates`: 12 cells.
  - `notes`, 18 cells: JPM #99 `Credit derivative and credit-related notes (h)`, `exported`.

  The spec lists the missing flag for identifier columns as a known gap; these headings are false positives of the
  identifier words. On the branch, 204 amount-like text cells in non-fallback tables carry no review issue. They
  comprise these 154, the regressions NTRA #8, TSM #105 and TSM #150-#152 (21), the TSM note references (20) and 9
  NVO page numbers. On `main`, 52 cells in other tables carry no issue (`task-3/silent.txt`,
  `task-3/silent_causes.py`).
- **C2. Mixed percent scale, newly exposed.** When only the first row of a column shows `%`, that row converts to a
  fraction and the rows below stay in percentage points. This is the spec's known gap, until now cited for JPM #279.
  It also appears in tables that used to fall back: BAC #127 `Weighted-average Rate` (`3.45 %` → 0.0345, `4.71` →
  4.71), CRM #60 `Contractual Interest Rate`, KO #56 `Average Rate`, and JPM #64, #73, #210, #281 and #282. The
  workbook shows `3.45%` beside `4.71`, so it reads correctly, but a sum or comparison across the column is wrong.
  Several of these tables are `exported` with no issues.
- **C3. TSM #48: the US$ convenience-translation column is headed `December 31, 2024`, like the NT$ column.** The
  `US$` and `(Note 3)` captions are dropped on both sides, and the table goes from `needs_review` to `exported`. The
  numbers sit under the right date, but the currency is unmarked.
- **C4. I2** stays a latent risk (see above).
- **C5. The stated Acceptance 4 checks miss stacked period blocks.** They cover lost and changed cells and the text
  of promoted rows. A promoted row can be a real heading and still label numbers that belong to another period (D1).
  Future acceptance runs should include the all-table XBRL period check.

## Revision 6: acceptance rerun

Acceptance rerun for spec revision 6 (the period-row guard in Rule 1, Acceptance 1-6 including 3b, and gate 6
below) and Task 7 of the plan. This section records the final run, made after the audit review.

- Candidate: branch `fix/xlsx-header-detection` at `5f779c0`. Three commits sit on top of `ad131b0`:
  - `f9a7a9e` and `429f1fd` add the guard;
  - `5f779c0` makes period text read captions with a unit suffix, such as
    `Year ended December 31, 2022 (in millions)`.

  `git diff ad131b0 5f779c0 -- src/sec2md/xlsx_tables.py` adds only `_period_text`, `_period_row`, their patterns
  and the guard line in `_export_header_count`.
- Baseline: `outputs/xlsx-header-detection/base` from the revision 5 run, reused. The main checkout's `src` has not
  changed.
- Export: `outputs/xlsx-header-detection/new6`, re-exported at `5f779c0`. It has 60 JSON files that all parse, and
  3,702 tables. File names match `base` and `new`. One run with `--workers 12` took 8m31s.
- Run on 2026-10-12.

### Audit review and rerun

The first revision 6 run, at `429f1fd` (commit `7607834`), passed gates 1-5, and an independent audit review
reproduced gates 1, 2, 3 and 5 exactly. It found one false claim in this section: the "Extra check: columns mixing
periods" said that no header named one period over another period's facts.

- **What the check missed.** JPM 10-K #159, #161 and #241 still stacked a second period block, with both captions in
  the label column. The label column's header cell was `Year ended December 31, 2023 (in millions)`; a body row
  later read `Year ended December 31, 2022 (in millions) | <column headings>`.
  - #161 and #241 were `exported` with no issues.
  - 63 XBRL facts disagreed with the label column's period.
- **Why it missed them.** The extra check looked only at the value columns' headers, not the label column's header.
  Its own output had listed #161 for review, but the record dropped it.
- **The fix.** The branch's `5f779c0` removes a parenthesised unit caption before the period-text test. The guard now
  fires on the three tables, and each equals `base`.
- **This rerun.** It repeats every gate, adds gate 6 (a structural scan for stacked period blocks), fixes the count
  errors the review found, and replaces every figure below.
- **What changed between the two runs.** Only JPM #159, #161 and #241 differ, table by table: #161 and #241 went
  from `exported` to source text, and #159 got `main`'s headers back. The all-facts mismatch, yearless, unlocated and
  unparsed lists are identical between the two runs.

### Result in one paragraph

All six gates pass. The guard fired in 169 tables. 107 of them differ from revision 5, and each of the 107 is now
identical to `main`'s output in every recorded field. The other 62 fall back to source text on both revisions. No
table differs from revision 5 for any other reason. The 21 D1 tables, TSM #105 and JPM #159, #161 and #241 are among
the 107.

The 126 vault primary statements are unchanged from revision 5, with every XBRL fact `ok`. In the vault, 0 cells are
lost or changed and 0 balanced columns are lost.

The all-table XBRL check finds 104 mismatched facts in 25 tables on the branch; 26 facts in 11 of those tables are on
`main` too. Every mismatch is a checker limit, except one existing TSM row where the filing's own tags disagree with
its own columns, so there are **0 real misattributions**.

The reviewer's stacked-block scan finds no table on the branch that is not also on `main`. A broader scan finds 3,
all META debt tables whose section labels name a note issuance (`August 2022 debt:`), not a period.

The guard costs more coverage than the spec first stated. Besides D1 and TSM #105, it returns 85 tables to `main`'s
output, which is 1,687 fewer numeric cells than revision 5.

Two groups of newly exported tables still have amounts under period headers without a year: NVDA's change columns
(58 tables, arithmetic verified) and CRM's percent-of-revenue columns (6 tables). The CRM columns are a
misattribution risk for the user to accept or reject.

### How to rerun (revision 6)

```bash
cd /c/Users/einstein/kelab5am/sec2md
PY=/c/Users/einstein/kelab5am/sec2md/.worktrees/xlsx-export/.venv/Scripts/python.exe
A=docs/superpowers/audits/2026-10-11-xlsx-header-detection
O=outputs/xlsx-header-detection
$PY -I $A/export_tables.py --src .worktrees/xlsx-header-detection/src --out $O/new6 --workers 12 $(cat $A/filings.txt)
$PY -I $A/compare.py $O/base $O/new6 --report $A/compare.md --details $O/task-7/compare-new6.json
$PY -I $A/primary_statements.py $O/new6 --report $A/statements.md --details $O/task-7/statements-new6.json
$PY -I $A/all_facts.py $O/base --report $O/task-7/all-facts-base.md --details $O/task-7/all-facts-base.json
$PY -I $A/all_facts.py $O/new6 --report $O/task-7/all-facts-new6.md --details $O/task-7/all-facts-new6.json
```

`all-facts.md` holds the two all-facts reports, unchanged except that their headings are one level lower. The
all-facts report on `base` is byte-identical to the one Task 6 produced.

The extra scripts and their outputs are in `outputs/xlsx-header-detection/task-7/` (git-ignored). The first
revision 6 run's export is kept as `new6-429f1fd`.

| Script | What it does |
|---|---|
| `guard_trace.py` | Runs the branch's `prepare_table` on every table twice, with the guard and with `_period_row` forced to `False`. It records where the guard changes the header count and which row fired it. |
| `diff_new6.py` | Compares `new` and `new6` table by table, and compares each changed table with `base`. |
| `stacked_scan.py` | The gate 6 scans: scan A is the audit reviewer's `stacked2.py` rule, unchanged; scan B is broader. |
| `yearless_check.py` | Counts the amounts and facts under each yearless header. |
| `mixed_columns.py` | Finds columns whose facts span more than one period. |
| `show7.py`, `htmlfacts.py` | Show export tables and the filing's own HTML rows, with each fact's period. |

### Numbers: group table, base → revision 6

`compare.md`:

| Group | Files | Fallback tables | Numeric cells | Balanced columns | Lost | Changed | Promoted rows | Balanced lost | Tables missing / added |
|---|---|---|---|---|---|---|---|---|---|
| META | 18 | 408 → 66 | 8,309 → 15,176 | 28 → 36 | 0 | 0 | 775 | 0 | 0 / 0 |
| NVDA | 14 | 270 → 15 | 6,550 → 12,886 | 22 → 28 | 0 | 0 | 650 | 0 | 0 / 0 |
| RDDT | 10 | 174 → 21 | 6,092 → 8,574 | 16 → 20 | 0 | 0 | 357 | 0 | 0 / 0 |
| Others | 18 | 1004 → 654 | 9,511 → 19,402 | 23 → 37 | 89 | 14 | 1210 | 0 | 0 / 0 |

Change from revision 5:

| Group | Fallback tables after | Numeric cells after | Promoted rows | Lost | Why |
|---|---|---|---|---|---|
| META | 57 → 66 (+9) | 16,091 → 15,176 (−915) | 810 → 775 | 0 → 0 | The 9 META D1 tables fall back again, as on `main`. 4 dividend tables return to `main`'s `needs_review` output with the same numbers. |
| NVDA | 8 → 15 (+7) | 13,084 → 12,886 (−198) | 677 → 650 | 0 → 0 | 17 segment-information and Schedule II tables return to `main`'s output; 7 of them fall back. |
| RDDT | 10 → 21 (+11) | 9,407 → 8,574 (−833) | 417 → 357 | 0 → 0 | The 12 RDDT D1 tables return to `main` (11 source text, 1 `needs_review`); 6 exhibit indexes return to `main`'s headers. |
| Others | 626 → 654 (+28) | 20,887 → 19,402 (−1,485) | 1314 → 1210 | 93 → 89 | 59 tables return to `main`'s output, 28 of them to source text. TSM #105 gets back its 4 numeric rates. |

In the vault, the fallback count over the three groups goes from 852 to 102 (revision 5: 75). Task 4's CHANGELOG
figure `852 to 75` needs to become `852 to 102`.

### Guard-fired tables

`guard_trace.py` traced every table of the 60 filings at `5f779c0`. The guard fired in 169 of them.

- **107 tables differ between revision 5 and revision 6** (META 13, NVDA 17, RDDT 18, Others 59). Every one:
  - is a table where the guard fired;
  - is identical to `main` in every field the export records: title, status, issues, headers, typed rows, cell
    sources, source cells, provenance and facts.

  So no Rule 3 difference from `main` remains in them, and no cell value differs from `main`.
- **62 tables where the guard fired are source text in both revisions.** Revision 5 already fell back on them.
- **0 tables differ for any other reason.**

What fired the guard in the 107:

| Kind | Tables | Examples |
|---|---|---|
| D1, stacked equity statements | 21 | META 10-Q #9, RDDT 10-Q #8 and #9. All are back to `main`'s output: 20 source text, plus RDDT 2024-Q2 #8, `needs_review` with `Column N` headers. 0 facts are mismatched in them. |
| I1, a stranded date row | 1 | TSM #105: the `December 31, 2023 \| December 31, 2024` row. `main`'s output is back: `needs_review`, with the 4 rates as numbers. |
| Exhibit indexes with dated rows | 8 | CRM #79, MSFT #80, RDDT 10-K FY2024 #63 and #64, FY2025 #62 and #63, 10-Q 2024-Q1 #48 and 2026-Q2 #47. Rows such as `10.2(a)# \| … \| S-1 \| 2/22/2024` count as period rows. |
| A period row below the extended header | 77 | NVDA segment information: `Three Months Ended April 30, 2023` and then `… May 1, 2022` as body captions. MSFT investment tables: a `June 30, 2025` caption row below the column headings. KO, UNH and JPM year blocks. META dividends: `2025` and then `2024` section labels. JPM #159, #161 and #241: `Year ended December 31, 2022 (in millions)`. BAC #92 and #93 `(Dollars in millions) \| December 31, 2024`. Repeated header blocks (TSM #165). Period rows right under the header (NTRA #43, UNH #12, UNH #52). |

In 63 of the 77 "period row" tables, revision 5's headers had no period wording at all, in any column; the periods
sat in body caption rows. The other 14:

- **Stacked blocks with a period in the label column's header, each now source text or `main`'s output:**
  - JPM #159, #161 and #241 (the audit review's finding): the label column's header named one year, such as
    `Year ended December 31, 2023 (in millions)`, above both the 2023 block and the 2022 block.
  - JPM #194: the label column's header read `December 31, 2024` over both the 2024 and the 2023 blocks.

  Each is a D1-like risk that the all-table check could not see, because the value columns' headers name no date.
- JPM #290 had a label-column caption.
- JPM #296 had the First Republic checker-limit mismatches.
- NTRA #43, UNH #12 and UNH #52 had yearless `December 31,` or `For the Years Ended December 31,` headers, with
  their years stranded in the body (the I1 shape).
- SPCX #51 had `As of` headers, with the dates `June 30, 2026 | June 30, 2025` in the body.
- TSM #108-#110 had `First Quarter — of 2022 — NT$` headers. The guard fired on a row of board-meeting dates.
- TSM #165 repeats the same years for a second section.

None of the 85 tables outside D1 and TSM #105 had a mismatch on revision 5, apart from JPM #296's checker limits.

- **Improvements:** the four label-column stacked blocks (JPM #159, #161, #194, #241) and the four yearless
  I1-shaped tables (NTRA #43, UNH #12, UNH #52, SPCX #51).
- **Coverage cost only:** the rest. The guard fixes nothing the checks could see there.

The table below lists the 107. The last column shows the first period row the guard found below the extended
header, as source origins.

| Filing | Table | Title | Status: main → rev 5 → rev 6 | Numbers: main / rev 5 / rev 6 | Header rows: main / rev 5 | First period row below the extended header (source row: origins) |
|---|---|---|---|---|---|---|
| META 10-K 2025 | #50 | Dividend | needs_review → exported → needs_review | 32 / 32 / 32 | 0 / 2 | r2: 2025 |
| META 10-Q 2022-Q2 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 96 / 0 | 0 / 4 | r13: Six Months Ended June 30, 2022 \| Six Months Ended June 30, 2021 |
| META 10-Q 2022-Q3 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 96 / 0 | 0 / 4 | r13: Nine Months Ended September 30, 2022 \| Nine Months Ended September 30, 2021 |
| META 10-Q 2023-Q2 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 96 / 0 | 0 / 4 | r13: Six Months Ended June 30, 2023 \| Six Months Ended June 30, 2022 |
| META 10-Q 2023-Q3 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 96 / 0 | 0 / 4 | r13: Nine Months Ended September 30, 2023 \| Nine Months Ended September 30, 2022 |
| META 10-Q 2024-Q2 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 100 / 0 | 0 / 4 | r14: Six Months Ended June 30, 2024 \| Six Months Ended June 30, 2023 |
| META 10-Q 2024-Q3 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 104 / 0 | 0 / 4 | r15: Nine Months Ended September 30, 2024 \| Nine Months Ended September 30, 2023 |
| META 10-Q 2025-Q1 | #22 | Dividend | needs_review → exported → needs_review | 20 / 20 / 20 | 0 / 2 | r2: 2025 |
| META 10-Q 2025-Q2 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 108 / 0 | 0 / 4 | r15: Six Months Ended June 30, 2025 \| Six Months Ended June 30, 2024 |
| META 10-Q 2025-Q2 | #22 | Dividend | needs_review → exported → needs_review | 24 / 24 / 24 | 0 / 2 | r2: 2025 |
| META 10-Q 2025-Q3 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 117 / 0 | 0 / 4 | r15: Nine Months Ended September 30, 2025 \| Nine Months Ended September 30, 2024 |
| META 10-Q 2025-Q3 | #25 | Dividend | needs_review → exported → needs_review | 28 / 28 / 28 | 0 / 2 | r2: 2025 |
| META 10-Q 2026-Q2 | #9 (D1) | CONDENSED CONSOLIDATED STATEMENTS OF STOCKHOL | source text → needs_review → source text | 0 / 102 / 0 | 0 / 4 | r15: Six Months Ended June 30, 2026 \| Six Months Ended June 30, 2025 |
| NVDA 10-K 2024 | #54 | Note 17 - Segment Information | needs_review → exported → needs_review | 21 / 21 / 21 | 0 / 2 | r4: Year Ended Jan 28, 2024: |
| NVDA 10-K 2024 | #59 | Schedule II – Valuation and Qualifying Accoun | needs_review → needs_review → needs_review | 28 / 28 / 28 | 0 / 2 | r4: Fiscal year 2024 |
| NVDA 10-K 2025 | #53 | Note 16 - Segment Information | source text → exported → source text | 0 / 27 / 0 | 0 / 2 | r4: Year Ended Jan 26, 2025 |
| NVDA 10-K 2025 | #61 | Schedule II – Valuation and Qualifying Accoun | needs_review → needs_review → needs_review | 28 / 28 / 28 | 0 / 2 | r4: Fiscal year 2025 |
| NVDA 10-K 2026 | #50 | Note 16 - Segment Information | source text → exported → source text | 0 / 27 / 0 | 0 / 2 | r4: Year Ended Jan 25, 2026 |
| NVDA 10-K 2026 | #57 | Schedule II – Valuation and Qualifying Accoun | needs_review → needs_review → needs_review | 29 / 29 / 29 | 0 / 2 | r4: Fiscal year 2026 |
| NVDA 10-Q 2024-Q1 | #31 | Note 15 - Segment Information | needs_review → exported → needs_review | 14 / 14 / 14 | 0 / 2 | r4: Three Months Ended April 30, 2023 |
| NVDA 10-Q 2024-Q2 | #32 | Note 15 - Segment Information | needs_review → exported → needs_review | 28 / 28 / 28 | 0 / 2 | r4: Three Months Ended July 30, 2023 |
| NVDA 10-Q 2024-Q3 | #32 | Note 15 - Segment Information | needs_review → exported → needs_review | 28 / 28 / 28 | 0 / 2 | r4: Three Months Ended October 29, 2023 |
| NVDA 10-Q 2025-Q1 | #33 | Note 14 - Segment Information | needs_review → exported → needs_review | 14 / 14 / 14 | 0 / 2 | r4: Three Months Ended Apr 28, 2024 |
| NVDA 10-Q 2025-Q2 | #33 | Note 14 - Segment Information | needs_review → exported → needs_review | 28 / 28 / 28 | 0 / 2 | r4: Three Months Ended Jul 28, 2024 |
| NVDA 10-Q 2025-Q3 | #33 | Note 14 - Segment Information | needs_review → exported → needs_review | 28 / 28 / 28 | 0 / 2 | r4: Three Months Ended Oct 27, 2024 |
| NVDA 10-Q 2026-Q1 | #29 | Note 13 - Segment Information | source text → exported → source text | 0 / 18 / 0 | 0 / 2 | r4: Three Months Ended Apr 27, 2025 |
| NVDA 10-Q 2026-Q2 | #29 | Note 13 - Segment Information | source text → exported → source text | 0 / 36 / 0 | 0 / 2 | r4: Three Months Ended Jul 27, 2025 |
| NVDA 10-Q 2026-Q3 | #28 | Note 13 - Segment Information | source text → exported → source text | 0 / 36 / 0 | 0 / 2 | r4: Three Months Ended Oct 26, 2025 |
| NVDA 10-Q 2027-Q1 | #26 | Note 13 - Segment Information | source text → exported → source text | 0 / 18 / 0 | 0 / 2 | r4: Three Months Ended Apr 26, 2026 |
| NVDA 10-Q 2027-Q2 | #29 | Note 13 - Segment Information | source text → exported → source text | 0 / 36 / 0 | 0 / 2 | r4: Three Months Ended Jul 26, 2026 |
| RDDT 10-K 2024 | #63 | Item 15. Exhibits and Financial Statement Sch | needs_review → exported → needs_review | 0 / 0 / 0 | 0 / 2 | r15: 10.5(a)# \| 2012 Stock Option and Grant Plan, as amended \| S-1 \| 2/22/2024 … |
| RDDT 10-K 2024 | #64 | Exhibit Number | needs_review → exported → needs_review | 0 / 0 / 0 | 0 / 2 | r2: 10.5(f)# \| Form of Restricted Stock Award Grant Notice a \| S-1 \| 2/22/2024 … |
| RDDT 10-K 2025 | #62 | Item 15. Exhibits and Financial Statement Sch | needs_review → exported → needs_review | 0 / 0 / 0 | 0 / 2 | r12: 10.4(a)# \| 2012 Stock Option and Grant Plan, as amended \| S-1 \| 2/22/2024 … |
| RDDT 10-K 2025 | #63 | Exhibit Number | needs_review → needs_review → needs_review | 0 / 0 / 0 | 0 / 2 | r2: 10.12(c)# \| Form of Restricted Stock Unit Award Grant Not \| S-1 \| 2/22/2024 … |
| RDDT 10-Q 2024-Q1 | #48 | Item 6. Exhibits | needs_review → exported → needs_review | 0 / 0 / 0 | 0 / 2 | r10: 10.2(a)# \| 2017 Equity Incentive and Grant Plan, as amen \| S-1 \| 2/22/2024 … |
| RDDT 10-Q 2024-Q2 | #8 (D1) | Consolidated Statements of Convertible Prefer | needs_review → needs_review → needs_review | 67 / 67 / 67 | 0 / 4 | r14: Three months ended June 30, 2024 |
| RDDT 10-Q 2024-Q2 | #9 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 83 / 0 | 0 / 5 | r14: Six months ended June 30, 2024 |
| RDDT 10-Q 2024-Q3 | #8 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 69 / 0 | 0 / 5 | r14: Three months ended September 30, 2024 |
| RDDT 10-Q 2024-Q3 | #9 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 86 / 0 | 0 / 5 | r14: Nine months ended September 30, 2024 |
| RDDT 10-Q 2025-Q1 | #8 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 81 / 0 | 0 / 5 | r17: Three months ended March 31, 2025 |
| RDDT 10-Q 2025-Q2 | #8 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 69 / 0 | 0 / 5 | r17: Three months ended June 30, 2025 |
| RDDT 10-Q 2025-Q2 | #9 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 83 / 0 | 0 / 5 | r17: Six months ended June 30, 2025 |
| RDDT 10-Q 2025-Q3 | #8 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 72 / 0 | 0 / 5 | r17: Three months ended September 30, 2025 |
| RDDT 10-Q 2025-Q3 | #9 (D1) | Consolidated Statements of Convertible Prefer | source text → needs_review → source text | 0 / 87 / 0 | 0 / 5 | r18: Nine months ended September 30, 2025 |
| RDDT 10-Q 2026-Q1 | #8 (D1) | Consolidated Statements of Stockholders’ Equi | source text → needs_review → source text | 0 / 68 / 0 | 0 / 5 | r15: Three months ended March 31, 2026 |
| RDDT 10-Q 2026-Q2 | #8 (D1) | Consolidated Statements of Stockholders’ Equi | source text → needs_review → source text | 0 / 67 / 0 | 0 / 5 | r15: Three months ended June 30, 2026 |
| RDDT 10-Q 2026-Q2 | #9 (D1) | Consolidated Statements of Stockholders’ Equi | source text → needs_review → source text | 0 / 68 / 0 | 0 / 5 | r14: Six months ended June 30, 2026 |
| RDDT 10-Q 2026-Q2 | #47 | Item 6. Exhibits | needs_review → exported → needs_review | 0 / 0 / 0 | 0 / 2 | r9: 10.1# \| Amended and Restated Employment Offer Letter  \| 10-Q \| 5/1/2026 … |
| BABA-20-F | #40 | As of March 31, 2024 and 2025, the Company’s  | needs_review → needs_review → needs_review | 8 / 8 / 8 | 0 / 3 | r4: For the year ending March 31, |
| BABA-20-F | #65 | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOL | needs_review → exported → needs_review | 7 / 7 / 7 | 0 / 3 | r4: For the year ending March 31, |
| BAC-10-K | #92 | (Dollars in millions) | source text → needs_review → source text | 0 / 100 / 0 | 0 / 3 | r3: (Dollars in millions) \| December 31, 2024 |
| BAC-10-K | #93 | (Dollars in millions) | source text → needs_review → source text | 0 / 100 / 0 | 0 / 3 | r3: (Dollars in millions) \| December 31, 2023 |
| CRM-10-K | #79 | Exhibit No. | needs_review → needs_review → needs_review | 0 / 0 / 0 | 0 / 2 | r22: 10.26* \| Amendment to Transition Agreement, dated Marc \| X |
| JPM-10-K | #137 | Year ended December 31, 2024 (in millions) | source text → source text → source text | 0 / 0 / 0 | 0 / 4 | r40: Year ended December 31, 2024 (in millions) \| Fair value at Jan. 1, 2024 \| Total realized/unrealized (gains)/losses \| Transfers (out of) level 3 … |
| JPM-10-K | #138 | Notes to consolidated financial statements | source text → source text → source text | 0 / 0 / 0 | 0 / 4 | r40: Year ended December 31, 2023 (in millions) \| Fair value at Jan. 1, 2023 \| Total realized/unrealized (gains)/losses \| Transfers (out of) level 3 … |
| JPM-10-K | #139 | Year ended December 31, 2022 (in millions) | source text → source text → source text | 0 / 0 / 0 | 0 / 4 | r40: Year ended December 31, 2022 (in millions) \| Fair value at Jan. 1, 2022 \| Total realized/unrealized (gains)/losses \| Transfers into level 3 … |
| JPM-10-K | #159 | December 31, 2024 (in millions) | needs_review → needs_review → needs_review | 20 / 20 / 20 | 0 / 3 | r10: December 31, 2023 (in millions) \| Carrying amount of the hedged items(a)(b) \| Active hedging relationships \| Discontinued hedging relationships(e) … |
| JPM-10-K | #161 | Year ended December 31, 2023 (in millions) | source text → exported → source text | 0 / 18 / 0 | 0 / 3 | r9: Year ended December 31, 2022 (in millions) \| Amounts reclassified from AOCI to income \| Amounts recorded in OCI \| Total change in OCI for period |
| JPM-10-K | #194 | Retained | source text → exported → source text | 0 / 28 / 0 | 0 / 3 | r8: December 31, 2023 \| Consumer, excluding credit card \| Credit card \| Wholesale … |
| JPM-10-K | #230 | Payment status of FDMs | source text → needs_review → source text | 0 / 23 / 0 | 0 / 3 | r3: (in millions) \| Year ended December 31, 2024 \| Year ended December 31, 2023 |
| JPM-10-K | #231 | Defaults of FDMs | source text → needs_review → source text | 0 / 16 / 0 | 0 / 3 | r3: (in millions) \| Year ended December 31, 2024 \| Year ended December 31, 2023 |
| JPM-10-K | #241 | Consolidated VIE assets and liabilities | source text → exported → source text | 0 / 77 / 0 | 0 / 3 | r12: December 31, 2023 (in millions) \| Trading assets \| Loans \| Other(c) … |
| JPM-10-K | #290 | Note 31 – International operations | source text → needs_review → source text | 0 / 90 / 0 | 0 / 2 | r2: 2024 |
| JPM-10-K | #296 | Notes to consolidated financial statements | source text → exported → source text | 0 / 19 / 0 | 0 / 2 | r2: (in millions) \| Fair value purchase price allocation as of Ma |
| KO-10-K | #33 | Net operating revenues disaggregated between  | source text → exported → source text | 0 / 27 / 0 | 0 / 2 | r2: Year Ended December 31, 2024 |
| KO-10-K | #34 | Equity Securities | source text → exported → source text | 0 / 10 / 0 | 0 / 2 | r2: December 31, 2024 |
| KO-10-K | #36 | Debt Securities | source text → exported → source text | 0 / 23 / 0 | 0 / 3 | r3: December 31, 2024 |
| KO-10-K | #42 | Pretax impact that changes in the fair values | source text → exported → source text | 0 / 35 / 0 | 0 / 2 | r2: 2024 |
| KO-10-K | #50 | NOTE 7: GOODWILL | source text → exported → source text | 0 / 46 / 0 | 0 / 2 | r2: 2023 |
| KO-10-K | #76 | Income taxes | source text → exported → source text | 0 / 24 / 0 | 0 / 2 | r2: 2024 |
| KO-10-K | #83 | The following tables present OCI attributable | source text → exported → source text | 0 / 43 / 0 | 0 / 2 | r2: 2024 |
| KO-10-K | #85 | Foreign currency translation adjustments | source text → exported → source text | 0 / 42 / 0 | 0 / 2 | r2: 2022 |
| KO-10-K | #91 | The following table provides a reconciliation | source text → exported → source text | 0 / 37 / 0 | 0 / 2 | r2: 2023 |
| KO-10-K | #92 | Productivity and Reinvestment Program | source text → exported → source text | 0 / 42 / 0 | 0 / 2 | r2: 2022 |
| KO-10-K | #96 | Year Ended December 31, 2024 | source text → exported → source text | 0 / 72 / 0 | 0 / 2 | r2: Year Ended December 31, 2024 |
| KO-10-K | #98 | Year Ended December 31, 2022 | source text → exported → source text | 0 / 73 / 0 | 0 / 2 | r2: Year Ended December 31, 2022 |
| MSFT-10-K | #32 | Investment Components | needs_review → needs_review → needs_review | 101 / 101 / 101 | 0 / 2 | r4: June 30, 2025 |
| MSFT-10-K | #33 | Changes in Fair Value Recorded in Other Compr | needs_review → needs_review → needs_review | 101 / 101 / 101 | 0 / 2 | r4: June 30, 2024 |
| MSFT-10-K | #34 | Unrealized Losses on Debt Investments | needs_review → exported → needs_review | 36 / 36 / 36 | 0 / 5 | r7: June 30, 2025 |
| MSFT-10-K | #35 | U.S. government and agency securities | needs_review → needs_review → needs_review | 36 / 36 / 36 | 0 / 2 | r7: June 30, 2024 |
| MSFT-10-K | #36 | Debt Investment Maturities | needs_review → exported → needs_review | 10 / 10 / 10 | 0 / 2 | r4: June 30, 2025 |
| MSFT-10-K | #38 | Fair Values of Derivative Instruments | needs_review → needs_review → needs_review | 62 / 62 / 62 | 0 / 2 | r5: June 30, 2025 \| June 30, 2024 |
| MSFT-10-K | #39 | Fair value of our derivatives instruments on  | needs_review → needs_review → needs_review | 14 / 14 / 14 | 0 / 2 | r4: June 30, 2025 |
| MSFT-10-K | #47 | The components of intangible assets, all of w | source text → exported → source text | 0 / 32 / 0 | 0 / 2 | r4: June 30, \| 2025 \| 2024 |
| MSFT-10-K | #48 | The components of intangible assets acquired  | source text → needs_review → source text | 0 / 12 / 0 | 0 / 2 | r4: Year Ended June 30, \| 2025 \| 2024 |
| MSFT-10-K | #80 | Exhibit Number | needs_review → needs_review → needs_review | 0 / 0 / 0 | 0 / 2 | r19: 10.2* \| Microsoft Corporation Employee Stock Purchase \| DEF14A \| Annex A … |
| MU-10-K | #38 | Note 17. Derivative Instruments | source text → exported → source text | 0 / 29 / 0 | 0 / 3 | r4: As of August 28, 2025 |
| NTRA-10-K | #32 | The present value of the future minimum lease | needs_review → exported → needs_review | 9 / 9 / 9 | 0 / 2 | r3: Year ending December 31: |
| NTRA-10-K | #43 | The following table shows the potentially dil | needs_review → needs_review → needs_review | 15 / 15 / 15 | 0 / 2 | r2: 2024 \| 2023 \| 2022 |
| SPCX-10-Q | #51 | AI | needs_review → needs_review → needs_review | 0 / 0 / 0 | 0 / 3 | r4: (in gigawatts) \| June 30, 2026 \| June 30, 2025 |
| TSM-20-F | #59 | The detail information of the subsidiaries at | needs_review → needs_review → needs_review | 12 / 12 / 12 | 0 / 2 | r2: Name of Investor \| Name of Investee \| Main Businesses and Products \| Establishment and Operating Location … |
| TSM-20-F | #78 | Associates | needs_review → needs_review → needs_review | 18 / 18 / 18 | 0 / 2 | r2: Name of Associate \| Principal Activities \| Incorporation and Operation \| December 31, 2023 … |
| TSM-20-F | #105 (I1) | The actuarial valuations of the present value | needs_review → exported → needs_review | 4 / 0 / 4 | 0 / 2 | r2: December 31, 2023 \| December 31, 2024 |
| TSM-20-F | #108 | Th e appropriations of 2022, 2023 and 2024 qu | needs_review → needs_review → needs_review | 9 / 9 / 9 | 0 / 4 | r7: Resolution date of TSMC’s Board of Directors  \| May 10, 2022 \| August 9, 2022 \| November 8, 2022 … |
| TSM-20-F | #109 | Resolution date of TSMC’s Board of Directors  | needs_review → needs_review → needs_review | 10 / 10 / 10 | 0 / 4 | r7: Resolution date of TSMC’s Board of Directors  \| May 9, 2023 \| August 8, 2023 \| November 14, 2023 … |
| TSM-20-F | #110 | Resolution date of TSMC’s Board of Directors  | needs_review → needs_review → needs_review | 8 / 8 / 8 | 0 / 4 | r7: Resolution date of TSMC’s Board of Directors  \| May 10, 2024 \| August 13, 2024 \| November 12, 2024 … |
| TSM-20-F | #155 | Non-derivative financial liabilities | needs_review → exported → needs_review | 31 / 31 / 31 | 0 / 2 | r5: December 31, 2023 |
| TSM-20-F | #156 | Derivative financial instruments | needs_review → exported → needs_review | 51 / 51 / 51 | 0 / 2 | r17: December 31, 2024 |
| TSM-20-F | #157 | Lease liabilities | needs_review → exported → needs_review | 10 / 10 / 10 | 0 / 2 | r5: December 31, 2023 |
| TSM-20-F | #165 | Item | needs_review → needs_review → needs_review | 13 / 13 / 13 | 3 / 4 | r11: Years Ended December 31 |
| UNH-10-K | #12 | Number of individuals served by our UnitedHea | needs_review → needs_review → needs_review | 55 / 55 / 55 | 0 / 2 | r2: (in thousands, except percentages) \| 2024 \| 2023 \| 2022 … |
| UNH-10-K | #27 | 3. Investments | source text → exported → source text | 0 / 80 / 0 | 0 / 2 | r2: December 31, 2024 |
| UNH-10-K | #29 | The fair value of available-for-sale debt sec | source text → exported → source text | 0 / 72 / 0 | 0 / 3 | r3: December 31, 2024 |
| UNH-10-K | #30 | A summary of fair value measurements by level | source text → exported → source text | 0 / 68 / 0 | 0 / 2 | r2: December 31, 2024 |
| UNH-10-K | #31 | A summary of fair value measurements by level | needs_review → exported → needs_review | 14 / 14 / 14 | 0 / 2 | r2: December 31, 2024 |
| UNH-10-K | #52 | Share-Based Compensation Recognition and Esti | needs_review → needs_review → needs_review | 4 / 4 / 4 | 0 / 2 | r2: 2024 \| 2023 \| 2022 |
| UNH-10-K | #55 | Reportable segment financial information | source text → exported → source text | 0 / 251 / 0 | 0 / 3 | r3: 2024 |

The 62 guard-fired tables that are source text on both revisions:

BAC-10-K #18, #113, #134; CAT-10-K #19, #36, #49, #60, #61, #70, #72, #73, #82, #84, #85, #97; GOOGL-10-Q #41; JPM-10-K #37, #38, #81, #90, #106, #152, #158, #163, #190, #205, #206, #212, #214, #215, #216, #217, #218, #219, #220, #221, #222, #223, #247; KO-10-K #40, #41, #44, #63, #64, #67, #68, #69, #70, #71, #72, #89; MSFT-10-K #64; TSLA-10-K #35; TSM-20-F #29, #30, #72; UNH-10-K #9, #10, #11, #13, #38, #39.

### Primary statements (Acceptance 3)

`statements.md` is unchanged from revision 5. `statements-new6.json` equals revision 5's `statements.json` field by
field.

| | Statements | Exported | XBRL facts | OK | Label-column facts | Failures | Untagged | Repeated | Yearless | Arithmetic | Ambiguous | Not found |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| META | 54 | 54 | 3,448 | 3,322 | 126 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| NVDA | 42 | 42 | 2,683 | 2,662 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| RDDT | 30 | 30 | 2,228 | 2,056 | 172 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Others | 41 found | 26 (+3 needs_review, 12 source_text_only) | 3,242 | 2,099 | | 976 fallback, 2 not numeric | 10 | 0 | 1 | 0 | 1 | 13 |

Totals: facts 11,601, ok 10,139, failures 978, untagged 10, repeated 3, yearless 1, arithmetic 0, ambiguous 1,
not found 13. The 3 repeated cells are in META's FY2023 10-K cash flow statement. The readings of the other filings'
statements under "Other filings' primary statements, read one by one" still hold.

The seven spot-check tables of Acceptance 6 are identical to revision 5's output, so the spot checks above still
hold:

- META FY2024 10-K #22, #9, #23 and #33;
- META Q1 2025 10-Q #7;
- NVDA FY2024 Q2 10-Q #6;
- RDDT Q2 2025 10-Q #39.

### All-table XBRL period check (Acceptance 3b), base vs revision 6

`all-facts.md`:

| Run | Group | Tables | Facts | ok | mismatch | unparsed length | no header date | label column | not placed |
|---|---|---|---|---|---|---|---|---|---|
| base | META | 456 | 6,813 | 6,431 | 0 | 0 | 284 | 98 | 0 |
| base | NVDA | 397 | 5,865 | 5,030 | 19 | 0 | 727 | 89 | 0 |
| base | RDDT | 312 | 4,034 | 3,666 | 0 | 0 | 232 | 136 | 0 |
| base | Others | 681 | 8,758 | 4,801 | 7 | 0 | 3,833 | 117 | 0 |
| base | Total | 1,846 | 25,470 | 19,928 | 26 | 0 | 5,076 | 440 | 0 |
| rev 6 | META | 798 | 12,958 | 10,277 | 0 | 0 | 2,553 | 128 | 0 |
| rev 6 | NVDA | 652 | 11,308 | 8,808 | 25 | 0 | 2,224 | 251 | 0 |
| rev 6 | RDDT | 465 | 6,002 | 5,087 | 0 | 0 | 743 | 172 | 0 |
| rev 6 | Others | 1,031 | 17,787 | 11,103 | 79 | 0 | 6,338 | 267 | 0 |
| rev 6 | Total | 2,946 | 48,055 | 35,275 | 104 | 0 | 11,858 | 818 | 0 |

The other lists in the check compare as follows:

| List | base | rev 5 | rev 6 |
|---|---|---|---|
| Mismatches | 26 facts in 11 tables | 975 in 47 | 104 in 25 |
| Yearless-header tables | 15 | 117 | 112 |
| Unlocated-fact tables | 5 | 7 | 7 |
| Unparsed-length headers | 0 | 249 in 79 tables | 249 in 79 tables |

Between the first revision 6 run (`429f1fd`) and the final one, only JPM #161 and #241 change these counts: their
102 `no header date` facts left with the tables. Revision 6's 249 unparsed-length headers are the same as
revision 5's. They are 226 aging-bucket headers, whose
facts are all `ok` instants at the header date, and 23 useful-life columns with no facts.

**Mismatches, every one classified.** None is a real misattribution.

Existing on `main` (the same 26 facts in the same 11 tables on `base` and on revision 6):

| Table | Facts | Source cells | Verdict |
|---|---|---|---|
| CRDO 10-K #44, #46 | 3 + 2 | r2 `Beginning valuation allowance \| 23,258 \| 9,306 \| 5,170` (instants 2024-04-27, 2023-04-29, 2022-04-30) under `May 3, 2025 \| April 27, 2024 \| April 29, 2023`; #46 the same for unrecognized tax benefits | Checker limit: opening balances under the bare year-end date. |
| NVDA 10-K FY2024 #44, #53; FY2025 #43, #52; FY2026 #39, #49; 10-Q 2025-Q1 #20, #28 | 19 | `Balance at beginning of period`, e.g. FY2024 #44 r4 `572 \| 502` (instants 2023-01-29, 2022-01-30) under `Jan 28, 2024 \| Jan 29, 2023` | Checker limit: opening balances. |
| TSM 20-F #135 | 2 | r4 `No expiry date \| $ 640.0 \| $ 11,896.9` under `December 31, 2023 \| December 31, 2024`. In the filing's HTML, `640.0` carries context `PAsOn12_31_2024` and `11,896.9` carries `PAsOn12_31_2023`. Every other fact in the table is tagged with its own column's date (`2,781.4` and `52,686.2` with 2023, `83,705.6` with 2024). | The filing's own tags disagree with its columns. The export places each number in the column the filing shows. Not an export misattribution. |

New on the branch: 14 tables, each with the same count on revision 5. 13 of them fall back on `main`; AMZN #23 is
`needs_review` on `main`, with yearless headers, so its facts there have no header date:

| Table | Facts | Source cells | Verdict |
|---|---|---|---|
| AMZN 10-Q #19 Commitments | 32 | The filing heads the columns `Year Ended December 31,` over `2026 … 2029`; r3 `Long-term debt principal and interest \| … \| 4,518` (an instant at 2025-09-30, `…InYearOne`) under `Year Ended December 31, — 2026` | Checker limit: a maturity schedule. The header names the year the amount falls due. |
| AMZN 10-Q #23 Scheduled vesting | 4 | `112.8 \| 70.9 \| 29.7 \| 8.3` (instants at 2025-09-30, `…VestingYearOne…Four`) under `Year Ended December 31, — 2026 … 2029` | Checker limit: a vesting schedule. On `base` this table was yearless; it now carries the years. |
| JPM 10-K #297 Loans (First Republic) | 16 | The filing reads `May 1, 2023` over `UPB \| Fair value`; r4 `106,240 \| 92,053` carry context 2024-12-31 | Checker limit: JPM tags the acquisition-date amounts with its reporting-date context. Each number sits under the filing's own header. |
| MU 10-K #22 cash flow statement | 3 | r38 `Cash … at beginning of period \| 7,052 \| 8,656 \| 8,339` (instants 2024-08-29, 2023-08-31, 2022-09-01) under `August 28, 2025 \| August 29, 2024 \| August 31, 2023`. `For the year ended` sits in column 0. Closing cash: 7,052 + 2,594 = 9,646. | Checker limit: opening cash. |
| NFLX 10-K #70 | 3 | `Balance at the beginning of the year \| 327,105 \| 226,977 \| 202,557` (instants at the prior year ends) under `As of December 31, — 2024 / 2023 / 2022` | Checker limit: opening balances. |
| NTRA 10-K #15, #16, #21, #26, #30, #42 | 14 | `Beginning balance` or `Balance at beginning of year`, e.g. #15 r4 `872 \| 748` (instants 2023-12-31, 2022-12-31) under `December 31, — 2024 \| — 2023` | Checker limit: opening balances. |
| NVDA 10-Q 2024-Q1 #26, 2024-Q2 #27, 2024-Q3 #27 Deferred revenue | 6 | e.g. 2024-Q1 #26: r1 `April 30, \| May 1,` over r2 `2023 \| 2022`; r5 `Balance at beginning of period \| 572 \| 502` (instants 2023-01-29, 2022-01-30). Closing balance: 597 and 537. | Checker limit: opening balances. |

Revision 5's other mismatch tables are gone. JPM #296 is source text again, and the 21 D1 tables are `main`'s output
with 0 mismatches.

**Yearless period headers, every one classified.** `base` has 15 tables, revision 5 had 117 and revision 6 has
112.

- **Existing (14).** They are on `base`, and their yearless header cells are identical:
  - BABA #23, #33, #37, #41, #50, #61; CRDO #26; META FY2025 10-K #57; NTRA #33, #36; SPCX #47, #48, #50; TSM #99.
  - Other header cells or the status differ in 7 of them:
    - BABA #33, #37, #41, #50 and #61 gained an `RMB` caption on their dated headers
      (`Year ended March 31, — 2023 — RMB`);
    - TSM #99 gained `NT$ (In Millions)`;
    - NTRA #36 went from `exported` to `needs_review`. Its values are the same, but Rule 3 removed the identifier
      veto, so `5.20` under `Year ended December 31,` is now flagged "Numeric role unresolved" instead of
      silent text.
  - The other `base` table, AMZN #23, now carries the years.
  - **No amounts under the yearless header (9): harmless.** BABA ×6, META #57, NTRA #36 and TSM #99. The yearless
    header is a spacer column with no number and no digit text, for example BABA #33's `Year ended March 31,` between
    the `2023` and `2024` columns.
  - **Amounts under the yearless header (5): an existing risk on `main`, unchanged by the branch.** In each, `main`
    leaves the date or year row in the first body row:
    - CRDO #26: `Year Ended` over the dates `May 3, 2025 | April 27, 2024 | April 29, 2023` (6 facts);
    - NTRA #33: `Year Ended December 31,` over `2025 … 2030 and thereafter` (23 commitment facts);
    - SPCX #47, #48 and #50: `Three Months Ended` / `Six Months Ended` over `June 30, 2026 | June 30, 2025`. These
      amounts are flagged text, except SPCX #50's ARPU.

    Every one is `needs_review`.
- **New on the branch (98).** Each is on revision 5 with identical headers, and all 98 tables are identical between
  the two revision 6 runs. 5 of revision 5's tables are gone: JPM
  #290, NTRA #43, SPCX #51, UNH #12 and UNH #52, which the guard returned to `main`'s output.
  - **Harmless, column 0 only (23):**
    - JPM #32, #65, #69, #113, #117, #148, #150, #183, #243, #271, #283, #285;
    - MU #18, #19, #20, #22, #24, #25, #26, #29, #32, #52, #64.

    These are stub captions in the label column (`December 31, (in millions)`, `Three months ended (in millions,
    except ratios)`, `For the year ended`, `As of`). Every value header carries its year, except JPM #65's
    `Capital ratio requirements(c)`, which is not a period. The digit-bearing column-0 cells are row labels, such
    as `+100 bps shift in rates` and MU #20's share-count label holding 8 label-column facts.
  - **Harmless, no amounts under the yearless header (11):**
    - BABA #63, #64, #67, #73 and #81: `As of March 31,`, over a lone `)`;
    - TSM #8-#12: `For the year ended December 31,`, over `%` and `)%` signs only;
    - JPM #266: `Dividend declared per share(d) — Year ended December 31,`, over the footnote markers `(e)`-`(h)`.
  - **Amounts under the yearless header, NVDA change columns (58 tables):**
    - The headers read `Year Ended — $ Change`, `— % Change`, `— Change`, and
      `Three/Six/Nine Months Ended — $ Change / % Change`.
    - Example, NVDA 10-Q 2025-Q2 #40:
      - r1 `Three Months Ended` (span 21) over r2 `Jul 28, 2024 | Jul 30, 2023 | $ Change | % Change`;
      - r5 `Compute & Networking | 26,446 | 10,402 | 16,044 | 154 %`, where 16,044 = 26,446 − 10,402.
    - The filing heads these columns the same way. Their values are differences between the two dated columns of
      the same block, not one period's amounts, and none is an XBRL fact.
    - Checked: every numeric `$ Change` (219 cells) equals the difference of its block's two dated columns, and every
      numeric `% Change` (134 cells) matches their ratio. 573 rows were skipped because an operand is text, blank or a dash.
    - Risk: low. The compared years are only in the neighbouring headers. **Called out.**
    - The mixed-scale gap also shows here. NVDA 10-Q 2024-Q1 #38 is `exported` with no issues, yet its
      `Three Months Ended — % Change` column holds 4 cells in percentage points (`16`, `7`, `—`, `−30`, with the `%`
      sign in a separate column) beside fractions (`0.26`, `0.20`) in the dated columns' `% of net revenue` rows.
      NVDA 10-Q 2024-Q3 #40 (`needs_review`) has one such cell, `Total` `552`.
  - **Amounts under the yearless header, CRM percent-of-revenue columns (6 tables): a misattribution risk.**
    - CRM #10, #11, #14, #15, #16 and #17.
    - The headers read `Fiscal Year Ended January 31, — % of Total Revenues`, `— As a % of Total …` and
      `— Growth Rate`.
    - Source, CRM #10: r1 `Fiscal Year Ended January 31,` (span 33) over r2
      `2025 | % of Total Revenues | 2024 | % of Total Revenues | 2023 | % of Total Revenues`.
    - Each percentage belongs to one fiscal year, but its header names no year. The year is only in the header of
      the amount column to its left, as in the filing.
    - Checked in #14 and #15: each percentage equals its row's amount over the total of the year to its left.
    - No XBRL facts. These tables were source text on `main`. They are `needs_review` now, because the first row of
      a column shows `%` and the rows below are plain points (concern C2) and some roles are unresolved. Copied
      into a sheet, a `% of Total Revenues` column does not say which year it belongs to.
    - **Called out; needs the user's acceptance.**

**Tables with numeric-fact cells but no located facts.** `base` has 5 and revision 6 has 7, the same 7 as revision
5. Each appears twice in its filing, once untagged, so its provenance is `ambiguous`. Each was checked by hand
against the filing's tagged copy:

| Table | Group | Check against the filing |
|---|---|---|
| NVDA 10-K FY2025 #56, direct customers (existing) | vault | Headers `Year Ended — Jan 26, 2025 \| — Jan 28, 2024`. Values `0.12, 0.11, 0.11 \| *, 0.13, *`. The filing's tagged copy (HTML table 58) has `12 %, 11 %, 11 %` for 2024-01-29..2025-01-26 and `13 %` for 2023-01-30..2024-01-28. **Pass.** |
| NVDA 10-Q 2025-Q2 #36 (existing) | vault | `Three Months Ended — Jul 28, 2024`: 0.14, 0.11, 0.11, 0.10, `*`. `Six Months Ended — Jul 28, 2024`: 0.14, `*`, `*`, 0.10, 0.10. HTML table 39 tags the first set 2024-04-29..2024-07-28 and the second 2024-01-29..2024-07-28. **Pass.** |
| NVDA 10-Q 2025-Q3 #36 (existing) | vault | `Three Months Ended — Oct 27, 2024`: 0.12, 0.12, 0.12, `*`. `Nine Months Ended — Oct 27, 2024`: `*`, 0.11, 0.11, 0.12. HTML table 39 tags 2024-07-29..2024-10-27 and 2024-01-29..2024-10-27. **Pass.** |
| CRM #69 (existing) | others | `2025 — Shares \| Average price per share \| Amount` = 30, 260.12, 7,757, and the same for 2024 and 2023. Matches HTML table 74. |
| CRM #70 (existing) | others | `Record Date \| Payment Date \| Dividend per Share \| Amount` rows. Matches HTML table 75. |
| GOOGL 10-Q #13 (new) | others | All 40 values match HTML table 27, with three- and nine-month facts for 2024 and 2025 under the matching headers. |
| GOOGL 10-Q #48 (new) | others | All 12 values match HTML table 67, with the same periods. |

**Extra check: columns mixing periods (corrected after the audit review).**

- **Method.** For each copy column, `mixed_columns.py` collects the periods of its facts. A column that holds more
  than one duration, or instants at more than two dates, is listed.
- **What was wrong.** The first record then checked only the listed column's own header for a year, and ignored the
  label column's header. So it missed JPM #161, even though its own review list had flagged #161; the record then
  dropped it.
- **The correction.** The check now also looks for period wording in the label column's header: a year, a month and
  day, `ended`, `ending`, `as of` or `as at`.
- **Validation.** On revision 5 the corrected check flags 23 tables: the 21 D1 tables, JPM #161 and JPM #290. On the
  first revision 6 run it flags JPM #161.
- **Final run.** 75 tables have a listed column, and 59 of them differ from `main` in headers or status. None of the
  59 has period wording in the label column's header or in the listed column's header. They are equity statements,
  roll-forwards and segment tables whose column headings name no period; their periods come from rows such as
  `Balance as of December 31, 2023`, as in the filings.
- **Limit.** A column whose instants fall on only two dates is not listed. So JPM #159 and #241, with one instant per
  block (2024-12-31 and 2023-12-31), passed this check even on the first run. The check supports gate 6; the
  structural scans below catch these tables, and the check does not replace them.

### Gate 6: stacked period blocks

`stacked_scan.py` runs two scans over every table that is not `source_text_only`, and lists hits on the branch that
are not also on `main`.

**Scan A** is the audit reviewer's `stacked2.py` rule, unchanged.

- **Rule.** The headers name a year, the label column's header included. A body row holds no number but has a dated
  caption: a bare year, a full date, `ended`, `ending` or `as of` with a year, or `fiscal`, `FY` or `year` with a
  year. Numbers follow below that row.
- **Results:**

  | Run | Hits | Not on `base` |
  |---|---|---|
  | `base` | 1 (TSM #165) | |
  | revision 5 | 29 | 28: the 21 D1 tables, JPM #159, #161, #194 and #241, and TSM #108-#110 |
  | first revision 6 run | 4 | 3: JPM #159, #161 and #241, the audit finding |
  | final run | 1 (TSM #165, as on `base`) | **0** |

  The reviewer's script itself also reports `new6 not on base 0` on the final export.

**Scan B** is broader.

- **Rule.** Any header cell, the label column's included, names a year, a month and day, or `ended`, `ending` or
  `as of`. A body row holds no number, and one of its cells (under 120 characters) carries a year, a month and day, a
  numeric date, `Q1`-`Q4`, `FY` with a year, or `ended`, `ending`, `as of`, `as at` or `through`. Numbers follow below
  that row.
- **Results:**

  | Run | Hits | Not on `base` |
  |---|---|---|
  | `base` | 8 | |
  | revision 5 | 40 | 34 |
  | first revision 6 run | 12 | 6 |
  | final run | 9 | 3 |

**Every final hit, classified:**

- **Existing on `main`, the same tables on `base` (6):**
  - CRDO #26 and NTRA #33 (`main` leaves the date row in the body, see the yearless headers);
  - JPM #162;
  - SPCX #50;
  - TSM #147;
  - TSM #165, a second section repeating the same years.

  The two other `base` hits are gone on the branch. AMZN #23 now carries its years in the header, and TSM #143 no
  longer matches.
- **Not on `base` (3): META 10-K FY2023 #52, 10-Q 2023-Q2 #33 and 10-Q 2023-Q3 #33, long-term debt.**
  - Source, FY2023 #52:
    - r1 `Maturity | Stated Interest Rate | Effective Interest Rate | December 31, 2023 | December 31, 2022`;
    - r2 `August 2022 debt:`;
    - r3 `2027 Notes | 2027 | 3.50% | 3.63% | $ 2,750 | $ 2,750`;
    - r8 `May 2023 debt:`, followed by `2028 Notes … 1,500` in the 2023 column only.
  - The section labels name the month a series of notes was issued. They are neither period text nor a period phrase
    in the spec's sense.
  - Every carrying amount sits under its own balance-sheet date. In each table, 19 facts are `ok` and 18 are rate
    facts in undated columns; 0 are mismatched.
  - Not a stacked period block. These tables fell back on `main`, and revision 5 exported them the same way.

**JPM #159, #161 and #241** now equal `base` in every field: #159 is `needs_review` with `main`'s headers, and #161
and #241 are source text.

**Gate 6: pass.**

### Other filings (Acceptance 5): changes since Task 3

| Item | Task 3 (rev 5) | Rev 6 | What changed |
|---|---|---|---|
| Lost cells | 93 | 89 | Only TSM #105's 4 cells left the list. The table is `main`'s output again, with its rates 0.0140, 0.0160, 0.0400 and 0.0400. |
| Classification of the lost cells | | | Task 3's still holds: 41 fixes (MSFT #50 21, TSM #48 12, TSM #49 8) and 48 regressions (NTRA #8 4, TSM #150-#152 13, TSM #19 and #20 31). |
| Changed cells | 14 | 14 | The same 14 items, all fixes. |
| Promoted rows | 3,218 | 2,992 | Every revision 6 promoted row is one of revision 5's, which Task 3 reviewed. The 226 that are gone were in the reverted tables. |
| Balanced columns lost | 0 | 0 | |
| Tables missing or added | 0 / 0 | 0 / 0 | |

Task 3's I1 status changes, revisited:

- **Back to `main`'s output:** the RDDT exhibit indexes 10-K FY2024 #63 and #64, FY2025 #62 and #63, and 10-Q
  2024-Q1 #48 and 2026-Q2 #47.
- **Revision 5's output kept, acceptable as Task 3 found:** the other RDDT exhibit indexes (2024-Q2 #47, 2024-Q3
  #47, 2025-Q1 #49, 2025-Q2 #50, 2025-Q3 #50, 2026-Q1 #46) and NFLX #74 and #75.
- **`main`'s headers again:** NTRA #43, UNH #52 and TSM #59, as the guard offered in Task 3 predicted.

### Gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Every table that differs between rev 5 and rev 6 is guard-fired, with `main`'s headers and status | **Pass** | 107 differ. All 107 are guard-fired and identical to `main` in every field, so no value differs from `main` and there is no Rule 3 difference to classify. 0 differ otherwise. The 21 D1 tables, TSM #105 and JPM #159, #161 and #241 are among them. |
| 2. Vault primary statements | **Pass** | All 126 export. OK facts: META 3,322, NVDA 2,662, RDDT 2,056. 0 failures, 0 yearless, 0 untagged, 0 arithmetic and 0 ambiguous. The results are identical to revision 5. |
| 3. Vault, all tables | **Pass** | 0 lost, 0 changed, 0 balanced lost, 0 / 0 missing and added. |
| 4. Acceptance 3b | **Pass** | 0 real misattributions. Every mismatch (26 on `base`, 104 on the branch) and every yearless header (15 and 112) is classified above. The 3 vault unlocated tables were checked by hand and pass. Called out: the CRM percent columns (a risk) and the NVDA change columns. |
| 5. Others | **Pass** | Only TSM #105 changed since Task 3 among the classified cells, and it is no longer a regression. |
| 6. Stacked period blocks | **Pass** | The reviewer's scan finds 0 tables on the branch that are not on `main`. The broader scan finds 3, all META debt tables whose labels name a note issuance; they are not period blocks, and their 19 dated facts each are `ok`. JPM #159, #161 and #241 equal `base`. |

### Needs the user's acceptance (revision 6)

Resolved by revision 6:

- D1, the 21 vault equity statements;
- TSM #105;
- the JPM stacked blocks #159, #161, #194 and #241.

Still open:

1. **NTRA 10-K #8, 4 cells.** Regression, unchanged from item 3 above.
2. **TSM 20-F #150, #151 and #152, 13 cells.** Regression, unchanged from item 4 above.
3. **TSM 20-F #19 and #20, 31 cells.** Regression known from the spec, unchanged from item 5 above.
4. **CRM 10-K #10, #11, #14, #15, #16 and #17: yearless percent-of-revenue columns.**
   - What: each fiscal year's percentages sit under `Fiscal Year Ended January 31, — % of Total Revenues`, with no
     year.
   - Where it shows: the tables fell back on `main`; they are `needs_review` now.
   - Why it matters: a misattribution risk, though not a misattribution. No number sits under another period.
5. **The guard's coverage cost.**
   - What: besides D1 and TSM #105, 85 tables return to `main`'s output. That is 1,687 fewer numeric cells than
     revision 5 (NVDA −198, Others −1,489), and 35 of these tables fall back again.
   - Scale against the spec: the spec now gives the first run's figures (82 tables, 1,592 cells, 33). This run adds
     JPM #159, #161 and #241.
   - Vault totals: fallback tables go from 852 to 102, not 75.
   - Decision needed: accept this cost, or narrow the guard in the follow-up spec.

### Concerns (revision 6)

- **The spec's "Period-row guard coverage cost" figures are the first run's.** Commit `0b9cede` set them to 82
  tables, 1,592 cells and 33 tables falling back. The final run has 85, 1,687 and 35, because the guard now also
  covers JPM #159, #161 and #241. The spec's claims hold: none of these tables is a primary statement, and none can
  misplace a number.
- **Task 4.** Its CHANGELOG figure `852 to 75` must become `852 to 102`.
- **The check is blind to undated columns.** `no header date` covers 11,858 facts (25%), which the all-table check
  cannot judge.
  - The mixed-period check misses stacked blocks whose columns hold instants at only two dates, as JPM #159 and #241
    did.
  - Gate 6's structural scans cover the stacked-block shape, but only the forms their patterns recognise. A caption
    such as `Q1 2025` alone is caught by scan B, not by the guard (see the spec's known gaps).
- **Existing yearless risk on `main`.** In CRDO #26, NTRA #33 and SPCX #47, #48 and #50, `main` itself leaves the
  date row in the body. The branch does not change them.
- **NVDA mixed percent scale.** NVDA 10-Q 2024-Q1 #38 is `exported` with no issues, yet its `% Change` column holds
  values in percentage points beside fractions. This is the known mixed-scale gap.
