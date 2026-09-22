from dataclasses import replace
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from openpyxl import load_workbook

from sec2md.xlsx_tables import prepare_table, snapshot_html_table
from sec2md.xlsx_values import CellValue
from sec2md.xlsx_writer import render_workbook


def sample():
    source = '''<h2>Income statement</h2><p>Amounts in millions</p><table id="native">
    <tr><th></th><th colspan="2">Three Months Ended</th></tr>
    <tr><th>Item</th><th>Jul 26, 2026</th><th>Jul 27, 2025</th></tr>
    <tr><td>Revenue</td><td>96,221</td><td>46,743</td></tr></table>'''
    soup = BeautifulSoup(source, 'lxml')
    return prepare_table(snapshot_html_table(soup.table, ordinal=1, page=3, source_url=None))


def render(tables, **kwargs):
    payload, records = render_workbook(tables, source_url='https://example.com/filing.htm',
                                      source_hash='abc123', hash_kind='utf8_text', **kwargs)
    return load_workbook(BytesIO(payload), data_only=False), records


def values(sheet):
    return [c.value for row in sheet for c in row if c.value is not None]


def test_grouped_headers_saved_values_navigation_and_no_frozen_rows():
    table = sample()
    wb, records = render([table])
    assert len(wb.worksheets) == 2
    record, = records
    sheet = wb[record.worksheet_name]
    assert record.ordinal == 1 and record.status == table.status
    assert wb.worksheets[0].title == 'Contents'
    assert wb.worksheets[0].freeze_panes is None
    assert sheet.freeze_panes is None
    assert 96221 in values(sheet)
    assert '96,221' in values(sheet)
    for heading in table.headers[1:]:
        assert heading in values(sheet)
    assert 'Amounts in millions' in values(sheet)
    assert any(c.hyperlink and c.hyperlink.target == 'https://example.com/filing.htm#native'
               for row in sheet for c in row)
    links = [c.hyperlink.location for row in wb['Contents'] for c in row if c.hyperlink]
    assert len(links) == 1
    assert all(record.worksheet_name in link for link in links)
    for ws in wb:
        assert not ws.auto_filter.ref
        assert not any(c.data_type == 'f' for row in ws for c in row)
    assert sheet.merged_cells.ranges  # Source reference preserves source spans.


@pytest.mark.parametrize('text', ['=1+1', '+SUM(A1)', '-1+2', '@SUM(A1)', '#N/A'])
def test_source_strings_are_explicit_text_everywhere(text):
    table = sample()
    table = replace(table, title=text, units=text, headers=(text,),
                    rows=((CellValue(text, '@', text),),), notes=(text,),
                    source=replace(table.source, original_text=text))
    wb, records = render([table])
    cells = [c for ws in wb for row in ws for c in row if c.value == text]
    assert len(cells) >= 5
    assert all(c.data_type == 's' for c in cells)


def test_names_order_fallback_and_native_anchor_only():
    table = sample()
    tables = [replace(table, title="'Contents[]:*?/\\" * 4,
                      source=replace(table.source, ordinal=n, source_anchor=None,
                                     element_id='sec2md-generated'),
                      status='source_text_only', issues=('Bad geometry',), rows=())
              for n in (2, 1, 1)]
    wb, records = render(tables)
    names = [r.worksheet_name for r in records]
    assert [r.ordinal for r in records] == [2, 1, 1]
    assert len(set(n.lower() for n in names)) == 3
    assert all(len(n) <= 31 and not any(c in n for c in '[]:*?/\\') for n in names)
    for name in names:
        sheet = wb[name]
        assert '96,221' in values(sheet)
        assert 'Bad geometry' not in values(sheet)
        assert 'Bad geometry' in records[names.index(name)].issues
        assert not any(c.hyperlink and 'sec2md-generated' in str(c.hyperlink.target)
                       for row in sheet for c in row)


def test_long_text_stays_in_its_cell_and_overlong_text_is_rejected():
    text = '=start' + 'abcdef ' * 100
    table = replace(sample(), rows=((CellValue(text, '@', text),),), headers=('Text',))
    wb, records = render([table])
    assert wb[records[0].worksheet_name]['A4'].value == text
    assert wb[records[0].worksheet_name]['A4'].data_type == 's'
    table = replace(table, rows=((CellValue('x' * 32768, '@', ''),),))
    with pytest.raises(ValueError, match='character limit'):
        render([table])


