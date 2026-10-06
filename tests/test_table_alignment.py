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
from sec2md.parser import Parser
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


# --- matching, findings and coverage (T9) ----------------------------------------------------

from sec2md.table_alignment import (  # noqa: E402
    COVERAGE_KEYS,
    MAX_STATES,
    Expectation,
    SEPARATOR,
    Verdict,
    judge,
)
from sec2md.table_completeness import check_tables  # noqa: E402

WHERE = "table 1 (snapshot 2, page 3)"


def check(html, markdown):
    """check_tables for every table of html; markdown is one output per table (None: no output)."""
    soup = BeautifulSoup(html, "lxml")
    tables = [t for t in soup.find_all("table") if t.find_parent("table") is None]
    outputs = markdown if isinstance(markdown, list) else [markdown]
    report = check_tables(
        soup,
        {id(t): text for t, text in zip(tables, outputs) if text is not None},
        {id(t): 3 for t in tables},
        {id(t): 2 for t in tables},
    )
    coverage = dict(report.alignment_coverage)
    assert tuple(coverage) == COVERAGE_KEYS
    assert_identities(coverage)
    return report


def assert_identities(c):
    """The four reconciliation identities of the coverage schema."""
    assert c["tables_total"] == c["tables_evaluated"] + sum(c[k] for k in (
        "table_no_output", "table_no_separator", "table_unreliable_grid", "table_no_header", "table_no_data"))
    assert c["rows_data"] == c["rows_paired"] + c["row_below_repeated_header"] + c["row_unpaired"]
    assert c["values_total"] == c["values_evaluated"] + sum(c[k] for k in (
        "value_nil", "value_no_discriminating_header", "value_missing_in_output",
        "value_ambiguous_position", "value_ambiguous_header", "value_unevaluated_budget"))
    assert c["values_evaluated"] == c["values_aligned"] + c["values_misaligned"]


def counts(report):
    """The non-zero coverage counts."""
    return {key: count for key, count in report.alignment_coverage if count}


def rendered(html):
    """The prototype renderer's Markdown for the first table of html."""
    return TableParser(BeautifulSoup(html, "lxml").find("table")).md()


PERIODS = (
    "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>90</td></tr>"
    "<tr><td>Cost</td><td>40</td><td>30</td></tr></table>"
)
PERIODS_MD = "|  | 2025 | 2024 |\n| --- | --- | --- |\n| Revenue | 100 | 90 |\n| Cost | 40 | 30 |"
EVALUATED = {"tables_total": 1, "tables_evaluated": 1, "rows_data": 2, "rows_paired": 2, "values_total": 4,
             "values_evaluated": 4}


def test_aligned_table_is_silent():
    assert rendered(PERIODS) == PERIODS_MD
    report = check(PERIODS, PERIODS_MD)
    assert report.alignment == ()
    assert counts(report) == {**EVALUATED, "values_aligned": 4}


def test_shifted_header_is_reported():
    report = check(PERIODS, PERIODS_MD.replace("|  | 2025 | 2024 |", "| 2025 | 2024 |  |"))
    assert report.alignment == (
        f'{WHERE}: "Revenue" 100 under "2024"; expected "2025"',
        f'{WHERE}: "Revenue" 90 under ""; expected "2024"',
        f'{WHERE}: "Cost" 40 under "2024"; expected "2025"',
        f'{WHERE}: "Cost" 30 under ""; expected "2024"',
    )
    assert counts(report) == {**EVALUATED, "values_misaligned": 4}


# Failing mutations: every segmentation disagrees with the path.

def test_merged_sibling_headers_are_misaligned():
    report = check(PERIODS, PERIODS_MD.replace("|  | 2025 | 2024 |", "|  | 2025 — 2024 | 2024 |"))
    assert report.alignment == (
        f'{WHERE}: "Revenue" 100 under "2025 — 2024"; expected "2025", conflicting "2024"',
        f'{WHERE}: "Cost" 40 under "2025 — 2024"; expected "2025", conflicting "2024"',
    )
    assert counts(report) == {**EVALUATED, "values_aligned": 2, "values_misaligned": 2}


def test_both_columns_carrying_every_period_label_are_misaligned():
    report = check(PERIODS, PERIODS_MD.replace("|  | 2025 | 2024 |", "|  | 2025 — 2024 | 2025 — 2024 |"))
    assert report.alignment == (
        f'{WHERE}: "Revenue" 100 under "2025 — 2024"; expected "2025", conflicting "2024"',
        f'{WHERE}: "Revenue" 90 under "2025 — 2024"; expected "2024", conflicting "2025"',
        f'{WHERE}: "Cost" 40 under "2025 — 2024"; expected "2025", conflicting "2024"',
        f'{WHERE}: "Cost" 30 under "2025 — 2024"; expected "2024", conflicting "2025"',
    )


@pytest.mark.parametrize("header, expected", [
    ("|  | 2025 | 2024 |", (
        '"Revenue" 100 under "2024"; expected "2025"',
        '"Revenue" 90 under "2025"; expected "2024"',
    )),
    ("|  | 2025 — 2024 | 2025 — 2024 |", (
        '"Revenue" 100 under "2025 — 2024"; expected "2025", conflicting "2024"',
        '"Revenue" 90 under "2025 — 2024"; expected "2024", conflicting "2025"',
        '"Cost" 40 under "2025 — 2024"; expected "2025", conflicting "2024"',
        '"Cost" 30 under "2025 — 2024"; expected "2024", conflicting "2025"',
    )),
], ids=["plain-labels", "combined-labels"])
def test_value_swap_is_misaligned(header, expected):
    swapped = PERIODS_MD.replace("|  | 2025 | 2024 |", header).replace("| 100 | 90 |", "| 90 | 100 |")
    report = check(PERIODS, swapped)
    assert report.alignment == tuple(f"{WHERE}: {finding}" for finding in expected)
    assert counts(report)["values_misaligned"] == len(expected)


