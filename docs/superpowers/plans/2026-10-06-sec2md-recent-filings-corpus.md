# sec2md Recent Filings Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the 18 issuers' annual reports from the last five years as a second corpus, and run strict, limitation prevalence and the table merge acceptance comparison on it, `main` against `feat/table-merge-header`.

**Architecture:** Audit tooling in a new folder next to Phase A, with no product code. `fetch_recent.py` lists the filings (index requests only) and, after the user approves the list, downloads them. `corpus_recent.py` loads them with the same interface as Phase A's loader. The table merge acceptance tooling gains a `--corpus` switch. `strict_compare.py` and `prevalence.py` produce the run's new results, and `REPORT.md` records them.

**Tech Stack:** Python 3.12 (the `tmh-proto` worktree venv), `requests` (already used by Phase A's fetcher), BeautifulSoup with lxml, and pytest.

**Spec:** [`../specs/2026-10-06-sec2md-recent-filings-corpus-design.md`](../specs/2026-10-06-sec2md-recent-filings-corpus-design.md) (revision 1)

## Global Constraints

- **No product code changes.** Nothing under any worktree's `src/` or `tests/` changes.
- **Folders.** Code and records go only in:
  - `docs/superpowers/audits/2026-10-06-recent-filings-corpus/` (F below);
  - the `--corpus` change in `docs/superpowers/audits/2026-10-06-table-merge-header-acceptance/` (ACC below).
  
  Documents go in the gitignored `outputs/recent-filings-corpus/` (CACHE below).
- **Network.** Only `fetch_recent.py` touches the network, and only sec.gov.
  - The User-Agent (a name and an email) comes from the user, who gave it on 2026-10-06. Pass it on the command line; never write it to a file.
  - Pause 0.25 s between requests.
  - The listing stage makes index requests only.
  - **No document is downloaded before the user approves `manifest_draft.json`.**
- **Selection.** The 18 issuers and their CIKs come from Phase A's `fetch_edgar.py`.
  - Forms: `10-K`, or `20-F` for TSM, BABA and NVO.
  - Filed from 2021-10-07 to 2026-10-06, inclusive.
  - One filing per `reportDate`: the original over an amendment, and an amendment only when it is the sole filing.
  - Primary document only.
  - Phase A accessions are de-duplicated.
- **`E:\RCQWealth` is read-only.** Nothing that installs anything. Never run the 14 EDGAR `integration` tests.
- **Sides.** `main` is a `git archive c674828` tree; the branch is `.worktrees/tmh-proto` at `1252c45`. Use the `tmh-proto` venv for both, selecting the side by `PYTHONPATH`.
- **Phase A stays reproducible.** `--corpus phase-a` (the default) must reproduce Task 11's `final/` results apart from timings.
- **Commits.** Commits in the main checkout need the user's agreement. Never push.

## File structure

| File | Responsibility |
|---|---|
| `F/fetch_recent.py` | `select(submissions_blocks, issuer, window, phase_a_accessions) -> (selected, excluded)`, a pure function. `list` stage: index requests → `manifest_draft.json`. `download` stage: approved draft → CACHE plus `manifest.json`. |
| `F/corpus_recent.py` | `documents(cache) -> (list[(id, group, bytes)], skipped)`. Ids are `recent:<file>`. Each SHA-256 is checked against `manifest.json`. |
| `F/strict_compare.py` | Strict on both sides and in both modes, per document. Classifies new failures. Writes `strict.json`. |
| `F/prevalence.py` | The five detectors on the source HTML, and their effect on the branch. Writes `prevalence.json`. |
| `F/test_tooling.py` | Offline tests for selection, the loader and the detectors. |
| `F/README.md`, `F/REPORT.md` | How to run the tooling; the record. |
| `ACC/acc_common.py` and the scripts that call `load_documents` / `verify_hashes` | `--corpus {phase-a,recent}`. Under `recent`, hashes are checked against F's manifest and its own count. |

## Task 1: Selection and the listing stage

**Interfaces:**
- **Produces:**
  - `ISSUERS` (imported from Phase A's `fetch_edgar.py` by path, with the form overridden as above).
  - `select(...)`.
  - The CLI `python F/fetch_recent.py list --user-agent "<ua>" --out F/manifest_draft.json`.
- **The draft:** one entry per selected filing, with ticker, company, CIK, form, `report_date`, `filing_date`, accession, URL, `bytes` (from the filing's `index.json`) and `amendment` (a bool). It also holds `excluded`, each with its reason (`amendment`, `phase_a_duplicate`, `outside_window`, `same_period_newer`), and `totals` (documents and bytes).

**Tests** (`test_tooling.py`, synthetic submissions blocks in the real columnar format):
- one per `reportDate`;
- an original beating its amendment;
- an amendment kept, and marked, when it is the only filing for its period;
- the window edges (filed on 2021-10-06 is excluded, 2021-10-07 included, 2026-10-06 included);
- a Phase A accession excluded;
- an older-filings page read only when its `filingFrom`/`filingTo` overlaps the window;
- a 20-F issuer;
- an issuer with none (SPCX) listed with the reason `no_annual_report`.

- [x] Write the selection tests and see them fail; implement `select`; see them pass.
- [x] Implement the `list` stage, reusing Phase A's session and `get` pattern.
- [x] Run `list` with the user's User-Agent and write `manifest_draft.json`. Report the per-issuer and per-year table and the total size.
  - A count far from about 70, or any issuer-year gap without a reason, is reported, not patched.
- [x] **GATE: the user approves the draft.** Stop here until they do.

## Task 2: Download and loader

**Interfaces:**
- **Consumes:** the approved `manifest_draft.json`.
- **Produces:**
  - `python F/fetch_recent.py download --user-agent "<ua>" --draft F/manifest_draft.json --cache CACHE --manifest F/manifest.json`. It skips files already in the cache with the manifest's hash, and stops on any HTTP error.
  - `corpus_recent.documents(cache)`.

**Tests:** the loader raises on a SHA-256 mismatch and on a missing file, and returns ids in sorted file order.

- [x] Loader tests first, then the loader.
- [x] Implement `download`, then run it.
- [x] Load all documents with `corpus_recent.documents(CACHE)`: the count must equal the manifest's, with no errors.

## Task 3: The acceptance `--corpus` switch

**Interfaces:**
- `acc_common.load_documents(edgar_cache, fixtures_root, corpus="phase-a", recent_cache=None)`.
- `acc_common.verify_hashes(docs, corpus="phase-a")`.
- Each ACC script that loads documents gains `--corpus` and `--recent-cache`.
- Scripts tied to Phase A content refuse `recent` with a clear message: `shifted_tables.py`, `review_sample.py`, `overhead.py`, and the class 8 table list in `report.py`, which is reported as not applicable.
- `run_check.json` records the corpus.

**Tests:** in `F/test_tooling.py`, `verify_hashes` under `recent` accepts a matching synthetic manifest and rejects a mismatch.

- [x] Implement the switch.
- [x] Rerun Task 11's Steps 1–2 with the default (`phase-a`) into scratch. Every result file must equal ACC `final/`'s, apart from timings, paths and the gzip mtime (as in Task 11).

## Task 4: Strict comparison

**Interfaces:** `python F/strict_compare.py --main-src <main>/src --branch-src <wt>/src --recent-cache CACHE --out F/strict.json --workers N`.
- Each side runs in its own subprocess, with its `PYTHONPATH`.
- Per document and mode, on each side: `passed`, the error message, trace failures without element ids, and the branch's `header_accounting_misses`.
- **A new failure** is pass → fail, or fail → fail with a different failure multiset.
- **Cause classes:**
  - `wrapped_table`: a `:missing` header-accounting miss on the failing element;
  - `zero_width_number`;
  - `header_row_table`: a `header:` excess from a `<table>` inside a header-row `<tr>`;
  - `other`.

**Tests:** classification from synthetic per-document records, one per class.

- [x] Tests first, then the script.
- [x] Run it on the recent corpus. Every `other` is investigated and described in the run notes for Task 7.

## Task 5: Limitation prevalence

**Interfaces:** `python F/prevalence.py --branch-src <wt>/src --recent-cache CACHE [--phase-a] --out F/prevalence.json`. `--phase-a` also runs it on the 109 Phase A documents, for comparison. Per detector, it reports documents, tables and occurrences, plus `affected` on the branch.

| Detector | Source condition | Effect on the branch |
|---|---|---|
| `wrapped_table` | A `<table>` with a header zone inside `<li>`, `<b>`, `<strong>`, `<i>`, `<em>`, or an inline element styled bold or italic | `header_accounting_misses` holds `:missing` for its element |
| `zero_width_number` | U+200B, U+200C, U+200D, U+2060 or U+FEFF between two digits, or between a digit and `,`, `.`, `(` or `)`, inside a table cell | Strict reports the joined token |
| `header_row_table` | A `<table>` whose nearest `<tr>` ancestor is in a table's header zone, with no cell between them | Strict reports a `header:` excess |
| `sub_label_currency` | A body column other than R0's label column holding two or more distinct currency codes from the closed list (letter codes and `US$`, `HK$`, `NT$`, `A$`, `C$`, `S$`), each directly before an amount; widened in review (Ruling 4) | The output joins code and amount |
| `page_top_part_table` | A one-row table whose first cell is a PART label, with other non-empty cells, first on its page | The sections differ from `main` |

**Tests:** for each detector, one positive and one negative synthetic case.
- The positives reuse the branch's limitation-test inputs:
  - `tests/test_parser.py` `TestWrappedTableHeaderLimitation`;
  - `tests/test_table_merge_headers.py`, the zero-width and `<tr>`-direct cases;
  - the sub-label `Forward contracts` rows;
  - `tests/test_section_extractor.py`, the running PART header.
- Copy the inputs. Don't import the branch's tests.

- [x] Tests first, then the detectors.
- [x] Run on the recent corpus and on Phase A.
  - Phase A must give 0 `affected` for every detector, matching the acceptance record.
  - Any other result is reported.

## Task 6: Acceptance comparison on the recent corpus

- [x] Run ACC's `run_side.py` (both sides), `merges_main.py`, `analyze_candidate.py`, `report.py` and `xlsx_detail.py` (dump and compare, every recent document) with `--corpus recent`. Results go to `F/acceptance/`.
- [x] Record the figures and the three hard verdicts:
  - 0 alignment identities lost;
  - XLSX prepared tables identical apart from `display_page`, with each change listed;
  - section changes listed.

## Task 7: Record

- [x] Write `F/README.md`, covering the files and the exact commands.
- [x] Write `F/REPORT.md`:
  - the corpus: per issuer and year, exclusions, total size;
  - the strict comparison, with each new failure, its cause class and the smallest source excerpt;
  - the prevalence table (recent against Phase A);
  - the acceptance figures and verdicts;
  - a recommended order for the strict-failure limitations work.
- [x] Run `pytest F/test_tooling.py` (all pass) and `ruff check F`.
- [ ] Ask the user before committing F, the ACC change, the spec and this plan to `main`.
