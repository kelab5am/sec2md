"""Table merge and header rules (spec 2026-10-05-sec2md-table-merge-header-rules-design.md).

Covers the structural policy boundary (R9) and zero-width cell text.
"""

import re

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


# --- Source grid, membership, R1, R2, R3.5-R3.6 ------------------------------------------

def _parser(html):
    return TableParser(_table(html))


def _membership(parser):
    return [(column.owners, column.markers) for column in parser.columns]


def _header_texts(parser):
    """Per output column, each header-zone row's header-cell texts (R6's inputs)."""
    return [
        [[cell.text for cell in cells] for cells in parser.column_header_cells(index)]
        for index in range(len(parser.columns))
    ]


def _body_rows(parser):
    return [row for index, row in enumerate(parser.to_matrix())
            if parser.roles.role(index) != "header"]


# edgar:CRM-10-K-2025-03-05.htm table 26, minimal: the caption's origin sits in a spacer
# column, and its span covers 2025 and 2024 but not 2023 (as in the source).
CRM_26_HTML = (
    '<table><tr><td>4</td><td colspan="5">Fiscal Year Ended January 31,</td></tr>'
    '<tr><td></td><td></td><td colspan="2">2025</td><td colspan="2">2024</td>'
    '<td colspan="2">2023</td></tr>'
    "<tr><td>Net cash provided by operating activities</td><td></td><td>$</td><td>13,092</td>"
    "<td>$</td><td>10,234</td><td>$</td><td>7,111</td></tr>"
    "<tr><td>Net cash used in investing activities</td><td></td><td colspan=\"2\">(3,163)</td>"
    '<td colspan="2">(1,327)</td><td colspan="2">(1,989)</td></tr></table>'
)


def test_row_roles_are_decided_once_on_the_cleaned_source_grid():
    from sec2md.table_parser import _origin_cells
    from sec2md.table_roles import row_roles

    parser = _parser(CRM_26_HTML)
    assert parser.roles == row_roles(_origin_cells(parser.source_grid))
    assert parser.roles.header_rows == (0, 1)
    assert parser.roles.data_rows == (2, 3)
    # Every source slot still points at its extracted cell: merges never rewrite the grid.
    extracted = {id(cell) for row in parser.cells for cell in row}
    assert all(slot is None or id(slot.cell) in extracted
               for row in parser.source_grid for slot in row)


def test_crm_26_caption_and_years_keep_their_own_columns():
    parser = _parser(CRM_26_HTML)
    assert _membership(parser) == [([0], []), ([1], []), ([2, 3], []), ([4, 5], []), ([6, 7], [])]
    assert _header_texts(parser) == [
        [["4"], []],
        [["Fiscal Year Ended January 31,"], []],
        [["Fiscal Year Ended January 31,"], ["2025"]],
        [["Fiscal Year Ended January 31,"], ["2024"]],
        [[], ["2023"]],
    ]
    assert _body_rows(parser) == [
        ["Net cash provided by operating activities", "", "$ 13,092", "$ 10,234", "$ 7,111"],
        ["Net cash used in investing activities", "", "(3,163)", "(1,327)", "(1,989)"],
    ]


# edgar:JPM-10-K-2025-02-14.htm table 109 (headerless, offset "$" rows) and
# edgar:TSLA-10-K-2025-01-30.htm table 38: R1 keeps row 0's amounts.
JPM_109_HTML = (
    "<table><tr><td>Noninterest revenue – reported (c)</td><td>$</td><td>84,973</td>"
    "<td>$</td><td>68,837</td></tr>"
    '<tr><td>Fully taxable-equivalent adjustments (c)</td><td colspan="2">2,560</td>'
    '<td colspan="2">3,782</td></tr>'
    "<tr><td>Noninterest revenue – managed basis</td><td>$</td><td>87,533</td>"
    "<td>$</td><td>72,619</td></tr></table>"
)
TSLA_38_HTML = (
    "<table><tr><td>Beginning balance at fair value</td><td>$</td><td>487</td></tr>"
    '<tr><td>Unrealized gains, net</td><td colspan="2">589</td></tr>'
    "<tr><td>Ending balance</td><td>$</td><td>1,076</td></tr></table>"
)


def test_legacy_merge_keeps_row_zero_amounts():
    parser = _parser(JPM_109_HTML)
    assert parser.roles.header_rows == ()
    assert _membership(parser) == [([0], []), ([1, 2], []), ([3, 4], [])]
    assert parser.to_matrix() == [
        ["Noninterest revenue – reported (c)", "$ 84,973", "$ 68,837"],
        ["Fully taxable-equivalent adjustments (c)", "2,560", "3,782"],
        ["Noninterest revenue – managed basis", "$ 87,533", "$ 72,619"],
    ]


def test_a_spanning_body_cell_counts_once_when_its_columns_merge():
    assert _parser(TSLA_38_HTML).to_matrix() == [
        ["Beginning balance at fair value", "$ 487"],
        ["Unrealized gains, net", "589"],
        ["Ending balance", "$ 1,076"],
    ]


# fixture:aapl-2023-10k table 15: a "$" row's amount sits one grid column right of the
# other rows' amounts, all under one "2023" span; "(4)" + "%" sit under "Change".
AAPL_15_HTML = (
    '<table><tr><td colspan="3"></td><td colspan="3">2023</td><td colspan="3">Change</td>'
    '<td colspan="3">2022</td></tr>'
    '<tr><td colspan="3">Net sales by reportable segment:</td><td colspan="3"></td>'
    '<td colspan="3"></td><td colspan="3"></td></tr>'
    '<tr><td colspan="3">Americas</td><td>$</td><td>162,560</td><td></td>'
    '<td colspan="2">(4)</td><td>%</td><td>$</td><td>169,658</td><td></td></tr>'
    '<tr><td colspan="3">Europe</td><td colspan="2">94,294</td><td></td>'
    '<td colspan="2">(1)</td><td>%</td><td colspan="2">95,118</td><td></td></tr></table>'
)


def test_offset_values_under_one_span_merge():
    parser = _parser(AAPL_15_HTML)
    assert _membership(parser) == [([0], []), ([1, 2], []), ([3], [4]), ([5, 6], [])]
    # Revision 8: "Net sales by reportable segment:" is a trailing label-only row, so it is
    # a body section label, not header.
    assert _header_texts(parser) == [[[]], [["2023"]], [["Change"]], [["2022"]]]
    assert _body_rows(parser) == [
        ["Net sales by reportable segment:", "", "", ""],
        ["Americas", "$ 162,560", "(4) %", "$ 169,658"],
        ["Europe", "94,294", "(1) %", "95,118"],
    ]
    assert parser.to_matrix()[0] == ["", "2023", "Change", "2022"]


# edgar:KO-10-K-2025-02-20.htm table 18: "$ —" in the offset "$" row.
KO_18_HTML = (
    '<table><tr><td colspan="3">Year Ended December 31,</td><td colspan="3">2024</td>'
    '<td colspan="3">2023</td></tr>'
    '<tr><td colspan="3">Europe, Middle East &amp; Africa</td><td>$</td><td>—</td><td></td>'
    "<td>$</td><td>—</td><td></td></tr>"
    '<tr><td colspan="3">Latin America</td><td colspan="2">126</td><td></td>'
    '<td colspan="2">—</td><td></td></tr></table>'
)


def test_offset_nil_values_under_one_span_merge():
    parser = _parser(KO_18_HTML)
    assert _membership(parser) == [([0], []), ([1, 2], []), ([3, 4], [])]
    assert _body_rows(parser) == [
        ["Europe, Middle East & Africa", "$ —", "$ —"],
        ["Latin America", "126", "—"],
    ]


def test_complementary_values_under_sibling_headers_do_not_merge():
    parser = _parser(
        "<table><tr><th>Item</th><th>2025</th><th>2024</th></tr>"
        "<tr><td>A</td><td>100</td><td></td></tr>"
        "<tr><td>B</td><td></td><td>200</td></tr></table>"
    )
    assert _membership(parser) == [([0], []), ([1], []), ([2], [])]
    assert _body_rows(parser) == [["A", "100", ""], ["B", "", "200"]]


def test_a_new_period_span_never_merges_into_the_previous_period_or_the_labels():
    # BABA 24 / TSM 312: each year's span starts on a column that is empty in the body.
    parser = _parser(
        '<table><tr><td></td><td colspan="2">2025</td><td colspan="2">2024</td></tr>'
        "<tr><td>Revenue</td><td></td><td>100</td><td></td><td>200</td></tr>"
        "<tr><td>Costs</td><td></td><td>60</td><td></td><td>70</td></tr></table>"
    )
    assert _membership(parser) == [([0], []), ([1, 2], []), ([3, 4], [])]
    assert _header_texts(parser) == [[[]], [["2025"]], [["2024"]]]
    assert _body_rows(parser) == [["Revenue", "100", "200"], ["Costs", "60", "70"]]


# Astra's round-1 case: one marker column under the 2024 span routes "$" right to 2024's
# amounts and ")" left to 2025's amounts.
MIXED_DIRECTION_HTML = (
    '<table><tr><th>Metric</th><th colspan="2">2025</th><th colspan="2">2024</th></tr>'
    "<tr><td>A</td><td>100</td><td></td><td>$</td><td>200</td></tr>"
    "<tr><td>B</td><td>110</td><td></td><td>$</td><td>210</td></tr>"
    "<tr><td>C</td><td>(30</td><td></td><td>)</td><td>400</td></tr>"
    "<tr><td>D</td><td>(40</td><td></td><td>)</td><td>500</td></tr></table>"
)


def test_mixed_direction_marker_column_never_moves_a_header():
    parser = _parser(MIXED_DIRECTION_HTML)
    # Source grid columns: Metric, 2025's amounts, the marker column, 2024's amounts.
    assert _membership(parser) == [([0], []), ([1], [2]), ([3], [2])]
    assert _header_texts(parser) == [[["Metric"]], [["2025"]], [["2024"]]]
    assert parser.to_matrix() == [
        ["Metric", "2025", "2024"],
        ["A", "100", "$ 200"],
        ["B", "110", "$ 210"],
        ["C", "(30)", "400"],
        ["D", "(40)", "500"],
    ]
    assert "2025 2024" not in parser.md()


def test_marker_column_with_independent_header_stays_visible():
    parser = _parser(
        "<table><tr><th>Label</th><th>2022</th><th>Change</th><th>2021</th></tr>"
        "<tr><td>A</td><td>10</td><td>%</td><td>20</td></tr>"
        "<tr><td>B</td><td>30</td><td>%</td><td>40</td></tr></table>"
    )
    assert _membership(parser) == [([0], []), ([1], []), ([2], []), ([3], [])]
    assert parser.to_matrix() == [
        ["Label", "2022", "Change", "2021"],
        ["A", "10", "%", "20"],
        ["B", "30", "%", "40"],
    ]


def test_header_veto_revalidates_the_remaining_marker_actions():
    # "(" owns the independent header "Sign" and stays; without it, ")" alone would
    # rebuild "10)", so the ")" action is dropped as well.
    parser = _parser(
        "<table><tr><th>Item</th><th>Sign</th><th>2025</th><th></th></tr>"
        "<tr><td>A</td><td>(</td><td>10</td><td>)</td></tr>"
        "<tr><td>B</td><td>(</td><td>20</td><td>)</td></tr></table>"
    )
    grid = parser.source_grid
    unvetoed = object.__new__(TableParser)._safe_structural_actions(grid, policy=EXTENDED)
    assert unvetoed == {1: {1: 2, 2: 2}, 3: {1: 2, 2: 2}}
    assert TableParser._independent_header_veto(grid, (0,), unvetoed) == {3: {1: 2, 2: 2}}
    assert _membership(parser) == [([0], []), ([1], []), ([2], []), ([3], [])]
    assert _body_rows(parser) == [["A", "(", "10", ")"], ["B", "(", "20", ")"]]


def test_marker_exception_joins_a_headerless_currency_column_to_the_next_period():
    # A stray ")" makes the structural pass reject the "$" column; the legacy pass then
    # applies the marker exception on the 2024 side and never joins the 2025 side.
    parser = _parser(
        "<table><tr><th>Item</th><th>2025</th><th></th><th>2024</th><th></th></tr>"
        "<tr><td>Revenue</td><td>100</td><td>$</td><td>200</td><td>)</td></tr>"
        "<tr><td>Costs</td><td>60</td><td>$</td><td>70</td><td></td></tr></table>"
    )
    assert _membership(parser) == [([0], []), ([1], []), ([2, 3], []), ([4], [])]
    assert _header_texts(parser) == [[["Item"]], [["2025"]], [["2024"]], [[]]]
    assert _body_rows(parser) == [["Revenue", "100", "$ 200", ")"], ["Costs", "60", "$ 70", ""]]


def test_marker_exception_needs_a_validated_value_in_every_marker_row():
    # "$ —" does not validate, so the "$" column keeps its own column and 2025 its header.
    parser = _parser(
        "<table><tr><th>Item</th><th></th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td>100</td></tr>"
        "<tr><td>Impairment</td><td>$</td><td>—</td></tr></table>"
    )
    assert _membership(parser) == [([0], []), ([1], []), ([2], [])]
    assert _header_texts(parser) == [[["Item"]], [[]], [["2025"]]]
    assert _body_rows(parser) == [["Revenue", "$", "100"], ["Impairment", "$", "—"]]


