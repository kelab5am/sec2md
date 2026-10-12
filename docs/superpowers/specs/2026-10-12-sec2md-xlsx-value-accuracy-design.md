# sec2md XLSX Value Accuracy Design

Date: 2026-10-12 (revision 2)

Status: Draft for review. Not implemented.

Scope:
- `src/sec2md/xlsx_tables.py` and `src/sec2md/xlsx_values.py` only.
- The Markdown renderer, strict's numeric trace and the table completeness check must not change.
- Nor must `table_parser.py` (including its marker sets), `_header_count`, `_PERIOD`, `_UNIT_DECLARATION`, or the header detection merged in PR #11.

Evidence: [`../audits/2026-10-12-xlsx-value-accuracy/fact-pack.md`](../audits/2026-10-12-xlsx-value-accuracy/fact-pack.md), measured on `main` at `2898b09` on the 60 filings of the header-detection acceptance.

## Purpose

The XLSX export must never show a number that may be wrong. Two problems break that today. In both, the exporter decides a value's meaning without proof.

1. **Percent scale.** The exporter writes percents as fractions: `15.7 %` becomes `0.157`. Filings print `%` on the first row of a block and often on the total; the rows between are plain numbers.
   - Today such a plain number is exported in percentage points. `Revenue 100 %` gives `1.0`, while `Cost of revenue 18` gives `18`: a hundred times its neighbour's scale, with no flag.
   - The count is 1,072 cells in 62 tables. 592 are in META's 10-K and 10-Q MD&A tables, wrong before PR #11 too.
   - The examples include RDDT `% Change` (`Revenue 0.54`, `Net income (loss) -75`), JPM capital ratio requirements (`0.123` beside `13.8`), and CRM, KO and BAC interest rates.
   - A second form: in `(29) | %` the sign sits in its own cell and does not join the number. That gives 123 more unscaled numbers.
   - A latent bug: a caption `(In millions, except per share and percentage data)` makes `_numeric_role` read every plain amount as a percent (`161,690` → `1616.90`).
2. **Identifier misreads.** `_identifier_column` (Rule 3 of the header-detection spec) keeps a column as text when a header part holds an identifier word (`year`, `note`, `date`, `number` …). It never looks at the cells.
   - Today 32 columns (178 cells) of amounts are exported as text with no flag.
   - The headers include `Within 1 year(a)`, `After 1 year through 5 years` and `<1 year` (JPM), `Less Than — 1 Year` (NTRA), `Other Changes (Note)` (TSM), `credit-related notes (h)` (JPM), `Full Year 2024` (CAT), `Year-over-Year Change` (NVDA) and `At Prior Year Rates` (AMZN).
   - Two were numbers before PR #11: NTRA #8 and TSM #150–#152.

**Principle (user decision, 2026-10-12).** A value is converted only when evidence proves its meaning. That evidence is the cell's own `%` or `$`, an explicit header or row label, or the inline XBRL fact in the cell. Without proof the cell stays source text and carries a review reason. There is no best-guess conversion, with or without a flag.

How it applies to numbers:
- A number exported equal to its displayed digits, in the table's displayed units, is what the filing shows.
- A conversion that changes the displayed number needs proof. Dividing by 100 for a percent is such a conversion.
- So does any rule that turns a text role into a number when the column's own evidence conflicts (Rule I).
- Plain numbers in columns that carry no evidence of another scale keep today's behaviour (see review history, round 1, finding 1).

## Review history

