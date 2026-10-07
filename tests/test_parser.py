"""Tests for the HTML parser (parser.py)."""

import re
from html import escape

import pytest
from bs4 import BeautifulSoup

from sec2md.absolute_table_parser import AbsolutelyPositionedTableParser
from sec2md.element_builder import (
    _extract_xbrl_tags,
    _merge_small_blocks,
    augment_html_with_ids,
    ordered_unique_nodes,
)
from sec2md.core import convert_to_markdown
from sec2md.models import Element, Page
from sec2md.parser import Parser
from sec2md.quality import (
    ElementHeaderRecord,
    HeaderLineLocation,
    enforce_quality,
    locate_header_lines,
    trace_numeric_failures,
)


class TestParserBasics:
    """Core parsing behavior."""

    def test_simple_paragraph(self):
        parser = Parser("<html><body><p>Hello world</p></body></html>")
        pages = parser.get_pages(include_elements=False)
        assert len(pages) == 1
        assert "Hello world" in pages[0].content

    def test_exposes_latest_parse_diagnostics(self):
        parser = Parser("<html><body><p>Hello world</p></body></html>")
        parser.get_pages(include_elements=False)
        assert parser.diagnostics is not None
        assert parser.diagnostics.source_visible_chars == 11
        assert parser.diagnostics.output_visible_chars == 11
        assert parser.diagnostics.warnings == ()

    def test_merged_blocks_preserve_identity_order_and_final_annotations(self):
        first = BeautifulSoup("<p>First paragraph</p>", "lxml").p
        second = BeautifulSoup("<p>Second paragraph</p>", "lxml").p
        proxy_one = BeautifulSoup("<p>Proxy paragraph</p>", "lxml").p
        proxy_two = BeautifulSoup("<p>Proxy paragraph</p>", "lxml").p
        generated_heading = BeautifulSoup(
            "<table><tr><th>Generated heading</th></tr></table>", "lxml"
        ).table
        proxy_one["data-sec2md-block"] = "stale-element"
        proxy_two["data-sec2md-block"] = "stale-element"

        blocks = [
            (
                Element(id="old-1", content="First paragraph", kind="paragraph", page_start=1, page_end=1),
                [first, proxy_one],
                None,
            ),
            (
                Element(id="old-2", content="Second paragraph", kind="paragraph", page_start=1, page_end=1),
                [second, proxy_two, generated_heading, proxy_one],
                None,
            ),
        ]

        merged = _merge_small_blocks(blocks, page_num=1, min_chars=500)
        assert len(merged) == 1
        element, nodes, _ = merged[0]
        expected_nodes = ordered_unique_nodes(
            [first, proxy_one], [second, proxy_two, generated_heading, proxy_one]
        )
        assert [id(node) for node in nodes] == [id(node) for node in expected_nodes]

        augment_html_with_ids({1: [element]}, {element.id: nodes})
        assert all(node.get("data-sec2md-block") == element.id for node in nodes)
        assert all(node.get("data-sec2md-block") != "stale-element" for node in nodes)

    def test_xbrl_tags_include_only_visible_mapped_nodes(self):
        soup = BeautifulSoup(
            """
            <div>
              <p><ix:nonfraction name="us-gaap:Revenue">100</ix:nonfraction></p>
              <p style="display:none"><ix:nonfraction name="us-gaap:Hidden">200</ix:nonfraction></p>
              <ix:hidden><ix:nonnumeric name="us-gaap:AlsoHidden">text</ix:nonnumeric></ix:hidden>
            </div>
            """,
            "lxml",
        )
        assert _extract_xbrl_tags([soup.div]) == ["us-gaap:Revenue"]

    def test_repeated_parse_clears_annotations_from_removed_image_nodes(self):
        parser = Parser(
            '<html><body><p>Visible filing text</p>'
            '<img src="chart.png" alt="Chart"></body></html>'
        )
        image_node = parser.soup.find("img")

        parser.get_pages(include_images=True)
        assert image_node.get("data-sec2md-block")

        parser.get_pages(include_images=False)
        assert image_node.get("data-sec2md-block") is None

    def test_multiple_paragraphs(self):
        parser = Parser("<html><body><p>Para one</p><p>Para two</p></body></html>")
        pages = parser.get_pages(include_elements=False)
        content = pages[0].content
        assert "Para one" in content
        assert "Para two" in content

    def test_nested_bold_italic(self):
        parser = Parser("<html><body><p><b><i>Bold italic</i></b></p></body></html>")
        pages = parser.get_pages(include_elements=False)
        assert "***Bold italic***" in pages[0].content

    def test_unordered_list(self):
        html = "<html><body><ul><li>Item A</li><li>Item B</li></ul></body></html>"
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        content = pages[0].content
        assert "- Item A" in content
        assert "- Item B" in content

    def test_ordered_list(self):
        html = "<html><body><ol><li>First</li><li>Second</li></ol></body></html>"
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        content = pages[0].content
        assert "1. First" in content
        assert "2. Second" in content

    def test_hidden_element_excluded(self):
        html = '<html><body><p>Visible</p><div style="display:none">Hidden</div></body></html>'
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert "Hidden" not in pages[0].content

    def test_nbsp_cleaned(self):
        html = "<html><body><p>Hello\u00a0world</p></body></html>"
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert "\u00a0" not in pages[0].content

    def test_zero_width_chars_cleaned(self):
        html = "<html><body><p>Hello\u200bworld</p></body></html>"
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert "\u200b" not in pages[0].content


