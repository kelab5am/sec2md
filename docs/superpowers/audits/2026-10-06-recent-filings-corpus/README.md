# Recent filings corpus

This folder holds the tooling and the record of the recent filings corpus: every annual report (10-K, or 20-F
for TSM, BABA and NVO) that the 18 Phase A EDGAR issuers filed from 2021-10-07 to 2026-10-06, less the filings
Phase A already holds. On it, `main` and the table merge branch are compared three ways: strict, the prevalence of
the five named limitations, and the table merge acceptance comparison. [`REPORT.md`](REPORT.md) holds the results.

- **Spec:** [`../../specs/2026-10-06-sec2md-recent-filings-corpus-design.md`](../../specs/2026-10-06-sec2md-recent-filings-corpus-design.md)
- **Plan:** [`../../plans/2026-10-06-sec2md-recent-filings-corpus.md`](../../plans/2026-10-06-sec2md-recent-filings-corpus.md)
- **Phase A corpus:** [`../2026-10-03-table-completeness-corpus/`](../2026-10-03-table-completeness-corpus/)
- **Acceptance tooling:** [`../2026-10-06-table-merge-header-acceptance/`](../2026-10-06-table-merge-header-acceptance/) (its `--corpus` switch)

## Files

| File | What it is |
|---|---|
| `fetch_recent.py` | Two stages. `list` makes index requests only (each issuer's submissions JSON, the older-filings pages that overlap the window, and each selected filing's `index.json` for the document's size) and writes the manifest draft. `download` fetches each document of an approved draft once into the cache and writes `manifest.json`. The issuers, CIKs and name checks are imported from Phase A's `fetch_edgar.py`. |
| `corpus_recent.py` | The loader: `documents(cache) -> (list[(id, "recent", raw bytes)], skipped)`, the shape of Phase A's `corpus_phase_a.documents()`. Ids are `recent:<file>`. A missing file or a SHA-256 that differs from `manifest.json` raises; a cache file the manifest does not list goes to `skipped`. |
| `strict_compare.py` | Strict on `main` and on the branch, per document and mode (normal and capture), each side in its own subprocess with its own `PYTHONPATH`. Classifies every new failure. Writes `strict.json`. |
| `prevalence.py` | The five limitation detectors on the source HTML, with each occurrence's effect on the branch, on the recent corpus and (with `--phase-a`) on Phase A's 109 documents. Writes `prevalence.json`. |
| `test_tooling.py` | Offline tests for selection, the list and download stages, the loader, and the acceptance tooling's `--corpus` switch (68 tests). |
| `test_strict_compare.py` | Tests for `strict_compare.py`: classification, the evidence helpers, and one end-to-end run (21 tests). |
| `test_prevalence.py` | Tests for `prevalence.py`: a positive and a negative case per detector, copied from the branch's own limitation tests, plus the review cases (30 tests). |
| [`manifest_draft.json`](manifest_draft.json) | The listing stage's draft, which the user approved on 2026-10-06: 70 documents with their `index.json` sizes, 82 exclusions with reasons, and totals. |
| [`manifest.json`](manifest.json) | The draft after the download: each document's file name, served byte count and SHA-256, the 70 size differences from `index.json`, and the totals. The loader checks every document against it. |
| [`strict.json`](strict.json) | The strict comparison: per document and mode, both sides' results, the transition, and the new, pre-existing and fixed failures. |
| [`prevalence.json`](prevalence.json) | The prevalence run on both corpora: per detector the documents, tables, occurrences and `affected`, each occurrence, and the near-miss and branch counters. |
| `acceptance/` | The acceptance comparison under `--corpus recent`: the 17 files `report.py` writes (`summary.json`, `run_check.json`, `check1.json`, `findings.json`, `strict.json`, `sections.json`, `xlsx.json`, `modes.json`, `alignment.json`, `alignment_losses.json`, `alignment_values.tsv.gz`, `assignment.json`, `retention.json`, `class8.json`, `limitations.json`, `moved_rows.json`, `header_departures.json`) and `xlsx_detail.json`. |
| [`REPORT.md`](REPORT.md) | The record: the corpus, the strict comparison, the prevalence table, the acceptance figures and verdicts, and the recommended order for the strict-failure limitations work. |

The documents themselves are in the main checkout's `outputs/recent-filings-corpus/` (gitignored), named
`<TICKER>-<FORM>-<filing date>.htm`.

## Running

Use the prototype worktree's venv for everything (never pip-install), with `PYTHONIOENCODING=utf-8`, and
`PYTHONDONTWRITEBYTECODE=1` so no `__pycache__` lands in this folder or in Phase A's.

- `<F>` is this folder, `<cache>` the main checkout's `outputs/recent-filings-corpus`.
- `<wt>` is the branch worktree `.worktrees/tmh-proto` (`feat/table-merge-header` at `1252c45`).
- `<main>` is a `git archive c674828` tree, the `main` side: `git -C <main checkout> archive c674828 | tar -x -C <main>`.
- `<s>` is a scratch folder for raw dumps.
- `PY=<wt>/venv/Scripts/python`

### Fetch (network: sec.gov only, 0.25 s between requests)

```bash
$PY <F>/fetch_recent.py list --user-agent "<name> <email>" --out <F>/manifest_draft.json
# The user reviews and approves the draft before anything is downloaded.
$PY <F>/fetch_recent.py download --user-agent "<name> <email>" --draft <F>/manifest_draft.json --cache <cache> --manifest <F>/manifest.json
```

- **The User-Agent is never stored.** It is given on the command line only, placed in the session's headers, and
  written to no file: not the draft, the manifest, the logs or this record. The user gave it on 2026-10-06.
- Any HTTP error stops either stage with its URL, and no draft or manifest is written. Redirects are refused in
  `download`. Nothing may be written inside `E:\RCQWealth`; both stages refuse such paths.
- `download` skips a cached file whose SHA-256 equals the one the existing manifest records for the same file and
  accession, so a rerun on the present cache makes no request.
- **A re-check of the listing** writes to another file and is compared with the approved draft, for example
  `--out <s>/manifest_relist.json`. Never overwrite the approved draft.

### Served bytes (Ruling 1)

- Every document was stored as sec.gov served it on 2026-10-06. Each served file holds one `<script>` tag that the
  SEC's web front end injects before `</body>`, so it is 108 bytes larger than the size `index.json` gives. All 70
  differ by exactly +108 bytes; with the tag removed, every file is `index.json`'s size. Phase A's files carry the
  same kind of tag, with a different `src`, and were stored the same way.
- The SHA-256s in `manifest.json` cover these served bytes. The tag's `src` changed between 2026-10-03 and
  2026-10-06, so **a re-download into an empty cache may give different bytes**, and the loader will then refuse
  them as SHA-256 mismatches. The present cache is stable and checks exactly.
- `download` does not warn when it re-fetches a file whose bytes differ: it records the new SHA-256 in the manifest
  it writes. To re-fetch, write to a scratch manifest (`--manifest <s>/manifest.json`) and compare it with this
  folder's before replacing anything.
- sec2md drops `<script>` content, so the tag does not change any result.

### Loader

```bash
$PY -c "import sys; sys.path.insert(0, '<F>'); import corpus_recent; docs, skipped = corpus_recent.documents('<cache>'); print(len(docs), skipped)"
# 70 []
```

### Strict comparison

```bash
$PY <F>/strict_compare.py --main-src <main>/src --branch-src <wt>/src --recent-cache <cache> --out <F>/strict.json --side-dir <s>/sides --workers 6
```

- Each side runs in its own subprocess with `PYTHONPATH` set to its `src`; `sec2md.__file__` is checked in the side
  process and in every worker. `strict.json` records `main` as a path, not a commit (`git_head` is null for the
  archive tree): the `main` side is `git archive c674828`.
- `--no-images` renders as `run_side.py` does (`get_pages(include_images=False)`); the default follows
  `convert_to_markdown`. Both give the same results on this corpus.
- The side dumps in `--side-dir` hold every failure's evidence (output and source excerpts).

### Limitation prevalence

```bash
$PY <F>/prevalence.py --branch-src <wt>/src --recent-cache <cache> --phase-a --fixtures-root <main> --edgar-cache <main checkout>/outputs/table-completeness-corpus --out <F>/prevalence.json --workers 8
```

`--phase-a` adds Phase A's 109 documents, loaded as the acceptance tooling loads them (`--fixtures-root` is a
`git archive c674828` tree; the hash check is against Phase A's `results.json`).

### Acceptance comparison (`--corpus recent`)

These are the acceptance tooling's Task 11 commands with the Phase A inputs replaced by
`--corpus recent --recent-cache <cache>`. `ACC` is `../2026-10-06-table-merge-header-acceptance`.

```bash
PYTHONPATH=<main>/src $PY ACC/run_side.py --side main --expect-src <main>/src --corpus recent --recent-cache <cache> --out-dir <s>/side-main --workers 7
PYTHONPATH=<wt>/src $PY ACC/run_side.py --side candidate --expect-src <wt>/src --corpus recent --recent-cache <cache> --out-dir <s>/side-candidate --workers 7
PYTHONPATH=<main>/src $PY ACC/merges_main.py --expect-src <main>/src --corpus recent --recent-cache <cache> --out <s>/merges.json.gz --workers 10
PYTHONPATH=<wt>/src $PY ACC/analyze_candidate.py --expect-src <wt>/src --corpus recent --recent-cache <cache> --main-dir <s>/side-main --candidate-dir <s>/side-candidate --merges <s>/merges.json.gz --out-dir <s>/analysis --workers 10
$PY ACC/report.py --corpus recent --main-dir <s>/side-main --candidate-dir <s>/side-candidate --analysis-dir <s>/analysis --merges <s>/merges.json.gz --out-dir <F>/acceptance
PYTHONPATH=<main>/src $PY ACC/xlsx_detail.py dump --corpus recent --recent-cache <cache> --out <s>/xd_main.json <ids>
PYTHONPATH=<wt>/src $PY ACC/xlsx_detail.py dump --corpus recent --recent-cache <cache> --out <s>/xd_cand.json <ids>
$PY ACC/xlsx_detail.py compare <s>/xd_main.json <s>/xd_cand.json --out <F>/acceptance/xlsx_detail.json
```

- `<ids>` is all 70 documents as `recent:<file>`, from `manifest.json`. `xlsx_detail.py dump` skips an id it does
  not find without an error, so check that both dumps hold 70 documents.
- `shifted_tables.py`, `review_sample.py` and `overhead.py` hold Phase A content and refuse `--corpus recent`.
- Measured wall times on this corpus: `run_side.py` about 150–165 s per side, `merges_main.py` 53 s,
  `analyze_candidate.py` 70 s, `report.py` 3 s, each `xlsx_detail.py dump` about 9.5 minutes. The raw dumps total
  about 580 MB and stay in the scratch folder.

## Tests

From the main checkout root:

```bash
PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 $PY -m pytest -p no:cacheprovider --basetemp <s>/pytest-tmp <F>/test_tooling.py <F>/test_strict_compare.py <F>/test_prevalence.py
$PY -m ruff check <F>
```

- The three files run in one session: 119 tests (68 + 21 + 30). They are separate files because Tasks 3, 4 and 5
  ran in parallel (Ruling 2).
- **`--basetemp` and `-p no:cacheprovider` are for this machine only.** Without `--basetemp`, every test passes
  but pytest's own clean-up raises `PermissionError: [WinError 5]` on a stale
  `%TEMP%\pytest-of-einstein\pytest-current` link and the run exits 1. Without `-p no:cacheprovider`, pytest warns
  that it cannot write `.pytest_cache`.
- `test_prevalence.py` runs the detectors on the branch's sec2md: the worktree's `src`, or the folder in the
  `TMH_SRC` environment variable. It skips itself when that folder has no `sec2md`. It raises `ImportError` if
  `sec2md` was already imported from somewhere else in the same session, which would mean testing the wrong code;
  run it on its own if that happens. With the three files above it does not.
- The end-to-end test in `test_strict_compare.py` needs the worktree and `git archive c674828`; it skips itself
  when either is unavailable.
- Every test is offline. The list and download stages are tested with fake sessions.
- Never run the repository's 14 EDGAR `integration` tests from here.
