import json
from collections import Counter
import re
import warnings
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

import pytest
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from sec2md.core import convert_to_markdown
from sec2md.encoding import decode_html
from sec2md.models import Element, Page
from sec2md.parser import Parser
from sec2md.quality import ElementHeaderRecord, ParseQualityError, normalize_numeric_token
from sec2md.table_parser import TableParser
from sec2md.utils import FetchedHtml

from tests.accuracy import metrics
from tests.accuracy.fixtures import FIXTURE_IDS, FixtureContract, load_fixture
from tests.accuracy.metrics import (
    SourceRow,
    _financial_row_recall,
    _in_header_line_cells,
    _mapping_and_trace,
    _markdown_cells,
    _oracle_page_ends,
    _oracle_trace_numeric_failures,
    _parse_document,
    _parse_once,
    _visible_text,
    audit_document,
    body_line_counts,
    body_matched_rows,
    extract_financial_rows,
    extract_header_lines,
    multiset_recall,
    normalize_numbers,
    normalize_words,
    source_soup,
    text_source_rows,
)


def test_audit_document_enforces_requested_quality_policy(monkeypatch):
    source = b"<html><body><p>Controlled diagnostics input.</p></body></html>"
    contract = FixtureContract(
        fixture_id="controlled",
        filename="",
        cik="",
        accession="",
        form="",
        report_date="",
        sec_url="",
        role="",
        sha256="",
        expected_encoding_reason="strict-utf8",
        min_word_recall=0.0,
        min_numeric_recall=0.0,
        min_financial_row_recall=0.0,
        expected_sections=(),
        representative_rows=(),
    )
    baseline = audit_document(source, contract, quality_policy="off")
    original_get_pages = Parser.get_pages

    def inject_controlled_diagnostic(self, *args, **kwargs):
        pages = original_get_pages(self, *args, **kwargs)
        assert self.diagnostics is not None
        self.diagnostics = replace(
            self.diagnostics, warnings=("controlled diagnostics failure",)
        )
        return pages

    monkeypatch.setattr(Parser, "get_pages", inject_controlled_diagnostic)

    with pytest.raises(ParseQualityError, match="controlled diagnostics failure"):
        audit_document(source, contract, quality_policy="strict")

    off_result = audit_document(source, contract, quality_policy="off")
    assert off_result.markdown_sha256 == baseline.markdown_sha256


@pytest.fixture(scope="session")
def all_accuracy_results():
    results = []
    for fixture_id in FIXTURE_IDS:
        contract, source = load_fixture(fixture_id)
        first = audit_document(source, contract, quality_policy="strict")
        second = audit_document(source, contract, quality_policy="strict")
        results.append((contract, first, second))
    return tuple(results)


def test_rcq_release_contract(all_accuracy_results):
    assert len(all_accuracy_results) == 7
    results_by_id = {}
    for contract, first, second in all_accuracy_results:
        results_by_id[contract.fixture_id] = first
        assert first.markdown_sha256 == second.markdown_sha256
        assert first.pages_sha256 == second.pages_sha256
        assert first.annotated_html_sha256 == second.annotated_html_sha256
        assert first.word_recall >= contract.min_word_recall
        assert first.numeric_recall >= contract.min_numeric_recall
        assert first.financial_row_recall >= contract.min_financial_row_recall
        assert first.inconsistent_table_widths == ()
        assert first.replacement_characters == 0
        assert first.c1_control_characters == 0
        assert first.duplicate_element_ids == ()
        assert first.missing_element_mappings == ()
        assert first.trace_numeric_failures == ()
        assert first.invalid_xbrl_tags == ()
        assert set(contract.expected_sections) <= set(first.sections)
        assert first.representative_row_failures == ()

    legacy_markdown, _, _, _, _ = _parse_once(load_fixture("nvda-2002-10k")[1])
    legacy_rows = [line for line in legacy_markdown.splitlines() if "16,173" in line]
    assert len(legacy_rows) == 1
    legacy_cells = _markdown_cells(legacy_rows[0])
    assert "(16,173)" in legacy_cells
    assert ")" not in legacy_cells
    assert normalize_numeric_token("(16,173)") == "-16173"

    eight_k_contract, eight_k_source = load_fixture("nvda-2026-08-26-8k")
    eight_k_markdown, _, _, _, _ = _parse_once(eight_k_source)
    assert {"ITEM 2.02", "ITEM 9.01"} <= set(results_by_id["nvda-2026-08-26-8k"].sections)
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", eight_k_markdown)
    resolved_links = {urljoin(eight_k_contract.sec_url, link) for link in links}
    assert load_fixture("nvda-2026-ex99-1")[0].sec_url in resolved_links
    assert load_fixture("nvda-2026-ex99-2")[0].sec_url in resolved_links

    # Fixtures stay gzipped; the gitignored golden-download cache is not a fixture.
    tests_dir = Path(__file__).resolve().parents[1]
    html_files = sorted(
        path.relative_to(tests_dir).as_posix()
        for path in tests_dir.rglob("*.html")
        if ".cache" not in path.relative_to(tests_dir).parts
    )
    assert html_files == ["fixtures/sec/positioned-issue-4.html"]


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_fixture_hash_and_identity(fixture_id: str):
    contract, source = load_fixture(fixture_id)
    assert source
    assert contract.fixture_id == fixture_id
    assert contract.sha256 == __import__("hashlib").sha256(source).hexdigest()


def test_corpus_has_required_document_roles_and_forms():
    contracts = [load_fixture(fixture_id)[0] for fixture_id in FIXTURE_IDS]
    assert {contract.form for contract in contracts} >= {"10-K", "10-Q", "8-K"}
    assert {contract.role for contract in contracts} >= {"primary", "exhibit"}
    assert len(contracts) == 7


def test_normalization_preserves_words_and_accounting_signs():
    assert normalize_words("Apple’s results — reviewed") == ["apple’s", "results", "reviewed"]
    assert normalize_numbers("$1,234; (16,173); −5%; —") == ["1234", "-16173", "-5"]


def test_multiset_recall_is_duplicate_aware():
    assert multiset_recall(["a", "a", "b"], ["a", "b", "b"]) == pytest.approx(2 / 3)
    assert multiset_recall([], []) == 1.0


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_audited_document_meets_baseline_contract(fixture_id: str):
    contract, source = load_fixture(fixture_id)
    result = audit_document(source, contract, quality_policy="strict")

    assert result.word_recall >= contract.min_word_recall
    assert result.numeric_recall >= contract.min_numeric_recall
    assert result.financial_row_recall >= contract.min_financial_row_recall
    assert not result.representative_row_failures
    assert result.expected_sections == contract.expected_sections
    if fixture_id != "nvda-2002-10k":
        assert not result.table_width_errors
    assert result.replacement_characters == 0
    assert result.c1_control_characters == 0
    assert not result.duplicate_element_ids
    assert not result.missing_mappings
    assert not result.trace_failures
    assert not result.invalid_visible_node_xbrl_tags
    assert result.deterministic_markdown
    assert result.deterministic_pages
    assert result.deterministic_annotated_html


def test_apple_trace_has_no_failures():
    contract, source = load_fixture("aapl-2023-10k")
    result = audit_document(source, contract, quality_policy="strict")
    assert result.trace_failures == ()


def test_fixture_encoding_reasons_match_manifest():
    for fixture_id in FIXTURE_IDS:
        contract, source = load_fixture(fixture_id)
        _, diagnostics = decode_html(source)
        assert diagnostics.reason == contract.expected_encoding_reason


def test_legacy_character_normalization_has_no_c1_controls():
    contract, source = load_fixture("nvda-2002-10k")
    result = audit_document(source, contract, quality_policy="strict")

    assert result.replacement_characters == 0
    assert result.c1_control_characters == 0


