# sec2md Table Completeness Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report, for every visible source table, the numbers its Markdown lost (check 1) and the rows or values whose order changed (check 2), plus document numeric recall (check 3). The checks never change rendering and never fail strict mode yet (Phase A).

**Architecture:** A new module `src/sec2md/table_completeness.py` compares each visible outermost `<table>` with the exact text the parser emitted for it. `Parser` records that text and the table's page and snapshot ordinal during its normal traversal. It runs `check_tables()` once after page assembly, and passes the report to `build_diagnostics()`. The results surface in new defaulted `ParseDiagnostics` fields, a new `convert_with_diagnostics()` function, warning log lines, and two new defaulted XLSX result fields.

**Tech Stack:** Python `>=3.10,<3.13`, BeautifulSoup 4 with lxml, pytest, ruff (rules `E4`, `E7`, `E9`, `F`), optional openpyxl for the XLSX tests. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`](../specs/2026-10-02-sec2md-table-completeness-check-design.md) (revision 6). Its review record is [`../reviews/2026-10-02-sec2md-table-completeness-check-review.md`](../reviews/2026-10-02-sec2md-table-completeness-check-review.md). This plan's own review record is [`../reviews/2026-10-03-sec2md-table-completeness-plan-review.md`](../reviews/2026-10-03-sec2md-table-completeness-plan-review.md). The reviewed prototype this plan reproduces is in [`../audits/2026-10-02-repo-audit/prototypes/v6/`](../audits/2026-10-02-repo-audit/prototypes/v6/).

## Global Constraints

- **Phase A is report-only.** Strict never raises because of a table completeness finding. Decision D1 assumes the spec's recommended option.
- **Phase A ends with the corpus run.** It is complete only when the corpus run (Task 11) is recorded in the spec and reviewed.
- **Rendering is unchanged.** Non-capture rendering is byte-identical with and without the checks, and capture-mode snapshots are identical too.
  - The accuracy suite's scores and Markdown hashes must equal unchanged `main`'s on every fixture (Task 12).
- **Policy `off` skips all three checks.** Every other policy computes them.
- **New dataclass fields are trailing and defaulted** on `ParseDiagnostics`, `XlsxExportResult` and `XlsxTableResult`. Existing positional construction and pickling keep working.
- **In Phase A the XLSX fields change nothing else.** `status`, `issues` and `diagnostics` of XLSX results are unchanged.
- **Diagnostics API:** add `convert_with_diagnostics(source, **kwargs) -> tuple[str | list[Page], ParseDiagnostics]`. The existing functions keep their return types (decision D2).
- **Token classes are per token** (decision D4):
  - Markers and references are reported only.
  - Every other token is a value and counts as a failure, whatever its digit count.
  - Period-header tokens stay values, under the `header` role.
  - Ambiguous value shortfalls are failures, labelled `ambiguous`.
- **Overhead (Phase A):** at most +25% of `Parser.get_pages()` time on the 7 fixtures in total, against an unchanged `main`. This was decided by the user on 2026-10-03.
  - Measure it with `overhead_vs_main.py` (Task 12) and report each fixture's figure in the PR.
  - The spec's 10% target moves to Phase B.
- **No extra work with the checks off.** `Parser(table_checks=False)` in normal mode does the same table work as `main`: one `_effective_rows()` traversal per table, and no metadata.
- **No new dependencies.** `python -m ruff check src tests` must pass.
- **`E:\RCQWealth` is read-only.** Never write there.
- **Design documents stay in the main checkout.** Specs, plans, audits and reviews live under `C:\Users\einstein\kelab5am\sec2md\docs\superpowers\` on `main`, never in the worktree.
  - The worktree commits only `src/`, `tests/`, `README.md`, `docs/usage/` and `CHANGELOG.md`.
  - Findings for the spec go back to the main checkout, not into the branch.

## Before you start

- **Worktree.** Implement in a worktree at `C:\Users\einstein\kelab5am\sec2md\.worktrees\table-completeness`, on a new branch `feat/table-completeness` from `main`. Create it with superpowers:using-git-worktrees. `main` must already contain:
  - this plan;
  - `prototypes/v6/parity_impl.py`, `prototypes/v6/overhead_vs_main.py` and `prototypes/v6/accuracy_vs_main.py`;
  - `docs/superpowers/audits/2026-10-03-table-completeness-corpus/`.
- **Baseline checkout.** The overhead baseline is the main checkout `C:\Users\einstein\kelab5am\sec2md` at the branch's base commit. If `main` moves on, make a detached worktree of the base commit and use that as the baseline instead.
- **Environment.** In the worktree, install with `python -m pip install -e ".[dev,xlsx]"`, then run `python -m pytest -q` to see the baseline pass.
  - If another sec2md install is active, the conftest guard stops the run. Prefix commands with `PYTHONPATH=src` in bash, or set `$env:PYTHONPATH="src"` in PowerShell.
  - `tests/test_xlsx.py::test_package_import_without_extra` starts a subprocess that must import the worktree's `sec2md`, so it needs the editable install or `PYTHONPATH`.
- **Paths.** All paths below are relative to the worktree root.

## Reviewer notes: where this plan differs from the spec

The code in this plan was run end to end on a scratch copy of `main` at `16a3e48`, before the plan was written, and again after plan review round 1:

- **Full suite:** 790 tests passed, 594 of them the existing suite, unchanged.
- **Ruff:** passes.
- **Finding parity:** findings equal the v6 prototype's on all 27 documents (7 fixtures, 20 RCQ filings) in both rendering modes: 0 mismatches.
- **Fixture figures:** the same as the spec's:
  - 290 tables checked
  - 9 tables flagged, with 20 value tokens
  - 1 reference token
  - 0 check-2 findings
  - mutation detection 50, 50 and 48 of 57
- **Overhead against unchanged `main`:**

  | Fixture | Overhead |
  |---|---|
  | AAPL 10-K | +24.0% |
  | NVDA 10-K | +20.1% |
  | NVDA 2002 10-K | +18.5% |
  | NVDA 10-Q | +21.9% |
  | NVDA 8-K | +15.1% |
  | EX-99.1 | +23.4% |
  | EX-99.2 | +23.0% |
  | **Total** | **+20.6%** |

**Plan review round 1** ([record](../reviews/2026-10-03-sec2md-table-completeness-plan-review.md)) changed three things:

- **Header rows are always computed.** An earlier draft computed them only when a table had value findings or year-only rows. That let a `<th>` row such as `Denomination | €1 | €2` count as a data row, so an unchanged table reported "values out of order". Now every table with digits gets its header rows, matching v6 exactly.
  - Header-cell text is read lazily, only for the rows `_header_count` examines.
  - Regression tests: Tasks 5 and 6.
- **No metadata work without capture or checks.** The draft computed snapshot ordinals for every table even with the checks off, which doubled the `_effective_rows()` traversals.
  - The parser now skips that work unless capture or the checks need it.
  - When they do, the parser reuses the rows for rendering.
  - The checks-off configuration now matches `main`: one traversal per table. Regression test: Task 6.
  - Overhead is measured against an unchanged `main` checkout, not against `table_checks=False`.
- **The corpus run is in the plan.** The ≥50-filing corpus run and the D3 measurement are now Task 11, before Phase A can be called complete.

Where the plan still departs from the spec text:

1. **Snapshot metadata without snapshots.** The spec says non-capture mode calls `snapshot_html_table()` for metadata only. Doing that for every table added 72% to parse time, so the plan doesn't.
   - **Ordinals:** snapshot ordinals are counted in the same parse whenever capture or the checks are on (`Parser._snapshot_ordinal`).
   - **Header rows:** they come from `header_row_count()`. It builds the grid with the snapshot builder's placement rules and calls `xlsx_tables._header_count()` on it.
   - **Verification:** header-row counts equal the snapshot-derived counts for every snapshot table in the 27 documents (0 mismatches).
2. **Check 3 normalizer.** The spec says recall is computed "the same way as the accuracy suite's `normalize_numbers`". That function lives in `tests/` and cannot be imported from `src/`.
   - The plan uses `quality._normalized_numbers()` over `_visible_source_text()` and `_visible_markdown_text()`, the visible text `build_diagnostics()` already computes.
   - The spec sentence should change to match.
3. **Header-only table.** The spec's testing list expects no finding for "a header-only table". The renderer actually drops year columns from header-only tables:
   - `| Item | 2026 | 2025 |` above a `$ | $` row renders as `| Item | 2026 |`.
   - The check reports `2025` correctly. This is a real loss of the column-fusion kind and belongs to the table-merge and header-rules spec.
   - The plan's no-finding case is therefore a header-only table without numbers.
4. **Reported class names.** Reported tokens carry `reference`, `marker` or `standalone_marker`, for example `missing 9 x1 [standalone_marker]`.
5. **Parenthesized markers.** These normalize like accounting negatives on both sides, so a lost plain-text `(1)` appears as `-1`, as in AAPL table 13. Matching is unaffected.
6. **New parser surface.**
   - `Parser(..., table_checks=True)`, `Parser.table_report` and `Parser.table_outputs`.
   - `Parser._render_table()`, extracted from `_process_element()` with its three branches unchanged.
   - Positioned-div tables advance the shared ordinal counter, so ordinals match capture mode, but they are not checked. They are listed under Deferred in the spec.
7. **Overhead target.** The spec's 10% target moves to Phase B. Phase A accepts up to +25% against unchanged `main`, by the user's decision of 2026-10-03.
   - Task 11 records this in the spec alongside the corpus results.

**Decisions assumed:** D1–D4 take the spec's recommended options. If Astra picks another option, Tasks 7 and 8 change.

## File structure

| File | Responsibility |
|---|---|
| Create `src/sec2md/table_completeness.py` | The checks. Covers cell text and tokens, token classes, output positions, period and data rows, header rows without snapshots, matching, row structure, and the `TableFinding`/`TableCompletenessReport` types. Exposes `check_tables()`. No rendering. |
| Modify `src/sec2md/quality.py` | Euro and pound normalization; precompiled number patterns; new `ParseDiagnostics` fields; `build_diagnostics(table_report=...)`; check-3 recall; warning log lines. |
| Modify `src/sec2md/parser.py` | `table_checks` flag, `_render_table()`, recording of table outputs, pages and snapshot ordinals; runs `check_tables()`. |
| Modify `src/sec2md/core.py` | Skip the checks under `off`; `convert_with_diagnostics()` via a shared `_convert()`. |
| Modify `src/sec2md/__init__.py` | Export `convert_with_diagnostics`. |
| Modify `src/sec2md/xlsx.py` | `XlsxTableResult.completeness`, `XlsxExportResult.parse_diagnostics`. |
| Create `tests/test_table_completeness.py` | Unit tests for the module (Tasks 2–5). |
| Create `tests/test_table_completeness_parser.py` | Every review case through `Parser`, in both rendering modes (Task 6). |
| Create `tests/test_table_completeness_fixtures.py` | Pinned fixture failures, mutations, unchanged rendering (Task 10). |
| Modify `tests/test_quality.py`, `tests/test_core.py`, `tests/test_xlsx.py` | Normalizer, diagnostics, API and XLSX tests. |
| Modify `README.md`, `docs/usage/direct-conversion.md`, `docs/usage/xlsx-export.md`, `CHANGELOG.md` | What strict checks and does not check; the new diagnostics. |
| Main checkout only: `docs/superpowers/audits/2026-10-03-table-completeness-corpus/` | Corpus tooling (`fetch_edgar.py`, `corpus_phase_a.py`, already on `main`), the Phase A results and classification (Task 11). |
| Main checkout only: the spec | The Phase A corpus record and the overhead decision (Task 11). |

---

### Task 1: Euro and pound in the shared number normalizer

The table checks reuse `quality._normalized_numbers()`. Today its pattern accepts `€` and `£`, but `normalize_numeric_token()` strips only `$`, so `€123` normalizes to nothing. This task also compiles the two patterns once, because the checks call this function many times.

**Files:**
- Modify: `src/sec2md/quality.py` (constants after `_QUALITY_POLICIES`, `normalize_numeric_token()`, `_normalized_numbers()`)
- Test: `tests/test_quality.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `normalize_numeric_token("€123") == "123"`; `quality._normalized_numbers(text: str) -> tuple[str, ...]` (signature unchanged).

- [x] **Step 1: Write the failing tests**

Append to `tests/test_quality.py`:

```python
# --- table completeness: normalizer, diagnostics fields, recall and logging --------------

def test_normalize_numeric_token_strips_euro_and_pound():
    assert normalize_numeric_token("€123") == "123"
    assert normalize_numeric_token("£ (456)") == "-456"


def test_normalized_numbers_reads_euro_and_pound_values():
    from sec2md.quality import _normalized_numbers

    assert _normalized_numbers("€1,234 and £5") == ("1234", "5")
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_quality.py -q -k "euro_and_pound"`
Expected: 2 failures. `normalize_numeric_token("€123")` returns `None`, and `_normalized_numbers` returns `()`.

- [x] **Step 3: Implement**

In `src/sec2md/quality.py`, add after `_QUALITY_POLICIES = frozenset({"strict", "warn", "off"})`:

```python
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_NUMBER_TOKEN_RE = re.compile(r"(?<![\w.])(?:[$€£]\s*)?\(?\s*[−–-]?\d[\d,]*(?:\.\d+)?\s*\)?%?(?!\w|\.\w)")
_CURRENCY_SYMBOLS = str.maketrans({"$": None, "\u20ac": None, "\u00a3": None})
```

In `normalize_numeric_token()`, replace

```python
    cleaned = cleaned.replace(",", "").replace("$", "").replace("%", "").strip()
```

with

```python
    cleaned = cleaned.translate(_CURRENCY_SYMBOLS).replace(",", "").replace("%", "").strip()
```

In `_normalized_numbers()`, replace

```python
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    normalized: list[str] = []
    pattern = r"(?<![\w.])(?:[$€£]\s*)?\(?\s*[−–-]?\d[\d,]*(?:\.\d+)?\s*\)?%?(?!\w|\.\w)"
    for match in re.finditer(pattern, text):
```

with

```python
    text = _MARKDOWN_IMAGE_RE.sub("", text)
    normalized: list[str] = []
    for match in _NUMBER_TOKEN_RE.finditer(text):
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_quality.py tests/accuracy -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/quality.py tests/test_quality.py
git commit -m "fix: normalize euro and pound amounts like dollar amounts"
```

---

### Task 2: Cell text and tokens

Creates the module with its full import and constant block, which Tasks 3–5 use without changing it, and the text primitives:

- **`numbers()`** returns a cell's normalized tokens:
  - `€` and `£` are unified with `$`.
  - A dash between two numbers is a range separator, not a minus sign.
  - The result is cached per document.
- **`merge_split_negatives()`** rebuilds `(29` + `)` and `(` + `29` + `)` across adjacent cells.
- **`hidden_sets()`** computes, once per document, the hidden nodes under each outermost table:
  - one set by the source-text rule (`quality._is_hidden_tag`, plus `script`, `style`, `template` and `noscript`);
  - one by the XLSX snapshot rule (`xlsx_tables._hidden`).
- **`cell_text()`** returns a cell's visible text, with footnote markers separated:
  - `sup`, `vertical-align:super`, and fragment links whose text is `(n)`, `[n]` or `*` are markers.
  - Relative positioning and bare-digit fragment links are not.

**Files:**
- Create: `src/sec2md/table_completeness.py`
- Create: `tests/test_table_completeness.py`

**Interfaces:**
- Consumes: `quality._normalized_numbers`, `quality._is_hidden_tag`, `quality._MARKDOWN_LINK_RE`, `xlsx_tables._hidden`, `xlsx_tables._header_count`, `xlsx_tables._visible_text`, `chunker.blocks.is_separator_row`.
- Produces:
  - `numbers(text: str) -> tuple[str, ...]`
  - `merge_split_negatives(cells: list[str]) -> list[str]`
  - `output_line_numbers(line: str) -> list[str]`
  - `hidden_sets(soup) -> tuple[list[Tag], set[int], set[int]]`, returning (outermost tables, hidden ids, grid-hidden ids)
  - `cell_text(cell: Tag, hidden: set[int]) -> tuple[str, str]`, returning (value text, marker text)

- [x] **Step 1: Write the failing tests**

Create `tests/test_table_completeness.py`:

```python
"""Unit tests for the table completeness checks (spec 2026-10-02, revision 6)."""

from collections import Counter

import pytest
from bs4 import BeautifulSoup

from sec2md.table_completeness import (
    cell_text,
    hidden_sets,
    merge_split_negatives,
    numbers,
    output_line_numbers,
)


def soup_of(html):
    return BeautifulSoup(html, "lxml")


# --- task 2: text and tokens -----------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("€123", ("123",)),
    ("£456", ("456",)),
    ("$ (16,173)", ("-16173",)),
    ("3.5%-4.3%", ("3.5", "4.3")),
    ("2024 – 2026", ("2024", "2026")),
    ("Revenue", ()),
])
def test_numbers_normalizes_currency_and_range_dashes(text, expected):
    assert numbers(text) == expected


@pytest.mark.parametrize("cells, expected", [
    (["Loss", "(29", ")"], ["Loss", "(29)"]),
    (["Loss", "(", "29", ")"], ["Loss", "(29)"]),
    (["Margin", "(3.2", ")%"], ["Margin", "(3.2)%"]),
    (["Revenue", "", "120", " "], ["Revenue", "120"]),
])
def test_merge_split_negatives(cells, expected):
    assert merge_split_negatives(cells) == expected


def test_output_line_numbers_tokenizes_each_cell_separately():
    assert output_line_numbers("| Loss | (29 | ) | 1,2 | 34 |") == ["-29", "12", "34"]


def test_hidden_sets_scopes_to_outermost_tables():
    soup = soup_of(
        '<div style="display:none"><table id="a"><tr><td>1</td></tr></table></div>'
        '<table id="b"><tr><td>2<span style="display:none">999</span>'
        '<table id="c"><tr><td>3</td></tr></table></td></tr></table>'
    )
    outermost, hidden, _ = hidden_sets(soup)
    assert [t["id"] for t in outermost] == ["a", "b"]
    assert id(soup.find(id="a")) in hidden
    assert id(soup.find(id="b")) not in hidden
    assert id(soup.find("span")) in hidden


@pytest.mark.parametrize("cell, expected", [
    ("<td>1,2<span>34</span></td>", ("1,234", "")),
    ("<td>Revenue<sup>(1)</sup></td>", ("Revenue", "(1)")),
    ('<td>Revenue<span style="vertical-align:super">2</span></td>', ("Revenue", "2")),
    ('<td>Revenue<a href="#f1">(1)</a></td>', ("Revenue", "(1)")),
    # NVDA kerns single digits with relative positioning and splits dates across
    # fragment links; neither is a footnote marker.
    ('<td><span style="position:relative;top:1px">1</span>23</td>', ("123", "")),
    ('<td>January <a href="#x">2</a>9, 2025</td>', ("January 29, 2025", "")),
    ("<td>Revenue<br/>Net</td>", ("Revenue Net", "")),
])
def test_cell_text_separates_footnote_markers(cell, expected):
    soup = soup_of(f"<table><tr>{cell}</tr></table>")
    _, hidden, _ = hidden_sets(soup)
    assert cell_text(soup.find("td"), hidden) == expected


def test_cell_text_skips_hidden_descendants():
    soup = soup_of('<table><tr><td>100<span style="display:none">999</span></td></tr></table>')
    _, hidden, _ = hidden_sets(soup)
    assert cell_text(soup.find("td"), hidden) == ("100", "")
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'sec2md.table_completeness'`.

- [x] **Step 3: Implement**

Create `src/sec2md/table_completeness.py`:

```python
"""Source-to-output completeness checks for tables.

Implements docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md
(revision 6). Each visible outermost source table is compared with the exact text the
parser emitted for it. Check 1 reports source numbers missing from that text; check 2
reports rows and values that changed order. Nothing here changes rendering.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

from bs4 import NavigableString, Tag
from bs4.element import Comment, Declaration, Doctype, ProcessingInstruction

from sec2md.chunker.blocks import is_separator_row
from sec2md.quality import _MARKDOWN_LINK_RE, _is_hidden_tag, _normalized_numbers
from sec2md.xlsx_tables import _header_count, _hidden as _grid_hidden, _visible_text

_BLOCK = {"p", "div", "br", "li", "tr", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"}
_SKIP_STRINGS = (Comment, Declaration, Doctype, ProcessingInstruction)
_NEVER_VISIBLE = {"script", "style", "template", "noscript"}
# Relative positioning is not a marker signal: NVDA uses it to kern single digits.
_MARKER_STYLE = re.compile(r"vertical-align\s*:\s*super", re.I)
# A bare digit in a fragment link is not a marker: NVDA splits dates across such links.
_MARKER_TEXT = re.compile(r"\(\*?\d{1,2}\)|\*+|\[\d{1,2}\]")
# A hyphen or en dash between two numbers is a range separator, not a minus sign.
_RANGE_DASH = re.compile(r"(?<=[\d%])\s*[-–]\s*(?=[$(]?\d)")
_CURRENCY = str.maketrans({"€": "$", "£": "$"})
_IDENTIFIER = re.compile(r"\b(?:item|note|exhibit|part|schedule)\s+\d+[A-Z]?(?:\.\d+)?\.?", re.I)
_SIGNATURE_CELL = re.compile(r"^\s*dated?\s*:|/s/", re.I)
_SIGNATURE_ROW_MARK = re.compile(r"/s/|^\s*dated?\s*:\s*$", re.I)
_DATE_CELL = re.compile(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+(?:19|20)\d{2}$"
                        r"|^\d{1,2}/\d{1,2}/\d{2,4}$", re.I)
# Split accounting negatives: "(29" + ")", "(3.2" + ")%", "(" + "29" + ")".
_OPEN_AMOUNT = re.compile(r"^[$€£]?\s*\(\s*[$€£]?\s*\d[\d,]*(?:\.\d+)?$")
_OPEN_ONLY = re.compile(r"^[$€£]?\s*\($")
_PLAIN_AMOUNT = re.compile(r"^[$€£]?\s*\d[\d,]*(?:\.\d+)?$")
_CLOSE = re.compile(r"^\)\s*%?$")
_STANDALONE_AMOUNT = re.compile(r"^[$€£]?\s*\(?\s*[$€£]?\s*[-−]?\d[\d,]*(?:\.\d+)?\s*\)?\s*%?$")
_BARE_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_PERIOD_TEXT = re.compile(r"\b(?:years?|quarters?|months?|weeks?|period|ended|ending|as of|fiscal|calendar|maturit\w*)\b"
                          r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}\b", re.I)
# A trailing footnote reference glued to a value in the output ("1,234 (1)").
_MARKER_SUFFIX = re.compile(r"(?:\s*(?:\(\d{1,2}\)|\[\d{1,2}\]|\*+))+\s*$")
_LETTER = re.compile(r"[A-Za-z]")
_NOT_LETTER = re.compile(r"[^a-z]+")
_ALPHANUMERIC = re.compile(r"[A-Za-z\d]")
_SPACES = re.compile(r"\s+")
_EXHIBIT_HEADING = re.compile(r"\s*exhibit\b", re.I)
_DESCRIPTION_HEADING = re.compile(r"\bdescription\b", re.I)
_DIGIT = re.compile(r"\d")

# Output positions each source occurrence may claim, in order of preference.
_COMPATIBLE = {
    "reference": ("reference", "text_cell", "text_rendering", "header_line"),
    "marker": ("text_cell", "text_rendering", "header_line"),
    "standalone_marker": ("numeric_cell", "header_line", "text_rendering"),
    "value_numeric": ("numeric_cell", "header_line", "text_rendering"),
    "value_text": ("text_cell", "numeric_cell", "header_line", "text_rendering"),
}
_CLAIM_ORDER = ("reference", "marker", "standalone_marker", "value_numeric", "value_text")


# --- text and tokens ---------------------------------------------------------------

@lru_cache(maxsize=65536)
def numbers(text: str) -> tuple[str, ...]:
    """Normalized numeric tokens: currency symbols unified, range dashes not minus signs."""
    if not _DIGIT.search(text):
        return ()  # most label cells: skip the token regexes entirely
    return _normalized_numbers(_RANGE_DASH.sub(" - ", text.translate(_CURRENCY)))


def merge_split_negatives(cells: list[str]) -> list[str]:
    """Rebuild accounting negatives split across adjacent non-empty cells of one row."""
    texts = [c.strip() for c in cells if c and c.strip()]
    merged, i = [], 0
    while i < len(texts):
        here = texts[i]
        nxt = texts[i + 1] if i + 1 < len(texts) else ""
        after = texts[i + 2] if i + 2 < len(texts) else ""
        if _OPEN_AMOUNT.match(here) and _CLOSE.match(nxt):
            merged.append(here + nxt.replace(" ", ""))
            i += 2
        elif _OPEN_ONLY.match(here) and _PLAIN_AMOUNT.match(nxt) and _CLOSE.match(after):
            merged.append(here + nxt + after.replace(" ", ""))
            i += 3
        else:
            merged.append(here)
            i += 1
    return merged


def output_line_numbers(line: str) -> list[str]:
    """Tokens of one output line, cell by cell, with split negatives rebuilt."""
    return [t for cell in merge_split_negatives(line.split("|")) for t in numbers(cell)]


def _self_hidden(tag: Tag) -> tuple[bool, bool]:
    """(hidden by the source-text rule, hidden by the XLSX snapshot rule) for one tag."""
    name = tag.name
    by_name = name in _NEVER_VISIBLE or name in ("ix:hidden", "hidden") or name.endswith(":hidden")
    attrs = tag.attrs
    if not attrs:
        return by_name, False
    # Both rules need a hidden/aria-hidden attribute or "none"/"hidden" in the style;
    # checking that first skips the full rules for almost every styled tag.
    style = str(attrs.get("style", "")).lower()
    if "hidden" not in attrs and "aria-hidden" not in attrs and "none" not in style and "hidden" not in style:
        return by_name, False
    return by_name or _is_hidden_tag(tag), _grid_hidden(tag)


def hidden_sets(soup) -> tuple[list[Tag], set[int], set[int]]:
    """Outermost tables and the hidden nodes inside them, from one scoped pass.

    Returns (outermost tables, hidden, grid_hidden). hidden follows
    quality._is_hidden_tag plus script, style, template and noscript, and decides what
    counts as source text. grid_hidden follows the XLSX snapshot rule, so header rows
    match the grids snapshots build. Only tables and their ancestor chains are examined.
    """
    hidden: set[int] = set()
    grid_hidden: set[int] = set()
    ancestors: dict[int, tuple[bool, bool]] = {}
    outermost = []
    for table in soup.find_all("table"):
        if table.find_parent("table") is not None:
            continue
        outermost.append(table)
        chain, flags = [], (False, False)
        for parent in table.parents:
            if not isinstance(parent, Tag):
                continue
            if id(parent) in ancestors:
                flags = ancestors[id(parent)]
                break
            chain.append(parent)
        for parent in reversed(chain):
            own = _self_hidden(parent)
            flags = (flags[0] or own[0], flags[1] or own[1])
            ancestors[id(parent)] = flags
        stack = [(table, flags)]
        while stack:
            node, (text_hidden, grid_rule) = stack.pop()
            own = _self_hidden(node)
            text_hidden, grid_rule = text_hidden or own[0], grid_rule or own[1]
            if text_hidden:
                hidden.add(id(node))
            if grid_rule:
                grid_hidden.add(id(node))
            stack.extend((child, (text_hidden, grid_rule)) for child in node.children if isinstance(child, Tag))
    return outermost, hidden, grid_hidden


def _is_marker(tag: Tag) -> bool:
    if tag.name == "sup" or _MARKER_STYLE.search(str(tag.get("style", ""))):
        return True
    return (tag.name == "a" and str(tag.get("href", "")).startswith("#")
            and bool(_MARKER_TEXT.fullmatch(tag.get_text(strip=True))))


def _walk(node: Tag, hidden: set[int], out: list, marker: bool) -> None:
    for child in node.children:
        if isinstance(child, _SKIP_STRINGS):
            continue
        if isinstance(child, NavigableString):
            out.append((str(child), marker))
            continue
        if id(child) in hidden or child.name == "table":
            continue  # nested tables are counted through their own rows
        child_marker = marker or _is_marker(child)
        separate = child.name in _BLOCK or child_marker != marker
        if separate:
            out.append((" ", marker))
        _walk(child, hidden, out, child_marker)
        if separate:
            out.append((" ", marker))


def cell_text(cell: Tag, hidden: set[int]) -> tuple[str, str]:
    """(value text, footnote-marker text) of one cell, built from its visible DOM."""
    pieces: list = []
    _walk(cell, hidden, pieces, False)
    value = _SPACES.sub(" ", "".join(" " if m else t for t, m in pieces)).strip()
    marks = _SPACES.sub(" ", " ".join(t for t, m in pieces if m)).strip()
    return value, marks
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: 20 passed.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/table_completeness.py tests/test_table_completeness.py
git commit -m "feat: add table completeness cell text and token primitives"
```

---

### Task 3: Token classes, output positions and period rows

What this task adds:

- **Source token classes.** Each source token gets a class:
  - `reference`: identifier numbers anywhere in a cell (`Item`, `Note`, `Exhibit`, `Part`, `Schedule`), signature `Date:` and `/s/` cells, and dates in signature rows;
  - `value_numeric` or `value_text`: everything else.
- **Output positions.** Each output token gets a position:
  - `reference` for identifiers;
  - `numeric_cell` or `text_cell` in body lines;
  - `header_line` above the separator;
  - `text_rendering` when there is no separator.
- **Glued markers.** A trailing `(1)` glued to a value is split off as a text-cell marker, but only when a number remains: `$ (96)` stays a negative.
- **Row labels.** `label_key()` builds the label used to prove row pairings: the label's letters plus its identifier numbers (`note#1`).
- **Period rows.** `is_period_row()` decides from context, never from the shape of a number.

**Files:**
- Modify: `src/sec2md/table_completeness.py` (append)
- Test: `tests/test_table_completeness.py` (append)

**Interfaces:**
- Consumes: `numbers()` and the constants from Task 2.
- Produces:
  - `classify_cell(text: str, signature_row: bool = False) -> list[tuple[str, str]]`, a list of (token, kind) in left-to-right order
  - `label_key(text: str) -> str`
  - `is_period_row(cells: list[str], before_header_end: bool) -> bool`
  - `is_data_row(cells: list[str], before_header_end: bool) -> bool`
  - `output_positions(segment: str, exhibit_index: bool) -> tuple[list[tuple[str, Counter]], Counter]`, returning (body lines as (label key, Counter of (token, position)), Counter of header-line and text-rendering occurrences)

- [x] **Step 1: Write the failing tests**

Append to `tests/test_table_completeness.py`:

```python
# --- task 3: classes, positions and period rows ------------------------------------------

from sec2md.table_completeness import (  # noqa: E402
    classify_cell,
    is_data_row,
    is_period_row,
    label_key,
    output_positions,
)


@pytest.mark.parametrize("text, signature_row, expected", [
    ("9,943", False, [("9943", "value_numeric")]),
    ("Revenue 2026", False, [("2026", "value_text")]),
    ("Note 9 Impairment", False, [("9", "reference")]),
    ("Previously filed as Exhibit 2.1", False, [("2.1", "reference")]),
    ("Item 7 and 120", False, [("7", "reference"), ("120", "value_text")]),
    ("Date:", False, []),
    ("January 29, 2025", True, [("29", "reference"), ("2025", "reference")]),
    ("January 29, 2025", False, [("29", "value_text"), ("2025", "value_text")]),
])
def test_classify_cell(text, signature_row, expected):
    assert classify_cell(text, signature_row) == expected


@pytest.mark.parametrize("text, expected", [
    ("Total revenue", "totalrevenue"),
    ("Note 1", "note#1"),
    ("Note 2", "note#2"),
    ("Note 9 Impairment", "noteimpairment#9"),
    ("", ""),
])
def test_label_key_keeps_identifier_numbers(text, expected):
    assert label_key(text) == expected


@pytest.mark.parametrize("cells, before_header_end, expected", [
    (["", "2023", "2022"], False, True),
    (["Maturities (calendar year)", "2023", "2022"], False, True),
    (["", "Three Months Ended June 30, 2025", "Three Months Ended June 30, 2024"], False, True),
    (["Revenue", "2000", "1900"], False, False),
    (["Revenue", "2,000"], True, True),
])
def test_is_period_row_uses_context_not_number_shape(cells, before_header_end, expected):
    assert is_period_row(cells, before_header_end) is expected


def test_is_data_row_needs_a_standalone_amount():
    assert is_data_row(["Revenue", "2000", "1900"], False)
    assert not is_data_row(["Revenue", "grew strongly"], False)
    assert not is_data_row(["", "2023", "2022"], False)


def test_output_positions_tags_each_token_with_its_position():
    segment = ("| Item | 2026 |\n| --- | --- |\n| Revenue | 1,234 (1) |\n"
               "| Loss | $ (96) |\n| Note 9 Impairment | 9 |")
    body, other = output_positions(segment, exhibit_index=False)
    # "(1)" normalizes like an accounting negative on both sides, so markers match as "-1".
    assert body == [
        ("revenue", Counter({("1234", "numeric_cell"): 1, ("-1", "text_cell"): 1})),
        ("loss", Counter({("-96", "numeric_cell"): 1})),
        ("noteimpairment#9", Counter({("9", "reference"): 1, ("9", "numeric_cell"): 1})),
    ]
    assert other == Counter({("2026", "header_line"): 1})


def test_output_positions_without_separator_is_text_rendering():
    body, other = output_positions("ITEM 8. FINANCIAL STATEMENTS 2026", exhibit_index=False)
    assert body == []
    assert other == Counter({("8", "reference"): 1, ("2026", "text_rendering"): 1})


def test_output_positions_exhibit_index_body_is_all_references():
    segment = "| Exhibit | Description |\n| --- | --- |\n| 3.1 | Restated Certificate, filed 2020 |"
    body, _ = output_positions(segment, exhibit_index=True)
    assert body == [("", Counter({("3.1", "reference"): 1, ("2020", "reference"): 1}))]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: collection error, `ImportError: cannot import name 'classify_cell'`.

- [x] **Step 3: Implement**

Append to `src/sec2md/table_completeness.py`:

```python
# --- classes and positions -----------------------------------------------------------

def _value_kind(text: str) -> str:
    return "value_text" if _LETTER.search(text) else "value_numeric"


def classify_cell(text: str, signature_row: bool = False) -> list[tuple[str, str]]:
    """(token, kind) for one source cell, in left-to-right order."""
    if _SIGNATURE_CELL.search(text) or (signature_row and _DATE_CELL.match(text)):
        return [(t, "reference") for t in numbers(text)]
    kind = _value_kind(text)
    tokens, last = [], 0
    for m in _IDENTIFIER.finditer(text):
        tokens += [(t, kind) for t in numbers(text[last:m.start()])]
        tokens += [(t, "reference") for t in numbers(m.group(0))]
        last = m.end()
    return tokens + [(t, kind) for t in numbers(text[last:])]


def label_key(text: str) -> str:
    """Letters of a row label plus its identifier numbers ("Note 1" -> "note#1")."""
    identifiers = [t for m in _IDENTIFIER.finditer(text) for t in numbers(m.group(0))]
    letters = _NOT_LETTER.sub("", text.lower())
    return letters + ("#" + ",".join(identifiers) if identifiers else "")


def is_period_row(cells: list[str], before_header_end: bool) -> bool:
    """Header or period row, decided by context, never by the shape of its numbers."""
    if before_header_end:
        return True
    texts = [c for c in cells if c]
    if not texts or not all(_PERIOD_TEXT.search(c) or _BARE_YEAR.match(c) for c in texts):
        return False
    return any(_PERIOD_TEXT.search(c) for c in texts) or all(_BARE_YEAR.match(c) for c in texts)


def is_data_row(cells: list[str], before_header_end: bool) -> bool:
    return not is_period_row(cells, before_header_end) and any(_STANDALONE_AMOUNT.match(c) for c in cells)


def _output_cell_positions(cell: str, signature_row: bool) -> list[tuple[str, str]]:
    if _SIGNATURE_CELL.search(cell) or (signature_row and _DATE_CELL.match(cell.strip())):
        return [(t, "reference") for t in numbers(cell)]
    position = "text_cell" if _LETTER.search(cell) else "numeric_cell"
    occurrences = [(t, "reference") for m in _IDENTIFIER.finditer(cell) for t in numbers(m.group(0))]
    cell = _IDENTIFIER.sub(" ", cell)
    suffix = _MARKER_SUFFIX.search(cell)
    # A trailing "(1)" is a marker only when a number remains ("1,234 (1)"); "$ (96)" is a negative.
    if suffix and _DIGIT.search(cell, 0, suffix.start()):
        core, tail = cell[:suffix.start()], cell[suffix.start():]
    else:
        core, tail = cell, ""
    occurrences += [(t, position) for t in numbers(core)]
    occurrences += [(t, "text_cell") for t in numbers(tail.replace("(", " (").replace(")", ") "))]
    return occurrences


def output_positions(segment: str, exhibit_index: bool) -> tuple[list[tuple[str, Counter]], Counter]:
    """(body lines as (label key, positioned tokens), header-line and text-rendering tokens)."""
    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    body, other = [], Counter()
    for i, line in enumerate(lines):
        if separator is None:
            last = 0
            for m in _IDENTIFIER.finditer(line):
                other.update((t, "text_rendering") for t in numbers(line[last:m.start()]))
                other.update((t, "reference") for t in numbers(m.group(0)))
                last = m.end()
            other.update((t, "text_rendering") for t in numbers(line[last:]))
            continue
        if i == separator:
            continue
        cells = merge_split_negatives(line.split("|"))
        if i < separator:
            other.update((t, "header_line") for cell in cells for t in numbers(cell))
            continue
        signature_row = any(_SIGNATURE_ROW_MARK.search(c) for c in cells)
        found: Counter = Counter()
        for cell in cells:
            if exhibit_index:
                found.update((t, "reference") for t in numbers(cell))
            else:
                found.update(_output_cell_positions(cell, signature_row))
        body.append((label_key(cells[0]) if cells else "", found))
    return body, other
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: 42 passed.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/table_completeness.py tests/test_table_completeness.py
git commit -m "feat: classify table tokens and output positions"
```

---

### Task 4: Header rows without building snapshots

Header rows decide two things:

- the `header` role label of a value finding;
- whether a row whose amounts are all bare years counts as a data row.

The spec takes them from snapshot metadata, but building snapshots in normal mode costs 72% of parse time. `header_row_count()` instead places cells with the snapshot builder's rules. It keeps the occupied spans for each row and calls `xlsx_tables._header_count()` on the resulting grid. It returns 0 wherever the snapshot builder reports an issue:

- a non-integer or out-of-range span;
- a rowspan past the table end;
- overlapping cells;
- a nested table;
- an oversized grid.

`unit_rows()` collects every `tr` of a table and its nested tables in one traversal, recording which rows the outer table owns.

Header rows are computed for every table that contains digits (Task 5). To keep that cheap, a placed cell's text and numeric-fact flag are computed only when `_header_count()` reads them, which is only for the rows it examines.

**Files:**
- Modify: `src/sec2md/table_completeness.py` (append)
- Test: `tests/test_table_completeness.py` (append)

**Interfaces:**
- Consumes: `hidden_sets()` (Task 2), `xlsx_tables._header_count`, `xlsx_tables._visible_text`.
- Produces:
  - `unit_rows(table: Tag) -> list[_Row]`, where `_Row` has `.tr: Tag`, `.own: bool` and `.cells: list[Tag]`
  - `header_row_count(table: Tag, rows: list[_Row], grid_hidden: set[int]) -> int`

- [x] **Step 1: Write the failing tests**

Append to `tests/test_table_completeness.py`:

```python
# --- task 4: header rows without building snapshots --------------------------------------

from sec2md.table_completeness import header_row_count, unit_rows  # noqa: E402
from sec2md.xlsx_tables import _header_count, snapshot_html_table  # noqa: E402


def snapshot_header_rows(table):
    """Header rows as the XLSX snapshot grid counts them (the reference implementation)."""
    snap = snapshot_html_table(table, ordinal=1, page=1, source_url=None)
    if not snap.source_cells or snap.issues:
        return 0
    height = max(c.row + max(c.rowspan, 1) for c in snap.source_cells)
    width = max(c.column + max(c.colspan, 1) for c in snap.source_cells)
    grid = [[None] * width for _ in range(height)]
    for c in snap.source_cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                grid[r][k] = c
    return _header_count(grid)


HEADER_TABLES = [
    "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>",
    "<table><tr><td></td><td>2023</td><td>2022</td></tr><tr><td>Revenue</td><td>2,000</td><td>1,900</td></tr></table>",
    ('<table><tr><td></td><td colspan="2">Year ended December 31,</td></tr>'
     "<tr><td></td><td>2024</td><td>2023</td></tr><tr><td>Revenue</td><td>1,300</td><td>804</td></tr></table>"),
    ('<table><tr><td rowspan="2">Item</td><td>2026</td></tr><tr><td>120</td></tr>'
     "<tr><td>Cost</td><td>50</td></tr></table>"),
    '<table><tr><td colspan="bad">Unreliable</td><td>123</td></tr><tr><td>Tail</td><td>456</td></tr></table>',
    '<table><tr><td rowspan="5">Too tall</td><td>1</td></tr><tr><td>2</td></tr></table>',
    ('<table><tr><th>Item</th><th>2026</th></tr><tr style="display:none"><td>Hidden</td><td>1</td></tr>'
     "<tr><td>Revenue</td><td>120</td></tr></table>"),
]


@pytest.mark.parametrize("html", HEADER_TABLES)
def test_header_row_count_matches_snapshot_grid(html):
    soup = soup_of(html)
    table = soup.find("table")
    _, _, grid_hidden = hidden_sets(soup)
    assert header_row_count(table, unit_rows(table), grid_hidden) == snapshot_header_rows(table)


def test_header_row_count_is_zero_for_nested_tables():
    soup = soup_of("<table><tr><th>Item</th><th>2026</th></tr><tr><td>A<table><tr><td>1</td></tr></table></td>"
                   "<td>120</td></tr></table>")
    table = soup.find("table")
    _, _, grid_hidden = hidden_sets(soup)
    assert header_row_count(table, unit_rows(table), grid_hidden) == 0


def test_unit_rows_marks_rows_of_nested_tables():
    soup = soup_of("<table><tr><td>A<table><tr><td>1</td></tr></table></td><td>2</td></tr></table>")
    rows = unit_rows(soup.find("table"))
    assert [(row.own, len(row.cells)) for row in rows] == [(True, 2), (False, 1)]


def test_header_row_count_matches_snapshots_on_a_fixture():
    from tests.accuracy.fixtures import load_fixture
    from sec2md.encoding import decode_html
    from sec2md.parser import Parser

    soup = Parser(decode_html(load_fixture("nvda-2026-q2-10q")[1])[0]).soup
    outermost, hidden, grid_hidden = hidden_sets(soup)
    checked = 0
    for table in outermost:
        if id(table) in hidden or len(table.find_all("tr")) < 2:
            continue
        assert header_row_count(table, unit_rows(table), grid_hidden) == snapshot_header_rows(table)
        checked += 1
    assert checked > 50
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: collection error, `ImportError: cannot import name 'header_row_count'`.

- [x] **Step 3: Implement**

Append to `src/sec2md/table_completeness.py`:

```python
# --- header rows without building snapshots ----------------------------------------

class _GridCell:
    """A placed cell. _header_count reads only the rows it examines, so the text and
    numeric-fact flag are computed on first read rather than for every cell."""

    __slots__ = ("td", "grid_hidden", "row", "column", "rowspan", "colspan", "is_header", "_text", "_numeric")

    def __init__(self, td, grid_hidden, row, column, rowspan, colspan):
        self.td, self.grid_hidden = td, grid_hidden
        self.row, self.column, self.rowspan, self.colspan = row, column, rowspan, colspan
        self.is_header = td.name == "th"
        self._text = self._numeric = None

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = _visible_text(self.td)
        return self._text

    @property
    def is_numeric_fact(self) -> bool:
        if self._numeric is None:
            self._numeric = any(isinstance(d, Tag) and d.name in _NUMERIC_FACT_NAMES and id(d) not in self.grid_hidden
                                for d in self.td.descendants)
        return self._numeric


class _Row:
    """A tr of a table unit: whether the unit owns it, and the cells whose nearest tr it is."""

    __slots__ = ("tr", "own", "cells")

    def __init__(self, tr: Tag, own: bool):
        self.tr, self.own, self.cells = tr, own, []


def unit_rows(table: Tag) -> list[_Row]:
    """Every tr inside a table unit, in document order, from one traversal.

    Avoids per-row and per-cell BeautifulSoup searches, which dominate the cost otherwise.
    """
    rows: list[_Row] = []
    stack = [(child, table, None) for child in reversed(list(table.children)) if isinstance(child, Tag)]
    while stack:
        node, owner, row = stack.pop()
        if node.name == "table":
            owner, row = node, None
        elif node.name == "tr":
            row = _Row(node, owner is table)
            rows.append(row)
        elif node.name in ("td", "th") and row is not None:
            row.cells.append(node)
        stack.extend((child, owner, row) for child in reversed(list(node.children)) if isinstance(child, Tag))
    return rows


_NUMERIC_FACT_NAMES = {"ix:nonfraction", "ix:fraction", "nonfraction", "fraction"}


def header_row_count(table: Tag, rows: list[_Row], grid_hidden: set[int]) -> int:
    """xlsx_tables._header_count over the grid a snapshot would build; 0 where a snapshot is unreliable."""
    if table.find("table") is not None:
        return 0
    rows = [row for row in rows if row.own and id(row.tr) not in grid_hidden]
    # The snapshot builder's placement rules, with occupied spans kept per row so each
    # lookup only scans its own row (the builder compares every cell with every other).
    taken: list[list[tuple[int, int]]] = [[] for _ in rows]
    cells, row_widths = [], [0] * len(rows)
    for r, row in enumerate(rows):
        column = 0
        for td in row.cells:
            if id(td) in grid_hidden:
                continue
            while True:
                covering = [end for start, end in taken[r] if start <= column < end]
                if not covering:
                    break
                column = max(covering)
            spans = []
            for attr, limit in (("rowspan", 65534), ("colspan", 1000)):
                try:
                    value = int(td.get(attr, "1"))
                except (TypeError, ValueError):
                    return 0
                if value <= 0 or value > limit:
                    return 0
                spans.append(value)
            rowspan, colspan = spans
            bottom, end = r + rowspan, column + colspan
            if bottom > len(rows) or any(start < end and finish > column
                                         for rr in range(r, bottom) for start, finish in taken[rr]):
                return 0
            cells.append(_GridCell(td, grid_hidden, r, column, rowspan, colspan))
            for rr in range(r, bottom):
                taken[rr].append((column, end))
            row_widths[r] += colspan
            column = end
    if not cells:
        return 0
    flat_width = max(row_widths)
    height = max(c.row + c.rowspan for c in cells)
    width = max(c.column + c.colspan for c in cells)
    if width > flat_width or height * width > 1_000_000:
        return 0
    grid = [[None] * width for _ in range(height)]
    for c in cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                grid[r][k] = c
    return _header_count(grid)
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: 52 passed. The fixture test checks more than 50 tables of the NVDA 10-Q against real snapshots.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/table_completeness.py tests/test_table_completeness.py
git commit -m "feat: count table header rows without building snapshots"
```

---

### Task 5: Matching, row structure and the report

What this task adds:

- **Check 1 matching** (`match_occurrences()`):
  - Pass 1 matches each source row only within its output line, when the row's label key is unique among the source rows and among the output body lines.
  - Pass 2 is table-wide.
  - Within each pass, claims go in the order reference, marker, standalone marker, numeric value, text value, each to the first compatible output position.
  - A value that is short in pass 2, while a reference or marker claimed the same token at a position the value could use, is `ambiguous`.
- **Check 2** (`row_structure()`) looks only at output body lines, and only at data rows with at least two tokens. It reports:
  - values out of order within a row;
  - a row that appears before an earlier source row;
  - values present but split across output rows.
- **`check_tables()`** ties the checks together for every visible outermost table:
  - Tables without digits are skipped.
  - Every other table gets its header rows from `header_row_count()`.
  - Header rows are never data rows for check 2, and their value findings carry the `header` role.