class TestPageSplitting:
    """CSS page-break handling."""

    def test_break_before_always(self):
        html = """<html><body>
        <p>Page 1</p>
        <div style="page-break-before:always"><p>Page 2</p></div>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert len(pages) == 2

    def test_break_after_always(self):
        html = """<html><body>
        <div style="page-break-after:always"><p>Page 1</p></div>
        <p>Page 2</p>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert len(pages) == 2

    def test_css_break_before_page(self):
        html = """<html><body>
        <p>Page 1</p>
        <div style="break-before:page"><p>Page 2</p></div>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert len(pages) == 2

    def test_multiple_breaks(self):
        html = """<html><body>
        <p>Page 1</p>
        <div style="page-break-before:always"><p>Page 2</p></div>
        <div style="page-break-before:always"><p>Page 3</p></div>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert len(pages) == 3

    def test_page_numbers_sequential(self):
        html = """<html><body>
        <p>Content A</p>
        <div style="page-break-before:always"><p>Content B</p></div>
        <div style="page-break-before:always"><p>Content C</p></div>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert pages[0].number == 1
        assert pages[1].number == 2
        assert pages[2].number == 3


class TestBreadcrumbStripping:
    """PART/ITEM breadcrumbs at page tops should be removed."""

    def test_strips_part_item_breadcrumb(self):
        content = "PART II\n\nItem 7\n\nActual content here"
        result = Parser._strip_page_breadcrumbs(content)
        assert "Actual content" in result
        assert result.startswith("Actual")

    def test_preserves_item_with_title(self):
        content = "PART II\n\nITEM 7. Management Discussion\n\nContent"
        result = Parser._strip_page_breadcrumbs(content)
        # Item with title is a real section header, not a breadcrumb
        assert "PART II" in result

    def test_preserves_non_breadcrumb_content(self):
        content = "Some regular content\nMore content"
        result = Parser._strip_page_breadcrumbs(content)
        assert result == content

    def test_strips_bold_wrapped_breadcrumb(self):
        content = "**PART I**\n\n**ITEM 1**\n\nActual content"
        result = Parser._strip_page_breadcrumbs(content)
        assert result.startswith("Actual")


class TestElementExtraction:
    """Element extraction from parsed pages."""

    def test_elements_have_ids(self):
        html = "<html><body><p>Paragraph one</p><p>Paragraph two</p></body></html>"
        parser = Parser(html)
        pages = parser.get_pages(include_elements=True)
        elements = pages[0].elements
        assert elements is not None
        for elem in elements:
            assert elem.id

    def test_elements_have_content(self):
        html = "<html><body><p>Some content here</p></body></html>"
        parser = Parser(html)
        pages = parser.get_pages(include_elements=True)
        assert any("Some content" in e.content for e in pages[0].elements)

    def test_element_ids_are_unique(self):
        html = "<html><body><p>A</p><p>B</p><p>C</p></body></html>"
        parser = Parser(html)
        pages = parser.get_pages(include_elements=True)
        ids = [e.id for e in pages[0].elements]
        assert len(ids) == len(set(ids))

    def test_table_element_kind(self):
        html = """<html><body>
        <table><tr><td>A</td><td>1</td></tr><tr><td>B</td><td>2</td></tr></table>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=True)
        table_elements = [e for e in pages[0].elements if e.kind == "table"]
        assert len(table_elements) >= 1

    def test_element_page_numbers(self):
        html = """<html><body>
        <p>Page 1</p>
        <div style="page-break-before:always"><p>Page 2</p></div>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=True)
        for page in pages:
            if page.elements:
                for elem in page.elements:
                    assert elem.page_start == page.number


class TestDisplayPageDetection:
    """Display page number extraction."""

    def _make_parser(self):
        return Parser("<html><body></body></html>")

    def test_validate_sequence_needs_five_pairs(self):
        candidates = [(1, 1), (2, 2), (3, 3)]
        assert self._make_parser()._validate_page_number_sequence(candidates) is False

    def test_validate_sequence_accepts_increasing(self):
        candidates = [(i, i + 10) for i in range(1, 10)]
        assert self._make_parser()._validate_page_number_sequence(candidates) is True

    def test_validate_sequence_rejects_decreasing(self):
        candidates = [(i, 100 - i) for i in range(1, 10)]
        assert self._make_parser()._validate_page_number_sequence(candidates) is False


class TestOneRowTable:
    """Single-row tables should be flattened to text."""

    def test_item_header_table(self):
        html = """<html><body>
        <table><tr><td>Item 1.</td><td>Business</td></tr></table>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        content = pages[0].content
        assert "ITEM 1" in content
        assert "Business" in content

    def test_part_header_table(self):
        html = """<html><body>
        <table><tr><td>Part II</td></tr></table>
        </body></html>"""
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False)
        assert "PART II" in pages[0].content

    @pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
    def test_part_header_table_keeps_every_cell(self, capture_tables):
        # R8, CAT 10-K 2025 table 7: the PART branch used to return "PART III" alone and
        # drop the cell holding 2025 and 120.
        parser = Parser(f"<html><body>{CAT_7_TABLE}</body></html>", capture_tables=capture_tables)
        pages = parser.get_pages()
        assert pages[0].content == f"PART III {CAT_7_SENTENCE}"
        assert [element.content for element in pages[0].elements] == [f"PART III {CAT_7_SENTENCE}"]
        assert parser.diagnostics.warnings == ()

    def test_part_header_cells_are_joined_after_the_normalized_label(self):
        parser = Parser("<p>x</p>")
        cells = BeautifulSoup(
            "<table><tr><td> part\xa0iv </td><td></td><td>Exhibits and</td><td>Financial Statement Schedules</td>"
            "</tr></table>",
            "lxml",
        ).find_all("td")
        assert parser._one_row_table_to_text(cells) == "PART IV Exhibits and Financial Statement Schedules"
        assert parser._one_row_table_to_text(cells[:2]) == "PART IV"

    def test_item_header_table_still_keeps_only_the_first_later_cell(self):
        # R8 changes the PART branch only; the ITEM branch keeps its title cell, as today.
        parser = Parser("<p>x</p>")
        cells = BeautifulSoup(
            "<table><tr><td>Item 1.</td><td></td><td>Business</td><td>Page 4</td></tr></table>", "lxml"
        ).find_all("td")
        assert parser._one_row_table_to_text(cells) == "ITEM 1. Business"


