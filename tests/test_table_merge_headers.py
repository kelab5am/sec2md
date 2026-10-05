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


# --- R3.1-R3.4 and R4: the careful marker merge under EXTENDED ---------------------------

def _actions(rows, policy=LEGACY):
    return object.__new__(TableParser)._safe_structural_actions(_grid(rows), policy=policy)


def _html(rows, header_tag="td"):
    """A table whose first row uses header_tag, one cell per text and no spans."""
    body = []
    for index, row in enumerate(rows):
        tag = header_tag if index == 0 else "td"
        body.append("<tr>" + "".join(f"<{tag}>{text}</{tag}>" for text in row) + "</tr>")
    return "<table>" + "".join(body) + "</table>"


def test_zero_width_marker_slot_is_empty_under_extended_only():
    # R3.1 (NTRA): XLSX passes source text with U+200B; LEGACY keeps reading it as content.
    rows = [
        ["Item", "", "2025"],
        ["Revenue", "$", "100"],
        ["Costs", "\u200b", "60"],
        ["Other", "$", "5"],
    ]
    assert _actions(rows, EXTENDED) == {1: {1: 2, 3: 2}}
    assert _actions(rows) == {}


# MSFT 24 / TSM 312: a bare year starts the "$" column in the last header row.
YEAR_IN_DOLLAR_COLUMN = [
    ["(In millions, except per share amounts)", "", "", "", ""],
    ["Year Ended June 30,", "2025", "", "2024", ""],
    ["Product", "$", "63,946", "$", "64,773"],
    ["Service and other", "", "217,778", "", "180,349"],
    ["Total revenue", "$", "281,724", "$", "245,122"],
]


def test_body_start_is_the_r0_body_under_extended():
    # R3.2: the year row is header, so the "$" columns are uniform marker columns.
    assert _actions(YEAR_IN_DOLLAR_COLUMN, EXTENDED) == {1: {2: 2, 4: 2}, 3: {2: 4, 4: 4}}
    assert _actions(YEAR_IN_DOLLAR_COLUMN) == {}
    parser = object.__new__(TableParser)
    assert parser._body_rows(_grid(YEAR_IN_DOLLAR_COLUMN), policy=EXTENDED) == (2, 3, 4)
    assert parser._body_rows(_grid(YEAR_IN_DOLLAR_COLUMN)) == range(1, 5)


def test_year_in_dollar_column_renders_joined_amounts():
    lines = _markdown(_html(YEAR_IN_DOLLAR_COLUMN))
    assert lines[-3:] == [
        "| Product | $ 63,946 | $ 64,773 |",
        "| Service and other | 217,778 | 180,349 |",
        "| Total revenue | $ 281,724 | $ 245,122 |",
    ]


# nvda-2002-10k table 138: per-share values with leading-dot decimals.
LEADING_DOT_ROWS = [
    ["", "", "2002", "", "2001"],
    ["Basic", "$", ".75", "$", ".62"],
    ["Diluted", "$", "(.62)", "$", ".60"],
]


def test_leading_dot_decimals_validate_under_extended_only():
    # R3.3: fragment recognition and final validation both accept ".75" and "(.62)".
    parser = object.__new__(TableParser)
    assert parser._is_numeric_fragment(".75", policy=EXTENDED)
    assert parser._is_numeric_fragment("(.62", policy=EXTENDED)
    assert parser._numeric_token("$ (.62)", policy=EXTENDED) == "-0.62"
    assert not parser._is_numeric_fragment(".75")
    assert parser._numeric_token("$ .75") is None
    assert _actions(LEADING_DOT_ROWS, EXTENDED) == {1: {1: 2, 2: 2}, 3: {1: 4, 2: 4}}
    assert _actions(LEADING_DOT_ROWS) == {}


def test_leading_dot_values_join_their_dollar_marker():
    assert _markdown(_html(LEADING_DOT_ROWS))[-2:] == [
        "| Basic | $ .75 | $ .62 |",
        "| Diluted | $ (.62) | $ .60 |",
    ]