def test_legacy_accounting_reconstruction_preserves_sign_and_widths():
    _, source = load_fixture("nvda-2002-10k")
    markdown, _, _, _, _ = _parse_once(source)
    from tests.accuracy.metrics import _table_width_errors

    expected_width_errors = ()
    actual_width_errors = _table_width_errors(markdown)
    assert actual_width_errors == expected_width_errors

    rows = [line for line in markdown.splitlines() if "16,173" in line]
    assert len(rows) == 1
    cells = _markdown_cells(rows[0])
    accounting_cells = [cell for cell in cells if "(16,173)" in cell]
    assert accounting_cells == ["(16,173)"]
    assert all(cell != ")" for cell in cells)
    assert normalize_numeric_token(accounting_cells[0]) == "-16173"


def _legacy_accounting_recovery_is_valid(markdown: str) -> bool:
    rows = [line for line in markdown.splitlines() if "16,173" in line]
    if len(rows) != 1:
        return False
    cells = _markdown_cells(rows[0])
    label = re.sub(r"\s+", " ", cells[0]).strip() if cells else ""
    return label == "Interest expense" and len(cells) == 4 and [
        normalize_numbers(cell) for cell in cells[1:]
    ] == [["-16173"], ["-4852"], ["-332"]]


def test_legacy_accounting_recovery_rejects_wrong_label():
    markdown = "| Other expense | (16,173) | (4,852) | (332) |"
    assert not _legacy_accounting_recovery_is_valid(markdown)


def test_known_8k_link_defect_is_exactly_bounded():
    contract, source = load_fixture("nvda-2026-08-26-8k")
    markdown, _, _, _, _ = _parse_once(source)
    result = audit_document(source, contract, quality_policy="strict")
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", markdown)
    assert result.exhibit_link_count >= 2
    assert _has_audited_exhibit_links(links)
    assert "Augu st 2 6" not in markdown
    assert "Se cond" not in markdown
    assert "August 26" in markdown
    assert "Second" in markdown


def test_8k_link_recovery_fetches_only_the_primary_filing(monkeypatch):
    contract, source = load_fixture("nvda-2026-08-26-8k")
    calls: list[str] = []

    def fetch_primary_only(url: str, user_agent: str | None = None) -> FetchedHtml:
        calls.append(url)
        assert url == contract.sec_url
        return FetchedHtml(source, "utf-8")

    monkeypatch.setattr("sec2md.core.fetch", fetch_primary_only)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        convert_to_markdown(contract.sec_url, quality_policy="off")

    assert calls == [contract.sec_url]


def _has_audited_exhibit_links(links: list[str]) -> bool:
    primary_url = load_fixture("nvda-2026-08-26-8k")[0].sec_url
    expected_urls = {
        load_fixture("nvda-2026-ex99-1")[0].sec_url,
        load_fixture("nvda-2026-ex99-2")[0].sec_url,
    }
    resolved_urls = {urljoin(primary_url, link) for link in links}
    return expected_urls <= resolved_urls


def test_8k_link_recovery_rejects_arbitrary_host_same_suffix_urls():
    links = [
        "https://example.test/q2fy27pr.htm",
        "https://example.test/q2fy27cfocommentary.htm",
    ]
    assert not _has_audited_exhibit_links(links)


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_audited_financial_rows_include_literal_representatives(fixture_id: str):
    contract, source = load_fixture(fixture_id)
    actual_rows = extract_financial_rows(source)
    for representative in contract.representative_rows:
        matches = [
            numbers
            for label, numbers in actual_rows
            if representative.label.casefold() in label.casefold()
            and multiset_recall(representative.numbers, numbers) == 1.0
        ]
        assert matches, (fixture_id, representative)


def test_positioned_fixture_contains_visible_text_inside_positioned_leaf():
    path = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "sec" / "positioned-issue-4.html"
    visible = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml").get_text(" ", strip=True)
    assert "POSITIONED LOSS SENTINEL" in visible
    assert len(visible) >= 1200


def test_positioned_fixture_quality_guard_rejects_silent_loss(monkeypatch):
    path = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "sec" / "positioned-issue-4.html"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    with pytest.raises(ParseQualityError):
        convert_to_markdown(path.read_text(encoding="utf-8"))


def test_financial_row_recall_rejects_labels_that_differ_after_eighth_word():
    source = [("One two three four five six seven eight nine ten", ("1", "2"))]
    actual = [("One two three four five six seven eight nine eleven", ("1", "2"))]
    assert _financial_row_recall(source, actual) == 0.0


def test_financial_row_recall_collapses_only_label_whitespace():
    source = [("Net (loss) from operations", ("1", "2"))]
    actual = [("Net  (loss)   from operations", ("1", "2"))]
    assert _financial_row_recall(source, actual) == 1.0


def test_financial_row_recall_preserves_nonwhitespace_label_case():
    source = [("Net (loss) from operations", ("1", "2"))]
    actual = [("net (loss) from operations", ("1", "2"))]
    assert _financial_row_recall(source, actual) == 0.0


def test_trace_validation_counts_duplicate_expected_numbers():
    page = Page(
        number=1,
        content="10 10",
        elements=[
            Element(id="element-1", content="10 10", kind="paragraph", page_start=1, page_end=1)
        ],
    )
    missing, failures, invalid_tags = _mapping_and_trace(
        [page], '<p data-sec2md-block="element-1">10</p>'
    )
    assert missing == ()
    assert failures == ("element-1:10",)
    assert invalid_tags == ()


def test_trace_validation_preserves_repeated_element_failures():
    page = Page(
        number=1,
        content="10 10 10 10",
        elements=[
            Element(id="element-1", content="10 10", kind="paragraph", page_start=1, page_end=1),
            Element(id="element-1", content="10 10", kind="paragraph", page_start=1, page_end=1),
        ],
    )
    _, failures, _ = _mapping_and_trace(
        [page], '<p data-sec2md-block="element-1">10</p>'
    )
    assert failures == ("element-1:10", "element-1:10")


# --- The suite's own trace applies R6a's header accounting (spec 2026-10-05) --------------
# Records carry header-zone cell texts only (strict's token fields are left empty here), so
# these tests show the harness tokenizes them itself.

R6A_TABLE = (
    '<table><tr><th>Metric</th><th colspan="2">{top}</th></tr>'
    "<tr><th></th><th>{lower}</th><th>Budget</th></tr>"
    "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
)
LABELS_CELLS = (("Metric", 1), ("2025", 2), ("Actual", 1), ("Budget", 1))
EQUAL_CELLS = (("Metric", 1), ("2025", 2), ("2025", 1), ("Budget", 1))
LABELS_HEADER = "| Metric | 2025 — Actual | 2025 — Budget |"
EQUAL_HEADER = "| Metric | 2025 | 2025 — Budget |"


def _table_element(header: str, body: str = "| Revenue | 100 | 200 |", *, separator="| --- | --- | --- |"):
    content = f"{header}\n{separator}\n{body}"
    return Element(id="e1", content=content, kind="table", page_start=1, page_end=1)


def _table_nodes(top="2025", lower="Actual"):
    return [BeautifulSoup(R6A_TABLE.format(top=top, lower=lower), "lxml").find("table")]


def _record(segment: str, header_line: str, cells):
    return ElementHeaderRecord(segment=segment, header_line=header_line, header_cells=cells)


def test_oracle_trace_accounts_a_repeated_header_number():
    element = _table_element(LABELS_HEADER)
    record = _record(element.content, LABELS_HEADER, LABELS_CELLS)
    assert _oracle_trace_numeric_failures(element, _table_nodes()) == ("e1:2025",)
    assert _oracle_trace_numeric_failures(element, _table_nodes(), [record]) == ()


