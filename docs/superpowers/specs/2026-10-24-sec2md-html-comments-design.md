# sec2md HTML Comments in the Text Stream

Date: 2026-10-24 (revision 3)

Status: Implemented on branch `fix/baba-mapping-gaps`, pending the user's review of the PR.
- Revision 2 applies the Codex review below.
- Revision 3 records the measured results: fixtures, tests and the corpus check.

## Review history

**Round 1** (Codex, gpt-6-astra, effort medium; revision 1 → 2). Each finding was checked against the code before it was accepted.

| Finding | Verdict | Change |
|---|---|---|
| 1. High: `space_between` still treats a comment as a sibling. Two touching line fragments with a comment between them read `2 0`, not `20`. | Confirmed by reading `space_between`. A comment is a non-whitespace string, so each fragment is set apart from it. Table cells already skip comments before tracking `previous`. | New D2. |
| 2. Medium: `_all_bold` reads `find_all(string=True)`, which returns comments, so a comment changes bold-line continuation. | Confirmed by probe: `find_all(string=True)` returns `Comment` nodes. | New D3. |
| 3. Medium: the regression test could pass with only the `_stream_pages` skip, and it checked neither exact content nor offsets. | Confirmed: plain paragraphs never reach `_render_inline`. | Tests cover the inline path, positioned fragments, bold continuation, exact content and offsets. |
| 4. Low: "one shared definition" was wrong, and conditional comments and CDATA were not addressed. | Wording confirmed; the rest partly. lxml drops CDATA in HTML, so no `CData` node can reach the parser. | The tuples are now described as matching, not shared. "Special strings" records what lxml does with conditionals and CDATA, and a downlevel-hidden conditional is tested. There is no `CData` test, because the parser cannot receive one. |

## Purpose

PR kelab5am/sec2md#14 added BABA's EX-99.1 (`tests/fixtures/sec/baba-2026-ex99-1.html.gz`, 0001104659-26-099220) as a fixture. The accuracy harness found two kinds of gap in it:
- 16 elements without a source-node mapping;
- 48 numeric trace failures.

Both are identical on `main` at `c6e120a`, so the PR did not cause them. The PR pinned them in `tests/accuracy/test_sec_accuracy.py` as `KNOWN_MAPPING_GAPS = {"baba-2026-ex99-1": (16, 48)}`. This spec fixes the cause and lifts the pin, so the release contract again requires (0, 0) for every fixture.

## Root cause

**sec2md writes HTML comments into the Markdown as if they were visible text.**

BABA's exhibit was typeset by Toppan Merrill. Its HTML carries 122 typesetting comments, among them:
- `<!-- Field: Page; Sequence: 1; Options: NewSection; Value: 1 -->`
- `<!-- Field: Sequence; Type: Arabic; Name: PageNo -->`
- `<!-- Field: /Page -->`
- `<!-- Field: Split-Segment; Name: 1 -->`

BeautifulSoup parses each one as a `Comment`, which is a subclass of `NavigableString`. `Parser._stream_pages` and `Parser._render_inline` treat every `NavigableString` as text. So the comments reach the output, for example `Field: Page; Sequence: 2; Value: 1` on page 2.

The two symptoms follow from this:

1. **Missing mappings (16).** A loose string maps to its parent tag. 72 of the comments sit directly under the SGML `<TEXT>` wrapper, which spans the whole document. An element made only of such comments, such as `Field: /Page` at the top of most pages, maps to `<TEXT>` alone. `augment_html_with_ids` writes one `data-sec2md-block` value per node, so the last element to claim `<TEXT>` keeps it and the other 16 lose their mapping.
2. **Trace failures (48).** The numbers in a comment (`Sequence: 2`, `Value: 1`) are in the element's content. They are not in its mapped nodes' text, because `get_text` skips comments. Each such number fails the trace, as `sec2md-p2-t5-b66119a6:2` and `…:1`.

**The suspects named in the task are not the cause.**
- BABA's one-row layout tables map and trace cleanly.
- The SGML `<DOCUMENT>` header text (`EX-99.1 2 tm2623667d1_ex99-1.htm EXHIBIT 99.1`) maps and traces cleanly too. Whether that header belongs in the Markdown at all is a separate question, outside this spec.

**The rest of sec2md already skips comments.** These paths skip `Comment`, `Declaration`, `Doctype` and `ProcessingInstruction`:
- the table renderer, through `table_parser._NON_TEXT_STRINGS`;
- the completeness check, through `table_completeness._SKIP_STRINGS`;
- the XLSX grid, through `xlsx_tables`;
- `Parser._has_visible_text`.

