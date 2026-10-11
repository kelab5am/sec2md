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
