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


# --- Rule 1, positive cases -----------------------------------------------------

def test_bare_instant_date_over_years_gives_period_headers():
    table = prepared(BALANCE_SHEET)
    assert table.status == 'exported'
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert values(table) == [['Cash', Decimal('43889'), Decimal('41862')],
                             ['Total assets', Decimal('276054'), Decimal('229623')]]
    assert table.cell_sources[0][1:] == (((2, 1), (2, 2)), ((2, 4), (2, 5)))


def test_change_column_beside_years_gets_its_own_header():
    table = prepared(
        '<table><tr><td></td><td colspan="9">Year Ended December 31,</td></tr>'
        '<tr><td></td><td colspan="3">2024</td><td colspan="3">2023</td><td colspan="3">2024 vs 2023 % change</td></tr>'
        '<tr><td>Advertising</td><td>$</td><td>160,633</td><td></td><td>$</td><td>131,948</td><td></td>'
        '<td></td><td>22</td><td>%</td></tr></table>')
    assert table.headers == ('Column 1', 'Year Ended December 31, — 2024', 'Year Ended December 31, — 2023',
                             'Year Ended December 31, — 2024 vs 2023 % change')
    assert values(table) == [['Advertising', Decimal('160633'), Decimal('131948'), Decimal('0.22')]]


def test_labelled_heading_row_with_heading_word_joins_the_header():
    table = prepared(
        '<table><tr><td></td><td></td><td></td><td colspan="4">Fair Value Measurement Using</td></tr>'
        '<tr><td>Description</td><td colspan="2">December 31, 2024</td><td colspan="2">Level 1</td>'
        '<td colspan="2">Level 2</td></tr>'
        + '<tr><td>Money market funds</td><td>$</td><td>36,165</td><td>$</td><td>36,165</td><td>$</td><td>12</td></tr>'
        '</table>')
    assert table.status == 'exported'
    assert table.headers == ('Description', 'December 31, 2024', 'Fair Value Measurement Using — Level 1',
                             'Fair Value Measurement Using — Level 2')
    assert values(table) == [['Money market funds', Decimal('36165'), Decimal('36165'), Decimal('12')]]


def test_three_level_td_header():
    table = prepared(
        '<table><tr><td></td><td colspan="4">December 31, 2024</td></tr>'
        '<tr><td></td><td colspan="2">Less than 12 months</td><td colspan="2">12 months or greater</td></tr>'
        '<tr><td></td><td colspan="2">Fair Value</td><td colspan="2">Fair Value</td></tr>'
        '<tr><td>U.S. government securities</td><td>$</td><td>6,860</td><td>$</td><td>4,330</td></tr></table>')
    assert table.headers == ('Column 1', 'December 31, 2024 — Less than 12 months — Fair Value',
                             'December 31, 2024 — 12 months or greater — Fair Value')
    assert values(table) == [['U.S. government securities', Decimal('6860'), Decimal('4330')]]
    assert table.cell_sources[0][1:] == (((3, 1), (3, 2)), ((3, 3), (3, 4)))


def test_equal_width_headings_in_the_evidenced_row():
    # META's debt table: Maturity and rates over cells as wide as they are.
    table = prepared(
        '<table><tr><td></td><td colspan="2">Maturity</td><td colspan="2">Stated Interest Rate</td>'
        '<td colspan="2">December 31, 2024</td></tr>'
        '<tr><td>2027 Notes</td><td colspan="2">2027</td><td colspan="2">3.50%</td><td>$</td><td>2,750</td></tr>'
        '</table>')
    assert table.headers == ('Column 1', 'Maturity', 'Stated Interest Rate', 'December 31, 2024')
    assert values(table)[0][3] == Decimal('2750')


def test_equal_width_headings_one_row_above_the_evidenced_row():
    # NVDA's debt table: term and rate headings above the evidenced dates.
    table = prepared(
        '<table><tr><td></td><td colspan="2">Expected Remaining Term (years)</td>'
        '<td colspan="2">Effective Interest Rate</td><td colspan="4">Carrying Value at</td></tr>'
        '<tr><td></td><td colspan="2"></td><td colspan="2"></td><td colspan="2">Jan 25, 2026</td>'
        '<td colspan="2">Jan 26, 2025</td></tr>'
        '<tr><td>3.50% Notes Due 2027</td><td colspan="2">1.2</td><td colspan="2">3.54%</td>'
        '<td>$</td><td>1,000</td><td>$</td><td>1,000</td></tr></table>')
    assert table.headers[-2:] == ('Carrying Value at — Jan 25, 2026', 'Carrying Value at — Jan 26, 2025')
    assert values(table)[0][-2:] == [Decimal('1000'), Decimal('1000')]


