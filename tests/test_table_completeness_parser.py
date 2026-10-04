"""Table completeness through the parser: every review case, in both rendering modes."""

import re

import pytest

from sec2md.core import convert_to_markdown
from sec2md.parser import Parser
from sec2md.table_completeness import check_tables

BOTH_MODES = pytest.mark.parametrize("capture", [False, True], ids=["normal", "capture"])


def findings(html, capture=False, mutate=None):
    """{ordinal: (missing values, missing reported, structure)} for one document.

    mutate rewrites each recorded table output before checking, which simulates a
    renderer that lost or moved something without touching the real rendering.
    """
    parser = Parser(html, capture_tables=capture)
    parser.get_pages(include_images=False)
    report = parser.table_report
    if mutate is not None:
        outputs = {key: mutate(value) for key, value in parser.table_outputs.items()}
        report = check_tables(parser.soup, outputs, parser._table_pages, parser._snapshot_ordinals)
    return {f.ordinal: (f.missing_values, f.missing_reported, f.structure) for f in report.findings}


def lost(*tokens, role="body", ambiguous=False):
    return tuple((token, role, ambiguous) for token in tokens)


def drop_line(prefix):
    """Delete the first output line starting with prefix (a whole rendered row)."""
    def mutate(segment):
        lines = segment.split("\n")
        index = next((i for i, line in enumerate(lines) if line.startswith(prefix)), None)
        if index is not None:
            del lines[index]
        return "\n".join(lines)
    return mutate


def swap_body_rows(segment):
    lines = segment.split("\n")
    lines[2], lines[3] = lines[3], lines[2]
    return "\n".join(lines)


def move_values_between_rows(segment):
    return segment.replace("| 100 |", "| @ |").replace("| 40 |", "| 100 |").replace("| @ |", "| 40 |")


def reverse_numeric_cells(segment):
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        for i, value in zip(idx, [cells[i] for i in idx][::-1]):
            cells[i] = value
        out.append("|".join(cells))
    return "\n".join(out)


MERGE_LOSS = ("<table><tr><td>2024</td><td>$</td><td>9,943</td></tr>"
              "<tr><td>2025</td><td></td><td>10,775</td></tr><tr><td>Total</td><td>$</td><td>20,718</td></tr></table>")
TWO_BY_TWO = ("<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
              "<tr><td>Revenue</td><td>120</td><td>100</td></tr><tr><td>Cost</td><td>50</td><td>40</td></tr></table>")
SPLIT_NEGATIVE = ('<table><tr><th>Item</th><th colspan="2">2026</th></tr>'
                  "<tr><td>Revenue</td><td>120</td><td></td></tr><tr><td>Loss</td><td>(29</td><td>)</td></tr></table>")
NOTE9 = ("<table><tr><th>Item</th><th>2026</th></tr>"
         "<tr><td>Note 9 Impairment</td><td>$</td><td>9</td></tr><tr><td>Other</td><td></td><td>12</td></tr></table>")
SUP9 = ("<table><tr><th>Item</th><th>2026</th></tr>"
        "<tr><td>Impairment<sup>9</sup></td><td>$</td><td>9</td></tr><tr><td>Other</td><td></td><td>12</td></tr></table>")
YEARS = ("<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
         "<tr><td>Revenue</td><td>2000</td><td>1900</td></tr><tr><td>Cost</td><td>500</td><td>400</td></tr></table>")
STANDALONE_MARKER = ("<table><tr><th>Item</th><th>Amount</th></tr>"
                     "<tr><td>Impairment</td><td>9</td></tr><tr><td>Footnote</td><td><sup>9</sup></td></tr></table>")
UNLABELLED_MARKER = ("<table><tr><th>Item</th><th>Amount</th></tr>"
                     "<tr><td></td><td>9</td></tr><tr><td></td><td><sup>9</sup></td></tr></table>")
NOTES = ("<table><tr><th>Item</th><th>Amount</th></tr>"
         "<tr><td>Note 1</td><td>9</td></tr><tr><td>Note 2</td><td><sup>9</sup></td></tr></table>")
TOTALS = ("<table><tr><th>Item</th><th>Amount</th></tr>"
          "<tr><td>Total</td><td>9</td></tr><tr><td>Total</td><td><sup>9</sup></td></tr></table>")