**Round 1** (Codex on gpt-6.1-sol, revision 1 → 2). Each finding was checked against the code before it was accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: unmixed columns convert plain numbers through `_VALUE` or `financial` without proof. | Rejected | A plain number exported as displayed changes nothing the filing shows; only a change of scale needs proof. Requiring proof for every plain number would turn nearly every statement cell into text. The principle section now says this explicitly. |
| 2. High: I1 lifted the identifier veto for every cell when one cell held `$`, so `Notes \| 7, 8, $12` converted the note references. | Confirmed | I1 is now per cell: only a cell with its own quantity proof converts. Plain cells in such a column stay text with a review reason. |
| 3. High: the percent-declaration prefixes accepted `Percentage of completion revenue` and `Percentage point change`. | Confirmed | Word declarations are now a closed list; `point(s)` excludes; negative tests added. |
| 4. High: a negative XBRL `scale` does not prove a percent (`5` years at `scale="-1"`). | Confirmed | A percent fact needs a pure unit and `scale="-2"` exactly. |
| 5. High: no defined fact-to-display association. Sign could apply twice (BAC #146 `(0.3)` with `sign="-"`), ranges hold two facts (AMZN #20), and transformed formats differ. | Confirmed | A fact proves only when it is the only fact on the value origin, its format is a supported US numeric format, its displayed digits equal the cell's token, and its sign agrees with the displayed sign. The value always comes from the displayed token. |
| 6. High: conflicting percent proofs (`50 %` with a pure fact at `scale="-4"`) had no conflict rule. | Confirmed | Proofs must agree. A pure fact whose scale is not -2 under a displayed `%`, or any amount fact under a displayed `%`, is a conflict. |
| 7. Medium: the split-`%` repair needs an attachment pass; `_column_groups` correctly refuses NFLX #13 (`$ \| 1,323,096 \| 7 \| %` under one leaf). | Confirmed | P4 specifies an XLSX-only attachment pass before grouping, with provenance and the unresolved-span fallback preserved. |
| 8. Medium: `(in percent)` and `(in percentages)` cannot enter `units`, which requires `_UNIT_DECLARATION.fullmatch`. | Confirmed | Table-wide percent declarations get their own pattern and collector, run on the same positions. `_UNIT_DECLARATION` is unchanged. |
| 9. Medium: table-wide percent plus a local non-percent unit (`Income per share \| 2.50`) is a number today (`test_wrapped_table_percent_context_and_local_unit_exception`); revision 1 made it a conflict. | Confirmed | Explicit precedence: a local proof overrides a table-wide declaration. Conflicts arise only between proofs at the cell, row or column level. |
| 10. Medium: "zero converts as 0" overrode the negative-zero safety (`-0`, `(0)`, `-0%` stay review text). | Confirmed | Zero is exempt only after the converter accepts the token, so negative zeros keep their review text. |
| 11. Medium: fact scaling can lose display precision (`0.005` formatted `0%`). | Confirmed | Moot for `scale="-2"`, whose value is the displayed number / 100 with the displayed decimals. Tests check `number_format`. |
| 12. Medium: acceptance must be anchored to a fixed manifest of baseline source coordinates, not to a re-classification of the new output. | Confirmed | The manifest is built from the baseline before implementation, and each entry needs a disposition. |

## Definitions

- **Copy cell, value origin, row label, header labels:** as in `prepare_table()`.
  - A copy cell joins its source origins: the value and its structural fragments.
  - The value origin is the origin holding the digits.
  - The row label is column 0's text.
  - The header labels are the copy column's flattened header levels, excluding unit lines.
- **Digit cell:** a copy cell whose joined text contains a digit.
- **Complete token:** text that `convert_cell` accepts as one number, with its optional `$`, `%`, sign and accounting parentheses.
- **Percent declaration.** A header label or row label is a percent declaration when it matches one of these forms:
  1. A `%` symbol as a word:
     - the label starts with `%`: `% Change`, `% change`, `% of Total Revenues`;
     - `% of` or `% change` appears anywhere: `Total % of IG`, `As a % of net sales`;
     - the label ends with `(%)` or `%`: `Gross margin %`.
  2. A word form, the whole label case-insensitive, optionally followed by a footnote marker:
     - `percent`, `percentage`, `percentages`;
     - `percent change`, `percentage change`;
     - `percent of <base>`, `percentage of <base>` and `as a percent(age) of <base>`, where `<base>` is `revenue(s)`, `total revenue(s)`, `net revenue(s)`, `total net revenue(s)`, `net sales` or `sales`;
     - `percent of retained loans to total retained loans`.
  3. A full match of today's `_PERCENT_UNIT`.

  A label is never a declaration when it contains `$`, `point` or `points`, or `pts`. Not declarations: `Percentage of completion revenue`, `Percentage point change`, `Increase in percentage of completion revenue`, `$ and % Change`.
- **Percent fact:** an `ix:nonFraction` that is the only fact on the cell's value origin and meets all of these:
  - its unit resolves, through the filing's `xbrli:unit` definitions, to `xbrli:pure` alone;
  - its `scale` is `-2`;
  - its `format` is absent, `ixt:num-dot-decimal` or `ixt:numdotdecimal` (any other transformation is not proof);
  - its displayed digits equal the digits of the cell's complete token;
  - its `sign` attribute agrees with the token's displayed sign (`sign="-"` exactly when the token is negative).
- **Amount fact:** an `ix:nonFraction` on the value origin whose unit has a currency or share measure.
- **Table-wide percent declaration:** a unit line, from the context before the table or a spanning in-table caption (the same positions `units` uses today), that wholly matches:
  - `_UNIT_DECLARATION` alternative 2 or 3: `(items/amounts expressed as a) percentage of revenue`, `the following table … expressed as a percentage of revenue`; or
  - `(in percent)`, `(in percentages)`, `(as a percentage of revenue)` or `(as a percentage of total revenue)`.

  A percent word inside an `except` clause is never a table-wide declaration.

## Rule P: percent scale

### P1. Percent proof

A digit cell is proven a percent by any of:

1. **Its own `%`:** the complete token ends in `%`, including after the attachment pass (P4).
2. **A percent fact** (definition above).
3. **A percent header:** a header label of its copy column is a percent declaration.
4. **A percent row label:** its row label is a percent declaration.
5. **A table-wide percent declaration.**

### P2. Non-percent proof

A digit cell is proven not a percent by any of:

1. **Its own `$`.**
2. **An amount fact.**
3. **A non-percent unit** in its copy column's header labels or its row label: today's `_ROW_UNIT` (`per share`, `dollars`, `shares`, `in thousands/millions/billions`).

Amount words (`_VALUE`: revenue, cost, total …) are proof of neither. `Cost of revenue` heads a percent row in META's tables.

### P3. Precedence and conflicts

Proofs are ranked by how local they are: cell level (P1.1, P1.2, P2.1, P2.2), then row or column level (P1.3, P1.4, P2.3), then table level (P1.5).

- **A table-wide declaration** applies only where no local proof of either kind exists. A local non-percent proof overrides it, as today: `Income per share | 2.50` under `expressed as a percentage of revenue` stays 2.50.
- **Conflicts.** The cell becomes text when, at the cell, row or column level, percent and non-percent proofs both apply, or when two percent proofs disagree:
  - a `$` token under a percent header or row label;
  - a displayed `%` with an amount fact;
  - a displayed `%` with a pure fact whose scale is not -2.

  The cell keeps today's reason, `Conflicting explicit units; verify the row, column and displayed value units.` (or the converter's `Currency and percent conflict`).