def test_strict_normalizer_is_unchanged_by_local_numeric_rules():
    from sec2md.quality import normalize_numeric_token

    assert normalize_numeric_token(".75") is None
    assert normalize_numeric_token("RMB 1,234") is None


# BABA 69: one negative per marker column.
SINGLE_NEGATIVE_ROWS = [
    ["", "2024", "", "2025", ""],
    ["Deferred revenue", "37,142", "", "44,138", ""],
    ["Less: current portion", "(72,818", ")", "(68,335", ")"],
]


def test_single_marker_column_merges_under_extended_only():
    # R3.4: one non-empty marker may merge when the rebuilt token validates.
    assert _actions(SINGLE_NEGATIVE_ROWS, EXTENDED) == {2: {2: 1}, 4: {2: 3}}
    assert _actions(SINGLE_NEGATIVE_ROWS) == {}
    assert _markdown(_html(SINGLE_NEGATIVE_ROWS))[-2:] == [
        "| Deferred revenue | 37,142 | 44,138 |",
        "| Less: current portion | (72,818) | (68,335) |",
    ]


def test_single_unmatched_open_marker_still_fails_validation():
    rows = [["Item", "", "2025"], ["A", "(", "10"], ["B", "", "20"]]
    assert _actions(rows, EXTENDED) == {}


# TSM 79: ")%" closes a percentage negative.
PERCENT_CLOSE_ROWS = [
    ["", "2023", "", "2024", ""],
    ["Net margin", "(3.2", ")%", "(4.5", ")%"],
    ["Growth", "1.5", "%", "(2.0", ")%"],
]


def test_percent_close_marker_merges_under_extended_only():
    # Column 2 mixes "%" and ")%" (percent and close classes), so it stays split.
    assert _actions(PERCENT_CLOSE_ROWS, EXTENDED) == {4: {1: 3, 2: 3}}
    assert _actions(PERCENT_CLOSE_ROWS) == {}
    rows = [["", "2023", ""], ["Net margin", "(3.2", ")%"], ["Growth", "(1.5", ")%"]]
    assert _actions(rows, EXTENDED) == {2: {1: 1, 2: 1}}
    assert _markdown(_html(rows))[-2:] == ["| Net margin | (3.2)% |", "| Growth | (1.5)% |"]


CURRENCY_MARKER_CASES = ["€", "NT$", "DKK"]
CURRENCY_IDS = ["symbol", "prefixed-dollar", "iso-code"]
CURRENCY_AMOUNTS = [
    ("1,234", "{m} 1,234"),
    ("(1,234)", "{m} (1,234)"),
    ("12.5", "{m} 12.5"),
    ("3.2 %", "{m} 3.2 %"),
]


@pytest.mark.parametrize("marker", CURRENCY_MARKER_CASES, ids=CURRENCY_IDS)
@pytest.mark.parametrize("amount, rendered", CURRENCY_AMOUNTS,
                         ids=["positive", "negative", "decimal", "percent"])
def test_currency_marker_column_joins_its_amount_under_extended(marker, amount, rendered):
    # R4: every marker of the closed list behaves as "$" does.
    rows = [["Item", "", "2025"], ["Revenue", marker, amount], ["Costs", marker, "60"]]
    assert _actions(rows, EXTENDED) == {1: {1: 2, 2: 2}}
    assert _actions(rows) == {}
    assert _markdown(_html(rows, "th"))[-2:] == [
        f"| Revenue | {rendered.format(m=marker)} |",
        f"| Costs | {marker} 60 |",
    ]


@pytest.mark.parametrize("marker", CURRENCY_MARKER_CASES, ids=CURRENCY_IDS)
def test_currency_marker_and_split_negative_rebuild_one_token(marker):
    rows = [["Item", "", "2025", ""], ["Revenue", marker, "(1,234", ")"], ["Costs", marker, "60", ""]]
    assert _actions(rows, EXTENDED) == {1: {1: 2, 2: 2}, 3: {1: 2}}
    assert _markdown(_html(rows, "th"))[-2:] == [
        f"| Revenue | {marker} (1,234) |",
        f"| Costs | {marker} 60 |",
    ]


