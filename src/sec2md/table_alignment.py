"""Header-alignment check: each value sits under the header its source column carries.

Implements the "Header-alignment check" of
docs/superpowers/specs/2026-10-05-sec2md-table-merge-header-rules-design.md (revision 17).
Like check 1, it compares a table's source HTML with the exact Markdown emitted for it.
It shares only R0 (table_roles) and the cell-text extraction with the renderer, and never
reads the renderer's merge decisions or output-column mapping, so it measures any
renderer's Markdown, today's main included.

The source side places the grid, applies R0 and derives values, repeated headers,
emitted paths and discriminating cells. The output side parses Markdown cells by position,
pairs rows and locates values. Matching judges each located value's output header against
its emitted path with a bounded search; findings and coverage counts are per table unit.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Literal, Mapping, Sequence

from bs4 import Tag

from sec2md.chunker.blocks import is_separator_row
from sec2md.table_completeness import (
    _PERIOD_TEXT,
    _GridCell,
    _Row,
    line_label_key,
    numbers,
    place_unit,
)
from sec2md.table_parser import extract_cell_text, has_descendant
from sec2md.table_roles import (
    _FOOTNOTED,
    OriginCell,
    OriginSlot,
    RowRoles,
    is_complete_number,
    is_nil_value,
    is_year_like,
    row_roles,
    row_values,
    visible_text,
)

# A leading-dot decimal (".75", "(.62)"), tokenized locally as "0.75"; strict's
# normalizer reads ".75" as no number and does not change.
_LEADING_DOT = re.compile(r"(?<![\w.])\.(?=\d)")
# R6's join between header rows; a header splits only at these separators.
SEPARATOR = " — "
# A Markdown link's destination in extracted cell text: after "](" up to the next ")".
_LINK_DESTINATION = re.compile(r"\]\(([^)]*)\)")


def label_text_key(text: str) -> str:
    """Normalized header or label text (spec step 10): visible text with links reduced to
    their labels, whitespace collapsed and case folded."""

    return " ".join(visible_text(text).split()).casefold()


def local_numbers(text: str) -> tuple[str, ...]:
    """Numeric tokens of one value or output cell, accepting leading-dot decimals."""

    return numbers(_LEADING_DOT.sub("0.", text))


def value_tokens(text: str) -> tuple[str, ...]:
    """The tokens of one complete number: its numeric core, without footnote markers.

    "2.1(1)" -> ("2.1",), "$ (1,234)" -> ("-1234",), ".75" -> ("0.75",), and a range
    "3.5 %- 4.3 %" -> ("3.5", "4.3"). A nil value has none.
    """

    if is_nil_value(text):
        return ()
    footnoted = _FOOTNOTED.fullmatch(text)
    return local_numbers(footnoted.group("number") if footnoted else text)


# --- source side -------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class SourceCell:
    """One placed source cell, in the placed grid's original coordinates.

    Cells compare by identity: the slots a spanning cell covers all hold the same object.
    """

    row: int
    column: int
    rowspan: int
    colspan: int
    text: str            # visible text: extracted text, links reduced, zero-width removed
    header: bool = False  # a th element
    links: tuple[str, ...] = ()  # link destinations of the extracted text, in order

    @cached_property
    def key(self) -> str:
        return label_text_key(self.text)

    def columns(self) -> range:
        return range(self.column, self.column + self.colspan)

    def rows(self) -> range:
        return range(self.row, self.row + self.rowspan)


@dataclass(frozen=True)
class SourceGrid:
    """A unit's placed grid: slots[r][k] is the cell covering slot (r, k), or None.

    Rows are the unit's own visible rows in document order, empty rows and columns
    included, so every coordinate is the original one. row_trs holds each row's tr.
    """

    slots: tuple[tuple[SourceCell | None, ...], ...]
    row_trs: tuple[Tag | None, ...] = ()

    @property
    def height(self) -> int:
        return len(self.slots)

    @property
    def width(self) -> int:
        return len(self.slots[0]) if self.slots else 0

    def origin_grid(self) -> list[list[OriginSlot]]:
        """R0's neutral grid: each cell at its top-left slot, None where a span covers."""

        return [
            [
                OriginCell(cell.text, cell.header) if cell is not None and (cell.row, cell.column) == (r, k) else None
                for k, cell in enumerate(row)
            ]
            for r, row in enumerate(self.slots)
        ]