def test_oracle_trace_reports_a_header_number_beyond_the_header_capacity():
    header = "| Metric | 2025 — Actual | 2025 — Budget 2024 |"
    element = _table_element(header)
    record = _record(element.content, header, LABELS_CELLS)
    assert _oracle_trace_numeric_failures(element, _table_nodes(), [record]) == ("e1:header:2024",)


def test_oracle_trace_reports_a_header_number_missing_from_the_header_line():
    # The header line lost the spanning 2025 and the body carries it instead. Header-zone
    # occurrences justify header-line copies only, so the body's 2025 is untraceable;
    # without accounting it would trace to the header cell.
    header = "| Metric | Actual | Budget |"
    element = _table_element(header, "| Revenue 2025 | 100 | 200 |")
    record = _record(element.content, header, LABELS_CELLS)
    assert _oracle_trace_numeric_failures(element, _table_nodes()) == ()
    assert _oracle_trace_numeric_failures(element, _table_nodes(), [record]) == ("e1:2025",)


def test_oracle_trace_does_not_excuse_a_body_number_by_header_capacity():
    # The lower 2025 equals the one above it, so R6 writes it once: the header zone holds
    # one 2025 more than the header line uses. That surplus never covers a body 2025.
    html = ("<table><tr><th>Metric</th><th>2025</th></tr><tr><th></th><th>2025</th></tr>"
            "<tr><td>Revenue</td><td>100</td></tr></table>")
    header = "| Metric | 2025 |"
    element = _table_element(header, "| Revenue | 100 2025 |", separator="| --- | --- |")
    record = _record(element.content, header, (("Metric", 1), ("2025", 1), ("2025", 1)))
    nodes = [BeautifulSoup(html, "lxml").find("table")]
    assert _oracle_trace_numeric_failures(element, nodes) == ()
    assert _oracle_trace_numeric_failures(element, nodes, [record]) == ("e1:2025",)


def test_oracle_trace_fails_astras_counterexample():
    # A spanning 2025 over a lower 2025 and Budget, with the body mutated to
    # "Revenue | 100 2025 | 200": the header line is within capacity, the body's 2025 is not.
    element = _table_element(EQUAL_HEADER, "| Revenue | 100 2025 | 200 |")
    record = _record(element.content, EQUAL_HEADER, EQUAL_CELLS)
    assert _oracle_trace_numeric_failures(element, _table_nodes(lower="2025"), [record]) == ("e1:2025",)
    faithful = _table_element(EQUAL_HEADER)
    assert _oracle_trace_numeric_failures(
        faithful, _table_nodes(lower="2025"), [_record(faithful.content, EQUAL_HEADER, EQUAL_CELLS)]
    ) == ()


@pytest.mark.parametrize("segment, header_line", [
    pytest.param(f"{LABELS_HEADER}\n|---|---|---|\n| Revenue | 100 | 200 |", LABELS_HEADER, id="segment-not-found"),
    pytest.param(None, "| Metric | 2025 | 2025 |", id="first-line-differs"),
])
def test_oracle_trace_without_a_located_header_line_keeps_the_ordinary_trace(segment, header_line):
    element = _table_element(LABELS_HEADER)
    record = _record(segment or element.content, header_line, LABELS_CELLS)
    ordinary = _oracle_trace_numeric_failures(element, _table_nodes())
    assert ordinary == ("e1:2025",)
    assert _oracle_trace_numeric_failures(element, _table_nodes(), [record]) == ordinary


def test_oracle_trace_consumes_each_header_line_once():
    # Two records claiming the same line (identical segments) are located for neither.
    element = _table_element(LABELS_HEADER)
    record = _record(element.content, LABELS_HEADER, LABELS_CELLS)
    assert _oracle_trace_numeric_failures(element, _table_nodes(), [record, record]) == ("e1:2025",)


def test_oracle_header_accounting_uses_the_harness_tokenizer():
    # nvda-2002's restated-year header: the harness reads "see Note 2)" as 2, strict reads
    # nothing. A capacity in strict's tokens would make each repeated 2 a header excess.
    from sec2md.quality import _normalized_numbers

    html = ('<table><tr><td></td><td>January 27, 2002</td><td>January 28, 2001</td></tr>'
            '<tr><td></td><td colspan="2">(As restated – see Note 2)</td></tr>'
            "<tr><td>Cash</td><td>100</td><td>90</td></tr></table>")
    header = ("|  | January 27, 2002 — (As restated – see Note 2) | "
              "January 28, 2001 — (As restated – see Note 2) |")
    element = _table_element(header, "| Cash | 100 | 90 |")
    cells = (("January 27, 2002", 1), ("January 28, 2001", 1), ("(As restated – see Note 2)", 2))
    nodes = [BeautifulSoup(html, "lxml").find("table")]
    assert _normalized_numbers("(As restated – see Note 2)") == ()
    assert normalize_numbers("(As restated – see Note 2)") == ["2"]
    assert _oracle_trace_numeric_failures(element, nodes) == ("e1:2",)
    assert _oracle_trace_numeric_failures(element, nodes, [_record(element.content, header, cells)]) == ()


@pytest.mark.parametrize("top", ["2025", '<a href="#fy2025">2025</a>'], ids=["plain", "links"])
def test_audit_trace_reads_the_parsers_header_records(top):
    source = f"<html><body>{R6A_TABLE.format(top=top, lower='Actual')}</body></html>".encode()
    contract = replace(load_fixture("nvda-2026-08-26-8k")[0], expected_sections=(), representative_rows=())
    assert audit_document(source, contract, quality_policy="strict").trace_failures == ()
    _, _, annotated_html, pages, _, header_records = _parse_document(source)
    (element,) = pages[0].elements
    assert [record.header_line for record in header_records[element.id]] == [LABELS_HEADER]
    _, ordinary, _ = _mapping_and_trace(pages, annotated_html)
    assert ordinary == (f"{element.id}:2025",)


# Revision 18 (C2): a table rendered inside a list item or an inline wrapper shares its first
# line with the wrapper's leading content and its last line with trailing content.
LABELS_SEGMENT = f"{LABELS_HEADER}\n| --- | --- | --- |\n| Revenue | 100 | 200 |"


def test_oracle_locates_a_wrapped_record_with_a_prefix_and_a_suffix():
    element = Element(id="e1", content=f"Intro.\n\n**{LABELS_SEGMENT}**", kind="table", page_start=1, page_end=1)
    record = replace(_record(LABELS_SEGMENT, LABELS_HEADER, LABELS_CELLS), wrapped=True)
    assert _oracle_trace_numeric_failures(element, _table_nodes(), [record]) == ()
    # A record that is not wrapped keeps whole-line semantics: no location, the ordinary trace.
    unwrapped = replace(record, wrapped=False)
    assert _oracle_trace_numeric_failures(element, _table_nodes(), [unwrapped]) == ("e1:2025",)


def test_oracle_trace_of_a_wrapped_segment_occurring_twice_is_the_ordinary_trace():
    element = Element(id="e1", content=f"**{LABELS_SEGMENT} {LABELS_SEGMENT}**", kind="table",
                      page_start=1, page_end=1)
    record = replace(_record(LABELS_SEGMENT, LABELS_HEADER, LABELS_CELLS), wrapped=True)
    nodes = _table_nodes() + _table_nodes()
    ordinary = _oracle_trace_numeric_failures(element, nodes)
    assert ordinary == ("e1:2025",) * 2
    assert _oracle_trace_numeric_failures(element, nodes, [record]) == ordinary
    # A segment without a second line is never located.
    single = replace(record, segment=LABELS_HEADER)
    alone = Element(id="e1", content=f"**{LABELS_SEGMENT}**", kind="table", page_start=1, page_end=1)
    assert _oracle_trace_numeric_failures(alone, _table_nodes(), [single]) == ("e1:2025",)