def test_currency_marker_needs_a_validated_amount_on_its_right():
    rows = [["Item", "", "2025"], ["Costs", "€", "60"], ["Revenue", "€", "n/a"]]
    assert _actions(rows, EXTENDED) == {}


@pytest.mark.parametrize("code", ["XYZ", "ABC"])
def test_unknown_currency_code_is_not_a_marker(code):
    rows = [["Item", "", "2025"], ["Revenue", code, "1,234"], ["Costs", code, "60"]]
    assert _actions(rows, EXTENDED) == {}
    assert _markdown(_html(rows, "th"))[-2:] == [
        f"| Revenue | {code} | 1,234 |",
        f"| Costs | {code} | 60 |",
    ]


def test_header_row_currency_label_is_not_a_marker_column():
    # BABA 24: "RMB" over each amount is header text (R4), never a body marker.
    rows = [
        ["", "Year ended March 31,", "", "", ""],
        ["", "2024", "", "2025", ""],
        ["", "RMB", "", "RMB", ""],
        ["Revenue", "", "941,168", "", "996,347"],
        ["Costs", "", "(12,000)", "", "(13,000)"],
    ]
    assert _actions(rows, EXTENDED) == {}


def test_currency_markers_merge_in_the_legacy_pass_like_dollar_under_extended():
    parser = object.__new__(TableParser)
    euro, amount = GridCell(Cell("€")), GridCell(Cell("1,234"))
    assert parser._should_merge_cells(euro, amount, policy=EXTENDED)
    assert not parser._should_merge_cells(euro, amount)
    assert not parser._should_merge_cells(GridCell(Cell("XYZ")), amount, policy=EXTENDED)
    assert parser._should_merge_cells(GridCell(Cell("$")), amount)


# Revision 17 (R4): R0's label column is never a currency-marker column for a marker other
# than "$", which keeps main's rule. Row labels such as "EUR" or "JPY" stay their own column.
EXCHANGE_RATE_ROWS = [
    ["", "2025", "2024"],
    ["EUR", "1.08", "1.10"],
    ["GBP", "1.27", "1.25"],
    ["JPY", "0.0067", "0.0071"],
]
NOTIONAL_BY_CURRENCY_ROWS = [["", "2025", "2024"], ["JPY", "1,234", "987"], ["EUR", "456", "789"]]


@pytest.mark.parametrize("rows", [EXCHANGE_RATE_ROWS, NOTIONAL_BY_CURRENCY_ROWS],
                         ids=["exchange-rates", "notional-by-currency"])
def test_currency_code_label_column_is_not_a_marker_column(rows):
    assert _actions(rows, EXTENDED) == {}
    assert _actions(rows) == {}
    labels = [row[0] for row in rows[1:]]
    assert table_parser._classify_structural_column(labels, policy=EXTENDED) == "currency"
    assert table_parser._classify_structural_column(labels, policy=EXTENDED, label=True) is None
    parser = object.__new__(TableParser)
    code, amount = GridCell(Cell(rows[1][0])), GridCell(Cell(rows[1][1]))
    assert parser._should_merge_cells(code, amount, policy=EXTENDED)
    assert not parser._should_merge_cells(code, amount, policy=EXTENDED, label=True)


def test_dollar_label_column_keeps_mains_rule():
    rows = [["", "2025", "2024"], ["$", "1,234", "987"], ["$", "456", "789"]]
    assert _actions(rows, EXTENDED) == _actions(rows) == {0: {1: 1, 2: 1}}
    dollars = table_parser._classify_structural_column(["$", "$"], policy=EXTENDED, label=True)
    assert dollars == "currency"
    parser = object.__new__(TableParser)
    dollar, amount = GridCell(Cell("$")), GridCell(Cell("1,234"))
    assert parser._should_merge_cells(dollar, amount, policy=EXTENDED, label=True)
    assert parser._should_merge_cells(dollar, amount, label=True)


