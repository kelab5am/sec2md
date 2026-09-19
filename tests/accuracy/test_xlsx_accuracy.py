"""Offline source-grounded XLSX acceptance; expectations never come from the exporter.

The JSON combines two independently reviewed retained-source audits. Matching uses
complete source cell coordinates/spans/text, then body provenance, never sheet names
or a presumed first data row. Whitespace alone is normalized for source comparisons.
"""
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import re
from urllib.parse import urljoin
from xml.etree import ElementTree
from zipfile import ZipFile

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries
import pytest

from sec2md import export_xlsx
from sec2md.parser import Parser
from sec2md.xlsx_tables import prepare_table
from tests.accuracy.fixtures import load_fixture

EXPECTED = json.loads(Path(__file__).with_name('xlsx_expected.json').read_text(encoding='utf-8'))
FILINGS = tuple(EXPECTED['filings'])
# Audited source occurrences: a sizing row plus one visible row, emitted as prose.
PROSE_TABLES = {'nvda-2026-10k': (0, 1, 4), 'nvda-2026-q2-10q': (0, 1, 2, 5)}


def compact(value):
    return ''.join(str(value or '').split())


def hidden(node):
    return any(parent.has_attr("hidden") or re.search(
        r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", parent.get("style", ""), re.I)
        for parent in (node, *node.parents) if getattr(parent, "attrs", None) is not None)


def source_cells(node):
    """Independent DOM coordinates and text for the retained, visible HTML tables."""
    result, occupied = [], set()
    rows = [tr for tr in node.find_all('tr') if tr.find_parent('table') is node and not hidden(tr)]
    for row, tr in enumerate(rows):
        column = 0
        for cell in tr.find_all(['td', 'th'], recursive=False):
            if hidden(cell):
                continue
            while (row, column) in occupied:
                column += 1
            height, width = int(cell.get('rowspan', 1)), int(cell.get('colspan', 1))
            text = ' '.join(cell.get_text(' ', strip=True).split())
            result.append((row, column, height, width, text))
            occupied.update((r, c) for r in range(row, row + height)
                            for c in range(column, column + width))
            column += width
    return result


def signature(cells):
    return tuple((*cell[:4], compact(cell[4])) for cell in cells)


def copy_bounds(sheet):
    instructions = [cell.value for row in sheet for cell in row
                    if isinstance(cell.value, str) and re.fullmatch(
                        r'Copy [A-Z]+\d+:[A-Z]+\d+, including units and complete headers\.', cell.value)]
    assert len(instructions) == 1
    return range_boundaries(instructions[0].split()[1].rstrip(','))


def visible(sheet):
    # Chunked long text is reconstructed without invented separators.
    return ''.join(str(cell.value or '') for row in sheet for cell in row)


@dataclass
class ExportAudit:
    fixture: str
    contract: object
    result: object
    workbook: object
    raw: list
    tables: dict
    reconciliation: list


def audit_export(fixture_id, directory):
    contract, source = load_fixture(fixture_id)
    assert contract.sha256 == EXPECTED['filings'][fixture_id]['sha256']
    # Retained ASCII XML declarations are intentionally fed to the HTML parser.
    # Account for the two known warnings at this exact export boundary.
    with pytest.warns(XMLParsedAsHTMLWarning) as warnings:
        result = export_xlsx(source, directory / f'{fixture_id}.xlsx', base_url=contract.sec_url, overwrite=True)
    assert len(warnings) == 2
    assert {Path(w.filename).name for w in warnings} == {'parser.py', 'quality.py'}
    workbook = load_workbook(result.path)
    html = re.sub(r'^\s*<\?xml[^>]*\?>', '', source.decode('ascii'))
    raw = BeautifulSoup(html, 'lxml').find_all('table')
    parser = Parser(html, source_url=contract.sec_url, capture_tables=True)
    parser.get_pages(include_images=False)
    snapshots = parser.table_snapshots
    assert len(raw) == EXPECTED['inventory'][fixture_id]['raw']
    assert len(snapshots) == len(result.tables) == EXPECTED['inventory'][fixture_id]['exported']
    assert len(workbook.worksheets) == len(result.tables) + 1
    raw_signatures = [signature(source_cells(node)) for node in raw]
    tables, reconciliation, selected = {}, [], []
    for snapshot, exported in zip(snapshots, result.tables):
        captured = signature([(c.row, c.column, c.rowspan, c.colspan, c.text) for c in snapshot.source_cells])
        matches = [i for i, candidate in enumerate(raw_signatures) if candidate == captured]
        assert len(matches) == 1, (fixture_id, snapshot.ordinal, matches)
        index, = matches
        assert index not in tables
        assert exported.ordinal == snapshot.ordinal == len(selected) + 1
        sheet = workbook[exported.sheet_name]
        assert sheet is workbook.worksheets[snapshot.ordinal]
        prepared = prepare_table(snapshot)
        tables[index] = (prepared, exported, sheet)
        selected.append(index)
        reconciliation.append({'raw_table': index, 'ordinal': exported.ordinal,
                               'sheet': sheet.title, 'status': exported.status,
                               'issues': list(exported.issues)})
    assert selected == sorted(selected)
    omitted = tuple(i for i in range(len(raw)) if i not in tables)
    assert omitted == PROSE_TABLES[fixture_id]
    for index in omitted:
        cells = source_cells(raw[index])
        visible_rows = {r for r, _, _, _, text in cells if text.strip()}
        assert len(visible_rows) == (0 if fixture_id == "nvda-2026-q2-10q" and index == 0 else 1)
        reconciliation.append({'raw_table': index, 'status': 'prose',
                               'reason': ('Empty layout table.' if not visible_rows else
                                          'Sizing row and one visible row; parser emits prose, not a table.')})
    return ExportAudit(fixture_id, contract, result, workbook, raw, tables,
                       sorted(reconciliation, key=lambda item: item['raw_table']))


@pytest.fixture(scope='module', params=FILINGS)
def audit(request, tmp_path_factory):
    result = audit_export(request.param, tmp_path_factory.mktemp('xlsx-acceptance'))
    yield result
    result.workbook.close()


def test_all_occurrences_navigation_originals_and_no_frozen_rows(audit):
    workbook = audit.workbook
    contents = workbook.worksheets[0]
    assert contents.freeze_panes is None
    assert audit.contract.sha256 in visible(contents)
    assert 'original bytes' in visible(contents)
    for _, exported, sheet in audit.tables.values():
        assert sheet.freeze_panes == 'B1'
        assert f'Status: {exported.status}' in visible(sheet)
        assert exported.status in {'exported', 'needs_review', 'source_text_only'}
        links = [cell.hyperlink for row in contents for cell in row if cell.hyperlink]
        assert any(link.location and sheet.title in link.location for link in links)
        assert any(cell.hyperlink and cell.hyperlink.target == audit.contract.sec_url
                   for row in sheet for cell in row)
        assert not any(cell.data_type == 'f' for row in sheet for cell in row)
        assert not sheet.auto_filter.ref
    with ZipFile(audit.result.path) as archive:
        for name in archive.namelist():
            if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
                xml = ElementTree.fromstring(archive.read(name))
                for pane in xml.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}pane'):
                    assert float(pane.get('ySplit', 0)) == 0