@pytest.mark.parametrize("wrapper", [
    pytest.param("<ul><li>{}</li></ul>", id="list-item"),
    pytest.param("<b>{}</b>", id="bold"),
    pytest.param("<p><b>Intro</b><b>{}</b></p>", id="merged-bold-runs"),
])
@pytest.mark.parametrize("top", ["2025", '<a href="#fy2025">2025</a>'], ids=["plain", "links"])
def test_audit_trace_locates_a_wrapped_table_as_production_does(wrapper, top):
    table = R6A_TABLE.format(top=top, lower="Actual")
    source = f"<html><body><p>Intro.</p>{wrapper.format(table)}</body></html>".encode()
    contract = replace(load_fixture("nvda-2026-08-26-8k")[0], expected_sections=(), representative_rows=())
    # Strict (production's trace) passes, and so does the harness's own trace.
    assert audit_document(source, contract, quality_policy="strict").trace_failures == ()
    _, _, annotated_html, pages, diagnostics, header_records = _parse_document(source)
    (element,) = pages[0].elements
    (record,) = header_records[element.id]
    assert record.wrapped and record.header_line == LABELS_HEADER
    assert diagnostics.trace_numeric_failures == ()
    _, ordinary, _ = _mapping_and_trace(pages, annotated_html)
    assert ordinary == (f"{element.id}:2025",)


# --- Financial rows: header rows as R6 renders them (spec 2026-10-05) ---------------------

FUSED_HEADER_MARKDOWN = (
    "|  | Fiscal Year Ended — 2025 — As restated, see Note 2 | Fiscal Year Ended — 2024 — As restated, see Note 2 |\n"
    "| --- | --- | --- |\n"
    "| Total revenue | 100 | 90 |"
)


def test_extract_header_lines_reads_the_line_before_each_delimiter_row():
    markdown = f"Intro 2023 text.\n\n{FUSED_HEADER_MARKDOWN}\n\n| A b | 1 |\n| --- | --- |\n| C d | 2 |"
    assert extract_header_lines(markdown) == [
        ("| Fiscal Year Ended — 2025 — As restated, see Note 2 | Fiscal Year Ended — 2024 — As restated, see Note 2",
         ("2025", "2", "2024", "2")),
        ("A b | 1", ("1",)),
    ]


def test_financial_row_recall_credits_source_header_rows_fused_into_a_header_line():
    source = [
        ("Fiscal Year Ended", ("2025", "2024")),
        ("As restated, see Note 2", ("2", "2")),
        ("Total revenue", ("100", "90")),
    ]
    actual = extract_financial_rows(FUSED_HEADER_MARKDOWN)
    assert _financial_row_recall(source, actual) == pytest.approx(1 / 3)
    assert _financial_row_recall(source, actual, extract_header_lines(FUSED_HEADER_MARKDOWN)) == 1.0


def test_financial_row_recall_needs_every_number_of_the_row_in_one_header_line():
    header_lines = extract_header_lines(FUSED_HEADER_MARKDOWN)
    assert _financial_row_recall([("Fiscal Year Ended", ("2025", "2024", "2023"))], [], header_lines) == 0.0
    assert _financial_row_recall([("As restated, see Note 2", ("2", "2", "2"))], [], header_lines) == 0.0
    # Label text and numbers must come from the same header line.
    other = extract_header_lines("| Fiscal Year Ended | Q1 |\n| --- | --- |\n| A b | 1 |\n\n"
                                 "| Item | 2025 | 2024 |\n| --- | --- | --- |\n| C d | 2 | 3 |")
    assert _financial_row_recall([("Fiscal Year Ended", ("2025", "2024"))], [], other) == 0.0


def test_financial_row_recall_still_matches_body_rows_exactly():
    source = [("Total revenue", ("100", "90"))]
    assert _financial_row_recall(source, extract_financial_rows(FUSED_HEADER_MARKDOWN),
                                 extract_header_lines(FUSED_HEADER_MARKDOWN)) == 1.0
    # A body line is never searched for label text: only exact labels match there.
    restated = "| Item | A | B |\n| --- | --- | --- |\n| Total revenue, restated | 100 | 90 |"
    assert _financial_row_recall(source, extract_financial_rows(restated), extract_header_lines(restated)) == 0.0


# --- Body rows must not drop (spec 2026-10-05, Acceptance) --------------------------------

BODY_ROW_BASELINE = Path(__file__).with_name("body_rows_main.json")