def test_empty_group_never_qualifies_for_the_marker_exception():
    parser = object.__new__(TableParser)
    grid = _grid([["Item", "", "2025"], ["Revenue", "", "100"], ["Costs", "", "60"]])
    columns = parser._structural_columns(grid, (0,), policy=EXTENDED)
    assert [column.owners for column in columns] == [[0], [1], [2]]
    assert not parser._merge_allowed(grid, (0,), columns[1], columns[2], policy=EXTENDED)
    # The same column without a header passes the header test itself.
    grid = _grid([["Item", "", ""], ["Revenue", "", "100"], ["Costs", "", "60"]])
    columns = parser._structural_columns(grid, (0,), policy=EXTENDED)
    assert parser._merge_allowed(grid, (0,), columns[1], columns[2], policy=EXTENDED)


def test_marker_exception_requires_every_group_slot_to_be_a_marker():
    parser = object.__new__(TableParser)
    grid = _grid([["Item", "", "2025"], ["Revenue", "$", "100"], ["Costs", "", "60"],
                  ["Other", "n/a", ""]])
    columns = parser._structural_columns(grid, (0,), policy=EXTENDED)
    assert not parser._merge_allowed(grid, (0,), columns[1], columns[2], policy=EXTENDED)


def test_marker_exception_covers_currency_markers_only():
    # An open-parenthesis group never qualifies: "(" columns stay with the careful merge.
    from sec2md.table_parser import BodySlot, OutputColumn

    parser = object.__new__(TableParser)
    grid = _grid([["Item", "", "2025"], ["A", "(", "29)"], ["B", "", "5"]])
    group = OutputColumn([1], [], [BodySlot(), BodySlot("(", (grid[1][1].cell,)), BodySlot()])
    column = OutputColumn([2], [], [BodySlot(), BodySlot("29)", (grid[1][2].cell,)),
                                    BodySlot("5", (grid[2][2].cell,))])
    assert not parser._marker_exception(grid, (0,), [1, 2], group, column, policy=EXTENDED)
    euro = OutputColumn([1], [], [BodySlot(), BodySlot("€", (grid[1][1].cell,)), BodySlot()])
    priced = OutputColumn([2], [], [BodySlot(), BodySlot("29", (grid[1][2].cell,)),
                                    BodySlot("5", (grid[2][2].cell,))])
    assert parser._marker_exception(grid, (0,), [1, 2], euro, priced, policy=EXTENDED)


def test_marker_exception_never_reads_a_currency_code_row_label_as_a_marker():
    # R4, revision 17: in R0's label column only "$" is a currency marker (main's rule).
    from sec2md.table_parser import BodySlot, OutputColumn

    def column(grid, index):
        return OutputColumn([index], [], [
            BodySlot(grid[row][index].text, (grid[row][index].cell,)) if row else BodySlot()
            for row in range(len(grid))])

    parser = object.__new__(TableParser)
    codes = _grid([["", "2025"], ["EUR", "1.08"], ["GBP", "1.27"]])
    assert not parser._marker_exception(
        codes, (0,), [1, 2], column(codes, 0), column(codes, 1), policy=EXTENDED)
    assert not parser._merge_allowed(
        codes, (0,), column(codes, 0), column(codes, 1), policy=EXTENDED)
    # Without a header zone only the body test can keep the row labels apart.
    headerless = _grid([["Rates", "2025"], ["EUR", "1.08"], ["GBP", "1.27"]])
    assert not parser._merge_allowed(
        headerless, (), column(headerless, 0), column(headerless, 1), policy=EXTENDED)
    # The same codes outside the label column are markers.
    marked = _grid([["", "", "2025"], ["Rate", "EUR", "1.08"], ["Rate", "GBP", "1.27"]])
    assert parser._marker_exception(
        marked, (0,), [1, 2], column(marked, 1), column(marked, 2), policy=EXTENDED)
    dollars = _grid([["", "2025"], ["$", "1,234"], ["$", "456"]])
    assert parser._marker_exception(
        dollars, (0,), [1, 2], column(dollars, 0), column(dollars, 1), policy=EXTENDED)
    assert vars(parser) == {}


CODE_ROW_LABEL_CASES = {
    # Task 4 review: one code row under text headers. The header test fails, so the body
    # test and the marker exception both stand between "EUR" and "EUR 1.08".
    "rate-and-prior-header": (
        "<table><tr><td></td><td>Rate</td><td>Prior</td></tr>"
        "<tr><td>EUR</td><td>1.08</td><td>1.10</td></tr></table>",
        ["|  | Rate | Prior |", "| --- | --- | --- |", "| EUR | 1.08 | 1.10 |"],
    ),
    # Its headerless variant: the header test passes vacuously, so the body test decides.
    "headerless": (
        "<table><tr><td>EUR</td><td>1.08</td><td>1.10</td></tr></table>",
        ["| EUR | 1.08 | 1.10 |"],
    ),
}


@pytest.mark.parametrize("case", list(CODE_ROW_LABEL_CASES))
def test_a_single_currency_code_row_label_keeps_its_own_column(case):
    # R4, revision 17: closes the structural pass, the body test and the marker exception.
    html, expected = CODE_ROW_LABEL_CASES[case]
    lines = _markdown(html)
    assert [line for line in expected if line not in lines] == []
    assert [line for line in lines if "EUR 1.08" in line] == []


def test_sub_label_currency_codes_fuse_into_the_first_period_known_limitation():
    """Known limitation (spec revision 17, accepted 2026-10-06), pinned as today's rendering.

    Codes that vary by row in a column other than R0's label column cannot be told apart
    from R4's per-row currency-marker column, so they fuse into the first period's
    amounts. main renders "| EUR | 1,234 | 987 |". A rule for this case is left to a
    later task, which will change this test.
    """
    assert _markdown(_html(SUB_LABEL_CODE_ROWS)) == [
        "|  | 2025 | 2024 |",
        "| --- | --- | --- |",
        "| Forward contracts |  |  |",
        "|  | EUR 1,234 | 987 |",
        "|  | JPY 456 | 789 |",
    ]


def test_header_text_is_never_concatenated_by_a_merge():
    # R2: a merge never joins two header cells, so each header-zone row of an output column
    # holds at most one header cell, and the matrix writes that cell's text unchanged.
    for html in (CRM_26_HTML, AAPL_15_HTML, KO_18_HTML, MIXED_DIRECTION_HTML, JPM_109_HTML):
        parser = _parser(html)
        matrix = parser.to_matrix()
        for index in range(len(parser.columns)):
            per_row = parser.column_header_cells(index)
            assert len(per_row) == len(parser.roles.header_rows)
            assert all(len(cells) <= 1 for cells in per_row), (
                index, [[cell.text for cell in cells] for cells in per_row])
            for row, cells in zip(parser.roles.header_rows, per_row):
                assert matrix[row][index] == (cells[0].text if cells else "")


@pytest.mark.parametrize("html", [CRM_26_HTML, JPM_109_HTML, TSLA_38_HTML, AAPL_15_HTML,
                                  KO_18_HTML, MIXED_DIRECTION_HTML],
                         ids=["crm-26", "jpm-109", "tsla-38", "aapl-15", "ko-18", "mixed"])
def test_merges_keep_every_source_cell_text(html):
    parser = _parser(html)
    kept = " ".join(" ".join(row) for row in parser.to_matrix())
    for row in parser.cells:
        for cell in row:
            assert cell.text in kept


def _fixture_tables(fixture_id):
    import warnings

    from sec2md.encoding import decode_html
    from tests.accuracy.fixtures import load_fixture

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        soup = BeautifulSoup(decode_html(load_fixture(fixture_id)[1])[0], "lxml")
    return soup.find_all("table")


def _fixture_ids():
    from tests.accuracy.fixtures import FIXTURE_IDS

    return FIXTURE_IDS


@pytest.mark.parametrize("fixture_id", _fixture_ids())
def test_r6_invariant_one_header_cell_per_row_and_output_column(fixture_id):
    # R2 and R3 guarantee it; the fallback join of conflicting texts is never accepted.
    for table in _fixture_tables(fixture_id):
        parser = TableParser(table)
        for index in range(len(parser.columns)):
            assert all(len(cells) <= 1 for cells in parser.column_header_cells(index)), (
                fixture_id, index, parser.md()[:200])


# Grid-hidden rows and cells (spec revision 11): left out before placement, with the
# snapshot builder's rule (xlsx_tables._hidden on the element or an ancestor inside the table).
HIDE = 'style="display:none"'

# The corpus run's S2 reproduction (edgar:CAT-10-K table 34's shape).
CAT_34_HIDDEN_HTML = (
    "<table>"
    f"<tr><td>Millions of dollars</td><td {HIDE}></td><td colspan='2'>Twelve Months Ended December 31,</td></tr>"
    f"<tr><td></td><td {HIDE}></td><td {HIDE}></td><td>2024</td><td>2023</td></tr>"
    f"<tr><td>Free cash flow</td><td {HIDE}></td><td {HIDE}></td><td>9,449</td><td>10,025</td></tr>"
    "</table>"
)

# edgar:BAC-10-K table 336's shape: one row carries one hidden cell fewer than the others,
# so counting hidden cells would shift its values one column left.
BAC_336_HIDDEN_HTML = (
    "<table>"
    f"<tr><td>(Dollars in millions)</td><td {HIDE}></td><td {HIDE}></td><td>2024</td><td>2023</td></tr>"
    f"<tr><td>Net income</td><td {HIDE}></td><td {HIDE}></td><td>27,132</td><td>26,515</td></tr>"
    f"<tr><td>Compensation and benefits</td><td {HIDE}></td><td>40,182</td><td>38,330</td></tr>"
    "</table>"
)


def _origin_texts(parser):
    from sec2md.table_parser import _origin_cells

    return [[None if slot is None else slot.text for slot in row] for row in _origin_cells(parser.source_grid)]


def test_grid_hidden_cells_are_left_out_before_placement():
    parser = _parser(CAT_34_HIDDEN_HTML)
    assert _origin_texts(parser) == [
        ["Millions of dollars", "Twelve Months Ended December 31,", None],
        ["", "2024", "2023"],
        ["Free cash flow", "9,449", "10,025"],
    ]
    assert [len(row) for row in parser.cells] == [2, 3, 3]


def test_grid_hidden_cells_never_split_a_value_column():
    parser = _parser(BAC_336_HIDDEN_HTML)
    assert _origin_texts(parser) == [
        ["(Dollars in millions)", "2024", "2023"],
        ["Net income", "27,132", "26,515"],
        ["Compensation and benefits", "40,182", "38,330"],
    ]
    assert _membership(parser) == [([0], []), ([1], []), ([2], [])]


@pytest.mark.parametrize("hidden_row", [
    f"<tr {HIDE}><td>Restated total</td><td>999</td></tr>",
    "<tr hidden><td>Restated total</td><td>999</td></tr>",
    '<tr style="visibility: hidden"><td>Restated total</td><td>999</td></tr>',
], ids=["display-none", "hidden-attribute", "visibility-hidden"])
def test_grid_hidden_row_is_left_out(hidden_row):
    parser = _parser(
        "<table><tr><td></td><td>2025</td></tr>"
        f"{hidden_row}<tr><td>Revenue</td><td>100</td></tr></table>"
    )
    assert _origin_texts(parser) == [["", "2025"], ["Revenue", "100"]]
    assert "999" not in " ".join(" ".join(row) for row in parser.to_matrix())


def test_grid_hidden_cell_with_text_is_left_out_and_never_rendered():
    parser = _parser(
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        f"<tr><td>Revenue</td><td {HIDE}>Draft 123</td><td>100</td><td>90</td></tr></table>"
    )
    assert _origin_texts(parser) == [["", "2025", "2024"], ["Revenue", "100", "90"]]
    assert "Draft" not in " ".join(" ".join(row) for row in parser.to_matrix())


def test_cells_inside_a_hidden_wrapper_within_the_table_are_left_out():
    parser = _parser(
        "<table><tbody><tr><td></td><td>2025</td></tr><tr><td>Revenue</td><td>100</td></tr></tbody>"
        f"<tbody {HIDE}><tr><td>Restated revenue</td><td>999</td></tr></tbody>"
        "<tbody><tr><td>Costs</td><td><span>60</span></td>"
        '<td style="visibility:hidden"><span>7</span></td></tr></tbody></table>'
    )
    assert _origin_texts(parser) == [["", "2025"], ["Revenue", "100"], ["Costs", "60"]]


def test_a_hidden_ancestor_outside_the_table_hides_nothing():
    # The rule looks at the element and its ancestors inside the table only.
    table = BeautifulSoup(
        f"<div {HIDE}><table><tr><td></td><td>2025</td></tr><tr><td>Revenue</td><td>100</td></tr></table></div>",
        "lxml",
    ).find("table")
    assert _origin_texts(TableParser(table)) == [["", "2025"], ["Revenue", "100"]]


