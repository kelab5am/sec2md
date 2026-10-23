"""Inline spacing: text split across adjacent inline nodes joins as the source has it.

Donnelley/ActiveDisclosure filings split words and numbers across adjacent <span>s with
no whitespace between them ("or 2</span><span>0</span>%"). A space is written only where
the source has whitespace at the boundary, or at a block, line-break, table-cell or
footnote-marker boundary.
"""

import pytest

from sec2md.parser import Parser
from sec2md.table_parser import TableParser, extract_cell_text, inline_text
from bs4 import BeautifulSoup

S = '<span style="font-size:10pt;font-family:Arial">'


def _content(body: str) -> str:
    parser = Parser(f"<html><body>{body}</body></html>")
    pages = parser.get_pages(include_elements=False)
    return "\n\n".join(page.content for page in pages)


def _parse(body: str):
    parser = Parser(f"<html><body>{body}</body></html>")
    return parser, parser.get_pages(include_elements=True)


class TestAdjacentSpans:
    def test_digits_split_across_spans_join(self):
        assert _content(f"<p>{S}billion or 2</span>{S}0</span>{S}%, driven</span></p>") == (
            "billion or 20%, driven"
        )

    def test_decimal_split_across_spans_joins(self):
        assert _content(f"<p>{S}valued at $</span>{S}68</span>{S}.7 billion.</span></p>") == (
            "valued at $68.7 billion."
        )

    def test_currency_symbol_joins_the_following_number(self):
        assert _content(f"<p>{S}increased $</span>{S}8.0</span>{S} billion</span></p>") == (
            "increased $8.0 billion"
        )

    def test_year_split_across_spans_joins(self):
        assert _content(f"<p>{S}fiscal year 202</span>{S}3</span>{S}.</span></p>") == (
            "fiscal year 2023."
        )

    def test_word_split_across_spans_joins(self):
        assert _content(
            f"<p>{S}Gross margin </span>{S}in</span>{S}creased $8.0 b</span>{S}illion</span></p>"
        ) == "Gross margin increased $8.0 billion"

    def test_repro_sentence(self):
        body = (
            f"<p>{S}Gross margin </span>{S}in</span>{S}creased $</span>{S}8.0</span>"
            f"{S} billion or 2</span>{S}0</span>{S}%, driven by growth.</span></p>"
        )
        assert _content(body) == "Gross margin increased $8.0 billion or 20%, driven by growth."

    @pytest.mark.parametrize(
        "body",
        [
            f"<p>{S}Gross </span>{S}margin</span></p>",
            f"<p>{S}Gross</span>{S} margin</span></p>",
            f"<p>{S}Gross</span> {S}margin</span></p>",
            f"<p>{S}Gross</span>\n{S}margin</span></p>",
            f"<p>{S}Gross</span>&#160;{S}margin</span></p>",
            f"<p>{S}Gross&#160;</span>{S}margin</span></p>",
            f"<p>{S}Gross</span><span> </span>{S}margin</span></p>",
        ],
    )
    def test_source_whitespace_at_the_boundary_stays_one_space(self, body):
        assert _content(body) == "Gross margin"

    def test_bare_text_and_span_join_without_whitespace(self):
        assert _content(f"<p>or 2{S}0</span>%</p>") == "or 20%"