**Files:**
- Modify: `src/sec2md/table_completeness.py` (append)
- Test: `tests/test_table_completeness.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 2–4.
- Produces:
  - **`match_occurrences(rows, body, other)`.** Its arguments:
    - `rows`: (label key, Counter of (token, kind, role)) for each source row.
    - `body` and `other`: as returned by `output_positions()`.

    It returns `(missing_values: list[tuple[str, str, bool]], missing_reported: list[tuple[str, str]])`, meaning (token, role, ambiguous) and (token, class). The class is `reference`, `marker` or `standalone_marker`.
  - **`row_structure(source_rows: list[tuple[str, ...]], segment: str) -> list[str]`.**
  - **`TableFinding`**, a frozen dataclass:
    - fields: `ordinal: int`, `snapshot_ordinal: int | None`, `page: int | None`, `missing_values`, `missing_reported`, `structure: tuple[str, ...]` and `produced_output: bool = True`;
    - methods: `value_message()`, `reported_message()`, `structure_messages()` and `messages()`.
  - **`TableCompletenessReport`**, a frozen dataclass with `tables_checked: int` and `findings: tuple[TableFinding, ...]`, and the properties `failures`, `reported` and `structure`, each a `tuple[str, ...]`.
  - **`check_tables(soup, table_outputs: Mapping[int, str], table_pages: Mapping[int, int], snapshot_ordinals: Mapping[int, int]) -> TableCompletenessReport`.** Its mappings are keyed by `id(table)`.
  - **Message format:** `table 1 (snapshot 1, page 1): missing 9943 x1 [body] (total 1)`, with `, ambiguous` inside the brackets when applicable. A table with no output produces `table 1 produced no output (5 numbers)`.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_table_completeness.py`:

```python
# --- task 5: matching, row structure and the report --------------------------------------

from sec2md.table_completeness import (  # noqa: E402
    TableCompletenessReport,
    TableFinding,
    check_tables,
    match_occurrences,
    row_structure,
)


def occurrences(*items):
    return Counter({item: 1 for item in items})


def test_match_occurrences_claims_within_proven_row_pairs():
    rows = [("impairment", occurrences(("9", "value_numeric", "body"))),
            ("footnote", occurrences(("9", "standalone_marker", "body")))]
    body = [("impairment", Counter()), ("footnote", Counter({("9", "numeric_cell"): 1}))]
    values, reported = match_occurrences(rows, body, Counter())
    assert values == [("9", "body", False)]
    assert reported == []


def test_match_occurrences_marks_shared_provenance_ambiguous():
    rows = [("total", occurrences(("9", "value_numeric", "body"))),
            ("total", occurrences(("9", "standalone_marker", "body")))]
    body = [("total", Counter({("9", "numeric_cell"): 1}))]
    values, reported = match_occurrences(rows, body, Counter())
    assert values == [("9", "body", True)]
    assert reported == []


def test_match_occurrences_reports_lost_references_without_failing():
    rows = [("noteimpairment#9", occurrences(("9", "reference", "label"), ("9", "value_numeric", "body")))]
    body = [("impairment", Counter({("9", "numeric_cell"): 1}))]
    assert match_occurrences(rows, body, Counter()) == ([], [("9", "reference")])


SEGMENT = "| Item | 2026 | 2025 |\n| --- | --- | --- |\n| Revenue | 120 | 100 |\n| Cost | 50 | 40 |"


@pytest.mark.parametrize("segment, expected", [
    (SEGMENT, []),
    (SEGMENT.replace("| 120 | 100 |", "| 100 | 120 |"), ["source row 1: values out of order within the row"]),
    ("| Item | 2026 | 2025 |\n| --- | --- | --- |\n| Cost | 50 | 40 |\n| Revenue | 120 | 100 |",
     ["source row 2: appears before an earlier source row"]),
    (SEGMENT.replace("| 100 |", "| 40 |", 1).replace("| 50 | 40 |", "| 50 | 100 |"),
     ["source row 1: values present but split across output rows",
      "source row 2: values present but split across output rows"]),
    ("Revenue 120 100 Cost 50 40", []),
])
def test_row_structure(segment, expected):
    assert row_structure([("120", "100"), ("50", "40")], segment) == expected


def test_finding_messages():
    finding = TableFinding(2, 1, 3, missing_values=(("9943", "body", False), ("9", "label", True)),
                           missing_reported=(("1", "reference"),),
                           structure=("source row 1: values out of order within the row",))
    assert finding.value_message() == "table 2 (snapshot 1, page 3): missing 9943 x1 [body], 9 x1 [label, ambiguous] (total 2)"
    assert finding.reported_message() == "table 2 (snapshot 1, page 3): missing 1 x1 [reference] (total 1)"
    assert finding.structure_messages() == ("table 2 (snapshot 1, page 3): source row 1: values out of order within the row",)
    assert finding.messages() == ((finding.value_message(), finding.reported_message()) + finding.structure_messages())
    empty = TableFinding(1, None, None, missing_values=(("12", "body", False),) * 3, produced_output=False)
    assert empty.value_message() == "table 1 produced no output (3 numbers)"
    report = TableCompletenessReport(4, (finding, empty))
    assert report.failures == (finding.value_message(), empty.value_message())
    assert report.reported == (finding.reported_message(),)
    assert report.structure == finding.structure_messages()


MERGE_LOSS = ("<table><tr><td>2024</td><td>$</td><td>9,943</td></tr>"
              "<tr><td>2025</td><td></td><td>10,775</td></tr><tr><td>Total</td><td>$</td><td>20,718</td></tr></table>")


def test_check_tables_compares_each_table_with_its_own_output():
    soup = soup_of("<p>Commitments include $9,943 million due in 2024.</p>" + MERGE_LOSS)
    table = soup.find("table")
    output = "| 2024 | $ |\n| --- | --- |\n| 2025 | 10,775 |\n| Total | $ 20,718 |"
    report = check_tables(soup, {id(table): output}, {id(table): 1}, {id(table): 1})
    assert report.tables_checked == 1
    assert report.failures == ("table 1 (snapshot 1, page 1): missing 9943 x1 [body] (total 1)",)


def test_check_tables_excludes_header_rows_from_row_structure():
    soup = soup_of("<table><tr><th>Denomination</th><th>€1</th><th>€2</th></tr>"
                   "<tr><td>Issued</td><td>2</td><td>1</td></tr></table>")
    table = soup.find("table")
    output = "| Denomination | €1 | €2 |\n| --- | --- | --- |\n| Issued | 2 | 1 |"
    report = check_tables(soup, {id(table): output}, {}, {})
    assert report == TableCompletenessReport(1, ())


def test_check_tables_reports_tables_without_output():
    soup = soup_of(MERGE_LOSS)
    report = check_tables(soup, {}, {}, {})
    assert report.failures == ("table 1 produced no output (5 numbers)",)


def test_check_tables_skips_hidden_and_token_free_tables():
    soup = soup_of('<div style="display:none">' + MERGE_LOSS + "</div>"
                   "<table><tr><td>Name</td><td>Title</td></tr><tr><td>Jane</td><td>CFO</td></tr></table>")
    report = check_tables(soup, {}, {}, {})
    assert report == TableCompletenessReport(0, ())
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: collection error, `ImportError: cannot import name 'TableCompletenessReport'`.

- [x] **Step 3: Implement**

Append to `src/sec2md/table_completeness.py`:

```python
# --- matching ------------------------------------------------------------------------

def _claim(occurrences: Counter, pool: Counter, shared: dict | None) -> Counter:
    left: Counter = Counter()
    for kind in _CLAIM_ORDER:
        for (token, k, role), count in sorted(occurrences.items()):
            if k != kind:
                continue
            for _ in range(count):
                position = next((p for p in _COMPATIBLE[kind] if pool[(token, p)] > 0), None)
                if position is None:
                    left[(token, k, role)] += 1
                    continue
                pool[(token, position)] -= 1
                if shared is not None and not kind.startswith("value"):
                    shared.setdefault(token, set()).add(position)
    return left


def match_occurrences(rows: list[tuple[str, Counter]], body: list[tuple[str, Counter]], other: Counter):
    """Check 1 matching: proven row pairs first, then a table-wide pass.

    Returns (missing values as (token, role, ambiguous), missing reported as (token, class)),
    where class is "reference", "marker" or "standalone_marker".
    """
    pools = [Counter(found) for _, found in body]
    source_counts = Counter(key for key, _ in rows if key)
    output_counts = Counter(key for key, _ in body if key)
    line_of = {key: i for i, (key, _) in enumerate(body) if key and output_counts[key] == 1}
    unclaimed: Counter = Counter()
    for key, occurrences in rows:
        line = line_of.get(key) if key and source_counts[key] == 1 else None
        unclaimed.update(occurrences if line is None else _claim(occurrences, pools[line], None))
    remaining = Counter(other)
    for pool in pools:
        remaining.update(+pool)
    shared: dict[str, set] = {}
    final = _claim(unclaimed, remaining, shared)
    missing_values, missing_reported = [], []
    for (token, kind, role), count in sorted(final.items()):
        for _ in range(count):
            if kind.startswith("value"):
                missing_values.append((token, role, bool(shared.get(token, set()) & set(_COMPATIBLE[kind]))))
            else:
                missing_reported.append((token, kind))
    return missing_values, missing_reported


def row_structure(source_rows: list[tuple[str, ...]], segment: str) -> list[str]:
    """Check 2 over body lines: within-row order, rows out of order, values split across rows."""
    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    if separator is None:
        return []
    body = [output_line_numbers(line) for line in lines[separator + 1:]]
    body_all = Counter(t for line in body for t in line)
    findings, pointer = [], 0
    for number, row in enumerate(source_rows, 1):
        need = Counter(row)
        hit = next((k for k in range(pointer, len(body)) if not need - Counter(body[k])), None)
        if hit is not None:
            left, projected = Counter(need), []
            for token in body[hit]:
                if left[token]:
                    projected.append(token)
                    left[token] -= 1
            if tuple(projected) != row:
                findings.append(f"source row {number}: values out of order within the row")
            pointer = hit
        elif any(not need - Counter(body[k]) for k in range(pointer)):
            findings.append(f"source row {number}: appears before an earlier source row")
        elif not need - body_all:
            findings.append(f"source row {number}: values present but split across output rows")
    return findings


# --- report ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TableFinding:
    """Check 1 and check 2 results for one table unit."""

    ordinal: int
    snapshot_ordinal: int | None
    page: int | None
    missing_values: tuple[tuple[str, str, bool], ...] = ()
    missing_reported: tuple[tuple[str, str], ...] = ()
    structure: tuple[str, ...] = ()
    produced_output: bool = True

    def _where(self) -> str:
        parts = [f"snapshot {self.snapshot_ordinal}" if self.snapshot_ordinal else "", f"page {self.page}" if self.page else ""]
        detail = ", ".join(p for p in parts if p)
        return f"table {self.ordinal}" + (f" ({detail})" if detail else "")

    def value_message(self) -> str | None:
        if not self.missing_values:
            return None
        if not self.produced_output:
            return f"{self._where()} produced no output ({len(self.missing_values)} numbers)"
        counts = Counter(self.missing_values)
        listed = ", ".join(f"{token} x{n} [{role}{', ambiguous' if ambiguous else ''}]"
                           for (token, role, ambiguous), n in list(counts.items())[:10])
        return f"{self._where()}: missing {listed} (total {len(self.missing_values)})"

    def reported_message(self) -> str | None:
        if not self.missing_reported:
            return None
        counts = Counter(self.missing_reported)
        listed = ", ".join(f"{token} x{n} [{cls}]" for (token, cls), n in list(counts.items())[:10])
        return f"{self._where()}: missing {listed} (total {len(self.missing_reported)})"

    def structure_messages(self) -> tuple[str, ...]:
        return tuple(f"{self._where()}: {s}" for s in self.structure)

    def messages(self) -> tuple[str, ...]:
        """Every message for this table: value failures, reported tokens, then row structure."""
        return tuple(m for m in (self.value_message(), self.reported_message()) if m) + self.structure_messages()


@dataclass(frozen=True)
class TableCompletenessReport:
    tables_checked: int
    findings: tuple[TableFinding, ...]

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(m for f in self.findings if (m := f.value_message()))

    @property
    def reported(self) -> tuple[str, ...]:
        return tuple(m for f in self.findings if (m := f.reported_message()))

    @property
    def structure(self) -> tuple[str, ...]:
        return tuple(m for f in self.findings for m in f.structure_messages())


def _direct_cells(tr: Tag) -> list[Tag]:
    return [c for c in tr.children if isinstance(c, Tag) and c.name in ("td", "th")]


def check_tables(soup, table_outputs: Mapping[int, str], table_pages: Mapping[int, int],
                 snapshot_ordinals: Mapping[int, int]) -> TableCompletenessReport:
    """Run checks 1 and 2 over every visible outermost table of a parsed document."""
    numbers.cache_clear()  # the token cache is per document
    outermost, hidden, grid_hidden = hidden_sets(soup)
    units = [t for t in outermost if id(t) not in hidden]
    findings, checked = [], 0
    for ordinal, table in enumerate(units, 1):
        all_rows = unit_rows(table)
        rows = [row for row in all_rows if id(row.tr) not in hidden]
        own_rows = [row for row in rows if row.own]
        own_index = {id(row.tr): i for i, row in enumerate(own_rows)}
        texts_by_row = [[cell_text(c, hidden) for c in _direct_cells(row.tr) if id(c) not in hidden] for row in rows]
        if not any(_DIGIT.search(value) or _DIGIT.search(marks) for texts in texts_by_row for value, marks in texts):
            continue  # no source tokens
        leading = [value for row, texts in zip(rows, texts_by_row) if row.own and own_index[id(row.tr)] < 3
                   for value, _ in texts]
        exhibit_index = (any(_EXHIBIT_HEADING.match(v) for v in leading)
                         and any(_DESCRIPTION_HEADING.search(v) for v in leading))
        raw = table_outputs.get(id(table), "")
        segment = _MARKDOWN_LINK_RE.sub(lambda m: m.group(1), raw)
        body, other = output_positions(segment, exhibit_index)

        # Header rows are never data rows (check 2) and label value findings "header".
        header_rows = header_row_count(table, all_rows, grid_hidden)
        row_occurrences, source_rows, total = [], [], 0
        for row, texts in zip(rows, texts_by_row):
            row_index = own_index[id(row.tr)] if row.own else -1
            row_role = "header" if row.own and row_index < header_rows else (None if row.own else "nested")
            values = merge_split_negatives([v for v, _ in texts])
            signature_row = any(_SIGNATURE_ROW_MARK.search(v) for v in values)
            occurrences: Counter = Counter()
            row_tokens = []
            for position, text in enumerate(values):
                role = row_role or ("label" if position == 0 else "body")
                for token, kind in classify_cell(text, signature_row):
                    occurrences[(token, "reference" if exhibit_index else kind, role)] += 1
                    row_tokens.append(token)
            for value, marks in texts:
                marker_kind = "marker" if _ALPHANUMERIC.search(value) else "standalone_marker"
                for token in numbers(marks.replace("(", " (").replace(")", ") ")):
                    occurrences[(token, marker_kind, row_role or "body")] += 1
            if row.own and len(row_tokens) >= 2 and is_data_row(values, row_index < header_rows):
                source_rows.append(tuple(row_tokens))
            total += sum(occurrences.values())
            row_occurrences.append((label_key(next((v for v, _ in texts if v), "")) if row.own else "", occurrences))
        if not total:
            continue
        missing_values, missing_reported = match_occurrences(row_occurrences, body, other)
        structure = row_structure(source_rows, segment)
        checked += 1
        if missing_values or missing_reported or structure:
            findings.append(TableFinding(ordinal, snapshot_ordinals.get(id(table)), table_pages.get(id(table)),
                                         tuple(missing_values), tuple(missing_reported), tuple(structure),
                                         produced_output=bool(raw.strip())))
    return TableCompletenessReport(checked, tuple(findings))
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_table_completeness.py -q`
Expected: 65 passed.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/table_completeness.py tests/test_table_completeness.py
git commit -m "feat: match table tokens, check row structure and report findings"
```

---

### Task 6: Parser integration

`Parser` changes so it can run the checks:

