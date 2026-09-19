"""Source capture must preserve occurrences and provenance before Markdown cleanup."""
import pytest
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

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


def test_nested_malformed_table_recovers_as_source_text_and_continues():
    # Small malformed span exercises the unsafe path without a large allocation.
    nested = '<table><tr><td>Outer<table><tr><td rowspan="5">Nested 123</td></tr><tr><td>Tail 456</td></tr></table></td></tr><tr><td>End</td></tr></table>'
    parser = Parser(nested + TABLE, capture_tables=True)
    pages = parser.get_pages()
    bad, good = parser.table_snapshots
    assert bad.issues and 'Nested 123' in bad.original_text and 'Tail 456' in bad.original_text
    assert pages[0].content.startswith(bad.original_text + '\n')
    assert not good.issues and good.source_anchor == 'native'


def test_comments_never_enter_captured_visible_text():
    source = '<table><tr><th>Label<!--internal--></th><th>Amount</th></tr><tr><td><a href="#n">Note<!--internal--></a></td><td>1<!--internal-->200</td></tr></table><p id="n">Note <!--internal-->body</p>'
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert snapshot.source_cells[-1].text == '1200'
    assert snapshot.source_cells[0].text == 'Label'
    assert snapshot.source_cells[-2].links == (('Note', '#n'),)
    assert snapshot.resolved_notes == (('#n', 'Note body'),)
    assert 'internal' not in snapshot.original_text
    assert snapshot.context_after == ('Note body',)


@pytest.mark.parametrize('anchor', ['<a name="n"></a>', '<span id="n"></span>'])
def test_empty_note_anchor_resolves_only_bounded_paragraph(anchor):
    source = '<table><tr><th>Item</th><th>Value</th></tr><tr><td><a href="#n">(1)</a></td><td>100</td></tr></table><p>' + anchor + '(1) Note text.</p><p>Unrelated prose.</p>'
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert snapshot.resolved_notes == (('#n', '(1) Note text.'),)
    assert not snapshot.unresolved_references
    parser.get_pages()
    assert parser.table_snapshots == [snapshot]


def test_empty_unbounded_note_anchor_stays_unresolved():
    source = TABLE.replace('#note', '#n') + '<a name="n"></a><p>Unrelated prose.</p>'
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert not snapshot.resolved_notes
    assert snapshot.unresolved_references == ('#n',)


def test_context_retains_heading_units_and_multiple_notes_in_source_order():
    source = '<p>Earlier unrelated prose</p><h2>Income statement</h2><p>Amounts in millions</p>' + TABLE + '<p>(1) First note.</p><p>(2) Second note.</p><h2>Next section</h2><p>Unrelated.</p>'
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    snapshot, = parser.table_snapshots
    assert snapshot.context_before == ('Income statement', 'Amounts in millions')
    assert snapshot.context_after == ('(1) First note.', '(2) Second note.')


def test_context_stops_at_next_table_and_is_bounded():
    from sec2md.xlsx_tables import snapshot_html_table
    source = TABLE + '<p>Nearby note</p>' + TABLE + '<p>Other table note</p>'
    soup = BeautifulSoup(source, 'lxml')
    snapshot = snapshot_html_table(soup.table, ordinal=1, page=1, source_url=None)
    assert snapshot.context_after == ('Nearby note',)
    soup = BeautifulSoup(TABLE + ''.join(f'<p>Note {i}</p>' for i in range(50)), 'lxml')
    snapshot = snapshot_html_table(soup.table, ordinal=1, page=1, source_url=None)
    assert 1 < len(snapshot.context_after) <= 12
    assert snapshot.context_after[0] == 'Note 0'


def test_comparative_column_keeps_its_duration():
    from sec2md.xlsx_tables import prepare_table
    source = '''<table><tr><th></th><th colspan="2">Three Months Ended</th></tr>
    <tr><th>Item</th><th>Jul 26, 2026</th><th>Jul 27, 2025</th></tr>
    <tr><td>Revenue</td><td>96,221</td><td>46,743</td></tr></table>'''
    parser = Parser(source, capture_tables=True)
    parser.get_pages()
    table = prepare_table(parser.table_snapshots[0])
    assert table.headers[1:] == ('Three Months Ended — Jul 26, 2026', 'Three Months Ended — Jul 27, 2025')