# CAT 10-K 2025 table 7: the cover page's "Documents Incorporated by Reference" row, with
# its column-width row of empty cells.
CAT_7_SENTENCE = (
    "2025 Annual Meeting Proxy Statement (Proxy Statement) to be filed with the Securities and "
    "Exchange Commission (SEC) within 120 days after the end of the fiscal year."
)
CAT_7_TABLE = (
    '<table style="border-collapse:collapse;display:inline-table;width:99.853%">'
    '<tr><td style="width:1.0%"></td><td style="width:13.980%"></td><td style="width:0.1%"></td>'
    '<td style="width:1.0%"></td><td style="width:83.820%"></td><td style="width:0.1%"></td></tr>'
    '<tr><td colspan="3"><span>Part&#160;III</span></td>'
    f'<td colspan="3"><div><span>{CAT_7_SENTENCE}</span></div></td></tr></table>'
)


# R6a: a spanning 2025 over two labels; its header line repeats 2025 legitimately.
REPEATED_HEADER_TABLE = (
    '<table><tr><th>Metric</th><th colspan="2">{top}</th></tr>'
    "<tr><th></th><th>{lower}</th><th>Budget</th></tr>"
    "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
)
LABELS_TABLE = REPEATED_HEADER_TABLE.format(top="2025", lower="Actual")
LINKED_LABELS_TABLE = REPEATED_HEADER_TABLE.format(top='<a href="#fy2025">2025</a>', lower="Actual")
EQUAL_TABLE = REPEATED_HEADER_TABLE.format(top="2025", lower="2025")
LABELS_HEADER = "| Metric | 2025 — Actual | 2025 — Budget |"
LABELS_HEADER_CELLS = (("Metric", 1), ("2025", 2), ("Actual", 1), ("Budget", 1))