- **Recording outputs.** It records the exact output of every outermost table: `_process_element()` returns that output unchanged, through the extracted `_render_table()`.
- **Recording metadata.** It records each table's first page and snapshot ordinal at the `_stream_pages()` table site.
- **One ordinal counter.** Snapshot ordinals come from a single counter, `_snapshot_ordinal`, used in every mode. It advances for each table with more than one effective row and for each positioned table group, exactly where capture mode appends a snapshot. That keeps findings naming the same snapshot in both modes. In capture mode the snapshots get the same ordinals as before.
- **No extra traversal.** With neither capture nor the checks on, the table site does no metadata work, exactly as `main`. When either is on, the effective rows it computes are kept in `_root_table_rows`, and `_render_table()` reuses them, so every table is traversed once.
- **Running the checks.** `get_pages()` resets this state on each call and runs `check_tables()` after page assembly, with or without elements.

**Files:**
- Modify: `src/sec2md/parser.py`
- Create: `tests/test_table_completeness_parser.py`

**Interfaces:**
- Consumes: `check_tables()`, `TableCompletenessReport` (Task 5).
- Produces:
  - **`Parser(...)`** takes a new keyword argument, `table_checks: bool = True`.
  - **`Parser.table_report: TableCompletenessReport | None`.** It is `None` until `get_pages()` runs, and when the checks are off.
  - **`Parser.table_outputs: dict[int, str]`**, the rendered text of each outermost table.
  - **`Parser._table_pages` and `Parser._snapshot_ordinals`**, both `dict[int, int]`.
  - **`Parser._root_table_rows: dict[int, list[list[Tag]]]`**: effective rows computed at the table site, used once by `_render_table()`.
  - **`Parser._render_table(element: Tag) -> str`.**

- [x] **Step 1: Write the failing tests**

Create `tests/test_table_completeness_parser.py`:

```python
"""Table completeness through the parser: every review case, in both rendering modes."""

import re

import pytest

from sec2md.parser import Parser
from sec2md.table_completeness import check_tables

BOTH_MODES = pytest.mark.parametrize("capture", [False, True], ids=["normal", "capture"])


def findings(html, capture=False, mutate=None):
    """{ordinal: (missing values, missing reported, structure)} for one document.

    mutate rewrites each recorded table output before checking, which simulates a
    renderer that lost or moved something without touching the real rendering.
    """
    parser = Parser(html, capture_tables=capture)
    parser.get_pages(include_images=False)
    report = parser.table_report
    if mutate is not None:
        outputs = {key: mutate(value) for key, value in parser.table_outputs.items()}
        report = check_tables(parser.soup, outputs, parser._table_pages, parser._snapshot_ordinals)
    return {f.ordinal: (f.missing_values, f.missing_reported, f.structure) for f in report.findings}


def lost(*tokens, role="body", ambiguous=False):
    return tuple((token, role, ambiguous) for token in tokens)


def drop_line(prefix):
    """Delete the first output line starting with prefix (a whole rendered row)."""
    def mutate(segment):
        lines = segment.split("\n")
        index = next((i for i, line in enumerate(lines) if line.startswith(prefix)), None)
        if index is not None:
            del lines[index]
        return "\n".join(lines)
    return mutate


def swap_body_rows(segment):
    lines = segment.split("\n")
    lines[2], lines[3] = lines[3], lines[2]
    return "\n".join(lines)


def move_values_between_rows(segment):
    return segment.replace("| 100 |", "| @ |").replace("| 40 |", "| 100 |").replace("| @ |", "| 40 |")


def reverse_numeric_cells(segment):
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        for i, value in zip(idx, [cells[i] for i in idx][::-1]):
            cells[i] = value
        out.append("|".join(cells))
    return "\n".join(out)


MERGE_LOSS = ("<table><tr><td>2024</td><td>$</td><td>9,943</td></tr>"
              "<tr><td>2025</td><td></td><td>10,775</td></tr><tr><td>Total</td><td>$</td><td>20,718</td></tr></table>")
TWO_BY_TWO = ("<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
              "<tr><td>Revenue</td><td>120</td><td>100</td></tr><tr><td>Cost</td><td>50</td><td>40</td></tr></table>")
SPLIT_NEGATIVE = ('<table><tr><th>Item</th><th colspan="2">2026</th></tr>'
                  "<tr><td>Revenue</td><td>120</td><td></td></tr><tr><td>Loss</td><td>(29</td><td>)</td></tr></table>")
NOTE9 = ("<table><tr><th>Item</th><th>2026</th></tr>"
         "<tr><td>Note 9 Impairment</td><td>$</td><td>9</td></tr><tr><td>Other</td><td></td><td>12</td></tr></table>")
SUP9 = ("<table><tr><th>Item</th><th>2026</th></tr>"
        "<tr><td>Impairment<sup>9</sup></td><td>$</td><td>9</td></tr><tr><td>Other</td><td></td><td>12</td></tr></table>")
YEARS = ("<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
         "<tr><td>Revenue</td><td>2000</td><td>1900</td></tr><tr><td>Cost</td><td>500</td><td>400</td></tr></table>")
STANDALONE_MARKER = ("<table><tr><th>Item</th><th>Amount</th></tr>"
                     "<tr><td>Impairment</td><td>9</td></tr><tr><td>Footnote</td><td><sup>9</sup></td></tr></table>")
UNLABELLED_MARKER = ("<table><tr><th>Item</th><th>Amount</th></tr>"
                     "<tr><td></td><td>9</td></tr><tr><td></td><td><sup>9</sup></td></tr></table>")
NOTES = ("<table><tr><th>Item</th><th>Amount</th></tr>"
         "<tr><td>Note 1</td><td>9</td></tr><tr><td>Note 2</td><td><sup>9</sup></td></tr></table>")
TOTALS = ("<table><tr><th>Item</th><th>Amount</th></tr>"
          "<tr><td>Total</td><td>9</td></tr><tr><td>Total</td><td><sup>9</sup></td></tr></table>")
CURRENCIES = ("<table><tr><td>Item</td><td>2026</td></tr><tr><td>Revenue</td><td>€123</td></tr>"
              "<tr><td>Cost</td><td>£456</td></tr></table>")
HIDDEN = ("<table><tr><td>Item</td><td>2026</td></tr>"
          '<tr><td>Revenue</td><td>100<span style="display:none">999</span></td></tr></table>')
EXHIBITS = ("<table><tr><th>Exhibit</th><th>Description</th></tr>"
            "<tr><td>3.1</td><td>Restated Certificate of Incorporation</td></tr>"
            "<tr><td>10.2</td><td>Credit Agreement</td></tr></table>")
SIGNATURE = ("<table><tr><td>Date:</td><td>January 29, 2025</td><td>/s/ Jane Doe</td></tr>"
             "<tr><td></td><td></td><td>Jane Doe, Chief Financial Officer</td></tr></table>")
STACKED = ("<table><tr><td></td><td>Three Months Ended June 30, 2025</td><td>Three Months Ended June 30, 2024</td></tr>"
           "<tr><td>Balance at beginning</td><td>2,523</td><td>2,537</td></tr>"
           "<tr><td>Net income</td><td>18,337</td><td>13,465</td></tr>"
           "<tr><td></td><td>Six Months Ended June 30, 2025</td><td>Six Months Ended June 30, 2024</td></tr>"
           "<tr><td>Balance at beginning</td><td>2,534</td><td>2,561</td></tr>"
           "<tr><td>Net income</td><td>34,981</td><td>25,834</td></tr></table>")
FUSED_HEADER = ('<table><tr><td></td><td colspan="2">Year ended December 31,</td><td colspan="2">2024 vs. 2023</td></tr>'
                "<tr><td></td><td>2024</td><td>2023</td><td>$ Change</td><td>% Change</td></tr>"
                "<tr><td>Revenue</td><td>1,300</td><td>804</td><td>496</td><td>62%</td></tr>"
                "<tr><td>Cost</td><td>300</td><td>200</td><td>100</td><td>50%</td></tr></table>")
NESTED = ("<table><tr><td>Outer<table><tr><td>Inner</td><td>77</td></tr><tr><td>B</td><td>88</td></tr></table></td>"
          "<td>12</td></tr><tr><td>Outer B</td><td>34</td></tr></table>")

# (name, html, mutate, expected findings) with the same result in both rendering modes.
CASES = [
    ("prose repeats the lost value", "<p>Commitments include $9,943 million due in 2024.</p>" + MERGE_LOSS, None,
     {1: (lost("9943"), (), ())}),
    ("inline-split number",
     "<table><tr><td>Item</td><td>2026</td></tr><tr><td>Revenue</td><td>1,2<span>34</span></td></tr></table>", None,
     {1: (lost("1234"), (), ())}),
    ("hidden descendant is not source", HIDDEN, None, {}),
    ("hidden value leaked into the output keeps the visible value", HIDDEN, lambda s: s.replace("100", "100 999"), {}),
    ("euro and pound values", CURRENCIES, None, {}),
    ("lost euro value", CURRENCIES, lambda s: s.replace("€123", "€"), {1: (lost("123"), (), ())}),
    ("lost single-digit $9",
     "<table><tr><td>Impairment</td><td>$</td><td>9</td></tr><tr><td>Other</td><td></td><td>12</td></tr>"
     "<tr><td>Total</td><td>$</td><td>21</td></tr></table>", None,
     {1: (lost("9"), (), ())}),
    ("sup footnote marker rendered as (1)",
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue<sup>(1)</sup></td><td>120</td></tr></table>", None, {}),
    ("percentage range",
     "<table><tr><th>Item</th><th>Rate</th></tr><tr><td>Discount rate</td><td>3.5%-4.3%</td></tr>"
     "<tr><td>Growth</td><td>2%</td></tr></table>", None, {}),
    ("NVDA link-split digits",
     '<table><tr><td><a href="#a">Statements of Income for the years ended January 2</a><a href="#a">5</a>'
     '<a href="#a">, 2025</a></td><td><a href="#p">84</a></td></tr>'
     '<tr><td><a href="#b">Balance Sheets</a></td><td><a href="#q">8</a><a href="#q">5</a></td></tr></table>', None, {}),
    ("one-row table before a multi-row table",
     "<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table>"
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>", None, {}),
    ("header-only table without numbers",
     "<table><tr><th>Name</th><th>Position</th></tr><tr><th>Directors</th><th></th></tr></table>", None, {}),
    ("numeric cells reversed", TWO_BY_TWO, reverse_numeric_cells,
     {1: ((), (), ("source row 1: values out of order within the row",
                   "source row 2: values out of order within the row"))}),
    ("'Note 1 Revenue' row loses its amount",
     "<table><tr><td>Note 1 Revenue</td><td>$</td><td>9,943</td></tr><tr><td>Other</td><td></td><td>12</td></tr>"
     "<tr><td>Total</td><td>$</td><td>9,955</td></tr></table>", None,
     {1: (lost("9943"), (), ())}),
    ("split negative preserved", SPLIT_NEGATIVE, None, {}),
    ("split negative deleted", SPLIT_NEGATIVE, lambda s: s.replace("(29", ""), {1: (lost("-29"), (), ())}),
    ("body rows swapped", TWO_BY_TWO, swap_body_rows,
     {1: ((), (), ("source row 2: appears before an earlier source row",))}),
    ("values moved between rows", TWO_BY_TWO, move_values_between_rows,
     {1: ((), (), ("source row 1: values present but split across output rows",
                   "source row 2: values present but split across output rows"))}),
    ("signature date lost (reported only)", SIGNATURE, lambda s: s.replace("January 29, 2025", ""),
     {1: ((), (("2025", "reference"), ("29", "reference")), ())}),
    ("lost exhibit-index identifier (reported only)", EXHIBITS, lambda s: s.replace("| 3.1 |", "|  |"),
     {1: ((), (("3.1", "reference"),), ())}),
    ("stacked statement with repeated section headers", STACKED, None, {}),
    ("'Note 9' kept, amount 9 deleted", NOTE9, lambda s: s.replace("| $ 9 |", "| $ |"), {1: (lost("9"), (), ())}),
    ("<sup>9</sup> kept, amount 9 deleted", SUP9, lambda s: s.replace("| $ 9 |", "| $ |"), {1: (lost("9"), (), ())}),
    ("amount kept, 'Note 9' identifier lost", NOTE9, lambda s: s.replace("Note 9 Impairment", "Impairment"),
     {1: ((), (("9", "reference"),), ())}),
    ("amount kept, <sup>9</sup> marker lost", SUP9, lambda s: s.replace("Impairment 9", "Impairment"),
     {1: ((), (("9", "marker"),), ())}),
    ("marker glued to the amount in the output",
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>1,234<sup>(1)</sup></td></tr>"
     "<tr><td>Cost</td><td>500</td></tr></table>", None, {}),
    ("accounting negative beside a currency cell",
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Loss</td><td>$</td><td>(96</td><td>)</td></tr>"
     "<tr><td>Cost</td><td></td><td>500</td><td></td></tr></table>", None, {}),
    ("'Revenue | 2000 | 1900' swapped", YEARS, lambda s: s.replace("| 2000 | 1900 |", "| 1900 | 2000 |"),
     {1: ((), (), ("source row 1: values out of order within the row",))}),
    ("year-only header row stays out of check 2",
     "<table><tr><td></td><td>2023</td><td>2022</td></tr><tr><td>Revenue</td><td>2,000</td><td>1,900</td></tr>"
     "<tr><td>Cost</td><td>500</td><td>400</td></tr></table>", None, {}),
    ("standalone <sup>9</sup> cell, output unchanged", STANDALONE_MARKER, None, {}),
    ("standalone <sup>9</sup> cell kept, amount deleted", STANDALONE_MARKER,
     lambda s: s.replace("| Impairment | 9 |", "| Impairment |  |"), {1: (lost("9"), (), ())}),
    ("amount kept, standalone <sup>9</sup> deleted", STANDALONE_MARKER,
     lambda s: s.replace("| Footnote | 9 |", "| Footnote |  |"), {1: ((), (("9", "standalone_marker"),), ())}),
    ("unlabelled rows, amount deleted", UNLABELLED_MARKER, lambda s: s.replace("| 9 |\n| 9 |", "|  |\n| 9 |", 1),
     {1: (lost("9", role="label", ambiguous=True), (), ())}),
    ("'Note 1' / 'Note 2' rows, output unchanged", NOTES, None, {}),
    ("'Note 1' row deleted", NOTES, drop_line("| Note 1 |"), {1: (lost("9"), (("1", "reference"),), ())}),
    ("'Note 2' footnote row deleted", NOTES, drop_line("| Note 2 |"),
     {1: ((), (("2", "reference"), ("9", "standalone_marker")), ())}),
    ("repeated 'Total' rows, output unchanged", TOTALS, None, {}),
    ("first 'Total' row deleted", TOTALS, drop_line("| Total |"), {1: (lost("9", ambiguous=True), (), ())}),
    ("fused multi-row header", FUSED_HEADER, None, {}),
    # Header rows are excluded from check 2 even when nothing is missing: the <th> row's
    # euro amounts are not a data row (plan review round 1, finding 1).
    ("<th> header row with euro amounts, output unchanged",
     "<table><tr><th>Denomination</th><th>€1</th><th>€2</th></tr><tr><td>Issued</td><td>2</td><td>1</td></tr></table>",
     None, {}),
]


@BOTH_MODES
@pytest.mark.parametrize("name, html, mutate, expected", CASES, ids=[case[0] for case in CASES])
def test_review_case(name, html, mutate, expected, capture):
    assert findings(html, capture, mutate) == expected


def test_nested_table_follows_each_rendering_mode():
    # Normal Markdown drops the outer cell's 12 beside a nested table; capture-mode
    # fallback text keeps it.
    assert findings(NESTED, capture=False) == {1: (lost("12"), (), ())}
    assert findings(NESTED, capture=True) == {}


@BOTH_MODES
def test_one_row_table_before_multi_row_table_is_ordinal_2_snapshot_1(capture):
    parser = Parser("<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table>"
                    "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>",
                    capture_tables=capture)
    parser.get_pages(include_images=False)
    outputs = {key: value.replace("120", "") for key, value in parser.table_outputs.items()}
    report = check_tables(parser.soup, outputs, parser._table_pages, parser._snapshot_ordinals)
    assert report.failures == ("table 2 (snapshot 1, page 1): missing 120 x1 [body] (total 1)",)
    if capture:
        assert [s.ordinal for s in parser.table_snapshots] == [1]


def test_table_checks_can_be_disabled():
    parser = Parser(MERGE_LOSS, table_checks=False)
    parser.get_pages()
    assert parser.table_report is None
    assert parser.table_outputs == {}


def test_report_is_reset_between_get_pages_calls():
    parser = Parser(TWO_BY_TWO)
    parser.get_pages()
    first = parser.table_report
    parser.get_pages()
    assert parser.table_report == first
    assert len(parser.table_outputs) == 1


@pytest.mark.parametrize("capture", [False, True], ids=["normal", "capture"])
@pytest.mark.parametrize("table_checks", [False, True], ids=["unchecked", "checked"])
def test_effective_rows_runs_once_per_table(capture, table_checks, monkeypatch):
    # Snapshot ordinals reuse the rows _render_table needs, and nothing is computed for
    # them when neither capture nor checks need it (plan review round 1, finding 2).
    calls = []
    original = Parser._effective_rows
    monkeypatch.setattr(Parser, "_effective_rows", lambda self, table: calls.append(1) or original(self, table))
    parser = Parser("<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table>" + TWO_BY_TWO,
                    capture_tables=capture, table_checks=table_checks)
    parser.get_pages()
    assert len(calls) == 2
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_table_completeness_parser.py -q`
Expected: every test fails, with `AttributeError: 'Parser' object has no attribute 'table_report'` (or `'table_outputs'`). `test_table_checks_can_be_disabled` fails with `TypeError: ... unexpected keyword argument 'table_checks'`.