def test_overlapping_label_strings_never_match_by_substring():
    html = PERIODS.replace("<td>2025</td><td>2024</td>", "<td>Adjusted</td><td>Unadjusted</td>")
    report = check(html, PERIODS_MD.replace("|  | 2025 | 2024 |", "|  | Unadjusted | Adjusted |"))
    assert report.alignment[:2] == (
        f'{WHERE}: "Revenue" 100 under "Unadjusted"; expected "Adjusted"',
        f'{WHERE}: "Revenue" 90 under "Adjusted"; expected "Unadjusted"',
    )
    assert counts(report)["values_misaligned"] == 4


ABA = (
    "<table><tr><td></td><td>A</td><td>C</td></tr><tr><td></td><td>B</td><td>D</td></tr>"
    "<tr><td></td><td>A</td><td>E</td></tr><tr><td>Revenue</td><td>1</td><td>2</td></tr></table>"
)
ABA_MD = "|  | A — B — A | C — D — E |\n| --- | --- | --- |\n| Revenue | 1 | 2 |"


def test_non_adjacent_path_needs_both_occurrences():
    assert rendered(ABA) == ABA_MD
    assert check(ABA, ABA_MD).alignment == ()
    report = check(ABA, ABA_MD.replace("A — B — A", "A — B"))
    assert report.alignment == (f'{WHERE}: "Revenue" 1 under "A — B"; expected "A — B — A"',)


def test_equal_labels_with_different_links_need_both_occurrences():
    # Revision 11: R6 keeps both "Plan" cells, and the checker's emitted path needs both, so
    # round 1's label-only suppression is reported.
    markdown = rendered(LINKED_PLANS)
    assert markdown.splitlines()[0] == "|  | [Plan](ex101.htm) — [Plan](ex102.htm) | [Plan](ex101.htm) — Budget |"
    assert check(LINKED_PLANS, markdown).alignment == ()
    suppressed = markdown.replace("[Plan](ex101.htm) — [Plan](ex102.htm)", "[Plan](ex101.htm)")
    report = check(LINKED_PLANS, suppressed)
    assert report.alignment == (f'{WHERE}: "Revenue" 100 under "Plan"; expected "Plan — Plan"',)


# Passing controls: R6's exact rendering of the emitted path.

CONTROLS = {
    "literal-label": (
        "<table><tr><td></td><td>Income — net</td><td>Other</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>",
        "|  | Income — net | Other |\n| --- | --- | --- |\n| Revenue | 100 | 200 |",
    ),
    "child-under-another-group": (
        "<table><tr><td></td><td colspan='2'>2025</td><td colspan='2'>2024</td></tr>"
        "<tr><td></td><td>Actual</td><td>2024</td><td>Actual</td><td>2023</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td><td>80</td><td>70</td></tr></table>",
        "|  | 2025 — Actual | 2025 — 2024 | 2024 — Actual | 2024 — 2023 |\n| --- | --- | --- | --- | --- |\n"
        "| Revenue | 100 | 90 | 80 | 70 |",
    ),
    "astras-r6a-source": (
        "<table><tr><th>Metric</th><th colspan='2'>2025</th></tr>"
        "<tr><th></th><th>2025</th><th>Budget</th></tr>"
        "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>",
        "| Metric | 2025 | 2025 — Budget |\n| --- | --- | --- |\n| Revenue | 100 | 200 |",
    ),
    "adjacent-duplicate": (
        "<table><tr><td></td><td>2025</td><td>2024</td></tr><tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        "|  | 2025 | 2024 |\n| --- | --- | --- |\n| Revenue | 100 | 90 |",
    ),
    "rowspan-cell": (
        "<table><tr><td></td><td rowspan='2'>2025</td><td>2024</td></tr><tr><td></td><td>Restated</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        "|  | 2025 | 2024 — Restated |\n| --- | --- | --- |\n| Revenue | 100 | 90 |",
    ),
    "astras-three-column-hierarchy": (
        "<table><tr><td>Metric</td><td colspan='2'>Income</td><td>Other</td></tr>"
        "<tr><td></td><td>net</td><td>gross</td><td>Income — net</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>200</td><td>300</td></tr></table>",
        "| Metric | Income — net | Income — gross | Other — Income — net |\n| --- | --- | --- | --- |\n"
        "| Revenue | 100 | 200 | 300 |",
    ),
}


CONTROL_VALUES = {"literal-label": 2, "child-under-another-group": 4, "astras-r6a-source": 2,
                  "adjacent-duplicate": 2, "rowspan-cell": 2, "astras-three-column-hierarchy": 3}


@pytest.mark.parametrize("name", list(CONTROLS))
def test_passing_controls_are_aligned(name):
    html, markdown = CONTROLS[name]
    assert rendered(html) == markdown
    report = check(html, markdown)
    assert report.alignment == ()
    assert counts(report)["values_aligned"] == counts(report)["values_total"] == CONTROL_VALUES[name]


def retention_audit(html, markdown):
    """The header-retention audit (spec "Acceptance criteria", matching semantics) on the first
    table, from production's SourceAnalysis and align_table's ValueOutcomes.

    Returns (values, value_misses, cell_misses): every located value as (row, column, its
    output column's header, its emitted path's rendering); the values whose header does not
    equal that rendering; and the header-zone cells that no output column's emitted-path
    rendering represents (only R6's adjacent suppression is permitted).
    """
    from sec2md.table_alignment import align_table
    from sec2md.table_completeness import _direct_cells, cell_text, row_label_key

    table, _, hidden, grid_hidden = unit(html)
    rows = unit_rows(table)
    keys = {
        id(row.tr): row_label_key([cell_text(c, hidden) for c in _direct_cells(row.tr) if id(c) not in hidden])
        for row in rows if row.own and id(row.tr) not in hidden
    }
    aligned = align_table(table, rows, grid_hidden, markdown, keys, Counter(key for key in keys.values() if key))
    source = SourceAnalysis(place_source_grid(table, rows, grid_hidden))
    output = parse_output(markdown)
    values = [
        (outcome.row, outcome.column, output.header_text(outcome.output_column),
         source.expectation(outcome.column).rendering())
        for outcome in aligned.outcomes if outcome.output_column is not None
    ]
    value_misses = [value for value in values if label_text_key(value[2]) != label_text_key(value[3])]
    headers = {label_text_key(header) for header in output.header}
    cell_misses = [
        cell.text for cell in source.header_cells
        if not {label_text_key(source.expectation(k).rendering()) for k in cell.columns()
                if k < source.grid.width} & headers
    ]
    return values, value_misses, cell_misses


