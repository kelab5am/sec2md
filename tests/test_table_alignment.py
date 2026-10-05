"""The header-alignment check (spec 2026-10-05, "Header-alignment check").

Source side and output side: the placed grid, R0 on visible content, values, repeated
headers, emitted paths, discriminating cells, the Markdown cell parser, pairing and
locating. Expected values are written out literally.
"""

from collections import Counter

import pytest
from bs4 import BeautifulSoup

from sec2md.table_alignment import (
    OutputTable,
    SourceAnalysis,
    cell_tokens,
    cell_visible_text,
    label_text_key,
    line_cells,
    locate,
    pair_rows,
    parse_output,
    place_source_grid,
    source_cell_text,
    split_cells,
    value_tokens,
)
from sec2md.table_completeness import hidden_sets, unit_rows
from sec2md.table_parser import TableParser, _origin_cells, extract_cell_text
from sec2md.table_roles import visible_text


def unit(html):
    """(table, soup, hidden, grid_hidden) for the first outermost table of html."""
    soup = BeautifulSoup(html, "lxml")
    outermost, hidden, grid_hidden = hidden_sets(soup)
    return outermost[0], soup, hidden, grid_hidden


def grid_of(html):
    table, _, _, grid_hidden = unit(html)
    return place_source_grid(table, unit_rows(table), grid_hidden)


def analysis(html):
    return SourceAnalysis(grid_of(html))


def texts(grid):
    """Each slot's cell text, "^" for a slot covered by a cell from another slot."""
    return [
        [None if cell is None else (cell.text if (cell.row, cell.column) == (r, k) else "^") for k, cell in enumerate(row)]
        for r, row in enumerate(grid.slots)
    ]


# --- source side: the placed grid --------------------------------------------------------

def test_placed_grid_keeps_original_coordinates():
    grid = grid_of(
        "<table><tr><td></td><td></td><td colspan='2'>Year ended</td></tr>"
        "<tr><td></td><td></td><td></td><td></td></tr>"
        "<tr><td></td><td rowspan='2'>Revenue</td><td>100</td><td>90</td></tr>"
        "<tr><td></td><td>5</td><td>4</td></tr></table>"
    )
    assert texts(grid) == [
        ["", "", "Year ended", "^"],
        ["", "", "", ""],
        ["", "Revenue", "100", "90"],
        ["", "^", "5", "4"],
    ]
    spanning = grid.slots[0][2]
    assert (spanning.row, spanning.column, spanning.rowspan, spanning.colspan) == (0, 2, 1, 2)
    assert grid.slots[0][3] is spanning
    assert grid.slots[3][1] is grid.slots[2][1]
    assert grid.height == 4 and grid.width == 4


def test_placed_grid_skips_hidden_rows_and_cells_and_keeps_each_rows_tr():
    table, _, _, grid_hidden = unit(
        "<table><tr><th>Item</th><th>2026</th></tr>"
        "<tr style='display:none'><td>Hidden</td><td>1</td></tr>"
        "<tr><td>Revenue</td><td style='display:none'>9</td><td>120</td></tr></table>"
    )
    grid = place_source_grid(table, unit_rows(table), grid_hidden)
    assert texts(grid) == [["Item", "2026"], ["Revenue", "120"]]
    assert [tr.get_text(" ", strip=True) for tr in grid.row_trs] == ["Item 2026", "Revenue 9 120"]


@pytest.mark.parametrize("html", [
    "<table><tr><td colspan='bad'>Unreliable</td><td>123</td></tr><tr><td>Tail</td><td>456</td></tr></table>",
    "<table><tr><td rowspan='5'>Too tall</td><td>1</td></tr><tr><td>2</td></tr></table>",
    "<table><tr><th>Item</th><th>2026</th></tr><tr><td>A<table><tr><td>1</td></tr></table></td>"
    "<td>120</td></tr></table>",
], ids=["bad-span", "span-past-the-last-row", "nested-table"])
def test_unreliable_placement_is_none(html):
    assert grid_of(html) is None


def test_source_cell_text_reads_visible_label_text():
    table, *_ = unit(
        "<table><tr><td><a href='#n1'>Net | income</a></td><td>Total\xa0revenue\u200b</td>"
        "<td><span>Year</span><span>Ended</span></td><td>2025<sup>(a)</sup></td></tr></table>"
    )
    cells = table.find_all("td")
    assert [source_cell_text(td) for td in cells] == ["Net | income", "Total revenue", "Year Ended", "2025 (a)"]


