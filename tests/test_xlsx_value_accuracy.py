"""XLSX value accuracy (docs/superpowers/specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md).

Tables use SEC-style inline XBRL: the units are defined in a hidden ix:header,
and each fact is an ix:nonFraction inside a table cell.
"""

from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from sec2md import xlsx_tables
from sec2md.xlsx_tables import snapshot_html_table
from sec2md.xlsx_values import convert_cell

UNITS = ('<div style="display:none"><ix:header><ix:resources>'
         '<xbrli:unit id="U_USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
         '<xbrli:unit id="U_shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>'
         '<xbrli:unit id="U_pure"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit>'
         '<xbrli:unit id="U_years"><xbrli:measure>utr:Y</xbrli:measure></xbrli:unit>'
         '<xbrli:unit id="U_USDPerShare"><xbrli:divide>'
         '<xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator>'
         '<xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator>'
         '</xbrli:divide></xbrli:unit>'
         '</ix:resources></ix:header></div>')


# Review reasons (sec2md.xlsx_tables and sec2md.xlsx_values).
_POINTS_REASON = 'Percentage points; verify the unit.'
_UNRESOLVED = 'Numeric role unresolved; verify the column heading and units.'
_INCOMPLETE = 'Not a complete supported US numeric token; verify the source value and markers.'
_UNPROVEN = 'Percent sign on other rows of this column; verify the scale.'
_CONFLICT = 'Conflicting explicit units; verify the row, column and displayed value units.'
_NEGATIVE_ZERO = 'Negative zero retained; verify the source meaning.'
_QUANTITIES = 'Identifier heading over quantities; verify the column.'
_AMOUNT_FORMATTED = 'Identifier heading over amount-formatted values; verify the column.'


def snapshot_cells(rows):
    """Source cells of a one-table filing whose units are defined in its ix:header."""
    source = f'<html><body>{UNITS}<table>{rows}</table></body></html>'
    soup = BeautifulSoup(source, 'lxml')
    return snapshot_html_table(soup.table, ordinal=1, page=1, source_url='https://example.com/main.htm').source_cells


def cell_at(cells, row, column):
    return next(cell for cell in cells if (cell.row, cell.column) == (row, column))


def test_pure_fact_keeps_scale_format_sign_and_displayed_text():
    cells = snapshot_cells(
        '<tr><td>Effective tax rate</td>'
        '<td><ix:nonFraction unitRef="U_pure" contextRef="FY2025" name="us-gaap:EffectiveIncomeTaxRateContinuingOperations" '
        'decimals="3" scale="-2" format="ixt:num-dot-decimal" sign="-">15.7</ix:nonFraction></td>'
        '<td>%</td></tr>')
    cell = cell_at(cells, 0, 1)
    assert cell.is_numeric_fact
    assert cell.facts == (xlsx_tables.FactAttributes(
        name='us-gaap:EffectiveIncomeTaxRateContinuingOperations', unit_measures=('xbrli:pure',), scale=-2,
        decimals='3', format='ixt:num-dot-decimal', sign='-', displayed='15.7'),)


@pytest.mark.parametrize('unit, measures', [
    ('U_USD', ('iso4217:USD',)),
    ('U_shares', ('xbrli:shares',)),
    ('U_USDPerShare', ('iso4217:USD', '/', 'xbrli:shares')),
])
def test_fact_unit_resolves_through_the_filing_unit_definitions(unit, measures):
    cells = snapshot_cells(
        '<tr><td>Amount</td><td>$</td>'
        f'<td><ix:nonFraction unitRef="{unit}" contextRef="FY2025" name="us-gaap:Example" decimals="-6" '
        'scale="6" format="ixt:num-dot-decimal">1,234</ix:nonFraction></td></tr>')
    (fact,) = cell_at(cells, 0, 2).facts
    assert fact.unit_measures == measures
    assert fact.scale == 6
    assert fact.displayed == '1,234'


def test_cell_without_facts_has_no_fact_attributes():
    cells = snapshot_cells('<tr><td>Gross margin</td><td>15.7</td><td>%</td></tr>')
    cell = cell_at(cells, 0, 1)
    assert cell.facts == ()
    assert not cell.is_numeric_fact


def test_two_facts_in_one_cell_keep_both_entries():
    cells = snapshot_cells(
        '<tr><td>Expected volatility</td><td>'
        '<ix:nonFraction unitRef="U_pure" contextRef="FY2025" name="us-gaap:VolatilityMinimum" decimals="3" '
        'scale="-2" format="ixt:num-dot-decimal">45.1</ix:nonFraction> - '
        '<ix:nonFraction unitRef="U_pure" contextRef="FY2025" name="us-gaap:VolatilityMaximum" decimals="3" '
        'scale="-2" format="ixt:num-dot-decimal">52.3</ix:nonFraction> %</td></tr>')
    facts = cell_at(cells, 0, 1).facts
    assert len(facts) == 2
    assert [(fact.name, fact.displayed, fact.unit_measures) for fact in facts] == [
        ('us-gaap:VolatilityMinimum', '45.1', ('xbrli:pure',)),
        ('us-gaap:VolatilityMaximum', '52.3', ('xbrli:pure',)),
    ]


# --- P4: the split '%', negative percents and percentage points -------------------------

def prepared(rows, before=''):
    """prepare_table for a one-table filing whose units are defined in its ix:header,
    with any blocks of context before the table."""
    source = f'<html><body>{UNITS}{before}<table>{rows}</table></body></html>'
    soup = BeautifulSoup(source, 'lxml')
    return xlsx_tables.prepare_table(
        snapshot_html_table(soup.table, ordinal=1, page=1, source_url='https://example.com/main.htm'))


def cell_rows(table):
    """(value, number_format, original, review_reason) for every copy cell."""
    return [[(c.value, c.number_format, c.original, c.review_reason) for c in row] for row in table.rows]


@pytest.mark.parametrize('text, value, number_format', [
    ('(29) %', Decimal('-0.29'), '0%;(0%)'),
    ('(4.5)%', Decimal('-0.045'), '0.0%;(0.0%)'),
    ('(12.3 %)', Decimal('-0.123'), '0.0%;(0.0%)'),
])
def test_converter_reads_negative_percent_forms(text, value, number_format):
    cell = convert_cell(text, role='number')
    assert (cell.value, cell.number_format, cell.original, cell.review_reason) == (value, number_format, text, None)


def test_split_percent_sign_attaches_to_the_negative_value_on_its_left():
    table = prepared('<tr><th>Item</th><th>2025</th><th></th></tr>'
                     '<tr><td>Growth</td><td>(29)</td><td>%</td></tr>')
    assert table.headers == ('Item', '2025', 'Column 3')
    assert cell_rows(table) == [[('Growth', '@', 'Growth', None),
                                 (Decimal('-0.29'), '0%;(0%)', '(29) %', None),
                                 (None, '@', '', None)]]
    # The value's provenance includes the % cell, whose own copy position is now empty.
    assert table.cell_sources == ((((1, 0),), ((1, 1), (1, 2)), ()),)


def test_close_percent_marker_attaches_to_the_open_value_on_its_left():
    table = prepared('<tr><th>Item</th><th>2025</th><th></th></tr>'
                     '<tr><td>Gross margin change</td><td>(4.5</td><td>)%</td></tr>')
    assert cell_rows(table) == [[('Gross margin change', '@', 'Gross margin change', None),
                                 (Decimal('-0.045'), '0.0%;(0.0%)', '(4.5)%', None),
                                 (None, '@', '', None)]]
    assert table.cell_sources == ((((1, 0),), ((1, 1), (1, 2)), ()),)


def test_column_with_a_negative_split_row_merges_and_every_row_converts():
    table = prepared('<tr><th>Item</th><th colspan="2">Change</th></tr>'
                     '<tr><td>Revenue</td><td>12</td><td>%</td></tr>'
                     '<tr><td>Costs</td><td>(29)</td><td>%</td></tr>'
                     '<tr><td>Margin</td><td>4.5</td><td>%</td></tr>')
    assert table.headers == ('Item', 'Change')
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('0.12'), '0%', '12 %', None)],
        [('Costs', '@', 'Costs', None), (Decimal('-0.29'), '0%;(0%)', '(29) %', None)],
        [('Margin', '@', 'Margin', None), (Decimal('0.045'), '0.0%', '4.5 %', None)],
    ]
    assert table.cell_sources == tuple((((r, 0),), ((r, 1), (r, 2))) for r in (1, 2, 3))
    assert table.status == 'exported'


def test_attachment_never_joins_two_values_under_one_leaf():
    """NFLX #13: 'Change — 2024 vs. 2023' covers both an amount and a percent."""
    table = prepared('<tr><th>Item</th><th colspan="4">Change</th></tr>'
                     '<tr><td>Revenue</td><td>$</td><td>1,323,096</td><td>7</td><td>%</td></tr>')
    assert table.headers == ('Item', 'Change', 'Change', 'Change', 'Change')
    assert cell_rows(table) == [[('Revenue', '@', 'Revenue', None), ('$', '@', '$', None),
                                 (Decimal('1323096'), '#,##0', '1,323,096', None),
                                 (Decimal('0.07'), '0%', '7 %', None), (None, '@', '', None)]]
    assert table.cell_sources == ((((1, 0),), ((1, 1),), ((1, 2),), ((1, 3), (1, 4)), ()),)


def test_percentage_points_stay_text_and_do_not_split_the_column():
    """NVDA's 'Gross margin 26.6 pts' among '%' changes."""
    table = prepared('<tr><th>Item</th><th colspan="2">Change</th></tr>'
                     '<tr><td>Revenue</td><td>101</td><td>%</td></tr>'
                     '<tr><td>Gross margin</td><td>26.6</td><td>pts</td></tr>'
                     '<tr><td>Operating expenses</td><td>10</td><td>%</td></tr>')
    assert table.headers == ('Item', 'Change')
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1.01'), '0%', '101 %', None)],
        [('Gross margin', '@', 'Gross margin', None), ('26.6 pts', '@', '26.6 pts', _POINTS_REASON)],
        [('Operating expenses', '@', 'Operating expenses', None), (Decimal('0.10'), '0%', '10 %', None)],
    ]
    assert table.issues == (f'Source row 2, column 1: {_POINTS_REASON}',)


def test_percent_heading_never_attaches_to_a_year_in_a_body_heading_row():
    """MD&A 'Year Ended | Change ($, %)' blocks: the heading rows stay in the body, and
    their '%' sub-heading is not a percent sign of the year on its left."""
    table = prepared('<tr><td></td><td colspan="2">Year Ended December 31,</td><td colspan="2">Change</td></tr>'
                     '<tr><td></td><td>2025</td><td>2024</td><td>$</td><td>%</td></tr>'
                     '<tr><td>Revenue</td><td>110</td><td>100</td><td>10</td><td>10</td></tr>'
                     '<tr><td></td><td>2024</td><td>2023</td><td>$</td><td>%</td></tr>'
                     '<tr><td>Revenue</td><td>100</td><td>90</td><td>10</td><td>11</td></tr>')
    heading = [(None, '@', '', None)]
    assert [cell_rows(table)[i] for i in (0, 2)] == [
        heading + [(Decimal('2025'), '#,##0', '2025', None), (Decimal('2024'), '#,##0', '2024', None),
                   ('$', '@', '$', None), ('%', '@', '%', None)],
        heading + [(Decimal('2024'), '#,##0', '2024', None), (Decimal('2023'), '#,##0', '2023', None),
                   ('$', '@', '$', None), ('%', '@', '%', None)],
    ]
    assert [table.cell_sources[i] for i in (0, 2)] == [tuple(((r, c),) for c in range(5)) for r in (1, 3)]


def test_percent_heading_never_attaches_in_a_period_row_without_headers():
    """A plain '| | 2025 | % |' heading row: no leaf header guards it, the period row does."""
    table = prepared('<tr><td></td><td>2025</td><td>%</td></tr>'
                     '<tr><td>Revenue</td><td>110</td><td>12 %</td></tr>'
                     '<tr><td>Costs</td><td>90</td><td>(5) %</td></tr>')
    assert cell_rows(table)[0] == [(None, '@', '', None), ('2025', '@', '2025', _UNRESOLVED), ('%', '@', '%', None)]
    assert table.cell_sources[0] == (((0, 0),), ((0, 1),), ((0, 2),))
    assert cell_rows(table)[2][2] == (Decimal('-0.05'), '0%;(0%)', '(5) %', None)


