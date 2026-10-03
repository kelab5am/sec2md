"""Unit tests for the table completeness checks (spec 2026-10-02, revision 6)."""

from collections import Counter

import pytest
from bs4 import BeautifulSoup

from sec2md.table_completeness import (
    cell_text,
    hidden_sets,
    merge_split_negatives,
    numbers,
    output_line_numbers,
)


def soup_of(html):
    return BeautifulSoup(html, "lxml")


# --- task 2: text and tokens -----------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("€123", ("123",)),
    ("£456", ("456",)),
    ("$ (16,173)", ("-16173",)),
    ("3.5%-4.3%", ("3.5", "4.3")),
    ("2024 – 2026", ("2024", "2026")),
    ("Revenue", ()),
])
def test_numbers_normalizes_currency_and_range_dashes(text, expected):
    assert numbers(text) == expected


@pytest.mark.parametrize("cells, expected", [
    (["Loss", "(29", ")"], ["Loss", "(29)"]),
    (["Loss", "(", "29", ")"], ["Loss", "(29)"]),
    (["Margin", "(3.2", ")%"], ["Margin", "(3.2)%"]),
    (["Revenue", "", "120", " "], ["Revenue", "120"]),
])
def test_merge_split_negatives(cells, expected):
    assert merge_split_negatives(cells) == expected


def test_output_line_numbers_tokenizes_each_cell_separately():
    assert output_line_numbers("| Loss | (29 | ) | 1,2 | 34 |") == ["-29", "12", "34"]


def test_hidden_sets_scopes_to_outermost_tables():
    soup = soup_of(
        '<div style="display:none"><table id="a"><tr><td>1</td></tr></table></div>'
        '<table id="b"><tr><td>2<span style="display:none">999</span>'
        '<table id="c"><tr><td>3</td></tr></table></td></tr></table>'
    )
    outermost, hidden, _ = hidden_sets(soup)
    assert [t["id"] for t in outermost] == ["a", "b"]
    assert id(soup.find(id="a")) in hidden
    assert id(soup.find(id="b")) not in hidden
    assert id(soup.find("span")) in hidden


@pytest.mark.parametrize("cell, expected", [
    ("<td>1,2<span>34</span></td>", ("1,234", "")),
    ("<td>Revenue<sup>(1)</sup></td>", ("Revenue", "(1)")),
    ('<td>Revenue<span style="vertical-align:super">2</span></td>', ("Revenue", "2")),
    ('<td>Revenue<a href="#f1">(1)</a></td>', ("Revenue", "(1)")),
    # NVDA kerns single digits with relative positioning and splits dates across
    # fragment links; neither is a footnote marker.
    ('<td><span style="position:relative;top:1px">1</span>23</td>', ("123", "")),
    ('<td>January <a href="#x">2</a>9, 2025</td>', ("January 29, 2025", "")),
    ("<td>Revenue<br/>Net</td>", ("Revenue Net", "")),
])
def test_cell_text_separates_footnote_markers(cell, expected):
    soup = soup_of(f"<table><tr>{cell}</tr></table>")
    _, hidden, _ = hidden_sets(soup)
    assert cell_text(soup.find("td"), hidden) == expected


def test_cell_text_skips_hidden_descendants():
    soup = soup_of('<table><tr><td>100<span style="display:none">999</span></td></tr></table>')
    _, hidden, _ = hidden_sets(soup)
    assert cell_text(soup.find("td"), hidden) == ("100", "")