@pytest.mark.parametrize("cell, expected", [
    ("<td><img src='x.png'></td>", "●"),
    ("<td><span><a href='#n'>Note</a> 3</span></td>", "[Note](#n) 3"),
    ("<td><span>Year</span><span>Ended</span></td>", "Year Ended"),
], ids=["image-only", "nested-link", "plain"])
def test_extract_cell_text_reads_cells_as_the_renderer_does(cell, expected):
    td = BeautifulSoup(f"<table><tr>{cell}</tr></table>", "lxml").find("td")
    assert extract_cell_text(td) == expected


# --- source side: R0 on visible content ---------------------------------------------------

COORDINATES = (
    "<table>"
    "<tr><td></td><td></td><td>Year Ended</td><td></td></tr>"
    "<tr><td></td><td></td><td></td><td></td></tr>"
    "<tr><td></td><td></td><td>2025</td><td>2024</td></tr>"
    "<tr><td></td><td rowspan='2'><a href='#seg'>Segment A</a></td><td>100</td><td>90</td></tr>"
    "<tr><td></td><td>(29</td><td>)</td></tr>"
    "<tr><td></td><td>Total</td><td>71</td><td>90</td></tr>"
    "</table>"
)


def row_text(origin_row):
    return " ".join(visible_text(slot.text) for slot in origin_row if slot is not None and visible_text(slot.text))


def by_role(grid, roles):
    return {
        role: [row_text(grid[row]) for row in range(len(grid)) if roles.role(row) == role]
        for role in ("header", "body", "empty")
    }


def test_checker_roles_match_the_renderers_in_original_coordinates():
    # Leading spacer column, a blank row, a span-covered label slot and a linked label.
    source = analysis(COORDINATES)
    assert source.roles.label_column == 1
    assert source.roles.header_rows == (0, 2)
    assert source.roles.data_rows == (3, 4, 5)
    assert source.roles.empty_rows == (1,)

    renderer = TableParser(unit(COORDINATES)[0])
    rendered = _origin_cells(renderer.source_grid)
    expected = {"header": ["Year Ended", "2025 2024"], "body": ["Segment A 100 90", "(29 )", "Total 71 90"]}
    assert by_role(source.origin, source.roles) == {**expected, "empty": [""]}
    assert {role: rows for role, rows in by_role(rendered, renderer.roles).items() if rows} == expected
    # The same logical label column: column 0 of the cleaned grid, column 1 of the placed one.
    assert renderer.roles.label_column == 0

    def labels(grid, roles):
        column = roles.label_column
        return [visible_text(row[column].text) if row[column] else None
                for r, row in enumerate(grid) if r not in roles.empty_rows]

    assert labels(rendered, renderer.roles) == labels(source.origin, source.roles) == [
        "", "", "Segment A", None, "Total"
    ]


def test_bare_years_beside_a_row_label_make_a_data_row_but_are_not_values():
    source = analysis(
        "<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
        "<tr><td>Founded</td><td>2000</td><td>1900</td></tr>"
        "<tr><td>Revenue</td><td>500</td><td>400</td></tr></table>"
    )
    assert source.roles.data_rows == (1, 2)
    assert source.values[1] == ()
    assert [(v.column, v.text) for v in source.values[2]] == [(1, "500"), (2, "400")]


# --- source side: values -------------------------------------------------------------------

def test_values_rebuild_split_negatives_at_their_digit_column():
    source = analysis(
        "<table><tr><th>Item</th><th colspan='3'>2026</th><th colspan='2'>2025</th></tr>"
        "<tr><td>Loss</td><td>(</td><td>29</td><td>)</td><td>(40</td><td>)%</td></tr>"
        "<tr><td>Gain</td><td></td><td>5</td><td></td><td>6</td><td></td></tr></table>"
    )
    assert [(v.column, v.text, v.tokens) for v in source.values[1]] == [(2, "(29)", ("-29",)), (4, "(40)%", ("-40",))]
    assert source.value_columns == {2, 4}


def test_values_tokenize_leading_dot_decimals_footnotes_ranges_and_nil_values_locally():
    source = analysis(
        "<table><tr><th>Item</th><th>A</th><th>B</th><th>C</th><th>D</th><th>E</th></tr>"
        "<tr><td>Per share</td><td>.75</td><td>(.62)</td><td>2.1(1)</td><td>3.5 %- 4.3 %</td><td>—</td></tr>"
        "</table>"
    )
    values = source.values[1]
    assert [(v.column, v.tokens, v.nil) for v in values] == [
        (1, ("0.75",), False),
        (2, ("-0.62",), False),
        (3, ("2.1",), False),
        (4, ("3.5", "4.3"), False),
        (5, (), True),
    ]
    assert source.value_columns == {1, 2, 3, 4}


