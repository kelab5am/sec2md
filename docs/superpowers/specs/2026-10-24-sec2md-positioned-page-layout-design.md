# sec2md Positioned Page Layout Design

Date: 2026-10-24 (revision 3)

Status: Approved by the user on 2026-10-24, together with the fixture fetch from sec.gov.
- Revision 2 applied the Codex review below.
- Revision 3 adds the corpus check the user asked for.
- The numbers below come from a throwaway spike.

## Purpose

Some foreign private issuers file statements that Workiva renders as PDF-like pages: every page is a fixed-height box, and every line of text is placed with `position:absolute`. sec2md drops nearly all of that text today. rcq-wealth's foreign-issuer intake (TSM, BABA, ASML 6-Ks) cannot stage TSM's quarterly financial statements until this is fixed. rcq-wealth's spec `2026-10-24` §9 says to fix it in sec2md, not with a workaround in `rcq_kb`.

Measured on `main` at `c6e120a`:

| Exhibit | Size | Tables | `main` output | `check_tables` |
|---|---|---|---|---|
| TSM EX-99.1, 0001046179-26-000541, `a2026q2consolidatedreport-.htm` | 4.7 MB | 133 | 0 characters (107 with the SGML wrapper) | 125 checked, all 125 "produced no output" |
| BABA EX-99.1, 0001104659-26-099220, `tm2623667d1_ex99-1.htm` | 0.46 MB | 44 checked | normal | table 8: 10 negatives missing (`(14 \| )%`) |
| ASML EX-99.3, 0000937966-25-000014, `financialstatementsusgaapq.htm` | 0.43 MB | 8 checked | normal | clean |

**What the spike shows.**
- **TSM.** It recovers 166,445 characters on 66 pages, with display page numbers. 125 tables are checked; 2 still have missing values, and both trace to the completeness check, not the render (D7).
- **Existing fixtures.** On the seven existing fixtures the spike passes every pin and golden test: 2633 passed. The one failure, `test_internal_version_matches_distribution`, comes from the borrowed venv's installed metadata, not the code.

## Review history

**Round 1** (Codex, gpt-6-astra, effort high; revision 1 → 2). Each finding was checked against the code, by probe where possible, before it was accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: D6 joined fragments whose geometry is incomplete. Positioned `12` at `left:0` and `0` at `left:100`, without widths, would read `120`, and D7 would agree. | Confirmed | Incomplete geometry now separates, as today; only a proven abutment joins. On TSM this costs only range cells: `0.39% ~ 3.50%` instead of `0.39%~3.50%` (8 lines, no change in check results). A fragment with its own `top` is not a line fragment. |
| 2. High: D4 reused `_extract_page_number_from_footer`. It reads `Debt due within 12` as page 12 and `See Page 3 for details` as page 3, so D4 would delete that text. | Confirmed | D4 uses its own whole-string grammar. Anything else in the footer zone is kept. |
| 3. High: D2 sent the whole container to the flow path when one child was unmeasurable. A `px` pseudo-table with a plain caption is rebuilt correctly today (only the caption is lost); it would lose its grid. | Confirmed | The flow path is taken only when no child is measurable. A container with any measurable child keeps today's path. Its caption loss stays out of scope. |
| 4. Medium: D7.3 removed identifiers from check 2's source rows only. `output_line_numbers` reads `Cash Note 6` as `6`, so unchanged output would be reported out of order. | Confirmed (probe: `['6', '100', '6']`) | Identifiers are removed from both sides of check 2. |
| 5. Medium: D8's merged `(14)% (3)` turns the footnote from a `standalone_marker` source token into a `text_cell` output token, so the check reports a false `missing -3`. | Confirmed (probe) | New D7.4: a footnote in a close-marker cell may claim either position. The fixture pins also cover `reported`. |
| 6. Medium: D4's page-box boundary was not reconciled with CSS `page-break-before` and `page-break-after`, so a boundary could count twice. | Confirmed by reading `_stream_pages` | A page box starts a new page only when the current page already has content, which absorbs any CSS break. Nested page boxes do not break. |

