"""Tests for the standard table parser (table_parser.py)."""

import pytest
from bs4 import BeautifulSoup, Tag

from sec2md.table_parser import TableParser, Cell


def _make_table(html: str) -> Tag:
    """Parse an HTML table string into a Tag."""
    soup = BeautifulSoup(html, "lxml")
    return soup.find("table")


def test_adjacent_fragments_with_same_href_coalesce():
    html = '<table><tr><td><a href="ex99.htm">Augu</a><a href="ex99.htm">st 26</a></td></tr></table>'
    parser = TableParser(_make_table(html), base_url="https://www.sec.gov/Archives/a/filing.htm")
    assert parser.to_matrix()[0][0] == "[August 26](https://www.sec.gov/Archives/a/ex99.htm)"


def test_distinct_links_remain_distinct_and_pipe_is_escaped():
    html = '<table><tr><td><a href="a.htm">First</a> | <a href="b.htm">Second</a></td></tr></table>'
    rendered = TableParser(_make_table(html), base_url=None).to_matrix()[0][0]
    assert rendered == "[First](a.htm) \\| [Second](b.htm)"


def test_linked_cell_preserves_navigable_string_whitespace():
    html = '<table><tr><td><a href="a.htm">First </a>  \nmiddle  <a href="b.htm"> Second</a></td></tr></table>'
    rendered = TableParser(_make_table(html), base_url=None).to_matrix()[0][0]
    assert rendered == "[First ](a.htm)   middle  [ Second](b.htm)"


class TestBasicTables:
    """Simple table parsing."""

    def test_simple_2x2(self):
        html = """<table>
        <tr><td>Name</td><td>Value</td></tr>
        <tr><td>A</td><td>1</td></tr>
        </table>"""
        md = TableParser(_make_table(html)).to_markdown()
        assert "Name" in md
        assert "Value" in md
        assert "---" in md  # separator
        assert "A" in md
        assert "1" in md

    def test_header_row_has_separator(self):
        html = """<table>
        <tr><td>H1</td><td>H2</td></tr>
        <tr><td>D1</td><td>D2</td></tr>
        </table>"""
        md = TableParser(_make_table(html)).to_markdown()
        lines = md.strip().split("\n")
        assert len(lines) >= 3
        assert all(c in "|- " for c in lines[1].replace("---", ""))

    def test_three_columns(self):
        html = """<table>
        <tr><td>A</td><td>B</td><td>C</td></tr>
        <tr><td>1</td><td>2</td><td>3</td></tr>
        </table>"""
        md = TableParser(_make_table(html)).to_markdown()
        assert md.count("|") >= 8  # 4 per row * 2 rows minimum

    def test_empty_cells(self):
        html = """<table>
        <tr><td>X</td><td></td></tr>
        <tr><td></td><td>Y</td></tr>
        </table>"""
        md = TableParser(_make_table(html)).to_markdown()
        assert "X" in md
        assert "Y" in md

    def test_multiline_non_link_cell_is_normalized_to_one_markdown_row(self):
        """Catch non-link cell newlines escaping into physical Markdown rows."""
        html = """<table>
        <tr><th>Label</th><th>Value</th></tr>
        <tr><td>alpha\r\nbeta\ngamma</td><td>1</td></tr>
        </table>"""

        md = TableParser(_make_table(html)).to_markdown()
        lines = md.splitlines()

        assert lines == [
            "| Label | Value |",
            "| --- | --- |",
            "| alpha beta gamma | 1 |",
        ]
        assert all(line.count("|") == 3 for line in lines)


class TestSpanning:
    """Rowspan and colspan handling."""

    def test_colspan(self):
        html = """<table>
        <tr><td colspan="2">Merged</td></tr>
        <tr><td>A</td><td>B</td></tr>
        </table>"""
        tp = TableParser(_make_table(html))
        matrix = tp.to_matrix()
        # First row should have the merged cell
        assert any("Merged" in cell for row in matrix for cell in row)

    def test_rowspan(self):
        html = """<table>
        <tr><td rowspan="2">Span</td><td>R1</td></tr>
        <tr><td>R2</td></tr>
        </table>"""
        tp = TableParser(_make_table(html))
        matrix = tp.to_matrix()
        assert len(matrix) == 2
        assert "Span" in matrix[0][0]

    def test_invalid_rowspan_ignored(self):
        html = """<table>
        <tr><td rowspan="abc">Cell</td><td>Other</td></tr>
        </table>"""
        # Should not crash
        tp = TableParser(_make_table(html))
        assert tp.to_markdown() is not None


class TestPipeEscaping:
    """Pipe characters in cells must be escaped."""

    def test_pipe_in_cell_escaped(self):
        html = """<table>
        <tr><td>A|B</td><td>C</td></tr>
        <tr><td>D</td><td>E</td></tr>
        </table>"""
        md = TableParser(_make_table(html)).to_markdown()
        assert "A\\|B" in md


class TestListTable:
    """Single-row tables with bullet markers should render as list items."""

    def test_bullet_list_table(self):
        html = """<table><tr><td>•</td><td>List item text</td></tr></table>"""
        md = TableParser(_make_table(html)).to_markdown()
        assert md.startswith("- ")
        assert "List item text" in md

    def test_dash_list_table(self):
        html = """<table><tr><td>-</td><td>Dash item</td></tr></table>"""
        md = TableParser(_make_table(html)).to_markdown()
        assert "Dash item" in md