class TestHeaderRecordBinding:
    """R6a: a table's header record comes from the render that supplied element content."""

    @pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
    def test_table_without_links_binds_the_normal_render_record(self, capture_tables):
        parser = Parser(f"<html><body>{LABELS_TABLE}</body></html>", capture_tables=capture_tables)
        pages = parser.get_pages()
        (element,) = pages[0].elements
        table = parser.soup.find("table")
        assert parser._header_records == {id(table): ElementHeaderRecord(
            segment=element.content,
            header_line=LABELS_HEADER,
            header_source=(("2025", 1),),
            header_capacity=(("2025", 2),),
            header_cells=LABELS_HEADER_CELLS,
        )}
        assert element.content.splitlines()[0] == LABELS_HEADER
        assert parser._render_header_records == {}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()

    @pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
    def test_table_with_links_binds_the_anchor_stripped_render_record(self, capture_tables):
        parser = Parser(f"<html><body>{LINKED_LABELS_TABLE}</body></html>", capture_tables=capture_tables)
        pages = parser.get_pages()
        (element,) = pages[0].elements
        table = parser.soup.find("table")
        # The page holds the normal render, with links; the element holds the anchor-stripped
        # re-render, whose record is bound. The normal render's record is discarded.
        assert pages[0].content.splitlines()[0] == (
            "| Metric | [2025](#fy2025) — Actual | [2025](#fy2025) — Budget |"
        )
        assert parser._header_records == {id(table): ElementHeaderRecord(
            segment=element.content,
            header_line=LABELS_HEADER,
            header_source=(("2025", 1),),
            header_capacity=(("2025", 2),),
            header_cells=LABELS_HEADER_CELLS,
        )}
        assert parser._render_header_records == {}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()

    @pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
    def test_element_header_records_returns_the_records_bound_to_an_element(self, capture_tables):
        parser = Parser(f"<html><body>{LABELS_TABLE}</body></html>", capture_tables=capture_tables)
        pages = parser.get_pages()
        (element,) = pages[0].elements
        table = parser.soup.find("table")
        assert parser.element_header_records(element.id) == (parser._header_records[id(table)],)
        assert parser.element_header_records("sec2md-unknown") == ()

    @pytest.mark.parametrize("html, capture_tables", [
        pytest.param(CAT_7_TABLE, False, id="one-row"),
        pytest.param("<table><tr><td>Revenue</td><td>100</td></tr><tr><td>Cost</td><td>40</td></tr></table>",
                     False, id="headerless"),
        pytest.param('<table><tr><td>•</td><td><a href="#p">First point</a></td></tr></table>', False,
                     id="list-table-re-render"),
        pytest.param(LABELS_TABLE.replace("<td>200</td>", "<td><table><tr><td>200</td></tr></table></td>"),
                     True, id="unreliable-capture"),
    ])
    def test_table_without_a_written_header_line_binds_no_record(self, html, capture_tables):
        parser = Parser(f"<html><body>{html}</body></html>", capture_tables=capture_tables)
        parser.get_pages()
        assert parser._header_records == {}
        assert parser.header_accounting_misses == ()

    @pytest.mark.parametrize("wrapper", ["<ul><li>{}</li></ul>", "<b>{}</b>"], ids=["list-item", "bold"])
    @pytest.mark.parametrize("table, ordinary", [
        pytest.param(EQUAL_TABLE, (), id="no-excess"),
        pytest.param(LABELS_TABLE, ("2025",), id="ordinary-excess"),
    ])
    @pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
    def test_table_rendered_inside_other_content_binds_a_wrapped_record(self, capture_tables, table,
                                                                        ordinary, wrapper):
        # Revision 18 (C2): the table's Markdown reaches the element inside a list item or bold
        # run, not as a segment of its own. Its record is bound from the wrapper path, marked
        # wrapped, and returned for the wrapper's element, so its header line is accounted for.
        parser = Parser(f"<html><body>{wrapper.format(table)}</body></html>", capture_tables=capture_tables)
        pages = parser.get_pages()
        (element,) = pages[0].elements
        node = parser.soup.find("table")
        assert "| --- | --- | --- |" in element.content
        (record,) = parser.element_header_records(element.id)
        assert parser._header_records == {id(node): record}
        assert record.wrapped
        assert record.segment in element.content
        assert parser._render_header_records == {}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()
        # Without the record, the ordinary trace is what strict applied before revision 18.
        nodes = parser.block_nodes_map[element.id]
        assert trace_numeric_failures(element, nodes) == tuple(f"{element.id}:{token}" for token in ordinary)

    def test_repeated_parse_resets_header_accounting(self):
        # The wrapped table and its standalone twin share one element: the standalone one is
        # located on its own lines, and the wrapped one's segment occurs twice (ambiguous).
        parser = Parser(f"<html><body><ul><li>{LABELS_TABLE}</li></ul>{LABELS_TABLE}</body></html>")
        first = (parser.get_pages(), parser.header_accounting_misses, parser.trace_numeric_failures)
        (element,) = first[0][0].elements
        wrapper = parser.soup.find("ul")
        wrapped, standalone = parser.soup.find_all("table")
        assert parser._header_records.keys() == {id(wrapped), id(standalone)}
        assert parser._wrapped_tables == {id(wrapper): [wrapped]}
        assert first[1:] == ((f"{element.id}:ambiguous",), (f"{element.id}:2025",))
        second = (parser.get_pages(), parser.header_accounting_misses, parser.trace_numeric_failures)
        assert second[1:] == first[1:]
        assert parser._header_records.keys() == {id(wrapped), id(standalone)}
        assert parser._wrapped_tables == {id(wrapper): [wrapped]}
        assert len(parser._wrapped_renders) == 1


# The final review's case: a period caption spanning two year columns. R6 writes it in both
# columns' header text, so the header line holds "31" twice against one source occurrence.
SPANNING_CAPTION_TABLE = (
    "<table><tr><td></td><td colspan='2'>Year Ended December 31,</td></tr>"
    "<tr><td></td><td>2025</td><td>2024</td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>"
)
SPANNING_CAPTION_HEADER = "|  | Year Ended December 31, — 2025 | Year Ended December 31, — 2024 |"
SPANNING_CAPTION_SEGMENT = f"{SPANNING_CAPTION_HEADER}\n| --- | --- | --- |\n| Revenue | 100 | 90 |"
SPANNING_CAPTION_RECORD = ElementHeaderRecord(
    segment=SPANNING_CAPTION_SEGMENT,
    header_line=SPANNING_CAPTION_HEADER,
    header_source=(("2024", 1), ("2025", 1), ("31", 1)),
    header_capacity=(("2024", 1), ("2025", 1), ("31", 2)),
    header_cells=(("Year Ended December 31,", 2), ("2025", 1), ("2024", 1)),
    wrapped=True,
)

# Revision 18 (C2): each wrapper that renders a table inside other content, as (the HTML around
# the table, the element content before and after the table's segment). The content is pinned
# byte-for-byte as before revision 18: the wrapper shares the header's line and the last row's.
WRAPPED_TABLE_SHAPES = {
    "ul-li": ("<ul><li>{}</li></ul>", "- ", ""),
    "ol-li-with-prose": ("<ol><li>Results: {}</li></ol>", "1. Results: ", ""),
    "b": ("<b>{}</b>", "**", "**"),
    "strong": ("<strong>{}</strong>", "**", "**"),
    "i": ("<i>{}</i>", "*", "*"),
    "em": ("<em>{}</em>", "*", "*"),
    "bold-styled-span": ('<span style="font-weight:700">{}</span>', "**", "**"),
    "italic-styled-span": ('<span style="font-style:italic">{}</span>', "*", "*"),
    "b-div": ("<b><div>{}</div></b>", "**", "**"),
    "b-i": ("<b><i>{}</i></b>", "***", "***"),
    "merged-after-a-bold-run": ("<p><b>Intro</b><b>{}</b></p>", "**Intro ", "**"),
    "merged-before-a-bold-run": ("<p><b>{}</b><b>more</b></p>", "**", " more**"),
    "b-ul-li": ("<b><ul><li>{}</li></ul></b>", "**- ", "**"),
}
CAPTURE_MODES = pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])


