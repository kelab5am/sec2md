"""R0 row roles, pinned independently of the shared helper.

Each named case is a minimal copy of a real table from the table-merge evidence report
(docs/superpowers/audits/2026-10-04-table-merge-header-evidence/REPORT.md). Grids hold
each slot's origin text (a plain string is a td cell, th() builds th cells); None marks a
slot covered by another cell's span. Expected roles are written out literally, never
computed with the helper under test.
"""

import pytest

from sec2md.table_roles import (
    OriginCell,
    counts_bare_years,
    is_bare_year,
    is_complete_number,
    is_currency_marker,
    fuses_like_main,
    is_explicit_header_row,
    is_header_like,
    is_label_only,
    is_period_text,
    is_unit_text,
    is_year_like,
    is_year_run,
    is_nil_value,
    row_roles,
    row_values,
    visible_text,
)


def th(*texts):
    """A row of th cells; None stays a span-covered slot."""
    return [None if text is None else OriginCell(text, header=True) for text in texts]


def role_names(grid):
    roles = row_roles(grid)
    return [roles.role(row) for row in range(len(grid))]


# --- named tables ----------------------------------------------------------------------

# edgar:CRM-10-K-2025-03-05.htm table 26, cleaned grid: a caption number `4` beside a
# period caption, then the year row, then cash-flow data.
CRM_26 = [
    ["4", "Fiscal Year Ended January 31,", None, None, None, None, None, None],
    ["", "", "2025", None, "2024", None, "2023", None],
    ["Net cash provided by operating activities", "", "$", "13,092", "$", "10,234", "$", "7,111"],
    ["Net cash used in investing activities", "", "(3,163)", None, "(1,327)", None, "(1,989)", None],
    ["Net cash used in financing activities", "", "(9,429)", None, "(7,477)", None, "(3,562)", None],
]


def test_crm_26_caption_and_year_rows_are_header():
    roles = row_roles(CRM_26)
    assert role_names(CRM_26) == ["header", "header", "body", "body", "body"]
    assert roles.header_rows == (0, 1)
    assert roles.data_rows == (2, 3, 4)
    assert roles.label_column == 0
    assert roles.identifier_column is False


# edgar:JPM-10-K-2025-02-14.htm table 109: headerless, the first row is data.
JPM_109 = [
    ["Noninterest revenue – reported (c)", "$", "84,973", "$", "68,837", "$", "61,985"],
    ["Fully taxable-equivalent adjustments (c)", "", "2,560", "", "3,782", "", "3,148"],
    ["Total noninterest revenue – managed", "$", "87,533", "$", "72,619", "$", "65,133"],
]


def test_jpm_109_first_row_is_data_and_header_zone_is_empty():
    roles = row_roles(JPM_109)
    assert role_names(JPM_109) == ["body", "body", "body"]
    assert roles.header_rows == ()
    assert roles.data_rows == (0, 1, 2)


# fixture:aapl-2023-10k table 18: "Products 36.5 %" is the first data row.
AAPL_18 = [
    ["Gross margin percentage:", "", None, "", None, "", None],
    ["Products", "36.5", "%", "36.3", "%", "35.3", "%"],
    ["Services", "70.8", "%", "71.7", "%", "69.7", "%"],
    ["Total gross margin percentage", "44.1", "%", "43.3", "%", "41.8", "%"],
]


def test_aapl_18_products_row_is_data():
    # Revision 8: the label-only "Gross margin percentage:" row right before the first data
    # row is a section label, so it is body too and the header zone is empty.
    roles = row_roles(AAPL_18)
    assert role_names(AAPL_18) == ["body", "body", "body", "body"]
    assert roles.data_rows == (1, 2, 3)
    assert roles.header_rows == ()


# fixture:nvda-2026-10k table 17: three header rows above the cash-flow data.
NVDA_17 = [
    ["", "Year Ended", None, None, None],
    ["", "Jan 25, 2026", None, "Jan 26, 2025", None],
    ["", "(In millions)", None, None, None],
    ["Net cash provided by operating activities", "$", "102,718", "$", "64,089"],
    ["Net cash used in investing activities", "$", "(52,228)", "$", "(20,421)"],
    ["Net cash used in financing activities", "$", "(48,474)", "$", "(42,359)"],
]


def test_nvda_2026_10k_17_has_three_header_rows():
    roles = row_roles(NVDA_17)
    assert role_names(NVDA_17) == ["header", "header", "header", "body", "body", "body"]
    assert roles.header_rows == (0, 1, 2)


# --- split negatives, single digits, identifier columns ----------------------------------

