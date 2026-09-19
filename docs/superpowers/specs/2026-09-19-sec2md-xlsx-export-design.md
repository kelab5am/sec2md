# Proposed sec2md XLSX export design

Status: **Sample output approved for implementation planning on 2026-09-19, with the navigation correction below. Exporter implementation has not started.**

User review correction: do not freeze the first 11 rows. Production workbooks must have **no frozen rows**. Only the first label column may remain fixed for horizontal scrolling (`freeze_panes="B1"`); Contents has no frozen panes. The accepted prototype files remain unchanged as review evidence. The implementation plan is at `../plans/2026-09-19-sec2md-xlsx-export.md` relative to this document's directory.

Prepared 2026-09-19. Target project: `C:\Users\einstein\kelab5am\sec2md`, inspected at commit `c6fe201d4589e425c4f15eba8cd423f2e808f15e`, distribution `0.1.22+rcq.2`.

## Refined prompt used

Write a proposed design specification for XLSX export in the existing local sec2md fork. Inspect its parser, table models, provenance, public API and dependencies, and reuse the retained NVIDIA comparison evidence. Separate observed capabilities and defects from proposed behavior.

The deliverable is one workbook per supplied 10-K or 10-Q primary HTML document, with one worksheet per extracted table, for browsing, manual copying into Google Sheets and source cross-checking. Recommend a minimal integration and explicit defaults for table inclusion and ordering, sheet names, formatting, complete headers, labels, units, notes, provenance, numerical typing, original-text retention and partial failures. Define conservative ambiguity rules and independently checkable acceptance criteria. Distinguish local XLSX checks from actual Google Sheets import and clipboard acceptance. Identify unresolved product decisions with recommended answers.

Produce the specification, not an implementation plan. Make no source, dependency, fixture, integration or Google Sheets changes. Exclude cross-company matching, historical consolidation, inter-filing formulas and automatic delivery. Stop after presenting the specification for review.

## 1. Goal and recommended approach

Produce an ordinary, editable `.xlsx` file from one supplied filing. The user opens it, finds a table, copies its headers and values into Google Sheets, and checks against the retained filing.

Recommend a source-backed exporter using sec2md's existing table detection and DOM mappings, with conservative numeric conversion and an optional `openpyxl` dependency. No EdgarTools or XBRL statement reconstruction is needed for this feature.

Two alternatives were considered: splitting generated Markdown is smaller but cannot reliably reconstruct discarded header spans or original cell boundaries; an XBRL exporter is useful for financial statements but does not cover arbitrary disclosure tables. Neither satisfies this workflow as directly.

The existing public Markdown and page APIs retain their behavior. Export does not fetch related filings, exhibits or images. Existing input handling may fetch the single supplied URL; retained HTML bytes remain the reproducible, offline route.

## 2. Findings that constrain the design

- `TableParser` retains source `Cell` text and `rowspan`/`colspan`, but `_create_grid()` performs cleanup and column merging. `to_matrix()` therefore returns an already processed grid, not a lossless source grid. `_process_headers()` then fuses at most two rows for Markdown. XLSX must retain span and coordinate information before these transformations.
- `Parser` provides ordered page segments, `block_nodes_map`, generated element IDs, source URL and diagnostics. `Page` has both parser page numbers and detected printed page numbers. `Element` has no structured cell grid; returning `Page` objects alone does not retain everything this export needs.
- Element construction can combine a short preceding paragraph with a table. Table selection must identify the actual table segment/source node, rather than treating all content in a table-kind element as cells.
- `quality.normalize_numeric_token()` is a comparison helper. It strips `%` and currency and does not enforce spreadsheet unit semantics or comma grouping. Reusing it as the XLSX value parser would be incorrect.
- The package currently has no console-script entry point and no XLSX dependency. A Python export function is the smallest native entry point.
- Claude's helper produced 61 annual and 48 quarterly CSV tables from table elements. These are baseline inventories, not proof that every HTML table should become a worksheet.
- The saved quarterly income CSV has bare comparative dates in two columns. Inspection of the retained HTML confirms explicit spans for both duration groups, so complete headers can be recovered from source structure without guessing.

## 3. Table selection, ordering and naming

**Default selection:** all tables sec2md emits as tabular content, including nonfinancial tables, text tables, exhibits and repeated disclosures. Use the current parser's table/list/layout decisions. Do not add a financial-only filter or deduplicate by label, values or content hash.

