# sec2md XLSX Export Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task after implementation is requested. Steps use checkbox syntax for tracking. This document authorizes no execution, delegation, merge, deployment or skill creation by itself.

**Goal:** Export one supplied filing to an editable workbook containing Contents and one worksheet per extracted table, using the approved NVIDIA sample layout with **no frozen rows**.

**Architecture:** Capture table cells and span/provenance information during existing sec2md traversal, before Markdown flattens the structure. Prepare conservative copy-ready values alongside original display text, then write XLSX through an optional openpyxl dependency. The exporter is a one-document Python API; Markdown behavior and return types remain compatible.

**Tech stack:** Existing Python `>=3.10,<3.13`, BeautifulSoup/lxml and pytest; optional `openpyxl>=3.1.5,<4`; standard-library Decimal, hashing and filesystem operations.

**Spec:** [Updated design specification](../specs/2026-09-19-sec2md-xlsx-export-design.md).

**Accepted sample:** [Prototype review guide](C:/Users/einstein/kelab5am/rcq-wealth/outputs/01a09638-84f1-79c3-92a9-ac199fd1ade6/xlsx-prototype-20260919/START-HERE.md). The user approved its output and requested removal of the frozen top 11 rows. Only planning is authorized in this turn.

## Project and baseline

This plan belongs to sec2md. Comparison evidence and prototype files remain in the RCQ research workspace. **The implementation target is `C:\Users\einstein\kelab5am\sec2md`, not rcq-wealth.** All `src/`, `tests/`, `docs/`, and configuration paths in the tasks below are relative to sec2md unless explicitly qualified.

Inspected baseline: `c6fe201d4589e425c4f15eba8cd423f2e808f15e`, package `0.1.22+rcq.2`. Before execution, recheck HEAD, relevant worktrees, current instructions and local changes. If unchanged, work in `C:\Users\einstein\kelab5am\sec2md\.worktrees\xlsx-export` on `codex/xlsx-export`. Reuse an existing matching worktree rather than creating a duplicate. Report the target repository, worktree and branch before editing implementation. Do not create that worktree during this planning task.

## Global constraints and settled defaults

- One workbook per primary HTML document. Include all tables emitted by the existing parser's tabular path, in source order, plus Contents. Include nonfinancial tables. Do not deduplicate, join continuations or silently drop failures.
- No frozen rows anywhere. Table sheets use `freeze_panes="B1"` (first column only), Contents uses `None`. No `B12`, vertical split, or equivalent pinned metadata/header block.
- Keep the accepted title, source, units, copy-ready table, notes and visible original-text areas. No merged cells in the copy range. Source strings remain available even after numeric conversion.
- Keep reported magnitude and scale. Dates and reported dashes stay text; blanks stay blank; explicit zeros stay zero. Percentages store fractions with percentage formats. Ambiguity stays text with an actionable note.
- Recover from identifiable table-local reliability failures and continue. Unexpected programming errors and workbook publication failures remain explicit errors. No automatic retries that repeat a deterministic parsing failure.
- Optional extra `xlsx = ["openpyxl>=3.1.5,<4"]`; no mandatory pandas, EdgarTools, artifact-tool, Excel installation, browser, network service or Sheets dependency.
- Default export quality is `warn`. Existing Markdown defaults stay unchanged. `strict` rejects parse-quality or table reliability failures before publication. `off` bypasses parser quality enforcement only; it must not disable conversion safeguards or conceal export problems.
- Public API first. No new CLI framework, custom skill, Google Sheets delivery, historical consolidation, row matching, inter-filing formulas, RCQ integration or live-vault changes.
- Never change source fixtures, manifests, old comparison scripts, approved sample XLSX files or their validation records. New evidence goes in the implementation worktree's output directory.
- A release label is not needed to write this feature. Keep the existing version during implementation; version bump/pin update and integration are separate release decisions.

## File ownership and shared interfaces

