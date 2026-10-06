"""Table completeness on the offline SEC fixtures: pinned losses, mutations, unchanged rendering."""

import re
import warnings
from functools import lru_cache

import pytest

from sec2md.chunker.blocks import is_separator_row
from sec2md.encoding import decode_html
from sec2md.parser import Parser
from sec2md.table_alignment import COVERAGE_KEYS
from sec2md.table_completeness import check_tables, hidden_sets, output_line_numbers
from sec2md.table_parser import TableParser
from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture

# Every value-class check-1 failure on the fixtures, as {unit ordinal: missing tokens}. The
# 10 losses pinned before the table-merge and header-rules spec (2026-10-05) were all class 1
# (the legacy merge dropped row-0 text); R1 keeps them, so none is left. A new loss fails the
# test, so update this list deliberately.
PINNED_FAILURES = {
    "aapl-2023-10k": {},
    "nvda-2026-10k": {},
    "nvda-2002-10k": {},
    "nvda-2026-q2-10q": {},
    "nvda-2026-08-26-8k": {},
    "nvda-2026-ex99-1": {},
    "nvda-2026-ex99-2": {},
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


# Header-alignment coverage per fixture (spec 2026-10-05), in COVERAGE_KEYS order and the
# same in both rendering modes. The renderer leaves no evaluated value misaligned.
# Revision 11's header zone: aapl gains two evaluated tables (years rows that read as data
# before). Revision 12: label-only rows continue the zone, so ex99-1 units 5, 6, 11 and
# ex99-2 unit 12, which stack two title rows, have their header zones again and are
# evaluated (all their values aligned).
ALIGNMENT_COVERAGE = {
    "aapl-2023-10k": (66, 8, 1, 0, 5, 5, 47, 423, 15, 159, 249, 758, 51, 30, 0, 30, 0, 0, 647, 647, 0),
    "nvda-2026-10k": (64, 0, 3, 0, 2, 3, 56, 465, 12, 106, 347, 894, 45, 72, 0, 49, 0, 0, 728, 728, 0),
    "nvda-2002-10k": (172, 0, 125, 0, 1, 4, 42, 459, 43, 80, 336, 1076, 148, 27, 0, 120, 0, 0, 781, 781, 0),
    "nvda-2026-q2-10q": (52, 1, 3, 0, 2, 2, 44, 354, 9, 87, 258, 865, 64, 32, 0, 59, 0, 0, 710, 710, 0),
    "nvda-2026-08-26-8k": (5, 0, 1, 0, 1, 2, 1, 3, 1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "nvda-2026-ex99-1": (11, 0, 0, 0, 2, 1, 8, 109, 0, 10, 99, 363, 5, 5, 0, 13, 0, 0, 340, 340, 0),
    "nvda-2026-ex99-2": (12, 0, 0, 0, 2, 1, 9, 65, 0, 4, 61, 296, 16, 5, 0, 19, 0, 0, 256, 256, 0),
}


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_header_alignment_reports_nothing_on_the_fixtures(fixture_id):
    parser = parse(fixture_id)[0]
    normal = parser.diagnostics
    capture = parse(fixture_id, capture_tables=True)[0].diagnostics
    assert normal.table_header_alignment == capture.table_header_alignment == ()
    expected = tuple(zip(COVERAGE_KEYS, ALIGNMENT_COVERAGE[fixture_id]))
    assert normal.table_header_alignment_coverage == capture.table_header_alignment_coverage == expected
    # Units are numbered as check 1 numbers them: every visible outermost table.
    outermost, hidden, _ = hidden_sets(parser.soup)
    assert dict(expected)["tables_total"] == sum(id(table) not in hidden for table in outermost)


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