def prepared(source):
    from sec2md.xlsx_tables import prepare_table, snapshot_html_table
    soup = BeautifulSoup(source, 'lxml')
    return prepare_table(snapshot_html_table(soup.table, ordinal=1, page=1, source_url='https://example.com/main.htm'))


def test_terminal_rowspan_preserves_empty_covered_row():
    from decimal import Decimal
    table = prepared('''<table><tr><th>Item</th><th>Amount</th></tr>
    <tr><td rowspan="2">Revenue</td><td rowspan="2">120</td></tr><tr></tr></table>''')
    assert not table.source.issues
    assert [[c.value for c in row] for row in table.rows] == [['Revenue', Decimal('120')], [None, None]]
    assert table.original_rows[-1] == ('', '')
    assert table.cell_sources[0] == (((1, 0),), ((1, 1),))


def test_numeric_year_and_amount_rows_are_never_consumed_as_headers():
    from decimal import Decimal
    table = prepared('''<table><tr><th>Year</th><th>Amount</th></tr>
    <tr><td>2026</td><td>2000</td></tr><tr><td>2025</td><td>150</td></tr></table>''')
    assert table.headers == ('Year', 'Amount')
    assert [[c.value for c in row] for row in table.rows] == [['2026', Decimal('2000')], ['2025', Decimal('150')]]


def test_all_numeric_td_rows_without_header_evidence_stay_data():
    table = prepared('<table><tr><td>2026</td><td>2000</td></tr><tr><td>2025</td><td>1999</td></tr></table>')
    assert table.headers == ('Column 1', 'Column 2')
    assert [[c.value for c in row] for row in table.rows] == [['2026', '2000'], ['2025', '1999']]


def test_numeric_facts_looking_like_years_after_blank_label_stay_data():
    from decimal import Decimal
    table = prepared('''<table><tr><th>Item</th><th>Amount</th></tr>
    <tr><td></td><td><ix:nonfraction>2026</ix:nonfraction></td></tr></table>''')
    assert table.headers == ('Item', 'Amount')
    assert table.rows[0][1].value == Decimal('2026')
    assert table.cell_sources[0][1] == ((1, 1),)


def test_numeric_year_data_after_duration_headers_stays_data():
    from decimal import Decimal
    table = prepared('''<table><tr><th colspan="2">Three Months Ended</th></tr>
    <tr><th>Year</th><th>Amount</th></tr><tr><td>2026</td><td>2000</td></tr>
    <tr><td>2025</td><td>150</td></tr></table>''')
    assert [[c.value for c in row] for row in table.rows] == [['2026', Decimal('2000')], ['2025', Decimal('150')]]


@pytest.mark.parametrize('prose', [
    'Earnings per share increased by 20 percent during the year.',
    'Revenue in millions increased by 20 percent during the year.',
    'The percentage of revenue increased by 20 percent during the year.',
])
def test_narrative_unit_mentions_do_not_scale_values(prose):
    from decimal import Decimal
    table = prepared(f'<p>{prose}</p><table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>')
    assert table.units == ''
    assert table.rows[0][1].value == Decimal('120')
    assert f'Context: {prose}' in table.notes


@pytest.mark.parametrize('header,label,token', [
    ('Percentage', 'Income per share (dollars)', '2.50'),
    ('Amount (dollars)', 'Tax rate (%)', '15'),
    ('Amount (dollars)', 'Revenue', '15%'),
    ('Percentage', 'Margin', '$15'),
])
def test_conflicting_explicit_units_keep_text_for_review(header, label, token):
    table = prepared(f'<table><tr><th>Item</th><th>{header}</th></tr><tr><td>{label}</td><td>{token}</td></tr></table>')
    value = table.rows[0][1]
    assert value.value == token
    assert value.original == token
    assert 'conflict' in value.review_reason.lower()
    assert table.status == 'needs_review'


