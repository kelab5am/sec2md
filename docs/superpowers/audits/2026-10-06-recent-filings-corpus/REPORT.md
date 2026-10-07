# Recent filings corpus: first run

Date: 2026-10-07. This is plan Task 7, the record of Tasks 1–6.

- **Spec:** [`../../specs/2026-10-06-sec2md-recent-filings-corpus-design.md`](../../specs/2026-10-06-sec2md-recent-filings-corpus-design.md) (revision 1)
- **Plan:** [`../../plans/2026-10-06-sec2md-recent-filings-corpus.md`](../../plans/2026-10-06-sec2md-recent-filings-corpus.md)
- **`main`:** a fresh `git archive c674828` tree for every run.
- **Branch:** `feat/table-merge-header` at `1252c45`, in the worktree `.worktrees/tmh-proto`. It was clean before and after every run, and no run wrote a `__pycache__`.
- **Python:** the worktree venv (3.12.10), with `PYTHONIOENCODING=utf-8`. Each run checked `sec2md.__file__` on each side.
- **How to rerun:** [`README.md`](README.md).
- **Names.** Sections 2–5 name documents by issuer and filing year, as their files are named. For example, TSM-2022 is `TSM-20-F-2022-04-14.htm`, which reports fiscal 2021. Section 1 uses fiscal years.

## Summary

- **Corpus.**
  - 70 annual reports from 17 issuers (SPCX has none), 380,186,110 bytes as served. Each passes the loader's SHA-256 check.
  - Two re-listings are byte-identical to the approved draft: one at 12:59 EDT on 2026-10-06, and a final one at 00:46 EDT on 2026-10-07, after EDGAR's filing day closed. MU filed no fiscal 2026 10-K inside the window, so the corpus has no gap (section 1.6).
- **Strict.**
  - 0 new failures in 140 document-modes.
  - 18 failures (9 documents × 2 modes) are identical on both sides: a cover-page telephone area code.
  - Default strict fails on 9 of the 70 filings on `main` as well as on the branch.
- **Prevalence.**
  - The recent corpus has 2 sub-label currency occurrences, both affected. Both are the benign form: each code is the currency of the amount it is joined to.
  - Every other detector finds 0. Phase A finds 0 for every detector.
- **Acceptance.**
  - Alignment: 0 identities lost. Pass.
  - Sections: 0 changes in 560 comparisons. Pass, though coverage is weak for 4 documents.
  - XLSX: identical apart from `display_page` in 42 snapshots on 24 pages. This meets the spec's wording. But the changes are a net regression and go beyond the S3 list the user accepted, so **they need a user decision** (section 4.1).
- **One branch finding outside the named limitations.** Strict fails on the branch, where `main` passes, for a `<table>` directly inside a body `<tr>`, or inside a `<div>` in a first row of `td` cells. The corpus has no occurrence (section 3.4).

## 1. The corpus

### 1.1 Selection

- **Issuers:** the 18 Phase A EDGAR issuers, with the CIKs and name checks of Phase A's `fetch_edgar.py`.
- **Forms:** `10-K`, or `20-F` for TSM, BABA and NVO. AMZN and GOOGL contribute 10-Ks here; Phase A used their 10-Qs.
- **Window:** filing dates from 2021-10-07 to 2026-10-06, inclusive.
- **One filing per fiscal year, by report date.** The original is taken over an amendment. An amendment is taken only when it is the sole filing for its period; that never happened.
- **Primary documents only.** Phase A's accessions are excluded: its EDGAR manifest and the five fixture filings.
- **Listing.** 141 index requests:
  - 18 submissions JSON files;
  - 53 older-filings pages: JPM 37, BAC 12, and one each for NTRA, NFLX, CRM and GOOGL;
  - 70 `index.json` files.
- **Approval.** The user approved the 70-document draft on 2026-10-06.
- **Download.** 70 requests in 37 s, with no error and no redirect.

### 1.2 Documents per issuer and fiscal year

The fiscal year is the year of the report date. Sizes are the primary document's, in MB. PA marks a Phase A duplicate, which is excluded. A dash means no filing in the window; the reasons are in 1.3.

