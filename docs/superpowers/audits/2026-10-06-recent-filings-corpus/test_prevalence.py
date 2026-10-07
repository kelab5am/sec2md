"""Offline tests for prevalence.py (Task 5 of the recent filings corpus plan).

    pytest docs/superpowers/audits/2026-10-06-recent-filings-corpus/test_prevalence.py

Each detector gets a positive and a negative synthetic document. The positives are the
branch's own limitation-test inputs, copied (not imported) from the tmh-proto worktree at
1252c45:
- tests/test_parser.py, TestWrappedTableHeaderLimitation (SPANNING_CAPTION_TABLE, its four
  wrappers and _intro_and);
- tests/test_table_merge_headers.py, test_zero_width_inside_a_number_is_a_known_strict_limitation
  and the tr-direct and div-wrapped cases of
  test_header_record_reads_each_cell_of_a_table_nested_in_a_header_row_once;
- tests/test_table_merge_headers.py, SUB_LABEL_CODE_ROWS (the `Forward contracts` rows) and _html;
- tests/test_section_extractor.py, RUNNING_PART_HEADER_DOCUMENT.

The detectors and their effects run on the branch's sec2md: the worktree's src, or TMH_SRC.
pytest's `pythonpath = ["src"]` puts the main checkout's src on the path first, so this module
puts the branch's src before it and checks where sec2md came from.
"""
from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
BRANCH_SRC = os.path.abspath(os.environ.get("TMH_SRC")
                             or os.path.join(ROOT, ".worktrees", "tmh-proto", "src"))
if not os.path.isdir(os.path.join(BRANCH_SRC, "sec2md")):
    pytest.skip(f"no branch sec2md under {BRANCH_SRC}", allow_module_level=True)
sys.path.insert(0, BRANCH_SRC)
sys.path.insert(0, HERE)

import sec2md  # noqa: E402

if not os.path.normcase(os.path.abspath(sec2md.__file__)).startswith(
        os.path.normcase(BRANCH_SRC) + os.sep):
    raise ImportError(f"sec2md came from {sec2md.__file__}, not from {BRANCH_SRC}: run this file "
                      "in its own pytest session")

import prevalence as pv  # noqa: E402

DETECTORS = ("wrapped_table", "zero_width_number", "header_row_table", "sub_label_currency",
             "page_top_part_table")


def _only(result, detector):
    """The detector's occurrences, after checking that no other detector fired."""
    assert {name: occurrences for name, occurrences in result.items()
            if name != detector and occurrences} == {}
    return result[detector]


# --- wrapped_table (tests/test_parser.py, TestWrappedTableHeaderLimitation) ---------------

SPANNING_CAPTION_TABLE = (
    "<table><tr><td></td><td colspan='2'>Year Ended December 31,</td></tr>"
    "<tr><td></td><td>2025</td><td>2024</td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>"
)


def _intro_and(fragment):
    return f"<html><body><p>Intro.</p>{fragment}</body></html>"


@pytest.mark.parametrize("wrapper", [
    pytest.param("<ol><li>Results: {}</li></ol>", id="list-item"),
    pytest.param("<b>{}</b>", id="bold"),
    pytest.param("<em>{}</em>", id="italic"),
    pytest.param('<span style="font-weight:700">{}</span>', id="bold-styled-span"),
])
def test_wrapped_table_is_found_and_has_a_missing_header_record(wrapper):
    (occurrence,) = _only(pv.analyse(_intro_and(wrapper.format(SPANNING_CAPTION_TABLE))),
                          "wrapped_table")
    assert occurrence["table"] == 1
    assert occurrence["affected"] is True
    assert occurrence["misses"] == ["missing"]
    assert occurrence["trace_failures"] == ["31"]


def test_same_table_in_a_div_is_not_a_wrapped_table():
    result = pv.analyse(_intro_and(f"<div>{SPANNING_CAPTION_TABLE}</div>"))
    assert {name: occurrences for name, occurrences in result.items() if occurrences} == {}


# --- zero_width_number (tests/test_table_merge_headers.py) --------------------------------