def test_percent_never_attaches_across_into_another_leaf_header():
    """The '%' under '% change' is not the percent sign of the amount under '2025'. Fix A
    (user decision 2026-10-13): the refused attachment flags the amount as P4 text."""
    table = prepared('<tr><th>Item</th><th>2025</th><th colspan="2">% change</th></tr>'
                     '<tr><td>Revenue</td><td>1,000</td><td></td><td>%</td></tr>')
    assert cell_rows(table) == [[('Revenue', '@', 'Revenue', None), ('1,000', '@', '1,000', _UNPROVEN),
                                 (None, '@', '', None), ('%', '@', '%', None)]]
    assert table.cell_sources == ((((1, 0),), ((1, 1),), ((1, 2),), ((1, 3),)),)
    assert table.issues == (f'Source row 1, column 1: {_UNPROVEN}',)
    assert table.status == 'needs_review'


def test_split_percent_attaches_under_a_spanning_period_heading():
    """TSM 20-F 2025 #8 'Results of Operations': 'For the year ended December 31,' spans
    the year leaves, and each split '%' or ')%' sits under that heading, not under the
    year above its value. The 2024 marker has no heading above it."""
    def row(label, *cells):
        return f'<tr><td>{label}</td>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>'
    table = prepared('<tr>' + '<td></td>' * 13 + '</tr>'
                     '<tr><td></td><td></td><td colspan="10">For the year ended December 31,</td><td></td></tr>'
                     '<tr><td></td><td></td><td colspan="2">2022</td><td></td><td></td><td colspan="2">2023</td>'
                     '<td></td><td></td><td colspan="2">2024</td><td></td></tr>'
                     + row('Net revenue', '', '', '100.0', '%', '', '', '100.0', '%', '', '', '100.0', '%')
                     + row('Cost of revenue', '', '', '(40.4', ')%', '', '', '(45.6', ')%', '', '', '(43.9', ')%')
                     + row('Gross profit', '', '', '59.6', '%', '', '', '54.4', '%', '', '', '56.1', '%'))
    converted = [[(c.value, c.number_format, c.original, c.review_reason) for c in row if c.value is not None][1:]
                 for row in table.rows]
    assert converted == [
        [(Decimal('1.000'), '0.0%', '100.0 %', None)] * 3,
        [(Decimal('-0.404'), '0.0%;(0.0%)', '(40.4)%', None), (Decimal('-0.456'), '0.0%;(0.0%)', '(45.6)%', None),
         (Decimal('-0.439'), '0.0%;(0.0%)', '(43.9)%', None)],
        [(Decimal('0.596'), '0.0%', '59.6 %', None), (Decimal('0.544'), '0.0%', '54.4 %', None),
         (Decimal('0.561'), '0.0%', '56.1 %', None)],
    ]
    # Each value's provenance includes its marker; the marker's own copy position is empty.
    for r, sources in zip((3, 4, 5), table.cell_sources):
        assert {((r, 3), (r, 4)), ((r, 7), (r, 8)), ((r, 11), (r, 12))} <= {tuple(s[-2:]) for s in sources}
        assert ((r, 4),) not in sources and ((r, 8),) not in sources
    assert not any('Percent sign' in issue for issue in table.issues)


def test_refused_split_percent_flags_a_plain_value_as_p4_text():
    """A '%' under 'Change' refused for the value under '2025' never leaves a plain number."""
    table = prepared('<tr><th>Item</th><th>2025</th><th colspan="2">Change</th></tr>'
                     '<tr><td>Gross margin</td><td>12.5</td><td></td><td>%</td></tr>'
                     '<tr><td>Operating margin</td><td>(0)</td><td></td><td>%</td></tr>')
    assert [row[1] for row in cell_rows(table)] == [
        ('12.5', '@', '12.5', _UNPROVEN),
        ('(0)', '@', '(0)', 'Negative zero retained; verify the source meaning.')]
    assert f'Source row 1, column 1: {_UNPROVEN}' in table.issues
    assert table.status == 'needs_review'


def test_ancestor_heading_never_attaches_across_another_leaf_heading():
    """Ruling 14: a stray '%' under the period heading '2025' would reach '5' only across
    the separately headed, blank '% of revenue' cell. It is refused, so '5' and '4' are
    P4 text, never 0.05 and 0.04. Revenue's markers sit beside their values and attach."""
    table = prepared('<tr><td></td><td colspan="4">2025</td><td colspan="4">2024</td></tr>'
                     '<tr><td></td><td colspan="2">Amount</td><td>% of revenue</td><td></td>'
                     '<td colspan="2">Amount</td><td>% of revenue</td><td></td></tr>'
                     '<tr><td>Revenue</td><td>$</td><td>1,000</td><td>100.0</td><td>%</td>'
                     '<td>$</td><td>900</td><td>100.0</td><td>%</td></tr>'
                     '<tr><td>Other income</td><td></td><td>5</td><td></td><td>%</td>'
                     '<td></td><td>4</td><td></td><td>%</td></tr>')
    empty = (None, '@', '', None)
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1000'), '"$"#,##0', '$ 1,000', None),
         (Decimal('1.000'), '0.0%', '100.0 %', None), empty,
         (Decimal('900'), '"$"#,##0', '$ 900', None), (Decimal('1.000'), '0.0%', '100.0 %', None), empty],
        [('Other income', '@', 'Other income', None), ('5', '@', '5', _UNPROVEN), empty, ('%', '@', '%', None),
         ('4', '@', '4', _UNPROVEN), empty, ('%', '@', '%', None)],
    ]
    assert table.cell_sources[1] == (((3, 0),), ((3, 1), (3, 2)), ((3, 3),), ((3, 4),),
                                     ((3, 5), (3, 6)), ((3, 7),), ((3, 8),))
    assert table.issues == (f'Source row 3, column 1: {_UNPROVEN}', f'Source row 3, column 5: {_UNPROVEN}')
    assert table.status == 'needs_review'


def _tr(*cells):
    """A source row; a (text, colspan) pair is a spanning cell."""
    return '<tr>' + ''.join(f'<td colspan="{c[1]}">{c[0]}</td>' if isinstance(c, tuple) else f'<td>{c}</td>'
                            for c in cells) + '</tr>'


_EMPTY = (None, '@', '', None)
_STRAY = ('%', '@', '%', None)


def test_split_percent_never_attaches_across_an_unheaded_gap_column():
    """Ruling 16 (r1b): Other's '%' is not beside '4'; a blank, unheaded percent column
    lies between them. '4' is P4 text, never 0.04, and Revenue's and Costs' adjacent
    markers attach."""
    table = prepared(_tr('', ('Year Ended December 31,', 4)) + _tr('', '2025', '2024', '', '')
                     + _tr('Revenue', '1,100', '1,000', '10', '%') + _tr('Costs', '600', '500', '20', '%')
                     + _tr('Other', '5', '4', '', '%'))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '#,##0', '1,100', None),
         (Decimal('1000'), '#,##0', '1,000', None), (Decimal('0.10'), '0%', '10 %', None), _EMPTY],
        [('Costs', '@', 'Costs', None), ('600', '@', '600', _UNRESOLVED), ('500', '@', '500', _UNRESOLVED),
         (Decimal('0.20'), '0%', '20 %', None), _EMPTY],
        [('Other', '@', 'Other', None), ('5', '@', '5', _UNRESOLVED), ('4', '@', '4', _UNPROVEN), _EMPTY, _STRAY],
    ]
    assert table.cell_sources == (
        (((2, 0),), ((2, 1),), ((2, 2),), ((2, 3), (2, 4)), ()),
        (((3, 0),), ((3, 1),), ((3, 2),), ((3, 3), (3, 4)), ()),
        (((4, 0),), ((4, 1),), ((4, 2),), ((4, 3),), ((4, 4),)),
    )
    assert table.issues == (f'Source row 3, column 1: {_UNRESOLVED}', f'Source row 3, column 2: {_UNRESOLVED}',
                            f'Source row 4, column 1: {_UNRESOLVED}', f'Source row 4, column 2: {_UNPROVEN}')
    assert table.status == 'needs_review'


def test_split_percent_never_attaches_past_a_blank_change_percent_cell():
    """Ruling 16 (r3): 'Change' heads the $ change; Costs' '%' lies past a blank, unheaded
    percent cell, so the $ change '100' is P4 text, never 1.00."""
    table = prepared(_tr('', ('Year Ended December 31,', 8))
                     + _tr('', ('2025', 2), ('2024', 2), ('Change', 2), '', '')
                     + _tr('Revenue', '$', '1,100', '$', '1,000', '$', '100', '10', '%')
                     + _tr('Costs', '', '600', '', '500', '', '100', '', '%'))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '"$"#,##0', '$ 1,100', None),
         (Decimal('1000'), '"$"#,##0', '$ 1,000', None), (Decimal('100'), '"$"#,##0', '$ 100', None),
         (Decimal('0.10'), '0%', '10 %', None), _EMPTY],
        [('Costs', '@', 'Costs', None), ('600', '@', '600', _UNRESOLVED), ('500', '@', '500', _UNRESOLVED),
         ('100', '@', '100', _UNPROVEN), _EMPTY, _STRAY],
    ]
    assert table.cell_sources == (
        (((2, 0),), ((2, 1), (2, 2)), ((2, 3), (2, 4)), ((2, 5), (2, 6)), ((2, 7), (2, 8)), ()),
        (((3, 0),), ((3, 1), (3, 2)), ((3, 3), (3, 4)), ((3, 5), (3, 6)), ((3, 7),), ((3, 8),)),
    )
    assert table.issues == (f'Source row 3, column 1: {_UNRESOLVED}', f'Source row 3, column 3: {_UNRESOLVED}',
                            f'Source row 3, column 5: {_UNPROVEN}')
    assert table.status == 'needs_review'


def test_split_percent_under_its_values_leaf_never_crosses_an_empty_origin():
    """Ruling 16 (r4'): 'Change' heads the $ and % columns; Costs' '%' shares that leaf
    with the $ change '100' but lies past an empty origin. '100' is P4 text, never 1.00."""
    table = prepared(_tr('', ('Year Ended December 31,', 8))
                     + _tr('', ('2025', 2), ('2024', 2), ('Change', 4))
                     + _tr('Revenue', '$', '1,100', '$', '1,000', '$', '100', '10', '%')
                     + _tr('Costs', '', '600', '', '500', '', '100', '', '%'))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '"$"#,##0', '$ 1,100', None),
         (Decimal('1000'), '"$"#,##0', '$ 1,000', None), ('$', '@', '$', None),
         (Decimal('100'), '#,##0', '100', None), (Decimal('0.10'), '0%', '10 %', None), _EMPTY],
        [('Costs', '@', 'Costs', None), ('600', '@', '600', _UNRESOLVED), ('500', '@', '500', _UNRESOLVED),
         _EMPTY, ('100', '@', '100', _UNPROVEN), _EMPTY, _STRAY],
    ]
    assert table.cell_sources == (
        (((2, 0),), ((2, 1), (2, 2)), ((2, 3), (2, 4)), ((2, 5),), ((2, 6),), ((2, 7), (2, 8)), ()),
        (((3, 0),), ((3, 1), (3, 2)), ((3, 3), (3, 4)), ((3, 5),), ((3, 6),), ((3, 7),), ((3, 8),)),
    )
    assert table.issues == (f'Source row 3, column 1: {_UNRESOLVED}', f'Source row 3, column 3: {_UNRESOLVED}',
                            f'Source row 3, column 6: {_UNPROVEN}')
    assert table.status == 'needs_review'


_GAP_HEADINGS = _tr('', ('Year Ended December 31,', 4)) + _tr('', '2025', '2024', '', '')
_GAP_REVENUE = _tr('Revenue', '1,100', '1,000', '10', '%')