# edgar:JPM-10-K table 606's shape: a header row of rowspan-2 cells over a row that holds
# only a hidden cell. That row stays, empty, so the rowspans end on it, as in the snapshot
# builder; dropping it would let them cover the first data row and push its cells out.
JPM_606_HIDDEN_HTML = (
    "<table>"
    "<tr><td rowspan='2'>Year ended December 31,</td><td rowspan='2'>Unrealized gains</td>"
    "<td rowspan='2'>Fair value hedges</td></tr>"
    f"<tr><td colspan='3' {HIDE}></td></tr>"
    "<tr><td>Balance at December 31, 2021</td><td>$ 2,640</td><td>$ (131)</td></tr>"
    "<tr><td>Net change</td><td>(11,764)</td><td>98</td></tr>"
    "</table>"
)


def test_row_of_grid_hidden_cells_stays_an_empty_row_under_rowspans():
    parser = _parser(JPM_606_HIDDEN_HTML)
    assert [len(row) for row in parser.cells] == [3, 0, 3, 3]
    assert _origin_texts(parser) == [
        ["Year ended December 31,", "Unrealized gains", "Fair value hedges"],
        ["Balance at December 31, 2021", "$ 2,640", "$ (131)"],
        ["Net change", "(11,764)", "98"],
    ]


def test_rowspan_label_over_a_row_of_grid_hidden_cells_keeps_later_rows_in_place():
    # edgar:BAC-10-K table 320's shape: a rowspan cell covers a row whose cells are hidden.
    parser = _parser(
        "<table><tr><td>Instrument</td><td>Fair Value</td><td>Technique</td></tr>"
        "<tr><td>Residential</td><td>$ 636</td><td rowspan='3'>Discounted cash flow</td></tr>"
        f"<tr><td {HIDE}></td><td {HIDE}></td></tr>"
        "<tr><td>Loans</td><td>77</td></tr>"
        "<tr><td>Commercial</td><td>$ 555</td><td>Market comparables</td></tr></table>"
    )
    assert _origin_texts(parser) == [
        ["Instrument", "Fair Value", "Technique"],
        ["Residential", "$ 636", "Discounted cash flow"],
        ["Loans", "77", None],
        ["Commercial", "$ 555", "Market comparables"],
    ]


# --- R5, R6, R7: the header line --------------------------------------------------------
# Each class case is a minimal copy of a real table from the evidence report; the
# expected Markdown follows from the rules, header line first.

PER_CLASS_CASES = {
    # Class 1, row-0 amounts: headerless, so the header line has empty cells.
    "jpm-109": (JPM_109_HTML, [
        "|  |  |  |",
        "| --- | --- | --- |",
        "| Noninterest revenue – reported (c) | $ 84,973 | $ 68,837 |",
        "| Fully taxable-equivalent adjustments (c) | 2,560 | 3,782 |",
        "| Noninterest revenue – managed basis | $ 87,533 | $ 72,619 |",
    ]),
    # Class 1, row-0 caption: the caption and the years stay header; the caption's spacer
    # column keeps its own header (R2, R7).
    "crm-26": (CRM_26_HTML, [
        "| 4 | Fiscal Year Ended January 31, | Fiscal Year Ended January 31, — 2025 "
        "| Fiscal Year Ended January 31, — 2024 | 2023 |",
        "| --- | --- | --- | --- | --- |",
        "| Net cash provided by operating activities |  | $ 13,092 | $ 10,234 | $ 7,111 |",
        "| Net cash used in investing activities |  | (3,163) | (1,327) | (1,989) |",
    ]),
    # Class 2: the Notes column and 2022's amounts stay apart (edgar:TSM-20-F table 248).
    "tsm-248": (
        "<table><tr><td></td><td>Notes</td><td colspan=\"2\">2022</td><td></td>"
        "<td colspan=\"2\">2023</td><td></td></tr>"
        "<tr><td></td><td></td><td colspan=\"2\">NT$</td><td></td><td colspan=\"2\">NT$</td><td></td></tr>"
        "<tr><td>Gain (loss) on hedging instruments</td><td></td><td>$</td><td>1,329.2</td><td></td>"
        "<td>$</td><td>( 74.7</td><td>)</td></tr>"
        "<tr><td>EARNINGS PER SHARE</td><td>27</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>"
        "<tr><td>Basic earnings per share</td><td></td><td>$</td><td>38.29</td><td></td>"
        "<td>$</td><td>32.85</td><td></td></tr></table>",
        [
            "|  | Notes | 2022 — NT$ | 2023 — NT$ |",
            "| --- | --- | --- | --- |",
            "| Gain (loss) on hedging instruments |  | $ 1,329.2 | $ ( 74.7) |",
            "| EARNINGS PER SHARE | 27 |  |  |",
            "| Basic earnings per share |  | $ 38.29 | $ 32.85 |",
        ],
    ),
    # Class 2: "Filed Herewith" X marks stay out of "Number" (rcq:RDDT 10-Q 2024 Q2 table 52).
    "rddt-52": (
        "<table><tr><td>Exhibit Number</td><td>Exhibit Description</td>"
        "<td colspan=\"3\">Incorporated by Reference</td><td>Filed Herewith</td></tr>"
        "<tr><td></td><td></td><td>Form</td><td>Filing Date</td><td>Number</td><td></td></tr>"
        "<tr><td>3.1</td><td>Amended and Restated Certificate of Incorporation</td><td>8-K</td>"
        "<td>3/25/2024</td><td>3.1</td><td></td></tr>"
        "<tr><td>31.1</td><td>Certification of Principal Executive Officer</td><td></td><td></td>"
        "<td></td><td>X</td></tr></table>",
        [
            "| Exhibit Number | Exhibit Description | Incorporated by Reference — Form "
            "| Incorporated by Reference — Filing Date | Incorporated by Reference — Number "
            "| Filed Herewith |",
            "| --- | --- | --- | --- | --- | --- |",
            "| 3.1 | Amended and Restated Certificate of Incorporation | 8-K | 3/25/2024 | 3.1 |  |",
            "| 31.1 | Certification of Principal Executive Officer |  |  |  | X |",
        ],
    ),
    # Class 3: a year starting on the "$" column (edgar:MSFT-10-K table 24). The label-only
    # "Revenue:" row right before the first data row is a body section label (revision 8).
    "msft-24": (
        "<table><tr><td>(In millions, except per share amounts)</td><td></td><td></td><td></td><td></td></tr>"
        "<tr><td>Year Ended June 30,</td><td colspan=\"2\">2025</td><td colspan=\"2\">2024</td></tr>"
        "<tr><td>Revenue:</td><td></td><td></td><td></td><td></td></tr>"
        "<tr><td>Product</td><td>$</td><td>63,946</td><td>$</td><td>64,773</td></tr>"
        "<tr><td>Service and other</td><td></td><td>217,778</td><td></td><td>180,349</td></tr></table>",
        [
            "| (In millions, except per share amounts) — Year Ended June 30, | 2025 | 2024 |",
            "| --- | --- | --- |",
            "| Revenue: |  |  |",
            "| Product | $ 63,946 | $ 64,773 |",
            "| Service and other | 217,778 | 180,349 |",
        ],
    ),
    # Class 3, empty-slot shift (edgar:BABA-20-F table 24).
    "baba-24": (
        "<table><tr><td></td><td></td><td></td><td colspan=\"7\">Year ended March 31,</td></tr>"
        "<tr><td></td><td></td><td></td><td colspan=\"2\">2023</td><td></td><td></td>"
        "<td colspan=\"2\">2024</td><td></td></tr>"
        "<tr><td></td><td></td><td></td><td colspan=\"2\">RMB</td><td></td><td></td>"
        "<td colspan=\"2\">RMB</td><td></td></tr>"
        "<tr><td></td><td>Notes</td><td></td><td colspan=\"2\"></td><td></td><td></td>"
        "<td colspan=\"2\"></td><td></td></tr>"
        "<tr><td>Revenue</td><td>5, 24</td><td></td><td></td><td>868,687</td><td></td><td></td>"
        "<td></td><td>941,168</td><td></td></tr>"
        "<tr><td>Cost of revenue</td><td>24</td><td></td><td></td><td>( 549,695</td><td>)</td><td></td>"
        "<td></td><td>( 586,323</td><td>)</td></tr></table>",
        [
            "|  | Notes | Year ended March 31, — 2023 — RMB | Year ended March 31, — 2024 — RMB |",
            "| --- | --- | --- | --- |",
            "| Revenue | 5, 24 | 868,687 | 941,168 |",
            "| Cost of revenue | 24 | ( 549,695) | ( 586,323) |",
        ],
    ),
    # Class 3: a footnote column inside a segment span (edgar:JPM-10-K table 482). "(b)(c)"
    # keeps its own column under its segment's header; "Consumer" starts one column
    # before the "2024" span, as in the source, so that column is header-only.
    "jpm-482": (
        "<table><tr><td></td><td></td><td colspan=\"9\">2024</td></tr>"
        "<tr><td>Year ended December 31, (in millions)</td>"
        "<td colspan=\"4\">Consumer, excluding credit card</td><td colspan=\"2\">Credit card</td>"
        "<td colspan=\"2\">Wholesale</td><td colspan=\"2\">Total</td></tr>"
        "<tr><td>Purchases</td><td></td><td>$</td><td>647</td><td>(b)(c)</td><td>$</td><td>—</td>"
        "<td>$</td><td>1,432</td><td>$</td><td>2,079</td></tr>"
        "<tr><td>Sales</td><td></td><td colspan=\"2\">10,440</td><td></td><td colspan=\"2\">—</td>"
        "<td colspan=\"2\">45,147</td><td colspan=\"2\">55,587</td></tr></table>",
        [
            "| Year ended December 31, (in millions) | Consumer, excluding credit card "
            "| 2024 — Consumer, excluding credit card | 2024 — Consumer, excluding credit card "
            "| 2024 — Credit card | 2024 — Wholesale | 2024 — Total |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            "| Purchases |  | $ 647 | (b)(c) | $ — | $ 1,432 | $ 2,079 |",
            "| Sales |  | 10,440 |  | — | 45,147 | 55,587 |",
        ],
    ),
    # Class 5: "Products 36.5 %" is data, never header (fixture:aapl-2023-10k table 18).
    "aapl-18": (
        "<table><tr><td>Gross margin percentage:</td><td colspan=\"2\"></td><td colspan=\"2\"></td></tr>"
        "<tr><td>Products</td><td>36.5</td><td>%</td><td>36.3</td><td>%</td></tr>"
        "<tr><td>Services</td><td>70.8</td><td>%</td><td>71.7</td><td>%</td></tr></table>",
        # Revision 8: "Gross margin percentage:" is a trailing label-only row (a body
        # section label), so the header zone is empty.
        [
            "|  |  |  |",
            "| --- | --- | --- |",
            "| Gross margin percentage: |  |  |",
            "| Products | 36.5 % | 36.3 % |",
            "| Services | 70.8 % | 71.7 % |",
        ],
    ),
    # Class 5: Class A's share count stays in the body (rcq:META 10-Q 2024 Q1 table 4).
    "meta-4": (
        "<table><tr><td colspan=\"2\">Class</td><td colspan=\"2\">Number of Shares Outstanding</td></tr>"
        "<tr><td>Class A Common Stock</td><td>$0.000006 par value</td><td>2,191,446,233</td>"
        "<td>shares outstanding as of April 19, 2024</td></tr>"
        "<tr><td>Class B Common Stock</td><td>$0.000006 par value</td><td>345,087,958</td>"
        "<td>shares outstanding as of April 19, 2024</td></tr></table>",
        [
            "| Class | Class | Number of Shares Outstanding | Number of Shares Outstanding |",
            "| --- | --- | --- | --- |",
            "| Class A Common Stock | $0.000006 par value | 2,191,446,233 "
            "| shares outstanding as of April 19, 2024 |",
            "| Class B Common Stock | $0.000006 par value | 345,087,958 "
            "| shares outstanding as of April 19, 2024 |",
        ],
    ),
    # Class 6: the signature date stays (edgar:GOOGL-10-Q table 89). No data row, so row
    # 0 alone is the header and row 1 is not fused into it (R5).
    "googl-89": (
        "<table><tr><td></td><td></td><td>ALPHABET INC.</td></tr>"
        "<tr><td>October 29, 2025</td><td>By:</td><td>/s/ ANAT ASHKENAZI</td></tr>"
        "<tr><td></td><td></td><td>Anat Ashkenazi</td></tr>"
        "<tr><td></td><td></td><td>Senior Vice President, Chief Financial Officer</td></tr></table>",
        [
            "|  |  | ALPHABET INC. |",
            "| --- | --- | --- |",
            "| October 29, 2025 | By: | /s/ ANAT ASHKENAZI |",
            "|  |  | Anat Ashkenazi |",
            "|  |  | Senior Vice President, Chief Financial Officer |",
        ],
    ),
    # Class 6: exhibit-index columns stay (fixture:aapl-2023-10k table 64). "104**" is a
    # footnoted complete number (revision 7), but one label-column number makes no
    # identifier column, so the table has no data row and row 0 alone is the header.
    "aapl-64": (
        "<table><tr><td colspan=\"2\"></td><td colspan=\"3\">Incorporated by Reference</td></tr>"
        "<tr><td>Exhibit Number</td><td>Exhibit Description</td><td>Form</td><td>Exhibit</td>"
        "<td>Filing Date/ Period End Date</td></tr>"
        "<tr><td>104**</td><td>Inline XBRL for the cover page of this Annual Report on Form 10-K</td>"
        "<td></td><td></td><td></td></tr></table>",
        [
            "|  |  | Incorporated by Reference | Incorporated by Reference | Incorporated by Reference |",
            "| --- | --- | --- | --- | --- |",
            "| Exhibit Number | Exhibit Description | Form | Exhibit | Filing Date/ Period End Date |",
            "| 104** | Inline XBRL for the cover page of this Annual Report on Form 10-K |  |  |  |",
        ],
    ),
    # Class 8: one negative per ")" column (edgar:BABA-20-F table 69).
    "baba-69": (
        "<table><tr><td></td><td></td><td colspan=\"6\">As of March 31,</td><td></td></tr>"
        "<tr><td></td><td></td><td colspan=\"2\">2024</td><td></td><td></td><td colspan=\"2\">2025</td><td></td></tr>"
        "<tr><td></td><td></td><td colspan=\"2\">RMB</td><td></td><td></td><td colspan=\"2\">RMB</td><td></td></tr>"
        "<tr><td>Deferred revenue</td><td></td><td></td><td>37,142</td><td></td><td></td><td></td>"
        "<td>44,138</td><td></td></tr>"
        "<tr><td>Less: current portion</td><td></td><td></td><td>( 72,818</td><td>)</td><td></td><td></td>"
        "<td>( 68,335</td><td>)</td></tr></table>",
        [
            "|  | As of March 31, — 2024 — RMB | As of March 31, — 2025 — RMB |",
            "| --- | --- | --- |",
            "| Deferred revenue | 37,142 | 44,138 |",
            "| Less: current portion | ( 72,818) | ( 68,335) |",
        ],
    ),
    # Class 8: the ")" column no longer shares 2024's "$" (edgar:MSFT-10-K table 43).
    "msft-43": (
        "<table><tr><td colspan=\"7\">(In millions)</td></tr>"
        "<tr><td>June 30,</td><td colspan=\"2\">2025</td><td></td><td colspan=\"2\">2024</td><td></td></tr>"
        "<tr><td>Land</td><td>$</td><td>9,338</td><td></td><td>$</td><td>8,163</td><td></td></tr>"
        "<tr><td>Buildings and improvements</td><td></td><td>137,921</td><td></td><td></td>"
        "<td>93,943</td><td></td></tr>"
        "<tr><td>Accumulated depreciation</td><td></td><td>( 93,653</td><td>)</td><td></td>"
        "<td>( 76,421</td><td>)</td></tr></table>",
        [
            "| (In millions) — June 30, | (In millions) — 2025 | (In millions) — 2024 |",
            "| --- | --- | --- |",
            "| Land | $ 9,338 | $ 8,163 |",
            "| Buildings and improvements | 137,921 | 93,943 |",
            "| Accumulated depreciation | ( 93,653) | ( 76,421) |",
        ],
    ),
}