def test_preparation_preserves_first_data_row_ids_blanks_and_repeats():
    table = prepared('<table><tr><td>0012</td><td>2026</td></tr><tr><td>0012</td><td>123</td></tr><tr><td></td><td></td></tr></table>')
    assert table.headers == ('Column 1', 'Column 2')
    assert [[c.value for c in r] for r in table.rows] == [['0012', '2026'], ['0012', '123'], [None, None]]
    assert table.rows[0][1].review_reason
    assert table.source.display_page is None


def test_preparation_mixed_units_groups_and_numeric_facts_keep_display():
    from decimal import Decimal
    table = prepared('''<h2>Results</h2><p>In millions, except per share data</p><table>
    <tr><th>Item</th><th>2026</th><th>Margin (%)</th></tr>
    <tr><td>Revenue</td><td><ix:nonfraction scale="6" sign="-">1,200</ix:nonfraction></td><td>25</td></tr>
    <tr><td>Per share</td><td>2.50</td><td></td></tr>
    <tr><td>Group</td><td></td><td></td></tr>
    <tr><td>Tax rate (%)</td><td>15</td><td>—</td></tr></table>''')
    assert table.title == 'Results'
    assert table.units == 'In millions, except per share data'
    assert [[c.value for c in r] for r in table.rows] == [
        ['Revenue', Decimal('1200'), Decimal('.25')], ['Per share', Decimal('2.50'), None],
        ['Group', None, None], ['Tax rate (%)', Decimal('.15'), '—']]
    assert table.original_rows[1][1] == '1,200'


def test_percent_context_and_td_duration_headers_are_supported():
    from decimal import Decimal
    table = prepared('''<p>Items expressed as a percentage of revenue</p><table>
    <tr><td></td><td colspan="2">Three Months Ended</td><td colspan="2">Six Months Ended</td></tr>
    <tr><td></td><td>July 26, 2026</td><td>July 27, 2025</td><td>July 26, 2026</td><td>July 27, 2025</td></tr>
    <tr><td>Revenue</td><td>100</td><td>100</td><td>100</td><td>100</td></tr></table>''')
    assert table.headers[2] == 'Three Months Ended — July 27, 2025'
    assert table.headers[4] == 'Six Months Ended — July 27, 2025'
    assert [c.value for c in table.rows[0][1:]] == [Decimal('1')] * 4


def test_safe_symbol_compaction_retains_all_origins_and_wider_original():
    from decimal import Decimal
    table = prepared('''<table><tr><th>Item</th><th colspan="3">Amount</th></tr>
    <tr><td>Income</td><td>$</td><td>(120</td><td>)</td></tr>
    <tr><td>Income</td><td>$</td><td>(30</td><td>)</td></tr></table>''')
    assert table.headers == ('Item', 'Amount')
    assert table.rows[0][1].value == Decimal('-120')
    assert table.cell_sources[0][1] == ((1, 1), (1, 2), (1, 3))
    assert table.original_rows[1] == ('Income', '$', '(120', ')')
    assert any('source' in n.lower() and 'span' in n.lower() for n in table.notes)


def test_preparation_notes_links_and_context_are_visible_and_bounded():
    table = prepared('''<h2>Inventory</h2><p>Nearby prose</p><table><caption>Inventory detail</caption>
    <tr><th>Item</th><th>Amount</th></tr><tr><td>Total (1)<a href="#n">[1]</a><a href="#missing">[2]</a><a href="other.htm">detail</a></td><td>120</td></tr></table>
    <p id="n">(1) Provision.</p><p>See accompanying Notes.</p><h2>Next</h2><p>Not local.</p>''')
    assert table.title == 'Inventory detail'
    assert table.references == (('[1]', 'https://example.com/main.htm#n'), ('[2]', 'https://example.com/main.htm#missing'), ('detail', 'https://example.com/other.htm'))
    assert any('Provision' in n for n in table.notes)
    assert any(n.startswith('Context:') and 'Nearby prose' in n for n in table.notes)
    assert any('See accompanying Notes' in n for n in table.notes)
    assert not any('Not local' in n for n in table.notes)
    assert any('missing' in n for n in table.issues)
    assert 'Total (1)' in table.rows[0][0].value


