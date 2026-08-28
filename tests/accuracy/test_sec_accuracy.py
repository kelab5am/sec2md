import pytest
from bs4 import BeautifulSoup

from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture
from tests.accuracy.metrics import audit_document, extract_financial_rows, multiset_recall, normalize_numbers, normalize_words


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

    if fixture_id == "nvda-2002-10k" and result.c1_control_characters:
        pytest.xfail("known baseline defect: 629 C1 controls and split accounting negative")
    if fixture_id == "nvda-2026-08-26-8k" and result.exhibit_link_count < 2:
        pytest.xfail("known baseline defect: lost exhibit URLs and fragmented exhibit text")
    if fixture_id == "aapl-2023-10k" and result.trace_failures:
        pytest.xfail("known baseline defect: two trace failures")

    assert result.word_recall >= contract.min_word_recall
    assert result.numeric_recall >= contract.min_numeric_recall
    assert result.financial_row_recall >= contract.min_financial_row_recall
    assert not result.representative_row_failures
    assert result.expected_sections == contract.expected_sections
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
