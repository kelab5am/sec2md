# sec2md repository audit — 2026-10-02

> **Status update (same day).** Branch `fix/audit-2026-10-02` (worktree
> `.worktrees/audit-fixes`, not yet committed) fixes:
> - findings #6, #7, #11, #12 and #13
> - from the Medium list: `<ol>` under strict, `get_section(Item8K)`, the 9C
>   enum name, `ParseQualityError` pickling, and `Chunk.tags` order
> - the staging-cleanup issue
> - the test-environment, version, docs, `requirements.txt` and CI hygiene items
>
> Finding #2 is designed in
> `docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`
> on that branch; its evidence scripts are in `prototypes/`. Everything else
> below is still open.

## RCQ data check: META and RDDT (added same day)

The findings below were first found on the repo's AAPL/NVDA fixtures. This
section is a read-only re-check against the 20 primary 10-K and 10-Q filings in
`E:\RCQWealth\{META,RDDT}\Originals\SEC` (2024 to 2026 Q2) and their exported
workbooks. Scripts and raw results are in `prototypes/rcq/`.

| Check | Code on `main` | Branch `fix/audit-2026-10-02` |
|---|---|---|
| Default strict quality | passes all 20 | passes all 20 |
| Tables missing source numbers in Markdown (spec check 1) | 103 of 1,037 tables (115 material tokens) | unchanged (parser not changed) |
| Sections per META 10-Q | **0** (`PART I—FINANCIAL INFORMATION` not recognised) | 9 |
| Worst `chunk_section()` size vs section text | 25×–143× (e.g. META 10-K Item 6: 28 → 4,002 chars) | ≤1.19× |
| XLSX tables exported as numbers | about 89 of 918 (META 10-Ks: 1 of 64–65) | 384 of 918 |
| Exported numbers matching their source table | not measured | 10,544 of 10,544 |

- **Markdown value losses, confirmed by inspection:**
  - META commitments `The remainder of 2024 | $ | 10,563` renders as
    `| The remainder of 2024 | $ |`.
  - META 10-K maturities `2025 | $ | 26,335` loses its value.
  - The META 10-K ARPP table keeps 3 of 9 values.
  - The RDDT 10-K exhibit-index header is fused with its first exhibit, and
    three columns are dropped.
  - "Three Months Ended March 31," period headers vanish from every Q1 statement.
- **XLSX on `main`:** income, comprehensive-income, equity and cash-flow
  statements are text-only in both companies' workbooks; only balance sheets
  exported as numbers. The cause is `_PERIOD` in `xlsx_tables.py`, which did not
  accept "Three Months Ended March 31," with the year on the next row. The
  header count became 0, so the year row looked like a numeric value spanning
  two columns.
- **Fixed on the branch:** the META and RDDT Q1 2026 income statements now export
  with correct headers, units and values (META revenue 56,311 / 42,314).