- [x] **Step 3: Implement**

In `src/sec2md/parser.py`:

1. Add the import after `from sec2md.encoding import DecodeDiagnostics, normalize_legacy_characters`:

```python
from sec2md.table_completeness import TableCompletenessReport, check_tables
```

2. In `Parser.__init__`, add the parameter after `capture_tables: bool = False,`:

```python
        table_checks: bool = True,
```

and after `self.capture_tables = capture_tables`:

```python
        self.table_checks = table_checks
        # Table completeness inputs, recorded during rendering without changing it.
        self.table_outputs: dict[int, str] = {}
        self._table_pages: dict[int, int] = {}
        self._snapshot_ordinals: dict[int, int] = {}
        self._snapshot_ordinal = 0
        self._root_table_rows: dict[int, list[list[Tag]]] = {}
        self.table_report: TableCompletenessReport | None = None
```

3. Add this method immediately before `def _process_element(self, element: Union[Tag, NavigableString]) -> str:`:

```python
    def _render_table(self, element: Tag) -> str:
        # A stream-root table's rows were already computed for its snapshot ordinal.
        eff_rows = self._root_table_rows.pop(id(element), None)
        if id(element) in self._unreliable_tables:
            self.includes_table = True
            return self._unreliable_tables[id(element)].original_text
        if eff_rows is None:
            eff_rows = self._effective_rows(element)
        if len(eff_rows) <= 1:
            cells = eff_rows[0] if eff_rows else []
            return self._one_row_table_to_text(cells)

        self.includes_table = True
        return TableParser(element, base_url=self.source_url).md().strip()
```

4. In `_process_element()`, replace the `if element.name == "table":` block

```python
        if element.name == "table":
            if id(element) in self._unreliable_tables:
                self.includes_table = True
                return self._unreliable_tables[id(element)].original_text
            eff_rows = self._effective_rows(element)
            if len(eff_rows) <= 1:
                cells = eff_rows[0] if eff_rows else []
                return self._one_row_table_to_text(cells)

            self.includes_table = True
            return TableParser(element, base_url=self.source_url).md().strip()
```

with

```python
        if element.name == "table":
            rendered = self._render_table(element)
            if self.table_checks and element.find_parent("table") is None:
                self.table_outputs[id(element)] = rendered
            return rendered
```

5. In the positioned-table branch of `_stream_pages()`, replace

```python
            if table_parser.is_table_like():
                self.includes_table = True
                if self.capture_tables:
                    self.table_snapshots.append(snapshot_positioned_table(
                        group, ordinal=len(self.table_snapshots) + 1, page=page_num,
```

with

```python
            if table_parser.is_table_like():
                self.includes_table = True
                self._snapshot_ordinal += 1
                if self.capture_tables:
                    self.table_snapshots.append(snapshot_positioned_table(
                        group, ordinal=self._snapshot_ordinal, page=page_num,
```

6. At the table site of `_stream_pages()`, replace

```python
        if root.name in {"table", "ul", "ol"}:
            if self.capture_tables and root.name == 'table' and len(self._effective_rows(root)) > 1:
                snapshot = snapshot_html_table(
                    root, ordinal=len(self.table_snapshots) + 1, page=page_num,
```

with

```python
        if root.name in {"table", "ul", "ol"}:
            # Ordinals count the tables that get a snapshot in capture mode, in every
            # mode, so table-completeness findings name the same snapshot either way.
            snapshot_ordinal = None
            if root.name == 'table' and (self.capture_tables or self.table_checks):
                self._table_pages.setdefault(id(root), page_num)
                rows = self._effective_rows(root)
                self._root_table_rows[id(root)] = rows
                if len(rows) > 1:
                    self._snapshot_ordinal += 1
                    snapshot_ordinal = self._snapshot_ordinal
                    self._snapshot_ordinals[id(root)] = snapshot_ordinal
            if self.capture_tables and snapshot_ordinal is not None:
                snapshot = snapshot_html_table(
                    root, ordinal=snapshot_ordinal, page=page_num,
```

The lines after it (`source_url=self.source_url, native_anchors=...`) stay as they are.

7. In `get_pages()`, after `self._unreliable_tables = {}`, add:

```python
        self.table_outputs = {}
        self._table_pages = {}
        self._snapshot_ordinals = {}
        self._snapshot_ordinal = 0
        self._root_table_rows = {}
        self.table_report = None
```

and immediately before `markdown = "\n\n".join(page.content for page in result if page.content)`, add:

```python
        if self.table_checks:
            self.table_report = check_tables(
                self.soup, self.table_outputs, self._table_pages, self._snapshot_ordinals
            )
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_table_completeness_parser.py tests/test_parser.py tests/test_xlsx_tables.py tests/test_xlsx.py -q`
Expected: all pass. The new file has 89 tests: 40 review cases in both modes, plus 9 more.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/parser.py tests/test_table_completeness_parser.py
git commit -m "feat: run table completeness checks from the parser"
```

---

### Task 7: Diagnostics fields, numeric recall and warning logs

`ParseDiagnostics` gains the spec's five fields, with defaults. `build_diagnostics()` takes the report and computes check 3 over the visible text it already builds. All three checks run together, so a missing report (policy `off`) also means no recall. `enforce_quality()` logs one warning per value failure under `strict` and `warn`, and raises for none of them. `core.py` turns the checks off when the policy is `off`.

**Files:**
- Modify: `src/sec2md/quality.py`, `src/sec2md/parser.py`, `src/sec2md/core.py`
- Test: `tests/test_quality.py`

**Interfaces:**
- Consumes: `TableCompletenessReport` (Task 5), `Parser.table_report` (Task 6).
- Produces:
  - **New `ParseDiagnostics` fields:** `table_completeness_failures: tuple[str, ...] = ()`, `table_completeness_reported: tuple[str, ...] = ()`, `table_structure_differences: tuple[str, ...] = ()`, `tables_checked: int = 0` and `numeric_recall: float | None = None`.
  - **`build_diagnostics(..., table_report=None)`.**
  - **Log line:** `sec2md table completeness: <message>`.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_quality.py`:

```python
LOSSY_TABLE = ("<p>" + "Revenue grew this year. " * 50 + "</p>"
               "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>9,943</td></tr>"
               "<tr><td>Cost</td><td>1,200</td></tr></table>")
LOSS_MESSAGE = "table 1 (snapshot 1, page 1): missing 9943 x1 [body] (total 1)"


@pytest.fixture
def lossy_renderer(monkeypatch):
    """Render tables without 9,943, as a column-merge defect would."""
    original = Parser._render_table
    monkeypatch.setattr(Parser, "_render_table", lambda self, element: original(self, element).replace("9,943", ""))


def test_parse_diagnostics_positional_construction_keeps_working():
    from sec2md.quality import ParseDiagnostics

    diagnostics = ParseDiagnostics(10, 10, 1.0, 0, 0, 1, 0, 0, (), ())
    assert diagnostics.table_completeness_failures == ()
    assert diagnostics.table_completeness_reported == ()
    assert diagnostics.table_structure_differences == ()
    assert diagnostics.tables_checked == 0
    assert diagnostics.numeric_recall is None


def test_diagnostics_with_table_findings_survive_pickling(lossy_renderer):
    import pickle

    parser = Parser(LOSSY_TABLE)
    parser.get_pages()
    assert parser.diagnostics.table_completeness_failures == (LOSS_MESSAGE,)
    assert pickle.loads(pickle.dumps(parser.diagnostics)) == parser.diagnostics


def test_build_diagnostics_records_table_report_and_numeric_recall():
    from sec2md.table_completeness import TableCompletenessReport, TableFinding

    finding = TableFinding(1, 1, 1, missing_values=(("50", "body", False),),
                           missing_reported=(("1", "reference"),),
                           structure=("source row 1: values out of order within the row",))
    diagnostics = build_diagnostics(
        "<p>Revenue 120 and cost 50.</p>", "Revenue 120 and cost.", [],
        mapped_element_ids=(), trace_failures=(), enforce_mappings=False,
        table_report=TableCompletenessReport(3, (finding,)),
    )
    assert diagnostics.table_completeness_failures == (finding.value_message(),)
    assert diagnostics.table_completeness_reported == (finding.reported_message(),)
    assert diagnostics.table_structure_differences == finding.structure_messages()
    assert diagnostics.tables_checked == 3
    assert diagnostics.numeric_recall == 0.5


def test_build_diagnostics_without_table_report_skips_all_three_checks():
    diagnostics = build_diagnostics(
        "<p>Revenue 120.</p>", "Revenue.", [],
        mapped_element_ids=(), trace_failures=(), enforce_mappings=False,
    )
    assert diagnostics.tables_checked == 0
    assert diagnostics.numeric_recall is None


@pytest.mark.parametrize("policy", ["strict", "warn"])
def test_table_failures_are_logged_but_never_enforced(policy, lossy_renderer, caplog):
    with caplog.at_level("WARNING"):
        output = convert_to_markdown(LOSSY_TABLE, quality_policy=policy)
    assert "9,943" not in output
    assert f"sec2md table completeness: {LOSS_MESSAGE}" in caplog.text


def test_off_policy_skips_table_checks(monkeypatch, caplog):
    monkeypatch.setattr("sec2md.parser.check_tables", lambda *a, **k: pytest.fail("checks ran"))
    with caplog.at_level("WARNING"):
        convert_to_markdown(LOSSY_TABLE, quality_policy="off")
        parse_filing(LOSSY_TABLE, quality_policy="off")
    assert "table completeness" not in caplog.text
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_quality.py -q`
Expected: the new tests fail:
- `AttributeError: 'ParseDiagnostics' object has no attribute 'table_completeness_failures'`
- `TypeError: build_diagnostics() got an unexpected keyword argument 'table_report'`
- the policy-`off` test fails with `checks ran`

- [x] **Step 3: Implement**

In `src/sec2md/quality.py`:

1. Replace `from typing import Collection, Literal, Sequence` with

```python
from typing import TYPE_CHECKING, Collection, Literal, Sequence
```

and after `from sec2md.models import Element, Page` add

```python

if TYPE_CHECKING:
    from sec2md.table_completeness import TableCompletenessReport
```

2. In `ParseDiagnostics`, after `warnings: tuple[str, ...]`, add:

```python
    # Table completeness (Phase A: reported, never enforced). Defaults keep existing
    # positional construction working.
    table_completeness_failures: tuple[str, ...] = ()
    table_completeness_reported: tuple[str, ...] = ()
    table_structure_differences: tuple[str, ...] = ()
    tables_checked: int = 0
    numeric_recall: float | None = None
```

3. In `build_diagnostics()`, add the parameter after `enforce_mappings: bool,`:

```python
    table_report: "TableCompletenessReport | None" = None,
```

replace

```python
    source_chars = len(_visible_source_text(source_text))
    output_chars = len(_visible_markdown_text(output))
```

with

```python
    source_visible = _visible_source_text(source_text)
    output_visible = _visible_markdown_text(output)
    source_chars = len(source_visible)
    output_chars = len(output_visible)
```

and in the returned `ParseDiagnostics(...)`, after `warnings=warnings,`, add:

```python
        table_completeness_failures=table_report.failures if table_report else (),
        table_completeness_reported=table_report.reported if table_report else (),
        table_structure_differences=table_report.structure if table_report else (),
        tables_checked=table_report.tables_checked if table_report else 0,
        # Checks 1-3 run together: Parser skips them all under quality_policy="off".
        numeric_recall=_numeric_recall(source_visible, output_visible) if table_report is not None else None,
```

4. Add this function immediately before `def enforce_quality(`:

```python
def _numeric_recall(source_visible: str, output_visible: str) -> float | None:
    """Share of visible source numbers present in the visible output (check 3, diagnostic only)."""

    expected = Counter(_normalized_numbers(source_visible))
    if not expected:
        return None
    available = Counter(_normalized_numbers(output_visible))
    matched = sum(min(count, available[token]) for token, count in expected.items())
    return matched / sum(expected.values())
```

5. In `enforce_quality()`, after

```python
    if policy == "off":
        return diagnostics
```

add

```python
    # Phase A: table completeness findings are reported, never enforced.
    for finding in diagnostics.table_completeness_failures:
        logger.warning("sec2md table completeness: %s", finding)
```

In `src/sec2md/parser.py`, in `get_pages()`, add the argument to the `self.diagnostics = build_diagnostics(` call after `enforce_mappings=include_elements,`:

```python
            table_report=self.table_report,
```

In `src/sec2md/core.py`:

- In both `Parser(` calls (in `convert_to_markdown()` and `parse_filing()`), add after `decode_diagnostics=decode_diagnostics,`:

```python
        table_checks=quality_policy != "off",
```

- In the three fallback `build_diagnostics(` calls, add `table_report=parser.table_report,` after their `enforce_mappings=...` argument. The calls are in `convert_to_markdown()` (return_pages branch and markdown branch) and in `parse_filing()`.

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_quality.py tests/test_core.py tests/test_table_completeness_parser.py -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/quality.py src/sec2md/parser.py src/sec2md/core.py tests/test_quality.py
git commit -m "feat: record table completeness and numeric recall in diagnostics"
```

---

### Task 8: `convert_with_diagnostics()` (decision D2)

`convert_to_markdown()` discards the diagnostics `enforce_quality()` returns. Its body moves into a private `_convert()` that returns `(result, diagnostics)`. `convert_to_markdown()` returns the first element, and the new public function returns both. Behavior, errors and return types of the existing functions are unchanged.

**Files:**
- Modify: `src/sec2md/core.py`, `src/sec2md/__init__.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: the `ParseDiagnostics` fields (Task 7).
- Produces: `sec2md.convert_with_diagnostics(source, *, base_url=None, user_agent=None, return_pages=False, embed_images=False, quality_policy="strict") -> tuple[str | List[Page], ParseDiagnostics]`.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_core.py`:

```python
TABLE_HTML = ("<p>Results for the year.</p><table><tr><th>Item</th><th>2026</th></tr>"
              "<tr><td>Revenue</td><td>9,943</td></tr><tr><td>Cost</td><td>1,200</td></tr></table>")


def test_convert_with_diagnostics_returns_the_same_output_and_its_diagnostics():
    from sec2md import convert_with_diagnostics

    markdown, diagnostics = convert_with_diagnostics(TABLE_HTML)
    assert markdown == convert_to_markdown(TABLE_HTML)
    assert diagnostics.tables_checked == 1
    assert diagnostics.table_completeness_failures == ()
    assert diagnostics.numeric_recall == 1.0


def test_convert_with_diagnostics_returns_pages():
    from sec2md import convert_with_diagnostics

    pages, diagnostics = convert_with_diagnostics(TABLE_HTML, return_pages=True)
    expected = convert_to_markdown(TABLE_HTML, return_pages=True)
    assert [page.content for page in pages] == [page.content for page in expected]
    assert diagnostics.pages == len(pages)


def test_convert_with_diagnostics_validates_policy_like_convert_to_markdown():
    from sec2md import convert_with_diagnostics

    with pytest.raises(ValueError):
        convert_with_diagnostics(TABLE_HTML, quality_policy="strictish")