@pytest.mark.parametrize('other', [
    _tr('Other', '5', '4', ('%', 2)),  # s2: the '%' spans the blank percent-value column
    _tr('Other', '5', '4', '%'),  # s3: a short row puts the '%' in the percent-value column
], ids=['marker_spans_value_column', 'marker_in_value_column'])
def test_ancestor_heading_percent_in_a_value_column_never_attaches(other):
    """Ruling 17: Other's '%' sits under only the period heading and in a column that holds
    Revenue's '10'. It is not 4's percent sign: '4' is P4 text, never 0.04, and Revenue's
    '1,000' keeps its number."""
    table = prepared(_GAP_HEADINGS + _GAP_REVENUE + other)
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '#,##0', '1,100', None),
         (Decimal('1000'), '#,##0', '1,000', None), (Decimal('0.10'), '0%', '10 %', None), _EMPTY],
        [('Other', '@', 'Other', None), ('5', '@', '5', _UNRESOLVED), ('4', '@', '4', _UNPROVEN), _STRAY, _EMPTY],
    ]
    assert table.cell_sources == (
        (((2, 0),), ((2, 1),), ((2, 2),), ((2, 3), (2, 4)), ()),
        (((3, 0),), ((3, 1),), ((3, 2),), ((3, 3),), ()),
    )
    assert table.issues == (f'Source row 3, column 1: {_UNRESOLVED}', f'Source row 3, column 2: {_UNPROVEN}')
    assert table.status == 'needs_review'


def test_split_percent_never_attaches_from_a_column_holding_a_year_in_a_body_period_row():
    """Ruling 18 (C1): a body period row writes '2023' in the column of Other's '%', so
    that column is not marker-only and the '%' is not 4's percent sign. '4' is P4 text,
    never 0.04, and Revenue's '1,000' keeps its number."""
    table = prepared(_GAP_HEADINGS + _tr('Revenue', '1,100', '1,000', '', '')
                     + _tr('', '2025', '2024', '2023', '') + _tr('Other', '5', '4', '%'))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '#,##0', '1,100', None),
         (Decimal('1000'), '#,##0', '1,000', None), _EMPTY],
        [_EMPTY, ('2025', '@', '2025', _UNRESOLVED), ('2024', '@', '2024', _UNRESOLVED),
         ('2023', '@', '2023', _UNRESOLVED)],
        [('Other', '@', 'Other', None), ('5', '@', '5', _UNRESOLVED), ('4', '@', '4', _UNPROVEN), _STRAY],
    ]
    assert table.cell_sources == tuple(tuple(((r, c),) for c in range(4)) for r in (2, 3, 4))
    assert table.issues == (f'Source row 3, column 1: {_UNRESOLVED}', f'Source row 3, column 2: {_UNRESOLVED}',
                            f'Source row 3, column 3: {_UNRESOLVED}', f'Source row 4, column 1: {_UNRESOLVED}',
                            f'Source row 4, column 2: {_UNPROVEN}')
    assert table.status == 'needs_review'


@pytest.mark.parametrize('marker', ['%', ('%', 2)], ids=['short_row', 'marker_colspan'])
def test_split_percent_under_its_values_leaf_never_attaches_from_a_value_column(marker):
    """Ruling 18 (shape 1): 'Change' heads the $ change, the percent change and its '%'.
    Costs' '%' sits beside its $ change '100' but in the column of Revenue's percent
    change '10', so it is not 100's percent sign: '100' is P4 text, never 1.00."""
    table = prepared(_tr('', ('Year Ended December 31,', 8)) + _tr('', ('2025', 2), ('2024', 2), ('Change', 4))
                     + _tr('Revenue', '$', '1,100', '$', '1,000', '$', '100', '10', '%')
                     + _tr('Costs', '', '600', '', '500', '', '100', marker))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '"$"#,##0', '$ 1,100', None),
         (Decimal('1000'), '"$"#,##0', '$ 1,000', None), ('$', '@', '$', None),
         (Decimal('100'), '#,##0', '100', None), (Decimal('0.10'), '0%', '10 %', None), _EMPTY],
        [('Costs', '@', 'Costs', None), ('600', '@', '600', _UNRESOLVED), ('500', '@', '500', _UNRESOLVED),
         _EMPTY, ('100', '@', '100', _UNPROVEN), _STRAY, _EMPTY],
    ]
    assert table.cell_sources == (
        (((2, 0),), ((2, 1), (2, 2)), ((2, 3), (2, 4)), ((2, 5),), ((2, 6),), ((2, 7), (2, 8)), ()),
        (((3, 0),), ((3, 1), (3, 2)), ((3, 3), (3, 4)), ((3, 5),), ((3, 6),), ((3, 7),), ()),
    )
    assert table.issues == (f'Source row 3, column 1: {_UNRESOLVED}', f'Source row 3, column 3: {_UNRESOLVED}',
                            f'Source row 3, column 6: {_UNPROVEN}')
    assert table.status == 'needs_review'


@pytest.mark.parametrize('marker', ['%', ('%', 2)], ids=['short_row', 'marker_colspan'])
@pytest.mark.parametrize('headed', [True, False], ids=['year_headings', 'no_headings'])
def test_unheaded_split_percent_never_attaches_from_a_value_column(headed, marker):
    """Ruling 18 (shape 2): no heading lies over Other's '%', which sits in (or spans) the
    column of Revenue's percent '10'. It is not 4's percent sign: '4' is P4 text, never
    0.04, and Revenue's '1,000' keeps its number."""
    table = prepared((_tr('', '2025', '2024', '', '') if headed else '') + _GAP_REVENUE
                     + _tr('Other', '5', '4', marker))
    r = 1 if headed else 0
    assert table.headers == (('Column 1', '2025', '2024', 'Column 4', 'Column 5') if headed
                             else ('Column 1', 'Column 2', 'Column 3', 'Column 4', 'Column 5'))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '#,##0', '1,100', None),
         (Decimal('1000'), '#,##0', '1,000', None), (Decimal('0.10'), '0%', '10 %', None), _EMPTY],
        [('Other', '@', 'Other', None), ('5', '@', '5', _UNRESOLVED), ('4', '@', '4', _UNPROVEN), _STRAY, _EMPTY],
    ]
    assert table.cell_sources == (
        (((r, 0),), ((r, 1),), ((r, 2),), ((r, 3), (r, 4)), ()),
        (((r + 1, 0),), ((r + 1, 1),), ((r + 1, 2),), ((r + 1, 3),), ()),
    )
    headings = (('Missing source header for Column 4; verify its meaning.',
                 'Missing source header for Column 5; verify its meaning.') if headed
                else ('No explicit headers; positional column names generated and every source row retained.',))
    assert table.issues == headings + (f'Source row {r + 1}, column 1: {_UNRESOLVED}',
                                       f'Source row {r + 1}, column 2: {_UNPROVEN}')
    assert table.status == 'needs_review'


def test_split_percent_never_attaches_from_a_column_of_dashes():
    """Ruling 18 (shape 3): Revenue's percent change is '—'. No digit lies in the column of
    Other's '%', but the column holds a value, not only markers, so '4' is P4 text, never
    0.04, and Revenue's '1,000' keeps its number."""
    table = prepared(_GAP_HEADINGS + _tr('Revenue', '1,100', '1,000', '—', '%') + _tr('Other', '5', '4', '%'))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '#,##0', '1,100', None),
         (Decimal('1000'), '#,##0', '1,000', None), ('—', '@', '—', None), _STRAY],
        [('Other', '@', 'Other', None), ('5', '@', '5', _UNRESOLVED), ('4', '@', '4', _UNPROVEN), _STRAY, _EMPTY],
    ]
    assert table.cell_sources == (
        tuple(((2, c),) for c in range(5)),
        (((3, 0),), ((3, 1),), ((3, 2),), ((3, 3),), ()),
    )
    assert table.issues == (f'Source row 3, column 1: {_UNRESOLVED}', f'Source row 3, column 2: {_UNPROVEN}')
    assert table.status == 'needs_review'


def test_split_percent_attaches_past_closing_fragments_and_a_unit_caption_row():
    """Ruling 18a, TSM 20-F 2025 #9-#12: the body's unit caption row spans the marker
    columns, and the ')' of a negative amount sits in them. Neither is a value of the
    marker column, so the margins' '%' still attach (2023 through the spanning period
    heading, 2024 with no heading above its marker)."""
    def row(label, *cells):
        return f'<tr><td>{label}</td>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>'
    table = prepared('<tr>' + '<td></td>' * 9 + '</tr>'
                     '<tr><td></td><td></td><td colspan="6">For the year ended December 31,</td><td></td></tr>'
                     '<tr><td></td><td></td><td colspan="2">2023</td><td></td><td></td>'
                     '<td colspan="2">2024</td><td></td></tr>'
                     '<tr><td></td><td></td><td colspan="6">(in millions, except percentages)</td><td></td></tr>'
                     + row('Cost of revenue', '', '', '(986', ')', '', '', '(1,270', ')')
                     + row('Gross margin', '', '', '54.4', '%', '', '', '56.1', '%'))
    caption = '(in millions, except percentages)'
    assert cell_rows(table) == [
        [_EMPTY, (caption, '@', caption, None), _EMPTY, _EMPTY, _EMPTY],
        [('Cost of revenue', '@', 'Cost of revenue', None), ('(986', '@', '(986', _INCOMPLETE), (')', '@', ')', None),
         ('(1,270', '@', '(1,270', _INCOMPLETE), (')', '@', ')', None)],
        [('Gross margin', '@', 'Gross margin', None), (Decimal('0.544'), '0.0%', '54.4 %', None), _EMPTY,
         (Decimal('0.561'), '0.0%', '56.1 %', None), _EMPTY],
    ]
    assert table.cell_sources == (
        (((3, 0),), ((3, 2),), (), (), ((3, 8),)),
        (((4, 0),), ((4, 2), (4, 3)), ((4, 4),), ((4, 6), (4, 7)), ((4, 8),)),
        (((5, 0),), ((5, 2), (5, 3), (5, 4)), (), ((5, 6), (5, 7), (5, 8)), ()),
    )
    assert table.issues == ('Missing source header for Column 5; verify its meaning.',
                            f'Source row 4, column 2: {_INCOMPLETE}', f'Source row 4, column 6: {_INCOMPLETE}')
    assert table.status == 'needs_review'


@pytest.mark.parametrize('middle, shown', [
    (_tr('Other X', '', '', ('—', 2)), [('Other X', '@', 'Other X', None), _EMPTY, _EMPTY, ('—', '@', '—', None)]),
    (_tr('', '', '', ('NM', 2)), [_EMPTY, _EMPTY, _EMPTY, ('NM', '@', 'NM', None)]),
    (_tr('', '', '', ('Change', 2)), [_EMPTY, _EMPTY, _EMPTY, ('Change', '@', 'Change', None)]),
], ids=['labelled_dash', 'unlabelled_nm', 'body_heading'])
def test_digitless_spanning_row_that_is_no_unit_caption_still_refuses(middle, shown):
    """Ruling 18a skips only a unit caption row. A digitless row whose dash, 'NM' or
    heading spans the percent-value and marker columns shows a value column there, so
    Other's '%' is not 4's percent sign: '4' is P4 text, never 0.04."""
    table = prepared(_GAP_HEADINGS + _tr('Revenue', '1,100', '1,000', '', '') + middle
                     + _tr('Other', '5', '4', '%'))
    assert cell_rows(table) == [
        [('Revenue', '@', 'Revenue', None), (Decimal('1100'), '#,##0', '1,100', None),
         (Decimal('1000'), '#,##0', '1,000', None), _EMPTY],
        shown,
        [('Other', '@', 'Other', None), ('5', '@', '5', _UNRESOLVED), ('4', '@', '4', _UNPROVEN), _STRAY],
    ]
    assert table.cell_sources == tuple(tuple(((r, c),) for c in range(4)) for r in (2, 3, 4))
    assert table.issues == (f'Source row 4, column 1: {_UNRESOLVED}', f'Source row 4, column 2: {_UNPROVEN}')
    assert table.status == 'needs_review'


def test_refused_split_percent_on_a_zero_keeps_the_zero():
    """Spec P4's zero exception: zero is right at any scale, so a refused zero converts."""
    table = prepared('<tr><th>Item</th><th>2025</th><th colspan="2">% change</th></tr>'
                     '<tr><td>Revenue</td><td>0</td><td></td><td>%</td></tr>'
                     '<tr><td>Costs</td><td>0.0</td><td></td><td>%</td></tr>')
    assert [row[1] for row in cell_rows(table)] == [(Decimal('0'), '#,##0', '0', None),
                                                    (Decimal('0.0'), '#,##0.0', '0.0', None)]
    assert table.issues == ()


def test_period_text_value_in_a_data_row_takes_no_split_percent():
    """A year is never a split percent's value, and its refusal is not flagged."""
    table = prepared('<tr><th>Item</th><th>2025</th><th colspan="2">% change</th></tr>'
                     '<tr><td>Revenue</td><td>2020</td><td></td><td>%</td></tr>')
    assert cell_rows(table) == [[('Revenue', '@', 'Revenue', None), (Decimal('2020'), '#,##0', '2020', None),
                                 (None, '@', '', None), ('%', '@', '%', None)]]
    assert table.issues == ()


