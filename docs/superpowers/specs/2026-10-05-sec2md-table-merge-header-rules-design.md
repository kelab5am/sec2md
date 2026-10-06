# sec2md Table Merge and Header Rules Design

Date: 2026-10-06 (revision 15)

Status: Approved for planning (Astra, round 4). Revisions 6–15 add the plan
prototype's corrections and interpretations, for Astra to confirm with the plan.

Evidence: `../audits/2026-10-04-table-merge-header-evidence/REPORT.md`

Review record: `../reviews/2026-10-05-sec2md-table-merge-header-rules-review.md`

## Review history

**Round 1** (revision 1 → 2):

| Finding | Change |
|---|---|
| 1. [P1] Repeated numeric headers break strict's numeric trace | New R6a. The renderer counts the header numbers it repeats, from source spans. Strict's trace credits exactly those copies for that table, in both renders that produce element content. Invented header numbers and extra body amounts still fail. |
| 2. [P1] The XLSX export reuses the merge helpers R3/R4 change | New R9. The structural helpers take a policy. XLSX keeps today's rules unchanged, and its prepared tables must be identical on the corpus. The evidence report's call-graph claim is corrected. |
| 3. [P1] The data-cell test misreads CRM 26, and split amounts have no rule | New R0. Row roles are decided once, on the cleaned source grid, before any merge. A number in the label column counts only when it has a decimal point. Split negatives are rebuilt first, and link labels are read without destinations. Expected row roles are pinned in tests independently of the shared helper. |
| 4. [P1] The careful merge can move a header across periods, and merged cells lose identity | Output columns carry their source-column membership through both passes. Headers are assigned from membership, never by marker direction. The structural pass no longer moves header text, and a marker column that owns independent header content is not removed. This follows XLSX's existing veto. |
| 5. [P2] Substring matching accepts conflicting sibling headers | The alignment check matches whole header components, and rejects a column that also carries a conflicting sibling header. Ambiguous assignments are unevaluated. |
| 6. [P2] The alignment check needs a position-preserving parser and a token rule | It has its own Markdown cell parser that keeps blank columns, escaped pipes and links. Split negatives are assigned to their numeric core's column, leading-dot decimals are tokenized locally, and nil dashes are counted as unevaluated. |
| 7. [P2] Zero findings could come from lost coverage | Coverage counts are part of the result. Acceptance compares a pinned population, with skip reasons, an assignment audit of the correct merges, a header-retention audit, individually documented residuals, a reconciled F7, and a fixed overhead measurement. |

**Round 2** (revision 2 → 3). Astra accepted R9, membership routing, freezing
row roles, the parser and token contract, and the overhead contract. The
remaining findings changed:

| Finding | Change |
|---|---|
| 1. [P1] R6a's aggregate credit can hide an extra body amount | R6a is replaced by header accounting. Each table's header line is checked on its own against the table's header-zone source cells. Those cells' source occurrences are then removed from the pool that body text and prose are traced against. A credit is never general availability, and Astra's `Revenue \| 100 2025 \| 200` mutation fails. |
| 2. [P2] T8 promotes integer exhibit entries into the header | The decimal-only rule is replaced by an identifier-column rule. A label column holding numbers in at least two rows counts integers too. CRM 26's single caption number does not qualify. |
| 3. [P2] The checker reads R0 in a different column-zero convention | R0 is now defined on visible content, independent of physical columns. Empty rows and columns are ignored, and the label column is the leftmost column with origin text. The renderer and the checker each apply it to their own grid, and the checker keeps original coordinates. |
| 4. [P2] Whole-component matching rejects literal and hierarchical headers | Matching now finds whole source labels in the output header, longest first, at ` — ` boundaries, and checks counts against each column's independently derived source path. A label used at another level is never a conflict, and an ambiguous segmentation is skipped. The header-retention audit uses the same rule. |
| 5. [P2] Aggregate coverage can conceal a replaced population | Acceptance compares per-value identities (document, unit, source row, numeric-core column) and reports every lost identity. The runtime counters get a fixed schema: units, precedence, always-present keys and reconciliation identities. |

**Round 3** (revision 3 → 4). Astra resolved round 2's findings 1–3 and 5 at
design level. The two remaining defects were in the matcher:

| Finding | Change |
|---|---|
| 1. [P2] The matcher requires duplicate labels that R6 suppresses | Requirements and conflict counts use the value's emitted path. That is the source path with source-cell duplicates removed and adjacent equal texts collapsed, exactly as R6 writes it. Each collapsed entry remembers every cell it satisfies. Non-adjacent repeats (`A — B — A`) still need both occurrences. |
| 2. [P2] A longer label in another column overrides a valid parent/child path | No table-wide longest-first choice. A header that exactly renders the value's emitted path is aligned. Otherwise every split of the header at its ` — ` boundaries is evaluated, and a value is reported only when all of them disagree with the path. When they disagree with each other, it is skipped as `value_ambiguous_header`. The header-retention audit uses the same semantics. |

Astra's implementation requirements for R6a are now written into R6a: an exact
table-to-output association, each located header line consumed once, failure
on a missing or ambiguous association, no unrestricted text replacement, and
the same token accounting on both pools.

**Round 4** (revision 4 → 5). Astra approved writing the implementation plan.
The two plan notes are applied to the spec as well:

| Note | Change |
|---|---|
| 1. [P2] Segmentation must not be enumerated without bound | Matching now prescribes a memoized search over separator positions. Its state is the capped counts of the relevant labels, and it stops early once both verdicts are reachable. The work bound is 100,000 states per value. Exhaustion is a new coverage key, `value_unevaluated_budget`, and is never counted as aligned. |
| 2. [P3] R6a's fallback restores the old trace and does not guarantee an error | A missing or ambiguous association grants no header exemption and subtracts nothing, so the trace is exactly today's. Misses are recorded in `header_accounting_misses`, and acceptance requires none, or each individually reviewed. |

**Prototype corrections** (revision 5 → 6). The plan's prototype found five
gaps. The fixes keep the earlier review decisions intact.

| Gap found by the prototype | Change |
|---|---|
| R0 never counted bare years, so `Revenue \| 2000 \| 1900` became a header row. The completeness spec's round 3 requires it to be data. | Bare years count as numbers only in a row whose label cell holds origin text that is neither period text nor unit text. `\| 2023 \| 2022`, `2023 \| Change \| 2022` and period- or unit-captioned year rows stay header-like. |
| A `th` header row such as `Denomination \| €1 \| €2` counted as data. That emptied the header line and created a check-2 false positive against a Phase A regression case. | An explicit header row, whose non-empty cells are all `th`, is never a data row. |
| R2's marker exception also listed `(`, but `_should_merge_cells` can never pass for it. | The exception covers currency markers only. `(` columns stay with the careful merge. |
| The spec said nested tables render as today, but R1–R7 apply to the flattened outer grid. | "What does not change" now says nested tables get no special handling and their output can change. |
| `header_source` was tokenized per cell, unlike strict's pool, so split negatives could differ. | Header-zone cell texts are joined in document order with single spaces, as the pool is built, and tokenized once. |

**Prototype corrections, continued** (revision 6 → 7):

| Gap found by the prototype | Change |
|---|---|
| "Complete number" excluded footnoted values (`2.1(1)`, `3,984 *`) and ranges (`3.5 %- 4.3 %`). Rows holding only such values were promoted into the header, which lowered financial-row recall on three NVDA fixtures. | Footnoted values and numeric ranges are complete numbers. A range of two bare years stays year-like. |
| The accuracy suite's own numeric-trace check has no header accounting, so it still flags repeated header numbers. | Acceptance requires it to apply R6a's accounting with its own tokenizer. |
| A table inside a list item or an inline wrapper has no segment of its own. | It is recorded as an R6a miss. |
| R8 can keep a short part-only stub that `main` drops. | Acceptance requires section extraction to be unchanged on fixtures and corpus, or each change reviewed. |

**Prototype corrections, continued** (revision 7 → 8):

| Gap found by the prototype | Change |
|---|---|
| A label-only section row (`Accounts Receivable:`) right before the first data row was absorbed into the header. | Trailing label-only rows of the header zone are body rows. |
| Footnoted bare years (`2024(a)`) and fiscal-year ranges (`2024–25`) read as complete numbers. | Both are year-like. |
| The accuracy suite's financial-row metric looks for a literal output row for every source row with two or more numbers, header rows of dates included. R6's fused header line can never match it. | A source row also counts as present when an output header line contains its label and numbers. Body-row-only recall must separately stay at or above `main`'s. |

**Prototype corrections, continued** (revision 8 → 9):

| Gap found by the prototype | Change |
|---|---|
| Body-only recall fell on nvda-2002 because three spellings of its second header row, `(As restated – see Note 2)`, moved into the header line. Main had misplaced them into its body. | Every row `main` matched as a body row must stay a body row, unless R0 classifies it as header-zone. Each such move is listed and reviewed, and any other loss fails. |
| A unit or period caption in the label column only, right before the data, became a body row with no rule saying so. | Accepted as designed and stated in the header-zone definition, with a pinning test. |