def source_cell_text(td: Tag) -> str:
    """A source cell's visible text: the renderer's extracted text, links reduced to their
    labels, zero-width characters removed, and in a cell with a link (whose label text the
    renderer escapes) pipes unescaped."""

    return source_cell_text_and_links(td)[0]


def source_cell_text_and_links(td: Tag, extracted: str | None = None, *,
                               base_url: str | None = None) -> tuple[str, tuple[str, ...]]:
    """A source cell's visible text (source_cell_text) and the destinations of the links in
    its extracted text, in order.

    extracted, when given, is the cell's ``extract_cell_text`` result already computed.
    base_url resolves link destinations as the render did (spec revision 12: the renderer
    and the checker compare the same extracted text, links resolved against the same base
    URL); the Parser passes its source URL, the base URL of its TableParser renders.
    """

    raw = extract_cell_text(td, base_url=base_url) if extracted is None else extracted
    text = visible_text(raw)
    if "\\|" in text and has_descendant(td, "a"):
        text = text.replace("\\|", "|")
    return text, (tuple(_LINK_DESTINATION.findall(raw)) if "](" in raw else ())


def place_source_grid(table: Tag, rows: list[_Row], grid_hidden: set[int], *,
                      base_url: str | None = None) -> SourceGrid | None:
    """Place a unit's own visible rows as the snapshot builder does (spec step 1).

    None when placement is unreliable (a bad span, an overlap, a nested table or an
    oversized grid): the unit is skipped as table_unreliable_grid.
    """

    return source_grid(place_unit(table, rows, grid_hidden), base_url=base_url)


def source_grid(placed: tuple[list[_Row], list[list[_GridCell | None]]] | None,
                cell_texts: Mapping[int, str] | None = None, *,
                base_url: str | None = None) -> SourceGrid | None:
    """The SourceGrid of a placement from table_completeness.place_unit (None stays None).

    cell_texts maps id(td) to that cell's ``extract_cell_text(td)`` result when a caller has
    it already (the Parser records the link-free extractions of the Markdown render); any
    other cell is extracted here, its links resolved against base_url as the render's were.
    """

    if placed is None:
        return None
    placed_rows, grid = placed
    cells: dict[int, SourceCell] = {}
    slots = []
    for row in grid:
        out = []
        for slot in row:
            if slot is None:
                out.append(None)
                continue
            cell = cells.get(id(slot))
            if cell is None:
                extracted = cell_texts.get(id(slot.td)) if cell_texts else None
                text, links = source_cell_text_and_links(slot.td, extracted, base_url=base_url)
                cell = SourceCell(slot.row, slot.column, slot.rowspan, slot.colspan, text, slot.is_header, links)
                cells[id(slot)] = cell
            out.append(cell)
        slots.append(tuple(out))
    return SourceGrid(tuple(slots), tuple(row.tr for row in placed_rows[:len(grid)]))


@dataclass(frozen=True)
class SourceValue:
    """One value of a data row: a complete number or a nil value outside the label column.

    column is the column of its numeric core (the cell holding the digits of a rebuilt
    split negative). tokens are the local numeric tokens of its core; a nil value has none.
    """

    row: int
    column: int
    text: str
    tokens: tuple[str, ...]

    @property
    def nil(self) -> bool:
        return is_nil_value(self.text)


@dataclass(frozen=True)
class PathEntry:
    """One entry of a value's emitted path: adjacent equal header texts collapsed.

    cells and levels are every source cell and header row the entry represents.
    """

    key: str
    text: str
    cells: tuple[SourceCell, ...]
    levels: tuple[int, ...]


@dataclass(frozen=True)
class Expectation:
    """What the header over one value column must carry (spec steps 6 and 13).

    path is the emitted path; required holds the keys of entries representing a
    discriminating cell, in path order; need counts emitted entries per key; conflicts
    holds the keys of the required entries' conflicting siblings, with a display text each.
    """

    column: int
    path: tuple[PathEntry, ...]
    required: tuple[str, ...]
    need: Mapping[str, int]
    conflicts: Mapping[str, str]

    def rendering(self) -> str:
        """The header R6 writes for this path: entries joined with " — "."""

        return SEPARATOR.join(entry.text for entry in self.path)

    def expected_text(self) -> str:
        """The required entries, as a finding names them."""

        return SEPARATOR.join(entry.text for entry in self.path if entry.key in self.required)