def test_refused_split_percent_under_an_identifier_heading_keeps_the_identifier_reason():
    """Existing reason precedence: an identifier heading keeps the cell text with its I2 reason."""
    table = prepared('<tr><th>Item</th><th>Notes</th><th colspan="2">% change</th></tr>'
                     '<tr><td>Revenue</td><td>1,000</td><td></td><td>%</td></tr>')
    assert cell_rows(table)[0][1] == ('1,000', '@', '1,000', _AMOUNT_FORMATTED)
    assert not any(_UNPROVEN in issue for issue in table.issues)


# --- Rule P: percent proofs (P1-P3), mixed columns (P4) and except captions (P5) --------


def fact(text, unit='U_pure', scale='-2', name='us-gaap:CapitalRatio', format='ixt:num-dot-decimal', sign=None):
    """An SEC-style ix:nonFraction; format=None leaves the attribute out."""
    attributes = f' format="{format}"' if format else ''
    attributes += f' sign="{sign}"' if sign else ''
    return (f'<ix:nonFraction unitRef="{unit}" contextRef="FY2025" name="{name}" decimals="1" '
            f'scale="{scale}"{attributes}>{text}</ix:nonFraction>')


def sec_cells(value):
    """One value as SEC filings lay it out under a heading spanning three cells:
    '$ 275,513' gives '$' | '275,513' | '', and '15.7 %' gives '' | '15.7' | '%'."""
    dollar = '$' if value.startswith('$ ') else ''
    percent = '%' if value.endswith(' %') else ''
    return f'<td>{dollar}</td><td>{value.removeprefix("$ ").removesuffix(" %")}</td><td>{percent}</td>'


def sec_row(label, *values):
    return f'<tr><td>{label}</td>{"".join(sec_cells(value) for value in values)}</tr>'


def heading(*labels):
    """The heading row: 'Item' over the labels, then each label over its three value cells."""
    return '<tr><th>Item</th>' + ''.join(f'<th colspan="3">{label}</th>' for label in labels) + '</tr>'


def text_cell(text, reason=None):
    return (text, '@', text, reason)


def test_own_percent_sign_proves_a_percent():
    table = prepared(heading('2025') + sec_row('Gross margin', '15.7 %'))
    assert cell_rows(table) == [[text_cell('Gross margin'), (Decimal('0.157'), '0.0%', '15.7 %', None)]]


CAPITAL_RATIOS = heading('2025') + sec_row('CET1 capital ratio', '15.7 %')


def test_percent_fact_proves_a_plain_value():
    """JPM capital ratios: a pure fact at scale -2 proves '13.8' beneath '15.7 %'."""
    table = prepared(CAPITAL_RATIOS + sec_row('Tier 1 capital ratio', fact('13.8')))
    assert cell_rows(table) == [
        [text_cell('CET1 capital ratio'), (Decimal('0.157'), '0.0%', '15.7 %', None)],
        [text_cell('Tier 1 capital ratio'), (Decimal('0.138'), '0.0%', '13.8', None)],
    ]
    assert table.status == 'exported'


def test_percent_fact_sign_is_applied_once():
    """BAC #146: the displayed parentheses and sign="-" are the same sign."""
    table = prepared(heading('Change') + sec_row('Net interest yield', '(' + fact('0.3', sign='-') + ')'))
    assert cell_rows(table) == [[text_cell('Net interest yield'), (Decimal('-0.003'), '0.0%;(0.0%)', '(0.3)', None)]]


@pytest.mark.parametrize('value, expected', [
    (fact('13.8', scale='-4'), text_cell('13.8', _UNPROVEN)),
    (fact('13.8', unit='U_years', scale='-1', name='us-gaap:ExpectedTerm'), text_cell('13.8', _UNPROVEN)),
    (fact('13.8', unit='U_USD', scale='6', name='us-gaap:Revenues'), (Decimal('13.8'), '#,##0.0', '13.8', None)),
    (fact(fact('13.8')), text_cell('13.8', _UNPROVEN)),  # a nested fact is a second fact
    (fact('13.8', format='ixt:num-comma-decimal'), text_cell('13.8', _UNPROVEN)),
    (fact('13.8', sign='-'), text_cell('13.8', _UNPROVEN)),
], ids=['scale-4', 'years-scale-1', 'amount-fact', 'two-facts', 'transformed-format', 'sign-mismatch'])
def test_facts_that_do_not_prove_a_percent(value, expected):
    table = prepared(CAPITAL_RATIOS + sec_row('Tier 1 capital ratio', value))
    assert cell_rows(table)[1] == [text_cell('Tier 1 capital ratio'), expected]


def test_percent_change_header_proves_its_plain_values():
    """RDDT: '% Change' over '54 %' and '(75)'."""
    table = prepared(heading('2025', '2024', '% Change')
                     + sec_row('Revenue', '$ 1,300', '$ 844', '54 %')
                     + sec_row('Net income (loss)', '(45)', '(180)', '(75)'))
    assert table.headers == ('Item', '2025', '2024', '% Change')
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1300'), '"$"#,##0', '$ 1,300', None),
         (Decimal('844'), '"$"#,##0', '$ 844', None), (Decimal('0.54'), '0%', '54 %', None)],
        [text_cell('Net income (loss)'), (Decimal('-45'), '#,##0;(#,##0)', '(45)', None),
         (Decimal('-180'), '#,##0;(#,##0)', '(180)', None), (Decimal('-0.75'), '0%;(0%)', '(75)', None)],
    ]


def test_percent_of_retained_loans_header_proves_its_plain_values():
    """JPM: 'Percent of retained loans to total retained loans' beside the loan amounts."""
    table = prepared(heading('2025', 'Percent of retained loans to total retained loans')
                     + sec_row('Consumer, excluding credit card', '$ 412,850', '30.9')
                     + sec_row('Credit card', '233,145', '17.4'), before='<p>(in millions)</p>')
    assert cell_rows(table) == [
        [text_cell('Consumer, excluding credit card'), (Decimal('412850'), '"$"#,##0', '$ 412,850', None),
         (Decimal('0.309'), '0.0%', '30.9', None)],
        [text_cell('Credit card'), (Decimal('233145'), '#,##0', '233,145', None),
         (Decimal('0.174'), '0.0%', '17.4', None)],
    ]


def test_percent_header_never_proves_values_that_share_its_leaf():
    """Rulings 7 and 10: NFLX #13's '$ | 1,323,096 | 7 | %' under one '% Change' leaf. The
    header cannot say which value it describes, so only the '%' proves the percent, and the
    amount it still declares a percent is flagged rather than scaled."""
    table = prepared('<tr><th>Item</th><th colspan="4">% Change</th></tr>'
                     '<tr><td>Revenue</td><td>$</td><td>1,323,096</td><td>7</td><td>%</td></tr>')
    assert table.headers == ('Item', '% Change', '% Change', '% Change', '% Change')
    assert cell_rows(table) == [[text_cell('Revenue'), text_cell('$'), text_cell('1,323,096', _UNPROVEN),
                                 (Decimal('0.07'), '0%', '7 %', None), (None, '@', '', None)]]
    assert table.issues == (f'Source row 1, column 2: {_UNPROVEN}',)


def test_shared_percent_header_flags_values_it_cannot_prove():
    """Ruling 10: a '%' leaf over two values per row cannot say which value it describes,
    yet declares percents, so plain values under it are flagged, never percentage points."""
    table = prepared('<tr><th>Item</th><th colspan="2">%</th></tr>'
                     '<tr><td>Revenue</td><td>100</td><td>100</td></tr>'
                     '<tr><td>Cost of revenue</td><td>18</td><td>19</td></tr>')
    assert table.headers == ('Item', '%', '%')
    assert cell_rows(table) == [
        [text_cell('Revenue'), text_cell('100', _UNPROVEN), text_cell('100', _UNPROVEN)],
        [text_cell('Cost of revenue'), text_cell('18', _UNPROVEN), text_cell('19', _UNPROVEN)],
    ]
    assert table.issues == tuple(f'Source row {r}, column {c}: {_UNPROVEN}' for r in (1, 2) for c in (1, 2))


@pytest.mark.parametrize('rows, headers, body_row', [
    ('<tr><th>Item</th><th colspan="2">Shares</th></tr><tr><th></th><th colspan="2">% Change</th></tr>'
     '<tr><td>Revenue</td><td>100</td><td>18</td></tr>', ('Item', 'Shares — % Change', 'Shares — % Change'), 2),
    ('<tr><th>Item</th><th colspan="2">% Change</th></tr><tr><td>Shares outstanding</td><td>100</td><td>18</td></tr>',
     ('Item', '% Change', '% Change'), 1),
], ids=['column-unit', 'row-unit'])
def test_withheld_percent_header_still_conflicts_with_a_unit(rows, headers, body_row):
    """Ruling 11: withholding a shared leaf's percent header removes its proof, not its
    conflict with a non-percent unit on the column or the row."""
    table = prepared(rows)
    assert table.headers == headers
    assert [row[1:] for row in cell_rows(table)] == [[text_cell('100', _CONFLICT), text_cell('18', _CONFLICT)]]
    assert table.issues == tuple(f'Source row {body_row}, column {c}: {_CONFLICT}' for c in (1, 2))


def test_table_wide_declaration_never_scales_values_that_share_a_leaf():
    """Ruling 11: '(in percentages)' over NFLX's 'Change' leaf proves neither value it heads."""
    table = prepared('<tr><th>Item</th><th colspan="4">Change</th></tr>'
                     '<tr><td>Revenue</td><td>$</td><td>1,323,096</td><td>7</td><td>%</td></tr>',
                     before='<p>(in percentages)</p>')
    assert cell_rows(table) == [[text_cell('Revenue'), text_cell('$'), text_cell('1,323,096', _UNPROVEN),
                                 (Decimal('0.07'), '0%', '7 %', None), (None, '@', '', None)]]
    assert table.issues == (f'Source row 1, column 2: {_UNPROVEN}',)


def test_table_wide_declaration_never_proves_a_shared_percent_leaf():
    table = prepared('<tr><th>Item</th><th colspan="2">%</th></tr><tr><td>Revenue</td><td>100</td><td>18</td></tr>',
                     before='<p>(in percentages)</p>')
    assert cell_rows(table) == [[text_cell('Revenue'), text_cell('100', _UNPROVEN), text_cell('18', _UNPROVEN)]]
    assert table.issues == tuple(f'Source row 1, column {c}: {_UNPROVEN}' for c in (1, 2))


def test_percent_row_label_proves_its_plain_value():
    table = prepared(heading('2025') + sec_row('Net revenue', '$ 1,000') + sec_row('% of net revenue', '26'))
    assert cell_rows(table) == [
        [text_cell('Net revenue'), (Decimal('1000'), '"$"#,##0', '$ 1,000', None)],
        [text_cell('% of net revenue'), (Decimal('0.26'), '0%', '26', None)],
    ]
    assert table.status == 'exported'


def test_nvda_table_wide_sentence_makes_plain_values_percents():
    sentence = ('<p>The following table sets forth, for the periods indicated, certain items in our '
                'Consolidated Statements of Income expressed as a percentage of revenue.</p>')
    table = prepared(heading('Jan 26, 2025', 'Jan 28, 2024') + sec_row('Revenue', '100.0', '100.0')
                     + sec_row('Cost of revenue', '24.7', '27.3') + sec_row('Gross profit', '75.3', '72.7'),
                     before=sentence)
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1.000'), '0.0%', '100.0', None), (Decimal('1.000'), '0.0%', '100.0', None)],
        [text_cell('Cost of revenue'), (Decimal('0.247'), '0.0%', '24.7', None),
         (Decimal('0.273'), '0.0%', '27.3', None)],
        [text_cell('Gross profit'), (Decimal('0.753'), '0.0%', '75.3', None),
         (Decimal('0.727'), '0.0%', '72.7', None)],
    ]


@pytest.mark.parametrize('before, caption', [
    ('<p>(in percentages)</p>', ''),
    ('', '<tr><th></th><th colspan="6">(in percentages)</th></tr>'),
], ids=['context-line', 'in-table-caption'])
def test_in_percentages_declares_a_percent_table(before, caption):
    table = prepared(caption + heading('2025', '2024') + sec_row('Gross margin', '45.2', '43.1')
                     + sec_row('Operating margin', '(3.5)', '12.0'), before=before)
    assert cell_rows(table) == [
        [text_cell('Gross margin'), (Decimal('0.452'), '0.0%', '45.2', None),
         (Decimal('0.431'), '0.0%', '43.1', None)],
        [text_cell('Operating margin'), (Decimal('-0.035'), '0.0%;(0.0%)', '(3.5)', None),
         (Decimal('0.120'), '0.0%', '12.0', None)],
    ]
    assert table.status == 'exported'


