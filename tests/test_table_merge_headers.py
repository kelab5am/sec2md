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