| Issuer | Form | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 | FY2026 | Docs | MB |
|---|---|---|---|---|---|---|---|---|---|
| JPM | 10-K | 16.0 | 15.9 | 13.2 | PA | 12.9 | - | 4 | 58.0 |
| KO | 10-K | 5.5 | 5.4 | 4.2 | PA | 3.8 | - | 4 | 18.8 |
| MSFT | 10-K | - | 6.2 | 10.0 | 6.9 | PA | 8.6 | 4 | 31.6 |
| TSLA | 10-K | 7.9 | 8.0 | 2.7 | PA | 2.4 | - | 4 | 20.9 |
| CAT | 10-K | 7.6 | 7.2 | 5.7 | PA | 6.1 | - | 4 | 26.6 |
| BAC | 10-K | 16.0 | 16.3 | 12.9 | PA | 12.8 | - | 4 | 58.0 |
| UNH | 10-K | 3.5 | 3.6 | 2.7 | PA | 2.9 | - | 4 | 12.7 |
| MU | 10-K | 2.8 | 2.9 | 2.2 | 2.2 | PA | - | 4 | 10.1 |
| NTRA | 10-K | 3.7 | 3.5 | 3.3 | PA | 3.3 | - | 4 | 13.9 |
| NFLX | 10-K | 2.0 | 2.0 | 1.8 | PA | 2.1 | - | 4 | 7.9 |
| CRM | 10-K | - | 3.0 | 3.0 | 2.4 | PA | 2.6 | 4 | 11.0 |
| CRDO | 10-K | - | 2.1 | 1.8 | 1.7 | PA | 1.7 | 4 | 7.2 |
| TSM | 20-F | 6.9 | 6.2 | 7.3 | PA | 10.4 | - | 4 | 30.8 |
| BABA | 20-F | - | 7.7 | 14.1 | 9.0 | PA | 11.7 | 4 | 42.6 |
| NVO | 20-F | 1.4 | 1.4 | 1.4 | PA | 1.4 | - | 4 | 5.6 |
| AMZN | 10-K | 2.4 | 2.5 | 1.9 | 1.9 | 2.0 | - | 5 | 10.7 |
| GOOGL | 10-K | 3.0 | 3.0 | 2.4 | 2.5 | 2.6 | - | 5 | 13.6 |
| SPCX | 10-K | - | - | - | - | - | - | 0 | 0 |
| **Total** | | **13** | **17** | **17** | **7** | **12** | **4** | **70** | **380.2** |

- **Size by fiscal year:** FY2021 78.9 MB, FY2022 96.9, FY2023 90.5, FY2024 26.6, FY2025 62.7 and FY2026 24.6.
- **Documents by filing year:** 2021 1, 2022 17, 2023 17, 2024 17, 2025 2 and 2026 16. Filing year 2025 is thin because Phase A holds 15 issuers' 2025 filings.
- **Count.** 70 matches the spec's "about 70":
  - 15 issuers each have 5 annual reports in the window, less 1 Phase A duplicate each, giving 60;
  - AMZN and GOOGL add 5 each;
  - SPCX adds 0.
- **Largest:** BAC FY2022 (16.27 MB), BAC FY2021, JPM FY2021, JPM FY2022 and BABA FY2023 (14.08 MB).
- **Smallest:** NVO, about 1.4 MB each year.

### 1.3 Gaps (each dash)

- **FY2021, filed before the window opened** (`outside_window`): MSFT (2021-07-29), CRM (2021-03-17) and BABA (2021-07-27).
- **FY2021, never filed:** CRDO's first 10-K is for fiscal 2022, as the spec expects.
- **FY2026, period not ended:** the issuers with a December year end.
- **FY2026, MU:** not filed by the time of the listing; see 1.6.
- **SPCX:** no annual report (`no_annual_report`), as the spec expects.

### 1.4 Exclusions (82)

| Reason | Count | Detail |
|---|---|---|
| `phase_a_duplicate` | 15 | Phase A's 15 annual reports: the 2024-period reports of the December year ends, MSFT FY2025, MU FY2025, CRM FY2025 (report date 2025-01-31), CRDO FY2025 and BABA FY2025. |
| `amendment` | 5 | An amendment whose original was kept (below). |
| `outside_window` | 61 | Annual reports and amendments filed before 2021-10-07, back to 2018–2019 for most issuers. |
| `no_annual_report` | 1 | SPCX. |
| `same_period_newer` | 0 | |