def test_convert_with_diagnostics_is_public():
    import sec2md

    assert "convert_with_diagnostics" in sec2md.__all__
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_core.py -q -k convert_with_diagnostics`
Expected: 4 failures, `ImportError: cannot import name 'convert_with_diagnostics' from 'sec2md'`.

- [x] **Step 3: Implement**

In `src/sec2md/core.py`, replace the import

```python
from sec2md.quality import QualityPolicy, build_diagnostics, enforce_quality, validate_quality_policy
```

with

```python
from sec2md.quality import (
    ParseDiagnostics,
    QualityPolicy,
    build_diagnostics,
    enforce_quality,
    validate_quality_policy,
)
```

In `convert_to_markdown()`, keep the signature and docstring. Replace everything after the docstring, from `validate_quality_policy(quality_policy)` to the final `return output`, with the following. It also adds the two new functions after `convert_to_markdown()`:

```python
    return _convert(
        source,
        base_url=base_url,
        user_agent=user_agent,
        return_pages=return_pages,
        embed_images=embed_images,
        quality_policy=quality_policy,
    )[0]


def convert_with_diagnostics(
    source: str | bytes,
    *,
    base_url: str | None = None,
    user_agent: str | None = None,
    return_pages: bool = False,
    embed_images: bool = False,
    quality_policy: QualityPolicy = "strict",
) -> tuple[str | List[Page], ParseDiagnostics]:
    """
    Convert like ``convert_to_markdown()`` and also return the parse diagnostics.

    Takes the same arguments and raises the same errors. The diagnostics include the
    table completeness findings, which every policy except ``off`` computes and none
    enforces yet.

    Returns:
        (markdown string, or List[Page] if return_pages=True; ParseDiagnostics)
    """
    return _convert(
        source,
        base_url=base_url,
        user_agent=user_agent,
        return_pages=return_pages,
        embed_images=embed_images,
        quality_policy=quality_policy,
    )


def _convert(
    source: str | bytes,
    *,
    base_url: str | None,
    user_agent: str | None,
    return_pages: bool,
    embed_images: bool,
    quality_policy: QualityPolicy,
) -> tuple[str | List[Page], ParseDiagnostics]:
    validate_quality_policy(quality_policy)
    source_url = source if isinstance(source, str) and is_url(source) else None
    link_resolution_url = _link_resolution_url(source_url, base_url)
    html, decode_diagnostics = _resolve_source(source, user_agent=user_agent)

    if embed_images and source_url:
        html = _embed_images(html, source_url, user_agent)

    parser = Parser(
        html,
        source_url=link_resolution_url,
        decode_diagnostics=decode_diagnostics,
        table_checks=quality_policy != "off",
    )

    if return_pages:
        pages = parser.get_pages()
        diagnostics = parser.diagnostics
        if diagnostics is None:
            diagnostics = build_diagnostics(
                html,
                "\n\n".join(page.content for page in pages if page.content),
                pages,
                mapped_element_ids=tuple(
                    element_id
                    for element_id, nodes in parser.block_nodes_map.items()
                    if nodes
                ),
                trace_failures=parser.trace_numeric_failures,
                enforce_mappings=True,
                table_report=parser.table_report,
            )
        return pages, enforce_quality(diagnostics, quality_policy)

    output = parser.markdown()
    pages = parser._last_pages
    diagnostics = parser.diagnostics
    if diagnostics is None or pages is None:
        pages = pages or parser.get_pages()
        diagnostics = build_diagnostics(
            html,
            output,
            pages,
            mapped_element_ids=tuple(
                element_id
                for element_id, nodes in parser.block_nodes_map.items()
                if nodes
            ),
            trace_failures=parser.trace_numeric_failures,
            enforce_mappings=True,
            table_report=parser.table_report,
        )
    return output, enforce_quality(diagnostics, quality_policy)
```

In `src/sec2md/__init__.py`, replace

```python
from sec2md.core import convert_to_markdown, parse_filing
```

with

```python
from sec2md.core import convert_to_markdown, convert_with_diagnostics, parse_filing
```

and add `"convert_with_diagnostics",` to `__all__` after `"convert_to_markdown",`.

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_core.py tests/test_quality.py tests/test_integration.py -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/core.py src/sec2md/__init__.py tests/test_core.py
git commit -m "feat: add convert_with_diagnostics"
```

---

### Task 9: XLSX result fields

- **`XlsxExportResult.parse_diagnostics`** carries the full `ParseDiagnostics`.
- **`XlsxTableResult.completeness`** carries that table's messages:
  - they come from `TableFinding.messages()`;
  - findings are matched to worksheets by snapshot ordinal, since worksheet ordinals are snapshot ordinals.
- **`quality_policy='off'`** skips the checks, as in Task 7.
- **Nothing else changes.** `status`, `issues` and `diagnostics` stay as they are (Phase A).

**Files:**
- Modify: `src/sec2md/xlsx.py`
- Test: `tests/test_xlsx.py`

**Interfaces:**
- Consumes: `Parser.table_report`, `TableFinding.messages()`, `TableFinding.snapshot_ordinal`.
- Produces: `XlsxTableResult.completeness: tuple[str, ...] = ()` and `XlsxExportResult.parse_diagnostics: ParseDiagnostics | None = None`.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_xlsx.py`:

```python
def drop_from_markdown(monkeypatch, text):
    """Render tables without text, leaving the snapshots (and so the workbook) intact."""
    from sec2md.parser import Parser

    original = Parser._render_table
    monkeypatch.setattr(Parser, '_render_table', lambda self, element: original(self, element).replace(text, ''))


def test_completeness_findings_are_reported_without_changing_results(tmp_path, monkeypatch):
    baseline = sec2md.export_xlsx(TABLE, tmp_path / 'baseline.xlsx')
    drop_from_markdown(monkeypatch, '96,221')
    result = sec2md.export_xlsx(TABLE, tmp_path / 'lossy.xlsx')
    message = 'table 1 (snapshot 1, page 1): missing 96221 x1 [body] (total 1)'
    assert result.tables[0].completeness == (message,)
    assert result.parse_diagnostics.table_completeness_failures == (message,)
    assert baseline.tables[0].completeness == ()
    assert baseline.parse_diagnostics.tables_checked == 1
    assert result.status == baseline.status == 'complete'
    assert result.diagnostics == baseline.diagnostics
    assert [(t.status, t.issues) for t in result.tables] == [(t.status, t.issues) for t in baseline.tables]


def test_off_policy_exports_without_completeness(tmp_path, monkeypatch):
    drop_from_markdown(monkeypatch, '96,221')
    result = sec2md.export_xlsx(TABLE, tmp_path / 'filing.xlsx', quality_policy='off')
    assert result.tables[0].completeness == ()
    assert result.parse_diagnostics.tables_checked == 0


def test_results_keep_positional_construction_and_pickling(tmp_path):
    import pickle
    from pathlib import Path

    table = sec2md.XlsxTableResult(1, 'T1', 'exported', ())
    export = sec2md.XlsxExportResult(Path('x.xlsx'), 'complete', (table,), ())
    assert table.completeness == ()
    assert export.parse_diagnostics is None
    result = sec2md.export_xlsx(TABLE, tmp_path / 'filing.xlsx')
    assert pickle.loads(pickle.dumps(result)) == result
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_xlsx.py -q`
Expected: 3 failures, `AttributeError: 'XlsxTableResult' object has no attribute 'completeness'` (or `'parse_diagnostics'`).

- [x] **Step 3: Implement**

In `src/sec2md/xlsx.py`:

1. Replace `from sec2md.quality import build_diagnostics, enforce_quality` with

```python
from sec2md.quality import ParseDiagnostics, build_diagnostics, enforce_quality
```

2. In `XlsxTableResult`, after `issues: tuple[str, ...]`, add:

```python
    # This table's table-completeness findings. Phase A reports them without
    # changing status or issues.
    completeness: tuple[str, ...] = ()
```

3. In `XlsxExportResult`, after `diagnostics: tuple[str, ...]`, add:

```python
    parse_diagnostics: ParseDiagnostics | None = None
```

4. In `export_xlsx()`, replace

```python
    parser = Parser(html, source_url=link_url, decode_diagnostics=decode_diagnostics,
                    capture_tables=True)
```

with

```python
    parser = Parser(html, source_url=link_url, decode_diagnostics=decode_diagnostics,
                    capture_tables=True, table_checks=quality_policy != 'off')