- **A cell proven a percent** converts as displayed number / 100. Its display format is derived from the displayed decimals, as today.
- **A cell proven not a percent** converts as today.

### P4. Mixed columns, unproven cells, and the split `%`

- **Percent column:** a copy column in which at least one digit cell is proven a percent by cell- or row-level proof (P1.1, P1.2 or P1.4).
- **Unproven digit cell:** a digit cell in a percent column with no percent or non-percent proof that applies to it.
  - It keeps its source text, with the review reason `Percent sign on other rows of this column; verify the scale.`
  - The table becomes `needs_review`.
  - This applies to amount and percent rows alike. JPM #64's `Tier 1 capital 294,881` (below `$ 275,513`) and META's `Cost of revenue 18` (below `Revenue 100 %`) both stay text.
  - Exception: a complete token whose value is zero, and which the converter accepts without a review reason, converts as 0. Negative zeros (`-0`, `(0)`, `-0%`) keep the converter's review text.
- **Columns with header- or table-level proof.** In a column whose header is a percent declaration, or under a table-wide declaration, plain cells are proven by it. They are not unproven. NVDA's 495 percent-of-revenue values stay as they are.
- **Columns that are not percent columns** keep today's behaviour.

**Attachment pass (split `%`).** This runs in the XLSX path only, before `_column_groups`.
- A source origin whose whole text is `%` or `)%` attaches to the nearest value origin to its left in the same source row. Only empty origins or `$`/`(` fragments may lie between them.
- The value's copy text then includes the attached marker: `(29) | %` gives `(29) %`; `(4.5 | )%` gives `(4.5)%`. The marker's own copy position shows no text for that row.
- `cell_sources` for the value lists the marker's coordinates too.
- The pass never joins two values. NFLX #13's `$ | 1,323,096 | 7 | %` still has two values under one leaf: `_column_groups` refuses to merge them as today, and `7` converts with its attached `%` in its own copy column.
- The unresolved-span fallback runs as today, on the source cells.
- The converter accepts the negative forms `(x) %`, `(x)%` and `(x %)` as −x/100.
- `_column_groups`' merge test treats a row whose token is one of these forms as converting cleanly.
- `table_parser.py` is unchanged.