| File | Responsibility |
| --- | --- |
| New `src/sec2md/xlsx_values.py` | Strict numeric token conversion; Decimal validation, format and review reason. No workbook dependency. |
| New `src/sec2md/xlsx_tables.py` | Table records, source snapshots, logical grid mapping, headers, context, references and preparation. No workbook dependency. |
| Modify `parser.py`, `table_parser.py`, `absolute_table_parser.py` | Opt-in capture of existing table occurrences before flattening; preserve default parsing behavior. |
| New `src/sec2md/xlsx_writer.py` | Workbook layout, text typing, links, original views and destination publication. Imports openpyxl only inside export operations. |
| New `src/sec2md/xlsx.py` | Public orchestration and export result/error types. |
| Modify `__init__.py`; narrowly reuse `core.py` helpers | Expose export and reuse validation, fetch/decoding and existing quality enforcement. Avoid duplicating the conversion pipeline. |
| New `tests/test_xlsx_values.py`, `test_xlsx_tables.py`, `test_xlsx_writer.py`, `test_xlsx.py`, `accuracy/test_xlsx_accuracy.py` | Conversion, structure/provenance, workbook round trip, API/failure behavior and frozen-fixture acceptance. |
| Modify `pyproject.toml`, `.github/workflows/ci.yml`, `README.md`, `docs/quickstart.md`, `mkdocs.yml`; new `docs/usage/xlsx-export.md` | Optional dependency, meaningful CI and usage/limits. |

Use these contracts consistently across tasks. New records can be frozen dataclasses; do not add XLSX fields to public `Page`/`Element` just to pass internal writer state.

```python
# xlsx_values.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

@dataclass(frozen=True)
class CellValue:
    value: str | Decimal | None
    number_format: str
    original: str
    review_reason: str | None = None

def convert_cell(text: str, *, role: Literal["text", "number", "percent"]) -> CellValue:
    """Convert only a complete token with a source-supported numeric role."""
```

`xlsx_tables.py` defines the following records. Coordinates are zero-based source `(row, column)` origins; tuples retain order and repeat occurrences rather than deduplicating text.

| Record | Required fields |
| --- | --- |
| `SourceCell` | `text: str`, `row: int`, `column: int`, `rowspan: int`, `colspan: int`, `links: tuple[tuple[str,str],...]`, `is_header: bool`, `is_numeric_fact: bool` |
| `TableSnapshot` | `ordinal: int`, `page: int`, `display_page: int|None`, `element_id: str|None`, `source_anchor: str|None`, `source_cells: tuple[SourceCell,...]`, `original_text: str`, `source_kind: Literal["html","positioned"]`, `context_before: tuple[str,...]`, `context_after: tuple[str,...]`, `issues: tuple[str,...]` |
| `PreparedTable` | `source: TableSnapshot`, `title: str`, `units: str`, `headers: tuple[str,...]`, `rows: tuple[tuple[CellValue,...],...]`, `cell_sources: tuple[tuple[tuple[tuple[int,int],...],...],...]`, `original_rows: tuple[tuple[str,...],...]`, `notes: tuple[str,...]`, `references: tuple[tuple[str,str],...]`, `issues: tuple[str,...]`, `status: Literal["exported","needs_review","source_text_only"]` |

`cell_sources[row][column]` lists every source-cell origin contributing to that body cell, including currency/parenthesis fragments. Keep header provenance separately in the source snapshot and do not infer it from the resulting strings. Expose internal `snapshot_html_table(node, *, ordinal, page, source_url) -> TableSnapshot`, `snapshot_positioned_table(nodes, *, ordinal, page, source_url) -> TableSnapshot`, and `prepare_table(snapshot: TableSnapshot) -> PreparedTable`. Resolve note targets using the parser DOM during capture so snapshots are self-contained. Export result/error types are defined in Task 5.

## Task 1: Capture source table structure without changing Markdown

**Files:** `xlsx_tables.py`, `parser.py`, `table_parser.py`, `absolute_table_parser.py`, `tests/test_xlsx_tables.py`.

