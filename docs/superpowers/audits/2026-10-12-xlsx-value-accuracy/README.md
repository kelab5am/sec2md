# XLSX value accuracy: acceptance record

This records the acceptance run for:
- the XLSX value accuracy spec ([`../../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md`](../../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md), revision 2, "Acceptance" items 3–8);
- Task 6 of its plan ([`../../plans/2026-10-12-sec2md-xlsx-value-accuracy.md`](../../plans/2026-10-12-sec2md-xlsx-value-accuracy.md)).

**Inputs:**
- **Candidate:** branch `fix/xlsx-value-accuracy` at **`732544d`**, in the worktree `.worktrees/xlsx-value-accuracy`.
- **Baseline:** `outputs/xlsx-value-accuracy/base`. It is `main`'s `src` exported by Task 1; `src` on `main` is unchanged since `1c0ac51`.
- **Manifest:** [`manifest.json`](manifest.json), with 4,048 entries built from that baseline by [`manifest.py`](manifest.py).
- **Corpus:** the 60 filings of the header-detection audit (`../2026-10-11-xlsx-header-detection/filings.txt`).
  - 42 vault filings: 18 META, 14 NVDA and 10 RDDT.
  - 18 other filings.
  - 3,702 tables on each side.
- **Run date:** 2026-10-13.

The decisions this record judges by:
- the spec's Rule P and Rule I;
- the rulings and user decisions in the plan's ledger (`.superpowers/sdd/2026-10-12-sec2md-xlsx-value-accuracy/progress.md`), Rulings 3–18a and the user decisions of 2026-10-13 (footnote marks and the TSM split-`%` fix).

## First run on `7484006`: blocked, then fixed

The first acceptance run exported the branch at `7484006`. It failed the disposition gate (Acceptance 3) on **31 `percent_row_split` cells in TSM 20-F #8–#12**. They were still unflagged numbers in percentage points.

- **Example, TSM #8 `Net revenue | 100.0 | % | 100.0 | % | 100.0 %`.** The 2022 and 2023 columns exported the number `100.0`, while 2024 exported `1.000`.
- **Cause: Ruling 5.** The ruling refused a `%` whose leaf heading differs from the value's. TSM's markers sit under the spanning `For the year ended December 31,`, not under the year cells. Nothing else proved or flagged the values.

The user decided the fix (ledger, user decision of 2026-10-13, and Rulings 13–18a). The branch implements it in `bcdfe4f`, `dc53e06`, `1466b39`, `ad816e0` and `732544d`.
- **When a split `%` attaches:** it may attach through a heading that spans its value's column, but only when:
  - it sits directly beside the value (Ruling 16);
  - its columns hold nothing else in any other body row, with `)` / `%)` fragments and unit-caption rows aside (Rulings 18, 18a).
- **Safety net:** any value whose marker is refused becomes text with the P4 reason (Ruling 13), whatever its other proofs. A zero still converts, and a token the converter rejects keeps the converter's reason.

This record is the rerun on `732544d`. The first run's export is kept as `outputs/xlsx-value-accuracy/new-7484006` (git-ignored).

## Result in one paragraph

Every gate passes on `732544d`.
- **Dispositions (Acceptance 3).** All 4,048 manifest entries have a valid disposition:
  - 338 proven percents, each with its proof named;
  - 47 proven quantities;
  - 988 flagged text cells with the expected reason;
  - 2,658 true identifier cells unchanged;
  - 17 non-digit misread cells unchanged.

  No manifest cell is an unflagged number at the wrong scale.
- **Primary statements (Acceptance 4).** The 126 vault primary statements export, with the same verified fact counts (META 3,322, NVDA 2,662, RDDT 2,056) and 0 failures. The whole `primary_statements.py` result is identical to the baseline's.
- **Other changed cells (Acceptance 5).** Every changed cell outside the manifest is classified: 1,751 cells, plus 164 tables whose status or headers changed. **0 numbers are wrong.**
  - Each of the 12 numbers whose value changed from one number to another was checked individually. Each is a rate proven by its own inline XBRL percent fact.
- **Percent facts (Acceptance 6).** Every cell proven by a percent fact (789) equals the fact / 100 with its sign.
- **Coverage cost (Acceptance 7):** 1,127 numbers became flagged text, in 74 tables. None is in a primary statement.
- **Header-detection checks (Acceptance 8).** `all_facts.py` and the stacked-block scans find nothing new.

## How to rerun

From the checkout root (the export JSONs name their filings by paths relative to it). Every python run is low priority; the export uses 3 workers.