**Percentage points.** A value whose text ends in `pts`, `pt` or `points` (NVDA `Gross margin 26.6 pts`) is a change in percentage points, not a percent.
- It keeps its source text with the reason `Percentage points; verify the unit.`
- For `_column_groups`' merge test it counts as converting cleanly, so it no longer splits the column.
- A `pts` cell is not percent proof for its column.

### P5. `except` captions

- **No percent meaning.** A percent word inside an `except` clause never proves a percent. This covers `(in millions, except percentages)` and `(In thousands, except share, per share and percentage data)`.
- **The replacement test.** `_PERCENT.search(units)` in `_numeric_role` is replaced by the table-wide declaration test.
- **`units` itself.** Captions that fully match `_UNIT_DECLARATION`, such as the singular `except … percentage data`, still enter `units` as today. They still make plain cells numbers through the existing `units` rule, which keeps their displayed value. The plural `except percentages` does not match and stays out of `units`, as today.

## Rule I: identifier columns

`_identifier_column(header)` keeps its header test (Rule 3 of the header-detection spec). What changes is how it applies to cells.

### I1. Per-cell quantity proof

In a copy column whose header is an identifier header, a digit cell converts on the ordinary role path, including Rule P, only when the cell itself proves a quantity. That means:
- its value origin is an `ix:nonFraction` fact; or
- its joined text is a complete token with `$` or `%`, including after the attachment pass.

Every other digit cell in the column stays text, as today. A `$` inside longer text, such as an exhibit description, is not a complete token and proves nothing.

### I2. Review reasons for the text cells

- **Columns with quantity evidence.** Where at least one cell of the column proves a quantity (I1), every other digit cell in it carries `Identifier heading over quantities; verify the column.` Examples:
  - CAT `Full Year 2024`: `$ 13,373` converts, while `164` stays text with this reason.
  - JPM `After 1 year through 5 years`: the `$` rows convert, while `55,731` stays text with the reason.
- **Columns without quantity evidence.** Where no cell proves a quantity, each digit cell formatted as an amount carries `Identifier heading over amount-formatted values; verify the column.` That means a thousands-separated number (`\d{1,3}(,\d{3})+`), or a number in accounting parentheses. Other cells stay text without a reason, as today.
- **True identifier columns** have neither in the corpus (fact pack D.1), so `Notes | 7`, exhibit indexes, form types, file numbers, dates and maturity years stay text and unflagged.

