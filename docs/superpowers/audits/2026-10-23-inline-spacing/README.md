# Inline spacing: acceptance record

This records the acceptance run for branch `fix/adjacent-span-spacing`: text that the source splits across adjacent inline nodes is joined as the source writes it.

## The bug

sec2md wrote a space at every text-node boundary, whether or not the source had one. Each string was stripped and appended as `t + " "`, and table cells, element contents and strict's source pool read `get_text(" ")`.

Donnelley/ActiveDisclosure filings split words and numbers across adjacent `<span>`s with no whitespace between them:
- `or 2</span><span>0</span>%` was written `or 2 0 %`;
- `$</span><span>68</span><span>.7 billion` was written `$ 68 .7 billion`;
- words split the same way: `in creased`, `b illion`, `D ELOITTE & T OUCHE`.

rcq-wealth held back 9 MSFT periodic filings on this. Its 17 applied MSFT periodic filings and 29 8-Ks carry the same splits.

## The rule

A space separates two pieces of text only where:
- the source has whitespace at the boundary (a trailing or leading space or no-break space, or a whitespace-only string between them);
- or a separating tag sits at the boundary (`table_parser.separates_inline`):
  - a block, line break or table cell;
  - a footnote marker: `sup`, `sub`, `vertical-align: super/sub`, or Workiva's raised `position: relative; top: -3.5pt`;
  - a box laid out on its own: `display: block/inline-block/...`, or `position: absolute`;
  - a gap made with horizontal padding or margin (Workiva's `Item 1.<span style="padding-left:22.5pt">Business`).

A relative offset that does not raise the text only kerns it, and joins: NVDA kerns digits that way. Hidden (`display: none`) text in a cell is skipped rather than joined (`100<span hidden>999</span>` reads `100`, not `100999`), as the stream already skips it.

The rule applies to:
- the page stream, inline bold and italic wrappers, and lists (`parser._render_inline`, `_separate`);
- table cells (`extract_cell_text` → `inline_text`) and one-row tables;
- positioned (PDF-style) element text;
- strict's numeric source pool.

Bold and italic runs that meet with no whitespace merge when their markers match: `**in**` + `**creased**` is `**increased**`. When their markers differ they keep one space, since Markdown emphasis delimiters cannot abut: `***Wafer Fabrication*** *:*`.

Strict's source pool (`quality.trace_numeric_failures`) and the header-zone source tokens (`TableHeaderRecord.header_source`) read the mapped nodes both ways:
- as before, with `get_text(" ")`;
- joined as the output joins them (`inline_source_text`).

Each token counts as often as the larger reading has it. A number traces when either reading shows it, so the earlier trace rulings keep their results: `<b>12</b>34` still reads 12 and 34.

## Behavior changes to existing tests

These changes need review. Each test was updated with a comment.

- **Bold runs that touch render as one run** (`test_quality`). `<b>(</b><b>650</b><b>)</b>` renders `**(650)**`, no longer `**(** **650** **)**`. MSFT's cover page now reads `**ONE MICROSOFT WAY,** **REDMOND,** ... **(425)** **882-8080**`.
- **Known limitation: numbers glued to a parenthesis or word drop out of strict's trace.** This affects split-run inputs whose runs touch. Strict's tokenizer reads no number in `650)`, `$(650)M`, `USD(650)` or `(650)thousand`.
  - Before, the spaces sec2md inserted made these split-run inputs tokenizable. A dropped `(` or an altered number was then reported, or, for `$(650)M`, strict failed on the unaltered filing.
  - They now read as the same text in one text node reads on `main`: out of the trace.
  - Tests: `test_dropped_bold_opening_parenthesis_reads_as_unsplit_text` and `test_split_parentheses_glued_to_a_word_read_as_unsplit_text`.
- **Zero-width characters inside a number now trace in strict.** This was a known limitation accepted on 2026-10-06 (`test_table_merge_headers`). The pool's joined reading drops the character as the render does, so strict passes where it used to fail.
- **Completeness check, "inline-split number"** (`test_table_completeness_parser`). The render now writes `1,2<span>34</span>` as `1,234`, so the check no longer reports a lost 1234. A new case reports it when the output writes `1,2 34`.
- **Accuracy harness oracle** (`tests/accuracy/metrics.py`). The harness's own source readings now join strings that touch inside inline elements, as a reader sees them (`_oracle_reader_text`). These readings are the visible text, the source rows and the trace pool.
  - The new rule generalizes the earlier exception for number fragments in links to one target.
  - Like the converter, the harness keeps the old split reading in its trace pool.
  - Touching range strings `3.5%-` + `4.3%` now read `3.5%-4.3%`, as the same text in one node does. The harness normalizer reads its dash as a sign there.

## Acceptance run

**Inputs:**
- **Candidate:** the branch head.
- **Baseline:** `main` at `33cfa14`.
- **Corpus:** 45 filings ([`filings.txt`](filings.txt)):
  - 18 MSFT 10-K/10-Q and 8 MSFT 8-Ks from the vault;
  - the latest three 10-K/10-Q of AAPL, CRDO, CRM, META, NVDA and RDDT, and the one SPCX 10-Q.
- **Settings:** each filing converted with `convert_to_markdown(..., return_pages=True, embed_images=False, quality_policy="warn")`, as rcq-wealth calls it ([`convert_corpus.py`](convert_corpus.py)).
- **Comparison:** [`compare.py`](compare.py) aligns the two outputs line by line and classifies every change. The summary is in [`corpus-diff.json`](corpus-diff.json).

**Results:**
- **Every change is a removed space.** 16,536 spaces were removed across all 45 filings, and none was added.
  - 28 lines changed more than spaces. All 28 are bold runs merged on MSFT cover pages (`**(** **425** **)**` → `**(425)**`) and in the MSFT 10-Q 2021-Q3 headings (`*March 3* *1, 202* *1*` → `*March 31, 2021*`).
- **Main categories, by the characters on either side of the removed space:**

  | Characters | Example | Count |
  |---|---|---|
  | `(` and digit | `( 248 )` → `(248)` | 7,617 |
  | digit and `)` | | 2,819 |
  | `$` and digit | `$ 14.3 billion` → `$14.3 billion` | 2,545 |
  | digit and `%` | `66 %` → `66%` | 1,323 |
  | letter and letter | `f or` → `for`, `A s` → `As`, `product s` → `products`, `D ELOITTE` → `DELOITTE` | 475 |
  | letter and `,` | `Cupertino ,` → `Cupertino,` | 320 |
  | digit and digit | `March 3 1, 202 1` → `March 31, 2021`, `20 2 1` → `2021` | 5 |

- **Spot checks against the source HTML:**
  - `Foreign currency–Revenue` is `Foreign currency<span>–</span>Revenue`.
  - `—%` is `<ix:nonFraction>—</ix:nonFraction>%`.
- **Padding gaps and raised markers keep their space:**
  - `Item 1. Business`, `• iPad Pro`, `(1) The valuation`;
  - `Depreciation and amortization (1)`, `iPhone ®`.
- **Digit-space-`%` in the MSFT output:** `<digit> %` occurs on 333 lines on `main` and on none on the branch. The `0. 44` and `202 3` shapes from the held-back MSFT filings do not occur in this corpus on either side.
- **Remaining `$ 287.97` and `| 25 % |`** (in the other companies' tables): these come from separate `$` or `%` cells, which the table renderer merges by its marker rules, not from split spans.
- **Strict warnings:** none in the corpus on either side.
- **AAPL golden fixture** (`tests/golden`, integration-only, already 277 lines from `main`'s output and not regenerated here): 266 changed lines, all removed spaces (475): `( 248 )` → `(248)`, `$ 14.3` → `$14.3`, `66 %` → `66%`.

**Tests:** the full suite passes (`pytest`, integration tests deselected as configured).