@pytest.mark.parametrize("text, expected", [
    ("$ 1,234", ("1234",)),
    ("RMB 941,168", ("941168",)),
    ("€ (1,234)", ("-1234",)),
    ("3,984 *", ("3984",)),
    ("36.5 %", ("36.5",)),
    ("—", ()),
])
def test_value_tokens(text, expected):
    assert value_tokens(text) == expected


def test_label_column_numbers_are_never_values():
    source = analysis(
        "<table><tr><th>Exhibit</th><th>Pages</th></tr>"
        "<tr><td>3.1</td><td>12</td></tr><tr><td>10.2</td><td>4</td></tr></table>"
    )
    assert source.roles.identifier_column is True
    assert [(v.column, v.text) for row in (1, 2) for v in source.values[row]] == [(1, "12"), (1, "4")]


# --- source side: repeated headers --------------------------------------------------------

def test_first_repeated_header_is_a_period_row_after_the_first_data_row():
    source = analysis(
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr>"
        "<tr><td>Segments:</td><td></td><td></td></tr>"
        "<tr><td></td><td>2023</td><td>2022</td></tr>"
        "<tr><td>Cost</td><td>50</td><td>40</td></tr>"
        "<tr><td>Year ended</td><td></td><td></td></tr></table>"
    )
    assert source.roles.data_rows == (1, 4)
    assert source.repeated_header == 3


@pytest.mark.parametrize("row", [
    "<tr><td>Total</td><td>150</td><td>130</td></tr>",           # a complete number
    "<tr><td>Segments:</td><td></td><td></td></tr>",             # no period text, no year
], ids=["data-row", "section-label"])
def test_rows_that_are_not_repeated_headers(row):
    source = analysis(
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr>" + row + "</table>"
    )
    assert source.repeated_header is None


# --- source side: paths, discriminating cells and expectations ---------------------------

HIERARCHY = (
    "<table><tr><td></td><td colspan='2'>Year ended March 31,</td><td></td></tr>"
    "<tr><td></td><td>2025</td><td colspan='2'>2024</td></tr>"
    "<tr><td></td><td>RMB</td><td>RMB</td><td>US$</td></tr>"
    "<tr><td>Revenue</td><td>868,687</td><td>941,168</td><td>129,688</td></tr></table>"
)


def entries(path):
    return [(entry.key, entry.text, [(c.row, c.column) for c in entry.cells], list(entry.levels)) for entry in path]


def test_discriminating_cells_cover_a_proper_subset_of_the_value_columns():
    source = analysis(HIERARCHY)
    assert source.value_columns == {1, 2, 3}
    cell = {(c.row, c.column): c for c in source.header_cells}
    assert set(cell) == {(0, 1), (1, 1), (1, 2), (2, 1), (2, 2), (2, 3)}
    assert source.is_discriminating(cell[(0, 1)])        # covers 1, 2 of 1, 2, 3
    assert source.is_discriminating(cell[(1, 2)])        # 2024 covers 2, 3
    assert source.is_discriminating(cell[(2, 3)])
    caption = analysis(
        "<table><tr><td>Item</td><td colspan='2'>(In millions)</td></tr>"
        "<tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>"
    )
    by_text = {c.text: c for c in caption.header_cells}
    assert not caption.is_discriminating(by_text["(In millions)"])   # spans every value column
    assert not caption.is_discriminating(by_text["Item"])            # covers no value column
    assert caption.is_discriminating(by_text["2025"])


def test_text_shared_by_every_sibling_is_not_discriminating():
    # Step 15: "RMB" over every period tells no value column from another. (The currency
    # row's label cell is empty, as in BABA 24: a column heading such as "Item" there
    # would end the header zone, revision 11.)
    source = analysis(
        "<table><tr><td>(In millions)</td><td>2025</td><td>2024</td></tr>"
        "<tr><td></td><td>RMB</td><td>RMB</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>"
    )
    rmb = [c for c in source.header_cells if c.text == "RMB"]
    assert len(rmb) == 2 and not any(source.is_discriminating(c) for c in rmb)
    assert source.expectation(1).required == ("2025",)
    # One sibling with other text keeps it discriminating (BABA 24's RMB beside US$).
    mixed = analysis(
        "<table><tr><td></td><td>2025</td><td>2024</td><td>2024</td></tr>"
        "<tr><td></td><td>RMB</td><td>RMB</td><td>US$</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td><td>12</td></tr></table>"
    )
    assert all(mixed.is_discriminating(c) for c in mixed.header_cells if c.text == "RMB")
    assert mixed.expectation(1).required == ("2025", "rmb")