- **Not seen in RCQ workbooks:** the dollars-as-percent bug (#3). No
  dollar-labelled percent cells were found.
- **Still open:** 373 tables remain text-only, mostly "Unresolved value span".
  Existing workbooks in `E:\RCQWealth` were produced by `main` and would need
  re-export to pick up the fix. Nothing in `E:\RCQWealth` was modified.

Scope: the whole repo. XLSX findings are against `fc1a91c` (PR #2 landed mid-audit);
parser, sections, chunking, quality and API code is unchanged since `7e99ea6`, so
those findings apply to both. No source files were modified.

Baseline: the suite passes (553 tests at `7e99ea6`, 565 at `fc1a91c`), Ruff is clean. It passes because
nothing in it checks that source values reach the output.

## Bottom line

The tool runs, but it can **silently produce wrong or missing financial numbers while
reporting success**. Four independent mechanisms do this on real or realistic filings,
and the strict quality gate cannot see any of them, because it only checks that numbers
in the output exist in the source, never the reverse. For RAG use, `chunk_section()`
returns text from neighbouring sections. Section extraction returns zero sections for
several common header formats without raising.

"Verified" below means I re-ran the reproduction myself; "auditor repro" means a
subagent ran a reproduction script (paths at the end); "read" means code reading only.

## Highest-impact findings

| # | Finding | Where | Evidence |
|---|---|---|---|
| 1 | **Table values dropped from Markdown.** When `$` columns merge, the merged column's row-0 cell is discarded as "header", but after spacer-row removal or in header-less tables row 0 is data. | `table_parser.py:625-639`, `289-310` | **Verified** on AAPL 10-K: `74,427`, `9,943`, `4,258` are in the source, absent from output (`\| 2024 \| $ \|`); default strict passes. Also loses NVDA ex99 cash-flow row (24,077 / 50,344 …). |
| 2 | **Strict quality gate is one-directional.** It checks output→source only; missing, reordered or column-swapped numbers pass. Size thresholds: <1,000 chars unchecked; 1k–10k only empty output fails; ≥10k fails only below 10%. | `quality.py:71-85`, `178-193` | **Verified**: AAPL with every table blanked passes strict (3,307 → 0 pipes). Auditor repro: reversed numeric columns pass. |
| 3 | **XLSX turns dollars into percents.** A units line "in millions, except … percentage data" makes percent the default numeric role. | `xlsx_tables.py:442`, `388` | **Verified**: Revenue 46,743 → cell value `467.43`, format `0%`, `status: complete` under strict. |
| 4 | **XLSX glues superscript-span footnote markers into numbers.** Only `<sup>`/`<a href="#">` count as marker boundaries. | `xlsx_tables.py:64`, `74-77` | Auditor repro: `567`+marker `1` → **5671**; `1.08`+`1` → **1.081**; `12.5`+`2`+`%` → **0.1252**; status `complete`. |
| 5 | **XLSX drops `td` sub-headers under a spanning period header**, mislabelling columns with no issue raised. | `xlsx_tables.py:403-430`, `573`, `600`; `table_parser.py:361` | Auditor repro on real AAPL table 26: all four headers read "2022", "Designated"/"Total Fair Value" lost, status `exported`, 0 issues. |
| 6 | **`chunk_section()` leaks other sections' content.** Section pages carry the whole page's `elements`, and the chunker prefers elements over the sliced content. | `section_extractor.py:360-366` (and 8 sibling sites); `chunker.py:87-88`, `193-222` | **Verified**: AAPL Item 1B ("None.", 41 chars) → 3 chunks / 6,483 chars of Risk Factors; Item 4 (48 chars) → 3,723 chars. Affects nearly every section in all fixtures. Element IDs, tags and page ranges leak too. |
| 7 | **`export_xlsx` hangs for ~days on a non-writable directory (Windows ACLs).** `tempfile` retries `PermissionError` up to `TMP_MAX` (2³¹) while `os.access` says writable. Nothing bounds it, and it happens after the full parse. | `xlsx.py:51` | Auditor repro on a write-denied scratch dir: ~6,500 attempts/s ≈ 92 h; killed at 20 s with no exception. This is the RDDT "hang". |
| 8 | **Header fusion swallows the first data row** into the header. | `table_parser.py:681-698` | Auditor repro: AAPL `\| Gross margin percentage: — Products \| 36.5 % \|` becomes header; synthetic `Revenue 2023 — 100`. |
| 9 | **Column-merge heuristic fuses complementary columns and drops period headers** (Debit/Credit become one column; year header over a blank spacer column vanishes). | `table_parser.py` (same as #1) | Auditor repro; nvda-2002 loses "Month Ended January 31, 1998" headers. |
| 10 | **Section extraction silently returns `[]`**: 8-K with no page breaks or with a "Table of Contents" back-link; 10-Q with `PART I—FINANCIAL…` (no spaces) or `PART I:`; ITEM number and title in separate elements; TOC heuristics only check pages 1-5. | `section_extractor.py:281-285`, `8-11`, `122-137`, `603-605`, `145-168` | Auditor repros (synthetic). With PART II missed, 10-Q Legal Proceedings comes back as a duplicate Part I Item 1 and Items 1A/6 are dropped. |
| 11 | **Chunk overlap is non-contiguous.** Short trailing blocks are skipped, so chunks show passages adjacent that are not adjacent in the filing. | `chunker.py:504-532` | Auditor repro: 25/49 AAPL, 56/101 NVDA 10-K, 16/51 10-Q overlapping pairs affected at default 512/128. |
| 12 | **Oversized-table splits erase a line and lose the column header** in continuation parts (header assumed to be line 1, separator line 2). | `chunker.py:107-158`, `blocks.py:306-309` | Auditor repro with `max_table_tokens=512`: units line and period header absent from continuation parts. Default 2048 doesn't split fixtures; bigger tables will. |
| 13 | **Table minifier emits one extra separator column**, which GFM won't render; repeats grow it. | `chunker/blocks.py:306-309` | **Verified**: `\| a \| b \|` → `\|a\|b\|\n\|---\|---\|---\|`. 11/11 AAPL tables affected in chunk output. |
| 14 | **`embed_images=True` fetches any URL in the filing (SSRF)** and embeds the response; no host/scheme allow-list, content-type check, size cap or de-dup. | `core.py:31-78` | Auditor repro against 127.0.0.1: an internal "secret" response was base64-embedded as an image. Matters only for untrusted HTML. |
| 15 | **Parser drops normal-flow content beside an absolutely-positioned child**, and treats `Label: text;` prose as CSS and deletes it. | `parser.py:612-670`, `726`; `parser.py:36`, `345` | Auditor repros (synthetic): a `<p>` with $4,321 and a table disappear; `<li>Compute: revenue increased 10% to $1,234 million;</li>` vanishes; strict passes. |

## Medium

**Parsing**
- Spaces inserted at every inline-tag boundary: "no t impaired", "NVIDIA CORP ORATION", `$1,2 34`, `( 565 )` (179 in AAPL tables). The gate tokenizes the source the same way, so it can't catch split numbers. `parser.py:425`, `686`, `784`; `table_parser.py:226`.
- Any `<ol>` raises `ParseQualityError` under default strict (list numbers count as untraceable). **Verified.** `parser.py:397-408`.
- Split accounting negatives misalign values: nvda-2002 has 16 rows like `(29 | ) | (18 | )`. `table_parser.py:384-476`.
- Positioned layouts: pt/in/% units or `right:` anchoring are dropped; `bottom:0` substring-matches `margin-bottom:0` and deletes real lines as footers. `parser.py:180-186`, `463-475`, `623-630`.
- Hidden content leaks (`visibility:hidden`, `hidden` attribute, hidden table rows, unwrapped `ix:header`); comments, `<script>` and `<style>` text are emitted ("Document created using Wdesk…" in ex99 outputs). `parser.py:217-222`, `682-687`.
- Display page numbers: printed 1-9 rejected, gap in numbering shifts every later page by +1. nvda-2002 page 41 → 1, page 66 → 825. `parser.py:822-891`.
- Element content differs from page content for tables with links (offsets wrong for 12 fixture elements); one-row tables collapse into one column. `parser.py:355-363`, `element_builder.py:122-135`.
- Encoding: declared utf-8 with cp1252 bytes raises `UnicodeDecodeError`; one stray byte decodes a UTF-8 file as cp1252 (mojibake passes strict); BOM-less UTF-16 passes as "R e v e n u e". `encoding.py:217-237`.
- `RecursionError` at ~1000 nested levels (legacy unclosed `<font>`); element building is quadratic in spans per block (16k spans → 14.8 s). `parser.py:677-803`, `element_builder.py:322`.

**Sections and chunking**
- Line-start "Item 7 of this Annual Report…" or "Part II of this report…" creates false sections that shadow real ones in `get_section`.
- Structure validation drops 10-K Item 4A and 20-F Items 16J/16K with their text; a 20-F without PART headers → 0 sections. `section_extractor.py:760-786`, `32-57`.
- Pre-2003 10-K: Part IV/Item 14 relabelled Part III, so `Item10K.PRINCIPAL_ACCOUNTANT` returns 96k chars of financial statements; the fixture manifest locks this in. `section_extractor.py:768-778`.
- `Item10K.CYBERSECURITY_DISCLOSURES = "9C"` is wrong (9C is the HFCAA disclosure; cybersecurity is 1C). `models.py:59`.
- `get_section(..., Item8K.X)` always returns `None` (no `Item8K` branch). `sections.py:62-84`.
- No hard cap on oversized text: one sentence-less paragraph → a 4,399-token chunk at `chunk_size=512`; sentence splitter only splits before capitals.
- Duplicate blocks inside one chunk from table-context backtracking (2–7 chunks per fixture). `chunker.py:373-396`.
- Last section absorbs SIGNATURES (golden `item_16.md` locks it in); 8-K check expects `**SIGNATURES**` but the fixture has `**SIGNATURE**`.
- `Section.markdown()` strips only edge `**` and deletes number-only lines, so it disagrees with the section's chunks. `section_extractor.py:115-119`.
- `Chunk.tags` order depends on `PYTHONHASHSEED` (built from a set). `chunk.py:153`.
- SC 13D/13G: answers on the heading line are lost; any line starting "Signature" (even on the cover) ends extraction; 13G Item 3 uses the 13D title.

**XLSX**
- Period header rows after a `th` caption, or with "(In millions)" top-left, aren't recognised; years are written as numbers (`2,026`). `xlsx_tables.py:418`.
- Header words like "year", "number", "date" force whole numeric columns to text with no review item. `xlsx_tables.py:399`, `435`, `618`.
- Every table before the contents table is dropped silently (AAPL ordinals 1-4). Contradicts spec §3. `xlsx_tables.py:232-251`.
- One unrenderable table (nested or ambiguous positioned) aborts the whole export even in `warn`/`off`, with plain `ValueError`. `xlsx_writer.py:169-198`.
- Review state, issues and "units not established" no longer appear in the workbook; `needs_review` tables look identical to `exported`. AAPL's unit line doesn't match `_UNIT_DECLARATION`, so its statements carry no units at all. `xlsx_writer.py:141-160`.
- `finally: unlink` in `_publish` can raise after a successful publish if another process holds the staged file, leaving a stray temp and a `FileExistsError` on retry. `xlsx.py:67-69`.

**API, network, quality**
- `ParseQualityError` can't be unpickled; `ProcessPoolExecutor` gives `BrokenProcessPool`, `multiprocessing.Pool` hangs. **Verified.** `quality.py:104-109`.
- URL fetch: no overall deadline (slow-drip hangs), no size cap, no content-type check (JSON or a 200 "rate exceeded" page is parsed as a filing), 429 not retried, cross-host redirects followed and links then resolved against the *original* URL. `utils.py:85-115`.
- URL input skips `base_url` validation: `https://user:secret@…` credentials are copied into every output link. `core.py:127-134`.
- Documented `open("10k.html").read()` pattern produces mojibake on Windows (cp1252 locale) and strict passes; docs should use `read_bytes()`. `docs/quickstart.md:89-92` and two other pages.
- A file path string (`"C:\\filings\\10k.htm"`) is treated as HTML and "converted" to the path text; strict passes. `core.py:100-109`.
- tiktoken downloads its encoding on first use with no timeout; on failure sec2md silently falls back to `len//4` and retries every call, so token counts differ between machines. `models.py:23-31`.
- `warn` diagnostics are discarded (only logged), contrary to docs. `core.py:233`, `253`, `331`.

## Low (selected)

- Strict rejects any filing containing a literal U+FFFD, with no override.
- `base_url` accepts invalid ports, whitespace, a trailing `#`; non-str raises `AttributeError`. Bad source types raise regex `TypeError`s. Invalid `quality_policy` is only rejected after fetching and parsing.
- `parse_filing(include_elements=False)` quietly disables the trace and mapping checks.
- Span parsing: `rowspan="2.0"` read as 20, `colspan="0"` drops a column, spans uncapped (CPU/memory).
- No Markdown escaping: "# of shares" becomes an H1; `&lt;img onerror…&gt;` comes out as raw HTML; `|` in hrefs breaks tables.
- XLSX: control characters in an href make `wb.save` fail the whole export; only the first link per cell kept; `javascript:`/`file:` links written live; 250-char destination names fail after full render (+15-char staging name); title fallback uses the first body label ("Revenue").
- `visualize.py` builds `file://C:\…` URIs incorrectly and leaves a full filing copy in `%TEMP%` per call.
- `get_section` string forms "Item 1A.", "ITEM1A", double spaces return `None`; `filing_type="10-K/A"` silently disables validation.
- Overload types use `bool` instead of `Literal[True/False]`; no `py.typed`.

## Release, environment and repo hygiene

- **Version doesn't identify code.** `0.1.22+rcq.2` covers both the reviewed rcq.2 state and +1,189 lines of XLSX/parser changes since, with no CHANGELOG entry. README tells consumers to pin by this version.
- **Local test runs can test the wrong tree.** This machine's global Python has an editable install pointing at `.worktrees/retained-bytes-base-url` (commit `c6fe201`, pre-XLSX), and pytest has no `pythonpath` setting. 78 core tests pass against the old tree. A stale, gitignored `src/sec2md.egg-info` (no `xlsx` extra) feeds wrong metadata to the metadata tests when `PYTHONPATH=src`. Fix: `pythonpath = ["src"]` in `[tool.pytest.ini_options]` plus a conftest guard on `sec2md.__file__`.
- **Diagnostic outputs committed to main.** `305906c` adds `outputs/rddt-export-diagnosis/` (a 287 KB probe workbook, a 1,722-line JSON with absolute `E:\RCQWealth\…` and `C:\Users\einstein\…` paths) and is pushed to `origin/main`. Its `pytest-tmp/` directory is unreadable, so `git status` warns on every run.
- **Design spec is stale** after PR #2 (still says implementation "has not started"; requires per-table fallback, all tables, review columns, frozen `B1`).
- Install docs (`pip install sec2md`), `mkdocs.yml` repo links and CONTRIBUTING point at upstream, which lacks `quality_policy`, `base_url` and XLSX. `requirements.txt` lacks pydantic and openpyxl.
- CI: no Python 3.11 job despite the classifier; dependency lower bounds never tested; integration/golden tests never run (the cache file isn't committed, and golden files are FY2024 while the fixture is FY2023). Running the documented `generate_golden.py` makes `test_sec_accuracy.py:117` fail. Two tests depend on cwd.
- `license = {text=…}` plus license classifiers trigger setuptools' overdue-deprecation warning; `setuptools>=61.0` is unbounded and every install of this fork builds from source.

## Test blind spots to close first

1. **Source→output numeric completeness** per table (multiset of source numbers must appear in that table's Markdown and XLSX grid). This would have caught #1, #2, #8, #9 and #15. Add the same check to the strict gate.
2. `chunk_section` on sections that share a page: chunk text, `element_ids` and tags must stay inside the section.
3. XLSX: "except … percentage" unit lines, `vertical-align:super` markers (including inside `ix:nonFraction`), the AAPL-26 sub-header shape, data tables before the TOC, and an ACL-denied destination that must fail fast.
4. Section extraction variants: 10-Q `PART I—`/`PART I:`, split ITEM headings, single-page and TOC-back-link 8-Ks, "Item 7 of…" cross-references, and section **content** checks (the accuracy suite compares only section keys; the golden suite always skips).
5. Overlap contiguity, separator column count and idempotent minification, and continuation-part headers for split tables.
6. `ParseQualityError` pickle round-trip; `fetch()` deadline, size, content-type and redirect handling against a local server; `<ol>` under strict.
7. A conftest guard that the imported `sec2md` is this checkout's `src`.

## Reproductions

Scripts live in this session's scratch directory (temporary, not in the repo):
`C:\Users\einstein\AppData\Local\Temp\claude\C--Users-einstein-kelab5am-sec2md\663da41d-2d89-4b2e-8ca7-661f78a35c68\scratchpad\`
- `audit-parsing/t1.py`–`t52.py` (e.g. `t21.py` minimal dropped-value table, `t18`/`t19` fixture losses)
- `audit-sections/` (`repro_section_elements.py`, `repro_overlap.py`, `repro_8k*.py`, `repro_synth*.py`)
- `audit-xlsx/` (`p14_rerun.py` percent and sub-header cases, `p10_tmpmax.py` publish hang)
- `audit-api/t01`–`t09` (`t04_quality.py` gate gaps, `t03_network.py` fetch/SSRF, `t05_pool.py` pickling)
- `verify_*.py` — the re-runs marked **Verified** above

Run from the repo root with the scratch venv and `PYTHONPATH=src` (the global Python imports a different worktree).
