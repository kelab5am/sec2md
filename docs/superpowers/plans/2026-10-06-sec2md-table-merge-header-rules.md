# sec2md Table Merge and Header Rules Implementation Plan

> **For agentic workers:** the code for this plan already exists. It was built test-first as a prototype, one commit per task, and is promoted to the implementation branch in Task 0. Execute this plan with superpowers:subagent-driven-development: each task verifies its commit against the spec, applies review changes test-first, and re-runs its checks. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Markdown table renderer keep every source value and put each value under the header its source column carries, and add a report-only header-alignment check.

**Architecture:** Row roles are decided once on the visible source grid (`table_roles`, R0). `TableParser` then merges columns while recording each output column's source-column membership, and builds one fused header line per column from that membership (R1–R7). A `policy` keyword keeps the XLSX path on today's rules (R9). Strict's numeric trace accounts for each table's header line separately (R6a). A new `table_alignment` module re-derives each value's expected header path from the source table and compares it with the emitted Markdown, inside `check_tables`. It reports findings and coverage in two new `ParseDiagnostics` fields.

**Tech Stack:** Python `>=3.10,<3.13`, BeautifulSoup 4 with lxml, pytest, ruff (rules `E4`, `E7`, `E9`, `F`), optional openpyxl for the XLSX tests. No new dependencies.

**Spec:** [`../specs/2026-10-05-sec2md-table-merge-header-rules-design.md`](../specs/2026-10-05-sec2md-table-merge-header-rules-design.md) (revision 17). Its review record is [`../reviews/2026-10-05-sec2md-table-merge-header-rules-review.md`](../reviews/2026-10-05-sec2md-table-merge-header-rules-review.md). Evidence: [`../audits/2026-10-04-table-merge-header-evidence/REPORT.md`](../audits/2026-10-04-table-merge-header-evidence/REPORT.md). Acceptance records of the prototype: [`../audits/2026-10-06-table-merge-header-acceptance/`](../audits/2026-10-06-table-merge-header-acceptance/).

## Global Constraints

- **Markdown only.** `TableParser` under the `EXTENDED` policy and the one-row path in `Parser` change. The XLSX export keeps the `LEGACY` policy: its prepared tables (values, column groups, source coordinates, headers and issues) must stay identical to unchanged `main` on every corpus document.
  - The one XLSX difference, accepted by the user on 2026-10-06, is `display_page`, which the parser guesses from Markdown page text. It changes on 4 pages in 2 documents, and each change is listed (Decisions and open items, item 1).
- **No value is lost and none is invented.** Strict's numeric trace accounts for each table's header line separately (R6a). There are no new strict failures in either rendering mode on the fixtures and the corpus.
  - The user accepted five named limitations during implementation (spec revision 17). Three can make strict fail where `main` passed, on inputs outside the corpus: a number split by a zero-width character, a `<table>` directly inside a header-row `<tr>`, and a table inside `<li>`, `<b>`, `<i>`, `<em>`, `<strong>` or an inline element styled bold or italic, whose header repeats a number. The other two change rendering only: currency codes in a sub-label column, and R8's page-top PART lines and part-only stubs.
- **The alignment check is report-only.** It never raises and never fails strict.
  - `quality_policy="off"` and `Parser(table_checks=False)` skip it.
  - If it fails, its two fields are `()` and the conversion continues, as for checks 1 and 2.
- **Checks 1–3 do not change.** F9, F10 and F11 are documented check-side false positives for Phase B.
- **New dataclass fields are trailing and defaulted:**
  - `ParseDiagnostics.table_header_alignment`;
  - `ParseDiagnostics.table_header_alignment_coverage`;
  - the header-record fields `header_source`, `header_capacity` and `header_cells`.
- **Overhead:** total `Parser.get_pages(include_images=False)` time on the 7 fixtures is at most 1.10 × unchanged `main`'s.
  - Same settings on both sides: normal mode, checks on.
  - Each figure is the median of at least five runs, each in its own process.
- **No new dependencies.** `python -m ruff check src tests` passes.
- **Version:** `0.1.22+rcq.4`, with a CHANGELOG section `0.1.22+rcq.4 (unreleased, pending review)`.
- **`E:\RCQWealth` is read-only.** Never write there.
- **Design documents stay in the main checkout,** under `C:\Users\einstein\kelab5am\sec2md\docs\superpowers\`. The branch commits only `src/`, `tests/`, `README.md`, `docs/usage/`, `CHANGELOG.md` and `pyproject.toml`.
- **Never push or open the PR yourself.** Task 12 hands the user the commands and the PR body.

## How this plan works

The usual plan carries full code. This one does not, by the user's choice on 2026-10-06. The code was built first as a prototype, test-first, with one commit per task. It was then run end to end on the Phase A corpus in five acceptance rounds, and the spec was corrected from what those rounds found (revisions 6–13). Round 5 checked the fixes from reviewing the code against the spec while this plan was drafted (revision 14). Revision 15 applies a read-only Codex review of the spec, and revision 16 records the user's acceptance of the XLSX display-page exception. The prototype branch becomes the implementation branch in Task 0.

Each of Tasks 1–10 describes one existing commit:
- the spec rules it covers;
- its files and interfaces;
- the behaviour its tests pin;
- the exact verification counts;
- the points a reviewer should check against the spec.

**Executing Tasks 1–10.** For each task:
1. Read the task and the spec sections it names.
2. Review the commit against them: `git show <sha>`.
3. Run the task's verification on that commit's tree, with the commands given below. The counts must match exactly.
4. If review finds a defect:
   - write a failing test first, then the fix;
   - fold the fix into the task's commit with `git commit --fixup <sha>` and a non-interactive autosquash (`GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash c674828`);
   - re-run the per-commit suites;
   - record the new SHAs in this plan and the change in the task.
5. Tick the task's boxes.

Task 11 reruns the acceptance on the corpus. Task 12 prepares the release notes and the PR for the user.

**Running a commit's suite.** Run the full suite on a clean tree of that commit, not on a checkout with uncommitted work:

```bash
git -C <worktree> archive <sha> | tar -x -C <scratch>/tree-<sha>
cd <scratch>/tree-<sha>
PYTHONPATH=src <worktree>/venv/Scripts/python -m pytest -q -p no:cacheprovider --basetemp=<scratch>/pt-<sha>
```

**Commits 1–9 are not green on their own.** Fixture pins and accuracy contracts that the rendering change breaks are updated in Task 10, so only commit 10 passes the whole suite. Each task lists its failing tests and the task that fixes them.

Commits 1–9 also show one environment-only failure, `tests/test_models.py::test_internal_version_matches_distribution`. The venv's installed metadata already says `0.1.22+rcq.4`, while those trees still pin rcq.3; it does not fail on a clean install of the same commit. If a reviewer wants every commit green, Task 10's pin and accuracy changes can be split into the commits that cause each failure. That is optional, and the plan does not do it.

## Before you start

- **Worktree and branch.** The implementation lives in the prototype worktree `C:\Users\einstein\kelab5am\sec2md\.worktrees\tmh-proto`. Task 0 renames its branch from `proto/table-merge-header` to `feat/table-merge-header`.
  - Do not move the worktree. Its venv has an editable install that records the worktree's absolute path.
- **Base.** The branch is based on `c674828`. Commits on `main` after it touch only `docs/`.
  - Leave the base as it is, so the acceptance baseline (`c674828`) stays the branch's own base.
  - Rebase onto `main` only if `main`'s `src/` or `tests/` have changed since.
- **Environment.** Use the worktree's venv, `venv/Scripts/python`. Never pip-install into the global Python, whose editable sec2md install must stay pointed at the main checkout.
  - The venv has no setuptools, and a normal `pip install -e .` would download it. After the version bump, refresh the installed metadata offline, from a copy of the base interpreter's setuptools:

    ```bash
    cp -r <Python312>/Lib/site-packages/{setuptools,setuptools-80.3.0.dist-info,_distutils_hack,pkg_resources} <scratch>/buildpath/
    PYTHONPATH=<scratch>/buildpath venv/Scripts/python -m pip install -e . --no-deps --no-build-isolation --no-index
    PYTHONPATH=<scratch>/buildpath venv/Scripts/python -c "from setuptools import setup; setup()" egg_info --egg-base src
    ```

  - The last command matters. The gitignored `src/sec2md.egg-info` shadows the venv's metadata under pytest's `pythonpath = ["src"]`, so `importlib.metadata.version("sec2md")` keeps reporting rcq.3 until it is rewritten.
- **Corpus.** The acceptance tooling is in the main checkout's [`audits/2026-10-06-table-merge-header-acceptance/`](../audits/2026-10-06-table-merge-header-acceptance/).
  - It reads the Phase A corpus as `corpus_phase_a.documents()` loads it.
  - The EDGAR cache is `outputs/table-completeness-corpus` in the main checkout, read only.
  - `E:\RCQWealth` is read only.
  - It needs no network.

## File structure

| File | Responsibility |
|---|---|
| Create `src/sec2md/table_roles.py` | R0: visible text, complete numbers, nil and year-like values, year runs, period and unit text (its own patterns), label and identifier columns, header-like rows, `main`'s sparse-row fusion, data rows and the header zone. Pure functions over an origin grid, shared by the renderer and the checker. |
| Modify `src/sec2md/table_parser.py` | The structural policy (R9). Shared `extract_cell_text`. Grid-hidden rows and cells. The `EXTENDED` careful merge and currency markers (R3, R4). Source grid, output columns with membership, the header guard and veto (R1, R2, R3.5–3.6). The header line (R5–R7). The per-render `TableHeaderRecord`. |
| Modify `src/sec2md/parser.py` | R8's one-row PART branch. Header records bound to table elements from the content-supplying render. `element_header_records()`. Header-accounting misses. Passes `source_url` to the checks. |
| Modify `src/sec2md/quality.py` | R6a in `trace_numeric_failures`: `ElementHeaderRecord`, header-line location, header accounting. The two new `ParseDiagnostics` fields, through `build_diagnostics`. |
| Create `src/sec2md/table_alignment.py` | The header-alignment check: placed source grid, values, emitted paths, the Markdown cell parser, row pairing and value location, matching (exact path, bounded memoized segmentation search), coverage, findings and per-value outcomes. |
| Modify `src/sec2md/table_completeness.py` | Runs the alignment check inside `check_tables`, sharing one placement with check 1, and carries findings and coverage in the report. Checks 1–3 are unchanged. |
| Tests | New `tests/test_table_roles.py`, `tests/test_table_merge_headers.py` and `tests/test_table_alignment.py`. Additions to `test_quality.py`, `test_parser.py`, `test_section_extractor.py`, `test_xlsx_tables.py` and `test_chunker.py`. Updates to `test_table_parser.py`, `test_table_completeness*.py` and `test_models.py`. The accuracy suite gets R6a accounting, the financial-row amendment and the body-row guard, with `body_rows_main.json` and its generator. |
| Release | `CHANGELOG.md`, `README.md`, `docs/usage/direct-conversion.md`, `pyproject.toml`, `src/sec2md/__init__.py` (version). |

## Commits and suite counts

| Task | Prototype commit | Commit (after Task 0) | Full suite on the prototype commit's tree | Commit after review fixes | Full suite after review fixes |
|---|---|---|---|---|---|
| 1 | `6a5f29f` | `b70399f` | 1138 passed, 1 failed (environment only) | `b70399f` | 1138 passed, 1 failed (environment only) |
| 2 | `c249876` | `1b4d300` | 1159 passed, 1 failed (environment only) | `0b24f37` | 1162 passed, 1 failed (environment only) |
| 3 | `d239a9d` | `99c39ad` | 1193 passed, 3 failed | `e3062f3` | 1204 passed, 3 failed |
| 4 | `fa1055e` | `60c3938` | 1216 passed, 19 failed, 1 error | `8346dc5` | 1231 passed, 19 failed, 1 error |
| 5 | `6680c47` | `e399f9c` | 1293 passed, 18 failed, 1 error | `372325a` | 1317 passed, 18 failed, 1 error |
| 6 | `129218b` | `ea6d993` | 1299 passed, 18 failed, 1 error | `78a9e19` | 1327 passed, 18 failed, 1 error |
| 7 | `9041958` | `7d1f85d` | 1418 passed, 17 failed | `1909fd1` | 1466 passed, 17 failed |
| 8 | `8a26ae4` | `72a8392` | 1461 passed, 17 failed | `2792ccf` | 1509 passed, 17 failed |
| 9 | `ac2b1f0` | `ea6e923` | 1540 passed, 17 failed | `14ddc63` | 1588 passed, 17 failed |
| 10 | `b229b8d` | `b43944e` | **1611 passed, 14 deselected**; ruff clean | `1252c45` | **1660 passed, 14 deselected**; ruff clean |

Every count was verified exactly on the prototype commits before any review fix. Review fixes (2026-10-06) raised the passing counts and left every commit's failing test ids unchanged. They also changed code: R4's label-column rule (Tasks 3-4), R6's once-per-column rule and the header record's node counting (Task 5), the regenerated body-row baseline and release text (Task 10). Each task's "Review changes" note lists them.

The baseline at `c674828` is 798 passed, 14 deselected. The 14 deselected tests are the EDGAR `integration` tests. Do not run them, because they download from sec.gov.

## Task 0: Promote the prototype branch

- [x] **Step 1: Confirm the preconditions.**
  - The user and Astra have approved this plan.
  - The spec (revision 16) and this plan are committed on `main`.
  - `git -C .worktrees/tmh-proto status` is clean at `b229b8d`.
- [x] **Step 2: Rename the branch.**

  ```bash
  git -C .worktrees/tmh-proto branch -m proto/table-merge-header feat/table-merge-header
  ```

- [x] **Step 3: Reword the commit subjects.** Map each `proto TN:` subject to its final subject, keeping each message body and its `Co-Authored-By` line:

  | Prototype subject | Final subject |
  |---|---|
  | `proto T1: row roles (R0) in table_roles` | `feat: decide table row roles on visible content before merging (R0)` |
  | `proto T2: structural policy (R9) and zero-width cell text` | `feat: add a structural policy so XLSX keeps today's merge rules (R9)` |
  | `proto T3: EXTENDED careful-merge rules and currency markers` | `feat: extend the careful marker merge and currency markers for Markdown (R3, R4)` |
  | `proto T4: source grid, membership, R1, R2 and the header veto` | `feat: track source membership and keep every cell when merging columns (R1, R2)` |
  | `proto T5: header line (R5-R7) and the per-render header record` | `feat: build one fused header line per column from membership (R5-R7)` |
  | `proto T6: keep every cell of a one-row PART table (R8)` | `fix: keep every cell of a one-row PART table (R8)` |
  | `proto T7: header accounting in strict's numeric trace (R6a)` | `feat: account for each table's header line in strict's numeric trace (R6a)` |
  | `proto T8: header-alignment source side and Markdown cell parser` | `feat: add the header-alignment check's source side and Markdown cell parser` |
  | `proto T9: header-alignment matching, coverage and diagnostics` | `feat: report header-alignment findings and coverage in diagnostics` |
  | `proto T10: regressions, accuracy guards, chunking tests and release notes` | `test: update regression pins and accuracy guards; add chunking tests and release notes` |

  Save the mapping as `<scratch>/reword.py`, which amends the current commit's subject. Fill `MAP` with all ten rows of the table, keyed by the `proto TN:` prefix:

  ```python
  import subprocess, sys
  MAP = {"proto T1:": "feat: decide table row roles on visible content before merging (R0)"}  # all ten rows
  message = subprocess.run(["git", "log", "-1", "--format=%B"], capture_output=True, text=True, check=True).stdout
  subject, _, body = message.partition("\n")
  key = next((k for k in MAP if subject.startswith(k + " ")), None)
  if key is None:
      sys.exit(f"unmapped subject: {subject}")
  subprocess.run(["git", "commit", "--amend", "-q", "-m", MAP[key] + "\n" + body], check=True)
  ```

  Run it on every commit:

  ```bash
  git -C .worktrees/tmh-proto rebase c674828 --exec "venv/Scripts/python <scratch>/reword.py"
  ```

- [x] **Step 4: Check that nothing but the subjects changed.**
  - `git diff b229b8d HEAD` is empty.
  - `git log --format=%s c674828..HEAD` lists the ten final subjects in order.
  - The full suite at HEAD gives 1611 passed, 14 deselected.
  - Record the new SHAs in the commit table above.

Spec line numbers in Tasks 1–10 refer to revision 14, as committed in `92da51b`. Revision 15 adds a table near the top, which shifts later lines; open `git show 92da51b:docs/superpowers/specs/2026-10-05-sec2md-table-merge-header-rules-design.md` to follow them. Every count was rerun on a `git archive` tree of each commit with the worktree venv, the ten full suites one at a time. The full suite's "3 warnings" are the existing `XMLParsedAsHTMLWarning`s. The version-test failure on Tasks 1–9 is environment-only.

## Task 1: Row roles (R0) in `table_roles` (commit `6a5f29f`, prototype `proto T1`)

**Spec:** Definitions (Visible cell text, Origin text, Label column, Identifier column, Complete number with revision 14's one currency marker, thousands in groups of three and one `%`, footnoted values, ranges and year-like values, Bare year, Nil value, Period text and unit text, Year run, Explicit header row, Data row with its three further rules and the named limitation, Header zone with header-like rows, label-only rows, `main`'s sparse-row fusion without marker-only columns (revision 13) and trailing label-only rows, "R0 is a rule on visible content", Row role, Currency markers); R0; Testing, "Row roles"; interpretation round 2, "R0's unit captions".

**Files:**
- Create: `src/sec2md/table_roles.py` — R0, shared by the renderer and the checker: visible text, the closed currency list, the number, year and nil predicates, split-negative rebuild, R0's caption patterns, year runs, header-like and label-only rows, the sparse-row fusion and `row_roles`.
- Test: `tests/test_table_roles.py` — new, 341 tests (module-level functions, no classes; expected roles written out literally).