def test_emitted_path_and_expectation_of_each_column():
    source = analysis(HIERARCHY)
    assert entries(source.emitted_path(1)) == [
        ("year ended march 31,", "Year ended March 31,", [(0, 1)], [0]),
        ("2025", "2025", [(1, 1)], [1]),
        ("rmb", "RMB", [(2, 1)], [2]),
    ]
    third = source.expectation(3)
    assert third.rendering() == "2024 — US$"
    assert third.required == ("2024", "us$")
    assert third.need == {"2024": 1, "us$": 1}
    assert third.conflicts == {"2025": "2025", "rmb": "RMB"}
    assert third.expected_text() == "2024 — US$"
    first = source.expectation(1)
    assert first.required == ("year ended march 31,", "2025", "rmb")
    assert first.conflicts == {"2024": "2024", "us$": "US$"}


def test_rowspan_cell_appears_once_and_adjacent_equal_texts_collapse():
    source = analysis(
        "<table><tr><td rowspan='2'></td><td rowspan='2'>2025</td><td colspan='2'>2025</td></tr>"
        "<tr><td>2025</td><td>Budget</td></tr>"
        "<tr><td>Revenue</td><td>1</td><td>100</td><td>200</td></tr></table>"
    )
    assert entries(source.emitted_path(1)) == [("2025", "2025", [(0, 1)], [0])]
    assert entries(source.emitted_path(2)) == [("2025", "2025", [(0, 2), (1, 2)], [0, 1])]
    assert source.expectation(2).rendering() == "2025"
    assert entries(source.emitted_path(3)) == [("2025", "2025", [(0, 2)], [0]), ("budget", "Budget", [(1, 3)], [1])]


def test_non_adjacent_equal_texts_stay_separate_entries():
    source = analysis(
        "<table><tr><td></td><td>A</td><td>C</td></tr><tr><td></td><td>B</td><td>D</td></tr>"
        "<tr><td></td><td>A</td><td>E</td></tr><tr><td>Revenue</td><td>1</td><td>2</td></tr></table>"
    )
    expectation = source.expectation(1)
    assert [entry.key for entry in expectation.path] == ["a", "b", "a"]
    assert expectation.need == {"a": 2, "b": 1}
    assert expectation.required == ("a", "b")
    assert expectation.rendering() == "A — B — A"


# Equal labels whose links differ (META 10-Q 2026-Q1 table 39's exhibit pair, as header cells).
LINKED_PLANS = (
    "<table><tr><td></td><td colspan='2'><a href='ex101.htm'>Plan</a></td></tr>"
    "<tr><td></td><td><a href='ex102.htm'>Plan</a></td><td>Budget</td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
)


def test_adjacent_equal_labels_with_different_links_stay_separate_entries():
    # Revision 11, R6 step 2: the collapse compares link destinations too, as R6 does.
    source = analysis(LINKED_PLANS)
    assert entries(source.emitted_path(1)) == [("plan", "Plan", [(0, 1)], [0]), ("plan", "Plan", [(1, 1)], [1])]
    assert source.expectation(1).need == {"plan": 2}
    assert source.expectation(1).rendering() == "Plan — Plan"
    same = analysis(LINKED_PLANS.replace("ex102.htm", "ex101.htm"))
    assert entries(same.emitted_path(1)) == [("plan", "Plan", [(0, 1), (1, 1)], [0, 1])]
    unlinked = analysis(LINKED_PLANS.replace("<a href='ex102.htm'>Plan</a>", "Plan"))
    assert [entry.key for entry in unlinked.emitted_path(1)] == ["plan", "plan"]