**Prototype interpretations** (revision 9 → 10), recorded for Astra:

| Point | Interpretation |
|---|---|
| Source cell text in the checker | The checker reads cell text through the renderer's cell-text extraction, `extract_cell_text`, shared like the R0 helper. This is the spec's "extracted text". Merge decisions and the output-column mapping are still never shared. |
| Year-like values | They are never alignment values: not counted in `values_total` and not evaluated. Bare years beside a row label still decide row roles (R0). |
| Step 15's "siblings" | The cells of the same header row that cover a value column. |
| Repeated-header detection | It treats year-like values as period evidence. |
| Header cell texts for the accuracy suite | The per-table header record gains a trailing `header_cells` field (each header-zone cell's text and the columns it covers), read through `Parser.element_header_records(element_id)`. The suite finds header lines itself with R6a's rules and tokenizes with its own normalizer. It never uses strict's token counts. |
| Body-row guard baseline | `tests/accuracy/body_rows_main.json` records the rows unchanged `main` rendered as body rows. Since revision 11 it covers every source row with origin text: 2,492 rows across 7 fixtures, counted per text signature. It is generated from `c674828` by `tests/accuracy/generate_body_row_baseline.py`. The guard lists 172 allowed moves, each verified as header-zone. Revision 10's first version covered financial rows only, with 1,550 rows and nvda-2002's five `(As restated – see Note 2)` rows as its only moves. |
| Golden files | `tests/golden/` is used only by the deselected EDGAR integration tests. It already differs from `main`, and was not regenerated through 16 rendering commits. This work does not regenerate it. |
| RCQ version | The minor bump is `0.1.22+rcq.4`, because rcq.3 is unreleased. |

**Acceptance-run corrections** (revision 10 → 11). The prototype's first corpus
run (`../audits/2026-10-06-table-merge-header-acceptance/REPORT.md`) found:

| Gap found by the corpus run | Change |
|---|---|
| S1. Body rows before the first row with a complete number became header zone, and R5 fused them into the header line. Examples: `Common Stock \| AAPL`, `Finance leases \| 15.1 years`, exhibit rows `10.5.22` and `10.1+`. At least 35 tables were affected, including fixture aapl 8. | The header zone continues past its first row only through header-like rows. A row whose label cell holds other text ends the zone, and it and the rows below it are body rows, as `main` renders them. |
| S1, continued. R6's equal-text suppression then dropped a link: two promoted exhibit descriptions with the same text but different destinations. | Suppression compares texts with their link destinations, so cells with different links are both kept. |
| S2. The renderer placed CSS-hidden cells, but the checker, check 1 and the snapshot builder do not. Spanning headers then landed over the wrong columns, in 1,075 tables. In BAC 336 a value column was split. | The source grid leaves out grid-hidden rows and cells, using the snapshot builder's rule. |
| A td years row such as `Function \| 2022 \| 2023 \| 2024` or `(Dollars in millions) \| 2024 \| 2023` read as data (106 tables). In 99 of them the label is a unit caption the unit-text pattern misses. TSM 136 regressed: `main` had its years in the header line. | A year run is never a data row. R0 gets its own caption patterns, which add the corpus's unit captions and `(Unaudited)`; the shared patterns stay as they are. A year-like label cell does not make bare years count. The `Segment \| 2025 \| 2024` named limitation is replaced by a narrower one. |
| Check 1 reads R4's `US$ 1,250.0` as a text cell and reports a value failure on a correct rendering (TSM 344). It also reads header lines with `numbers()` only, so identifier references that R5 correctly moves into the header line are reported (15 tables). | Both are recorded as check-side false positives, F9 and F10. Checks 1–3 do not change. The fixes belong to Phase B, with the source-token fixes. |
| The fixture body-row guard covered only rows with two or more numbers, so it missed S1 on aapl 8. | The guard covers every source row with origin text. Acceptance lists every row that moves from `main`'s body into a header line, on fixtures and corpus. |

**Acceptance-run corrections, round 2** (revision 11 → 12). Round 2
(`REPORT-round2.md`) met check 1, alignment (0 misaligned), the assignment audit
(6,616 of 6,616), the known shifted tables (34 of 34) and overhead (1.088). It
found:

| Gap found by the corpus run | Change |
|---|---|
| S7. A second title line in the label column ended the header zone. The first title then became a trailing label-only row, so the zone was empty and the dates fell into the body (4 fixture tables in the EX-99s). | Label-only rows continue the zone. Trailing label-only rows still leave it. |
| S8. The spec claimed `main` renders a column-heading second row in the body. For 82 rows in 80 tables `main` had fused it into its header line through its sparse-row rule. Examples: exhibit index headings, fair-value headings with dates. | The header-like rules include `main`'s sparse-row fusion for the second row. |
| A row whose cells are all hidden was dropped, so rowspans from above shifted onto the next row (JPM 606, BAC 320 and 322). | Such a row stays as an empty row, as the snapshot builder keeps it. |
| F11. Check 2 reads a unit-captioned years row as a data row and flags 4 correct BAC tables. | Recorded as a check-side false positive. |
| S5. MSFT 69: a value cell's span covers its year header's column. | A documented residual, under Deferred. |

**Acceptance-run corrections, round 3** (revision 12 → 13). Round 3
(`REPORT-round3.md`) resolved S7. It brought back 62 of S8's 82 rows; the other
19 are tables with no data row or a data first row, where R5 applies, and the
JPM 207 case below. Every criterion except the review sample and moved rows was
met. It found:

| Gap found by the corpus run | Change |
|---|---|
| S9. The sparse-row fusion counted `%` and `$` marker columns in n, which `main` merges before counting. AMZN 10-Q table 21 fused the body row `operating leases \| 10.6 years \| 10.0 years` into the header line. JPM 207 was the mirror case: a heading row `main` fuses stayed in the body. | n and both rows' counts leave out marker-only columns. Simulated on the corpus, this changes exactly these 2 tables, both to `main`'s rendering. |
| The fusion, counted on the source grid, also fuses 45 second rows that `main`'s merged grid did not (46 in round 3, one of them AMZN 21, which P1 removes). | Accepted and listed: 43 NVDA unit-caption rows that read well, NTRA 123 (better than `main`) and TSM 216 (list item (b) fused, no value lost). |

**Plan-drafting review** (revision 13 → 14). Checking the code against this spec
while the plan was drafted found:

| Point | Change |
|---|---|
| The complete-number pattern accepted `$ $ 5`, `1,,2`, `12,34` and `5 % %`. | The definition now says one currency marker, thousands in groups of three and one trailing `%`. The code is tightened to match. |
| `judge` stopped early only within each frame, not as soon as both verdicts were reachable from the start. Its verdicts were right, but a value could reach the work bound where a global stop would not. | The code follows the spec's global early stop. |
| The spec counted the label column as a value column. | Value columns leave out the label column: an identifier column's numbers are row labels. |
| R6's equality folds case and whitespace, like the checker's step 10. | The spec says so. |
| The fiscal-year range has no consecutiveness check (`2022-03` is year-like). | The spec says what it matches. |
| The header-retention audit on the matching controls, and check 1's `header_row_count` role differences on named tables, had no suite tests. | Tests are added. |
| The release notes did not say that marker-only columns are left out of the sparse-row count. | They do now. |

**Codex review** (revision 14 → 15). A read-only Codex review of revision 14
found:

| Finding | Change |
|---|---|
| P2. "XLSX output must not change" contradicted the recorded `display_page` changes (S3). | S3 is written as an open exception for the user to decide, in Scope, "What does not change" and the XLSX acceptance criterion. |
| P2. "A caption that spans the value columns stays header" contradicted the origin-only label-only rule for a caption that starts in the label column. | Label-only is decided by origin. A full-width caption that starts in the label column is label-only. A control test pins it. |
| P2. The checker's emitted path collapsed equal normalized texts, but normalization drops link destinations, which R6 compares. | Collapsing also needs equal link destinations. The prototype already does this, and a test pins it. |
| P2. Repeated-header detection still said "bare year". | It says year-like value. Controls for footnoted years and fiscal-year ranges are added. |
| P3. Check 1's acceptance said "294 tables to 0", conflating class-1 losses with all value failures. | 294 class-1 tables restored; 305 → the documented false positives (13 in round 5). |
| P3. R3's body-start note and the checker's introduction kept superseded wording. | R3 defers to R0's roles. The introduction names the shared cell-text extraction. |

**Prototype interpretations, round 2,** recorded for Astra:

| Point | Interpretation |
|---|---|
| Cell texts in the checker | For a cell without links, the checker reuses the text the render already extracted from the same cell with the same function, instead of extracting it again. This is behaviour-identical, with identical results on all 109 documents, and it brought overhead under 1.10. Merge decisions and the column mapping are still never shared. |
| R0's unit captions | Dollar captions only. "(Shares in millions)" is not unit text, and a role test pins this. |
| Link-aware equality | The renderer and the checker compare the same extracted text, with links resolved against the same base URL. |
| Body-row guard | It counts rows per text signature, as a multiset. Set semantics masked a real move on ex99-1. |

## Purpose

Make the Markdown table renderer keep every source value and put each value
under the header its source column carries. Today `TableParser` silently drops
row-0 text when it merges columns and places spanning headers over the wrong
column. The table completeness checks (spec 2026-10-02, Phase A) report the
first problem and cannot see the second.

This spec is the prerequisite that the completeness spec's Phase B and Astra's
Round 6 ruling name: "the table-merge and header-rules work". It changes
Markdown rendering on purpose, and adds a report-only header-alignment check.
It does not enable strict enforcement of any table check. The other Round 6
Phase B prerequisites remain outstanding: failed-check visibility, the
source-token and marker fixes, and the page-furniture class.

## Decisions taken in design (user, 2026-10-04 and 2026-10-05)

| Question | Decision |
|---|---|
| Scope | The Markdown renderer only: `TableParser` and the one-row path in `Parser`. XLSX output must not change. One exception is open for the user's decision (S3, below): the workbook's `display_page`, which the parser guesses from Markdown page text. |
| Layout stability | Readers are LLMs and RAG chunking; nothing parses tables by column position. Layout may change wherever it keeps every value and puts it under the right header. CHANGELOG entry and minor version bump. |
| Currency cells | Merged into the amount, as `$` is today: `€ 1,234`, `RMB 941,168`. |
| Multi-row headers | Fused per output column into one header line, top to bottom, joined with ` — `. A spanning header repeats in every column it spans. |
| Repeated header numbers | Kept. Strict's numeric trace accounts for each table's header line separately (R6a). |
| Header-alignment check | Built in this work, report-only. |
| Approach | Repair the existing pipeline with source provenance, not a new renderer. The current merge is right about body values in 6,616 measured cases and wrong in one. |

## Background

The evidence report replays `TableParser` stage by stage over the Phase A corpus
(109 documents; 3,707 tables rendered by `TableParser`, 1,042 one-row tables)
and reproduces its Markdown exactly for every table. Astra re-ran it in round 1
with the same results. Its findings:

| Class | Tables / documents | What goes wrong |
|---|---|---|
| 1. Legacy merge drops row-0 text | 469 / 47 | `_merge_grid` keeps only the left column's row 0 (`merged = [current_col[0]]`). This is the cause of every genuine check-1 value loss in `TableParser` output: 294 tables, including all 10 pinned fixture failures. |
| 2. Columns under different headers fused | 1 value fusion (TSM 248); 37 non-amount fusions | A note column fused with 2022's amounts; exhibit-index X marks fused into "Number". |
| 3. Spanning header off its values | 138 / 10 with an empty first slot; 107 / 8 shifted over another span's values | A spanning header's text lives only in its first grid column. When that column is empty in the body it merges left and carries the header with it (BABA 24, TSM 79/312, JPM 482, BAC, RDDT, MSFT). 43 more tables put a header over a separate `$` column. |
| 4. Non-`$` currency columns | 1 / 1 | No per-row `€`, `£`, `RMB`, `NT$` or `DKK` columns exist in the corpus. They appear only as header labels. |
| 5. Header rows | 29 / 19 data rows swallowed; 244 / 27 rows k ≥ 3 left in the body; 129 / 32 second header rows left in the body | `_process_headers` always uses row 0 and fuses row 1 when row 0 looks sparse. |
| 6. Header-only columns dropped | 37 / 30 | `_clean_empty_rows_and_cols` drops a column with header text and an empty body: signature dates, exhibit-index columns, `(a)`. |
| 7. One-row PART branch | 1 (CAT 7) | `_one_row_table_to_text` returns "PART III" and drops the other cell. |
| 8. Split negatives left split | 80 / 4 (50 misaligned) | `(29 \| )` stays in two columns when the marker column has one negative, uses `)%`, or the careful pass rejects the whole column. |
| Other | 48 / 1 (NTRA) | U+200B cells count as content and block every merge. Leading-dot decimals (`.75`) and a year in a `$` column also block the careful merge. |

**Correction to the evidence.** The report states that the XLSX path uses only
`_join_structural_text`. It is wrong: `xlsx_tables.prepare_table()` also builds
a bare `TableParser` and calls `_safe_structural_actions()` and
`_validated_structural_actions()` (Astra, round 1, finding 2). The report
carries a dated correction.

## Definitions

- **Source cell:** one `td` or `th` that is not grid-hidden, read by
  `_extract_cells` into a `Cell`.
- **Grid-hidden:** a row or cell hidden by the snapshot builder's rule,
  `xlsx_tables._hidden`: `display:none`, `visibility:hidden` or a `hidden`
  attribute, on the element itself or on an ancestor inside the table.
  - The renderer leaves grid-hidden rows and cells out before placement, as the
    snapshot builder and the checker's placed grid do.
  - Their text is not rendered.
  - Spans and positions are computed without them, so spanning headers sit over
    the columns a reader sees.
  - A row that is not hidden itself but whose cells are all grid-hidden stays
    as an empty row, as the snapshot builder keeps it. Rowspans from the rows
    above still cover it. Dropping it would shift those rowspans onto the next
    row: the prototype lost JPM 606's "Balance at December 31, 2021" row this
    way.
- **Source grid:** the grid after span expansion and `_clean_grid`. It is kept
  unchanged for the whole render. Its rows and columns are the coordinates that
  all rules below refer to.
- **Slot:** one position of the source grid. `GridCell.cell` identifies the
  source cell covering it; every slot a spanning cell covers points to the same
  `Cell` object. That identity is the span.
- **Visible cell text:** the extracted text with zero-width and format
  characters removed (U+200B, U+200C, U+200D, U+2060, U+FEFF), and with each
  Markdown link reduced to its label. Every classification below reads visible
  text. The rendered Markdown keeps links as today.
- **Origin text:** a column or row holds visible text when some source cell
  whose top-left slot lies in it has visible text. Slots covered only by a span
  from another column or row do not count. This is the convention `_clean_grid`
  already follows, because spanning slots carry no text.
- **Label column:** the leftmost column that holds origin text. In the
  renderer's cleaned source grid this is column 0. In the checker's placed
  grid, which keeps empty columns, it is the same logical column at whatever
  physical index it has.
- **Identifier column:** the label column, when it holds a complete number
  (integer or decimal) in at least two data-candidate rows. A data-candidate
  row is any row other than an empty one. Exhibit and item indexes are
  identifier columns. A table whose only label-column number is a caption
  number (CRM 26's `4`) is not.
- **Complete number:** a cell's whole visible text, or a split negative rebuilt
  within its row, that is a standalone number other than a bare year.
  - A standalone number may have one currency marker, parentheses, a sign,
    digits with thousands separators (groups of three) or a leading-dot decimal
    (`.75`), and one trailing `%`. Strings such as `$ $ 5`, `1,,2`, `12,34`
    and `5 % %` are not standalone numbers. Examples: `9,943`, `(29)`, `36.5 %`, `$ 1,234`, `RMB 941,168`, `.75`,
    `3.1`, `9`.
  - A split negative is rebuilt first, from adjacent non-empty cells of one
    row in the shapes `(29` + `)`, `(3.2` + `)%` and `(` + `29` + `)`, as
    `merge_split_negatives` does. Its column is the column of the cell holding
    the digits.
  - **Footnoted values count.** A standalone number followed by one or more
    footnote markers is a complete number. The markers are `(1)`, `(a)`, `[1]`,
    `*`, `**`, `†` and `‡`, and the number may have a space before them.
    Examples: `2.1(1)`, `3,984 *`.
  - **Ranges count.** Two standalone numbers joined by `-`, `–`, `—` or `to`
    form a complete number, each side optionally with `%` or a currency marker.
    Examples: `3.5 %- 4.3 %`, `0.2 - 1.0`.
  - **Year-like values.** These follow the bare-year rule rather than counting
    as complete numbers:
    - a bare year;
    - a footnoted bare year, such as `2024(a)`;
    - a range of two bare years, such as `2024 – 2026`;
    - a fiscal-year range: a bare year joined by a dash to two more digits,
      such as `2024–25`.
  - A bare year is four digits from 1900 to 2099 and nothing else.
- **Nil value:** a cell whose visible text is only `—`, `–`, `-` or `−`.
- **Period text** and **unit text:** period text is `table_completeness`'s
  `_PERIOD_TEXT` (duration words and month-day dates). Unit text is a unit
  declaration or a caption:
  - what `xlsx_tables._UNIT_LINE` matches, such as "(In millions)";
  - the unit captions the corpus run found, such as "(Dollars in millions)",
    "(Millions of dollars)", "(Dollars in billions)" and "(Dollars in
    millions, except per share amounts)";
  - the captions "(Unaudited)" and "(Audited)".

  R0 defines these patterns in `table_roles`. `_PERIOD_TEXT` and `_UNIT_LINE`
  themselves do not change, because checks 1–3 and the XLSX export use them.
- **Year run:** a row whose numbers outside the label column are all bare years,
  at least two of them, each within one of the next.
  - Examples: `2022 | 2023 | 2024`, `2025 | 2024 | 2025 | 2024` and
    `2023 | 2024 | 2025 | 2025`.
  - `Revenue | 2000 | 1900` is not a year run.
- **Explicit header row:** a row whose non-empty origin cells are all `th`
  elements.
- **Data row:** a row that is not an explicit header row and holds either:
  - a complete number or a nil value in a column other than the label column;
    or
  - a complete number in the label column, when that column is an identifier
    column.

  Three further rules apply:
  - A label-column number in a column that is not an identifier column does not
    make a data row (CRM 26's `4`).
  - **Bare years count as numbers in a row only when its label cell holds
    origin text that is neither period text, unit text nor a year-like value,
    and the row is not a year run.**
    - So `Revenue | 2000 | 1900` is a data row, as the completeness spec
      requires.
    - Header-like rows are not data rows: `| 2023 | 2022`,
      `2023 | Change | 2022` (empty label), `Maturities (calendar year) |
      2023 | 2022`, `Year Ended June 30, | 2025 | 2024`,
      `(Dollars in millions) | 2024 | 2023`, `2023 | 2022` with the first year
      in the label column, and the year runs `Segment | 2025 | 2024` and
      `Function | 2022 | 2023 | 2024`.
  - An explicit header row, such as a `th` row `Denomination | €1 | €2`, is
    never a data row.

  **Named limitation:** a data row whose only numbers are bare years within one
  of each other, such as `Units | 2024 | 2025`, reads as a header row. A role
  test pins this. The corpus run counts the year runs that are followed by no
  data row, and reviews them.
- **Header zone:** the rows before the first data row, ignoring rows without
  origin text. It continues only through header-like rows, and does not include
  its trailing label-only rows.
  - **Header-like rows.** The first row with origin text starts the zone. Each
    later row stays in the zone only when one of these holds:
    - its label cell has no origin text;
    - its label cell holds period text, unit text or a year-like value;
    - it is a year run;
    - it is an explicit header row;
    - it is a label-only row, such as a second title line. Trailing label-only
      rows still leave the zone (below).
    - it is the second row with origin text, and `main`'s sparse-row fusion
      applies to the first two rows.
      - Let n be the number of columns with origin text, leaving out
        marker-only columns. A marker-only column is one whose every origin
        text is a currency marker, `%`, `)`, `)%` or `(`. `main` merges these
        columns before it counts.
      - The first row must have no origin text in at least max(2, n // 2) of
        those columns, and the second row must have origin text in at least
        max(2, n // 2) of them.
      - `main` fuses such a pair into its header line, for example an
        `Exhibit Index` title over `Exhibit Number | Description | Filed
        Herewith`.
      - Counted on the source grid, the rule also fuses some pairs that
        `main`'s merged grid did not. The corpus has 45 such rows. 43 are NVDA
        section labels over a unit caption (`Inventories: | (In millions)`),
        and they read well. NTRA 123 renders better than `main`. TSM 216 fuses
        list item (b) with item (a), losing no value. Acceptance lists these
        rows.

    The first row that fails ends the zone. That row and every row below it
    are body rows, as `main` renders them. Examples:
    - `Common Stock | AAPL` under `Title of each class | Trading symbol(s)`;
    - `Finance leases | 15.1 years` under `| 2025 | 2024`;
    - the exhibit row `10.5.23 | Plan B` under `10.5.22 | Plan A`.

    A second header row whose label cell holds a column heading, such as
    `Contractual obligations | Total | Less than 1 year`, ends the zone unless
    the sparse-row fusion applies. `main` renders it in the body in exactly
    that case too.
  - A label-only row has origin text in the label column only.
  - Label-only rows right before the first data row are section labels, such as
    `Accounts Receivable:`, so they are body rows.
  - This includes a unit or period caption written in the label column only,
    such as `(In millions)`, which `main` also renders in the body.
  - Label-only is decided by origin. A caption whose cell starts in the label
    column is label-only even when its colspan covers the value columns, so a
    full-width caption right before the data is a body row. A caption whose
    cell starts in a value column is not label-only, so it stays header.
  - When no row is a data row, the header zone is the first row with origin
    text alone.
  - When the first row with origin text is a data row, the header zone is
    empty.
- **R0 is a rule on visible content.** Empty rows and empty columns (no origin
  text) are ignored, and positions are logical. The renderer and the checker
  apply it to their own grids and reach the same roles for the same visible
  table. Tests pin leading spacer columns, blank rows, span-covered slots and
  linked labels for this.
- **Row role:** header or body, from the header zone. Row roles are decided
  once, before any merge, and never change during the render (R0).
- **Header cell of a slot:** in a header-zone row, the slot's source cell when
  that cell has visible text.
- **Membership:** the source-grid columns an output column was built from.
  - An **owning member** contributes header ownership.
  - A **marker member** is a marker column removed by the structural pass. It
    contributes body text to the columns it fed, and no header ownership.
- **Currency markers:** `$`, `€`, `£`, `¥`, the prefixed dollars `US$`,
  `NT$`, `HK$`, `A$`, `C$`, `S$`, and the ISO codes `USD`, `EUR`, `GBP`,
  `JPY`, `CNY`, `RMB`, `CHF`, `DKK`, `SEK`, `NOK`, `HKD`, `TWD`, `CAD`, `AUD`,
  `INR`, `KRW`, `SGD`. The list is closed. A cell is a currency marker only when
  its whole visible text is one of them.
- **Structural policy:** `LEGACY` (today's vocabulary and thresholds) or
  `EXTENDED` (R3, R4). Only the Markdown render uses `EXTENDED` (R9).

## Rendering rules

### R0. Row roles first

`TableParser` decides row roles on the source grid, before the structural pass,
the legacy pass or any text concatenation, and keeps them. A shared helper
implements "complete number", "nil value" and "data row". The header-alignment
check uses the same helper. Tests pin expected row roles for named tables
independently of that helper (see Testing).

### R1. Merges never discard text

When the legacy pass merges column B into a group, every row is combined, row 0
included.

- A slot whose source cell is the same as the group's slot in that row counts
  once.
- Otherwise the two texts are joined with a space, as body rows are today.
- Header-zone rows are not concatenated into the output: the header line is
  assembled from membership (R6). Body text is joined as above.

This restores the 294 tables' lost values, for example JPM 109's `$ 84,973`,
TSLA 38's `$ 487`, AAPL's `9,943` and the pinned fixture losses. A pin is
removed only when its original content is shown to survive.

### R2. The header guard

Column B may merge into the group on its left only when all of these hold:

- **Body:** `_should_merge_cells` passes for every body row (R0). Under
  `EXTENDED` it treats every currency marker as it treats `$` today.
- **Header:** in every header-zone row, B's owning members have no header cell,
  or their header cells are all among the group's header cells in that row,
  compared by source-cell identity. When the group has no header cell in a row
  and B has one, B does not merge.
- **Marker exception:** the header test is waived when the group has no header
  cell in any header-zone row, and every non-empty body slot of the group is a
  currency marker, with at least one such slot. `(` columns are left to the
  careful merge (R3), because `_should_merge_cells` can never pass for them. In each body row where
  the group holds a marker, B must hold a value that validates when joined. The
  merged column carries B's headers. An empty group never qualifies.

Effects:

- **Kept:** offset values under one header, such as a `$` row's amount one grid
  column right of the other rows' amounts (AAPL 15 and the other measured
  shapes). Trailing `)`, `%` and spacer columns without header text are still
  absorbed.
- **Blocked:** a column that starts a new period's span no longer merges into
  the previous period or the label column (class 3).
- **Blocked:** columns under different header cells, such as TSM 248's "Notes"
  and "2022", or RDDT's "Filed Herewith" and "Number" (class 2).

Acceptance (below) audits that the offset merges keep their values and header
attribution. It does not require the old number of merges.

### R3. The careful marker merge under `EXTENDED`

`_merge_structural_columns` keeps its validation: a merge happens only when the
complete rebuilt token is a valid number. Under `EXTENDED`:

1. **Visible text.** Zero-width characters are whitespace (NTRA).
2. **Body start.** The body is the R0 body rows, exactly as R0 classifies
   them. A header-zone row of period text or a year run is not body (MSFT 24,
   TSM 312), while a data row such as `Revenue | 2000 | 1900` is.
3. **Leading-dot decimals.** Fragment recognition and final validation both
   accept `.75` and `(.62)`. Both are local to `TableParser`; strict's
   `quality.normalize_numeric_token` does not change.
4. **Single and percent negatives.** A marker column with one non-empty marker
   may merge, and `)%` is a closing marker, when the rebuilt token validates
   (BABA 69, TSM 79).
5. **Header ownership never moves.** The structural pass routes body markers
   only. It does not move or join header text, so `_header_merge_target` is not
   used under `EXTENDED`. The removed column becomes a marker member of the
   columns it fed.
6. **Independent header content.** A marker column is not removed when, in some
   header-zone row, its header cell covers no owning member of any surviving
   column. That is, the marker column owns header text no value column shares.
   This mirrors `prepare_table`'s existing veto: "A marker column carrying
   independent header text must remain visible."

Astra's mixed-direction case is a marker column under the 2024 span, with `$`
rows routing right to 2024's amounts and `)` rows routing left to 2025's
amounts. Its body tokens rebuild correctly in both directions. The 2024 header
belongs to the 2024 amount column through its owning member, never to 2025.

Whole-column validation still rejects a marker column that also holds nil
values or other periods' markers. The class-8 cases this leaves split are
listed individually in the acceptance record, not assumed fixed.

### R4. Currency markers

Under `EXTENDED`, every marker in the list behaves as `$` does in the careful
merge: a currency-marker column merges into the amount on its right, written
`€ 1,234` or `RMB 941,168`.

- The match is whole-cell, and the attachment side must hold a validated
  amount.
- Validation strips the marker before the local numeric test. Strict's
  normalizer is unchanged.
- A header-row currency label ("RMB" over an amount) is header text, assembled
  by R6. It is not a marker column.
- An unknown code (for example `ABC` or `XYZ`) is not a marker.
- The corpus has no per-row non-`$` currency column, so these cases are tested
  synthetically.

### R5. The header line

`_process_headers` uses the R0 header zone instead of "row 0, plus row 1 when
row 0 is sparse".

- Every header-zone row contributes to the header line, so third and later
  header rows leave the body (244 tables).
- No data row is promoted into the header (29 tables).
- When the zone is empty, the header line is written with empty cells and every
  row is body. Example: JPM 109, whose first row is
  `Noninterest revenue – reported | $ 84,973 | …`.
- When no row is a data row (text tables, signature blocks), row 0 alone is the
  header. Row 1 is not fused into it. A misread numeric fragment must not cause
  this fallback to be chosen: split negatives are rebuilt before the test (R0).

### R6. Header assembly from membership

For each output column, the header line text is built from the header zone, top
to bottom:

1. In each header-zone row, collect the header cells of the column's owning
   members, by source-cell identity, in member order. R2 and R3 together
   guarantee at most one distinct cell per row. If two ever occur, their texts
   are joined with a space; the alignment check reports the conflict.
2. Join the rows' texts with ` — `, skipping empty texts and a text equal to the
   one before it. Equality uses the checker's normalization (step 10:
   whitespace collapsed, case folded), but compares link destinations too.
   Two cells with the same label but different links are both kept.

A header cell that spans several output columns appears in each of them:
`Year ended March 31, — 2024 — RMB`. A table-wide title therefore repeats in
every column header, for example BAC's "Table 10 | …Regulatory Capital under
Basel 3". This is the user's choice: every column keeps its full context.

### R6a. Header accounting in strict's numeric trace

Repeating a spanning header writes extra copies of its numbers, such as a
`2025` over "Actual" and "Budget". `quality.trace_numeric_failures` counts each
number's occurrences in an element against its mapped source nodes, so without
this rule strict raises "untraceable normalized number" (Astra reproduced this
in both modes). An aggregate credit is not enough. Combined with R6's skipping
of an equal lower header text, it leaves unused occurrences that a body number
could consume (Astra, round 2).

The trace therefore accounts for a table's header line separately from
everything else in the element.

1. **The header record.** The render that produced the element content records,
   for each table:
   - the exact header-line string it wrote, or none when the header line is
     empty;
   - `header_source`, the multiset of numeric tokens in all of the table's
     header-zone source cells, each cell counted once, using strict's
     `_normalized_numbers` over visible text;
   - `header_capacity`, each header-zone cell's tokens multiplied by the number
     of output columns whose header that cell covers.
2. **Which render.** The record comes from the render whose Markdown became the
   element content:
   - for a table without links, the normal render;
   - for a table with links, the anchor-stripped re-render in
     `Parser._element_segment_content`.

   The record is bound to the original table node. A record from a render that
   did not supply element content is discarded.
3. **Header check.** For each table node among the element's mapped source
   nodes that has a record:
   - **Locate the header line** by an exact table-to-output association. The
     record identifies the table's own segment within the element content, and
     the header line is found only inside that segment, as its first line.
     Never search the whole element or replace text freely, because an
     identical prose or body line elsewhere must not be removed.
   - Each located header line is consumed once.
   - Every token count of that line must be within `header_capacity`. An excess
     is a failure: `<element id>:header:<token>`.
   - **When the association is missing or ambiguous** (the segment cannot be
     found, or its first line is not the recorded string), the table is granted
     no header exemption.
     - Its header line stays in the output pool, and its `header_source` is not
       subtracted, so the trace is exactly today's.
     - That does not guarantee a strict error: a faithful repeated header can
       balance, as in the `2025` over `2025` and `Budget` source.
     - Each such miss is recorded on the parser (`header_accounting_misses`),
       so it can never pass as successful accounting. Acceptance requires none
       on the fixtures and the corpus, or each one individually reviewed.
     - A table rendered inside a list item or an inline wrapper has no segment
       of its own, so it is recorded as a miss.
   - Tests cover the missing and the ambiguous case, each with a genuine
     ordinary-trace excess and with the no-excess source above.
4. **Everything else.** The occurrence-sensitive trace then runs on the
   remainders:
   - the output pool is the element content without the located header lines;
   - the source pool is the mapped nodes' tokens minus each recorded table's
     `header_source`.

   Header-zone source occurrences therefore justify header-line copies only,
   and can never cover a body number or nearby prose.

   `header_source` uses the same token accounting as the mapped source pool.
   - The header-zone cell nodes' `get_text(" ", strip=True)` are joined in
     document order with single spaces, as the pool string is built, and then
     tokenized once with strict's `_normalized_numbers`.
   - A split negative across header cells therefore tokenizes exactly as it
     does in the pool.
   - Subtraction is a multiset difference.

Astra's counterexample is a spanning `2025` over a lower `2025` and "Budget",
with the body mutated to `Revenue | 100 2025 | 200`:

- the header line holds two `2025` copies, within a capacity of two from the
  spanning cell plus one from the lower cell;
- both source `2025`s are removed from the body pool;
- the body's `2025` has no source occurrence left, so it fails.

`trace_numeric_failures` gains an optional argument carrying the element's
header records. Without records, it behaves exactly as today. Strict's other
checks do not change.

### R7. Empty-column cleanup

`_clean_empty_rows_and_cols` removes a column only when it has neither header
text nor body text. Header-only columns stay, including signature dates,
exhibit-index columns with no entries and `(a)` heads (37 tables). Empty rows
are still removed.

### R8. One-row PART tables

The PART branch of `Parser._one_row_table_to_text` keeps every cell after
normalizing the label:

> `PART III 2025 Annual Meeting Proxy Statement (Proxy Statement) to be filed
> with the Securities and Exchange Commission (SEC) within 120 days after the
> end of the fiscal year.`

The line still starts with `PART III` followed by whitespace, which Astra
confirmed `PART_PATTERN` matches. The section regex does not change. The ITEM
branch keeps only the first non-empty cell after the label, as today; this spec
does not claim that every one-row table keeps every cell. The plain join is
unchanged.

### R9. The XLSX boundary

`TableParser`'s structural helpers gain a keyword-only `policy` argument that
defaults to `LEGACY`:

- `_safe_structural_actions(grid, *, policy=LEGACY)`;
- `_validated_structural_actions(grid, actions, *, policy=LEGACY)`;
- the predicates and marker vocabulary they use.

`TableParser`'s own Markdown render passes `EXTENDED`. `xlsx_tables.prepare_table`
is not changed, so its calls stay `LEGACY`. `_join_structural_text` keeps its
current behaviour for the legacy vocabulary; currency joining is reached only
under `EXTENDED`. XLSX's sentinel-header construction is untouched.

### What does not change

- `TableParser.md()`, `to_markdown()` and `to_matrix()` keep their signatures.
- List tables, unreliable-table fallback text (capture mode) and positioned-div
  tables render as today.
- Nested tables get no special handling. `TableParser`'s grid already
  flattens their rows into the outer table, and R1–R7 apply to that grid like
  any other. Their output can therefore change, for example keeping an outer
  cell's `12` that was dropped before. Nested-table structure stays deferred.
- Cell text extraction is unchanged apart from removing zero-width characters.
- XLSX prepared tables, and XLSX workbooks apart from the open S3 exception:
  - The contents sheet prints `display_page`.
  - `Parser._extract_page_number_from_content` guesses it from the first and last lines of each Markdown page, table lines included.
  - So a changed table line can change the guess. The corpus has 9 such snapshots in 2 documents: NTRA page 76, and TSM pages 47, 146 and 160.
  - **Open decision (user).** The proposal is to accept these changes and list each one; the guess is a bug already on `main`, offered as a separate task. Until the user decides, acceptance marks XLSX as needing review.
- The completeness checks 1–3 and their definitions.

## Header-alignment check

A report-only check that each value sits under the header its source column
carries. It compares the source HTML with the Markdown text, like check 1. It
shares the R0 helper and the renderer's cell-text extraction with the renderer.
For cells without links it reuses the text the render already extracted (see
the interpretation tables). It never reads the renderer's merge decisions or
output-column mapping. So it can measure today's `main` and
would catch a later renderer regression.

### Source side

1. **Grid.** Place the unit's own visible rows with the snapshot builder's
   placement rules, as `table_completeness.header_row_count` does. Original
   coordinates are kept: placed rows and columns, including empty ones, are the
   coordinates of every span, value identity and finding.
   - When placement is unreliable (a bad span, an overlap, a nested table or an
     oversized grid), skip the unit with reason `table_unreliable_grid`.
2. **Row roles.** Apply R0, a rule on visible content, to the cells' visible
   text (link labels only).
   - Empty rows and columns (no origin text) are ignored for classification.
   - The label column is the leftmost column with origin text.
   - This analysis is the checker's own, and does not use the renderer's
     cleanup or merges.
   - When the header zone is empty or no row is a data row, skip the unit with
     reason `table_no_header` or `table_no_data`.
3. **Value columns and discriminating headers.** Value columns are the grid
   columns other than the label column that hold a complete number in a data
   row. An identifier column's numbers are row labels, not values. A header cell is
   discriminating when the value columns it covers are a non-empty proper
   subset of all value columns. Captions that span every value column are never
   required.
4. **Repeated headers.** A body row after the first data row that holds no
   complete number outside the label column, and holds period text or a
   year-like value (a bare year, a footnoted year, a range of years or a
   fiscal-year range), is a repeated header. Values below the first repeated header are not
   evaluated (reason `row_below_repeated_header`). The check does not judge stacked
   blocks against the top header.
5. **Values.** In each data row, rebuild split negatives. Each complete number
   outside the label column is one value; its column is its numeric core's
   column. The check tokenizes locally, accepting leading-dot decimals. A nil
   value is not evaluated (reason `value_nil`).
6. **Emitted path and expected headers.** For each value:
   - **Source path:** the header-zone cells covering its column, top to bottom.
     A cell that spans several header rows (rowspan) appears once, by
     source-cell identity, and cells with empty normalized text are dropped.
   - **Emitted path:** the source path with adjacent entries collapsed into
     one entry when their normalized texts are equal and their link
     destinations are equal, exactly as R6 writes a header. Two `Plan` cells
     linking to different exhibits stay two entries.
     Each emitted entry keeps the set of source cells and levels it represents.
     Non-adjacent equal texts stay separate entries, so `A — B — A` has three.
   - **Required entries:** emitted entries that represent at least one
     discriminating cell.
   - When there is none, the value is skipped (reason
     `value_no_discriminating_header`).

### Output side

7. **Cell parser.** Each Markdown table line is split on unescaped `|` outside
   link destinations, after one leading and one trailing pipe are removed.
   Blank cells are kept. Header and body cells align by index, and visible text
   reads link labels only. Split negatives are rebuilt across adjacent output
   cells, and the token is assigned to the index of the cell holding the
   digits.
8. **Pairing.** Use check 1's rule: a source data row pairs with an output body
   line only when its label key is unique among the unit's source rows and its
   output body lines. Unpaired rows are skipped (reason `row_unpaired`).
9. **Locating a value.** Find the output cells of the paired line that hold the
   value's token.
   - No cell: skipped (reason `value_missing_in_output`, which is check 1's concern).
   - More than one cell: skipped (reason `value_ambiguous_position`).
   - Exactly one cell: that is the value's output column j.

### Matching

The output header is judged against the value's own emitted path first, and only
then against the table's other labels. A literal ` — ` inside a source label, or
a longer label from another column, cannot hide the expected path.

10. **Normalization.** Header text and labels are normalized by collapsing
    whitespace, case folding and reducing links to their labels.
11. **Exact path rendering.** When column j's normalized header text equals the
    value's emitted path joined with ` — `, the value is aligned. This is how
    R6 renders a faithful header. It does not depend on other columns' labels,
    so `Income — net` over a column whose path is `Income`, `net` is aligned,
    even when another column's single source label reads `Income — net`.
12. **Segmentations.** Otherwise, consider every way to split the header text at
    a subset of its ` — ` separators.
    - A segment that equals the normalized text of one of the table's
      header-zone cells is a label occurrence.
    - Any other segment is unattributed text.
    - Each segmentation yields counts `found(x)` of label occurrences.
13. **Verdict of one segmentation.** It is consistent with the path when both
    hold:
    - every required entry's text x has `found(x) ≥ need(x)`, where `need(x)`
      is the number of emitted-path entries with text x;
    - no conflicting sibling text s has `found(s) > need(s)`.

    A **conflicting sibling** of a required entry is a discriminating header
    cell in the same header row as one of the cells the entry represents. It
    covers different value columns and has different text. An occurrence that
    the emitted path accounts for at another level is never a conflict. A
    comparison column labelled `2024` under the `2025` group has the path
    `2025 — 2024`, so its `2024` is needed, not conflicting.
14. **Decision.**
    - When every segmentation is consistent, the value is aligned.
    - When none is, the value is misaligned.
    - When they disagree, there are materially different viable assignments of
      labels to the path, so the value is skipped (reason
      `value_ambiguous_header`). The checker never reports a misalignment it
      cannot distinguish.
15. **Rows without discriminating text.** When a cell's text is shared by every
    sibling in its row (for example "RMB" over every period), that cell is not
    discriminating and imposes no requirement.

**Evaluation is bounded.** "Every segmentation" is the meaning of the rule, not
an instruction to list all 2^k splits.

- The checker runs a memoized search over separator positions. Its state is a
  position plus the counts of the relevant labels: the required texts and the
  conflicting-sibling texts. Each count is capped at `need + 1`, the most the
  verdict can depend on.
- From each state it records whether a consistent completion and an
  inconsistent completion are reachable. It stops as soon as both are reachable
  from the start.
- **The work bound** is 100,000 states per value. When it is reached, the value
  is skipped with the coverage key `value_unevaluated_budget`. Budget
  exhaustion is never aligned and never a zero-finding success.
- Tests include a header with many separators that is not exact. They cover
  both an all-inconsistent case, which cannot stop early, and a case that hits
  the bound.

**Failing controls, which stay misaligned:**

- `2025 — 2024` over 2025's amounts: every segmentation either lacks `2025`
  or carries an unaccounted `2024`;
- the same combined header over both columns, and a value swap under those
  headers;
- `Unadjusted` standing in for `Adjusted`: no segment equals `Adjusted`.

**Passing controls:**

- Astra's R6a source: a spanning `2025` over a lower `2025` and "Budget". The
  emitted path is one `2025`, which R6 writes once.
- An adjacent duplicate header.
- A faithful literal `Income — net`.
- Astra's three-column hierarchy: `Income` over `net` and `gross`, and a third
  column labelled `Income — net`. Each column is aligned by its exact path
  rendering.
- A repeated child label like `2025 — 2024`.

**Required both times:** a non-adjacent path `A — B — A`, which needs both
occurrences of `A`.

**The header-retention audit** (Acceptance) uses the same semantics. For each
output column holding values, the candidate's header must equal its emitted
path's rendering. Every header-zone cell must be represented in some emitted
entry that a column renders, which permits R6's adjacent suppression and
nothing else.

### Findings and coverage

```
table 24 (snapshot 19, page 41): "Revenue" 941168 under "2025 — RMB"; expected "2024"
table 7 (snapshot 5, page 12): "Product" 63946 under "2025 — 2024"; expected "2025", conflicting "2024"
```

- **Findings.** One per misaligned value, at most 10 listed per table, with the
  total, in a trailing defaulted field:
  `ParseDiagnostics.table_header_alignment: tuple[str, ...] = ()`.
- **Coverage.** Counts go in a second trailing defaulted field:
  `ParseDiagnostics.table_header_alignment_coverage: tuple[tuple[str, int], ...] = ()`.
  A completed run always emits every key below, in this order, with zeros where
  nothing applies.

  | Key | Unit | Meaning |
  |---|---|---|
  | `tables_total` | table unit | visible outermost units that `check_tables` numbers |
  | `table_no_output` | table unit | no output segment, or an empty one |
  | `table_no_separator` | table unit | output without a Markdown separator (one-row and text renderings) |
  | `table_unreliable_grid` | table unit | placement unreliable |
  | `table_no_header` | table unit | empty header zone |
  | `table_no_data` | table unit | no data row |
  | `tables_evaluated` | table unit | the rest |
  | `rows_data` | data row of an evaluated table | |
  | `row_below_repeated_header` | data row | below a repeated header |
  | `row_unpaired` | data row | label key not unique on both sides |
  | `rows_paired` | data row | the rest |
  | `values_total` | complete number or nil value outside the label column, in a paired row | |
  | `value_nil` | value | a nil value |
  | `value_no_discriminating_header` | value | no required label |
  | `value_missing_in_output` | value | no output cell holds it |
  | `value_ambiguous_position` | value | more than one output cell holds it |
  | `value_ambiguous_header` | value | the label occurrences are ambiguous |
  | `value_unevaluated_budget` | value | the matching search hit its work bound |
  | `values_evaluated` | value | the rest |
  | `values_aligned` | value | |
  | `values_misaligned` | value | |

  - **Precedence.** Each table, row or value takes the first applicable skip
    key in table order, so skip keys are mutually exclusive.
  - **Reconciliation.** These identities hold:
    - `tables_total = tables_evaluated + ` the five `table_` skips;
    - `rows_data = rows_paired + ` the two `row_` skips;
    - `values_total = values_evaluated + ` the six `value_` skips;
    - `values_evaluated = values_aligned + values_misaligned`.

    Rows and values of skipped tables are not counted.
  - **An empty tuple means the check did not run**: policy `off`, or a failure
    in `check_tables()`. It is never a successful zero. A completed run with
    nothing eligible records zeros. The separate Phase B requirement to tell
    disabled checks from failed ones remains.
- **Plumbing.** The check runs inside the guarded `check_tables()` call, and
  policy `off` skips it.
- **Not yet:** it is not logged, like check 2, and not added to
  `XlsxTableResult.completeness`, because the workbook has its own grid. It
  never makes strict raise; any enforcement needs a separate decision.

## Interaction with strict and the completeness checks

- **Strict.** R6a accounts for each table's header line separately. No other
  strict behaviour
  changes. Acceptance requires no new strict failures in either mode.
- **Pinned failures.** All 10 pinned value failures in
  `tests/test_table_completeness_fixtures.py` are class 1, so `PINNED_FAILURES`
  is expected to become empty. Each removal is recorded with the evidence that
  the original content now appears in the output. `TABLES_CHECKED` does not
  change, because units and their numbering do not change.
- **Definition false positives.**
  - F7 (CAT 143) is expected to disappear. The headerless table's first data
    row stays in the body under an empty header line, so check 2 sees it.
  - F1–F6 and F8 are check-side and expected to be unchanged.
  - **F9 (new, check-side).** Check 1 classifies an output cell such as R4's
    `US$ 1,250.0` as a text cell, so a correct rendering reports a value
    failure (TSM 344).
  - **F10 (new, check-side).** Check 1 reads header-line cells with `numbers()`
    only. Identifier references that R5 correctly moves into the header line
    are reported as missing, for example `2` in `(As restated – see Note 2)`
    and `3` in `(Note 3)`. This affects 15 tables.
  - **F11 (new, check-side).** Check 2's Phase A period-row test reads a
    unit-captioned years row, `(Dollars in millions) | 2024 | 2023`, as a data
    row. R0 writes that row into the header line. Check 2 then pairs it with a
    later stacked block's years row and flags every row below. This affects
    BAC 260, 293, 336 and 338, whose renderings are correct. Phase B: check 2
    takes its header rows from R0.
  - F9, F10 and F11 are fixed in Phase B with the source-token fixes. Checks 1–3 do
    not change here.

  Each change is recorded.
- **Check 1's header role** keeps using `header_row_count`. Tests pin the
  resulting role differences from R0 on named tables. Checks 1–3 do not change.
- **Mutations.** The three Phase A mutations must still be detected.

## Testing

Tests are written before the code they cover.

- **Row roles,** pinned independently of the shared helper. Each case states
  the expected role of every source row and the expected output header:
  - CRM 26: caption row with `4`, year row, then data;
  - JPM 109: headerless, first row is data;
  - AAPL 18: "Products 36.5 %" is data;
  - nvda-2026-10k 17: three header rows;
  - a first data row of split negatives: `Loss | (29 | ) | (40 | )` before
    `50 | 60`;
  - a genuine single-digit first data row;
  - an exhibit index starting at `3.1`;
  - an exhibit index `Exhibit Number | Description`, `1 | Agreement`,
    `3.1 | Articles`: header, body, body;
  - the all-integer variant (`1`, `2`): header, body, body;
  - a caption-number control (CRM 26's shape, with one label-column number):
    the caption stays header;
  - coordinate equivalence: leading spacer columns, blank rows, span-covered
    slots and linked labels. The renderer's cleaned grid and the checker's
    placed grid must assign the same roles and the same label column, and the
    checker must keep the original coordinates;
  - a text table with no data row, and a signature block;
  - a label column of bare years with amounts beside it;
  - a header row holding a standalone `(1)`, recording which role it gets;
  - a linked number, classified from its label.
- **One rendering test per class,** each built from a minimal copy of a real
  table in the evidence report:
  - JPM 109 (row-0 amounts) and CRM 26 (row-0 caption);
  - TSM 248 (Notes and 2022) and RDDT 52 (X marks);
  - MSFT 24 (`$` column and year) and BABA 24 (empty-slot shift);
  - JPM 482 (footnote column inside a segment span);
  - AAPL 18 and META 4 (swallowed data rows);
  - GOOGL 89 (signature date) and AAPL 64 (exhibit-index columns);
  - CAT 7 (PART);
  - BABA 69 and MSFT 43 (split negatives).
- **Provenance and the guard.**
  - Positive: offset values under one span (AAPL 15 and the other measured
    legitimate shapes).
  - Negative: sibling spans.
  - Astra's mixed-direction marker column: `2025` and `2024` each over their own
    amounts, with no `2025 2024` header.
  - The marker exception on both sides of a period boundary.
  - An empty group that must not qualify.
  - A marker column with independent header content that must stay, with
    complete tokens revalidated after the veto.
  - The R6 invariant: at most one distinct header cell per header row of an
    output column, asserted as a regression test. The fallback join is never
    an accepted outcome.
- **Currency, parametrized** across a symbol (`€`), a prefixed dollar (`NT$`)
  and an ISO code (`DKK`), each with positive, negative (`(1,234)`), decimal
  and percent amounts. Also an unknown-code control (`XYZ`), and a header-row
  currency label that must stay header text.
- **Other synthetic cases:** a U+200B cell beside an amount; `.75` per-share
  values; and a marker column with a nil value, recording the residual split.
- **Strict (R6a)**, in both rendering modes, with and without links, and with
  the table grouped with nearby prose in one element:
  - legitimate repetition passes strict;
  - Astra's counterexample fails: a spanning `2025` over a lower `2025` and
    "Budget", with the body mutated to `Revenue | 100 2025 | 200`;
  - an invented header year fails as a header excess;
  - an extra body amount fails;
  - a prose number that matches only a header-zone number fails;
  - a table with links is traced through the anchor-stripped re-render's
    record. A record from the other render is discarded.
- **XLSX boundary (R9).** `LEGACY` works on the bare `object.__new__(TableParser)`
  that XLSX uses, without new instance state, and every transitive helper,
  including final validation and joining, receives the policy. `prepare_table`
  results are unchanged for:
  - singleton markers;
  - currency codes;
  - leading-dot decimals;
  - the sentinel and header-start case (Astra's `Metric | 2025 | blank` probe).

  The comparison covers values, column groups, source coordinates, headers and
  issues.
- **The alignment check:**
  - a shifted header is reported, and an aligned table is silent;
  - failing mutations: merged sibling headers (`2025 — 2024`), both columns
    carrying every period label, a value swap under those labels, and
    overlapping label strings (`Adjusted` and `Unadjusted`);
  - passing controls:
    - a faithful literal label `Income — net`;
    - a comparison column `2024` under the `2025` group (path `2025 — 2024`);
    - Astra's R6a source (a spanning `2025` over a lower `2025` and "Budget"),
      and another adjacent duplicate;
    - Astra's three-column hierarchy, tested with all three columns together;
  - a non-adjacent path `A — B — A` that fails when one `A` is missing;
  - an ambiguous segmentation, skipped as `value_ambiguous_header`;
  - the header-retention audit on the same controls: suppression is permitted,
    and an unrelated loss is reported;
  - controls with blank columns, split negatives, leading-dot decimals, linked
    labels and escaped pipes;
  - each skip key, its precedence and the reconciliation identities. A
    completed run emits every key; a failed run emits `()`;
  - a non-discriminating caption is never required.
- **Integration:**
  - CAT 7 through `Parser` and the section extractor, keeping `2025` and `120`
    with Part III's boundaries unchanged.
  - Chunked tables with fused headers and empty header cells: content kept,
    header prefix repeated in full, column count right, citation offsets right.
    The existing oversize behaviour stays: a single row may exceed the token
    budget with its prefix.
- **Regression guards:** the existing suite passes, apart from deliberately
  updated pins and golden files. A `TableParser` test that pins today's
  behaviour is changed only where this spec changes it, each with a reason.

## Acceptance criteria

Acceptance compares a fixed population: unchanged `main` at the commit before
implementation, against the candidate. The corpus is the Phase A corpus,
identified by `results.json`'s document hashes and the EDGAR manifest.

- **Fixtures:**
  - `PINNED_FAILURES` is empty, or holds only individually documented and
    reviewed residuals;
  - check 2 reports nothing;
  - the three mutations are still detected;
  - rendering is identical with checks on and off.
- **Accuracy suite:** no fixture's words, numbers or financial-rows score drops.
  Markdown and page hashes change, as expected.
  - The suite's own independent numeric-trace check (`tests/accuracy/metrics.py`)
    applies R6a's header accounting with its own tokenizer.
  - It takes the header-zone cell texts from the parser's per-table header
    records, and the header lines from the output.
  - **The financial-row metric treats header rows as R6 renders them.** The
    metric counts any source row with at least two label words and two numbers,
    including header rows of dates. R6 fuses header rows into one header line by
    design, so a source row is also present when an output header line contains
    its label text and its numbers as a sub-multiset.
  - **Body rows must not drop.** Every source row that `main`'s output matched
    as a body row must be matched by the candidate as a body row, with one
    exception.
    - The exception is a row that R0 classifies as header-zone, which may move
      into the header line. Main misplaced such rows into its body, for example
      nvda-2002's second header row `(As restated – see Note 2)`.
    - Every such move is listed with its row and reviewed.
    - Any other body row lost is a failure.
    - The guard covers every source row with origin text that `main` rendered
      as a body row, not only rows the financial-row metric counts.
  - Both changes land with the regression task and are reviewed.
- **Moved rows.** Every source row that `main` rendered in its body and the
  candidate renders in a header line is listed, on fixtures and corpus.
  - The acceptance tooling checks each one against the header-like rule
    independently of `table_roles`.
  - A moved row that fails the rule is a failure.
  - The rows are reviewed by content signals: words in value cells, values
    with units, identifiers and links.
- **Sections:** section extraction on every fixture and corpus document gives
  the same sections and boundaries as unchanged `main`, or each change is
  individually reviewed. R8 can keep a short part-only stub that `main` drops.
- **Strict:** no new strict failure on any fixture or corpus document, in either
  mode.
- **XLSX:** prepared tables are identical to unchanged `main` for every corpus
  document: values, column groups, source coordinates, headers and issues.
  Workbook `display_page` changes are listed one by one. They are allowed only
  if the user accepts the S3 exception ("What does not change").
- **Check 1:** every one of the 294 class-1 tables has its lost content
  restored. Tables with value failures in `TableParser` output fall from 305 to
  the documented false positives: F1, F2, F3, F5, F8 and F9 (13 tables in the
  prototype's round 5). Any other residual is individually documented, reviewed
  and given its Phase B consequence. Page-furniture tables (573) are unchanged and reported
  separately.
- **Other findings:** no new check-1 or check-2 finding, unless individually
  documented. The F7 change and any other change to F1–F8 are recorded.
- **Alignment.** The candidate's checker runs on both unchanged `main`'s
  Markdown and the candidate's Markdown, over the same documents. Every run
  completes, with coverage present and its identities holding.
  - Findings fall to 0, apart from individually documented and reviewed
    residuals.
  - **Per-value identities.** The acceptance artifact lists every value by
    document, unit ordinal, source row and numeric-core column, in the placed
    grid's original coordinates, with its outcome in each run (aligned,
    misaligned, or the skip key).
    - The evaluated sets of the two runs are compared.
    - Every identity evaluated on `main` but not on the candidate is reported,
      even when total coverage grows.
    - Each such loss is reviewed individually, with its rendering consequence
      and its Phase B consequence. A skip key explains a loss; it does not
      approve it.
  - Per-key coverage is reported for both runs.
- **Assignment audit.** For the 6,616 measured same-header merges, the values of
  both source columns land in one output column, whose header renders their
  shared emitted path exactly.
- **Header retention audit.** This follows the matching section's semantics.
  - For every value in the alignment population, the candidate's column header
    equals the rendering of that value's emitted path.
  - Every header-zone source cell is represented by an emitted entry that some
    output column renders. That permits R6's adjacent suppression and nothing
    else.
  - Header-only columns must render the header cells that cover them.

  It covers word-only headers, literal ` — ` labels and header-only columns.
  The one documented residual is MSFT 69 (see Deferred). Any other mismatch is
  a failure.
- **Known shifted tables,** asserted header over value, independently of the
  checker's pairing: BABA 24, TSM 79, TSM 312, JPM 482, MSFT 24, MSFT 65 and
  RDDT 10-Q 2024 Q2 table 17.
- **Class 8:** a list of which split cases are fixed, with every remaining one
  reviewed.
- **Modes:** all 109 documents agree across the two rendering modes.
- **Review:** a stratified sample of about 30 changed tables is reviewed by eye,
  covering every class.
- **Overhead:** the candidate's total `Parser.get_pages(include_images=False)`
  time, divided by unchanged `main`'s, is at most 1.10 on the 7 fixtures.
  - Both sides use the same settings, normal mode and checks on.
  - Each figure is the median of at least five runs, in separate processes.
  - Per-fixture outliers are recorded.
  - This is separate from the completeness spec's Phase B budget and baseline.
- **Release:** a CHANGELOG entry lists each rendering change and the new
  diagnostics fields, and the RCQ version gets a minor bump. README and
  `docs/usage/direct-conversion.md` describe the header line, the alignment
  fields, and what the alignment check does not cover.

## Decisions for review

| Decision | Status in revision 4 |
|---|---|
| **T1.** Repeating spanning headers | Kept. R6a is now header accounting: header lines are checked against header-zone capacity, and header-zone source occurrences leave the body pool. |
| **T2.** The row-role test | R0, defined on visible content. Split negatives are rebuilt first, link labels are read without destinations, bare years never count, and single digits count outside the label column. A label-column number counts only in an identifier column. Roles are pinned independently, including coordinate-equivalence cases. |
| **T3.** Tables without a data row | The first row with origin text alone (accepted in rounds 1 and 2). |
| **T4.** Headerless tables | Empty header cells (accepted in rounds 1 and 2). |
| **T5.** The alignment check | Matching against each value's emitted path, which applies R6's adjacent suppression and keeps the cells each entry represents. An exact path rendering is aligned. Otherwise every split at ` — ` is evaluated: aligned if all are consistent, misaligned if none is, and skipped as ambiguous if they disagree. The coverage schema and per-value identity comparison were accepted in round 3. Values below a repeated header are skipped and counted. |
| **T6.** Currency markers | The closed list, with whole-cell matching, a validated attachment side, unknown-code controls and R9 (accepted). |
| **T7.** Overhead | +10% in total over unchanged `main`, under the measurement contract (accepted). |
| **T8.** The label-column rule | Replaced by the identifier-column rule: a label column with complete numbers in at least two rows counts integers and decimals alike. Named limitation: a table that also has numbered row labels as well as a caption number in its first row treats that caption row as data. It is pinned and reviewed if found in the corpus. |
| **T9.** Coverage in `ParseDiagnostics` | A tuple of name and count pairs, with the fixed schema, precedence and identities above (accepted with the schema). |

## Deferred

- **The XLSX grid** (`xlsx_tables.py`), including its own dropped sub-headers
  (audit #5). XLSX could later adopt the `EXTENDED` policy under its own spec.
- **Inline-run spacing in cell text** ("March 3 1", `1,2 34`). This is a
  text-extraction change with wide effects.
- **Nested tables.**
- **One-row tables that flatten a data row into one line** (23 tables). They
  lose column labels, not values.
- **Footnote-marker columns** such as JPM's "(b)(c)", which stay their own
  column under the right header rather than merging into the amount.
- **Positioned-div tables.**
- **Page-furniture tables.** These belong to the completeness spec's Phase B.
- **Mid-table repeated headers in stacked tables.** Rendered as body rows, and
  not evaluated by the alignment check below them.
- **Enforcement of the header-alignment check.**
- **A value cell whose span covers its period header's column** (MSFT 69).
  - The value's origin column has no header cell, so R2 keeps the year column
    apart, and each year heads the next period's value. `main` dropped the
    years instead.
  - The checker skips these values as `value_no_discriminating_header`.
  - A span-continuation rule fixes it. Simulated on the corpus, it changes MSFT
    69 and nothing else, but it needs a matching checker rule. It is left for
    a later change.