@pytest.mark.parametrize("name", list(CONTROLS))
def test_header_retention_audit_holds_on_every_matching_control(name):
    # Spec Testing: the header-retention audit on the same controls.
    html, markdown = CONTROLS[name]
    values, value_misses, cell_misses = retention_audit(html, markdown)
    assert len(values) == CONTROL_VALUES[name]
    assert value_misses == [] and cell_misses == []


def test_header_retention_audit_permits_adjacent_suppression():
    # Astra's R6a source: the lower "2025" is written once, under the spanning "2025"; its
    # cell is represented by the emitted entry that column 1 renders.
    html, markdown = CONTROLS["astras-r6a-source"]
    values, value_misses, cell_misses = retention_audit(html, markdown)
    assert [(column, header, expected) for _, column, header, expected in values] == [
        (1, "2025", "2025"), (2, "2025 — Budget", "2025 — Budget")]
    assert value_misses == [] and cell_misses == []


def test_header_retention_audit_reports_an_unrelated_header_loss():
    html, markdown = CONTROLS["child-under-another-group"]
    # The 2025 span lost over its first column: that value's header no longer renders its path.
    lost = markdown.replace("| 2025 — Actual |", "| Actual |")
    _, value_misses, cell_misses = retention_audit(html, lost)
    assert value_misses == [(2, 1, "Actual", "2025 — Actual")]
    # The 2025 cell is still rendered over column 2; the "Actual" cell under it is not.
    assert cell_misses == ["Actual"]
    # A label lost from every column: its value and its cell are both reported.
    html, markdown = CONTROLS["literal-label"]
    _, value_misses, cell_misses = retention_audit(html, markdown.replace("| Other |", "|  |"))
    assert value_misses == [(1, 2, "", "Other")]
    assert cell_misses == ["Other"]


def _row(*cells, tag="td"):
    """One tr; a (text, colspan) tuple spans columns."""
    return "<tr>" + "".join(
        f"<{tag} colspan='{cell[1]}'>{cell[0]}</{tag}>" if isinstance(cell, tuple) else f"<{tag}>{cell}</{tag}>"
        for cell in cells
    ) + "</tr>"


# Spec "Interaction with strict and the completeness checks": check 1's header role keeps
# using header_row_count (the snapshot builder's count of leading header rows). These pin
# that unchanged count next to R0's header zone on the same tables.
CHECK_ONE_HEADER_ROWS = {
    # CRM 26: check 1 reads the caption row with "4" as numeric, so it counts no header row;
    # R0 keeps the caption and the years row.
    "crm-26": ("<table>" + _row("4", "", ("Fiscal Year Ended January 31,", 6))
               + _row("", "", ("2025", 2), ("2024", 2), ("2023", 2))
               + _row("Net cash provided by operating activities", "", "$", "13,092", "$", "10,234", "$", "7,111")
               + _row("Net cash used in investing activities", "", ("(3,163)", 2), ("(1,327)", 2), ("(1,989)", 2))
               + "</table>", 0, (0, 1)),
    # JPM 109: the first row is data for both.
    "jpm-109": ("<table>" + _row("Noninterest revenue – reported (c)", "$", "84,973", "$", "68,837", "$", "61,985")
                + _row("Fully taxable-equivalent adjustments (c)", "", "2,560", "", "3,782", "", "3,148")
                + _row("Total noninterest revenue – managed", "$", "87,533", "$", "72,619", "$", "65,133")
                + "</table>", 0, ()),
    # AAPL 18: the section label right before the data is body for both.
    "aapl-18": ("<table>" + _row("Gross margin percentage:", "", "", "", "", "", "")
                + _row("Products", "36.5", "%", "36.3", "%", "35.3", "%")
                + _row("Services", "70.8", "%", "71.7", "%", "69.7", "%") + "</table>", 0, ()),
    # nvda-2026-10k 17: three header rows for both.
    "nvda-2026-10k-17": ("<table>" + _row("", ("Year Ended", 4))
                         + _row("", ("Jan 25, 2026", 2), ("Jan 26, 2025", 2)) + _row("", ("(In millions)", 4))
                         + _row("Net cash provided by operating activities", "$", "102,718", "$", "64,089")
                         + _row("Net cash used in investing activities", "$", "(52,228)", "$", "(20,421)")
                         + "</table>", 3, (0, 1, 2)),
    # A th header row: one header row for both.
    "th-row": ("<table>" + _row("Denomination", "€1", "€2", tag="th")
               + _row("Coins issued", "1,234", "567") + _row("Coins withdrawn", "89", "10") + "</table>", 1, (0,)),
    # A years row under a unit caption in the label cell: check 1 counts no header row (its
    # period test needs an empty label cell), R0 keeps the row (spec F11).
    "unit-caption-years-row": ("<table>" + _row("(Dollars in millions)", "2024", "2023")
                               + _row("Card income", "$ 5,964", "$ 5,957")
                               + _row("Service charges", "5,500", "5,400") + "</table>", 0, (0,)),
}


@pytest.mark.parametrize("name", list(CHECK_ONE_HEADER_ROWS))
def test_check_one_header_rows_next_to_r0_on_named_tables(name):
    from sec2md.table_completeness import header_row_count

    html, check_one, r0 = CHECK_ONE_HEADER_ROWS[name]
    table, _, _, grid_hidden = unit(html)
    rows = unit_rows(table)
    assert header_row_count(table, rows, grid_hidden) == check_one
    assert SourceAnalysis(place_source_grid(table, rows, grid_hidden)).roles.header_rows == r0
    assert TableParser(table).roles.header_rows == r0  # the renderer reaches the same zone