@pytest.mark.parametrize("case", list(PER_CLASS_CASES))
def test_per_class_rendering(case):
    html, expected = PER_CLASS_CASES[case]
    assert _markdown(html) == expected


# The R0 named cases with their expected output headers (roles are pinned in
# tests/test_table_roles.py).
NAMED_ROLE_HEADERS = {
    "nvda-2026-10k-17": (
        '<table><tr><td></td><td colspan="4">Year Ended</td></tr>'
        '<tr><td></td><td colspan="2">Jan 25, 2026</td><td colspan="2">Jan 26, 2025</td></tr>'
        '<tr><td></td><td colspan="4">(In millions)</td></tr>'
        "<tr><td>Net cash provided by operating activities</td><td>$</td><td>102,718</td>"
        "<td>$</td><td>64,089</td></tr>"
        "<tr><td>Net cash used in investing activities</td><td>$</td><td>(52,228)</td>"
        "<td>$</td><td>(20,421)</td></tr></table>",
        "|  | Year Ended — Jan 25, 2026 — (In millions) | Year Ended — Jan 26, 2025 — (In millions) |",
        ["| Net cash provided by operating activities | $ 102,718 | $ 64,089 |",
         "| Net cash used in investing activities | $ (52,228) | $ (20,421) |"],
    ),
    "split-negative-first-data-row": (
        '<table><tr><th>Metric</th><th colspan="2">2025</th><th colspan="2">2024</th></tr>'
        "<tr><td>Loss</td><td>(29</td><td>)</td><td>(40</td><td>)</td></tr>"
        "<tr><td>Gain</td><td>50</td><td></td><td>60</td><td></td></tr></table>",
        "| Metric | 2025 | 2024 |",
        ["| Loss | (29) | (40) |", "| Gain | 50 | 60 |"],
    ),
    "single-digit-first-data-row": (
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Stores</td><td>9</td><td>7</td></tr><tr><td>Employees</td><td>3</td><td>4</td></tr></table>",
        "|  | 2025 | 2024 |",
        ["| Stores | 9 | 7 |", "| Employees | 3 | 4 |"],
    ),
    "exhibit-index-at-3.1": (
        "<table><tr><td>Exhibit Number</td><td>Description</td></tr>"
        "<tr><td>3.1</td><td>Articles of Incorporation</td></tr><tr><td>3.2</td><td>Bylaws</td></tr></table>",
        "| Exhibit Number | Description |",
        ["| 3.1 | Articles of Incorporation |", "| 3.2 | Bylaws |"],
    ),
    # Revision 8: a trailing label-only row is a body section label (nvda-2002-10k).
    "section-label-row": (
        "<table><tr><td></td><td>As of Jan 27, 2002</td><td>As of Jan 28, 2001</td></tr>"
        "<tr><td>Accounts Receivable:</td><td></td><td></td></tr>"
        "<tr><td>Accounts receivable</td><td>$ 100</td><td>$ 90</td></tr></table>",
        "|  | As of Jan 27, 2002 | As of Jan 28, 2001 |",
        ["| Accounts Receivable: |  |  |", "| Accounts receivable | $ 100 | $ 90 |"],
    ),
    # Revision 7: "2.1(1)" is a footnoted complete number (nvda-2002-10k exhibit index).
    "footnoted-exhibit-index": (
        "<table><tr><td>Exhibit Number</td><td>Description</td></tr>"
        "<tr><td>2.1(1)</td><td>Asset Purchase Agreement</td></tr>"
        "<tr><td>4.1</td><td>Specimen Stock Certificate</td></tr>"
        "<tr><td>10.2</td><td>Stock Plan</td></tr></table>",
        "| Exhibit Number | Description |",
        ["| 2.1(1) | Asset Purchase Agreement |", "| 4.1 | Specimen Stock Certificate |",
         "| 10.2 | Stock Plan |"],
    ),
    "exhibit-index-1-then-3.1": (
        "<table><tr><td>Exhibit Number</td><td>Description</td></tr>"
        "<tr><td>1</td><td>Agreement</td></tr><tr><td>3.1</td><td>Articles</td></tr></table>",
        "| Exhibit Number | Description |",
        ["| 1 | Agreement |", "| 3.1 | Articles |"],
    ),
    "all-integer-exhibit-index": (
        "<table><tr><td>Exhibit Number</td><td>Description</td></tr>"
        "<tr><td>1</td><td>Agreement</td></tr><tr><td>2</td><td>Plan</td></tr></table>",
        "| Exhibit Number | Description |",
        ["| 1 | Agreement |", "| 2 | Plan |"],
    ),
    "caption-number-control": (
        '<table><tr><td>4</td><td colspan="2">Fiscal Year Ended January 31,</td></tr>'
        "<tr><td></td><td>2025</td><td>2024</td></tr><tr><td>Revenue</td><td>100</td><td>200</td></tr></table>",
        "| 4 | Fiscal Year Ended January 31, — 2025 | Fiscal Year Ended January 31, — 2024 |",
        ["| Revenue | 100 | 200 |"],
    ),
    "text-table-without-data": (
        "<table><tr><td>Name</td><td>Title</td></tr><tr><td>Jane Doe</td><td>Director</td></tr>"
        "<tr><td>John Roe</td><td>Officer</td></tr></table>",
        "| Name | Title |",
        ["| Jane Doe | Director |", "| John Roe | Officer |"],
    ),
    "bare-year-label-column": (
        "<table><tr><td>Year</td><td>Amount</td></tr><tr><td>2025</td><td>100</td></tr>"
        "<tr><td>2024</td><td>90</td></tr></table>",
        "| Year | Amount |",
        ["| 2025 | 100 |", "| 2024 | 90 |"],
    ),
    "standalone-footnote-mark-in-header-row": (
        "<table><tr><td>Item</td><td>Amount</td><td>(1)</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td></td></tr><tr><td>Costs</td><td>60</td><td></td></tr></table>",
        "|  |  |  |",
        ["| Item | Amount | (1) |", "| Revenue | 100 |  |", "| Costs | 60 |  |"],
    ),
    "linked-number": (
        '<table><tr><th>Item</th><th>2025</th></tr><tr><td>Revenue</td>'
        '<td><a href="https://www.sec.gov/a/filing.htm#r1">1,234</a></td></tr></table>',
        "| Item | 2025 |",
        ["| Revenue | [1,234](https://www.sec.gov/a/filing.htm#r1) |"],
    ),
}


@pytest.mark.parametrize("case", list(NAMED_ROLE_HEADERS))
def test_named_role_case_renders_its_expected_header(case):
    html, header, body = NAMED_ROLE_HEADERS[case]
    lines = _markdown(html)
    assert lines[0] == header
    assert lines[2:] == body


# Renderer side of R0's coordinate equivalence: the same table as test_table_roles'
# PLACED grid, with a leading spacer column, a blank row, a rowspan and linked labels.
COORDINATE_HTML = (
    '<table><tr><td></td><td>4</td><td colspan="3">Fiscal Year Ended January 31,</td></tr>'
    "<tr><td></td><td></td><td></td><td></td><td></td></tr>"
    '<tr><td></td><td></td><td colspan="2">2025</td><td>2024</td></tr>'
    '<tr><td></td><td><a href="#revenue">Revenue</a></td><td>$</td><td>100</td><td>200</td></tr>'
    '<tr><td></td><td>Costs</td><td></td><td><a href="#costs">60</a></td><td>70</td></tr>'
    '<tr><td></td><td rowspan="2">Total</td><td>$</td><td>160</td><td>270</td></tr>'
    "<tr><td></td><td></td><td></td><td>5</td></tr></table>"
)


def test_renderer_reads_r0_on_its_cleaned_grid_like_the_placed_grid():
    from sec2md.table_parser import _origin_cells

    parser = _parser(COORDINATE_HTML)
    assert [[None if slot is None else slot.text for slot in row]
            for row in _origin_cells(parser.source_grid)] == [
        ["4", "Fiscal Year Ended January 31,", None, None],
        ["", "2025", None, "2024"],
        ["[Revenue](#revenue)", "$", "100", "200"],
        ["Costs", "", "[60](#costs)", "70"],
        ["Total", "$", "160", "270"],
        [None, "", "", "5"],
    ]
    assert parser.roles.header_rows == (0, 1)
    assert parser.roles.data_rows == (2, 3, 4, 5)
    assert parser.roles.label_column == 0


def test_spanning_header_and_its_equal_lower_text_are_written_once():
    # Astra's R6a source: a spanning 2025 over a lower 2025 and "Budget".
    assert _markdown(
        '<table><tr><th></th><th colspan="2">2025</th></tr>'
        "<tr><th>Item</th><th>2025</th><th>Budget</th></tr>"
        "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
    ) == ["| Item | 2025 | 2025 — Budget |", "| --- | --- | --- |", "| Revenue | 100 | 200 |"]


def test_rowspan_header_cell_appears_once_per_column():
    assert _markdown(
        '<table><tr><th rowspan="2">Item</th><th colspan="2">2025</th></tr>'
        "<tr><th>Actual</th><th>Budget</th></tr>"
        "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
    )[0] == "| Item | 2025 — Actual | 2025 — Budget |"


def test_equal_header_texts_compare_by_normalized_visible_text():
    # Case and whitespace do not make a lower text new, with or without the same link.
    assert _markdown(
        '<table><tr><th></th><th>Total</th></tr><tr><th></th><th>TOTAL </th></tr>'
        "<tr><td>Revenue</td><td>100</td></tr></table>"
    )[0] == "|  | Total |"
    assert _markdown(
        '<table><tr><th></th><th><a href="#t">Total</a></th></tr><tr><th></th><th><a href="#t">TOTAL </a></th></tr>'
        "<tr><td>Revenue</td><td>100</td></tr></table>"
    )[0] == "|  | [Total](#t) |"


@pytest.mark.parametrize("upper, lower, header", [
    ('<a href="ex101.htm">Plan</a>', '<a href="ex102.htm">Plan</a>', "[Plan](ex101.htm) — [Plan](ex102.htm)"),
    ("Total", '<a href="#t">TOTAL</a>', "Total — [TOTAL](#t)"),
], ids=["different-destinations", "link-and-no-link"])
def test_equal_labels_with_different_links_are_both_kept(upper, lower, header):
    # Revision 11, R6 step 2: equality compares link destinations too (was: suppressed by
    # label, which dropped META 10-Q 2026-Q1 table 39's second exhibit link).
    assert _markdown(
        f"<table><tr><th></th><th>{upper}</th></tr><tr><th></th><th>{lower}</th></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table>"
    )[0] == f"|  | {header} |"


