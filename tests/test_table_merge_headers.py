"""Table merge and header rules (spec 2026-10-05-sec2md-table-merge-header-rules-design.md).

Covers the structural policy boundary (R9) and zero-width cell text.
"""

import pytest
from bs4 import BeautifulSoup

from sec2md import table_parser
from sec2md.table_parser import (
    EXTENDED,
    LEGACY,
    Cell,
    GridCell,
    StructuralPolicy,
    TableParser,
)


def _table(html: str):
    return BeautifulSoup(html, "lxml").find("table")


def _grid(rows):
    return [[GridCell(Cell(text)) for text in row] for row in rows]


def _markdown(html: str) -> list[str]:
    return TableParser(_table(html)).md().splitlines()


# --- R9: the structural policy -----------------------------------------------------------

# Two repeated close-marker columns, two currency columns and one final singleton close
# marker: the legacy NVIDIA exception path runs too.
NVIDIA_SHAPE = [
    ["Label", "", "A", "", "", "B", "", "C", ""],
    ["R1", "$", "(10", ")", "$", "(20", ")", "(30", ")"],
    ["R2", "$", "(11", ")", "$", "(21", ")", "31", ""],
]
NVIDIA_ACTIONS = {1: {1: 2, 2: 2}, 3: {1: 2, 2: 2}, 4: {1: 5, 2: 5}, 6: {1: 5, 2: 5}, 8: {1: 7}}


def test_policies_are_named_constants():
    assert LEGACY is StructuralPolicy.LEGACY
    assert EXTENDED is StructuralPolicy.EXTENDED
    assert LEGACY is not EXTENDED


def test_legacy_structural_helpers_work_on_a_bare_parser_without_instance_state():
    parser = object.__new__(TableParser)
    grid = _grid(NVIDIA_SHAPE)
    assert parser._safe_structural_actions(grid) == NVIDIA_ACTIONS
    paired = {1: {1: 2, 2: 2}, 3: {1: 2, 2: 2}}
    assert parser._validated_structural_actions(grid, paired) == paired
    # "$ (10" alone is not a complete token, so the action is rejected.
    assert parser._validated_structural_actions(grid, {1: {1: 2, 2: 2}}) == {}
    assert parser._join_structural_text(["$"], "(10", [")"]) == "$ (10)"
    assert parser._is_numeric_fragment("(29")
    assert parser._body_rows(grid) == range(1, 3)
    assert parser._should_merge_cells(GridCell(Cell("$")), GridCell(Cell("10")))
    assert vars(parser) == {}


def test_extended_structural_helpers_also_need_no_instance_state():
    parser = object.__new__(TableParser)
    grid = _grid(NVIDIA_SHAPE)
    assert parser._safe_structural_actions(grid, policy=EXTENDED) == NVIDIA_ACTIONS
    paired = {1: {1: 2, 2: 2}, 3: {1: 2, 2: 2}}
    assert parser._validated_structural_actions(grid, paired, policy=EXTENDED) == paired
    assert vars(parser) == {}


_DEFAULT = "<default>"
_SPIED_FUNCTIONS = ("_classify_structural_column", "_marker_class")
_SPIED_STATIC = ("_is_numeric_fragment", "_numeric_token", "_join_structural_text", "_body_start")
_SPIED_METHODS = ("_validated_structural_actions", "_body_rows", "_safe_structural_actions",
                  "_should_merge_cells")


@pytest.fixture
def policy_calls(monkeypatch):
    """Record the policy each structural helper receives; an omitted policy is a bug."""

    calls: list[tuple[str, object]] = []

    def wrap(name, original):
        def recorder(*args, **kwargs):
            calls.append((name, kwargs.get("policy", _DEFAULT)))
            return original(*args, **kwargs)
        return recorder

    for name in _SPIED_FUNCTIONS:
        monkeypatch.setattr(table_parser, name, wrap(name, getattr(table_parser, name)))
    for name in _SPIED_STATIC:
        original = getattr(TableParser, name)
        monkeypatch.setattr(TableParser, name, staticmethod(wrap(name, original)))
    for name in _SPIED_METHODS:
        monkeypatch.setattr(TableParser, name, wrap(name, getattr(TableParser, name)))
    return calls


@pytest.mark.parametrize("policy", [LEGACY, EXTENDED], ids=["legacy", "extended"])
def test_every_transitive_structural_helper_receives_the_policy(policy_calls, policy):
    parser = object.__new__(TableParser)
    parser._safe_structural_actions(_grid(NVIDIA_SHAPE), policy=policy)
    called = {name for name, _ in policy_calls}
    expected = {"_safe_structural_actions", "_validated_structural_actions", "_body_rows",
                "_classify_structural_column", "_marker_class", "_is_numeric_fragment",
                "_numeric_token", "_join_structural_text"}
    assert expected <= called
    assert {received for _, received in policy_calls} == {policy}