def test_three_column_hierarchy_judges_each_column_by_its_own_path():
    html, _ = CONTROLS["astras-three-column-hierarchy"]
    source = analysis(html)
    assert [source.expectation(column).rendering() for column in (1, 2, 3)] == [
        "Income — net", "Income — gross", "Other — Income — net"
    ]
    # Column 3's literal label never satisfies column 1's path, nor the reverse.
    assert judge("Income — net", source.expectation(1)) == Verdict("aligned")
    assert judge("Income — net", source.expectation(3)).outcome == "misaligned"
    assert judge("Other — Income — net", source.expectation(1)).outcome == "misaligned"


def test_ambiguous_segmentation_is_skipped():
    report = check(PERIODS, PERIODS_MD.replace("|  | 2025 | 2024 |", "|  | 2025 — Restated | 2024 |"))
    assert report.alignment == ()
    assert counts(report) == {**EVALUATED, "value_ambiguous_header": 2, "values_evaluated": 2, "values_aligned": 2}


def test_non_discriminating_caption_is_never_required():
    html = ("<table><tr><td></td><td colspan='2'>(In millions)</td></tr>"
            "<tr><td></td><td>RMB</td><td>RMB</td></tr>"
            "<tr><td></td><td>2025</td><td>2024</td></tr>"
            "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>")
    report = check(html, "|  | 2025 | 2024 |\n| --- | --- | --- |\n| Revenue | 100 | 90 |")
    assert report.alignment == ()
    assert counts(report)["values_aligned"] == 2


# Bounded evaluation.

ADJUSTED = ("<table><tr><td></td><td>Adjusted</td><td>Unadjusted</td><td>Other</td></tr>"
            "<tr><td>Revenue</td><td>1</td><td>2</td><td>3</td></tr></table>")


def test_many_separators_all_inconsistent_completes_within_the_bound():
    header = SEPARATOR.join(["Unadjusted", "Other"] * 15 + ["Unadjusted"])
    assert header.count(SEPARATOR) == 30
    verdict = judge(header, analysis(ADJUSTED).expectation(1))
    # Every completion lacks "Adjusted", so the search cannot stop early; it is exhaustive.
    assert verdict.outcome == "misaligned"
    assert 31 < verdict.states < MAX_STATES
    assert judge(header, analysis(ADJUSTED).expectation(1), max_states=verdict.states) == verdict
    assert judge(header, analysis(ADJUSTED).expectation(1), max_states=verdict.states - 1) == Verdict(
        "budget", verdict.states - 1)


def test_search_stops_once_both_verdicts_are_reachable():
    # Twelve header rows: column 1's path is A1 ... A12, column 2's is B1 ... B12.
    html = ("<table>" + "".join(f"<tr><td></td><td>A{i}</td><td>B{i}</td></tr>" for i in range(1, 13))
            + "<tr><td>Revenue</td><td>1</td><td>2</td></tr></table>")
    expectation = analysis(html).expectation(1)
    assert len(expectation.required) == 12 and len(expectation.conflicts) == 12
    header = SEPARATOR.join([f"A{i}" for i in range(1, 13)] + ["Note"])
    # The first completion (every atom alone) is consistent and the next one, "A12 — Note",
    # is not: the search stops there instead of visiting every reachable count.
    verdict = judge(header, expectation)
    assert verdict.outcome == "ambiguous"
    assert verdict.states <= 16


def _sibling_expectation(count):
    """Required "a — b" with count conflicting siblings c1 ... c<count>, each needed once."""
    conflicts = [f"c{index}" for index in range(1, count + 1)]
    need = {"a — b": 1, **{key: 1 for key in conflicts}}
    expectation = Expectation(1, (), ("a — b",), need, {key: key.upper() for key in conflicts})
    return expectation, SEPARATOR.join(["A", "B", *[key.upper() for key in conflicts]])


@pytest.mark.parametrize("count, states", [(15, 10_269), (19, 97_250)])
def test_search_stops_as_soon_as_both_verdicts_are_reachable_from_the_start(count, states):
    # Spec revision 14: every state the search visits is reachable from the start, so the
    # search stops once it has seen a consistent and an inconsistent completion anywhere,
    # not only when one frame holds both. Here every completion under "A" alone lacks
    # "a — b" (inconsistent); the first consistent one starts with "A — B". The per-frame
    # stop needed 17,991 states for 15 siblings and hit the bound (170,625 > 100,000) for 19.
    expectation, header = _sibling_expectation(count)
    assert judge(header, expectation) == Verdict("ambiguous", states)
    assert states < MAX_STATES


SIBLINGS = [f"S{index}" for index in range(1, 31)]
BUDGET = ("<table><tr><td></td><td>Adjusted</td>" + "".join(f"<td>{label}</td>" for label in SIBLINGS) + "</tr>"
          "<tr><td>Revenue</td><td>1</td>" + "".join(f"<td>{index + 2}</td>" for index in range(30)) + "</tr></table>")


def test_search_that_hits_the_bound_is_unevaluated():
    # Thirty conflicting siblings in one header: the reachable counts exceed the bound.
    header = SEPARATOR.join(SIBLINGS)
    assert judge(header, analysis(BUDGET).expectation(1)) == Verdict("budget", MAX_STATES)
    markdown = ("|  | " + header + " | " + " | ".join(SIBLINGS) + " |\n" + "| --- " * 32 + "|\n"
                "| Revenue | 1 | " + " | ".join(str(index + 2) for index in range(30)) + " |")
    report = check(BUDGET, markdown)
    assert report.alignment == ()
    assert counts(report) == {"tables_total": 1, "tables_evaluated": 1, "rows_data": 1, "rows_paired": 1,
                              "values_total": 31, "value_unevaluated_budget": 1, "values_evaluated": 30,
                              "values_aligned": 30}


# Parser and token controls.