Only the main text stream in `parser.py` is missing the skip.

## Change

The rule is that a comment is inert: the output is what it would be without the comment. Three places in the main stream still read comments, and each one changes.

`positioned_layout` gets a public tuple, `NON_TEXT_STRINGS = (Comment, Declaration, Doctype, ProcessingInstruction)`. It matches `table_parser._NON_TEXT_STRINGS` and `table_completeness._SKIP_STRINGS`, which stay as they are. It lives in `positioned_layout` because `space_between` needs it, and `table_parser` already imports from that module.

**D1. Text.** `Parser._stream_pages` and `Parser._render_inline` skip a string of a non-text type.
- A skipped string contributes nothing, not even the space its own edge whitespace would add, because `_edge_whitespace` would see the comment's body, not source whitespace.
- So `2<!-- x -->0` reads `20`, as a browser draws it.
- `a <!-- x --> b` keeps the single space that the surrounding text strings give.

**D2. Spacing.** `space_between(previous, node)` treats non-text strings as absent:
- It returns `False` when `node` is one.
- It steps `previous` back over them to the nearest other sibling.

Without this, two touching line fragments with a comment between them read `2 0` instead of `20`. The comment is a non-whitespace string, so `space_between` sets each fragment apart from it.

The callers that pass `previous_sibling` gain this:
- `Parser._join_inline`, `_stream_line` and `_stream_pages`;
- `table_parser`'s adjacency walk, which currently checks `separates_inline(cursor) or space_between(cursor.previous_sibling, cursor)` and `space_between(second.previous_sibling, second)`.

The cell walkers in `table_parser` and `table_completeness` already skip non-text children before tracking `previous`, so their results do not change.

**D3. Bold lines.** `Parser._all_bold` ignores non-text strings. It reads `line.find_all(string=True)`, which returns comments. Today a comment outside the `<b>` of a bold line box makes the line "not all bold", which breaks the line's continuation (D5 of the positioned-layout spec) into a new paragraph.

**Special strings.**
- lxml, which `Parser` always uses, turns a downlevel-hidden conditional comment (`<!--[if IE]>…<![endif]-->`) into a `Comment`, so its content is skipped, as a browser skips it.
- In a downlevel-revealed conditional (`<![if !IE]>shown<![endif]>`), lxml drops the markers and keeps `shown` as text, so it stays.
- lxml drops CDATA sections in HTML, so no `CData` node reaches the parser. D1 does not list `CData`.

Nothing else changes:
- The element builder and `augment_html_with_ids` stay as they are. A node still carries one `data-sec2md-block`, so an element whose only source is a shared ancestor can still lose its mapping (see "Out of scope").
- Hidden-node rules and table rendering stay as they are.

## Effect on the fixtures

Measured with D1–D3 against `main` at `2690d9f`:

| Fixture | Gaps before → after | Rendered output |
|---|---|---|
| `baba-2026-ex99-1` | (16, 48) → (0, 0) | All `Field: …` comment text is gone. Elements fall from 150 to 134, because comment-only blocks disappear, and most ids renumber. |
| `nvda-2026-ex99-1`, `nvda-2026-ex99-2`, `asml-2025-ex99-3` | (0, 0) → (0, 0) | One line changes in each. The Workiva comments `<!-- Document created using Wdesk -->` and `<!-- Copyright 2026 Workiva -->` (2025 for ASML) leave the SGML header line, for example `EX-99.1 2 q2fy27pr.htm EX-99.1 Document created using Wdesk Copyright 2026 Workiva Document` → `EX-99.1 2 q2fy27pr.htm EX-99.1 Document`. |
| the other six | (0, 0) → (0, 0) | Identical: Markdown, pages and annotated HTML. |

In the three changed Workiva exhibits, only the first element's content changes, so only its id changes. In the other six fixtures every element id is the same.

## Tests