### I3. Deliberate changes

- **Facts under identifier headers.** `test_identifier_columns_keep_text_even_for_facts` pins an XBRL fact under a `Notes` header as text. Under I1 a tagged number proves a quantity, so it converts. The test is rewritten to assert that.
- **Regressions repaired by I1.** NTRA #8: its `$` rows convert, and the plain rows carry the I2 reason. TSM #150–#152: the facts convert.

## Snapshot change

- **`SourceCell` gains a field** `facts: tuple[FactAttributes, ...]`, defaulting to `()`. `FactAttributes` holds:
  - `name`;
  - `unit_measures`: the resolved measures, as a tuple of strings;
  - `scale` and `decimals`;
  - `format` and `sign`;
  - `displayed`: the fact element's visible text.
- **`_cell` fills it** from the `ix:nonFraction` nodes inside the cell.
- **Unit resolution.** A unit map is built once per document from its `xbrli:unit` definitions. It is reached from the table node's document root and cached by that root, so `parser.py` does not change.
- **`is_numeric_fact` keeps its meaning,** so `table_completeness.py` and every other reader are unaffected.
- **The audit harness's `export_tables.py`** records `scale`, `format` and the resolved unit for each fact.

## Unchanged behaviour

- Columns that are not percent columns and hold no identifier header.
- Conversion of `$` amounts.
- The period-row guard, `_header_count`, `_PERIOD`, `_UNIT_DECLARATION` and `table_completeness.py`.
- Markdown, strict and `table_parser.py`.
- NVDA's percent-of-revenue tables: the same 495 values and formats.
- True identifier columns: text, unflagged.

## Testing

Write the tests first, in a new `tests/test_xlsx_value_accuracy.py`, with SEC-style spans. Each converted cell asserts its value and `number_format`. Each text cell asserts its exact review reason.

**Rule P:**
1. Own `%`: `15.7 %` → 0.157, format `0.0%`.
2. Attachment:
   - `(29) | %` → −0.29 and `(4.5 | )%` → −0.045;
   - a column with one such row and other `x %` rows merges, and every row converts;
   - NFLX-shaped `$ | 1,323,096 | 7 | %` under one leaf → `7 %` → 0.07, and `$ 1,323,096` is unchanged.
3. Percent fact:
   - plain `13.8` with a pure unit and `scale="-2"` → 0.138;
   - not proof: `scale="-4"`, `scale="-1"` with a `years` unit, an amount fact, two facts in one cell (a range), a transformed format, and a sign mismatch;
   - BAC-shaped `(0.3)` with `sign="-"` → −0.003.
4. Percent header: `% Change` over `54 %` and `(75)` → 0.54 and −0.75 (RDDT); `Percent of retained loans to total retained loans` likewise.
5. Percent row label: `% of net revenue | 26` → 0.26.
6. Table-wide declaration:
   - NVDA's sentence → plain cells are percents (unchanged);
   - `(in percentages)` as a context line and as a spanning in-table caption → percents;
   - `Income per share | 2.50` under the declaration → 2.50 (the existing test).
7. Not declarations: `Percentage of completion revenue`, `Percentage point change` and `Increase in percentage of completion revenue`, as header and as row label, over plain numbers. The numbers keep today's values.
8. Unproven cells:
   - META-shaped `Revenue 100 %` / `Cost of revenue 18` → 18 is text with the P4 reason;
   - JPM #64-shaped `$ 275,513` / `294,881` / `CET1 capital ratio 15.7 %` / `16.8` → 294,881 and 16.8 are text with the reason, while `$ 275,513` and `15.7 %` convert;
   - `0` converts; `(0)` keeps the converter's negative-zero reason.