@pytest.mark.parametrize(
    ("amount", "token"),
    [
        ("1,2\u200b34", "1234"),
        ("12\u200c345", "12345"),
        ("(1,234\u200b)", "-1234"),
    ],
    ids=["u200b_in_thousands", "u200c_in_digits", "u200b_before_close_paren"],
)
def test_zero_width_inside_a_number_is_found_and_strict_reports_the_joined_token(amount, token):
    html = (
        "<html><body><p>Operating results for the year.</p><table>"
        "<tr><th>Item</th><th>2025</th></tr>"
        f"<tr><td>Revenue</td><td>{amount}</td></tr>"
        "<tr><td>Costs</td><td>567</td></tr></table></body></html>"
    )
    (occurrence,) = _only(pv.analyse(html), "zero_width_number")
    assert occurrence["table"] == 1
    assert occurrence["joined"] == [token]
    assert occurrence["affected"] is True
    assert occurrence["failures"] == [token]


def test_zero_width_cells_beside_an_amount_are_not_a_split_number():
    # tests/test_table_merge_headers.py test_zero_width_cell_beside_an_amount, plus a label.
    html = (
        "<html><body>"
        '<table><tr><td></td><td colspan="3">2025</td></tr>'
        "<tr><td>Revenue\u200b</td><td>$</td><td>1,234</td><td>\u200b</td></tr>"
        "<tr><td>Costs</td><td>\u200b</td><td>567</td><td>\u200b</td></tr></table>"
        "</body></html>"
    )
    result = pv.analyse(html)
    assert {name: occurrences for name, occurrences in result.items() if occurrences} == {}


def _amount_table(amount, header="2025"):
    return ("<html><body><p>Operating results for the year.</p><table>"
            f"<tr><th>Item</th><th>{header}</th></tr>"
            f"<tr><td>Revenue</td><td>{amount}</td></tr>"
            "<tr><td>Costs</td><td>567</td></tr></table></body></html>")


@pytest.mark.parametrize("sign", ["-", "\u2212"], ids=["hyphen-minus", "minus-sign"])
def test_zero_width_between_a_sign_and_its_digits_is_found(sign):
    # Fix round 1 (I3a): the render joins "-1,234"; strict's source pool holds 1,234 alone.
    (occurrence,) = _only(pv.analyse(_amount_table(f"{sign}\u200b1,234")), "zero_width_number")
    assert occurrence["joined"] == ["-1234"]
    assert occurrence["affected"] is True
    assert occurrence["failures"] == ["-1234"]


def test_zero_width_after_a_range_dash_is_not_a_split_number():
    # Fix round 2: a dash after a digit is a range dash, not a sign.
    result = pv.analyse(_amount_table("1,234", header="2023-\u200b2024"))
    assert result["zero_width_number"] == []


def test_zero_width_inside_a_header_number_is_affected_as_a_header_excess():
    # Fix round 1 (I3b): strict reports the joined header number as "header:2025".
    (occurrence,) = _only(pv.analyse(_amount_table("1,234", header="20\u200b25")), "zero_width_number")
    assert occurrence["joined"] == ["2025"]
    assert occurrence["affected"] is True
    assert occurrence["failures"] == ["header:2025"]


# --- header_row_table (tests/test_table_merge_headers.py, tr-direct) ----------------------

@pytest.mark.parametrize("nested", [
    "<table><tr><th>Fiscal</th><th>2024</th></tr></table>",
    "<div><table><tr><th>Fiscal</th><th>2024</th></tr></table></div>",
], ids=["tr-direct", "div-wrapped"])
def test_table_in_a_header_row_is_found_and_strict_reports_a_header_excess(nested):
    html = (f"<html><body><table><tr><th>Item</th><th>Period</th>{nested}</tr>"
            "<tr><td>Revenue</td><td>100</td></tr></table></body></html>")
    (occurrence,) = _only(pv.analyse(html), "header_row_table")
    assert occurrence["table"] == 1
    assert occurrence["affected"] is True
    assert occurrence["header_failures"] == ["header:2024"]


@pytest.mark.parametrize("html", [
    # A cell between them: tests/test_quality.py's table nested in a header cell.
    "<html><body><table><tr><th>Item</th><th>Period<table><tr><th>Fiscal</th><th>2024</th></tr>"
    "</table></th></tr><tr><td>Revenue</td><td>100</td></tr></table></body></html>",
    # The same nested table in a body row.
    "<html><body><table><tr><th>Item</th><th>2025</th></tr><tr><td>Revenue</td><td>100</td>"
    "<table><tr><td>Fiscal</td><td>2024</td></tr></table></tr></table></body></html>",
], ids=["in-a-header-cell", "in-a-body-row"])
def test_table_in_a_header_cell_or_a_body_row_is_not_a_header_row_table(html):
    assert pv.analyse(html)["header_row_table"] == []