A single-row layout table that sec2md currently turns into prose remains outside this export's table inventory. This limitation must be stated in documentation; the feature does not promise every HTML `<table>` node. Do not independently rescan all nested table tags and duplicate wrapper content. If a recognized tabular segment fails export, retain its place as a review worksheet.

Order worksheets by source traversal: parser page order, then table occurrence within each page. Do not sort by amount, statement type or inferred importance. Separate table fragments across pages remain separate worksheets; retain explicit continuation labels, but do not stitch them or borrow headers automatically.

Use names such as `001_p051_Income statement`. The prefix is the table ordinal, `p051` means parser page 51, and the suffix comes from an explicit caption or confidently associated heading. Otherwise use `Table`. Remove Excel-invalid characters, avoid reserved names, cap the total at 31 characters and ensure case-insensitive uniqueness while preserving the ordinal. The full title remains inside the sheet. Names need only be deterministic for identical input and exporter version; they are not cross-filing identifiers.

Recommend one additional first sheet, `Contents`, with internal links to every table, title, source pages, status and review count. This means **one worksheet per table plus Contents**: provisionally 62 and 49 total for the existing NVIDIA inventories. This extra navigation sheet is an explicit review choice, not an unstated interpretation of the requirement.

Do not infer fiscal year from a filename. Use supplied or explicitly available filing metadata; otherwise show the source filename and report date without inventing a fiscal label. Caller chooses the destination path; a suggested filename is `NVDA_10-Q_2026-07-26_tables.xlsx`.

## 4. Worksheet layout and readable formatting

Each table worksheet contains these visible areas, in order:

1. **Identity and source:** full title, supplied company/form/report metadata, source URL or input filename, parser page, detected printed page when available, element ID and export status. Show units verbatim, or `Units not established`.
2. **Copy-ready table:** complete headers followed by source rows in order, with numeric values only where conversion is unambiguous. No merged cells, extra audit columns, totals calculated by the exporter, or formulas. Clearly identify the complete range to copy, including the units/context rows immediately above it.
3. **Notes and review items:** associated footnotes, relevant local context, unresolved references and a compact cell-address/reason list. Include a link to the original-text area.
4. **Original extracted text:** source cell text before numerical conversion, with original header levels, structural symbol cells and spans retained visibly. This area is entirely text, except genuine blank cells. It is not hidden and does not depend on cell comments surviving another application.

Use a familiar 11-point font, restrained header shading, wrapped labels and headers, numeric right alignment and text left alignment. Do not freeze any rows: all identity, context and header rows scroll away normally. Freeze only the first label column for horizontal navigation (`B1`), and use no frozen panes on Contents. Follow the accepted sample's readable column widths, adapting to content without clipping. Set row heights to fit ordinary wrapped content. Preserve evident row groups/indentation and explicit subtotal emphasis without inventing accounting hierarchy. No automatic filter across mixed headers and row groups.

The original-text area may use merges to reflect proven source spans. It preserves extracted characters and logical structure, not exact browser typography. Line-break/whitespace normalization and any existing parser normalization must be disclosed; retained HTML remains the ultimate visual source. Cell comments on converted values can repeat original text and source coordinates as a convenience, but are not the sole audit record.

`Contents` also records source SHA-256 for retained bytes, sec2md/export schema versions, overall status and counts. For string input, identify a UTF-8 text hash as such; do not describe it as a hash of the original downloaded bytes.

## 5. Headers, labels, units, notes and provenance

Preserve row labels, order, repeated rows, grouping rows, footnote markers and mixed textual disclosures. Numeric-looking labels, identifiers and year headers remain text. Do not rename labels to a standard accounting taxonomy.

Flatten a proven header hierarchy into a self-contained label for each copy column. For the NVIDIA quarterly income statement, the four value columns must be:

- `Three Months Ended — Jul 26, 2026`
- `Three Months Ended — Jul 27, 2025`
- `Six Months Ended — Jul 26, 2026`
- `Six Months Ended — Jul 27, 2025`

Expand group text only over the columns covered by source spans, carrying those memberships through any structural-column consolidation. Do not forward-fill arbitrary blanks. A missing/conflicting header relationship stays visible as incomplete and is flagged; if values cannot be assigned reliably, make the table source-text-only. A first data row must never be discarded simply because a table lacks headers. Neutral labels such as `Column 2` may describe position and must be marked exporter-generated.

Retain units verbatim, including exceptions such as `in millions, except per-share data`. Explicit row or column units override broader table units. Never multiply a whole table by a scale when it contains mixed units. Unknown currency or scale stays unknown.

