"""Positioned page layouts (spec 2026-10-24-sec2md-positioned-page-layout-design.md).

Workiva's PDF-like pages: a page box of fixed height, line boxes placed by ``top`` and
inline fragments placed by ``left``. Each test names the spec decision it covers.
"""

import re
import warnings

import pytest
from bs4 import BeautifulSoup

from sec2md.parser import Parser
from sec2md.positioned_layout import is_line_box, is_line_fragment, space_between
from sec2md.table_completeness import check_tables, row_structure
from sec2md.table_parser import (
    EXTENDED,
    LEGACY,
    TableParser,
    _marker_class,
    inline_source_text,
    inline_text,
    separates_inline,
)


def page(*children, height=792, style=""):
    # Workiva opens each page with an empty positioned box (TSM: the footer slot).
    slot = f'<div style="position:absolute;top:{height - 100}pt"><div style="width:499pt"></div></div>'
    return (f'<div style="--position:absolute;{style}height:{height}pt;overflow:hidden;'
            f'position:relative;width:612pt">{slot}{"".join(children)}</div>')


def body(*lines):
    """The non-positioned content box of a page, as Workiva writes it."""
    return f"<div>{''.join(lines)}</div>"


def line(top, *fragments, size=11):
    return (f'<div style="line-height:7.63pt;position:absolute;top:{top}pt;width:612pt">'
            + "".join(frag if isinstance(frag, str) and frag.startswith("<") else fragment(*frag, size=size)
                      for frag in fragments) + "</div>")


def fragment(left, text, width=None, bold=False, size=11):
    style = f"font-size:{size}pt;left:{left}pt;position:absolute;white-space:pre"
    if width is not None:
        style += f";width:{width}pt"
    if bold:
        style += ";font-weight:bold"
    return f'<font style="{style}">{text}</font>'


def footer(top, text):
    return (f'<div style="position:absolute;top:{top}pt"><div style="width:499pt">'
            f'{line(24.2, (430, text))}</div></div>')


