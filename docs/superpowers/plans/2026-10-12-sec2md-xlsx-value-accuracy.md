# sec2md XLSX Value Accuracy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The XLSX export converts a value only on proof. Plain numbers in percent columns, and amounts under identifier headers, become proven numbers or flagged source text. No silent wrong scale remains.

**Architecture:**
- **Snapshot.** `SourceCell` gains the attributes of the inline XBRL facts in each cell.
- **Joining.** An XLSX-only attachment pass joins split `%` signs to their values before column grouping.
- **Roles.** `_numeric_role` and `prepare_table` get per-cell percent proofs (P1-P5), and a per-column pass that flags unproven cells in mixed columns.
- **Identifier columns.** `_identifier_column` keeps its header test, but its veto now yields per cell to the cell's own proof of a quantity.

**Tech Stack:** Python 3.12, BeautifulSoup with lxml, openpyxl, pytest, ruff.

**Spec:** [`../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md`](../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md), revision 2. Rule P, Rule I, Snapshot change, Testing and Acceptance are the contract. The fact pack in `../audits/2026-10-12-xlsx-value-accuracy/` is the evidence.

## Global Constraints

- **Where the work goes.**
  - Code, tests, `CHANGELOG.md` and `docs/usage/xlsx-export.md` go on a new branch `fix/xlsx-value-accuracy`, in the worktree `C:\Users\einstein\kelab5am\sec2md\.worktrees\xlsx-value-accuracy`, created from `main`.
  - The plan, the audit harness changes, the manifest and the audit record go on `main` in `C:\Users\einstein\kelab5am\sec2md`.
  - Never stage the untracked `docs/superpowers/specs/2026-10-12-sec2md-xlsx-period-rows-design.md`, which belongs to another session.
  - Never push.
- **Python.** Use `C:\Users\einstein\kelab5am\sec2md\.worktrees\xlsx-export\.venv\Scripts\python.exe` (`$PY`), run from the checkout root. Install nothing and download nothing. Never run the `integration` tests.
- **Known baseline failure.** `tests/test_models.py::test_internal_version_matches_distribution` fails for environmental reasons. Every other test must pass. Today's suite on `main`: `1 failed, 2106 passed, 14 deselected`.
- **Scope.**
  - In `src`, only `src/sec2md/xlsx_tables.py` and `src/sec2md/xlsx_values.py` change.
  - `parser.py` stays unchanged: the unit map is reached from the table node's document root.
  - `table_parser.py`, `table_completeness.py`, `_header_count`, `_PERIOD` and `_UNIT_DECLARATION` stay byte-identical. So do the header-detection rules, including the period-row guard.
  - Markdown output and strict's numeric trace must not change.
- **The principle (user decision).**
  - A value converts only on proof: the cell's own `%` or `$`, an explicit header or row label, or the inline XBRL fact in the cell.
  - Anything unproven stays source text, with the spec's exact review reason.
  - Never weaken an assertion or adjust an expected result to make a run pass. If a result differs from this plan, stop and report.
- **Accuracy first.** The balance sheet, income statement and cash flow statement must stay exactly correct. A wrong number anywhere blocks the merge.
- **Machine resources.** The machine runs live trading.
  - Run one corpus export at a time, with `--workers 3`, at low priority: `cmd /c start "" /low /b /wait …`.
  - Before starting, check that no other `export_tables.py` is running, and wait if one is.
  - After any crash, stop only the orphaned workers this run started.
- **Version.** It stays `0.1.22+rcq.4`. CHANGELOG edits stay within its first section.
- **Read-only:** `E:\RCQWealth`.
- **Lint:** `$PY -m ruff check src tests` passes at every commit.

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `src/sec2md/xlsx_tables.py` | Modify | `FactAttributes`, `SourceCell.facts`, the unit map, the attachment pass, the percent proofs and declarations, the mixed-column pass, and Rule I. |
| `src/sec2md/xlsx_values.py` | Modify | Accept the negative percent forms `(x) %`, `(x)%` and `(x %)`. |
| `tests/test_xlsx_value_accuracy.py` | Create | Every Testing case of the spec. |
| `tests/test_xlsx_header_detection.py` | Modify | Rewrite `test_identifier_columns_keep_text_even_for_facts` (spec I3). |
| `docs/superpowers/audits/2026-10-11-xlsx-header-detection/export_tables.py` (main) | Modify | Record `scale`, `format`, `unitref` and the resolved unit measures for each fact. |
| `docs/superpowers/audits/2026-10-12-xlsx-value-accuracy/{manifest.py,manifest.json,dispositions.py,changes.py,README.md}` (main) | Create | The manifest, dispositions, the changed-cell report and the audit record. |
| `CHANGELOG.md`, `docs/usage/xlsx-export.md` | Modify | The entry and the usage note. |