# --- sub_label_currency (tests/test_table_merge_headers.py, Forward contracts) ------------

SUB_LABEL_CODE_ROWS = [
    ["", "", "2025", "2024"],
    ["Forward contracts", "", "", ""],
    ["", "EUR", "1,234", "987"],
    ["", "JPY", "456", "789"],
]


def _html(rows, header_tag="td"):
    """A table whose first row uses header_tag, one cell per text and no spans."""
    body = []
    for index, row in enumerate(rows):
        tag = header_tag if index == 0 else "td"
        body.append("<tr>" + "".join(f"<{tag}>{text}</{tag}>" for text in row) + "</tr>")
    return "<table>" + "".join(body) + "</table>"


def test_sub_label_currency_codes_are_found_and_joined_to_their_amounts():
    html = f"<html><body><p>Notional amounts.</p>{_html(SUB_LABEL_CODE_ROWS)}</body></html>"
    (occurrence,) = _only(pv.analyse(html), "sub_label_currency")
    assert occurrence["table"] == 1
    assert occurrence["codes"] == ["EUR", "JPY"]
    assert occurrence["rows"] == 2
    assert occurrence["joined"] == ["EUR 1,234", "JPY 456"]
    assert occurrence["affected"] is True


def test_marker_column_beside_code_labels_is_not_a_sub_label_column():
    # tests/test_table_merge_headers.py CURRENCY_LABEL_TABLES "marker-column-beside-code-labels":
    # the codes are R0's label column, and the column beside it holds symbols, which R4 joins.
    html = ("<html><body><table><tr><th></th><th></th><th>2025</th></tr>"
            "<tr><td>EUR</td><td>€</td><td>1,234</td></tr>"
            "<tr><td>GBP</td><td>£</td><td>987</td></tr></table></body></html>")
    assert pv.analyse(html)["sub_label_currency"] == []


def test_currency_codes_are_the_letter_and_x_dollar_codes_of_the_closed_list():
    # Fix round 1 (I1): US$, HK$, NT$, A$, C$ and S$ are codes; bare symbols stay out.
    codes = pv._currency_codes()
    assert {"US$", "HK$", "NT$", "A$", "C$", "S$", "EUR", "RMB"} <= codes
    assert codes.isdisjoint({"$", "€", "£", "¥"})
    assert len(codes) == 23


# Fix round 1 (I1): BABA-20-F-2026-05-20.htm table 39 (directors' grants), trimmed to five of its
# rows and its two header rows, with the source's column layout: the per-row US$ / HK$ codes stand
# in the column beside Name, before the exercise price.
BABA_39_TABLE = (
    "<table>"
    "<tr><td>Name</td><td colspan='2'>Exercise price per RSU/ option granted</td>"
    "<td colspan='4'>Shares underlying outstanding RSUs/ options granted (1)</td>"
    "<td>Date of grant</td><td>Date of expiration</td></tr>"
    "<tr><td></td><td colspan='2'></td><td colspan='2'>(in the number of Shares)</td>"
    "<td colspan='2'>(in the number of ADSs)</td><td></td><td></td></tr>"
    "<tr><td>Eddie Yongming WU</td><td></td><td>-</td><td></td><td>1,240,000</td><td></td>"
    "<td>155,000</td><td>November 25, 2023 to May 23, 2025</td><td>November 25, 2030 to May 23, 2033</td></tr>"
    "<tr><td></td><td>US$</td><td>78.37</td><td></td><td>16,000,000</td><td></td><td>2,000,000</td>"
    "<td>November 25, 2023</td><td>November 25, 2033</td></tr>"
    "<tr><td></td><td>HK$</td><td>116.70</td><td></td><td>12,000,000</td><td></td><td>1,500,000</td>"
    "<td>November 26, 2025</td><td>November 26, 2035</td></tr>"
    "<tr><td>J. Michael EVANS</td><td>US$</td><td>79.96</td><td></td><td>8,000,000</td><td></td>"
    "<td>1,000,000</td><td>July 31, 2015</td><td>July 31, 2027</td></tr>"
    "<tr><td>Jane Fang JIANG</td><td></td><td>-</td><td></td><td>167,217</td><td></td><td>20,902</td>"
    "<td>May 24, 2021 to May 23, 2025</td><td>May 24, 2029 to May 23, 2033</td></tr>"
    "</table>"
)


