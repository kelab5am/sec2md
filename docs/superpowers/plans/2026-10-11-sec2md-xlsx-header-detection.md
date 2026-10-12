# sec2md XLSX Header Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `export_xlsx()` read the header rows of ordinary SEC financial tables, so balance sheets, income statements, cash flow statements and most notes reach the workbook as numbers under correct period headers. Where the exporter cannot prove a header, it keeps today's output.

**Architecture:**
- **Rule 3, identifier columns** (`_identifier_column`): an identifier word (`number`, `date`, `year`, `notes`, …) in one header part keeps the column as text, unless that word belongs to a note reference, a maturity bucket, period wording or a measured quantity. It replaces the two `_IDENTIFIER` call sites.
- **Rules 1 and 2, header extension** (`_export_header_count`): starts from the unchanged `_header_count` and extends the header downward only through rows that pass the spec's checks. It ends at the last row with span evidence. `prepare_table()` calls it instead of `_header_count`. Year tokens accept a footnote marker (`2023 (2)`), and `_EXPORT_PERIOD` (an XLSX-only copy of `_PERIOD` that also accepts it) is used only to recognise period headings.
- `_header_count` and `_PERIOD` stay byte-identical because `table_completeness.py` imports `_header_count`. Markdown output does not change.

**Tech Stack:** Python 3.12, BeautifulSoup with lxml, openpyxl, pytest, ruff.

**Spec:** [`../specs/2026-10-11-sec2md-xlsx-header-detection-design.md`](../specs/2026-10-11-sec2md-xlsx-header-detection-design.md), revision 6. Rules 1–3, Testing and Acceptance are the contract. Large caps that put the period caption in the label column (JPM, BAC, KO, MSFT, CAT, CRM) are a follow-up and out of scope. So is giving each stacked period block its own header row (a separate spec).

**Execution order (revision 6):** Tasks 1, 2 and 3 implemented revision 5 and are done (branch `4373afd`, `ad131b0`; audit `3894d2b` on `main`). Task 3's acceptance run found stacked period blocks exported under the wrong period (D1), so revision 6 adds Tasks 5, 6 and 7. Run them in that order, then Task 4 last.

**Acceptance harness:** [`../audits/2026-10-11-xlsx-header-detection/`](../audits/2026-10-11-xlsx-header-detection/) holds `export_tables.py`, `compare.py`, `primary_statements.py`, `mutation_check.py` and `filings.txt`, committed on `main` in the same commit as this plan. Every expected result below comes from running them against a scratch copy of this exact implementation.

## Global Constraints