def test_child_label_under_another_group_is_needed_not_conflicting():
    source = analysis(
        "<table><tr><td></td><td colspan='2'>2025</td><td colspan='2'>2024</td></tr>"
        "<tr><td></td><td>Actual</td><td>2024</td><td>Actual</td><td>2023</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td><td>80</td><td>70</td></tr></table>"
    )
    expectation = source.expectation(2)
    assert expectation.rendering() == "2025 — 2024"
    assert expectation.need == {"2025": 1, "2024": 1}
    assert expectation.conflicts == {"2023": "2023", "2024": "2024", "actual": "Actual"}


def test_single_value_column_has_no_discriminating_header():
    source = analysis(
        "<table><tr><td></td><td>2025</td></tr><tr><td>Revenue</td><td>100</td></tr>"
        "<tr><td>Cost</td><td>40</td></tr></table>"
    )
    assert source.expectation(1).required == ()


def test_label_keys_collapse_whitespace_fold_case_and_reduce_links():
    assert label_text_key("  Year\xa0 Ended  [June 30,](#fy) ") == "year ended june 30,"


# --- output side ---------------------------------------------------------------------------

@pytest.mark.parametrize("line, expected", [
    ("| Revenue | 100 | 90 |", [" Revenue ", " 100 ", " 90 "]),
    ("|  | 100 |  |", ["  ", " 100 ", "  "]),
    ("| a \\| b | 1 |", [" a \\| b ", " 1 "]),
    ("| [Note | 3](http://x.test/a|b) | 7 |", [" [Note ", " 3](http://x.test/a|b) ", " 7 "]),
    ("| [Total](#t) | 1 |", [" [Total](#t) ", " 1 "]),
    ("Revenue | 1", ["Revenue ", " 1"]),
], ids=["plain", "blank-cells", "escaped-pipe", "pipe-in-destination", "link", "no-outer-pipes"])
def test_split_cells_keeps_positions(line, expected):
    assert split_cells(line) == expected


def test_cell_visible_text_reads_link_labels_and_unescapes_pipes():
    assert [cell_visible_text(cell) for cell in split_cells("| [Net](#n) \\| gross |  | $ 1,234 |")] == [
        "Net | gross", "", "$ 1,234"
    ]


def test_cell_tokens_rebuild_split_negatives_at_the_digit_cell():
    assert cell_tokens(["Loss", "(29", ")", "(", "40", ")", ".75", "", "$ 1,234"]) == [
        Counter(), Counter({"-29": 1}), Counter(), Counter(), Counter({"-40": 1}), Counter(),
        Counter({"0.75": 1}), Counter(), Counter({"1234": 1}),
    ]


def test_parse_output_reads_the_header_line_body_lines_and_check_1_keys():
    output = parse_output(
        "| Item | [2025](#fy) | 2024 |\n| --- | --- | --- |\n| Revenue | 100 | 90 |\n| Note 3 Cost | (5 | ) |\n"
        "| A\\|B | 1 | 2 |\n|  | [Total](#t) | 3 |"
    )
    assert output == OutputTable(
        header=("Item", "2025", "2024"),
        body=("| Revenue | 100 | 90 |", "| Note 3 Cost | (5 | ) |", "| A\\|B | 1 | 2 |", "|  | [Total](#t) | 3 |"),
        cells=(("Revenue", "100", "90"), ("Note 3 Cost", "(5", ")"), ("A|B", "1", "2"), ("", "Total", "3")),
        # An escaped pipe stays inside its label ("ab"); check 1's own split would read "a".
        keys=("revenue", "notecost#3", "ab", "total"),
    )
    assert output.header_text(5) == ""
    assert parse_output("Revenue 100 90") is None


def test_pairing_needs_a_unique_label_on_both_sides():
    output = parse_output(
        "|  | 2025 |\n| --- | --- |\n| Revenue | 1 |\n| Cost | 2 |\n| Cost | 3 |\n| Other | 4 |\n| 5 | 5 |"
    )
    source_keys = {1: "revenue", 2: "cost", 3: "other", 4: "", 5: "taxes"}
    key_counts = Counter({"revenue": 1, "cost": 1, "other": 2, "taxes": 1})
    assert pair_rows(source_keys, key_counts, output) == {1: 0}


def test_locate_finds_the_cells_holding_every_token():
    _, cells = line_cells("| Revenue | 100 | 100 2025 | ( | 7 | ) | 3.5 %- 4.3 % |")
    assert locate(("100",), cells) == [1, 2]
    assert locate(("2025",), cells) == [2]
    assert locate(("-7",), cells) == [4]
    assert locate(("3.5", "4.3"), cells) == [6]
    assert locate(("999",), cells) == []
    assert locate((), cells) == []