def test_x_dollar_codes_beside_the_label_column_are_found_and_joined():
    (occurrence,) = _only(pv.analyse(f"<html><body><p>Context.</p>{BABA_39_TABLE}</body></html>"),
                          "sub_label_currency")
    assert occurrence["codes"] == ["HK$", "US$"]
    assert occurrence["rows"] == 3
    assert occurrence["joined"] == ["US$ 78.37", "HK$ 116.70", "US$ 79.96"]
    assert occurrence["column"] == 1
    assert occurrence["affected"] is True


# Fix round 2: TSM-20-F-2023-04-20.htm table 278 (forward exchange contracts), trimmed to its
# header rows and its 2022 section: the label, a Maturity Date text column, then the per-row
# codes, then the amounts. The code column is not next to the label column.
TSM_278_TABLE = (
    "<table>"
    "<tr><td></td><td></td><td colspan='2'>Contract Amount</td></tr>"
    "<tr><td></td><td>Maturity Date</td><td colspan='2'>(In Millions)</td></tr>"
    "<tr><td>December 31, 2022</td><td></td><td></td><td></td></tr>"
    "<tr><td>Sell NT$</td><td>January 2023 to March 2023</td><td>NT$</td><td>79,610.6</td></tr>"
    "<tr><td>Sell US$</td><td>January 2023 to March 2023</td><td>US$</td><td>752.5</td></tr>"
    "<tr><td>Sell RMB</td><td>January 2023 to March 2023</td><td>RMB</td><td>1,448.4</td></tr>"
    "</table>"
)


def test_codes_in_a_body_column_after_a_text_column_are_found_and_joined():
    (occurrence,) = _only(pv.analyse(f"<html><body><p>Context.</p>{TSM_278_TABLE}</body></html>"),
                          "sub_label_currency")
    assert occurrence["column"] == 2
    assert occurrence["codes"] == ["NT$", "RMB", "US$"]
    assert occurrence["rows"] == 3
    assert occurrence["joined"] == ["NT$ 79,610.6", "US$ 752.5", "RMB 1,448.4"]
    assert occurrence["affected"] is True


# --- page_top_part_table (tests/test_section_extractor.py) --------------------------------

RUNNING_PART_HEADER = "<table><tr><td>Part II</td><td>Annual Report 2024</td></tr></table><p>Item 7</p>"
RUNNING_PART_BODY = "Revenue increased because of higher demand across every segment we report on. " * 3
RUNNING_PART_HEADER_DOCUMENT = f"""<html><body>
<div style="page-break-after:always">
<p><b>PART II</b></p>
<p><b>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</b></p>
<p>{RUNNING_PART_BODY} Page one.</p>
</div>
<div style="page-break-after:always">
{RUNNING_PART_HEADER}
<p>{RUNNING_PART_BODY} Page two.</p>
</div>
<div>
{RUNNING_PART_HEADER}
<p>{RUNNING_PART_BODY} Page three.</p>
<p><b>Item 8. Financial Statements and Supplementary Data</b></p>
<p>{RUNNING_PART_BODY} Item eight.</p>
</div>
</body></html>"""


def test_running_part_header_tables_are_found_and_change_the_sections():
    occurrences = _only(pv.analyse(RUNNING_PART_HEADER_DOCUMENT), "page_top_part_table")
    assert [(o["table"], o["page"], o["line"]) for o in occurrences] == [
        (1, 2, "PART II Annual Report 2024"), (2, 3, "PART II Annual Report 2024")]
    assert all(o["affected"] for o in occurrences)
    assert "10-K" in occurrences[0]["sections_differ"]


def test_part_table_below_text_on_its_page_is_not_at_the_page_top():
    # The running header of the positive case, after text on page 2 and without the page-3 copy.
    html = RUNNING_PART_HEADER_DOCUMENT.replace(
        f"\n{RUNNING_PART_HEADER}\n<p>{RUNNING_PART_BODY} Page two.</p>",
        f"\n<p>{RUNNING_PART_BODY} Page two.</p>\n{RUNNING_PART_HEADER}",
    ).replace(f"{RUNNING_PART_HEADER}\n<p>{RUNNING_PART_BODY} Page three.</p>",
              f"<p>{RUNNING_PART_BODY} Page three.</p>")
    assert html.count("Annual Report 2024") == 1
    assert pv.analyse(html)["page_top_part_table"] == []


