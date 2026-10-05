"""Header-alignment check: each value sits under the header its source column carries.

Implements the "Header-alignment check" of
docs/superpowers/specs/2026-10-05-sec2md-table-merge-header-rules-design.md (revision 17).
Like check 1, it compares a table's source HTML with the exact Markdown emitted for it.
It shares only R0 (table_roles) and the cell-text extraction with the renderer, and never
reads the renderer's merge decisions or output-column mapping, so it measures any
renderer's Markdown, today's main included.

This module holds the source side (placed grid, R0, values, repeated headers, emitted
paths, discriminating cells) and the output side (the position-preserving Markdown cell
parser, pairing and locating).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from typing import Mapping, Sequence

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
_SPACES = re.compile(r"\s+")
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


def source_cell_text_and_links(td: Tag) -> tuple[str, tuple[str, ...]]:
    """A source cell's visible text (source_cell_text) and the destinations of the links in
    its extracted text, in order."""

    raw = extract_cell_text(td)
    text = visible_text(raw)
    if "\\|" in text and has_descendant(td, "a"):
        text = text.replace("\\|", "|")
    return text, (tuple(_LINK_DESTINATION.findall(raw)) if "](" in raw else ())


def place_source_grid(table: Tag, rows: list[_Row], grid_hidden: set[int]) -> SourceGrid | None:
    """Place a unit's own visible rows as the snapshot builder does (spec step 1).

    None when placement is unreliable (a bad span, an overlap, a nested table or an
    oversized grid): the unit is skipped as table_unreliable_grid.
    """

    return source_grid(place_unit(table, rows, grid_hidden))


def source_grid(placed: tuple[list[_Row], list[list[_GridCell | None]]] | None) -> SourceGrid | None:
    """The SourceGrid of a placement from table_completeness.place_unit (None stays None)."""

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
                text, links = source_cell_text_and_links(slot.td)
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