@pytest.mark.parametrize("html, markdown", [
    pytest.param(PERIODS, "|  | 2025 |  | 2024 |\n| --- | --- | --- | --- |\n| Revenue | 100 |  | 90 |\n"
                          "| Cost | 40 |  | 30 |", id="blank-columns"),
    pytest.param("<table><tr><td></td><td colspan='2'>2025</td><td colspan='3'>2024</td></tr>"
                 "<tr><td>Loss</td><td>(29</td><td>)</td><td>(</td><td>40</td><td>)</td></tr>"
                 "<tr><td>Gain</td><td>5</td><td></td><td></td><td>6</td><td></td></tr></table>",
                 "|  | 2025 |  |  | 2024 |  |\n| --- | --- | --- | --- | --- | --- |\n"
                 "| Loss | (29 | ) | ( | 40 | ) |\n| Gain | 5 |  |  | 6 |  |",
                 id="split-negatives"),
    pytest.param(PERIODS.replace("100", ".75").replace("90", "(.62)"),
                 PERIODS_MD.replace("100", ".75").replace("90", "(.62)"), id="leading-dot-decimals"),
    pytest.param(PERIODS.replace("<td>2025</td>", "<td><a href='#fy25'>2025</a></td>")
                 .replace("<td>Revenue</td>", "<td><a href='#rev'>Revenue</a></td>"),
                 PERIODS_MD.replace("| 2025 |", "| [2025](#fy25) |").replace("| Revenue |", "| [Revenue](#rev) |"),
                 id="linked-labels"),
    pytest.param(PERIODS.replace("<td>2025</td>", "<td>Gross | net</td>").replace("<td>Revenue</td>", "<td>A|B</td>"),
                 PERIODS_MD.replace("| 2025 |", "| Gross \\| net |").replace("| Revenue |", "| A\\|B |"),
                 id="escaped-pipes"),
])
def test_parser_and_token_controls_are_aligned(html, markdown):
    report = check(html, markdown)
    assert report.alignment == ()
    assert counts(report)["values_aligned"] == 4


# Skip keys and their precedence.

BAD_SPAN = "<table><tr><td colspan='bad'>Item</td><td>2025</td></tr><tr><td>Revenue</td><td>100</td></tr></table>"
HEADERLESS = "<table><tr><td>Revenue</td><td>100</td></tr><tr><td>Cost</td><td>40</td></tr></table>"
TEXT_TABLE = "<table><tr><td>Name</td><td>Title</td></tr><tr><td>Jane</td><td>CFO</td></tr></table>"
TABLE_MD = "| Item | 2025 |\n| --- | --- |\n| Revenue | 100 |"


@pytest.mark.parametrize("html, markdown, key", [
    (BAD_SPAN, None, "table_no_output"),               # also unreliable
    (BAD_SPAN, "   \n", "table_no_output"),
    (BAD_SPAN, "Item 2025 Revenue 100", "table_no_separator"),
    (BAD_SPAN, TABLE_MD, "table_unreliable_grid"),
    ("<table><tr><td>Item</td><td>A<table><tr><td>1</td></tr></table></td></tr></table>", TABLE_MD,
     "table_unreliable_grid"),
    (HEADERLESS, "|  |  |\n| --- | --- |\n| Revenue | 100 |\n| Cost | 40 |", "table_no_header"),
    (TEXT_TABLE, "| Name | Title |\n| --- | --- |\n| Jane | CFO |", "table_no_data"),
], ids=["missing", "empty", "no-separator", "bad-span", "nested", "headerless", "text-table"])
def test_table_skip_keys_take_the_first_applicable_key(html, markdown, key):
    assert counts(check(html, markdown)) == {"tables_total": 1, key: 1}


REPEATED_HEADER_TABLE = (
    "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>90</td></tr>"
    "{middle}"
    "<tr><td>Cost</td><td>50</td><td>40</td></tr>"
    "<tr><td>Taxes</td><td>8</td><td>7</td></tr></table>"
)


@pytest.mark.parametrize("middle", [
    "<tr><td></td><td>2024(a)</td><td>2023(a)</td></tr>",
    "<tr><td></td><td>2024–25</td><td>2023–24</td></tr>",
], ids=["footnoted-years", "fiscal-year-ranges"])
def test_year_like_mid_table_row_is_a_repeated_header(middle):
    # Spec revision 15, step 4: a body row after the first data row with no complete number
    # outside the label column and a year-like value (a footnoted year, a fiscal-year range)
    # is a repeated header; the values below it are not evaluated.
    html = REPEATED_HEADER_TABLE.format(middle=middle)
    source = analysis(html)
    assert source.roles.data_rows == (1, 3, 4)
    assert source.repeated_header == 2
    report = check(html, rendered(html))
    assert report.alignment == ()
    assert counts(report) == {"tables_total": 1, "tables_evaluated": 1, "rows_data": 3,
                              "row_below_repeated_header": 2, "rows_paired": 1, "values_total": 2,
                              "values_evaluated": 2, "values_aligned": 2}
    assert [(row, column, outcome) for row, column, outcome, _, _ in outcomes(html, rendered(html))] == [
        (1, 1, "aligned"), (1, 2, "aligned"),
        (3, 1, "row_below_repeated_header"), (3, 2, "row_below_repeated_header"),
        (4, 1, "row_below_repeated_header"), (4, 2, "row_below_repeated_header"),
    ]


def test_mid_table_row_with_an_amount_beside_a_fiscal_year_range_is_not_a_repeated_header():
    # Control: the row holds complete numbers, so it is a data row, not a repeated header.
    html = REPEATED_HEADER_TABLE.format(middle="<tr><td>Fiscal 2024–25 adjustment</td><td>15</td><td>13</td></tr>")
    source = analysis(html)
    assert source.roles.data_rows == (1, 2, 3, 4)
    assert source.repeated_header is None
    report = check(html, rendered(html))
    assert report.alignment == ()
    assert counts(report) == {"tables_total": 1, "tables_evaluated": 1, "rows_data": 4, "rows_paired": 4,
                              "values_total": 8, "values_evaluated": 8, "values_aligned": 8}