class SourceAnalysis:
    """The checker's own reading of one placed grid (spec steps 2 to 6)."""

    def __init__(self, grid: SourceGrid):
        self.grid = grid
        self.origin = grid.origin_grid()
        self.roles: RowRoles = row_roles(self.origin)
        label = self.roles.label_column
        # Data row -> its values, split negatives rebuilt (step 5).
        self.values: dict[int, tuple[SourceValue, ...]] = {
            row: tuple(
                SourceValue(row, column, text, value_tokens(text))
                for column, text in row_values(self.origin[row])
                if column != label and (is_complete_number(text) or is_nil_value(text))
            )
            for row in self.roles.data_rows
        }
        # Step 3: columns holding a complete number in a data row.
        self.value_columns = frozenset(
            value.column for values in self.values.values() for value in values if not value.nil
        )
        self._header_rows = set(self.roles.header_rows)
        self.header_cells: tuple[SourceCell, ...] = tuple(dict.fromkeys(
            cell
            for row in self.roles.header_rows
            for cell in grid.slots[row]
            if cell is not None and cell.key
        ))
        self._covered: dict[int, frozenset[int]] = {}
        self._discriminating: dict[int, bool] = {}
        self._expectations: dict[int, Expectation] = {}

    def covered_value_columns(self, cell: SourceCell) -> frozenset[int]:
        covered = self._covered.get(id(cell))
        if covered is None:
            covered = frozenset(column for column in cell.columns() if column in self.value_columns)
            self._covered[id(cell)] = covered
        return covered

    def is_discriminating(self, cell: SourceCell) -> bool:
        """A header cell covering a non-empty proper subset of the value columns (step 3)
        whose text its siblings do not all share (step 15).

        Siblings are the other cells of the cell's header rows that cover a value column.
        When every sibling has the cell's text ("RMB" over every period), the text tells no
        value column from another, so the cell imposes no requirement.
        """

        found = self._discriminating.get(id(cell))
        if found is not None:
            return found
        covered = self.covered_value_columns(cell)
        if not covered or covered == self.value_columns:
            found = False
        else:
            siblings = {
                id(other): other
                for row in cell.rows() if row in self._header_rows
                for other in self.grid.slots[row]
                if other is not None and other is not cell and self.covered_value_columns(other)
            }
            found = not siblings or any(other.key != cell.key for other in siblings.values())
        self._discriminating[id(cell)] = found
        return found

    @cached_property
    def repeated_header(self) -> int | None:
        """The first repeated header row (step 4), or None.

        A body row after the first data row with no complete number outside the label
        column, and holding period text or a year-like value. Values below it are not
        evaluated.
        """

        if not self.roles.data_rows:
            return None
        first = self.roles.data_rows[0]
        label = self.roles.label_column
        for row in range(first + 1, self.grid.height):
            if row in self._header_rows:
                continue
            texts = row_values(self.origin[row])
            if not texts or any(column != label and is_complete_number(text) for column, text in texts):
                continue
            if any(_PERIOD_TEXT.search(text) or is_year_like(text) for _, text in texts):
                return row
        return None

    def source_path(self, column: int) -> list[tuple[SourceCell, int]]:
        """Header-zone cells covering a column, top to bottom, each once (step 6)."""

        path: list[tuple[SourceCell, int]] = []
        seen: set[int] = set()
        for row in self.roles.header_rows:
            cell = self.grid.slots[row][column] if column < self.grid.width else None
            if cell is None or not cell.key or id(cell) in seen:
                continue
            seen.add(id(cell))
            path.append((cell, row))
        return path

    def emitted_path(self, column: int) -> tuple[PathEntry, ...]:
        """The source path with adjacent equal texts collapsed, exactly as R6 writes it.

        Equal means equal normalized text and equal link destinations (R6 step 2), so two
        cells with one label and different links stay two entries.
        """

        entries: list[PathEntry] = []
        for cell, row in self.source_path(column):
            if entries and entries[-1].key == cell.key and entries[-1].cells[0].links == cell.links:
                last = entries[-1]
                entries[-1] = PathEntry(last.key, last.text, last.cells + (cell,), last.levels + (row,))
            else:
                entries.append(PathEntry(cell.key, " ".join(cell.text.split()), (cell,), (row,)))
        return tuple(entries)

    def expectation(self, column: int) -> Expectation:
        """Required entries, needs and conflicting siblings for one value column."""

        if column in self._expectations:
            return self._expectations[column]
        path = self.emitted_path(column)
        required = tuple(dict.fromkeys(
            entry.key for entry in path if any(self.is_discriminating(cell) for cell in entry.cells)
        ))
        need = Counter(entry.key for entry in path)
        conflicts: dict[str, str] = {}
        for entry in path:
            if entry.key not in required:
                continue
            for cell in entry.cells:
                for row in cell.rows():
                    if row not in self._header_rows:
                        continue
                    for sibling in dict.fromkeys(self.grid.slots[row]):
                        if (sibling is None or sibling is cell or not sibling.key or sibling.key == entry.key
                                or not self.is_discriminating(sibling)):
                            continue
                        conflicts.setdefault(sibling.key, " ".join(sibling.text.split()))
        expectation = Expectation(column, path, required, dict(need), dict(sorted(conflicts.items())))
        self._expectations[column] = expectation
        return expectation