def test_unreliable_table_keeps_original_text_only():
    table = prepared('<table><tr><td rowspan="99">Label</td><td>123</td></tr><tr><td>Tail</td></tr></table>')
    assert table.status == 'source_text_only'
    assert table.rows == ()
    assert '123' in table.source.original_text
    assert table.original_rows


def test_numeric_looking_identifier_column_stays_text_despite_units():
    table = prepared('<p>Amounts in millions</p><table><tr><th>Code</th><th>Identifier</th><th>Amount</th></tr><tr><td>123</td><td>456</td><td>10</td></tr></table>')
    assert table.rows[0][0].value == '123'
    assert table.rows[0][1].value == '456'


def test_variable_value_spans_align_under_their_source_period():
    from decimal import Decimal
    table = prepared('''<p>In millions</p><div><table>
    <tr><td></td><td colspan="3">2026</td><td colspan="3">2025</td></tr>
    <tr><td>Revenue</td><td>$</td><td>120</td><td></td><td>$</td><td>90</td><td></td></tr>
    <tr><td>Cost</td><td colspan="2">(30</td><td>)</td><td colspan="2">(20</td><td>)</td></tr>
    <tr><td>Total</td><td colspan="2">90</td><td></td><td colspan="2">70</td><td></td></tr>
    </table></div>''')
    assert table.headers == ('Column 1', '2026', '2025')
    assert [[v.value for v in r] for r in table.rows] == [
        ['Revenue', Decimal('120'), Decimal('90')],
        ['Cost', Decimal('-30'), Decimal('-20')], ['Total', Decimal('90'), Decimal('70')]]
    assert (2, 1) in table.cell_sources[1][1] and (2, 3) in table.cell_sources[1][1]
    assert table.units == 'In millions'


def test_wrapped_table_percent_context_and_local_unit_exception():
    from decimal import Decimal
    table = prepared('''<h2>Margins</h2><p>Expressed as a percentage of revenue</p><div><table>
    <tr><th>Item</th><th>2026</th></tr><tr><td>Gross margin</td><td>25</td></tr>
    <tr><td>Income per share</td><td>2.50</td></tr></table></div><h2>Next</h2><p>Unrelated</p>''')
    assert table.rows[0][1].value == Decimal('.25')
    assert table.rows[1][1].value == Decimal('2.50')
    assert table.title == 'Margins'
    assert not any('Unrelated' in note for note in table.notes)


def test_numeric_body_ths_are_not_discarded_as_headers():
    table = prepared('<table><tr><th>Item</th><th>Amount</th></tr><tr><th>Revenue</th><th>120</th></tr></table>')
    assert len(table.rows) == 1 and table.rows[0][0].value == 'Revenue'


def test_duplicate_note_targets_are_ambiguous_and_broad_note_links_stay_references():
    table = prepared('''<table><tr><th>Item</th><th>Amount</th></tr>
    <tr><td><a href="#n">(1)</a><a href="#notes">See accompanying Notes</a></td><td>10</td></tr></table>
    <p id="n">First</p><p id="n">Second</p><div id="notes"><h2>Notes</h2><p>Whole notes section</p></div>''')
    assert any('#n' in issue for issue in table.issues)
    assert not any('Linked note' in note and ('First' in note or 'Whole notes' in note) for note in table.notes)
    assert any('accompanying' in label for label, _ in table.references)


def test_conflicting_body_value_span_requires_source_review():
    table = prepared('''<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>
    <tr><td>Revenue</td><td colspan="2">120</td></tr></table>''')
    assert table.status == 'source_text_only'
    assert '120' in table.source.original_text