def parse(html, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = Parser(f"<html><body>{html}</body></html>", **kwargs)
        pages = parser.get_pages(include_elements=False)
    return parser, pages


def content(html):
    return "\n\n".join(p.content for p in parse(html)[1])


# --- D1 ---------------------------------------------------------------------------------

def test_custom_property_is_not_positioning():
    tag = BeautifulSoup('<div style="--position:absolute;position:relative">x</div>', "lxml").div
    assert not Parser._is_absolutely_positioned(tag)
    span = BeautifulSoup('<span style="--position:absolute">x</span>', "lxml").span
    assert not separates_inline(span)


# --- D2 ---------------------------------------------------------------------------------

def test_page_layout_takes_the_flow_path_and_keeps_its_text():
    html = page(body(line(100, (85.5, "Taiwan Semiconductor Manufacturing Company"))))
    assert content(html) == "Taiwan Semiconductor Manufacturing Company"


def px_grid(caption=""):
    # Column-major source order: every label, then each year's column.
    cells = []
    for x, values in ((10, ("Item", "Revenue", "Cost")), (200, ("2026", "100", "70")),
                      (300, ("2025", "90", "60"))):
        for y, value in zip((10, 30, 50), values):
            cells.append(f'<div style="position:absolute;left:{x}px;top:{y}px">{value}</div>')
    return f'<div style="position:relative">{caption}{"".join(cells)}</div>'


def test_measurable_children_keep_the_measured_path():
    expected = content(px_grid())
    assert "| Revenue | 100 | 90 |" in expected and "| Cost | 70 | 60 |" in expected
    # Review finding 3: an unmeasurable caption does not send the grid to the flow path.
    with_caption = content(px_grid("<p>Selected data</p>"))
    assert with_caption == expected


# --- D4 ---------------------------------------------------------------------------------

def test_page_number_footer_becomes_the_display_page_and_is_not_emitted():
    html = page(footer(700, "- 3 -"), body(line(100, (85.5, "First page text")))) + page(
        footer(700, "- 4 -"), body(line(100, (85.5, "Second page text"))))
    _, pages = parse(html)
    assert [(p.content, p.display_page) for p in pages] == [
        ("First page text", 3), ("Second page text", 4)]


@pytest.mark.parametrize("text", ["Debt due within 12", "See Page 3 for details", "1,234", "2026"])
def test_other_footer_zone_text_is_kept_after_the_page_body(text):
    html = page(footer(700, text), body(line(100, (85.5, "Body text"))))
    assert content(html) == f"Body text\n\n{text}"


def test_footer_zone_box_with_a_table_is_kept():
    table = '<div style="position:absolute;top:700pt"><table><tr><td>Page</td><td>7</td></tr></table></div>'
    assert "7" in content(page(table, body(line(100, (85.5, "Body text")))))


def test_each_page_box_starts_a_page_once():
    one = body(line(100, (85.5, "One")))
    two = body(line(100, (85.5, "Two")))
    plain = [p.content for p in parse(page(one) + page(two))[1]]
    after = [p.content for p in parse(page(one, style="page-break-after:always;") + page(two))[1]]
    before = [p.content for p in parse(page(one) + page(two, style="page-break-before:always;"))[1]]
    assert plain == after == before == ["One", "Two"]


def test_nested_page_box_does_not_break():
    inner = page(body(line(10, (85.5, "Inner"))), height=100)
    html = page(body(line(100, (85.5, "Outer"))), inner)
    assert [p.content for p in parse(html)[1]] == ["Outer\n\nInner"]


# --- D5 ---------------------------------------------------------------------------------

def test_lines_at_the_line_pitch_join_into_one_paragraph():
    html = page(body(
        line(100, (85.5, "We have reviewed the accompanying")),
        line(113.2, (85.5, "consolidated balance sheets.")),
        line(139.6, (85.5, "Next paragraph.")),
    ))
    assert content(html) == ("We have reviewed the accompanying consolidated balance sheets."
                             "\n\nNext paragraph.")


def test_bold_heading_line_does_not_run_into_body_text():
    html = page(body(
        line(100, (85.5, "Introduction", None, True)),
        line(113.2, (85.5, "We have reviewed")),
    ))
    assert content(html) == "**Introduction**\n\nWe have reviewed"


def test_line_ending_in_a_hyphen_joins_without_a_space():
    html = page(body(line(100, (85.5, "the Chinese-")), line(113.2, (85.5, "language report"))))
    assert content(html) == "the Chinese-language report"


def test_a_table_between_lines_ends_the_paragraph():
    table = "<table><tr><td>Cash</td><td>100</td></tr><tr><td>Debt</td><td>50</td></tr></table>"
    html = page(body(line(100, (85.5, "Before")), table, line(113.2, (85.5, "After"))))
    text = content(html)
    assert text.startswith("Before\n\n") and text.endswith("\n\nAfter")


# --- D6 ---------------------------------------------------------------------------------

def test_fragments_whose_geometry_touches_join():
    html = page(body(line(100, (85.5, "NT$", 20.0), (105.5, "7,931,592", 40.0))))
    assert content(html) == "NT$7,931,592"


def test_fragments_with_a_measured_gap_get_one_space():
    html = page(body(line(100, (85.5, "a.", 8.0), (104.0, "Initial application", 80.0))))
    assert content(html) == "a. Initial application"


def unmeasured():
    return line(100, (0, "12"), (100, "0"))


def test_fragments_without_widths_are_not_joined_in_body_text():
    assert content(page(body(unmeasured()))) == "12 0"


def test_fragments_without_widths_are_not_joined_in_a_table_cell():
    cell = BeautifulSoup(f"<table><tr><td>{unmeasured()}</td></tr></table>", "lxml").td
    assert inline_text(cell) == "12 0"


def test_fragments_without_widths_are_not_joined_in_a_measured_element():
    soup = BeautifulSoup(
        '<div style="position:absolute;left:10px;top:10px">'
        '<span style="position:absolute;left:0px">12</span><span style="position:absolute;left:100px">0</span>'
        "</div>", "lxml")
    assert inline_text(soup.div) == "12 0"


def test_fragment_with_its_own_top_is_not_a_line_fragment():
    soup = BeautifulSoup(line(100, (0, "12", 8.0), '<font style="left:8pt;position:absolute;top:-3pt">1</font>'),
                         "lxml")
    raised = soup.find_all("font")[1]
    assert is_line_box(soup.div) and not is_line_fragment(raised)
    assert inline_text(soup.div) == "12 1"


def test_nested_positioned_box_still_separates():
    # TSM's "JPY [spacer] 6,095,977": fragments inside a non-positioned wrapper.
    html = line(100, '<font style="white-space:pre"><font style="left:2.63pt;position:absolute">JPY'
                     '<font style="display:inline-block;width:60.38pt"></font></font>'
                     '<font style="left:81.34pt;position:absolute">6,095,977</font></font>')
    assert inline_text(BeautifulSoup(html, "lxml").div) == "JPY 6,095,977"


def test_a_table_cell_reads_like_body_text():
    frags = ((85.5, "Financial assets (Note", 100.0), (185.5, " 7)", 10.0), (200, "x"))
    cell = BeautifulSoup(f"<table><tr><td>{line(0, *frags)}</td></tr></table>", "lxml").td
    assert inline_text(cell) == content(page(body(line(100, *frags)))) == "Financial assets (Note 7) x"


def test_source_text_joins_touching_fragments_like_the_output():
    soup = BeautifulSoup(line(100, (0, "2", 6.0), (6, "0", 6.0), (100, "%")), "lxml")
    fonts = soup.find_all("font")
    assert inline_source_text(fonts) == "20 %"
    assert space_between(fonts[1], fonts[2]) and not space_between(fonts[0], fonts[1])


# --- D7 ---------------------------------------------------------------------------------

def report(html):
    return parse(html)[0].table_report


def test_check_reads_separately_positioned_boxes_as_separate_tokens():
    jpy = line(2.76, '<font style="white-space:pre"><font style="left:2.63pt;position:absolute">JPY'
                     '<font style="display:inline-block;width:60.38pt"></font></font>'
                     '<font style="left:81.34pt;position:absolute">6,095,977</font></font>')
    html = (f"<table><tr><td>Currency</td><td>Amount</td></tr>"
            f"<tr><td>Sell JPY</td><td>{jpy}</td></tr><tr><td>Sell USD</td><td>1,000</td></tr></table>")
    result = report(html)
    assert result.failures == () and result.reported == ()


def test_check_counts_identifiers_in_header_lines():
    html = ("<table><tr><th>No.</th><th>Limit (Note 1)</th><th>Maximum (Notes 1 and 2)</th></tr>"
            "<tr><td>0</td><td>2,573</td><td>2,656</td></tr>"
            "<tr><td>1</td><td>2,574</td><td>2,657</td></tr></table>")
    result = report(html)
    assert result.failures == () and result.reported == ()


@pytest.mark.parametrize("label", ["Cash (Note 6)", "Cash Note 6"])
def test_check_two_reads_identifiers_on_both_sides(label):
    # Source rows carry the identifier's 6 (classify_cell); so must the output line, though
    # numbers() drops a parenthesized "(Note 6)" (D7.3, revision 4).
    segment = f"|  | 2026 | 2025 |\n| --- | --- | --- |\n| {label} | 100 | 6 |\n| Debt | 6 | 7 |"
    assert row_structure([("6", "100", "6"), ("6", "7")], segment) == []
    html = (f"<table><tr><td></td><td>2026</td><td>2025</td></tr><tr><td>{label}</td><td>100</td>"
            "<td>6</td></tr><tr><td>Debt</td><td>6</td><td>7</td></tr></table>")
    assert report(html).structure == ()


FOOTNOTED = ("<table><tr><td></td><td>2026</td><td></td><td>YoY</td><td></td></tr>"
             "<tr><td>Revenue</td><td>247,652</td><td></td><td>9</td><td>%</td></tr>"
             "<tr><td>Adjusted EBITDA</td><td>45,735</td><td></td><td>(14</td><td>)%<sup>(3)</sup></td></tr>"
             "<tr><td>Net income</td><td>42,382</td><td></td><td>(75</td><td>)%<sup>(4)</sup></td></tr></table>")


def footnoted_check(outputs):
    soup = BeautifulSoup(FOOTNOTED, "lxml")
    table = soup.find("table")
    return check_tables(soup, {id(table): outputs}, {}, {})


def test_check_matches_a_footnote_after_a_merged_negative():
    merged = ("|  | 2026 | YoY |\n| --- | --- | --- |\n| Revenue | 247,652 | 9 % |\n"
              "| Adjusted EBITDA | 45,735 | (14)% (3) |\n| Net income | 42,382 | (75)% (4) |")
    result = footnoted_check(merged)
    assert result.failures == () and result.reported == ()
    # A mutation that drops a reference is still reported.
    assert footnoted_check(merged.replace("(14)% (3)", "(14)%")).reported


def test_check_matches_a_footnote_left_unmerged():
    # The footnote matches either way (D7.4). The unmerged negatives themselves are what D8's
    # merge fixes, and the check still reports them.
    unmerged = ("|  | 2026 | YoY |  |\n| --- | --- | --- | --- |\n| Revenue | 247,652 | 9 | % |\n"
                "| Adjusted EBITDA | 45,735 | (14 | )% (3) |\n| Net income | 42,382 | (75 | )% (4) |")
    result = footnoted_check(unmerged)
    assert result.reported == ()
    assert len(result.failures) == 1 and "-14" in result.failures[0]


# --- D8 ---------------------------------------------------------------------------------

def markdown(table_html):
    return TableParser(BeautifulSoup(table_html, "lxml").find("table")).md().strip()


def test_footnoted_close_marker_merges_into_its_value():
    out = markdown(FOOTNOTED)
    assert "| (14)% (3) |" in out and "| (75)% (4) |" in out and "| 9 % |" in out
    assert ")%" not in out.replace("(14)%", "").replace("(75)%", "")


def test_mixed_close_column_with_a_row_that_does_not_validate_stays_unmerged():
    broken = FOOTNOTED.replace("<td>(75</td>", "<td>n/a</td>")
    out = markdown(broken)
    assert "(14)%" not in out and re.search(r"\| \(14 \| \)% \(3\) \|", out)


def test_legacy_policy_is_unchanged():
    assert _marker_class(")% (3)", policy=LEGACY) is None
    assert _marker_class(")% (3)", policy=EXTENDED) == "close_paren"
    assert TableParser._join_structural_text([], "(14", [")% (3)"], policy=LEGACY) == "(14 )% (3)"
    assert TableParser._join_structural_text([], "(14", [")% (3)"], policy=EXTENDED) == "(14)% (3)"


# --- HTML comments (spec 2026-10-24-sec2md-html-comments-design.md) ----------------------

@pytest.mark.parametrize("comment", ["<!---->", "<!-- c -->", "<!-- c --><!-- d -->"])
def test_a_comment_between_fragments_does_not_change_their_spacing(comment):
    touching = page(body(line(100, (85.5, "2", 6.0), comment, (91.5, "0", 6.0))))
    apart = page(body(line(100, (85.5, "2", 6.0), comment, (104.0, "0", 6.0))))
    assert content(touching) == "20"
    assert content(apart) == "2 0"


def test_a_comment_in_a_bold_line_does_not_end_the_paragraph():
    plain = page(body(line(100, (85.5, "First", None, True)), line(113.2, (85.5, "Second", None, True))))
    commented = page(body(
        line(100, "<!-- c -->", (85.5, "First", None, True)),
        line(113.2, (85.5, "Second", None, True)),
    ))
    assert content(plain) == content(commented)
    assert "\n\n" not in content(commented)