@pytest.mark.parametrize("html, header", [
    # Only a text equal to the one kept just before it is skipped: each lower 2025 is a
    # new cell after "Q1" or "Q2", so it is written again.
    ('<table><tr><th></th><th colspan="2">2025</th></tr>'
     "<tr><th></th><th>Q1</th><th>Q2</th></tr>"
     "<tr><th>x</th><th>2025</th><th>2025</th></tr>"
     "<tr><td>Revenue</td><td>100</td><td>3</td></tr></table>",
     "| x | 2025 — Q1 — 2025 | 2025 — Q2 — 2025 |"),
    # Whitespace inside a text is collapsed before comparing: a line break in the lower cell
    # does not make it new.
    ("<table><tr><th></th><th>Total amount</th></tr><tr><th></th><th>Total\n   amount</th></tr>"
     "<tr><td>Revenue</td><td>100</td></tr></table>",
     "|  | Total amount |"),
    # An empty header row between two equal texts does not separate them.
    ("<table><tr><th></th><th>Total</th><th>X</th></tr><tr><th></th><th></th><th>Y</th></tr>"
     "<tr><th></th><th>Total</th><th>Z</th></tr>"
     "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>",
     "|  | Total | X — Y — Z |"),
], ids=["adjacent-only", "whitespace-collapsed", "empty-row-between"])
def test_r6_skips_only_a_text_equal_to_the_one_kept_before_it(html, header):
    assert _markdown(html)[0] == header


# Malformed markup: row 1's colspan overlaps the 2025 rowspan, so placement gives row 1 of
# that column to "Budget" and the same 2025 cell comes back below it.
OVERLAPPING_SPANS_HTML = (
    '<table><tr><td></td><td>X</td><td rowspan="3">2025</td></tr>'
    '<tr><td></td><td colspan="2">Budget</td></tr>'
    "<tr><td></td><td>Y</td></tr>"
    "<tr><td>Revenue</td><td>1</td><td>2</td></tr></table>"
)


def test_a_header_cell_is_written_once_per_column_when_spans_overlap():
    # R6: a cell already written in a column is not written again, as a rowspan is not, so
    # the header line stays within header_capacity (R6a), which counts each cell once per
    # column (was "2025 — Budget — 2025" with a capacity of one 2025).
    assert _markdown(OVERLAPPING_SPANS_HTML) == [
        "|  | X — Budget — Y | 2025 — Budget |",
        "| --- | --- | --- |",
        "| Revenue | 1 | 2 |",
    ]
    record, markdown = _record(OVERLAPPING_SPANS_HTML)
    assert record.header_line == markdown.splitlines()[0]
    assert record.header_source == record.header_capacity == (("2025", 1),)


@pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])
def test_overlapping_spans_pass_strict(capture_tables):
    # main passes this document; the header line must not invent a second 2025.
    from sec2md.parser import Parser
    from sec2md.quality import enforce_quality

    parser = Parser(
        "<html><body><p>Segment results for the year are shown below.</p>"
        f"{OVERLAPPING_SPANS_HTML}<p>End of note.</p></body></html>",
        capture_tables=capture_tables,
    )
    parser.get_pages()
    assert parser.trace_numeric_failures == ()
    enforce_quality(parser.diagnostics, "strict")


def test_header_record_counts_a_table_nested_in_a_header_cell_once():
    # The nested cells are read as cells of the outer row and of their own row, and the
    # outer cell's text already holds theirs. R6a counts each source cell once, as strict's
    # pool holds it: one 2024 (was three, which let three header copies pass strict).
    from collections import Counter

    from sec2md.quality import _normalized_numbers

    html = ("<table><tr><th>Item</th><th>Period<table><tr><th>Fiscal</th><th>2024</th></tr></table></th></tr>"
            "<tr><td>Revenue</td><td>100</td></tr></table>")
    record, markdown = _record(html)
    assert markdown.splitlines()[0] == "| Item — Fiscal | Period Fiscal 2024 — 2024 | Fiscal | 2024 |"
    assert Counter(_normalized_numbers(_table(html).get_text(" ", strip=True)))["2024"] == 1
    assert record.header_source == record.header_capacity == (("2024", 1),)


@pytest.mark.parametrize("nested", [
    "<table><tr><th>Fiscal</th><th>2024</th></tr></table>",
    "<div><table><tr><th>Fiscal</th><th>2024</th></tr></table></div>",
], ids=["tr-direct", "div-wrapped"])
def test_header_record_reads_each_cell_of_a_table_nested_in_a_header_row_once(nested):
    # lxml keeps a table placed in a <tr> (directly or in a wrapper) inside that row, and no
    # zone cell holds it. R6a counts each source cell once: one 2024 heading one column.
    # Revision 18 (C1): its rows are no longer also read as header rows, so 2024 is written once.
    from collections import Counter

    from sec2md.quality import _normalized_numbers

    html = (f"<table><tr><th>Item</th><th>Period</th>{nested}</tr>"
            "<tr><td>Revenue</td><td>100</td></tr></table>")
    record, markdown = _record(html)
    assert markdown.splitlines()[0] == "| Item | Period | Fiscal | 2024 |"
    assert Counter(_normalized_numbers(_table(html).get_text(" ", strip=True)))["2024"] == 1
    assert record.header_source == record.header_capacity == (("2024", 1),)


def test_header_only_column_stays():
    # R7: "(a)" heads a column with no body text (nvda-2026-10k table 20's shape).
    assert _markdown(
        "<table><tr><th>Statement</th><th>Page</th><th>(a)</th></tr>"
        "<tr><td>Balance Sheets</td><td>45</td><td></td></tr>"
        "<tr><td>Income Statements</td><td>46</td><td></td></tr></table>"
    ) == [
        "| Statement | Page | (a) |",
        "| --- | --- | --- |",
        "| Balance Sheets | 45 |  |",
        "| Income Statements | 46 |  |",
    ]


def test_single_data_row_table_renders_an_empty_header_line():
    assert _markdown("<table><tr><td>Revenue</td><td>100</td></tr></table>") == [
        "|  |  |", "| --- | --- |", "| Revenue | 100 |"]


def test_zero_width_cell_beside_an_amount():
    assert _markdown(
        '<table><tr><td></td><td colspan="3">2025</td></tr>'
        "<tr><td>Revenue</td><td>$</td><td>1,234</td><td>\u200b</td></tr>"
        "<tr><td>Costs</td><td>\u200b</td><td>567</td><td>\u200b</td></tr></table>"
    ) == ["|  | 2025 |", "| --- | --- |", "| Revenue | $ 1,234 |", "| Costs | 567 |"]


def test_leading_dot_per_share_values():
    assert _markdown(
        '<table><tr><td></td><td colspan="2">2002</td><td colspan="2">2001</td></tr>'
        "<tr><td>Basic</td><td>$</td><td>.75</td><td>$</td><td>.62</td></tr>"
        "<tr><td>Diluted</td><td>$</td><td>(.62)</td><td>$</td><td>.60</td></tr></table>"
    ) == [
        "|  | 2002 | 2001 |",
        "| --- | --- | --- |",
        "| Basic | $ .75 | $ .62 |",
        "| Diluted | $ (.62) | $ .60 |",
    ]


def test_marker_column_holding_a_nil_value_stays_split():
    # Recorded residual (class 8): whole-column validation rejects a ")" column that also
    # holds a nil value, so "(29" and ")" stay in two columns under the same span.
    assert _markdown(
        '<table><tr><td></td><td colspan="2">2025</td></tr>'
        "<tr><td>Loss</td><td>(29</td><td>)</td></tr>"
        "<tr><td>Other</td><td>40</td><td>—</td></tr></table>"
    ) == ["|  | 2025 | 2025 |", "| --- | --- | --- |", "| Loss | (29 | ) |", "| Other | 40 | — |"]


# --- R5 with revision 11's header zone: header-like rows only ----------------------------
# The corpus run's S1 reproductions (acceptance REPORT.md): body rows before the first row
# with a complete number stay in the body, as main renders them.