# Source rows that main (c674828) rendered as body rows and the candidate writes into the
# header line instead (spec revision 11: the guard covers every source row with visible
# text). Each is an R0 header-zone row (checked below) that main's row-0 header left in its
# body; the test fails on any other lost body row and on a listed move that stops moving.
# Revision 12 adds 25: the ex99s' stacked titles, captions and date rows (label-only rows
# continue the zone, 17 rows), and 8 "Inventories: | (In millions)"-style rows that R0's
# sparse-row fusion keeps in the zone on the source grid (its 5 columns with origin text;
# main counted its 3 merged columns and did not fuse them).
# Rows are counted per text signature, as the baseline counts them (body_matched_rows). A row
# that main already wrote in a header line, or fused into another line, is not a move, even
# when another row with the same text was one of main's body rows: of nvda-2026-10k's five
# "Jan 25, 2026" rows only those in tables 47 and 49 were, of nvda-2002-10k's five model-table
# heading rows only the three repeated mid-table, and ex99-1's table 3 "Three Months Ended"
# and "July 26," rows were not.
# 165 moves: nvda-2026-10k 48, nvda-2002-10k 41, nvda-2026-q2-10q 38, nvda-2026-ex99-1 24
# and nvda-2026-ex99-2 14.
HEADER_ZONE_MOVES = {
    "nvda-2026-10k": (
        SourceRow(5, 2, ("Part I",)),
        SourceRow(9, 4, ("($ in millions, except per share data)",)),
        SourceRow(11, 4, ("($ in millions)",)),
        SourceRow(12, 4, ("($ in millions)",)),
        SourceRow(13, 4, ("($ in millions)",)),
        SourceRow(14, 4, ("($ in millions)",)),
        SourceRow(15, 3, ("(In millions)",)),
        SourceRow(16, 4, ("(In millions)",)),
        SourceRow(17, 3, ("(In millions)",)),
        SourceRow(23, 2, ("Shares", "Amount", "Capital", "Income (Loss)", "Earnings", "Equity")),
        SourceRow(25, 4, ("(In millions)",)),
        SourceRow(26, 4, ("(In millions, except per share data)",)),
        SourceRow(27, 4, ("(Using the Black-Scholes model)",)),
        SourceRow(28, 4, ("(In millions, except per share data)",)),
        SourceRow(29, 4, ("(In millions, except per share data)",)),
        SourceRow(30, 4, ("(In millions)",)),
        SourceRow(31, 2, ("(In millions)",)),
        SourceRow(32, 3, ("Cash Equivalents", "Marketable Securities", "Other Assets")),
        SourceRow(32, 5, ("(In millions)",)),
        SourceRow(33, 3, ("Cash Equivalents", "Marketable Securities")),
        SourceRow(33, 5, ("(In millions)",)),
        SourceRow(34, 3, (
            "Estimated Fair Value",
            "Gross Unrealized Loss",
            "Estimated Fair Value",
            "Gross Unrealized Loss",
        )),
        SourceRow(34, 5, ("(In millions)",)),
        SourceRow(35, 3, ("(In millions)",)),
        SourceRow(36, 4, ("(In millions)",)),
        SourceRow(37, 2, ("Inventories:", "(In millions)")),
        SourceRow(38, 3, ("Property and Equipment:", "(In millions)", "(In years)")),
        SourceRow(39, 3, ("Accrued and Other Current Liabilities:", "(In millions)")),
        SourceRow(40, 3, ("Other Long-Term Liabilities:", "(In millions)")),
        SourceRow(41, 3, ("(In millions)",)),
        SourceRow(42, 3, ("(In millions)",)),
        SourceRow(43, 3, ("(In millions)",)),
        SourceRow(44, 3, ("(In millions)",)),
        SourceRow(45, 4, ("(In millions)",)),
        SourceRow(46, 4, ("(In millions)",)),
        SourceRow(47, 2, ("Jan 25, 2026",)),
        SourceRow(47, 4, ("(In millions, except percentages)",)),
        SourceRow(48, 3, ("(In millions, except percentages)",)),
        SourceRow(49, 2, ("Jan 25, 2026",)),
        SourceRow(49, 4, ("(In millions)",)),
        SourceRow(50, 3, ("(In millions)",)),
        SourceRow(51, 3, ("(In millions)",)),
        SourceRow(52, 3, ("(In millions)",)),
        SourceRow(53, 4, ("(In millions)",)),
        SourceRow(56, 3, ("Long-lived assets:", "(In millions)")),
        SourceRow(57, 2, ("(In millions)",)),
        SourceRow(58, 4, ("(In millions)",)),
        SourceRow(59, 3, ("(In millions)",)),
    ),
    "nvda-2002-10k": (
        SourceRow(18, 1, (
            "January 27, 2002",
            "January 28, 2001",
            "January 30, 2000",
            "January 31, 1999",
        )),
        SourceRow(18, 2, ("(in thousands, except per share data)",)),
        SourceRow(18, 3, ("(As restated\u2013 See Note 2)", "(As restated\u2013 See Note 2)")),
        SourceRow(19, 2, ("(As restated \u2013 see Note 2)", "(As restated \u2013 see Note 2)")),
        SourceRow(21, 1, ("(As restated \u2013see Note 2)", "(As restated \u2013see Note 2)")),
        SourceRow(22, 1, ("(in thousands)",)),
        SourceRow(128, 1, ("(As restated \u2013see Note 2)",)),
        SourceRow(129, 1, ("(As restated \u2013see Note 2)", "(As restated \u2013see Note 2)")),
        SourceRow(130, 1, ("Common Stock",)),
        SourceRow(130, 2, ("Shares", "Amount")),
        SourceRow(132, 1, ("(As restated \u2013 see Note 2)", "(As restated \u2013see Note 2)")),
        SourceRow(133, 1, ("(in thousands, except per share data)",)),
        SourceRow(137, 1, ("January 28, 2001", "January 30, 2000")),
        SourceRow(137, 2, (
            "As Restated",
            "As Previously Reported",
            "As Restated",
            "As Previously Reported",
        )),
        SourceRow(137, 3, ("(in thousands, except per share data)",)),
        SourceRow(138, 2, ("(in thousands, except share data)",)),
        SourceRow(139, 1, ("(in thousands)", "(years)")),
        SourceRow(140, 2, ("(As Restated)", "(As Restated)")),
        SourceRow(140, 3, ("(in thousands, except per share data)",)),
        SourceRow(141, 1, ("(in thousands)",)),
        SourceRow(142, 1, ("(in thousands)",)),
        SourceRow(143, 2, ("(As restated \u2013see Note 2)",)),
        SourceRow(143, 3, ("(in thousands)",)),
        SourceRow(144, 2, ("(in thousands)",)),
        SourceRow(145, 2, ("(As restated \u2013 see Note 2)",)),
        SourceRow(145, 3, ("(in thousands)",)),
        SourceRow(146, 1, ("(As Restated)", "(As Restated)")),
        SourceRow(146, 2, ("(in thousands, except per share data)",)),
        SourceRow(151, 1, ("(in thousands)",)),
        SourceRow(152, 1, ("(in thousands)",)),
        SourceRow(153, 1, ("(As Restated)", "(As Restated)")),
        SourceRow(153, 2, ("(in thousands)",)),
        SourceRow(154, 1, ("(As Restated)", "(As Restated)")),
        SourceRow(154, 2, ("(in thousands)",)),
        SourceRow(155, 1, ("(As Restated)", "(As Restated)")),
        SourceRow(155, 2, ("(in thousands)",)),
        SourceRow(156, 1, ("(in thousands)",)),
        SourceRow(157, 2, ("(in thousands)",)),
        SourceRow(158, 2, ("(in thousands)",)),
        SourceRow(162, 3, (
            "As Restated",
            "As Reported",
            "As Restated",
            "As Reported",
            "As Restated",
            "As Reported",
            "As Restated",
            "As Reported",
        )),
        SourceRow(162, 4, ("(in thousands, except per share data)",)),
    ),
    "nvda-2026-q2-10q": (
        SourceRow(6, 2, ("Part I . Financial Information",)),
        SourceRow(10, 2, ("Shares", "Amount")),
        SourceRow(11, 2, ("Shares", "Amount")),
        SourceRow(13, 4, ("(In millions)",)),
        SourceRow(14, 4, ("(In millions, except per share data)",)),
        SourceRow(15, 4, ("(In millions, except per share data)",)),
        SourceRow(16, 4, ("(In millions)",)),
        SourceRow(17, 2, ("(In millions)",)),
        SourceRow(18, 3, (
            "Cash Equivalents",
            "Marketable Debt Securities",
            "Marketable Equity Securities",
            "Other Assets",
        )),
        SourceRow(18, 5, ("(In millions)",)),
        SourceRow(19, 3, (
            "Cash Equivalents",
            "Marketable Debt Securities",
            "Marketable Equity Securities",
            "Other Assets",
        )),
        SourceRow(19, 5, ("(In millions)",)),
        SourceRow(20, 4, ("(In millions)",)),
        SourceRow(21, 3, ("Inventories:", "(In millions)")),
        SourceRow(22, 3, ("Accrued and Other Current Liabilities:", "(In millions)")),
        SourceRow(23, 3, ("Other Long-Term Liabilities:", "(In millions)")),
        SourceRow(24, 4, ("(In millions)",)),
        SourceRow(25, 4, ("(In millions)",)),
        SourceRow(26, 3, ("(In millions)",)),
        SourceRow(27, 4, ("(In millions)",)),
        SourceRow(28, 3, ("(In billions)",)),
        SourceRow(29, 3, ("(In billions)",)),
        SourceRow(31, 3, ("(In millions)",)),
        SourceRow(32, 3, ("(In millions)",)),
        SourceRow(33, 4, ("(In millions)",)),
        SourceRow(34, 4, ("(In millions)",)),
        SourceRow(35, 4, ("(In millions)",)),
        SourceRow(36, 2, ("(In millions)",)),
        SourceRow(37, 4, ("(In millions)",)),
        SourceRow(38, 4, ("($ in millions, except per share data)",)),
        SourceRow(39, 4, ("($ in millions)",)),
        SourceRow(41, 4, ("($ in millions)",)),
        SourceRow(42, 4, ("($ in millions)",)),
        SourceRow(43, 4, ("($ in millions)",)),
        SourceRow(44, 4, ("($ in millions)",)),
        SourceRow(45, 3, ("(In millions)",)),
        SourceRow(46, 4, ("(In millions)",)),
        SourceRow(47, 3, ("(In millions)",)),
    ),
    "nvda-2026-ex99-1": (
        SourceRow(3, 3, ("2026", "2025", "2026", "2025")),
        SourceRow(4, 2, ("CONDENSED CONSOLIDATED BALANCE SHEETS",)),
        SourceRow(4, 3, ("(In millions)",)),
        SourceRow(4, 4, ("(Unaudited)",)),
        SourceRow(4, 6, ("July 26,", "January 25,")),
        SourceRow(4, 7, ("2026", "2026")),
        SourceRow(5, 2, ("CONDENSED CONSOLIDATED STATEMENTS OF CASH FLOWS",)),
        SourceRow(5, 3, ("(In millions)",)),
        SourceRow(5, 4, ("(Unaudited)",)),
        SourceRow(5, 5, ("Three Months Ended", "Six Months Ended")),
        SourceRow(5, 6, ("July 26,", "July 27,", "July 26,", "July 27,")),
        SourceRow(5, 7, ("2026", "2025", "2026", "2025")),
        SourceRow(7, 2, ("RECONCILIATION OF GAAP TO NON-GAAP FINANCIAL MEASURES",)),
        SourceRow(7, 3, ("($ In millions, except per share data)",)),
        SourceRow(7, 4, ("(Unaudited)",)),
        SourceRow(7, 6, ("Three Months Ended", "Six Months Ended")),
        SourceRow(7, 7, ("July 26,", "April 26,", "July 27,", "July 26,", "July 27,")),
        SourceRow(7, 8, ("2026", "2026", "2025", "2026", "2025")),
        SourceRow(9, 2, ("Three Months Ended", "Six Months Ended")),
        SourceRow(9, 3, ("July 26,", "April 26,", "July 27,", "July 26,", "July 27,")),
        SourceRow(9, 4, ("2026", "2026", "2025", "2026", "2025")),
        SourceRow(10, 2, ("RECONCILIATION OF GAAP TO NON-GAAP OUTLOOK",)),
        SourceRow(10, 4, ("Q3 FY2027 Outlook",)),
        SourceRow(10, 5, ("($ in billions)",)),
    ),
    "nvda-2026-ex99-2": (
        SourceRow(4, 3, ("(In billions)",)),
        SourceRow(5, 3, ("(In billions)",)),
        SourceRow(8, 2, ("RECONCILIATION OF GAAP TO NON-GAAP FINANCIAL MEASURES",)),
        SourceRow(8, 3, ("($ In millions, except per share data)",)),
        SourceRow(8, 4, ("(Unaudited)",)),
        SourceRow(8, 6, ("Three Months Ended", "Six Months Ended")),
        SourceRow(8, 7, ("July 26,", "April 26,", "July 27,", "July 26,", "July 27,")),
        SourceRow(8, 8, ("2026", "2026", "2025", "2026", "2025")),
        SourceRow(10, 2, ("Three Months Ended", "Six Months Ended")),
        SourceRow(10, 3, ("July 26,", "April 26,", "July 27,", "July 26,", "July 27,")),
        SourceRow(10, 4, ("2026", "2026", "2025", "2026", "2025")),
        SourceRow(11, 2, ("RECONCILIATION OF GAAP TO NON-GAAP OUTLOOK",)),
        SourceRow(11, 4, ("Q3 FY2027 Outlook",)),
        SourceRow(11, 5, ("($ in billions)",)),
    ),
}


