"""Table completeness on the offline SEC fixtures: pinned losses, mutations, unchanged rendering."""

import re
import warnings
from functools import lru_cache

import pytest

from sec2md.chunker.blocks import is_separator_row
from sec2md.encoding import decode_html
from sec2md.parser import Parser
from sec2md.table_completeness import check_tables, output_line_numbers
from sec2md.table_parser import TableParser
from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture

# Every value-class check-1 failure on the fixtures today, as {unit ordinal: missing tokens}.
# Each traces to a parser defect named in the 2026-10-02 audit; the table-merge and
# header-rules spec should empty this list. A new loss or a fixed loss both fail the test,
# so update this list deliberately.
PINNED_FAILURES = {
    "aapl-2023-10k": {
        13: ("-1",),       # repurchase-table header, lost with its plain-text "(1)"
        32: ("74427",),    # column-merge row 0
        49: ("9943",),     # column-merge row 0
        53: ("4258",),     # column-merge row 0
    },
    "nvda-2026-10k": {},
    "nvda-2002-10k": {19: ("1997", "1998", "31", "31")},  # period headers
    "nvda-2026-q2-10q": {31: ("3.5",)},                   # $3.5 guarantees row
    "nvda-2026-08-26-8k": {},
    "nvda-2026-ex99-1": {9: ("15365", "24077", "42779", "50344", "74421")},  # operating cash flow row
    "nvda-2026-ex99-2": {7: ("3.5",), 10: ("15365", "24077", "42779", "50344", "74421")},
}
TABLES_CHECKED = {
    "aapl-2023-10k": 57, "nvda-2026-10k": 62, "nvda-2002-10k": 97, "nvda-2026-q2-10q": 49,
    "nvda-2026-08-26-8k": 4, "nvda-2026-ex99-1": 10, "nvda-2026-ex99-2": 11,
}


@lru_cache(maxsize=None)
def fixture_html(fixture_id):
    return decode_html(load_fixture(fixture_id)[1])[0]


def parse(fixture_id, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = Parser(fixture_html(fixture_id), **kwargs)
        pages = parser.get_pages(include_images=False)
    return parser, pages


def test_pinned_list_covers_every_fixture():
    assert set(PINNED_FAILURES) == set(FIXTURE_IDS) == set(TABLES_CHECKED)


@pytest.mark.parametrize("capture", [False, True], ids=["normal", "capture"])
@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_fixture_reports_exactly_the_pinned_failures(fixture_id, capture):
    report = parse(fixture_id, capture_tables=capture)[0].table_report
    actual = {f.ordinal: tuple(sorted(token for token, _, _ in f.missing_values))
              for f in report.findings if f.missing_values}
    assert actual == PINNED_FAILURES[fixture_id]
    assert report.tables_checked == TABLES_CHECKED[fixture_id]
    assert report.structure == ()
    assert not any(ambiguous for f in report.findings for _, _, ambiguous in f.missing_values)


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_rendering_is_identical_with_and_without_checks(fixture_id):
    _, checked = parse(fixture_id)
    _, unchecked = parse(fixture_id, table_checks=False)
    assert [page.content for page in checked] == [page.content for page in unchecked]


def test_capture_snapshots_are_identical_with_and_without_checks():
    with_checks = parse("aapl-2023-10k", capture_tables=True)[0].table_snapshots
    without = parse("aapl-2023-10k", capture_tables=True, table_checks=False)[0].table_snapshots
    assert with_checks == without


def reverse_numeric_cells(segment):
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        for i, value in zip(idx, [cells[i] for i in idx][::-1]):
            cells[i] = value
        out.append("|".join(cells))
    return "\n".join(out)


def swap_first_body_rows(segment):
    """Swap the first two distinct body lines that each carry two or more tokens."""
    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    if separator is None:
        return segment
    rows = [i for i in range(separator + 1, len(lines)) if len(output_line_numbers(lines[i])) >= 2]
    pair = next(((a, b) for a, b in zip(rows, rows[1:]) if lines[a] != lines[b]), None)
    if pair:
        a, b = pair
        lines[a], lines[b] = lines[b], lines[a]
    return "\n".join(lines)


def test_blank_table_renderer_is_detected(monkeypatch):
    monkeypatch.setattr(TableParser, "md", lambda self, *args, **kwargs: "")
    report = parse("aapl-2023-10k")[0].table_report
    value_flagged = [f for f in report.findings if f.missing_values]
    reference_only = [f for f in report.findings if not f.missing_values and f.missing_reported]
    # The 7 units without value failures: 6 reference-only units (3 exhibit indexes,
    # 3 signature blocks) whose losses are reported, and one one-row table rendered as text.
    assert (report.tables_checked, len(value_flagged), len(reference_only)) == (57, 50, 6)


@pytest.mark.parametrize("mutate, message, expected", [
    (reverse_numeric_cells, "values out of order within the row", 50),
    (swap_first_body_rows, "appears before an earlier source row", 48),
])
def test_row_structure_mutations_are_detected(mutate, message, expected):
    parser, _ = parse("aapl-2023-10k")
    outputs = {key: mutate(value) for key, value in parser.table_outputs.items()}
    report = check_tables(parser.soup, outputs, parser._table_pages, parser._snapshot_ordinals)
    assert sum(1 for f in report.findings if any(message in s for s in f.structure)) == expected
