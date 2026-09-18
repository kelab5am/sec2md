"""Source capture must preserve occurrences and provenance before Markdown cleanup."""
import pytest
from bs4 import BeautifulSoup

from sec2md.parser import Parser


TABLE = '''<table id="native"><tr><th></th><th colspan="4">Three Months Ended</th></tr>
<tr><th>Item</th><th colspan="2">2026</th><th colspan="2">2025</th></tr>
<tr><td id="revenue">Revenue<a href="#note">(1)</a></td><td>$</td>
<td><ix:nonfraction>96,221</ix:nonfraction></td><td>$</td><td>46,743</td></tr></table>'''


def test_capture_preserves_spans_occurrences_and_default_output():
    source = '<p>Amounts in millions</p>' + TABLE * 2 + '<table><tr><td>Layout prose</td></tr></table><p id="note">(1) Includes sales.</p>'
    baseline = Parser(source)
    expected = baseline.get_pages()
    parser = Parser(source, capture_tables=True)
    assert parser.get_pages() == expected
    assert baseline.table_snapshots == []
    first, second = parser.table_snapshots
    assert [first.ordinal, second.ordinal] == [1, 2]
    assert first.source_anchor == 'native'
    assert first.context_before == ('Amounts in millions',)
    group = next(c for c in first.source_cells if c.text == 'Three Months Ended')
    assert (group.row, group.column, group.rowspan, group.colspan) == (0, 1, 1, 4)
    assert [(c.column, c.text) for c in first.source_cells if c.row == 2] == [(0, 'Revenue(1)'), (1, '$'), (2, '96,221'), (3, '$'), (4, '46,743')]
    assert first.source_cells[-3].is_numeric_fact
    assert first.source_cells[-5].source_anchor == 'revenue'
    assert first.source_cells[-5].links == (('(1)', '#note'),)
    assert first.resolved_notes == (('#note', '(1) Includes sales.'),)
    assert first.element_id in parser.block_nodes_map
    element = next(e for p in expected for e in p.elements if e.id == first.element_id)
    assert 'Amounts in millions' in element.content
    parser.get_pages()
    assert parser.table_snapshots == [first, second]


def test_capture_uses_parser_pages_and_printed_pages_independently():
    source = TABLE + '<div><div style="position:absolute;bottom:0;width:100%">Page 42</div></div><hr style="page-break-after:always">' + TABLE
    parser = Parser(source, capture_tables=True)
    parser.get_pages(include_elements=False)
    assert [(s.page, s.display_page, s.element_id) for s in parser.table_snapshots] == [(1, 42, None), (2, None, None)]


@pytest.mark.parametrize('span', ['rowspan="99"', 'colspan="0"', 'colspan="bad"'])
def test_malformed_table_is_retained_and_following_table_survives(span):
    source = f'<table><tr><td {span}>Unreliable 123</td><td>456</td></tr><tr><td>Tail</td><td>789</td></tr></table>' + TABLE
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    bad, good = parser.table_snapshots
    assert bad.issues
    assert 'Unreliable 123' in bad.original_text
    assert 'Tail' in bad.original_text
    assert not good.issues


def test_nested_rows_have_direct_ownership_without_extra_occurrences():
    source = '<table><tr><td>Outer<table><tr><td>Inner A</td></tr><tr><td>Inner B</td></tr></table></td><td>12</td></tr><tr><td>Outer B</td><td>34</td></tr></table>'
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    assert len(parser.table_snapshots) == 1
    snapshot = parser.table_snapshots[0]
    assert len(snapshot.source_cells) == 4
    assert 'Inner A' in snapshot.original_text
    assert snapshot.issues  # nested content cannot be mistaken for a flat grid


def positioned_source(extra=''):
    # Same regular geometry as TestIsTableLike.test_grid_with_numbers_is_table.
    return '<div>' + ''.join(
        f'<div style="position:absolute;left:{x}px;top:{y}px">{value}</div>'
        for y in range(0, 120, 20)
        for x, value in [(10, f'Label {y}'), (200, str(1000+y)), (350, f'${2000+y}')]
    ) + extra + '</div>'


def test_positioned_capture_uses_existing_selected_group():
    source = positioned_source()
    parser = Parser(source, capture_tables=True)
    assert parser.get_pages() == Parser(source).get_pages()
    snapshot, = parser.table_snapshots
    assert snapshot.source_kind == 'positioned'
    assert len(snapshot.source_cells) == 18
    assert (snapshot.source_cells[-1].row, snapshot.source_cells[-1].column) == (5, 2)
    assert not snapshot.issues
    assert snapshot.element_id


def test_ambiguous_positioned_geometry_retains_all_text():
    source = positioned_source('<div style="position:absolute;left:210px;top:20px">9999</div>')
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert snapshot.issues
    assert snapshot.source_cells == ()
    assert '9999' in snapshot.original_text and '1020' in snapshot.original_text


def test_span_overlap_is_reported_before_flattening():
    from sec2md.xlsx_tables import snapshot_html_table
    soup = BeautifulSoup('<table><tr><td>A</td><td rowspan="2">B</td></tr><tr><td colspan="2">C</td></tr></table>', 'lxml')
    snapshot = snapshot_html_table(soup.table, ordinal=1, page=1, source_url=None)
    assert any('overlap' in issue for issue in snapshot.issues)
    assert [c.text for c in snapshot.source_cells] == ['A', 'B', 'C']


def test_rowspan_displacement_beyond_flattened_width_is_reported():
    source = '<table><tr><td rowspan="2">A</td><td rowspan="2">B</td></tr><tr><td>C</td><td>D</td></tr></table>'
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert snapshot.issues
    assert [(c.text, c.column) for c in snapshot.source_cells] == [('A', 0), ('B', 1), ('C', 2), ('D', 3)]


def test_hidden_text_is_excluded_and_relative_references_are_self_contained():
    source = '<table><tr><th>Item</th><th>Value</th></tr><tr><td><a href="#missing">Note</a><span style="display:none">SECRET</span></td><td><span>1,</span><span>200</span><a href="detail.htm">detail</a></td></tr></table>'
    parser = Parser(source, capture_tables=True, source_url='https://example.com/filing/main.htm')
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert 'SECRET' not in snapshot.original_text
    assert snapshot.source_cells[-1].text == '1,200detail'
    assert snapshot.source_cells[-1].links == (('detail', 'https://example.com/filing/detail.htm'),)
    assert snapshot.unresolved_references == ('https://example.com/filing/main.htm#missing',)


def test_valid_rowspan_and_native_anchor_survive_annotation_on_table_itself():
    source = '<table id="original"><tr><th rowspan="2">Item</th><th>Year</th></tr><tr><td>2026</td></tr><tr><td>Revenue</td><td>100</td></tr></table>'
    parser = Parser(source, capture_tables=True)
    assert parser.get_pages() == Parser(source).get_pages()
    first, = parser.table_snapshots
    assert not first.issues
    assert first.source_cells[2].column == 1
    assert first.source_anchor == 'original'
    parser.get_pages()
    assert parser.table_snapshots == [first]


def test_inline_whitespace_is_preserved_without_splitting_numeric_tokens():
    source = '<table><tr><th>Item</th><th>Value</th></tr><tr><td><span>Net </span><b>income</b></td><td><span>1,</span><b>200</b></td></tr></table>'
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert [c.text for c in snapshot.source_cells[-2:]] == ['Net income', '1,200']