_NOT_DECLARATIONS = ['Percentage of completion revenue', 'Percentage point change',
                     'Increase in percentage of completion revenue']


@pytest.mark.parametrize('position', ['header', 'row label'])
@pytest.mark.parametrize('label', _NOT_DECLARATIONS)
def test_percent_words_that_are_not_declarations_keep_plain_values(label, position):
    header, last = (label, 'Other') if position == 'header' else ('2025', label)
    table = prepared(heading(header) + sec_row('Revenue', '1,250') + sec_row('Cost of revenue', '(310)')
                     + sec_row(last, '12.5'))
    assert [row[1] for row in cell_rows(table)] == [
        (Decimal('1250'), '#,##0', '1,250', None), (Decimal('-310'), '#,##0;(#,##0)', '(310)', None),
        (Decimal('12.5'), '#,##0.0', '12.5', None)]


def test_meta_plain_rows_between_percent_rows_are_unproven():
    """META MD&A: '%' on the first row and the total only; the rows between stay text."""
    table = prepared(heading('2025', '2024') + sec_row('Revenue', '100 %', '100 %')
                     + sec_row('Cost of revenue', '18', '19') + sec_row('Research and development', '25', '27')
                     + sec_row('Income from operations', '42 %', '35 %'))
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1.00'), '0%', '100 %', None), (Decimal('1.00'), '0%', '100 %', None)],
        [text_cell('Cost of revenue'), text_cell('18', _UNPROVEN), text_cell('19', _UNPROVEN)],
        [text_cell('Research and development'), text_cell('25', _UNPROVEN), text_cell('27', _UNPROVEN)],
        [text_cell('Income from operations'), (Decimal('0.42'), '0%', '42 %', None),
         (Decimal('0.35'), '0%', '35 %', None)],
    ]
    assert table.issues == tuple(f'Source row {r}, column {c}: {_UNPROVEN}' for r in (2, 3) for c in (1, 4))
    assert table.status == 'needs_review'


def test_jpm_amount_and_ratio_rows_without_proof_are_unproven():
    """JPM #64: '$ 275,513' and '15.7 %' convert; '294,881' and '16.8' stay text."""
    table = prepared(heading('2025') + sec_row('CET1 capital', '$ 275,513') + sec_row('Tier 1 capital', '294,881')
                     + sec_row('CET1 capital ratio', '15.7 %') + sec_row('Tier 1 capital ratio', '16.8'))
    assert cell_rows(table) == [
        [text_cell('CET1 capital'), (Decimal('275513'), '"$"#,##0', '$ 275,513', None)],
        [text_cell('Tier 1 capital'), text_cell('294,881', _UNPROVEN)],
        [text_cell('CET1 capital ratio'), (Decimal('0.157'), '0.0%', '15.7 %', None)],
        [text_cell('Tier 1 capital ratio'), text_cell('16.8', _UNPROVEN)],
    ]
    assert table.issues == (f'Source row 2, column 1: {_UNPROVEN}', f'Source row 4, column 1: {_UNPROVEN}')


def test_zero_in_a_percent_column_converts():
    table = prepared(heading('2025') + sec_row('Revenue', '100 %') + sec_row('Cost of revenue', '0'))
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1.00'), '0%', '100 %', None)],
        [text_cell('Cost of revenue'), (Decimal('0'), '#,##0', '0', None)],
    ]
    assert table.status == 'exported'


def test_negative_zero_in_a_percent_column_keeps_its_reason():
    table = prepared(heading('2025') + sec_row('Revenue', '100 %') + sec_row('Cost of revenue', '(0)'))
    assert cell_rows(table)[1] == [text_cell('Cost of revenue'), text_cell('(0)', _NEGATIVE_ZERO)]


@pytest.mark.parametrize('caption', [
    '(in millions, except percentages)',
    '(In thousands, except share, per share and percentage data)',
])
def test_except_caption_never_makes_amounts_percents(caption):
    table = prepared(heading('2025', '2024') + sec_row('Revenue', '$ 161,690', '$ 134,902')
                     + sec_row('Cost of revenue', '30,161', '25,959'), before=f'<p>{caption}</p>')
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('161690'), '"$"#,##0', '$ 161,690', None),
         (Decimal('134902'), '"$"#,##0', '$ 134,902', None)],
        [text_cell('Cost of revenue'), (Decimal('30161'), '#,##0', '30,161', None),
         (Decimal('25959'), '#,##0', '25,959', None)],
    ]


@pytest.mark.parametrize('header, value, shown', [
    ('% Change', '$ 12', '$ 12'),
    ('2025', fact('50', unit='U_USD', scale='6', name='us-gaap:Revenues') + ' %', '50 %'),
    ('2025', fact('50', scale='-4') + ' %', '50 %'),
], ids=['dollar-under-percent-header', 'percent-with-amount-fact', 'percent-with-pure-fact-scale-4'])
def test_conflicting_percent_proofs_keep_text(header, value, shown):
    table = prepared(heading(header) + sec_row('Revenue', value))
    assert cell_rows(table) == [[text_cell('Revenue'), text_cell(shown, _CONFLICT)]]
    assert table.status == 'needs_review'


@pytest.mark.parametrize('text, declared', [
    ('% Change', True),
    ('% of Total Revenues', True),
    ('Total % of IG', True),
    ('Gross margin %', True),
    ('Tax rate (%)', True),
    ('Percentage', True),
    ('Percent change', True),
    ('As a percentage of total net revenues (1)', True),
    ('Percent of retained loans to total retained loans', True),
    ('Operating margin (percent)', True),
    ('Percentage of completion revenue', False),
    ('Percentage point change', False),
    ('Increase in percentage of completion revenue', False),
    ('$ and % Change', False),
    ('% Change (points)', False),
    ('% Change (pts)', False),
])
def test_percent_declaration(text, declared):
    assert xlsx_tables._percent_declaration(text) is declared


@pytest.mark.parametrize('line, declared', [
    ('(in percent)', True),
    ('(In percentages)', True),
    ('(as a percentage of revenue)', True),
    ('(as a percentage of total revenue)', True),
    ('Expressed as a percentage of revenue', True),  # _UNIT_DECLARATION alternative 2
    ('The following table sets forth, for the periods indicated, certain items in our Consolidated '
     'Statements of Income expressed as a percentage of revenue.', True),  # alternative 3 (NVDA)
    ('In percent', False),
    ('in percentages', False),
    ('(in percent', False),
    ('in percentages)', False),
    ('as a percentage of revenue)', False),
    ('(In thousands, except share, per share and percentage data)', False),
])
def test_table_percent_declaration(line, declared):
    """A7: the table-wide forms are the spec's list, parenthesised, plus _UNIT_DECLARATION
    alternatives 2 and 3."""
    assert xlsx_tables._table_percent_declaration(line) is declared


# --- Rule I: identifier columns, per-cell quantity proof (I1, I2) -----------------------


def test_identifier_heading_converts_only_cells_with_their_own_dollar():
    """JPM #91: 'Within 1 year(a)' over '$ 21,442' and '19,404'."""
    table = prepared(heading('Within 1 year(a)') + sec_row('Residential real estate', '$ 21,442')
                     + sec_row('Auto and other', '19,404'))
    assert table.headers == ('Item', 'Within 1 year(a)')
    assert cell_rows(table) == [
        [text_cell('Residential real estate'), (Decimal('21442'), '"$"#,##0', '$ 21,442', None)],
        [text_cell('Auto and other'), text_cell('19,404', _QUANTITIES)],
    ]
    assert table.issues == (f'Source row 2, column 1: {_QUANTITIES}',)
    assert table.status == 'needs_review'


def test_facts_under_an_identifier_heading_convert():
    """TSM #150: 'Other Changes (Note)' over tagged amounts."""
    amount = {'unit': 'U_USD', 'scale': '9', 'name': 'ifrs-full:OtherChangesLiabilitiesArisingFromFinancingActivities'}
    table = prepared(heading('Other Changes (Note)')
                     + sec_row('Short-term loans', '$ (' + fact('589.3', sign='-', **amount) + ')')
                     + sec_row('Bonds payable', fact('303.4', **amount))
                     + sec_row('Long-term bank loans', '(' + fact('5.2', sign='-', **amount) + ')'))
    assert table.headers == ('Item', 'Other Changes (Note)')
    assert cell_rows(table) == [
        [text_cell('Short-term loans'), (Decimal('-589.3'), '"$"#,##0.0;("$"#,##0.0)', '$ (589.3)', None)],
        [text_cell('Bonds payable'), (Decimal('303.4'), '#,##0.0', '303.4', None)],
        [text_cell('Long-term bank loans'), (Decimal('-5.2'), '#,##0.0;(#,##0.0)', '(5.2)', None)],
    ]
    assert table.status == 'exported'


def test_split_percent_signs_under_an_identifier_heading_convert_after_attachment():
    """NVDA 10-Q 2027-Q1 #32: 'Year-over-Year Change' heads the values, and each '%' sits in
    an unheaded cell of its own. A points value keeps its own reason (Ruling 4)."""
    table = prepared('<tr><th>Item</th><th>Year-over-Year Change</th><th></th></tr>'
                     '<tr><td>Revenue</td><td>85</td><td>%</td></tr>'
                     '<tr><td>Gross margin</td><td>14.4 pts</td><td></td></tr>'
                     '<tr><td>Operating expenses</td><td>(30)</td><td>%</td></tr>')
    assert table.headers == ('Item', 'Year-over-Year Change')
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('0.85'), '0%', '85 %', None)],
        [text_cell('Gross margin'), text_cell('14.4 pts', _POINTS_REASON)],
        [text_cell('Operating expenses'), (Decimal('-0.30'), '0%;(0%)', '(30) %', None)],
    ]
    # Each '%' joined its value; the emptied '%' column is not kept.
    assert [row[1] for row in table.cell_sources] == [((1, 1), (1, 2)), ((2, 1),), ((3, 1), (3, 2))]
    assert table.issues == (f'Source row 2, column 1: {_POINTS_REASON}',)


def test_one_dollar_cell_never_converts_the_note_references_beside_it():
    """Codex's counterexample: 'Notes' over '7', '8' and '$ 12'."""
    table = prepared(heading('Notes') + sec_row('Cash', '7') + sec_row('Receivables', '8')
                     + sec_row('Other', '$ 12'))
    assert cell_rows(table) == [
        [text_cell('Cash'), text_cell('7', _QUANTITIES)],
        [text_cell('Receivables'), text_cell('8', _QUANTITIES)],
        [text_cell('Other'), (Decimal('12'), '"$"#,##0', '$ 12', None)],
    ]
    assert table.issues == tuple(f'Source row {r}, column 1: {_QUANTITIES}' for r in (1, 2))


@pytest.mark.parametrize('header, label, value', [
    ('Notes', 'Property, plant and equipment', '7'),
    ('Exhibit', 'Amended and Restated Bylaws', '3.1'),
    ('Filing Date', 'Amended and Restated Bylaws', '07/09/2015'),
    ('Maturities (calendar year)', 'Senior unsecured notes', '2028'),
    ('Incorporated by Reference', 'Amended and Restated Bylaws', '10-Q'),
], ids=['notes', 'exhibit', 'filing-date', 'maturity-year', 'form-type'])
def test_true_identifiers_stay_unflagged_text(header, label, value):
    table = prepared(f'<tr><th>Item</th><th>{header}</th></tr><tr><td>{label}</td><td>{value}</td></tr>')
    assert table.headers == ('Item', header)
    assert cell_rows(table) == [[text_cell(label), text_cell(value)]]
    assert table.issues == ()
    assert table.status == 'exported'


def test_dollar_inside_an_exhibit_description_proves_nothing():
    table = prepared('<tr><th>Exhibit Number</th><th>Exhibit Description</th></tr>'
                     '<tr><td>4.1</td><td>Indenture, dated as of February 5, 2015</td></tr>'
                     '<tr><td>10.1</td><td>Credit Agreement for a $1,000,000 revolving facility, '
                     'dated as of May 2, 2017</td></tr>')
    assert table.headers == ('Exhibit Number', 'Exhibit Description')
    assert cell_rows(table) == [
        [text_cell('4.1'), text_cell('Indenture, dated as of February 5, 2015')],
        [text_cell('10.1'), text_cell('Credit Agreement for a $1,000,000 revolving facility, dated as of May 2, 2017')],
    ]
    assert table.issues == ()


