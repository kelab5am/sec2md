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