Associate notes using explicit cell markers/links and unambiguous local table context. Include contiguous caption/unit/note text bounded by the next table or heading; uncertain nearby text is labeled `Nearby source context`, not asserted to be a table footnote. Resolve explicit note targets within the supplied document. Keep external references as links without fetching them. A missing or multiply matching target gets an unresolved-reference warning. A generic reference to the financial-statement notes is retained as a reference, not expanded into the entire notes section.

Keep plain link labels in copy cells and preserve their destinations in hyperlink metadata or a visible reference list when a cell contains multiple links. Show parser page and detected printed page separately; printed-page detection is not proof of pagination and must not be inferred when absent. Record cell-to-source coordinates and transformation notes internally so merged currency/parenthesis fragments remain traceable.

Only append a source fragment to the SEC URL when that anchor actually exists in the original HTML. Generated `sec2md-*` IDs identify local annotated content; they are not live SEC anchors. A filing URL plus page and element references is an acceptable fallback.

## 6. Numeric handling

Keep the filing's displayed magnitude. Store **215938** for a displayed `$ 215,938` in a table reported in millions; retain the millions label. Do not convert it to 215938000000 or silently use an underlying full-unit XBRL value.

Conversion requires both a complete, valid token and a confidently numeric cell role. Financial values can be converted within proven value columns; headers, labels, postal codes, exhibit numbers, reference numbers and ambiguous mixed columns remain text. Percentage recognition requires an explicit `%` or an unambiguous percentage-only column/row unit. Column type alone must not coerce exceptions.

| Displayed content | Copy-ready behavior |
| --- | --- |
| `1,234`, `$ 1,234` | Numeric 1234 only with valid grouping and value context; preserve explicit currency/unit information. |
| `( 259 )`, `(259)`, `−259` | Numeric -259 when the entire token is a valid accounting amount. Parentheses on footnote markers are not negative signs. |
| `12.3 %` | Numeric 0.123 with `0.0%` display formatting. Preserve displayed precision. |
| `12.3` under a proven `%` header | Numeric 0.123; record that percentage meaning came from the header. Otherwise leave its meaning unresolved. |
| `0`, `0.00` | Numeric zero; preserve displayed decimal places. Accounting negative zero remains text with a review note if its sign cannot be preserved reliably. |
| Dates and year headings | Preserve displayed text in v1. No Excel serial dates, locale parsing or inferred date conversion. |
| Blank | Blank cell; never zero. Preserve a header-span blank as structural, not missing data. |
| `—`, `–`, `-` alone | Preserve the exact dash as text; never silently substitute zero or blank, even when an underlying tagged fact is zero. |
| `N/A`, `NM`, ranges, inequalities, malformed separators or mixed text | Preserve as text; flag potentially numeric ambiguities. Ordinary prose is not an error. |
| Value with a footnote marker | Separate the marker only when source markup proves the association; retain marker and note linkage in the visible notes/original area. Otherwise preserve the entire cell as text. |
| More than 15 significant digits, or outside Excel's reliable numeric range | Preserve as text and flag precision/range rather than round silently. |

Use decimal arithmetic for validation before writing ordinary spreadsheet numbers. Apply a strict grammar for US-style grouping/decimal tokens in these filings; do not reuse permissive comma removal or attempt locale guessing. Conflicting signs, units, unsupported currency/number formats or conflicting span mappings are review cases. A plain number's role is not established merely because a regular expression matches it.

Use standard Excel number formats for thousands separators, decimal precision, parentheses and percentages. Original text remains available even where spacing changes in the copy view. Write source text as explicit string cells, including text beginning with `=`, `+`, `-` or `@`; this export generates no executable formulas or external-workbook references.

## 7. Minimal integration and failure behavior

Propose a public Python function shaped as `export_xlsx(source, destination, *, base_url=None, user_agent=None, quality_policy="warn", overwrite=False)` returning a small export result with path, overall status, table counts and diagnostics. This is a proposed interface, not existing functionality. Accept the same HTML text/bytes or single URL inputs as the present convenience functions; local files are read as bytes by the caller. No new CLI framework is required for v1.

Add an optional `xlsx` dependency extra using `openpyxl` 3.1.x, with a tested minimum and upper major-version bound. Import it only for export. Missing dependency errors explain installation before parsing or writing. Markdown users acquire no new mandatory spreadsheet dependency. No pandas, Excel automation, browser runtime or network service is required.

Proposed code boundaries:

