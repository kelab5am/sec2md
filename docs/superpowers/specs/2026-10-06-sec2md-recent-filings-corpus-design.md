# sec2md Recent Filings Corpus Design

Date: 2026-10-06 (revision 1)

Status: Approved in brainstorming by the user (2026-10-06); written for review.

## Purpose

The Phase A corpus (109 documents) holds one 2025–26 filing per EDGAR issuer, plus the RCQ set and the fixtures. Filings older than about five years matter little to the user; filings from the last five years do. This corpus adds every annual report those issuers filed in the last five years, so that:

1. any new strict failure that the table merge and header rules branch (`feat/table-merge-header`, PR head `1252c45`) causes on real recent filings is found;
2. the prevalence of the five named limitations (spec `2026-10-05-sec2md-table-merge-header-rules-design.md`, revision 17) is measured, to set the priorities of the strict-failure limitations work that follows;
3. the table merge acceptance comparison is repeated on older layouts of the same issuers.

This corpus comes first. The strict-failure limitations work gets its own spec afterwards and uses this corpus as part of its acceptance set.

## Decisions taken in brainstorming (user, 2026-10-06)

| Question | Decision |
|---|---|
| Order | The corpus comes before the strict-failure limitations work. |
| Issuers | The 18 EDGAR issuers the user chose on 2026-10-03. The RCQ set (META, RDDT, NVDA in `E:\RCQWealth`) stays as it is in Phase A. |
| Depth | Annual reports only, one per fiscal year, filed in the last five years. |
| First run | Strict on `main` against the branch; limitation prevalence; the full acceptance comparison. Accuracy-style recall is not part of it. |
| Fetch | The controller runs the fetch after the user approves the exact filing list and gives the User-Agent text. |
| Layout | A new corpus folder next to Phase A. The Phase A record stays reproducible. |

## Scope

- **In:** the filing selection, a two-stage fetch, a corpus loader, a `--corpus` switch in the table merge acceptance tooling, a strict comparison script, five limitation detectors, the first run and its report.
- **Out:**
  - product code changes;
  - 10-Qs, 8-Ks and exhibits;
  - new issuers;
  - hand-checked expectations for the new filings;
  - accuracy-style recall.
  - The accuracy harness fixes from the 2026-10-06 numeric-recall audit are a separate task.

## Selection

- **Issuers:** JPM, KO, MSFT, TSLA, CAT, BAC, UNH, MU, NTRA, NFLX, CRM, CRDO, TSM, BABA, NVO, AMZN, GOOGL and SPCX, with the CIKs and name checks in Phase A's `fetch_edgar.py`.
- **Forms:** `10-K`, or `20-F` for TSM, BABA and NVO.
  - Phase A used 10-Qs for AMZN, GOOGL and SPCX. Here they contribute their 10-Ks.
- **Window:** filing date from 2021-10-07 to 2026-10-06, inclusive.
- **One per fiscal year:** filings are grouped by the report date (`reportDate`, the period of report).
  - In each group the original filing is taken, not an amendment (`10-K/A`, `20-F/A`).
  - An amendment is taken only when no original exists in the window for that period, and the manifest marks it.
- **Primary document only:** the filing's `primaryDocument`, as Phase A does.
- **De-duplication:** a filing whose accession number is already in the Phase A EDGAR manifest, or among the Phase A fixtures, is left out and listed under `excluded` with the reason `phase_a_duplicate`.
- **Expected size:**
  - about 70 documents: 18 issuers × about 5 fiscal years, less the Phase A duplicates;
  - SPCX has no annual report;
  - CRDO's first 10-K is for fiscal 2022.
  - The listing stage gives the exact number. A count far from 70 is reported, not explained away.

## Fetch

Two stages, each a separate run of `fetch_recent.py`. It reuses Phase A's EDGAR access code: the session with a User-Agent, a pause of 0.25 s per request (under SEC's 10 a second), the submissions JSON and the older-filings pages.

