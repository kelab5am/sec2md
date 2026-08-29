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
from sec2md.models import Element, Page
from sec2md.parser import Parser


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
