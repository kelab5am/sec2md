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


# --- task 5: matching, row structure and the report --------------------------------------

from sec2md.table_completeness import (  # noqa: E402
    TableCompletenessReport,
    TableFinding,
    check_tables,
    match_occurrences,
    row_structure,
)


def occurrences(*items):
    return Counter({item: 1 for item in items})


def test_match_occurrences_claims_within_proven_row_pairs():
    rows = [("impairment", occurrences(("9", "value_numeric", "body"))),
            ("footnote", occurrences(("9", "standalone_marker", "body")))]
    body = [("impairment", Counter()), ("footnote", Counter({("9", "numeric_cell"): 1}))]
    values, reported = match_occurrences(rows, body, Counter())
    assert values == [("9", "body", False)]
    assert reported == []


def test_match_occurrences_marks_shared_provenance_ambiguous():
    rows = [("total", occurrences(("9", "value_numeric", "body"))),
            ("total", occurrences(("9", "standalone_marker", "body")))]
    body = [("total", Counter({("9", "numeric_cell"): 1}))]
    values, reported = match_occurrences(rows, body, Counter())
    assert values == [("9", "body", True)]
    assert reported == []


def test_match_occurrences_reports_lost_references_without_failing():
    rows = [("noteimpairment#9", occurrences(("9", "reference", "label"), ("9", "value_numeric", "body")))]
    body = [("impairment", Counter({("9", "numeric_cell"): 1}))]
    assert match_occurrences(rows, body, Counter()) == ([], [("9", "reference")])


SEGMENT = "| Item | 2026 | 2025 |\n| --- | --- | --- |\n| Revenue | 120 | 100 |\n| Cost | 50 | 40 |"


@pytest.mark.parametrize("segment, expected", [
    (SEGMENT, []),
    (SEGMENT.replace("| 120 | 100 |", "| 100 | 120 |"), ["source row 1: values out of order within the row"]),
    ("| Item | 2026 | 2025 |\n| --- | --- | --- |\n| Cost | 50 | 40 |\n| Revenue | 120 | 100 |",
     ["source row 2: appears before an earlier source row"]),
    (SEGMENT.replace("| 100 |", "| 40 |", 1).replace("| 50 | 40 |", "| 50 | 100 |"),
     ["source row 1: values present but split across output rows",
      "source row 2: values present but split across output rows"]),
    ("Revenue 120 100 Cost 50 40", []),
])
def test_row_structure(segment, expected):
    assert row_structure([("120", "100"), ("50", "40")], segment) == expected


def test_finding_messages():
    finding = TableFinding(2, 1, 3, missing_values=(("9943", "body", False), ("9", "label", True)),
                           missing_reported=(("1", "reference"),),
                           structure=("source row 1: values out of order within the row",))
    assert finding.value_message() == "table 2 (snapshot 1, page 3): missing 9943 x1 [body], 9 x1 [label, ambiguous] (total 2)"
    assert finding.reported_message() == "table 2 (snapshot 1, page 3): missing 1 x1 [reference] (total 1)"
    assert finding.structure_messages() == ("table 2 (snapshot 1, page 3): source row 1: values out of order within the row",)
    assert finding.messages() == ((finding.value_message(), finding.reported_message()) + finding.structure_messages())
    empty = TableFinding(1, None, None, missing_values=(("12", "body", False),) * 3, produced_output=False)
    assert empty.value_message() == "table 1 produced no output (3 numbers)"
    report = TableCompletenessReport(4, (finding, empty))
    assert report.failures == (finding.value_message(), empty.value_message())
    assert report.reported == (finding.reported_message(),)
    assert report.structure == finding.structure_messages()


MERGE_LOSS = ("<table><tr><td>2024</td><td>$</td><td>9,943</td></tr>"
              "<tr><td>2025</td><td></td><td>10,775</td></tr><tr><td>Total</td><td>$</td><td>20,718</td></tr></table>")


def test_check_tables_compares_each_table_with_its_own_output():
    soup = soup_of("<p>Commitments include $9,943 million due in 2024.</p>" + MERGE_LOSS)
    table = soup.find("table")
    output = "| 2024 | $ |\n| --- | --- |\n| 2025 | 10,775 |\n| Total | $ 20,718 |"
    report = check_tables(soup, {id(table): output}, {id(table): 1}, {id(table): 1})
    assert report.tables_checked == 1
    assert report.failures == ("table 1 (snapshot 1, page 1): missing 9943 x1 [body] (total 1)",)


def test_check_tables_excludes_header_rows_from_row_structure():
    soup = soup_of("<table><tr><th>Denomination</th><th>€1</th><th>€2</th></tr>"
                   "<tr><td>Issued</td><td>2</td><td>1</td></tr></table>")
    table = soup.find("table")
    output = "| Denomination | €1 | €2 |\n| --- | --- | --- |\n| Issued | 2 | 1 |"
    report = check_tables(soup, {id(table): output}, {}, {})
    assert report == TableCompletenessReport(1, ())


def test_check_tables_reports_tables_without_output():
    soup = soup_of(MERGE_LOSS)
    report = check_tables(soup, {}, {}, {})
    assert report.failures == ("table 1 produced no output (5 numbers)",)


def test_check_tables_skips_hidden_and_token_free_tables():
    soup = soup_of('<div style="display:none">' + MERGE_LOSS + "</div>"
                   "<table><tr><td>Name</td><td>Title</td></tr><tr><td>Jane</td><td>CFO</td></tr></table>")
    report = check_tables(soup, {}, {}, {})
    assert report == TableCompletenessReport(0, ())