def test_amount_formatted_cells_without_quantity_evidence_are_flagged():
    """CAT #12 without its '$' rows: '13,373' and '(154)' are formatted as amounts, '164' is not."""
    table = prepared(heading('Full Year 2024') + sec_row('Profit', '13,373') + sec_row('Restructuring costs', '164')
                     + sec_row('Pension/OPEB mark-to-market (gains) losses', '(154)'))
    assert table.headers == ('Item', 'Full Year 2024')
    assert cell_rows(table) == [
        [text_cell('Profit'), text_cell('13,373', _AMOUNT_FORMATTED)],
        [text_cell('Restructuring costs'), text_cell('164')],
        [text_cell('Pension/OPEB mark-to-market (gains) losses'), text_cell('(154)', _AMOUNT_FORMATTED)],
    ]
    assert table.issues == tuple(f'Source row {r}, column 1: {_AMOUNT_FORMATTED}' for r in (1, 3))
    assert table.status == 'needs_review'


# --- Ruling 21: a percent proof never overrides contrary evidence (final review) --------

_RATE_ROWS = (sec_row('Risk-free interest rate', '4.2', '3.9'), sec_row('Expected volatility', '45', '50'))
_RATES = ([text_cell('Risk-free interest rate'), (Decimal('0.042'), '0.0%', '4.2', None),
           (Decimal('0.039'), '0.0%', '3.9', None)],
          [text_cell('Expected volatility'), (Decimal('0.45'), '0%', '45', None), (Decimal('0.50'), '0%', '50', None)])


@pytest.mark.parametrize('label', [
    'Expected term (in years)', 'Vesting period (months)', 'Remaining life in years', 'Average life, years',
    'Days sales outstanding', 'Times interest earned', 'Interest coverage (times)', 'Net leverage ratio (x)',
    'Credit spread (bps)', 'Change in spread, basis points', 'Gross margin change (percentage points)',
])
def test_row_label_naming_another_unit_conflicts_with_a_table_wide_declaration(label):
    """Ruling 21 (A1): '(in percent)' declares the table percents, but a row label naming
    another unit contradicts it on that row. Its values are conflict text, never 0.055;
    the other rows keep the declaration."""
    table = prepared(heading('2025', '2024') + _RATE_ROWS[0] + sec_row(label, '5.5', '6.0') + _RATE_ROWS[1],
                     before='<p>(in percent)</p>')
    assert cell_rows(table) == [
        _RATES[0], [text_cell(label), text_cell('5.5', _CONFLICT), text_cell('6.0', _CONFLICT)], _RATES[1]]
    assert table.issues == tuple(f'Source row 2, column {c}: {_CONFLICT}' for c in (1, 4))
    assert table.status == 'needs_review'


@pytest.mark.parametrize('header, value, shown', [
    ('2025', '5.5 %', '5.5 %'),
    ('% Change', '5.5', '5.5'),
    ('2025', fact('5.5'), '5.5'),
], ids=['own-percent', 'percent-header', 'percent-fact'])
def test_row_label_naming_another_unit_conflicts_with_every_percent_proof(header, value, shown):
    """Ruling 21 (A1): the row's other unit conflicts with the cell's own '%', a percent
    heading and a percent fact alike."""
    table = prepared(heading(header) + sec_row('Expected term (in years)', value))
    assert cell_rows(table) == [[text_cell('Expected term (in years)'), text_cell(shown, _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 1: {_CONFLICT}',)
    assert table.status == 'needs_review'


def test_row_labels_that_name_no_unit_keep_the_table_wide_declaration():
    """'Six months ended June 30' names a period and 'Changes in prior years' tax positions'
    a time, not a unit of their values: the table-wide declaration still proves them."""
    table = prepared(heading('2025', '2024') + _RATE_ROWS[0] + sec_row('Six months ended June 30', '5.5', '6.0')
                     + sec_row("Changes in prior years' tax positions", '(0.3)', '0.2'), before='<p>(in percent)</p>')
    assert cell_rows(table) == [
        _RATES[0],
        [text_cell('Six months ended June 30'), (Decimal('0.055'), '0.0%', '5.5', None),
         (Decimal('0.060'), '0.0%', '6.0', None)],
        [text_cell("Changes in prior years' tax positions"), (Decimal('-0.003'), '0.0%;(0.0%)', '(0.3)', None),
         (Decimal('0.002'), '0.0%', '0.2', None)]]
    assert table.status == 'exported'


@pytest.mark.parametrize('first', ['$ 1,000', fact('1,000', unit='U_USD', scale='6', name='us-gaap:Revenues')],
                         ids=['dollar', 'amount-fact'])
def test_cell_level_amount_withholds_a_table_wide_declaration_from_its_column(first):
    """Ruling 21 (A2): under '(in percentages)' a column holding a cell's own '$' or amount
    fact takes no table-wide proof, so its plain values are P4 text, never 5.00. Its own
    '%' still proves a percent, and a column without such a cell keeps the declaration."""
    table = prepared(heading('2025', 'Change') + sec_row('Revenue', first, '11.1')
                     + sec_row('Cost of revenue', '500', '25.0') + sec_row('Gross margin', '50 %', '(2.0)'),
                     before='<p>(in percentages)</p>')
    revenue = ((Decimal('1000'), '"$"#,##0', '$ 1,000', None) if first.startswith('$')
               else (Decimal('1000'), '#,##0', '1,000', None))
    assert cell_rows(table) == [
        [text_cell('Revenue'), revenue, (Decimal('0.111'), '0.0%', '11.1', None)],
        [text_cell('Cost of revenue'), text_cell('500', _UNPROVEN), (Decimal('0.250'), '0.0%', '25.0', None)],
        [text_cell('Gross margin'), (Decimal('0.50'), '0%', '50 %', None),
         (Decimal('-0.020'), '0.0%;(0.0%)', '(2.0)', None)],
    ]
    assert table.issues == (f'Source row 2, column 1: {_UNPROVEN}',)
    assert table.status == 'needs_review'


def test_dollar_cell_withholds_a_percent_heading_from_its_column():
    """Ruling 21: a '$' amount under '% Change' contradicts the heading for its whole
    column. The '$' cell keeps its conflict (spec Testing 11) and the heading proves no
    other value there: '5' is P4 text, never 0.05. A zero still converts."""
    table = prepared(heading('2025', '% Change') + sec_row('Revenue', '$ 1,000', '$ 12')
                     + sec_row('Cost of revenue', '400', '5') + sec_row('Other', '10', '0'))
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1000'), '"$"#,##0', '$ 1,000', None), text_cell('$ 12', _CONFLICT)],
        [text_cell('Cost of revenue'), (Decimal('400'), '#,##0', '400', None), text_cell('5', _UNPROVEN)],
        [text_cell('Other'), (Decimal('10'), '#,##0', '10', None), (Decimal('0'), '#,##0', '0', None)],
    ]
    assert table.issues == (f'Source row 1, column 4: {_CONFLICT}', f'Source row 2, column 4: {_UNPROVEN}')


@pytest.mark.parametrize('header, label, before', [
    ('% Change', 'Revenue', ''),
    ('2025', '% of net revenue', ''),
    ('2025', 'Revenue', '<p>(in percentages)</p>'),
], ids=['percent-header', 'percent-row-label', 'table-wide'])
@pytest.mark.parametrize('scale', ['0', '-4'])
def test_pure_fact_off_scale_conflicts_with_every_percent_proof(header, label, before, scale):
    """Ruling 21 (A3): a pure fact whose scale is not -2 says the value is no percent of
    that scale; under a percent heading, row label or table-wide declaration it is a
    conflict, never 0.35."""
    table = prepared(heading(header) + sec_row(label, fact('35', scale=scale)), before=before)
    assert cell_rows(table) == [[text_cell(label), text_cell('35', _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 1: {_CONFLICT}',)


def test_amount_heading_under_a_table_wide_declaration_proves_nothing():
    """Ruling 8 as amended by Ruling 21 (A4): under '(in percentages)' an amount heading
    ('Total') neither proves its plain values percents nor exports them as displayed
    numbers (percentage points): they are P4 text, a zero aside. The other column keeps
    the declaration."""
    table = prepared(heading('2025', 'Total') + sec_row('Gross margin', '45.2', '43.1')
                     + sec_row('Operating margin', '12.0', '11.5') + sec_row('Other', '0.5', '0'),
                     before='<p>(in percentages)</p>')
    assert cell_rows(table) == [
        [text_cell('Gross margin'), (Decimal('0.452'), '0.0%', '45.2', None), text_cell('43.1', _UNPROVEN)],
        [text_cell('Operating margin'), (Decimal('0.120'), '0.0%', '12.0', None), text_cell('11.5', _UNPROVEN)],
        [text_cell('Other'), (Decimal('0.005'), '0.0%', '0.5', None), (Decimal('0'), '#,##0', '0', None)],
    ]
    assert table.issues == (f'Source row 1, column 4: {_UNPROVEN}', f'Source row 2, column 4: {_UNPROVEN}')


def test_own_proofs_under_an_amount_heading_and_a_table_wide_declaration_stand():
    """Ruling 8 as amended: an amount heading withholds only the table-wide declaration.
    A cell's own '%', its own '$' and a percent heading keep proving their values."""
    table = prepared(heading('Total', '% of Total Revenues') + sec_row('Revenue', '$ 1,000', '100.0')
                     + sec_row('Gross margin', '45.2 %', '45.2'), before='<p>(in percentages)</p>')
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1000'), '"$"#,##0', '$ 1,000', None),
         (Decimal('1.000'), '0.0%', '100.0', None)],
        [text_cell('Gross margin'), (Decimal('0.452'), '0.0%', '45.2 %', None),
         (Decimal('0.452'), '0.0%', '45.2', None)],
    ]
    assert table.status == 'exported'


@pytest.mark.parametrize('label', ['% Change in NT$ from 2023 to 2024', 'Percent Change 2024 versus 2023',
                                   '$ and % Change'])
def test_heading_naming_a_percent_without_declaring_one_flags_plain_values(label):
    """Ruling 21 (A5): TSM's '% Change in NT$ from …' and KO's 'Percent Change 2024 versus
    2023' name a percent but are no declaration. Their plain values may be percents, so
    they are P4 text, never 33.9; a zero still converts."""
    table = prepared(heading('2024', label) + sec_row('Net revenue', '$ 2,894,308', '33.9')
                     + sec_row('Cost of revenue', '1,269,954', '(5.2)') + sec_row('Other', '10', '0'))
    assert table.headers == ('Item', '2024', label)
    assert cell_rows(table) == [
        [text_cell('Net revenue'), (Decimal('2894308'), '"$"#,##0', '$ 2,894,308', None),
         text_cell('33.9', _UNPROVEN)],
        [text_cell('Cost of revenue'), (Decimal('1269954'), '#,##0', '1,269,954', None),
         text_cell('(5.2)', _UNPROVEN)],
        [text_cell('Other'), (Decimal('10'), '#,##0', '10', None), (Decimal('0'), '#,##0', '0', None)],
    ]
    assert table.issues == tuple(f'Source row {r}, column 4: {_UNPROVEN}' for r in (1, 2))
    assert table.status == 'needs_review'


def test_own_proofs_under_a_heading_naming_a_percent_keep_their_path():
    """Ruling 21 (A5) flags only cells without proof of their own: a cell's own '%', its
    percent fact and its own '$' keep the existing path."""
    table = prepared(heading('Percent Change 2024 versus 2023') + sec_row('Revenue', '12 %')
                     + sec_row('Operating margin', fact('3.5')) + sec_row('Other', '$ 12'))
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('0.12'), '0%', '12 %', None)],
        [text_cell('Operating margin'), (Decimal('0.035'), '0.0%', '3.5', None)],
        [text_cell('Other'), (Decimal('12'), '"$"#,##0', '$ 12', None)],
    ]
    assert table.status == 'exported'


