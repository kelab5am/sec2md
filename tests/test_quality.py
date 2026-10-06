"""Tests for runtime parse diagnostics and quality enforcement."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from sec2md.core import convert_to_markdown, parse_filing
from sec2md.models import Element, Page
from sec2md.parser import Parser
from sec2md.quality import (
    ParseQualityError,
    build_diagnostics,
    enforce_quality,
    normalize_numeric_token,
    trace_numeric_failures,
)


def test_untraceable_normalized_number_is_reported():
    element = Element(id="e1", content="Revenue $1,234", kind="paragraph", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<p>Revenue 999</p>", "lxml").p]
    assert trace_numeric_failures(element, nodes) == ("e1:1234",)


def test_sentence_final_integer_is_traced_against_mapped_source():
    element = Element(id="e1", content="Revenue 123.", kind="paragraph", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<p>Revenue 999.</p>", "lxml").p]

    assert trace_numeric_failures(element, nodes) == ("e1:123",)


def test_sentence_final_decimal_is_traced_without_truncating_integer_part():
    element = Element(id="e1", content="Margin 12.5.", kind="paragraph", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<p>Margin 999.5.</p>", "lxml").p]

    assert trace_numeric_failures(element, nodes) == ("e1:12.5",)


def test_accounting_format_change_remains_traceable():
    element = Element(id="e1", content="Loss (16,173)", kind="table", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<td>(</td><td>16,173</td><td>)</td>", "lxml").body]
    assert trace_numeric_failures(element, nodes) == ()


def test_strict_rejects_empty_output_from_substantial_source(monkeypatch):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    with pytest.raises(ParseQualityError) as exc:
        convert_to_markdown(source)
    assert exc.value.diagnostics.source_visible_chars >= 1000
    assert exc.value.diagnostics.output_visible_chars == 0


def test_warn_returns_output_and_logs_warning(monkeypatch, caplog):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    assert convert_to_markdown(source, quality_policy="warn") == ""
    assert "substantial source produced empty output" in caplog.text


def test_off_skips_quality_enforcement(monkeypatch):
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    assert convert_to_markdown("<p>" + ("x " * 600) + "</p>", quality_policy="off") == ""


@pytest.mark.parametrize("quality_policy", ["strict", "warn", "off"])
def test_raw_bytes_base_url_preserves_quality_policy(quality_policy, monkeypatch, caplog):
    source = b"<html><body><p>" + (b"loss sentinel " * 100) + b"</p></body></html>"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")

    if quality_policy == "strict":
        with pytest.raises(ParseQualityError):
            convert_to_markdown(
                source,
                base_url="https://www.sec.gov/Archives/a.htm",
                quality_policy=quality_policy,
            )
    else:
        with caplog.at_level("WARNING"):
            assert (
                convert_to_markdown(
                    source,
                    base_url="https://www.sec.gov/Archives/a.htm",
                    quality_policy=quality_policy,
                )
                == ""
            )
        if quality_policy == "warn":
            assert "substantial source produced empty output" in caplog.text
        else:
            assert not caplog.records


def test_strict_rejects_catastrophic_output_ratio():
    source = "source " * 2_000
    diagnostics = build_diagnostics(
        source,
        "tiny",
        [],
        mapped_element_ids=(),
        trace_failures=(),
        enforce_mappings=False,
    )
    with pytest.raises(ParseQualityError, match="catastrophic output ratio"):
        enforce_quality(diagnostics, "strict")


@pytest.mark.parametrize(
    ("output", "mapped_ids", "trace_failures", "message"),
    [
        ("bad \ufffd text", {"e1"}, (), "replacement character"),
        ("bad \u0092 text", {"e1"}, (), "C1 control character"),
        ("Revenue 123", set(), (), "element lacks a source-node mapping"),
        ("Revenue 123", {"e1"}, ("e1:123",), "untraceable normalized number"),
    ],
)
def test_strict_hard_failures(output, mapped_ids, trace_failures, message):
    element = Element(id="e1", content=output, kind="paragraph", page_start=1, page_end=1)
    pages = [Page(number=1, content=output, elements=[element])]
    diagnostics = build_diagnostics(
        "source " * 200,
        output,
        pages,
        mapped_element_ids=mapped_ids,
        trace_failures=trace_failures,
        enforce_mappings=True,
    )
    with pytest.raises(ParseQualityError, match=message):
        enforce_quality(diagnostics, "strict")


def test_warn_logs_all_hard_failures_and_returns_diagnostics(caplog):
    diagnostics = build_diagnostics(
        "source " * 200,
        "bad \ufffd text",
        [
            Page(
                number=1,
                content="bad \ufffd text",
                elements=[Element(id="e1", content="bad \ufffd text", kind="paragraph", page_start=1, page_end=1)],
            )
        ],
        mapped_element_ids=(),
        trace_failures=("e1:123",),
        enforce_mappings=True,
    )
    with caplog.at_level("WARNING"):
        assert enforce_quality(diagnostics, "warn") is diagnostics
    assert "replacement character" in caplog.text
    assert "element lacks a source-node mapping" in caplog.text
    assert "untraceable normalized number" in caplog.text


def test_off_returns_diagnostics_without_logging(caplog):
    diagnostics = build_diagnostics(
        "source " * 200,
        "bad \ufffd text",
        [],
        mapped_element_ids=(),
        trace_failures=(),
        enforce_mappings=False,
    )
    with caplog.at_level("WARNING"):
        assert enforce_quality(diagnostics, "off") is diagnostics
    assert not caplog.records


def test_normalize_numeric_token_preserves_accounting_signs_and_blanks():
    assert normalize_numeric_token("$ (16,173)") == "-16173"
    assert normalize_numeric_token("−42") == "-42"
    assert normalize_numeric_token("65%") == "65"
    assert normalize_numeric_token("—") is None


def test_normalize_numeric_token_strips_markdown_emphasis():
    assert normalize_numeric_token("**$ (16,173)**") == "-16173"


@pytest.mark.parametrize("policy", ["invalid", "strictish", ""])
def test_invalid_quality_policy_rejected(policy):
    with pytest.raises(ValueError, match="invalid quality_policy"):
        convert_to_markdown("<p>ok</p>", quality_policy=policy)


def test_parse_filing_is_strict_by_default(monkeypatch):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "get_pages", lambda self, include_elements=True: [])
    with pytest.raises(ParseQualityError):
        parse_filing(source)


def test_parse_filing_warn_and_off_return_pages():
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    assert isinstance(parse_filing(source, quality_policy="warn"), list)
    assert isinstance(parse_filing(source, quality_policy="off"), list)


def test_include_elements_false_does_not_require_mappings():
    pages = parse_filing("<p>Content without citable elements</p>", include_elements=False)
    assert pages[0].elements is None


def test_positioned_fixture_rejects_silent_loss(monkeypatch):
    path = Path(__file__).parent / "fixtures" / "sec" / "positioned-issue-4.html"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    with pytest.raises(ParseQualityError):
        convert_to_markdown(path.read_text(encoding="utf-8"))


def test_strict_rejects_element_with_empty_source_node_mapping(monkeypatch):
    source = "<html><body><p>" + ("mapped content " * 100) + "</p></body></html>"

    def add_element_without_source_nodes(self, pages):
        pages[0].elements = [
            Element(
                id="empty-node-map",
                content=pages[0].content,
                kind="paragraph",
                page_start=1,
                page_end=1,
            )
        ]
        self.block_nodes_map = {"empty-node-map": []}
        return pages

    monkeypatch.setattr(Parser, "_add_elements_to_pages", add_element_without_source_nodes)
    with pytest.raises(ParseQualityError, match="element lacks a source-node mapping") as exc:
        convert_to_markdown(source, return_pages=True)
    assert exc.value.diagnostics.mapped_elements == 0


# ---------------------------------------------------------------------------
# Audit regressions (2026-10-02)
# ---------------------------------------------------------------------------

def test_parse_quality_error_survives_pickling():
    import pickle

    with pytest.raises(ParseQualityError) as caught:
        convert_to_markdown("<p>The Company&#65533;s revenue grew strongly this year.</p>")
    restored = pickle.loads(pickle.dumps(caught.value))

    assert type(restored) is ParseQualityError
    assert restored.diagnostics == caught.value.diagnostics
    assert str(restored) == str(caught.value)


def test_ordered_list_passes_strict_quality():
    html = "<p>Our principal risks are listed below.</p><ol><li>Supply chain risk</li><li>Competition risk</li></ol>"
    markdown = convert_to_markdown(html, quality_policy="strict")
    assert "1. Supply chain risk\n2. Competition risk" in markdown


def test_ordered_list_marker_does_not_hide_real_untraceable_numbers():
    element = Element(id="e1", content="1. Revenue $1,234", kind="list", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<ol><li>Revenue 999</li></ol>", "lxml").ol]
    assert trace_numeric_failures(element, nodes) == ("e1:1234",)


def test_line_start_number_outside_ordered_list_is_still_traced():
    element = Element(id="e1", content="2023. Revenue grew", kind="paragraph", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<p>Revenue grew</p>", "lxml").p]
    assert trace_numeric_failures(element, nodes) == ("e1:2023",)


@pytest.mark.parametrize("function", [convert_to_markdown, parse_filing])
def test_invalid_quality_policy_is_rejected_before_fetching(monkeypatch, function):
    import sec2md.core

    def fail_fetch(*args, **kwargs):
        raise AssertionError("source was fetched before quality_policy validation")

    monkeypatch.setattr(sec2md.core, "_resolve_source", fail_fetch)
    with pytest.raises(ValueError, match="invalid quality_policy"):
        function(
            "https://www.sec.gov/Archives/edgar/data/1/2/primary.htm",
            user_agent="Test User test@example.com",
            quality_policy="STRICT",
        )


# --- table completeness: normalizer, diagnostics fields, recall and logging --------------

def test_normalize_numeric_token_strips_euro_and_pound():
    assert normalize_numeric_token("€123") == "123"
    assert normalize_numeric_token("£ (456)") == "-456"


def test_normalized_numbers_reads_euro_and_pound_values():
    from sec2md.quality import _normalized_numbers

    assert _normalized_numbers("€1,234 and £5") == ("1234", "5")


OWN_CELL_CURRENCY = ('<table><tr><th>Item</th><th colspan="3">2026</th></tr>'
                     "<tr><td>Revenue</td><td>{sign}</td><td>1,234</td><td></td></tr>"
                     "<tr><td>Operating loss</td><td>{sign}</td><td>(567</td><td>)</td></tr>"
                     "<tr><td>Net loss</td><td>{sign}</td><td>(89</td><td>)</td></tr></table>")


@pytest.mark.parametrize("sign", ["$", "€", "£"], ids=["dollar", "euro", "pound"])
def test_strict_traces_amount_whose_currency_sign_has_its_own_cell(sign):
    # The source text reads "€ 1,234" and "€ (567 )" as single tokens. Unless the
    # normalizer strips euro and pound signs as it strips dollar signs, those source
    # numbers vanish and strict rejects the output's 1234 and -567 as untraceable.
    markdown = convert_to_markdown(OWN_CELL_CURRENCY.format(sign=sign))

    # Strict passing is not enough: each amount and its currency sign must reach
    # its row. Column alignment is not asserted, since euro and pound headers
    # still shift.
    lines = markdown.splitlines()
    for label, amount in [("Revenue", "1,234"), ("Operating loss", "(567)"), ("Net loss", "(89)")]:
        row = next((line for line in lines if line.startswith(f"| {label} |")), "")
        assert amount in row, markdown
        assert sign in row, markdown


LOSSY_TABLE = ("<p>" + "Revenue grew this year. " * 50 + "</p>"
               "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>9,943</td></tr>"
               "<tr><td>Cost</td><td>1,200</td></tr></table>")
LOSS_MESSAGE = "table 1 (snapshot 1, page 1): missing 9943 x1 [body] (total 1)"


@pytest.fixture
def lossy_renderer(monkeypatch):
    """Render tables without 9,943, as a column-merge defect would."""
    original = Parser._render_table
    monkeypatch.setattr(Parser, "_render_table", lambda self, element: original(self, element).replace("9,943", ""))


def test_parse_diagnostics_positional_construction_keeps_working():
    from sec2md.quality import ParseDiagnostics

    diagnostics = ParseDiagnostics(10, 10, 1.0, 0, 0, 1, 0, 0, (), ())
    assert diagnostics.table_completeness_failures == ()
    assert diagnostics.table_completeness_reported == ()
    assert diagnostics.table_structure_differences == ()
    assert diagnostics.tables_checked == 0
    assert diagnostics.numeric_recall is None


def test_diagnostics_with_table_findings_survive_pickling(lossy_renderer):
    import pickle

    parser = Parser(LOSSY_TABLE)
    parser.get_pages()
    assert parser.diagnostics.table_completeness_failures == (LOSS_MESSAGE,)
    assert pickle.loads(pickle.dumps(parser.diagnostics)) == parser.diagnostics


def test_build_diagnostics_records_table_report_and_numeric_recall():
    from sec2md.table_completeness import TableCompletenessReport, TableFinding

    finding = TableFinding(1, 1, 1, missing_values=(("50", "body", False),),
                           missing_reported=(("1", "reference"),),
                           structure=("source row 1: values out of order within the row",))
    diagnostics = build_diagnostics(
        "<p>Revenue 120 and cost 50.</p>", "Revenue 120 and cost.", [],
        mapped_element_ids=(), trace_failures=(), enforce_mappings=False,
        table_report=TableCompletenessReport(3, (finding,)),
    )
    assert diagnostics.table_completeness_failures == (finding.value_message(),)
    assert diagnostics.table_completeness_reported == (finding.reported_message(),)
    assert diagnostics.table_structure_differences == finding.structure_messages()
    assert diagnostics.tables_checked == 3
    assert diagnostics.numeric_recall == 0.5


def test_build_diagnostics_without_table_report_skips_all_three_checks():
    diagnostics = build_diagnostics(
        "<p>Revenue 120.</p>", "Revenue.", [],
        mapped_element_ids=(), trace_failures=(), enforce_mappings=False,
    )
    assert diagnostics.tables_checked == 0
    assert diagnostics.numeric_recall is None


def table_completeness_logs(caplog, level):
    """Messages the quality logger emitted at level for table completeness."""
    return [record.getMessage() for record in caplog.records
            if record.name == "sec2md.quality" and record.levelname == level
            and record.getMessage().startswith("sec2md table completeness: ")]


@pytest.mark.parametrize("policy", ["strict", "warn"])
def test_table_failures_are_logged_but_never_enforced(policy, lossy_renderer, caplog):
    with caplog.at_level("INFO"):
        output = convert_to_markdown(LOSSY_TABLE, quality_policy=policy)
    assert "9,943" not in output
    warnings = table_completeness_logs(caplog, "WARNING")
    assert len(warnings) == 1
    assert "sec2md table completeness: 1 table(s) with missing values" in warnings[0]
    assert f"sec2md table completeness: {LOSS_MESSAGE}" in table_completeness_logs(caplog, "INFO")


TWO_LOSSY_TABLES = (LOSSY_TABLE + "<p>" + "Costs rose this year. " * 20 + "</p>"
                    "<table><tr><th>Item</th><th>2025</th></tr><tr><td>Revenue</td><td>9,943</td></tr>"
                    "<tr><td>Cost</td><td>1,100</td></tr></table>")


def test_one_table_completeness_warning_per_document(lossy_renderer, caplog):
    with caplog.at_level("INFO"):
        output = convert_to_markdown(TWO_LOSSY_TABLES)
    assert "9,943" not in output
    warnings = table_completeness_logs(caplog, "WARNING")
    assert len(warnings) == 1
    assert "sec2md table completeness: 2 table(s) with missing values" in warnings[0]
    assert table_completeness_logs(caplog, "INFO") == [
        f"sec2md table completeness: {LOSS_MESSAGE}",
        "sec2md table completeness: table 2 (snapshot 2, page 1): missing 9943 x1 [body] (total 1)",
    ]


def test_off_policy_skips_table_checks(monkeypatch, caplog):
    monkeypatch.setattr("sec2md.parser.check_tables", lambda *a, **k: pytest.fail("checks ran"))
    with caplog.at_level("WARNING"):
        convert_to_markdown(LOSSY_TABLE, quality_policy="off")
        parse_filing(LOSSY_TABLE, quality_policy="off")
    assert "table completeness" not in caplog.text


# --- strict's numeric trace reads emphasised numbers like the source (2026-10-07) -----------
# The source pool reads separate bold runs "(", "650", ")" as "( 650 )", the accounting token
# -650. The output's Markdown delimiters sat between the parentheses and the digits, so the
# trace read 650 and strict failed on cover-page telephone numbers (MSFT, NTRA, TSLA). Only a
# number in parentheses that emphasis runs split is closed up; everything else reads as before.

NTRA_PHONE = ('<p><b>(</b><ix:nonNumeric name="dei:CityAreaCode"><b>650</b></ix:nonNumeric>'
              '<b>)&#160;</b><ix:nonNumeric name="dei:LocalPhoneNumber"><b>249-9090</b></ix:nonNumeric></p>')
_BOLD_RUN = 'style="white-space:pre-wrap;font-weight:bold;font-size:8pt;"'
SPAN_PHONE = (f'<p><span {_BOLD_RUN}>(</span><span style="font-size:8pt;">'
              f'<ix:nonNumeric name="dei:CityAreaCode"><span {_BOLD_RUN}>425</span></ix:nonNumeric></span>'
              f'<span {_BOLD_RUN}>) </span><span style="font-size:8pt;">'
              f'<ix:nonNumeric name="dei:LocalPhoneNumber"><span {_BOLD_RUN}>882-8080</span>'
              '</ix:nonNumeric></span></p>')
SPLIT_NET_LOSS = ('<p>Net loss was <b>(</b><ix:nonFraction name="us-gaap:NetIncomeLoss"><b>1,234</b>'
                  '</ix:nonFraction><b>)</b> for the year.</p>')


@pytest.mark.parametrize(("html", "rendered"), [
    (NTRA_PHONE, "**(** **650** **)** **249-9090**"),
    (SPAN_PHONE, "**(** **425** **)** **882-8080**"),
], ids=["bold-tags", "bold-spans"])
def test_strict_traces_phone_number_whose_parentheses_are_separate_bold_runs(html, rendered):
    # The fix is on the trace's output side only: the rendered Markdown keeps its emphasis.
    assert convert_to_markdown(html, quality_policy="strict") == rendered


@pytest.mark.parametrize(("html", "rendered"), [
    ("<p>Net loss was <b>(1,234)</b> for the year.</p>", "**(1,234)**"),
    ("<p>Net loss was <b>(</b><b>1,234</b><b>)</b> for the year.</p>", "**( 1,234 )**"),
    (SPLIT_NET_LOSS, "**(** **1,234** **)**"),
    ('<p>Net loss was <b>$(</b><ix:nonFraction name="us-gaap:NetIncomeLoss"><b>1,234</b></ix:nonFraction>'
     "<b>)</b> million.</p>", "**$(** **1,234** **)**"),
], ids=["one-run", "merged-runs", "separate-runs", "separate-runs-dollar"])
def test_strict_traces_bold_accounting_negative(html, rendered):
    assert rendered in convert_to_markdown(html, quality_policy="strict")


@pytest.mark.parametrize(("content", "negative", "positive", "failure"), [
    ("Net loss **(1,234)**", "<p>Net loss <b>(1,234)</b></p>", "<p>Net loss <b>1,234</b></p>", "e1:-1234"),
    ("**(** **650** **)** **249-9090**", NTRA_PHONE, "<p><b>650</b> <b>249-9090</b></p>", "e1:-650"),
], ids=["one-run", "separate-runs"])
def test_bold_accounting_negative_keeps_its_sign_in_the_trace(content, negative, positive, failure):
    element = Element(id="e1", content=content, kind="paragraph", page_start=1, page_end=1)
    assert trace_numeric_failures(element, [BeautifulSoup(negative, "lxml").p]) == ()
    # Parentheses the output shows around a number the source shows without them are caught.
    assert trace_numeric_failures(element, [BeautifulSoup(positive, "lxml").p]) == (failure,)


@pytest.mark.parametrize("content", ["Code **12**34", "Code *12*34", "Code ***12***34", "Code **12****34**"])
def test_emphasis_between_digits_does_not_merge_two_numbers(content):
    element = Element(id="e1", content=content, kind="paragraph", page_start=1, page_end=1)
    # The source reads "Code 12 34": two numbers, and the output must read two as well.
    assert trace_numeric_failures(element, [BeautifulSoup("<p>Code <b>12</b>34</p>", "lxml").p]) == ()
    # Merging them would trace a 1234 that the output never shows.
    assert trace_numeric_failures(element, [BeautifulSoup("<p>Code 1234</p>", "lxml").p]) == ("e1:12", "e1:34")


def test_split_parentheses_never_close_up_two_numbers():
    element = Element(id="e1", content="**(** **12** **34** **)**", kind="paragraph", page_start=1, page_end=1)
    assert trace_numeric_failures(element, [BeautifulSoup("<p>(1234)</p>", "lxml").p]) == ("e1:12", "e1:34")


def test_number_lost_from_bold_runs_still_fails_the_trace():
    element = Element(id="e1", content="**(** **650** **)** **249-9090**", kind="paragraph",
                      page_start=1, page_end=1)
    nodes = [BeautifulSoup("<p><b>(</b><b>)</b> <b>249-9090</b></p>", "lxml").p]
    assert trace_numeric_failures(element, nodes) == ("e1:-650",)


def _strict_trace_tokens(html):
    """The untraceable tokens strict reports for html, without element ids ([] when it passes)."""
    try:
        convert_to_markdown(html, quality_policy="strict")
    except ParseQualityError as exc:
        assert all(w.startswith("untraceable normalized number: ") for w in exc.diagnostics.warnings)
        return [failure.rsplit(":", 1)[1] for failure in exc.diagnostics.trace_numeric_failures]
    return []


@pytest.mark.parametrize(("html", "old", "new", "token"), [
    (NTRA_PHONE, "650", "605", "-605"),
    ("<p>Revenue (up <b>$1,234</b>) grew.</p>", "1,234", "1,834", "1834"),
    ("<p>Terms (as defined in <b>Section 5</b>) apply.</p>", "5", "7", "7"),
    ("<p>Leases are described (see <i>Note 12</i>) and elsewhere.</p>", "12", "17", "17"),
], ids=["inside-split-parentheses", "bold-amount-before-paren", "bold-section-before-paren",
        "italic-note-before-paren"])
def test_strict_rejects_a_number_altered_inside_emphasis(monkeypatch, html, old, new, token):
    # A number next to only one parenthesis reads as main reads it, so an alteration still fails.
    original = Parser._process_text_node
    monkeypatch.setattr(Parser, "_process_text_node", lambda self, node: original(self, node).replace(old, new))
    assert _strict_trace_tokens(html) == [token]


@pytest.mark.parametrize(("html", "token"), [(NTRA_PHONE, "650"), (SPLIT_NET_LOSS, "1234")],
                         ids=["phone", "net-loss"])
def test_strict_rejects_a_dropped_bold_opening_parenthesis(monkeypatch, html, token):
    original = Parser._process_text_node
    monkeypatch.setattr(Parser, "_process_text_node",
                        lambda self, node: "" if str(node).strip() == "(" else original(self, node))
    assert _strict_trace_tokens(html) == [token]


_SPLIT_650 = '<ix:nonFraction name="us-gaap:NetIncomeLoss"><b>650</b></ix:nonFraction>'


@pytest.mark.parametrize(("html", "rendered"), [
    (f"<p>Loss <b>$(</b>{_SPLIT_650}<b>)M</b> total</p>", "**$(** **650** **)M**"),
    (f"<p>Loss <b>USD(</b>{_SPLIT_650}<b>)</b> total</p>", "**USD(** **650** **)**"),
    (f"<p>Loss <b>(</b>{_SPLIT_650}<b>)thousand</b> total</p>", "**(** **650** **)thousand**"),
], ids=["paren-glued-to-M", "USD-glued-to-paren", "paren-glued-to-thousand"])
def test_split_parentheses_glued_to_a_word_read_as_before(monkeypatch, html, rendered):
    # Closed up, "(650)M" or "USD(650)" is no token the tokenizer reads, so the number would drop
    # out of the trace. Parentheses glued to a word or digit stay as they are: the number reads
    # 650 as on main (the source, "USD( 650 )", reads none), and an altered one still fails.
    assert rendered in convert_to_markdown(html, quality_policy="off")
    assert _strict_trace_tokens(html) == ["650"]
    original = Parser._process_text_node
    monkeypatch.setattr(Parser, "_process_text_node", lambda self, node: original(self, node).replace("650", "651"))
    assert _strict_trace_tokens(html) == ["651"]


@pytest.mark.parametrize("html", [
    "<p>Shares repurchased (125*) during the year.</p>",
    "<p>Shares repurchased (*125) during the year.</p>",
    "<table><tr><td>Revenue</td><td>(1,234*)</td></tr><tr><td>Cost</td><td>500</td></tr></table>",
    "<p>(10.1*) Filed herewith.</p>",
    "<p>Net loss <b>(1,234*)</b> for the year.</p>",
    "<p>Basic loss per share $(0.12*) for the year.</p>",
    "<p>Number of copies requested: _5_ (five).</p>",
    "<p>Page _1_ of _3_</p>",
    "<p>Amount withheld (_5_) per share.</p>",
    "<p>Signed _on March 5, 2024_ by the Registrant.</p>",
    "<p>Yes _X_ No ___ Shares outstanding: __1,234__</p>",
    "<p>See file_2023_report for the year ended 20__.</p>",
], ids=["paren-125-star", "paren-star-125", "table-1234-star", "exhibit-10.1-star", "bold-1234-star",
        "dollar-0.12-star", "underscore-5", "underscore-page", "underscore-paren", "underscore-span",
        "underscore-blank", "underscore-word"])
def test_literal_asterisks_and_underscores_read_as_before(html):
    # Footnote stars and underscores are source text, not emphasis the renderer added.
    assert _strict_trace_tokens(html) == []