def test_row_skip_keys_and_their_precedence():
    html = ("<table><tr><td></td><td>2025</td><td>2024</td></tr>"
            "<tr><td>Revenue</td><td>100</td><td>90</td></tr>"
            "<tr><td>Cost</td><td>40</td><td>30</td></tr>"
            "<tr><td>Cost</td><td>41</td><td>31</td></tr>"
            "<tr><td>Other</td><td>7</td><td>6</td></tr>"
            "<tr><td></td><td>2023</td><td>2022</td></tr>"
            "<tr><td>Revenue</td><td>80</td><td>70</td></tr>"
            "<tr><td>Taxes</td><td>5</td><td>4</td></tr></table>")
    markdown = ("|  | 2025 | 2024 |\n| --- | --- | --- |\n| Revenue | 100 | 90 |\n| Cost | 40 | 30 |\n"
                "| Cost | 41 | 31 |\n|  | 2023 | 2022 |\n| Revenue | 80 | 70 |\n| Taxes | 5 | 4 |")
    report = check(html, markdown)
    # Revenue is not unique in the source and Other is missing from the output: unpaired.
    # Both rows under the repeated "2023 | 2022" header count there first, unpaired or not.
    assert counts(report) == {"tables_total": 1, "tables_evaluated": 1, "rows_data": 6,
                              "row_below_repeated_header": 2, "row_unpaired": 4}


def test_value_skip_keys_and_their_precedence():
    html = ("<table><tr><td></td><td>2025</td><td>2024</td><td></td></tr>"
            "<tr><td>Revenue</td><td>100</td><td>—</td><td>—</td></tr>"
            "<tr><td>Cost</td><td>40</td><td>30</td><td>9</td></tr>"
            "<tr><td>Taxes</td><td>8</td><td>8</td><td>2</td></tr>"
            "<tr><td>Other</td><td>5</td><td>3</td><td>1</td></tr></table>")
    markdown = ("|  | 2025 — Restated | 2024 |  |\n| --- | --- | --- | --- |\n| Revenue | 100 | — | — |\n"
                "| Cost | 40 |  |  |\n| Taxes | 8 | 8 | 2 |\n| Other | 5 | 2025 | 1 |")
    report = check(html, markdown)
    assert report.alignment == ()
    assert counts(report) == {
        "tables_total": 1, "tables_evaluated": 1, "rows_data": 4, "rows_paired": 4, "values_total": 12,
        # Revenue's two dashes (the second also lacks a discriminating header).
        "value_nil": 2,
        # Column 3 has no header text: 9, 2 and 1, though 9 is also missing from the output.
        "value_no_discriminating_header": 3,
        # Cost's 30 and Other's 3 are not in the output.
        "value_missing_in_output": 2,
        # Taxes' two 8s sit in two cells.
        "value_ambiguous_position": 2,
        # 100, 40 and 5 under "2025 — Restated".
        "value_ambiguous_header": 3,
    }


def outcomes(html, markdown):
    """align_table's per-value outcomes for the first table, its rows keyed as check_tables keys them.

    Each value outcome is also checked against the table's coverage counts.
    """
    from sec2md.table_alignment import align_table
    from sec2md.table_completeness import _direct_cells, cell_text, row_label_key

    table, _, hidden, grid_hidden = unit(html)
    rows = unit_rows(table)
    keys = {
        id(row.tr): row_label_key([cell_text(c, hidden) for c in _direct_cells(row.tr) if id(c) not in hidden])
        for row in rows if row.own and id(row.tr) not in hidden
    }
    aligned = align_table(table, rows, grid_hidden, markdown, keys, Counter(key for key in keys.values() if key))
    found = Counter(outcome.outcome for outcome in aligned.outcomes)
    for key in ("value_nil", "value_no_discriminating_header", "value_missing_in_output",
                "value_ambiguous_position", "value_ambiguous_header", "value_unevaluated_budget"):
        assert found[key] == aligned.coverage[key]
    assert found["aligned"] == aligned.coverage["values_aligned"]
    assert found["misaligned"] == aligned.coverage["values_misaligned"]
    return [(o.row, o.column, o.outcome, o.line, o.output_column) for o in aligned.outcomes]


def test_value_outcomes_name_each_values_skip_key_line_and_output_column():
    html = ("<table><tr><td></td><td>2025</td><td>2024</td><td></td></tr>"
            "<tr><td>Revenue</td><td>100</td><td>—</td><td>—</td></tr>"
            "<tr><td>Cost</td><td>40</td><td>30</td><td>9</td></tr>"
            "<tr><td>Taxes</td><td>8</td><td>8</td><td>2</td></tr>"
            "<tr><td>Other</td><td>5</td><td>3</td><td>1</td></tr></table>")
    markdown = ("|  | 2025 — Restated | 2024 |  |\n| --- | --- | --- | --- |\n| Revenue | 100 | — | — |\n"
                "| Cost | 40 |  |  |\n| Taxes | 8 | 8 | 2 |\n| Other | 5 | 2025 | 1 |")
    # (source row, numeric-core column, outcome, paired output line, output column).
    assert outcomes(html, markdown) == [
        (1, 1, "value_ambiguous_header", 0, 1),
        (1, 2, "value_nil", 0, None),
        (1, 3, "value_nil", 0, None),
        (2, 1, "value_ambiguous_header", 1, 1),
        (2, 2, "value_missing_in_output", 1, None),
        (2, 3, "value_no_discriminating_header", 1, None),
        (3, 1, "value_ambiguous_position", 2, None),
        (3, 2, "value_ambiguous_position", 2, None),
        (3, 3, "value_no_discriminating_header", 2, None),
        (4, 1, "value_ambiguous_header", 3, 1),
        (4, 2, "value_missing_in_output", 3, None),
        (4, 3, "value_no_discriminating_header", 3, None),
    ]


def test_value_outcomes_name_aligned_and_misaligned_values():
    markdown = PERIODS_MD.replace("|  | 2025 | 2024 |", "|  | 2025 | 2025 |")
    assert outcomes(PERIODS, markdown) == [
        (1, 1, "aligned", 0, 1),
        (1, 2, "misaligned", 0, 2),
        (2, 1, "aligned", 1, 1),
        (2, 2, "misaligned", 1, 2),
    ]