HEADER_ZONE_CASES = {
    # fixture:aapl-2023-10k table 8: trading symbols are text, the notes' symbols nil values.
    "securities": (
        "<table><tr><td>Title of each class</td><td>Trading symbol(s)</td></tr>"
        "<tr><td>Common Stock</td><td>AAPL</td></tr>"
        "<tr><td>1.375% Notes due 2024</td><td>—</td></tr></table>",
        ["| Title of each class | Trading symbol(s) |",
         "| --- | --- |",
         "| Common Stock | AAPL |",
         "| 1.375% Notes due 2024 | — |"],
    ),
    # META 10-K table 44's shape: values with units are not complete numbers.
    "values-with-units": (
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Finance leases</td><td>15.1 years</td><td>13.7 years</td></tr>"
        "<tr><td>Discount rate</td><td>4.1 %</td><td>3.6 %</td></tr></table>",
        ["|  | 2025 | 2024 |",
         "| --- | --- | --- |",
         "| Finance leases | 15.1 years | 13.7 years |",
         "| Discount rate | 4.1 % | 3.6 % |"],
    ),
    # KO 10-K table 110's shape: three-part exhibit numbers before the first two-part one.
    "exhibit-numbers": (
        "<table><tr><td>10.5.22</td><td>Plan A</td></tr><tr><td>10.5.23</td><td>Plan B</td></tr>"
        "<tr><td>10.6</td><td>Plan C</td></tr><tr><td>10.7</td><td>Plan D</td></tr></table>",
        ["| 10.5.22 | Plan A |",
         "| --- | --- |",
         "| 10.5.23 | Plan B |",
         "| 10.6 | Plan C |",
         "| 10.7 | Plan D |"],
    ),
    # META 10-Q 2026-Q1 table 39's shape: "10.1+" rows with equal descriptions and different
    # links stay body rows, so both links are kept.
    "linked-exhibit-pair": (
        "<table><tr><td>Exhibit Number</td><td>Exhibit Description</td></tr>"
        '<tr><td>10.1+</td><td><a href="ex101.htm">Director Compensation Policy</a></td></tr>'
        '<tr><td>10.2+</td><td><a href="ex102.htm">Director Compensation Policy</a></td></tr>'
        "<tr><td>31.1</td><td>Certification</td></tr><tr><td>31.2</td><td>Certification</td></tr></table>",
        ["| Exhibit Number | Exhibit Description |",
         "| --- | --- |",
         "| 10.1+ | [Director Compensation Policy](ex101.htm) |",
         "| 10.2+ | [Director Compensation Policy](ex102.htm) |",
         "| 31.1 | Certification |",
         "| 31.2 | Certification |"],
    ),
    # A column-heading second row under a first row that is not sparse ends the zone and
    # stays in the body, as main renders it.
    "column-heading-second-row-under-a-full-row": (
        '<table><tr><td>Obligations</td><td colspan="2">Payments Due by Period</td></tr>'
        "<tr><td>Contractual obligations</td><td>Total</td><td>Less than 1 year</td></tr>"
        "<tr><td>Long-term debt</td><td>$ 9,000</td><td>$ 1,000</td></tr></table>",
        ["| Obligations | Payments Due by Period | Payments Due by Period |",
         "| --- | --- | --- |",
         "| Contractual obligations | Total | Less than 1 year |",
         "| Long-term debt | $ 9,000 | $ 1,000 |"],
    ),
    # Revision 12 (S8): under a sparse first row, main fuses the column headings into its
    # header line, so they stay in the zone.
    "column-heading-second-row-under-a-sparse-row": (
        '<table><tr><td></td><td colspan="3">Payments Due by Period</td></tr>'
        "<tr><td>Contractual obligations</td><td>Total</td><td>Less than 1 year</td><td>1-3 years</td></tr>"
        "<tr><td>Long-term debt</td><td>$ 9,000</td><td>$ 1,000</td><td>$ 2,000</td></tr></table>",
        ["| Contractual obligations | Payments Due by Period — Total | Payments Due by Period — Less than 1 year "
         "| Payments Due by Period — 1-3 years |",
         "| --- | --- | --- | --- |",
         "| Long-term debt | $ 9,000 | $ 1,000 | $ 2,000 |"],
    ),
    # The fusion applies to the second row only: a third column-heading row is body.
    "third-column-heading-row": (
        '<table><tr><td></td><td colspan="3">Payments Due by Period</td></tr>'
        "<tr><td>Contractual obligations</td><td>Total</td><td>Less than 1 year</td><td>1-3 years</td></tr>"
        "<tr><td>Obligation type</td><td>All</td><td>Short</td><td>Medium</td></tr>"
        "<tr><td>Long-term debt</td><td>$ 9,000</td><td>$ 1,000</td><td>$ 2,000</td></tr></table>",
        ["| Contractual obligations | Payments Due by Period — Total | Payments Due by Period — Less than 1 year "
         "| Payments Due by Period — 1-3 years |",
         "| --- | --- | --- | --- |",
         "| Obligation type | All | Short | Medium |",
         "| Long-term debt | $ 9,000 | $ 1,000 | $ 2,000 |"],
    ),
    # S8: an exhibit index title over its column headings (fixtures aapl-2023-10k 61-63,
    # nvda-2026-10k 61, nvda-2026-q2-10q 51 have this pair under a caption span).
    "exhibit-index-title": (
        '<table><tr><td colspan="3">Exhibit Index</td></tr>'
        "<tr><td>Exhibit Number</td><td>Description</td><td>Filed Herewith</td></tr>"
        "<tr><td>3.1</td><td>Articles of Incorporation</td><td></td></tr>"
        "<tr><td>31.1</td><td>Certification</td><td>X</td></tr></table>",
        ["| Exhibit Index — Exhibit Number | Exhibit Index — Description | Exhibit Index — Filed Herewith |",
         "| --- | --- | --- |",
         "| 3.1 | Articles of Incorporation |  |",
         "| 31.1 | Certification | X |"],
    ),
    # S8: rcq META 10-K 2025-FY table 37's shape, the balance date among the headings.
    "fair-value-headings": (
        '<table><tr><td></td><td colspan="2"></td><td colspan="6">Fair Value Measurement Using</td></tr>'
        '<tr><td>Description</td><td colspan="2">December 31, 2024</td><td colspan="2">Level 1</td>'
        '<td colspan="2">Level 2</td><td colspan="2">Level 3</td></tr>'
        "<tr><td>Cash equivalents:</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>"
        "<tr><td>Money market funds</td><td>$</td><td>36,165</td><td>$</td><td>36,165</td><td>$</td><td>—</td>"
        "<td>$</td><td>—</td></tr>"
        "<tr><td>Time deposits</td><td></td><td>369</td><td></td><td>—</td><td></td><td>369</td><td></td><td>—</td>"
        "</tr></table>",
        ["| Description | December 31, 2024 | Fair Value Measurement Using — Level 1 "
         "| Fair Value Measurement Using — Level 2 | Fair Value Measurement Using — Level 3 |",
         "| --- | --- | --- | --- | --- |",
         "| Cash equivalents: |  |  |  |  |",
         "| Money market funds | $ 36,165 | $ 36,165 | $ — | $ — |",
         "| Time deposits | 369 | — | 369 | — |"],
    ),
    # S8: edgar:TSLA-10-K table 40's shape, a statement title beside the quarter-end dates.
    "statement-title-beside-dates": (
        '<table><tr><td></td><td colspan="6">Three Months Ended</td></tr>'
        "<tr><td>Condensed Consolidated Statements of Operations (unaudited):</td>"
        '<td colspan="2">March 31, 2024</td><td colspan="2">June 30, 2024</td><td colspan="2">September 30, 2024</td></tr>'
        "<tr><td>Other income (expense), net</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>"
        "<tr><td>Before adoption</td><td>$</td><td>108</td><td>$</td><td>20</td><td>$</td><td>(270)</td></tr>"
        "<tr><td>Adjustments</td><td></td><td>335</td><td></td><td>(100)</td><td></td><td>7</td></tr></table>",
        ["| Condensed Consolidated Statements of Operations (unaudited): | Three Months Ended — March 31, 2024 "
         "| Three Months Ended — June 30, 2024 | Three Months Ended — September 30, 2024 |",
         "| --- | --- | --- | --- |",
         "| Other income (expense), net |  |  |  |",
         "| Before adoption | $ 108 | $ 20 | $ (270) |",
         "| Adjustments | 335 | (100) | 7 |"],
    ),
    # Revision 12 (S7): fixture:nvda-2026-ex99-1 unit 5's shape. Stacked full-width titles
    # and captions are label-only rows, so they continue the zone and the dates join the
    # header line; the trailing section labels stay body.
    "stacked-titles": (
        '<table><tr><td colspan="3">NVIDIA CORPORATION</td></tr>'
        '<tr><td colspan="3">CONDENSED CONSOLIDATED BALANCE SHEETS</td></tr>'
        '<tr><td colspan="3">(In millions)</td></tr><tr><td colspan="3">(Unaudited)</td></tr>'
        "<tr><td></td><td>July 26,</td><td>January 25,</td></tr>"
        "<tr><td></td><td>2026</td><td>2026</td></tr>"
        '<tr><td colspan="3">ASSETS</td></tr><tr><td>Current assets:</td><td></td><td></td></tr>'
        "<tr><td>Cash and cash equivalents</td><td>$ 22,443</td><td>$ 10,605</td></tr></table>",
        ["| NVIDIA CORPORATION — CONDENSED CONSOLIDATED BALANCE SHEETS — (In millions) — (Unaudited) "
         "| NVIDIA CORPORATION — CONDENSED CONSOLIDATED BALANCE SHEETS — (In millions) — (Unaudited) — July 26, — 2026 "
         "| NVIDIA CORPORATION — CONDENSED CONSOLIDATED BALANCE SHEETS — (In millions) — (Unaudited) — January 25, — 2026 |",
         "| --- | --- | --- |",
         "| ASSETS |  |  |",
         "| Current assets: |  |  |",
         "| Cash and cash equivalents | $ 22,443 | $ 10,605 |"],
    ),
    # Revision 13 (S9): the "%" columns are marker-only, so they leave the sparse-row count
    # and the operating-lease row stays in the body, as main renders it (AMZN 10-Q table 21).
    "marker-columns-leave-the-sparse-row-count": (
        '<table><tr><td></td><td colspan="2">December 31, 2024</td><td colspan="2">September 30, 2025</td></tr>'
        '<tr><td>Remaining lease term, operating leases</td><td colspan="2">10.6 years</td>'
        '<td colspan="2">10.0 years</td></tr>'
        '<tr><td>Remaining lease term, finance leases</td><td colspan="2">11.9 years</td>'
        '<td colspan="2">12.1 years</td></tr>'
        "<tr><td>Discount rate, operating leases</td><td>3.5</td><td>%</td><td>3.6</td><td>%</td></tr></table>",
        ["|  | December 31, 2024 | September 30, 2025 |",
         "| --- | --- | --- |",
         "| Remaining lease term, operating leases | 10.6 years | 10.0 years |",
         "| Remaining lease term, finance leases | 11.9 years | 12.1 years |",
         "| Discount rate, operating leases | 3.5 % | 3.6 % |"],
    ),
    # Revision 13, the mirror case (JPM 10-K table 207's shape): without its "%" columns the
    # headings row is full, so it joins the header line, as main fuses it.
    "headings-fuse-without-marker-columns": (
        '<table><tr><td></td><td colspan="9">Three months ended</td></tr>'
        '<tr><td>Average amount (in millions)</td><td colspan="3">December 31, 2024</td>'
        '<td colspan="3">September 30, 2024</td><td colspan="3">December 31, 2023</td></tr>'
        "<tr><td>JPMorgan Chase &amp; Co.:</td><td></td><td></td><td></td><td></td><td></td><td></td>"
        "<td></td><td></td><td></td></tr>"
        "<tr><td>Eligible cash (a)</td><td>$</td><td>396,123</td><td></td><td>$</td><td>412,389</td><td></td>"
        "<td>$</td><td>485,263</td><td></td></tr>"
        '<tr><td>Eligible securities (b)(c)</td><td colspan="2">464,877</td><td></td>'
        '<td colspan="2">453,899</td><td></td><td colspan="2">313,365</td><td></td></tr>'
        '<tr><td>LCR</td><td colspan="2">113</td><td>%</td><td colspan="2">114</td><td>%</td>'
        '<td colspan="2">113</td><td>%</td></tr></table>',
        ["| Average amount (in millions) | Three months ended — December 31, 2024 "
         "| Three months ended — September 30, 2024 | Three months ended — December 31, 2023 |",
         "| --- | --- | --- | --- |",
         "| JPMorgan Chase & Co.: |  |  |  |",
         "| Eligible cash (a) | $ 396,123 | $ 412,389 | $ 485,263 |",
         "| Eligible securities (b)(c) | 464,877 | 453,899 | 313,365 |",
         "| LCR | 113 % | 114 % | 113 % |"],
    ),
    # Revision 13 control (nvda-2026-10k unit 38's shape): "$" columns that also hold the
    # dates and values written from them still count, so the pair fuses.
    "currency-columns-holding-values-still-count": (
        '<table><tr><td></td><td colspan="2">Jan 25, 2026</td><td colspan="2">Jan 26, 2025</td></tr>'
        '<tr><td>Inventories:</td><td colspan="4">(In millions)</td></tr>'
        "<tr><td>Raw materials</td><td>$</td><td>3,807</td><td>$</td><td>3,408</td></tr>"
        '<tr><td>Work in process</td><td colspan="2">8,822</td><td colspan="2">3,399</td></tr></table>',
        ["| Inventories: | Jan 25, 2026 — (In millions) | Jan 26, 2025 — (In millions) |",
         "| --- | --- | --- |",
         "| Raw materials | $ 3,807 | $ 3,408 |",
         "| Work in process | 8,822 | 3,399 |"],
    ),
    # Revision 15: a full-width caption whose cell starts in the label column is label-only
    # (decided by origin), so right before the data it is a body row ...
    "full-width-caption-from-the-label-column": (
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        '<tr><td colspan="3">(In millions)</td></tr>'
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        ["|  | 2025 | 2024 |",
         "| --- | --- | --- |",
         "| (In millions) |  |  |",
         "| Revenue | 100 | 90 |"],
    ),
    # ... while the same caption starting in a value column is not label-only: header.
    "caption-from-a-value-column": (
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        '<tr><td></td><td colspan="2">(In millions)</td></tr>'
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        ["|  | 2025 — (In millions) | 2024 — (In millions) |",
         "| --- | --- | --- |",
         "| Revenue | 100 | 90 |"],
    ),
    # Round-2 control: the label-only lease-term title continues the zone, the
    # "Finance leases | 15.1 years" row ends it, and the title then trails, so it is body.
    "lease-term-title": (
        "<table><tr><td></td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Weighted-average remaining lease term:</td><td></td><td></td></tr>"
        "<tr><td>Finance leases</td><td>15.1 years</td><td>13.7 years</td></tr>"
        "<tr><td>Weighted-average discount rate:</td><td></td><td></td></tr>"
        "<tr><td>Finance leases</td><td>3.5 %</td><td>3.4 %</td></tr></table>",
        ["|  | 2025 | 2024 |",
         "| --- | --- | --- |",
         "| Weighted-average remaining lease term: |  |  |",
         "| Finance leases | 15.1 years | 13.7 years |",
         "| Weighted-average discount rate: |  |  |",
         "| Finance leases | 3.5 % | 3.4 % |"],
    ),
    # Controls: header-like second rows keep today's multi-row header.
    "period-label-control": (
        '<table><tr><td></td><td colspan="2">Payments due</td></tr>'
        "<tr><td>Year Ended December 31,</td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        ["| Year Ended December 31, | Payments due — 2025 | Payments due — 2024 |",
         "| --- | --- | --- |",
         "| Revenue | 100 | 90 |"],
    ),
    # edgar:BAC-10-K table 46's shape: a unit-caption years row under the table title.
    "unit-caption-years-row": (
        '<table><tr><td>Table 2</td><td colspan="2">Noninterest Income</td></tr>'
        "<tr><td>(Dollars in millions)</td><td>2024</td><td>2023</td></tr>"
        "<tr><td>Fees and commissions:</td><td></td><td></td></tr>"
        "<tr><td>Card income</td><td>$ 5,964</td><td>$ 5,957</td></tr></table>",
        ["| Table 2 — (Dollars in millions) | Noninterest Income — 2024 | Noninterest Income — 2023 |",
         "| --- | --- | --- |",
         "| Fees and commissions: |  |  |",
         "| Card income | $ 5,964 | $ 5,957 |"],
    ),
    "year-like-label-control": (
        "<table><tr><td>Region</td><td>Q1</td><td>Q2</td></tr>"
        "<tr><td>2024(a)</td><td>Actual</td><td>Actual</td></tr>"
        "<tr><td>East</td><td>10</td><td>20</td></tr></table>",
        ["| Region — 2024(a) | Q1 — Actual | Q2 — Actual |",
         "| --- | --- | --- |",
         "| East | 10 | 20 |"],
    ),
    # edgar:TSM-20-F table 136's shape: the canonical years row, here under a caption.
    "year-run-control": (
        '<table><tr><td></td><td colspan="3">Year Ended December 31,</td></tr>'
        "<tr><td>Function</td><td>2022</td><td>2023</td><td>2024</td></tr>"
        "<tr><td>Research</td><td>10</td><td>20</td><td>30</td></tr></table>",
        ["| Function | Year Ended December 31, — 2022 | Year Ended December 31, — 2023 "
         "| Year Ended December 31, — 2024 |",
         "| --- | --- | --- | --- |",
         "| Research | 10 | 20 | 30 |"],
    ),
    "th-row-control": (
        '<table><tr><td></td><td colspan="2">Fiscal Year</td></tr>'
        "<tr><th>Item</th><th>Actual</th><th>Budget</th></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        ["| Item | Fiscal Year — Actual | Fiscal Year — Budget |",
         "| --- | --- | --- |",
         "| Revenue | 100 | 90 |"],
    ),
    # Years rows (spec revision 11): a year run, a unit caption or a year in the label
    # column keeps the years in the header line.
    "years-row-function": (
        "<table><tr><td>Function</td><td>2022</td><td>2023</td><td>2024</td></tr>"
        "<tr><td>Research</td><td>10</td><td>20</td><td>30</td></tr></table>",
        ["| Function | 2022 | 2023 | 2024 |", "| --- | --- | --- | --- |", "| Research | 10 | 20 | 30 |"],
    ),
    "years-row-dollars-caption": (
        "<table><tr><td>(Dollars in millions)</td><td>2024</td><td>2023</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        ["| (Dollars in millions) | 2024 | 2023 |", "| --- | --- | --- |", "| Revenue | 100 | 90 |"],
    ),
    "years-row-first-year-in-label-column": (
        "<table><tr><td>2023</td><td>2022</td></tr><tr><td>Revenue</td><td>100</td></tr></table>",
        ["| 2023 | 2022 |", "| --- | --- |", "| Revenue | 100 |"],
    ),
    "year-shaped-amounts-stay-data": (
        "<table><tr><td></td><td>2026</td><td>2025</td></tr>"
        "<tr><td>Revenue</td><td>2000</td><td>1900</td></tr></table>",
        ["|  | 2026 | 2025 |", "| --- | --- | --- |", "| Revenue | 2000 | 1900 |"],
    ),
    # Named limitation: bare years within one of each other read as a header row.
    "named-limitation-units": (
        "<table><tr><th>Item</th><th>First</th><th>Second</th></tr>"
        "<tr><td>Units</td><td>2024</td><td>2025</td></tr>"
        "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>",
        ["| Item — Units | First — 2024 | Second — 2025 |", "| --- | --- | --- |", "| Revenue | 100 | 90 |"],
    ),
}


