from collections import Counter
import re
from urllib.parse import urljoin

import pytest
from bs4 import BeautifulSoup
from sec2md.core import convert_to_markdown
from sec2md.encoding import decode_html
from sec2md.models import Element, Page
from sec2md.parser import Parser
from sec2md.quality import ParseQualityError

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
    assert result.financial_row_recall >= contract.min_financial_row_recall
    assert not result.representative_row_failures
    assert result.expected_sections == contract.expected_sections
    if fixture_id != "nvda-2002-10k":
        assert not result.table_width_errors
    assert result.replacement_characters == 0
    assert result.c1_control_characters == 0
    assert not result.duplicate_element_ids
    assert not result.missing_mappings
    if fixture_id != "aapl-2023-10k":
        assert not result.trace_failures
    assert not result.invalid_visible_node_xbrl_tags
    assert result.deterministic_markdown
    assert result.deterministic_pages
    assert result.deterministic_annotated_html


def test_known_apple_trace_defect_is_exactly_bounded():
    contract, source = load_fixture("aapl-2023-10k")
    result = audit_document(source, contract, quality_policy="off")
    expected = Counter(
        {
            "sec2md-p55-t3-2d2bcdab": 1,
            "sec2md-p56-t3-56ef4eec": 1,
        }
    )
    if Counter(result.trace_failures) == expected:
        pytest.xfail("known baseline defect: exactly two Apple trace failures")
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


def test_known_legacy_accounting_defect_is_exactly_bounded():
    _, source = load_fixture("nvda-2002-10k")
    markdown, _, _, _ = _parse_once(source)
    from tests.accuracy.metrics import _table_width_errors

    expected_width_errors = (
        "line 27: expected 2 columns, got 1",
        "line 1198: expected 4 columns, got 1",
    )
    split_accounting_row = "| Interest expense | (16,173 | ) | (4,852 | ) | (332 | ) |"
    actual_width_errors = _table_width_errors(markdown)
    if actual_width_errors == expected_width_errors and split_accounting_row in markdown:
        pytest.xfail("known baseline defect: split legacy accounting negative")
    assert actual_width_errors == ()
    assert split_accounting_row not in markdown
    assert _legacy_accounting_recovery_is_valid(markdown)


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
    if (
        result.exhibit_link_count == 0
        and markdown.count("Augu st 2 6") == 1
        and markdown.count("Se cond") == 1
        and not _has_audited_exhibit_links(links)
    ):
        pytest.xfail("known baseline defect: lost exhibit links and fragmented text")
    assert result.exhibit_link_count >= 2
    assert _has_audited_exhibit_links(links)
    assert "Augu st 2 6" not in markdown
    assert "Se cond" not in markdown


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
    assert failures == ("element-1",)
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
    assert failures == ("element-1", "element-1")