def _page_break_then(top):
    """Page 1 ends with an empty page-break div; page 2 opens with top, then a bare Item 7."""
    return f"""<html><body>
<p><b>PART II</b></p>
<p><b>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</b></p>
<p>{RUNNING_PART_BODY} Page one.</p>
<div style="page-break-after:always"></div>
{top}
<p>Item 7</p>
<p>{RUNNING_PART_BODY} Page two.</p>
<p><b>Item 8. Financial Statements and Supplementary Data</b></p>
<p>{RUNNING_PART_BODY} Item eight.</p>
</body></html>"""


PART_TABLE = "<table><tr><td>Part II</td><td>Annual Report 2024</td></tr></table>"


@pytest.mark.parametrize("wrapper", [
    pytest.param("<b>{}</b>", id="bold"),
    pytest.param('<span style="font-weight:bold">{}</span>', id="bold-styled-span"),
])
def test_part_table_in_an_inline_wrapper_at_the_page_top_is_found(wrapper):
    # Fix round 1 (I2): the page's first segment is the wrapper's, not the table's.
    (occurrence,) = _only(pv.analyse(_page_break_then(wrapper.format(PART_TABLE))),
                          "page_top_part_table")
    assert (occurrence["table"], occurrence["page"], occurrence["line"]) == (
        1, 2, "PART II Annual Report 2024")
    assert occurrence["affected"] is True


def test_wrapped_part_table_below_text_on_its_page_is_not_at_the_page_top():
    context = {}
    html = _page_break_then(f"<p>{RUNNING_PART_BODY}</p><b>{PART_TABLE}</b>")
    assert pv.analyse(html, context)["page_top_part_table"] == []
    assert (context["near"]["part_page_unknown"], context["near"]["part_not_first"]) == (1, 0)


# --- the record ---------------------------------------------------------------------------

def test_context_counts_near_misses_and_the_branch_effects():
    context = {}
    pv.analyse(_intro_and(f"<b>{SPANNING_CAPTION_TABLE}</b><b><table><tr><td>A</td><td>1</td></tr>"
                          "</table></b>"), context)
    assert context["near"]["wrapped_any"] == 2
    assert context["near"]["wrapped_one_row"] == 1
    assert {key: context["branch"][key] for key in ("trace_failures", "header_failures", "missing")} == {
        "trace_failures": 1, "header_failures": 0, "missing": 1}

    context = {}
    pv.analyse("<html><body><table><tr><th>Item</th><th>2025</th></tr><tr><td>Revenue</td><td>100</td>"
               "<table><tr><td>Fiscal</td><td>2024</td></tr></table></tr></table></body></html>", context)
    assert (context["near"]["nested_tables"], context["near"]["nested_in_row"]) == (1, 1)

    context = {}
    pv.analyse(f"<html><body><p>{RUNNING_PART_BODY}</p>{RUNNING_PART_HEADER}</body></html>", context)
    assert {key: context["near"][key] for key in ("part_one_row", "part_with_cells", "part_not_first",
                                                  "part_page_unknown")} == {
        "part_one_row": 1, "part_with_cells": 1, "part_not_first": 1, "part_page_unknown": 0}

    context = {}
    pv.analyse("<html><body><span style='font-weight: bold'>"
               f"{SPANNING_CAPTION_TABLE}</span></body></html>", context)
    assert context["near"]["styled_not_read"] == 1
    assert context["branch"]["missing"] == 0


def test_context_lists_every_near_miss_counter_even_at_zero():
    # Fix round 1 (M1).
    context = {}
    pv.analyse("<html><body><p>No tables.</p></body></html>", context)
    assert tuple(context["near"]) == tuple(sorted(pv.NEAR_KEYS))
    assert set(context["near"].values()) == {0}


def test_summary_counts_documents_tables_occurrences_and_affected():
    records = {
        "a": {"wrapped_table": [{"table": 3, "affected": True}, {"table": 3, "affected": False}],
              "zero_width_number": [], "header_row_table": [], "sub_label_currency": [],
              "page_top_part_table": []},
        "b": {"wrapped_table": [{"table": 1, "affected": False}],
              "zero_width_number": [], "header_row_table": [], "sub_label_currency": [],
              "page_top_part_table": []},
    }
    summary = pv.summarize(records)
    assert summary["wrapped_table"] == {
        "documents": 2, "tables": 2, "occurrences": 3, "affected": 1,
        "affected_tables": 1, "affected_documents": 1}
    assert summary["page_top_part_table"] == {
        "documents": 0, "tables": 0, "occurrences": 0, "affected": 0,
        "affected_tables": 0, "affected_documents": 0}
    assert tuple(summary) == DETECTORS