@pytest.mark.parametrize("case", list(HEADER_ZONE_CASES))
def test_header_zone_continues_only_through_header_like_rows(case):
    html, expected = HEADER_ZONE_CASES[case]
    assert _markdown(html) == expected


def test_grid_hidden_cells_leave_spanning_headers_over_their_values():
    # The corpus run's S2 reproduction: main wrote "| Millions of dollars | 2024 | 2023 |".
    assert _markdown(CAT_34_HIDDEN_HTML) == [
        "| Millions of dollars | Twelve Months Ended December 31, — 2024 | Twelve Months Ended December 31, — 2023 |",
        "| --- | --- | --- |",
        "| Free cash flow | 9,449 | 10,025 |",
    ]


def test_grid_hidden_cells_keep_a_row_with_fewer_hidden_cells_in_its_columns():
    # BAC 336's shape: counting hidden cells split a value column.
    assert _markdown(BAC_336_HIDDEN_HTML) == [
        "| (Dollars in millions) | 2024 | 2023 |",
        "| --- | --- | --- |",
        "| Net income | 27,132 | 26,515 |",
        "| Compensation and benefits | 40,182 | 38,330 |",
    ]


def test_row_of_grid_hidden_cells_under_rowspans_keeps_the_first_data_row():
    # JPM 606's shape: the first data row is kept, under its headers.
    assert _markdown(JPM_606_HIDDEN_HTML) == [
        "| Year ended December 31, | Unrealized gains | Fair value hedges |",
        "| --- | --- | --- |",
        "| Balance at December 31, 2021 | $ 2,640 | $ (131) |",
        "| Net change | (11,764) | 98 |",
    ]


# --- R6a inputs: the per-render header record --------------------------------------------

def _record(html):
    parser = _parser(html)
    markdown = parser.md()
    return parser.header_record, markdown


def test_header_record_counts_spanning_headers_per_output_column():
    record, markdown = _record(PER_CLASS_CASES["jpm-482"][0])
    assert record.header_line == markdown.splitlines()[0]
    assert record.header_source == (("2024", 1), ("31", 1))
    # "2024" covers five output columns; "December 31," only the label column.
    assert record.header_capacity == (("2024", 5), ("31", 1))


def test_header_record_for_astras_repeated_2025_source():
    record, _ = _record(
        '<table><tr><th></th><th colspan="2">2025</th></tr>'
        "<tr><th>Item</th><th>2025</th><th>Budget</th></tr>"
        "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
    )
    assert record.header_line == "| Item | 2025 | 2025 — Budget |"
    assert record.header_source == (("2025", 2),)
    # Two columns under the spanning cell plus one under the lower cell.
    assert record.header_capacity == (("2025", 3),)


def test_header_record_of_a_headerless_table_has_no_header_line():
    record, markdown = _record(JPM_109_HTML)
    assert markdown.splitlines()[0] == "|  |  |  |"
    assert record.header_line is None
    assert record.header_source == record.header_capacity == ()


def test_header_record_reads_cell_nodes_not_link_destinations():
    record, markdown = _record(
        '<table><tr><th>Item</th><th><a href="https://www.sec.gov/2024/10.htm">2025</a></th></tr>'
        "<tr><td>Revenue</td><td>100</td></tr></table>"
    )
    assert markdown.splitlines()[0] == "| Item | [2025](https://www.sec.gov/2024/10.htm) |"
    assert record.header_source == record.header_capacity == (("2025", 1),)


def test_header_record_counts_each_header_cell_once_across_rowspans():
    record, _ = _record(
        '<table><tr><th rowspan="2">Fiscal 2025</th><th colspan="2">2025</th></tr>'
        "<tr><th>Q1</th><th>Q2</th></tr><tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
    )
    assert record.header_line == "| Fiscal 2025 | 2025 — Q1 | 2025 — Q2 |"
    # "Q1" and "Q2" hold no standalone number for strict's tokenizer.
    assert record.header_source == (("2025", 2),)
    assert record.header_capacity == (("2025", 3),)


def test_header_record_lists_each_header_cell_with_the_columns_it_heads():
    # The accuracy suite's own trace re-tokenizes these texts with its own normalizer.
    record, _ = _record(
        '<table><tr><th></th><th colspan="2">2025</th></tr>'
        "<tr><th>Item</th><th>2025</th><th>Budget</th></tr>"
        "<tr><td>Revenue</td><td>100</td><td>200</td></tr></table>"
    )
    # Document order, cells without text left out; the spanning 2025 heads two columns.
    assert record.header_cells == (("2025", 2), ("Item", 1), ("2025", 1), ("Budget", 1))


def test_header_record_of_a_headerless_table_lists_no_header_cells():
    record, _ = _record(JPM_109_HTML)
    assert record.header_cells == ()


# Malformed markup: lxml keeps a table placed directly in a header-zone <tr> inside that row.
# Revision 18 (C1): its cells are read once, in that row (they were read again as their own row).
NESTED_IN_HEADER_ROW_HTML = (
    "<table><tr><th>Item</th><th>Period</th><table><tr><th>Fiscal</th><th>2024</th></tr></table></tr>"
    "<tr><td>Revenue</td><td>100</td></tr></table>"
)


@pytest.mark.parametrize("case", [*sorted(PER_CLASS_CASES), "nested-in-header-row"])
def test_header_cells_reproduce_the_header_source_and_capacity(case):
    from collections import Counter

    from sec2md.quality import _normalized_numbers

    html = NESTED_IN_HEADER_ROW_HTML if case == "nested-in-header-row" else PER_CLASS_CASES[case][0]
    record, _ = _record(html)
    texts = [text for text, _ in record.header_cells]
    assert all(texts)
    assert tuple(sorted(Counter(_normalized_numbers(" ".join(texts))).items())) == record.header_source
    capacity: Counter[str] = Counter()
    for text, columns in record.header_cells:
        for token, count in Counter(_normalized_numbers(text)).items():
            capacity[token] += count * columns
    assert tuple(sorted((token, count) for token, count in capacity.items() if count)) == record.header_capacity
    if case == "nested-in-header-row":
        # Each source cell is listed once, as header_source counts it: one 2024 heading one column.
        assert record.header_source == record.header_capacity == (("2024", 1),)
        assert record.header_cells == (("Item", 1), ("Period", 1), ("Fiscal", 1), ("2024", 1))
        # Revision 18 (C1): the header line writes it once too (no second, nested header row).
        assert record.header_line == "| Item | Period | Fiscal | 2024 |"


def test_list_table_has_no_header_record():
    parser = _parser("<table><tr><td>•</td><td>List item text</td></tr></table>")
    assert parser.md() == "- List item text"
    assert parser.header_record is None


def test_header_record_is_none_until_a_render_writes_one():
    # Parser reads header_record after md(); a render replaced without writing one (the
    # fixtures' blank-renderer mutation) must leave None, not a missing attribute.
    parser = _parser('<table><tr><th>Item</th><th>2025</th></tr><tr><td>Revenue</td><td>100</td></tr></table>')
    assert parser.header_record is None
    parser.md()
    assert parser.header_record is not None


def test_year_shaped_amounts_beside_a_row_label_stay_in_the_body():
    # R0 (revision 6): the label "Revenue" lets the bare years of its row count.
    assert _markdown(
        "<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>2000</td><td>1900</td></tr>"
        "<tr><td>Cost</td><td>500</td><td>400</td></tr></table>"
    ) == ["| Item | 2026 | 2025 |", "| --- | --- | --- |", "| Revenue | 2000 | 1900 |",
          "| Cost | 500 | 400 |"]


def test_th_row_of_currency_denominations_stays_header():
    # R0 (revision 6): an explicit header row, all th, is never a data row.
    assert _markdown(
        "<table><tr><th>Denomination</th><th>€1</th><th>€2</th></tr>"
        "<tr><td>Issued</td><td>2</td><td>1</td></tr></table>"
    ) == ["| Denomination | €1 | €2 |", "| --- | --- | --- |", "| Issued | 2 | 1 |"]


def test_header_source_tokenizes_header_cells_like_the_strict_source_pool():
    # A split negative across header cells is one token, exactly as in the table's text.
    from collections import Counter

    from sec2md.quality import _normalized_numbers

    html = ("<table><tr><th>Item</th><th>(</th><th>29</th><th>)</th></tr>"
            "<tr><td>Revenue</td><td></td><td>100</td><td></td></tr></table>")
    record, markdown = _record(html)
    assert markdown.splitlines()[0] == "| Item | ( | 29 | ) |"
    assert record.header_source == (("-29", 1),)
    assert Counter(_normalized_numbers(_table(html).get_text(" ", strip=True)))["-29"] == 1
    # Capacity stays per cell: the "29" cell heads one output column.
    assert record.header_capacity == (("29", 1),)


# --- Revision 18, C1: a table nested in a row outside every cell is read once -----------

# lxml keeps a <table> placed in a <tr>, directly or in a <div>, inside that row. Its cells
# stay cells of the outer row, and its own rows are no longer also rows of the outer table.
# Each layout: (html, the nested values, TableParser's Markdown).
C1_LAYOUTS = {
    "header-tr": (
        "<table><tr><th>Item</th><th>Period</th><table><tr><th>Fiscal</th><th>2024</th></tr></table></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table>",
        ("Fiscal", "2024"),
        ["| Item | Period | Fiscal | 2024 |", "| --- | --- | --- | --- |", "| Revenue | 100 |  |  |"],
    ),
    "body-tr": (
        "<table><tr><th>Item</th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>100</td><table><tr><td>Other</td><td>555</td></tr></table></tr>"
        "<tr><td>Costs</td><td>40</td></tr></table>",
        ("Other", "555"),
        ["| Item | 2025 |  |  |", "| --- | --- | --- | --- |", "| Revenue | 100 | Other | 555 |",
         "| Costs | 40 |  |  |"],
    ),
    "first-td-row-div": (
        "<table><tr><td>Item</td><td>Amount</td><div><table><tr><td>Note</td><td>777</td></tr></table></div></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table>",
        ("Note", "777"),
        ["|  |  |  |  |", "| --- | --- | --- | --- |", "| Item | Amount | Note | 777 |",
         "| Revenue | 100 |  |  |"],
    ),
}

# Both rendering modes. The completeness checks are asserted in normal mode only: capture
# mode writes a nested table's source text, whose check-1 findings predate C1 and are the
# same at 1252c45.
C1_MODES = pytest.mark.parametrize("capture_tables", [False, True], ids=["normal", "capture"])


def _c1_document(table_html: str) -> str:
    return f"<html><body><p>Intro.</p>{table_html}<p>End.</p></body></html>"


def _c1_parse(table_html: str, capture_tables: bool):
    """Parse a document holding the table; return the parser and its page Markdown."""
    from sec2md.parser import Parser

    parser = Parser(_c1_document(table_html), capture_tables=capture_tables)
    return parser, "\n\n".join(page.content for page in parser.get_pages())


def _cell_texts(html: str) -> list[list[str]]:
    return [[cell.text for cell in row] for row in _parser(html).cells]


@pytest.mark.parametrize("layout", sorted(C1_LAYOUTS))
def test_c1_a_table_nested_in_a_row_outside_every_cell_is_read_once(layout):
    html, values, expected = C1_LAYOUTS[layout]
    parser = _parser(html)
    markdown = parser.md()
    assert markdown.splitlines() == expected
    for value in values:
        assert markdown.count(value) == 1
    nodes = [id(cell.node) for row in parser.cells for cell in row]
    assert len(nodes) == len(set(nodes))