@pytest.mark.parametrize('header', ['LTV under 80 %', '2025 (in millions, except percentages)'])
def test_number_percent_and_except_clause_in_a_heading_name_no_percent(header):
    """A number's own percent sign and an except clause name no percent of the column: its
    amounts keep their numbers."""
    table = prepared(heading(header) + sec_row('Revenue', '1,250') + sec_row('Cost of revenue', '(310)'))
    assert [row[1] for row in cell_rows(table)] == [
        (Decimal('1250'), '#,##0', '1,250', None), (Decimal('-310'), '#,##0;(#,##0)', '(310)', None)]
    assert table.status == 'exported'


def test_percent_sign_spanning_two_rows_never_attaches():
    """A6: a '%' spanning two rows names no one row's value. It is refused for both rows it
    spans (Ruling 23), so '4' and '5' are P4 text, never 0.04."""
    table = prepared('<tr><th>Item</th><th>2025</th><th></th></tr>'
                     '<tr><td>Gross margin</td><td>4</td><td rowspan="2">%</td></tr>'
                     '<tr><td>Operating margin</td><td>5</td></tr>')
    assert cell_rows(table) == [
        [text_cell('Gross margin'), text_cell('4', _UNPROVEN), _STRAY],
        [text_cell('Operating margin'), text_cell('5', _UNPROVEN), _EMPTY],
    ]
    assert table.cell_sources == ((((1, 0),), ((1, 1),), ((1, 2),)), (((2, 0),), ((2, 1),), ()))


def test_conflict_reason_outranks_the_identifier_reason():
    """Ruling 12: under an identifier heading a cell whose units conflict keeps the conflict
    reason, not the I2 reason, while the column's other cells keep theirs."""
    table = prepared(heading('Notes') + sec_row('Payout per share (%)', '12') + sec_row('Cash', '13,373'))
    assert cell_rows(table) == [[text_cell('Payout per share (%)'), text_cell('12', _CONFLICT)],
                                [text_cell('Cash'), text_cell('13,373', _AMOUNT_FORMATTED)]]
    assert table.issues == (f'Source row 1, column 1: {_CONFLICT}', f'Source row 2, column 1: {_AMOUNT_FORMATTED}')


def test_refused_split_percent_flags_a_value_with_its_own_dollar():
    """Ruling 13: the safety net applies literally. The '%' under '% change' is refused for
    the amount under '2025', so '$ 1,000' is P4 text, though its own '$' proves an amount."""
    table = prepared('<tr><th>Item</th><th colspan="2">2025</th><th colspan="2">% change</th></tr>'
                     '<tr><td>Revenue</td><td>$</td><td>1,000</td><td></td><td>%</td></tr>')
    assert cell_rows(table) == [[text_cell('Revenue'), text_cell('$ 1,000', _UNPROVEN), _EMPTY, _STRAY]]
    assert table.cell_sources == ((((1, 0),), ((1, 1), (1, 2)), ((1, 3),), ((1, 4),)),)
    assert table.issues == (f'Source row 1, column 1: {_UNPROVEN}',)


# --- Ruling 21, completed (final fix round 2) ------------------------------------------

_YEARS_FACT = fact('5.5', unit='U_years', scale='-1', name='us-gaap:ExpectedTerm')


def test_spanning_percent_sign_never_joins_through_column_grouping():
    """R1 (Ruling 23): '2025' heads the value and the '%' spanning two rows. Column grouping must not
    join that '%' to '4' either: both values beside it are P4 text, never 0.04."""
    table = prepared('<tr><th>Item</th><th colspan="2">2025</th></tr>'
                     '<tr><td>Revenue</td><td>4</td><td rowspan="2">%</td></tr>'
                     '<tr><td>Cost</td><td>6</td></tr>')
    assert table.headers == ('Item', '2025', '2025')
    assert cell_rows(table) == [[text_cell('Revenue'), text_cell('4', _UNPROVEN), _STRAY],
                                [text_cell('Cost'), text_cell('6', _UNPROVEN), _EMPTY]]
    assert table.cell_sources == ((((1, 0),), ((1, 1),), ((1, 2),)), (((2, 0),), ((2, 1),), ()))
    assert table.issues == tuple(f'Source row {r}, column 1: {_UNPROVEN}' for r in (1, 2))
    assert table.status == 'needs_review'


def test_spanning_percent_sign_never_joins_through_the_marker_column_merge():
    """R1 (Ruling 23): a column of '%' signs merges into its values, but not the '%' spanning two rows:
    '4' and '5' beside it are P4 text, while C's own '%' still attaches."""
    table = prepared('<tr><th>Item</th><th>2025</th><th></th></tr>'
                     '<tr><td>A</td><td>4</td><td rowspan="2">%</td></tr><tr><td>B</td><td>5</td></tr>'
                     '<tr><td>C</td><td>6</td><td>%</td></tr>')
    assert table.headers == ('Item', '2025', 'Column 3')
    assert cell_rows(table) == [[text_cell('A'), text_cell('4', _UNPROVEN), _STRAY],
                                [text_cell('B'), text_cell('5', _UNPROVEN), _EMPTY],
                                [text_cell('C'), (Decimal('0.06'), '0%', '6 %', None), _EMPTY]]
    assert table.cell_sources == ((((1, 0),), ((1, 1),), ((1, 2),)), (((2, 0),), ((2, 1),), ()),
                                  (((3, 0),), ((3, 1), (3, 2)), ()))
    assert table.issues == ('Missing source header for Column 3; verify its meaning.',
                            f'Source row 1, column 1: {_UNPROVEN}', f'Source row 2, column 1: {_UNPROVEN}')