# --- output side -------------------------------------------------------------------------

def split_cells(line: str) -> list[str]:
    """Raw Markdown cells of one table line, by position (spec step 7).

    One leading and one trailing pipe are removed, then the line splits on unescaped "|"
    outside link destinations. Blank cells are kept, so header and body cells align by
    index.
    """

    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    if "\\" not in text and "](" not in text:
        return text.split("|")  # no escape and no link destination: every pipe splits
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and text.startswith("|", index + 1):
            current.append("\\|")
            index += 2
            continue
        if text.startswith("](", index):
            close = text.find(")", index + 2)
            if close != -1:
                current.append(text[index:close + 1])
                index = close + 1
                continue
        if char == "|":
            cells.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current))
    return cells


def cell_visible_text(raw: str) -> str:
    """An output cell's visible text: link labels only, escaped pipes unescaped."""

    return " ".join(visible_text(raw).replace("\\|", "|").split())


def cell_tokens(texts: Sequence[str]) -> list[Counter]:
    """Local numeric tokens per cell index, with split negatives rebuilt across adjacent
    non-empty cells and assigned to the cell holding the digits."""

    tokens = [Counter() for _ in texts]
    for index, text in row_values(list(texts)):
        tokens[index].update(local_numbers(text))
    return tokens


@dataclass(frozen=True)
class OutputTable:
    """One table's Markdown: visible header cells, raw body lines, each body line's visible
    cells and its check 1 label key."""

    header: tuple[str, ...]
    body: tuple[str, ...]
    cells: tuple[tuple[str, ...], ...]
    keys: tuple[str, ...]

    def header_text(self, index: int) -> str:
        return self.header[index] if index < len(self.header) else ""


def parse_output(segment: str) -> OutputTable | None:
    """Parse a table's emitted Markdown; None when it has no separator row."""

    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    if separator is None:
        return None
    header = tuple(cell_visible_text(cell) for cell in split_cells(lines[separator - 1])) if separator else ()
    body = tuple(lines[separator + 1:])
    cells = tuple(tuple(cell_visible_text(cell) for cell in split_cells(line)) for line in body)
    # Check 1's label key of each line's first non-empty cell (split negatives rebuilt),
    # read through the position-preserving parser, so an escaped pipe stays in its label.
    keys = tuple(line_label_key([text for _, text in row_values(list(texts))]) for texts in cells)
    return OutputTable(header, body, cells, keys)


def pair_rows(source_keys: Mapping[int, str], key_counts: Mapping[str, int], output: OutputTable) -> dict[int, int]:
    """Check 1's pairing (spec step 8): data row -> output body line.

    A row pairs only when its label key is non-empty and unique among the unit's source
    rows (key_counts) and among the output body lines.
    """

    output_counts = Counter(key for key in output.keys if key)
    line_of = {key: index for index, key in enumerate(output.keys) if key and output_counts[key] == 1}
    return {
        row: line_of[key]
        for row, key in source_keys.items()
        if key and key_counts.get(key, 0) == 1 and key in line_of
    }