def _intro_and(fragment):
    return f"<html><body><p>Intro.</p>{fragment}</body></html>"


def _only_element(parser):
    """Parse with elements; return the single element and its mapped nodes."""
    pages = parser.get_pages()
    (element,) = [element for page in pages for element in page.elements or ()]
    return element, parser.block_nodes_map[element.id]


def _ordinary(element, tokens):
    return tuple(f"{element.id}:{token}" for token in tokens)


class TestWrappedTableHeaderRecords:
    """R6a binds and locates the header record of a table rendered inside other content (rev. 18)."""

    @pytest.mark.parametrize("shape", sorted(WRAPPED_TABLE_SHAPES))
    @CAPTURE_MODES
    def test_wrapped_spanning_caption_binds_its_record_and_passes_strict(self, capture_tables, shape):
        """Revision 18 withdraws revision 17's limitation for wrapped tables.

        R6 repeats the spanning caption's "31" in both year columns against one source
        occurrence. The record, bound from the wrapper path and marked wrapped, locates the
        header line inside the wrapper's content, so the repetition is header capacity, not an
        untraceable number, and strict passes as it does on main.
        """
        html_format, prefix, suffix = WRAPPED_TABLE_SHAPES[shape]
        html = _intro_and(html_format.format(SPANNING_CAPTION_TABLE))
        parser = Parser(html, capture_tables=capture_tables)
        element, _ = _only_element(parser)
        assert element.content == f"Intro.\n\n{prefix}{SPANNING_CAPTION_SEGMENT}{suffix}"
        table = parser.soup.find("table")
        assert parser._header_records == {id(table): SPANNING_CAPTION_RECORD}
        assert parser.element_header_records(element.id) == (SPANNING_CAPTION_RECORD,)
        # The located span is the header line only; the wrapper's prefix stays in the pool.
        start = len(f"Intro.\n\n{prefix}")
        assert locate_header_lines(element.content, [SPANNING_CAPTION_RECORD]) == (
            HeaderLineLocation((start, start + len(SPANNING_CAPTION_HEADER))),
        )
        assert parser._render_header_records == {}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()
        assert parser.diagnostics.warnings == ()
        enforce_quality(parser.diagnostics, "strict")
        if not capture_tables:
            markdown = convert_to_markdown(html, quality_policy="strict")
            assert f"{prefix}{SPANNING_CAPTION_HEADER}" in markdown

    @pytest.mark.parametrize("shape", ["b", "ul-li"])
    @CAPTURE_MODES
    def test_wrapped_table_with_links_binds_the_anchor_stripped_record(self, capture_tables, shape):
        html_format, prefix, suffix = WRAPPED_TABLE_SHAPES[shape]
        parser = Parser(_intro_and(html_format.format(LINKED_LABELS_TABLE)), capture_tables=capture_tables)
        pages = parser.get_pages()
        (element,) = pages[0].elements
        # The page keeps the links; the element holds their labels, as the anchor-stripped
        # re-render writes them. Its record is bound; the normal render's is discarded.
        labels_segment = f"{LABELS_HEADER}\n| --- | --- | --- |\n| Revenue | 100 | 200 |"
        assert pages[0].content == f"Intro.\n\n{prefix}{labels_segment}{suffix}".replace(
            "| 2025 — ", "| [2025](#fy2025) — "
        )
        assert element.content == f"Intro.\n\n{prefix}{labels_segment}{suffix}"
        table = parser.soup.find("table")
        assert parser._header_records == {id(table): ElementHeaderRecord(
            segment=labels_segment,
            header_line=LABELS_HEADER,
            header_source=(("2025", 1),),
            header_capacity=(("2025", 2),),
            header_cells=LABELS_HEADER_CELLS,
            wrapped=True,
        )}
        assert parser._render_header_records == {}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()

    @pytest.mark.parametrize("shape", ["ul-li", "b"])
    @CAPTURE_MODES
    def test_wrapped_table_holding_a_table_outside_every_cell_binds_and_writes_it_once(self, capture_tables,
                                                                                       shape):
        """C1 and C2 together (revision 18): a table placed directly in a body row of a
        wrapped table is read once, in that row, and the wrapped table's record is bound.

        main reads 987 twice and cannot bind the record, so strict reports 31 and 987.
        """
        table = SPANNING_CAPTION_TABLE.replace(
            "<td>90</td></tr></table>", "<td>90</td><table><tr><td>987</td></tr></table></tr></table>")
        html_format, prefix, suffix = WRAPPED_TABLE_SHAPES[shape]
        parser = Parser(_intro_and(html_format.format(table)), capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        header = SPANNING_CAPTION_HEADER + "  |"
        segment = f"{header}\n| --- | --- | --- | --- |\n| Revenue | 100 | 90 | 987 |"
        assert element.content == f"Intro.\n\n{prefix}{segment}{suffix}"
        assert element.content.count("987") == 1
        outer = parser.soup.find("table")
        (record,) = parser.element_header_records(element.id)
        assert parser._header_records == {id(outer): record}
        assert record.wrapped and record.segment == segment and record.header_line == header
        assert record.header_capacity == (("2024", 1), ("2025", 1), ("31", 2))
        assert locate_header_lines(element.content, [record])[0].span is not None
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()
        # Without the record, the ordinary trace reports the caption's repeated 31.
        assert trace_numeric_failures(element, nodes) == (f"{element.id}:31",)
        enforce_quality(parser.diagnostics, "strict")

    @CAPTURE_MODES
    def test_same_table_in_a_div_binds_its_record_and_passes_strict(self, capture_tables):
        html = _intro_and(f"<div>{SPANNING_CAPTION_TABLE}</div>")
        parser = Parser(html, capture_tables=capture_tables)
        parser.get_pages()
        table = parser.soup.find("table")
        (record,) = parser._header_records.values()
        assert record.header_line == SPANNING_CAPTION_HEADER
        assert record.header_capacity == (("2024", 1), ("2025", 1), ("31", 2))
        assert not record.wrapped
        assert parser._header_records.keys() == {id(table)}
        assert parser._wrapped_tables == {}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()
        assert parser.diagnostics.warnings == ()
        if not capture_tables:
            assert SPANNING_CAPTION_HEADER in convert_to_markdown(html, quality_policy="strict")


# The faithful repeated 2025 balances without accounting; repetition over labels does not.
WRAPPED_ASSOCIATION_SOURCES = pytest.mark.parametrize("table, ordinary", [
    pytest.param(EQUAL_TABLE, (), id="no-excess"),
    pytest.param(LABELS_TABLE, ("2025",), id="ordinary-excess"),
])
# A literal "[note" in a cell: link reduction over the wrapper's text can run from it into
# text after the table.
NOTE_TABLE = LABELS_TABLE.replace("<td>Revenue</td>", "<td>Revenue [note</td>")


class TestWrappedTableAssociationMisses:
    """A wrapped record that cannot be associated with its own copy grants no exemption (rev. 18).

    Each miss is recorded, and strict applies exactly the ordinary trace.
    """

    @pytest.mark.parametrize("html_format", [
        pytest.param("<ul><li>{0}</li><li>{0}</li></ul>", id="one-list"),
        pytest.param("<b>{0}{0}</b>", id="one-bold-run"),
    ])
    @WRAPPED_ASSOCIATION_SOURCES
    @CAPTURE_MODES
    def test_identical_tables_in_one_wrapper_are_ambiguous(self, capture_tables, table, ordinary, html_format):
        parser = Parser(f"<html><body>{html_format.format(table)}</body></html>", capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        records = parser.element_header_records(element.id)
        assert len(records) == 2 and all(record.wrapped for record in records)
        assert parser.header_accounting_misses == (f"{element.id}:ambiguous",) * 2
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == _ordinary(element, ordinary) * 2

    @WRAPPED_ASSOCIATION_SOURCES
    @CAPTURE_MODES
    def test_wrapped_table_with_a_standalone_twin_is_ambiguous(self, capture_tables, table, ordinary):
        parser = Parser(f"<html><body><b>{table}</b>{table}</body></html>", capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        wrapped, standalone = parser.soup.find_all("table")
        records = parser.element_header_records(element.id)
        assert records == (parser._header_records[id(wrapped)], parser._header_records[id(standalone)])
        assert [record.wrapped for record in records] == [True, False]
        # The standalone copy occupies whole lines once; the wrapped segment occurs twice.
        locations = locate_header_lines(element.content, records)
        assert [location.miss for location in locations] == ["ambiguous", None]
        assert parser.header_accounting_misses == (f"{element.id}:ambiguous",)
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes, records[1:])
        assert parser.trace_numeric_failures == _ordinary(element, ordinary)

    @pytest.mark.parametrize("html_format, table, damaged", [
        pytest.param("<ul><li>See [note {}</li></ul>", LINKED_LABELS_TABLE,
                     "- See note | Metric | [2025 — Actual |", id="into-the-table-in-a-list-item"),
        pytest.param("<b>See [note {}</b>", LINKED_LABELS_TABLE,
                     "**See note | Metric | [2025 — Actual |", id="into-the-table-in-a-bold-run"),
        pytest.param("<ul><li>{} ](#n) follows</li></ul>", NOTE_TABLE,
                     "| Revenue note | 100 | 200 |  follows", id="out-of-the-table"),
    ])
    @CAPTURE_MODES
    def test_link_reduction_across_the_tables_boundary_is_a_miss(self, capture_tables, html_format, table,
                                                                 damaged):
        parser = Parser(_intro_and(html_format.format(table)), capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        assert damaged in element.content
        node = parser.soup.find("table")
        assert parser._header_records == {}
        assert parser._render_header_records[id(node)][1].header_line is not None
        assert parser.header_accounting_misses == (f"{element.id}:missing",)
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == (f"{element.id}:2025",)

    @pytest.mark.parametrize("shape", ["b", "ul-li"])
    @CAPTURE_MODES
    def test_padded_link_label_is_a_miss(self, capture_tables, shape):
        # The element reduces "[ 2025 ](#fy2025)" to " 2025 "; the anchor-stripped re-render
        # writes "2025", so the wrapper's copy is not the record's segment.
        table = LINKED_LABELS_TABLE.replace(">2025</a>", "> 2025 </a>")
        parser = Parser(_intro_and(WRAPPED_TABLE_SHAPES[shape][0].format(table)), capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        assert "| Metric |  2025  — Actual |  2025  — Budget |" in element.content
        assert parser._header_records == {}
        assert parser.header_accounting_misses == (f"{element.id}:missing",)
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == (f"{element.id}:2025",)

    @CAPTURE_MODES
    def test_padded_link_label_is_never_located_on_a_twin(self, capture_tables):
        # A standalone twin whose literal "[Metric](z)" header reduces to exactly the padded
        # table's anchor-stripped segment (so the twin's own record is missing). The wrapped
        # copy reads " 2025 ", not the record's segment, so the record is a miss; it is never
        # located on the twin.
        table = LINKED_LABELS_TABLE.replace(">2025</a>", "> 2025 </a>")
        twin = LABELS_TABLE.replace("<th>Metric</th>", "<th>[Metric](z)</th>")
        parser = Parser(_intro_and(f"<b>{table}</b>{twin}"), capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        wrapped, standalone = parser.soup.find_all("table")
        labels_segment = f"{LABELS_HEADER}\n| --- | --- | --- |\n| Revenue | 100 | 200 |"
        assert element.content.count(labels_segment) == 1
        assert id(wrapped) not in parser._header_records
        assert parser._header_records[id(standalone)].segment == labels_segment
        records = parser.element_header_records(element.id)
        assert all(location.span is None for location in locate_header_lines(element.content, records))
        assert parser.header_accounting_misses == (f"{element.id}:missing",) * 2
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == (f"{element.id}:2025",) * 2

    @pytest.mark.parametrize("literal", ["[2025](x)", "[2025](#fy2025)"], ids=["other-link", "same-link"])
    @CAPTURE_MODES
    def test_codex_counterexample_a_damaged_copy_is_never_located_on_a_twin(self, capture_tables, literal):
        """Codex's counterexample (spec revision 18).

        Two otherwise identical tables in one list item after "See [note": A's 2025 is an HTML
        link, B's is the literal text "[2025](x)". The wrapper's link reduction runs from
        "[note" into A's header, damaging A's copy, and reduces B's literal text so that B
        reads exactly as A's anchor-stripped segment. A must be a miss, never located on B.
        """
        twin = LINKED_LABELS_TABLE.replace('<a href="#fy2025">2025</a>', literal)
        parser = Parser(_intro_and(f"<ul><li>See [note {LINKED_LABELS_TABLE}{twin}</li></ul>"),
                        capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        first, second = parser.soup.find_all("table")
        labels_segment = f"{LABELS_HEADER}\n| --- | --- | --- |\n| Revenue | 100 | 200 |"
        assert "- See note | Metric | [2025 — Actual |" in element.content
        assert element.content.count(labels_segment) == 1
        assert id(first) not in parser._header_records
        records = parser.element_header_records(element.id)
        assert all(location.span is None for location in locate_header_lines(element.content, records))
        assert parser.header_accounting_misses == (f"{element.id}:missing",) * 2
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == (f"{element.id}:2025",) * 2

    @CAPTURE_MODES
    def test_a_later_merge_that_damages_the_own_copy_is_a_miss(self, capture_tables):
        """The own copy is checked in the wrapper's final segment, not as first appended.

        A later bold run merges into the wrapper's segment, and link reduction over the merged
        text runs from A's literal "[note" out of the table. The element still holds A's
        segment once, as a standalone twin whose literal "[Metric](z)" header reduces to it
        (so the twin's own record is missing). A must be a miss, never located on the twin.
        """
        twin = NOTE_TABLE.replace("<th>Metric</th>", "<th>[Metric](z)</th>")
        parser = Parser(_intro_and(f"<p><b>{NOTE_TABLE}</b><b>](y) more</b></p>{twin}"),
                        capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        wrapped, standalone = parser.soup.find_all("table")
        segment = f"{LABELS_HEADER}\n| --- | --- | --- |\n| Revenue [note | 100 | 200 |"
        assert "| Revenue note | 100 | 200 |  more**" in element.content
        assert element.content.count(segment) == 1
        assert id(wrapped) not in parser._header_records
        assert parser._header_records[id(standalone)].segment == segment
        records = parser.element_header_records(element.id)
        assert all(location.span is None for location in locate_header_lines(element.content, records))
        assert parser.header_accounting_misses == (f"{element.id}:missing",) * 2
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == (f"{element.id}:2025",) * 2

    @pytest.mark.parametrize("html_format, misses", [
        pytest.param("<ul><li>{0} See [note {0}</li></ul>", 2, id="an-identical-table-before-it"),
        pytest.param('<b><img alt="{1}" src="x.png"> See [note {0}</b>', 1, id="its-render-in-an-image-alt"),
    ])
    @CAPTURE_MODES
    def test_every_occurrence_of_the_render_is_checked_not_only_the_first(self, capture_tables, html_format,
                                                                          misses):
        """The table's own copy can be the later occurrence of its render in the wrapper's text.

        The first occurrence is intact: an identical table, or an image alt that holds the
        render verbatim. The own copy comes after "See [note", whose link reduction runs into
        its header. A check of the first occurrence alone would bind the record on the intact
        text; every occurrence is checked, so each table is a miss with the ordinary trace.
        """
        normal_render = f"{LABELS_HEADER}\n| --- | --- | --- |\n| Revenue | 100 | 200 |".replace(
            "| 2025 — ", "| [2025](#fy2025) — ")
        alt = escape(normal_render, quote=True).replace("\n", "&#10;")
        parser = Parser(_intro_and(html_format.format(LINKED_LABELS_TABLE, alt)), capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        assert "See note | Metric | [2025 — Actual |" in element.content
        assert parser._header_records == {}
        assert parser._wrapped_tables == {}
        assert len(parser._render_header_records) == misses
        assert parser.header_accounting_misses == (f"{element.id}:missing",) * misses
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == (f"{element.id}:2025",) * misses

    @CAPTURE_MODES
    def test_a_link_reduction_out_of_the_table_is_a_miss_even_when_it_rebuilds_the_copy(self, capture_tables):
        """The boundary check is not subsumed by the check of the reduced copy.

        The last cell ends in "[[](ab" and the wrapper's text after the table is "c)[](ab |".
        Link reduction over the wrapper's text runs from the cell's first "[" out of the table
        to "c)", and the text after it rebuilds the characters it removed: the element holds
        the record's segment exactly where the own copy's image would be. Only the check that
        no reduction crosses the table's boundary rejects it, so the record is a miss.
        """
        table = LABELS_TABLE.replace("<td>200</td>", "<td>200 [[](ab</td>")
        parser = Parser(_intro_and(f"<b>{table}c)[](ab |</b>"), capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        segment = f"{LABELS_HEADER}\n| --- | --- | --- |\n| Revenue | 100 | 200 [[](ab |"
        assert element.content == f"Intro.\n\n**{segment}**"
        node = parser.soup.find("table")
        assert parser._header_records == {}
        assert parser._render_header_records[id(node)][1].header_line == LABELS_HEADER
        assert parser.header_accounting_misses == (f"{element.id}:missing",)
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes)
        assert parser.trace_numeric_failures == (f"{element.id}:2025",)

    @pytest.mark.parametrize("fragment, header_line, held", [
        # The review's input: the later table's segment replaces the wrapper's, so the wrapped
        # table's text is no longer in the element (a separate, older defect).
        pytest.param(f"<b>{SPANNING_CAPTION_TABLE}</b>"
                     '<table style="display:inline-block"><tr><td>**<a href="#n">note</a></td></tr></table>',
                     SPANNING_CAPTION_HEADER, None, id="the-wrapped-text-is-replaced"),
        # The later table's own text holds the wrapped record's segment at the offset of the
        # wrapper's copy ("**Note " and "| **ab\" are both 7 characters), so the check of the
        # copy's image alone would accept it there.
        pytest.param('<b>Note <table><tr><th>Metric</th><th colspan="2">2025</th></tr>'
                     '<tr style="display:none"><td>hidden</td></tr></table></b>'
                     '<table style="display:inline-block"><tr><th>**ab| Metric</th>'
                     '<th><a href="#n">2025</a></th></tr></table>',
                     "| Metric | 2025 |", "| **ab\\| Metric | 2025 |\n| --- | --- |",
                     id="the-replacement-holds-the-segment"),
    ])
    @CAPTURE_MODES
    def test_a_final_segment_that_is_not_the_wrappers_reduced_text_is_a_miss(self, capture_tables, fragment,
                                                                            header_line, held):
        """A later inline-block table with a link merges into the wrapper's segment.

        The merged segment's content is then that table's anchor-stripped re-render, not the
        link reduction of the wrapper's text, so the wrapper's final segment no longer shows
        where the wrapped table's copy is. The wrapped record is a miss with the ordinary trace,
        never located on the other table's text.
        """
        parser = Parser(_intro_and(f"<div>{fragment}</div>"), capture_tables=capture_tables)
        element, nodes = _only_element(parser)
        if held is not None:
            assert held in element.content
        wrapped = parser.soup.find("b").find("table")
        assert id(wrapped) not in parser._header_records
        assert parser._render_header_records[id(wrapped)][1].header_line == header_line
        assert parser._wrapped_tables == {}
        records = parser.element_header_records(element.id)
        assert not any(record.wrapped for record in records)
        assert parser.header_accounting_misses == (f"{element.id}:missing",)
        assert parser.trace_numeric_failures == trace_numeric_failures(element, nodes, records)


class TestSpacerPreservation:
    """Regression: spacer divs with &nbsp; must not be dropped before table parsing."""

    def test_extract_positioned_children_includes_spacers(self):
        html = """<html><body>
        <div style="position:relative">
            <div style="position:absolute; left:10px; top:10px">Hello</div>
            <div style="position:absolute; display:inline-block; width:5px; left:60px; top:10px">&nbsp;</div>
            <div style="position:absolute; left:70px; top:10px">World</div>
        </div>
        </body></html>"""
        parser = Parser(html)
        container = parser.soup.find("div", style=re.compile("position:relative"))
        children = parser._extract_absolutely_positioned_children(container)
        assert len(children) == 3, f"Expected 3 children (including spacer), got {len(children)}"