```bash
cd /c/Users/einstein/kelab5am/sec2md
PY=.worktrees/xlsx-export/.venv/Scripts/python.exe   # cmd: start "" /low /b /wait <PY> ...
H=docs/superpowers/audits/2026-10-11-xlsx-header-detection
A=docs/superpowers/audits/2026-10-12-xlsx-value-accuracy
O=outputs/xlsx-value-accuracy
SRC=.worktrees/xlsx-value-accuracy/src                 # the branch at 732544d
$PY -I $H/export_tables.py --src $SRC --out $O/new --workers 3 $(cat $H/filings.txt)
$PY -I $A/dispositions.py $O/base $O/new --manifest $A/manifest.json --src $SRC --details $O/dispositions.json
$PY -I $H/primary_statements.py $O/new --report $O/statements-new.md --details $O/statements-new.json --workers 3
$PY -I $H/primary_statements.py $O/base --report $O/statements-base.md --details $O/statements-base.json --workers 3
$PY -I $H/all_facts.py $O/base --report $O/all-facts-base.md --details $O/all-facts-base.json --workers 3
$PY -I $H/all_facts.py $O/new --report $O/all-facts-new.md --details $O/all-facts-new.json --workers 3
$PY -I $A/changes.py $O/base $O/new --manifest $A/manifest.json --src $SRC --details $O/changes.json \
    --all-facts $O/all-facts-base.json $O/all-facts-new.json \
    --stacked-scan outputs/xlsx-header-detection/task-7/stacked_scan.py
```

| Step | Duration |
|---|---|
| Export, 60 filings | 11m12s (04:33:05–04:44:17) |
| `dispositions.py` | about 10 s |
| `primary_statements.py`, each side | 0.6 s |
| `all_facts.py`, each side | 0.6 s |
| `changes.py` | about 8 s |

Two runs of each script gave byte-identical output.

Notes on the inputs:
- **The stacked-block scan** is the header-detection audit's gate 6 script (`stacked_scan.py`, git-ignored with that audit's outputs). `changes.py` imports its `scan_a` and `scan_b` unchanged.
- **Outputs:** all outputs are in `outputs/xlsx-value-accuracy/` (git-ignored), with each script's printout in a `.log` beside its JSON.

### The two scripts

**[`dispositions.py`](dispositions.py)** covers Acceptance 3 and 6.
- **How it reads the rules.** It re-reads Rule P and Rule I from the spec and the ledger's rulings, against the export JSON. It does not use the branch's code, so any disagreement with the branch shows up as a failure.
- **What it takes from the branch's `src`:**
  - the patterns the spec calls today's (`_ROW_UNIT`, `_PERCENT`, `_PERCENT_UNIT`, `_FOOTNOTE_MARK`, `_UNIT_LINE`, `_VALUE`);
  - the unchanged header-detection helpers (`_identifier_heading`, `_period_row`, `_period_text`);
  - `convert_cell`, for the converter's own review reasons.
- **What it does:**
  - **Locates each manifest entry.** It finds the copy cell whose `cell_sources` hold the entry's source coordinates. It asserts that coordinates are unique per table on both sides, and they are.
  - **Gathers the proofs.** For each entry it collects the evidence: own `%`, own `$`, percent fact, amount fact, percent header (withheld in shared leaves, Rulings 7, 10 and 11), percent row label, in-table table-wide caption, non-percent unit and conflicts.
  - **Sets the expected outcome and compares.** It derives the expected disposition and compares the value, format and reason.
  - **Audits every split `%` marker** the attachment pass reaches, against the attachment rules.
  - **Lists every percent-fact cell.**
- **Nested facts.** `export_tables.py` loses a fact nested inside another fact, because marking the outer fact clears the inner one. So `dispositions.py` reads each filing's own `ix:nonFraction` tags to restore the count, which matters because Ruling 3 counts a nested fact as a second fact. The corpus holds 1,068 nested facts: META 229, NVDA 118, RDDT 261 and Others 460.

**[`changes.py`](changes.py)** covers Acceptance 5, 7 and 8.
- **Matching cells.** It keys every copy cell by its value origin, as the manifest does, and lists each cell whose type, value, original, format or review reason differs from `base`, outside the manifest.
- **Classes.** It classifies each changed cell by a stated rule (below) and checks the new cell against the expectation `dispositions.py` gives for it.
- **Headings.** It checks that every new number sits under its own heading: its copy column's header must be the header above its value origin's source column.
- **Coverage cost.** It counts the coverage cost.
- **Header-detection checks.** It compares the `all_facts.py` mismatches and the stacked-block scan hits of the two exports.

## Gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Export | **Pass** | 60 JSONs, 3,702 tables. Run at Idle priority with 3 workers; no workers left over. |
| 2. Dispositions (Acc. 3) | **Pass** | 0 of 4,048 entries without a valid disposition. `identifier_true`: 2,658 of 2,658 unchanged in value, type, format and reason. Split-`%` audit: 0 disagreements. |
| 3. Primary statements (Acc. 4) | **Pass** | All 126 vault statements export (META 54, NVDA 42, RDDT 30). OK facts: META 3,322, NVDA 2,662, RDDT 2,056. Failures 0, arithmetic failures 0. `statements-new.json` is identical to `statements-base.json`. |
| 4. Changed cells (Acc. 5) | **Pass** | 1,751 changed cells, all as the spec gives. 0 wrong numbers; 0 new numbers outside their own heading. |
| 5. Percent facts (Acc. 6) | **Pass** | 789 numbers equal the fact / 100 with its sign; 0 differ. |
| 6. Coverage and header checks (Acc. 7, 8) | **Pass** | Coverage cost: 1,127 cells in 74 tables, counted per group and table below. `all_facts.py`: 104 mismatches on both sides, 0 new. Stacked-block scan A: 1 and 1 hits, 0 new. Scan B: 9 and 9 hits, 0 new. |

## Dispositions (Acceptance 3)

| Kind | Entries | Disposition | Cells | Proof named |
|---|---|---|---|---|
| `percent_row_joined` | 1,072 | proven percent | 170 | percent fact 109; fact + header 3; header 58 |
| | | text, P4 reason | 902 | (no proof, in a percent column) |
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
| Joined by column grouping under one leaf | 144 | The attachment rules refuse these markers, because another row's value spans the marker's column. But value and marker sit under the same leaf heading, and `_column_groups` merged that leaf's columns, as `main` does whenever every row converts. Spec P4 now lets `(x) %` rows pass that test. META 84, NVDA 46, RDDT 14. Example: META 10-K FY2025 #5 `Operating margin 52 \| %` under `2025`, where `$ 198,759` spans the same columns. |
| Refused | 8 | Every one fails the marker-only rule, and every value is P4 text. They are BAC #4 (3), CRDO #25, #26, KO #11 (2) and KO #54. |
| Branch and rules disagree | **0** | |

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

`statements-new.json` and `statements-base.json` are identical, and so are the two reports. The 167 tables identified as primary statements (126 vault and 41 others) hold no changed cell, no status or header change and no manifest entry.

## Changed cells outside the manifest (Acceptance 5)

There are 1,751 changed cells outside the manifest. Separately, 164 tables changed status or headers (see "Tables" below). Each class below has a stated rule, and `changes.py` checks every cell against the spec's expectation for it: value, format, reason and heading. All 1,751 hold.

| Class | Cells | Rule | Inspection |
|---|---|---|---|
| Number rescaled | **12** | A base number, now a different number. It must be a proven percent equal to D / 100. | Each one checked against its cell and fact (below). |
| Text to number | 370 | A base text cell, now a number: D / 100 with a percent proof, or D with a quantity proof. | Two parts, below. |
| New only | 705 | Cells in 20 META tables that were `source_text_only` on `main`. | Below. |
| Number to flagged text | 205 | A base number, now text with the reason the rules give: P4 200, points 4, conflict 1. | All 28 tables, first 3 cells each. This is coverage cost, below. |
| Format or reason only | 193 | Text on both sides; only the reason changed. | Every table group (46 tables), below. |
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

**Format or reason only: 193 cells.** These were text on `main` and are still text. Only the reason changed:
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
- **Header changes in tables exported on both sides (54):** every one only removes a duplicate column. A `%` marker column that repeated its value column's header has been joined into the value's column.

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

## Concerns (none blocks the merge)

1. **Coverage cost is large in MD&A tables.**
   - 1,127 numbers became flagged text, mostly META's and RDDT's percent-of-revenue rows (820).
   - The spec also asks for amount rows in percent columns to be flagged, for example JPM #32 (48) and TSM #9, #10 and #12 (41). That includes TSM's `Net revenue 2,263,891`, which sits in a column whose other rows carry an attached `%`.
   - These are text, never wrong numbers, and no primary statement is affected.
2. **The literal safety net flags three cells that carry their own percent fact**, CRDO #25 and #26 and KO #54 (Ruling 13). Each heading was left in the body: `May 3, 2025` and `8 years` span the `%` column.
3. **The harness drops nested facts.** `export_tables.py` drops facts nested in facts (1,068 in the corpus). So `primary_statements.py` and `all_facts.py` never check the inner facts either; JPM's inner `c-2025` contexts are one example. `dispositions.py` restores the count from the filings for Ruling 3, but the period check does not.
4. **The table-wide percent declaration in the context lines is not in the export JSON.** `dispositions.py` sees only in-table spanning captions. No entry or changed cell needed the context proof in this run. Such a cell would have appeared as invalid and been checked by hand.
5. **Emptied split-`%` columns keep their header.** For example, TSM #8 keeps two blank `For the year ended December 31,` columns. This is cosmetic.