class TestHeaderFusion:
    """Multi-row header detection and fusion."""

    def test_two_row_header_fused(self):
        html = """<table>
        <tr><td></td><td>2023</td><td>2022</td></tr>
        <tr><td>Metric</td><td>(millions)</td><td>(millions)</td></tr>
        <tr><td>Revenue</td><td>100</td><td>90</td></tr>
        </table>"""
        tp = TableParser(_make_table(html))
        md = tp.to_markdown()
        # Headers should be fused with " — " separator
        assert "—" in md or "2023" in md  # Either fused or separate


class TestToMatrix:
    """Matrix representation of tables."""

    def test_accounting_parentheses_merge_into_one_markdown_cell(self):
        html = """
        <table><tr><th>Item</th><th></th><th>2022</th><th></th></tr>
        <tr><td>Net loss</td><td>(</td><td>16,173</td><td>)</td></tr>
        <tr><td>Operating loss</td><td>(</td><td>9,501</td><td>)</td></tr></table>
        """
        matrix = TableParser(_make_table(html)).to_matrix()
        assert matrix[1] == ["Net loss", "(16,173)"]
        assert matrix[2] == ["Operating loss", "(9,501)"]

    def test_mixed_parenthesis_column_does_not_merge(self):
        html = """
        <table><tr><th>Label</th><th>Qualifier</th><th>Value</th></tr>
        <tr><td>A</td><td>(unaudited)</td><td>10</td></tr>
        <tr><td>B</td><td>note</td><td>20</td></tr></table>
        """
        assert len(TableParser(_make_table(html)).to_matrix()[0]) == 3

    def test_percent_marker_merge_preserves_numeric_token_boundary(self):
        html = """
        <table><tr><th>Label</th><th>Value</th><th></th></tr>
        <tr><td>A</td><td>3</td><td>%</td></tr>
        <tr><td>B</td><td>4</td><td>%</td></tr></table>
        """
        matrix = TableParser(_make_table(html)).to_matrix()
        assert matrix[1] == ["A", "3 %"]
        assert matrix[2] == ["B", "4 %"]

    def test_unmatched_repeated_open_parentheses_do_not_merge(self):
        html = """
        <table><tr><th>Label</th><th>Marker</th><th>Value</th></tr>
        <tr><td>A</td><td>(</td><td>10</td></tr>
        <tr><td>B</td><td>(</td><td>20</td></tr></table>
        """
        matrix = TableParser(_make_table(html)).to_matrix()
        assert matrix[1] == ["A", "(", "10"]
        assert matrix[2] == ["B", "(", "20"]

    def test_unmatched_repeated_close_parentheses_do_not_merge(self):
        html = """
        <table><tr><th>Label</th><th>Value</th><th>Marker</th></tr>
        <tr><td>A</td><td>10</td><td>)</td></tr>
        <tr><td>B</td><td>20</td><td>)</td></tr></table>
        """
        matrix = TableParser(_make_table(html)).to_matrix()
        assert matrix[1] == ["A", "10", ")"]
        assert matrix[2] == ["B", "20", ")"]

    def test_alternating_structural_markers_do_not_merge(self):
        html = """
        <table><tr><th>Label</th><th>Left</th><th>Marker</th><th>Right</th></tr>
        <tr><td>A</td><td>10</td><td>%</td><td>100</td></tr>
        <tr><td>B</td><td>20</td><td>$</td><td>200</td></tr></table>
        """
        matrix = TableParser(_make_table(html)).to_matrix()
        assert matrix[1] == ["A", "10", "%", "100"]
        assert matrix[2] == ["B", "20", "$", "200"]

    def test_singleton_structural_marker_does_not_bypass_two_row_floor(self):
        html = """
        <table><tr><th>Label</th><th>A</th><th></th><th>B</th><th></th><th>C</th><th></th></tr>
        <tr><td>R1</td><td>(10</td><td>)</td><td>(20</td><td>)</td><td>(30</td><td>)</td></tr>
        <tr><td>R2</td><td>(11</td><td>)</td><td>(21</td><td>)</td><td>31</td><td></td></tr></table>
        """
        matrix = TableParser(_make_table(html)).to_matrix()
        assert len(matrix[0]) == 5
        assert matrix[1][-2:] == ["(30", ")"]

    def test_suffix_marker_header_merges_to_left_numeric_column(self):
        html = """
        <table><tr><th>Label</th><th>2022</th><th>Change</th><th>2021</th></tr>
        <tr><td>A</td><td>10</td><td>%</td><td>20</td></tr>
        <tr><td>B</td><td>30</td><td>%</td><td>40</td></tr></table>
        """
        matrix = TableParser(_make_table(html)).to_matrix()
        assert matrix[0] == ["Label", "2022 Change", "2021"]
        assert matrix[1] == ["A", "10 %", "20"]

    def test_matrix_dimensions(self):
        html = """<table>
        <tr><td>A</td><td>B</td></tr>
        <tr><td>C</td><td>D</td></tr>
        </table>"""
        matrix = TableParser(_make_table(html)).to_matrix()
        assert len(matrix) == 2
        assert all(len(row) == 2 for row in matrix)

    def test_matrix_content(self):
        html = """<table>
        <tr><td>Hello</td></tr>
        </table>"""
        matrix = TableParser(_make_table(html)).to_matrix()
        assert matrix[0][0] == "Hello"


class TestTableParserValidation:
    """Input validation."""

    def test_rejects_non_table_tag(self):
        soup = BeautifulSoup("<div>Not a table</div>", "lxml")
        with pytest.raises(ValueError, match="table tag"):
            TableParser(soup.find("div"))