@pytest.mark.parametrize('before, value, shown', [
    ('<p>(in percentages)</p>', '5.5', '5.5'),
    ('', '5.5 %', '5.5 %'),
    ('', fact('5.5'), '5.5'),
], ids=['table-wide', 'own-percent', 'percent-fact'])
def test_heading_naming_another_unit_conflicts_with_every_percent_proof(before, value, shown):
    """R2a: a column heading naming another unit contradicts every percent claim on its
    cells, as a row label does: conflict text, never 0.055."""
    table = prepared(heading('Expected term (in years)') + sec_row('Options', value), before=before)
    assert cell_rows(table) == [[text_cell('Options'), text_cell(shown, _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 1: {_CONFLICT}',)
    assert table.status == 'needs_review'


def test_period_heading_names_no_unit():
    """'Years Ended December 31,' is period wording, not a unit: the table-wide declaration
    proves the values below it."""
    table = prepared('<tr><th></th><th colspan="6">Years Ended December 31,</th></tr>' + heading('2025', '2024')
                     + sec_row('Gross margin', '45.2', '43.1'), before='<p>(in percentages)</p>')
    assert table.headers == ('Item', 'Years Ended December 31, — 2025', 'Years Ended December 31, — 2024')
    assert cell_rows(table) == [[text_cell('Gross margin'), (Decimal('0.452'), '0.0%', '45.2', None),
                                 (Decimal('0.431'), '0.0%', '43.1', None)]]
    assert table.status == 'exported'


@pytest.mark.parametrize('header, label, before, value, shown', [
    ('% Change', 'Term', '', _YEARS_FACT, '5.5'),
    ('2025', '% of net revenue', '', _YEARS_FACT, '5.5'),
    ('2025', 'Term', '<p>(in percentages)</p>', _YEARS_FACT, '5.5'),
    ('2025', 'Term', '', _YEARS_FACT + ' %', '5.5 %'),
    ('% Change', 'Term', '', fact('5.5', unit='U_missing'), '5.5'),
], ids=['percent-header', 'percent-row-label', 'table-wide', 'own-percent', 'unresolved-unit'])
def test_fact_in_another_unit_conflicts_with_every_percent_proof(header, label, before, value, shown):
    """R2b: a fact that is no pure fact at scale -2 says the value is no percent; a fact in
    years (utr:Y) or in a unit the filing does not define conflicts with every percent
    claim, never 0.055."""
    table = prepared(heading(header) + sec_row(label, value), before=before)
    assert cell_rows(table) == [[text_cell(label), text_cell(shown, _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 1: {_CONFLICT}',)


def test_spanning_row_label_contradicts_every_row_it_covers():
    """R3: 'Expected term (in years)' spans two rows; its unit contradicts the table-wide
    declaration on both, so 6.0 is conflict text too, never 0.060."""
    table = prepared('<tr><th>Item</th><th>2025</th></tr>'
                     '<tr><td rowspan="2">Expected term (in years)</td><td>5.5</td></tr><tr><td>6.0</td></tr>',
                     before='<p>(in percentages)</p>')
    assert cell_rows(table) == [[text_cell('Expected term (in years)'), text_cell('5.5', _CONFLICT)],
                                [_EMPTY, text_cell('6.0', _CONFLICT)]]
    assert table.issues == tuple(f'Source row {r}, column 1: {_CONFLICT}' for r in (1, 2))


def test_spanning_row_label_proves_every_row_it_covers():
    """R3: a spanning percent row label proves both rows (spec P1.4), and a spanning
    'Income per share' keeps both rows out of the table-wide declaration (P2.3)."""
    table = prepared('<tr><th>Item</th><th>2025</th></tr>'
                     '<tr><td>Net revenue</td><td>$ 1,000</td></tr>'
                     '<tr><td rowspan="2">% of net revenue</td><td>26</td></tr><tr><td>27</td></tr>')
    assert cell_rows(table) == [[text_cell('Net revenue'), (Decimal('1000'), '"$"#,##0', '$ 1,000', None)],
                                [text_cell('% of net revenue'), (Decimal('0.26'), '0%', '26', None)],
                                [_EMPTY, (Decimal('0.27'), '0%', '27', None)]]
    assert table.status == 'exported'
    table = prepared('<tr><th>Item</th><th>2025</th></tr><tr><td>Gross margin</td><td>25</td></tr>'
                     '<tr><td rowspan="2">Income per share</td><td>2.50</td></tr><tr><td>2.40</td></tr>',
                     before='<p>(in percentages)</p>')
    assert cell_rows(table) == [[text_cell('Gross margin'), (Decimal('0.25'), '0%', '25', None)],
                                [text_cell('Income per share'), (Decimal('2.50'), '#,##0.00', '2.50', None)],
                                [_EMPTY, (Decimal('2.40'), '#,##0.00', '2.40', None)]]
    assert table.status == 'exported'


def test_identifier_heading_naming_a_percent_flags_plain_values():
    """R4: 'Percent Change Year-over-Year' is an identifier heading that names a percent.
    The identifier rule keeps '33.9' text, and the P4 reason flags it before any I2 reason;
    the cell's own '%' converts, and a zero keeps the I2 reason only."""
    table = prepared(heading('Percent Change Year-over-Year') + sec_row('Gross margin', '33.9')
                     + sec_row('Revenue', '12 %') + sec_row('Other', '0'))
    assert cell_rows(table) == [[text_cell('Gross margin'), text_cell('33.9', _UNPROVEN)],
                                [text_cell('Revenue'), (Decimal('0.12'), '0%', '12 %', None)],
                                [text_cell('Other'), text_cell('0', _QUANTITIES)]]
    assert table.issues == (f'Source row 1, column 1: {_UNPROVEN}', f'Source row 3, column 1: {_QUANTITIES}')
    assert table.status == 'needs_review'


@pytest.mark.parametrize('label', ['Years 1-5'])
def test_unit_words_outside_a_unit_position_name_no_unit(label):
    """R5: a maturity bucket holds a unit word, but names no unit of the row's values: its
    own '%' converts. ('Months of supply' names one: Ruling 25; a rate-shock scenario's
    points unit is contrary evidence: Ruling 26.)"""
    table = prepared(heading('2025') + sec_row(label, '5.2 %'))
    assert cell_rows(table) == [[text_cell(label), (Decimal('0.052'), '0.0%', '5.2 %', None)]]
    assert table.status == 'exported'


def test_scenario_headings_are_contrary_evidence():
    """Ruling 26: '+100 basis points' and '-100 basis points' scenario headings hold a
    points unit, which is contrary evidence in any position: the percents beside them are
    conflict text (a coverage cost, never a wrong number)."""
    table = prepared(heading('+100 basis points', '-100 basis points') + sec_row('Net interest income', '5.2 %', '(4.8) %'))
    assert cell_rows(table) == [[text_cell('Net interest income'), text_cell('5.2 %', _CONFLICT),
                                 text_cell('(4.8) %', _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 1: {_CONFLICT}', f'Source row 1, column 4: {_CONFLICT}')
    assert table.status == 'needs_review'


@pytest.mark.parametrize('label', ['Days payable outstanding', 'Days inventory outstanding', 'Number of days',
                                   'Rate change (in basis points)', 'Rate change in basis points'])
def test_unit_positions_kept_after_narrowing(label):
    """R5 keeps the unit positions: a 'days … outstanding' measure, 'Number of', a unit in
    parentheses or after 'in'. Each conflicts with the row's own '%'."""
    table = prepared(heading('2025') + sec_row(label, '5.2 %'))
    assert cell_rows(table) == [[text_cell(label), text_cell('5.2 %', _CONFLICT)]]


# --- Ruling 24: broad unit matching for contrary evidence -------------------------------

_IN_PERCENTAGES = '<p>(in percentages)</p>'
_NVDA_SENTENCE = ('<p>The following table sets forth, for the periods indicated, certain items in our '
                  'Consolidated Statements of Income expressed as a percentage of revenue.</p>')
_MARGIN_45 = [text_cell('Gross margin'), (Decimal('0.45'), '0%', '45', None)]


@pytest.mark.parametrize('label', [
    # Regressed by the R5 narrowing (e02bb44 gave conflict text).
    'bps change', 'Margin change bps', 'Basis points change', 'Days in inventory', 'Days to maturity',
    'Months to maturity', 'Years to maturity', 'Times covered', 'Days', 'Months', 'Years',
    # Never recognised before Ruling 24.
    'Basis point change', 'bp change', 'Change in margin (basis point)', 'Percentage point change',
    'Change in percentage point', 'Change (pp)', 'pp change', 'Change in points', 'Points change',
    'Leverage ratio x', 'Average years to maturity', 'Duration', 'Lead time (weeks)', 'Weeks',
])
def test_row_label_naming_another_unit_never_takes_a_table_wide_declaration(label):
    """Ruling 24: under '(in percentages)' a row label naming another unit is a conflict,
    never 120 → 1.20."""
    table = prepared(heading('2025') + sec_row('Gross margin', '45') + sec_row(label, '120'), before=_IN_PERCENTAGES)
    assert cell_rows(table) == [_MARGIN_45, [text_cell(label), text_cell('120', _CONFLICT)]]
    assert table.issues == (f'Source row 2, column 1: {_CONFLICT}',)
    assert table.status == 'needs_review'


@pytest.mark.parametrize('before', [_IN_PERCENTAGES, _NVDA_SENTENCE], ids=['in-percentages', 'nvda-sentence'])
@pytest.mark.parametrize('header', ['bps', 'bps change', 'Change (bps)', 'Percentage point change', 'pp',
                                    'Basis Point Change', 'Years', 'Duration'])
def test_heading_naming_another_unit_never_takes_a_table_wide_declaration(header, before):
    """Ruling 24: a column heading naming another unit conflicts with the table-wide
    declaration on its cells; the other column keeps it."""
    table = prepared(heading('2025', header) + sec_row('Gross margin', '45', '120'), before=before)
    assert cell_rows(table) == [_MARGIN_45 + [text_cell('120', _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 4: {_CONFLICT}',)


@pytest.mark.parametrize('label', ['-25 bp', '+50 bps', '+1 percentage point', 'Shock -100 basis points',
                                   '+100 basis points', 'Interest rate shock +200 basis points', '-100 bps',
                                   'Change -25 bp'])
def test_signed_scenarios_are_contrary_evidence(label):
    """Ruling 26 (replacing Ruling 24's exemption): a points unit after a signed number is
    contrary evidence too, so a rate-shock row's own '%' is conflict text."""
    table = prepared(heading('2025') + sec_row(label, '5.2 %'))
    assert cell_rows(table) == [[text_cell(label), text_cell('5.2 %', _CONFLICT)]]
    assert table.status == 'needs_review'


_MATURITY_BUCKETS = ['Less than 1 year', '1-3 years', '1 - 3 Years', '3–5 years', 'More than 5 years', 'Over 10 Years',
                     'Due after ten years', '0-30 days', '30-59 Days', 'Past due - 90 days', 'After 5 Years']


@pytest.mark.parametrize('bucket', _MATURITY_BUCKETS)
def test_maturity_buckets_name_no_unit(bucket):
    """Ruling 24 must-keep: a maturity or aging bucket heading names no unit of its values,
    whether a value has its own '%' or a table-wide declaration proves it."""
    table = prepared(heading(bucket) + sec_row('Weighted average yield', '3.25 %'))
    assert cell_rows(table) == [[text_cell('Weighted average yield'), (Decimal('0.0325'), '0.00%', '3.25 %', None)]]
    table = prepared(heading(bucket) + sec_row('Gross margin', '3.25'), before=_IN_PERCENTAGES)
    assert cell_rows(table) == [[text_cell('Gross margin'), (Decimal('0.0325'), '0.00%', '3.25', None)]]
    assert table.status == 'exported'


@pytest.mark.parametrize('period', ['Year Ended December 31,', 'Three Months Ended September 30,', 'Nine Months Ended',
                                    'Fiscal Years Ended', 'For the Years Ended December 31,', 'Weeks Ended',
                                    '52 Weeks Ended', 'Fiscal Year 2025'])
def test_period_headings_name_no_unit(period):
    """Ruling 24 must-keep: period headings over the years name no unit; a statement's
    '$' amounts and its own-'%' rate keep their values."""
    table = prepared(f'<tr><th></th><th colspan="6">{period}</th></tr>' + heading('2025', '2024')
                     + sec_row('Revenue', '$ 1,000', '$ 900') + sec_row('Effective tax rate', '21.0 %', '20.5 %'))
    assert table.headers == ('Item', f'{period} — 2025', f'{period} — 2024')
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1000'), '"$"#,##0', '$ 1,000', None), (Decimal('900'), '"$"#,##0', '$ 900', None)],
        [text_cell('Effective tax rate'), (Decimal('0.210'), '0.0%', '21.0 %', None),
         (Decimal('0.205'), '0.0%', '20.5 %', None)],
    ]
    assert table.status == 'exported'


def test_nvda_sentence_under_year_ended_headings_keeps_its_percents():
    """Ruling 24 must-keep: NVDA's table-wide sentence over 'Year Ended — Jan 26, 2025'."""
    table = prepared('<tr><th></th><th colspan="6">Year Ended</th></tr>' + heading('Jan 26, 2025', 'Jan 28, 2024')
                     + sec_row('Revenue', '100.0 %', '100.0 %') + sec_row('Cost of revenue', '24.4', '27.3')
                     + sec_row('Gross profit', '75.6', '72.7'), before=_NVDA_SENTENCE)
    assert table.headers == ('Item', 'Year Ended — Jan 26, 2025', 'Year Ended — Jan 28, 2024')
    assert cell_rows(table) == [
        [text_cell('Revenue'), (Decimal('1.000'), '0.0%', '100.0 %', None), (Decimal('1.000'), '0.0%', '100.0 %', None)],
        [text_cell('Cost of revenue'), (Decimal('0.244'), '0.0%', '24.4', None), (Decimal('0.273'), '0.0%', '27.3', None)],
        [text_cell('Gross profit'), (Decimal('0.756'), '0.0%', '75.6', None), (Decimal('0.727'), '0.0%', '72.7', None)],
    ]
    assert table.status == 'exported'


# --- Ruling 25: no 'of' exemption, anchored signed points, more spellings ----------------

_RULING_25_LABELS = [
    # The 'of' exemption is gone: 'Days/Months/Years of …' and 'Number of … of …' name a measure.
    'Number of days of supply', 'Number of days of sales outstanding', 'Number of years of service',
    'Number of months of supply', 'Days of sales outstanding', 'Days of inventory on hand', 'Years of service',
    'Months of supply',
    # A year range or a digit range before bps is no signed scenario.
    'Change 2024-25, bps', 'Change in margin 2024-25 bps', 'Margin change FY24-25 bps', 'Spread 1-10 bps',
    # Hyphenated and abbreviated spellings.
    'Percentage-point change', 'Basis-point change', 'Change (ppt)', 'Change (ppts)', 'Change in ppts',
    'Weighted average life (yrs)', 'Remaining term (yrs.)', 'Term (mos.)', 'Remaining life (in yrs)', 'Term, mos.',
]


@pytest.mark.parametrize('label', _RULING_25_LABELS)
def test_ruling_25_row_labels_never_take_a_table_wide_declaration(label):
    """Ruling 25: each label names another unit, so under '(in percentages)' its value is
    conflict text, never 120 → 1.20."""
    table = prepared(heading('2025') + sec_row('Gross margin', '45') + sec_row(label, '120'), before=_IN_PERCENTAGES)
    assert cell_rows(table) == [_MARGIN_45, [text_cell(label), text_cell('120', _CONFLICT)]]
    assert table.issues == (f'Source row 2, column 1: {_CONFLICT}',)
    assert table.status == 'needs_review'


@pytest.mark.parametrize('header', ['Change 2024-25, bps', 'Number of days of supply', 'Percentage-point change',
                                    'Basis-point change', 'Change (ppt)'])
def test_ruling_25_headings_never_take_nvdas_sentence(header):
    """Ruling 25: as column headings under NVDA's sentence, the same labels conflict."""
    table = prepared(heading('2025', header) + sec_row('Gross margin', '45', '120'), before=_NVDA_SENTENCE)
    assert cell_rows(table) == [_MARGIN_45 + [text_cell('120', _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 4: {_CONFLICT}',)


def test_measure_row_under_a_percent_heading_conflicts():
    """Ruling 25: 'Number of days of supply' under '% of total' conflicts, never 0.45."""
    table = prepared(heading('% of total') + sec_row('Number of days of supply', '45'))
    assert cell_rows(table) == [[text_cell('Number of days of supply'), text_cell('45', _CONFLICT)]]
    assert table.status == 'needs_review'


@pytest.mark.parametrize('label', ['Years 1-5', 'Days 31-60', 'Years 2027-2030', 'Months 1 to 12'])
def test_leading_digit_range_buckets_name_no_unit(label):
    """Ruling 25 keeps one exemption: a bucket that starts with years, months or days and a
    digit range names no unit of its values, whether they have their own '%' or a
    table-wide declaration proves them."""
    table = prepared(heading('2025') + sec_row(label, '5.2 %'))
    assert cell_rows(table) == [[text_cell(label), (Decimal('0.052'), '0.0%', '5.2 %', None)]]
    table = prepared(heading('2025') + sec_row(label, '3.25'), before=_IN_PERCENTAGES)
    assert cell_rows(table) == [[text_cell(label), (Decimal('0.0325'), '0.00%', '3.25', None)]]
    assert table.status == 'exported'


# --- Ruling 26: every points unit is contrary evidence ---------------------------------

_RULING_26_LABELS = ['Change 2024 - 2025 bps', 'Change 2024 - 25 bps', 'Change 2024 -25 bps',
                     'Change in margin 2024 - 2025 basis points', 'Margin change 2023 − 2024 bps']


@pytest.mark.parametrize('label', _RULING_26_LABELS)
def test_ruling_26_row_labels_never_take_a_table_wide_declaration(label):
    """Ruling 26: a year range before bps is no scenario; the label names a points unit, so
    under '(in percentages)' its value is conflict text, never 120 → 1.20."""
    table = prepared(heading('2025') + sec_row('Gross margin', '45') + sec_row(label, '120'), before=_IN_PERCENTAGES)
    assert cell_rows(table) == [_MARGIN_45, [text_cell(label), text_cell('120', _CONFLICT)]]
    assert table.issues == (f'Source row 2, column 1: {_CONFLICT}',)
    assert table.status == 'needs_review'


@pytest.mark.parametrize('header', _RULING_26_LABELS + ['2025 - 2024 bps change'])
def test_ruling_26_headings_never_take_nvdas_sentence(header):
    """Ruling 26: as column headings under NVDA's sentence, the same labels conflict."""
    table = prepared(heading('2025', header) + sec_row('Gross margin', '45', '120'), before=_NVDA_SENTENCE)
    assert cell_rows(table) == [_MARGIN_45 + [text_cell('120', _CONFLICT)]]
    assert table.issues == (f'Source row 1, column 4: {_CONFLICT}',)


def test_ruling_26_own_percent_beside_a_points_label_conflicts():
    """Ruling 26: a row's own '120 %' beside 'Change 2024 - 2025 bps' is conflict text,
    never 1.20."""
    table = prepared(heading('2025') + sec_row('Change 2024 - 2025 bps', '120 %'))
    assert cell_rows(table) == [[text_cell('Change 2024 - 2025 bps'), text_cell('120 %', _CONFLICT)]]
    assert table.status == 'needs_review'