@C1_MODES
@pytest.mark.parametrize("layout", sorted(C1_LAYOUTS))
def test_c1_nested_layout_passes_strict_with_each_nested_value_once(layout, capture_tables):
    # main passes these documents. Reading the nested rows too wrote a second copy: a header
    # excess in a header row, an untraceable body token elsewhere. Capture mode writes the
    # table's source text, as before.
    from sec2md.quality import enforce_quality

    html, values, expected = C1_LAYOUTS[layout]
    parser, markdown = _c1_parse(html, capture_tables)
    assert parser.trace_numeric_failures == ()
    assert parser.header_accounting_misses == ()
    enforce_quality(parser.diagnostics, "strict")
    for value in values:
        assert markdown.count(value) == 1
    if not capture_tables:  # completeness in normal mode only (see C1_MODES)
        assert "\n".join(expected) in markdown
        assert parser.diagnostics.table_completeness_failures == ()


@pytest.mark.parametrize("layout", sorted(C1_LAYOUTS))
def test_c1_nested_layout_converts_under_strict(layout):
    from sec2md.core import convert_to_markdown

    html, values, expected = C1_LAYOUTS[layout]
    markdown = convert_to_markdown(_c1_document(html), quality_policy="strict")
    assert "\n".join(expected) in markdown
    for value in values:
        assert markdown.count(value) == 1


# Codex's counterexamples to reading such a table in its own rows instead: with no inner
# <tr>, or under the outer row's rowspans, 987 would be dropped. C1 keeps it, once.
C1_VALUE_CONTROLS = {
    "no-inner-tr": "<tr><td>A</td><td>1</td><table><td>987</td></table></tr>",
    "outer-rowspan": '<tr><td rowspan="2">A</td><td rowspan="2">1</td><table><tr><td>987</td></tr></table></tr>',
}


@pytest.mark.parametrize("control", sorted(C1_VALUE_CONTROLS))
def test_c1_keeps_a_nested_value_without_a_row_of_its_own(control):
    assert _markdown(f"<table>{C1_VALUE_CONTROLS[control]}</table>") == [
        "|  |  |  |", "| --- | --- | --- |", "| A | 1 | 987 |"]


@C1_MODES
@pytest.mark.parametrize("control", sorted(C1_VALUE_CONTROLS))
def test_c1_value_controls_keep_the_nested_value_once_under_strict(control, capture_tables):
    # Below a header row, so Parser renders a table. Alone, the no-inner-tr row takes Parser's
    # one-row path, which reads only a row's direct cells and loses 987 (as on main): a
    # separate follow-up, outside C1.
    from sec2md.quality import enforce_quality

    parser, markdown = _c1_parse(
        f"<table><tr><th>Item</th><th>2025</th></tr>{C1_VALUE_CONTROLS[control]}</table>", capture_tables)
    assert markdown.count("987") == 1
    assert parser.trace_numeric_failures == ()
    enforce_quality(parser.diagnostics, "strict")
    if not capture_tables:
        assert "| A | 1 | 987 |" in markdown.splitlines()


# A table nested inside a cell is read as before: pinned from the 1252c45 render, as
# (html, TableParser's Markdown, the normal-mode page, the capture-mode page).
C1_IN_CELL = {
    "header-cell": (
        "<table><tr><th>Item</th><th>Period<table><tr><th>Fiscal</th><th>2024</th></tr></table></th></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table>",
        ["| Item — Fiscal | Period Fiscal 2024 — 2024 | Fiscal | 2024 |", "| --- | --- | --- | --- |",
         "| Revenue | 100 |  |  |"],
        "Intro.\n\n| Item — Fiscal | Period Fiscal 2024 — 2024 | Fiscal | 2024 |\n| --- | --- | --- | --- |\n"
        "| Revenue | 100 |  |  |\n\nEnd.",
        "Intro.\n\nItem Period Fiscal 2024 Revenue 100\n\nEnd.",
    ),
    "body-cell": (
        "<table><tr><td>Outer<table><tr><td>Inner</td><td>77</td></tr><tr><td>B</td><td>88</td></tr></table></td>"
        "<td>12</td></tr><tr><td>Outer B</td><td>34</td></tr></table>",
        ["|  |  |  |  |  |  |", "| --- | --- | --- | --- | --- | --- |",
         "| Outer Inner 77 B 88 | Inner | 77 | B | 88 | 12 |", "| Inner | 77 |  |  |  |  |",
         "| B | 88 |  |  |  |  |", "| Outer B | 34 |  |  |  |  |"],
        "Intro.\n\n|  |  |  |  |  |  |\n| --- | --- | --- | --- | --- | --- |\n"
        "| Outer Inner 77 B 88 | Inner | 77 | B | 88 | 12 |\n| Inner | 77 |  |  |  |  |\n"
        "| B | 88 |  |  |  |  |\n| Outer B | 34 |  |  |  |  |\n\nEnd.",
        "Intro.\n\nOuter Inner 77 B 88 12 Outer B 34\n\nEnd.",
    ),
    "div-in-a-first-row-cell": (
        "<table><tr><td>Item</td><td><div><table><tr><td>Note</td><td>777</td></tr></table></div></td></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table>",
        ["|  |  |  |  |", "| --- | --- | --- | --- |", "| Item | Note 777 | Note | 777 |",
         "| Note | 777 |  |  |", "| Revenue | 100 |  |  |"],
        "Intro.\n\n|  |  |  |  |\n| --- | --- | --- | --- |\n| Item | Note 777 | Note | 777 |\n"
        "| Note | 777 |  |  |\n| Revenue | 100 |  |  |\n\nEnd.",
        "Intro.\n\nItem Note 777 Revenue 100\n\nEnd.",
    ),
}


@pytest.mark.parametrize("case", sorted(C1_IN_CELL))
def test_c1_a_table_nested_inside_a_cell_renders_as_before(case):
    html, expected, normal, capture = C1_IN_CELL[case]
    assert _markdown(html) == expected
    assert _c1_parse(html, capture_tables=False)[1] == normal
    assert _c1_parse(html, capture_tables=True)[1] == capture


def test_c1_classifies_each_nested_table_by_where_it_sits():
    # A table inside a cell keeps its rows, even within a table placed in a row; a table
    # placed in a row loses its rows, even within a table inside a cell.
    assert _cell_texts(
        "<table><tr><th>Item</th><th>2025</th></tr><tr><td>A</td><td>1</td>"
        "<table><tr><td>B<table><tr><td>X</td><td>5</td></tr></table></td></tr></table></tr></table>"
    ) == [["Item", "2025"], ["A", "1", "B X 5", "X", "5"], ["X", "5"]]
    assert _cell_texts(
        "<table><tr><th>Item</th><th>2025</th></tr><tr><td>A<table><tr><td>B</td><td>6</td>"
        "<table><tr><td>X</td><td>5</td></tr></table></tr></table></td><td>1</td></tr></table>"
    ) == [["Item", "2025"], ["A B 6 X 5", "B", "6", "X", "5", "1"], ["B", "6", "X", "5"]]


# Read once, the table below has one row. A bullet in it must not make it a list line,
# which keeps only the row's last cell and would drop "Sales grew 100".
C1_BULLET_ROW = ("<table><tr><td>•</td><td>Sales grew 100</td>"
                 "<table><tr><td>Other</td><td>50</td></tr></table></tr></table>")


@pytest.mark.parametrize("html, expected", [
    (C1_BULLET_ROW, ["|  |  |  |  |", "| --- | --- | --- | --- |", "| • | Sales grew 100 | Other | 50 |"]),
    # Every cell of the nested row is grid-hidden: the row it no longer adds (1252c45 kept it
    # empty) still keeps the table from becoming "- Costs 7", which would drop "Sales 300".
    ("<table><tr><td>•</td><td>Sales 300</td><td>Costs 7</td>"
     '<table><tr><td style="display:none">Other 50</td></tr></table></tr></table>',
     ["| • | Sales 300 | Costs 7 |", "| --- | --- | --- |"]),
], ids=["nested-row", "nested-row-of-hidden-cells"])
def test_c1_a_table_holding_a_table_in_its_row_is_never_a_list_table(html, expected):
    assert _markdown(html) == expected


def test_c1_an_entirely_grid_hidden_table_outside_every_cell_changes_nothing():
    # It adds no cell to the row, and its rows were never read: as at 1252c45.
    assert _markdown(
        '<table><tr><td>•</td><td>Sales grew 100</td><table style="display:none">'
        "<tr><td>Other</td><td>50</td></tr></table></tr></table>"
    ) == ["- Sales grew 100"]


@C1_MODES
def test_c1_a_bullet_row_holding_a_nested_table_keeps_every_value_once(capture_tables):
    from sec2md.quality import enforce_quality

    parser, markdown = _c1_parse(C1_BULLET_ROW, capture_tables)
    for value in ("Sales grew 100", "Other", "50"):
        assert markdown.count(value) == 1
    enforce_quality(parser.diagnostics, "strict")
    if not capture_tables:  # completeness in normal mode only (see C1_MODES)
        assert parser.diagnostics.table_completeness_failures == ()


def test_c1_a_grid_hidden_row_of_the_nested_table_stays_hidden():
    assert _cell_texts(
        "<table><tr><th>Item</th><th>2025</th></tr><tr><td>A</td><td>1</td><table>"
        '<tr style="display:none"><td>H</td><td>9</td></tr><tr><td>V</td><td>8</td></tr></table></tr></table>'
    ) == [["Item", "2025"], ["A", "1", "V", "8"]]


# A rowspan reaching into or out of a row that reads a nested table pushes that row, or the
# next, past the widest row's colspan sum, where the grid used to end and drop the cells
# (before C1 the nested table's own row kept a second copy). Each layout: (html, its values).
C1_ROWSPAN_REACH = {
    "rowspan-into-a-header-row": (
        '<table><tr><th rowspan="2">Item</th><th>2025</th></tr>'
        "<tr><th>Q4</th><table><tr><td>Note</td><td>777</td></tr></table></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table>",
        ("Item", "2025", "Q4", "Note", "777", "Revenue", "100"),
    ),
    "rowspan-into-a-body-row": (
        "<table><tr><th>Item</th><th>2025</th><th>2024</th></tr>"
        '<tr><td rowspan="2">Revenue</td><td>100</td><td>90</td></tr>'
        "<tr><td>110</td><table><tr><td>Adj</td><td>5</td></tr></table></tr>"
        "<tr><td>Costs</td><td>40</td><td>30</td></tr></table>",
        ("Item", "2025", "2024", "Revenue", "100", "90", "110", "Adj", "5", "Costs", "40", "30"),
    ),
    "rowspan-out-of-the-row": (
        "<table><tr><th>Item</th><th>2025</th></tr>"
        '<tr><td rowspan="2">A</td><td rowspan="2">1</td><table><tr><td>987</td></tr></table></tr>'
        "<tr><td>B</td><td>2</td></tr></table>",
        ("Item", "2025", "A", "1", "987", "B", "2"),
    ),
    # The nested row's only cell is grid-hidden: 1252c45 kept the row, empty, and A's rowspan
    # ended on it. Without that row the rowspan reaches B's row.
    "rowspan-out-of-a-row-with-hidden-nested-cells": (
        "<table><tr><th>Item</th><th>2025</th></tr>"
        '<tr><td rowspan="2">A</td><td>1</td><table><tr><td style="display:none">X 49</td></tr></table></tr>'
        "<tr><td>B</td><td>2</td></tr></table>",
        ("Item", "2025", "A", "1", "B", "2"),
    ),
}


def _token_count(text: str, value: str) -> int:
    return len(re.findall(rf"(?<![\w.,]){re.escape(value)}(?![\w.,])", text))


@pytest.mark.parametrize("layout", sorted(C1_ROWSPAN_REACH))
def test_c1_places_every_cell_when_a_rowspan_reaches_the_row(layout):
    parser = _parser(C1_ROWSPAN_REACH[layout][0])
    placed = {id(slot.cell) for row in parser.source_grid for slot in row if slot is not None}
    assert [cell.text for row in parser.cells for cell in row if id(cell) not in placed] == []


@C1_MODES
@pytest.mark.parametrize("layout", sorted(C1_ROWSPAN_REACH))
def test_c1_rowspan_reaching_the_row_keeps_every_value_once(layout, capture_tables):
    from sec2md.quality import enforce_quality

    html, values = C1_ROWSPAN_REACH[layout]
    parser, markdown = _c1_parse(html, capture_tables)
    assert {value: _token_count(markdown, value) for value in values} == dict.fromkeys(values, 1)
    assert parser.trace_numeric_failures == ()
    enforce_quality(parser.diagnostics, "strict")
    if not capture_tables:  # completeness in normal mode only (see C1_MODES)
        assert parser.diagnostics.table_completeness_failures == ()


def test_c1_a_table_between_rows_is_read_as_before():
    # Outside every row, its cells belong to no outer row: its own rows are the only read.
    assert _cell_texts(
        "<table><tr><th>Item</th><th>2025</th></tr><table><tr><td>Z</td><td>3</td></tr></table>"
        "<tr><td>C</td><td>4</td></tr></table>"
    ) == [["Item", "2025"], ["Z", "3"], ["C", "4"]]