- **Where the work goes.**
  - Code, tests, `CHANGELOG.md` and `docs/usage/xlsx-export.md` go on branch `fix/xlsx-header-detection` in the worktree `C:\Users\einstein\kelab5am\sec2md\.worktrees\xlsx-header-detection`, one commit per task.
  - Design documents, this plan, the harness and the audit record go on `main` in the main checkout `C:\Users\einstein\kelab5am\sec2md`, never on the branch (the user's standing instruction). The spec, plan and harness are already committed there; Task 3 adds the audit record.
  - Never push; the user pushes and opens the PR.
- **Python.** Use `C:\Users\einstein\kelab5am\sec2md\.worktrees\xlsx-export\.venv\Scripts\python.exe`, written `$PY` below, from the worktree root, where `pyproject.toml` puts `src` on the path. No installs and nothing that downloads. Never run the 14 EDGAR `integration` tests (they are deselected by default).
- **Known baseline failure.** In the worktree, `tests/test_models.py::test_internal_version_matches_distribution` fails before any change: the venv's installed metadata says `0.1.22+rcq.2`, and only the main checkout has the local `src/sec2md.egg-info` saying `0.1.22+rcq.4`. It is environmental. Every other test must pass. Do not change the test or the metadata.
- **Scope.** Only `src/sec2md/xlsx_tables.py` changes in `src`. `_header_count`, `_PERIOD` and `table_completeness.py` stay byte-identical. Markdown output, strict's numeric trace and the table completeness check must not change.
- **Accuracy first.** If an implementation detail is ambiguous, choose the behaviour that keeps today's output or falls back to source text. A wrong header, a number under the wrong period or a body row swallowed into a header is never acceptable.
- **Version** stays `0.1.22+rcq.4`. CHANGELOG edits stay within its first section.
- **Read-only:** `E:\RCQWealth` (the vault filings are harness inputs).
- **Lint:** `$PY -m ruff check src tests` passes at every commit.

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `src/sec2md/xlsx_tables.py` | Modify | Add the Rule 3 block (`_identifier_column` and its patterns) and the Rule 1/2 block (`_export_header_count`, `_EXPORT_PERIOD` and helpers) after `_header_count`. Switch `_numeric_role`, `prepare_table()` and the review-reason check to them. |
| `tests/test_xlsx_header_detection.py` | Create | Every Testing case of spec revision 4. |
| `CHANGELOG.md` | Modify | One entry under `0.1.22+rcq.4`. |
| `docs/usage/xlsx-export.md` | Modify | A short paragraph on header rows. |
| `docs/superpowers/audits/2026-10-11-xlsx-header-detection/README.md` (main) | Create | Acceptance results and classifications. |

---

### Task 1: Identifier columns (Rule 3)

**Files:**
- Modify: `src/sec2md/xlsx_tables.py` (insert before `def _numeric_role(`; edit `_numeric_role`'s identifier test and the review-reason line in `prepare_table()`)
- Create: `tests/test_xlsx_header_detection.py`

**Interfaces:**
- Produces: `_identifier_column(header: str) -> bool`, and module patterns `_NOTE_REF`, `_MATURITY_BUCKET`, `_PERIOD_WORDS`, `_QUANTITY`.
- Consumes: the existing `_IDENTIFIER`, `_MONTH`, `_VALUE`, `_ROW_UNIT`.

- [ ] **Step 1: Point the branch at `main` and record the baseline**

The worktree exists with branch `fix/xlsx-header-detection` and no commits of its own. Move it to `main`, which now carries the spec, so it starts from the design commits:

```bash
cd /c/Users/einstein/kelab5am/sec2md/.worktrees/xlsx-header-detection
git status --short          # must print nothing
git reset --hard main
PY=/c/Users/einstein/kelab5am/sec2md/.worktrees/xlsx-export/.venv/Scripts/python.exe
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected: `1 failed, 1976 passed, 14 deselected`. The single failure must be `test_models.py::test_internal_version_matches_distribution` (see Global Constraints). Stop and report anything else.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_xlsx_header_detection.py` with this content. Task 2 adds the Rule 1 and 2 tests to the same file.

```python
"""XLSX header detection (docs/superpowers/specs/2026-10-11-sec2md-xlsx-header-detection-design.md).

Tables use SEC-style spans: each period heading spans the '$', amount and padding
cells beneath it, as in the evidence filings.
"""

import hashlib
import inspect
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from sec2md import xlsx_tables
from sec2md.xlsx_tables import _header_count, _identifier_column, prepare_table, snapshot_html_table


def prepared(source):
    soup = BeautifulSoup(source, 'lxml')
    return prepare_table(snapshot_html_table(soup.table, ordinal=1, page=1, source_url='https://example.com/main.htm'))


def values(table):
    return [[cell.value for cell in row] for row in table.rows]


def grid_of(source):
    """The span grid prepare_table builds, for direct _header_count assertions."""
    soup = BeautifulSoup(source, 'lxml')
    cells = snapshot_html_table(soup.table, ordinal=1, page=1, source_url='https://example.com/main.htm').source_cells
    height = max(c.row + c.rowspan for c in cells)
    width = max(c.column + c.colspan for c in cells)
    grid = [[None] * width for _ in range(height)]
    for cell in cells:
        for r in range(cell.row, cell.row + cell.rowspan):
            for k in range(cell.column, cell.column + cell.colspan):
                grid[r][k] = cell
    return grid


DATE_OVER_YEARS = ('<tr><td></td><td colspan="6">December 31,</td></tr>'
                   '<tr><td></td><td colspan="3">2024</td><td colspan="3">2023</td></tr>')


def money(label, first, second):
    return f'<tr><td>{label}</td><td>$</td><td>{first}</td><td></td><td>$</td><td>{second}</td><td></td></tr>'


def plain(label, first, second):
    return f'<tr><td>{label}</td><td colspan="2">{first}</td><td></td><td colspan="2">{second}</td><td></td></tr>'


BALANCE_SHEET = ('<table>' + DATE_OVER_YEARS + money('Cash', '43,889', '41,862')
                 + plain('Total assets', '276,054', '229,623') + '</table>')


# --- Rule 3: identifier columns -------------------------------------------------

@pytest.mark.parametrize('header', [
    'Number of Shares', 'Number — of RSUs (iii)', 'Weighted- — average — grant date — fair value — US$',
    'Plan to Date — Severance', 'Year ended March 31, — 2023 — RMB',
    'For the year ended December 31, 2024 — NT$', 'Less Than 1 Year — NT$', 'December 31, 2024 — US$ — (Note 3)',
    'Notes 2(a)', 'Year Ended December 31, — 2023 (2)'])
def test_not_identifier_columns(header):
    assert not _identifier_column(header)


@pytest.mark.parametrize('header', [
    'Exhibit Number', 'CUSIP', 'Notes', 'Date', 'Filing Date', 'December 31, 2024 — Notes',
    'December 31, 2024 — CUSIP', '2024 — Exhibit Number', 'CUSIP — RMB', 'Filing Date — December 31, 2024',
    'CUSIP as of December 31, 2024', 'Notes for year ended December 31, 2024', 'Notes — Cash',
    'CUSIP — Shares', 'Notes — Amount'])
def test_identifier_columns(header):
    assert _identifier_column(header)


def test_quantity_headers_hold_numbers():
    table = prepared('<table><tr><th>Item</th><th>Number of Shares</th></tr>'
                     '<tr><td>Granted</td><td>48,661</td></tr></table>')
    assert values(table) == [['Granted', Decimal('48661')]]


def test_period_and_currency_header_holds_numbers():
    table = prepared('<table><tr><th></th><th>Year ended March 31,</th></tr><tr><th></th><th>2023</th></tr>'
                     '<tr><th></th><th>RMB</th></tr><tr><td>Revenue</td><td>868,687</td></tr></table>')
    assert values(table) == [['Revenue', Decimal('868687')]]


@pytest.mark.parametrize('top, leaf', [('', 'Notes'), ('December 31, 2024', 'Notes'), ('', 'CUSIP'),
                                       ('', 'Exhibit Number'), ('Notes', 'Cash'), ('CUSIP', 'Shares')])
def test_identifier_columns_keep_text_in_tables(top, leaf):
    table = prepared(f'<table><tr><th></th><th>{top}</th><th>December 31, 2024</th></tr>'
                     f'<tr><th>Item</th><th>{leaf}</th><th>Amount</th></tr>'
                     '<tr><td>Revenue</td><td>7</td><td>$100</td></tr></table>')
    assert table.rows[0][1].value == '7'
    assert table.rows[0][2].value == Decimal('100')


@pytest.mark.parametrize('top, leaf', [('', 'Number of Shares'), ('Number', 'of RSUs (iii)'),
                                       ('Plan to Date', 'Severance'), ('Year ended March 31,', '2023'),
                                       ('Less Than 1 Year', 'NT$')])
def test_measured_columns_hold_numbers_in_tables(top, leaf):
    table = prepared(f'<table><tr><th></th><th>{top}</th></tr><tr><th>Item</th><th>{leaf}</th></tr>'
                     '<tr><td>Revenue</td><td>$1,234</td></tr></table>')
    assert table.rows[0][1].value == Decimal('1234')


def test_identifier_columns_keep_text_even_for_facts():
    table = prepared('<table><tr><th></th><th colspan="2">December 31, 2024</th></tr>'
                     '<tr><th>Item</th><th>Notes</th><th>Amount</th></tr>'
                     '<tr><td>Revenue</td><td><ix:nonfraction>7</ix:nonfraction></td><td>$100</td></tr></table>')
    assert table.rows[0][1].value == '7'


def test_measured_column_without_context_is_flagged_not_silent():
    table = prepared('<table><tr><th>Item</th><th>Plan to Date</th></tr>'
                     '<tr><td>Employee termination benefits</td><td>500</td></tr></table>')
    assert table.rows[0][1].value == '500'
    assert table.rows[0][1].review_reason
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_xlsx_header_detection.py`
Expected: a collection error, `ImportError: cannot import name '_identifier_column'`.

- [ ] **Step 4: Implement Rule 3**

In `src/sec2md/xlsx_tables.py`, insert this block immediately before `def _numeric_role(`:

```python
# Identifier columns (Rule 3). A header part keeps identifier meaning unless the
# identifier word belongs to a note reference, a maturity bucket, period wording
# or a measured quantity. Ancestor parts never clear another part.
_NOTE_REF = re.compile(r'\(?notes? \d+[a-z]?(?:\([a-z]\))?\)?', re.I)
_MATURITY_BUCKET = re.compile(r'(?:(?:less|more) than \d+ years?|\d+\s*[-–]\s*\d+ years?'
                              r'|\d+ years? or (?:more|greater|less))', re.I)
_PERIOD_WORDS = re.compile(
    rf'\b(?:for )?(?:the )?(?:(?:three|six|nine|twelve) )?(?:years?|months?|quarters?|weeks?|periods?) ended\b'
    rf'|\b{_MONTH} \d{{1,2}},?(?: (?:19|20)\d{{2}})?|\b(?:19|20)\d{{2}}\b|\bas (?:of|at)\b', re.I)
_QUANTITY = re.compile(r'\bnumber of\b|\bto date\b|\bper share\b', re.I)
# Quantity phrases a heading may wrap across two header rows.
_WRAPPED_QUANTITY = re.compile(r'\bnumber of\b|\bgrant[- ]date fair value\b', re.I)


def _identifier_column(header):
    """Whether a flattened header names an identifier column."""
    parts = [part.strip() for part in header.split(' — ') if part.strip()]
    for index, part in enumerate(parts):
        if not _IDENTIFIER.search(part):
            continue
        if _NOTE_REF.fullmatch(part) or _MATURITY_BUCKET.fullmatch(part):
            continue
        if not _IDENTIFIER.search(_PERIOD_WORDS.sub(' ', part)):
            continue  # 'Year ended March 31,' is a period, not an identifier
        if any(pattern.search(part) for pattern in (_VALUE, _ROW_UNIT, _QUANTITY)):
            continue  # the identifier word names a measured quantity: 'Number of Shares'
        if _WRAPPED_QUANTITY.search(' '.join(parts[index:index + 2])):
            continue  # a wrapped heading: 'Number — of RSUs', 'grant date — fair value'
        return True
    return False


```

In `_numeric_role`, replace

```python
    if _IDENTIFIER.search(header) and not period_header:
```

with

```python
    if _identifier_column(header) and not period_header:
```

In `prepare_table()`, in the review-reason branch, replace

```python
            elif role == 'text' and index > 0 and re.search(r'\d', text) and not _IDENTIFIER.search(headers[index]):
```

with

```python
            elif role == 'text' and index > 0 and re.search(r'\d', text) and not _identifier_column(headers[index]):
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_xlsx_header_detection.py`
Expected: `40 passed`.

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_xlsx.py tests/test_xlsx_clean.py tests/test_xlsx_tables.py tests/test_xlsx_values.py tests/test_xlsx_writer.py`
Expected: `249 passed`.

Run: `$PY -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/sec2md/xlsx_tables.py tests/test_xlsx_header_detection.py
git commit -m "fix: judge XLSX identifier columns per header part"
```

---

### Task 2: Header extension (Rules 1 and 2)

**Files:**
- Modify: `src/sec2md/xlsx_tables.py` (insert after `_header_count`, before the Rule 3 block; switch `prepare_table()` and `_numeric_role`)
- Modify: `tests/test_xlsx_header_detection.py`

**Interfaces:**
- Consumes: `_identifier_column` from Task 1; the existing `_header_count`, `_UNIT_DECLARATION`, `_MONTH`.
- Produces: `_export_header_count(grid) -> int` and `_EXPORT_PERIOD`, with helpers `_row_origins`, `_is_data_cell(cell, digits=False)`, `_period_heading(text)`, `_caption_label(text)` and `_heading_label(text)`. `_numeric_role` is not changed in this task.

- [ ] **Step 1: Write the failing tests**

In `tests/test_xlsx_header_detection.py`, insert this section between the `BALANCE_SHEET` constant and the `# --- Rule 3` section:

```python
# --- Rule 1, positive cases -----------------------------------------------------

def test_bare_instant_date_over_years_gives_period_headers():
    table = prepared(BALANCE_SHEET)
    assert table.status == 'exported'
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert values(table) == [['Cash', Decimal('43889'), Decimal('41862')],
                             ['Total assets', Decimal('276054'), Decimal('229623')]]
    assert table.cell_sources[0][1:] == (((2, 1), (2, 2)), ((2, 4), (2, 5)))


def test_change_column_beside_years_gets_its_own_header():
    table = prepared(
        '<table><tr><td></td><td colspan="9">Year Ended December 31,</td></tr>'
        '<tr><td></td><td colspan="3">2024</td><td colspan="3">2023</td><td colspan="3">2024 vs 2023 % change</td></tr>'
        '<tr><td>Advertising</td><td>$</td><td>160,633</td><td></td><td>$</td><td>131,948</td><td></td>'
        '<td></td><td>22</td><td>%</td></tr></table>')
    assert table.headers == ('Column 1', 'Year Ended December 31, — 2024', 'Year Ended December 31, — 2023',
                             'Year Ended December 31, — 2024 vs 2023 % change')
    assert values(table) == [['Advertising', Decimal('160633'), Decimal('131948'), Decimal('0.22')]]


def test_labelled_heading_row_with_heading_word_joins_the_header():
    table = prepared(
        '<table><tr><td></td><td></td><td></td><td colspan="4">Fair Value Measurement Using</td></tr>'
        '<tr><td>Description</td><td colspan="2">December 31, 2024</td><td colspan="2">Level 1</td>'
        '<td colspan="2">Level 2</td></tr>'
        + '<tr><td>Money market funds</td><td>$</td><td>36,165</td><td>$</td><td>36,165</td><td>$</td><td>12</td></tr>'
        '</table>')
    assert table.status == 'exported'
    assert table.headers == ('Description', 'December 31, 2024', 'Fair Value Measurement Using — Level 1',
                             'Fair Value Measurement Using — Level 2')
    assert values(table) == [['Money market funds', Decimal('36165'), Decimal('36165'), Decimal('12')]]


def test_three_level_td_header():
    table = prepared(
        '<table><tr><td></td><td colspan="4">December 31, 2024</td></tr>'
        '<tr><td></td><td colspan="2">Less than 12 months</td><td colspan="2">12 months or greater</td></tr>'
        '<tr><td></td><td colspan="2">Fair Value</td><td colspan="2">Fair Value</td></tr>'
        '<tr><td>U.S. government securities</td><td>$</td><td>6,860</td><td>$</td><td>4,330</td></tr></table>')
    assert table.headers == ('Column 1', 'December 31, 2024 — Less than 12 months — Fair Value',
                             'December 31, 2024 — 12 months or greater — Fair Value')
    assert values(table) == [['U.S. government securities', Decimal('6860'), Decimal('4330')]]
    assert table.cell_sources[0][1:] == (((3, 1), (3, 2)), ((3, 3), (3, 4)))


def test_equal_width_headings_in_the_evidenced_row():
    # META's debt table: Maturity and rates over cells as wide as they are.
    table = prepared(
        '<table><tr><td></td><td colspan="2">Maturity</td><td colspan="2">Stated Interest Rate</td>'
        '<td colspan="2">December 31, 2024</td></tr>'
        '<tr><td>2027 Notes</td><td colspan="2">2027</td><td colspan="2">3.50%</td><td>$</td><td>2,750</td></tr>'
        '</table>')
    assert table.headers == ('Column 1', 'Maturity', 'Stated Interest Rate', 'December 31, 2024')
    assert values(table)[0][3] == Decimal('2750')


def test_equal_width_headings_one_row_above_the_evidenced_row():
    # NVDA's debt table: term and rate headings above the evidenced dates.
    table = prepared(
        '<table><tr><td></td><td colspan="2">Expected Remaining Term (years)</td>'
        '<td colspan="2">Effective Interest Rate</td><td colspan="4">Carrying Value at</td></tr>'
        '<tr><td></td><td colspan="2"></td><td colspan="2"></td><td colspan="2">Jan 25, 2026</td>'
        '<td colspan="2">Jan 26, 2025</td></tr>'
        '<tr><td>3.50% Notes Due 2027</td><td colspan="2">1.2</td><td colspan="2">3.54%</td>'
        '<td>$</td><td>1,000</td><td>$</td><td>1,000</td></tr></table>')
    assert table.headers[-2:] == ('Carrying Value at — Jan 25, 2026', 'Carrying Value at — Jan 26, 2025')
    assert values(table)[0][-2:] == [Decimal('1000'), Decimal('1000')]


def test_full_width_text_or_nil_in_the_data_row_does_not_block_the_header():
    table = prepared(
        '<table>' + DATE_OVER_YEARS
        + '<tr><td>Level</td><td colspan="3">Level 1</td><td colspan="3">—</td></tr>'
        + money('Cash', '10', '20') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')


def test_year_completes_an_equally_wide_yearless_date():
    # NVDA FY2024 10-Q balance sheets: 'July 30,' over an equally wide '2023'.
    table = prepared(
        '<table><tr><td></td><td colspan="3">July 30,</td><td colspan="3">January 29,</td></tr>'
        '<tr><td></td><td colspan="3">2023</td><td colspan="3">2023</td></tr>'
        + money('Cash and cash equivalents', '5,783', '3,389') + '</table>')
    assert table.headers == ('Column 1', 'July 30, — 2023', 'January 29, — 2023')
    assert values(table) == [['Cash and cash equivalents', Decimal('5783'), Decimal('3389')]]
    assert table.cell_sources[0][1:] == (((2, 1), (2, 2)), ((2, 4), (2, 5)))


def test_footnoted_years_are_periods():
    table = prepared(
        '<table><tr><td></td><td colspan="9">Year Ended December 31,</td></tr>'
        '<tr><td></td><td colspan="3">2024</td><td colspan="3">2023 (2)</td><td colspan="3">2022 (2)</td></tr>'
        '<tr><td>Net income</td><td>$</td><td>62,360</td><td></td><td>$</td><td>39,098</td><td></td>'
        '<td>$</td><td>23,200</td><td></td></tr></table>')
    assert values(table) == [['Net income', Decimal('62360'), Decimal('39098'), Decimal('23200')]]
    assert table.headers[1:] == ('Year Ended December 31, — 2024', 'Year Ended December 31, — 2023 (2)',
                                 'Year Ended December 31, — 2022 (2)')


# --- Rule 1, negative cases: today's output, or a fallback ----------------------

def assert_body_row_kept(table, label, texts):
    row = next(row for row in table.rows if row[0].value == label)
    assert [cell.value for cell in row[1:] if cell.value is not None] == texts


def test_unaudited_and_unit_captions_are_not_column_leaves():
    for captions in (['(unaudited)'], ['(in thousands)'], ['(unaudited)', '(in thousands)']):
        rows = ''.join(f'<tr><td></td><td colspan="6">{c}</td></tr>' for c in captions)
        table = prepared('<table><tr><td></td><td colspan="6">Three months ended June 30,</td></tr>'
                         '<tr><td></td><td colspan="3">2025</td><td colspan="3">2024</td></tr>'
                         + rows + money('Revenue', '499,628', '281,184') + '</table>')
        assert table.status == 'exported', captions
        assert table.headers[1:] == ('Three months ended June 30, — 2025', 'Three months ended June 30, — 2024')


def test_label_and_units_row_stays_in_the_body():
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Inventories:</td><td colspan="6">(In millions)</td></tr>'
                     + money('Raw materials', '3,807', '3,408') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert table.rows[0][0].value == 'Inventories:'


@pytest.mark.parametrize('first, second', [('N/A', 'NM'), ('NM', '—'), ('March 31, 2025', 'June 30, 2025'),
                                           ('Foo', 'Bar')])
def test_labelled_text_row_as_wide_as_the_years_stays_in_the_body(first, second):
    table = prepared('<table>' + DATE_OVER_YEARS
                     + f'<tr><td>Alpha</td><td colspan="3">{first}</td><td colspan="3">{second}</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert_body_row_kept(table, 'Alpha', [first, second])
    assert values(table)[-1] == ['Beta', Decimal('10'), Decimal('20')]


def test_labelled_range_row_falls_back_as_today():
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Alpha</td><td colspan="3">2027 - 2062</td><td colspan="3">3.50% - 4.65%</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.status == 'source_text_only'


def test_unlabelled_text_row():
    narrow = prepared('<table>' + DATE_OVER_YEARS
                      + '<tr><td></td><td></td><td>Foo</td><td></td><td></td><td>Bar</td><td></td></tr>'
                      + money('Beta', '10', '20') + '</table>')
    assert narrow.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert [cell.value for cell in narrow.rows[0]] == [None, 'Foo', 'Bar']
    wide = prepared('<table>' + DATE_OVER_YEARS
                    + '<tr><td></td><td colspan="3">As Reported</td><td colspan="3">As Adjusted</td></tr>'
                    + money('Beta', '10', '20') + '</table>')
    assert wide.headers == ('Column 1', 'December 31, — 2024 — As Reported', 'December 31, — 2023 — As Adjusted')


@pytest.mark.parametrize('row', [
    '<tr><td>Alpha</td><td>N/A</td></tr>', '<tr><td>Alpha</td><td>NM</td></tr>',
    '<tr><td>Alpha</td><td>—</td></tr>', '<tr><td>Alpha</td><td>March 31, 2025</td></tr>',
    '<tr><td>Alpha</td><td>2027 - 2062</td></tr>'])
def test_codex_round_1_text_row_after_th_header(row):
    source = f'<table><tr><th>Item</th><th>Amount</th></tr>{row}<tr><td>Beta</td><td>10</td></tr></table>'
    table = prepared(source)
    assert table.headers == ('Item', 'Amount')
    assert table.rows[0][0].value == 'Alpha'
    assert table.rows[-1][1].value == Decimal('10')


def test_codex_round_1_year_shaped_amounts_under_a_wider_heading():
    table = prepared('<table><tr><th>Item</th><th colspan="2">Amount</th></tr>'
                     '<tr><td>Revenue</td><td>2024</td><td>2025</td></tr>'
                     '<tr><td>Cost</td><td>100</td><td>150</td></tr></table>')
    assert values(table) == [['Revenue', Decimal('2024'), Decimal('2025')], ['Cost', Decimal('100'), Decimal('150')]]


def test_codex_round_1_text_table_with_a_dash():
    table = prepared('<table><tr><td>Name</td><td>Title</td></tr><tr><td>Alice</td><td>CEO</td></tr>'
                     '<tr><td>Bob</td><td>-</td></tr></table>')
    assert table.headers == ('Column 1', 'Column 2')
    assert len(table.rows) == 3


def test_signature_table_is_unchanged():
    table = prepared('<table><tr><td>Signature</td><td>Title</td><td>Date</td></tr>'
                     '<tr><td>/s/ Mark Zuckerberg</td><td>Chief Executive Officer</td><td>January 29, 2025</td></tr>'
                     '<tr><td>Peggy Alford</td><td></td><td></td></tr></table>')
    assert table.headers == ('Column 1', 'Column 2', 'Column 3')
    assert len(table.rows) == 3


def test_currency_row_narrower_than_its_date_stays_out_of_the_header():
    # TSM: 'NT$' spans only the '$' and amount cells of a wider date column.
    table = prepared(
        '<table><tr><td></td><td colspan="4">December 31, 2023</td><td colspan="4">December 31, 2024</td></tr>'
        '<tr><td></td><td></td><td colspan="2">NT$</td><td></td><td></td><td colspan="2">NT$</td><td></td></tr>'
        '<tr><td>Corporate bonds</td><td></td><td>$</td><td>113,851.9</td><td></td><td></td><td>$</td>'
        '<td>172,092.0</td><td></td></tr></table>')
    assert table.headers == ('Column 1', 'December 31, 2023', 'December 31, 2024')


def test_codex_round_2_labelled_rows_of_amounts_fall_back():
    for middle in ('<tr><td>Revenue</td><td colspan="2">2024</td><td colspan="2">2025</td></tr>',
                   '<tr><td>Basic EPS</td><td colspan="2">.75</td><td colspan="2">.50</td></tr>'):
        table = prepared('<table><tr><th>Item</th><th colspan="4">December 31, 2025</th></tr>' + middle
                         + '<tr><td>Cost</td><td>$</td><td>100</td><td>$</td><td>150</td></tr></table>')
        assert table.status == 'source_text_only', middle


def test_codex_round_2_heading_across_two_periods_keeps_each_amount_under_its_date():
    table = prepared(
        '<table><tr><th>Item</th><th colspan="3">December 31, 2024</th><th colspan="3">December 31, 2023</th></tr>'
        '<tr><td>Description</td><td colspan="2">Cash</td><td colspan="2">Debt</td><td colspan="2">Other</td></tr>'
        '<tr><td>Revenue</td><td>$</td><td>100</td><td>$</td><td>200</td><td>$</td><td>300</td></tr></table>')
    by_header = {}
    for header, cell in zip(table.headers, table.rows[-1]):
        by_header.setdefault(header, []).append(cell.value)
    assert Decimal('200') not in by_header.get('December 31, 2024 — Debt', [])
    assert all('Debt' not in header for header in table.headers)


def test_codex_round_2_narrower_labelled_text_row_stays_in_the_body():
    table = prepared('<table><tr><th>Item</th><th colspan="4">December 31, 2025</th></tr>'
                     '<tr><td>Alpha</td><td colspan="2">Foo</td><td colspan="2">Bar</td></tr>'
                     '<tr><td>Cost</td><td>$</td><td>100</td><td>$</td><td>150</td></tr></table>')
    assert table.rows[0][0].value == 'Alpha'
    assert all('Foo' not in header for header in table.headers)


@pytest.mark.parametrize('first, second', [('N/A', 'NM'), ('.75', '.50')])
def test_check_1_unlabelled_row_of_data_stays_in_the_body(first, second):
    # Unlabelled, so checks 3 and 3b do not apply; only check 1 sees data cells.
    table = prepared('<table>' + DATE_OVER_YEARS
                     + f'<tr><td></td><td colspan="3">{first}</td><td colspan="3">{second}</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert all(first not in header for header in table.headers)


def test_check_3_labelled_row_needs_two_headings():
    # 'Description' passes check 3b and 'Foo' is narrower than '2024'; only check 3 stops it.
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Description</td><td colspan="2">Foo</td><td></td><td></td><td></td><td></td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert all('Foo' not in header for header in table.headers)
    assert table.status == 'source_text_only' or table.rows[0][0].value == 'Description'


def test_check_8_years_need_a_period_heading_above():
    # Unlabelled years under a non-period heading: only check 8 keeps them out of the header.
    table = prepared('<table><tr><td></td><td colspan="6">Amount</td></tr>'
                     '<tr><td></td><td colspan="3">2024</td><td colspan="3">2023</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert all('2024' not in header for header in table.headers)


def test_check_4b_labelled_row_as_wide_as_its_heading_stays_in_the_body():
    # 'Description' is a heading word, so only check 4b keeps this row out of the header.
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Description</td><td colspan="3">Foo</td><td colspan="3">Bar</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert_body_row_kept(table, 'Description', ['Foo', 'Bar'])


def test_check_7b_years_on_a_heading_word_row_are_not_headers():
    # 'Description' passes check 3b; only check 7b stops its years becoming headings.
    table = prepared('<table><tr><td></td><td colspan="6">December 31,</td></tr>'
                     '<tr><td>Description</td><td colspan="3">2024</td><td colspan="3">2023</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.status == 'source_text_only' or table.rows[0][0].value == 'Description'


def test_heading_over_part_of_a_wider_amount_falls_back():
    # Check 5 is a second line of defence: without it the unresolved-span check falls back too.
    table = prepared('<table><tr><td></td><td colspan="4">December 31, 2024</td></tr>'
                     '<tr><td></td><td>A</td><td>B</td><td colspan="2">C</td></tr>'
                     '<tr><td>Revenue</td><td colspan="2">100</td><td>$</td><td>200</td></tr></table>')
    assert table.status == 'source_text_only'


@pytest.mark.parametrize('label', ['Revenue for year ended December 31, 2025', 'Cash as of December 31, 2025'])
def test_line_item_mentioning_a_period_is_not_a_caption(label):
    # A body label containing period wording must not head its year-shaped amounts.
    table = prepared(f'<table><tr><th>Item</th><th colspan="4">December 31, 2025</th></tr>'
                     f'<tr><td>{label}</td><td colspan="2">2024</td><td colspan="2">2025</td></tr>'
                     '<tr><td>Cost</td><td>$</td><td>100</td><td>$</td><td>150</td></tr></table>')
    assert table.status == 'source_text_only' or table.rows[0][0].value == label


def test_pricing_category_heading_row():
    table = prepared(
        '<table><tr><td></td><td colspan="4">Fair Value at</td></tr>'
        '<tr><td>Pricing Category</td><td colspan="2">Apr 27, 2025</td><td colspan="2">Jan 26, 2025</td></tr>'
        '<tr><td>Money market funds</td><td>$</td><td>14,925</td><td>$</td><td>11,423</td></tr></table>')
    assert table.headers == ('Pricing Category', 'Fair Value at — Apr 27, 2025', 'Fair Value at — Jan 26, 2025')
    assert values(table) == [['Money market funds', Decimal('14925'), Decimal('11423')]]


def test_header_count_and_period_are_byte_identical():
    # table_completeness reads _header_count, which uses _PERIOD; neither may change.
    source = inspect.getsource(xlsx_tables._header_count).encode()
    assert hashlib.sha256(source).hexdigest() == 'ee9602d3dbf304d6dd0abbc69b84c830eaa16cf0f285437d7a2776ca3a3b9df1'
    pattern = xlsx_tables._PERIOD.pattern.encode()
    assert hashlib.sha256(pattern).hexdigest() == 'ee6996610a505583030f3ab913a7e8854dafd0e6b3c115602df6bbffcda21f16'


def test_header_count_is_unchanged_for_the_completeness_check():
    # table_completeness reads _header_count; these grids keep today's counts.
    assert _header_count(grid_of(BALANCE_SHEET)) == 0
    assert _header_count(grid_of('<table><tr><th>Item</th><th>Amount</th></tr>'
                                 '<tr><td>Alpha</td><td>N/A</td></tr></table>')) == 1


```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_xlsx_header_detection.py`
Expected: `17 failed, 64 passed`. The failures are the positive Rule 1 and 2 cases (`test_bare_instant_date_over_years_gives_period_headers` through `test_footnoted_years_are_periods`, and `test_pricing_category_heading_row`) and the cases whose expected header exists only after extension (`test_label_and_units_row_stays_in_the_body`, the four `test_labelled_text_row_as_wide_as_the_years_stays_in_the_body[*]`, `test_unlabelled_text_row`, `test_check_4b_labelled_row_as_wide_as_its_heading_stays_in_the_body`). Every case that expects today's output or a fallback already passes.

- [ ] **Step 3: Implement Rules 1 and 2**

Insert this block immediately after `_header_count` (after its `return count`), before the `# Identifier columns (Rule 3).` comment from Task 1:

```python
# XLSX header extension (Rules 1 and 2 of the 2026-10-11 header detection spec).
# _header_count and _PERIOD stay as they are: table_completeness reads
# _header_count. A footnoted year ("2023 (2)") is a period in the export only.
_EXPORT_PERIOD = re.compile(rf'^(?:(?:(?:three|six|nine|twelve) months?|years?) ended(?: {_MONTH} \d{{1,2}},?)?'
                            rf'|(?:19|20)\d{{2}}(?: \(\d{{1,2}}\))?|{_MONTH} \d{{1,2}},? (?:19|20)\d{{2}})$', re.I)
_YEAR_TOKEN = re.compile(r'(?:19|20)\d{2}(?:\s*\(\d{1,2}\))?')
_HAS_YEAR = re.compile(r'(?:19|20)\d{2}')
_BODY_NUMBER = re.compile(r'[$(\d+−.-][\d,.() $%+−-]*')
_NIL = re.compile(r'(?:[—–-]+|n/?a|n\.a\.|nm|n/m|not meaningful|\*+)', re.I)
_PERIOD_PHRASE = re.compile(rf'\b(?:years?|months?|quarters?|weeks?|periods?) ended\b'
                            rf'|\b{_MONTH} \d{{1,2}},? (?:19|20)\d{{2}}\b', re.I)
_INSTANT = re.compile(rf'(?:as of |as at )?{_MONTH} \d{{1,2}},?', re.I)
_CURRENCY = re.compile(r'\(?(?:US\$|NT\$|HK\$|RMB|€|£|¥|\$)\)?', re.I)
_SCALE_CAPTION = re.compile(r'\((?:dollars |amounts )?in (?:thousands|millions|billions)[^)]*\)', re.I)
# A label-column caption is a period or unit caption and nothing else, so a line
# item that merely mentions a date ('Cash as of December 31, 2025') is not one.
_CAPTION_PERIOD = re.compile(
    rf'(?:(?:as of|as at|as of or for the|for the)\s+)?'
    rf'(?:(?:(?:three|six|nine|twelve) months?|(?:fiscal )?years?|quarters?) ended,?'
    rf'(?: {_MONTH} \d{{1,2}},?(?: (?:19|20)\d{{2}})?)?'
    rf'|{_MONTH} \d{{1,2}},?(?: (?:19|20)\d{{2}})?)'
    rf'(?:,? \((?:dollars |amounts )?in (?:thousands|millions|billions)[^)]*\))?', re.I)
# Column-heading words seen in the label column of real header rows.
_HEADING_WORD = re.compile(
    r'(?:description|exhibit(?: number| no\.?)?|period|issuance(?: period)?|name(?:/title| of [a-z ]+)?'
    r'|record date|payment date|plan category|instrument|fiscal year|investment type|pricing category'
    r'|range of exercise prices|type|category|item|class|security|date[a-z ]*)(?:\s*\(\d\))?', re.I)


def _row_origins(row):
    return [cell for cell in dict.fromkeys(c for c in row if c is not None) if cell.text.strip()]


def _is_data_cell(cell, digits=False):
    """A body value: a numeric fact, a number other than a bare year or, unless
    digits are required, a nil token such as 'N/A', 'NM' or a dash."""
    text = cell.text.strip()
    if cell.is_numeric_fact:
        return True
    if _YEAR_TOKEN.fullmatch(text):
        return False
    if _BODY_NUMBER.fullmatch(text):
        return not digits or bool(re.search(r'\d', text))
    return not digits and bool(_NIL.fullmatch(text))


def _period_heading(text):
    text = text.strip()
    return bool(_EXPORT_PERIOD.fullmatch(text) or _INSTANT.fullmatch(text) or _PERIOD_PHRASE.search(text))


def _caption_label(text):
    """A whole unit or period caption: '(in millions)', 'December 31,', 'As of'."""
    text = re.sub(r'\s+', ' ', text).strip()
    return bool(_UNIT_DECLARATION.fullmatch(text) or _SCALE_CAPTION.fullmatch(text)
                or re.fullmatch(r'as (?:of|at)', text, re.I) or _CAPTION_PERIOD.fullmatch(text))


def _heading_label(text):
    """A label-column cell that can head a header row ('Description', '(in millions)')."""
    return _caption_label(text) or bool(_HEADING_WORD.fullmatch(re.sub(r'\s+', ' ', text).strip()))


def _export_header_count(grid):
    """Header rows for the XLSX copy table.

    Starts from _header_count and extends it downward through heading rows, up to
    the first row with an amount. The header ends at the last accepted row with
    span evidence: a heading wider than an amount beneath it, as
    'December 31, 2024' spans '$' and '2,750'. Accepted rows after it stay in the
    body. Without a data row the count is unchanged, so text tables are too.
    """
    base = _header_count(grid)
    data = next((r for r in range(base, len(grid))
                 if any(_is_data_cell(cell, digits=True) for cell in _row_origins(grid[r]))), None)
    if data is None:
        return base

    def above(cell, index):
        """The nearest heading above any of the cell's columns."""
        for r in range(index - 1, -1, -1):
            for col in range(cell.column, cell.column + cell.colspan):
                upper = grid[r][col]
                if upper is not None and upper is not cell and upper.text.strip():
                    return upper
        return None

    def straddles(cell, index):
        """Whether the cell is not wholly under one parent heading."""
        columns = range(cell.column, cell.column + cell.colspan)
        for r in range(index - 1, -1, -1):
            uppers = [grid[r][col] for col in columns]
            if any(u is not None and u is not cell and u.text.strip() for u in uppers):
                return len(set(uppers)) != 1 or uppers[0] is None or not uppers[0].text.strip()
        return False

    def amounts_under(cell):
        return [u for u in dict.fromkeys(grid[data][col] for col in range(cell.column, cell.column + cell.colspan))
                if u is not None and _is_data_cell(u, digits=True)]

    def year_heading_ok(year, index):
        # A year heading completes a wider period heading, or an equally wide one
        # that has no year of its own ('July 30,' over '2023').
        upper = above(year, index)
        return (upper is not None and _period_heading(upper.text)
                and (upper.colspan > year.colspan
                     or (upper.colspan == year.colspan and not _HAS_YEAR.search(upper.text))))

    def rejected(index, label, headings, cells):
        if any(_is_data_cell(cell) for cell in cells):
            return True  # a body value, including 'N/A' and '.75'
        if not headings or all(_UNIT_DECLARATION.fullmatch(cell.text.strip()) for cell in headings):
            return True  # a body label: 'Assets', 'Inventories: | (In millions)'
        if label is not None and (len(headings) < 2 or not _heading_label(label.text)):
            return True  # a labelled row must look like a header row: 'Description | ...'
        for cell in headings:
            upper = above(cell, index)
            if upper is not None and cell.colspan > upper.colspan:
                return True  # header rows narrow downward
            if (label is not None and upper is not None and cell.colspan >= upper.colspan
                    and not _CURRENCY.fullmatch(cell.text.strip())):
                return True  # a labelled row must subdivide the heading above it
            if straddles(cell, index):
                return True  # a heading across two parents would misattribute amounts
            if any(cell.colspan < amount.colspan for amount in amounts_under(cell)):
                return True
            if _CURRENCY.fullmatch(cell.text.strip()) and upper is not None and cell.colspan < upper.colspan:
                return True  # 'NT$' over part of a date column would split it
        years = [cell for cell in headings if _YEAR_TOKEN.fullmatch(cell.text.strip())]
        if label is not None and (_YEAR_TOKEN.fullmatch(label.text.strip()) or (years and not _caption_label(label.text))):
            return True  # 'Revenue | 2024 | 2025' holds amounts
        return not all(year_heading_ok(year, index) for year in years)

    evidenced = base
    for index in range(base, data):
        row = grid[index]
        cells = _row_origins(row)
        if not cells:
            continue
        label = row[0] if row[0] is not None and row[0].text.strip() else None
        headings = [cell for cell in cells if cell is not label]
        if rejected(index, label, headings, cells):
            break
        if any(cell.colspan > amount.colspan for cell in headings for amount in amounts_under(cell)):
            evidenced = index + 1
    return evidenced


```

In `prepare_table()`, replace

```python
    header_count = _header_count(grid)
```

with

```python
    header_count = _export_header_count(grid)
```

Do not touch `_header_count`, `_PERIOD`, `_numeric_role`'s `period_header` line, or the title filter in `prepare_table()` that reads `_PERIOD`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_xlsx_header_detection.py`
Expected: `81 passed`.

Run: `$PY -m pytest -q -p no:cacheprovider`
Expected: `1 failed, 2057 passed, 14 deselected`, with the only failure the known `test_internal_version_matches_distribution`. The completeness, quality, parser and accuracy suites must all pass unchanged.

Run the mutation check, which disables each safeguard in turn and runs the new tests (about 15 seconds; it restores the file even on error):

```bash
$PY -I /c/Users/einstein/kelab5am/sec2md/docs/superpowers/audits/2026-10-11-xlsx-header-detection/mutation_check.py . $PY | tail -1
git diff --quiet -- src/sec2md/xlsx_tables.py || git status --short    # the file is restored
```

Expected: `all mutants behaved as expected`. Checks 2 (its unit-declaration half), 4, 5 and 7 survive by design: they are implied by other checks (spec Rule 1). Every other mutant must be caught.

Run: `git diff main -- src/sec2md/table_completeness.py` and check that `_header_count` and `_PERIOD` in `src/sec2md/xlsx_tables.py` are unchanged:

```bash
git diff main -- src/sec2md/table_completeness.py          # prints nothing
git diff main -- src/sec2md/xlsx_tables.py | grep -E '^[-+](def _header_count|_PERIOD = )'   # prints nothing
```

Run: `$PY -m ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/sec2md/xlsx_tables.py tests/test_xlsx_header_detection.py
git commit -m "fix: extend XLSX header rows on span evidence"
```

---

### Task 3: Acceptance run and audit record

**Files:**
- Read: `docs/superpowers/audits/2026-10-11-xlsx-header-detection/{export_tables.py,compare.py,primary_statements.py,filings.txt}` (on `main`)
- Create (main checkout): `docs/superpowers/audits/2026-10-11-xlsx-header-detection/README.md`, `compare.md`, `statements.md`
- Outputs (not committed): `C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection\{base,new}\*.json`, `compare.json`, `statements.json`

**Interfaces:**
- Consumes: the branch from Task 2. The baseline is the main checkout's `src`, which still has today's code because the change lives only on the branch.

- [ ] **Step 1: Export every table with both checkouts**

`filings.txt` lists the 60 filings: 42 vault 10-K/10-Q filings (18 META, 14 NVDA, 10 RDDT) and the 18 in `outputs/table-completeness-corpus`. Each export takes about 5 minutes.

```bash
cd /c/Users/einstein/kelab5am/sec2md
PY=/c/Users/einstein/kelab5am/sec2md/.worktrees/xlsx-export/.venv/Scripts/python.exe
A=docs/superpowers/audits/2026-10-11-xlsx-header-detection
O=outputs/xlsx-header-detection
$PY -I $A/export_tables.py --src src --out $O/base $(cat $A/filings.txt) | tail -1
$PY -I $A/export_tables.py --src .worktrees/xlsx-header-detection/src --out $O/new $(cat $A/filings.txt) | tail -1
ls $O/base | wc -l; ls $O/new | wc -l      # 60 and 60
```

- [ ] **Step 2: Compare and check the primary statements**

```bash
$PY -I $A/compare.py $O/base $O/new --report $A/compare.md --details $O/compare.json
$PY -I $A/primary_statements.py $O/new --report $A/statements.md --details $O/statements.json
```

Expected (the scratch validation of this exact code):

| Group | Fallback tables | Numeric cells | Lost | Changed | Balanced lost | Tables missing / added |
|---|---|---|---|---|---|---|
| META | 408 → 57 | 8,309 → 16,091 | 0 | 0 | 0 | 0 / 0 |
| NVDA | 270 → 8 | 6,550 → 13,084 | 0 | 0 | 0 | 0 / 0 |
| RDDT | 174 → 10 | 6,092 → 9,407 | 0 | 0 | 0 | 0 / 0 |
| Others | 1004 → 626 | 9,511 → 20,887 | 93 | 14 | 0 | 0 / 0 |

`statements.md`, vault rows (126 statements, 42 filings × 3): every statement exported, every XBRL fact in them `ok` (META 3,322, NVDA 2,662, RDDT 2,056; the remaining facts sit in row labels, such as share counts in a par-value line), 0 failures, 0 untagged, 0 yearless headers, 0 arithmetic problems and none ambiguous. META's FY2023 10-K cash flow statement has 3 `repeated` cells: an untagged second `Total cash, cash equivalents, and restricted cash` line equal to the tagged closing cash.

Other filings: 12 statements fall back (the label-column period captions left for the large-cap follow-up), 976 facts fail as `fallback`, 2 as `not numeric`, 10 numbers are untagged, 1 header is yearless, 1 statement is ambiguous and 13 are not found. Read each; none may be an exported number under the wrong period or with the wrong value.

Investigate any difference from these numbers before going on.

- [ ] **Step 3: Apply the acceptance criteria**

Check each against the outputs; any failure blocks the merge and goes back to the user.
1. **Primary statements, vault** (spec Acceptance 3): from `statements.md` as above.
2. **Vault, all tables** (Acceptance 4): `compare.md` shows 0 lost, 0 changed, 0 balanced columns lost and 0 tables missing or added for META, NVDA and RDDT. Read every META, NVDA and RDDT line under "promoted rows" in full. Every one must be a column heading (period or date rows, `% change` / `$ Change` columns, fair value levels, equity column headings, debt maturity and rate headings, exhibit index headings, group captions). A data row or a line item there is a defect.
3. **Other filings** (Acceptance 5): classify every lost and changed cell, and every `Others` promoted row marked `DIGITS`, as a fix or a regression, opening the filing to check the source cells. Known from the spec: TSM note references under `Notes` (fix), MSFT maturity years under `Maturities (calendar year)` (likely fix), JPM `12.3 | %` → `0.123` (fix), TSM share-ownership percentages now flagged text (regression in a 20-F filer, visible and flagged). Regressions need the user's acceptance.
4. **Spot checks** (Acceptance 6): open the `new` JSON for each table below and compare it with the filing:
   - META FY2024 10-K balance sheet: headers `December 31, — 2024` and `December 31, — 2023`; `Total assets` 276054 and 229623.
   - META FY2024 10-K revenue MD&A table: `Total revenue` 164501, 134902, 116609.
   - META FY2024 10-K Basic EPS: `Basic EPS` 24.61, 15.19, 8.63.
   - META Q1 2025 10-Q income statement: `Revenue` 42314 and 36455; `Net income` 16644 and 12369.
   - NVDA FY2024 Q2 10-Q balance sheet: headers `July 30, — 2023` and `January 29, — 2023`.
   - One RDDT 10-Q results-of-operations table: period headers with years, and amounts as numbers.

- [ ] **Step 4: Write the audit record and commit it on `main`**

Write `docs/superpowers/audits/2026-10-11-xlsx-header-detection/README.md` with:
- how to rerun (the commands above);
- the group table from `compare.md`;
- the primary-statement totals from `statements.md`;
- the reviewed promoted-row verdict (vault rows in full; other filers' digit-bearing rows);
- the mutation check result;
- every lost or changed cell in the other filings with its classification;
- the spot-check results.

Keep the large JSON outputs in `outputs/` (gitignored).

```bash
cd /c/Users/einstein/kelab5am/sec2md
git add docs/superpowers/audits/2026-10-11-xlsx-header-detection/README.md \
        docs/superpowers/audits/2026-10-11-xlsx-header-detection/compare.md \
        docs/superpowers/audits/2026-10-11-xlsx-header-detection/statements.md
git commit -m "docs: acceptance record for XLSX header detection"
```

---

### Task 5: Period-row guard (spec revision 6, Rule 1)

**Files:**
- Modify (branch): `src/sec2md/xlsx_tables.py` (the Rule 1/2 block from Task 2), `tests/test_xlsx_header_detection.py`
- Modify (main): `docs/superpowers/audits/2026-10-11-xlsx-header-detection/mutation_check.py`

**Interfaces:**
- Consumes: `_export_header_count`, `_row_origins`, `_is_data_cell`, `_MONTH`, `_header_count` (Task 2 and existing).
- Produces: `_period_text(text: str) -> bool` and `_period_row(row) -> bool` (a grid row, as `_row_origins` takes). `_export_header_count(grid)` keeps its signature.

**Behaviour** (spec Definitions "Period text" and "Period row", Rule 1 "Period-row guard"):
- `_period_text`: strip the text; remove footnote markers `\(\d{1,2}\)` and `\*+`; remove dates (`{_MONTH} \d{1,2}`), years (`(?:19|20)\d{2}`), the spec's period words (`three six nine twelve fiscal month(s) year(s) quarter(s) week(s) period(s) ended ending as of at for the and through to`, whole words, case-insensitive) and the punctuation `, . - – —`. True when only whitespace remains and the original held a date, a year or the word `ended`.
- `_period_row(row)`: the row has origins, none is a data cell (`_is_data_cell(cell)`), and at least one origin, label included, is period text.
- In `_export_header_count`, after the scan: when `evidenced > base` and any row from `evidenced` to `len(grid) - 1` is a period row, return `base`. Otherwise return `evidenced` as before.
- `_header_count`, `_PERIOD`, `_numeric_role` and `table_completeness.py` stay unchanged; the fingerprint test must still pass.

- [ ] **Step 1: Write the failing tests** (spec Testing 12f–12j), in a new section `# --- Rule 1, period-row guard` placed before `# --- Rule 3`.
  - A helper `todays(source, monkeypatch)` prepares the table with `xlsx_tables._export_header_count` monkeypatched to `xlsx_tables._header_count`. Guard cases assert `(status, headers, rows values, cell_sources, issues)` of `prepared(source)` equal those of `todays(...)`.
  - Reach the new helpers as `xlsx_tables._period_text` inside tests, not by import, so a missing helper fails only its own tests.
  - `test_guard_stacked_period_blocks` parametrized over 5 variants (12f): separate caption row; caption sharing its row with the column headings; `Three Months Ended June 30, 2025 and 2024`; `Three Months Ended June 30, 2025 (1)`; caption in the label column. Use SEC-style spans and `$`/amount pairs in both blocks, as in the D1 RDDT and META 10-Q equity statements. Each also asserts no header names the first block's period over a second-block amount.
  - `test_guard_stranded_period_rows` parametrized over 3 variants (12g): 1-column `2024 | 2023` under `December 31,` (colspan 4); unlabelled `December 31, 2023 | December 31, 2024` under `Measurement Date`; the same row labelled `Date`.
  - `test_guard_ignores_rows_with_amounts` (12h): body row `Balance as of December 31, 2024 | $ | 2,130,749` keeps the extended header (assert the extended headers explicitly).
  - `test_guard_fires_on_labelled_period_rows` parametrized over 2 variants (12h): body rows `Revenue | 2024 | 2025` and `Alpha | March 31, 2025 | June 30, 2025` (under `DATE_OVER_YEARS`, each cell spanning 3) give today's header rows.
  - Remove the `('March 31, 2025', 'June 30, 2025')` case from `test_labelled_text_row_as_wide_as_the_years_stays_in_the_body` (spec 12a, revision 6): it is a period row now, covered by the test above. This is the one existing expectation revision 6 changes; no other existing test may change.
  - `test_guard_cost_on_repeated_section_label` (12i): balance sheet with a repeated `December 31, 2025` label row gives today's header rows.
  - `test_period_text` parametrized over the spec's 7 period-text examples (True) and 4 non-period examples (False) (12j).
- [ ] **Step 2: Run them; verify they fail.** `$PY -m pytest -q -p no:cacheprovider tests/test_xlsx_header_detection.py`. Expected: `22 failed, 81 passed` (the 23 new cases except `test_guard_ignores_rows_with_amounts` fail: 11 guard cases and the 11 `test_period_text` cases; the 80 remaining existing cases and that one pass). A guard case that passes here does not exercise the guard (revision 5 already gives today's header rows): fix its fixture so revision 5 extends the header, never the expectation.
- [ ] **Step 3: Implement the behaviour above** in the Rule 1/2 block of `xlsx_tables.py`.
- [ ] **Step 4: Verify.**
  - `tests/test_xlsx_header_detection.py`: `103 passed`.
  - Full suite: `1 failed, 2079 passed, 14 deselected`, the failure being the known `test_internal_version_matches_distribution`.
  - `git diff main -- src/sec2md/table_completeness.py` prints nothing; `_header_count` and `_PERIOD` lines unchanged (as Task 2 Step 4).
  - `$PY -m ruff check src tests`: `All checks passed!`
- [ ] **Step 5: Extend the mutation check (main).** Add three mutants to `MUTANTS` in `mutation_check.py`, each of which a new test must catch: the guard disabled (`return base` never taken); `_period_row` requiring every origin to be period text (the mixed-row variant of 12f fails); footnote removal dropped from `_period_text` (the `2024 (a)` stranded-row variant fails). Run it as in Task 2 Step 4: `all mutants behaved as expected`, with the same four expected survivors, and the source file restored.
- [ ] **Step 6: Commit.** Branch: `git add src/sec2md/xlsx_tables.py tests/test_xlsx_header_detection.py`, message `fix: keep today's XLSX header when a period row follows it`. Main: `git add docs/superpowers/audits/2026-10-11-xlsx-header-detection/mutation_check.py`, message `docs: mutation check covers the period-row guard`.

- [ ] **Step 7: Fix round from the Task 5 review** (spec revision 6, "Task 5 review" in the review history; Definitions "Footnote marker", "Period text", "Period phrase", "Period row"; Testing 12f, 12g, 12h, 12j as extended).
  - Behaviour: widen `_period_text` (footnote markers with letters, the listed parenthesised qualifiers, a trailing `:`, numeric dates, week counts, `from`, a word boundary before month names); add `_PERIOD_PHRASE`-style matching for headings (non-label origins) in `_period_row`, never for the label; cells holding only a footnote marker are not data in `_period_row`.
  - Tests: 8 more `test_guard_stacked_period_blocks` variants (13 in all), 3 more `test_guard_stranded_period_rows` variants (6), a new `test_guard_ignores_label_with_period_phrase` (the supplemental cash flow label row), and 10 more `test_period_text` cases (21: the spec's 15 period-text and 6 non-period examples).
  - RED: `20 failed, 105 passed` (the 8 new 12f variants, the 3 new 12g variants, the 8 new period-text examples and `Market 10`; the new label test and the `Cash paid …` example already pass). GREEN: `125 passed`. Full suite: `1 failed, 2101 passed, 14 deselected`.
  - Mutation check (main): three more mutants, each caught: the heading period-phrase clause removed (the `, as restated` variant fails); footnote-only cells counted as data (the separate `(1)` cell variant fails); the period phrase allowed in the label (the supplemental label test fails).
  - Commit the branch change as `fix: widen the XLSX period-row guard` and the mutants on main as `docs: mutation check covers the widened period-row guard`.

---

### Task 6: All-table XBRL period check (spec Acceptance 3b)

**Files (main):**
- Create: `docs/superpowers/audits/2026-10-11-xlsx-header-detection/all_facts.py`, `docs/superpowers/audits/2026-10-11-xlsx-header-detection/test_all_facts.py`
- Read: `outputs/xlsx-header-detection/task-3/allfacts.py` (Task 3's scratch version, the starting point), `primary_statements.py` (its `header_period`, `displayed`)

**Interfaces:**
- `python -I all_facts.py EXPORT_DIR --report REPORT_MD --details DETAILS_JSON`, run once per export directory.
- Keep `primary_statements.py` unchanged; add any period parsing all_facts needs in all_facts.py.

**Behaviour** (spec Acceptance 3b): for every table that is not `source_text_only` and every inline XBRL fact, one verdict: `ok`, `mismatch`, `no header date`, `label column` (column 0), or `not placed` (no copy cell). Separately, list every such table that has `is_numeric_fact` source cells but no located facts, with the count (Codex found 7 in revision 5's exports, 3 of them NVDA). Instants: within 7 days of the header date, or at the start of a stated period. Durations: ending within 7 days of the header date with the stated length (`three months` and `quarter` 3, `six months` 6, `nine months` 9, `year`, `fiscal year` and `twelve months` 12); a duration starting the day after the header date is `ok` only under a header that states no length. The report gives verdict counts per group (META, NVDA, RDDT, Others), every mismatch with filing, ordinal, title, source cell, fact context and header, and every table with a yearless period header (a header with period wording and no year).

- [ ] **Step 1: Tests first.** `test_all_facts.py` checks the period rule directly: a 6-month duration under `Three Months Ended June 30, 2025` → mismatch; a duration starting the day after `Three Months Ended March 31, 2025` → mismatch; a 6-month duration under `Quarter ended June 30, 2025` → mismatch; a duration starting the day after a bare `December 31, 2024` header → ok; durations starting on `December 31, 2024` or `December 30, 2024` under that bare header → mismatch (Task 3's scratch checker wrongly accepts both); an instant at the start of `Three Months Ended March 31, 2025` (opening balance) → ok; a 3-month duration under `Three Months Ended March 31, 2025` → ok. Run `$PY -m pytest -q -p no:cacheprovider docs/superpowers/audits/2026-10-11-xlsx-header-detection/test_all_facts.py`: they fail before `all_facts.py` exists, then `8 passed`.
- [ ] **Step 2: Implement `all_facts.py`** and run it on Task 3's exports: `outputs/xlsx-header-detection/base` and `new` (revision 5). The D1 tables (9 META and 12 RDDT 10-Q equity statements) must show as mismatches on `new` and not on `base`; if not, the checker is wrong. Record the counts in the task report.
- [ ] **Step 3: Commit (main):** the two files, message `docs: all-table XBRL period check for XLSX header detection`.

---

### Task 7: Acceptance rerun for revision 6 and audit update

**Files (main):** Modify `docs/superpowers/audits/2026-10-11-xlsx-header-detection/README.md`, `compare.md`, `statements.md`; Create `all-facts.md`. Outputs (not committed): `outputs/xlsx-header-detection/new6/`.

- [ ] **Step 1: Export with the branch** (Task 5's code) into `outputs/xlsx-header-detection/new6`; reuse `base` from Task 3 (the main checkout's `src` has not changed). 60 files.
- [ ] **Step 2: Run** `compare.py base new6`, `primary_statements.py new6`, and `all_facts.py` on `base` and `new6`, writing `compare.md`, `statements.md` and `all-facts.md` into the audit directory. Also compare `new` (revision 5) with `new6` table by table.
- [ ] **Step 3: Gates.** Any failure stops the work and goes to the user, with no expectation adjusted:
  1. Every table that differs between `new` and `new6` is one where the guard fired, and its `new6` headers and status equal `base`'s (list them all; a cell value that still differs from `base` must be a Rule 3 difference, classified). The 21 D1 tables and TSM #105 are among them.
  2. Vault primary statements (spec Acceptance 3): all 126 still export; every fact `ok`; the same counts as Task 3 (META 3,322, NVDA 2,662, RDDT 2,056 ok facts), 0 failures, 0 yearless headers. A vault balance sheet, income statement or cash flow statement falling back is a stop.
  3. Vault, all tables (Acceptance 4): 0 lost, 0 changed, 0 balanced lost, 0 missing or added.
  4. Acceptance 3b: 0 real misattributions in any filing. Every mismatch and yearless period header, on `base` and on `new6`, is classified with its source cells (those on `base` marked existing). Every vault table with numeric-fact cells but no located facts is checked by hand against the filing (headers carry the right periods, values match) and the result recorded.
  5. Others (Acceptance 5): reclassify only what changed since Task 3; TSM #105 should no longer be a regression.
- [ ] **Step 4: Update the audit README** with a "Revision 6" section: the rerun commands, the new group table, primary-statement totals, all-facts totals (base vs new6), the guard-fired table list, the gate results and the remaining regressions needing the user's acceptance. Keep the revision 5 record above it.
- [ ] **Step 5: Commit (main):** `README.md`, `compare.md`, `statements.md`, `all-facts.md`, message `docs: acceptance record for XLSX header detection revision 6`.

---

### Task 4: CHANGELOG, usage doc and handoff

Runs after Task 7. Revision 6 changes to this task: the CHANGELOG bullet's fallback numbers (`852 to 75`) and its claims come from Task 7's README, and it adds one sentence: `A body row holding a period caption and no amounts, as in stacked 10-Q equity statements, keeps today's header so no number lands under another block's period.` Step 3's expected full suite is `1 failed (known), 2101 passed`, and `git log --oneline main..HEAD` shows five commits (Tasks 1, 2, 5, the Task 5 fix round, 4).

**Files:**
- Modify (branch): `CHANGELOG.md`, `docs/usage/xlsx-export.md`
- Modify (main): spec status line

- [ ] **Step 1: CHANGELOG entry**

Add this bullet at the top of the `0.1.22+rcq.4` section of `CHANGELOG.md` on the branch:

```markdown
- XLSX export reads more header rows, so statement and note tables export as
  numbers under period headers instead of as source text. A header now extends
  through rows such as a bare `December 31,` over the years, `% change` columns,
  footnoted years (`2023 (2)`) and labelled heading rows (`Description`,
  `Pricing Category`), but only with span evidence: the row directly above the
  data must have a heading wider than an amount beneath it. Rows that look like
  data, a heading across two parent periods and labelled rows of year-shaped
  amounts keep today's output or fall back to source text. Identifier columns
  are judged per header part, so `Number of Shares` and `Year ended March 31,
  — 2023 — RMB` hold numbers while `CUSIP as of December 31, 2024` and
  `December 31, 2024 — Notes` stay text. `_header_count`, Markdown output,
  strict and the table completeness check are unchanged. On the RCQ vault's 42
  META, NVDA and RDDT filings, fallback tables fall from 852 to 75, no number
  that converted before changes, and every number in the balance sheets, income
  statements and cash flow statements equals the inline XBRL fact in its own
  source cell, with that fact's period in its column header
  (`docs/superpowers/audits/2026-10-11-xlsx-header-detection/`).
```

- [ ] **Step 2: Usage doc**

In `docs/usage/xlsx-export.md`, after the paragraph that begins "Each worksheet contains the title, reported units, headers and values", add:

```markdown
Header rows are read from the table's own layout. Besides `<th>` rows and period
rows, a row joins the header when it reads as a heading and the row directly above
the data spans the `$` and amount cells beneath it, as `December 31, 2024` does.
Each column header joins its levels with ` — `, such as `December 31, — 2024` or
`Year Ended December 31, — 2024 vs 2023 % change`. Rows that might be data stay
in the body. When a header cannot be established, the table keeps its original
grid instead.
```

- [ ] **Step 3: Final verification and commit**

```bash
cd /c/Users/einstein/kelab5am/sec2md/.worktrees/xlsx-header-detection
$PY -m pytest -q -p no:cacheprovider 2>&1 | tail -2     # 1 failed (known), 2033 passed
$PY -m ruff check src tests                              # All checks passed!
git add CHANGELOG.md docs/usage/xlsx-export.md
git commit -m "docs: changelog and usage for XLSX header detection"
git log --oneline main..HEAD                             # three commits
```

- [ ] **Step 4: Mark the spec implemented on `main`**

In the main checkout, change the spec's `Status:` line to
`Status: Implemented on branch fix/xlsx-header-detection (pending PR). Acceptance: ../audits/2026-10-11-xlsx-header-detection/README.md.`
and commit it on `main`:

```bash
cd /c/Users/einstein/kelab5am/sec2md
git add docs/superpowers/specs/2026-10-11-sec2md-xlsx-header-detection-design.md
git commit -m "docs: mark XLSX header detection spec implemented"
```

- [ ] **Step 5: Hand off**

Report to the user:
- the branch and its three commits;
- the acceptance table;
- the classification of every non-vault lost or changed cell;
- any regression that needs their acceptance.

Do not push. After the user merges, the vault workbooks are re-exported with the `xbrl-to-excel` skill's `--reextract`.