def body_row(prepared, source_row):
    matches = [i for i, row in enumerate(prepared.cell_sources)
               if any(r == source_row and c == 0 for r, c in row[0])]
    assert len(matches) == 1, (prepared.source.ordinal, source_row, matches)
    return matches[0]


def copy_cell(prepared, sheet, source_row, period):
    row = body_row(prepared, source_row)
    columns = [i for i, header in enumerate(prepared.headers) if header == period]
    assert len(columns) == 1, period
    column, = columns
    left, top, _, _ = copy_bounds(sheet)
    return sheet.cell(top + 2 + row, left + column)


def original_grid(sheet):
    matches = [cell.row for row in sheet for cell in row
               if cell.value == 'Original cell grid — source spans recorded below']
    assert len(matches) == 1
    return matches[0] + 1


def check_financial_table(audit, expectation):
    prepared, exported, sheet = audit.tables[expectation['sourceTable']]
    assert exported.status == prepared.status == 'exported', exported.issues
    assert prepared.headers[1:] == tuple(expectation['headers'][1:])
    assert prepared.source.display_page == expectation['printedPage']
    assert f'Printed page {expectation["printedPage"]}' in visible(sheet)
    left, top, right, bottom = copy_bounds(sheet)
    assert right - left + 1 == len(expectation['headers'])
    assert [sheet.cell(top + 1, c).value for c in range(left + 1, right + 1)] == expectation['headers'][1:]
    for merged in sheet.merged_cells.ranges:
        assert merged.max_row < top or merged.min_row > bottom
    if expectation['kind'] == 'percent':
        assert 'expressed as a percentage of revenue' in sheet.cell(top, left).value
    else:
        assert sheet.cell(top, left).value == expectation['unit']
    original_start = original_grid(sheet)
    # Every source cell is retained visibly, including all header levels and symbols.
    for row, column, _, _, text in source_cells(audit.raw[expectation['sourceTable']]):
        assert compact(sheet.cell(original_start + row, column + 1).value) == compact(text)
    proof = []
    for expected in expectation['checked_cells']:
        row = body_row(prepared, expected['source_row'])
        assert compact(sheet.cell(top + 2 + row, left).value) == compact(expected['label'])
        saved = copy_cell(prepared, sheet, expected['source_row'], expected['period'])
        if expected['source_display'] == '—':
            assert saved.value == '—' and saved.data_type == 's'
        else:
            assert saved.data_type == 'n' and not isinstance(saved.value, bool)
            assert Decimal(str(saved.value)) == Decimal(expected['expected'])
            if expectation['kind'] == 'percent':
                assert '%' in saved.number_format
        col = prepared.headers.index(expected['period'])
        assert compact(prepared.rows[row][col].original) == compact(expected['source_display'])
        proof.append({'filing': audit.fixture, 'source_table': expectation['sourceTable'],
                      'source_row': expected['source_row'], 'label': expected['label'],
                      'period': expected['period'], 'source_display': expected['source_display'],
                      'expected': expected['expected'], 'sheet': sheet.title,
                      'cell': saved.coordinate, 'saved': saved.value, 'type': saved.data_type})
    for expected in expectation['statement_rows']:
        row = body_row(prepared, expected['source_row'])
        assert compact(sheet.cell(top + 2 + row, left).value) == compact(expected['label'])
        actual = [Decimal(str(sheet.cell(top + 2 + row, c).value)) for c in range(left + 1, right + 1)
                  if sheet.cell(top + 2 + row, c).data_type == 'n'
                  and sheet.cell(top + 2 + row, c).value is not None]
        assert actual == [Decimal(value) for value in expected['values']]
    if expectation['kind'] in {'income', 'balance', 'cashflow'}:
        assert 'See accompanying Notes' in visible(sheet)
    return proof