def test_default_call_passes_legacy_explicitly_to_every_helper(policy_calls):
    object.__new__(TableParser)._safe_structural_actions(_grid(NVIDIA_SHAPE))
    assert policy_calls[0] == ("_safe_structural_actions", _DEFAULT)
    assert {received for _, received in policy_calls[1:]} == {LEGACY}


def test_markdown_render_passes_extended(policy_calls):
    TableParser(_table(
        "<table><tr><th>Item</th><th></th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td>100</td></tr>"
        "<tr><td>Costs</td><td>$</td><td>60</td></tr></table>"
    ))
    assert {"_safe_structural_actions", "_join_structural_text", "_should_merge_cells"} <= {
        name for name, _ in policy_calls}
    assert {received for _, received in policy_calls} == {EXTENDED}


def test_xlsx_prepare_table_stays_legacy(policy_calls):
    from sec2md.xlsx_tables import prepare_table, snapshot_html_table

    table = _table(
        "<table><tr><th>Item</th><th></th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td>100</td></tr>"
        "<tr><td>Costs</td><td>$</td><td>60</td></tr></table>"
    )
    prepare_table(snapshot_html_table(table, ordinal=1, page=1, source_url=None))
    assert {name for name, _ in policy_calls} >= {"_safe_structural_actions",
                                                  "_validated_structural_actions"}
    assert {received for _, received in policy_calls} <= {_DEFAULT, LEGACY}


# --- zero-width cell text ----------------------------------------------------------------

def test_zero_width_characters_are_removed_from_cell_text():
    matrix = TableParser(_table(
        "<table><tr><td>Item\u200b</td><td>\ufeff2025</td></tr>"
        "<tr><td>A\u2060B</td><td>1,234\u200c\u200d</td></tr>"
        '<tr><td><a href="x.htm">C\u200cD\u200b</a></td><td>\u200b</td></tr></table>'
    )).to_matrix()
    assert matrix == [["Item", "2025"], ["AB", "1,234"], ["[CD](x.htm)", ""]]


def test_zero_width_cell_does_not_block_a_currency_merge():
    # NTRA: a U+200B cell in the "$" column made the column non-uniform.
    assert _markdown(
        "<table><tr><th>Item</th><th></th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td>100</td></tr>"
        "<tr><td>Costs</td><td>$</td><td>60</td></tr>"
        "<tr><td>Other</td><td>\u200b</td><td>5</td></tr></table>"
    ) == [
        "| Item | 2025 |",
        "| --- | --- |",
        "| Revenue | $ 100 |",
        "| Costs | $ 60 |",
        "| Other | 5 |",
    ]


def test_zero_width_only_row_is_not_a_header_line():
    # NTRA 141: rows of U+200B cells rendered as a header line of invisible cells.
    assert _markdown(
        "<table><tr><td>\u200b</td><td>\u200b</td></tr>"
        "<tr><th>Item</th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table>"
    ) == ["| Item | 2025 |", "| --- | --- |", "| Revenue | 100 |"]


@pytest.mark.parametrize(
    ("amount", "rendered", "token"),
    [
        ("1,2\u200b34", "1,234", "1234"),
        ("12\u200c345", "12345", "12345"),
        ("(1,234\u200b)", "(1,234)", "-1234"),
    ],
    ids=["u200b_in_thousands", "u200c_in_digits", "u200b_before_close_paren"],
)
def test_zero_width_inside_a_number_is_a_known_strict_limitation(amount, rendered, token):
    """Known limitation (accepted 2026-10-06), pinned as today's behaviour.

    The render removes a zero-width character inside a table number, but strict's source
    pool still splits the source number at it, so strict reports the joined number as
    untraceable. A separate strict fix will change this test.
    """
    from sec2md.core import convert_to_markdown
    from sec2md.quality import ParseQualityError

    html = (
        "<html><body><p>Operating results for the year.</p><table>"
        "<tr><th>Item</th><th>2025</th></tr>"
        f"<tr><td>Revenue</td><td>{amount}</td></tr>"
        "<tr><td>Costs</td><td>567</td></tr></table></body></html>"
    )
    with pytest.raises(ParseQualityError,
                       match=rf"^untraceable normalized number: [^\s,:]+:{token}$"):
        convert_to_markdown(html, quality_policy="strict")
    assert f"| Revenue | {rendered} |" in convert_to_markdown(
        html, quality_policy="off").splitlines()


def test_cells_keep_their_td_or_th_markup():
    parser = TableParser(_table(
        "<table><tr><th>Item</th><td>2025</td></tr><tr><td>Revenue</td><th>100</th></tr></table>"
    ))
    assert [[cell.header for cell in row] for row in parser.cells] == [[True, False], [False, True]]
    # XLSX builds cells from text alone; they are td cells.
    assert Cell("x").header is False
