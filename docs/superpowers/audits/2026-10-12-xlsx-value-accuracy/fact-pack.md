# Spec A fact pack: percent scale and identifier misreads

Facts for the next XLSX spec ("Spec A"). Gathered on 2026-10-12, read-only, from `main` at `2898b09` (merge of PR #11).

## Sources and method

- **Code:** `src/sec2md/xlsx_tables.py` (867 lines), `src/sec2md/xlsx_values.py` and `src/sec2md/table_parser.py` in the main checkout.
- **Exports:**
  - `outputs/xlsx-header-detection/new6`: main's current output.
  - `outputs/xlsx-header-detection/base`: the output before header detection.
  - Both cover the same 60 filings: META 18, NVDA 14, RDDT 10 and Others 18.
  - Every count below covers all 60 filings.
- **Units:** the export JSON does not store `units` or `context_before`.
  - `units` was rebuilt with main's `prepare_table`. The inputs were each table's JSON source cells and the context unit lines in `outputs/xlsx-header-detection/investigation-1/instr-new.json`. Context lines do not depend on the header count.
  - The rebuild matched new6's headers and rows exactly for 2,922 of 2,946 non-fallback tables.
  - The 24 tables that differ are exhibit, signature and text tables. They differ because the JSON drops `is_header` (TH) and numeric markers. No percent or identifier finding below depends on them: part D reads new6's own headers.
- **HTML:** the source filings were read with regexes, without the sec2md parser. This read covered caption wordings and the `ix:nonFraction` attributes `scale`, `unitRef` and `format`.
- **Nothing was exported.** No corpus run was made, and no checkout was changed.
- **Scripts** are in `scripts/` beside this file. They were run from a session scratchpad, so their paths need adjusting before a rerun. Their raw JSON outputs were not kept. The scripts:
  - `classify.py` produces `cls-new6.json` and `cls-base.json`.
  - `partb.py` produces `partb.txt` and `split.json`.
  - `recon.py` produces `recon.json`.
  - `partc.py`, `plural.py`, `plural2.py`, `grep_captions2.py` and `captions2.txt` cover part C.
  - `partd.py`, `partd2.py` and `veto.py` produce `ident-new6.json` for part D.
  - `ixattrs.py` and `scale_facts.py` cover the XBRL attributes, and `rules.py` scores the candidate rules.
- **Group labels:** META, NVDA and RDDT are the vault filings. Others are the 18 corpus filings.
- **Notation:** `a → b` means the original text `a` was exported as the cell value `b`.

---

## A. Code map: what decides a value's role and scale

All line numbers are `src/sec2md/xlsx_tables.py` unless another file is named.

### Patterns

| Name | Line | What it does today |
|---|---|---|
| `_UNITS` | 386 | Matches `in thousands/millions/billions`, `per share` or `percentage of revenue`. It is used only by `_header_count` (426) to accept a unit cell in a period row. |
| `_UNIT_LINE` | 387 | Matches a cell starting `(amounts) in thousands/millions/billions`. Such header cells are kept out of flattened header labels (822) and out of leaf-header lookup in `_column_groups` (726, 730). |
| `_UNIT_DECLARATION` | 388-392 | A whole unit caption. There are three alternatives:<br>(1) `in thousands/millions/billions`, optionally followed by `, except (for) par value` or by `, except` and a list of `per share` / `share` / `percent(age)` joined by ` and ` or `, `, ending in an optional ` data` or ` amounts`;<br>(2) `(items/amounts expressed as a) percentage of revenue`;<br>(3) `the following table … expressed as a percentage of revenue`.<br>It is used fullmatch only: as a header unit row (427, 432, 597), for context lines (752), for in-table captions (788) and in `_caption_label` / `_period_text`. **It does not match the plural `percentages`** (`percent(?:age)?` followed by `s`). |
| `_PERCENT` | 393 | `%\|\bpercent(?:age)?\b`. Because of the closing `\b`, **it does not match `percentages`**. It is used on `units` (680), on the label-column header (843) and on cell text in the conflict rule (852). |
| `_PERCENT_UNIT` | 394-396 | Fullmatch only. It accepts a header label or row label that is exactly `%`, `percent`, `percentage`, `(expressed as a) percent(age) of revenue`, or `<words> (%)` / `<words> (percent)`. It does **not** accept `% Change`, `% change`, `As a % of Total Revenues`, `% of Total Revenues`, `Growth Rate`, `Percent Change …`, `Weighted-average Rate` or `Contractual Interest Rate`. |
| `_ROW_UNIT` | 397 | `per share`, `dollars`, `shares` or `in thousands/millions/billions`. It forces role `number` from the header or row label (678) and feeds the conflict rule (853). It is also one of `_identifier_column`'s quantity exemptions (663). |
| `_VALUE` | 398 | Amount words: amount, value, revenue, income, expense, cost, assets, liabilities, cash, shares, inventory, earnings, balance, total. It is used in four places:<br>(a) a header match forces `number` (678);<br>(b) a row-label match gives `number` as a fallback (684);<br>(c) two or more body labels with these words make the table `financial` (834);<br>(d) a header match lets the label column be numeric (843). |
| `_IDENTIFIER` | 399 | `id`, `identifier`, `code`, `number`, `date`, `year`, `exhibit`, `section`, `zip`, `cusip`, `note(s)`, `reference(s)`, `ref(s)`. |
| `_PERIOD` | 403-404 | A strict period heading. `period_header` (672) is true when every header part fullmatches it, and that overrides Rule 3. |

### Functions and rules

- **`_numeric_role(text, header, label, cells, units, financial, percent_header)`, 671-686.** The order is fixed and the first match wins:
  1. **Rule 3:** `_identifier_column(header)` holds and the header is not a period header, so the role is `text` (673-674).
  2. `percent_header`, or the row label fullmatches `_PERCENT_UNIT`, so the role is `percent` (675-676).
  3. The header matches `_VALUE` or `_ROW_UNIT`, or the label matches `_ROW_UNIT`, so the role is `number` (678-679).
  4. `_PERCENT.search(units)`, so the role is `percent`: the table-wide percent (680-681).
  5. A source cell is an `ix:nonFraction`, or the text has `$` or `%`, so the role is `number` (682-683).
  6. `units` is non-empty, the label matches `_VALUE`, or the table is `financial`, so the role is `number` (684-685).
  7. Otherwise the role is `text`.

  A `%` written in the cell does not make the role `percent`. Role `number` plus an explicit `%` is scaled by `convert_cell` (`xlsx_values.py:51`). A plain number in a `number` column stays in percentage points.
- **`_joined(cells)`, 689-696.** It joins one value with the standalone structural fragments `$`, `(`, `)` and `%` through `TableParser._join_structural_text` (`table_parser.py:946-969`). A trailing `%` cell becomes `"<value> %"` (`table_parser.py:968`). If more than one non-marker part is present, the parts are joined with spaces.
- **`_convert_prepared(text, role, origins)`, 699-707.** An origin carrying a numeric superscript or local-link marker gives `@` text with a review reason (700-701). `$ (120)` is rewritten to `($ 120)` for the strict converter (705-706). Everything else goes through `convert_cell`.
- **`convert_cell`, `xlsx_values.py:27-91`.**
  - It accepts one complete US token: an optional sign, `$`, a number, then an optional `%`.
  - Accounting parentheses must wrap the whole token, so `"(29) %"` and `"(29)%"` are **not** supported and become review text.
  - `percent = explicit % or role == 'percent'` (51), and the value is divided by 100 (68-69).
  - `$` together with percent gives "Currency and percent conflict" (52-53).
- **`_column_groups`, 710-742.** A leaf header's columns are consolidated into one copy column only when every body row has at most one non-marker origin (734-736) and every row that has a marker converts cleanly as a `number` (738).
  - So one row `(29) | %` (an unsupported token), a `pts` cell, or a second value under the same leaf header vetoes the merge for **every row** of that column. The `%` then stays in its own copy column (see "split `%`" in B).
  - The later structural pass (807-817, `table_parser.py:906-943`) uses the LEGACY marker set `$ ( ) %` (`table_parser.py:29-34`). `)%` is only in the Markdown renderer's EXTENDED set (`table_parser.py:37-41`).
- **`percent_headers`, 819-826.** For each kept column, the flattened header labels are tested: the column is a percent column if any label fullmatches `_PERCENT_UNIT`. Unit lines (`_UNIT_LINE`) are excluded from the labels.
- **`financial`, 834.** The table is financial when two or more body row labels match `_VALUE`. A financial table makes plain digits `number` instead of `text` (684).
- **`units` collection.** Lines enter `units` from two places, and both require `_UNIT_DECLARATION.fullmatch`:
  - Context before the table (752-753): any line that fullmatches.
  - In-table captions (784-789): a cell up to the first body row that starts in column 0, or right after the label cell, ends at the last column and spans more than one column.

  Neither path ever sees a caption written `except percentages`. `units` is table-wide: one `_PERCENT` hit makes every cell without a `_VALUE` / `_ROW_UNIT` header or label a percent (680).
- **Label column, 842-843.** Copy column 0 is `text` unless its header matches `_VALUE` or `_PERCENT`.
- **Currency/percent conflict, 847-855.** The rule fires when the cell has digits, the column is a percent header, a label fullmatches `_PERCENT_UNIT`, or the text has `%`, **and** `_ROW_UNIT` or `$` appears in `header + label + text`. The cell then becomes text with "Conflicting explicit units; verify the row, column and displayed value units."
- **Review reasons:**
  - The conflict reason (855).
  - "Numeric role unresolved; verify the column heading and units." This applies to role `text` with digits in a non-label column, unless the header is an identifier column (856-857). **Rule 3 cells therefore carry no flag.**
  - "Numeric footnote marker retained…" (701).
  - Converter reasons, for example "Not a complete supported US numeric token…".
  - Each reason is appended to `issues` (858-859), which makes the table `needs_review` (867).
  - A role `percent` without `%` in the text adds only a **note**: "percentage meaning comes from the displayed heading or units" (860-861). It is not an issue.
- **`_identifier_column(header)`, 653-668.** The header is split on ` — ` into parts. A part makes the column an identifier column when all of these hold:
  - it matches `_IDENTIFIER`;
  - it does not fullmatch `_NOTE_REF` (642: `(Note 3)`, `Notes 12(a)`) or `_MATURITY_BUCKET` (643-644: `less/more than N year(s)`, `N-M years`, `N year(s) or more/greater/less`);
  - `_IDENTIFIER` still matches after `_PERIOD_WORDS` is removed (645-647: `(three …) months/years ended`, dates, 4-digit years, `as of/at`);
  - it does not match `_VALUE`, `_ROW_UNIT` or `_QUANTITY` (648: `number of`, `to date`, `per share`);
  - no `_WRAPPED_QUANTITY` (650: `number of`, `grant-date fair value`) spans it and the next part.

  The exemptions are fullmatch on one part, so a footnote marker (`Within 1 year(a)`) or a bucket split across header rows (`Less Than — 1 Year`) defeats them. The cell contents are never consulted.

### Does the snapshot keep ix:nonFraction attributes?

**No.** `SourceCell` (17-28) has only `is_numeric_fact: bool`. `_cell` (90-98) sets it as `any(_visible_nodes(node, ['ix:nonfraction', 'ix:fraction', 'nonfraction', 'fraction']))`, which discards `scale`, `format`, `unitRef`, `decimals`, `sign`, `name` and `contextRef`.

- **Where to capture them:** in `_cell` (90-98). It serves both `snapshot_html_table` (322) and `snapshot_positioned_table` (352).
  - The parser builds the soup with `BeautifulSoup(content, "lxml")` (`parser.py:103`) and snapshots the live DOM (`parser.py:965`). The `ix:` tags are therefore present at that point, and lxml lower-cases the attribute names (`scale`, `unitref`, `format`, `decimals`, `sign`, `name`).
  - A new `SourceCell` field, for example a tuple of `(name, unitref, scale, decimals, format, sign)` per fact, would reach `_numeric_role` through `origins` (840, 845).
  - One copy cell can have several origins (the value plus `$`/`%` markers). The fact sits on the value origin.
- **The audit export has the same gap.** `export_tables._facts` (`docs/superpowers/audits/2026-10-11-xlsx-header-detection/export_tables.py:58-70`) records `contextref`, `name`, text and `sign`, but not `scale`. A future measurement needs `scale` added there.
- **What the source carries.** These figures come from a regex read of the 60 filings:
  - 3,869 `ix:nonFraction` facts with a `pure`/`number` unit and `scale="-2"`; 49 with `scale="-4"`.
  - Every concept found on a mixed-column plain cell that part B classes as a percent row has `unitRef="number"` and `scale="-2"`. Examples: `LongtermDebtWeightedAverageInterestRate`, `DebtInstrumentInterestRateStatedPercentage`, `TierOneRiskBasedCapitalRequired…ToRiskWeightedAssets`, `EffectiveIncomeTaxRateReconciliation*`.
  - Every amount concept there has a currency or share unit with `scale` 0, 3 or 6.
- **Facts with `scale=-2` exported in percentage points (unscaled)** in non-fallback tables:
  - new6: META 67 (4 tables), RDDT 27 (2), Others 88 (16). That is 182 in total.
  - base: 136.

---

## B. Mixed scale, measured on new6 and base

**Scope.** A mixed column is a value column (not column 0) of a table that is not `source_text_only`. It holds at least one number whose original text has `%` and at least one plain number: a complete number token with no `%` and no `$`.

| | Mixed columns | Tables | Plain cells |
|---|---|---|---|
| new6 | 314 | 112 | 2,007 |
| base | 205 | 70 | 1,605 |

**Classification.** Each plain cell was classed by its row. `classify.py` applies these signals in order, and the first decisive one wins:
1. XBRL concept: `Ratio`/`Percent`/`Rate`/`Margin`/`Yield`/`…ToRiskWeightedAssets` against monetary or share concepts. This agrees 100% with the facts' `scale` (see A).
2. Row label words.
3. Section-heading row words.
4. Thousands separator while every `%` value in the column is under 1000.
5. Same-row `%` majority.
6. Header words.
7. Title (`as a percentage of`).
8. Nearest classified neighbour in the column (with a magnitude guard).

Every Others, NVDA and RDDT table was then reviewed by hand, and the rules were corrected until no misclass remained. META is 25 homogeneous tables. **Category (iii) unclear: 0 cells.**

**Outcome** is what the exporter wrote for the cell:
- `unscaled`: a number in percentage points;
- `scaled`: a number that is the displayed number divided by 100;
- `text`;
- `zero`: the value is 0, so scale is moot.

### B.1 Counts per group and status (new6)

| Group | Status | Mixed cols | (i) percent row, **unscaled number** | (i) as text (flagged) | (i) scaled / zero | (ii) amount / count / duration | (iii) |
|---|---|---|---|---|---|---|---|
| META | exported | 79 | **592** (25 tables) | 0 | 0 | 0 | 0 |
| NVDA | exported | 56 | 0 | 0 | 495 scaled (units sentence) | 15 | 0 |
| NVDA | needs_review | 10 | 0 | 0 | 0 | 13 | 0 |
| RDDT | exported | 9 | **55** (4 tables) | 0 | 5 zero | 0 | 0 |
| RDDT | needs_review | 36 | **239** (10 tables) | 0 | 9 scaled, 22 zero | 4 text | 0 |
| Others | exported | 64 | **114** (11 tables) | 0 | 0 | 233 | 0 |
| Others | needs_review | 60 | **72** (12 tables) | 60 (6 tables) | 3 zero | 52 + 24 text | 0 |

- **Category (i) exported as unscaled numbers.** These are silent scale errors.
  - new6: **1,072 cells in 62 tables.** META 592 / 25, RDDT 294 / 14, Others 186 / 23, NVDA 0.
  - base: 926 cells in 39 tables. META 592 / 25, RDDT 288 / 12, Others 46 / 2.
- **New since base: 132 cells in 21 tables.**
  - RDDT: 6 cells, in the `% Change` columns of RDDT 10-Q 2024-Q1 #36 and 2024-Q2 #36. These tables were `source_text_only` on base.
  - Others: 126 cells in 19 tables. Every Others table except AMZN #33, JPM #279, JPM #280 and UNH #12. Those 19 were `source_text_only` on base, apart from KO #12, whose cells were text on base.
  - META: none.
  - In JPM #279 and #280 the plain cells were unscaled on base too. On base the `%` row was also unscaled, because the `%` sat in its own column. What is new in them is the mix.
- **Facts.** XBRL facts sit on 156 of the 1,072 cells: META 67, RDDT 27, Others 62. The rest have none. That covers the META, RDDT and CRM percent-of-revenue tables, AMZN #33, JPM #64 / #73 / #96 / #97 / #113, and KO #12.
- **NVDA.** NVDA has no category (i) cells in joined-`%` columns:
  - 495 plain cells are correctly scaled by the table-wide units sentence (see C);
  - 28 are amounts (SG&A rows of the Operating Expenses tables).
  - NVDA's percent-point errors are all in the split-`%` columns of B.3.

### B.2 Where the `%` sits in category (i) columns

The digit rows are the copy rows that hold digits. "First" and "last" refer to the first and last of these rows. There are 176 category (i) columns:

- **On the first and last rows: 127 columns.**
  - META: 78 columns. `Revenue 100 %` … `Net income 38 %`, and the tax-rate tables (`U.S. federal statutory income tax rate 21.0 %` … `Effective tax rate`).
  - RDDT: 37 columns, of the same two kinds.
  - Others: 2 KO #56 columns, plus 10 columns that also have `%` in the header: CRM #14, #15 and #17, and JPM #96, #97 and #113 (`… % of Total Revenues`, `Total % of IG`, `Percent of retained loans …`).
- **On the first row only: 25 columns.**
  - Others, 13 columns: JPM #279 and #280, BAC #127, CRM #60, and JPM #64's `Capital ratio requirements` columns.
  - With `%` also in the header, 12 columns: CRM #10 and #11, JPM #227 and #229, KO #12 (`Percent Change …`), and RDDT #36 (`% Change`).
- **On the first row of a later block: 23 columns.** Amounts sit above, and the percent rows below start with the `%` row.
  - JPM #64: the `CET1 capital ratio 15.7 %` row sits under the `$ 275,513` amount block.
  - Also JPM #73, #210, #281 and #282, AMZN #33 (`Year-over-year Percentage Growth:` and `Percent of Net Sales:`) and UNH #12.
- **On the last row only: 1 column**, META 10-Q 2022-Q1 #39 c2.
- **In a separate cell:** see B.3.
- **The common convention:** the symbol (`$` or `%`) is printed on the first row of each block, and often on the total. The rows below inherit it.
- **Header percent words** are present in 22 of these columns, but none fullmatches `_PERCENT_UNIT`.

### B.3 Split `%`: the `%` in its own copy column

This is a second, separate form of percentage points: a number whose `%` was left in the next copy column (`(29) | %`, `16 | %`, `(4.5 | )%`).

**new6: 235 cells in 74 tables.** By outcome:

| Group | Unscaled number | Text | Zero |
|---|---|---|---|
| META | 15 cells / 10 tables | 26 / 18 | |
| NVDA | 24 / 6 | 22 / 5 | |
| RDDT | 8 / 6 | 10 / 10 | |
| Others | 76 / 15 | 49 / 14 | 5 / 1 |

- **base: 33 cells**, all Others (23 unscaled / 7 tables, 10 text).
- **Of the 123 unscaled cells in new6, 109 are new since base.** Their tables were `source_text_only` there, for example NVDA 10-Q 2024-Q1 #38 `% Change`, RDDT `% Change` columns, META `% change` tax rows and TSM #8-#12.
- **Mechanism: `_column_groups` refuses to merge the leaf header's columns** (734-739), so every row of the column keeps its `%` apart. Three blockers were observed:
  - **A negative row `(x) | %`.** It joins as `(x) %`, which is not a LEGACY token (`convert_cell` needs the parentheses outermost). 64 of the 96 split columns hold one.
  - **A non-marker unit cell in the column:** NVDA summary tables, `11.9 | pts`.
  - **One leaf header over two independent values:** NFLX `Change — 2024 vs. 2023` covers both `$ 1,323,096` and `7 %`.

  TSM writes `(4.5 | )%`, with `)%` in one cell. That marker exists only in the EXTENDED policy.

### B.4 Category (i) tables (new6, unscaled numbers)

Each entry gives the filing, table, status and title; the cell count; whether the cells are new since base; and the deciding signal. One line per column follows: `label 'original' → exported`.

- **META 10-K 2022-FY #9** [exported] "Consolidated statements of income data (as a percentage of revenue)(1)" — 25 cells; all also on base; signal: title 25
  - `Year Ended December 31, — 2022` (% on copy rows [0, 11]): Cost of revenue `22`→22; Research and development `30`→30; Marketing and sales `13`→13; General and administrative `10`→10; Total costs and expenses `75`→75; Income from operations `25`→25; Income before provision for income taxes `25`→25; Provision for income taxes `5`→5
  - `Year Ended December 31, — 2021` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `21`→21; Marketing and sales `12`→12; General and administrative `8`→8; Total costs and expenses `60`→60; Income from operations `40`→40; Income before provision for income taxes `40`→40; Provision for income taxes `7`→7
  - `Year Ended December 31, — 2020` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `21`→21; Marketing and sales `13`→13; General and administrative `8`→8; Total costs and expenses `62`→62; Income from operations `38`→38; Interest and other income (expense), net `1`→1; Income before provision for income taxes `39`→39; Provision for income taxes `5`→5
- **META 10-K 2022-FY #59** [exported] "U.S. federal statutory income tax rate" — 19 cells; all also on base; signal: fact 19
  - `Year Ended December 31, — 2022` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.0`→1.0; Share-based compensation `2.6`→2.6; Research and development tax credits `(2.4)`→-2.4; Foreign-derived intangible income deduct `(7.0)`→-7.0; Effect of non-U.S. operations `3.0`→3.0; Other `1.3`→1.3
  - `Year Ended December 31, — 2021` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.0`→1.0; Share-based compensation `(1.7)`→-1.7; Research and development tax credits `(1.3)`→-1.3; Foreign-derived intangible income deduct `(3.5)`→-3.5; Effect of non-U.S. operations `0.9`→0.9; Other `0.3`→0.3
  - `Year Ended December 31, — 2020` (% on copy rows [0, 8]): State income taxes, net of federal benef `0.8`→0.8; Share-based compensation `(1.4)`→-1.4; Research and development tax credits `(1.3)`→-1.3; Foreign-derived intangible income deduct `(1.9)`→-1.9; Effect of non-U.S. operations `(2.4)`→-2.4; Research and development capitalization `(3.0)`→-3.0; Other `0.4`→0.4
- **META 10-K 2023-FY #10** [exported] "Consolidated statements of income data (as a percentage of revenue)(1)" — 25 cells; all also on base; signal: title 25
  - `Year Ended December 31, — 2023` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `29`→29; Marketing and sales `9`→9; General and administrative `8`→8; Total costs and expenses `65`→65; Income from operations `35`→35; Interest and other income (expense), net `1`→1; Income before provision for income taxes `35`→35; Provision for income taxes `6`→6
  - `Year Ended December 31, — 2022` (% on copy rows [0, 11]): Cost of revenue `22`→22; Research and development `30`→30; Marketing and sales `13`→13; General and administrative `10`→10; Total costs and expenses `75`→75; Income from operations `25`→25; Income before provision for income taxes `25`→25; Provision for income taxes `5`→5
  - `Year Ended December 31, — 2021` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `21`→21; Marketing and sales `12`→12; General and administrative `8`→8; Total costs and expenses `60`→60; Income from operations `40`→40; Income before provision for income taxes `40`→40; Provision for income taxes `7`→7
- **META 10-K 2023-FY #62** [exported] "U.S. federal statutory income tax rate" — 18 cells; all also on base; signal: fact 18
  - `Year Ended December 31, — 2023` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.1`→1.1; Share-based compensation `(0.6)`→-0.6; Research and development tax credits `(1.5)`→-1.5; Foreign-derived intangible income deduct `(4.3)`→-4.3; Effect of non-U.S. operations `0.9`→0.9; Other `1.0`→1.0
  - `Year Ended December 31, — 2022` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.0`→1.0; Share-based compensation `2.6`→2.6; Research and development tax credits `(2.4)`→-2.4; Foreign-derived intangible income deduct `(7.0)`→-7.0; Effect of non-U.S. operations `3.0`→3.0; Other `1.3`→1.3
  - `Year Ended December 31, — 2021` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.0`→1.0; Share-based compensation `(1.7)`→-1.7; Research and development tax credits `(1.3)`→-1.3; Foreign-derived intangible income deduct `(3.5)`→-3.5; Effect of non-U.S. operations `0.9`→0.9; Other `0.3`→0.3
- **META 10-K 2024-FY #8** [exported] "Consolidated statements of income data (as a percentage of revenue)(1)" — 26 cells; all also on base; signal: title 26
  - `Year Ended December 31, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `6`→6; Total costs and expenses `58`→58; Income from operations `42`→42; Interest and other income (expense), net `1`→1; Income before provision for income taxes `43`→43; Provision for income taxes `5`→5
  - `Year Ended December 31, — 2023` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `29`→29; Marketing and sales `9`→9; General and administrative `8`→8; Total costs and expenses `65`→65; Income from operations `35`→35; Interest and other income (expense), net `1`→1; Income before provision for income taxes `35`→35; Provision for income taxes `6`→6
  - `Year Ended December 31, — 2022` (% on copy rows [0, 11]): Cost of revenue `22`→22; Research and development `30`→30; Marketing and sales `13`→13; General and administrative `10`→10; Total costs and expenses `75`→75; Income from operations `25`→25; Income before provision for income taxes `25`→25; Provision for income taxes `5`→5
- **META 10-K 2024-FY #57** [exported] "U.S. federal statutory income tax rate" — 18 cells; all also on base; signal: fact 18
  - `Year Ended December 31, — 2024` (% on copy rows [0, 8]): State income taxes, net of federal benef `0.7`→0.7; Share-based compensation `(3.7)`→-3.7; Research and development tax credits `(2.9)`→-2.9; Foreign-derived intangible income deduct `(4.9)`→-4.9; Effect of non-U.S. operations `0.2`→0.2; Other `1.4`→1.4
  - `Year Ended December 31, — 2023` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.1`→1.1; Share-based compensation `(0.6)`→-0.6; Research and development tax credits `(1.5)`→-1.5; Foreign-derived intangible income deduct `(4.3)`→-4.3; Effect of non-U.S. operations `0.9`→0.9; Other `1.0`→1.0
  - `Year Ended December 31, — 2022` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.0`→1.0; Share-based compensation `2.6`→2.6; Research and development tax credits `(2.4)`→-2.4; Foreign-derived intangible income deduct `(7.0)`→-7.0; Effect of non-U.S. operations `3.0`→3.0; Other `1.3`→1.3
- **META 10-K 2025-FY #7** [exported] "Consolidated statements of income data (as a percentage of revenue)(1)" — 27 cells; all also on base; signal: title 27
  - `Year Ended December 31, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `29`→29; Marketing and sales `6`→6; General and administrative `6`→6; Total costs and expenses `59`→59; Income from operations `41`→41; Interest and other income, net `1`→1; Income before provision for income taxes `43`→43; Provision for income taxes `13`→13
  - `Year Ended December 31, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `6`→6; Total costs and expenses `58`→58; Income from operations `42`→42; Interest and other income, net `1`→1; Income before provision for income taxes `43`→43; Provision for income taxes `5`→5
  - `Year Ended December 31, — 2023` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `29`→29; Marketing and sales `9`→9; General and administrative `8`→8; Total costs and expenses `65`→65; Income from operations `35`→35; Interest and other income, net `1`→1; Income before provision for income taxes `35`→35; Provision for income taxes `6`→6
- **META 10-K 2025-FY #57** [exported] "U.S. federal statutory income tax rate" — 12 cells; all also on base; signal: fact 12
  - `Year Ended December 31, — 2024` (% on copy rows [0, 8]): State income taxes, net of federal benef `0.7`→0.7; Share-based compensation `(3.7)`→-3.7; Research and development tax credits `(2.9)`→-2.9; Foreign-derived intangible income deduct `(4.9)`→-4.9; Effect of non-U.S. operations `0.2`→0.2; Other `1.4`→1.4
  - `Year Ended December 31, — 2023` (% on copy rows [0, 8]): State income taxes, net of federal benef `1.1`→1.1; Share-based compensation `(0.6)`→-0.6; Research and development tax credits `(1.5)`→-1.5; Foreign-derived intangible income deduct `(4.3)`→-4.3; Effect of non-U.S. operations `0.9`→0.9; Other `1.0`→1.0
- **META 10-Q 2022-Q1 #37** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 17 cells; all also on base; signal: title 17
  - `Three Months Ended March 31, — 2022` (% on copy rows [0, 11]): Cost of revenue `22`→22; Research and development `28`→28; Marketing and sales `12`→12; General and administrative `8`→8; Total costs and expenses `69`→69; Income from operations `31`→31; Interest and other income, net `1`→1; Income before provision for income taxes `32`→32; Provision for income taxes `5`→5
  - `Three Months Ended March 31, — 2021` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `20`→20; Marketing and sales `11`→11; General and administrative `6`→6; Total costs and expenses `57`→57; Income from operations `43`→43; Income before provision for income taxes `44`→44; Provision for income taxes `8`→8
- **META 10-Q 2022-Q1 #39** [exported] "Cost of revenue" — 5 cells; all also on base; signal: block 5
  - `Three Months Ended March 31, — 2022` (% on copy rows [0, 4]): Research and development `7`→7; Marketing and sales `1`→1; General and administrative `1`→1
  - `Three Months Ended March 31, — 2021` (% on copy rows [4]): Research and development `5`→5; Marketing and sales `1`→1
- **META 10-Q 2022-Q2 #37** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 34 cells; all also on base; signal: title 34
  - `Three Months Ended June 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `30`→30; Marketing and sales `12`→12; General and administrative `10`→10; Total costs and expenses `71`→71; Income from operations `29`→29; Interest and other income (expense), net `(1)`→-1; Income before provision for income taxes `28`→28; Provision for income taxes `5`→5
  - `Three Months Ended June 30, — 2021` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `21`→21; Marketing and sales `11`→11; General and administrative `7`→7; Total costs and expenses `57`→57; Income from operations `43`→43; Interest and other income (expense), net `1`→1; Income before provision for income taxes `43`→43; Provision for income taxes `7`→7
  - `Six Months Ended June 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `29`→29; Marketing and sales `12`→12; General and administrative `9`→9; Total costs and expenses `70`→70; Income from operations `30`→30; Income before provision for income taxes `30`→30; Provision for income taxes `5`→5
  - `Six Months Ended June 30, — 2021` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `20`→20; Marketing and sales `11`→11; General and administrative `6`→6; Total costs and expenses `57`→57; Income from operations `43`→43; Income before provision for income taxes `43`→43; Provision for income taxes `7`→7
- **META 10-Q 2022-Q2 #39** [exported] "Cost of revenue" — 12 cells; all also on base; signal: block 12
  - `Three Months Ended June 30, — 2022` (% on copy rows [0, 4]): Research and development `9`→9; Marketing and sales `1`→1; General and administrative `1`→1
  - `Three Months Ended June 30, — 2021` (% on copy rows [0, 4]): Research and development `7`→7; Marketing and sales `1`→1; General and administrative `1`→1
  - `Six Months Ended June 30, — 2022` (% on copy rows [0, 4]): Research and development `8`→8; Marketing and sales `1`→1; General and administrative `1`→1
  - `Six Months Ended June 30, — 2021` (% on copy rows [0, 4]): Research and development `6`→6; Marketing and sales `1`→1; General and administrative `1`→1
- **META 10-Q 2022-Q3 #39** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 32 cells; all also on base; signal: title 32
  - `Three Months Ended September 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `21`→21; Research and development `33`→33; Marketing and sales `14`→14; General and administrative `12`→12; Total costs and expenses `80`→80; Income from operations `20`→20; Income before provision for income taxes `20`→20; Provision for income taxes `4`→4
  - `Three Months Ended September 30, — 2021` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `22`→22; Marketing and sales `12`→12; General and administrative `10`→10; Total costs and expenses `64`→64; Income from operations `36`→36; Income before provision for income taxes `36`→36; Provision for income taxes `5`→5
  - `Nine Months Ended September 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `30`→30; Marketing and sales `13`→13; General and administrative `10`→10; Total costs and expenses `73`→73; Income from operations `27`→27; Income before provision for income taxes `27`→27; Provision for income taxes `5`→5
  - `Nine Months Ended September 30, — 2021` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `21`→21; Marketing and sales `11`→11; General and administrative `8`→8; Total costs and expenses `59`→59; Income from operations `41`→41; Income before provision for income taxes `41`→41; Provision for income taxes `7`→7
- **META 10-Q 2022-Q3 #41** [exported] "Cost of revenue" — 12 cells; all also on base; signal: block 12
  - `Three Months Ended September 30, — 2022` (% on copy rows [0, 4]): Research and development `9`→9; Marketing and sales `1`→1; General and administrative `1`→1
  - `Three Months Ended September 30, — 2021` (% on copy rows [0, 4]): Research and development `6`→6; Marketing and sales `1`→1; General and administrative `1`→1
  - `Nine Months Ended September 30, — 2022` (% on copy rows [0, 4]): Research and development `8`→8; Marketing and sales `1`→1; General and administrative `1`→1
  - `Nine Months Ended September 30, — 2021` (% on copy rows [0, 4]): Research and development `6`→6; Marketing and sales `1`→1; General and administrative `1`→1
- **META 10-Q 2023-Q1 #46** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 17 cells; all also on base; signal: title 17
  - `Three Months Ended March 31, — 2023` (% on copy rows [0, 11]): Cost of revenue `21`→21; Research and development `33`→33; Marketing and sales `11`→11; General and administrative `10`→10; Total costs and expenses `75`→75; Income from operations `25`→25; Income before provision for income taxes `26`→26; Provision for income taxes `6`→6
  - `Three Months Ended March 31, — 2022` (% on copy rows [0, 11]): Cost of revenue `22`→22; Research and development `28`→28; Marketing and sales `12`→12; General and administrative `8`→8; Total costs and expenses `69`→69; Income from operations `31`→31; Interest and other income, net `1`→1; Income before provision for income taxes `32`→32; Provision for income taxes `5`→5
- **META 10-Q 2023-Q2 #46** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 33 cells; all also on base; signal: title 33
  - `Three Months Ended June 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `29`→29; Marketing and sales `10`→10; General and administrative `13`→13; Total costs and expenses `71`→71; Income from operations `29`→29; Income before provision for income taxes `29`→29; Provision for income taxes `5`→5
  - `Three Months Ended June 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `30`→30; Marketing and sales `12`→12; General and administrative `10`→10; Total costs and expenses `71`→71; Income from operations `29`→29; Interest and other income (expense), net `(1)`→-1; Income before provision for income taxes `28`→28; Provision for income taxes `5`→5
  - `Six Months Ended June 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `31`→31; Marketing and sales `10`→10; General and administrative `12`→12; Total costs and expenses `73`→73; Income from operations `27`→27; Income before provision for income taxes `27`→27; Provision for income taxes `5`→5
  - `Six Months Ended June 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `29`→29; Marketing and sales `12`→12; General and administrative `9`→9; Total costs and expenses `70`→70; Income from operations `30`→30; Income before provision for income taxes `30`→30; Provision for income taxes `5`→5
- **META 10-Q 2023-Q3 #46** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 33 cells; all also on base; signal: title 33
  - `Three Months Ended September 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `8`→8; General and administrative `6`→6; Total costs and expenses `60`→60; Income from operations `40`→40; Interest and other income (expense), net `1`→1; Income before provision for income taxes `41`→41; Provision for income taxes `7`→7
  - `Three Months Ended September 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `21`→21; Research and development `33`→33; Marketing and sales `14`→14; General and administrative `12`→12; Total costs and expenses `80`→80; Income from operations `20`→20; Income before provision for income taxes `20`→20; Provision for income taxes `4`→4
  - `Nine Months Ended September 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `30`→30; Marketing and sales `10`→10; General and administrative `10`→10; Total costs and expenses `68`→68; Income from operations `32`→32; Income before provision for income taxes `32`→32; Provision for income taxes `6`→6
  - `Nine Months Ended September 30, — 2022` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `30`→30; Marketing and sales `13`→13; General and administrative `10`→10; Total costs and expenses `73`→73; Income from operations `27`→27; Income before provision for income taxes `27`→27; Provision for income taxes `5`→5
- **META 10-Q 2024-Q1 #33** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 17 cells; all also on base; signal: title 17
  - `Three Months Ended March 31, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `9`→9; Total costs and expenses `62`→62; Income from operations `38`→38; Interest and other income, net `1`→1; Income before provision for income taxes `39`→39; Provision for income taxes `5`→5
  - `Three Months Ended March 31, — 2023` (% on copy rows [0, 11]): Cost of revenue `21`→21; Research and development `33`→33; Marketing and sales `11`→11; General and administrative `10`→10; Total costs and expenses `75`→75; Income from operations `25`→25; Income before provision for income taxes `26`→26; Provision for income taxes `6`→6
- **META 10-Q 2024-Q2 #35** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 34 cells; all also on base; signal: title 34
  - `Three Months Ended June 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `9`→9; Total costs and expenses `62`→62; Income from operations `38`→38; Interest and other income (expense), net `1`→1; Income before provision for income taxes `39`→39; Provision for income taxes `4`→4
  - `Three Months Ended June 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `29`→29; Marketing and sales `10`→10; General and administrative `13`→13; Total costs and expenses `71`→71; Income from operations `29`→29; Income before provision for income taxes `29`→29; Provision for income taxes `5`→5
  - `Six Months Ended June 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `9`→9; Total costs and expenses `62`→62; Income from operations `38`→38; Interest and other income (expense), net `1`→1; Income before provision for income taxes `39`→39; Provision for income taxes `5`→5
  - `Six Months Ended June 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `20`→20; Research and development `31`→31; Marketing and sales `10`→10; General and administrative `12`→12; Total costs and expenses `73`→73; Income from operations `27`→27; Income before provision for income taxes `27`→27; Provision for income taxes `5`→5
- **META 10-Q 2024-Q3 #37** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 35 cells; all also on base; signal: title 35
  - `Three Months Ended September 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `28`→28; Marketing and sales `7`→7; General and administrative `5`→5; Total costs and expenses `57`→57; Income from operations `43`→43; Interest and other income, net `1`→1; Income before provision for income taxes `44`→44; Provision for income taxes `5`→5
  - `Three Months Ended September 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `8`→8; General and administrative `6`→6; Total costs and expenses `60`→60; Income from operations `40`→40; Interest and other income, net `1`→1; Income before provision for income taxes `41`→41; Provision for income taxes `7`→7
  - `Nine Months Ended September 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `8`→8; Total costs and expenses `60`→60; Income from operations `40`→40; Interest and other income, net `1`→1; Income before provision for income taxes `41`→41; Provision for income taxes `5`→5
  - `Nine Months Ended September 30, — 2023` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `30`→30; Marketing and sales `10`→10; General and administrative `10`→10; Total costs and expenses `68`→68; Income from operations `32`→32; Income before provision for income taxes `32`→32; Provision for income taxes `6`→6
- **META 10-Q 2025-Q1 #28** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 18 cells; all also on base; signal: title 18
  - `Three Months Ended March 31, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `29`→29; Marketing and sales `7`→7; General and administrative `5`→5; Total costs and expenses `59`→59; Income from operations `41`→41; Interest and other income, net `2`→2; Income before provision for income taxes `43`→43; Provision for income taxes `4`→4
  - `Three Months Ended March 31, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `9`→9; Total costs and expenses `62`→62; Income from operations `38`→38; Interest and other income, net `1`→1; Income before provision for income taxes `39`→39; Provision for income taxes `5`→5
- **META 10-Q 2025-Q2 #28** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 35 cells; all also on base; signal: title 35
  - `Three Months Ended June 30, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `6`→6; General and administrative `6`→6; Total costs and expenses `57`→57; Income from operations `43`→43; Income before provision for income taxes `43`→43; Provision for income taxes `5`→5
  - `Three Months Ended June 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `9`→9; Total costs and expenses `62`→62; Income from operations `38`→38; Interest and other income, net `1`→1; Income before provision for income taxes `39`→39; Provision for income taxes `4`→4
  - `Six Months Ended June 30, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `28`→28; Marketing and sales `6`→6; General and administrative `6`→6; Total costs and expenses `58`→58; Income from operations `42`→42; Interest and other income, net `1`→1; Income before provision for income taxes `43`→43; Provision for income taxes `4`→4
  - `Six Months Ended June 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `9`→9; Total costs and expenses `62`→62; Income from operations `38`→38; Interest and other income, net `1`→1; Income before provision for income taxes `39`→39; Provision for income taxes `5`→5
- **META 10-Q 2025-Q3 #31** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 36 cells; all also on base; signal: title 36
  - `Three Months Ended September 30, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `30`→30; Marketing and sales `6`→6; General and administrative `7`→7; Total costs and expenses `60`→60; Income from operations `40`→40; Interest and other income, net `2`→2; Income before provision for income taxes `42`→42; Provision for income taxes `37`→37
  - `Three Months Ended September 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `28`→28; Marketing and sales `7`→7; General and administrative `5`→5; Total costs and expenses `57`→57; Income from operations `43`→43; Interest and other income, net `1`→1; Income before provision for income taxes `44`→44; Provision for income taxes `5`→5
  - `Nine Months Ended September 30, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `29`→29; Marketing and sales `6`→6; General and administrative `6`→6; Total costs and expenses `59`→59; Income from operations `41`→41; Interest and other income, net `1`→1; Income before provision for income taxes `43`→43; Provision for income taxes `16`→16
  - `Nine Months Ended September 30, — 2024` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `7`→7; General and administrative `8`→8; Total costs and expenses `60`→60; Income from operations `40`→40; Interest and other income, net `1`→1; Income before provision for income taxes `41`→41; Provision for income taxes `5`→5
- **META 10-Q 2026-Q1 #27** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 18 cells; all also on base; signal: title 18
  - `Three Months Ended March 31, — 2026` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `31`→31; Marketing and sales `5`→5; General and administrative `5`→5; Total costs and expenses `59`→59; Income from operations `41`→41; Interest and other income (expense), net `(2)`→-2; Income before income taxes `39`→39; Provision (benefit) for income taxes `(9)`→-9
  - `Three Months Ended March 31, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `29`→29; Marketing and sales `7`→7; General and administrative `5`→5; Total costs and expenses `59`→59; Income from operations `41`→41; Interest and other income (expense), net `2`→2; Income before income taxes `43`→43; Provision (benefit) for income taxes `4`→4
- **META 10-Q 2026-Q2 #30** [exported] "Condensed consolidated statements of income data (as a percentage of revenue)(1)" — 34 cells; all also on base; signal: title 34
  - `Three Months Ended June 30, — 2026` (% on copy rows [0, 11]): Cost of revenue `19`→19; Research and development `36`→36; Marketing and sales `6`→6; General and administrative `9`→9; Total costs and expenses `69`→69; Income from operations `31`→31; Income before income taxes `31`→31; Provision (benefit) for income taxes `5`→5
  - `Three Months Ended June 30, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `27`→27; Marketing and sales `6`→6; General and administrative `6`→6; Total costs and expenses `57`→57; Income from operations `43`→43; Income before income taxes `43`→43; Provision (benefit) for income taxes `5`→5
  - `Six Months Ended June 30, — 2026` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `34`→34; Marketing and sales `5`→5; General and administrative `7`→7; Total costs and expenses `64`→64; Income from operations `36`→36; Interest and other income (expense), net `(1)`→-1; Income before income taxes `35`→35; Provision (benefit) for income taxes `(2)`→-2
  - `Six Months Ended June 30, — 2025` (% on copy rows [0, 11]): Cost of revenue `18`→18; Research and development `28`→28; Marketing and sales `6`→6; General and administrative `6`→6; Total costs and expenses `58`→58; Income from operations `42`→42; Interest and other income (expense), net `1`→1; Income before income taxes `43`→43; Provision (benefit) for income taxes `4`→4
- **RDDT 10-K 2024-FY #16** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 24 cells; all also on base; signal: title 24
  - `Year ended December 31, — 2024` (% on copy rows [1, 12]): Cost of revenue `10`→10; Research and development `72`→72; Sales and marketing `27`→27; General and administrative `35`→35; Total costs and expenses `144`→144; Income (loss) from operations `(44)`→-44; Other income (expense), net `6`→6; Income (loss) before income taxes `(38)`→-38
  - `Year ended December 31, — 2023` (% on copy rows [1, 12]): Cost of revenue `14`→14; Research and development `55`→55; Sales and marketing `29`→29; General and administrative `20`→20; Total costs and expenses `118`→118; Income (loss) from operations `(18)`→-18; Other income (expense), net `7`→7; Income (loss) before income taxes `(11)`→-11
  - `Year ended December 31, — 2022` (% on copy rows [1, 12]): Cost of revenue `16`→16; Research and development `55`→55; Sales and marketing `34`→34; General and administrative `22`→22; Total costs and expenses `127`→127; Income (loss) from operations `(27)`→-27; Other income (expense), net `2`→2; Income (loss) before income taxes `(25)`→-25
- **RDDT 10-K 2024-FY #57** [needs_review] "Our effective tax rate, as a percentage of pre-tax income (loss), differs from the statuto" — 16 cells; all also on base; signal: fact 16
  - `Year ended December 31, — 2024` (% on copy rows [0, 7]): State income taxes, net of federal benef `5.3`→5.3; Non-deductible compensation `(14.0)`→-14.0; Stock-based compensation `44.4`→44.4; Research and development credits `14.6`→14.6; Change in valuation allowance `(71.0)`→-71.0; Other `(0.2)`→-0.2
  - `Year ended December 31, — 2023` (% on copy rows [0, 7]): State income taxes, net of federal benef `1.2`→1.2; Stock-based compensation `3.9`→3.9; Research and development credits `13.5`→13.5; Change in valuation allowance `(41.1)`→-41.1; Other `(2.9)`→-2.9
  - `Year ended December 31, — 2022` (% on copy rows [0, 7]): State income taxes, net of federal benef `2.3`→2.3; Stock-based compensation `0.6`→0.6; Research and development credits `14.1`→14.1; Change in valuation allowance `(37.4)`→-37.4; Other `(1.0)`→-1.0
- **RDDT 10-K 2025-FY #16** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 24 cells; all also on base; signal: title 24
  - `Year ended December 31, — 2025` (% on copy rows [1, 12]): Cost of revenue `9`→9; Research and development `35`→35; Sales and marketing `23`→23; General and administrative `13`→13; Total costs and expenses `80`→80; Income (loss) from operations `20`→20; Other income (expense), net `4`→4; Income (loss) before income taxes `24`→24
  - `Year ended December 31, — 2024` (% on copy rows [1, 12]): Cost of revenue `10`→10; Research and development `72`→72; Sales and marketing `27`→27; General and administrative `35`→35; Total costs and expenses `144`→144; Income (loss) from operations `(44)`→-44; Other income (expense), net `6`→6; Income (loss) before income taxes `(38)`→-38
  - `Year ended December 31, — 2023` (% on copy rows [1, 12]): Cost of revenue `14`→14; Research and development `55`→55; Sales and marketing `29`→29; General and administrative `20`→20; Total costs and expenses `118`→118; Income (loss) from operations `(18)`→-18; Other income (expense), net `7`→7; Income (loss) before income taxes `(11)`→-11
- **RDDT 10-K 2025-FY #56** [needs_review] "For the years ended December 31, 2024 and 2023, prior to the adoption of ASU 2023-09, our " — 11 cells; all also on base; signal: fact 11
  - `Year ended December 31, — 2024` (% on copy rows [0, 7]): State income taxes, net of federal benef `5.3`→5.3; Non-deductible compensation `(14.0)`→-14.0; Stock-based compensation `44.4`→44.4; Research and development credits `14.6`→14.6; Change in valuation allowance `(71.0)`→-71.0; Other `(0.2)`→-0.2
  - `Year ended December 31, — 2023` (% on copy rows [0, 7]): State income taxes, net of federal benef `1.2`→1.2; Stock-based compensation `3.9`→3.9; Research and development credits `13.5`→13.5; Change in valuation allowance `(41.1)`→-41.1; Other `(2.9)`→-2.9
- **RDDT 10-Q 2024-Q1 #36** [exported] "Results of Operations" — 2 cells; all new since base; signal: header 2
  - `% Change` (% on copy rows [2]): Net income (loss) `845`→845; Adjusted EBITDA(1) `(120)`→-120
- **RDDT 10-Q 2024-Q1 #38** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 17 cells; all also on base; signal: title 17
  - `Three months ended March 31, — 2024` (% on copy rows [2, 13]): Cost of revenue `11`→11; Research and development `180`→180; Sales and marketing `51`→51; General and administrative `100`→100; Total costs and expenses `342`→342; Income (loss) from operations `(242)`→-242; Other income (expense), net `6`→6; Income (loss) before income taxes `(236)`→-236
  - `Three months ended March 31, — 2023` (% on copy rows [2, 13]): Cost of revenue `16`→16; Research and development `66`→66; Sales and marketing `35`→35; General and administrative `25`→25; Total costs and expenses `142`→142; Income (loss) from operations `(42)`→-42; Other income (expense), net `7`→7; Income (loss) before income taxes `(35)`→-35; Income tax expense (benefit) `1`→1
- **RDDT 10-Q 2024-Q2 #36** [exported] "Results of Operations" — 4 cells; all new since base; signal: header 4
  - `% Change` (% on copy rows [2]): Net income (loss) `(75)`→-75; Adjusted EBITDA(1) `(212)`→-212
  - `% Change` (% on copy rows [2]): Net income (loss) `474`→474; Adjusted EBITDA(1) `(158)`→-158
- **RDDT 10-Q 2024-Q2 #38** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 34 cells; all also on base; signal: title 34
  - `Three months ended June 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `10`→10; Research and development `51`→51; Sales and marketing `25`→25; General and administrative `24`→24; Total costs and expenses `110`→110; Income (loss) from operations `(10)`→-10; Other income (expense), net `7`→7; Income (loss) before income taxes `(3)`→-3
  - `Three months ended June 30, — 2023` (% on copy rows [2, 13]): Cost of revenue `16`→16; Research and development `60`→60; Sales and marketing `32`→32; General and administrative `21`→21; Total costs and expenses `129`→129; Income (loss) from operations `(29)`→-29; Other income (expense), net `7`→7; Income (loss) before income taxes `(22)`→-22; Income tax expense (benefit) `1`→1
  - `Six months ended June 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `11`→11; Research and development `111`→111; Sales and marketing `37`→37; General and administrative `60`→60; Total costs and expenses `219`→219; Income (loss) from operations `(119)`→-119; Other income (expense), net `7`→7; Income (loss) before income taxes `(112)`→-112
  - `Six months ended June 30, — 2023` (% on copy rows [2, 13]): Cost of revenue `16`→16; Research and development `63`→63; Sales and marketing `34`→34; General and administrative `23`→23; Total costs and expenses `136`→136; Income (loss) from operations `(36)`→-36; Other income (expense), net `7`→7; Income (loss) before income taxes `(29)`→-29; Income tax expense (benefit) `1`→1
- **RDDT 10-Q 2024-Q3 #38** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 33 cells; all also on base; signal: title 33
  - `Three months ended September 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `10`→10; Research and development `48`→48; Sales and marketing `21`→21; General and administrative `19`→19; Total costs and expenses `98`→98; Income (loss) from operations `2`→2; Other income (expense), net `7`→7; Income (loss) before income taxes `9`→9
  - `Three months ended September 30, — 2023` (% on copy rows [2, 13]): Cost of revenue `13`→13; Research and development `52`→52; Sales and marketing `27`→27; General and administrative `18`→18; Total costs and expenses `110`→110; Income (loss) from operations `(10)`→-10; Other income (expense), net `6`→6; Income (loss) before income taxes `(4)`→-4
  - `Nine months ended September 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `11`→11; Research and development `86`→86; Sales and marketing `31`→31; General and administrative `43`→43; Total costs and expenses `171`→171; Income (loss) from operations `(71)`→-71; Other income (expense), net `7`→7; Income (loss) before income taxes `(64)`→-64
  - `Nine months ended September 30, — 2023` (% on copy rows [2, 13]): Cost of revenue `15`→15; Research and development `59`→59; Sales and marketing `31`→31; General and administrative `21`→21; Total costs and expenses `126`→126; Income (loss) from operations `(26)`→-26; Other income (expense), net `7`→7; Income (loss) before income taxes `(19)`→-19; Income tax expense (benefit) `1`→1
- **RDDT 10-Q 2025-Q1 #40** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 16 cells; all also on base; signal: title 16
  - `Three months ended March 31, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `49`→49; Sales and marketing `23`→23; General and administrative `18`→18; Total costs and expenses `99`→99; Income (loss) from operations `1`→1; Other income (expense), net `5`→5; Income (loss) before income taxes `6`→6
  - `Three months ended March 31, — 2024` (% on copy rows [2, 13]): Cost of revenue `11`→11; Research and development `180`→180; Sales and marketing `51`→51; General and administrative `100`→100; Total costs and expenses `342`→342; Income (loss) from operations `(242)`→-242; Other income (expense), net `6`→6; Income (loss) before income taxes `(236)`→-236
- **RDDT 10-Q 2025-Q2 #41** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 32 cells; all also on base; signal: title 32
  - `Three months ended June 30, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `39`→39; Sales and marketing `24`→24; General and administrative `14`→14; Total costs and expenses `86`→86; Income (loss) from operations `14`→14; Other income (expense), net `4`→4; Income (loss) before income taxes `18`→18
  - `Three months ended June 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `10`→10; Research and development `51`→51; Sales and marketing `25`→25; General and administrative `24`→24; Total costs and expenses `110`→110; Income (loss) from operations `(10)`→-10; Other income (expense), net `7`→7; Income (loss) before income taxes `(3)`→-3
  - `Six months ended June 30, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `43`→43; Sales and marketing `24`→24; General and administrative `15`→15; Total costs and expenses `91`→91; Income (loss) from operations `9`→9; Other income (expense), net `5`→5; Income (loss) before income taxes `14`→14
  - `Six months ended June 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `11`→11; Research and development `111`→111; Sales and marketing `37`→37; General and administrative `60`→60; Total costs and expenses `219`→219; Income (loss) from operations `(119)`→-119; Other income (expense), net `7`→7; Income (loss) before income taxes `(112)`→-112
- **RDDT 10-Q 2025-Q3 #41** [needs_review] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 32 cells; all also on base; signal: title 32
  - `Three months ended September 30, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `34`→34; Sales and marketing `22`→22; General and administrative `12`→12; Total costs and expenses `77`→77; Income (loss) from operations `23`→23; Other income (expense), net `4`→4; Income (loss) before income taxes `27`→27
  - `Three months ended September 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `10`→10; Research and development `48`→48; Sales and marketing `21`→21; General and administrative `19`→19; Total costs and expenses `98`→98; Income (loss) from operations `2`→2; Other income (expense), net `7`→7; Income (loss) before income taxes `9`→9
  - `Nine months ended September 30, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `40`→40; Sales and marketing `23`→23; General and administrative `14`→14; Total costs and expenses `86`→86; Income (loss) from operations `14`→14; Other income (expense), net `4`→4; Income (loss) before income taxes `18`→18
  - `Nine months ended September 30, — 2024` (% on copy rows [2, 13]): Cost of revenue `11`→11; Research and development `86`→86; Sales and marketing `31`→31; General and administrative `43`→43; Total costs and expenses `171`→171; Income (loss) from operations `(71)`→-71; Other income (expense), net `7`→7; Income (loss) before income taxes `(64)`→-64
- **RDDT 10-Q 2026-Q1 #36** [exported] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 16 cells; all also on base; signal: title 16
  - `Three months ended March 31, — 2026` (% on copy rows [2, 13]): Cost of revenue `8`→8; Research and development `31`→31; Sales and marketing `23`→23; General and administrative `10`→10; Total costs and expenses `72`→72; Income (loss) from operations `28`→28; Other income (expense), net `3`→3; Income (loss) before income taxes `31`→31
  - `Three months ended March 31, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `49`→49; Sales and marketing `23`→23; General and administrative `18`→18; Total costs and expenses `99`→99; Income (loss) from operations `1`→1; Other income (expense), net `5`→5; Income (loss) before income taxes `6`→6
- **RDDT 10-Q 2026-Q2 #37** [exported] "Consolidated statements of operations data expressed as a percentage of revenue for the pe" — 33 cells; all also on base; signal: title 33
  - `Three months ended June 30, — 2026` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `29`→29; Sales and marketing `24`→24; General and administrative `9`→9; Total costs and expenses `71`→71; Income (loss) from operations `29`→29; Other income (expense), net `3`→3; Income (loss) before income taxes `32`→32; Income tax expense (benefit) `1`→1
  - `Three months ended June 30, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `39`→39; Sales and marketing `24`→24; General and administrative `14`→14; Total costs and expenses `86`→86; Income (loss) from operations `14`→14; Other income (expense), net `4`→4; Income (loss) before income taxes `18`→18
  - `Six months ended June 30, — 2026` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `30`→30; Sales and marketing `24`→24; General and administrative `9`→9; Total costs and expenses `72`→72; Income (loss) from operations `28`→28; Other income (expense), net `3`→3; Income (loss) before income taxes `31`→31
  - `Six months ended June 30, — 2025` (% on copy rows [2, 13]): Cost of revenue `9`→9; Research and development `44`→44; Sales and marketing `24`→24; General and administrative `15`→15; Total costs and expenses `92`→92; Income (loss) from operations `8`→8; Other income (expense), net `5`→5; Income (loss) before income taxes `13`→13
- **AMZN-10-Q-2025-10-31 #33** [exported] "Operating Expenses" — 39 cells; all also on base; signal: section 39
  - `Three Months Ended September 30, — 2024` (% on copy rows [9, 16]): Fulfillment `11`→11; Technology and infrastructure `5`→5; Sales and marketing `1`→1; General and administrative `6`→6; Other operating expense (income), net `8`→8; Fulfillment `15.5`→15.5; Technology and infrastructure `14.0`→14.0; Sales and marketing `6.7`→6.7; General and administrative `1.7`→1.7; Other operating expense (income), net `0.2`→0.2
  - `Three Months Ended September 30, — 2025` (% on copy rows [9, 16]): Fulfillment `12`→12; Technology and infrastructure `30`→30; Sales and marketing `10`→10; General and administrative `6`→6; Other operating expense (income), net `994`→994; Fulfillment `15.4`→15.4; Technology and infrastructure `16.1`→16.1; Sales and marketing `6.5`→6.5; General and administrative `1.6`→1.6; Other operating expense (income), net `1.6`→1.6
  - `Nine Months Ended September 30, — 2024` (% on copy rows [9, 16]): Fulfillment `9`→9; Technology and infrastructure `2`→2; Sales and marketing `(2)`→-2; General and administrative `(4)`→-4; Other operating expense (income), net `(4)`→-4; Fulfillment `15.7`→15.7; Technology and infrastructure `14.4`→14.4; Sales and marketing `6.8`→6.8; General and administrative `1.9`→1.9; Other operating expense (income), net `0.1`→0.1
  - `Nine Months Ended September 30, — 2025` (% on copy rows [9, 16]): Fulfillment `11`→11; Technology and infrastructure `22`→22; Sales and marketing `7`→7; Other operating expense (income), net `476`→476; Fulfillment `15.5`→15.5; Technology and infrastructure `15.7`→15.7; Sales and marketing `6.5`→6.5; General and administrative `1.7`→1.7; Other operating expense (income), net `0.7`→0.7
- **BAC-10-K-2025-02-25 #127** [needs_review] "(Dollars in millions)" — 10 cells; all new since base; signal: fact 10
  - `Weighted-average Rate` (% on copy rows [2]): Floating `4.71`→4.71; Fixed `5.12`→5.12; Floating `3.44`→3.44; Fixed `6.71`→6.71; Floating `5.65`→5.65; Fixed `5.55`→5.55; Floating `4.99`→4.99; Subordinated notes `6.00`→6.00; Fixed `4.55`→4.55; Floating `4.64`→4.64
- **CRM-10-K-2025-03-05 #10** [needs_review] "Cost of revenues" — 3 cells; all new since base; signal: header 3
  - `Fiscal Year Ended January 31, — % of Total Revenues` (% on copy rows [0]): Sales and marketing `2`→2
  - `Fiscal Year Ended January 31, — % of Total Revenues` (% on copy rows [0]): Sales and marketing `2`→2
  - `Fiscal Year Ended January 31, — % of Total Revenues` (% on copy rows [0]): Sales and marketing `3`→3
- **CRM-10-K-2025-03-05 #11** [needs_review] "Cost of revenues" — 9 cells; all new since base; signal: header 9
  - `Fiscal Year Ended January 31, — % of Total Revenues` (% on copy rows [0]): Research and development `3`→3; Sales and marketing `3`→3; General and administrative `1`→1
  - `Fiscal Year Ended January 31, — % of Total Revenues` (% on copy rows [0]): Research and development `3`→3; Sales and marketing `3`→3; General and administrative `1`→1
  - `Fiscal Year Ended January 31, — % of Total Revenues` (% on copy rows [0]): Research and development `3`→3; Sales and marketing `4`→4; General and administrative `1`→1
- **CRM-10-K-2025-03-05 #14** [needs_review] "Subscription and Support Revenues by Service Offering" — 8 cells; all new since base; signal: header 8
  - `Fiscal Year Ended January 31, — As a % of Total Subscription and Support Revenues` (% on copy rows [0, 5]): Service `25`→25; Platform and Other `21`→21; Marketing and Commerce `15`→15; Integration and Analytics `16`→16
  - `Fiscal Year Ended January 31, — As a % of Total Subscription and Support Revenues` (% on copy rows [0, 5]): Service `25`→25; Platform and Other `21`→21; Marketing and Commerce `15`→15; Integration and Analytics `16`→16
- **CRM-10-K-2025-03-05 #15** [needs_review] "Americas" — 4 cells; all new since base; signal: header 4
  - `Fiscal Year Ended January 31, — As a % of Total Revenues` (% on copy rows [0, 3]): Europe `24`→24; Asia Pacific `10`→10
  - `Fiscal Year Ended January 31, — As a % of Total Revenues` (% on copy rows [0, 3]): Europe `23`→23; Asia Pacific `10`→10
- **CRM-10-K-2025-03-05 #17** [needs_review] "Operating Expenses" — 6 cells; all new since base; signal: header 6
  - `Fiscal Year Ended January 31, — As a % of Total Revenues` (% on copy rows [0, 5]): Sales and marketing `35`→35; General and administrative `7`→7; Restructuring `1`→1
  - `Fiscal Year Ended January 31, — As a % of Total Revenues` (% on copy rows [0, 5]): Sales and marketing `37`→37; General and administrative `7`→7; Restructuring `3`→3
- **CRM-10-K-2025-03-05 #60** [exported] "9. Debt" — 6 cells; all new since base; signal: fact 6
  - `Contractual Interest Rate` (% on copy rows [2]): 2028 Senior Notes `3.70`→3.70; 2028 Senior Sustainability Notes `1.50`→1.50; 2031 Senior Notes `1.95`→1.95; 2041 Senior Notes `2.70`→2.70; 2051 Senior Notes `2.90`→2.90; 2061 Senior Notes `3.05`→3.05
- **JPM-10-K-2025-02-14 #64** [exported] "Selected capital and RWA data" — 12 cells; all new since base; signal: label 12
  - `Standardized — December 31, 2024` (% on copy rows [5]): Tier 1 capital ratio `16.8`→16.8; Total capital ratio `18.5`→18.5
  - `Standardized — December 31, 2023` (% on copy rows [5]): Tier 1 capital ratio `16.6`→16.6; Total capital ratio `18.5`→18.5
  - `Standardized — Capital ratio requirements(b)` (% on copy rows [5]): Tier 1 capital ratio `13.8`→13.8; Total capital ratio `15.8`→15.8
  - `Advanced — December 31, 2024` (% on copy rows [5]): Tier 1 capital ratio `16.9`→16.9; Total capital ratio `17.9`→17.9
  - `Advanced — December 31, 2023` (% on copy rows [5]): Tier 1 capital ratio `16.6`→16.6; Total capital ratio `17.7`→17.7
  - `Advanced — Capital ratio requirements(b)` (% on copy rows [5]): Tier 1 capital ratio `13.0`→13.0; Total capital ratio `15.0`→15.0
- **JPM-10-K-2025-02-14 #73** [exported] "Management’s discussion and analysis" — 8 cells; all new since base; signal: block 8
  - `December 31, 2024 — External TLAC` (% on copy rows [1, 5]): Regulatory requirements `23.0`→23.0; Regulatory requirements `9.5`→9.5
  - `December 31, 2024 — LTD` (% on copy rows [1, 5]): Regulatory requirements `10.5`→10.5; Regulatory requirements `4.5`→4.5
  - `December 31, 2023 — External TLAC` (% on copy rows [1, 5]): Regulatory requirements `23.0`→23.0; Regulatory requirements `9.5`→9.5
  - `December 31, 2023 — LTD` (% on copy rows [1, 5]): Regulatory requirements `10.0`→10.0; Regulatory requirements `4.5`→4.5
- **JPM-10-K-2025-02-14 #96** [exported] "Wholesale credit exposure – maturity and ratings profile" — 3 cells; all new since base; signal: header 3
  - `Ratings profile — Total % of IG` (% on copy rows [0, 9]): Total derivative receivables, net of col `75`→75; Lending-related commitments `66`→66; Subtotal `68`→68
- **JPM-10-K-2025-02-14 #97** [exported] "December 31, 2023 (in millions, except ratios)" — 3 cells; all new since base; signal: header 3
  - `Ratings profile — Total % of IG` (% on copy rows [0, 9]): Total derivative receivables, net of col `77`→77; Lending-related commitments `64`→64; Subtotal `66`→66
- **JPM-10-K-2025-02-14 #113** [exported] "Allocation of allowance for loan losses" — 16 cells; all new since base; signal: header 16
  - `2024 — Percent of retained loans to total retained loans` (% on copy rows [0, 9]): Auto and other `5`→5; Consumer, excluding credit card `29`→29; Credit card `18`→18; Total consumer `47`→47; Secured by real estate `12`→12; Commercial and industrial `13`→13; Other `28`→28; Total wholesale `53`→53
  - `2023 — Percent of retained loans to total retained loans` (% on copy rows [0, 9]): Auto and other `6`→6; Consumer, excluding credit card `31`→31; Credit card `16`→16; Total consumer `47`→47; Secured by real estate `13`→13; Commercial and industrial `13`→13; Other `27`→27; Total wholesale `53`→53
- **JPM-10-K-2025-02-14 #210** [exported] "Other credit quality indicators" — 4 cells; all new since base; signal: fact 4
  - `December 31, 2024` (% on copy rows [14]): Less than 660 `14.3`→14.3; No FICO available `0.2`→0.2
  - `December 31, 2023` (% on copy rows [14]): Less than 660 `14.0`→14.0; No FICO available `0.2`→0.2
- **JPM-10-K-2025-02-14 #227** [needs_review] "(in millions, except ratios)" — 2 cells; all new since base; signal: fact 2
  - `Commercial and industrial — Year ended December 31, 2023 — % of loan modifications to total retained Commercial and industrial loans` (% on copy rows [1]): Other-than-insignificant payment deferra `0.24`→0.24; Other-than-insignificant payment deferra `0.02`→0.02
- **JPM-10-K-2025-02-14 #229** [needs_review] "(in millions, except ratios)" — 1 cells; all new since base; signal: fact 1
  - `Other — Year ended December 31, 2023 — % of loan modifications to total retained Other loans` (% on copy rows [1]): Other-than-insignificant payment deferra `0.07`→0.07
- **JPM-10-K-2025-02-14 #279** [exported] "Note 27 – Regulatory capital" — 11 cells; all also on base; signal: fact 11
  - `Standardized capital ratio requirements — BHC(a)(b)` (% on copy rows [1]): Tier 1 capital `13.8`→13.8; Total capital `15.8`→15.8
  - `Standardized capital ratio requirements — IDI(c)` (% on copy rows [1]): Tier 1 capital `8.5`→8.5; Total capital `10.5`→10.5
  - `Advanced capital ratio requirements — BHC(a)(b)` (% on copy rows [1]): Tier 1 capital `13.0`→13.0; Total capital `15.0`→15.0
  - `Advanced capital ratio requirements — IDI(c)` (% on copy rows [1]): Tier 1 capital `8.5`→8.5; Total capital `10.5`→10.5
  - `Well-capitalized ratios — BHC(d)` (% on copy rows [2]): Total capital `10.0`→10.0
  - `Well-capitalized ratios — IDI(e)` (% on copy rows [1]): Tier 1 capital `8.0`→8.0; Total capital `10.0`→10.0
- **JPM-10-K-2025-02-14 #280** [exported] "Leverage-based capital ratios" — 3 cells; all also on base; signal: fact 3
  - `Capital ratio requirements(a) — BHC` (% on copy rows [1]): SLR `5.0`→5.0
  - `Capital ratio requirements(a) — IDI` (% on copy rows [1]): SLR `6.0`→6.0
  - `Well-capitalized ratios — IDI` (% on copy rows [1]): SLR `6.0`→6.0
- **JPM-10-K-2025-02-14 #281** [needs_review] "December 31, 2024 (in millions, except ratios)" — 8 cells; all new since base; signal: fact 8
  - `Basel III Standardized — JPMorgan Chase & Co.` (% on copy rows [5]): Tier 1 capital ratio `16.8`→16.8; Total capital ratio `18.5`→18.5
  - `Basel III Standardized — JPMorgan Chase Bank, N.A.` (% on copy rows [5]): Tier 1 capital ratio `16.0`→16.0; Total capital ratio `17.2`→17.2
  - `Basel III Advanced — JPMorgan Chase & Co.` (% on copy rows [5]): Tier 1 capital ratio `16.9`→16.9; Total capital ratio `17.9`→17.9
  - `Basel III Advanced — JPMorgan Chase Bank, N.A.` (% on copy rows [5]): Tier 1 capital ratio `17.3`→17.3; Total capital ratio `17.7`→17.7
- **JPM-10-K-2025-02-14 #282** [needs_review] "December 31, 2023 (in millions, except ratios)" — 8 cells; all new since base; signal: fact 8
  - `Basel III Standardized — JPMorgan Chase & Co.` (% on copy rows [5]): Tier 1 capital ratio `16.6`→16.6; Total capital ratio `18.5`→18.5
  - `Basel III Standardized — JPMorgan Chase Bank, N.A.` (% on copy rows [5]): Tier 1 capital ratio `16.2`→16.2; Total capital ratio `17.3`→17.3
  - `Basel III Advanced — JPMorgan Chase & Co.` (% on copy rows [5]): Tier 1 capital ratio `16.6`→16.6; Total capital ratio `17.7`→17.7
  - `Basel III Advanced — JPMorgan Chase Bank, N.A.` (% on copy rows [5]): Tier 1 capital ratio `17.2`→17.2; Total capital ratio `17.6`→17.6
- **KO-10-K-2025-02-20 #12** [needs_review] "Net Operating Revenues" — 6 cells; all new since base; signal: header 6
  - `Percent Change 2024 versus 2023 — Total` (% on copy rows [0]): Europe, Middle East & Africa `1`→1; Latin America `11`→11; North America `11`→11; Asia Pacific `2`→2; Global Ventures `2`→2; Bottling Investments `(21)`→-21
- **KO-10-K-2025-02-20 #56** [exported] "Long-Term Debt" — 9 cells; all new since base; signal: fact 9
  - `December 31, 2024 — Average Rate1` (% on copy rows [1, 10]): U.S. dollar debentures due 2026-2098 `4.8`→4.8; Euro notes due 2024-2053 `3.1`→3.1; Swiss franc notes due 2028 `6.7`→6.7; Other, due through 20982 `7.1`→7.1
  - `December 31, 2023 — Average Rate1` (% on copy rows [1, 10]): U.S. dollar debentures due 2026-2098 `4.8`→4.8; Australian dollar notes due 2024 `2.7`→2.7; Euro notes due 2024-2053 `2.7`→2.7; Swiss franc notes due 2028 `6.0`→6.0; Other, due through 20982 `8.1`→8.1
- **UNH-10-K-2025-02-27 #12** [needs_review] "Number of individuals served by our UnitedHealthcare businesses, by major market segment a" — 7 cells; all also on base; signal: block 7
  - `Column 6` (% on copy rows [4, 13, 15]): Fee-based `9`→9; Total commercial - domestic `9`→9; Medicare Advantage `2`→2; Medicaid `(5)`→-5; Total community and senior `(1)`→-1; Total UnitedHealthcare - domestic medica `5`→5; Commercial - global `(76)`→-76

### B.5 Category (i) cells exported as text (already flagged "Numeric role unresolved")

- **AMZN-10-Q-2025-10-31 #32** [needs_review] 32 cells, e.g. `Three Months Ended September 30, — 2024` International `12`; `Three Months Ended September 30, — 2024` AWS `19`; `Three Months Ended September 30, — 2025` International `14`; `Three Months Ended September 30, — 2025` AWS `20`
- **BAC-10-K-2025-02-25 #63** [needs_review] 6 cells, e.g. `Column 3` 12-month forward rates `4.00`; `Column 3` 12-month forward rates `3.89`; `Column 4` 12-month forward rates `3.94`; `Column 4` 12-month forward rates `3.93`
- **BAC-10-K-2025-02-25 #65** [needs_review] 4 cells, e.g. `Column 3` December 31, 2024 forecast `4.8`; `Column 3` December 31, 2024 forecast `1.4`; `Column 4` December 31, 2024 forecast `4.7`; `Column 4` December 31, 2024 forecast `1.8`
- **CRM-10-K-2025-03-05 #14** [needs_review] 4 cells, e.g. `Growth Rate` Service `10`; `Growth Rate` Platform and Other `10`
- **CRM-10-K-2025-03-05 #15** [needs_review] 2 cells, e.g. `Fiscal Year Ended January 31, — Growth Rate` Europe `9`; `Fiscal Year Ended January 31, — Growth Rate` Asia Pacific `12`
- **KO-10-K-2025-02-20 #12** [needs_review] 12 cells, e.g. `Percent Change 2024 versus 2023 — Volume1` Europe, Middle East & Africa `(1)`; `Percent Change 2024 versus 2023 — Volume1` Latin America `3`; `Percent Change 2024 versus 2023 — Price, Product &` Europe, Middle East & Africa `17`; `Percent Change 2024 versus 2023 — Price, Product &` Latin America `21`

### B.6 Split `%` tables (new6)

- **META 10-K 2022-FY #17** [exported] {'unscaled': 1}; unscaled new since base: 1. `2022 vs 2021 % change` Provision for income taxes `(29)`+`%`→-29
- **META 10-K 2023-FY #14** [needs_review] {'text': 1}; unscaled new since base: 0. `2023 vs 2022 % change` Marketing and sales `(19)`+`%`→(19)
- **META 10-K 2023-FY #15** [needs_review] {'text': 1}; unscaled new since base: 0. `2023 vs 2022 % change` General and administrative `(3)`+`%`→(3)
- **META 10-K 2023-FY #18** [exported] {'unscaled': 1}; unscaled new since base: 1. `2022 vs 2021 % change` Provision for income taxes `(29)`+`%`→-29
- **META 10-K 2024-FY #12** [needs_review] {'text': 2}; unscaled new since base: 0. `2024 vs 2023 % change` Marketing and sales `(8)`+`%`→(8); `2023 vs 2022 % change` Marketing and sales `(19)`+`%`→(19)
- **META 10-K 2024-FY #13** [needs_review] {'text': 2}; unscaled new since base: 0. `2024 vs 2023 % change` General and administrative `(15)`+`%`→(15); `2023 vs 2022 % change` General and administrative `(3)`+`%`→(3)
- **META 10-K 2025-FY #11** [needs_review] {'text': 1}; unscaled new since base: 0. `2024 vs 2023 % change` Marketing and sales `(8)`+`%`→(8)
- **META 10-K 2025-FY #12** [needs_review] {'text': 1}; unscaled new since base: 0. `2024 vs 2023 % change` General and administrative `(15)`+`%`→(15)
- **META 10-Q 2022-Q1 #47** [exported] {'unscaled': 1}; unscaled new since base: 1. `% change` Provision for income taxes `(28)`+`%`→-28
- **META 10-Q 2022-Q2 #41** [exported] {'unscaled': 1}; unscaled new since base: 1. `% change` Cost of revenue `(4)`+`%`→-4
- **META 10-Q 2022-Q2 #47** [exported] {'unscaled': 2}; unscaled new since base: 2. `% change` Provision for income taxes `(29)`+`%`→-29; `% change` Provision for income taxes `(29)`+`%`→-29
- **META 10-Q 2022-Q3 #43** [exported] {'unscaled': 1}; unscaled new since base: 1. `% change` Cost of revenue `(1)`+`%`→-1
- **META 10-Q 2022-Q3 #49** [exported] {'unscaled': 2}; unscaled new since base: 2. `% change` Provision for income taxes `(14)`+`%`→-14; `% change` Provision for income taxes `(25)`+`%`→-25
- **META 10-Q 2023-Q1 #50** [needs_review] {'text': 1}; unscaled new since base: 0. `% change` Marketing and sales `(8)`+`%`→(8)
- **META 10-Q 2023-Q2 #50** [needs_review] {'text': 2}; unscaled new since base: 0. `% change` Marketing and sales `(12)`+`%`→(12); `% change` Marketing and sales `(10)`+`%`→(10)
- **META 10-Q 2023-Q3 #50** [needs_review] {'text': 2}; unscaled new since base: 0. `% change` Marketing and sales `(24)`+`%`→(24); `% change` Marketing and sales `(15)`+`%`→(15)
- **META 10-Q 2023-Q3 #51** [needs_review] {'text': 1}; unscaled new since base: 0. `% change` General and administrative `(39)`+`%`→(39)
- **META 10-Q 2024-Q1 #37** [needs_review] {'text': 1}; unscaled new since base: 0. `% change` Marketing and sales `(16)`+`%`→(16)
- **META 10-Q 2024-Q2 #39** [needs_review] {'text': 2}; unscaled new since base: 0. `% change` Marketing and sales `(14)`+`%`→(14); `% change` Marketing and sales `(15)`+`%`→(15)
- **META 10-Q 2024-Q2 #40** [needs_review] {'text': 1}; unscaled new since base: 0. `% change` General and administrative `(12)`+`%`→(12)
- **META 10-Q 2024-Q3 #41** [needs_review] {'text': 2}; unscaled new since base: 0. `% change` Marketing and sales `(2)`+`%`→(2); `% change` Marketing and sales `(11)`+`%`→(11)
- **META 10-Q 2024-Q3 #42** [needs_review] {'text': 2}; unscaled new since base: 0. `% change` General and administrative `(10)`+`%`→(10); `% change` General and administrative `(2)`+`%`→(2)
- **META 10-Q 2024-Q3 #44** [needs_review] {'unscaled': 4}; unscaled new since base: 4. `% change` Interest income `70`+`%`→70; `% change` Interest expense `(50)`+`%`→-50; `% change` Other income (expense), net `143`+`%`→143; `% change` Interest and other income, net `331`+`%`→331
- **META 10-Q 2024-Q3 #45** [exported] {'unscaled': 1}; unscaled new since base: 1. `% change` Provision for income taxes `(12)`+`%`→-12
- **META 10-Q 2025-Q1 #33** [needs_review] {'text': 1}; unscaled new since base: 0. `% change` General and administrative `(34)`+`%`→(34)
- **META 10-Q 2025-Q1 #36** [exported] {'unscaled': 1}; unscaled new since base: 1. `% change` Provision for income taxes `(4)`+`%`→-4
- **META 10-Q 2025-Q2 #33** [needs_review] {'text': 2}; unscaled new since base: 0. `% change` General and administrative `(27)`+`%`→(27); `% change` General and administrative `(31)`+`%`→(31)
- **META 10-Q 2025-Q3 #36** [needs_review] {'text': 1}; unscaled new since base: 0. `% change` General and administrative `(6)`+`%`→(6)
- **NVDA 10-Q 2024-Q1 #38** [exported] {'unscaled': 3}; unscaled new since base: 3. `Three Months Ended — % Change` Research and development expen `16`+`%`→16; `Three Months Ended — % Change` Sales, general and administrat `7`+`%`→7; `Three Months Ended — % Change` Total operating expenses `(30)`+`%`→-30
- **NVDA 10-Q 2024-Q3 #40** [needs_review] {'text': 2, 'unscaled': 1}; unscaled new since base: 1. `Nine Months Ended — % Change` Compute & Networking `446`+`%`→446; `Nine Months Ended — % Change` All Other `(17)`+`%`→(17); `Nine Months Ended — % Change` Total `552`+`%`→552
- **NVDA 10-Q 2026-Q1 #35** [exported] {'unscaled': 5, 'text': 5}; unscaled new since base: 5. `Quarter-over-Quarter Change` Revenue `12`+`%`→12; `Year-over-Year Change` Revenue `69`+`%`→69; `Quarter-over-Quarter Change` Operating expenses `7`+`%`→7; `Year-over-Year Change` Operating expenses `44`+`%`→44 …
- **NVDA 10-Q 2026-Q2 #35** [exported] {'unscaled': 5, 'text': 5}; unscaled new since base: 5. `Quarter-over-Quarter Change` Revenue `6`+`%`→6; `Year-over-Year Change` Revenue `56`+`%`→56; `Quarter-over-Quarter Change` Operating expenses `8`+`%`→8; `Year-over-Year Change` Operating expenses `38`+`%`→38 …
- **NVDA 10-Q 2026-Q3 #34** [exported] {'unscaled': 5, 'text': 5}; unscaled new since base: 5. `Quarter-over-Quarter Change` Revenue `22`+`%`→22; `Year-over-Year Change` Revenue `62`+`%`→62; `Quarter-over-Quarter Change` Operating expenses `8`+`%`→8; `Year-over-Year Change` Operating expenses `36`+`%`→36 …
- **NVDA 10-Q 2027-Q1 #32** [exported] {'unscaled': 5, 'text': 5}; unscaled new since base: 5. `Quarter-over-Quarter Change` Revenue `20`+`%`→20; `Year-over-Year Change` Revenue `85`+`%`→85; `Quarter-over-Quarter Change` Operating expenses `12`+`%`→12; `Year-over-Year Change` Operating expenses `52`+`%`→52 …
- **RDDT 10-K 2024-FY #23** [exported] {'unscaled': 1}; unscaled new since base: 1. `% Change` Income tax expense (benefit) `(124)`+`%`→-124
- **RDDT 10-K 2025-FY #19** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` Research and development `(16)`+`%`→(16)
- **RDDT 10-K 2025-FY #21** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` General and administrative `(38)`+`%`→(38)
- **RDDT 10-Q 2024-Q1 #45** [exported] {'unscaled': 1}; unscaled new since base: 1. `% Change` Income tax expense (benefit) `(63)`+`%`→-63
- **RDDT 10-Q 2024-Q2 #45** [exported] {'unscaled': 2}; unscaled new since base: 2. `% Change` Income tax expense (benefit) `(115)`+`%`→-115; `% Change` Income tax expense (benefit) `(94)`+`%`→-94
- **RDDT 10-Q 2024-Q3 #45** [exported] {'unscaled': 2}; unscaled new since base: 2. `% Change` Income tax expense (benefit) `(107)`+`%`→-107; `% Change` Income tax expense (benefit) `(96)`+`%`→-96
- **RDDT 10-Q 2025-Q1 #43** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` Research and development `(56)`+`%`→(56)
- **RDDT 10-Q 2025-Q1 #44** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` Sales and marketing `(27)`+`%`→(27)
- **RDDT 10-Q 2025-Q1 #45** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` General and administrative `(71)`+`%`→(71)
- **RDDT 10-Q 2025-Q2 #44** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` Research and development `(33)`+`%`→(33)
- **RDDT 10-Q 2025-Q2 #46** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` General and administrative `(56)`+`%`→(56)
- **RDDT 10-Q 2025-Q3 #44** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` Research and development `(22)`+`%`→(22)
- **RDDT 10-Q 2025-Q3 #46** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` General and administrative `(45)`+`%`→(45)
- **RDDT 10-Q 2025-Q3 #47** [exported] {'unscaled': 1}; unscaled new since base: 1. `% Change` Other income (expense), net `(4)`+`%`→-4
- **RDDT 10-Q 2026-Q1 #41** [needs_review] {'text': 1}; unscaled new since base: 0. `% Change` General and administrative `(6)`+`%`→(6)
- **RDDT 10-Q 2026-Q1 #43** [exported] {'unscaled': 1}; unscaled new since base: 1. `% Change` Income tax expense (benefit) `(202)`+`%`→-202
- **BAC-10-K-2025-02-25 #4** [needs_review] {'text': 3}; unscaled new since base: 0. `Column 2` Women `50`+`%`→50; `Column 4` Women `42`+`%`→42; `Column 6` Women `42`+`%`→42
- **BAC-10-K-2025-02-25 #127** [needs_review] {'text': 1}; unscaled new since base: 0. `Interest Rates` Fixed `0.25 - 8.05`+`%`→0.25 - 8.05
- **CRDO-10-K-2025-07-02 #15** [exported] {'unscaled': 1}; unscaled new since base: 1. `% Change` Provision for income taxes `(52.2)`+`%`→-52.2
- **CRDO-10-K-2025-07-02 #25** [needs_review] {'unscaled': 1}; unscaled new since base: 0. `Column 2` Customer A `86`+`%`→86
- **CRDO-10-K-2025-07-02 #26** [needs_review] {'unscaled': 1}; unscaled new since base: 0. `Year Ended` Customer A `67`+`%`→67
- **CRDO-10-K-2025-07-02 #45** [needs_review] {'unscaled': 7}; unscaled new since base: 0. `Year Ended — May 3, 2025` Statutory federal tax expense  `21`+`%`→21; `Year Ended — May 3, 2025` Research tax credits `(24)`+`%`→-24; `Year Ended — May 3, 2025` Share compensation `(53)`+`%`→-53; `Year Ended — May 3, 2025` Foreign rate differential `(12)`+`%`→-12 …
- **GOOGL-10-Q-2025-10-30 #56** [needs_review] {'text': 5}; unscaled new since base: 0. `Nine Months Ended September 30, 2025 — % Chan` United States `0`+`%`→0; `Nine Months Ended September 30, 2025 — % Chan` EMEA `2`+`%`→2; `Nine Months Ended September 30, 2025 — % Chan` APAC `0`+`%`→0; `Nine Months Ended September 30, 2025 — % Chan` Other Americas `(6)`+`%`→(6) …
- **KO-10-K-2025-02-20 #11** [needs_review] {'text': 2}; unscaled new since base: 0. `Percent Change 2024 versus 2023` Worldwide `1`+`%`→1; `Percent Change 2024 versus 2023` Worldwide `1`+`%`→1
- **KO-10-K-2025-02-20 #12** [needs_review] {'text': 2}; unscaled new since base: 0. `Percent Change 2024 versus 2023 — Foreign Cur` Consolidated `(5)`+`%`→(5); `Percent Change 2024 versus 2023 — Acquisition` Consolidated `(4)`+`%`→(4)
- **KO-10-K-2025-02-20 #54** [needs_review] {'unscaled': 1}; unscaled new since base: 0. `Column 2` Weighted-average discount rate `3.7`+`%`→3.7
- **NFLX-10-K-2025-01-27 #8** [needs_review] {'text': 1}; unscaled new since base: 0. `Change — 2024 vs. 2023` Streaming revenues `16`+`%`→16
- **NFLX-10-K-2025-01-27 #13** [exported] {'unscaled': 1}; unscaled new since base: 1. `Change — 2024 vs. 2023` Cost of revenues `7`+`%`→7
- **NFLX-10-K-2025-01-27 #14** [needs_review] {'text': 1}; unscaled new since base: 0. `Change — 2024 vs. 2023` Sales and marketing `10`+`%`→10
- **NFLX-10-K-2025-01-27 #15** [needs_review] {'text': 1}; unscaled new since base: 0. `Change — 2024 vs. 2023` Technology and development `9`+`%`→9
- **NFLX-10-K-2025-01-27 #16** [needs_review] {'text': 1}; unscaled new since base: 0. `Change — 2024 vs. 2023` General and administrative `(1)`+`%`→(1)
- **NFLX-10-K-2025-01-27 #17** [exported] {'unscaled': 1}; unscaled new since base: 1. `Change — 2024 vs. 2023` Interest expense `3`+`%`→3
- **NFLX-10-K-2025-01-27 #18** [exported] {'unscaled': 1}; unscaled new since base: 1. `Change — 2024 vs. 2023` Interest and other income (exp `647`+`%`→647
- **NFLX-10-K-2025-01-27 #19** [exported] {'unscaled': 1}; unscaled new since base: 1. `Change — 2024 vs. 2023` Provision for income taxes `57`+`%`→57
- **NTRA-10-K-2025-02-28 #36** [needs_review] {'unscaled': 4}; unscaled new since base: 0. `Year ended December 31, — 2023` Expected volatility `70.07`+`%`→70.07; `Year ended December 31, — 2022` Expected volatility `62.30`+`%`→62.30; `Year ended December 31, — 2023` Risk-free interest rate `4.80`+`%`→4.80; `Year ended December 31, — 2022` Risk-free interest rate `4.16`+`%`→4.16
- **TSM-20-F-2025-04-17 #8** [needs_review] {'unscaled': 26, 'text': 20, 'zero': 5}; unscaled new since base: 26. `For the year ended December 31, — 2022` Net revenue `100.0`+`%`→100.0; `For the year ended December 31, — 2023` Net revenue `100.0`+`%`→100.0; `For the year ended December 31, — 2024` Net revenue `100.0`+`%`→100.0; `For the year ended December 31, — 2022` Cost of revenue `(40.4`+`)%`→(40.4 …
- **TSM-20-F-2025-04-17 #9** [needs_review] {'text': 2, 'unscaled': 5}; unscaled new since base: 5. `For the year ended December 31, — % Change in` Net revenue `(4.5`+`)%`→(4.5; `For the year ended December 31, — % Change in` Cost of revenue `7.8`+`%`→7.8; `For the year ended December 31, — % Change in` Gross profit `(12.8`+`)%`→(12.8; `For the year ended December 31, — 2022` Gross margin percentage `59.6`+`%`→59.6 …
- **TSM-20-F-2025-04-17 #10** [needs_review] {'unscaled': 15, 'text': 2}; unscaled new since base: 15. `For the year ended December 31, — % Change in` Research and development `11.7`+`%`→11.7; `For the year ended December 31, — % Change in` Research and development `12.0`+`%`→12.0; `For the year ended December 31, — % Change in` General and administrative `13.7`+`%`→13.7; `For the year ended December 31, — % Change in` General and administrative `37.6`+`%`→37.6 …
- **TSM-20-F-2025-04-17 #11** [needs_review] {'text': 5, 'unscaled': 7}; unscaled new since base: 7. `For the year ended December 31, — % Change in` Share of profits of associates `(37.5`+`)%`→(37.5; `For the year ended December 31, — % Change in` Share of profits of associates `1.7`+`%`→1.7; `For the year ended December 31, — % Change in` Interest income `168.9`+`%`→168.9; `For the year ended December 31, — % Change in` Interest income `44.6`+`%`→44.6 …
- **TSM-20-F-2025-04-17 #12** [needs_review] {'text': 3, 'unscaled': 4}; unscaled new since base: 4. `For the year ended December 31, — % Change in` Income tax expense `(14.9`+`)%`→(14.9; `For the year ended December 31, — % Change in` Net income `(14.3`+`)%`→(14.3; `For the year ended December 31, — % Change in` Net income attributable to sha `(14.2`+`)%`→(14.2; `For the year ended December 31, — 2022` Net margin attributable to sha `43.9`+`%`→43.9 …

---

## C. Table-wide percent captions

### C.1 Tables whose `units` mention percent (new6, main's rebuilt `units`)

- **14 tables, all NVDA.** All are `exported`. They are the "Results of Operations" percent-of-revenue tables: 10-K #8 (FY2024-FY2026), 10-Q 2024-Q1 #36, 2024-Q2 #37, 2024-Q3 #37, 2025-Q1 #39, 2025-Q2 #39, 2025-Q3 #39, 2026-Q1 #36, 2026-Q2 #36, 2026-Q3 #35, 2027-Q1 #34 and 2027-Q2 #37.
- **The caption** is the context sentence "The following table sets forth, for the periods indicated, certain items in our (Condensed) Consolidated Statements of Income expressed as a percentage of revenue."
  - `_UNIT_DECLARATION` fully matches it (alternative 3).
  - It is **not** an `except` clause: the whole table is percent.
- **654 value cells take role `percent` from `units`.**
  - 495 of them got the role only from `units`: the value is the source number / 100, with no `%` in the cell, header or row label.
  - 84 carry `%` anyway, and 75 are blank or a dash.
  - All 495 are genuine percent-of-revenue values. **Misreads from table-wide percent units today: 0.**
- **No other table** in new6 has a percent word in `units`. No META, RDDT or Others table does.

### C.2 Percent captions inside tables (new6 source cells, every status)

- **277 tables** have a caption cell that mentions percent and a scale word:

  | Group | Exported | needs_review | source_text_only |
  |---|---|---|---|
  | META | 71 | 63 | 18 |
  | RDDT | 67 | 14 | 0 |
  | NVDA | 0 | 0 | 4 |
  | Others | 10 | 15 | 15 |

- **Every caption is plural and inside an `except` clause.** None fully matches `_UNIT_DECLARATION`, so none reaches `units`:

  | Cells | Caption |
  |---|---|
  | 159 | `(in millions, except percentages)` |
  | 99 | `(in thousands, except percentages)` |
  | 8 | `(In millions, except percentages)` |
  | 5 | `(in thousands, except revenue per membership and percentages)` |
  | 2 | `(NT$ in millions, except percentages)` |
  | 1 | `(In millions, except percentages and per share amounts)` |
  | 1 | `(in thousands except percentages)` |
  | 1 | `(in millions, except for percentages and wafer shipment)` |
  | 1 | `(in millions, except percentages and per share data)` |

- **Plain-amount cells that took role `percent` from these captions: 0.** The plural is blocked twice: `_UNIT_DECLARATION` does not match it, and `_PERCENT` (`\bpercent(?:age)?\b`) does not match `percentages` either.

Tables with such a caption (`r` = needs_review, `s` = source_text_only, otherwise exported):

- CRDO-10-K-2025-07-02: #9r #10r #11 #12 #13 #14 #15
- META 10-K 2022-FY: #6s #10r #11 #12 #13 #14 #15r #16r #17
- META 10-K 2023-FY: #6s #11r #12 #13 #14r #15r #16r #17r #18
- META 10-K 2024-FY: #5s #9r #10 #11 #12r #13r #14r #15r #16
- META 10-K 2025-FY: #5s #8 #9 #10 #11r #12r #13r #14r #15
- META 10-Q 2022-Q2: #40r #41 #42 #43 #44 #45r #46r #47
- META 10-Q 2022-Q3: #35s #42r #43 #44 #45 #46 #47r #48r #49
- META 10-Q 2023-Q1: #42s #47r #48 #49 #50r #51 #52r #53r #54
- META 10-Q 2023-Q2: #42s #47r #48 #49 #50r #51 #52r #53r #54
- META 10-Q 2023-Q3: #42s #47r #48 #49 #50r #51r #52r #53r #54
- META 10-Q 2024-Q1: #31s #34 #35 #36 #37r #38 #39r #40r #41
- META 10-Q 2024-Q2: #33s #36 #37 #38 #39r #40r #41r #42r #43
- META 10-Q 2024-Q3: #35s #38 #39 #40 #41r #42r #43r #44r #45
- META 10-Q 2025-Q1: #26s #29r #30 #31 #32 #33r #34r #35r #36
- META 10-Q 2025-Q2: #26s #29r #30 #31 #32 #33r #34r #35r #36
- META 10-Q 2025-Q3: #29s #32 #33 #34 #35 #36r #37r #38r #39
- META 10-Q 2026-Q1: #25s #28r #29 #30 #31 #32 #33r #34r #35s
- META 10-Q 2026-Q2: #28s #31 #32 #33 #34 #35 #36r #37r #38s
- MSFT-10-K-2025-07-30: #13s #14s #15s #16s #17s
- NFLX-10-K-2025-01-27: #7r #8r #9s #10s #11s #12s #13 #14r #15r #16r #17 #18 #19 #20s
- NTRA-10-K-2025-02-28: #17 #40r
- NVDA 10-K 2024-FY: #51s
- NVDA 10-K 2025-FY: #50s
- NVDA 10-K 2026-FY: #45s #46s
- RDDT 10-K 2024-FY: #14r #17 #18 #19 #20 #21 #22 #23
- RDDT 10-K 2025-FY: #14 #17 #18 #19r #20 #21r #22 #23 #55r
- RDDT 10-Q 2024-Q1: #36 #39 #40 #41 #42 #43 #44 #45
- RDDT 10-Q 2024-Q2: #36 #39 #40 #41 #42 #43 #44 #45
- RDDT 10-Q 2024-Q3: #36 #39 #40 #41 #42 #43 #44 #45
- RDDT 10-Q 2025-Q1: #38r #41 #42 #43r #44r #45r #46 #47
- RDDT 10-Q 2025-Q2: #39 #42 #43 #44r #45 #46r #47 #48
- RDDT 10-Q 2025-Q3: #39 #42 #43 #44r #45 #46r #47 #48
- RDDT 10-Q 2026-Q1: #34 #37r #38 #39 #40 #41r #42 #43
- RDDT 10-Q 2026-Q2: #35 #38 #39 #40 #41 #42 #43 #44
- TSM-20-F-2025-04-17: #5r #6r #9r #10r #11r #12r
- UNH-10-K-2025-02-27: #9s #10s #11s #12r #39s #43s

### C.3 Caption wordings in the source HTML (60 filings, tag-stripped text)

| Count | Fully matched by `_UNIT_DECLARATION` | Wording | Filers |
|---|---|---|---|
| 177 | no | `(in millions, except percentages)` | META 163, GOOGL 6, TSM 3, UNH 5 |
| 99 | no | `(in thousands, except percentages)` | RDDT 81, CRDO 7, NFLX 9, NTRA 1, UNH 1 |
| 72 | yes | `Percentage of revenue` | META 72 |
| 23 | yes | `percentage of revenue` | META 18, NVDA 2, CRM 1, MU 1, TSLA 1 |
| 23 | no | `percentage of revenues` | CRM 3, GOOGL 8, NFLX 6, NTRA 3, TSLA 2, UNH 1 |
| 21 | no | `(as a percentage of revenue)` | META 21 |
| 14 | yes | `expressed as a percentage of revenue` | NVDA 14 |
| 10 | no | `The following table sets forth our consolidated statements of operations data expressed as a percentage of revenue for the periods indica` | RDDT 10 |
| 8 | no | `(In millions, except percentages)` | NVDA 4, MSFT 4 |
| 5 | no | `percentage of total revenues` | CRM 4, NTRA 1 |
| 5 | no | `(in thousands, except revenue per membership and percentages)` | NFLX 5 |
| 4 | no | `(in percentages)` | META 4 |
| 2 | no | `percentage of total revenue` | CRDO 1, CRM 1 |
| 2 | no | `percentage of total net revenue` | JPM 2 |
| 2 | no | `(NT$ in millions, except percentages)` | TSM 2 |
| 1 | no | `(e.g., percentage of loan book in higher-risk categories)` | BAC 1 |
| 1 | no | `( 2.19 percent of total plan assets)` | BAC 1 |
| 1 | no | `( 1.69 percent of total plan assets)` | BAC 1 |
| 1 | no | `The following table sets forth information derived from our consolidated statements of operations expressed as a percentage of total revenue` | CRDO 1 |
| 1 | no | `(in millions, except per share information and percentages)` | GOOGL 1 |
| 1 | no | `("percentage change in constant currency revenues")` | GOOGL 1 |
| 1 | no | `expressed as a percentage of the current equity price` | JPM 1 |
| 1 | no | `expressed as a percentage of average deposits` | JPM 1 |
| 1 | no | `expressed as a percentage of average loans for the period` | JPM 1 |
| 1 | no | `(In millions, except percentages and per share amounts)` | MSFT 1 |
| 1 | no | `Percentages of total revenue` | MU 1 |
| 1 | no | `(in thousands except percentages)` | NTRA 1 |
| 1 | no | `percentage of net revenue` | TSM 1 |
| 1 | no | `(in millions, except for percentages and wafer shipment)` | TSM 1 |
| 1 | no | `Percentage of net revenue` | TSM 1 |
| 1 | no | `(in millions, except percentages and per share data)` | UNH 1 |

- **How to read the table.** The grep matched parenthesised percent phrases, `expressed as a percentage of …`, `percentage(s) of (total) (net) revenue(s)` and `in percent(ages)`.
  - Rows without a scale word are free-text hits. They include row labels and prose, as well as captions.
  - META's 72 `Percentage of revenue` hits are mostly row labels. As a row label, this phrase fullmatches `_PERCENT_UNIT` and makes its row a percent row (675).
  - The scale captions are the `(… in thousands/millions, except …percentages…)` rows.

- **No singular wording occurs.** Neither `except per share and percentage data` nor `except percent` appears in the 60 filings. Issue I2 of the header-detection audit (the singular form entering `units` and making plain amounts percents) remains **latent**. Its test has to be synthetic.
- **19 plural captions lie outside the table cells:** 296 in the HTML against 277 inside tables. Examples are 11 META and 6 GOOGL captions in paragraphs. They could only reach `units` as context lines, which also need a fullmatch.

### C.4 Counterfactual: the effect of accepting the plural

These figures come from rebuilding new6 with patched patterns (`plural.py` and `plural2.py`).

- **Plural accepted by `_UNIT_DECLARATION` only:**
  - 158 tables gain a percent caption in `units`: META 134, RDDT 17, Others 7.
  - **0 cells** are scaled, because `_PERCENT` still misses `percentages`.
  - 88 text cells become plain numbers, because a non-empty `units` resolves the role. Examples are META #15 `Reality Labs (13,717)`, CRDO #9 and RDDT #19 / #21.
- **Plural accepted by both `_UNIT_DECLARATION` and `_PERCENT`:**
  - **364 number cells are divided by 100:** META 338 in 42 tables, RDDT 21 in 3, Others 5 in 2. Examples: META `Family of Apps 114,450 → 1144.50`, RDDT `Net income (loss) (484,276) → -4842.76`.
  - **680 `$` cells turn into text** with "Currency and percent conflict": META 610 in 134 tables, RDDT 52 in 16, Others 18 in 7.
  - The 88 cells above become /100 numbers.
- **Conclusion:** a units rule must read the `except` clause as "these rows or columns are percents", not as table-wide percent.

---

## D. Identifier misreads (Rule 3), measured on new6

**Scope.** These are value columns (not column 0) of non-fallback tables whose header makes `_identifier_column` true. The header is not a period header, and the column holds digit-bearing cells. Every such cell is exported as text, and Rule 3 adds **no review flag** (856).

|  | Columns | Tables | Cells |
|---|---|---|---|
| new6 | 273 | 101 | 2,497 |
| base | 16 | 4 | 152 |

On base, all 16 columns are NTRA exhibit-index columns, which are true identifiers.

| Group | True identifier columns / tables / cells | Misread columns / tables / cells | Misread cells with XBRL facts |
|---|---|---|---|
| META | 56 / 14 / 528 | 0 | 0 |
| NVDA | 16 / 8 / 180 | **13 / 13 / 76** | 0 |
| RDDT | 28 / 7 / 128 | 0 | 0 |
| Others | 141 / 47 / 1,483 | **19 / 12 / 102** | 16 (TSM #150-152: 13; JPM #166: 3) |
| **Total** | 241 / 76 / 2,319 | **32 / 25 / 178** | 16 |

- **True identifiers carry no XBRL facts** (0 of 2,319 cells).
- **Of the 32 misread columns, 14 are in `needs_review` tables.** These are 7 NVDA summary columns (2024-Q1 to 2025-Q3 and 2027-Q2 #35), AMZN #36 (4 columns), JPM #91, and TSM #150 / #151. The other 18 are in `exported` tables with no flag.
- **New since base.**
  - NTRA #8 (4 cells) and TSM #150-152 (13 cells) were exported as numbers on base. These are **regressions** of header detection.
  - The other 28 misread columns are in tables that were `source_text_only` on base.
- **Headers the brief asked about.**
  - `CUSIP` does not occur as a column header in the corpus.
  - `Exhibit Number` / `Exhibit No.` occur only as column 0 (labels), which is text anyway.
  - `Filing Date` occurs as `Incorporated by Reference — Filing Date` (NTRA #44-#47).
  - `Notes` occurs as TSM #48 / #49 (note references `7`, `8`, …).
  - MSFT #50 `Maturities (calendar year)` holds the years `2028`, `2025`, ….

### D.1 True identifier columns, by matching header part

- `Incorporated by Reference` (word `Reference`): 213 columns, 60 tables, 2089 cells, facts 0; headers `Incorporated by Reference`, `Incorporated by Reference — Exhibit`, `Incorporated by Reference — File No.` …; samples `10-Q`, `10-Q`, `S-3`, `8-K`, `8-K`; tables: BAC-10-K-2025-02-25 #172, BAC-10-K-2025-02-25 #173, BAC-10-K-2025-02-25 #174, BAC-10-K-2025-02-25 #175, CRDO-10-K-2025-07-02 #53, CRM-10-K-2025-03-05 #78 …
- `Exhibit Description` (word `Exhibit`): 9 columns, 9 tables, 61 cells, facts 0; headers `Exhibit Description`; samples `Indenture, dated as of February 5, 2015,`, `Indenture, dated as of October 27, 2016,`, `Indenture, dated as of May 2, 2017, by a`, `Indenture, dated as of October 26, 2017,`, `Indenture, dated as of April 26, 2018, b`; tables: NFLX-10-K-2025-01-27 #74, NFLX-10-K-2025-01-27 #75, RDDT 10-K 2024-FY #65, RDDT 10-Q 2024-Q2 #47, RDDT 10-Q 2024-Q3 #47, RDDT 10-Q 2025-Q1 #49 …
- `Notes` (word `Notes`): 2 columns, 2 tables, 37 cells, facts 0; headers `Notes`; samples `7`, `8`, `9`, `10`, `11`; tables: TSM-20-F-2025-04-17 #48, TSM-20-F-2025-04-17 #49
- `Maturities (calendar year)` (word `year`): 2 columns, 1 tables, 21 cells, facts 0; headers `Maturities (calendar year)`; samples `2028`, `2025`, `2026`, `2026`, `2030`; tables: MSFT-10-K-2025-07-30 #50
- `Issue date` (word `date`): 1 columns, 1 tables, 19 cells, facts 0; headers `Issue date`; samples `9/21/2018`, `1/24/2019`, `11/7/2019`, `3/17/2021`, `5/20/2021`; tables: JPM-10-K-2025-02-14 #266
- `Earliest redemption date(b)` (word `date`): 1 columns, 1 tables, 19 cells, facts 0; headers `Earliest redemption date(b)`; samples `12/1/2023`, `3/1/2024`, `12/1/2024`, `6/1/2026`, `6/1/2026`; tables: JPM-10-K-2025-02-14 #266
- `Issuance Date` (word `Date`): 1 columns, 1 tables, 16 cells, facts 0; headers `Issuance Date`; samples `February 2014`, `February 2015`, `April 2020`, `April 2020`, `October 2016`; tables: NFLX-10-K-2025-01-27 #50
- `Maturity Date` (word `Date`): 2 columns, 2 tables, 14 cells, facts 0; headers `Maturity Date`; samples `October 2029`, `April 2028`, `July 2028`, `July 2031`, `July 2041`; tables: CRM-10-K-2025-03-05 #23, CRM-10-K-2025-03-05 #60
- `Payment Date` (word `Date`): 3 columns, 3 tables, 12 cells, facts 0; headers `Payment Date`; samples `April 11, 2024`, `July 25, 2024`, `October 8, 2024`, `January 9, 2025`, `April 11, 2024`; tables: CRM-10-K-2025-03-05 #22, CRM-10-K-2025-03-05 #6, CRM-10-K-2025-03-05 #70
- `Contractual Maturity Date` (word `Date`): 2 columns, 2 tables, 12 cells, facts 0; headers `Contractual Maturity Date`; samples `January 2028`, `March 2025-January 2031`, `September 2025-June 2035`, `April 2025 (2)`, `December 2025-June 2050`; tables: TSLA-10-K-2025-01-30 #44, TSLA-10-K-2025-01-30 #45
- `Transaction Date` (word `Date`): 1 columns, 1 tables, 9 cells, facts 0; headers `Transaction Date`; samples `January 16, 2025`, `January 17, 2025`, `April 29, 2025`, `April 29, 2025`, `January 17, 2025`; tables: MU-10-K-2025-10-03 #34
- `Date of Issuance` (word `Date`): 1 columns, 1 tables, 7 cells, facts 0; headers `Date of Issuance`; samples `July 2021`, `April 2018`, `July 2021`, `July 2021`, `July 2021`; tables: CRM-10-K-2025-03-05 #60
- `Grant Date` (word `Date`): 3 columns, 3 tables, 3 cells, facts 0; headers `Grant Date`; samples `March 1, 2023`, `March 1, 2024`, `September 1,2024`; tables: TSM-20-F-2025-04-17 #21, TSM-20-F-2025-04-17 #23, TSM-20-F-2025-04-17 #25

The `Incorporated by Reference` columns hold form types (`10-Q`), dotted exhibit numbers (`3.1`, `10.2.8`), file numbers (`001-37478`) and filing dates (`07/09/2015`). Most have lost their leaf header (`Form`, `Exhibit`, …) and show only `Incorporated by Reference`.

### D.2 Misread columns: amounts, rates and percentages under an identifier word

- **NVDA 10-Q 2024-Q1 #35** [needs_review] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `(13) %`; Gross margin `(0.9) pts`; Operating expenses `(30) %`; Income from operations `15 %`; Net income `26 %`
- **NVDA 10-Q 2024-Q2 #36** [needs_review] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `101 %`; Gross margin `26.6 pts`; Operating expenses `10 %`; Operating income `1,263 %`; Net income `843 %`
- **NVDA 10-Q 2024-Q3 #36** [needs_review] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `206 %`; Gross margin `20.4 pts`; Operating expenses `16 %`; Operating income `1,633 %`; Net income `1,259 %`
- **NVDA 10-Q 2025-Q1 #38** [needs_review] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `262 %`; Gross margin `13.8 pts`; Operating expenses `39 %`; Operating income `690 %`; Net income `628 %`
- **NVDA 10-Q 2025-Q2 #38** [needs_review] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `122 %`; Gross margin `5.0 pts`; Operating expenses `48 %`; Operating income `174 %`; Net income `168 %`
- **NVDA 10-Q 2025-Q3 #38** [needs_review] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `94 %`; Gross margin `0.6 pts`; Operating expenses `44 %`; Operating income `110 %`; Net income `109 %`
- **NVDA 10-Q 2026-Q1 #35** [exported] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `69`; Gross margin `(17.9)`; Operating expenses `44`; Operating income `28`; Net income `26`
- **NVDA 10-Q 2026-Q2 #35** [exported] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `56`; Gross margin `(2.7)`; Operating expenses `38`; Operating income `53`; Net income `59`
- **NVDA 10-Q 2026-Q3 #34** [exported] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `62`; Gross margin `(1.2)`; Operating expenses `36`; Operating income `65`; Net income `65`
- **NVDA 10-Q 2027-Q1 #32** [exported] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `85`; Gross margin `14.4`; Operating expenses `52`; Operating income `147`; Net income `211`
- **NVDA 10-Q 2027-Q1 #33** [exported] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 5 cells, facts 0; base source_text_only. Data Center `92 %`; Hyperscale `115 %`; AI Clouds, Industrial, & Ent `74 %`; Edge Computing `29 %`; Total revenue `85 %`
- **NVDA 10-Q 2027-Q2 #35** [needs_review] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 6 cells, facts 0; base source_text_only. Revenue `106 %`; Gross margin `2.6 pts`; Operating expenses `55 %`; Operating income `124 %`; Net income `126 %`
- **NVDA 10-Q 2027-Q2 #36** [exported] `Year-over-Year Change` — part `Year-over-Year Change`, word `Year`, 5 cells, facts 0; base source_text_only. Data Center `117 %`; Hyperscale `102 %`; AI Clouds, Industrial, & Ent `138 %`; Edge Computing `27 %`; Total revenue `106 %`
- **AMZN-10-Q-2025-10-31 #36** [needs_review] `Three Months Ended September 30, — 2024 — At Prior Year Rates (2)` — part `At Prior Year Rates (2)`, word `Year`, 3 cells, facts 0; base source_text_only. Net sales `$ 159,110`; Operating expenses `141,715`; Operating income `17,395`
- **AMZN-10-Q-2025-10-31 #36** [needs_review] `Three Months Ended September 30, — 2025 — At Prior Year Rates (2)` — part `At Prior Year Rates (2)`, word `Year`, 3 cells, facts 0; base source_text_only. Net sales `$ 178,658`; Operating expenses `161,365`; Operating income `17,293`
- **AMZN-10-Q-2025-10-31 #36** [needs_review] `Nine Months Ended September 30, — 2024 — At Prior Year Rates (2)` — part `At Prior Year Rates (2)`, word `Year`, 3 cells, facts 0; base source_text_only. Net sales `$ 451,605`; Operating expenses `404,332`; Operating income `47,273`
- **AMZN-10-Q-2025-10-31 #36** [needs_review] `Nine Months Ended September 30, — 2025 — At Prior Year Rates (2)` — part `At Prior Year Rates (2)`, word `Year`, 3 cells, facts 0; base source_text_only. Net sales `$ 501,952`; Operating expenses `447,289`; Operating income `54,663`
- **CAT-10-K-2025-02-14 #12** [exported] `Full Year 2024 — Profit Before Taxes` — part `Full Year 2024`, word `Year`, 5 cells, facts 0; base source_text_only. Profit `$ 13,373`; Restructuring (income) costs `164`; Other restructuring (income) `195`; Pension/OPEB mark-to-market  `(154)`; Adjusted profit `$ 13,578`
- **CAT-10-K-2025-02-14 #12** [exported] `Full Year 2024 — Profit Per Share` — part `Full Year 2024`, word `Year`, 6 cells, facts 0; base source_text_only. Profit `$ 22.05`; Restructuring (income) costs `0.22`; Other restructuring (income) `0.32`; Pension/OPEB mark-to-market  `(0.23)`; Tax law change related to cu `(0.46)`
- **CAT-10-K-2025-02-14 #12** [exported] `Full Year 2023 — Profit Before Taxes` — part `Full Year 2023`, word `Year`, 5 cells, facts 0; base source_text_only. Profit `$ 13,050`; Other restructuring (income) `194`; Pension/OPEB mark-to-market  `(97)`; Restructuring costs - Longwa `586`; Adjusted profit `$ 13,733`
- **CAT-10-K-2025-02-14 #12** [exported] `Full Year 2023 — Profit Per Share` — part `Full Year 2023`, word `Year`, 6 cells, facts 0; base source_text_only. Profit `$ 20.12`; Other restructuring (income) `0.30`; Pension/OPEB mark-to-market  `(0.14)`; Restructuring costs - Longwa `1.14`; Deferred tax valuation allow `(0.21)`
- **JPM-10-K-2025-02-14 #91** [needs_review] `Within 1 year(a)` — part `Within 1 year(a)`, word `year`, 5 cells, facts 0; base source_text_only. Residential real estate `$ 21,442`; Auto and other `19,404`; Total consumer, excluding cr `$ 40,846`; Total credit card loans `$ 231,799`; Total consumer loans `$ 272,645`
- **JPM-10-K-2025-02-14 #96** [exported] `Maturity profile(d) — After 1 year through 5 years` — part `After 1 year through 5 years`, word `year`, 5 cells, facts 0; base source_text_only. Loans retained `$ 289,199`; Total derivative receivables `7,418`; Lending-related commitments `384,529`; Subtotal `681,146`; Credit derivatives and credi `$ (33,751)`
- **JPM-10-K-2025-02-14 #97** [exported] `Maturity profile(d) — After 1 year through 5 years` — part `After 1 year through 5 years`, word `year`, 5 cells, facts 0; base source_text_only. Loans retained `$ 280,821`; Total derivative receivables `8,970`; Lending-related commitments `368,646`; Subtotal `658,437`; Credit derivatives and credi `$ (28,353)`
- **JPM-10-K-2025-02-14 #99** [exported] `Selected metrics — Credit derivative and credit-related notes (h)` — part `Credit derivative and credit-related notes (h)`, word `notes`, 18 cells, facts 0; base source_text_only. Real Estate `$ (574)`; Consumer & Retail `(4,204)`; Technology, Media & Telecomm `(4,287)`; Industrials `(2,949)`; Healthcare `(3,070)`
- **JPM-10-K-2025-02-14 #105** [exported] `1 year or less(b)` — part `1 year or less(b)`, word `year`, 4 cells, facts 0; base source_text_only. Secured by real estate `$ 12,474`; Commercial and industrial `55,731`; Other `182,722`; Total wholesale loans `$ 250,927`
- **JPM-10-K-2025-02-14 #105** [exported] `After 1 year through 5 years` — part `After 1 year through 5 years`, word `year`, 11 cells, facts 0; base source_text_only. Secured by real estate `$ 57,125`; Commercial and industrial `109,839`; Other `150,346`; Total wholesale loans `$ 317,310`; Secured by real estate `$ 13,119`
- **JPM-10-K-2025-02-14 #166** [exported] `<1 year` — part `<1 year`, word `year`, 3 cells, facts 3; base source_text_only. Investment-grade `$ (89,981)`; Noninvestment-grade `(31,419)`; Total `$ (121,400)`
- **NTRA-10-K-2025-02-28 #8** [exported] `Payments Due by Period — Less Than — 1 Year` — part `1 Year`, word `Year`, 4 cells, facts 0; base exported these cells as numbers. Short-term debt obligations( `$ 80,000`; Interest accrued on debt(2) `362`; Inventory purchase and other `113,818`; Total `$ 194,180`
- **TSM-20-F-2025-04-17 #150** [needs_review] `Non-cash Changes — Other Changes (Note) — NT$` — part `Other Changes (Note)`, word `Note`, 5 cells, facts 5; base exported these cells as numbers. Short-term loans `$ (589.3)`; Bonds payable `303.4`; Long-term bank loans `(5.2)`; Lease liabilities `267.1`; Total `$ (24.0)`
- **TSM-20-F-2025-04-17 #151** [needs_review] `Non-cash Changes — Other Changes (Note) — NT$` — part `Other Changes (Note)`, word `Note`, 4 cells, facts 4; base exported these cells as numbers. Bonds payable `362.1`; Long-term bank loans `11.6`; Lease liabilities `382.0`; Total `$ 755.7`
- **TSM-20-F-2025-04-17 #152** [exported] `Non-cash Changes — Other Changes (Note) — NT$` — part `Other Changes (Note)`, word `Note`, 4 cells, facts 4; base exported these cells as numbers. Bonds payable `387.8`; Long-term bank loans `18.0`; Lease liabilities `373.4`; Total `$ 779.2`

**Why the exemptions miss them:**
- `_MATURITY_BUCKET` is fullmatch on one header part, and its vocabulary is limited.
  - `Within 1 year(a)` and `1 year or less(b)` fail on the footnote marker.
  - `After 1 year through 5 years`, `<1 year` and `Within 1 year` are not in the vocabulary.
  - NTRA's bucket is split across header rows (`Less Than — 1 Year`), so no single part matches.
- `_NOTE_REF` needs a note number: `Other Changes (Note)` has none, and `credit-related notes (h)` names an instrument, not a note.
- After `_PERIOD_WORDS` removes the year, `Full Year 2024` still contains `Year`.
- `Year-over-Year Change` and `At Prior Year Rates (2)` contain `Year`, and nothing exempts them.

---

## E. Observations

### E.1 What separates true cases from misreads

**Identifier columns (D).**
- The cell contents separate the two cleanly; the header alone does not.
- A column-level veto was tested on new6 (`veto.py`). The veto fires when any digit cell is an `ix:nonFraction`, a complete number carrying `$`, `%`, a thousands `,` or accounting `(…)`, or ends in `%` / `pts`.
  - It vetoes **31 of the 32 misread columns and 0 of the 241 true columns.**
  - True identifier cells are dates, form codes, dotted exhibit numbers, file numbers, bare years and small integers. None is formatted as an amount, and none is a fact.
  - The one miss is NVDA 10-Q 2027-Q1 #32 `Year-over-Year Change`. All six values are plain (`85`, `14.4`, `52`, …) because their `%` / `pts` sit in the next copy column (split `%`).
  - Three other NVDA columns (2026-Q1 #35, 2026-Q2 #35, 2026-Q3 #34) are vetoed only by their single negative gross-margin cell, for example `(17.9)`. That makes the veto fragile there.

**Percent rows (B).**
- XBRL is decisive where present: every percent-row fact has `scale="-2"` and unit `number`/`pure`, and every amount fact has a currency/share unit and scale 0/3/6. Facts cover only 156 of 1,072 category (i) cells.
- Without facts, the strongest signal is position. The `%` is on the first row of a block (and often the total), and the plain rows below inherit it.
- Candidate rules, scored against the B classification (1,132 percent-row cells including the 60 text ones, and 341 amount / count / duration cells):

  | Rule | Percent rows fixed | Amounts broken (÷100) | Missed |
  |---|---|---|---|
  | R1: every plain cell in a column with any `%` becomes percent | 1,132 | **341** | 0 |
  | R2: nearest symbol (`$` or `%`) above in the same column, crossing section rows | 1,130 | **64** | 2 |
  | R3: like R2, but stopping at a label-only section row | 362 | 43 | 770 (all META / RDDT percent-of-revenue tables, whose `Costs and expenses:` row sits between `Revenue 100 %` and the rows) |
  | R4: fact (scale) first, else R2 | 1,130 | 55 | 2 |

  The two R2 misses are META 10-Q 2022-Q1 #39 c2, where the `%` appears on the last row only.

- **R2's 64 broken amounts:**
  - NVDA Operating Expenses tables, 28 cells. `% of net revenue 26 %` rows alternate with amount rows. `$` is printed only on the first and total amount rows, so `Sales, general and administrative 633` inherits the `%` above it.
  - NFLX #72 (12) and #7 (9): amounts below an `Operating margin` `%` row.
  - Durations and scores: `Expected term (in years)` / `Expected life (years)` rows (BABA #48, CRDO #27 / #37, TSLA #55, UNH #52; 11 cells) and JPM #201 `Weighted-average FICO` (2).
  - TSM #10 (2).
  - Label words (`years`, `term`, `life`, `FICO`) and the fact unit (`y`, `number` with scale 0) would catch the durations and scores. The NVDA case needs something else: there the `%` row names itself (`% of net revenue`), so its `%` does not carry to the next row.

### E.2 Risks

- **JPM #64 against JPM #279.**
  - A column-level rule ("a `%` anywhere makes the column percent", R1) fixes #279 / #280. It also turns JPM #64's `Tier 1 capital 294,881` into 2,948.81. Overall it breaks 341 amounts.
  - JPM #64 itself has percent-point errors too: `Tier 1 capital ratio 16.8`, `Total capital ratio 18.5` and the `Capital ratio requirements` columns, 12 cells, new since base. The fix must be row-level: R2 handles both #64 and #279 correctly.
  - #64 carries no XBRL facts, so a facts-only rule does not help there. #281 / #282, the Note 27 version of the same data, do carry them.
- **R2 against NVDA Operating Expenses.** Nearest-symbol inheritance scales the SG&A amounts by 1/100, in 8 NVDA tables with 28 cells. Five of these tables are `exported`.
- **Header words alone are unsafe.**
  - `Change` heads both `$ Change` and `% Change`.
  - `Rate` is in `At Prior Year Rates`, an amount column.
  - `% of Total Revenues` (CRM) is genuinely percent.
  - `_PERCENT_UNIT` recognises none of `% Change`, `As a % of …`, `Growth Rate` or `Percent Change …` today.
- **Plural captions.** Making either regex read `percentages` without honouring `except` would scale 364 META, RDDT and Others amounts and flag 680 `$` cells (C.4).
- **Negative percentages.** `(x) %` and `(x)%` are not convertible by `convert_cell` even when joined, and one such row splits the whole column (B.3).
  - A fix to grouping must also teach the converter `(x) %` → −x/100.
  - Otherwise the merged cells become review text instead of the split numbers they are now.
- **`pts`.** NVDA's `Gross margin 11.9 pts` is a change in percentage points, not a percent of anything. Treating `pts` like `%` would write 0.119, a format change the spec has to decide on.
- **Rule 3 against split `%`.** The NVDA `Year-over-Year Change` columns are both misread identifiers and split `%`. Lifting Rule 3 alone would export `69` (percentage points) as a plain number. The two fixes have to land together, or the column needs a flag.
- **Content veto edge cases.** A note-reference column written `(7)` or a footnote cell `(1)` would trip an accounting-parentheses veto. Neither occurs in the corpus's true columns, but synthetic tests should cover them, together with `CUSIP`, which never occurs.
- **NVDA percent-of-revenue tables** depend on the context sentence matching `_UNIT_DECLARATION` alternative 3. They are correct today with 495 cells, and a units refactor must keep them.