**Execution order:** Task 1 (main), then Tasks 2–5 (branch), Task 6 (acceptance, main and branch), Task 7 (docs).

---

### Task 1: Harness, baseline and manifest (main)

**Files (main):** modify `docs/superpowers/audits/2026-10-11-xlsx-header-detection/export_tables.py`; create `docs/superpowers/audits/2026-10-12-xlsx-value-accuracy/manifest.py` and `manifest.json`.

**Interfaces:**
- Produces:
  - Per table, a new list `fact_attributes` parallel to `facts` (same order), each `[scale, format, unitref, unit_measures]`. The six-field `facts` records stay as they are: `primary_statements.py` and `all_facts.py` unpack exactly six fields.
  - Per table, two new lists parallel to `rows`: `cell_formats` (each cell's `number_format`) and `cell_reasons` (each cell's `review_reason` or null). Acceptance compares formats and reasons cell by cell.
  - `manifest.json`: a list of entries `{filing, ordinal, source_row, source_column, kind, displayed, baseline_value}`, where:
    - `kind` is one of `percent_row_joined`, `percent_row_split`, `identifier_misread` or `identifier_true`;
    - `displayed` is the source text;
    - `baseline_value` is the baseline export's cell value.

- [ ] **Step 1:** Extend `export_tables.py` with `fact_attributes`, `cell_formats` and `cell_reasons` (above). Resolve `unitref` against the document's `xbrli:unit` definitions into a sorted tuple of measures (numerator and denominator kept apart, e.g. `('iso4217:USD', '/', 'xbrli:shares')`). Check that `compare.py`, `primary_statements.py` and `all_facts.py` still run unchanged on an old JSON and a new one.
- [ ] **Step 2:** Re-export the baseline from `main`'s `src` into `outputs/xlsx-value-accuracy/base`. Use `--workers 3` at low priority, on the 60 filings in `docs/superpowers/audits/2026-10-11-xlsx-header-detection/filings.txt`. You should get 60 JSONs. Apart from the three new lists, the output must equal `outputs/xlsx-header-detection/new6`; check this with a field-by-field diff that ignores them. A difference: stop and report.
- [ ] **Step 3:** Write `manifest.py`, adapted from the fact pack's `fact-pack-scripts/classify.py`, `partb.py`, `partd.py` and `partd2.py`. It produces `manifest.json` from the baseline. Required counts, from the fact pack:
  - `percent_row_joined`: 1,072 cells in 62 tables;
  - `percent_row_split`: 123 unscaled cells;
  - `identifier_misread`: every nonempty cell of the 32 columns, which is 195 cells, of which 178 hold digits;
  - `identifier_true`: every nonempty cell of the 241 columns, which is 2,658 cells, of which 2,319 hold digits.

  Any other count: stop and report. Do not tune the classifier to the counts.
- [ ] **Step 4:** Commit `export_tables.py`, `manifest.py` and `manifest.json` on `main`: `docs: value-accuracy baseline harness and manifest`.

---

### Task 2: Fact attributes in the snapshot (branch)

**Files:** modify `src/sec2md/xlsx_tables.py` (`SourceCell`, `_cell`, a new `_unit_map(root)`); create `tests/test_xlsx_value_accuracy.py`.

Step 0, before the first task on the branch: create the worktree:

```bash
git worktree add .worktrees/xlsx-value-accuracy -b fix/xlsx-value-accuracy main
```

Run the baseline suite: expected `1 failed, 2106 passed, 14 deselected`.

**Interfaces:**
- `@dataclass(frozen=True) class FactAttributes`: `name: str`, `unit_measures: tuple[str, ...]`, `scale: int | None`, `decimals: str | None`, `format: str | None`, `sign: str | None`, `displayed: str`.
- `SourceCell.facts: tuple[FactAttributes, ...] = ()`, added last with its default.
- `_unit_map(root) -> Mapping[str, tuple[str, ...]]`; `root` is the table node's top-level document. Cache the map as an attribute on the root object itself, so it lives and dies with that document. No `id()`-keyed module cache: export workers reuse processes across filings. Build it for both snapshot paths, independent of the `note_targets` fallback.
- `is_numeric_fact` is unchanged.

**Tests (6):**
- a pure fact, with `scale`, `format`, `sign` and `displayed` captured;
- unit resolution for `iso4217:USD`, `xbrli:shares` and a divide (USD per share), parametrized over 3;
- a cell without facts, with `facts == ()` and `is_numeric_fact` False;
- two facts in one cell (a range), giving 2 entries.

**Steps:** RED: `6 failed`. Then implement. GREEN: `6 passed`. Full suite: `1 failed, 2112 passed`. Ruff clean. Commit: `feat: keep inline XBRL fact attributes in XLSX table snapshots`.