1. **List.** Index requests only: `data.sec.gov/submissions/CIK….json`, and the older-filings pages whose date range overlaps the window.
   - It writes `manifest_draft.json` with one entry per selected filing: company, CIK, form, fiscal year (report date), filing date, accession, URL and size.
     - The size comes from the filing's `index.json` (one index request per filing, under `Archives/edgar/data/<cik>/<accession>/`), which lists each file's size. The document itself is never downloaded to measure it.
   - It also writes the excluded filings with their reasons: amendment, duplicate of Phase A, outside the window.
   - The user reviews the list and its total size before any document is downloaded.
2. **Download.** After the user approves the list, each document is downloaded once into `outputs/recent-filings-corpus/` (gitignored), named `<TICKER>-<FORM>-<filing date>.htm`.
   - Its SHA-256 and byte count are written to `manifest.json`, which is committed.
   - A document already in the cache with the manifest's SHA-256 is not fetched again.
   - Any HTTP error stops the run, with the URL.

The User-Agent comes from the user at run time and is never written into a file. Nothing is written into `E:\RCQWealth`.

## Loader

`corpus_recent.py` exposes `documents(cache) -> (list[(id, group, raw bytes)], skipped)`, with the same shape as Phase A's `corpus_phase_a.documents()`.
- Ids are `recent:<file name>` and the group is `recent`.
- Each file's SHA-256 is checked against `manifest.json`. A mismatch or a missing file is an error, not a skip.

## Acceptance tooling switch

The table merge acceptance tooling (`docs/superpowers/audits/2026-10-06-table-merge-header-acceptance/`) loads documents through `acc_common.load_documents()`.
- It gains a `--corpus {phase-a,recent}` option, which defaults to `phase-a`.
- With `phase-a` every script behaves byte for byte as today; a rerun of its round-5 comparison on the 109 documents must still match.
- With `recent` the documents come from `corpus_recent.documents()`.
- `acc_common.verify_hashes()` is tied to Phase A today: it checks each document against Phase A's `results.json` and `edgar_manifest.json`, and requires exactly 109 and 18. Under `recent` it checks each document against the recent `manifest.json` instead, and requires the manifest's own count. `run_check.json` records which corpus ran.
- Scripts tied to Phase A content keep `phase-a` only and say so when given `recent`:
  - the known shifted tables;
  - the review sample;
  - class 8's table list;
  - the overhead fixtures.

## The first run

Both sides use the worktree venv. `main` is a `git archive c674828` tree, the source of `main` today. The branch is `feat/table-merge-header` at `1252c45`. Both rendering modes are used, with checks on.

1. **Strict comparison** (`strict_compare.py`).
   - Each document is converted under the default `strict` policy, on both sides and in both modes.
   - The record per document and mode: pass, or the `ParseQualityError` message; the branch's `header_accounting_misses`; and the trace failures without element ids.
   - **A new strict failure** is a document and mode that passes on `main` and fails on the branch, or fails on both with a different multiset of failures.
   - Each new failure is classified by cause:
     - a header-accounting miss (wrapped table);
     - a zero-width number;
     - a header excess from a table inside a header row;
     - other.
     
     "Other" is investigated and described in the report.
2. **Limitation prevalence** (`prevalence.py`). Each detector runs on the source HTML and reports documents, tables and occurrences. Where it can, it also reports whether the branch's output shows the effect:

   | Detector | Source condition | Effect on the branch |
   |---|---|---|
   | Wrapped table | A `<table>` with a header zone inside `<li>`, `<b>`, `<strong>`, `<i>`, `<em>`, or an inline element styled bold or italic | A `missing` header-accounting miss on its element |
   | Zero-width number | U+200B, U+200C, U+200D, U+2060 or U+FEFF between two digits, or between a digit and `,`, `.`, `(` or `)`, in a table cell | Strict reports the joined token |
   | Table inside a header row | A `<table>` that is a child of a `<tr>`, directly or through non-cell elements, in a table's header zone | A strict `header:` excess |
   | Sub-label currency codes | A body column other than R0's label column holding two or more distinct currency codes from the closed list, each directly before an amount (widened during the run: a column next to the label missed TSM-2023 table 278) | The codes joined to the amounts |
   | Page-top PART table | A one-row table whose first cell is a PART label and which has other non-empty cells, at the top of a page | The PART line is not stripped, and the sections differ from `main` |