def test_empty_workbook_has_honest_hash_and_document_diagnostics():
    wb, records = render([], document_diagnostics=('Parse warning',))
    assert not records and wb.sheetnames == ['Contents']
    assert 'utf8_text' in values(wb['Contents'])
    assert 'abc123' in values(wb['Contents'])
    assert 'Parse warning' not in values(wb['Contents'])
    assert all(wb['Contents'].row_dimensions[r].hidden for r in range(1, 7))
    assert any('No tables' in str(v) for v in values(wb['Contents']))


def test_dimension_limit_rejects_instead_of_truncating(monkeypatch):
    import sec2md.xlsx_writer as writer
    monkeypatch.setattr(writer, 'MAX_COLUMNS', 2)
    with pytest.raises(ValueError, match='dimension limit'):
        render([sample()])


def test_original_grid_and_span_ledger_are_visible():
    table = sample()
    wb, records = render([table])
    sheet = wb[records[0].worksheet_name]
    assert 'Original table' in values(sheet)
    numeric_original = next(c for row in sheet for c in row if c.value == '96,221')
    assert numeric_original.column == 2
    assert numeric_original.data_type == 's'
    assert not any('rowspan' in str(v) for v in values(sheet))
    assert any(r.max_col - r.min_col == 1 for r in sheet.merged_cells.ranges)


def test_formats_blank_dash_zero_and_original_provenance():
    from decimal import Decimal
    table = replace(sample(), headers=('Label', 'Amount', 'Percent', 'Blank', 'Dash'),
                    rows=((CellValue('Example', '@', 'Example'),
                           CellValue(Decimal('0'), '#,##0', '0'),
                           CellValue(Decimal('.123'), '0.0%', '12.3%'),
                           CellValue(None, '@', ''), CellValue('—', '@', '—')),))
    wb, records = render([table])
    sheet = wb[records[0].worksheet_name]
    row = next(row for row in sheet if row[0].value == 'Example')
    assert [c.value for c in row[:5]] == ['Example', 0, .123, None, '—']
    assert row[2].number_format == '0.0%'
    assert not any('Body row' in str(v) for v in values(sheet))


def test_xml_incompatible_text_is_reversibly_escaped_and_reported():
    table = replace(sample(), title='Bad\x01 title')
    wb, records = render([table])
    assert records[0].status == 'needs_review'
    assert any('XML' in issue for issue in records[0].issues)
    assert any('\\u0001' in str(v) for v in values(wb[records[0].worksheet_name]))


def test_row_limit_rejects_instead_of_truncating(monkeypatch):
    import sec2md.xlsx_writer as writer
    monkeypatch.setattr(writer, 'MAX_ROWS', 40)
    table = replace(sample(), rows=sample().rows * 50)
    with pytest.raises(ValueError, match='dimension limit'):
        render([table])


def test_table_ranges_are_available_without_instruction_prose():
    wb, records = render([sample()])
    sheet = wb[records[0].worksheet_name]
    assert sheet['A1'].hyperlink.location == "'Contents'!A8"
    assert list(sheet.defined_names['CopyTable'].destinations)[0][1] == records[0].copy_range
    assert list(sheet.defined_names['OriginalTable'].destinations)[0][1] == records[0].original_range
    assert not any('whitespace' in str(v).lower() for v in values(sheet))


def test_writer_import_does_not_load_optional_dependency():
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-c',
                             'import sys; import sec2md.xlsx_writer; assert "openpyxl" not in sys.modules'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_supplied_title_and_printed_page_are_retained():
    table = replace(sample(), title='Explicit full filing title',
                    source=replace(sample().source, display_page=17))
    wb, records = render([table])
    sheet = wb[records[0].worksheet_name]
    assert sheet['A1'].value == table.title
    assert not any('Parser page' in str(v) for v in values(sheet))
    assert 17 in values(wb['Contents'])


def test_encoding_warning_preserves_source_text_only_status_in_report():
    table = replace(sample(), title='Invalid\x01 title', status='source_text_only',
                    rows=(), issues=('Unreliable source grid',))
    wb, records = render([table])
    record, = records
    assert record.status == 'source_text_only'
    assert record.copy_range is None
    assert any('XML' in issue for issue in record.issues)
    sheet = wb[record.worksheet_name]
    assert not any('Status:' in str(v) for v in values(sheet))
    assert '96,221' in values(sheet)