- One exporter module owns XLSX formatting, conservative numeric typing and the export result.
- A small structured table record carries original cells/spans, cleaned cells, source-coordinate mappings, contextual text and diagnostics. Capture it during existing table processing before destructive normalization. Reuse structural-column rules only when each result retains traceable source membership.
- `parser.py` supplies ordered table records and provenance using existing traversal and maps. `table_parser.py` exposes the required pre-flattening information. Positioned tables use their existing geometry; if a complete mapping cannot be established, export a flagged source-text view instead of guessing.
- The existing source resolution/decoding and quality checks are shared rather than duplicated. `core.py`/`__init__.py` expose the function, and `pyproject.toml` declares the optional extra. Existing return types and Markdown behavior stay compatible.

This is more than saving the current Markdown matrix with another extension: source spans and provenance must survive the export path. Limit that extension to table export; do not refactor the entire parser or build a financial data model.

Default behavior is best effort per table. Distinguish `Exported`, `Needs review` and `Source text only`. An ambiguous cell can remain text while other cells are usable. An unreliable grid gets a source-text worksheet with the reason and source reference; do not put uncertain numbers into a seemingly valid grid. Expected table failures do not stop other tables, and no recognized table is silently dropped.

The exporter defaults to warning/reporting for recoverable quality problems because this is a manual review workflow. Existing Markdown defaults remain unchanged. Explicit `strict` use honors existing parse-quality failures and additionally rejects export with table reliability failures. Structural ambiguities and fallback tables produce an overall `needs_review` result; ordinary reported dashes or blanks alone do not.

Show a concise result such as `61 tables: 58 exported, 2 need review, 1 source text only`, with details inside the workbook. Catch identifiable table-level failures, but propagate unexpected programming failures rather than mislabeling them as routine source problems. A missing destination permission, invalid input, unavailable dependency or workbook-write failure is a whole-export error.

Write to a temporary sibling file, reopen and check basic structure, then publish to the destination. Never replace an existing file unless overwrite was explicitly requested. Do not silently truncate Excel-limit violations (cell length, rows or columns). Preserve oversize text in clearly labeled chunks when possible; otherwise mark the affected table as unavailable in full, retain its source reference and return `needs_review`. If nothing can be exported, return a clear no-tables result rather than claim success; a Contents-only diagnostic workbook may explain the outcome.

## 8. Acceptance criteria

### Existing evidence and fixtures

Reuse the immutable files under `sec2md/tests/fixtures/sec/` and the independent row evidence in this comparison directory. Verify decompressed hashes before each acceptance run:

| Fixture | Actual period | SHA-256 |
| --- | --- | --- |
| `nvda-2026-10k.html.gz` | FY2026, ended 2026-01-25 | `73d81f5a111abcf72426c840871e76f5f5edc9631f436d495a86b6f87306d58b` |
| `nvda-2026-q2-10q.html.gz` | Q2 FY2027, ended 2026-07-26 | `e2634e509c241c5f45e3f6c115dc38a85645e5fdbee760b4a04f5e9035f6f7a9` |

Both hashes were rechecked during this design investigation. The quarterly fixture's calendar-year filename is not its fiscal-year label.

Prior comparison evidence checked 162 primary-statement rows and 389 explicit displayed numbers across the six statements. That excludes dash-only/blank cells and does not certify every other table. Claude's 61/48 CSV inventories are useful reconciliation inputs, but the CSV helper is not a source-of-truth oracle for header completeness or original values.

### Local workbook acceptance, after implementation

1. Generate both workbooks entirely offline from the frozen bytes. Reconcile every existing table inventory entry to a worksheet or explicit fallback. Expect 61/48 table worksheets under the current detection contract; investigate every count change against source rather than changing expected counts merely to pass.
2. Reopen the saved XLSX and verify the 162 primary-statement rows and 389 explicit numbers against retained HTML/independent evidence, including labels, sign, period column and reported scale. All six statements must be copy-ready; fallback is not a passing substitute for them.
3. Verify all four quarterly income headers above. Verify annual periods, balance-sheet instant dates, cash-flow duration labels, and unit exceptions separately. Header completeness is not established by numeric-value agreement.
4. Verify every exported cell has source mapping or is explicitly marked generated context. Retain all source display text represented by each table, including negatives, dashes, notes, links and mixed text. Compare original-text areas with source extraction, not with the typed copy area.
5. Include source-grounded spot checks of exhibits, trading-plan disclosures, a units/footnotes table and a mixed text/numeric table. Reuse prior defect examples to ensure coverage beyond the three financial statements.
6. Add focused edge cases for percent scaling, invalid comma grouping, identifiers, date text, negative zero, precision limits, footnote markers, formula-like strings, incomplete spans and positioned-table fallback. Do not rely on NVIDIA alone to exercise all rules.
7. Confirm table-local recovery preserves other sheets, zero-table and write errors are explicit, overwrite policy works, sheet names are valid/unique, and no formulas, macros or external-workbook links exist. Confirm every table sheet uses `freeze_panes="B1"` and Contents has none: no vertical freeze or horizontal split may pin the first 11 rows. Verify names/order/values deterministically; XLSX ZIP timestamps need not be byte-identical.
8. Run existing relevant parser/accuracy checks to prove export additions do not change Markdown, table detection or provenance. Visually inspect representative rendered/opened sheets for clipped headers, units, notes and navigability. Merely reopening via `openpyxl` is not visual acceptance.