3. **Acceptance comparison.** The table merge tooling runs with `--corpus recent`: `run_side.py` on both sides, `merges_main.py`, `analyze_candidate.py`, `report.py`, `xlsx_detail.py`.
   - With no round-5 expectations, it reports the figures for check 1, other findings, sections, XLSX, modes, alignment, assignment, header retention, class 8 split cells, R0's named limitations and moved rows.
   - Hard verdicts, each listed in full if it fails:
     - 0 alignment identities lost against `main`;
     - XLSX prepared tables identical apart from `display_page`, with each `display_page` change listed;
     - section changes listed one by one.

## Record

`docs/superpowers/audits/2026-10-06-recent-filings-corpus/` holds:
- `README.md`, with the files and how to run them;
- `fetch_recent.py`, `corpus_recent.py`, `strict_compare.py`, `prevalence.py` and `test_tooling.py`;
- `manifest.json`;
- `strict.json`, `prevalence.json` and the acceptance results under `acceptance/`;
- `REPORT.md`, with:
  - the corpus: counts per issuer and year, exclusions;
  - each new strict failure with its cause and the smallest source excerpt;
  - the prevalence table;
  - the acceptance figures and verdicts;
  - a recommended order for the strict-failure limitations work.

Commits go to `main` in the main checkout only after the user agrees, as for every design document.

## Testing

The tooling is audit code, not product code; `test_tooling.py` runs offline with `pytest <folder>/test_tooling.py`.
- **Selection.** Recorded submissions JSON, trimmed to a few issuers, pins:
  - one filing per report date;
  - original over amendment;
  - an amendment kept when it is the only one, and marked;
  - the window edges;
  - de-duplication against a Phase A accession;
  - the older-filings pages read only when their date range overlaps the window.
- **Loader.** A SHA-256 mismatch and a missing file each raise.
- **Detectors.** Each gets a positive and a negative synthetic case. The wrapped-table, zero-width and table-in-header-row detectors are checked against the branch's own limitation tests' inputs. The sub-label detector is checked against the `Forward contracts` case of spec revision 17.
- **Acceptance switch.** `--corpus phase-a` reproduces the Task 11 `final/` results on the 109 documents: the same files, apart from timings.

## Acceptance criteria

1. The listing stage's manifest draft covers every issuer and fiscal year in the window, or gives a reason for each gap. The user approves it before any download.
2. Every approved document is in the cache, with its SHA-256 recorded and checked by the loader.
3. `test_tooling.py` passes, and `--corpus phase-a` still reproduces Task 11.
4. `REPORT.md` holds the three parts of the first run. Every new strict failure is listed and classified, with none left as unexplained "other". The prevalence counts and the acceptance figures are complete.
5. No product code changed. No file was written outside the new folder, the acceptance folder's `--corpus` change and `outputs/recent-filings-corpus/`.

## Risks

- **Size.** JPM and BAC 10-Ks run to about 13 MB each, and the whole corpus to about 350 MB. A side run on about 70 large 10-Ks takes several minutes. The acceptance tooling already runs with 7–10 workers.
- **EDGAR access.** Banks file so often that their 10-Ks fall out of the recent-filings list, which is why Phase A reads the older-filings pages. A filing that cannot be found is reported as a gap, not substituted.
- **Fiscal years.** BABA's fiscal year ends in March and NVO's in December, so the report-date grouping, not the filing year, defines a fiscal year.