@lru_cache(maxsize=None)
def _body_row_baseline() -> dict[str, frozenset[SourceRow]]:
    raw = json.loads(BODY_ROW_BASELINE.read_text(encoding="utf-8"))
    assert raw["commit"] == "c674828"
    return {
        fixture_id: frozenset(SourceRow(table, row, tuple(cells)) for table, row, cells in rows)
        for fixture_id, rows in raw["fixtures"].items()
    }


@lru_cache(maxsize=None)
def _candidate_markdown(fixture_id: str) -> str:
    return _parse_once(load_fixture(fixture_id)[1])[0]


def test_body_row_baseline_covers_every_fixture_with_current_source_rows():
    baseline = _body_row_baseline()
    assert set(baseline) == set(FIXTURE_IDS)
    for fixture_id, rows in baseline.items():
        assert rows <= set(text_source_rows(load_fixture(fixture_id)[1])), fixture_id


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_body_rows_matched_by_main_stay_body_rows(fixture_id):
    # Rows are counted per signature, so a moved row is never masked by an identical body
    # row elsewhere in the document; each lost count must be a listed header-zone move.
    _, source = load_fixture(fixture_id)
    main = Counter(row.key for row in _body_row_baseline()[fixture_id])
    candidate = Counter(row.key for row in body_matched_rows(source, _candidate_markdown(fixture_id)))
    assert main - candidate == Counter(row.key for row in HEADER_ZONE_MOVES.get(fixture_id, ()))


@pytest.mark.parametrize("fixture_id", sorted(HEADER_ZONE_MOVES))
def test_header_zone_moves_are_r0_header_rows_written_in_the_header_line(fixture_id):
    _, source = load_fixture(fixture_id)
    tables = source_soup(source).find_all("table")
    markdown = _candidate_markdown(fixture_id)
    for row in HEADER_ZONE_MOVES[fixture_id]:
        table = tables[row.table]
        cells = {id(cell) for cell in table.find_all("tr")[row.row].find_all(["td", "th"])}
        renderer = TableParser(table)
        (grid_row,) = [
            index for index, slots in enumerate(renderer.source_grid)
            if any(slot is not None and not slot.is_spanning and id(slot.cell.node) in cells for slot in slots)
        ]
        assert renderer.roles.role(grid_row) == "header", row
        assert _in_header_line_cells(row.cells, markdown), row


SECURITIES_SOURCE = (
    b"<table><tr><td>Title of each class</td><td>Trading symbol(s)</td></tr>"
    b"<tr><td>Common Stock</td><td>AAPL</td></tr>"
    b"<tr><td>1.375% Notes due 2024</td><td>\xe2\x80\x94</td></tr></table>"
)


def test_text_source_rows_cover_every_row_with_visible_text():
    source = (
        b"<table><tr><td>Title</td><td><a href='x.htm'>Symbol</a></td></tr>"
        b"<tr><td></td><td></td></tr>"
        b"<tr><td>Common Stock</td><td>\xe2\x80\x8bAAPL</td><td><img src='x.png'></td></tr>"
        b"<tr style='display:none'><td>Draft</td><td>DRFT</td></tr>"
        b"<tr><td>Preferred</td><td style='display:none'>Hidden</td><td>PRF</td></tr>"
        b"<tr><td>Single cell</td></tr></table>"
    )
    assert text_source_rows(source) == (
        SourceRow(0, 0, ("Title", "Symbol")),
        SourceRow(0, 2, ("Common Stock", "AAPL", "\u25cf")),
        SourceRow(0, 4, ("Preferred", "PRF")),
        SourceRow(0, 5, ("Single cell",)),
    )


def test_body_matched_rows_cover_text_rows_and_leave_out_header_lines():
    main = ("| Title of each class | Trading symbol(s) |\n| --- | --- |\n"
            "| Common Stock | AAPL |\n| 1.375% Notes due 2024 | \u2014 |")
    assert [row.row for row in body_matched_rows(SECURITIES_SOURCE, main)] == [1, 2]
    # Round 1's S1 promotion: the security row moved into the header line is not body-matched.
    promoted = ("| Title of each class \u2014 Common Stock | Trading symbol(s) \u2014 AAPL |\n| --- | --- |\n"
                "| 1.375% Notes due 2024 | \u2014 |")
    assert [row.row for row in body_matched_rows(SECURITIES_SOURCE, promoted)] == [2]
    assert _in_header_line_cells(("Common Stock", "AAPL"), promoted)
    assert not _in_header_line_cells(("Common Stock", "AAPL"), main)


def test_body_matched_rows_count_rows_that_share_a_signature():
    source = (b"<table><tr><td></td><td>2025</td></tr><tr><td>Total</td><td>5</td></tr></table>"
              b"<table><tr><td></td><td>2025</td></tr><tr><td>Total</td><td>5</td></tr></table>")
    both = ("|  | 2025 |\n| --- | --- |\n| Total | 5 |\n\n"
            "|  | 2025 |\n| --- | --- |\n| Total | 5 |")
    assert [(row.table, row.row) for row in body_matched_rows(source, both)] == [(0, 1), (1, 1)]
    # One of the two identical rows moved into a header line: one match is lost, not masked.
    moved = ("|  | 2025 — Total |\n| --- | --- |\n|  | 5 |\n\n"
             "|  | 2025 |\n| --- | --- |\n| Total | 5 |")
    assert [(row.table, row.row) for row in body_matched_rows(source, moved)] == [(0, 1)]