1. **Regression tests**: the BABA-shape and inline tests are in `tests/test_parser.py` (`TestHtmlComments`), and the D2 and D3 tests are in `tests/test_positioned_layout.py`. Each one fails on `main`. Removing any one of the four skips (stream, inline, spacing, bold) fails at least one of them.
   - **BABA's shape.** A small document has an SGML `<DOCUMENT>`/`<TEXT>` wrapper and four pages. It has `Field:` comments with numbers: directly under `<TEXT>`, inside a paragraph, and two in a row. As in BABA, a page opens with `<!-- Field: /Page -->` and a bold heading, so the comment forms an element of its own that maps only to `<TEXT>`. On `main` this reproduces both symptoms: one element without a mapping (`sec2md-p3-t0-93cc5d45`, the same content hash as BABA's) and five trace failures. The test asserts:
     - each page's exact content;
     - every element's id appears as a `data-sec2md-block` in `parser.html()`;
     - every element has non-null offsets whose page slice equals its content (the document has no links);
     - the accuracy harness's `_mapping_and_trace` finds no gaps.
   - **Inline (D1, `_render_inline`).** The same paragraph is rendered with and without comments, in a bold wrapper and in a list item, which take the `_render_inline` path. A comment sits between spans (`2<!-- c -->0`), with whitespace on either side (`a <!-- c --> b`), and as a downlevel-hidden conditional. The output must be identical with and without comments: `20`, `a b`.
   - **Positioned fragments (D2).** In a line box, two touching fragments `2` and `0` read `20`, and two separated fragments read `2 0`, exactly as without a comment. The comment between them is empty (`<!---->`), has text, or comes as two in a row.
   - **Bold continuation (D3).** Two bold line boxes, one above the other, join into one paragraph (`**First** **Second**`) both with and without a comment outside the first `<b>`.
2. **Release contract.** Remove `KNOWN_MAPPING_GAPS` and its comment from `tests/accuracy/test_sec_accuracy.py`, and restore the two plain assertions from before PR #14:
   - `missing_element_mappings == ()` and `trace_numeric_failures == ()` in `test_rcq_release_contract`;
   - `not missing_mappings` and `not trace_failures` in `test_audited_document_meets_baseline_contract`.
3. **Full suite** passes, including the golden AAPL output and the body-row baseline, in a venv with `openpyxl`.

## Corpus check

This is the same check as PR #14's (`docs/superpowers/audits/2026-10-24-positioned-layout-corpus/compare.py`), run over the same 2,217 documents. It compares the branch against `main` at `2690d9f`.

**Acceptance.**
- No conversion errors.
- No document's table-check failures, reported tokens or structure findings rise.
- Every changed document is explained by comment removal: each removed or changed line differs only by text that occurs in that document's comments.

The record is in `docs/superpowers/audits/2026-10-24-html-comments-corpus/`: a README, `explain.py` and `explained.json`. The Markdown dumps stay in scratch.

**Result: accepted.**
- No conversion errors on either side.
- No table-check failure, reported token or structure finding changed in any document.
- 686 documents are identical. 1,531 changed, all through page content, and every one is explained by comment removal (two after review; see the audit README).

The comments that leaked:

| Source | Documents |
|---|---|
| Workiva `Document created using Wdesk` / `Copyright … Workiva` | 939 |
| `<!DOCTYPE …>` text inside the SGML wrapper (`html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" …`) | 491 |
| EDGAR filing-index pages: the SEC's Google Tag Manager script, `BEGIN BANNER` and other markers | 461 |
| Broadridge PROfile banners and page-number codes | 11 |
| Toppan Merrill `Field:` codes: BABA, and three CRDO 8-K documents | 4 |
| Other generator banners (DFIN ActiveDisclosure, older Workiva) and image file names | 43 |

418 documents have both a Workiva banner and a DOCTYPE, so the column adds to more than 1,531.

## Effect on rcq-wealth

Once rcq-wealth moves its sec2md pin, documents with comments in the body convert differently. The corpus check counts 1,527 vault documents: 5 primary documents and 1,522 retained exhibits and filing-index pages. Most lose one banner line at the top. The index pages lose the SEC's tag-manager script text.

Under rcq-wealth's rules, an existing document changes only by re-conversion into a new derivative revision, if the user chooses that. Nothing is rebuilt.

## Out of scope

- **Whether the SGML header belongs in the output.** The `<DOCUMENT>` header (`<TYPE>`, `<SEQUENCE>`, `<FILENAME>`, `<DESCRIPTION>`) still renders as one text line at the top of every exhibit.
- **Elements that map only to a shared ancestor.** A loose text string under a wrapper that spans several elements maps to that wrapper. The single-valued `data-sec2md-block` then keeps only one of those elements. With comments skipped, no fixture has such an element. Making the mapping multi-valued would change the annotated-HTML contract that rcq-wealth reads.