def test_value_outcomes_of_skipped_rows_carry_the_row_key():
    html = ("<table><tr><td></td><td>2025</td><td>2024</td></tr>"
            "<tr><td>Revenue</td><td>100</td><td>90</td></tr>"
            "<tr><td>Cost</td><td>40</td><td>30</td></tr>"
            "<tr><td>Cost</td><td>41</td><td>31</td></tr>"
            "<tr><td></td><td>2023</td><td>2022</td></tr>"
            "<tr><td>Taxes</td><td>5</td><td>4</td></tr></table>")
    markdown = ("|  | 2025 | 2024 |\n| --- | --- | --- |\n| Revenue | 100 | 90 |\n| Cost | 40 | 30 |\n"
                "| Cost | 41 | 31 |\n|  | 2023 | 2022 |\n| Taxes | 5 | 4 |")
    assert outcomes(html, markdown) == [
        (1, 1, "aligned", 0, 1),
        (1, 2, "aligned", 0, 2),
        (2, 1, "row_unpaired", None, None),
        (2, 2, "row_unpaired", None, None),
        (3, 1, "row_unpaired", None, None),
        (3, 2, "row_unpaired", None, None),
        (5, 1, "row_below_repeated_header", None, None),
        (5, 2, "row_below_repeated_header", None, None),
    ]


def test_skipped_table_has_no_value_outcomes():
    assert outcomes(PERIODS, "") == []
    assert outcomes(PERIODS, "Revenue 100 90") == []


def test_completed_run_with_nothing_eligible_records_zeros():
    report = check("<p>No tables here.</p>", [])
    assert report.alignment_coverage == tuple((key, 0) for key in COVERAGE_KEYS)
    parser = Parser("<p>Revenue was 100.</p>")
    parser.get_pages()
    assert parser.diagnostics.table_header_alignment == ()
    assert parser.diagnostics.table_header_alignment_coverage == tuple((key, 0) for key in COVERAGE_KEYS)


def test_findings_list_ten_per_table_with_the_total():
    columns = 12
    html = ("<table><tr><td></td>" + "".join(f"<td>Q{index}</td>" for index in range(columns)) + "</tr>"
            "<tr><td>Revenue</td>" + "".join(f"<td>{index + 10}</td>" for index in range(columns)) + "</tr></table>")
    header = "|  | " + " | ".join(f"Q{(index + 1) % columns}" for index in range(columns)) + " |"
    markdown = header + "\n" + "| --- " * (columns + 1) + "|\n| Revenue | " + " | ".join(
        str(index + 10) for index in range(columns)) + " |"
    report = check(html, markdown)
    assert len(report.alignment) == 11
    assert report.alignment[0] == f'{WHERE}: "Revenue" 10 under "Q1"; expected "Q0"'
    assert report.alignment[-1] == f"{WHERE}: 12 misaligned values in total, 10 listed"
    assert counts(report)["values_misaligned"] == 12


# The baseline shift: today's main on a BABA-24-shaped table.

BABA_24 = (
    "<table>"
    "<tr><td></td><td></td><td></td><td colspan='14'>Year ended March 31,</td><td></td></tr>"
    "<tr><td></td><td></td><td></td><td colspan='2'>2023</td><td></td><td></td><td colspan='2'>2024</td>"
    "<td></td><td></td><td colspan='6'>2025</td><td></td></tr>"
    "<tr><td></td><td></td><td></td><td colspan='2'>RMB</td><td></td><td></td><td colspan='2'>RMB</td>"
    "<td></td><td></td><td colspan='2'>RMB</td><td></td><td></td><td colspan='2'>US$</td><td></td></tr>"
    "<tr><td></td><td>Notes</td><td colspan='16'></td></tr>"
    "<tr><td>Revenue</td><td>5, 24</td><td></td><td></td><td>868,687</td><td></td><td></td><td></td>"
    "<td>941,168</td><td></td><td></td><td></td><td>996,347</td><td></td><td></td><td></td><td>137,300</td>"
    "<td></td></tr></table>"
)
# main's rendering (evidence report, example 3b): each year carried one column left.
BABA_24_MAIN = ("|  | 2023 | 2024 | 2025 |  |  |\n| --- | --- | --- | --- | --- | --- |\n"
                "|  | RMB | RMB | RMB | US$ |  |\n| Revenue | 5, 24 | 868,687 | 941,168 | 996,347 | 137,300 |")


def test_checker_reports_mains_baba_24_shift():
    report = check(BABA_24, BABA_24_MAIN)
    assert report.alignment == (
        f'{WHERE}: "Revenue" 868687 under "2024"; expected "2023 — RMB"',
        f'{WHERE}: "Revenue" 941168 under "2025"; expected "2024 — RMB"',
        f'{WHERE}: "Revenue" 996347 under ""; expected "2025 — RMB"',
        f'{WHERE}: "Revenue" 137300 under ""; expected "2025 — US$"',
    )
    assert counts(report) == {"tables_total": 1, "tables_evaluated": 1, "rows_data": 1, "rows_paired": 1,
                              "values_total": 4, "values_evaluated": 4, "values_misaligned": 4}


def test_prototype_rendering_of_baba_24_is_aligned():
    markdown = rendered(BABA_24)
    assert markdown.split("\n")[0] == (
        "|  | Notes | Year ended March 31, — 2023 — RMB | Year ended March 31, — 2024 — RMB "
        "| Year ended March 31, — 2025 — RMB | Year ended March 31, — 2025 — US$ |"
    )
    report = check(BABA_24, markdown)
    assert report.alignment == ()
    assert counts(report)["values_aligned"] == 4


# Integration: check_tables, Parser and ParseDiagnostics.