def test_body_row_signatures_ignore_cell_boundaries_whitespace_links_and_escapes():
    source = (
        b"<table><tr><td>Item</td><td>2025</td></tr>"
        b"<tr><td>Net  loss</td><td>$</td><td>(29</td><td>)</td></tr>"
        b"<tr><td><a href='n.htm'>Note A|B</a></td><td>12</td></tr></table>"
    )
    markdown = ("| Item | 2025 |\n| --- | --- |\n| Net loss | $ (29) |\n"
                "| [Note A\\|B](https://example.com/n.htm) | 12 |")
    assert [row.row for row in body_matched_rows(source, markdown)] == [1, 2]
    assert body_line_counts(markdown) == Counter({"Netloss$(29)": 1, "NoteA|B12": 1})
    # Text changes are not matches: a lost value or a changed label.
    changed = markdown.replace("$ (29)", "$").replace("Note A", "Note C")
    assert body_matched_rows(source, changed) == ()


# --- Numeric recall counts content, not furniture (recall audit 2026-10-06) ---------------
# The branch's remaining numeric-recall gap on the recent fixtures was all metric artefacts:
# the <head> title (a file name), page footers the parser strips on purpose, and numbers
# split across consecutive links to one target. Link destinations and image markup in the
# output could also hide a future loss.


def _visible(html: str) -> str:
    return _visible_text(source_soup(html.encode()))


AFTER_BREAK = '<hr style="page-break-after:always"/>'
BODIES = ("Net sales 383,285", "Gross margin 169,148", "Operating income 114,301")
BODY_NUMBERS = ["383285", "169148", "114301"]


def _workiva_footer(text) -> str:
    """A page footer as Workiva writes it (aapl, nvda): a box at the bottom of the page."""

    return ('<div style="height:42.75pt;position:relative;width:100%">'
            '<div style="bottom:0;position:absolute;width:100%">'
            f'<div style="text-align:center"><span>{text}</span></div></div></div>')


def _pages(pages, separator: str = AFTER_BREAK, head: str = "") -> str:
    return f"<html><head>{head}</head><body>{separator.join(pages)}</body></html>"


def _footed(footer) -> str:
    """BODIES on three pages, each closed by footer(page number)."""

    return _pages([f"<p>{body}</p>{footer(number)}" for number, body in enumerate(BODIES, 1)])


def _legacy_footed(bodies=BODIES, footer: str = "{}") -> str:
    """nvda-2002's shape: a right-aligned page number (footer.format(number)), the next page
    opening with a page-break-before paragraph."""

    pages = []
    for number, body in enumerate(bodies, 1):
        style = ' style="page-break-before:always"' if number > 1 else ""
        pages.append(f'<p{style}>{body}</p><div align="right"><font size="2">'
                     f'{footer.format(number)}</font></div>')
    return _pages(pages, separator="")


def test_visible_text_leaves_out_the_head():
    # The <title> names the file (aapl-20230930); no browser draws it on the page.
    html = _pages(["<p>Total net sales 383,285</p>"], head="<title>aapl-20230930</title>")
    assert _visible(html) == "Total net sales 383,285"


@pytest.mark.parametrize("html", [
    pytest.param(_footed(lambda n: _workiva_footer(f"Apple Inc. | 2023 Form 10-K | {n}")),
                 id="running-line"),
    pytest.param(_footed(lambda n: _workiva_footer(n + 1)), id="page-number"),
    pytest.param(_legacy_footed(), id="legacy-page-number"),
    pytest.param(_pages([f'<div style="page-break-after:always"><p>{body}</p><p>{n}</p></div>'
                         for n, body in enumerate(BODIES, 1)], separator=""),
                 id="break-after-content"),
])
def test_visible_text_leaves_out_page_footers(html):
    assert normalize_numbers(_visible(html)) == BODY_NUMBERS


@pytest.mark.parametrize("html", [
    pytest.param(_pages([f"<p>{BODIES[0]}</p>{_workiva_footer(1)}", f"<p>{BODIES[1]}</p>",
                         f"<p>{BODIES[2]}</p>{_workiva_footer(3)}"]), id="page-without-footer"),
    pytest.param(_pages([f"<p>{BODIES[0]}</p>{_workiva_footer(1)}", "",
                         f"<p>{BODIES[1]}</p>{_workiva_footer(3)}",
                         f"<p>{BODIES[2]}</p>{_workiva_footer(4)}"]), id="blank-page"),
    # One physical break written twice: an after-break rule, then a before-break page.
    pytest.param(_pages([f"<p>{BODIES[0]}</p>{_workiva_footer('Acme | 1')}"] + [
        f'<div style="page-break-before:always"><p>{body}</p>{_workiva_footer(f"Acme | {n}")}</div>'
        for n, body in enumerate(BODIES[1:], 2)]), id="one-break-written-twice"),
])
def test_page_numbers_keep_step_with_pages_without_a_footer(html):
    # Page number minus page-end ordinal stays constant across a page with no footer, across
    # a page with no text at all, and across one break that two elements both declare.
    assert normalize_numbers(_visible(html)) == BODY_NUMBERS


def test_page_ends_follow_document_order():
    # A before-break nested inside an after-break element ends its page first.
    soup = source_soup(b'<html><body><p>A 1</p><div style="page-break-after:always"><p>B 2</p>'
                       b'<p style="page-break-before:always">C 3</p></div><p>D 4</p></body></html>')
    visible = [node for node in soup.strings if node.strip()]
    assert [str(node) for node in _oracle_page_ends(soup, visible)] == ["B 2", "C 3", "D 4"]


@pytest.mark.parametrize("html", [
    pytest.param(_footed(lambda n: f"<table><tr><td>Page</td><td>{n}</td></tr></table>"),
                 id="in-a-table"),
    pytest.param(_footed(lambda n: f"<p>See Note {(12, 7, 9)[n - 1]}</p>"),
                 id="numbers-not-increasing"),
    pytest.param(_pages([f"<p>{BODIES[0]}</p><p>Acme | 1</p>", f"<p>{BODIES[1]}</p><p>Acme | 2</p>",
                         f"<p>{BODIES[2]}</p>", "<p>Net income 96,995</p>",
                         "<p>Total assets 352,583</p>"]),
                 id="under-half-of-the-pages"),
    pytest.param(_footed(lambda n: f"<p>{n} units</p>"), id="number-not-last"),
    pytest.param(_footed(lambda n: f"<div><p>Revenue grew</p>{n}</div>"), id="closing-block-holds-more"),
    pytest.param(_pages([f"<p>{BODIES[0]}</p><p>7</p>"]), id="single-page"),
    # A page number stands alone or after whitespace: never the tail of a longer number.
    pytest.param(_footed(lambda n: f"<p>Total 1,00{n}</p>"), id="thousands-tail"),
    pytest.param(_footed(lambda n: f"<p>Rate 1.{n}</p>"), id="decimal-tail"),
    pytest.param(_footed(lambda n: f"<p>{12340 + n}</p>"), id="five-digit-tail"),
    # Page numbers advance with the pages: page number minus page-end ordinal is constant.
    pytest.param(_footed(lambda n: f"<p>{(1, 2, 9)[n - 1]}</p>"), id="numbers-skip"),
    pytest.param(_footed(lambda n: f"<p>{(150, 275, 390)[n - 1]}</p>"), id="body-values"),
    # A year series closing consecutive pages advances with them, but its offset (page
    # number minus page-end ordinal) is far beyond any page of the document.
    pytest.param(_footed(lambda n: f"<p>Fiscal {2023 + n}</p>"), id="fiscal-years"),
    pytest.param(_footed(lambda n: f"<p>{2023 + n}</p>"), id="bare-years"),
    # A tagged XBRL fact is content.
    pytest.param(_footed(lambda n: f'<p><ix:nonFraction name="us-gaap:Shares">{n}</ix:nonFraction></p>'),
                 id="xbrl-fact"),
])
def test_visible_text_keeps_page_end_lines_that_are_not_page_furniture(html):
    assert _visible(html) == BeautifulSoup(html, "lxml").get_text(" ", strip=True)