**Consumes:** supplied HTML and existing parser table decisions. **Produces:** ordered `Parser.table_snapshots: list[TableSnapshot]` when a new keyword-only `capture_tables=True` is supplied; default false. The writer never tries to reconstruct source spans from Markdown.

- [ ] Add a failing test with grouped header colspans, accounting symbol columns, preceding prose and two identical table occurrences. Assert both source occurrences survive in order and the span/text origins are retained. Include a one-row layout table that stays prose.

```python
from sec2md.parser import Parser

def test_capture_preserves_spans_and_default_markdown():
    source = """<p>Amounts in millions</p><table>
    <tr><th></th><th colspan="2">Three Months Ended</th></tr>
    <tr><th>Item</th><th>Jul 26, 2026</th><th>Jul 27, 2025</th></tr>
    <tr><td>Revenue</td><td>96,221</td><td>46,743</td></tr>
    </table>"""
    baseline = Parser(source).markdown()
    parser = Parser(source, capture_tables=True)
    assert parser.markdown() == baseline
    assert len(parser.table_snapshots) == 1
    group = next(c for c in parser.table_snapshots[0].source_cells
                 if c.text == "Three Months Ended")
    assert group.colspan == 2
```

- [ ] Run `python -m pytest tests/test_xlsx_tables.py -q` and establish the expected missing-capture failure.
- [ ] Capture the raw visible cells **before** `TableParser._create_grid()` cleans/merges them. Preserve native cell IDs/links before HTML annotation. Add the opt-in capture at `_stream_pages()`'s table branch, where the actual `page_num` is known, and at the existing positioned-table branch. Use the existing selection logic; do not rescan every nested `<table>` as a new occurrence.
- [ ] Preserve direct row/cell ownership for nested tables. Detect overlapping/out-of-range spans before flattening. Retain the original text and a structural issue rather than quietly clipping cells. Keep only expected structural failures recoverable; do not broadly catch `Exception` around ordinary parsing.
- [ ] After pages/elements are built, map snapshots to elements using source node identity in `block_nodes_map`; an element can include preceding prose. Populate detected printed pages independently of parser page numbers. Reset captures on repeat `get_pages()` calls to avoid duplicate inventory.
- [ ] Add positioned-table coverage using existing position fixtures. If source geometry cannot yield an unambiguous grid, retain a `source_text_only` candidate with all source text; do not manufacture numeric columns. Add an expected malformed-table case followed by a valid table and assert the second still appears in export capture.
- [ ] Run the new tests plus `tests/test_parser.py`, `tests/test_table_parser.py`, `tests/test_absolute_table_parser.py` and `tests/test_quality.py`. Confirm default Markdown and element IDs remain unchanged. Commit only this capture increment after checks pass.

## Task 2: Implement conservative numerical conversion

**Files:** `xlsx_values.py`, `tests/test_xlsx_values.py`. **Consumes:** text and a role established from source structure. **Produces:** `CellValue`; no dependence on HTML or Excel libraries.

- [ ] Write focused expected-value tests, including these cases:

```python
from decimal import Decimal
import pytest
from sec2md.xlsx_values import convert_cell

@pytest.mark.parametrize("text,role,expected", [
    ("$ 215,938", "number", Decimal("215938")),
    ("( 259 )", "number", Decimal("-259")),
    ("12.3 %", "percent", Decimal("0.123")),
    ("0.00", "number", Decimal("0.00")),
    ("—", "number", "—"), ("", "number", None),
    ("00123", "text", "00123"),
    ("Jul 26, 2026", "text", "Jul 26, 2026"),
    ("1,23", "number", "1,23"),
    ("1234567890123456", "number", "1234567890123456"),
])
def test_source_meaning_survives(text, role, expected):
    result = convert_cell(text, role=role)
    assert result.value == expected
    assert result.original == text
```