```

5. In its fallback `build_diagnostics(` call, add after `trace_failures=parser.trace_numeric_failures, enforce_mappings=True,`:

```python
            table_report=parser.table_report,
```

6. Replace

```python
    results = tuple(XlsxTableResult(w.ordinal, w.worksheet_name, w.status, w.issues)
                    for w in worksheets)
```

with

```python
    # Worksheet ordinals are snapshot ordinals, which table findings also carry.
    findings = parser.table_report.findings if parser.table_report else ()
    completeness = {f.snapshot_ordinal: f.messages() for f in findings if f.snapshot_ordinal is not None}
    results = tuple(XlsxTableResult(w.ordinal, w.worksheet_name, w.status, w.issues,
                                    completeness.get(w.ordinal, ()))
                    for w in worksheets)
```

7. Replace the final `return XlsxExportResult(path, status, results, tuple(messages))` with

```python
    return XlsxExportResult(path, status, results, tuple(messages), diagnostics)
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_xlsx.py tests/test_xlsx_tables.py tests/test_xlsx_writer.py tests/accuracy/test_xlsx_accuracy.py -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/sec2md/xlsx.py tests/test_xlsx.py
git commit -m "feat: report table completeness in XLSX export results"
```

---

### Task 10: Fixture pins, mutations and unchanged rendering

These tests lock in the spec's acceptance criteria on the seven offline fixtures:

- **Exact failures.** Check 1 reports exactly the 9 pinned tables with their 20 value tokens, and check 2 reports nothing, in both modes.
- **Mutations.** All three are detected.
- **Rendering.** It is identical with and without the checks.

This task adds no production code. The pins describe the code from Tasks 1–9, so the tests pass at once; Step 2 proves they can fail.

**Files:**
- Create: `tests/test_table_completeness_fixtures.py`

**Interfaces:**
- Consumes: `Parser(table_checks=...)`, `Parser.table_report`, `Parser.table_outputs`, `Parser._table_pages`, `Parser._snapshot_ordinals`, `check_tables()`, `output_line_numbers()`, `tests.accuracy.fixtures.load_fixture`.
- Produces: `PINNED_FAILURES`, which the table-merge and header-rules work will shrink.

- [x] **Step 1: Write the tests**

Create `tests/test_table_completeness_fixtures.py`:

```python
"""Table completeness on the offline SEC fixtures: pinned losses, mutations, unchanged rendering."""

import re
import warnings
from functools import lru_cache

import pytest

from sec2md.chunker.blocks import is_separator_row
from sec2md.encoding import decode_html
from sec2md.parser import Parser
from sec2md.table_completeness import check_tables, output_line_numbers
from sec2md.table_parser import TableParser
from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture

# Every value-class check-1 failure on the fixtures today, as {unit ordinal: missing tokens}.
# Each traces to a parser defect named in the 2026-10-02 audit; the table-merge and
# header-rules spec should empty this list. A new loss or a fixed loss both fail the test,
# so update this list deliberately.
PINNED_FAILURES = {
    "aapl-2023-10k": {
        13: ("-1",),       # repurchase-table header, lost with its plain-text "(1)"
        32: ("74427",),    # column-merge row 0
        49: ("9943",),     # column-merge row 0
        53: ("4258",),     # column-merge row 0
    },
    "nvda-2026-10k": {},
    "nvda-2002-10k": {19: ("1997", "1998", "31", "31")},  # period headers
    "nvda-2026-q2-10q": {31: ("3.5",)},                   # $3.5 guarantees row
    "nvda-2026-08-26-8k": {},
    "nvda-2026-ex99-1": {9: ("15365", "24077", "42779", "50344", "74421")},  # operating cash flow row
    "nvda-2026-ex99-2": {7: ("3.5",), 10: ("15365", "24077", "42779", "50344", "74421")},
}
TABLES_CHECKED = {
    "aapl-2023-10k": 57, "nvda-2026-10k": 62, "nvda-2002-10k": 97, "nvda-2026-q2-10q": 49,
    "nvda-2026-08-26-8k": 4, "nvda-2026-ex99-1": 10, "nvda-2026-ex99-2": 11,
}


@lru_cache(maxsize=None)
def fixture_html(fixture_id):
    return decode_html(load_fixture(fixture_id)[1])[0]


def parse(fixture_id, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = Parser(fixture_html(fixture_id), **kwargs)
        pages = parser.get_pages(include_images=False)
    return parser, pages


def test_pinned_list_covers_every_fixture():
    assert set(PINNED_FAILURES) == set(FIXTURE_IDS) == set(TABLES_CHECKED)


@pytest.mark.parametrize("capture", [False, True], ids=["normal", "capture"])
@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_fixture_reports_exactly_the_pinned_failures(fixture_id, capture):
    report = parse(fixture_id, capture_tables=capture)[0].table_report
    actual = {f.ordinal: tuple(sorted(token for token, _, _ in f.missing_values))
              for f in report.findings if f.missing_values}
    assert actual == PINNED_FAILURES[fixture_id]
    assert report.tables_checked == TABLES_CHECKED[fixture_id]
    assert report.structure == ()
    assert not any(ambiguous for f in report.findings for _, _, ambiguous in f.missing_values)


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_rendering_is_identical_with_and_without_checks(fixture_id):
    _, checked = parse(fixture_id)
    _, unchecked = parse(fixture_id, table_checks=False)
    assert [page.content for page in checked] == [page.content for page in unchecked]


def test_capture_snapshots_are_identical_with_and_without_checks():
    with_checks = parse("aapl-2023-10k", capture_tables=True)[0].table_snapshots
    without = parse("aapl-2023-10k", capture_tables=True, table_checks=False)[0].table_snapshots
    assert with_checks == without


def reverse_numeric_cells(segment):
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        for i, value in zip(idx, [cells[i] for i in idx][::-1]):
            cells[i] = value
        out.append("|".join(cells))
    return "\n".join(out)


def swap_first_body_rows(segment):
    """Swap the first two distinct body lines that each carry two or more tokens."""
    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    if separator is None:
        return segment
    rows = [i for i in range(separator + 1, len(lines)) if len(output_line_numbers(lines[i])) >= 2]
    pair = next(((a, b) for a, b in zip(rows, rows[1:]) if lines[a] != lines[b]), None)
    if pair:
        a, b = pair
        lines[a], lines[b] = lines[b], lines[a]
    return "\n".join(lines)


def test_blank_table_renderer_is_detected(monkeypatch):
    monkeypatch.setattr(TableParser, "md", lambda self, *args, **kwargs: "")
    report = parse("aapl-2023-10k")[0].table_report
    value_flagged = [f for f in report.findings if f.missing_values]
    reference_only = [f for f in report.findings if not f.missing_values and f.missing_reported]
    # The 7 units without value failures: 6 reference-only units (3 exhibit indexes,
    # 3 signature blocks) whose losses are reported, and one one-row table rendered as text.
    assert (report.tables_checked, len(value_flagged), len(reference_only)) == (57, 50, 6)


@pytest.mark.parametrize("mutate, message, expected", [
    (reverse_numeric_cells, "values out of order within the row", 50),
    (swap_first_body_rows, "appears before an earlier source row", 48),
])
def test_row_structure_mutations_are_detected(mutate, message, expected):
    parser, _ = parse("aapl-2023-10k")
    outputs = {key: mutate(value) for key, value in parser.table_outputs.items()}
    report = check_tables(parser.soup, outputs, parser._table_pages, parser._snapshot_ordinals)
    assert sum(1 for f in report.findings if any(message in s for s in f.structure)) == expected
```

- [x] **Step 2: Run the tests, then prove the pins can fail**

Run: `python -m pytest tests/test_table_completeness_fixtures.py -q`
Expected: 26 passed, in about 35 seconds.

Then change `49: ("9943",)` to `49: ("9944",)` in `PINNED_FAILURES` and run `python -m pytest tests/test_table_completeness_fixtures.py -q -k "aapl and pinned"`.
Expected: 2 failures, normal and capture. Revert the change.

- [x] **Step 3: Run the full suite and ruff**

Run: `python -m pytest -q` and `python -m ruff check src tests`
Expected: about 790 passed, 14 deselected; ruff reports `All checks passed!`.

- [x] **Step 4: Commit**

```bash
git add tests/test_table_completeness_fixtures.py
git commit -m "test: pin fixture table completeness failures and mutation detection"
```

---

### Task 11: Phase A corpus run and the D3 measurement

The spec puts two things in Phase A:

- **A corpus run of at least 50 filings,** with every false positive recorded in the spec. The 7 fixtures and the 20 RCQ filings already reviewed count toward the 50.
- **The D3 measurement.** It asks how much a per-table word check would add over check 1, and how much of it would be noise. It is measured in the same run, so D3 can then be decided.

**Phase A is complete only when this task's record is in the spec and Astra has reviewed it.**

The tooling is already on `main`, in `docs/superpowers/audits/2026-10-03-table-completeness-corpus/`:

| Script | What it does |
|---|---|
| `fetch_edgar.py` | Downloads 16 primary documents from new issuers into a cache and writes a manifest with their SHA-256 hashes. The issuers are JPM, XOM, BRK, KO, PFE, WMT, MSFT, TSLA, JNJ, CAT, PRU, BAC, HD and UNH (10-Ks filed in 2025), plus AMZN and GOOGL (10-Qs filed in 2025). |
| `corpus_phase_a.py` | Runs the implementation over the corpus in both rendering modes, records every finding and each table's missing words, and prints the summary the spec needs. `--inspect` shows one table's source rows and output. |

The corpus, deduplicated by content hash:

| Part | Documents | Filings |
|---|---|---|
| Fixtures | 7 | 5 |
| RCQ primary 10-Ks and 10-Qs (META 10, RDDT 10, NVDA 12) | 32 | 32 |
| RCQ exhibits with at least two tables | 52 | (exhibits of the RCQ filings) |
| EDGAR, new issuers | 16 | 16 |

That makes 107 documents and 53 distinct filings. Two RCQ NVDA primaries are skipped because they are the same filings as fixtures.

**Preview.** `corpus_phase_a.py` ran on the scratch implementation over the 91 documents available offline.

| Measure | Result |
|---|---|
| Tables checked | 2,131 |
| Tables with value failures | 141 (185 tokens: 102 header, 45 body, 38 label) |
| Reported tokens | 41 reference |
| Ambiguous tokens | 0 |
| Check-2 findings | 0 |
| Tables without output | 21 |
| Mode disagreements | 0 |
| D3: tables with missing words | 178 |
| D3: of those, without a check-1 failure | 54 |

Two newly flagged exhibit tables were inspected, and both are genuine renderer losses:

- an NVDA exhibit table holding only "Effective Date: September 16, 2024", which never reaches the Markdown;
- a META award-agreement table whose whole "Taxes … Section 6 …" paragraph cell is dropped.

Expect figures of this size. The new findings, not the old ones, are what this task must classify.

**Files** (all in the main checkout, never in the worktree):
- Create: `docs/superpowers/audits/2026-10-03-table-completeness-corpus/results.json`, `edgar_manifest.json` and `classification.md`
- Modify: `docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md` (the Phase A record)

**Interfaces:**
- Consumes: the finished implementation (Tasks 1–10), run from the worktree root.
- Produces: the spec's Phase A record, which Task 12's PR description links to.

- [x] **Step 1: Fetch the EDGAR filings**

This downloads 16 documents from sec.gov, so ask the user first, and ask for the User-Agent string to send: SEC requires a name and email. Do not invent one, and do not use an address from another context without asking.

Use the main checkout's ignored `outputs/` folder as the cache:

```bash
python C:/Users/einstein/kelab5am/sec2md/docs/superpowers/audits/2026-10-03-table-completeness-corpus/fetch_edgar.py --user-agent "<name> <email>" --cache C:/Users/einstein/kelab5am/sec2md/outputs/table-completeness-corpus --manifest C:/Users/einstein/kelab5am/sec2md/docs/superpowers/audits/2026-10-03-table-completeness-corpus/edgar_manifest.json
```

Expected: one line per issuer, then `16 fetched, 0 failed`.

At least 13 are required, to reach 50 distinct filings. For each failure (a name mismatch, or no such filing), replace that issuer in `ISSUERS` with another large filer of the same form, and run the script again; cached files are not fetched again. Record each replacement in `classification.md`.

- [x] **Step 2: Run the corpus**

From the worktree root:

```bash
python C:/Users/einstein/kelab5am/sec2md/docs/superpowers/audits/2026-10-03-table-completeness-corpus/corpus_phase_a.py --edgar-cache C:/Users/einstein/kelab5am/sec2md/outputs/table-completeness-corpus --out C:/Users/einstein/kelab5am/sec2md/docs/superpowers/audits/2026-10-03-table-completeness-corpus/results.json
```

Expected:
- a JSON summary with `documents_total` of 107, and `mode_mismatched_documents: 0`;
- the 91 offline documents show the preview figures above, unchanged.

Rendering-mode disagreement is a defect: investigate it like a false positive (Step 4).

- [x] **Step 3: Classify every new finding**

Previously reviewed documents need no new classification: the 7 fixtures and the 20 META and RDDT primaries. First run the parity command from Task 12, Step 5 (`parity_impl.py`). It must report 0 mismatches, which confirms those documents' findings are unchanged from the reviewed evidence.

For every other document, take each table with a value failure, a check-2 finding, an ambiguous token, or no output. Inspect it with:

```bash
python C:/Users/einstein/kelab5am/sec2md/docs/superpowers/audits/2026-10-03-table-completeness-corpus/corpus_phase_a.py --edgar-cache C:/Users/einstein/kelab5am/sec2md/outputs/table-completeness-corpus --inspect "<document id>" <table>
```

Then write one row per table in `classification.md`:

```markdown
| Document | Table | Tokens (role) | Verdict | Cause |
|---|---|---|---|---|
| rcq-exhibit:META__10-Q__2025-Q2__.../a-3xxtfn45xh6zkzu2.htm | 1 | 6 (body) | genuine loss | paragraph cell dropped by TableParser |
```

The verdict is `genuine loss` when the token's text is absent from that table's output, and `false positive` otherwise. When many tables share one cause, as with repeated exhibit headers, one row may cover a run of tables; list their numbers. Also scan the reported-only tokens and note any that look like values.

- [x] **Step 4: Resolve each false positive**

For each false positive, run the v6 prototype on the same document to see whether it reports the same finding: `inspect_v6.py`, or `completeness_v6.analyze`.

- **The implementation differs from the prototype:** that is an implementation defect. In the worktree:
  1. Add a failing test to `tests/test_table_completeness_parser.py` built from a minimal copy of the table.
  2. Fix the code.
  3. Rerun Step 2 and the full suite.
- **The prototype agrees:** the spec's definitions cause it. Do not change the code. Record the case for the spec in Step 6, so Astra can decide.

- [x] **Step 5: Measure D3**

From `results.json`, take the tables whose `word_losses` entry has `check1_value_failure: false`: these are the tables only a word check would flag.

Classify 30 of them, or all of them if fewer, picking every k-th table in document order so all groups are sampled. Each is one of:

- **genuine text loss:** words absent from the output that a reader needs;
- **noise:** words reordered into fused headers, repeated header words collapsed, or formatting artefacts.

In `classification.md`, record:
- the counts;
- the noise rate;
- the summary's top missing words;
- two examples of each kind.

- [x] **Step 6: Record Phase A in the spec**

In the main checkout, add a section "Phase A corpus run" to the spec, after "Evidence", and an entry in its review history. Record:

- **The corpus:** documents and filings per part, the EDGAR manifest path, and any replaced issuers.
- **The summary figures:**
  - tables checked;
  - check-1 tables and tokens, by role;
  - reported tokens, by class;
  - ambiguous tokens;
  - check-2 tables;
  - tables without output;
  - mode agreement.
- **False positives:** each one, with its cause and its resolution (fixed in the implementation, or a definition case awaiting decision).
- **The D3 measurement** and a recommendation. That decision then goes to Astra and the user.
- **The overhead decision:** Phase A accepts up to +25% parse time against unchanged `main` on the fixtures, by the user's decision of 2026-10-03, and the 10% target moves to Phase B. Change the "Where it runs" target and the matching acceptance criterion to match.

- [ ] **Step 7: Commit on `main`, after asking**

These files belong on `main`, not on the feature branch. Ask the user before committing, then:

```bash
git -C C:/Users/einstein/kelab5am/sec2md add docs/superpowers/audits/2026-10-03-table-completeness-corpus docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md
git -C C:/Users/einstein/kelab5am/sec2md commit -m "docs: record the table completeness Phase A corpus run"
```

---

### Task 12: Documentation, CHANGELOG, parity and overhead

The spec's acceptance criteria require the README and `docs/usage/direct-conversion.md` to say what strict checks and does not check, including the size thresholds. Before the PR, also do three things against unchanged `main`:

- confirm parity with the reviewed prototype;
- measure the overhead;
- show that the Markdown content is unchanged.

**Files:**
- Modify: `README.md`, `docs/usage/direct-conversion.md`, `docs/usage/xlsx-export.md`, `CHANGELOG.md`

**Interfaces:**
- Consumes: everything above.
- Produces: user documentation, and the figures for the PR description.

- [x] **Step 1: README**

In `README.md`, under "### Input, quality, and exhibit links", insert this after the paragraph ending "A strict failure exposes the immutable `ParseQualityError.diagnostics` object.":

```markdown
Strict raises in these cases:

- a source with at least 1,000 visible characters produces empty output
- a source with at least 10,000 visible characters keeps less than 10% of them
- the output contains replacement (U+FFFD) or C1 control characters
- an element lacks a source-node mapping
- a number in an element cannot be traced to its source nodes

Strict does not check that every source number reached the output. Table
completeness checks do that for each table, and they are reported but not
enforced yet. They appear in these `ParseDiagnostics` fields:

- `table_completeness_failures`: numbers missing from a table's output
- `table_completeness_reported`: lost footnote markers and references such as
  `Note 9`, which are never enforced
- `table_structure_differences`: rows or values that changed order
- `numeric_recall`: the share of visible source numbers present in the output

Each failure is also logged as a warning. Use `convert_with_diagnostics()` to get
the output together with its diagnostics. `quality_policy="off"` skips these
checks.
```

- [x] **Step 2: Direct-conversion usage**

In `docs/usage/direct-conversion.md`, under "### Quality policy and supported input", insert this after the paragraph ending "structured quality evidence.":

````markdown
Strict raises when a source with at least 1,000 visible characters produces
empty output, or when one with at least 10,000 keeps less than 10% of them. It
also raises on replacement or C1 control characters, on elements without a
source-node mapping, and on numbers in an element that cannot be traced to its
source.

It does not yet fail when a table loses a number. Table completeness findings are
reported in the diagnostics and logged as warnings:

```python
from sec2md import convert_with_diagnostics

markdown, diagnostics = convert_with_diagnostics(html_bytes)
for failure in diagnostics.table_completeness_failures:
    print(failure)  # table 49 (snapshot 41, page 46): missing 9943 x1 [body] (total 1)
print(diagnostics.tables_checked, diagnostics.numeric_recall)
```
````

- [x] **Step 3: XLSX usage**

In `docs/usage/xlsx-export.md`, replace

```markdown
The frozen `XlsxExportResult` contains `path`, `status`, `tables` and `diagnostics`.
Each `XlsxTableResult` contains `ordinal`, `sheet_name`, `status` and `issues`.
```

with

```markdown
The frozen `XlsxExportResult` contains `path`, `status`, `tables`, `diagnostics`
and `parse_diagnostics`, the parser's full `ParseDiagnostics`. Each
`XlsxTableResult` contains `ordinal`, `sheet_name`, `status`, `issues` and
`completeness`. That last field holds the table's completeness findings: numbers
its Markdown lost and rows that changed order. Completeness findings do not
change `status` or `issues` yet.
```

- [x] **Step 4: CHANGELOG**

In `CHANGELOG.md`, add to the top of the "## 0.1.22+rcq.3 (unreleased, pending review)" list:

```markdown
- Table completeness checks, report-only: each visible table's Markdown is
  compared with its source table.
  - `ParseDiagnostics` gains `table_completeness_failures`,
    `table_completeness_reported`, `table_structure_differences`,
    `tables_checked` and `numeric_recall`.
  - Failures are logged as warnings under `strict` and `warn`; nothing raises
    yet. `quality_policy="off"` and `Parser(table_checks=False)` skip the checks.
  - `convert_with_diagnostics()` returns the output with its diagnostics.
  - `export_xlsx()` results gain `parse_diagnostics` and a per-table
    `completeness`.
- Quality checks normalize euro and pound amounts like dollar amounts.
```

- [x] **Step 5: Parity with the reviewed prototype, and overhead against `main`**

Run both from the worktree root. The scripts are in the main checkout's docs folder; the worktree has the same files from `main`.

```bash
python docs/superpowers/audits/2026-10-02-repo-audit/prototypes/v6/parity_impl.py docs/superpowers/audits/2026-10-02-repo-audit/prototypes/v6
```

Expected: `documents 27: finding mismatches 0, header-row mismatches 0`.
- Without access to `E:\RCQWealth`, add `--fixtures-only` and expect `documents 7: ...`.
- Any `MISMATCH` line is a defect in Tasks 2–6: fix it before opening the PR.

```bash
python docs/superpowers/audits/2026-10-02-repo-audit/prototypes/v6/overhead_vs_main.py --baseline C:/Users/einstein/kelab5am/sec2md --candidate .
```

Expected: one line per fixture, and a `total` line at or below `+25.0%`. The validated implementation measured +20.6% in total, with AAPL highest at +24.0%. If the total exceeds +25%, stop and report it: the overhead limit is a user decision, not something to work around. Copy both outputs into the PR description.

- [x] **Step 6: Content before and after, against `main`**

The checks only report, so the Markdown must be exactly what `main` produces. The accuracy suite measures that content: words, numbers and financial rows kept, for each fixture. Run it on both checkouts from the worktree root:

```bash
python docs/superpowers/audits/2026-10-02-repo-audit/prototypes/v6/accuracy_vs_main.py --baseline C:/Users/einstein/kelab5am/sec2md --candidate .
```

Expected: the line `fixtures 7: 0 with a changed score or hash`, and exit status 0. The validated implementation printed:

| Fixture | Words | Numbers | Financial rows | Pass marks (words/numbers/rows) | Markdown | Pages |
|---|---|---|---|---|---|---|
| AAPL 10-K | 98.59 → 98.59 | 93.93 → 93.93 | 99.71 → 99.71 | 98 / 93 / 99 | same | same |
| NVDA 10-K | 99.71 → 99.71 | 95.23 → 95.23 | 99.17 → 99.17 | 98 / 93 / 99 | same | same |
| NVDA 2002 10-K | 99.96 → 99.96 | 99.87 → 99.87 | 90.19 → 90.19 | 99 / 95 / 89 | same | same |
| NVDA 10-Q | 99.81 → 99.81 | 98.15 → 98.15 | 99.26 → 99.26 | 98 / 93 / 99 | same | same |
| NVDA 8-K | 98.77 → 98.77 | 95.83 → 95.83 | 100.00 → 100.00 | 98 / 93 / 99 | same | same |
| EX-99.1 | 99.68 → 99.68 | 99.12 → 99.12 | 98.04 → 98.04 | 99 / 98 / 97 | same | same |
| EX-99.2 | 99.57 → 99.57 | 98.62 → 98.62 | 98.11 → 98.11 | 99 / 98 / 94 | same | same |

Any changed score or `DIFF` is a rendering change: find and fix it before opening the PR. Copy the output into the PR description.

- [x] **Step 7: Final checks and commit**

Run: `python -m pytest -q` and `python -m ruff check src tests`
Expected: all pass.

```bash
git add README.md docs/usage/direct-conversion.md docs/usage/xlsx-export.md CHANGELOG.md
git commit -m "docs: describe strict checks and table completeness diagnostics"
```

Open the PR from `feat/table-completeness` to `main`. Its description lists:

- the pinned failures, with their audit causes;
- the parity and overhead output from Step 5;
- the content before/after table from Step 6;
- the Task 11 corpus summary, with a link to its record in the spec;
- reviewer notes 1–7 from this plan.

If review changes the spec, update the spec in the main checkout, not in the branch.