def locate(tokens: Sequence[str], cells: Sequence[Counter]) -> list[int]:
    """Indices of the output cells holding every token of a value (spec step 9)."""

    need = Counter(tokens)
    if not need:
        return []
    return [index for index, found in enumerate(cells) if not need - found]


def line_cells(line: str) -> tuple[list[str], list[Counter]]:
    """(visible texts, tokens) of one output line's cells, by index."""

    texts = [cell_visible_text(cell) for cell in split_cells(line)]
    return texts, cell_tokens(texts)


# --- matching (spec steps 10 to 15) ----------------------------------------------------

# The work bound of one value's segmentation search (states created, the start included).
MAX_STATES = 100_000
_CONSISTENT, _INCONSISTENT = 1, 2
_BOTH = _CONSISTENT | _INCONSISTENT

Outcome = Literal["aligned", "misaligned", "ambiguous", "budget"]


@dataclass(frozen=True)
class Verdict:
    """How one output header judges one value's expectation.

    states counts the search states created (0 for the exact path rendering). For a
    misaligned value, conflicting holds the display texts of the conflicting siblings found
    in excess in some segmentation that meets every requirement.
    """

    outcome: Outcome
    states: int = 0
    conflicting: tuple[str, ...] = ()


def header_atoms(header: str) -> list[str]:
    """A header's visible text, whitespace collapsed, split at every " — " separator."""

    return " ".join(visible_text(header).split()).split(SEPARATOR)


def judge(header: str, expectation: Expectation, *, max_states: int = MAX_STATES) -> Verdict:
    """Judge an output header against a value's emitted path (spec steps 11 to 14).

    A header that renders the emitted path exactly is aligned. Otherwise a memoized search
    over separator positions decides whether every segmentation is consistent with the
    path (aligned), none is (misaligned) or they disagree (ambiguous). Its state is a
    position plus the counts of the required and conflicting-sibling texts, each capped at
    need + 1. Every state it visits is reachable from the start, so it stops as soon as it
    has seen both a consistent and an inconsistent completion, in any frame (spec revision
    14). A search that would create more than max_states states is abandoned ("budget"),
    never aligned.
    """

    if label_text_key(header) == label_text_key(expectation.rendering()):
        return Verdict("aligned")
    atoms = [atom.casefold() for atom in header_atoms(header)]
    relevant = sorted(set(expectation.required) | set(expectation.conflicts))
    index = {key: position for position, key in enumerate(relevant)}
    need = [expectation.need.get(key, 0) for key in relevant]
    required = [index[key] for key in expectation.required]
    conflicts = [index[key] for key in expectation.conflicts]
    longest = max((len(key) for key in relevant), default=-1)
    size = len(atoms)
    labels: dict[tuple[int, int], int] = {}

    def label_at(start: int, end: int) -> int:
        """The relevant label a segment of atoms[start..end] equals, or -1."""
        found = labels.get((start, end))
        if found is None:
            length = sum(len(atom) for atom in atoms[start:end + 1]) + len(SEPARATOR) * (end - start)
            found = index.get(SEPARATOR.join(atoms[start:end + 1]), -1) if length <= longest else -1
            labels[(start, end)] = found
        return found

    def consistent(counts: tuple[int, ...]) -> bool:
        return (all(counts[r] >= need[r] for r in required)
                and all(counts[c] <= need[c] for c in conflicts))

    start = (0, (0,) * len(relevant))
    memo: dict[tuple[int, tuple[int, ...]], int] = {}
    terminals: set[tuple[int, ...]] = set()
    created = 1
    # Verdicts seen anywhere: each is reachable from the start (the global early stop).
    seen = 0
    # Each frame: [state, next segment end, verdicts reachable so far].
    stack: list[list] = [[start, 0, 0]]
    while stack:
        frame = stack[-1]
        (position, counts), end, reachable = frame
        if end >= size:
            memo[frame[0]] = reachable
            stack.pop()
            if stack:
                stack[-1][2] |= reachable
            continue
        frame[1] = end + 1
        label = label_at(position, end)
        if label >= 0 and counts[label] <= need[label]:
            counts = counts[:label] + (counts[label] + 1,) + counts[label + 1:]
        child = (end + 1, counts)
        if child in memo:
            frame[2] |= memo[child]
            seen |= memo[child]
        else:
            created += 1
            if created > max_states:
                return Verdict("budget", created - 1)
            if end + 1 != size:
                stack.append([child, end + 1, 0])
                continue
            memo[child] = _CONSISTENT if consistent(counts) else _INCONSISTENT
            terminals.add(counts)
            frame[2] |= memo[child]
            seen |= memo[child]
        if seen == _BOTH:
            return Verdict("ambiguous", created)
    # The search finished without seeing both verdicts (every frame's verdicts are among
    # those seen), so the start reaches exactly one.
    if memo[start] == _CONSISTENT:
        return Verdict("aligned", created)
    excess = {
        relevant[c]
        for counts in terminals
        if all(counts[r] >= need[r] for r in required)
        for c in conflicts
        if counts[c] > need[c]
    }
    return Verdict("misaligned", created, tuple(expectation.conflicts[key] for key in sorted(excess)))