def test_first_column_with_explicit_value_heading_can_be_numeric():
    from decimal import Decimal
    table = prepared('<table><tr><th>Percentage</th><th>Amount</th></tr><tr><td>25</td><td>120</td></tr></table>')
    assert [c.value for c in table.rows[0]] == [Decimal('.25'), Decimal('120')]


def test_uncertain_prose_does_not_supply_percentage_units():
    from decimal import Decimal
    table = prepared('<p>Revenue increased by 20% during the year.</p><table><tr><th>Item</th><th>Amount</th></tr><tr><td>Revenue</td><td>120</td></tr></table>')
    assert table.units == ''
    assert table.rows[0][1].value == Decimal('120')


def test_partial_blank_header_and_unresolved_fragments_are_flagged():
    table = prepared('<table><tr><th>Item</th><th></th><th>Amount</th></tr><tr><td>Revenue</td><td>(20</td><td>100</td></tr></table>')
    assert table.headers[1] == 'Column 2'
    assert table.status == 'needs_review'
    assert table.rows[0][1].value == '(20'


def test_blank_body_row_immediately_after_headers_stays_in_copy_grid():
    table = prepared('<table><tr><th>Item</th><th>Amount</th></tr><tr><td></td><td></td></tr><tr><td>Revenue</td><td>10</td></tr></table>')
    assert len(table.rows) == 2
    assert [c.value for c in table.rows[0]] == [None, None]


def test_spanning_unit_row_does_not_replace_leaf_period_membership():
    from decimal import Decimal
    table = prepared('''<table><tr><td></td><td colspan="2">2026</td><td colspan="2">2025</td></tr>
    <tr><td></td><td colspan="4">(In millions)</td></tr>
    <tr><td>Revenue</td><td>$</td><td>120</td><td>$</td><td>90</td></tr>
    <tr><td>Cost</td><td colspan="2">30</td><td colspan="2">20</td></tr></table>''')
    assert table.headers == ('Column 1', '2026', '2025')
    assert [c.value for c in table.rows[-1]] == ['Cost', Decimal('30'), Decimal('20')]
    assert table.units == '(In millions)'


@pytest.mark.parametrize('fixture_id, expected', [
    ('nvda-2026-10k', [(10, 3, 28), (20, 4, 54), (22, 3, 55), (24, 4, 100), (37, 3, 8)]),
    ('nvda-2026-q2-10q', [(7, 5, 60), (9, 3, 58), (12, 3, 62), (21, 3, 8), (40, 5, 44)]),
])
def test_retained_source_statement_periods_and_typed_value_counts(fixture_id, expected):
    """Counts/indices independently checked in retained source evidence, not output."""
    from decimal import Decimal
    from tests.accuracy.fixtures import load_fixture
    from sec2md.xlsx_tables import prepare_table, snapshot_html_table
    contract, source = load_fixture(fixture_id)  # verifies immutable source hash
    # These immutable SEC XHTML fixtures intentionally use the production HTML
    # parser; their XML declaration triggers this one known warning.
    with pytest.warns(XMLParsedAsHTMLWarning, match="using an HTML parser to parse an XML document") as warnings:
        soup = BeautifulSoup(source, 'lxml')
    assert len(warnings) == 1
    source_tables = soup.find_all('table')
    for index, width, count in expected:
        table = prepare_table(snapshot_html_table(source_tables[index], ordinal=index + 1,
                                                  page=1, source_url=contract.sec_url))
        assert table.status == 'exported', table.issues
        assert len(table.headers) == width
        assert sum(isinstance(c.value, Decimal) for row in table.rows for c in row) == count
        assert table.units
        if fixture_id == 'nvda-2026-q2-10q' and index in {7, 40}:
            assert table.headers[1:] == (
                'Three Months Ended — Jul 26, 2026', 'Three Months Ended — Jul 27, 2025',
                'Six Months Ended — Jul 26, 2026', 'Six Months Ended — Jul 27, 2025')