def test_visible_text_joins_a_number_split_across_consecutive_links_to_one_target():
    # nvda-2026-10k's Item 15 index and the 8-K's exhibit table write one date as several
    # links to one target; a reader sees "January 25, 2026" and "August 26, 2026".
    index = "".join(f'<a href="#fs">{part}</a>'
                    for part in ("Statements for January 2", "5", ", 202", "6"))
    exhibit = "".join(f'<a href="q2.htm">{part}</a>' for part in ("Augu", "st ", "2", "6", ", 2026"))
    wrapped = ('<span><a href="#n">$ 1,23</a></span><span><a href="#n">4</a></span>'
               '<a href="#n">.5</a>')
    assert normalize_numbers(_visible(f"<p>{index}</p>")) == ["25", "2026"]
    assert normalize_numbers(_visible(f"<p>{exhibit}</p>")) == ["26", "2026"]
    assert normalize_numbers(_visible(f"<p>{wrapped}</p>")) == ["1234.5"]


@pytest.mark.parametrize("html, numbers", [
    pytest.param('<p><a href="#a">2</a><a href="#b">5</a></p>', ["2", "5"], id="different-targets"),
    pytest.param('<p><a href="#a">2</a> <a href="#a">5</a></p>', ["2", "5"], id="space-between"),
    pytest.param('<p><a href="#a">2 </a><a href="#a">5</a></p>', ["2", "5"], id="space-inside"),
    pytest.param('<p><a href="#a">2</a><br/><a href="#a">5</a></p>', ["2", "5"], id="line-break"),
    pytest.param('<div><div><a href="#a">2</a></div><a href="#a">5</a></div>', ["2", "5"],
                 id="block-boundary"),
    pytest.param('<table><tr><td><a href="#a">2</a></td><td><a href="#a">5</a></td></tr></table>',
                 ["2", "5"], id="table-cells"),
    pytest.param("<p><a>2</a><a>5</a></p>", ["2", "5"], id="no-target"),
    # Not every untagged boundary: a range dash must not turn 4.3 into a negative number.
    pytest.param("<p><span>3.5%-</span><span>4.3%</span></p>", ["3.5", "4.3"], id="untagged-range"),
    pytest.param('<p><a href="#a">3.5%-</a><a href="#a">4.3%</a></p>', ["3.5", "4.3"],
                 id="linked-range"),
])
def test_visible_text_joins_only_number_fragments_of_touching_same_target_links(html, numbers):
    assert normalize_numbers(_visible(html)) == numbers


def _audit_with_markdown(monkeypatch, source: bytes, markdown: str):
    """audit_document's measurements of a source, with the parser's Markdown replaced."""

    monkeypatch.setattr(
        metrics, "_parse_document", lambda raw: (markdown, *_parse_document(raw)[1:])
    )
    contract = replace(load_fixture("nvda-2026-08-26-8k")[0], expected_sections=(),
                       representative_rows=())
    return audit_document(source, contract, quality_policy="off")


def test_numeric_recall_counts_neither_title_nor_footers_nor_split_link_fragments(monkeypatch):
    split = "".join(f'<a href="#fs">{part}</a>' for part in ("January 2", "5", ", 202", "6"))
    pages = [f"<p>{body}</p>" for body in BODIES]
    pages[1] = f"<p>{BODIES[1]} {split}</p>"
    pages = [page + _workiva_footer(f"Acme Inc. | 2023 Form 10-K | {n}")
             for n, page in enumerate(pages, 1)]
    source = _pages(pages, head="<title>acme-20230930</title>").encode()
    markdown = f"{BODIES[0]}\n\n{BODIES[1]} [January 25, 2026](#fs)\n\n{BODIES[2]}"
    assert _audit_with_markdown(monkeypatch, source, markdown).numeric_recall == 1.0


def test_numeric_recall_does_not_let_kept_footer_lines_stand_in_for_lost_values(monkeypatch):
    # nvda-2002: the parser keeps the page numbers the harness leaves out of the source, as
    # lines of their own. One such line per footer leaves the output too, so a lost body
    # value with a page number's digits still counts as lost.
    bodies = ("Revenue grew 2%", BODIES[0], BODIES[1])
    source = _legacy_footed(bodies).encode()
    kept = "\n\n".join(f"{body}\n\n{number}" for number, body in enumerate(bodies, 1))
    assert _audit_with_markdown(monkeypatch, source, kept).numeric_recall == 1.0
    lost = kept.replace("grew 2%", "grew %")
    assert _audit_with_markdown(monkeypatch, source, lost).numeric_recall == pytest.approx(2 / 3)


def test_numeric_recall_counts_a_lost_year_line_closing_a_page(monkeypatch):
    # "Fiscal 2024 / 2025 / 2026" closing three consecutive pages is content, not a footer.
    source = _footed(lambda n: f"<p>Fiscal {2023 + n}</p>").encode()
    faithful = "\n\n".join(f"{body}\n\nFiscal {2023 + n}" for n, body in enumerate(BODIES, 1))
    assert _audit_with_markdown(monkeypatch, source, faithful).numeric_recall == 1.0
    lost = faithful.replace("Fiscal 2025", "Fiscal")
    assert _audit_with_markdown(monkeypatch, source, lost).numeric_recall == pytest.approx(5 / 6)


@pytest.mark.parametrize("footer, line", [
    pytest.param("<b>{}</b>", "**{}**", id="bold"),
    pytest.param("<i>{}</i>", "*{}*", id="italic"),
    pytest.param("<b>NVIDIA Corporation {}</b>", "**NVIDIA Corporation {}**", id="bold-running-text"),
    pytest.param("NVIDIA_Corp {}", "NVIDIA\\_Corp {}", id="escaped-running-text"),
])
def test_numeric_recall_drops_kept_footer_lines_whatever_their_emphasis(monkeypatch, footer, line):
    # A legacy page number the parser keeps as **2** or *2* is still the footer's line: it is
    # read without emphasis and escapes, so it never stands in for a lost body value.
    bodies = ("Revenue grew 2%", BODIES[0], BODIES[1])
    source = _legacy_footed(bodies, footer).encode()
    kept = "\n\n".join(f"{body}\n\n{line.format(n)}" for n, body in enumerate(bodies, 1))
    assert _audit_with_markdown(monkeypatch, source, kept).numeric_recall == 1.0
    lost = kept.replace("grew 2%", "grew %")
    assert _audit_with_markdown(monkeypatch, source, lost).numeric_recall == pytest.approx(2 / 3)


def test_numeric_recall_reads_link_labels_not_destinations_or_image_markup(monkeypatch):
    source = b"<html><body><p>Exhibit 99.1 lists 320193 shares and 1731 holders.</p></body></html>"
    # The output lost 320193 and 1731: only a link destination and an image's alt text hold them.
    lost = ("Exhibit [99.1](https://www.sec.gov/Archives/edgar/data/320193/x.htm) lists shares "
            "and ![1731](chart.jpg) holders.")
    result = _audit_with_markdown(monkeypatch, source, lost)
    assert result.numeric_recall == pytest.approx(1 / 3)
    assert result.word_recall == pytest.approx(7 / 9)
    faithful = "Exhibit [99.1](https://www.sec.gov/x.htm) lists 320193 shares and 1731 holders."
    assert _audit_with_markdown(monkeypatch, source, faithful).numeric_recall == 1.0