**Interfaces:**
- Consumes: `sec2md.quality._MARKDOWN_LINK_RE`; `table_completeness._PERIOD_TEXT` and `xlsx_tables._UNIT_LINE`, imported lazily inside `_caption_patterns()` (lru_cache) because both modules import `table_parser`, which imports this module.
- Produces:
  - `@dataclass(frozen=True) class OriginCell: text: str; header: bool = False` (a th cell when `header`).
  - `OriginSlot = Union[str, OriginCell, None]` (a plain `str` is a td cell's text, `None` a span-covered slot); `OriginGrid = Sequence[Sequence[OriginSlot]]`; `RowRole = Literal["header", "body", "empty"]`.
  - `ZERO_WIDTH_CHARACTERS = "\u200b\u200c\u200d\u2060\ufeff"`; `CURRENCY_MARKERS: frozenset[str]` (27: `$ € £ ¥ US$ NT$ HK$ A$ C$ S$` and 17 ISO codes); `CURRENCY_PATTERN: str` (regex alternation, longest marker first).
  - `_FOOTNOTED: re.Pattern` (groups `number`, `marks`): private, imported by `table_alignment` (Task 8).
  - `visible_text(text: str | None) -> str`; `is_period_text(text) -> bool`; `is_unit_text(text) -> bool`; `is_currency_marker(text) -> bool`; `is_bare_year(text) -> bool`; `is_nil_value(text) -> bool`; `is_year_like(text) -> bool` and `is_complete_number(text) -> bool` (both `lru_cache(maxsize=65536)`); `row_values(row) -> list[tuple[int, str]]`; `is_explicit_header_row(row) -> bool`; `is_year_run(row, label_column: int) -> bool`; `counts_bare_years(row, label_column: int) -> bool`; `is_label_only(row, label_column: int) -> bool`; `is_header_like(row, label_column: int) -> bool`; `fuses_like_main(grid: OriginGrid) -> bool`; `row_roles(grid: OriginGrid) -> RowRoles`.
  - `@dataclass(frozen=True) class RowRoles: label_column: int | None; identifier_column: bool; header_rows: tuple[int, ...]; data_rows: tuple[int, ...]; empty_rows: tuple[int, ...]` with `role(self, row: int) -> RowRole`.
  - Private, used only here: `_caption_patterns`, `_slot_text`, `_origin_texts`, `_rebuild_split_negatives`, `_label_text`, `_caption_label` (lru_cache), `_year_run`, `_counts_bare_years`, `_label_only`, `_header_like`, `_is_marker_text`, `_fuses_like_main(cells, text_rows)`; constants `_NUMBER`, `_CURRENCY`, `_SIGN`, `_STANDALONE`, `_FOOTNOTE_MARKER`, `_RANGE`, `_BARE_YEAR`, `_FISCAL_YEAR_RANGE`, `_NIL_VALUES`, `_OPEN_AMOUNT`, `_OPEN_ONLY`, `_PLAIN_AMOUNT`, `_CLOSE`, `_UNIT_CAPTION`, `_AUDIT_CAPTION`, `_MARKER_TEXTS = {"%", ")", ")%", "("}`.

**Behaviour the tests pin** (`tests/test_table_roles.py`):
- Named tables: CRM 26 (`4 | Fiscal Year Ended January 31,`, empty-label years row, cash-flow data) → header, header, body, body, body, `header_rows == (0, 1)`, `identifier_column is False`; JPM 109 → body, body, body, header zone empty; AAPL 18 (`Gross margin percentage:` then `Products | 36.5 | %`) → all four rows body, header zone empty (the label-only row trails); nvda-2026-10k 17 → header ×3, body ×3.
- Split negatives: th `Metric | 2025 | 2024` over `Loss | (29 | ) | (40 | )` and `Gain | 50 | | 60 |` → header, body, body, data rows (1, 2); the same rows without a header → body, body; `( + 29 + )`, `(3.2 + )%` and `(.62 + )` each make a data row. A genuine single-digit first row `Stores | 9 | 7` is body.
- Identifier columns: `Exhibit Number | Description` over `3.1`, `3.2` → header, body, body, `identifier_column is True`; over `1 | Agreement`, `3.1 | Articles` → the same; all-integer `1`, `2` → the same; caption-number control (`4 | Fiscal Year Ended January 31,`, years, `Revenue | 100 | 200`) → header, header, body, no identifier column.
- Coordinate equivalence: a placed grid with a leading spacer column, a blank row, a span-covered label slot and linked label and number, against its cleaned grid → the same roles through the row map, label columns 1 and 0, placed `empty_rows == (1,)`; `row_values` keeps original columns (`[(1, "Costs"), (3, "60"), (4, "70")]` against `[(0, ...), (2, ...), (3, ...)]`).
- No data row: a text table (`Name | Title`) and GOOGL 89's signature block → the first row alone is header.
- Years, footnote marks and links: `Year | Amount` over year labels → data through the amounts, `identifier_column is False`; `Year | Event` over year labels → no data row (revision 11); a td header row `Item | Amount | (1)` → data (`(1)` is a complete number; recorded limitation), header zone empty; `(1)` in the label column stays header; a linked number is classified from its label; digits in a link destination never make data; a nil value outside the label column makes data; an all-empty grid → `label_column is None`, every row `empty`.
- Bare years beside labels: th `Item | 2026 | 2025` over `Revenue | 2000 | 1900` → data; td `Segment | 2025 | 2024` is a year run → header, body; `| 2023 | Change | 2022` (empty label), period captions (`Maturities (calendar year)`, `Year Ended June 30,`, `June 30,`, `Fiscal Year`) and unit captions (`(In millions)`, `(in thousands, except per share data)`, `Amounts in billions`) keep their years rows header; all-th `Denomination | €1 | €2` is never data; a th label cell beside td values stays data; `counts_bare_years` is false for a span-covered or empty label.
- Footnoted values and ranges (revision 7): exhibit index with `2.1(1)` → header, body ×3, identifier column; a `3,984 *` row is data; range rows (`0.1 - 2.0`, `3.5 %- 4.3 %`) are data; bare-year ranges in a header row stay header; `Topic | Reference` / `Liquidity | Item 7 and 120` / `Revenue | 1,234` → header, body, body.
- Section labels (revisions 8, 9): `Accounts Receivable:` before the data → header, body, body; every trailing label-only row is body; label-only rows above period rows stay header (header ×4, body); a zone of label-only rows alone is empty; a no-data table keeps a label-only first row as its header; a unit or period caption in the label column only, before the data, is body; the same caption spanning the value columns stays header; footnoted years, fiscal-year ranges and bare-year ranges stay header in a header row and follow the bare-year rule beside a row label.
- Header-like rows (revision 11): the S1 rows end the zone and are body: `Common Stock | AAPL` under `Title of each class | Trading symbol(s)`, `Finance leases | 15.1 years` under `| 2025 | 2024`, KO 110's `10.5.22 | Plan A` rows (data rows (3, 4)), META 39's linked `10.1+` rows; a column-heading second row under a full first row ends the zone; under a sparse first row it joins it (header, header, body); nine header-like second rows keep the two-row header (empty label, span-covered label, period label, unit declaration, unit caption, audit caption, year-like label, year run, th row); rows below the zone-ending row stay body even when header-like; td years rows (`Function | 2022 | 2023 | 2024`, `(Dollars in millions) | 2024 | 2023`, `(Millions of dollars)`, `(Unaudited)`, `2023 | 2022`) are header; BAC 46's title plus unit-caption years row stay header with the section label body; the named limitation `Units | 2024 | 2025` under a th row reads as header; a year run followed by no data row is the header alone.
- Predicates: `is_year_run` true ×5 (ascending, repeated pairs, equal neighbours, text between, nil between) and false ×6 (far apart, one year, with an amount, footnoted years, two apart, label year only); `is_unit_text` true ×19 and false ×9 (`(Shares in millions)`, `(Notional in millions)`, `Unaudited`, `Consolidated Balance Sheets (unaudited):`, `Total revenue (in millions)`, …); `is_period_text` reads the shared pattern; `is_header_like` ×13, label-only rows included.
- Label-only rows and the fusion (revision 12): nvda-2026-ex99-1 unit 5's stacked titles → header ×6, body ×4; ex99-1 unit 11 → header ×4, body ×2; stacked titles right before the data leave the zone; the lease-term title control stays body; a label-only row between header rows stays header; an `Exhibit Index` title over its headings fuses (identifier column); META 10-K 2025 t37 and TSLA 40 → header, header, body ×3; the fusion needs a sparse first row (two controls) and a full second row; a third heading row ends the zone; a placed 10-column grid (label column 2) and its cleaned grid fuse alike; `is_label_only` ×5.
- Marker-only columns (revision 13): AMZN 10-Q 21 → header, body ×3, `fuses_like_main` false; JPM 207 → header, header, body ×4, true; the NVDA 10-K 38 control (`$` columns that also hold dates and values) → header, header, body, body, true; `test_main_sparse_row_fusion` ×17 (exhibit title, payments span, … currency columns, percent columns, close-percent columns, open columns, currency codes: no fusion; unknown codes, currency column holding values, marker under a heading: fusion).
- Number predicates: 35 complete numbers (`9,943`, `(29)`, `36.5 %`, `$ 1,234`, `RMB 941,168`, `.75`, `3.1`, `9`, `(3.2)%`, `€ (1,234)`, `NT$ 1,329.2`, `−5`, `(.62)`, `$(120)`, `( 29)`, `2,191,446,233`, `2.1(1)`, `3,984 *`, `104**`, `1,234 (1)`, `10.1(10)`, `36.5 %(a)`, `$ 1,234 †`, `9‡`, `4.3 [1]`, `(29)(1)`, `1,234 (a)(2)`, `3.5 %- 4.3 %`, `0.2 - 1.0`, `0.1 - 2.0`, `26 %- 96 %`, `1 – 2`, `$ 10 to $ 20`, `(5)—(3)`, `RMB 1.2 - RMB 1.5`); 28 non-numbers (`2025`, `1999`, `—`, `(29`, `29)`, `abc`, `XYZ 100`, `$`, `5, 24`, `""`, `Jan 25, 2026`, `1,`, `Item 7 and 120`, `1,234 (123)`, `1,234 (ab)`, `1,234 [a]`, `*`, `(1)(2)x`, `2025 (1)`, `2024(a)`, `2024 – 2026`, `2023-2024`, `2024–25`, `1 - 2 - 3`, `1 to`, `0.1 - 2.0 (1)`, `Note 2`, `5 or 6`); bare years are 1900–2099 (`1899` and `$ 2025` are complete numbers); `is_year_like` ×18 (`2024–25`, `2024 – 25`, `2024-25`, `2024 — 25` true; `2024–5`, `2024–255`, `24–25`, `Fiscal 2025` false); nil values ×9; the 27 currency markers; 8 non-markers (`ABC`, `XYZ`, `rmb`, `$$`, `US`, `RMB 1`, `(`, `%`); `visible_text`; `row_values` rebuilds split negatives at the digit column and skips span-covered and empty slots.
- Revision 14's grammar: `test_standalone_numbers_have_one_marker_one_percent_and_groups_of_three` ×14 rejects `$ $ 5`, `USD $ 5`, `$ ($ 120)`, `RMB (€ 5)`, `5 % %`, `(3.2 %)%`, `$ 1,234 % %`, `1,,2`, `12,34`, `(12,34)`, `1,00,000`, `12,345,6`, `0,5`, `1,2345`; `test_standalone_numbers_keep_every_form_with_one_marker_and_one_percent` ×17 keeps `US$ 1,250.0`, `$ (120)`, `($ 120)`, `( $ 120 )`, `(3.2 %)`, `(3.2) %`, `$ 5 %`, `$-5`, `+5`, `– 5`, `(−5)`, `1234`, `1,234.5`, `1,234,567.89`, `0.000`, `RMB(1,234)`, `($ 120 %)`; `test_split_negatives_rebuild_only_standalone_amounts`: `Loss | (12,34 | )` keeps `(12,34` and `)` apart (neither is a value), `Loss | (1,234 | )` rebuilds `(1,234)`.
- Revision 15's control: `test_full_width_caption_starting_in_the_label_column_before_the_data_is_a_body_row` ×2 (a unit caption and a period caption). The grid `["", "2025", "2024"]`, `[caption, None, None]`, then a data row gives header, body, body. The label-only test is true for the caption that starts in the label column and false for `["", caption, None]`. It sits next to `test_caption_spanning_the_value_columns_before_the_data_stays_header`.

**Tests changed:** none (new file).

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_table_roles.py` → 341 passed
- Full suite at `6a5f29f` (`git archive` tree): 1138 passed, 1 failed, 14 deselected, 3 warnings. Real failures: none. Environment-only: `tests/test_models.py::test_internal_version_matches_distribution` (`'0.1.22+rcq.4' == '0.1.22+rcq.3'`: the venv's editable metadata is rcq.4; the tree pins rcq.3 until Task 10).
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- Complete number (spec 259-263, revision 14; resolved): `_NUMBER` (`table_roles.py:52`) takes thousands in groups of three or plain digits, with an optional decimal, or a leading-dot decimal; `_STANDALONE` (`table_roles.py:58-61`) takes one currency marker, before or inside the parentheses, an optional sign after it, and one `%`, inside or after the parentheses. The split-negative pieces (`_OPEN_AMOUNT`, `_PLAIN_AMOUNT`) share `_NUMBER`, so `(12,34` is no longer an open amount. Two readings the definition leaves open: a `%` inside the parentheses is the one trailing `%` (`(3.2 %)`, `($ 120 %)` are numbers; `(3.2 %)%` is not), and the marker must come before the sign (`$-5` and `$ - 5` are numbers, `-$5` is not; verified on the tree). A random check (`plan-checks/standalone_check.py` in the acceptance folder: 200,000 strings built from markers, parentheses, signs, `%`, spaces and well-formed and malformed numbers) found no disagreement between `_STANDALONE` and a procedural reading of the definition with those two readings. Corpus effect (REPORT-round5.md): footnote-reference cells such as `1,2` are no longer numbers (KO 10-K unit 14, CAT 10-K units 37 and 39).
- Footnote markers (spec 268-271): `(1)` and `[1]` take one or two digits, `(a)` one letter, one or more markers each with optional space before it. So `1,234 (123)` and `1,234 [a]` are not complete numbers, `(1)(2)x` is text.
- Year-like values (spec 275-282): "other than a bare year" is applied to the number before its markers, so `2025 (1)` and `2024(a)` are year-like. A fiscal-year range is `19xx` or `20xx`, a hyphen, en or em dash (spaces allowed) and two digits, with no consecutiveness check (`table_roles.py:69`); revision 14 words it that way (spec 280-281: "a bare year joined by a dash to two more digits"), so CAT's series `2022-03` is year-like by the spec too (resolved). `2024 to 25` is a complete number (the fiscal form is dash-only). A range carries no footnote markers (`0.1 - 2.0 (1)` is not a number) and three numbers are no range.
- Year run (spec 295-299): its numbers are the complete numbers and year-like values outside the label column, so nil values and text cells are skipped (`Units | 2024 | — | 2025` is a year run) and footnoted years break it (`2024(a) | 2023(a)`, "bare years" read literally). "Within one" is `abs(a - b) <= 1`.
- Unit text (spec 284-294): `_UNIT_LINE.search`, or `_UNIT_CAPTION` (dollar captions anchored at the start, with or without parentheses, `$` for "Dollars", optional "U.S."), or `_AUDIT_CAPTION` as the whole cell. Period text is `_PERIOD_TEXT.search` anywhere in the label, so any label holding "year(s)", "ended", "fiscal", "as of" or a month-day date counts.
- Label-only rows read origin cells, not rebuilt values (spec 369: "origin text in the label column only"); the two differ only for a split negative straddling the label column.
- Sparse-row fusion (spec 340-357): n is counted over every row with origin text in the whole grid, so the placed and the cleaned grid agree; marker texts are compared with spaces removed (`) %` is `)%`); the currency test is whole visible text; "the second row" is the second row with origin text; the fusion is tried only at that position.
- The trailing label-only strip runs after the zone is cut; with no data row the first row stays even when label-only (spec 375-376).
- `visible_text` also maps U+00A0 to a space and strips the text; internal whitespace is not collapsed.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 2: Structural policy (R9) and zero-width cell text (commit `c249876`, prototype `proto T2`)

**Spec:** R9; Definitions (Visible cell text: zero-width removal; Structural policy; Explicit header row's th markup); "What does not change" (cell text extraction apart from zero-width characters; XLSX); Testing, "XLSX boundary (R9)".

**Files:**
- Modify: `src/sec2md/table_parser.py` — the `StructuralPolicy` enum, a keyword-only `policy` on every structural helper, one marker-vocabulary function, zero-width removal at extraction, `Cell.header`, and the Markdown render passing `EXTENDED`.
- Test: `tests/test_table_merge_headers.py` — new, 12 tests.
- Test: `tests/test_xlsx_tables.py` — 9 parametrized `prepare_table` controls (69 → 78).

**Interfaces:**
- Consumes: `table_roles.ZERO_WIDTH_CHARACTERS` (Task 1).
- Produces:
  - `class StructuralPolicy(Enum): LEGACY = "legacy"; EXTENDED = "extended"`; module constants `LEGACY`, `EXTENDED`; `_ZERO_WIDTH` (translate table).
  - `_marker_class(value: str, *, policy: StructuralPolicy = LEGACY) -> StructuralColumn | None`; `_classify_structural_column(values: Sequence[str], *, policy: StructuralPolicy = LEGACY) -> StructuralColumn | None`.
  - `Cell` gains `header: bool = False` after `colspan` (a th element; `Cell(text)` stays a td).
  - `TableParser._should_merge_cells(self, val1, val2, *, policy=LEGACY) -> bool`; `@staticmethod _numeric_token(value: str, *, policy=LEGACY) -> str | None` (new; LEGACY = `normalize_numeric_token`); `@staticmethod _is_numeric_fragment(value: str, *, policy=LEGACY) -> bool`; `@staticmethod _body_start(grid, *, policy=LEGACY) -> int`; `_body_rows(self, grid, *, policy=LEGACY) -> Sequence[int]` (new; LEGACY = `range(_body_start, len(grid))`); `_safe_structural_actions(self, grid, *, policy=LEGACY) -> dict[int, dict[int, int]]`; `_validated_structural_actions(self, grid, actions, *, policy=LEGACY) -> dict[int, dict[int, int]]`; `@staticmethod _header_merge_target(source, value, source_actions, removed, column_count, *, policy=LEGACY) -> int | None`; `@staticmethod _join_structural_text(prefixes, target, suffixes, *, policy=LEGACY) -> str`; `_merge_structural_columns(self, grid, *, policy=LEGACY)`; `_merge_grid(self, grid, *, policy=LEGACY)`. `_create_grid` calls `self._merge_grid(grid, policy=EXTENDED)`; `xlsx_tables.py` is untouched, so its calls stay `LEGACY`.

**Behaviour the tests pin:**
- `tests/test_table_merge_headers.py`:
  - `LEGACY is StructuralPolicy.LEGACY`, `EXTENDED is StructuralPolicy.EXTENDED`, distinct.
  - On a bare `object.__new__(TableParser)` with the NVIDIA-shaped grid (two repeated `)` columns, two `$` columns, a final singleton `)`): `_safe_structural_actions(grid)` → `{1: {1: 2, 2: 2}, 3: {1: 2, 2: 2}, 4: {1: 5, 2: 5}, 6: {1: 5, 2: 5}, 8: {1: 7}}`; paired actions validate, `$` alone is rejected (`$ (10` incomplete); `_join_structural_text(["$"], "(10", [")"]) == "$ (10)"`; `_is_numeric_fragment("(29")`; `_body_rows(grid) == range(1, 3)`; `_should_merge_cells($, 10)`; `vars(parser) == {}`. `EXTENDED` gives the same actions without instance state.
  - A spy fixture wrapping `_classify_structural_column`, `_marker_class`, `_is_numeric_fragment`, `_numeric_token`, `_join_structural_text`, `_body_start`, `_validated_structural_actions`, `_body_rows`, `_safe_structural_actions`, `_should_merge_cells`: every transitive helper is reached and receives the policy (legacy and extended); the default call passes `LEGACY` explicitly to every helper; the Markdown render passes only `EXTENDED`; `prepare_table` passes only the default or `LEGACY`.
  - Zero-width text: `Item\u200b`, `\ufeff2025`, `A\u2060B`, `1,234\u200c\u200d` and a linked `C\u200cD\u200b` read `Item`, `2025`, `AB`, `1,234`, `[CD](x.htm)`; NTRA's `$` column with a U+200B cell merges (`| Revenue | $ 100 |`, `| Other | 5 |`); a U+200B-only first row is not a header line (`| Item | 2025 |` first); cells keep td/th markup (`[[True, False], [False, True]]`).
- `tests/test_xlsx_tables.py::test_prepared_tables_keep_legacy_structural_rules[...]` ×9 (singleton_dollar, singleton_close, currency_euro, currency_iso_code, currency_prefixed_dollar, leading_dot_decimals, percent_close_marker, zero_width_marker_slot, sentinel_header_start): headers, every cell's value, number format, original and review reason, `cell_sources`, issues and status, captured from `prepare_table` at `c674828`.

**Tests changed:** none.

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_table_merge_headers.py tests/test_xlsx_tables.py` → 90 passed in 1.84 s (wall 2.6 s)
- Full suite at `c249876`: 1159 passed, 1 failed, 14 deselected, 3 warnings. Real failures: none. Environment-only: `tests/test_models.py::test_internal_version_matches_distribution` (rcq.4 metadata against the tree's rcq.3; Task 10).
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- Plumbing only: at this commit `EXTENDED` behaves exactly like `LEGACY`; Task 3 fills the branches.
- One vocabulary function: every `STRUCTURAL_MARKERS.get(v)`, `v in STRUCTURAL_MARKERS`, `v == "$"` goes through `_marker_class`. The legacy mixed-column test is rewritten as `set(classes) == {"currency", "close_paren"}` with at least two of each class; under `LEGACY` `currency` is only `$` and `close_paren` only `)`, so it is equivalent to the old test.
- Spec R9 names `_safe_structural_actions(grid, *, policy=LEGACY)` and `_validated_structural_actions(grid, actions, *, policy=LEGACY)` "and the predicates and marker vocabulary they use": all of them, plus `_body_start`, `_body_rows`, `_join_structural_text` and the new `_numeric_token`, take the policy.
- Zero-width removal (spec 240-242 "removed", 667): `_extract_cells`' non-link path now ends `.translate(_ZERO_WIDTH).strip()`, and `_inline_fragments` (link path) removes all five characters (before: U+200B and U+FEFF only). Removal, not a space.
- `Cell.header = td.name == "th"` feeds R0's explicit header rows from Task 3 on; nothing reads it here.
- The XLSX controls are characterization tests (green before and after); their discrimination was shown by a temporary `EXTENDED` leak into `prepare_table` (9 failed; the leak was not committed). Spec 995-996 asks for "values, column groups, source coordinates, headers and issues": column groups are visible only through `cell_sources` (each output cell sourced from its own slot).

**Review changes (2026-10-06):**
- The user accepted the zero-width conflict as a named limitation (spec revision 17). Zero-width removal joins a number that the source splits with a zero-width character (`1,2​34`); strict's source pool still splits it, so strict reports the joined token as untraceable, and check 1 can report the parts as missing. `main` passes; the corpus has no such cell.
  - Task 2's commit gains `test_zero_width_inside_a_number_is_a_known_strict_limitation` ×3 (fails on `c674828` with "DID NOT RAISE"). Task 2's task tests: 93 passed; every later full suite: the plan's count + 3, same failing ids.
  - Task 10's commit gains a known-limitation bullet in the `0.1.22+rcq.4` CHANGELOG section.
  - Strict's source pool is fixed in a separate task.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 3: EXTENDED careful-merge rules and currency markers (commit `d239a9d`, prototype `proto T3`)

**Spec:** R3 steps 1–4; R4; R9 (the `EXTENDED` branches); Testing, "Currency, parametrized" and "Other synthetic cases" (helper level), "XLSX boundary".

**Files:**
- Modify: `src/sec2md/table_parser.py` — `EXTENDED` vocabulary (`)%`, the closed currency list), visible text, R0 body rows, single-marker columns and local numeric validation (leading dots, currency prefix).
- Test: `tests/test_table_merge_headers.py` — 30 additions (12 → 42).
- Test: `tests/test_table_parser.py` — 1 test changed.
- Test: `tests/test_table_completeness_parser.py` — 3 cases changed and 3 controls added, each in both modes (90 → 96).

**Interfaces:**
- Consumes: `CURRENCY_MARKERS`, `CURRENCY_PATTERN`, `OriginCell`, `row_roles`, `visible_text` (Task 1); the Task 2 helpers and `StructuralPolicy`.
- Produces:
  - `EXTENDED_MARKERS: dict[str, StructuralColumn]` = `STRUCTURAL_MARKERS` + `")%": "close_paren"` + every currency marker as `"currency"`.
  - `_CURRENCY_PREFIX = re.compile(rf"^(\(?\s*){CURRENCY_PATTERN}\s*")`; `_LEADING_DOT = re.compile(r"(?<!\d)\.(?=\d)")`.
  - `_cell_value(text: str, *, policy: StructuralPolicy = LEGACY) -> str` (LEGACY `text.strip()`, EXTENDED `visible_text`).
  - `_origin_cells(grid) -> list[list[OriginCell | None]]` — the neutral R0 grid (origin text and th flag, `None` where a span covers); private, used by Task 4's `_create_grid` and imported by tests (`tests/test_table_merge_headers.py`, `tests/test_table_alignment.py`).
  - EXTENDED branches: `_marker_class` → `EXTENDED_MARKERS.get(visible_text(value))`; `_classify_structural_column` accepts one marker (LEGACY two); `_numeric_token` → visible text, one leading currency marker stripped (also after a leading `(`), `.75` → `0.75`, then strict's `normalize_numeric_token`; `_is_numeric_fragment` strips the same prefix first; `_body_rows` → the rows whose role is `"body"` in `row_roles(_origin_cells(grid))`, as a tuple; `_should_merge_cells`, `_safe_structural_actions`, `_validated_structural_actions`, `_merge_structural_columns` read cells through `_cell_value`.

**Behaviour the tests pin** (`tests/test_table_merge_headers.py`):
- R3.1 (NTRA): a U+200B marker slot → EXTENDED actions `{1: {1: 2, 3: 2}}`, LEGACY `{}`.
- R3.2 (MSFT 24 / TSM 312, a year starting the `$` column): EXTENDED `{1: {2: 2, 4: 2}, 3: {2: 4, 4: 4}}`, LEGACY `{}`; `_body_rows` EXTENDED `(2, 3, 4)`, LEGACY `range(1, 5)`; rendered `| Product | $ 63,946 | $ 64,773 |`, `| Service and other | 217,778 | 180,349 |`, `| Total revenue | $ 281,724 | $ 245,122 |`.
- R3.3 (nvda-2002 138): EXTENDED accepts fragments `.75` and `(.62`, `_numeric_token("$ (.62)") == "-0.62"`; LEGACY does not; actions `{1: {1: 2, 2: 2}, 3: {1: 4, 2: 4}}`; rendered `| Basic | $ .75 | $ .62 |`, `| Diluted | $ (.62) | $ .60 |`; strict's `normalize_numeric_token(".75")` and `("RMB 1,234")` stay `None`.
- R3.4: BABA 69's one negative per `)` column → `{2: {2: 1}, 4: {2: 3}}`, rendered `(72,818)`, `(68,335)`; a single unmatched `(` still fails validation; TSM 79: a column mixing `%` and `)%` stays split, a uniform `)%` column merges (`| Net margin | (3.2)% |`).
- R4: `€`, `NT$`, `DKK` × `1,234`, `(1,234)`, `12.5`, `3.2 %` → `{1: {1: 2, 2: 2}}` under EXTENDED only, rendered `{marker} {amount}` (12 cases); currency plus split negative → `{marker} (1,234)` (3 cases); an `n/a` attachment rejects the column; `XYZ` and `ABC` stay separate (`| Revenue | XYZ | 1,234 |`); BABA 24's header-row `RMB` is no marker column; `_should_merge_cells(€, 1,234)` holds under EXTENDED only; joins: `RMB 941,168`, `€ (1,234)`, `(3.2)%` under EXTENDED, `(3.2 )%` under LEGACY.

**Tests changed:**
- `tests/test_table_parser.py::TestToMatrix::test_singleton_structural_marker_does_not_bypass_two_row_floor` → `test_singleton_structural_marker_keeps_the_legacy_two_row_floor`: R3.4 lets the Markdown render merge the single `)` (`["R1", "(10)", "(20)", "(30)"]`); the LEGACY two-row floor is asserted on a bare parser (`sorted(actions) == [2, 4]`).
- `tests/test_table_completeness_parser.py` CASES "prose repeats the lost value", "lost single-digit $9", "'Note 1 Revenue' row loses its amount": R0 makes a headerless first row body (R3.2), so its `$` merges and the amount is kept; the losses are now simulated by a mutation (`"| $ 9,943 |"` → `"| $ |"`, `"| $ 9 |"` → `"| $ |"`), and three "kept" controls expect `{}`.

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_table_merge_headers.py tests/test_table_parser.py tests/test_table_completeness_parser.py` → 167 passed in 0.49 s (wall 1.3 s)
- Full suite at `d239a9d`: 1193 passed, 3 failed, 14 deselected, 3 warnings. Real failures: `tests/test_table_completeness_fixtures.py::test_fixture_reports_exactly_the_pinned_failures[nvda-2002-10k-normal]` and `[nvda-2002-10k-capture]`: `assert {} == {19: ('1997', '1998', '31', '31')}` — R3.2/R3.3 merge table 19's `$` columns, so its period headers are no longer lost; Task 10 empties the pin. Environment-only: the version test.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- Mixed `$` + `)` marker columns keep LEGACY's "two of each" threshold under EXTENDED; only uniform columns drop to one marker (spec 467-469: "A marker column with one non-empty marker may merge").
- Fragment recognition strips a leading currency marker first, so `€ (1,234` is a fragment, matching R0's split shapes.
- `_CURRENCY_PREFIX` strips one marker at the start or right after a leading `(`; validation then calls strict's `normalize_numeric_token`, which stays unchanged (spec 464-466, 497-498).
- `_should_merge_cells` reads `_cell_value` under both policies; under LEGACY that equals the old test, since `GridCell.__bool__` is `bool(self.text.strip())`.
- Until Task 4, `_merge_structural_columns` still moves header text with `_header_merge_target` in R0 header rows; R3.5 lands with membership.
- R3.1 matters for callers that pass raw text (XLSX, bare parsers); the Markdown path already removes zero-width characters at extraction (Task 2).

**Review changes (2026-10-06):**
- The user decided to fix a gap the spec did not cover (spec revision 17, R4): under `EXTENDED`, a label column holding only currency codes was a currency-marker column, so an exchange-rate table (`EUR | 1.08 | 1.10` under an empty corner cell) rendered `| EUR 1.08 | 1.10 |`. Now R0's label column is never a currency-marker column for a marker other than `$`; `$` keeps `main`'s rule and LEGACY ignores the flag.
  - `_marker_class(..., label=...)`; the structural pass and Task 3's legacy pass pass the flag for the label column. Task 3 gains 7 tests (task tests 177 at this commit, with Task 2's 3).
  - Task 4's pipeline passes it too, in `_merge_allowed` (R2's body test, via `_holds_label_cell`) and `_marker_exception`; Task 4 gains 3 tests.
  - XLSX `prepare_table` output and the Markdown of the 382 fixture tables are identical before and after the fix.
- The user accepted a related case as a named limitation (spec revision 17): currency codes in a sub-label column beside the label column still fuse into the first value column (`|  | EUR 1,234 | 987 |`, where `main` keeps `| EUR | 1,234 | 987 |`). Task 3 gains a helper-level characterization test (task tests 178), Task 4 a rendered one, and Task 10 a CHANGELOG known-limitation bullet.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 4: Source grid, membership, R1, R2 and the header veto (commit `fa1055e`, prototype `proto T4`)

**Spec:** Definitions (Source cell, Grid-hidden with the all-hidden row rule, Source grid, Slot, Header cell of a slot, Membership: owning and marker members); R1; R2 (body, header, currency-only marker exception); R3 steps 5–6; Testing, "Provenance and the guard".

**Files:**
- Modify: `src/sec2md/table_parser.py` — grid-hidden rows and cells left out at extraction; the source grid and row roles kept on the parser; the membership pipeline (structural pass with the header veto, then the left-to-right merge under R1 and R2) replacing `_merge_structural_columns`, `_header_merge_target` and the old `_merge_grid`.
- Test: `tests/test_table_merge_headers.py` — 40 additions (42 → 82).
- Test: `tests/test_table_parser.py` — 1 test changed.

**Interfaces:**
- Consumes: `row_roles`, `RowRoles`, `visible_text` (Task 1); `_origin_cells`, `_cell_value`, `_marker_class`, `_safe_structural_actions`, `_validated_structural_actions`, `_join_structural_text`, `_numeric_token`, `_should_merge_cells` (Tasks 2–3); `xlsx_tables._hidden`, imported lazily.
- Produces:
  - `_snapshot_hidden_rule() -> Callable[[Tag], bool]` (lru_cache; lazy import of `xlsx_tables._hidden`, since `xlsx_tables` imports this module); `_grid_hidden_within(node: Tag, table: Tag, known: dict) -> bool`; `_descendants_named(node: Tag, names: tuple[str, ...]) -> list[Tag]`.
  - `@dataclass(frozen=True) class BodySlot: text: str = ""; cells: tuple[Cell, ...] = ()`.
  - `@dataclass class OutputColumn: owners: list[int]; markers: list[int]; slots: list[BodySlot]`.
  - `_contains_cells(container: Sequence[Cell], cells: Sequence[Cell]) -> bool` (identity subset).
  - Instance state set by `_create_grid`: `source_grid: List[List[Optional[GridCell]]]` (span expansion + `_clean_grid`, never rewritten), `roles: RowRoles` (`row_roles(_origin_cells(source_grid))`), `columns: list[OutputColumn]`; `grid` is `_output_grid()`.
  - `@staticmethod _header_cells(grid, owners: Sequence[int], row: int) -> list[Cell]`; `@staticmethod _independent_header_veto(grid, header_rows: Sequence[int], actions) -> dict[int, dict[int, int]]`; `_structural_columns(self, grid, header_rows, *, policy: StructuralPolicy) -> list[OutputColumn]`; `_merge_allowed(self, grid, header_rows, group: OutputColumn, column: OutputColumn, *, policy) -> bool`; `_marker_exception(self, grid, header_rows, body_rows, group, column, *, policy) -> bool`; `@staticmethod _merged_column(group: OutputColumn, column: OutputColumn) -> OutputColumn`; `_merge_grid(self, grid, header_rows: Sequence[int], *, policy: StructuralPolicy) -> list[OutputColumn]` (signature changed, `policy` required); `column_header_cells(self, index: int) -> list[list[Cell]]` (public, one list per header-zone row); `_output_grid(self) -> List[List[GridCell]]`.
  - Removed: `_merge_structural_columns`, `_header_merge_target`. `_body_rows` reuses `self.roles` when `grid is self.source_grid`.

**Behaviour the tests pin** (`tests/test_table_merge_headers.py`):
- Roles are decided once on the cleaned source grid: `parser.roles == row_roles(_origin_cells(parser.source_grid))`; CRM 26 header rows (0, 1), data rows (2, 3); every slot still points at an extracted `Cell`.
- CRM 26: membership `[([0], []), ([1], []), ([2, 3], []), ([4, 5], []), ([6, 7], [])]`; the caption heads columns 1–3 (it covers 2025 and 2024, not 2023, as in the source); body `["Net cash provided by operating activities", "", "$ 13,092", "$ 10,234", "$ 7,111"]`.
- R1: JPM 109 (headerless) → `[([0], []), ([1, 2], []), ([3, 4], [])]` with `$ 84,973`, `$ 68,837`, `$ 87,533` kept; TSLA 38's spanning body cell counts once (`$ 487`, `589`, `$ 1,076`).
- AAPL 15 offset values under one span: membership `[([0], []), ([1, 2], []), ([3], [4]), ([5, 6], [])]` (the `%` column is a marker member of `Change`); headers `[[[]], [["2023"]], [["Change"]], [["2022"]]]`; body `Americas | $ 162,560 | (4) % | $ 169,658`, with `Net sales by reportable segment:` as the first body row. KO 18's offset `$ —` rows merge.
- Blocked merges: complementary values under sibling headers `2025 | 2024` stay three columns; BABA/TSM spans starting on an empty body column never merge into the previous period or the labels.
- Astra's mixed-direction marker column: membership `[([0], []), ([1], [2]), ([3], [2])]`, headers `Metric`, `2025`, `2024`; rows `A | 100 | $ 200`, `C | (30) | 400`; `"2025 2024"` never appears.
- R3.6: `Label | 2022 | Change | 2021` over `10 | % | 20` keeps four columns; veto then revalidation: `(` under `Sign` stays, so the `)` action is dropped too (`_safe_structural_actions` → `{1: {1: 2, 2: 2}, 3: {1: 2, 2: 2}}`, `_independent_header_veto(grid, (0,), …) == {3: {1: 2, 2: 2}}`, four own columns).
- Marker exception: a headerless `$` column that the structural pass rejected (a stray `)`) joins 2024's amounts, never 2025's (`[([0], []), ([1], []), ([2, 3], []), ([4], [])]`); every marker row needs a validating value (`$ —` stays split, 2025 keeps its header); an empty group never qualifies (direct `_merge_allowed`), while the same headerless column passes the header test itself; one non-marker group slot (`n/a`) disqualifies; a `(` group never qualifies, a `€` group does.
- Header text is never concatenated (5 tables); every source cell text is kept (6 tables).
- R6 invariant: at most one header cell per header-zone row and output column over every `<table>` of the 7 fixtures (×7).
- Grid-hidden: CAT 34's S2 shape → source grid `[["Millions of dollars", "Twelve Months Ended December 31,", None], ["", "2024", "2023"], ["Free cash flow", "9,449", "10,025"]]`, cells per row `[2, 3, 3]`; BAC 336's row with one hidden cell fewer keeps three own columns; rows hidden by `display:none`, `hidden` or `visibility: hidden` (×3) are left out; a hidden cell's `Draft 123` is never rendered; a hidden `tbody` and a `visibility:hidden` td inside the table are left out; a hidden wrapper outside the table hides nothing.
- All-hidden rows: JPM 606 → cells per row `[3, 0, 3, 3]`, and the `Balance at December 31, 2021` row keeps its place under rowspans; BAC 320's rowspan label over an all-hidden row keeps the later rows in their columns.

**Tests changed:**
- `tests/test_table_parser.py::TestToMatrix::test_suffix_marker_header_merges_to_left_numeric_column` → `test_suffix_marker_column_with_its_own_header_stays_visible`: R3.5/R3.6, header text never moves and a marker column whose header covers no value column stays (`["Label", "2022", "Change", "2021"]`, `["A", "10", "%", "20"]`; was `"2022 Change"` over `"10 %"`).

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_table_merge_headers.py tests/test_table_parser.py` → 111 passed in 2.43 s (wall 3.2 s)
- Full suite at `fa1055e`: 1216 passed, 19 failed, 1 error, 14 deselected, 3 warnings. Real failures:
  - Strict `ParseQualityError: untraceable normalized number` (repeated spanning header numbers, for example `sec2md-p38-t0-…:2023` ×6 on aapl), fixed by Task 7: `tests/accuracy/test_sec_accuracy.py::test_audited_document_meets_baseline_contract[aapl-2023-10k]`, `[nvda-2026-10k]`, `[nvda-2002-10k]`, `[nvda-2026-q2-10q]`, `::test_apple_trace_has_no_failures`, `::test_legacy_character_normalization_has_no_c1_controls`, `tests/test_chunker.py::TestChunkSectionIsolation::test_real_filing_item_1b_chunks_match_section_text`, and ERROR at setup of `tests/accuracy/test_sec_accuracy.py::test_rcq_release_contract`. After Task 7 the four contracts, the apple trace and the release contract still fail on the accuracy harness's own trace (and q2's financial rows) until Task 10.
  - `tests/test_table_completeness_fixtures.py::test_fixture_reports_exactly_the_pinned_failures[...]` ×10 (aapl-2023-10k, nvda-2002-10k, nvda-2026-q2-10q, nvda-2026-ex99-1, nvda-2026-ex99-2; normal and capture): `assert {} == {13: ('-1',), …}` — R1 keeps every pinned loss; Task 10 empties `PINNED_FAILURES`.
  - `tests/test_table_completeness_fixtures.py::test_row_structure_mutations_are_detected[swap_first_body_rows-appears before an earlier source row-48]`: `assert 44 == 48` (the swap mutation is still detected, in 4 fewer aapl tables at this layout); passes again from Task 5.
  - Environment-only: the version test.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- Deleting `_merge_structural_columns`, `_header_merge_target` and the old `_merge_grid` body leaves XLSX untouched: `prepare_table` calls only `_safe_structural_actions`, `_validated_structural_actions` and `_join_structural_text`, which keep their LEGACY defaults.
- Markdown-only pipeline methods take a required keyword `policy` (no default).
- Structural pass order: `_safe_structural_actions` → `_independent_header_veto` (one pass, against the candidate actions' survivors) → `_validated_structural_actions`. Vetoing only adds survivors; two adjacent marker columns under a header cell spanning only them are both kept, where a fixpoint could remove one. Conservative: no header text is lost.
- "Covers" (spec 474-478) is read as: the header cell object occupies a slot of a surviving column in that header row. A header cell of a slot (spec 386-387) is the slot's `Cell`, origin or span, with non-empty visible text.
- R1's "counts once" (spec 415-416): `_merged_column` keeps the group's slot when B's cells are all among the group's (identity subset); otherwise it joins the texts with a space and adds the new cells. Span-covered slots carry no text and no cells.
- R2's body test (spec 429-430) wraps body-slot texts in `GridCell(Cell(text))` and runs `_should_merge_cells(..., policy=EXTENDED)` over every non-header row (empty rows pass).
- Marker exception (spec 435-440): currency markers only; B's value is joined with `_join_structural_text([marker], value, [])` and validated with `_numeric_token`; an empty group returns False. It is reachable only when the structural pass rejected the marker column, since EXTENDED already merges single markers.
- Grid-hidden (spec 221-233): the rule runs on the element and each ancestor up to, not including, the table; it is memoized per element id and per `(style, "hidden" in attrs)`, the only two attributes `xlsx_tables._hidden` reads (`xlsx_tables.py:49-51`). A `tr` whose cells are all hidden stays as an empty row; a `tr` with no cell at all is dropped as before. `_descendants_named` returns the same elements, in the same order, as `find_all`.
- At this commit `_output_grid`'s header rows hold R6 step 1 (each column's distinct owner header cells joined with a space), but `_process_headers` is still the legacy one until Task 5.

**Review changes (2026-10-06):** Task 3's revision-17 fix reaches this commit's pipeline (`_label_column`, `_holds_label_cell`, the flag in `_merge_allowed` and `_marker_exception`) with 3 tests. After the final review, `test_header_text_is_never_concatenated_by_a_merge` asserts at most one header cell per header-zone row and output column (it compared the output with itself before). The rest of the commit is unchanged.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 5: Header line (R5–R7) and the per-render header record (commit `6680c47`, prototype `proto T5`)

**Spec:** R5; R6 (with link-aware equality, revision 11, and step 2's normalized equality as revision 14 words it); R7; R6a step 1 (the header record: header line, `header_source` tokenized once as the pool is, `header_capacity`); Testing, "One rendering test per class", the row-role cases' expected output headers, "Other synthetic cases" (U+200B, `.75`, the nil residual), and the header-zone cases of revisions 11–13.

**Files:**
- Modify: `src/sec2md/table_parser.py` — `_process_headers` from the R0 header zone, R6 step 2 with link-aware equality, R7's `_kept_columns`, `Cell.node`, `TableHeaderRecord` and `_header_record`, set by `to_markdown`.
- Test: `tests/test_table_merge_headers.py` — 76 additions (82 → 158).
- Test: `tests/test_table_completeness_parser.py` — 1 case and 1 test changed.

**Interfaces:**
- Consumes: `self.roles.header_rows`, `self.source_grid`, `self.columns`, `column_header_cells`, `_output_grid` (Task 4); `visible_text` (Task 1); `quality._normalized_numbers` (private, strict's tokenizer).
- Produces:
  - `Cell` gains `node: Optional[Tag] = field(default=None, repr=False, compare=False)` (fifth field; `_extract_cells` passes `node=td`).
  - `_LINK_DESTINATION = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")`; `_header_key(text: str) -> tuple[str, tuple[str, ...]]` (visible text, whitespace collapsed, case folded; link destinations in order).
  - `@dataclass(frozen=True) class TableHeaderRecord: header_line: str | None; header_source: tuple[tuple[str, int], ...] = (); header_capacity: tuple[tuple[str, int], ...] = ()` (sorted `(token, count)` pairs; zero capacities dropped).
  - `_process_headers(self, matrix) -> tuple[List[str], List[List[str]]]`; `_kept_columns(self, headers, data) -> List[int]`; `_clean_empty_rows_and_cols(self, headers, data)`; `_header_record(self, header_line: str | None, kept: Sequence[int]) -> TableHeaderRecord`; `self.header_record: TableHeaderRecord | None`, set by every `to_markdown()` / `md()` (`None` for list tables and empty renders).

**Behaviour the tests pin** (`tests/test_table_merge_headers.py`):
- `test_per_class_rendering` ×13, exact Markdown: jpm-109 (header `|  |  |  |`, every amount kept); crm-26 (`| 4 | Fiscal Year Ended January 31, | Fiscal Year Ended January 31, — 2025 | Fiscal Year Ended January 31, — 2024 | 2023 |`); tsm-248 (`|  | Notes | 2022 — NT$ | 2023 — NT$ |`, `27` under Notes); rddt-52 (`Incorporated by Reference — Form | … — Filing Date | … — Number`, `X` under `Filed Herewith`); msft-24 (`| (In millions, except per share amounts) — Year Ended June 30, | 2025 | 2024 |`, `Revenue:` the first body row); baba-24 (`|  | Notes | Year ended March 31, — 2023 — RMB | Year ended March 31, — 2024 — RMB |`); jpm-482 (`(b)(c)` keeps its own column under `2024 — Consumer, excluding credit card`, and the column where `Consumer` starts is header-only); aapl-18 (empty header line); meta-4 (`2,191,446,233` in the body); googl-89 (row 0 alone is the header); aapl-64 (no data row: row 0 alone, `Exhibit Number | …` in the body); baba-69 (`( 72,818)`); msft-43 (`| (In millions) — June 30, | (In millions) — 2025 | (In millions) — 2024 |`).
- `test_named_role_case_renders_its_expected_header` ×13: nvda-2026-10k-17 (`|  | Year Ended — Jan 25, 2026 — (In millions) | Year Ended — Jan 26, 2025 — (In millions) |`), split-negative first data row, single digit, exhibit index at 3.1, section-label row, footnoted exhibit index, 1 then 3.1, all-integer, caption-number control (`| 4 | Fiscal Year Ended January 31, — 2025 | …`), text table, bare-year label column, standalone `(1)` (`|  |  |  |` with `| Item | Amount | (1) |` as a body row), linked number.
- The renderer's cleaned grid assigns the coordinate-equivalence roles (header rows (0, 1), data rows (2, 3, 4, 5), label column 0).
- R6: Astra's spanning `2025` over `2025` and `Budget` → `| Item | 2025 | 2025 — Budget |`; a rowspan header appears once per column (`| Item | 2025 — Actual | 2025 — Budget |`); `Total` over `TOTAL ` is written once, also when both carry the same link; equal labels with different links are both kept (`[Plan](ex101.htm) — [Plan](ex102.htm)`, `Total — [TOTAL](#t)`).
- R7: the `(a)` header-only column stays; a single data row renders `|  |  |` over it.
- Synthetic: a U+200B cell beside an amount (`| Revenue | $ 1,234 |`, `| Costs | 567 |`); `.75` per-share values (`| Basic | $ .75 | $ .62 |`); the recorded class-8 residual: a `)` column holding a nil value stays split (`| Loss | (29 | ) |` under `|  | 2025 | 2025 |`).
- `test_header_zone_continues_only_through_header_like_rows` ×27 (25 plus revision 15's two): securities, values-with-units, exhibit-numbers (`| 10.5.22 | Plan A |` is the header line), linked-exhibit-pair (both links kept), column heading under a full row (body) and under a sparse row (`| Contractual obligations | Payments Due by Period — Total | …`), third column-heading row (body), exhibit-index title (`| Exhibit Index — Exhibit Number | Exhibit Index — Description | Exhibit Index — Filed Herewith |`), fair-value headings (META t37), statement title beside dates (TSLA 40), stacked titles (ex99-1 unit 5: `NVIDIA CORPORATION — CONDENSED CONSOLIDATED BALANCE SHEETS — (In millions) — (Unaudited) — July 26, — 2026` over `$ 22,443`), marker columns leave the sparse-row count (AMZN 21: `|  | December 31, 2024 | September 30, 2025 |`, lease rows in the body), headings fuse without marker columns (JPM 207: `| Average amount (in millions) | Three months ended — December 31, 2024 | …`), currency columns holding values still count (NVDA 38: `| Inventories: | Jan 25, 2026 — (In millions) | Jan 26, 2025 — (In millions) |`), lease-term title (body), period-label control, unit-caption years row (`| Table 2 — (Dollars in millions) | Noninterest Income — 2024 | Noninterest Income — 2023 |`), year-like label, year run and th-row controls, three years rows, year-shaped amounts stay data, the named limitation (`| Item — Units | First — 2024 | Second — 2025 |`).
- Grid-hidden renders: CAT 34 → `| Millions of dollars | Twelve Months Ended December 31, — 2024 | Twelve Months Ended December 31, — 2023 |`; BAC 336 → three columns; JPM 606 keeps `| Balance at December 31, 2021 | $ 2,640 | $ (131) |`.
- Header record: JPM 482 → `header_source == (("2024", 1), ("31", 1))`, `header_capacity == (("2024", 5), ("31", 1))`; Astra's source → `(("2025", 2),)` and `(("2025", 3),)`; headerless → `header_line is None`, both counts empty; link destinations are not read (`(("2025", 1),)`); a rowspan cell counts once (`("2025", 2)`, capacity `("2025", 3)`); a list table → `header_record is None`; th `Item | ( | 29 | )` → `header_source == (("-29", 1),)`, as the table text tokenizes, and per-cell `header_capacity == (("29", 1),)`.
- Revision 6 renders: `| Item | 2026 | 2025 |` over `| Revenue | 2000 | 1900 |`; th `| Denomination | €1 | €2 |` stays the header line.
- Revision 15's rendering cases in the header-zone table:
  - `full-width-caption-from-the-label-column` renders `|  | 2025 | 2024 |`, `| (In millions) |  |  |`, `| Revenue | 100 | 90 |`;
  - `caption-from-a-value-column` renders `|  | 2025 — (In millions) | 2024 — (In millions) |`, `| Revenue | 100 | 90 |`.

**Tests changed:**
- `tests/test_table_completeness_parser.py` case "unlabelled rows, amount deleted": R7 keeps the `Item` column (header text, empty body), so rows read `|  | 9 |`; the mutation now targets `"|  | 9 |\n|  | 9 |"` (finding unchanged).
- `tests/test_table_completeness_parser.py::test_nested_table_follows_each_rendering_mode`: normal mode now `{}` (was `lost("12")`): R1 and R7 keep the outer cell's `12` (spec 663-666: nested tables get no special handling and their output can change).

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_table_merge_headers.py tests/test_table_completeness_parser.py` → 254 passed
- Full suite at `6680c47`: 1293 passed, 18 failed, 1 error, 14 deselected, 3 warnings. Real failures (Task 4's list without the swap-mutation count, which passes again):
  - Strict `untraceable normalized number` (Task 7; then the harness trace and q2's financial rows until Task 10): `tests/accuracy/test_sec_accuracy.py::test_audited_document_meets_baseline_contract[aapl-2023-10k]`, `[nvda-2026-10k]`, `[nvda-2002-10k]`, `[nvda-2026-q2-10q]`, `::test_apple_trace_has_no_failures`, `::test_legacy_character_normalization_has_no_c1_controls`, `tests/test_chunker.py::TestChunkSectionIsolation::test_real_filing_item_1b_chunks_match_section_text`, and ERROR at setup of `tests/accuracy/test_sec_accuracy.py::test_rcq_release_contract`.
  - `tests/test_table_completeness_fixtures.py::test_fixture_reports_exactly_the_pinned_failures[...]` ×10 (aapl-2023-10k, nvda-2002-10k, nvda-2026-q2-10q, nvda-2026-ex99-1, nvda-2026-ex99-2; normal and capture): `assert {} == {…}` (Task 10).
  - Environment-only: the version test.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- R6's equality (spec 529-532, revision 14: "Equality uses the checker's normalization (step 10: whitespace collapsed, case folded), but compares link destinations too"; resolved) is `_header_key` (`table_parser.py:396-400`): visible text with whitespace collapsed and case folded, plus the link destinations in order, compared with the last kept text, so `Total` over `TOTAL ` is written once and the emitted path collapses alike.
- An empty header zone writes a header line of empty cells and its separator; `header_line` is then `None`.
- R7: a column stays when its header text or any body cell is non-empty. `kept` is computed before empty rows are removed (the same set).
- `header_source` (spec 556-558, 602-608): the distinct `Cell`s occupying any header-zone slot (a rowspan once), sorted by extraction order, each node's `get_text(" ", strip=True)` (empty texts skipped) joined with single spaces and tokenized once with `quality._normalized_numbers`. `header_capacity` (spec 559-560): each cell's own tokens times the kept output columns whose `column_header_cells` contain it, so R6's suppressed repeats still count as capacity.
- Every `to_markdown()` call produces a record; binding it to the original table node is Task 7.
- `_process_headers` reads `self.roles.header_rows` filtered to `row < len(matrix)`; the output grid has one row per source row (Task 4), so the indices match.

**Review changes (2026-10-06):**
- R6 writes a header cell at most once per output column. With overlapping spans (a colspan overwriting a rowspan's middle row) one cell was written twice (`2025 — Budget — 2025`) against a capacity of one, so strict reported `header:2025` where `main` passes.
- `_header_record` leaves out a header-zone cell nested inside another zone cell, then keeps one read per source node, for `header_source`, `header_capacity` and (from Task 10) `header_cells`. A table nested in a header cell had counted `2024` three times, so from Task 7 on R6a credited copies the source does not hold and strict passed.
- Tests pin R6's adjacent-only suppression, whitespace collapse and an empty row between equal texts.
- Task 5 gains 9 tests (task tests 278 at this commit, with earlier tasks' additions); Task 7 gains 10 Parser strict tests.
- Named limitation (user, spec revision 17): a `<table>` directly inside a header-row `<tr>` (malformed) is read twice by extraction, so strict now reports the second copy as a header excess where `main` passed.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 6: Keep every cell of a one-row PART table (R8) (commit `129218b`, prototype `proto T6`)

**Spec:** R8; Testing, "Integration" (CAT 7 through `Parser` and the section extractor); Acceptance, "Sections" (R8 can keep a short part-only stub).

**Files:**
- Modify: `src/sec2md/parser.py` — `_one_row_table_to_text`: the PART branch keeps every non-empty later cell after the normalized label; docstring.
- Test: `tests/test_parser.py` — 4 additions in `TestOneRowTable` (32 → 36) and module constants `CAT_7_SENTENCE`, `CAT_7_TABLE`.
- Test: `tests/test_section_extractor.py` — 2 additions (60 → 62), `CAT_7_DOCUMENT` and `_section_boundaries`.

**Interfaces:**
- Consumes: nothing new (the cells' existing texts from `render_cell_content` or `clean_text(get_text(" ", strip=True))`).
- Produces: no signature change. `Parser._one_row_table_to_text(self, cells: list[Tag]) -> str`, PART branch: `" ".join([f"PART {roman}", *(t for t in texts[1:] if t)])`. Test constants `CAT_7_SENTENCE`, `CAT_7_TABLE` (a minimal copy of CAT 10-K 2025 table 7 with its column-width row), imported by `tests/test_section_extractor.py` and reused by Task 7's `TestHeaderRecordBinding`.

**Behaviour the tests pin:**
- `tests/test_parser.py::TestOneRowTable::test_part_header_table_keeps_every_cell[normal|capture]`: page content and the single element are exactly `PART III 2025 Annual Meeting Proxy Statement (Proxy Statement) to be filed with the Securities and Exchange Commission (SEC) within 120 days after the end of the fiscal year.`; `parser.diagnostics.warnings == ()`.
- `TestOneRowTable::test_part_header_cells_are_joined_after_the_normalized_label`: ` part\xa0iv ` + empty + `Exhibits and` + `Financial Statement Schedules` → `PART IV Exhibits and Financial Statement Schedules`; label plus an empty cell → `PART IV`.
- `TestOneRowTable::test_item_header_table_still_keeps_only_the_first_later_cell`: `Item 1. | | Business | Page 4` → `ITEM 1. Business` (unchanged ITEM branch).
- `tests/test_section_extractor.py::test_cat_7_part_table_keeps_its_cells_and_part_iii_boundaries[normal|capture]`: `extract_sections(filing_type="10-K")` boundaries `[("PART III", None, [1, 2]), ("PART I", "ITEM 1", [3]), ("PART III", "ITEM 10", [4]), ("PART III", "ITEM 11", [4])]`; the cover section's content is exactly the PART III line holding `2025` and `120`; no warnings; the boundaries equal those of the old rendering (the same pages with the line replaced by `PART III`).

**Tests changed:** none.

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_parser.py tests/test_section_extractor.py` → 98 passed in 0.20 s (wall 1.0 s)
- Full suite at `129218b`: 1299 passed, 18 failed, 1 error, 14 deselected, 3 warnings. Real failures: identical to Task 5's list: the 7 strict failures (`test_audited_document_meets_baseline_contract` ×4, `test_apple_trace_has_no_failures`, `test_legacy_character_normalization_has_no_c1_controls`, the chunker's `test_real_filing_item_1b_chunks_match_section_text`) and the setup error of `test_rcq_release_contract` (Task 7, then Task 10), and the 10 `test_fixture_reports_exactly_the_pinned_failures` pins (Task 10). Environment-only: the version test.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- Separator is a single space, as in the plain join and the ITEM branch; the line still starts with `PART III` and whitespace, so `PART_PATTERN` matches (spec 638-639); the section regex is unchanged.
- Second-order effect (spec 1071 accepts it): `_get_standard_sections` drops a part-only stub of at most 80 characters; R8's kept cells can lift such a stub over 80 characters, so it is kept as a `PART III` section without an item. CAT's stub already holds the TOC pages, so its boundaries do not change; no test pins the general case.
- `Parser._strip_page_breadcrumbs` strips a bare `PART X` line followed by an `ITEM` line at a page top; a PART line with kept cells is no longer bare and is not stripped.

**Review changes (2026-10-06):** the user accepted R8's section-extraction side effects as a named limitation (spec revision 17): a running page-top `Part II | Annual Report 2024` table is no longer stripped as a breadcrumb, so sections split; and a kept part-only stub changes `get_section` for a part without an item. Four characterization tests in `tests/test_section_extractor.py` pin both (task tests 102).

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 7: Header accounting in strict's numeric trace (R6a) (commit `9041958`, prototype `proto T7`)

**Spec:** R6a steps 2–4 (the render that supplied content, the exact table-to-output association, header capacity, misses incl. tables inside list items or inline wrappers, the remainders and multiset subtraction); "Interaction with strict and the completeness checks", "Strict"; Testing, "Strict (R6a)".

**Files:**
- Modify: `src/sec2md/quality.py` — `ElementHeaderRecord`, `HeaderLineLocation`, `locate_header_lines` and the optional `header_records` argument of `trace_numeric_failures`.
- Modify: `src/sec2md/parser.py` — records bound in `_element_segment_content` from the content-supplying render, the per-element trace with records, `header_accounting_misses`.
- Modify: `src/sec2md/table_parser.py` — `TableParser.__init__` sets `header_record = None`.
- Test: `tests/test_quality.py` — 99 additions (46 → 145).
- Test: `tests/test_parser.py` — 17 additions in `TestHeaderRecordBinding` (36 → 53) and constants `REPEATED_HEADER_TABLE`, `LABELS_TABLE`, `LINKED_LABELS_TABLE`, `EQUAL_TABLE`, `LABELS_HEADER`.
- Test: `tests/test_table_merge_headers.py` — 1 addition (158 → 159).

**Interfaces:**
- Consumes: `TableHeaderRecord` and `TableParser.header_record` (Task 5); `quality._normalized_numbers`.
- Produces:
  - `quality`: `@dataclass(frozen=True) class ElementHeaderRecord: segment: str; header_line: str; header_source: tuple[tuple[str, int], ...] = (); header_capacity: tuple[tuple[str, int], ...] = ()`; `HeaderMiss = Literal["missing", "ambiguous"]`; `@dataclass(frozen=True) class HeaderLineLocation: span: tuple[int, int] | None; miss: HeaderMiss | None = None`; `_whole_line_occurrences(content: str, segment: str) -> list[int]`; `locate_header_lines(content: str, records: Sequence[ElementHeaderRecord]) -> tuple[HeaderLineLocation, ...]`; `trace_numeric_failures(element: Element, nodes: Sequence[Tag], header_records: Sequence[ElementHeaderRecord] | None = None) -> tuple[str, ...]`.
  - `parser.Parser`: `_render_header_records: dict[int, tuple[Tag, TableHeaderRecord | None]]`, `_header_records: dict[int, ElementHeaderRecord]` (keyed by `id(original table node)`), `header_accounting_misses: tuple[str, ...]` (`"<element id>:missing"` / `"<element id>:ambiguous"`), all reset in `get_pages()`; `_bind_header_record(self, table: Tag, segment: str, record: TableHeaderRecord | None) -> None`; `_trace_elements(self, pages: List[Page]) -> None`; `_unbound_header_tables(self) -> Counter[str]`.
  - `TableParser.__init__`: `self.header_record: TableHeaderRecord | None = None`.

**Behaviour the tests pin:**
- `tests/test_quality.py`, unit tests:
  - Records `None` or `()` leave the trace unchanged (`("e1:2025",)` for the labels table).
  - A located header line within capacity leaves both pools: the labels table and Astra's source trace clean; Astra's counterexample (`| Revenue | 100 2025 | 200 |`) still fails `("e1:2025",)`.
  - A header excess is reported per token: `| Metric | 2025 2025 2024 | 2025 — Budget 2025 |` → `("e1:header:2024", "e1:header:2025")`.
  - Header source never covers a prose number (`… plan for 2025.` → `("e1:2025",)`); the subtraction is a multiset difference (the prose's own `2025` still traces; a recorded `7` the pool lacks leaves no negative count, `("e1:7",)`).
  - The header line is located only as its own segment's first line (an identical line elsewhere is not taken); the segment must occupy whole lines (`**segment**` → missing).
  - Failed association ×6 (segment not found, first line differs, segment twice; each over the no-excess and the ordinary-excess source): `locate_header_lines` reports `missing` or `ambiguous`, and the trace equals the ordinary trace (`()` or `("e1:2025",)` per copy).
  - A header line is consumed once (a segment that is a whole-line prefix of another, and identical records: both `ambiguous`); two tables in one element are accounted separately.
- `tests/test_quality.py`, Parser scenarios over capture ∈ {normal, capture} × links ∈ {plain, `<a href="#fy2025">`} × {alone, grouped with `<p>Revenue was reviewed against plan.</p>`} (84):
  - `test_r6a_legitimate_repetition_passes_strict` ×8: `| Metric | 2025 — Actual | 2025 — Budget |`, no failures, no misses, no warnings; the trace without records gives `<id>:2025`.
  - `test_r6a_astras_counterexample_fails` ×8: body mutated to `| Revenue | 100 2025 | 200 |` → `(<id>:2025,)`.
  - `test_r6a_invented_header_year_fails_as_a_header_excess` ×8: `… — Budget 2024` → `(<id>:header:2024,)`.
  - `test_r6a_extra_body_amount_fails` ×16: the surplus source (a lower `2025` written once) with body `100 2025` → `<id>:2025` while the ordinary trace passes; the labels source with `200 300` → `<id>:300`.
  - `test_r6a_prose_number_matching_only_a_header_number_fails` ×4 (grouped only): prose `plan for 2025.` → `<id>:2025`; the ordinary trace passes.
  - `test_r6a_missing_association_keeps_the_ordinary_trace` ×16 (separators rewritten to `|---|`): `(<id>:missing,)`, failures equal the ordinary trace.
  - `test_r6a_header_line_that_differs_from_its_record_is_a_missing_association` ×8 (literal `[Metric](basis)` in a th): `missing`, ordinary trace.
  - `test_r6a_ambiguous_association_keeps_the_ordinary_trace` ×16 (two identical tables merged into one element): two `ambiguous` misses, ordinary trace twice.
- `tests/test_parser.py::TestHeaderRecordBinding` (17): a table without links binds the normal render's record with the segment as it entered the element (×2 modes); a table with links binds the anchor-stripped re-render's record, the page still shows `[2025](#fy2025)` and `_render_header_records == {}` (×2); no record for a one-row table, a headerless table, a list-table re-render or an unreliable capture table (×4); a table inside a list item or `<b>` → `(<id>:missing,)` with the ordinary trace (×8: wrapper × source × mode); a repeated parse resets the accounting.
- `tests/test_table_merge_headers.py::test_header_record_is_none_until_a_render_writes_one`.

**Tests changed:** none.

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_quality.py tests/test_parser.py tests/test_table_merge_headers.py` → 357 passed
- Full suite at `9041958`: 1418 passed, 17 failed, 14 deselected, 3 warnings. Real failures, all fixed by Task 10:
  - The accuracy harness's own trace (`tests/accuracy/metrics.py::_oracle_trace_numeric_failures`, deliberately independent of production) has no header accounting yet and reports the repeated header tokens: `tests/accuracy/test_sec_accuracy.py::test_audited_document_meets_baseline_contract[aapl-2023-10k]`, `[nvda-2026-10k]`, `[nvda-2002-10k]` (`assert not ('sec2md-p…:2023', …)`), `::test_apple_trace_has_no_failures`, `::test_rcq_release_contract` (now a failure, no longer a setup error).
  - `tests/accuracy/test_sec_accuracy.py::test_audited_document_meets_baseline_contract[nvda-2026-q2-10q]`: `assert 0.988929889298893 >= 0.99` (financial-row recall; the amended metric is Task 10's).
  - The 10 pins (Task 10).
  - Environment-only: the version test.
  - Passing again from here: `test_legacy_character_normalization_has_no_c1_controls` and the chunker's Item 1B test.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- `ElementHeaderRecord` is a flat type in `quality` because `quality` cannot import `table_parser` (which imports `quality`), and only `Parser` knows the segment.
- Binding (spec 561-568): a table with links binds the anchor-stripped re-render's record with its `md().strip()` as the segment and pops the normal render's record; a table without links binds the normal render's record with the content after `MARKDOWN_LINK_RE.sub`. Unreliable capture tables, one-row tables and list tables have no record; a record whose `header_line` is `None` is not bound.
- Location (spec 571-576): the whole recorded segment is searched for, and an occurrence counts only on whole lines. Exactly one occurrence whose first line is the recorded header line is located; none, or a different first line, is `missing`; more than one is `ambiguous`; two records whose located spans coincide are both `ambiguous`.
- Trace (spec 577-608): header failures come first, records in order, tokens sorted, one string per excess occurrence; located lines are cut from the content as text (newlines stay, so no tokens fuse), ordered-list markers are then removed as before, and `available -= header_source` (Counter subtraction never goes negative).
- Misses (spec 579-590): `_trace_elements` runs `locate_header_lines` for misses and `trace_numeric_failures` for failures, so location runs twice per element with records. A table rendered inside a list item or an inline wrapper leaves its normal-render record unbound; `_unbound_header_tables` counts it against the element mapped to its nearest ancestor as `missing`, and discards a leftover with no mapped ancestor.
- `TableParser.__init__` sets `header_record = None` because `tests/test_table_completeness_fixtures.py::test_blank_table_renderer_is_detected` replaces `TableParser.md` and the new `_render_table` read the attribute; XLSX's bare `object.__new__(TableParser)` is unaffected.

**Review changes (2026-10-06):** the nested-table over-count found here was fixed at its root in Task 5's `_header_record`; this commit gains the Parser strict tests for it (10). After the final review it also gains 10 characterization tests for the fifth named limitation (spec revision 17): a table inside `<li>`, `<b>`, `<i>`, `<em>`, `<strong>` or a bold- or italic-styled inline element has no segment of its own, so R6a records a miss and a spanning header's repeated number (`Year Ended December 31,` → `31` twice) fails strict where `main` passed.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 8: Header-alignment source side and Markdown cell parser (commit `8a26ae4`, prototype `proto T8`)

**Spec:** Header-alignment check, "Source side" steps 1–6 (placed grid, R0 on visible text, value columns without the label column as revision 14 words step 3, discriminating headers with step 15, repeated headers, values, source and emitted paths, required entries, and the conflicting siblings of step 13) and "Output side" steps 7–9; interpretations round 1 ("Source cell text in the checker", "Year-like values", "Step 15's siblings", "Repeated-header detection"); revision 11's link-aware emitted path.

**Files:**
- Create: `src/sec2md/table_alignment.py` — the checker's source side and output side.
- Modify: `src/sec2md/table_completeness.py` — `place_unit` factored out of `header_row_count`; check 1's keys as `row_label_key` / `line_label_key`, used by check 1 itself; `unit_location` factored out of `TableFinding._where` (behaviour unchanged).
- Modify: `src/sec2md/table_parser.py` — `extract_cell_text` and `has_descendant` factored out of `_extract_cells` (behaviour unchanged).
- Test: `tests/test_table_alignment.py` — new, 43 tests.

**Interfaces:**
- Consumes: `OriginCell`, `OriginSlot`, `RowRoles`, `row_roles`, `row_values`, `is_complete_number`, `is_nil_value`, `is_year_like`, `visible_text` and the private `_FOOTNOTED` (Task 1); `table_completeness._PERIOD_TEXT`, `_GridCell`, `_Row`, `numbers`; `chunker.blocks.is_separator_row`; tests also use `TableParser`, `_origin_cells` (Task 3), `hidden_sets`, `unit_rows`.
- Produces:
  - `table_parser`: `has_descendant(node: Tag, name: str) -> bool`; `extract_cell_text(td: Tag, *, base_url: str | None = None) -> str`.
  - `table_completeness`: `row_label_key(texts: list[tuple[str, str]]) -> str`; `line_label_key(cells: list[str]) -> str`; `place_unit(table: Tag, rows: list[_Row], grid_hidden: set[int]) -> tuple[list[_Row], list[list[_GridCell | None]]] | None` (None = unreliable; no visible cells → `(rows, [])`); `header_row_count(...)` now through `place_unit`; `unit_location(ordinal: int, snapshot_ordinal: int | None, page: int | None) -> str` (`"table 24 (snapshot 19, page 41)"`).
  - `table_alignment`: `SEPARATOR = " — "`; `label_text_key(text: str) -> str`; `local_numbers(text: str) -> tuple[str, ...]`; `value_tokens(text: str) -> tuple[str, ...]`; `@dataclass(frozen=True, eq=False) class SourceCell: row: int; column: int; rowspan: int; colspan: int; text: str; header: bool = False; links: tuple[str, ...] = ()` (cached `key`, `columns()`, `rows()`); `@dataclass(frozen=True) class SourceGrid: slots: tuple[tuple[SourceCell | None, ...], ...]; row_trs: tuple[Tag | None, ...] = ()` (`height`, `width`, `origin_grid() -> list[list[OriginSlot]]`); `source_cell_text(td: Tag) -> str`; `source_cell_text_and_links(td: Tag) -> tuple[str, tuple[str, ...]]`; `place_source_grid(table, rows, grid_hidden) -> SourceGrid | None`; `source_grid(placed) -> SourceGrid | None`; `@dataclass(frozen=True) class SourceValue: row: int; column: int; text: str; tokens: tuple[str, ...]` (`nil`); `@dataclass(frozen=True) class PathEntry: key: str; text: str; cells: tuple[SourceCell, ...]; levels: tuple[int, ...]`; `@dataclass(frozen=True) class Expectation: column: int; path: tuple[PathEntry, ...]; required: tuple[str, ...]; need: Mapping[str, int]; conflicts: Mapping[str, str]` (`rendering()`, `expected_text()`); `class SourceAnalysis(grid: SourceGrid)` with `grid`, `origin`, `roles`, `values: dict[int, tuple[SourceValue, ...]]`, `value_columns: frozenset[int]`, `header_cells: tuple[SourceCell, ...]`, `covered_value_columns(cell)`, `is_discriminating(cell)`, cached `repeated_header: int | None`, `source_path(column)`, `emitted_path(column)`, `expectation(column)`; `split_cells(line: str) -> list[str]`; `cell_visible_text(raw: str) -> str`; `cell_tokens(texts) -> list[Counter]`; `@dataclass(frozen=True) class OutputTable: header: tuple[str, ...]; body: tuple[str, ...]; cells: tuple[tuple[str, ...], ...]; keys: tuple[str, ...]` (`header_text(index)`); `parse_output(segment: str) -> OutputTable | None`; `pair_rows(source_keys, key_counts, output) -> dict[int, int]`; `locate(tokens, cells) -> list[int]`; `line_cells(line) -> tuple[list[str], list[Counter]]`.

**Behaviour the tests pin** (`tests/test_table_alignment.py`):
- Placed grid: original coordinates with empty rows and columns kept, a colspan and a rowspan held by one object (`grid.slots[0][3] is spanning`), 4 × 4; hidden rows and cells skipped while `row_trs` maps each placed row to its `tr`; unreliable placement → `None` for a bad span, a span past the last row, a nested table.
- Cell text: `source_cell_text` reads `Net | income`, `Total revenue`, `Year Ended`, `2025 (a)`; `extract_cell_text` reads an image-only cell as `●`, a nested link as `[Note](#n) 3`, spans as `Year Ended`.
- R0 equivalence: the checker's placed grid (leading spacer column, blank row, span-covered label slot, linked label) → label column 1, header rows (0, 2), data rows (3, 4, 5), empty rows (1,); the renderer's cleaned grid gives the same rows per role and the same label texts `["", "", "Segment A", None, "Total"]`.
- Values: bare years beside a row label make a data row but are not values (`values[1] == ()`); split negatives sit at the digit column (`[(2, "(29)", ("-29",)), (4, "(40)%", ("-40",))]`); `.75` → `("0.75",)`, `(.62)` → `("-0.62",)`, `2.1(1)` → `("2.1",)`, `3.5 %- 4.3 %` → `("3.5", "4.3")`, `—` → nil with no tokens; `value_tokens` ×6 (`$ 1,234`, `RMB 941,168`, `€ (1,234)`, `3,984 *`, `36.5 %`, `—`); identifier-column numbers are never values.
- Repeated header: a `2023 | 2022` row after the first data row → `repeated_header == 3`; a data row and a section label are not repeated headers.
- Discriminating cells: in `Year ended March 31,` over `2025 | 2024` over `RMB | RMB | US$`, the caption, `2024` and `US$` are discriminating; `(In millions)` over every value column and `Item` over none are not; `RMB` over every period is not (step 15), while `RMB` beside `US$` is.
- Paths and expectations: column 1's emitted path `Year ended March 31, — 2025 — RMB`; column 3 renders `2024 — US$`, needs `{"2024": 1, "us$": 1}`, conflicts `{"2025": "2025", "rmb": "RMB"}`; a rowspan cell appears once and adjacent equal texts collapse into one entry keeping both cells and levels; `A — B — A` keeps three entries (`need == {"a": 2, "b": 1}`); equal labels with different links stay two entries (`need == {"plan": 2}`), with the same link one; a child `2024` under the `2025` group is needed and `2024` also listed as a conflict (`{"2023", "2024", "actual"}`); a single value column has no required entry.
- Output side: `label_text_key("  Year\xa0 Ended  [June 30,](#fy) ") == "year ended june 30,"`; `split_cells` ×6 keeps blank cells, escaped pipes and pipes in link destinations; `cell_visible_text` reads labels and unescapes pipes; `cell_tokens` rebuilds split negatives at the digit cell; `parse_output` reads header, body lines, visible cells and keys (`("revenue", "notecost#3", "ab", "total")`; `A\|B` keys as `ab`), `None` without a separator; pairing needs a unique label on both sides (`{1: 0}`); `locate` returns every cell holding all tokens (`[1, 2]` for `100`, `[6]` for the range).

**Tests changed:** none.

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_table_alignment.py tests/test_table_completeness.py` → 108 passed, 1 warning in 4.62 s (wall 5.4 s); the warning is the existing `XMLParsedAsHTMLWarning` of `tests/test_table_completeness.py::test_header_row_count_matches_snapshots_on_a_fixture`
- Full suite at `8a26ae4`: 1461 passed, 17 failed, 14 deselected, 3 warnings. Real failures: identical to Task 7's list, all fixed by Task 10: `tests/accuracy/test_sec_accuracy.py::test_audited_document_meets_baseline_contract[aapl-2023-10k]`, `[nvda-2026-10k]`, `[nvda-2002-10k]` (the harness's own trace), `[nvda-2026-q2-10q]` (financial-row recall 0.9889 < 0.99), `::test_apple_trace_has_no_failures`, `::test_rcq_release_contract` (harness trace), and the 10 `test_fixture_reports_exactly_the_pinned_failures` pins. Environment-only: the version test.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- Visible cell text is `extract_cell_text` with links reduced to labels and zero-width characters removed; `\|` is unescaped only in cells with a link, where `render_cell_content` escapes pipes (interpretation, spec 98). A DOM walk would read `<span>Year</span><span>Ended</span>` as `YearEnded`; pinned.
- Value columns leave out the label column (`SourceAnalysis.value_columns`, `table_alignment.py:286-288`, built from the values, which step 5 takes outside the label column). Revision 14's step 3 says so (spec 695-700: "Value columns are the grid columns other than the label column that hold a complete number in a data row. An identifier column's numbers are row labels, not values."; resolved); `test_label_column_numbers_are_never_values` pins it.
- Values come from R0 data rows only; bare years beside a row label make a data row but are not values (interpretation, spec 99); tokens drop footnote markers, keep both range numbers and read `.75` as `0.75`.
- Repeated header (spec 701-705): a row after the first data row, not in the header zone, with no complete number outside the label column and with `_PERIOD_TEXT` or a year-like value in any column (interpretation, spec 101). Data rows are not exempt, so a nil-only row with period text counts.
- Step 15 (interpretation, spec 100): siblings are the other cells of the cell's header rows that cover a value column; a cell with at least one sibling, all with its text, is not discriminating; with no sibling, step 3 decides.
- Conflicting siblings (spec 765-770): every discriminating cell in a header row of a represented cell with a different key; "covers different value columns" holds by construction, since distinct cells of one row occupy disjoint columns.
- Cell parser (spec 725-730): only link destinations are protected, so a pipe inside a link label splits (the renderer always escapes label pipes); the header line is the line right before the separator.
- Pairing: source keys are check 1's own; output keys are `line_label_key` over the position-preserving parser with split negatives rebuilt. Check 1's own output split would key `A\|B` as `a`; it is left unchanged in check 1.
- Locating (spec 734-738): a cell holds a value when its token multiset contains the value's tokens; every cell, the label cell included, counts.
- The `table_completeness` and `table_parser` refactors keep behaviour: check 1 calls the same key functions, and `has_descendant` is `node.find(name)` without bs4's filter cost.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 9: Header-alignment matching, coverage and diagnostics (commit `ac2b1f0`, prototype `proto T9`)

**Spec:** Header-alignment check, "Matching" steps 10–15 with "Evaluation is bounded", the failing and passing controls; "Findings and coverage" (finding format, at most 10 per table plus the total, the two trailing `ParseDiagnostics` fields, the 21 keys, precedence, reconciliation, an empty tuple meaning the check did not run, plumbing inside the guarded `check_tables()` call, policy `off`); Testing, "The alignment check" with the header-retention audit on the matching controls (spec 1010-1011); "Interaction with strict and the completeness checks", check 1's header role next to R0 (spec 916-917); revision 14's global early stop (spec 790-791); interpretations round 2 ("Cell texts in the checker", "Link-aware equality" with the same base URL).

**Files:**
- Modify: `src/sec2md/table_alignment.py` — the bounded matcher (`judge`, with the global early stop), coverage keys, findings, per-value outcomes and `align_table`; `cell_texts` and `base_url` threaded through the source side.
- Modify: `src/sec2md/table_completeness.py` — `check_tables` runs the check for every visible outermost unit with one shared placement; `TableCompletenessReport.alignment` and `.alignment_coverage`; `placed_header_rows`; `has_descendant` in `place_unit`.
- Modify: `src/sec2md/quality.py` — the two trailing `ParseDiagnostics` fields and their `build_diagnostics` pass-through.
- Modify: `src/sec2md/parser.py` — `_cell_texts` recorded by `_render_table` (checks on only) and passed with `base_url=self.source_url` to `check_tables`.
- Modify: `src/sec2md/table_roles.py` — `visible_text` ASCII fast path (performance only).
- Test: `tests/test_table_alignment.py` — 71 additions (43 → 114).
- Test: `tests/test_quality.py` — 1 addition (145 → 146) and 2 tests extended.
- Test: `tests/test_table_completeness_fixtures.py` — 7 additions (26 → 33).
- Test: `tests/test_table_completeness.py` — 2 tests changed.

**Interfaces:**
- Consumes: everything Task 8 produced (`SourceAnalysis`, `Expectation`, `source_grid`, `parse_output`, `pair_rows`, `locate`, `cell_tokens`, `label_text_key`, `place_unit`, `row_label_key`, `unit_location`); `has_descendant`, `extract_cell_text` (Task 8); `TableParser.cells` with `Cell.node` (Task 5).
- Produces:
  - `table_alignment`: `MAX_STATES = 100_000`; `_CONSISTENT, _INCONSISTENT = 1, 2`, `_BOTH = 3`; `Outcome = Literal["aligned", "misaligned", "ambiguous", "budget"]`; `@dataclass(frozen=True) class Verdict: outcome: Outcome; states: int = 0; conflicting: tuple[str, ...] = ()`; `header_atoms(header: str) -> list[str]`; `judge(header: str, expectation: Expectation, *, max_states: int = MAX_STATES) -> Verdict` (a `seen` bitmask of the verdicts met at any terminal or memo hit; `ambiguous` as soon as it holds both); `COVERAGE_KEYS` (21 keys, spec order); `MAX_LISTED = 10`; `coverage_items(coverage: Mapping[str, int]) -> tuple[tuple[str, int], ...]`; `@dataclass(frozen=True) class Misalignment: row: int; column: int; label: str; tokens: tuple[str, ...]; header: str; expected: str; conflicting: tuple[str, ...] = ()` with `message(where) -> str`; `@dataclass(frozen=True) class ValueOutcome: row: int; column: int; outcome: str; line: int | None = None; output_column: int | None = None`; `@dataclass(frozen=True) class TableAlignment: coverage: Counter; misalignments: tuple[Misalignment, ...] = (); outcomes: tuple[ValueOutcome, ...] = ()` with `messages(where) -> tuple[str, ...]`; `align_table(table, rows, grid_hidden, segment, row_keys, key_counts, *, placement=None, max_states=MAX_STATES, cell_texts=None, base_url=None) -> TableAlignment`. Changed signatures: `source_cell_text_and_links(td, extracted: str | None = None, *, base_url=None)`, `place_source_grid(table, rows, grid_hidden, *, base_url=None)`, `source_grid(placed, cell_texts: Mapping[int, str] | None = None, *, base_url=None)`.
  - `table_completeness`: `placed_header_rows(placed) -> int`; `header_row_count(table, rows, grid_hidden) -> int` (= `placed_header_rows(place_unit(...))`); `@dataclass(frozen=True) class TableCompletenessReport: tables_checked: int; findings: tuple[TableFinding, ...]; alignment: tuple[str, ...] = (); alignment_coverage: tuple[tuple[str, int], ...] = ()`; `check_tables(soup, table_outputs, table_pages, snapshot_ordinals, *, cell_texts: Mapping[int, str] | None = None, base_url: str | None = None) -> TableCompletenessReport` (imports `table_alignment` inside the function, which imports this module).
  - `quality.ParseDiagnostics`, trailing: `table_header_alignment: tuple[str, ...] = ()`, `table_header_alignment_coverage: tuple[tuple[str, int], ...] = ()`; `build_diagnostics` fills them from `table_report` or `()`.
  - `parser.Parser._cell_texts: dict[int, str]` (`id(td)` → the render's link-free extracted text; reset per `get_pages`).
  - Test-only helpers in `tests/test_table_alignment.py`: `retention_audit(html, markdown) -> (values, value_misses, cell_misses)` (reads `table_completeness._direct_cells`, `cell_text`, `row_label_key`), `_row(*cells, tag="td")`, `CHECK_ONE_HEADER_ROWS`, `_sibling_expectation(count)`.

**Behaviour the tests pin:**
- `tests/test_table_alignment.py` (every `check()` call asserts the 21 keys in order and the four reconciliation identities; `WHERE` is `table 1 (snapshot 2, page 3)`):
  - An aligned table is silent (`|  | 2025 | 2024 |`, 4 values aligned); a shifted header is reported: `"Revenue" 100 under "2024"; expected "2025"`, `"Revenue" 90 under ""; expected "2024"` and the same for `Cost` (4 misaligned).
  - Failing mutations: merged sibling headers `|  | 2025 — 2024 | 2024 |` → `"Revenue" 100 under "2025 — 2024"; expected "2025", conflicting "2024"` (2 misaligned, 2 aligned); both columns carrying `2025 — 2024` → 4 findings with the conflicting sibling named; a value swap under plain and under combined labels; `Unadjusted` over the `Adjusted` value (`expected "Adjusted"`, 4 misaligned); `A — B` over the path `A — B — A` → `expected "A — B — A"`; a suppressed `[Plan](ex101.htm)` over `Plan — Plan` (different links) → `expected "Plan — Plan"`.
  - Passing controls ×6, each also rendered by the prototype `TableParser` to exactly the Markdown checked: literal `Income — net`, child `2024` under the `2025` group (`2025 — 2024`), Astra's R6a source (`| Metric | 2025 | 2025 — Budget |`), an adjacent duplicate, a rowspan cell, Astra's three-column hierarchy (`Income — net | Income — gross | Other — Income — net`); the hierarchy judged per column (`judge("Income — net", column 3)` and `judge("Other — Income — net", column 1)` are misaligned).
  - `2025 — Restated` over 2025's values → `value_ambiguous_header` 2; a non-discriminating caption and `RMB` over every period are never required.
  - Bounded search: 30 separators, all inconsistent → misaligned with `31 < states < MAX_STATES`, and the same header with `max_states = states - 1` → `Verdict("budget", states - 1)`; a 12-level path with a trailing `Note` → `ambiguous` within 16 states; 30 conflicting siblings → `Verdict("budget", 100000)` and, through `check_tables`, `value_unevaluated_budget` 1 with the other 30 values aligned; global early stop (`test_search_stops_as_soon_as_both_verdicts_are_reachable_from_the_start[15-10269|19-97250]`): header `A — B — C1 … Cn`, required `a — b`, n conflicting siblings each needed once → `Verdict("ambiguous", 10269)` for 15 and `Verdict("ambiguous", 97250)` for 19, under the bound (the per-frame stop needed 17,991 states and hit the bound at 170,625).
  - Header-retention audit (`retention_audit`, built on production `SourceAnalysis` and `align_table` outcomes): `test_header_retention_audit_holds_on_every_matching_control` ×6 (every located value's header equals its emitted-path rendering and every header-zone cell is represented); `test_header_retention_audit_permits_adjacent_suppression` (Astra's source → `(1, "2025", "2025")`, `(2, "2025 — Budget", "2025 — Budget")`, no misses); `test_header_retention_audit_reports_an_unrelated_header_loss` (the 2025 span lost over its first column → value miss `(2, 1, "Actual", "2025 — Actual")` and cell miss `["Actual"]`; `Other` lost from every column → `(1, 2, "", "Other")` and `["Other"]`).
  - Check 1's header role (`test_check_one_header_rows_next_to_r0_on_named_tables` ×6, `CHECK_ONE_HEADER_ROWS`): `header_row_count` against R0's zone on the checker's placed grid and on the renderer's grid: crm-26 0 vs (0, 1); jpm-109 0 vs (); aapl-18 0 vs (); nvda-2026-10k-17 3 vs (0, 1, 2); th-row 1 vs (0,); unit-caption-years-row 0 vs (0,) (check 1's period test needs an empty label cell; spec F11).
  - Parser and token controls aligned: blank columns, split negatives in both shapes, `.75` / `(.62)`, linked labels, escaped pipes.
  - Table skip keys take the first applicable key (no output over an unreliable grid, no separator over an unreliable grid, bad span, nested table, headerless, text table); row skip precedence (below a repeated header before unpaired); value skip precedence (all six value keys reachable, in order).
  - Value outcomes name each value's skip key, paired line and output column, aligned and misaligned values, and row keys for skipped rows; a skipped table has none.
  - A completed run with nothing eligible records 21 zeros (soup and `Parser`); 12 findings are listed as 10 plus `12 misaligned values in total, 10 listed`.
  - `main`'s BABA 24 Markdown (`|  | 2023 | 2024 | 2025 |  |  |`) → 4 findings (`"Revenue" 868687 under "2024"; expected "2023 — RMB"`, …, `"Revenue" 137300 under ""; expected "2025 — US$"`); the prototype's BABA 24 rendering is aligned.
  - `Parser` records findings and coverage in `ParseDiagnostics`; `check_tables` places each unit once; the alignment check reuses passed cell texts and extracts link cells itself (a changed map text changes the expectation); `Parser` records the link-free texts of its render; link destinations resolve against the render's base URL (`[Plan](https://…/ex101.htm)` over `[Plan](./ex101.htm)` aligned with `base_url`, reported without it); without a base URL both sides compare raw destinations; `Parser` checks links against its `source_url`.
  - A forced exception inside `align_table` leaves `table_report` `None` and both fields `()`; policy `off` never runs the check and leaves `()`.
- `tests/test_quality.py::test_build_diagnostics_carries_header_alignment_findings_and_coverage`: a report with one finding and 21 coverage pairs passes through unchanged, no warnings.
- `tests/test_table_completeness_fixtures.py::test_header_alignment_reports_nothing_on_the_fixtures` ×7: no findings in either mode, coverage pinned per fixture in `ALIGNMENT_COVERAGE` and equal across modes (for example aapl-2023-10k `(66, 8, 1, 0, 5, 5, 47, 423, 15, 159, 249, 758, 51, 30, 0, 30, 0, 0, 647, 647, 0)`), `tables_total` equal to the visible outermost tables.
- Repeated headers by year-like value (revision 15):
  - `test_year_like_mid_table_row_is_a_repeated_header[footnoted|fiscal-range]`: a mid-table `2024(a) | 2023(a)` or `2024–25 | 2023–24` row at row 2 is a repeated header, so rows 3 and 4 are `row_below_repeated_header` (3 data rows, 2 below, 1 paired, 2 values aligned).
  - The control `test_mid_table_row_with_an_amount_beside_a_fiscal_year_range_is_not_a_repeated_header`: `Fiscal 2024–25 adjustment | 15 | 13` is a data row, and all 8 values are aligned.
  - The link-aware emitted path is pinned by Task 8's `test_adjacent_equal_labels_with_different_links_stay_separate_entries` and this task's `test_equal_labels_with_different_links_need_both_occurrences`.

**Tests changed:**
- `tests/test_table_completeness.py::test_check_tables_excludes_header_rows_from_row_structure` and `::test_check_tables_skips_hidden_and_token_free_tables`: compared the whole report with `TableCompletenessReport(n, ())`; the report now also carries alignment coverage, so they compare `(tables_checked, findings)` (the second also asserts the text table counts as `table_no_output`).
- `tests/test_quality.py::test_parse_diagnostics_positional_construction_keeps_working` and `::test_build_diagnostics_without_table_report_skips_all_three_checks`: extended with the two `()` assertions for the new fields.

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/test_table_alignment.py tests/test_quality.py tests/test_table_completeness.py tests/test_table_completeness_fixtures.py` → 348 passed, 10 failed, 1 warning. The 10 failures are the `test_fixture_reports_exactly_the_pinned_failures` cases (the pins Task 10 empties); the warning is the existing `XMLParsedAsHTMLWarning` of `tests/test_table_completeness.py::test_header_row_count_matches_snapshots_on_a_fixture`. With `tests/test_table_completeness_fixtures.py::test_header_alignment_reports_nothing_on_the_fixtures` in place of the whole fixtures file: 332 passed, 1 warning in 22.24 s (wall 23.1 s)
- Full suite at `ac2b1f0`: 1540 passed, 17 failed, 14 deselected, 3 warnings. Real failures: identical to Task 7's and Task 8's list, all fixed by Task 10: `test_audited_document_meets_baseline_contract[aapl-2023-10k]`, `[nvda-2026-10k]`, `[nvda-2002-10k]` (harness trace), `[nvda-2026-q2-10q]` (financial-row recall), `test_apple_trace_has_no_failures`, `test_rcq_release_contract` (all in `tests/accuracy/test_sec_accuracy.py`), and the 10 `test_fixture_reports_exactly_the_pinned_failures` pins. Environment-only: the version test.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- Exact path rendering (spec 748-752) is `label_text_key(header) == label_text_key(expectation.rendering())`.
- Segmentations (spec 753-758): the header's visible text, whitespace collapsed and case folded, splits at every ` — `; only the relevant labels (required and conflicting-sibling keys) are looked up, which is what the verdict depends on, and a segment longer than the longest relevant key is skipped.
- Search (spec 782-797): an iterative depth-first search over `(position, capped counts)` with counts capped at `need + 1`; a state is counted when created, the start and the terminals included; creating state `max_states + 1` abandons the search as `Verdict("budget", max_states)`, never aligned.
- Global early stop (spec 790-791; resolved in round 5): `judge` (`table_alignment.py:605-638`) ORs every verdict it meets, at a terminal or a memo hit, into `seen` and returns `ambiguous` as soon as `seen` holds both; every visited state is reachable from the start, so this is the spec's stop. The per-frame `reachable == _BOTH` pop and the final `memo[start] == _BOTH` branch are gone; without both, `memo[start]` holds exactly one verdict (`table_alignment.py:639-642`). My differential check (`plan-checks/judge_diff.py` in the acceptance folder: 5,000 random headers and expectations, `28298ff`'s judge against `8f4991e`'s (round 6 changed tests only, so `ac2b1f0`'s judge is the same code), at bounds 200 and 100,000) found no changed outcome or conflicting text, and the new judge never created more states; on the round-4 probe (`plan-checks/early_stop_probe.py`) it now equals my independent global-stop search state for state (10,269 and 97,250). The 19-sibling case lands 2.75% under the bound (97,250): the search finishes the all-inconsistent subtree under `A` before it tries `A — B`. The corpus still has no budget value (REPORT-round5.md).
- Header-retention audit tests (spec 1010-1011): the audit is a test helper, not production code (acceptance has its own implementation in `analyze_candidate.py`). It counts a header-zone cell as represented when a column the cell covers has an emitted-path rendering equal to some output header, which allows R6's adjacent suppression and nothing else.
- Check 1's header role (spec 916-917): the pins sit in Task 9, beside the `check_tables` integration, and assert both R0 zones, so a renderer-checker difference would also fail them.
- Verdicts are cached per (source value column, output column) inside a table: values of one column under one header share one search, and each still counts under its own key.
- Findings (spec 829-836): the label is the row's first non-empty visible origin text; `expected` is the required entries in path order; `conflicting` lists the conflicting-sibling texts found in excess in some segmentation that meets every requirement, which reproduces both spec examples; findings are in source order.
- Precedence (spec 866-867) is `align_table`'s code order, which is `COVERAGE_KEYS` order; `tables_total` counts every visible outermost unit, including those check 1 skips as token-free, because the check runs before check 1's token test.
- Plumbing (spec 879-880): one `functools.cache` placement per unit is shared with check 1 (`placed_header_rows(placement())`); the existing try/except in `Parser.get_pages` (skipped when `table_checks` is False) leaves `table_report = None`, so both fields are `()`.
- Cell texts (interpretation, spec 160): `_render_table` records `cell.text` by `id(cell.node)` only for cells whose text holds no `](`; link cells are extracted by the checker itself against `base_url` (interpretation, spec 162). Corpus runs use `Parser(html)` without a source URL.
- `ValueOutcome` and `TableAlignment.outcomes` go beyond the spec's diagnostics; the acceptance tooling reads them for the per-value identity comparison (spec 1087-1096).
- `visible_text`'s fast path (`text.isascii() and "[" not in text` → `text.strip()`) is behaviour-preserving: zero-width characters and U+00A0 are non-ASCII and a link needs `[`.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 10: Regressions, accuracy guards, chunking tests and release notes (commit `b229b8d`, prototype `proto T10`)

**Spec:** Acceptance criteria, "Fixtures" (`PINNED_FAILURES` empty, check 2, mutations, rendering with checks on and off) and "Accuracy suite" (R6a accounting in the suite's own trace with its own tokenizer from the records' header-zone cell texts; the financial-row metric treating header rows as R6 renders them; "Body rows must not drop" over every row with origin text, each move listed and checked as header-zone); "Interaction with strict and the completeness checks", "Pinned failures"; Testing, "Integration" (chunked tables) and "Regression guards"; "Release", with revision 14's release-text point (marker-only columns in the fusion count); interpretations round 1 ("Header cell texts for the accuracy suite", "Body-row guard baseline", "Golden files", "RCQ version") and round 2 ("Body-row guard": per-signature counts).

**Files:**
- Modify: `src/sec2md/table_parser.py` — `TableHeaderRecord.header_cells` (trailing field), filled by `_header_record`.
- Modify: `src/sec2md/quality.py` — `ElementHeaderRecord.header_cells` (trailing field).
- Modify: `src/sec2md/parser.py` — `_bind_header_record` copies `header_cells`; `Parser.element_header_records(element_id)`, now also used by `_trace_elements` (behaviour unchanged).
- Modify: `src/sec2md/__init__.py`, `pyproject.toml` — version `0.1.22+rcq.4`.
- Modify: `tests/accuracy/metrics.py` — R6a accounting in `_oracle_trace_numeric_failures` (own locator, own tokenizer), the amended financial-row metric, the body-row guard's helpers, `_parse_document`.
- Create: `tests/accuracy/generate_body_row_baseline.py` — writes the guard's baseline by rendering with a baseline checkout's `src` and measuring with this checkout's `metrics.py`.
- Create: `tests/accuracy/body_rows_main.json` — the baseline generated from `c674828`: 2,485 rows (aapl-2023-10k 537, nvda-2026-10k 621, nvda-2002-10k 612, nvda-2026-q2-10q 449, nvda-2026-08-26-8k 9, nvda-2026-ex99-1 166, nvda-2026-ex99-2 91). Review fix: the prototype committed 2,492 rows from the older set semantics.
- Modify: `CHANGELOG.md` (new `## 0.1.22+rcq.4 (unreleased, pending review)`), `README.md` (version line, quality section, "Complex Table Handling"), `docs/usage/direct-conversion.md` ("Table header lines", "Header alignment"); revision 14's wording: marker-only columns leave the second-row fusion count, and equal header texts compare ignoring case and spacing.
- Test: `tests/accuracy/test_sec_accuracy.py` — 32 additions (41 → 73) and `HEADER_ZONE_MOVES` (165 rows after review: nvda-2026-10k 48, nvda-2002-10k 41, nvda-2026-q2-10q 38, nvda-2026-ex99-1 24, nvda-2026-ex99-2 14; the prototype listed 172).
- Test: `tests/test_chunker.py` — 5 additions in `TestChunkedFusedHeaderTables` (50 → 55).
- Test: `tests/test_table_merge_headers.py` — 15 additions (159 → 174).
- Test: `tests/test_parser.py` — 2 additions (53 → 55) and 2 tests changed.
- Test: `tests/test_models.py`, `tests/test_table_completeness_fixtures.py` — changed (below).

**Interfaces:**
- Consumes: `TableHeaderRecord`, `_header_record`, `column_header_cells` (Tasks 4–5); `ElementHeaderRecord`, `_bind_header_record`, `_header_records`, `_trace_elements` (Task 7); `TableParser.source_grid` and `.roles` (Task 4) in the move check; `Parser.get_pages(include_elements=True)` and its elements and offsets (chunker tests).
- Produces:
  - `TableHeaderRecord.header_cells: tuple[tuple[str, int], ...] = ()` — each header-zone cell with text, in document order, as `(pool text, output columns whose header it covers)`; `header_source` and `header_capacity` are computed exactly as before.
  - `ElementHeaderRecord.header_cells: tuple[tuple[str, int], ...] = ()`.
  - `Parser.element_header_records(self, element_id: str) -> tuple[ElementHeaderRecord, ...]` — the bound records of the tables mapped to one element, in mapped-node order; `()` for an unknown element; valid after `get_pages(include_elements=True)`.
  - `sec2md.__version__ == "0.1.22+rcq.4"`.
  - `tests/accuracy/metrics.py`: `_oracle_whole_line_starts(content, segment) -> list[int]`; `_oracle_header_line_spans(content, records) -> list[tuple[int, int] | None]`; `_oracle_header_tokens(record) -> tuple[Counter, Counter]` (source, capacity; harness tokenizer); `_oracle_trace_numeric_failures(element, nodes, header_records: Sequence = ()) -> tuple[str, ...]`; `_mapping_and_trace(pages, annotated_html, header_records: Mapping[str, Sequence] | None = None)`; `_is_table_line(line) -> bool`; `_header_line_indexes(lines) -> set[int]`; `extract_header_lines(markdown) -> list[tuple[str, tuple[str, ...]]]`; `_body_markdown(markdown) -> str`; `source_soup(source) -> BeautifulSoup`; `_link_aware_source_row_positions(source)`; `_in_header_line(row, header_lines) -> bool`; `_financial_row_recall(source, actual, header_lines=()) -> float`; `@dataclass(frozen=True, order=True) class SourceRow: table: int; row: int; cells: tuple[str, ...]` (`key`: whitespace-free signature); `text_source_rows(source) -> tuple[SourceRow, ...]`; `body_line_counts(markdown) -> Counter`; `body_matched_rows(source, markdown) -> tuple[SourceRow, ...]`; `_in_header_line_cells(cells, markdown) -> bool`; `_render(source) -> tuple[Parser, list[Page]]`; `_markdown_of(pages) -> str`; `_parse_document(source) -> tuple[str, bytes, str, list[Page], ParseDiagnostics, dict[str, tuple]]`; `_parse_once(source)` = `_parse_document(source)[:5]`.
  - `tests/accuracy/generate_body_row_baseline.py`: `main(argv: list[str] | None = None) -> None` with `--src` (required), `--commit` (default `c674828`), `--out`.

**Behaviour the tests pin:**
- `tests/accuracy/test_sec_accuracy.py`, harness trace (11):
  - The labels table's repeated `2025` traces with its record (`("e1:2025",)` without); `| Metric | 2025 — Actual | 2025 — Budget 2024 |` → `("e1:header:2024",)`; a header line that lost the spanning `2025` to the body → `("e1:2025",)` with the record (`()` without); the surplus lower `2025` never covers a body `2025`; Astra's counterexample → `("e1:2025",)`, the faithful table `()`.
  - A record not located (segment not found, first line differs) keeps the ordinary trace; two records claiming one line are located for neither.
  - Capacity uses the harness tokenizer: `(As restated – see Note 2)` reads `["2"]` for the harness and `()` for strict; with the record the trace is `()` (without: `("e1:2",)`).
  - `audit_document(..., quality_policy="strict")` on the labels table (plain and linked) has no trace failure and reads the parser's records through `_parse_document`; the ordinary harness trace gives `<id>:2025`.
- Financial rows (4): `extract_header_lines` reads the line before each delimiter row (cells joined, numbers); a source header row fused into a header line counts (`1/3` → `1.0` with header lines); every number of the row must sit in one header line, with its label text; body rows still match exactly (a body line is never searched for label text).
- Body-row guard (17): the baseline names `c674828`, covers every fixture and holds only current source rows; per fixture (×7) `Counter(main keys) - Counter(candidate keys) == Counter(HEADER_ZONE_MOVES keys)`, so a new loss and a vanished move both fail; per fixture with moves (×5) every listed move is an R0 header row of `TableParser(table).roles` (found by the row's cell nodes in `source_grid`) and appears in a candidate header line; `text_source_rows` covers every row with visible text (links reduced, U+200B removed, an image as `●`, hidden rows and cells left out); `body_matched_rows` leaves out header lines (round 1's promoted `Common Stock | AAPL` is not body-matched), counts rows that share a signature (one of two identical rows moved is one loss), and signatures ignore cell boundaries, whitespace, links and escapes.
- `tests/test_chunker.py::TestChunkedFusedHeaderTables` (5): the renderer writes `|  | Year Ended — 2025 — (In millions) | Year Ended — 2024 — (In millions) |  |` with empty label and note headers, and the element's offsets cite it; with `chunk_size=128, max_table_tokens=128` every part keeps its rows in order, repeats the caption, header line and separator in full, keeps 4 cells per line, cites the table's page span, and an over-budget row is kept whole with its prefix (`estimate_tokens(...) > 128`).
- `tests/test_table_merge_headers.py` (15): Astra's source → `header_cells == (("2025", 2), ("Item", 1), ("2025", 1), ("Budget", 1))`; headerless → `()`; for each of the 13 per-class tables, `header_cells` re-tokenized with strict's tokenizer reproduces `header_source` and `header_capacity`.
- `tests/test_parser.py::TestHeaderRecordBinding::test_element_header_records_returns_the_records_bound_to_an_element[normal|capture]`: the element's records equal the bound record; an unknown id gives `()`.

**Tests changed:**
- `tests/test_table_completeness_fixtures.py::PINNED_FAILURES`: all seven fixtures `{}` (the 10 losses were class 1 and R1 keeps them; per-pin evidence in [`plan-checks/pin_evidence.txt`](../audits/2026-10-06-table-merge-header-acceptance/plan-checks/pin_evidence.txt)); the comment is rewritten. `TABLES_CHECKED` and the mutation counts are unchanged.
- `tests/test_models.py::test_internal_version_matches_distribution`: `rcq.3` → `rcq.4` (release bump).
- `tests/test_parser.py::TestHeaderRecordBinding::test_table_without_links_binds_the_normal_render_record` and `::test_table_with_links_binds_the_anchor_stripped_render_record` (×2 modes): the expected `ElementHeaderRecord` gains `header_cells=LABELS_HEADER_CELLS` (`(("Metric", 1), ("2025", 2), ("Actual", 1), ("Budget", 1))`).
- `tests/accuracy/test_sec_accuracy.py` and `tests/accuracy/metrics.py`: the existing contract tests keep their thresholds and baseline numbers, but measure through the amended harness: the trace applies R6a with the parser's records, and financial-row recall credits header lines (spec 1040-1061).

**Verification:**
- Task tests: `venv/Scripts/python -m pytest -q tests/accuracy/test_sec_accuracy.py tests/test_chunker.py tests/test_table_merge_headers.py tests/test_parser.py tests/test_models.py tests/test_table_completeness_fixtures.py` → 411 passed, 2 warnings; both warnings are the existing `XMLParsedAsHTMLWarning`s of `tests/test_chunker.py::TestChunkSectionIsolation::test_real_filing_item_1b_chunks_match_section_text`
- Full suite at `b229b8d`: 1611 passed, 14 deselected, 3 warnings. No failure: the six accuracy failures, the ten pins and the version test (the tree now pins rcq.4, as the venv's metadata says) pass.
- `venv/Scripts/python -m ruff check src tests` → All checks passed!

**Review points:**
- `header_cells` (interpretation, spec 102): the spec says the suite "takes the header-zone cell texts from the parser's per-table header records", which held only strict-tokenized multisets, so both records gain the trailing field and `Parser.element_header_records` is the public read path. A test pins that the field reproduces production's `header_source` and `header_capacity` on all 13 per-class tables.
- Harness independence: the harness reads only `segment`, `header_line` and `header_cells`, locates header lines itself (whole-line segment exactly once, first line equal, a span two records claim is located for neither: R6a step 3's contract, not production's code) and tokenizes with `normalize_numbers`; it never reads `header_source` or `header_capacity`.
- Amended metric (spec 1046-1050): a header line is a Markdown table line right before a delimiter row; a source key is present when one header line holds its canonical label as a substring of `" | ".join(cells)` (whitespace collapsed, case kept) and its numbers as a sub-multiset. Without `header_lines` the function is the old metric.
- Body-row guard (spec 1051-1060; interpretation round 2): a committed baseline of 2,485 body-rendered rows (2,492 before review) (`SourceRow(table, row, cells)`, signatures compared as multisets) and 165 listed moves (172 before review). The guard runs in the normal suite without a `main` checkout; the generator renders with the baseline's `src` (main has no `element_header_records`) and measures with this checkout's `metrics.py`, with an import-location check.
- The spec's interpretation row (spec 103, revision 14; resolved) now describes this guard: 2,485 rows counted per text signature (revision 17; 2,492 before review) (`tests/accuracy/body_rows_main.json`) and 165 allowed moves (`tests/accuracy/test_sec_accuracy.py:565` after review); revision 10's 1,550-row version is kept as history.
- Version (interpretation, spec 105): `0.1.22+rcq.4`, changed where the rcq.3 bump changed it (`pyproject.toml`, `src/sec2md/__init__.py`, `tests/test_models.py`, README line 3). The editable install must be refreshed after the bump, including the gitignored `src/sec2md.egg-info`, which shadows the venv's dist-info under pytest's `pythonpath = ["src"]` (see "Before you start"); `git archive` trees have no egg-info, so they read the venv's rcq.4 metadata.
- Golden files (interpretation, spec 104): `tests/golden/` is used only by the 14 deselected EDGAR integration tests and is not regenerated.
- Release notes (spec 1126-1129; resolved in round 5): CHANGELOG, README and `docs/usage/direct-conversion.md` describe the header line, the alignment fields and what the check does not cover, and now say that marker-only columns leave the second-row fusion count (spec 342-345): `CHANGELOG.md:17-22`, `docs/usage/direct-conversion.md:75-80` (with max(2, n // 2)), `README.md:245-246`; and that equal header texts compare ignoring case and spacing (`CHANGELOG.md:31-33`, `docs/usage/direct-conversion.md:85-86`). The CHANGELOG states the threshold as max(2, n // 2), as the code and the docs page do (amended into this commit after the round-5 check; text only).

**Review changes (2026-10-06):**
- `body_rows_main.json` regenerated with the committed generator: 2,485 rows (the prototype committed 2,492 from the older set semantics). Seven `HEADER_ZONE_MOVES` entries were rows `main` already rendered in its header lines and are dropped: 165 moves.
- CHANGELOG and README no longer say XLSX workbooks are unchanged; they state the accepted `display_page` exception.
- Five CHANGELOG known-limitation bullets: zero-width numbers, sub-label currency codes, R8's PART running headers and stubs, a `<table>` directly inside a header `<tr>`, and (after the final review) tables inside list items or inline wrappers.
- After the final review: the CHANGELOG also lists the completeness-diagnostic changes (F9-F11, class-1 losses gone), the public additions and the `display_page` footer precedence; README and the usage doc describe trailing label-only rows and the full data-row rule.
- The skip-key lists in README and `docs/usage/direct-conversion.md` are complete; "a row of `th` cells is never a data row"; an unused import is removed.
- `test_header_cells_reproduce_the_header_source_and_capacity` gains the malformed nested case.
- Task tests 446 passed, 2 warnings; full suite 1660 passed, 14 deselected, 3 warnings; ruff clean.

- [x] **Review** the commit against the spec sections and review points above.
- [x] **Verify** the counts above on the commit's tree (task tests, full suite, ruff).
- [x] **Record** any review change (failing test first, folded into this commit) and the new SHAs.

## Task 11: Acceptance run on the corpus

**Spec:** "Acceptance criteria" (all of it).

The tooling is in the main checkout's [`audits/2026-10-06-table-merge-header-acceptance/`](../audits/2026-10-06-table-merge-header-acceptance/). Its `README.md` explains each script. The expected results are the prototype's round 5, in [`REPORT-round5.md`](../audits/2026-10-06-table-merge-header-acceptance/REPORT-round5.md). A final run that reproduces them, apart from timings, meets the spec.

Placeholders:
- `<main>` is a `git archive c674828` tree, which also supplies the fixtures;
- `<wt>` is the worktree;
- `<cache>` is the main checkout's `outputs/table-completeness-corpus`;
- `<s>` is a scratch folder;
- `<acc>` is the acceptance folder.

Run every command with the worktree's venv and `PYTHONIOENCODING=utf-8`.

- [x] **Step 1: Run both sides.** Each `run_side.py` takes about 60 s with 7 workers.

  ```bash
  git -C C:/Users/einstein/kelab5am/sec2md archive c674828 | tar -x -C <main>
  PY=<wt>/venv/Scripts/python
  PYTHONPATH=<main>/src $PY <acc>/run_side.py --side main --expect-src <main>/src --fixtures-root <main> --edgar-cache <cache> --out-dir <s>/side-main --workers 7
  PYTHONPATH=<wt>/src $PY <acc>/run_side.py --side candidate --expect-src <wt>/src --fixtures-root <main> --edgar-cache <cache> --out-dir <s>/side-candidate --workers 7
  PYTHONPATH=<main>/src $PY <acc>/merges_main.py --expect-src <main>/src --fixtures-root <main> --edgar-cache <cache> --out <s>/merges.json.gz --workers 10
  PYTHONPATH=<wt>/src $PY <acc>/analyze_candidate.py --expect-src <wt>/src --fixtures-root <main> --edgar-cache <cache> --main-dir <s>/side-main --candidate-dir <s>/side-candidate --merges <s>/merges.json.gz --out-dir <s>/analysis --workers 10
  ```

- [x] **Step 2: Write the results to a fresh folder.** Use `<acc>/final/`, so the prototype's files stay untouched for comparison.

  ```bash
  $PY <acc>/report.py --main-dir <s>/side-main --candidate-dir <s>/side-candidate --analysis-dir <s>/analysis --merges <s>/merges.json.gz --out-dir <acc>/final
  $PY <acc>/shifted_tables.py --main-dir <s>/side-main --candidate-dir <s>/side-candidate --out <acc>/final/shifted_tables.json
  PYTHONPATH=<wt>/src $PY <acc>/review_sample.py --fixtures-root <main> --edgar-cache <cache> --main-dir <s>/side-main --candidate-dir <s>/side-candidate --out <acc>/final/review_sample.txt --lines 9
  PYTHONPATH=<main>/src $PY <acc>/xlsx_detail.py dump --fixtures-root <main> --edgar-cache <cache> --out <s>/xd_main.json edgar:NTRA-10-K-2025-02-28.htm edgar:TSM-20-F-2025-04-17.htm
  PYTHONPATH=<wt>/src $PY <acc>/xlsx_detail.py dump --fixtures-root <main> --edgar-cache <cache> --out <s>/xd_cand.json edgar:NTRA-10-K-2025-02-28.htm edgar:TSM-20-F-2025-04-17.htm
  $PY <acc>/xlsx_detail.py compare <s>/xd_main.json <s>/xd_cand.json --out <acc>/final/xlsx_detail.json
  ```

- [x] **Step 3: Measure overhead.** Run it alone on a quiet machine; it takes about 3 minutes.

  ```bash
  $PY <acc>/overhead.py --main-src <main>/src --candidate-src <wt>/src --fixtures-root <main> --runs 9 --out <acc>/final/overhead.json
  ```

- [x] **Step 4: Compare with round 5.** Every result file in `final/` must equal the prototype's file of the same name, apart from timing fields, the baseline's `sec2md` path, and the gzip header's mtime in `alignment_values.tsv.gz`. Expected:

  | # | Criterion | Expected |
  |---|---|---|
  | 1 | Check 1 | `TableParser` value failures 305 → 13: the 12 Phase A false-positive tables and TSM 344 (F9). All 294 class-1 tables fixed. Page furniture 573, unchanged. |
  | 2 | Other findings | F7 gone. New findings only F9 (TSM 344), F10 (15 tables) and F11 (BAC 260, 293, 336, 338). Tables with findings 937 → 633. |
  | 3 | Strict | 0 new failures in either mode. `header_accounting_misses` 0. The same 14 pre-existing trace failures on both sides. |
  | 4 | Sections | 872 of 872 identical. |
  | 5 | XLSX | 3,707 prepared tables identical, apart from `display_page` in 8 snapshots of NTRA and TSM (earlier text said 9, a miscount), the accepted S3 exception. |
  | 6 | Modes | 109 of 109 agree. |
  | 7 | Alignment | Candidate: 52,954 values evaluated, all aligned, 0 findings. 0 identities lost against `main`; 3,295 gained. |
  | 8 | Assignment audit | 6,616 of 6,616. |
  | 9 | Header retention | 54,986 of 54,990 values; the 4 misses are MSFT 69, the documented residual. 19,594 of 19,594 header cells. 733 of 733 header-only columns. |
  | 10 | Known shifted tables | 34 of 34 assertions (`main` 1 of 34). |
  | 11 | Class 8 | 75 of 80 fixed. The 5 TSM tables 79, 80, 82, 83 and 84 remain, with headers over the right values. |
  | 12 | Named limitations | Years rows read as data 0. Year runs followed by no data row 2 (CAT 27, KO 76). Year-run data rows 0. T8 caption numbers 0. |
  | 13 | Review sample | 42 tables: 35 correct, 6 with a note, 1 wrong (MSFT 69). |
  | 14 | Overhead | At most 1.10 (round 5: 1.090, and 1.085 on a repeat run). |
  | 15 | Moved rows | 2,270 rows in 1,609 tables. 0 failures of the independent header-like check. The 45 sparse-row-only rows are the spec's accepted list. |

  Stop and report any other difference instead of working around it.

- [x] **Step 5: Write the record.** Write `<acc>/final/REPORT.md`, with one section per criterion, its verdict and the comparison with round 5.
  - Do not commit in the main checkout; Task 12 asks the user.

**Result (2026-10-06):** reproduces round 5 apart from timings; all 15 criteria met; overhead 1.0904. `review_sample.py` needs `--lines 9` to match round 5 (the command above omits it). Criterion 5's count is 8 snapshots (earlier text said 9). Record: [`final/REPORT.md`](../audits/2026-10-06-table-merge-header-acceptance/final/REPORT.md).

## Task 12: Release notes and the PR

**Spec:** "Acceptance criteria", Release.

- [x] **Step 1: Check the release text.**
  - The `0.1.22+rcq.4` section of `CHANGELOG.md` lists each rendering change and the two new diagnostics fields.
  - `README.md` and `docs/usage/direct-conversion.md` describe the header line, the alignment fields and what the alignment check does not cover.
  - Fold any fix into Task 10's commit.
- [x] **Step 2: Final checks at HEAD.**
  - The full suite gives 1611 passed, 14 deselected, unless review changes added tests; record the new count.
  - `venv/Scripts/python -m ruff check src tests` is clean.
  - `git status` is clean.
- [x] **Step 3: Write the PR body** to the main checkout's ignored `outputs/table-merge-header-pr.md`. Include:
  - the summary;
  - the rendering changes;
  - the acceptance summary from Task 11;
  - the decisions and open items;
  - the documented residuals;
  - the test counts.

  End it with:

  ```
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  ```

- [x] **Step 4: Hand over.** Give the user the push and `gh pr create` commands and the path of the PR body. Do not run them.
- [x] **Step 5: Ask before committing in the main checkout.** Ask the user before committing the Task 11 record and any other docs to `main`.

**Result (2026-10-06):** release text corrected and folded into Task 10 (`1252c45`); full suite at HEAD 1660 passed, 14 deselected, 3 warnings; ruff clean; `git status` clean. A final whole-branch review (one fix round, re-reviewed clean) and a read-only Codex review of spec revision 17 and this plan ran before it. PR body: `outputs/table-merge-header-pr.md`.

## Decisions and open items

1. **XLSX display pages (S3): accepted by the user on 2026-10-06.** Every prepared XLSX table is identical to `main`'s. But `display_page`, which the workbook's contents sheet prints, is guessed from the Markdown page text, and the guess reads numbers out of table lines.
   - The new rendering changes it on 4 pages in 2 documents (8 snapshots; earlier text said 9, a miscount):
     - NTRA page 76: worse.
     - TSM page 47: better.
     - TSM pages 146 and 160: wrong before and after.
   - Task 11 lists each change. Any change beyond these 8 snapshots fails.
   - The guess is a bug already on `main` (TSM page 46 reads 118 from `2,608,118 |`). Fixing it is a separate task.
2. **Golden files.** `tests/golden/` is used only by the deselected EDGAR integration tests, and it already differs from `main`. Regenerating it needs a download from sec.gov, which needs the user's approval. This plan does not regenerate it.
3. **Commits 1–9 fail tests on their own** (see "How this plan works"). Splitting Task 10's updates into the commits that cause each failure is optional.

## Reviewer notes

**The spec was corrected from the prototype's corpus runs.** Revisions 6–16 add the corrections and interpretations, each in its own table at the top of the spec. The ones that change behaviour:

- **R0 counts footnoted values and ranges as complete numbers.** Footnoted bare years and fiscal-year ranges are year-like.
- **A year run is never a data row.** R0 has its own caption patterns, which add the corpus's dollar captions and `(Unaudited)`.
- **The header zone continues only through header-like rows.** These are rows with an empty, period, unit or year-like label cell, year runs, explicit header rows, label-only rows, and the second row under `main`'s sparse-row fusion, which leaves out marker-only columns. Trailing label-only rows are body rows.
- **Grid-hidden rows and cells are left out before placement.** A row whose cells are all hidden stays as an empty row.
- **R6's equal-text suppression** compares link destinations too, after the checker's normalization (whitespace collapsed, case folded).
- **Revision 14,** from checking the code against the spec while this plan was drafted:
  - a complete number allows one currency marker, thousands in groups of three and one trailing `%`;
  - `judge` stops as soon as both verdicts are reachable;
  - value columns leave out the label column;
  - two missing test groups were added: the header-retention audit on the matching controls, and `header_row_count` next to R0.
- **Revision 15,** from a read-only Codex review of the spec:
  - the XLSX `display_page` exception is written into the spec, and the user accepted it on 2026-10-06 (revision 16);
  - label-only is decided by origin, so a full-width caption that starts in the label column is a body row;
  - the checker's emitted path collapses entries only when their link destinations are equal too;
  - repeated headers are detected with year-like values;
  - check 1's acceptance distinguishes the 294 class-1 tables from the 305 → 13 value-failure tables;
  - two older passages were updated, and control tests were added.
- **The accuracy suite** applies R6a with its own tokenizer, amends the financial-row metric for header lines, and guards every row `main` rendered as a body row (165 listed header-zone moves on the fixtures).
- **Documented residuals:**
  - MSFT 69 (a value span over its year header);
  - class 8's 5 TSM tables;
  - F9–F11, which are check-side;
  - the 45 accepted source-grid fusions.

**Interpretations for Astra to confirm:**
- **Cell text in the checker.**
  - It reads cell text through the renderer's `extract_cell_text`.
  - For cells without links, it reuses the text the render already extracted from the same cell. This was behaviour-identical on all 109 documents, and it brought overhead under 1.10.
  - Merge decisions and the column mapping are never shared.
- **Year-like values** are never alignment values.
- **The header records** gain `header_cells`, read through `Parser.element_header_records()`.
- **The version** is `0.1.22+rcq.4`.