- [ ] Run `python -m pytest tests/test_xlsx_values.py -q` before implementation.
- [ ] Implement full-token US grouping/decimal validation, balanced accounting parentheses and Unicode minus. Use Decimal, preserve precision and generate standard Excel number formats. Explicit percent signs or a proven percent role divide by 100 exactly once. Do not multiply displayed millions/billions into base units.
- [ ] Keep dates, labels, IDs, unsupported currency formats, ranges, inequalities, ambiguous footnotes, malformed grouping, conflicting signs, negative zero and numbers exceeding 15 significant digits or Excel range as text. Preserve the original string; give ambiguous numeric candidates a review reason. Valid dashes/blanks and ordinary text have no error warning. Never strip a marker just because it resembles a footnote.
- [ ] Add assertions for percent format, zero precision, negative zero, `=1+1` as literal text, `(1)` in a text-role cell, unbalanced parentheses and explicit percent signs in a number-role column. Do not alter `quality.normalize_numeric_token()`, whose comparison behavior differs.
- [ ] Run the focused suite; commit the conversion increment after it passes.

## Task 3: Prepare faithful copy grids, headers and local context

**Files:** `xlsx_tables.py`, `tests/test_xlsx_tables.py`; targeted source mapping support in `table_parser.py` as needed. **Consumes:** snapshots and `convert_cell`. **Produces:** `PreparedTable`.

- [ ] Add a test proving that source header spans yield complete comparative duration labels, rather than arbitrary forward-fill:

```python
from sec2md.parser import Parser
from sec2md.xlsx_tables import prepare_table

def test_comparative_column_keeps_its_duration():
    source = """<table>
    <tr><th></th><th colspan="2">Three Months Ended</th></tr>
    <tr><th>Item</th><th>Jul 26, 2026</th><th>Jul 27, 2025</th></tr>
    <tr><td>Revenue</td><td>96,221</td><td>46,743</td></tr>
    </table>"""
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    table = prepare_table(parser.table_snapshots[0])
    assert table.headers[1:] == (
        "Three Months Ended — Jul 26, 2026",
        "Three Months Ended — Jul 27, 2025",
    )
```

- [ ] Run the new test and establish the preparation failure before adding the implementation.
- [ ] Build a source-coordinate grid and retain header-group membership while applying the existing safe structural-column rules. Do not call `to_matrix()` and assume it is raw. Every merged body cell carries all contributing source coordinates. Do not remove a first data row when header evidence is absent; use explicitly generated positional headers where necessary.
- [ ] Establish numeric roles from unambiguous value-column/row headings, displayed units, source numeric facts and consistent financial row structure. Numeric-looking labels/IDs remain text. Preserve column/row unit exceptions; source iXBRL may confirm a role but must not replace displayed magnitude/sign with underlying scale/sign. If role or column alignment is unresolved, keep text and explain the uncertainty. Do not use blanket conversion across all table cells.
- [ ] Preserve every row label, grouping row, repeated disclosure, meaningful blank and source footnote marker. Never join separate page fragments. Prepare an original-text area from source display strings with original header levels and traceable symbol/span relationships; it must remain understandable alongside the compact sample layout. If compacting it would lose meaning, retain the wider source structure and label it, rather than copy cleaned numbers back into the original view.
- [ ] Extract only explicit captions/headings, unit text, local bounded context and linked note targets. Stop local context at the next heading/table; label uncertain nearby prose as context. Preserve multi-link destinations in a visible reference list. Ambiguous/missing note targets get a review note. Keep broad “See accompanying Notes” references without embedding all financial-statement notes.
- [ ] Test mixed scale, percentage-only tables, blank headers, subtotal/group rows, matched/unmatched footnotes, external links without fetching and missing printed page. Test a structurally unreliable grid as `source_text_only` while preserving original text. Run the capture/preparation and value suites, then commit this preparation increment.

## Task 4: Write the approved workbook layout with freely scrolling rows

**Files:** `xlsx_writer.py`, `tests/test_xlsx_writer.py`, `pyproject.toml`. **Consumes:** `PreparedTable` sequence and document source metadata. **Produces:** workbook bytes and internal per-table worksheet/status mapping.

