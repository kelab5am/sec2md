"""XLSX value accuracy (docs/superpowers/specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md).

Tables use SEC-style inline XBRL: the units are defined in a hidden ix:header,
and each fact is an ix:nonFraction inside a table cell.
"""

import pytest
from bs4 import BeautifulSoup

from sec2md import xlsx_tables
from sec2md.xlsx_tables import snapshot_html_table

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