class TestBoundaries:
    def test_line_break_separates(self):
        assert _content("<p>Gross<br/>margin</p>") == "Gross margin"

    def test_blocks_stay_separate_paragraphs(self):
        assert _content("<div>Gross</div><div>margin</div>") == "Gross\n\nmargin"

    @pytest.mark.parametrize("tag", ["sup", "sub"])
    def test_footnote_marker_stays_separate_from_a_number(self, tag):
        assert _content(f"<p>Revenue was $5.2<{tag}>(1)</{tag}> billion</p>") == (
            "Revenue was $5.2 (1) billion"
        )

    def test_superscript_style_stays_separate_from_a_number(self):
        body = '<p>Revenue was $5.2<span style="vertical-align:super">1</span> billion</p>'
        assert _content(body) == "Revenue was $5.2 1 billion"

    def test_inline_block_box_stays_separate(self):
        body = (
            '<p><span style="display:inline-block;width:20pt">(1)</span>'
            "<span>Represents revenue</span></p>"
        )
        assert _content(body) == "(1) Represents revenue"

    def test_center_block_stays_separate(self):
        assert _content("<center>PART I</center><center>Item 1</center>") == "PART I Item 1"

    def test_gap_made_with_padding_stays_a_space(self):
        # Workiva: "Item 1.<span style="padding-left:...">Business</span>", bullets, notes.
        body = (
            f"<p>{S}Item 1.</span>"
            '<span style="font-size:10pt;padding-left:22.5pt">Business</span></p>'
            f"<p>{S}&#8226;</span>"
            '<span style="font-size:10pt;padding-left:14.85pt">iPad Pro</span></p>'
        )
        assert _content(body) == "Item 1. Business\n\n• iPad Pro"

    def test_zero_padding_does_not_separate(self):
        body = f'<p>{S}2</span><span style="padding-left:0pt">0</span>%</p>'
        assert _content(body) == "20%"

    def test_raised_relative_text_stays_separate(self):
        # Workiva footnote markers: position:relative with a negative top, not <sup>.
        raised = '<span style="font-size:6.5pt;position:relative;top:-3.5pt;vertical-align:baseline">'
        assert _content(f"<p>{S}Depreciation and amortization</span>{raised}(1)</span></p>") == (
            "Depreciation and amortization (1)"
        )
        assert _content(f"<p>{S}was $5.2</span>{raised}1</span>{S} billion</span></p>") == (
            "was $5.2 1 billion"
        )

    def test_relative_text_not_raised_joins(self):
        kerned = '<span style="position:relative;left:-0.5pt">'
        assert _content(f"<p>{S}fiscal 202</span>{kerned}3</span></p>") == "fiscal 2023"

    def test_padding_inside_a_table_cell_stays_a_space(self):
        cell = _cell('<td><span>(1)</span><span style="padding-left:8.24pt">Represents</span></td>')
        assert inline_text(cell) == "(1) Represents"


class TestEmphasis:
    def test_bold_split_mid_word_merges_into_one_word(self):
        assert _content("<p><b>in</b><b>creased</b></p>") == "**increased**"

    def test_bold_with_whitespace_between_merges_with_one_space(self):
        assert _content("<p><b>Net</b> <b>income</b></p>") == "**Net income**"

    def test_bold_with_inner_trailing_whitespace_keeps_the_space(self):
        assert _content("<p><b>Revenue </b>grew 2<span>0</span>%</p>") == "**Revenue** grew 20%"

    def test_text_before_bold_without_whitespace_joins(self):
        assert _content("<p>$<b>68</b>.7 billion</p>") == "$**68**.7 billion"

    def test_digits_inside_a_bold_wrapper_join(self):
        assert _content(f"<p><b>{S}2</span>{S}0</span>%</b> growth</p>") == "**20%** growth"

    def test_italic_split_mid_word_merges(self):
        assert _content("<p><i>in</i><i>creased</i></p>") == "*increased*"

    def test_bold_split_across_parents_merges(self):
        assert _content("<p><span><b>in</b></span><span><b>creased</b></span></p>") == "**increased**"

    def test_different_emphasis_runs_meeting_keep_a_space(self):
        # CRDO: bold-italic "Wafer Fabrication" then italic ":" with no whitespace.
        body = '<p><span style="font-weight:700;font-style:italic">Wafer Fabrication</span><i>:</i> We</p>'
        assert _content(body) == "***Wafer Fabrication*** *:* We"

    def test_bold_runs_meeting_inside_a_wrapper_merge(self):
        assert _content("<p><i><b>in</b><b>creased</b></i></p>") == "***increased***"

    def test_different_runs_meeting_in_the_stream_keep_a_space(self):
        assert _content("<p><span><b>Total</b><i>:</i></span> net</p>") == "**Total** *:* net"

    def test_runs_meeting_in_a_list_item(self):
        body = "<ul><li><b>Total</b><i>:</i> net <b>in</b><b>come</b></li></ul>"
        assert _content(body) == "- **Total** *:* net **income**"