def test_all_primary_rows_and_sample_cells_with_periods_units_and_originals(audit):
    for expectation in EXPECTED['filings'][audit.fixture]['tables']:
        check_financial_table(audit, expectation)


def check_extra_positions(audit):
    proof = []
    for expected in EXPECTED['source_supplement']['additional_statement_positions']:
        if expected['filing'] != audit.fixture:
            continue
        prepared, _, sheet = audit.tables[expected['source_table']]
        cell = copy_cell(prepared, sheet, expected['source_row'], expected['period'])
        assert cell.value == expected['copy_value']
        assert cell.value != 0
        if expected['kind'] == 'dash':
            assert cell.data_type == 's'
        row = body_row(prepared, expected['source_row'])
        assert compact(prepared.rows[row][0].original) == compact(expected['label'])
        proof.append({**expected, 'sheet': sheet.title, 'cell': cell.coordinate,
                      'saved': cell.value, 'type': cell.data_type})
    return proof


def test_additional_statement_dashes_and_blanks_never_become_zero(audit):
    check_extra_positions(audit)


def test_nonfinancial_rows_ids_links_and_continuation_first_row(audit):
    for expected in EXPECTED['source_supplement']['nonfinancial_tables']:
        if expected['filing'] != audit.fixture:
            continue
        prepared, exported, sheet = audit.tables[expected['source_table']]
        assert prepared.source.display_page == expected['printed_page']
        assert exported.status != 'source_text_only'
        assert prepared.issues  # mixed text/identifiers are explicitly reviewable
        start = original_grid(sheet)
        left, top, _, _ = copy_bounds(sheet)
        for row in expected['rows']:
            ri = body_row(prepared, row['source_row'])
            for expected_cell in row['cells']:
                raw_origin = (row['source_row'], expected_cell['source_column'])
                # Supplement coordinates count hidden DOM gutters; capture coordinates
                # describe visible cells. Reconcile those independently from source.
                tr = audit.raw[expected['source_table']].find_all('tr')[raw_origin[0]]
                raw_column = visible_column = 0
                for td in tr.find_all(['td', 'th'], recursive=False):
                    if raw_column == raw_origin[1]:
                        break
                    width = int(td.get('colspan', 1))
                    raw_column += width
                    if not hidden(td):
                        visible_column += width
                assert raw_column == raw_origin[1]
                if hidden(td):
                    assert not expected_cell['text']
                    continue
                origin = (raw_origin[0], visible_column)
                source = [c for c in prepared.source.source_cells if (c.row, c.column) == origin]
                assert len(source) == 1
                assert compact(source[0].text) == compact(expected_cell['text'])
                assert source[0].colspan == expected_cell['colspan']
                original = sheet.cell(start + origin[0], origin[1] + 1)
                assert compact(original.value) == compact(expected_cell['text'])
                if original.value is not None:
                    assert original.data_type == 's'
                columns = [i for i, origins in enumerate(prepared.cell_sources[ri]) if origin in origins]
                if not expected_cell['text'] and not columns:
                    continue  # Empty structural gutters need only the source grid.
                assert len(columns) == 1, (origin, expected_cell['text'])
                saved = sheet.cell(top + 2 + ri, left + columns[0])
                if expected_cell['text']:
                    # Independently audited unmarked share counts; dates/IDs/mixed markers remain text.
                    share_counts = {('nvda-2026-10k', 18, 3, 24): 500000,
                                    ('nvda-2026-q2-10q', 49, 2, 24): 6500}
                    key = (audit.fixture, expected['source_table'], *origin)
                    if key in share_counts:
                        assert saved.value == share_counts[key] and saved.data_type == 'n'
                    else:
                        assert compact(saved.value) == compact(expected_cell['text'])
                        assert saved.data_type == 's'
                for link in expected_cell['links']:
                    target = urljoin(audit.contract.sec_url, link['href'])
                    assert any(c.hyperlink and c.hyperlink.target == target for r in sheet for c in r)
    if audit.fixture == 'nvda-2026-10k':
        prepared, _, sheet = audit.tables[61]
        ri = body_row(prepared, 1)
        assert prepared.rows[ri][0].value == '10.10+'
        assert any(c.value == '4.10' and c.data_type == 's' for row in audit.tables[60][2] for c in row)


