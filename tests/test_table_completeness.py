"""Unit tests for the table completeness checks (spec 2026-10-02, revision 6)."""

from collections import Counter

import pytest
from bs4 import BeautifulSoup

from sec2md.table_completeness import (
    cell_text,
    hidden_sets,
    merge_split_negatives,
    numbers,
    output_line_numbers,
)


def soup_of(html):
    return BeautifulSoup(html, "lxml")


# --- task 2: text and tokens -----------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("€123", ("123",)),
    ("£456", ("456",)),
    ("$ (16,173)", ("-16173",)),
    ("3.5%-4.3%", ("3.5", "4.3")),
    ("2024 – 2026", ("2024", "2026")),
    ("Revenue", ()),
])
def test_numbers_normalizes_currency_and_range_dashes(text, expected):
    assert numbers(text) == expected


@pytest.mark.parametrize("cells, expected", [
    (["Loss", "(29", ")"], ["Loss", "(29)"]),
    (["Loss", "(", "29", ")"], ["Loss", "(29)"]),
    (["Margin", "(3.2", ")%"], ["Margin", "(3.2)%"]),
    (["Revenue", "", "120", " "], ["Revenue", "120"]),
])
def test_merge_split_negatives(cells, expected):
    assert merge_split_negatives(cells) == expected


def test_output_line_numbers_tokenizes_each_cell_separately():
    assert output_line_numbers("| Loss | (29 | ) | 1,2 | 34 |") == ["-29", "12", "34"]


def test_hidden_sets_scopes_to_outermost_tables():
    soup = soup_of(
        '<div style="display:none"><table id="a"><tr><td>1</td></tr></table></div>'
        '<table id="b"><tr><td>2<span style="display:none">999</span>'
        '<table id="c"><tr><td>3</td></tr></table></td></tr></table>'
    )
    outermost, hidden, _ = hidden_sets(soup)
    assert [t["id"] for t in outermost] == ["a", "b"]
    assert id(soup.find(id="a")) in hidden
    assert id(soup.find(id="b")) not in hidden
    assert id(soup.find("span")) in hidden


@pytest.mark.parametrize("cell, expected", [
    ("<td>1,2<span>34</span></td>", ("1,234", "")),
    ("<td>Revenue<sup>(1)</sup></td>", ("Revenue", "(1)")),
    ('<td>Revenue<span style="vertical-align:super">2</span></td>', ("Revenue", "2")),
    ('<td>Revenue<a href="#f1">(1)</a></td>', ("Revenue", "(1)")),
    # NVDA kerns single digits with relative positioning and splits dates across
    # fragment links; neither is a footnote marker.
    ('<td><span style="position:relative;top:1px">1</span>23</td>', ("123", "")),
    ('<td>January <a href="#x">2</a>9, 2025</td>', ("January 29, 2025", "")),
    ("<td>Revenue<br/>Net</td>", ("Revenue Net", "")),
])
def test_cell_text_separates_footnote_markers(cell, expected):
    soup = soup_of(f"<table><tr>{cell}</tr></table>")
    _, hidden, _ = hidden_sets(soup)
    assert cell_text(soup.find("td"), hidden) == expected


def test_cell_text_skips_hidden_descendants():
    soup = soup_of('<table><tr><td>100<span style="display:none">999</span></td></tr></table>')
    _, hidden, _ = hidden_sets(soup)
    assert cell_text(soup.find("td"), hidden) == ("100", "")


# --- task 3: classes, positions and period rows ------------------------------------------

from sec2md.table_completeness import (  # noqa: E402
    classify_cell,
    is_data_row,
    is_period_row,
    label_key,
    output_positions,
)


@pytest.mark.parametrize("text, signature_row, expected", [
    ("9,943", False, [("9943", "value_numeric")]),
    ("Revenue 2026", False, [("2026", "value_text")]),
    ("Note 9 Impairment", False, [("9", "reference")]),
    ("Previously filed as Exhibit 2.1", False, [("2.1", "reference")]),
    ("Item 7 and 120", False, [("7", "reference"), ("120", "value_text")]),
    ("Date:", False, []),
    ("January 29, 2025", True, [("29", "reference"), ("2025", "reference")]),
    ("January 29, 2025", False, [("29", "value_text"), ("2025", "value_text")]),
])
def test_classify_cell(text, signature_row, expected):
    assert classify_cell(text, signature_row) == expected


@pytest.mark.parametrize("text, expected", [
    ("Total revenue", "totalrevenue"),
    ("Note 1", "note#1"),
    ("Note 2", "note#2"),
    ("Note 9 Impairment", "noteimpairment#9"),
    ("", ""),
])
def test_label_key_keeps_identifier_numbers(text, expected):
    assert label_key(text) == expected


@pytest.mark.parametrize("cells, before_header_end, expected", [
    (["", "2023", "2022"], False, True),
    (["Maturities (calendar year)", "2023", "2022"], False, True),
    (["", "Three Months Ended June 30, 2025", "Three Months Ended June 30, 2024"], False, True),
    (["Revenue", "2000", "1900"], False, False),
    (["Revenue", "2,000"], True, True),
])
def test_is_period_row_uses_context_not_number_shape(cells, before_header_end, expected):
    assert is_period_row(cells, before_header_end) is expected


