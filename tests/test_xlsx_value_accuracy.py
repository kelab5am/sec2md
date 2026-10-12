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
         '<xbrli:unit id="U_USDPerShare"><xbrli:divide>'
         '<xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator>'
         '<xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator>'
         '</xbrli:divide></xbrli:unit>'
         '</ix:resources></ix:header></div>')


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

def prepared(rows):
    """prepare_table for a one-table filing whose units are defined in its ix:header."""
    source = f'<html><body>{UNITS}<table>{rows}</table></body></html>'
    soup = BeautifulSoup(source, 'lxml')
    return xlsx_tables.prepare_table(
        snapshot_html_table(soup.table, ordinal=1, page=1, source_url='https://example.com/main.htm'))


def cell_rows(table):
    """(value, number_format, original, review_reason) for every copy cell."""
    return [[(c.value, c.number_format, c.original, c.review_reason) for c in row] for row in table.rows]


_POINTS_REASON = 'Percentage points; verify the unit.'


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