def test_parser_records_alignment_findings_and_coverage(monkeypatch):
    original = Parser._render_table

    def shifted(self, element):
        return original(self, element).replace("|  | 2025 | 2024 |", "| 2025 | 2024 |  |")

    monkeypatch.setattr(Parser, "_render_table", shifted)
    parser = Parser(PERIODS)
    parser.get_pages()
    diagnostics = parser.diagnostics
    assert diagnostics.table_header_alignment == (
        'table 1 (snapshot 1, page 1): "Revenue" 100 under "2024"; expected "2025"',
        'table 1 (snapshot 1, page 1): "Revenue" 90 under ""; expected "2024"',
        'table 1 (snapshot 1, page 1): "Cost" 40 under "2024"; expected "2025"',
        'table 1 (snapshot 1, page 1): "Cost" 30 under ""; expected "2024"',
    )
    assert dict(diagnostics.table_header_alignment_coverage)["values_misaligned"] == 4
    assert parser.table_report.alignment == diagnostics.table_header_alignment


def test_check_tables_places_each_unit_once(monkeypatch):
    import sec2md.table_completeness as completeness

    calls = []
    real = completeness.place_unit

    def counted(*args):
        calls.append(args[0])
        return real(*args)

    monkeypatch.setattr(completeness, "place_unit", counted)
    report = check(PERIODS + TEXT_TABLE, [PERIODS_MD, "Name Title Jane CFO"])
    # Checks 1 and the alignment share one placement; the text rendering needs none.
    assert len(calls) == 1
    assert counts(report)["values_aligned"] == 4 and counts(report)["table_no_separator"] == 1


LINKED_YEAR = (
    "<table><tr><td></td><td>2025</td><td><a href='a.htm'>2024</a></td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>"
)


def test_alignment_reuses_extracted_cell_texts_and_extracts_link_cells_itself():
    soup = BeautifulSoup(LINKED_YEAR, "lxml")
    table = soup.find("table")
    renderer = TableParser(table, base_url="https://example.com/doc.htm")
    markdown = renderer.md()
    texts = {id(cell.node): cell.text for row in renderer.cells for cell in row if "](" not in cell.text}
    assert sorted(texts.values()) == ["", "100", "2025", "90", "Revenue"]
    inputs = (soup, {id(table): markdown}, {id(table): 3}, {id(table): 2})
    own = check_tables(*inputs)
    assert check_tables(*inputs, cell_texts=texts) == own
    assert counts(own)["values_aligned"] == 2
    # The texts are read, not extracted again: a different text changes the expectation.
    year = next(cell for row in renderer.cells for cell in row if cell.text == "2025")
    changed = check_tables(*inputs, cell_texts={**texts, id(year.node): "2023"})
    assert changed.alignment == (f'{WHERE}: "Revenue" 100 under "2025"; expected "2023"',)


def test_parser_records_the_link_free_cell_texts_of_its_render():
    parser = Parser(LINKED_YEAR)
    parser.get_pages()
    assert sorted(parser._cell_texts.values()) == ["", "100", "2025", "90", "Revenue"]
    assert parser.table_report is not None
    assert parser.diagnostics.table_header_alignment == ()


# Spec revision 12, link-aware equality: the renderer and the checker compare the same
# extracted text, with links resolved against the same base URL. These two relative hrefs
# differ only in form and join to one URL.
SAME_PLAN = LINKED_PLANS.replace("ex102.htm", "./ex101.htm")
BASE_URL = "https://www.sec.gov/Archives/edgar/data/1/000000000000000001/doc.htm"


def test_link_destinations_resolve_against_the_render_base_url():
    soup = BeautifulSoup(SAME_PLAN, "lxml")
    table = soup.find("table")
    markdown = TableParser(table, base_url=BASE_URL).md()
    plan = "[Plan](https://www.sec.gov/Archives/edgar/data/1/000000000000000001/ex101.htm)"
    # R6 compares the joined destinations, so it writes "Plan" once.
    assert markdown.splitlines()[0] == f"|  | {plan} | {plan} — Budget |"
    inputs = (soup, {id(table): markdown}, {id(table): 3}, {id(table): 2})
    report = check_tables(*inputs, base_url=BASE_URL)
    assert report.alignment == ()
    assert counts(report)["values_aligned"] == 2
    # Raw hrefs would keep two entries, so the faithful header would read as a loss.
    assert check_tables(*inputs).alignment == (f'{WHERE}: "Revenue" 100 under "Plan"; expected "Plan — Plan"',)


def test_without_a_base_url_both_sides_compare_raw_destinations():
    markdown = rendered(SAME_PLAN)
    assert markdown.splitlines()[0] == "|  | [Plan](ex101.htm) — [Plan](./ex101.htm) | [Plan](ex101.htm) — Budget |"
    assert check(SAME_PLAN, markdown).alignment == ()


def test_parser_checks_links_against_its_source_url():
    parser = Parser(SAME_PLAN, source_url=BASE_URL)
    parser.get_pages()
    assert parser.table_report is not None
    assert parser.diagnostics.table_header_alignment == ()
    assert dict(parser.diagnostics.table_header_alignment_coverage)["values_aligned"] == 2


def test_alignment_failure_inside_check_tables_leaves_empty_fields(monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("sec2md.table_alignment.align_table", boom)
    parser = Parser(PERIODS)
    pages = parser.get_pages()
    assert "| Revenue | 100 | 90 |" in pages[0].content
    assert parser.table_report is None
    assert parser.diagnostics.table_header_alignment == ()
    assert parser.diagnostics.table_header_alignment_coverage == ()
    assert "the checks failed" in caplog.text


def test_policy_off_skips_the_alignment_check(monkeypatch):
    from sec2md.core import convert_with_diagnostics

    monkeypatch.setattr("sec2md.table_alignment.align_table", lambda *a, **k: pytest.fail("alignment ran"))
    _, diagnostics = convert_with_diagnostics(PERIODS, quality_policy="off")
    assert diagnostics.table_header_alignment == ()
    assert diagnostics.table_header_alignment_coverage == ()
    monkeypatch.undo()
    _, diagnostics = convert_with_diagnostics(PERIODS, quality_policy="warn")
    assert dict(diagnostics.table_header_alignment_coverage)["values_aligned"] == 4