def test_is_data_row_needs_a_standalone_amount():
    assert is_data_row(["Revenue", "2000", "1900"], False)
    assert not is_data_row(["Revenue", "grew strongly"], False)
    assert not is_data_row(["", "2023", "2022"], False)


def test_output_positions_tags_each_token_with_its_position():
    segment = ("| Item | 2026 |\n| --- | --- |\n| Revenue | 1,234 (1) |\n"
               "| Loss | $ (96) |\n| Note 9 Impairment | 9 |")
    body, other = output_positions(segment, exhibit_index=False)
    # "(1)" normalizes like an accounting negative on both sides, so markers match as "-1".
    assert body == [
        ("revenue", Counter({("1234", "numeric_cell"): 1, ("-1", "text_cell"): 1})),
        ("loss", Counter({("-96", "numeric_cell"): 1})),
        ("noteimpairment#9", Counter({("9", "reference"): 1, ("9", "numeric_cell"): 1})),
    ]
    assert other == Counter({("2026", "header_line"): 1})


def test_output_positions_without_separator_is_text_rendering():
    body, other = output_positions("ITEM 8. FINANCIAL STATEMENTS 2026", exhibit_index=False)
    assert body == []
    assert other == Counter({("8", "reference"): 1, ("2026", "text_rendering"): 1})


def test_output_positions_exhibit_index_body_is_all_references():
    segment = "| Exhibit | Description |\n| --- | --- |\n| 3.1 | Restated Certificate, filed 2020 |"
    body, _ = output_positions(segment, exhibit_index=True)
    assert body == [("", Counter({("3.1", "reference"): 1, ("2020", "reference"): 1}))]


# --- task 4: header rows without building snapshots --------------------------------------

from sec2md.table_completeness import header_row_count, unit_rows  # noqa: E402
from sec2md.xlsx_tables import _header_count, snapshot_html_table  # noqa: E402


def snapshot_header_rows(table):
    """Header rows as the XLSX snapshot grid counts them (the reference implementation)."""
    snap = snapshot_html_table(table, ordinal=1, page=1, source_url=None)
    if not snap.source_cells or snap.issues:
        return 0
    height = max(c.row + max(c.rowspan, 1) for c in snap.source_cells)
    width = max(c.column + max(c.colspan, 1) for c in snap.source_cells)
    grid = [[None] * width for _ in range(height)]
    for c in snap.source_cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                grid[r][k] = c
    return _header_count(grid)


HEADER_TABLES = [
    "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>",
    "<table><tr><td></td><td>2023</td><td>2022</td></tr><tr><td>Revenue</td><td>2,000</td><td>1,900</td></tr></table>",
    ('<table><tr><td></td><td colspan="2">Year ended December 31,</td></tr>'
     "<tr><td></td><td>2024</td><td>2023</td></tr><tr><td>Revenue</td><td>1,300</td><td>804</td></tr></table>"),
    ('<table><tr><td rowspan="2">Item</td><td>2026</td></tr><tr><td>120</td></tr>'
     "<tr><td>Cost</td><td>50</td></tr></table>"),
    '<table><tr><td colspan="bad">Unreliable</td><td>123</td></tr><tr><td>Tail</td><td>456</td></tr></table>',
    '<table><tr><td rowspan="5">Too tall</td><td>1</td></tr><tr><td>2</td></tr></table>',
    ('<table><tr><th>Item</th><th>2026</th></tr><tr style="display:none"><td>Hidden</td><td>1</td></tr>'
     "<tr><td>Revenue</td><td>120</td></tr></table>"),
]


@pytest.mark.parametrize("html", HEADER_TABLES)
def test_header_row_count_matches_snapshot_grid(html):
    soup = soup_of(html)
    table = soup.find("table")
    _, _, grid_hidden = hidden_sets(soup)
    assert header_row_count(table, unit_rows(table), grid_hidden) == snapshot_header_rows(table)


def test_header_row_count_is_zero_for_nested_tables():
    soup = soup_of("<table><tr><th>Item</th><th>2026</th></tr><tr><td>A<table><tr><td>1</td></tr></table></td>"
                   "<td>120</td></tr></table>")
    table = soup.find("table")
    _, _, grid_hidden = hidden_sets(soup)
    assert header_row_count(table, unit_rows(table), grid_hidden) == 0


def test_unit_rows_marks_rows_of_nested_tables():
    soup = soup_of("<table><tr><td>A<table><tr><td>1</td></tr></table></td><td>2</td></tr></table>")
    rows = unit_rows(soup.find("table"))
    assert [(row.own, len(row.cells)) for row in rows] == [(True, 2), (False, 1)]


def test_header_row_count_matches_snapshots_on_a_fixture():
    from tests.accuracy.fixtures import load_fixture
    from sec2md.encoding import decode_html
    from sec2md.parser import Parser

    soup = Parser(decode_html(load_fixture("nvda-2026-q2-10q")[1])[0]).soup
    outermost, hidden, grid_hidden = hidden_sets(soup)
    checked = 0
    for table in outermost:
        if id(table) in hidden or len(table.find_all("tr")) < 2:
            continue
        assert header_row_count(table, unit_rows(table), grid_hidden) == snapshot_header_rows(table)
        checked += 1
    assert checked > 50