def test_split_negative_first_data_row_is_body():
    grid = [
        th("Metric", "2025", None, "2024", None),
        ["Loss", "(29", ")", "(40", ")"],
        ["Gain", "50", "", "60", ""],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.data_rows == (1, 2)


def test_split_negative_first_row_without_header_leaves_header_zone_empty():
    grid = [
        ["Loss", "(29", ")", "(40", ")"],
        ["Gain", "50", "", "60", ""],
    ]
    assert role_names(grid) == ["body", "body"]


@pytest.mark.parametrize("cells", [
    ["Loss", "(", "29", ")"],
    ["Loss", "(3.2", ")%", ""],
    ["Loss", "(.62", ")", ""],
], ids=["three-cell", "percent-close", "leading-dot"])
def test_other_split_negative_shapes_make_a_data_row(cells):
    grid = [th("Metric", "2025", None, None), cells]
    assert role_names(grid) == ["header", "body"]


def test_genuine_single_digit_first_data_row_is_body():
    grid = [
        ["", "2025", "2024"],
        ["Stores", "9", "7"],
        ["Employees", "3", "4"],
    ]
    assert role_names(grid) == ["header", "body", "body"]


def test_exhibit_index_starting_at_3_1_is_an_identifier_column():
    grid = [
        ["Exhibit Number", "Description"],
        ["3.1", "Articles of Incorporation"],
        ["3.2", "Bylaws"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.identifier_column is True
    assert roles.data_rows == (1, 2)


def test_exhibit_index_integer_then_decimal_keeps_both_entries_in_body():
    grid = [
        ["Exhibit Number", "Description"],
        ["1", "Agreement"],
        ["3.1", "Articles"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.identifier_column is True


def test_all_integer_exhibit_index_keeps_both_entries_in_body():
    grid = [
        ["Exhibit Number", "Description"],
        ["1", "Agreement"],
        ["2", "Plan"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.data_rows == (1, 2)


def test_caption_number_control_stays_header():
    grid = [
        ["4", "Fiscal Year Ended January 31,", None],
        ["", "2025", "2024"],
        ["Revenue", "100", "200"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body"]
    assert roles.identifier_column is False


# --- coordinate equivalence --------------------------------------------------------------

# The checker's placed grid keeps a leading spacer column, a blank row, a rowspan and
# linked labels; the renderer's cleaned grid drops the spacer column and the blank row.
PLACED = [
    ["", "4", "Fiscal Year Ended January 31,", None, None],
    ["", "", "", "", ""],
    ["", "", "2025", None, "2024"],
    ["", "[Revenue](#revenue)", "$", "100", "200"],
    ["", "Costs", "", "[60](#costs)", "70"],
    ["", "Total", "$", "160", "270"],
    ["", None, "", "", "5"],
]
CLEANED = [
    ["4", "Fiscal Year Ended January 31,", None, None],
    ["", "2025", None, "2024"],
    ["[Revenue](#revenue)", "$", "100", "200"],
    ["Costs", "", "[60](#costs)", "70"],
    ["Total", "$", "160", "270"],
    [None, "", "", "5"],
]
PLACED_ROWS = [0, 2, 3, 4, 5, 6]   # cleaned row -> placed row
PLACED_COLUMNS = [1, 2, 3, 4]      # cleaned column -> placed column


def test_placed_and_cleaned_grids_assign_the_same_roles():
    placed, cleaned = row_roles(PLACED), row_roles(CLEANED)
    assert role_names(PLACED) == ["header", "empty", "header", "body", "body", "body", "body"]
    assert role_names(CLEANED) == ["header", "header", "body", "body", "body", "body"]
    assert [placed.role(PLACED_ROWS[r]) for r in range(len(CLEANED))] == role_names(CLEANED)
    assert placed.data_rows == tuple(PLACED_ROWS[r] for r in cleaned.data_rows)
    assert placed.header_rows == tuple(PLACED_ROWS[r] for r in cleaned.header_rows)
    # The same logical label column, each in its own coordinates.
    assert (placed.label_column, cleaned.label_column) == (1, 0)
    assert PLACED_COLUMNS[cleaned.label_column] == placed.label_column
    assert placed.identifier_column is cleaned.identifier_column is False
    assert placed.empty_rows == (1,)


def test_placed_grid_values_keep_original_columns():
    assert row_values(PLACED[4]) == [(1, "Costs"), (3, "60"), (4, "70")]
    assert row_values(CLEANED[3]) == [(0, "Costs"), (2, "60"), (3, "70")]


# --- tables without data, bare years, footnote marks, links ------------------------------

def test_text_table_without_data_uses_first_row_alone_as_header():
    grid = [
        ["Name", "Title"],
        ["Jane Doe", "Director"],
        ["John Roe", "Officer"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.data_rows == ()


# edgar:GOOGL-10-Q-2025-10-30.htm table 89.
def test_signature_block_uses_first_row_alone_as_header():
    grid = [
        ["", "", "ALPHABET INC."],
        ["October 29, 2025", "By:", "/s/ ANAT ASHKENAZI"],
        ["", "", "Anat Ashkenazi"],
        ["", "", "Senior Vice President, Chief Financial Officer"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body"]
    assert roles.label_column == 0


def test_bare_year_label_column_with_amounts_beside_it():
    grid = [
        ["Year", "Amount"],
        ["2025", "100"],
        ["2024", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.data_rows == (1, 2)
    # Revision 11: a year-like label cell does not make bare years count, so the label
    # years are not numbers and the column is no identifier column; the amounts make the
    # rows data.
    assert roles.identifier_column is False


def test_bare_year_labels_do_not_count_in_their_own_rows():
    # Revision 11 (was: the label years counted, an identifier column of data rows). The
    # roles are unchanged, because a table without a data row keeps its first row alone.
    grid = [
        ["Year", "Event"],
        ["2025", "Launch"],
        ["2024", "Founding"],
    ]
    roles = row_roles(grid)
    assert roles.identifier_column is False
    assert roles.data_rows == ()
    assert role_names(grid) == ["header", "body", "body"]


def test_standalone_footnote_mark_in_a_header_row_makes_it_a_data_row():
    # Recorded limitation: a standalone "(1)" is a complete number, so the row is data
    # and the header zone is empty.
    grid = [
        ["Item", "Amount", "(1)"],
        ["Revenue", "100", ""],
        ["Costs", "60", ""],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["body", "body", "body"]
    assert roles.data_rows == (0, 1, 2)


def test_standalone_footnote_mark_in_the_label_column_stays_header():
    grid = [
        ["(1)", "Amount"],
        ["Revenue", "100"],
    ]
    assert role_names(grid) == ["header", "body"]


def test_linked_number_is_classified_from_its_label():
    grid = [
        th("Item", "2025"),
        ["Revenue", "[1,234](https://www.sec.gov/a/filing.htm#r1)"],
    ]
    assert role_names(grid) == ["header", "body"]


def test_link_destination_digits_never_make_a_data_row():
    grid = [
        ["Item", "Description"],
        ["Note", "[See note](https://www.sec.gov/2025/12/34.htm)"],
    ]
    roles = row_roles(grid)
    assert roles.data_rows == ()
    assert role_names(grid) == ["header", "body"]


def test_nil_value_outside_the_label_column_makes_a_data_row():
    grid = [
        ["", "2025", "2024"],
        ["Impairment", "—", "12"],
    ]
    assert role_names(grid) == ["header", "body"]
    assert role_names([["", "2025"], ["Impairment", "—"]]) == ["header", "body"]


def test_empty_grid_has_no_roles():
    roles = row_roles([["", None], [None, ""]])
    assert roles.label_column is None
    assert roles.header_rows == roles.data_rows == ()
    assert roles.empty_rows == (0, 1)


# --- bare years and explicit header rows (spec revision 6) -------------------------------

def test_year_shaped_amounts_beside_a_row_label_are_data():
    # The completeness spec's Phase A case: "Revenue | 2000 | 1900" is a data row.
    grid = [
        th("Item", "2026", "2025"),
        ["Revenue", "2000", "1900"],
        ["Cost", "500", "400"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.data_rows == (1, 2)


def test_td_year_run_with_a_plain_label_is_header_like():
    # Revision 11 replaces the revision 6 limitation ("Segment | 2025 | 2024" read as data,
    # leaving the header zone empty): bare years never count in a year run.
    grid = [
        ["Segment", "2025", "2024"],
        ["Revenue", "2000", "1900"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body"]
    assert roles.data_rows == (1,)
    assert not counts_bare_years(grid[0], 0)


def test_year_row_with_an_empty_label_stays_header_like():
    # fixture:aapl-2023-10k table 15: "2023 | Change | 2022" beside an empty label cell.
    grid = [
        ["", "2023", "Change", "2022"],
        ["Americas", "$ 162,560", "(4) %", "$ 169,658"],
    ]
    assert role_names(grid) == ["header", "body"]
    assert not counts_bare_years(grid[0], 0)


@pytest.mark.parametrize("caption", [
    "Maturities (calendar year)", "Year Ended June 30,", "June 30,", "Fiscal Year",
])
def test_period_captioned_year_row_stays_header_like(caption):
    grid = [
        [caption, "2025", "2024"],
        ["Revenue", "100", "90"],
    ]
    assert role_names(grid) == ["header", "body"]
    assert not counts_bare_years(grid[0], 0)


@pytest.mark.parametrize("caption", [
    "(In millions)", "(in thousands, except per share data)", "Amounts in billions",
])
def test_unit_captioned_year_row_stays_header_like(caption):
    grid = [
        [caption, "2025", "2024"],
        ["Revenue", "100", "90"],
    ]
    assert role_names(grid) == ["header", "body"]
    assert not counts_bare_years(grid[0], 0)


def test_all_th_row_with_currency_amounts_is_never_data():
    # Phase A regression case: denominations in a th header row.
    grid = [
        th("Denomination", "€1", "€2"),
        ["Issued", "2", "1"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body"]
    assert roles.data_rows == (1,)
    assert is_explicit_header_row(grid[0])


def test_th_label_column_with_td_values_stays_data():
    grid = [
        th("Item", "2025", "2024"),
        [OriginCell("Revenue", header=True), "100", "200"],
        [OriginCell("Costs", header=True), "60", "70"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.data_rows == (1, 2)
    assert not is_explicit_header_row(grid[1])


def test_crm_26_control_years_beside_an_empty_label_stay_header():
    assert not counts_bare_years(CRM_26[1], 0)
    assert role_names(CRM_26) == ["header", "header", "body", "body", "body"]


def test_bare_years_need_a_label_cell_holding_origin_text():
    # A rowspan label leaves the label slot of its later rows span-covered.
    assert not counts_bare_years([None, "2000", "1900"], 0)
    assert not counts_bare_years(["", "2000", "1900"], 0)
    assert counts_bare_years(["Revenue", "2000", "1900"], 0)
    assert counts_bare_years([OriginCell("Revenue", header=True), "2000"], 0)


def test_explicit_header_row_needs_every_non_empty_cell_to_be_th():
    assert is_explicit_header_row(th("Item", "", "2025"))
    assert is_explicit_header_row([OriginCell("Item", True), OriginCell("", False), None])
    assert not is_explicit_header_row([OriginCell("Item", True), "2025"])
    assert not is_explicit_header_row(["", None])
# --- footnoted values and ranges (spec revision 7) ---------------------------------------

def test_footnoted_exhibit_numbers_are_body():
    # nvda-2002-10k's exhibit index: "2.1(1)" is a footnoted complete number, so its row is
    # body, not a second header row.
    grid = [
        ["Exhibit Number", "Description"],
        ["2.1(1)", "Asset Purchase Agreement"],
        ["4.1", "Specimen Stock Certificate"],
        ["10.2", "Stock Plan"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body"]
    assert roles.identifier_column is True
    assert roles.data_rows == (1, 2, 3)


def test_value_with_a_footnote_mark_makes_a_data_row():
    # nvda-2026-10k's trading-arrangement table: "3,984 *" is the first row's only amount.
    grid = [
        ["Name", "Title", "Action", "Date", "Total Shares to be Sold", "Expiration Date"],
        ["John O. Dabiri", "Director", "Adoption", "12/10/2025", "3,984 *", "12/7/2026"],
        ["Colette M. Kress", "Chief Financial Officer", "Adoption", "12/18/2025", "500,000", "3/23/2027"],
    ]
    assert role_names(grid) == ["header", "body", "body"]


def test_rows_of_ranges_are_data():
    # nvda-2026-10k's Black-Scholes table: range rows before the first single value.
    grid = [
        ["", "Jan 25, 2026", "Jan 26, 2025"],
        ["Weighted average expected life (in years)", "0.1 - 2.0", "0.2 - 1.0"],
        ["Risk-free interest rate", "3.5 %- 4.3 %", "3.6 %- 5.4 %"],
        ["Dividend yield", "0.03 %", "0.03 %"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body"]
    assert roles.data_rows == (1, 2, 3)


@pytest.mark.parametrize("label", ["", "Years ended December 31,"], ids=["empty-label", "period-caption"])
def test_bare_year_range_in_a_header_row_stays_header_like(label):
    grid = [
        [label, "2024 – 2026", "2021 – 2023"],
        ["Revenue", "100", "90"],
    ]
    assert role_names(grid) == ["header", "body"]


def test_bare_year_range_beside_a_row_label_follows_the_bare_year_rule():
    grid = [
        th("Notes", "Maturities"),
        ["Senior notes", "2027 - 2057"],
        ["Term loan", "2026 to 2028"],
    ]
    assert role_names(grid) == ["header", "body", "body"]


def test_text_holding_numbers_is_not_a_data_value():
    grid = [
        ["Topic", "Reference"],
        ["Liquidity", "Item 7 and 120"],
        ["Revenue", "1,234"],
    ]
    roles = row_roles(grid)
    # Revision 11: "Liquidity" is a row label, not a header-like label, so its row ends
    # the header zone and is body, as main renders it (was: header).
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.data_rows == (2,)
# --- section labels and fiscal-year values (spec revision 8) -----------------------------

def test_trailing_label_only_row_is_a_body_section_label():
    # nvda-2002-10k: "Accounts Receivable:" sits between the date header and the data.
    grid = [
        ["", "As of Jan 27, 2002", "As of Jan 28, 2001"],
        ["Accounts Receivable:", "", ""],
        ["Accounts receivable", "$ 100", "$ 90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (2,)


def test_every_trailing_label_only_row_is_body():
    grid = [
        ["", "2025", "2024"],
        ["Assets:", None, None],
        ["Current assets:", "", ""],
        ["Cash", "100", "90"],
    ]
    assert role_names(grid) == ["header", "body", "body", "body"]


def test_label_only_rows_above_period_rows_stay_header():
    # Negative control: the label-only rows are not trailing, so they stay in the header.
    grid = [
        ["Consolidated Statements of Operations", None, None],
        ["(In millions)", "", ""],
        ["", "Year Ended", None],
        ["", "Jan 25, 2026", "Jan 26, 2025"],
        ["Revenue", "100", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "header", "header", "body"]
    assert roles.header_rows == (0, 1, 2, 3)


def test_header_zone_of_label_only_rows_alone_is_empty():
    # Every header-zone row is a trailing label-only row: all are section labels.
    grid = [
        ["Revenue:", "", ""],
        ["Products", "100", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["body", "body"]
    assert roles.header_rows == ()


def test_label_only_first_row_of_a_table_without_data_stays_its_header():
    grid = [
        ["Signatures", None],
        ["Jane Doe", "Director"],
    ]
    assert role_names(grid) == ["header", "body"]


@pytest.mark.parametrize("caption", ["(In millions)", "Year Ended December 31,"], ids=["unit", "period"])
def test_caption_in_the_label_column_only_before_the_data_is_a_body_row(caption):
    # Spec revision 9: a unit or period caption written in the label column alone, right
    # before the first data row, is a label-only row, so it is a body row (main also
    # renders it in the body).
    grid = [
        ["", "2025", "2024"],
        [caption, "", ""],
        ["Revenue", "100", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (2,)


@pytest.mark.parametrize("caption", ["(In millions)", "Year Ended December 31,"], ids=["unit", "period"])
def test_caption_spanning_the_value_columns_before_the_data_stays_header(caption):
    # Counterpart: the same caption spanning the value columns is not label-only.
    grid = [
        ["", "2025", "2024"],
        ["", caption, None],
        ["Revenue", "100", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body"]
    assert roles.header_rows == (0, 1)
    assert roles.data_rows == (2,)


@pytest.mark.parametrize("caption", ["(In millions)", "Year Ended December 31,"], ids=["unit", "period"])
def test_full_width_caption_starting_in_the_label_column_before_the_data_is_a_body_row(caption):
    # Spec revision 15: label-only is decided by origin. A caption cell that starts in the
    # label column is label-only even when its colspan covers the value columns, so right
    # before the data it is a trailing label-only row: body. (A caption starting in a value
    # column stays header: the control above.)
    grid = [
        ["", "2025", "2024"],
        [caption, None, None],
        ["Revenue", "100", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (2,)
    assert is_label_only(grid[1], 0)
    assert not is_label_only(["", caption, None], 0)


@pytest.mark.parametrize("years", [("2024(a)", "2023(b)"), ("2024–25", "2023–24"), ("2024 – 2026", "2021 – 2023")],
                         ids=["footnoted-years", "fiscal-year-ranges", "bare-year-ranges"])
def test_year_like_header_row_stays_header(years):
    grid = [
        ["", *years],
        ["Revenue", "100", "90"],
    ]
    assert role_names(grid) == ["header", "body"]


@pytest.mark.parametrize("years", [("2024(a)", "2023(b)"), ("2024–25", "2023–24")],
                         ids=["footnoted-years", "fiscal-year-ranges"])
def test_year_like_values_beside_a_row_label_follow_the_bare_year_rule(years):
    grid = [
        th("Item", "First", "Second"),
        ["Plan term", *years],
    ]
    assert role_names(grid) == ["header", "body"]


# --- header-like rows, year runs and R0's captions (spec revision 11) --------------------

# The corpus run's reproductions (acceptance REPORT.md, S1): body rows before the first row
# with a complete number end the header zone instead of joining the header line.
def test_security_rows_below_the_column_headings_are_body():
    # fixture:aapl-2023-10k table 8: the trading symbols of the registered securities.
    grid = [
        ["Title of each class", "Trading symbol(s)", "Name of each exchange on which registered"],
        ["Common Stock, $0.00001 par value per share", "AAPL", "The Nasdaq Stock Market LLC"],
        ["1.375% Notes due 2024", "—", "The Nasdaq Stock Market LLC"],
        ["0.000% Notes due 2025", "—", "The Nasdaq Stock Market LLC"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (2, 3)


def test_values_with_units_below_the_year_row_are_body():
    grid = [
        ["", "2025", "2024"],
        ["Finance leases", "15.1 years", "13.7 years"],
        ["Operating leases", "7.4 years", "7.6 years"],
        ["Discount rate", "4.1 %", "3.6 %"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (3,)


def test_exhibit_rows_that_are_not_complete_numbers_are_body():
    # edgar:KO-10-K table 110's shape: three-part exhibit numbers are not complete numbers,
    # so the first data row is "10.6"; the rows above it after the first are body.
    grid = [
        ["10.5.22", "Plan A"],
        ["10.5.23", "Plan B"],
        ["10.5.24", "Plan C"],
        ["10.6", "Plan D"],
        ["10.7", "Plan E"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body", "body"]
    assert roles.identifier_column is True
    assert roles.data_rows == (3, 4)


def test_linked_exhibit_rows_with_plus_marks_are_body():
    # META 10-Q 2026-Q1 table 39's shape: "10.1+" is not a complete number, and the two
    # descriptions read alike apart from their link destinations.
    grid = [
        ["Exhibit Number", "Exhibit Description", "Filed Herewith"],
        ["10.1+", "[Amended Director Compensation Policy](https://example.com/ex101.htm)", "X"],
        ["10.2+", "[Amended Director Compensation Policy](https://example.com/ex102.htm)", "X"],
        ["31.1", "Certification of Chief Executive Officer", "X"],
        ["31.2", "Certification of Chief Financial Officer", "X"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (3, 4)


def test_column_heading_second_row_under_a_full_first_row_ends_the_header_zone():
    # A second header row whose label cell holds a column heading is body when main's
    # sparse-row fusion does not apply: the first row has origin text in two of the three
    # columns, so it is not sparse, and main renders the row in its body too.
    grid = [
        ["Obligations", "Payments Due by Period", None],
        ["Contractual obligations", "Total", "Less than 1 year"],
        ["Long-term debt", "$ 9,000", "$ 1,000"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.header_rows == (0,)


def test_column_heading_second_row_under_a_sparse_first_row_joins_the_header_zone():
    # Revision 12 (S8): main fuses this pair into its header line (the first row has no
    # origin text in 3 of 4 columns, the second has origin text in all 4), so it stays in
    # the zone. Revision 11 wrongly said main renders it in the body.
    grid = [
        ["", "Payments Due by Period", None, None],
        ["Contractual obligations", "Total", "Less than 1 year", "1-3 years"],
        ["Long-term debt", "$ 9,000", "$ 1,000", "$ 2,000"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body"]
    assert roles.header_rows == (0, 1)


@pytest.mark.parametrize("second", [
    ["", "Jan 25, 2026", "Jan 26, 2025"],
    [None, "Jan 25, 2026", "Jan 26, 2025"],
    ["Year Ended December 31,", "Actual", "Budget"],
    ["(In millions)", "Actual", "Budget"],
    ["(Dollars in millions)", "Actual", "Budget"],
    ["(Unaudited)", "Actual", "Budget"],
    ["2024(a)", "Actual", "Budget"],
    ["Segment", "2025", "2024"],
    th("Item", "Actual", "Budget"),
], ids=["empty-label", "span-covered-label", "period-label", "unit-declaration-label",
        "unit-caption-label", "audit-caption-label", "year-like-label", "year-run", "th-row"])
def test_header_like_second_rows_keep_the_multi_row_header(second):
    grid = [
        ["Consolidated", "Year Ended", None],
        second,
        ["Revenue", "100", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body"]
    assert roles.header_rows == (0, 1)


def test_rows_below_the_row_that_ends_the_zone_are_body_even_when_header_like():
    grid = [
        ["", "2025", "2024"],
        ["Common Stock", "AAPL", "AAPL"],
        ["", "Actual", "Actual"],
        ["Revenue", "100", "90"],
    ]
    assert role_names(grid) == ["header", "body", "body", "body"]


@pytest.mark.parametrize("row", [
    ["Function", "2022", "2023", "2024"],
    ["(Dollars in millions)", "2024", "2023"],
    ["(Millions of dollars)", "2024", "2023"],
    ["(Unaudited)", "2024", "2023"],
    ["2023", "2022"],
], ids=["year-run", "dollars-caption", "millions-of-dollars", "unaudited", "first-year-in-label-column"])
def test_td_years_rows_are_header(row):
    # The corpus run's years rows (TSM 136, BAC, CAT, JPM 543/662): never data.
    grid = [row, ["Revenue", "100", "90", "80"][:len(row)]]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body"]
    assert roles.data_rows == (1,)


def test_years_row_under_a_table_title_stays_in_the_header():
    # edgar:BAC-10-K table 46's shape: title row, unit-caption years row, section label.
    grid = [
        ["Table 2", "Noninterest Income", None],
        ["(Dollars in millions)", "2024", "2023"],
        ["Fees and commissions:", "", ""],
        ["Card income", "$ 5,964", "$ 5,957"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body", "body"]
    assert roles.header_rows == (0, 1)
    assert roles.data_rows == (3,)


def test_year_shaped_amounts_beside_a_td_row_label_stay_data():
    grid = [
        ["", "2026", "2025"],
        ["Revenue", "2000", "1900"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body"]
    assert roles.data_rows == (1,)
    assert counts_bare_years(grid[1], 0)


def test_named_limitation_bare_years_within_one_read_as_a_header_row():
    # Named limitation (revision 11): a data row whose only numbers are bare years within
    # one of each other, "Units | 2024 | 2025", is a year run, so it is header-like and
    # never data.
    grid = [
        th("Item", "First", "Second"),
        ["Units", "2024", "2025"],
        ["Revenue", "100", "90"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body"]
    assert roles.data_rows == (2,)


def test_year_run_followed_by_no_data_row_is_the_header_alone():
    grid = [
        ["Units", "2024", "2025"],
        ["Plant", "Austin", "Berlin"],
    ]
    roles = row_roles(grid)
    assert roles.data_rows == ()
    assert role_names(grid) == ["header", "body"]


@pytest.mark.parametrize("row", [
    ["Function", "2022", "2023", "2024"],
    ["", "2025", "2024", "2025", "2024"],
    ["Segment", "2023", "2024", "2025", "2025"],
    ["", "2023", "Change", "2022"],
    ["Units", "2024", "—", "2025"],
], ids=["ascending", "repeated-pairs", "equal-neighbours", "text-between", "nil-between"])
def test_year_runs(row):
    assert is_year_run(row, 0)


@pytest.mark.parametrize("row", [
    ["Revenue", "2000", "1900"],
    ["Units", "2024"],
    ["Item", "2024", "100"],
    ["Item", "2024(a)", "2023(a)"],
    ["Item", "2024", "2026"],
    ["2024", "2023"],
], ids=["far-apart", "one-year", "with-an-amount", "footnoted-years", "two-apart", "label-year-only"])
def test_not_year_runs(row):
    assert not is_year_run(row, 0)


@pytest.mark.parametrize("text", [
    "(In millions)", "(in thousands, except per share data)", "Amounts in billions",
    "(Dollars in millions)", "(Millions of dollars)", "(Dollars in billions)",
    "(Dollars in millions, except per share amounts)", "(Dollars in millions except per share data)",
    "(Dollars in millions, shares in thousands)", "(Dollars in millions, amounts pretax)",
    "(Dollars in thousands)", "($ in millions)", "($ in millions, except earnings per share)",
    "Millions of dollars", "(Billions of dollars)", "(U.S. dollars in millions)",
    "(Unaudited)", "(Audited)", "( unaudited )",
])
def test_unit_text(text):
    assert is_unit_text(text)


@pytest.mark.parametrize("text", [
    "Revenue", "Dollars", "(Shares in millions)", "(Notional in millions)", "Unaudited",
    "Consolidated Balance Sheets (unaudited):", "Total revenue (in millions)", "$250 billion",
    "U.S. dollar notes due 2024-2093",
])
def test_not_unit_text(text):
    assert not is_unit_text(text)


def test_period_text_is_the_shared_pattern():
    assert is_period_text("Year Ended June 30,")
    assert is_period_text("Jan 25, 2026")
    assert not is_period_text("Revenue")


@pytest.mark.parametrize("row, expected", [
    (["", "2025"], True),
    ([None, "2025"], True),
    (["Year Ended", "Actual"], True),
    (["(Millions of dollars)", "Actual"], True),
    (["2024", "Actual"], True),
    (["Function", "2022", "2023"], True),
    ([OriginCell("Item", True), OriginCell("Actual", True)], True),
    (["Common Stock", "AAPL"], False),
    (["10.5.23", "Plan B"], False),
    (["Contractual obligations", "Total"], False),
    (["Revenue", "2000", "1900"], False),
    # Revision 12: a label-only row (a second title line, a section label) is header-like.
    (["CONDENSED CONSOLIDATED BALANCE SHEETS", None, None], True),
    (["Assets:", "", ""], True),
])
def test_header_like_rows(row, expected):
    assert is_header_like(row, 0) is expected


# --- label-only rows and main's sparse-row fusion (spec revision 12) ---------------------

# The round-2 corpus run's reproductions (acceptance REPORT-round2.md, S7 and S8).

# fixture:nvda-2026-ex99-1 unit 5, cleaned grid: two stacked full-width titles, two
# full-width captions, the date rows with empty label cells, then section labels and data.
NVDA_EX99_1_UNIT_5 = [
    ["NVIDIA CORPORATION", None, None],
    ["CONDENSED CONSOLIDATED BALANCE SHEETS", None, None],
    ["(In millions)", None, None],
    ["(Unaudited)", None, None],
    ["", "July 26,", "January 25,"],
    ["", "2026", "2026"],
    ["ASSETS", None, None],
    ["Current assets:", None, None],
    ["Cash and cash equivalents", "$ 22,443", "$ 10,605"],
    ["Marketable debt securities", "34,143", "39,065"],
]


def test_stacked_title_rows_continue_the_header_zone():
    # S7: the second title is a label-only row, so it continues the zone; the dates join
    # the header line and the trailing section labels stay body.
    roles = row_roles(NVDA_EX99_1_UNIT_5)
    assert role_names(NVDA_EX99_1_UNIT_5) == [
        "header", "header", "header", "header", "header", "header", "body", "body", "body", "body"]
    assert roles.header_rows == (0, 1, 2, 3, 4, 5)
    assert roles.data_rows == (8, 9)


def test_stacked_titles_over_a_period_caption_stay_header():
    # fixture:nvda-2026-ex99-1 unit 11: two titles, then the outlook caption and its unit
    # caption over the value column.
    grid = [
        ["NVIDIA CORPORATION", None],
        ["RECONCILIATION OF GAAP TO NON-GAAP OUTLOOK", None],
        ["", "Q3 FY2027 Outlook"],
        ["", "($ in billions)"],
        ["GAAP gross margin", "74.0 %"],
        ["Impact of acquisition-related costs", "—"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "header", "header", "body", "body"]
    assert roles.header_rows == (0, 1, 2, 3)


def test_stacked_titles_right_before_the_data_leave_the_zone():
    # Trailing label-only rows still leave the zone, however many: here every row before
    # the data is label-only, so the zone is empty.
    grid = [
        ["NVIDIA CORPORATION", None, None],
        ["CONDENSED CONSOLIDATED BALANCE SHEETS", None, None],
        ["Cash and cash equivalents", "$ 22,443", "$ 10,605"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["body", "body", "body"]
    assert roles.header_rows == ()


def test_lease_term_title_above_values_with_units_stays_a_body_row():
    # Round-2 control (META 10-K table 45's shape): the label-only lease-term title
    # continues the zone, "Finance leases | 15.1 years" ends it (the years row above is not
    # sparse: it has origin text in 2 of 3 columns), and the title is then a trailing
    # label-only row, so it is body.
    grid = [
        ["", "2025", "2024"],
        ["Weighted-average remaining lease term:", "", ""],
        ["Finance leases", "15.1 years", "13.7 years"],
        ["Operating leases", "7.4 years", "7.6 years"],
        ["Weighted-average discount rate:", "", ""],
        ["Finance leases", "3.5 %", "3.4 %"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body", "body", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (5,)


def test_label_only_row_between_header_rows_stays_header():
    grid = [
        ["", "Year Ended", None],
        ["Statements of Operations", None, None],
        ["", "2025", "2024"],
        ["Revenue", "100", "90"],
    ]
    assert role_names(grid) == ["header", "header", "header", "body"]


def test_exhibit_index_title_over_its_column_headings_fuses_like_main():
    # S8: a full-width title over the column headings. The title row has no origin text in
    # 2 of 3 columns and the headings fill all 3, so main fuses the pair.
    grid = [
        ["Exhibit Index", None, None],
        ["Exhibit Number", "Description", "Filed Herewith"],
        ["3.1", "Articles of Incorporation", ""],
        ["31.1", "Certification", "X"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body", "body"]
    assert roles.header_rows == (0, 1)
    assert roles.identifier_column is True


# rcq META 10-K 2025-FY table 37, cleaned grid: a spanning measurement caption, then the
# column headings with the balance date in the first value column.
META_10K_2025_37 = [
    ["", "", None, "Fair Value Measurement at Reporting Date Using", None, None, None, None, None],
    ["Description", "December 31, 2024", None, "Quoted Prices in Active Markets (Level 1)", None,
     "Significant Other Observable Inputs (Level 2)", None, "Significant Unobservable Inputs (Level 3)", None],
    ["Cash equivalents:", "", "", "", "", "", "", "", ""],
    ["Money market funds", "$", "36,165", "$", "36,165", "$", "—", "$", "—"],
    ["Time deposits", "", "369", "", "—", "", "369", "", "—"],
]

# edgar:TSLA-10-K-2025-01-30.htm table 40, cleaned grid: a period span, then a statement
# title in the label column beside the quarter-end dates.
TSLA_40 = [
    ["", "Three Months Ended", None, None, None, None, None],
    ["Condensed Consolidated Statements of Operations (unaudited):", "March 31, 2024", None,
     "June 30, 2024", None, "September 30, 2024", None],
    ["Other income (expense), net", "", "", "", "", "", ""],
    ["Before adoption", "$", "108", "$", "20", "$", "(270)"],
    ["Adjustments", "", "335", "", "(100)", "", "7"],
]


@pytest.mark.parametrize("grid", [META_10K_2025_37, TSLA_40], ids=["meta-10k-2025-37", "tsla-40"])
def test_column_heading_rows_main_fused_stay_in_the_header_zone(grid):
    # S8: 9 (META) and 7 (TSLA) columns hold origin text; the first row has text in 1 of
    # them, the second in 5 and 4 (at least max(2, n // 2) = 4 and 3). The section label
    # below continues the zone and then leaves it as a trailing label-only row.
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body", "body", "body"]
    assert roles.header_rows == (0, 1)
    assert roles.data_rows == (3, 4)


@pytest.mark.parametrize("grid", [
    # The first row has origin text in every column, so it is not sparse.
    [["Title of each class", "Trading symbol(s)", "Name of each exchange on which registered"],
     ["Common Stock, $0.00001 par value per share", "AAPL", "The Nasdaq Stock Market LLC"],
     ["1.375% Notes due 2024", "—", "The Nasdaq Stock Market LLC"]],
    # The years row has origin text in 2 of 3 columns: 1 empty column < max(2, 3 // 2).
    [["", "2025", "2024"],
     ["Finance leases", "15.1 years", "13.7 years"],
     ["Discount rate", "4.1 %", "3.6 %"]],
], ids=["securities", "lease-terms"])
def test_sparse_row_fusion_needs_a_sparse_first_row(grid):
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.header_rows == (0,)


def test_sparse_row_fusion_needs_a_full_second_row():
    # The second row has origin text in 2 of 6 columns, fewer than max(2, 6 // 2) = 3, and
    # it is not label-only, so its label text ends the zone (main does not fuse it either).
    grid = [
        ["", "Payments Due by Period", None, None, None, None],
        ["Contractual obligations", "", "", "", "", "Note 4"],
        ["Long-term debt", "$ 9,000", "$ 1,000", "$ 2,000", "$ 3,000", "$ 4,000"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "body", "body"]
    assert roles.header_rows == (0,)


def test_third_column_heading_row_under_a_fused_pair_ends_the_zone():
    # The fusion applies to the second row only; a third column-heading row is body.
    grid = [
        ["", "Payments Due by Period", None, None],
        ["Contractual obligations", "Total", "Less than 1 year", "1-3 years"],
        ["Obligation type", "All", "Short", "Medium"],
        ["Long-term debt", "$ 9,000", "$ 1,000", "$ 2,000"],
    ]
    roles = row_roles(grid)
    assert role_names(grid) == ["header", "header", "body", "body"]
    assert roles.header_rows == (0, 1)


def test_sparse_row_fusion_counts_only_columns_with_origin_text():
    # Coordinate equivalence: the checker's placed grid keeps empty spacer columns and
    # span-covered slots. Counting all 10 physical columns would need 5 heading cells
    # (max(2, 10 // 2)); the 4 columns with origin text need 2, as on the cleaned grid.
    placed = [
        ["", "", "Exhibit Index", None, None, None, None, None, None, ""],
        ["", "", "Exhibit Number", "", "Description", None, "Form", "", "Filed Herewith", ""],
        ["", "", "3.1", "", "Articles of Incorporation", None, "8-K", "", "", ""],
        ["", "", "31.1", "", "Certification", None, "", "", "X", ""],
    ]
    cleaned = [
        ["Exhibit Index", None, None, None],
        ["Exhibit Number", "Description", "Form", "Filed Herewith"],
        ["3.1", "Articles of Incorporation", "8-K", ""],
        ["31.1", "Certification", "", "X"],
    ]
    expected = ["header", "header", "body", "body"]
    assert role_names(placed) == expected
    assert role_names(cleaned) == expected
    assert row_roles(placed).label_column == 2
    assert row_roles(cleaned).label_column == 0


@pytest.mark.parametrize("row, expected", [
    (["CONDENSED CONSOLIDATED BALANCE SHEETS", None, None], True),
    (["Assets:", "", "\u200b"], True),
    ([None, "Assets:", ""], False),
    (["Revenue", "100"], False),
    (["", ""], False),
])
def test_label_only_rows(row, expected):
    assert is_label_only(row, 0) is expected


# --- marker-only columns leave the sparse-row count (spec revision 13) ------------------

# The round-3 corpus run's S9 reproduction (edgar:AMZN-10-Q-2025-10-31.htm table 21): the
# two "%" columns are marker-only, so n is 3, not 5, and the dates row is not sparse.
AMZN_10Q_21 = [
    ["", "December 31, 2024", None, "September 30, 2025", None],
    ["Remaining lease term, operating leases", "10.6 years", None, "10.0 years", None],
    ["Remaining lease term, finance leases", "11.9 years", None, "12.1 years", None],
    ["Discount rate, operating leases", "3.5", "%", "3.6", "%"],
]

# edgar:JPM-10-K-2025-02-14.htm table 207's shape, the mirror case: each period has a "$"
# column (which also holds values and the dates), a value column and a "%" column; the
# three "%" columns are marker-only, so n is 7, not 10, and the headings row is full.
JPM_207 = [
    ["", "Three months ended", None, None, None, None, None, None, None, None],
    ["Average amount (in millions)", "December 31, 2024", None, None, "September 30, 2024", None, None,
     "December 31, 2023", None, None],
    ["JPMorgan Chase & Co.:", "", "", "", "", "", "", "", "", ""],
    ["Eligible cash (a)", "$", "396,123", "", "$", "412,389", "", "$", "485,263", ""],
    ["Eligible securities (b)(c)", "464,877", None, "", "453,899", None, "", "313,365", None, ""],
    ["LCR", "113", None, "%", "114", None, "%", "113", None, "%"],
]

# fixture:nvda-2026-10k unit 38's shape, the control: the "$" columns also hold the dates and
# values written from them, so they are not marker-only and still count (n = 5).
NVDA_10K_38 = [
    ["", "Jan 25, 2026", None, "Jan 26, 2025", None],
    ["Inventories:", "(In millions)", None, None, None],
    ["Raw materials", "$", "3,807", "$", "3,408"],
    ["Work in process", "8,822", None, "3,399", None],
]


def test_marker_columns_never_make_a_values_row_fuse_like_main():
    # S9: main kept the operating-lease row in its body, and so does R0 now.
    roles = row_roles(AMZN_10Q_21)
    assert role_names(AMZN_10Q_21) == ["header", "body", "body", "body"]
    assert roles.header_rows == (0,)
    assert roles.data_rows == (3,)
    assert not fuses_like_main(AMZN_10Q_21)


def test_headings_row_fuses_when_marker_columns_leave_the_count():
    # JPM 207: main fuses the headings into its header line; R0 keeps them in the zone, and
    # the trailing section label leaves it.
    roles = row_roles(JPM_207)
    assert role_names(JPM_207) == ["header", "header", "body", "body", "body", "body"]
    assert roles.header_rows == (0, 1)
    assert fuses_like_main(JPM_207)


def test_currency_columns_that_also_hold_values_or_dates_still_count():
    roles = row_roles(NVDA_10K_38)
    assert role_names(NVDA_10K_38) == ["header", "header", "body", "body"]
    assert roles.header_rows == (0, 1)
    assert fuses_like_main(NVDA_10K_38)


@pytest.mark.parametrize("grid, expected", [
    ([["Exhibit Index", None, None], ["Exhibit Number", "Description", "Filed Herewith"],
      ["3.1", "Articles", "X"]], True),
    ([["", "Payments Due by Period", None, None], ["Obligations", "Total", "Short", "Long"],
      ["Debt", "1", "2", "3"]], True),
    # The first row needs max(2, n // 2) columns without origin text.
    ([["", "2025", "2024"], ["Finance leases", "15.1 years", "13.7 years"], ["Rate", "4.1 %", "3.6 %"]], False),
    ([["Title of each class", "Trading symbol(s)"], ["Common Stock", "AAPL"]], False),
    # The second row needs origin text in max(2, n // 2) columns: 3 of 6 here.
    ([["", "", "Caption", None, None, None], ["Label", "", "A", "", "", ""], ["R", "1", "2", "3", "4", "5"]],
     False),
    ([["", "", "Caption", None, None, None], ["Label", "", "A", "", "B", ""], ["R", "1", "2", "3", "4", "5"]],
     True),
    # Span-covered and zero-width slots hold no origin text; empty rows are ignored.
    ([["Title", None, None, "\u200b"], ["A", "B", None, None], ["R", "1", "2", "3"]], True),
    ([["Title", None, None, "\u200b"], ["A", None, None, None], ["R", "1", "2", "3"]], False),
    ([["", "", "", ""], ["Title", None, None, None], ["A", "B", None, None], ["R", "1", "2", "3"]], True),
    # Revision 13: a column whose every origin text is a currency marker, "%", ")", ")%" or "("
    # is marker-only and leaves n and both counts.
    ([["", "", "Q1", "", "Q2"], ["Item", "", "A", "", "B"], ["Cost", "$", "10", "$", "20"]], False),
    ([["", "Q1", "", "Q2", ""], ["Item", "A", "", "B", ""], ["Rate", "3.5", "%", "3.6", "%"]], False),
    ([["", "Q1", "", "Q2", ""], ["Item", "A", "", "B", ""], ["Loss", "(10", ") %", "(20", ")%"]], False),
    ([["", "", "Q1", "", "Q2"], ["Item", "", "A", "", "B"], ["Loss", "(", "10)", "(", "20)"]], False),
    ([["", "", "Q1", "", "Q2"], ["Item", "", "A", "", "B"], ["Cost", "RMB", "10", "€", "20"]], False),
    # Not marker-only: unknown codes, a marker column that also holds a value, a marker
    # under a heading in the same column.
    ([["", "", "Q1", "", "Q2"], ["Item", "", "A", "", "B"], ["Cost", "ABC", "10", "XYZ", "20"]], True),
    ([["", "", "Q1", "", "Q2"], ["Item", "", "A", "", "B"], ["Cost", "$", "10", "$", "20"],
      ["Total", "15", None, "25", None]], True),
    ([["", "Q1", "", "Q2", ""], ["Item", "A", "", "B", ""], ["Cost", "$", "10", "$", "20"]], True),
], ids=["exhibit-title", "payments-span", "years-row-not-sparse", "two-columns", "second-row-short",
        "second-row-full", "span-and-zero-width", "zero-width-second-row-short", "leading-empty-row",
        "currency-columns", "percent-columns", "close-percent-columns", "open-columns", "currency-codes",
        "unknown-codes-count", "currency-column-holding-values", "marker-under-a-heading-counts"])
def test_main_sparse_row_fusion(grid, expected):
    assert fuses_like_main(grid) is expected


# --- predicates --------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "9,943", "(29)", "36.5 %", "$ 1,234", "RMB 941,168", ".75", "3.1", "9",
    "(3.2)%", "€ (1,234)", "NT$ 1,329.2", "−5", "(.62)", "$(120)", "( 29)", "2,191,446,233",
    # Revision 7: footnoted values and ranges.
    "2.1(1)", "3,984 *", "104**", "1,234 (1)", "10.1(10)", "36.5 %(a)", "$ 1,234 †", "9‡", "4.3 [1]",
    "(29)(1)", "1,234 (a)(2)", "3.5 %- 4.3 %", "0.2 - 1.0", "0.1 - 2.0", "26 %- 96 %", "1 – 2",
    "$ 10 to $ 20", "(5)—(3)", "RMB 1.2 - RMB 1.5",
])
def test_complete_numbers(text):
    assert is_complete_number(text)


@pytest.mark.parametrize("text", [
    "2025", "1999", "—", "(29", "29)", "abc", "XYZ 100", "$", "5, 24", "",
    "Jan 25, 2026", "1,",
    # Revision 7 controls: text holding numbers, unlisted marks, bare years with marks or
    # in ranges (year-like), more than two numbers, a range with a footnote.
    "Item 7 and 120", "1,234 (123)", "1,234 (ab)", "1,234 [a]", "*", "(1)(2)x", "2025 (1)", "2024(a)",
    "2024 – 2026", "2023-2024", "2024–25", "1 - 2 - 3", "1 to", "0.1 - 2.0 (1)", "Note 2", "5 or 6",
])
def test_not_complete_numbers(text):
    assert not is_complete_number(text)


# Revision 14: one currency marker, thousands in groups of three (or plain digits), one "%".
@pytest.mark.parametrize("text", [
    "$ $ 5", "USD $ 5", "$ ($ 120)", "RMB (€ 5)", "5 % %", "(3.2 %)%", "$ 1,234 % %",
    "1,,2", "12,34", "(12,34)", "1,00,000", "12,345,6", "0,5", "1,2345",
])
def test_standalone_numbers_have_one_marker_one_percent_and_groups_of_three(text):
    assert not is_complete_number(text)


@pytest.mark.parametrize("text", [
    "US$ 1,250.0", "$ (120)", "($ 120)", "( $ 120 )", "(3.2 %)", "(3.2) %", "$ 5 %", "$-5", "+5", "– 5",
    "(−5)", "1234", "1,234.5", "1,234,567.89", "0.000", "RMB(1,234)", "($ 120 %)",
])
def test_standalone_numbers_keep_every_form_with_one_marker_and_one_percent(text):
    assert is_complete_number(text)


def test_split_negatives_rebuild_only_standalone_amounts():
    # "(12,34" is not an open amount, so it and ")" stay apart, and neither is a value.
    assert row_values(["Loss", "(12,34", ")"]) == [(0, "Loss"), (1, "(12,34"), (2, ")")]
    assert row_values(["Loss", "(1,234", ")"]) == [(0, "Loss"), (1, "(1,234)")]


def test_bare_year_is_four_digits_from_1900_to_2099():
    assert is_bare_year("1900") and is_bare_year("2099") and is_bare_year(" 2025 ")
    assert not is_bare_year("1899") and not is_bare_year("2100") and not is_bare_year("$ 2025")
    assert is_complete_number("1899") and is_complete_number("$ 2025")


@pytest.mark.parametrize("text, expected", [
    ("2025", True), ("2025 (1)", True), ("2024(a)", True), ("2024 – 2026", True), ("2023-2024", True),
    ("2025 to 2026", True), ("2024 — 2026", True),
    ("2024–25", True), ("2024 – 25", True), ("2024-25", True), ("2024 — 25", True),
    ("1899", False), ("$ 2025", False), ("2.1(1)", False), ("Fiscal 2025", False), ("2024–5", False),
    ("2024–255", False), ("24–25", False),
])
def test_year_like_values(text, expected):
    # Revisions 7 and 8: a footnoted bare year, a range of two bare years and a fiscal-year
    # range ("2024–25") follow the bare-year rule.
    assert is_year_like(text) is expected


@pytest.mark.parametrize("text, expected", [
    ("—", True), ("–", True), ("-", True), ("−", True), (" — ", True),
    ("--", False), ("0", False), ("— (1)", False), ("", False),
])
def test_nil_values(text, expected):
    assert is_nil_value(text) is expected


@pytest.mark.parametrize("text", ["$", "€", "£", "¥", "US$", "NT$", "HK$", "A$", "C$", "S$",
                                  "USD", "EUR", "GBP", "JPY", "CNY", "RMB", "CHF", "DKK", "SEK",
                                  "NOK", "HKD", "TWD", "CAD", "AUD", "INR", "KRW", "SGD"])
def test_currency_markers_are_the_closed_list(text):
    assert is_currency_marker(text)


@pytest.mark.parametrize("text", ["ABC", "XYZ", "rmb", "$$", "US", "RMB 1", "(", "%"])
def test_unknown_codes_are_not_currency_markers(text):
    assert not is_currency_marker(text)


def test_visible_text_drops_zero_width_characters_and_link_destinations():
    assert visible_text("\u200b") == ""
    assert visible_text("1,234\u200b\u200c\u200d\u2060\ufeff") == "1,234"
    assert visible_text("[Revenue](https://x/2025.htm) (1)") == "Revenue (1)"
    assert visible_text(None) == ""


def test_row_values_rebuild_split_negatives_at_the_digit_column():
    row = ["Loss", "(29", ")", "", "(3.2", ")%", "(", "40", ")", "\u200b"]
    assert row_values(row) == [(0, "Loss"), (1, "(29)"), (4, "(3.2)%"), (7, "(40)")]


def test_row_values_skip_span_covered_and_empty_slots():
    assert row_values([None, "", "A", None, "\u200b", "1"]) == [(2, "A"), (5, "1")]