Define `render_workbook(tables: Sequence[PreparedTable], *, source_url: str|None, source_hash: str, hash_kind: str) -> tuple[bytes, tuple[tuple[int,str,str],...]]`. The mapping contains `(ordinal, worksheet_name, status)`. New metadata is derived from explicitly available filing text or left unknown; no ticker/fiscal year is guessed from filenames.

- [ ] Add the optional `xlsx` extra and install `.[dev,xlsx]` only in the implementation environment. Add a failing save/reopen test built from a prepared grouped-header table. Assert Contents + one table sheet, typed numbers, text originals, valid hyperlinks and **no frozen rows**:

```python
from io import BytesIO
from openpyxl import load_workbook

def assert_navigation_and_values(payload: bytes):
    workbook = load_workbook(BytesIO(payload), data_only=False)
    assert workbook.worksheets[0].title == "Contents"
    assert workbook.worksheets[0].freeze_panes is None
    for sheet in workbook.worksheets[1:]:
        assert sheet.freeze_panes == "B1"
        assert not any(cell.data_type == "f" for row in sheet for cell in row)
```

Use the Task 3 three-month table inside the actual test and assert the saved `96221` numeric cell, both complete dates/durations and original `96,221` text. Test assertions must locate the table via its returned sheet mapping, not an unrelated hardcoded sheet position.

- [ ] Run `python -m pytest tests/test_xlsx_writer.py -q` to establish the missing writer failure.
- [ ] Implement source-order sheet naming with ordinal, parser page and sanitized title, length at most 31, case-insensitive uniqueness, reserved-name handling, and full title retained inside the sheet. Contents links to both the copy and original areas and lists source pages, status and review counts.
- [ ] Implement the accepted sample areas and readable sizing. All rows scroll vertically. Use `B1` only for horizontal label retention. Keep copy headers/data unmerged, use wrapped headers and long labels, explicit number formats, restrained fills, clear unit labels and copy-range instructions. Do not add filters, calculation columns or charts. Avoid excessive empty metadata rows when a field is unavailable.
- [ ] Write original strings with explicit text cell types, including strings starting `=`, `+`, `-`, `@`; setting number format alone is insufficient. Use ordinary hyperlink objects, not `HYPERLINK()` formulas. Link to real source anchors only; generated sec2md IDs are not SEC fragments. Source URL plus printed/parser pages and element ID is the fallback.
- [ ] Write visible notes/review reasons and originals on each table sheet. For `source_text_only`, prominently label that the copy grid is unavailable and show original text/source references. Do not hide failures on Contents alone. Chunk text above Excel's 32,767-character cell limit without loss and explain chunks; if table dimensions exceed XLSX limits, retain a text fallback or explicit unavailable-in-full warning. Do not silently truncate.
- [ ] Reopen files and test types, values, text, units, row/column order, links, names, formula absence, long cells, no-table Contents-only output and every freeze setting. Render representative top, long-label and original sections. Commit the writer increment after the tests and visual checks pass.

## Task 5: Add the public API, quality semantics and safe publication

**Files:** `xlsx.py`, `__init__.py`, narrow `core.py` changes if needed, `xlsx_writer.py`, `tests/test_xlsx.py`, `tests/test_core.py`.

**Consumes:** existing `_resolve_source`, `_link_resolution_url`, `Parser`, quality diagnostics, `prepare_table`, `render_workbook`. **Produces:** public `export_xlsx` and the result/errors below.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class XlsxTableResult:
    ordinal: int
    sheet_name: str
    status: Literal["exported", "needs_review", "source_text_only"]
    issues: tuple[str, ...]

@dataclass(frozen=True)
class XlsxExportResult:
    path: Path
    status: Literal["complete", "needs_review", "no_tables"]
    tables: tuple[XlsxTableResult, ...]
    diagnostics: tuple[str, ...]

class XlsxDependencyError(ImportError):
    pass

class XlsxQualityError(ValueError):
    """Carries .issues: tuple[str, ...] for strict table-quality rejection."""

def export_xlsx(source: str | bytes, destination: str | Path, *,
                base_url: str | None = None,
                user_agent: str | None = None,
                quality_policy: Literal["strict", "warn", "off"] = "warn",
                overwrite: bool = False) -> XlsxExportResult:
    """Export one supplied HTML document; local files are read as bytes by caller."""