9. `except` captions over plain amounts: `(in millions, except percentages)` and `(In thousands, except share, per share and percentage data)` → the amounts keep their displayed values (the `161,690` case).
10. Percentage points: `26.6 pts` is text with its reason, and the column's other rows still merge.
11. Conflicts: `$ 12` under `% Change`; `50 %` with an amount fact; `50 %` with a pure fact at `scale="-4"`.

**Rule I:**

12. Per-cell proof:
    - `Within 1 year(a)` over `$ 21,442` and `19,404`: the first converts, the second is text with the I2 reason.
    - `Other Changes (Note)` over facts: they convert.
    - `Year-over-Year Change` over split `%` cells: they convert after attachment.
    - The Codex counterexample, `Notes` over `7`, `8` and `$ 12`: `7` and `8` stay text with the I2 reason, and `$ 12` converts.
13. Unchanged identifiers: `Notes | 7`, `Exhibit | 3.1`, `Filing Date | 07/09/2015`, `Maturities (calendar year) | 2028`, `Incorporated by Reference | 10-Q` (text, no reason).
14. Prose: a `$` inside an exhibit description proves nothing.
15. Amount format without quantity evidence: `13,373` → text with the second I2 reason; `164` → text, no reason.
16. The rewritten facts test (I3).

**Guards:**

17. The full suite passes. The plan lists every existing test whose expectation this spec changes, with the reason.

## Acceptance

All runs use the same 60 filings, one export at a time, at most 3 workers, low priority. The baseline is `main` re-exported once with the extended harness (fact attributes), before any code change.

1. **Tests:** all pass.
2. **Manifest.** From the baseline, before implementation, a manifest records by source coordinates (filing, table, source row and column):
   - every percent-row cell exported unscaled: the fact pack's 1,072 joined cells and 123 split-`%` cells;
   - every cell of the 32 misread identifier columns;
   - every cell of the 241 true identifier columns.

   The manifest is committed with the audit.
3. **Dispositions.** In the new output, each manifest cell is one of:
   - **proven percent:** a number equal to displayed / 100, with its proof named;
   - **proven quantity** (Rule I): a number equal to its displayed value;
   - **text with the expected review reason.**

   True identifier cells must be unchanged. No manifest cell may be an unflagged number at the wrong scale, or unflagged text that holds an amount.
4. **Vault primary statements:**
   - all 126 still export;
   - every fact still verifies with the same counts (META 3,322, NVDA 2,662, RDDT 2,056).
5. **Every other changed cell** (numeric or text, value, format or reason) compared with the baseline is listed and classified with its source cells. A wrong number blocks the merge.
6. **Percent facts:** every cell proven by a percent fact equals the fact's displayed number / 100 with the fact's sign.
7. **Coverage cost:** cells that turn from numbers into flagged text are counted per group and table, and reported to the user.
8. **Header-detection checks:** `all_facts.py` and the stacked-block scan still pass.

## Known remaining gaps

- **Percent columns with no proof at all.** A column of percents with no `%`, percent header, row label, fact or table declaration keeps its displayed numbers. That is exactly what the filing prints, but its scale is unknown. No case is known in the corpus.
- **Section headings are not proof.** A label-only row such as `Percentage of revenue:` does not prove the rows below it, because its scope cannot be proven. Those rows stay flagged unless another proof applies.
- **The convention of a `%` on the first row is not proof.** META's and RDDT's percent-of-revenue rows, JPM's capital ratios and CRM's rates become flagged text unless a fact, header or row label proves them. The cost is coverage; the gain is that no number in them is wrong.
- **Facts prove only scale, and only on their own cell.** A runtime XBRL guard that checks every tagged value and period remains a follow-up.

## Sequencing

This lands before the large-cap period-caption spec, which would export more of the affected tables (JPM, BAC, KO, CRM). Re-extract the RCQ vault workbooks after it merges.