CURRENCY_LABEL_TABLES = {
    # The exchange-rate shape: an empty th over the codes, years over the rates.
    "exchange-rates": (
        "<table><tr><th></th><th>2025</th><th>2024</th></tr>"
        "<tr><td>EUR</td><td>1.08</td><td>1.10</td></tr>"
        "<tr><td>GBP</td><td>1.27</td><td>1.25</td></tr>"
        "<tr><td>JPY</td><td>0.0067</td><td>0.0071</td></tr></table>",
        ["|  | 2025 | 2024 |", "| --- | --- | --- |", "| EUR | 1.08 | 1.10 |",
         "| GBP | 1.27 | 1.25 |", "| JPY | 0.0067 | 0.0071 |"],
    ),
    # USD notionals by currency under td years: "JPY 1,234" would read as a yen amount.
    "notional-by-currency": (
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>JPY</td><td>1,234</td><td>987</td></tr>"
        "<tr><td>EUR</td><td>456</td><td>789</td></tr></table>",
        ["|  | 2025 | 2024 |", "| --- | --- | --- |", "| JPY | 1,234 | 987 |",
         "| EUR | 456 | 789 |"],
    ),
    # A real currency-marker column beside the code labels still joins its amounts.
    "marker-column-beside-code-labels": (
        "<table><tr><th></th><th></th><th>2025</th></tr>"
        "<tr><td>EUR</td><td>€</td><td>1,234</td></tr>"
        "<tr><td>GBP</td><td>£</td><td>987</td></tr></table>",
        ["|  | 2025 |", "| --- | --- |", "| EUR | € 1,234 |", "| GBP | £ 987 |"],
    ),
}


@pytest.mark.parametrize("case", list(CURRENCY_LABEL_TABLES))
def test_currency_code_row_labels_keep_their_own_column(case):
    html, expected = CURRENCY_LABEL_TABLES[case]
    assert _markdown(html) == expected


def test_headerless_currency_code_row_labels_keep_their_own_column():
    # No header zone, so only the body test of the merge can keep the labels apart.
    lines = _markdown(
        "<table><tr><td>JPY</td><td>1,234</td><td>987</td></tr>"
        "<tr><td>EUR</td><td>456</td><td>789</td></tr></table>"
    )
    assert "| JPY | 1,234 | 987 |" in lines
    assert "| EUR | 456 | 789 |" in lines


# Codes in a sub-label column: R0's label column holds the section label only.
SUB_LABEL_CODE_ROWS = [
    ["", "", "2025", "2024"],
    ["Forward contracts", "", "", ""],
    ["", "EUR", "1,234", "987"],
    ["", "JPY", "456", "789"],
]


def test_sub_label_currency_codes_merge_as_a_marker_column_known_limitation():
    """Known limitation (spec revision 17, accepted 2026-10-06), pinned as today's behaviour.

    Codes that vary by row in a column other than R0's label column cannot be told apart
    from R4's per-row currency-marker column, so the structural pass joins them to the
    first period's amounts. A rule for this case is left to a later task, which will
    change this test.
    """
    assert _actions(SUB_LABEL_CODE_ROWS, EXTENDED) == {1: {2: 2, 3: 2}}
    assert _actions(SUB_LABEL_CODE_ROWS) == {}


def test_extended_join_writes_currency_like_dollar_and_closes_percent_negatives():
    join = TableParser._join_structural_text
    assert join(["RMB"], "941,168", [], policy=EXTENDED) == "RMB 941,168"
    assert join(["€", "("], "1,234", [")"], policy=EXTENDED) == "€ (1,234)"
    assert join([], "(3.2", [")%"], policy=EXTENDED) == "(3.2)%"
    assert join(["RMB"], "941,168", []) == "RMB 941,168"   # LEGACY: a plain space join
    assert join([], "(3.2", [")%"]) == "(3.2 )%"