```

- [ ] Add failing API tests for offline bytes, base URL resolution without fetch, missing dependency before fetch/write, strict rejection, two-table partial recovery and no-overwrite preservation. Reuse `tests/test_core.py`'s monkeypatch pattern for `sec2md.core.fetch`.
- [ ] Keep `import sec2md` functional without openpyxl. Load it inside export before parsing; raise `XlsxDependencyError` with installation guidance. Export result types must be importable without the extra. Avoid circular imports: `xlsx.py` may reuse core helpers, but core must not import `xlsx.py` at module scope.
- [ ] Parse once with capture enabled and images disabled. Raw text/bytes cause zero network calls; URL input uses existing single-document fetching. Validate base URL before fetching, preserve existing decoding rules and never download notes, exhibits or images. SHA-256 retained bytes exactly; label supplied-text or normalized-HTML hashes honestly for other inputs rather than claiming original-byte identity.
- [ ] Keep known table failures local, represent each occurrence, and derive a compact result count/status. `strict` propagates existing `ParseQualityError` and rejects new table reliability issues via `XlsxQualityError` before publishing. `warn` returns reviewable output and diagnostics. `off` still retains export issues. Ordinary blanks/dashes are not failures. Zero tables returns `no_tables` plus a diagnostic Contents workbook.
- [ ] Stage XLSX in the destination directory, validate/reopen it, then publish. On `overwrite=False`, publish the validated sibling temporary file with `os.link(temp_path, destination)`, then unlink the temporary name. Hard-link creation fails if the destination already exists, so a concurrent new file is never replaced. If the filesystem cannot support this publication primitive, return an explicit publication error; do not fall back to an overwrite or partially copied final file. On explicit overwrite, use `os.replace` from the same directory. Clean only temporary files created by this invocation; preserve an old destination on parse/render/reopen failure. A locked Windows destination raises a useful error and leaves the old workbook intact. Do not claim cross-platform atomic no-clobber semantics unless the chosen primitive supplies them; validate the actual strategy on Windows/Linux.
- [ ] Test invalid quality policy, unusable paths, missing parent, existing file, simulated concurrent destination, locked/write failure, unexpected exception propagation, and absence of temporary remnants. Use a real saved workbook for round-trip checks, not mocked success. Run the API/writer/value/table tests and core regression tests, then commit the public API increment.

## Task 6: Validate full NVIDIA exports and document the supported feature

**Files:** `tests/accuracy/test_xlsx_accuracy.py`, new `tests/accuracy/xlsx_expected.json`, `.github/workflows/ci.yml`, `README.md`, `docs/quickstart.md`, `docs/usage/xlsx-export.md`, `mkdocs.yml`. No changes to immutable HTML or fixture manifest.

**Consumes:** completed public API and existing `tests.accuracy.fixtures.load_fixture`. **Produces:** source-grounded acceptance tests, two full workbooks, row-level proof and usage documentation.

- [ ] Create independently reviewed expected rows/header/unit contracts from the retained source and existing comparison proof; do not generate expected values by calling the exporter. Store the small expectation file in `tests/accuracy/xlsx_expected.json` so CI never depends on another checkout, the prototype directory or Claude's temporary files.
- [ ] Add a failing acceptance check if any required behavior is still missing:

```python
import pytest
from openpyxl import load_workbook
from sec2md import export_xlsx
from tests.accuracy.fixtures import load_fixture

@pytest.mark.parametrize("fixture_id,count", [
    ("nvda-2026-10k", 61),
    ("nvda-2026-q2-10q", 48),
])
def test_inventory_and_scroll_behavior(fixture_id, count, tmp_path):
    contract, source = load_fixture(fixture_id)
    output = tmp_path / f"{fixture_id}.xlsx"
    result = export_xlsx(source, output, base_url=contract.sec_url)
    workbook = load_workbook(output)
    assert len(result.tables) == count
    assert len(workbook.worksheets) == count + 1
    assert workbook.worksheets[0].freeze_panes is None
    assert all(s.freeze_panes == "B1" for s in workbook.worksheets[1:])
