"""Tests for the HTML parser (parser.py)."""

import re

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
from sec2md.quality import ElementHeaderRecord, ParseQualityError, enforce_quality


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
        )}
        assert parser._render_header_records == {}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()

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
    def test_table_rendered_inside_other_content_is_a_missing_association(self, capture_tables, table,
                                                                         ordinary, wrapper):
        # The table's Markdown reaches the element inside a list item or bold run, not as a
        # segment of its own, so its header line cannot be located.
        parser = Parser(f"<html><body>{wrapper.format(table)}</body></html>", capture_tables=capture_tables)
        pages = parser.get_pages()
        (element,) = pages[0].elements
        assert "| --- | --- | --- |" in element.content
        assert parser._header_records == {}
        assert parser.header_accounting_misses == (f"{element.id}:missing",)
        assert parser.trace_numeric_failures == tuple(f"{element.id}:{token}" for token in ordinary)

    def test_repeated_parse_resets_header_accounting(self):
        parser = Parser(f"<html><body><ul><li>{LABELS_TABLE}</li></ul>{LABELS_TABLE}</body></html>")
        first = (parser.get_pages(), parser.header_accounting_misses, parser.trace_numeric_failures)
        assert len(parser._header_records) == 1 and len(first[1]) == 1
        second = (parser.get_pages(), parser.header_accounting_misses, parser.trace_numeric_failures)
        assert second[1:] == first[1:]
        assert len(parser._header_records) == 1


# The final review's case: a period caption spanning two year columns. R6 writes it in both
# columns' header text, so the header line holds "31" twice against one source occurrence.
SPANNING_CAPTION_TABLE = (
    "<table><tr><td></td><td colspan='2'>Year Ended December 31,</td></tr>"
    "<tr><td></td><td>2025</td><td>2024</td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>"
)
SPANNING_CAPTION_HEADER = "|  | Year Ended December 31, — 2025 | Year Ended December 31, — 2024 |"


def _intro_and(fragment):
    return f"<html><body><p>Intro.</p>{fragment}</body></html>"


class TestWrappedTableHeaderLimitation:
    """R6a cannot locate the header line of a table rendered inside other content."""

    @pytest.mark.parametrize("wrapper", [
        pytest.param("<ol><li>Results: {}</li></ol>", id="list-item"),
        pytest.param("<b>{}</b>", id="bold"),
        pytest.param("<em>{}</em>", id="italic"),
        pytest.param('<span style="font-weight:700">{}</span>', id="bold-styled-span"),
    ])
    @pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
    def test_wrapped_spanning_caption_fails_strict_known_limitation(self, capture_tables, wrapper):
        """Known limitation (spec revision 17, accepted 2026-10-06); binding records for wrapped
        tables is a follow-up task.

        A table rendered inside a list item or a bold or italic run reaches the element inside
        that content, not as a segment of its own, so R6a records a miss and strict applies the
        ordinary trace. R6 repeats the spanning caption's "31" in both year columns against one
        source occurrence, so default strict raises where main passes (main wrote the caption
        once). The same table in a <div> passes (next test).
        """
        html = _intro_and(wrapper.format(SPANNING_CAPTION_TABLE))
        parser = Parser(html, capture_tables=capture_tables)
        pages = parser.get_pages()
        (element,) = pages[0].elements
        message = f"untraceable normalized number: {element.id}:31"
        with pytest.raises(ParseQualityError) as caught:
            enforce_quality(parser.diagnostics, "strict")
        assert str(caught.value) == message
        if not capture_tables:
            with pytest.raises(ParseQualityError) as caught:
                convert_to_markdown(html, quality_policy="strict")
            assert str(caught.value) == message
        assert SPANNING_CAPTION_HEADER in element.content
        assert parser._header_records == {}
        assert parser.header_accounting_misses == (f"{element.id}:missing",)
        assert parser.trace_numeric_failures == (f"{element.id}:31",)

    @pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
    def test_same_table_in_a_div_binds_its_record_and_passes_strict(self, capture_tables):
        html = _intro_and(f"<div>{SPANNING_CAPTION_TABLE}</div>")
        parser = Parser(html, capture_tables=capture_tables)
        parser.get_pages()
        table = parser.soup.find("table")
        (record,) = parser._header_records.values()
        assert record.header_line == SPANNING_CAPTION_HEADER
        assert record.header_capacity == (("2024", 1), ("2025", 1), ("31", 2))
        assert parser._header_records.keys() == {id(table)}
        assert parser.header_accounting_misses == ()
        assert parser.trace_numeric_failures == ()
        assert parser.diagnostics.warnings == ()
        if not capture_tables:
            assert SPANNING_CAPTION_HEADER in convert_to_markdown(html, quality_policy="strict")


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