# --- findings and coverage -------------------------------------------------------------

# Every key, in order; a completed run emits each one (spec "Findings and coverage").
COVERAGE_KEYS = (
    "tables_total",
    "table_no_output",
    "table_no_separator",
    "table_unreliable_grid",
    "table_no_header",
    "table_no_data",
    "tables_evaluated",
    "rows_data",
    "row_below_repeated_header",
    "row_unpaired",
    "rows_paired",
    "values_total",
    "value_nil",
    "value_no_discriminating_header",
    "value_missing_in_output",
    "value_ambiguous_position",
    "value_ambiguous_header",
    "value_unevaluated_budget",
    "values_evaluated",
    "values_aligned",
    "values_misaligned",
)
# Findings listed per table; the total follows when there are more.
MAX_LISTED = 10


def coverage_items(coverage: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    """Every coverage key in order, with zeros where nothing applies."""

    return tuple((key, coverage.get(key, 0)) for key in COVERAGE_KEYS)


@dataclass(frozen=True)
class Misalignment:
    """One misaligned value: its source row and column, and what the output put over it."""

    row: int
    column: int
    label: str
    tokens: tuple[str, ...]
    header: str
    expected: str
    conflicting: tuple[str, ...] = ()

    def message(self, where: str) -> str:
        text = f'{where}: "{self.label}" {" ".join(self.tokens)} under "{self.header}"; expected "{self.expected}"'
        if self.conflicting:
            text += ", conflicting " + ", ".join(f'"{sibling}"' for sibling in self.conflicting)
        return text


@dataclass(frozen=True)
class ValueOutcome:
    """One source value's outcome: "aligned", "misaligned", or its row or value skip key.

    row and column are the value's identity in the placed grid's original coordinates
    (column is its numeric core's column). line is the paired output body line (None for
    a row skip); output_column is the one output cell holding the value, when located.
    """

    row: int
    column: int
    outcome: str
    line: int | None = None
    output_column: int | None = None


@dataclass(frozen=True)
class TableAlignment:
    """One table unit's coverage counts and misaligned values.

    outcomes lists every value of every data row of an evaluated table, in source order,
    for acceptance's per-value identity comparison; a skipped table has none.
    """

    coverage: Counter
    misalignments: tuple[Misalignment, ...] = ()
    outcomes: tuple[ValueOutcome, ...] = ()

    def messages(self, where: str) -> tuple[str, ...]:
        """At most MAX_LISTED findings, then the total when more were found."""

        listed = [finding.message(where) for finding in self.misalignments[:MAX_LISTED]]
        if len(self.misalignments) > MAX_LISTED:
            listed.append(f"{where}: {len(self.misalignments)} misaligned values in total, {MAX_LISTED} listed")
        return tuple(listed)


def align_table(table: Tag, rows: list[_Row], grid_hidden: set[int], segment: str,
                row_keys: Mapping[int, str], key_counts: Mapping[str, int], *,
                placement: Callable[[], tuple[list[_Row], list[list[_GridCell | None]]] | None] | None = None,
                max_states: int = MAX_STATES, cell_texts: Mapping[int, str] | None = None,
                base_url: str | None = None) -> TableAlignment:
    """Run the header-alignment check on one table unit and its emitted Markdown.

    rows are the unit's rows (table_completeness.unit_rows); segment is the raw Markdown
    emitted for the unit; row_keys maps each source row's tr to check 1's label key and
    key_counts counts those keys over the unit. placement, when given, returns the unit's
    place_unit result (check_tables shares one placement with check 1); cell_texts, when
    given, holds cells' extract_cell_text results by id(td) (source_grid); base_url resolves
    the other cells' links as the render that wrote segment resolved them. Each table, row and
    value takes the first applicable skip key in COVERAGE_KEYS order.
    """

    coverage: Counter = Counter(tables_total=1)
    if not segment.strip():
        coverage["table_no_output"] += 1
        return TableAlignment(coverage)
    output = parse_output(segment)
    if output is None:
        coverage["table_no_separator"] += 1
        return TableAlignment(coverage)
    grid = source_grid(placement() if placement is not None else place_unit(table, rows, grid_hidden), cell_texts,
                       base_url=base_url)
    if grid is None:
        coverage["table_unreliable_grid"] += 1
        return TableAlignment(coverage)
    source = SourceAnalysis(grid)
    if not source.roles.header_rows:
        coverage["table_no_header"] += 1
        return TableAlignment(coverage)
    if not source.roles.data_rows:
        coverage["table_no_data"] += 1
        return TableAlignment(coverage)
    coverage["tables_evaluated"] += 1

    source_keys = {row: row_keys.get(id(grid.row_trs[row]), "") for row in source.roles.data_rows}
    pairs = pair_rows(source_keys, key_counts, output)
    repeated = source.repeated_header
    verdicts: dict[tuple[int, int], Verdict] = {}
    misalignments: list[Misalignment] = []
    outcomes: list[ValueOutcome] = []
    for row in source.roles.data_rows:
        coverage["rows_data"] += 1
        if repeated is not None and row > repeated:
            coverage["row_below_repeated_header"] += 1
            outcomes.extend(ValueOutcome(row, value.column, "row_below_repeated_header")
                            for value in source.values[row])
            continue
        line = pairs.get(row)
        if line is None:
            coverage["row_unpaired"] += 1
            outcomes.extend(ValueOutcome(row, value.column, "row_unpaired") for value in source.values[row])
            continue
        coverage["rows_paired"] += 1
        tokens = cell_tokens(output.cells[line])
        for value in source.values[row]:
            coverage["values_total"] += 1
            if value.nil:
                coverage["value_nil"] += 1
                outcomes.append(ValueOutcome(row, value.column, "value_nil", line))
                continue
            expectation = source.expectation(value.column)
            if not expectation.required:
                coverage["value_no_discriminating_header"] += 1
                outcomes.append(ValueOutcome(row, value.column, "value_no_discriminating_header", line))
                continue
            cells = locate(value.tokens, tokens)
            if not cells:
                coverage["value_missing_in_output"] += 1
                outcomes.append(ValueOutcome(row, value.column, "value_missing_in_output", line))
                continue
            if len(cells) > 1:
                coverage["value_ambiguous_position"] += 1
                outcomes.append(ValueOutcome(row, value.column, "value_ambiguous_position", line))
                continue
            column = cells[0]
            verdict = verdicts.get((value.column, column))
            if verdict is None:
                verdict = judge(output.header_text(column), expectation, max_states=max_states)
                verdicts[(value.column, column)] = verdict
            if verdict.outcome == "ambiguous":
                coverage["value_ambiguous_header"] += 1
                outcomes.append(ValueOutcome(row, value.column, "value_ambiguous_header", line, column))
                continue
            if verdict.outcome == "budget":
                coverage["value_unevaluated_budget"] += 1
                outcomes.append(ValueOutcome(row, value.column, "value_unevaluated_budget", line, column))
                continue
            coverage["values_evaluated"] += 1
            if verdict.outcome == "aligned":
                coverage["values_aligned"] += 1
                outcomes.append(ValueOutcome(row, value.column, "aligned", line, column))
                continue
            coverage["values_misaligned"] += 1
            outcomes.append(ValueOutcome(row, value.column, "misaligned", line, column))
            label = next((slot.text for slot in source.origin[row] if slot is not None and slot.text), "")
            misalignments.append(Misalignment(
                row, value.column, " ".join(label.split()), value.tokens, output.header_text(column),
                expectation.expected_text(), verdict.conflicting,
            ))
    return TableAlignment(coverage, tuple(misalignments), tuple(outcomes))