class TestElementsAndChecks:
    def test_element_content_and_citation_join(self):
        parser, pages = _parse(f"<p>{S}grew 2</span>{S}0</span>{S}% to $</span>{S}68</span>{S}.7 billion</span></p>")
        (element,) = pages[0].elements
        assert element.content == "grew 20% to $68.7 billion"
        assert parser.trace_numeric_failures == ()

    def test_numeric_trace_reads_the_source_as_joined(self):
        parser, pages = _parse(
            f"<p>{S}fiscal year 202</span>{S}3 sales rose 1</span>{S}2</span>{S}%</span></p>"
        )
        assert pages[0].elements[0].content == "fiscal year 2023 sales rose 12%"
        assert parser.trace_numeric_failures == ()


def _cell(html: str):
    return BeautifulSoup(f"<table><tr>{html}</tr></table>", "lxml").td


class TestTableCells:
    def test_inline_text_joins_adjacent_spans(self):
        assert inline_text(_cell(f"<td>{S}2</span>{S}0</span>%</td>")) == "20%"

    def test_inline_text_keeps_source_whitespace_and_block_boundaries(self):
        cell = _cell(f"<td>{S}Total </span>{S}net</span><br/>sales<p>(in millions)</p></td>")
        assert inline_text(cell) == "Total net sales (in millions)"

    def test_inline_text_skips_comments(self):
        assert inline_text(_cell("<td>2<!-- x -->0</td>")) == "20"

    def test_inline_text_skips_hidden_text_rather_than_joining_it(self):
        assert inline_text(_cell('<td>100<span style="display:none">999</span></td>')) == "100"

    def test_extract_cell_text_joins_adjacent_spans(self):
        assert extract_cell_text(_cell(f"<td>{S}$</span>{S}68</span>{S}.7</span></td>")) == "$68.7"

    def test_extract_cell_text_keeps_footnote_marker_apart(self):
        assert extract_cell_text(_cell("<td>1,234<sup>(1)</sup></td>")) == "1,234 (1)"

    def test_linked_cell_keeps_footnote_marker_apart(self):
        cell = _cell('<td><a href="#n1">Revenue</a>1,234<sup>(1)</sup></td>')
        assert extract_cell_text(cell) == "[Revenue](#n1)1,234 (1)"

    def test_table_render_joins_split_cell_text(self):
        table = BeautifulSoup(
            "<table>"
            f"<tr><td>{S}Fiscal year</span></td><td>{S}202</span>{S}3</span></td></tr>"
            f"<tr><td>{S}Gross margin in</span>{S}creased</span></td><td>{S}2</span>{S}0</span>%</td></tr>"
            "</table>",
            "lxml",
        ).table
        rendered = TableParser(table).md()
        assert "2023" in rendered
        assert "Gross margin increased" in rendered
        assert "20%" in rendered

    def test_document_table_joins_split_cell_text_without_trace_failures(self):
        parser, pages = _parse(
            "<table>"
            f"<tr><td>{S}Year</span></td><td>{S}202</span>{S}3</span></td></tr>"
            f"<tr><td>{S}Gross margin</span></td><td>{S}2</span>{S}0</span>%</td></tr>"
            "</table>"
        )
        content = pages[0].content
        assert "2023" in content and "20%" in content
        assert "2 0" not in content and "202 3" not in content
        assert parser.trace_numeric_failures == ()

    def test_one_row_table_joins_split_cell_text(self):
        assert _content(f"<table><tr><td>{S}Net sales rose 2</span>{S}0</span>%</td></tr></table>") == (
            "Net sales rose 20%"
        )