### Google Sheets acceptance, separately recorded

Import each generated workbook into a disposable Google Sheets spreadsheet and check tab preservation, labels, long headers, numeric types, negative amounts, percentage values/formats, dates-as-text, blanks, dashes and scale labels. Check numeric types through actual cell values/types or temporary calculation checks; appearance alone is insufficient.

Also test the user's intended clipboard route: copy a representative table from the chosen local workbook application into an existing Sheets file. Include a quarterly statement, a percentage-bearing table and a mixed/footnoted table. Check the copied range with units and headers as well as value-only pasting where used. Record source application/version, browser, Sheets locale and paste mode because they affect interpretation.

Import and clipboard are distinct acceptance results: passing one does not certify the other. Hyperlinks, comments or formatting that do not survive must be documented; copy-critical provenance, units and headers cannot depend solely on those features. Until executed, label Sheets acceptance **not tested**. Two NVIDIA filings validate this starting point, not every issuer or historical filing format.

## 9. Decisions for review

| Decision | Recommended default |
| --- | --- |
| Extra navigation worksheet? | Include `Contents` in addition to one sheet per extracted table. If exactly N sheets is required, omit it and repeat diagnostics on each table sheet. |
| Where should original values live? | Visible original-text area below each table; comments are supplemental. |
| Keep all extracted tables, including nonfinancial ones? | Yes; preserve source order and current detection decisions. No selection configuration in v1. |
| Rescale figures into base currency units? | No; retain reported magnitude and explicit unit/scale labels. |
| Treat dates and reported dashes as numeric values? | No; keep them as source text in v1. |
| Required entry point? | Python API first, consistent with current sec2md. A CLI is a separate convenience decision if a no-code command is needed. |
| Which clipboard environment is authoritative? | Use the spreadsheet application and Sheets locale the user actually uses. This remains unresolved and affects live acceptance, not source extraction design. |

No cross-company row matching, historical consolidation, calculated financial statements, inter-filing formulas, automatic Google Sheets delivery or RCQ integration changes are included.

## 10. Evidence pointers and status

- Local implementation: `src/sec2md/table_parser.py` (`Cell`, `_create_grid`, `_process_headers`, `to_matrix`); `parser.py` (`page_segments`, table dispatch, `block_nodes_map`); `element_builder.py` (table/context grouping); `models.py` (`Page`, `Element`); `quality.py` (`normalize_numeric_token`); `core.py` and `pyproject.toml`.
- Prior controlled comparison: [REPORT.md](C:/Users/einstein/kelab5am/rcq-wealth/outputs/nvda-parser-comparison-20260914/REPORT.md), [sources.json](C:/Users/einstein/kelab5am/rcq-wealth/outputs/nvda-parser-comparison-20260914/sources.json), [primary-statement-row-proof.csv](C:/Users/einstein/kelab5am/rcq-wealth/outputs/nvda-parser-comparison-20260914/primary-statement-row-proof.csv).
- Claude evidence root: `C:\Users\einstein\AppData\Local\Temp\claude\C--Users-einstein-kelab5am-sec2md\bb934776-339d-460e-b22f-0f34085e9a0e\scratchpad`. Inspected `run_sec2md.py`, saved CSV outputs and validation JSON, including the quarterly income CSV `out/sec2md/10q/tables/p003_sec2md-p3-t1-ddd696a3.csv`.

This turn inspected source and saved evidence and rechecked fixture hashes/header spans. It did not rerun the whole comparison, produce an XLSX, implement export, install dependencies, edit either parser or test Google Sheets. The specification is the review deliverable; implementation has not started.