---

### Task 3: Split `%`, negative percents and percentage points (branch)

**Files:** modify `src/sec2md/xlsx_values.py` (`convert_cell`) and `src/sec2md/xlsx_tables.py` (the attachment pass before `_column_groups`, and `_column_groups`' clean-conversion test); extend `tests/test_xlsx_value_accuracy.py`.

**Interfaces:**
- `convert_cell` accepts `(x) %`, `(x)%` and `(x %)` as −x/100, with a percent format derived from the displayed decimals.
- An attachment helper inside `prepare_table` (its name is the implementer's choice). It maps each attached `%` or `)%` origin to the value origin on its left in the same row; only empty, `$` or `(` origins may lie between them.
  - `_joined` and `cell_sources` include the attached marker.
  - The marker's own copy position becomes empty for that row.
- `pts`, `pt` and `points` values become text with `Percentage points; verify the unit.`, and they count as clean for the merge test.
- `table_parser.py` is unchanged.

**Tests (8):**
- the negative forms in `convert_cell`, parametrized over 3, with value and `number_format`;
- `(29) | %` gives −0.29, and `cell_sources` include the `%` cell;
- `(4.5 | )%` gives −0.045;
- a column with one negative split row and other `x %` rows merges, and every row converts;
- the NFLX-shaped `$ | 1,323,096 | 7 | %` under one leaf: 0.07, and `$ 1,323,096` is unchanged;
- `26.6 pts` stays text with its reason, while the column's other rows merge.

**Steps:** RED: `7 failed` (`(x %)` already converts today). GREEN: `14 passed`. Full suite: `1 failed, 2120 passed`. One existing expectation changes by design: `test_prepared_tables_keep_legacy_structural_rules[percent_close_marker]` (`tests/test_xlsx_tables.py:670`) pins `(3.2 | )%` as separate text cells; under spec P4 they attach and convert to −0.032 and −0.015. Update that fixture and state the reason in the commit. Any other existing test that fails: stop. Commit: `fix: join split percent signs and read negative percents in XLSX`.

---

### Task 4: Percent proofs and mixed columns (branch)

**Files:** modify `src/sec2md/xlsx_tables.py` (`_numeric_role`, `prepare_table`, new helpers); extend `tests/test_xlsx_value_accuracy.py`.

**Interfaces:**
- `_percent_declaration(text: str) -> bool`: spec Definitions, "Percent declaration".
- `_percent_fact(cell_origins) -> bool` and `_amount_fact(cell_origins) -> bool`: spec Definitions.
- `_table_percent_declaration(line: str) -> bool`: spec Definitions. The two `units` collection positions also feed a table-level flag; `_UNIT_DECLARATION` is unchanged.
- `_PERCENT.search(units)` in `_numeric_role` is replaced by the table-level flag.
- A per-copy-column pass after roles are decided. It marks percent columns (P4), and sets unproven digit cells to text with `Percent sign on other rows of this column; verify the scale.`
- Precedence and conflicts as in spec P3. The existing conflict reason and `test_wrapped_table_percent_context_and_local_unit_exception` stay.

**Tests (46):**
- own `%` (1);
- percent fact: proof (2: plain `13.8` → 0.138, and BAC-shaped `(0.3)` with `sign="-"` → −0.003); not proof, parametrized over 6 (`scale="-4"`, `scale="-1"` with years, an amount fact, two facts, a transformed format, a sign mismatch);
- percent header (2: RDDT `% Change`, JPM `Percent of retained loans to total retained loans`);
- percent row label (1);
- table-wide declarations: the NVDA sentence (1), and `(in percentages)` as a context line and as an in-table caption, parametrized over 2;
- non-declarations as header and as row label, parametrized over 6;
- unproven cells (4): the META shape, the JPM #64 shape, zero converting, and `(0)` keeping its negative-zero reason;
- `except` captions, parametrized over 2;
- conflicts, parametrized over 3;
- `_percent_declaration` directly: 10 declarations and 6 non-declarations, from the spec's lists, parametrized over 16.

Every converted cell asserts its value and `number_format`. Every text cell asserts its exact reason.

**Steps:** RED: `46 failed` is not required. Cases that already pass on today's code (the `except`-caption plain amounts, the local-unit exception) are listed in the report as passing before the change. GREEN: `60 passed`. Full suite: `1 failed, 2166 passed`. Existing tests that change by design are listed with their reasons; any other failure: stop. Commit: `fix: convert XLSX percents only on proof`.

---

### Task 5: Identifier columns, per-cell proof (branch)

**Files:** modify `src/sec2md/xlsx_tables.py` (Rule I in `_numeric_role` and the review-reason pass); extend `tests/test_xlsx_value_accuracy.py`; modify `tests/test_xlsx_header_detection.py` (`test_identifier_columns_keep_text_even_for_facts`, rewritten per spec I3).

**Interfaces:**
- `_identifier_column(header)` is unchanged.
- A cell under an identifier header takes the ordinary role path only with its own quantity proof (spec I1).
- Review reasons follow spec I2: `Identifier heading over quantities; verify the column.` and `Identifier heading over amount-formatted values; verify the column.`

**Tests (11):**
- per-cell proof (4): `Within 1 year(a)`; `Other Changes (Note)` with facts; `Year-over-Year Change` with split `%`; `Notes` over `7`, `8` and `$ 12`;
- unchanged identifiers, parametrized over 5;
- a `$` in prose (1);
- the amount-format flag with no quantity evidence (1).

The rewritten I3 test is a modification, not a new test.

**Steps:** RED, then GREEN: `71 passed` in `tests/test_xlsx_value_accuracy.py`, and the header-detection file still `130 passed`. Full suite: `1 failed, 2177 passed`. Commit: `fix: judge XLSX identifier columns by each cell's proof`.

---

### Task 6: Acceptance (main and branch)

**Files (main):** create `docs/superpowers/audits/2026-10-12-xlsx-value-accuracy/dispositions.py`, `changes.py` and `README.md`. Outputs (not committed) go to `outputs/xlsx-value-accuracy/new`.

- [ ] **Step 1:** Export the branch's `src` into `outputs/xlsx-value-accuracy/new`: one run, `--workers 3`, low priority, 60 JSONs.
- [ ] **Step 2:** `dispositions.py` checks every `manifest.json` entry in `new` (spec Acceptance 3). Each entry must be:
  - a proven percent: a number equal to displayed / 100, with its proof named;
  - a proven quantity: a number equal to its displayed value;
  - or text with the expected reason.

  `identifier_true` cells must be unchanged. Gate: 0 entries without a valid disposition.
- [ ] **Step 3:** `primary_statements.py` on `new`: all 126 vault statements export, with ok facts META 3,322, NVDA 2,662 and RDDT 2,056, and 0 failures (spec Acceptance 4).
- [ ] **Step 4:** `changes.py` lists every cell whose value, type, `cell_formats` entry or `cell_reasons` entry differs from `base`, outside the manifest. Each is classified by hand against its source cells (spec Acceptance 5). Gate: 0 wrong numbers.
- [ ] **Step 5:** Every cell proven by a percent fact equals the fact's displayed number / 100, with the fact's sign (spec Acceptance 6).
- [ ] **Step 6:** Count the coverage cost, number → flagged text, per group and table (spec Acceptance 7). Run `all_facts.py` and the stacked-block scan from the header-detection audit on `new`: no new mismatches, and no new stacked-block tables (spec Acceptance 8).
- [ ] **Step 7:** Write `README.md` with the commands, every gate result, the disposition counts, the classified changes, the coverage cost and the spot checks:
  - META 10-K FY2024 #8 percent-of-revenue rows;
  - RDDT 10-Q 2024-Q2 #36 `% Change`;
  - JPM #279;
  - TSM #150;
  - CAT #12.

  Commit `dispositions.py`, `changes.py` and `README.md` on `main`: `docs: acceptance record for XLSX value accuracy`.

Any failed gate: stop and report. Do not commit the README, and do not adjust any expectation.

---

### Task 7: CHANGELOG, usage doc and spec status (branch and main)

- [ ] **Step 1 (branch):** Add one bullet at the top of the `0.1.22+rcq.4` section of `CHANGELOG.md`, stating:
  - the proof principle;
  - percent proofs, and unproven cells as flagged text;
  - split `%` and negative percents;
  - `except` captions;
  - `pts`;
  - identifier columns judged per cell;
  - the counts from Task 6's README.

  Every claim must be supported by that README.
- [ ] **Step 2 (branch):** Add a short paragraph to `docs/usage/xlsx-export.md` on percent cells and the new review reasons.
- [ ] **Step 3 (branch):** Full suite `1 failed, 2177 passed`, ruff clean. Commit: `docs: changelog and usage for XLSX value accuracy`. `git log --oneline main..HEAD` shows five commits.
- [ ] **Step 4 (main):** Set the spec's status to `Implemented on branch fix/xlsx-value-accuracy (pending PR). Plan: ../plans/2026-10-12-sec2md-xlsx-value-accuracy.md. Acceptance: ../audits/2026-10-12-xlsx-value-accuracy/README.md.` Commit `docs: mark XLSX value accuracy spec implemented`.

Do not push. After the user merges, re-extract the vault workbooks.