CURRENCIES = ("<table><tr><td>Item</td><td>2026</td></tr><tr><td>Revenue</td><td>€123</td></tr>"
              "<tr><td>Cost</td><td>£456</td></tr></table>")
HIDDEN = ("<table><tr><td>Item</td><td>2026</td></tr>"
          '<tr><td>Revenue</td><td>100<span style="display:none">999</span></td></tr></table>')
EXHIBITS = ("<table><tr><th>Exhibit</th><th>Description</th></tr>"
            "<tr><td>3.1</td><td>Restated Certificate of Incorporation</td></tr>"
            "<tr><td>10.2</td><td>Credit Agreement</td></tr></table>")
SIGNATURE = ("<table><tr><td>Date:</td><td>January 29, 2025</td><td>/s/ Jane Doe</td></tr>"
             "<tr><td></td><td></td><td>Jane Doe, Chief Financial Officer</td></tr></table>")
STACKED = ("<table><tr><td></td><td>Three Months Ended June 30, 2025</td><td>Three Months Ended June 30, 2024</td></tr>"
           "<tr><td>Balance at beginning</td><td>2,523</td><td>2,537</td></tr>"
           "<tr><td>Net income</td><td>18,337</td><td>13,465</td></tr>"
           "<tr><td></td><td>Six Months Ended June 30, 2025</td><td>Six Months Ended June 30, 2024</td></tr>"
           "<tr><td>Balance at beginning</td><td>2,534</td><td>2,561</td></tr>"
           "<tr><td>Net income</td><td>34,981</td><td>25,834</td></tr></table>")
FUSED_HEADER = ('<table><tr><td></td><td colspan="2">Year ended December 31,</td><td colspan="2">2024 vs. 2023</td></tr>'
                "<tr><td></td><td>2024</td><td>2023</td><td>$ Change</td><td>% Change</td></tr>"
                "<tr><td>Revenue</td><td>1,300</td><td>804</td><td>496</td><td>62%</td></tr>"
                "<tr><td>Cost</td><td>300</td><td>200</td><td>100</td><td>50%</td></tr></table>")
NESTED = ("<table><tr><td>Outer<table><tr><td>Inner</td><td>77</td></tr><tr><td>B</td><td>88</td></tr></table></td>"
          "<td>12</td></tr><tr><td>Outer B</td><td>34</td></tr></table>")