The five amendments, each excluded in favour of its original:
- TSLA 10-K/A for FY2021 (filed 2022-05-02), FY2024 (2025-04-30; its original is Phase A's) and FY2025 (2026-04-30);
- CRDO 10-K/A for FY2022 (2023-04-05);
- BABA 20-F/A for FY2023 (2024-02-23).

No selected document is an amendment. No `10-KT` or other annual-form variant appears in the window.

### 1.5 Size and bytes

- **Size.** 70 documents, 380,186,110 bytes as served (`manifest.json`). `index.json` gives 380,178,550.
- **The +108 bytes.** Each file is exactly 108 bytes larger than `index.json` says. The SEC's web front end injected one `<script>` tag before `</body>`. With that tag removed, all 70 equal `index.json`'s size.
- **Ruling 1: the files are kept as served,** as Phase A's were.
  - The SHA-256s cover the bytes served on 2026-10-06.
  - The tag's `src` changed between 2026-10-03 and 2026-10-06, so a re-download into an empty cache may give different bytes.
  - `download` records a re-fetched file's new hash without a warning (README, "Served bytes").
  - sec2md drops `<script>`, so results are unaffected.

### 1.6 MU fiscal 2026 and the re-listing

- **Why MU matters.** MU's fiscal 2026 ended in early September 2026, and its 10-Ks for 2021–2025 were filed on October 8, 7, 6, 4 and 3. A fiscal 2026 10-K filed on 2026-10-06 would fall inside the window.
- **The approved listing has no such filing.** When Task 1 listed, MU's newest filings were Form 4s of 2026-10-02 and the earnings 8-K of 2026-09-30.
- **The Task 7 re-listing** ran `fetch_recent.py list` into a scratch file, with index requests only and no document downloaded.
  - It exited 0, with 70 documents, 380,178,550 bytes and 82 exclusions.
  - **The file is byte-identical to the approved `manifest_draft.json`** (SHA-256 `68e286b6…cb336`). The documents, exclusions, order and totals all match.
  - So MU had still not filed a fiscal 2026 10-K, and nothing else had changed.
- **That was not yet the post-window check.**
  - The re-listing finished at 2026-10-06 16:59 UTC: 12:59 EDT, or 00:59 on 2026-10-07 local time (UTC+8).
  - EDGAR's 2026-10-06 filing day was still open. A 10-K submitted by 17:30 Eastern gets that day's filing date.
- **The final re-listing settles it: no gap.**
  - It ran from 2026-10-07 04:46:00 to 04:47:01 UTC (00:46 EDT, or 12:46 local time), after the 2026-10-06 filing day closed. The command and safeguards were the same: index requests only, no document downloaded, and the output went to a scratch file.
  - It exited 0, with 70 documents, 380,178,550 bytes and 82 exclusions.
  - **The file is again byte-identical to the approved `manifest_draft.json`** (SHA-256 `68e286b6…cb336`).
  - So MU filed no fiscal 2026 10-K on or before 2026-10-06, and the corpus stays at the approved 70. A 10-K filed on 2026-10-07 or later is outside the window and is no gap.

## 2. Strict comparison (`strict.json`)

**Method**
- Each document is converted under the default `strict` policy on both sides, in normal mode (`capture_tables=False`) and capture mode (`capture_tables=True`). Each conversion is done as the public `convert_to_markdown` does it, with images.
- A cross-check rendered without images, as `run_side.py` does. Its results are identical.
- **A new failure** is pass→fail, or fail→fail with a different multiset of failures.
  - The multiset holds the trace tokens without element ids, mapping warnings and other strict warnings.
  - Each item the branch adds is classified `zero_width_number`, `header_row_table`, `wrapped_table` or `other`.

| | Pass | Fail |
|---|---|---|
| `main`, 140 document-modes | 122 (61 normal, 61 capture) | 18 |
| Branch, 140 document-modes | 122 (61 normal, 61 capture) | 18 |

**Results**
- **Transitions:** pass→pass 122 and fail→fail-same 18. There are none of pass→fail, fail→fail-different or fail→pass.
- **New failures: 0.** By class: `wrapped_table` 0, `zero_width_number` 0, `header_row_table` 0 and `other` 0. No "other" was left to investigate.
- **The comparison is not empty.**
  - The branch's output differs from `main`'s in all 140 document-modes.
  - Pages (18,242), elements (106,124) and tables checked (20,358) are equal on both sides.
  - The branch recorded 0 `header_accounting_misses` in all 140.
  - Neither side had a crash, or a mapping, replacement, C1 or ratio warning.

### 2.1 The 18 pre-existing failures: a cover-page telephone area code

| Document | Modes | Untraceable token |
|---|---|---|
| MSFT FY2023, FY2024, FY2026 (`MSFT-10-K-2023-07-27`, `-2024-07-30`, `-2026-07-29`) | normal, capture | `425` |
| NTRA FY2021, FY2022, FY2023, FY2025 (`NTRA-10-K-2022-02-25`, `-2023-03-01`, `-2024-02-29`, `-2026-02-27`) | normal, capture | `650` |
| TSLA FY2021, FY2022 (`TSLA-10-K-2022-02-07`, `-2023-01-31`) | normal, capture | `512` |

**Root cause.** In the registrant's telephone number on page 1, the area code's parentheses sit in their own inline elements. The smallest source is in `NTRA-10-K-2022-02-25.htm`:

```html
<p><b>(</b><ix:nonNumeric name="dei:CityAreaCode"><b>650</b></ix:nonNumeric><b>)&#160;</b><ix:nonNumeric name="dei:LocalPhoneNumber"><b>249-9090</b></ix:nonNumeric></p>
```

1. sec2md writes each bold run separately: `**(** **650** **)** **249-9090**`.
2. Strict's source pool reads the node text `( 650 ) 249-9090` and tokenizes it as `-650`, `249`, `9090`. The parentheses make an accounting negative.
3. On the output side, the bold markers sit between the parentheses and the digits, so the tokenizer reads `650`, `249`, `9090`.
4. `650` is in the output but not in the source pool, so strict raises `ParseQualityError: untraceable normalized number: <element>:650`.

This was reproduced on the branch for this record, and the side dumps show it on both sides. MSFT (`425`) and TSLA (`512`) are the same, with `<span>` runs instead of `<b>`.

**Effect**
- **`main` fails default strict on 9 of the 70 recent filings (12.9%), and so does the branch.** A user calling `convert_to_markdown` with the default policy on these 10-Ks gets a `ParseQualityError` today, with or without the branch.
- Phase A shows the same failure for MSFT FY2025 and NTRA FY2025.
- It has nothing to do with tables and is not one of the five named limitations.

## 3. Limitation prevalence (`prevalence.json`)

Each detector reads its source condition from the HTML as the branch's `Parser(html)` parses it. `affected` means the branch's output shows the limitation's effect. The branch runs as `convert_to_markdown` does under the default strict policy.

### 3.1 Recent against Phase A

| Detector | Recent (70): docs | tables | occurrences | affected | Phase A (109): docs | tables | occurrences | affected |
|---|---|---|---|---|---|---|---|---|
| `wrapped_table` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `zero_width_number` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `header_row_table` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `sub_label_currency` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| `page_top_part_table` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

- **Phase A gives 0 `affected` for every detector,** matching the acceptance record. Its hash check matched 109 of 109.
- **Both runs had 0 errors.** Recent: 70/70 in 40.2 s. Phase A: 109/109 in 18.2 s, with 2 RCQ duplicates of fixtures skipped, as the acceptance tooling skips them.

### 3.2 The two sub-label currency occurrences: the named limitation in its benign form

| Document | Table | Code column | Codes | Rows | Joined on the branch |
|---|---|---|---|---|---|
| `BABA-20-F-2026-05-20` | 39 (directors' and officers' RSU and option grants) | 1 | `HK$`, `US$` | 6 | `US$ 78.37`, `HK$ 116.70`, `HK$ 152.69`, `US$ 79.96`, `US$ 84.60`, `HK$ 68.00` |
| `TSM-20-F-2023-04-20` | 278 (forward exchange contracts) | 2 | `NT$`, `RMB`, `US$` | 5 | `NT$ 132,734.5`, `US$ 2,009.1`, `NT$ 79,610.6`, `US$ 752.5`, `RMB 1,448.4` |

- **These are the named sub-label currency limitation of spec revision 17:** R4 fuses a column of varying currency codes into the amounts beside it.
  - BABA 39: the branch writes `| | US$ 78.37 | 16,000,000 | …`, where `main` writes `| | US$ | 78.37 | …`.
  - TSM 278: the branch writes `| Sell NT$ | January 2022 to March 2022 | NT$ 132,734.5 |`, where `main` keeps `NT$ | 132,734.5` in separate columns.
- **Here the fusion is benign.**
  - In both tables, each code is the currency of the amount it is joined to: an exercise price, or a contract amount.
  - The joined text reads correctly, and the branch reports no strict failure for either table.
  - The harmful form is the spec's `Forward contracts` case, where a code is a sub-label over amounts in another currency. Neither corpus contains it.
- **Both tables are also check 1 F9 false positives** (section 4.3): check 1 reads `US$ 78.37` as a text cell.
- **Ruling 4: the detector was widened during the run.**
  - The plan's condition was "a body column next to R0's label column". It missed TSM 278, whose code column comes after a Maturity Date text column.
  - The condition is now any body column other than R0's label column that holds two or more distinct codes from the closed list, each directly before an amount. The closed list is the branch's letter codes plus `US$`, `HK$`, `NT$`, `A$`, `C$` and `S$`.
  - The widened scan adds only TSM 278 and keeps Phase A at 0.
  - The cost if this is wrong: the detector is broader than the plan's literal wording.
- **Tables with a single code before amounts are not the limitation.**
  - Examples are TSM-2023 288 (`US$ | 328.0`) and the other F9 tables. They are R4's intended per-row currency column.
  - The `code_before_amount` counter (2 recent, 0 Phase A) counts only within the tables that hold two or more distinct codes anywhere: 188 tables in 8 recent documents, and 25 in 2 Phase A documents.
  - Apart from BABA 39 and TSM 278, the codes in those tables are header labels or captions.

### 3.3 Why the zeros can be trusted

- **The branch's own effect counts are 0 for every cause:** 0 `:missing` and 0 `:ambiguous` header-accounting records, and 0 `header:` excesses. This holds over 13,105 recent tables and 5,332 Phase A tables. So `wrapped_table` and `header_row_table` cannot be affected anywhere, whatever their detectors find.
- **The near-miss counters, recent and Phase A:**
  - wrapped tables of any kind: 0 and 0;
  - tables under a bold or italic style that the parser does not read: 0 and 0;
  - nested tables of any kind: 0 and 0;
  - zero-width cells: 20,804 in 5 documents, and 3,407 in 1. Of these, cells where a zero-width character touches a digit: 1 and 0. The one is NTRA FY2021 table 246, where four trailing U+200B follow `February 24, 2022`;
  - one-row PART tables: 4 and 1. Each has other cells, and none is at a page top. They are CAT's table 7 in every year, the spec's "CAT 7".
- **An independent BeautifulSoup scan agrees:** 13,105 and 5,332 tables, 0 nested and 0 wrapped.
- **The branch's trace failures are not limitations.** They are the 9 telephone-number documents in the recent corpus, and Phase A's 7 known pre-existing failures.

### 3.4 Branch finding outside the named limitations (M3)

Strict can fail on the branch, where `main` passes, for two layouts that none of the five named limitations covers:
- a `<table>` directly inside a **body** `<tr>`;
- a first row of `td` cells (not an R0 header row) that holds `<div><table>…</table></div>`.

The table merge spec says only three named limitations can make strict fail where `main` passed.

The probe for this record ran `convert_to_markdown(..., quality_policy="strict")` on the `main` archive tree and on the branch:

| Input | `main` | Branch |
|---|---|---|
| `<table><tr><th>Item</th><th>2025</th></tr><tr><td>Revenue</td><td>100</td><table><tr><td>Fiscal</td><td>2024</td></tr></table></tr></table>` | pass | `untraceable normalized number: …:2024` |
| `<table><tr><td>Item</td><td>Period</td><div><table><tr><td>Fiscal</td><td>2024</td></tr></table></div></tr><tr><td>Revenue</td><td>100</td></tr></table>` | pass | `untraceable normalized number: …:2024` |
| For comparison, the named limitation: the same nested table in a `th` header row | pass | `…:header:2024` |

- **How the tooling sees it.** The failure is a body token, not a `header:` excess, so `strict_compare.py` would class it `other`. No prevalence detector targets it.
- **Corpus count: 0.** Neither corpus has a nested table of any kind: the `nested_tables` and `nested_in_row` counters are 0, and so is the independent scan.
- **Where it belongs:** the strict-failure limitations spec.

## 4. Acceptance comparison (`acceptance/`)

- **What ran.** The table merge acceptance tooling ran with `--corpus recent` on all 70 documents:
  - `run_side.py` on both sides;
  - `merges_main.py` and `analyze_candidate.py`;
  - `report.py`;
  - `xlsx_detail.py dump` and `compare`.
- **Checks.** Every step exited 0. The hash check passed on 70/70 in each loading script. `run_check.json` records `"corpus": "recent"` for all three runs.
- **Not run:** the Phase A-only scripts `shifted_tables.py`, `review_sample.py` and `overhead.py`.
- **Not applicable:** class 8's table list, and check 1's class-1 and false-positive lists, are Phase A evidence.

### 4.1 Hard verdicts

**1. Alignment identities lost against `main`: 0. PASS.**
- `evaluated_on_main_not_candidate` is 0, `loss_transitions` is empty, and `alignment_losses.json` is `[]`.
- An independent recount from `alignment_values.tsv.gz` (222,099 value rows) gives 0 lost and 2,119 gained.
- `identities_hold`, `production_match` and `deterministic_candidate_outputs` are all true.

**2. XLSX prepared tables identical apart from `display_page`: met as this spec words it, but a user decision is needed.**

*What differs*
- Both sides have 7,075 prepared tables. 42 snapshots on 24 pages in 10 documents differ, each only in `source.display_page`.
- A field-by-field comparison agrees, and so does `only_display_page_differs`, which is true for all 10 documents. Every page is listed below.

*Cause: the S3 mechanism*
- `Parser._extract_page_number_from_content` guesses a page number from each Markdown page's first 3 and last 3 lines, table lines included.
- On each of the 24 pages, the lines that differ are table lines that the branch renders differently.

*The changes are a net regression*
- This is the Task 6 review's finding. Each guess is judged against the page number printed on the page, which is the page's last line in Task 6's line dump.

**Worse on the branch: 9 pages, 15 snapshots** (`main` was right, the branch is wrong)

| Document | Page | Printed | `main` | Branch | Snapshots |
|---|---|---|---|---|---|
| BABA-20-F-2022-07-26 | 152 | 139 | 139 | 31 | 11, 12 |
| BABA-20-F-2023-07-21 | 141 | 130 | 130 | 2 | 19, 20 |
| NTRA-10-K-2022-02-25 | 74 | 74 | 74 | 304 | 6 |
| NTRA-10-K-2022-02-25 | 86 | 86 | 86 | 614 | 9 |
| NTRA-10-K-2024-02-29 | 117 | 117 | 117 | 25 | 34, 35 |
| NTRA-10-K-2024-02-29 | 118 | 118 | 118 | 3 | 36, 37, 38 |
| NTRA-10-K-2024-02-29 | 121 | 121 | 121 | 271 | 41 |
| NTRA-10-K-2026-02-27 | 81 | 81 | 81 | 140 | 7 |
| NTRA-10-K-2026-02-27 | 128 | 128 | 128 | 64 | 41, 42 |

**Better on the branch: 5 pages, 7 snapshots** (`main` was wrong, the branch is right)

| Document | Page | Printed | `main` | Branch | Snapshots |
|---|---|---|---|---|---|
| NTRA-10-K-2023-03-01 | 118 | 118 | 7 | 118 | 37, 38, 39 |
| TSM-20-F-2022-04-14 | 37 | 34 | 8 | 34 | 23 |
| TSM-20-F-2023-04-20 | 51 | 48 | 980 | 48 | 30 |
| TSM-20-F-2024-04-18 | 44 | 41 | 532 | 41 | 21 |
| TSM-20-F-2024-04-18 | 53 | 50 | 980 | 50 | 29 |

**Wrong on both sides: 10 pages, 20 snapshots** (financial-statement pages numbered F-nn, and TSLA)

| Document | Page | Printed | `main` | Branch | Snapshots |
|---|---|---|---|---|---|
| BABA-20-F-2023-07-21 | 290 | F- 71 | None | 2 | 107, 108 |
| TSLA-10-K-2023-01-31 | 67 | 67 | 399 | 211 | 35 |
| TSM-20-F-2022-04-14 | 146 | F - 69 | 3 | None | 143, 144 |
| TSM-20-F-2022-04-14 | 148 | F - 71 | 1 | 9 | 147, 148 |
| TSM-20-F-2022-04-14 | 150 | F - 73 | 2 | None | 150, 151 |
| TSM-20-F-2023-04-20 | 112 | F - 31 | 1 | None | 68, 69 |
| TSM-20-F-2023-04-20 | 150 | F - 69 | 1 | None | 151, 152 |
| TSM-20-F-2023-04-20 | 152 | F - 71 | 1 | 9 | 155, 156 |
| TSM-20-F-2023-04-20 | 154 | F - 73 | 2 | None | 158, 159, 160 |
| TSM-20-F-2024-04-18 | 156 | F - 72 | 1 | 8 | 151, 152 |

*Beyond the accepted S3 list*
- The user accepted S3 on 2026-10-06 for Phase A's 8 snapshots on 4 pages: NTRA page 76, and TSM pages 47, 146 and 160.
- The table merge spec's XLSX criterion says "Any change beyond the listed snapshots fails". These 42 snapshots are beyond that list, and on balance they make the guess worse.
- **User decision needed:** extend S3 to this list, or fix `_extract_page_number_from_content` (the guess bug already on `main`) before the branch merges.
- Page numbers and page counts are equal on both sides. The 20 `pages_differences` in `sections.json` are these 10 documents × 2 modes.

**3. Section changes: 0. PASS, with weak coverage for four documents.**
- `sections.json` holds 560 of 560 identical comparisons: 70 documents × 4 filing types × 2 modes. This includes 140 of 140 for each document's own type. `differences` is `[]`.
- For four documents, the identity says little: both sides find almost no own-type section, so the check is equal but nearly empty.
  - **BABA-2023, BABA-2024 and BABA-2026 (20-F)** have only 2–3 own-type sections (Items 17–19), covering 75–87 of 285–299 pages. Their other item headings come out only under the 10-K rules, as 17 sections. For comparison, BABA-2022 has 26 20-F sections covering 307 of 321 pages.
  - **TSM-2026 (20-F)** has no CSS page breaks, so it renders as one page on both sides. It has 0 sections under every filing type. Its page-based checks, such as `display_page` and the page-top PART detector, cannot apply either.

### 4.2 Figures

The Phase A column is the table merge acceptance tooling's `final/` run on 109 documents, which Task 3 reproduced at `1252c45`. It is given for scale only.

| Area | Recent: `main` | Recent: branch | Phase A: `main` → branch |
|---|---|---|---|
| Check 1: `TableParser` value-failure tables with output | 608 | 62 | 305 → 13 |
| Check 1: one-row value failures with output | 8 | 4 | 2 → 1 |
| Check 1: page furniture (no output) | 2,135 | 2,135 (unchanged) | 573 (unchanged) |
| Tables with any finding | 2,851 | 2,316 | 937 → 633 |
| Strict: trace failures / document-modes with warnings | 18 / 18 | 18 / 18 (0 new, 0 misses) | 14 / 14 (0 new) |
| Sections identical | — | 560/560 (own type 140/140) | 872/872 |
| XLSX prepared tables | 7,075 | 7,075; 42 differ in `display_page` only | 3,707; 8 differ in `display_page` only |
| Modes agree (7 checks) | — | 70/70 on every check | 109/109 |
| Alignment: values evaluated | 111,255 | 113,374 | 49,659 → 52,954 |
| Alignment: aligned / misaligned | 53,568 / 57,687 | 113,374 / 0 | 26,609 → 52,954 aligned |
| Alignment: ambiguous header / budget | 1,986 / 0 | 0 / 0 | |
| Alignment findings lines | 18,734 | 0 | → 0 |
| Alignment identities lost / gained | — | 0 / 2,119 | 0 / 3,295 |
| Assignment audit (same-header value merges) | 11,576 steps in 3,501 tables | 11,576/11,576 ok, 0 contradictions | 6,616/6,616 |
| Header retention: values | — | 117,330/117,342 | 54,986/54,990 |
| Header retention: header cells / header-only columns | — | 38,572/38,572 and 2,256/2,256 | 19,594/19,594 and 733/733 |
| Class 8 split cells | 728 in 285 tables | 146 in 41 tables | 180 in 80 → 39 in 5 |
| Years rows read as data | — | 3 | 0 |
| Year runs followed by no data row | — | 2 | 2 |
| Year-run data rows | — | 0 | 0 |
| Identifier-caption tables (T8) | — | 100 | 21 |
| Moved rows (`main` body → branch header) | — | 4,252 rows in 2,177 tables; 0 rule failures; 10 sparse-row-only | 2,270 in 1,609; 0 failures; 45 sparse-row-only |
| Header departures | — | 502 rows in 477 tables (316 data rows); 193 zone cuts, 0 inconsistent | |

### 4.3 Details

**Check 1: the 62 branch value-failure tables**

- **49 are unchanged from `main`, not classified.** They have exactly `main`'s tokens: KO 30, NVO 5, CAT 4, JPM 3, UNH 3, BABA 2 and TSM 2. They were not reviewed table by table.
- **13 are new or changed.** Each is explained here or under "Other findings".
  - **8 new, all F9.** R4 writes a currency code and its amount in one cell, and check 1 reads that cell as text. The tables are TSM-2022 272, 314 and 315, and TSM-2023 278, 288, 328, 329 and 330.
  - **5 changed:**
    - BABA-2026 39: F9, and the sub-label occurrence of 3.2.
    - BABA-2026 108: it keeps only its F2-type tokens `000`, `100`, `400` and `500`. `31` is restored, as for Phase A's BABA 75.
    - JPM-2024 367.
    - TSM-2022 193 and 194.
- **One-row output: 8 → 4.** CAT's table 7 is fixed in all four years (R8). BABA-2022's four one-row tables remain.

**Other findings**

- **New check-1 value tokens: 12 tables.** Every token is still in the branch's output.
  - **F9, 9 tables:** TSM-2022 272, 314 and 315; TSM-2023 278, 288, 328, 329 and 330; and BABA-2026 39.
    - R4 writes a currency code and its amount in one cell, such as `US$ 328.0` or `NT$ 132,734.5`, and check 1 reads it as text.
    - TSM-2023 278 and BABA-2026 39 are also the named sub-label limitation (3.2).
  - **JPM-2024 367: F8, a glued unit suffix.**
    - The token `3` comes from the cell `<ix:nonFraction …>3,617</ix:nonFraction>bps`, whose text `3,617bps` tokenizes as `3`. It is not the `3` of "Level 3".
    - The table is the prior year's version of Phase A's F8 table, JPM-2025 367.
    - Only the role check 1 gives the token changes: label on `main`, body on the branch, which gives the table an empty header line.
  - **TSM-2022 193 and 194: the exhibit-marker pattern.** It is check-side and pre-existing.
    - Check 1 reads the `(n)` footnote markers of headerless exhibit-index continuations as accounting negatives.
    - On `main`, tables 192–194 already report 46 such tokens (15, 22 and 9). The branch reports 48.
    - The two new ones, `-2` and `-5`, are the markers in `4.13 (2)` and `4.37 (5)`. `main`'s header line held them. The branch gives these headerless tables an empty header line, so they are now body text.
    - The output is correct.
- **New check-1 reported tokens: 26 TSM tables (F10).** Each is `3`, an identifier reference that now sits in the header line: TSM-2022 (6 tables), TSM-2023 (6), TSM-2024 (7) and TSM-2026 (7).
- **New check-2 findings: 16 BAC tables (F11), 4 per 10-K.**
  - The tables: 2022 79, 284, 326 and 328; 2023 252, 284, 327 and 329; 2024 256, 289, 332 and 334; 2026 256, 290, 335 and 337.
  - In each, a unit-captioned years row in the header line is paired with a later stacked years row.
  - On BAC-2022 79, `main` flagged rows 3–9, and the branch flags row 2 only.
- **Removed:** 770 check-1 value tokens, 40 reported tokens and 7 check-2 rows.

**Header retention**
- The 12 value misses are one MSFT table in three 10-Ks: FY2023 unit 74, FY2024 unit 76 and FY2026 unit 72.
- They are rows 5–6 × columns 10 and 16, all with outcome `value_no_discriminating_header` and all word-only values.
- These are the same rows, columns and outcome as Phase A's documented MSFT 69 (FY2025).

**Class 8**
- The branch's 41 split tables are BABA 20, TSM 14, TSLA 6 and MSFT 1 (`class8.json`).
- The largest are TSM-2023 82 and TSM-2024 79, with 21 cells each, and TSM-2022 74, with 12. They fall in the range of the TSM tables that Phase A's class 8 leaves split (TSM 79–84), but they were not matched table by table.

**Named limitations of the table merge spec (acceptance counts)**
- **Years rows read as data: 3, all correct.**
  - TSM-2022 376, TSM-2023 391 and TSM-2024 397 each have one data row, `Construction and expansion of 2009 by TSMC | 2018 to 2022`, under the header `Tax-exemption Period`.
  - The year range is that row's value, and the branch rightly renders it in the body.
- **Year runs followed by no data row: 2.**
  - CAT-2022 31 (row 17) and KO-2024 80 (row 4), both reading `Year that the (cost) trend rate reaches (the) ultimate (trend) rate`.
  - They are the same rows as Phase A's CAT 27 and KO 76.
- **T8 identifier captions: 100 tables, all exhibit-index continuations,** the same kind as Phase A's 21.
  - By issuer: JPM 28, KO 22, CAT 16, TSM 12, AMZN 9, UNH 5, CRDO 4 and MU 4.
  - 89 have plain labels such as `4.6`. The other 11 are in the JPM `4.3(b)` / `4.2(a)` and TSM `4.13 (2)` styles.

**Moved rows**
- `rule_ok` holds for all 4,252 rows.
- Reasons: label_empty 3,407, year_run 672, label_unit_text 605, sparse_row_fusion 257, label_period_text 196, label_only 124 and label_year_like 12.
- **The 10 sparse-row-only rows have all been reviewed:**
  - **NTRA, 4 rows** (FY2021, 2022, 2023 and 2025): the performance-graph `Trade Date` row, the shape of Phase A's accepted NTRA 123.
  - **TSM, 4 rows** (FY2021, 2022, 2023 and 2025): `(b) Exhibits to this annual report:`, the shape of Phase A's accepted TSM 216.
  - **BABA-2022 5:** the contents row `LETTER FROM OUR CHAIRMAN AND CEO TO SHAREHOLDERS | ii`. Cosmetic, the same class as TSM 216.
  - **BABA-2022 492:** the shareholding header `Name | (Ordinary shares) | (ADSs) (3) | Percent`. An improvement.

## 5. Recommended order for the strict-failure limitations work

1. **The cover-page telephone-number false failure.** It has the biggest real-world impact.
   - Default strict fails on 9 of 70 recent filings (MSFT ×3, NTRA ×4, TSLA ×2), and on MSFT and NTRA in Phase A. It fails identically on `main` and the branch.
   - The source pool reads `( 650 )` as `-650`, while the output `**(** **650** **)**` reads as `650` (section 2.1).
2. **The `display_page` guess regression: a user decision, then a fix.**
   - 42 snapshots on 24 pages in 10 documents change.
   - The branch is worse on 9 pages (15 snapshots) and better on 5 pages (7 snapshots). Both sides are wrong on 10 pages (20 snapshots).
   - This goes beyond the accepted S3 list (section 4.1).
3. **The wrapped-table and nested-table strict regressions.**
   - The corpus has 0 occurrences: no wrapped or nested table, and 0 header-accounting misses in 13,105 + 5,332 tables.
   - But M3 shows that a table nested in a body row, or in a first `td` row, fails strict on the branch where `main` passes. That is outside the five named limitations (section 3.4).
   - Binding header records for wrapped tables was already the table merge spec's first follow-up.

**Outcome (2026-10-07):** all three are fixed and merged: 1 by PR #7, 2 by PR #8, and 3 by PR #9 (spec revision 18). On `main` after #9, the recent corpus passes default strict on 140 of 140 document-modes.
4. **The remaining named limitations: no harmful occurrence.**
   - Zero-width number: 0. One zero-width character touches a digit, and it trails a date.
   - Page-top PART table: 0. CAT 7 (4 recent, 1 Phase A) is never at a page top.
   - Sub-label currency: 2, both benign, with each code the amount's own currency (section 3.2).

## 6. Open points

- **Settled after this report:**
  - The `display_page` changes (section 4.1): the user chose to fix the guess first. PR #8 (merged) leaves Markdown table lines out of it, which removes all 42 changes.
  - The final re-listing (section 1.6): byte-identical to the approved draft, so MU fiscal 2026 leaves no gap.
  - This folder, the acceptance tooling's `--corpus` change, the spec and the plan were committed to `main` with the user's agreement.
- **Tooling minors deferred in the task reviews.** None changes a result here.
  - Selection:
    - an empty `reportDate` forms its own group;
    - filings of other annual-form variants are not traced (none is in the window).
  - Download:
    - `check_draft` accepts `..` in a document name;
    - a re-fetch replaces a recorded hash silently (see 1.5);
    - a duplicate manifest entry is not refused.
  - Strict:
    - ratio warnings are kept verbatim, which could over-report fail→fail-different (none occurred);
    - `strict.json` records the `main` side as a path, without a commit; it is `c674828`.
  - Prevalence:
    - an `<li>` outside a list counts as a wrapper, which can only add false positives;
    - a zero-width character inside a range such as `2023<ZW>-<ZW>2024` is not tested.
  - Acceptance: `xlsx_detail.py dump` skips an unknown id silently. Both dumps were checked to hold all 70 documents.