```

The 61/48 counts are the baseline inventory, not a license to omit or fabricate tables. If the source-backed detection reconciles differently, investigate and document each source occurrence before changing the assertion. A placeholder worksheet counts for inventory but does not pass primary-statement accuracy.

- [ ] Require all six financial statements to be copy-ready and verify 162 numeric source rows / 389 explicit displayed numbers with labels, signs, period positions and units. Recheck the accepted sample's 477 numeric cells plus ten dash positions across the ten selected tables. Preserve current/previous quarter versus year-to-date headers exactly. Add separate original-string, blank, source-footnote, reference and display-page assertions.
- [ ] Reconcile every recognized table occurrence to a sheet/status. Check beyond statements: inventories and percent-of-revenue tables, exhibit rows, trading-plan rows, mixed labels/IDs, matched and unresolved footnotes, and a positioned-table fixture. Tables outside reliable conversion still need intact text and explicit status. Raw fixture hashes are checked by `load_fixture`.
- [ ] Update CI test jobs to install `.[dev,xlsx]`; retain a clean minimal-install smoke that proves Markdown import/conversion does not need openpyxl. Existing CI's wheel assertion incorrectly expects `0.1.22+rcq.1` although current package metadata is `.rcq.2`. Replace the stale literal with a comparison between built wheel metadata and source `__version__`; verify declared Python range, repository URL and optional-extra metadata as well. Do not bump the version merely to appease that stale assertion.
- [ ] Document the exact API, optional install, all-table scope, static values, unit/percent handling, preserved uncertainty, no frozen rows, fallback/status behavior, overwrite behavior and known original-layout limits. Include this minimal example:

```python
from pathlib import Path
from sec2md import export_xlsx

result = export_xlsx(
    Path("nvda-20260726.htm").read_bytes(),
    Path("NVDA_10-Q_2026-07-26_tables.xlsx"),
    base_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/nvda-20260726.htm",
)
print(result.path, result.status)
```

- [ ] Run focused tests once after final edits, then the required full offline gates from the sec2md worktree:

```powershell
python -m pytest -q
python -m ruff check src tests
python -m build
```

Use the supported project environment; do not mutate the global runtime. Run the CI matrix on Python 3.10/3.12 Linux and 3.12 Windows where available, and distinguish local results from CI results. Inspect the built metadata, do the minimal install smoke, and inspect diff/status for protected or unrelated changes.

- [ ] Generate the two full workbooks and a new validation report under the implementation worktree's `outputs/xlsx-acceptance/`. Reopen them and render representative sheet tops, lower long-label sections, notes and original-text views. Check the XML contains no frozen-row split; manually scroll in the chosen workbook application when available. Keep automated structure checks distinct from native-application acceptance.
- [ ] Report local unit/regression checks, full-fixture checks, visual checks, CI and native-app status separately. Google Sheets import and clipboard remain separate acceptance checks; do not create online files automatically. If that phase is requested, use disposable Sheets and record the user's actual application/locale/paste mode.
- [ ] Commit the validation/docs increment after gates pass. Present the diff, output files, row-level proof and remaining limitations for review. Do not merge, deploy, update RCQ pins, create a skill or start historical processing as an implied follow-on.

## Plan self-review and stopping point

Spec coverage: selection/order/naming → Tasks 1/4/6; spans/labels/headers/notes/provenance → Tasks 1/3/6; numeric safeguards → Task 2; original text and approved layout → Tasks 3/4; no frozen rows → Tasks 4/6; dependency/API/failures/publication → Tasks 4/5; offline/full-fixture/Sheets separation → Task 6. Interface names and coordinate conventions above apply throughout.

This planning turn changes only this plan and the design's approval/navigation notes. The accepted sample workbooks are intentionally retained unchanged. No implementation, environment installation, worktree creation, commit or test run is represented as completed by these checkboxes.