def test_source_notes_and_marker_context_retained(audit):
    for expected in EXPECTED['source_supplement']['source_notes']:
        if expected['filing'] != audit.fixture:
            continue
        prepared, _, sheet = audit.tables[expected['source_table']]
        text = compact(visible(sheet))
        assert compact(expected['text']) in text
        if 'source_row' in expected:
            ri = body_row(prepared, expected['source_row'])
            assert expected['marker'] in ''.join(value.original for value in prepared.rows[ri])


def test_independent_contract_totals():
    tables = [t for f in EXPECTED['filings'].values() for t in f['tables']]
    rows = [r for t in tables for r in t['statement_rows']]
    cells = [c for t in tables for c in t['checked_cells']]
    assert len(rows) == 162 and sum(len(r['values']) for r in rows) == 389
    assert len(cells) == 487
    assert sum(c['source_display'] == '—' for c in cells) == 10
    assert len({(f, t['sourceTable'], c['source_row'], c['period'])
                for f, e in EXPECTED['filings'].items() for t in e['tables'] for c in t['checked_cells']}) == 487
    extra = EXPECTED['source_supplement']['additional_statement_positions']
    assert len(extra) == 8 and sum(c['kind'] == 'blank' for c in extra) == 2


def test_positioned_source_and_genuinely_absent_note_have_honest_status(tmp_path):
    source = '<div>' + ''.join(
        f'<div style="position:absolute;left:{x}px;top:{y}px">{value}</div>'
        for y in range(0, 120, 20)
        for x, value in [(10, f'Label {y}'), (200, str(1000 + y)), (350, f'${2000 + y}')]
    ) + '</div><h2>Notes</h2><table><tr><th>Item</th><th>Amount</th></tr>' \
        '<tr><td>Cost <a href="#absent">(1)</a></td><td>5</td></tr></table>'
    result = export_xlsx(source, tmp_path / 'positioned.xlsx')
    assert len(result.tables) == 2
    assert result.status == 'needs_review'
    assert any('absent' in issue for issue in result.tables[1].issues)
    workbook = load_workbook(result.path)
    positioned = workbook[result.tables[0].sheet_name]
    assert 'Label 0' in visible(positioned) and 'Label 100' in visible(positioned)
    left, top, _, _ = copy_bounds(positioned)
    assert positioned.cell(top + 2, left).value == 'Label 0'
    assert positioned.cell(top + 2, left + 2).value == 2000
    notes = workbook[result.tables[1].sheet_name]
    assert 'Unresolved or ambiguous note target: #absent' in visible(notes)
    assert 'Linked note (#absent)' not in visible(notes)
    workbook.close()