def test_full_width_text_or_nil_in_the_data_row_does_not_block_the_header():
    table = prepared(
        '<table>' + DATE_OVER_YEARS
        + '<tr><td>Level</td><td colspan="3">Level 1</td><td colspan="3">—</td></tr>'
        + money('Cash', '10', '20') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')


def test_year_completes_an_equally_wide_yearless_date():
    # NVDA FY2024 10-Q balance sheets: 'July 30,' over an equally wide '2023'.
    table = prepared(
        '<table><tr><td></td><td colspan="3">July 30,</td><td colspan="3">January 29,</td></tr>'
        '<tr><td></td><td colspan="3">2023</td><td colspan="3">2023</td></tr>'
        + money('Cash and cash equivalents', '5,783', '3,389') + '</table>')
    assert table.headers == ('Column 1', 'July 30, — 2023', 'January 29, — 2023')
    assert values(table) == [['Cash and cash equivalents', Decimal('5783'), Decimal('3389')]]
    assert table.cell_sources[0][1:] == (((2, 1), (2, 2)), ((2, 4), (2, 5)))


def test_footnoted_years_are_periods():
    table = prepared(
        '<table><tr><td></td><td colspan="9">Year Ended December 31,</td></tr>'
        '<tr><td></td><td colspan="3">2024</td><td colspan="3">2023 (2)</td><td colspan="3">2022 (2)</td></tr>'
        '<tr><td>Net income</td><td>$</td><td>62,360</td><td></td><td>$</td><td>39,098</td><td></td>'
        '<td>$</td><td>23,200</td><td></td></tr></table>')
    assert values(table) == [['Net income', Decimal('62360'), Decimal('39098'), Decimal('23200')]]
    assert table.headers[1:] == ('Year Ended December 31, — 2024', 'Year Ended December 31, — 2023 (2)',
                                 'Year Ended December 31, — 2022 (2)')


# --- Rule 1, negative cases: today's output, or a fallback ----------------------

def assert_body_row_kept(table, label, texts):
    row = next(row for row in table.rows if row[0].value == label)
    assert [cell.value for cell in row[1:] if cell.value is not None] == texts


def test_unaudited_and_unit_captions_are_not_column_leaves():
    for captions in (['(unaudited)'], ['(in thousands)'], ['(unaudited)', '(in thousands)']):
        rows = ''.join(f'<tr><td></td><td colspan="6">{c}</td></tr>' for c in captions)
        table = prepared('<table><tr><td></td><td colspan="6">Three months ended June 30,</td></tr>'
                         '<tr><td></td><td colspan="3">2025</td><td colspan="3">2024</td></tr>'
                         + rows + money('Revenue', '499,628', '281,184') + '</table>')
        assert table.status == 'exported', captions
        assert table.headers[1:] == ('Three months ended June 30, — 2025', 'Three months ended June 30, — 2024')


def test_label_and_units_row_stays_in_the_body():
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Inventories:</td><td colspan="6">(In millions)</td></tr>'
                     + money('Raw materials', '3,807', '3,408') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert table.rows[0][0].value == 'Inventories:'


@pytest.mark.parametrize('first, second', [('N/A', 'NM'), ('NM', '—'), ('Foo', 'Bar')])
def test_labelled_text_row_as_wide_as_the_years_stays_in_the_body(first, second):
    table = prepared('<table>' + DATE_OVER_YEARS
                     + f'<tr><td>Alpha</td><td colspan="3">{first}</td><td colspan="3">{second}</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert_body_row_kept(table, 'Alpha', [first, second])
    assert values(table)[-1] == ['Beta', Decimal('10'), Decimal('20')]


def test_labelled_range_row_falls_back_as_today():
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Alpha</td><td colspan="3">2027 - 2062</td><td colspan="3">3.50% - 4.65%</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.status == 'source_text_only'


def test_unlabelled_text_row():
    narrow = prepared('<table>' + DATE_OVER_YEARS
                      + '<tr><td></td><td></td><td>Foo</td><td></td><td></td><td>Bar</td><td></td></tr>'
                      + money('Beta', '10', '20') + '</table>')
    assert narrow.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert [cell.value for cell in narrow.rows[0]] == [None, 'Foo', 'Bar']
    wide = prepared('<table>' + DATE_OVER_YEARS
                    + '<tr><td></td><td colspan="3">As Reported</td><td colspan="3">As Adjusted</td></tr>'
                    + money('Beta', '10', '20') + '</table>')
    assert wide.headers == ('Column 1', 'December 31, — 2024 — As Reported', 'December 31, — 2023 — As Adjusted')


@pytest.mark.parametrize('row', [
    '<tr><td>Alpha</td><td>N/A</td></tr>', '<tr><td>Alpha</td><td>NM</td></tr>',
    '<tr><td>Alpha</td><td>—</td></tr>', '<tr><td>Alpha</td><td>March 31, 2025</td></tr>',
    '<tr><td>Alpha</td><td>2027 - 2062</td></tr>'])
def test_codex_round_1_text_row_after_th_header(row):
    source = f'<table><tr><th>Item</th><th>Amount</th></tr>{row}<tr><td>Beta</td><td>10</td></tr></table>'
    table = prepared(source)
    assert table.headers == ('Item', 'Amount')
    assert table.rows[0][0].value == 'Alpha'
    assert table.rows[-1][1].value == Decimal('10')


def test_codex_round_1_year_shaped_amounts_under_a_wider_heading():
    table = prepared('<table><tr><th>Item</th><th colspan="2">Amount</th></tr>'
                     '<tr><td>Revenue</td><td>2024</td><td>2025</td></tr>'
                     '<tr><td>Cost</td><td>100</td><td>150</td></tr></table>')
    assert values(table) == [['Revenue', Decimal('2024'), Decimal('2025')], ['Cost', Decimal('100'), Decimal('150')]]


def test_codex_round_1_text_table_with_a_dash():
    table = prepared('<table><tr><td>Name</td><td>Title</td></tr><tr><td>Alice</td><td>CEO</td></tr>'
                     '<tr><td>Bob</td><td>-</td></tr></table>')
    assert table.headers == ('Column 1', 'Column 2')
    assert len(table.rows) == 3


def test_signature_table_is_unchanged():
    table = prepared('<table><tr><td>Signature</td><td>Title</td><td>Date</td></tr>'
                     '<tr><td>/s/ Mark Zuckerberg</td><td>Chief Executive Officer</td><td>January 29, 2025</td></tr>'
                     '<tr><td>Peggy Alford</td><td></td><td></td></tr></table>')
    assert table.headers == ('Column 1', 'Column 2', 'Column 3')
    assert len(table.rows) == 3


def test_currency_row_narrower_than_its_date_stays_out_of_the_header():
    # TSM: 'NT$' spans only the '$' and amount cells of a wider date column.
    table = prepared(
        '<table><tr><td></td><td colspan="4">December 31, 2023</td><td colspan="4">December 31, 2024</td></tr>'
        '<tr><td></td><td></td><td colspan="2">NT$</td><td></td><td></td><td colspan="2">NT$</td><td></td></tr>'
        '<tr><td>Corporate bonds</td><td></td><td>$</td><td>113,851.9</td><td></td><td></td><td>$</td>'
        '<td>172,092.0</td><td></td></tr></table>')
    assert table.headers == ('Column 1', 'December 31, 2023', 'December 31, 2024')


def test_codex_round_2_labelled_rows_of_amounts_fall_back():
    for middle in ('<tr><td>Revenue</td><td colspan="2">2024</td><td colspan="2">2025</td></tr>',
                   '<tr><td>Basic EPS</td><td colspan="2">.75</td><td colspan="2">.50</td></tr>'):
        table = prepared('<table><tr><th>Item</th><th colspan="4">December 31, 2025</th></tr>' + middle
                         + '<tr><td>Cost</td><td>$</td><td>100</td><td>$</td><td>150</td></tr></table>')
        assert table.status == 'source_text_only', middle


def test_codex_round_2_heading_across_two_periods_keeps_each_amount_under_its_date():
    table = prepared(
        '<table><tr><th>Item</th><th colspan="3">December 31, 2024</th><th colspan="3">December 31, 2023</th></tr>'
        '<tr><td>Description</td><td colspan="2">Cash</td><td colspan="2">Debt</td><td colspan="2">Other</td></tr>'
        '<tr><td>Revenue</td><td>$</td><td>100</td><td>$</td><td>200</td><td>$</td><td>300</td></tr></table>')
    by_header = {}
    for header, cell in zip(table.headers, table.rows[-1]):
        by_header.setdefault(header, []).append(cell.value)
    assert Decimal('200') not in by_header.get('December 31, 2024 — Debt', [])
    assert all('Debt' not in header for header in table.headers)


def test_codex_round_2_narrower_labelled_text_row_stays_in_the_body():
    table = prepared('<table><tr><th>Item</th><th colspan="4">December 31, 2025</th></tr>'
                     '<tr><td>Alpha</td><td colspan="2">Foo</td><td colspan="2">Bar</td></tr>'
                     '<tr><td>Cost</td><td>$</td><td>100</td><td>$</td><td>150</td></tr></table>')
    assert table.rows[0][0].value == 'Alpha'
    assert all('Foo' not in header for header in table.headers)


@pytest.mark.parametrize('first, second', [('N/A', 'NM'), ('.75', '.50')])
def test_check_1_unlabelled_row_of_data_stays_in_the_body(first, second):
    # Unlabelled, so checks 3 and 3b do not apply; only check 1 sees data cells.
    table = prepared('<table>' + DATE_OVER_YEARS
                     + f'<tr><td></td><td colspan="3">{first}</td><td colspan="3">{second}</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert all(first not in header for header in table.headers)


def test_check_3_labelled_row_needs_two_headings():
    # 'Description' passes check 3b and 'Foo' is narrower than '2024'; only check 3 stops it.
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Description</td><td colspan="2">Foo</td><td></td><td></td><td></td><td></td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert all('Foo' not in header for header in table.headers)
    assert table.status == 'source_text_only' or table.rows[0][0].value == 'Description'


def test_check_8_years_need_a_period_heading_above():
    # Unlabelled years under a non-period heading: only check 8 keeps them out of the header.
    table = prepared('<table><tr><td></td><td colspan="6">Amount</td></tr>'
                     '<tr><td></td><td colspan="3">2024</td><td colspan="3">2023</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert all('2024' not in header for header in table.headers)


def test_check_4b_labelled_row_as_wide_as_its_heading_stays_in_the_body():
    # 'Description' is a heading word, so only check 4b keeps this row out of the header.
    table = prepared('<table>' + DATE_OVER_YEARS
                     + '<tr><td>Description</td><td colspan="3">Foo</td><td colspan="3">Bar</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert_body_row_kept(table, 'Description', ['Foo', 'Bar'])


def test_check_7b_years_on_a_heading_word_row_are_not_headers():
    # 'Description' passes check 3b; only check 7b stops its years becoming headings.
    table = prepared('<table><tr><td></td><td colspan="6">December 31,</td></tr>'
                     '<tr><td>Description</td><td colspan="3">2024</td><td colspan="3">2023</td></tr>'
                     + money('Beta', '10', '20') + '</table>')
    assert table.status == 'source_text_only' or table.rows[0][0].value == 'Description'


def test_heading_over_part_of_a_wider_amount_falls_back():
    # Check 5 is a second line of defence: without it the unresolved-span check falls back too.
    table = prepared('<table><tr><td></td><td colspan="4">December 31, 2024</td></tr>'
                     '<tr><td></td><td>A</td><td>B</td><td colspan="2">C</td></tr>'
                     '<tr><td>Revenue</td><td colspan="2">100</td><td>$</td><td>200</td></tr></table>')
    assert table.status == 'source_text_only'


@pytest.mark.parametrize('label', ['Revenue for year ended December 31, 2025', 'Cash as of December 31, 2025'])
def test_line_item_mentioning_a_period_is_not_a_caption(label):
    # A body label containing period wording must not head its year-shaped amounts.
    table = prepared(f'<table><tr><th>Item</th><th colspan="4">December 31, 2025</th></tr>'
                     f'<tr><td>{label}</td><td colspan="2">2024</td><td colspan="2">2025</td></tr>'
                     '<tr><td>Cost</td><td>$</td><td>100</td><td>$</td><td>150</td></tr></table>')
    assert table.status == 'source_text_only' or table.rows[0][0].value == label


def test_pricing_category_heading_row():
    table = prepared(
        '<table><tr><td></td><td colspan="4">Fair Value at</td></tr>'
        '<tr><td>Pricing Category</td><td colspan="2">Apr 27, 2025</td><td colspan="2">Jan 26, 2025</td></tr>'
        '<tr><td>Money market funds</td><td>$</td><td>14,925</td><td>$</td><td>11,423</td></tr></table>')
    assert table.headers == ('Pricing Category', 'Fair Value at — Apr 27, 2025', 'Fair Value at — Jan 26, 2025')
    assert values(table) == [['Money market funds', Decimal('14925'), Decimal('11423')]]


def test_header_count_and_period_are_byte_identical():
    # table_completeness reads _header_count, which uses _PERIOD; neither may change.
    source = inspect.getsource(xlsx_tables._header_count).encode()
    assert hashlib.sha256(source).hexdigest() == 'ee9602d3dbf304d6dd0abbc69b84c830eaa16cf0f285437d7a2776ca3a3b9df1'
    pattern = xlsx_tables._PERIOD.pattern.encode()
    assert hashlib.sha256(pattern).hexdigest() == 'ee6996610a505583030f3ab913a7e8854dafd0e6b3c115602df6bbffcda21f16'


def test_header_count_is_unchanged_for_the_completeness_check():
    # table_completeness reads _header_count; these grids keep today's counts.
    assert _header_count(grid_of(BALANCE_SHEET)) == 0
    assert _header_count(grid_of('<table><tr><th>Item</th><th>Amount</th></tr>'
                                 '<tr><td>Alpha</td><td>N/A</td></tr></table>')) == 1


# --- Rule 1, period-row guard ---------------------------------------------------

def todays(source, monkeypatch):
    """The table prepared with today's header rows: _export_header_count replaced by _header_count."""
    with monkeypatch.context() as patch:
        patch.setattr(xlsx_tables, '_export_header_count', xlsx_tables._header_count)
        return prepared(source)


def outcome(table):
    return table.status, table.headers, values(table), table.cell_sources, table.issues


def headers_over_amounts(table, first_row):
    """The headers over every amount converted from source row first_row on: its column's header and the label
    column's header, which heads every row (JPM: 'Year ended December 31, 2023 (in millions)')."""
    over = [header for row, sources in zip(table.rows, table.cell_sources)
            for header, cell, origins in zip(table.headers, row, sources)
            if origins and origins[0][0] >= first_row and isinstance(cell.value, Decimal)]
    return over + list(table.headers[:1]) if over else over


# A stockholders' equity statement stacking two period blocks, as in the RDDT and
# META 10-Qs: the first block's caption row over column headings over amounts.
EQUITY_HEADINGS = ('<tr><td></td><td colspan="3">Accumulated Deficit</td>'
                   "<td colspan=\"3\">Total Stockholders' Equity (Deficit)</td></tr>")
FIRST_CAPTION = 'Three months ended March 31, 2024'


def first_block(caption):
    return (f'<tr><td></td><td colspan="6">{caption}</td></tr>' + EQUITY_HEADINGS
            + money('Balance as of December 31, 2023', '(1,190,563)', '1,893,071')
            + money('Net loss', '(575,076)', '(575,076)'))


def caption_row(caption):
    return f'<tr><td></td><td colspan="6">{caption}</td></tr>' + EQUITY_HEADINGS


def caption_beside_headings(caption):
    return (f'<tr><td>{caption}</td><td colspan="3">Accumulated Deficit</td>'
            "<td colspan=\"3\">Total Stockholders' Equity (Deficit)</td></tr>")


def label_caption(caption):
    return f'<tr><td>{caption}</td><td colspan="6"></td></tr>' + EQUITY_HEADINGS


FIRST_BLOCK = first_block(FIRST_CAPTION)
SECOND_BLOCK_ROW = 4  # the source row of the second block's caption
SECOND_BLOCK_AMOUNTS = (money('Balance as of December 31, 2024', '(1,705,853)', '2,130,749')
                        + money('Net income', '26,158', '26,158'))


def stacked(second_caption, first_caption=FIRST_CAPTION):
    return '<table>' + first_block(first_caption) + second_caption + SECOND_BLOCK_AMOUNTS + '</table>'


def jpm_block(caption, interest_rate, total):
    # JPM 10-K derivatives table: the period, with its unit, heads the label column beside the column headings.
    return (f'<tr><td>{caption}</td><td colspan="3">Amounts reclassified from AOCI to income</td>'
            '<td colspan="3">Amounts recorded in OCI</td></tr><tr><td>Contract type</td></tr>'
            + money('Interest rate', *interest_rate) + money('Total', *total))


JPM_LAYOUT = ('<table>' + jpm_block('Year ended December 31, 2023 (in millions)', ('(1,839)', '274'), ('(1,775)', '483'))
              + jpm_block('Year ended December 31, 2022 (in millions)', ('(153)', '(7,131)'), ('(420)', '(7,473)'))
              + '</table>')


@pytest.mark.parametrize('first_period, source', [
    (FIRST_CAPTION, stacked(caption_row('Three months ended March 31, 2025'))),
    (FIRST_CAPTION, stacked(caption_beside_headings('Three months ended March 31, 2025'))),
    (FIRST_CAPTION, stacked(caption_row('Three Months Ended June 30, 2025 and 2024'))),
    (FIRST_CAPTION, stacked(caption_row('Three Months Ended June 30, 2025 (1)'))),
    (FIRST_CAPTION, stacked(label_caption('Three months ended March 31, 2025'))),
    (FIRST_CAPTION, stacked(caption_row('Three Months Ended March 31, 2025 (a)'))),
    (FIRST_CAPTION, stacked(caption_beside_headings('Three Months Ended March 31, 2025 (Unaudited)'))),
    (FIRST_CAPTION, stacked(label_caption('Three months ended March 31, 2025:'))),
    ('Thirteen Weeks Ended May 4, 2024',
     stacked(caption_row('Thirteen Weeks Ended May 3, 2025'), 'Thirteen Weeks Ended May 4, 2024')),
    (FIRST_CAPTION, stacked(caption_row('Period from January 1, 2025 through March 31, 2025'))),
    (FIRST_CAPTION, stacked(caption_row('Three months ended March 31, 2025, as restated'))),
    (FIRST_CAPTION, stacked('<tr><td></td><td colspan="5">Three months ended March 31, 2025</td><td>(1)</td></tr>'
                            + EQUITY_HEADINGS)),
    (FIRST_CAPTION, stacked('<tr><td>Three months ended March 31, 2025</td><td colspan="5"></td><td>*</td></tr>'
                            + EQUITY_HEADINGS)),
    ('Year ended December 31, 2023', JPM_LAYOUT),
], ids=['caption-row', 'caption-beside-headings', 'two-years', 'footnoted', 'label-column', 'letter-footnote',
        'unaudited-beside-headings', 'colon-label-column', 'thirteen-weeks', 'period-from-through', 'as-restated',
        'footnote-own-cell', 'star-own-cell-label-column', 'jpm-unit-captions'])
def test_guard_stacked_period_blocks(first_period, source, monkeypatch):
    # D1: the extended header would put the second block's amounts under the first block's period.
    table = prepared(source)
    assert outcome(table) == outcome(todays(source, monkeypatch))
    assert not any(first_period in header for header in headers_over_amounts(table, SECOND_BLOCK_ROW))


def years_under_instant(first, second):
    return ('<table><tr><td></td><td colspan="4">December 31,</td></tr>'
            f'<tr><td></td><td></td><td>{first}</td><td></td><td>{second}</td></tr>'
            '<tr><td>Cash</td><td>$</td><td>43,889</td><td>$</td><td>41,862</td></tr></table>')


def dates_under_measurement_date(label, first, second):
    return ('<table><tr><td></td><td colspan="4">Measurement Date</td></tr>'
            f'<tr><td>{label}</td><td colspan="2">{first}</td><td colspan="2">{second}</td></tr>'
            '<tr><td>Expected volatility</td><td colspan="2">30.5%</td><td colspan="2">28.1%</td></tr></table>')


@pytest.mark.parametrize('source', [
    years_under_instant('2024', '2023'),
    dates_under_measurement_date('', 'December 31, 2023', 'December 31, 2024'),
    dates_under_measurement_date('Date', 'December 31, 2023', 'December 31, 2024'),
    dates_under_measurement_date('', 'December 31, 2023 (a)', 'December 31, 2024 (a)'),
    dates_under_measurement_date('', '12/31/2023', '12/31/2024'),
    years_under_instant('2024 (a)', '2023 (a)'),
], ids=['years-under-instant', 'dates-under-measurement-date', 'dates-labelled-date', 'letter-footnoted-dates',
        'numeric-dates', 'letter-footnoted-years'])
def test_guard_stranded_period_rows(source, monkeypatch):
    # I1: an accepted period row below the evidenced row would leave its periods out of the headers.
    assert outcome(prepared(source)) == outcome(todays(source, monkeypatch))


def test_guard_ignores_rows_with_amounts():
    # Rows of amounts hold data cells, so they are not period rows, even under a year label.
    table = prepared('<table>' + DATE_OVER_YEARS
                     + money('Balance as of December 31, 2024', '2,130,749', '1,893,071')
                     + money('2026', '1,234', '1,100') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert values(table) == [['Balance as of December 31, 2024', Decimal('2130749'), Decimal('1893071')],
                             ['2026', Decimal('1234'), Decimal('1100')]]


def test_guard_ignores_label_with_period_phrase():
    # A section label that only mentions a period is not a period row, so the statement keeps its header.
    label = 'Supplemental cash flow information for the years ended December 31:'
    table = prepared('<table>' + DATE_OVER_YEARS + money('Net cash provided by operating activities', '91,328', '71,113')
                     + f'<tr><td>{label}</td><td colspan="6"></td></tr>'
                     + money('Cash paid for income taxes, net', '9,999', '6,407') + '</table>')
    assert table.headers == ('Column 1', 'December 31, — 2024', 'December 31, — 2023')
    assert values(table) == [['Net cash provided by operating activities', Decimal('91328'), Decimal('71113')],
                             [label, None, None],
                             ['Cash paid for income taxes, net', Decimal('9999'), Decimal('6407')]]


@pytest.mark.parametrize('label, first, second', [('Revenue', '2024', '2025'),
                                                  ('Alpha', 'March 31, 2025', 'June 30, 2025')])
def test_guard_fires_on_labelled_period_rows(label, first, second, monkeypatch):
    source = ('<table>' + DATE_OVER_YEARS
              + f'<tr><td>{label}</td><td colspan="3">{first}</td><td colspan="3">{second}</td></tr>'
              + money('Beta', '10', '20') + '</table>')
    assert outcome(prepared(source)) == outcome(todays(source, monkeypatch))


def test_guard_cost_on_repeated_section_label(monkeypatch):
    # The stated trade-off: a section label repeating a period falls back to today's header rows.
    source = ('<table><tr><td></td><td colspan="6">December 31,</td></tr>'
              '<tr><td></td><td colspan="3">2025</td><td colspan="3">2024</td></tr>'
              + money('Cash', '43,889', '41,862')
              + '<tr><td>December 31, 2025</td><td colspan="6"></td></tr>'
              + money('Accounts receivable', '16,169', '14,519') + '</table>')
    assert outcome(prepared(source)) == outcome(todays(source, monkeypatch))


@pytest.mark.parametrize('text, expected', [
    ('Three months ended March 31, 2025', True), ('Three Months Ended June 30, 2025 and 2024', True),
    ('December 31, 2025 (1)', True), ('Six Months Ended', True), ('December 31,', True), ('2023 (2)', True),
    ('As of December 31, 2024', True), ('Three Months Ended March 31, 2025 (a)', True),
    ('Three Months Ended March 31, 2025 (Unaudited)', True), ('Three months ended March 31, 2025:', True),
    ('Thirteen Weeks Ended May 3, 2025', True), ('Period from January 1, 2025 through March 31, 2025', True),
    ('12/31/2024', True), ('2024 (a)', True), ('March 31, 2025 (Restated)', True),
    ('Year ended December 31, 2022 (in millions)', True),
    ('Balance as of December 31, 2024', False), ('2024 vs 2023 % change', False), ('Common Stock', False),
    ('Fiscal Year', False), ('Market 10', False),
    ('Cash paid for income taxes for the years ended December 31,', False)])
def test_period_text(text, expected):
    assert xlsx_tables._period_text(text) is expected


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
