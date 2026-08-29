import re
import warnings
from urllib.parse import urljoin

import pytest
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from sec2md.core import convert_to_markdown
from sec2md.encoding import decode_html, normalize_legacy_characters
from sec2md.models import Element, Page
from sec2md.parser import Parser
from sec2md.quality import ParseQualityError, normalize_numeric_token
from sec2md.table_parser import render_cell_content
from sec2md.utils import FetchedHtml

from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture
from tests.accuracy.metrics import (
    _financial_row_recall,
    _mapping_and_trace,
    _markdown_cells,
    _parse_once,
    audit_document,
    extract_financial_rows,
    multiset_recall,
    normalize_numbers,
    normalize_words,
)


_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\([^)]+\)")


def _strip_markdown_link_destinations(text: str) -> str:
    """Remove non-visible destinations while retaining rendered link labels."""

    return _MARKDOWN_LINK_RE.sub(r"\1", text)


def _link_aware_source_rows(source: bytes) -> list[tuple[str, tuple[str, ...]]]:
    """Use DOM-aware labels only for tables with split same-destination anchors."""

    decoded, _ = decode_html(source)
    source_text = normalize_legacy_characters(decoded)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(source_text, "lxml")

    rows: list[tuple[str, tuple[str, ...]]] = []
    for table in soup.find_all("table"):
        table_has_split_link = any(
            left.get("href")
            and left.get("href") == right.get("href")
            for cell in table.find_all(["td", "th"])
            for left, right in zip(cell.find_all("a"), cell.find_all("a")[1:])
        )
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            values = []
            for cell in cells:
                if table_has_split_link and cell.find("a"):
                    value = render_cell_content(cell)
                else:
                    value = re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
                values.append(_strip_markdown_link_destinations(value))

            numbers = tuple(normalize_numbers(" | ".join(values)))
            label = next(
                (value for value in values if re.search(r"[^\W\d_]", value, re.UNICODE)),
                "",
            )
            if numbers:
                rows.append((label, numbers))
    return rows


def _link_aware_financial_row_recall(source: bytes) -> float:
    """Compare visible table content without counting Markdown link syntax."""

    markdown, _, _, _ = _parse_once(source)
    return _financial_row_recall(
        _link_aware_source_rows(source),
        extract_financial_rows(_strip_markdown_link_destinations(markdown)),
    )


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
    result = audit_document(source, contract, quality_policy="off")

    assert result.word_recall >= contract.min_word_recall
    assert result.numeric_recall >= contract.min_numeric_recall
    assert _link_aware_financial_row_recall(source) >= contract.min_financial_row_recall
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
    result = audit_document(source, contract, quality_policy="off")
    assert result.trace_failures == ()


def test_fixture_encoding_reasons_match_manifest():
    for fixture_id in FIXTURE_IDS:
        contract, source = load_fixture(fixture_id)
        _, diagnostics = decode_html(source)
        assert diagnostics.reason == contract.expected_encoding_reason


def test_legacy_character_normalization_has_no_c1_controls():
    contract, source = load_fixture("nvda-2002-10k")
    result = audit_document(source, contract, quality_policy="off")

    assert result.replacement_characters == 0
    assert result.c1_control_characters == 0


def test_legacy_accounting_reconstruction_preserves_sign_and_widths():
    _, source = load_fixture("nvda-2002-10k")
    markdown, _, _, _ = _parse_once(source)
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
    markdown, _, _, _ = _parse_once(source)
    result = audit_document(source, contract, quality_policy="off")
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