# (name, html, mutate, expected findings) with the same result in both rendering modes.
CASES = [
    ("prose repeats the lost value", "<p>Commitments include $9,943 million due in 2024.</p>" + MERGE_LOSS, None,
     {1: (lost("9943"), (), ())}),
    ("inline-split number",
     "<table><tr><td>Item</td><td>2026</td></tr><tr><td>Revenue</td><td>1,2<span>34</span></td></tr></table>", None,
     {1: (lost("1234"), (), ())}),
    ("hidden descendant is not source", HIDDEN, None, {}),
    ("hidden value leaked into the output keeps the visible value", HIDDEN, lambda s: s.replace("100", "100 999"), {}),
    ("euro and pound values", CURRENCIES, None, {}),
    ("lost euro value", CURRENCIES, lambda s: s.replace("€123", "€"), {1: (lost("123"), (), ())}),
    ("lost single-digit $9",
     "<table><tr><td>Impairment</td><td>$</td><td>9</td></tr><tr><td>Other</td><td></td><td>12</td></tr>"
     "<tr><td>Total</td><td>$</td><td>21</td></tr></table>", None,
     {1: (lost("9"), (), ())}),
    ("sup footnote marker rendered as (1)",
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue<sup>(1)</sup></td><td>120</td></tr></table>", None, {}),
    ("percentage range",
     "<table><tr><th>Item</th><th>Rate</th></tr><tr><td>Discount rate</td><td>3.5%-4.3%</td></tr>"
     "<tr><td>Growth</td><td>2%</td></tr></table>", None, {}),
    ("NVDA link-split digits",
     '<table><tr><td><a href="#a">Statements of Income for the years ended January 2</a><a href="#a">5</a>'
     '<a href="#a">, 2025</a></td><td><a href="#p">84</a></td></tr>'
     '<tr><td><a href="#b">Balance Sheets</a></td><td><a href="#q">8</a><a href="#q">5</a></td></tr></table>', None, {}),
    ("one-row table before a multi-row table",
     "<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table>"
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>", None, {}),
    ("header-only table without numbers",
     "<table><tr><th>Name</th><th>Position</th></tr><tr><th>Directors</th><th></th></tr></table>", None, {}),
    ("numeric cells reversed", TWO_BY_TWO, reverse_numeric_cells,
     {1: ((), (), ("source row 1: values out of order within the row",
                   "source row 2: values out of order within the row"))}),
    ("'Note 1 Revenue' row loses its amount",
     "<table><tr><td>Note 1 Revenue</td><td>$</td><td>9,943</td></tr><tr><td>Other</td><td></td><td>12</td></tr>"
     "<tr><td>Total</td><td>$</td><td>9,955</td></tr></table>", None,
     {1: (lost("9943"), (), ())}),
    ("split negative preserved", SPLIT_NEGATIVE, None, {}),
    ("split negative deleted", SPLIT_NEGATIVE, lambda s: s.replace("(29", ""), {1: (lost("-29"), (), ())}),
    ("body rows swapped", TWO_BY_TWO, swap_body_rows,
     {1: ((), (), ("source row 2: appears before an earlier source row",))}),
    ("values moved between rows", TWO_BY_TWO, move_values_between_rows,
     {1: ((), (), ("source row 1: values present but split across output rows",
                   "source row 2: values present but split across output rows"))}),
    ("signature date lost (reported only)", SIGNATURE, lambda s: s.replace("January 29, 2025", ""),
     {1: ((), (("2025", "reference"), ("29", "reference")), ())}),
    ("lost exhibit-index identifier (reported only)", EXHIBITS, lambda s: s.replace("| 3.1 |", "|  |"),
     {1: ((), (("3.1", "reference"),), ())}),
    ("stacked statement with repeated section headers", STACKED, None, {}),
    ("'Note 9' kept, amount 9 deleted", NOTE9, lambda s: s.replace("| $ 9 |", "| $ |"), {1: (lost("9"), (), ())}),
    ("<sup>9</sup> kept, amount 9 deleted", SUP9, lambda s: s.replace("| $ 9 |", "| $ |"), {1: (lost("9"), (), ())}),
    ("amount kept, 'Note 9' identifier lost", NOTE9, lambda s: s.replace("Note 9 Impairment", "Impairment"),
     {1: ((), (("9", "reference"),), ())}),
    ("amount kept, <sup>9</sup> marker lost", SUP9, lambda s: s.replace("Impairment 9", "Impairment"),
     {1: ((), (("9", "marker"),), ())}),
    ("marker glued to the amount in the output",
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>1,234<sup>(1)</sup></td></tr>"
     "<tr><td>Cost</td><td>500</td></tr></table>", None, {}),
    ("accounting negative beside a currency cell",
     "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Loss</td><td>$</td><td>(96</td><td>)</td></tr>"
     "<tr><td>Cost</td><td></td><td>500</td><td></td></tr></table>", None, {}),
    ("'Revenue | 2000 | 1900' swapped", YEARS, lambda s: s.replace("| 2000 | 1900 |", "| 1900 | 2000 |"),
     {1: ((), (), ("source row 1: values out of order within the row",))}),
    ("year-only header row stays out of check 2",
     "<table><tr><td></td><td>2023</td><td>2022</td></tr><tr><td>Revenue</td><td>2,000</td><td>1,900</td></tr>"
     "<tr><td>Cost</td><td>500</td><td>400</td></tr></table>", None, {}),
    ("standalone <sup>9</sup> cell, output unchanged", STANDALONE_MARKER, None, {}),
    ("standalone <sup>9</sup> cell kept, amount deleted", STANDALONE_MARKER,
     lambda s: s.replace("| Impairment | 9 |", "| Impairment |  |"), {1: (lost("9"), (), ())}),
    ("amount kept, standalone <sup>9</sup> deleted", STANDALONE_MARKER,
     lambda s: s.replace("| Footnote | 9 |", "| Footnote |  |"), {1: ((), (("9", "standalone_marker"),), ())}),
    ("unlabelled rows, amount deleted", UNLABELLED_MARKER, lambda s: s.replace("| 9 |\n| 9 |", "|  |\n| 9 |", 1),
     {1: (lost("9", role="label", ambiguous=True), (), ())}),
    ("'Note 1' / 'Note 2' rows, output unchanged", NOTES, None, {}),
    ("'Note 1' row deleted", NOTES, drop_line("| Note 1 |"), {1: (lost("9"), (("1", "reference"),), ())}),
    ("'Note 2' footnote row deleted", NOTES, drop_line("| Note 2 |"),
     {1: ((), (("2", "reference"), ("9", "standalone_marker")), ())}),
    ("repeated 'Total' rows, output unchanged", TOTALS, None, {}),
    ("first 'Total' row deleted", TOTALS, drop_line("| Total |"), {1: (lost("9", ambiguous=True), (), ())}),
    ("fused multi-row header", FUSED_HEADER, None, {}),
    # Header rows are excluded from check 2 even when nothing is missing: the <th> row's
    # euro amounts are not a data row (plan review round 1, finding 1).
    ("<th> header row with euro amounts, output unchanged",
     "<table><tr><th>Denomination</th><th>€1</th><th>€2</th></tr><tr><td>Issued</td><td>2</td><td>1</td></tr></table>",
     None, {}),
]


@BOTH_MODES
@pytest.mark.parametrize("name, html, mutate, expected", CASES, ids=[case[0] for case in CASES])
def test_review_case(name, html, mutate, expected, capture):
    assert findings(html, capture, mutate) == expected


def test_nested_table_follows_each_rendering_mode():
    # Normal Markdown drops the outer cell's 12 beside a nested table; capture-mode
    # fallback text keeps it.
    assert findings(NESTED, capture=False) == {1: (lost("12"), (), ())}
    assert findings(NESTED, capture=True) == {}


@BOTH_MODES
def test_one_row_table_before_multi_row_table_is_ordinal_2_snapshot_1(capture):
    parser = Parser("<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table>"
                    "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>",
                    capture_tables=capture)
    parser.get_pages(include_images=False)
    outputs = {key: value.replace("120", "") for key, value in parser.table_outputs.items()}
    report = check_tables(parser.soup, outputs, parser._table_pages, parser._snapshot_ordinals)
    assert report.failures == ("table 2 (snapshot 1, page 1): missing 120 x1 [body] (total 1)",)
    if capture:
        assert [s.ordinal for s in parser.table_snapshots] == [1]


def test_table_checks_can_be_disabled():
    parser = Parser(MERGE_LOSS, table_checks=False)
    parser.get_pages()
    assert parser.table_report is None
    assert parser.table_outputs == {}


def test_failing_checks_never_fail_the_conversion(monkeypatch, caplog):
    # Phase A is report-only: a defect inside the checks must leave the output intact.
    expected = convert_to_markdown(TWO_BY_TWO)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("sec2md.parser.check_tables", boom)
    with caplog.at_level("ERROR"):
        assert convert_to_markdown(TWO_BY_TWO) == expected
        parser = Parser(TWO_BY_TWO)
        parser.get_pages()
    assert parser.table_report is None
    assert parser.diagnostics.tables_checked == 0
    assert any(record.levelname == "ERROR" and "the checks failed" in record.getMessage()
               for record in caplog.records)


def test_report_is_reset_between_get_pages_calls():
    parser = Parser(TWO_BY_TWO)
    parser.get_pages()
    first = parser.table_report
    parser.get_pages()
    assert parser.table_report == first
    assert len(parser.table_outputs) == 1


@pytest.mark.parametrize("capture", [False, True], ids=["normal", "capture"])
@pytest.mark.parametrize("table_checks", [False, True], ids=["unchecked", "checked"])
def test_effective_rows_runs_once_per_table(capture, table_checks, monkeypatch):
    # Snapshot ordinals reuse the rows _render_table needs, and nothing is computed for
    # them when neither capture nor checks need it (plan review round 1, finding 2).
    calls = []
    original = Parser._effective_rows
    monkeypatch.setattr(Parser, "_effective_rows", lambda self, table: calls.append(1) or original(self, table))
    parser = Parser("<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table>" + TWO_BY_TWO,
                    capture_tables=capture, table_checks=table_checks)
    parser.get_pages()
    assert len(calls) == 2