## Layout being fixed

TSM's exhibit (Workiva "Wdesk" page output), simplified:

```html
<div style="--position:absolute; …; height:792pt; overflow:hidden; position:relative; width:612pt">   <!-- page box -->
  <div style="position:absolute; top:692.64pt"> … "- 3 -" … </div>                                <!-- footer, first in source -->
  <div style="position:absolute"> <div> <div style="position:absolute; top:18pt"> … </div></div></div>
  <div>                                                                                              <!-- not positioned -->
    <div style="line-height:7.63pt; position:absolute; top:700.72pt; width:612pt">                   <!-- line box -->
      <font style="left:85.5pt; position:absolute; width:449.86pt; white-space:pre">prepared and used in …</font>   <!-- fragment -->
      <font style="left:535.36pt; position:absolute; width:2.75pt"> </font>
    </div>
    …
  </div>
</div>
```

Tables are real `<table>` elements, but every cell's text sits in positioned line boxes inside the cell.

## Root causes

1. **Positioned containers keep only what the pseudo-table reader can measure.**
   - `_stream_pages` sends a `div` with absolutely positioned children to `_process_absolutely_positioned_container`. That path keeps only the absolutely positioned children with text, and passes them to `AbsolutelyPositionedTableParser`.
   - That parser reads `left` and `top` in `px` only.
   - So any non-positioned child (TSM's content `<div>`) is skipped, and positioned children without `px` coordinates produce nothing. The text is lost silently.
2. **A CSS custom property reads as positioning.** `_is_absolutely_positioned` tests for the substring `position:absolute`. That matches Workiva's custom property `--position:absolute` on every page box. `table_parser._SEPARATE_STYLE` has the same flaw. None of the seven fixtures contains `--position`, so fixing it changes nothing there.
3. **Positioned fragments are always set apart.**
   - `separates_inline` gives every absolutely positioned tag a space on each side.
   - Inside a line box, the fragments are pieces of one line.
   - In TSM, 113 adjacent fragment pairs abut with no whitespace at the boundary (`NT$` + `7,931,592`, `mar` + `ket`, `2025` + `, the related`). Spacing them would corrupt the text.

## Decisions

### D1. Custom properties are not positioning

`position:absolute` is matched only as a property name, not inside a custom property (`(?<![\w-])position\s*:\s*absolute`). This applies to the parser's `_is_absolutely_positioned` and `_is_footer_element`, and to `_SEPARATE_STYLE`.

A new module, `src/sec2md/positioned_layout.py`, holds this pattern and the geometry helpers below. The parser, the table parser and the completeness check then share one definition.

### D2. Choose the reading path per container; keep the measured path wherever it reads anything

**Measurable child.** An absolutely positioned child with a `px` `left` and `top`, or a footer that `_is_footer_element` recognises.

`_process_absolutely_positioned_container` takes the new **flow path** only when both of these hold:
- the container has at least one child with visible text: a non-positioned element, a non-empty text node directly in the container, or an unmeasurable positioned child;
- it has no measurable child.

Otherwise it keeps today's measured path: footer extraction, gap grouping, then `AbsolutelyPositionedTableParser`.

**Restriction (review finding 3).** A container that mixes measurable children with an unmeasurable one keeps today's measured path. An example is a `px` pseudo-table with a plain caption: its rebuilt grid stays as it is, and its caption is still lost, which stays out of scope.

**Result.**
- Every container the measured path renders today keeps that path. Only containers whose text is lost entirely today change.
- D6 can still change measured-path text, but only where the geometry proves two fragments touch.
- The measured path is not extended to `pt` units. It was built and tested for `px` pseudo-tables, and TSM's page layout is not a pseudo-table.

### D3. Flow path reading order: source order, footers last

The flow path reads the container's children in source order through `_stream_pages`. Workiva writes lines and tables in reading order. The one exception in TSM is the page footer, which comes first in the source (D4).

**Rejected alternative: sort every line by its coordinates.**
- Line boxes sit at several nesting depths, and each `top` is relative to a different positioned ancestor (page, table wrapper, cell).
- Sorting would need absolute coordinates accumulated through those ancestors.
- It would reorder content that source order already gets right. That adds risk for no gain on the evidence.

### D4. Page boxes are pages; page-number footers become display page numbers

A **page box** is a container on the flow path whose own style has `position:relative` (custom properties excluded) and an explicit `height`.

- **Footer zone.** A direct absolutely positioned child of a page box whose `top` is at least 80% of the box height. TSM's footers sit at 87% and 95%.
- **Page-number footer.** A footer-zone child with no table whose whole text is a page number.
  - The text must match `^[\s\-–—]*(\d{1,4})[\s\-–—]*$` (`3`, `- 3 -`, `– 3 –`) or `^Page\s+(\d{1,4})(\s+of\s+\d{1,4})?$`, case-insensitive, and the number must pass `_is_plausible_page_number`.
  - It is recorded in `footer_page_numbers` and not emitted, as the measured path does today for `px` footers.
  - `_extract_page_number_from_footer` is not reused, because it finds a number inside any text (`Debt due within 12`).
- **Other footer-zone content.** It is kept, and emitted after the page box's other children in its relative order.
- **Page breaks.**
  - A page box starts a new page when the current page already has content. A CSS `page-break-before` or `page-break-after` that has already opened an empty page is therefore not counted twice.
  - A page box inside another page box does not break.
  - TSM becomes 66 pages. The first (the cover) has no display number; the rest are numbered 1, 2, 3 … from their footers.

Only flow-path page boxes break pages, so no existing document's paging changes.

### D5. Line boxes join into paragraphs

- **Line box.** An absolutely positioned element with a `top` whose element children are all inline: `font`, `span`, `a`, `b`, `i`, `sup`, `sub`, inline XBRL and similar.
- **Continuation.** In the flow path, consecutive line boxes that are direct children of the same container belong to one paragraph when both hold:
  1. the next line's `top` is below the previous one by more than 0, and by at most 1.5 × the larger font size written on either line (10 pt when none is written);
  2. both lines are entirely bold, or neither is, so a bold heading line does not run into body text.

  Otherwise a blank line starts a new paragraph. Any other child, such as a table or a nested box, also ends the paragraph.
- **Joining.**
  - Continued lines are joined with one space, as a browser reflows wrapped text.
  - The one exception is a line that ends in a letter followed by `-`. It joins the next line with no space, so `Chinese-` + `language` reads `Chinese-language`. The characters are the source's own; only the line break goes.
- **Evidence (TSM).**
  - Body text is 11 pt, with a 13.2 pt line pitch and 26.4 pt between paragraphs.
  - The 14 pt title lines are 16.8 pt apart.

**Known limitation.** Emphasis is written per line, so the two bold lines of one heading read `**Taiwan Semiconductor Manufacturing** **Company Limited and Subsidiaries**`. That is faithful and readable. Merging emphasis runs across lines is out of scope.

### D6. Fragments of a line join only where the geometry proves they touch

- **Line fragment.** An absolutely positioned inline element that is a direct child of a line box and has no `top` of its own. A fragment with its own `top` may sit on another baseline, so it keeps today's separation.
- **Position alone does not separate.** `separates_inline` ignores `position:absolute` on a line fragment. Its other separating styles still apply: `display:inline-block` spacers, raised superscripts, padding gaps.
- **Join rule.** Two adjacent line fragments join as the source writes them only when the geometry proves they touch:
  - both have a `left`;
  - the previous fragment has a `width`;
  - `left − (previous.left + previous.width) ≤ 0.5 pt`.
- **Gap rule.** In every other case they are separated by one space, as all positioned text is today. That covers a measured gap and incomplete geometry alike.
  - Joining two separately placed numbers would corrupt them (`12` + `0` → `120`).
  - An extra space between the pieces of a word is the lesser error (review finding 1).
- **Evidence (TSM).**
  - Of 917 adjacent fragment pairs, 113 abut without whitespace and must join: `NT$` + `7,931,592`, `mar` + `ket`.
  - 74 have a measured gap: list markers such as `a.` and `1)`, and bullets.
  - 39 have no width. Only range cells change among them; they read `0.39% ~ 3.50%`.
- **Where it applies.** Everywhere inline text is joined: the parser's stream and inline render (`_stream_pages`, `_join_inline`), the table parser's cell walk (`_inline_fragments`), and `_joins_inline`. Body text and table cells therefore read alike.

Fragments nested inside a non-positioned inline wrapper are not line fragments, and keep today's separation. TSM's `JPY` [60 pt spacer] `6,095,977` reads `JPY 6,095,977`.

### D7. The completeness check reads the source as it is drawn

The spike's remaining TSM findings, and one introduced by D8, are check-side misreadings. The render is correct in each.

1. **Positioned boxes in the source reading.**
   - **Problem.** `table_completeness._walk` separates text only at block tags and marker changes. It reads `JPY` and `6,095,977`, two positioned boxes 60 pt apart, as `JPY6,095,977`, and reports `095977` missing.
   - **Fix.** The walk will also separate at every absolutely positioned tag, except a line fragment that D6 joins to the previous one.
   - **Result.** The check joins only what the geometry proves joined. It cannot agree with a concatenation the source does not show.
2. **Identifier references in header lines.**
   - **Problem.** For a source header cell `… (Note 1)`, `classify_cell` yields a `reference` token `1`. The output header line's tokens come from `numbers()`, which yields nothing for `(Note 1)`. So the source reference claims the header line's other `1`, the one from `(Notes 1 and 2)`, and that `1` is reported missing (TSM table 120).
   - **Fix.** Header lines will count identifier tokens, as body lines already do (`_output_cell_positions`).
3. **Identifier references in check 2.**
   - **Problem.** Check 2's source rows carry the `6` of `Cash and cash equivalents (Note 6)` as a token. The output tokenizer drops a parenthesized `(Note 6)` but keeps a bare `Note 6`. The balance sheet's rows are therefore reported as "values present but split across output rows" (TSM table 2, 21 messages).
   - **Fix.** Identifier tokens (`_IDENTIFIER` matches) are removed from both sides of check 2: from the source rows, and from each output line before `output_line_numbers` tokenizes it for `row_structure`. Check 2 is about where values sit, and an identifier is a label, not a value.
4. **Footnotes that travel with a merged marker (review finding 5).**
   - **Problem.** In the source, the `(3)` of `)%<sup>(3)</sup>` sits in a cell with no alphanumeric value. That makes it a `standalone_marker`, which claims only `numeric_cell`, `header_line` and `text_rendering` positions. After D8's merge, the output `(14)% (3)` puts it in a `text_cell` tail. The check then reports `missing -3 [standalone_marker]` (probe).
   - **Fix.** A footnote whose source cell value is only a close marker (`_CLOSE`: `)` or `)%`) or `%` gets its own kind. That kind may claim `text_cell` as well as the `standalone_marker` positions, so it matches whether or not the render merged the cell.

Items 2 to 4 are general check bugs that TSM's `(Note N)` labels and BABA's footnoted negatives expose. Rendering is untouched. The seven existing fixtures' pinned check results must not change; the existing pins verify that.

### D8. Split parentheses with footnotes merge in the render

**Decision: merge.**

BABA writes `(14` in one cell and `)%<sup>(3)</sup>` in the next. Its positive rows, `9` + `%`, use the same pair of columns. Today's output is `| (14 | )% (3) |` and `| 9 | % |`. The check reports the 10 negatives as missing, and a reader of the Markdown sees a positive `14` beside a stray `)%`.

The EXTENDED structural-marker merge already joins `)`, `)%` and `%` columns into their numbers: the 2002 NVIDIA fixture reads `(16,173)`. It fails here for two reasons. Both are fixed under EXTENDED only; LEGACY, which the XLSX path uses, is unchanged.

1. **Footnote suffix.**
   - A marker cell whose visible text is a close marker (`)`, `)%`, `%`) followed only by footnote references (`(3)`, `(4)(6)`, `[2]`, `*`) classifies as that marker.
   - The merged cell keeps the references after the rebuilt token: `(14)% (3)`.
   - Validation (`_validated_structural_actions`) checks the rebuilt token without the references.
2. **Mixed close column.**
   - A column whose markers are only `percent` and `close_paren` classifies as a mixed close column.
   - Both classes attach to the column on their left, so each row merges by its own marker. This is the same kind of exception as today's `legacy_mixed` (`currency` with `close_paren`).
   - Every rebuilt token must still validate, or the column is left as it is.
   - The independent-header veto and its revalidation still apply.

**Expected BABA rows.** `| (14)% (3) |` and `| 9 % |`. `9 %` keeps today's spacing of a merged `%` (`_join_structural_text`). D7.4 keeps the check's footnote accounting right after the merge.

**Rejected alternative: teach only the check to accept `)% (3)` as a split negative.** That would silence the finding but leave the sign detached from the number in the corpus.

## Fixtures and tests

### Fixtures

The three exhibits become deterministic-gzip fixtures in `tests/fixtures/sec/`: `tsm-2026-q2-ex99-1`, `baba-2026-ex99-1` and `asml-2025-ex99-3`. Each gets a `manifest.json` entry and a README row.

**Fixture bytes (user decision, 2026-10-24: fetch from sec.gov).** The cached copies differ from what EDGAR serves in two ways:
- **SGML wrapper.** They begin with the SGML `<DOCUMENT>…<TEXT>` wrapper.
  - EDGAR serves that wrapper on non-inline-XBRL exhibits, and the existing `nvda-2026-ex99-1` and `ex99-2` fixtures keep it.
  - The brief's instruction to strip it would make these fixtures unlike the real file.
- **Injected script.** They end with a `<script src="/GZe8DtCU…">` tag that sec.gov's bot manager injects into served pages. It is not part of the filing, and no existing fixture has it.

**Decision.**
- Fetch the three files once from `https://www.sec.gov/Archives/edgar/data/…`, with the User-Agent rcq-wealth's intake uses.
- Keep the bytes exactly as served, without the injected script, and record their SHA-256 values.
  - The existing fixtures carry no injected tag.
  - With the tag removed, each file's size must equal the size in the filing's `index.json`, as in the recent corpus's Ruling 1.
- The cached copies serve only as a cross-check.
- Fixture tests strip nothing. With the wrapper, the output gains only the SGML header line (about 110 characters); tables and check results are identical, as for the NVIDIA exhibit fixtures.

### Contracts

Each manifest entry carries:
- `form`: `EX-99.1` or `EX-99.3`, with `role: exhibit`;
- `expected_encoding_reason`: `strict-utf-8` (measured on all three);
- `expected_sections: []`;
- recall floors set from the measured values, rounded down to two decimals;
- one or two representative rows, taken from the source by hand:
  - TSM `Total current assets`: `4565700742`, `3817130817`, `3264917475`;
  - BABA `Revenue`: `247652`, `268953`, `39639`;
  - ASML: a row from its income statement, chosen when the contract is built.

### Pins and assertions

- **`tests/test_table_completeness_fixtures.py`:**
  - `PINNED_FAILURES` is `{}` for all three. A new assertion pins `report.reported` (missing references) as empty for them.
  - `TABLES_CHECKED` holds their measured counts.
  - `ALIGNMENT_COVERAGE` holds their measured tuples.
  - The mutation tests (blank renderer, reversed numeric cells, swapped body rows) are parametrized over `aapl-2023-10k` plus the three new fixtures, with measured expected counts.
- **`tests/accuracy/test_sec_accuracy.py`:**
  - The two corpus-size assertions go from 7 to 10.
  - The required forms stay `{10-K, 10-Q, 8-K}`.
  - `body_rows_main.json` gains entries for the new fixtures, generated from `main` with `generate_body_row_baseline.py`, as the file's header describes.

### Unit tests (new, synthetic HTML)

- **D1:** `--position:absolute` on a `div` does not make it positioned.
- **D2:**
  - a `px` pseudo-table container still takes the measured path (the existing tests stay);
  - a container with a non-positioned text child and no measurable child takes the flow path and keeps all text;
  - a column-major `px` grid with a plain caption keeps its rebuilt rows exactly as today (review finding 3).
- **D4:**
  - footer-zone page numbers fill `display_page` and are not emitted;
  - footer-zone `Debt due within 12`, `See Page 3 for details`, amounts, and a footer with a table are all kept, after the page body;
  - each page box starts a page;
  - `page-break-after` on a page box, or `page-break-before` on the next one, gives one boundary, not two;
  - a nested fixed-height box does not break.
- **D5:**
  - the line pitch decides continuation;
  - a change between bold and non-bold splits;
  - a trailing hyphen joins without a space;
  - a table between lines ends the paragraph.
- **D6:**
  - abutting fragments join;
  - a measured gap gives one space;
  - `12` at `left:0pt` and `0` at `left:100pt`, without widths, read `12 0`, in body text, in a table cell and in a measured `px` element;
  - a fragment with its own `top` stays separated;
  - a nested positioned box that is not a line fragment still separates;
  - a table cell reads the same as body text.
- **D7:**
  - each of these has a test that fails before the change: the `JPY` spacer, `(Note 1)` in a header line, `(Note 6)` and `Note 6` in check 2 (with the reference number equal to a value in the row), and a footnoted close marker, merged and unmerged;
  - a mutation that removes the `(3)` from the merged output is still reported.
- **D8:**
  - `(14` + `)%<sup>(3)</sup>` merges to `(14)% (3)`;
  - a mixed `%` / `)%` column merges per row;
  - a mixed column with one row that does not validate stays unmerged;
  - LEGACY output is unchanged.

## Corpus check (user, 2026-10-24)

The seven fixtures are a small sample of US filings, so this branch is also compared with `main` on the existing audit corpora:
- Phase A, the 109 documents of `audits/2026-10-03-table-completeness-corpus/`, including the RCQ set read from `E:\RCQWealth` (read only);
- the 70 annual reports of `audits/2026-10-06-recent-filings-corpus/`.

**Method.**
- Each document is converted on both sides, `main` at `c6e120a` (a `git archive` tree) and the branch, each in its own subprocess with its own `PYTHONPATH`.
- Two things are compared per document:
  - every page's content, number and display page;
  - the table-completeness report (failures, reported tokens, structure, tables checked).
- **Expected result.** A document whose source has no positioned container that takes the flow path is identical on both sides.
- **Explaining a difference.** Each document that differs is listed with its cause: a flow-path container, a D6 join, a D8 merge or a D7 check change. Each cause is explained from the diff.
- **What counts as a regression.** An unexplained difference, or a new loss.

**Where it lives.** The tooling and its results go in `audits/2026-10-24-positioned-layout-corpus/`: a script, `results.json` and a short `README.md`. Corpus bytes stay in the ignored `outputs/` folders as today.

## Acceptance

1. The seven existing fixtures render byte-identically. Their Markdown hashes, golden files and every existing pin stay unchanged.
2. TSM converts with its tables. `check_tables` reports no missing values, no missing references and no structure findings on TSM, BABA and ASML.
3. The full sec2md suite passes.
4. The corpus check finds no unexplained difference from `main`.

## Out of scope

- Extending `AbsolutelyPositionedTableParser` to `pt` units, or applying the flow path to `px` pseudo-tables it already reads.
- Recovering a caption or other unmeasurable child of a container that also holds measurable children.
- Multi-column page layouts, which the flow path reads in source order.
- Merging emphasis runs across lines, and dehyphenation beyond D5's trailing-hyphen join.
- rcq-wealth changes. The operator guide's note not to stage TSM's quarterly financial-statement 6-Ks is lifted in rcq-wealth after this merges and its sec2md pin moves.
