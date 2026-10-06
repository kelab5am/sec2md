"""Source-to-output completeness checks for tables.

Implements docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md
(revision 6). Each visible outermost source table is compared with the exact text the
parser emitted for it. Check 1 reports source numbers missing from that text; check 2
reports rows and values that changed order. check_tables also runs the header-alignment
check (table_alignment; spec 2026-10-05). Nothing here changes rendering.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import cache, lru_cache, partial
from typing import Mapping

from bs4 import NavigableString, Tag
from bs4.element import Comment, Declaration, Doctype, ProcessingInstruction

from sec2md.chunker.blocks import is_separator_row
from sec2md.quality import _MARKDOWN_LINK_RE, _is_hidden_tag, _normalized_numbers
from sec2md.table_parser import has_descendant
from sec2md.xlsx_tables import _header_count, _hidden as _grid_hidden, _visible_text

_BLOCK = {"p", "div", "br", "li", "tr", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"}
_SKIP_STRINGS = (Comment, Declaration, Doctype, ProcessingInstruction)
_NEVER_VISIBLE = {"script", "style", "template", "noscript"}
# Relative positioning is not a marker signal: NVDA uses it to kern single digits.
_MARKER_STYLE = re.compile(r"vertical-align\s*:\s*super", re.I)
# A bare digit in a fragment link is not a marker: NVDA splits dates across such links.
_MARKER_TEXT = re.compile(r"\(\*?\d{1,2}\)|\*+|\[\d{1,2}\]")
# A hyphen or en dash between two numbers is a range separator, not a minus sign.
_RANGE_DASH = re.compile(r"(?<=[\d%])\s*[-–]\s*(?=[$(]?\d)")
_CURRENCY = str.maketrans({"€": "$", "£": "$"})
_IDENTIFIER = re.compile(r"\b(?:item|note|exhibit|part|schedule)\s+\d+[A-Z]?(?:\.\d+)?\.?", re.I)
_SIGNATURE_CELL = re.compile(r"^\s*dated?\s*:|/s/", re.I)
_SIGNATURE_ROW_MARK = re.compile(r"/s/|^\s*dated?\s*:\s*$", re.I)
_DATE_CELL = re.compile(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+(?:19|20)\d{2}$"
                        r"|^\d{1,2}/\d{1,2}/\d{2,4}$", re.I)
# Split accounting negatives: "(29" + ")", "(3.2" + ")%", "(" + "29" + ")".
_OPEN_AMOUNT = re.compile(r"^[$€£]?\s*\(\s*[$€£]?\s*\d[\d,]*(?:\.\d+)?$")
_OPEN_ONLY = re.compile(r"^[$€£]?\s*\($")
_PLAIN_AMOUNT = re.compile(r"^[$€£]?\s*\d[\d,]*(?:\.\d+)?$")
_CLOSE = re.compile(r"^\)\s*%?$")
_STANDALONE_AMOUNT = re.compile(r"^[$€£]?\s*\(?\s*[$€£]?\s*[-−]?\d[\d,]*(?:\.\d+)?\s*\)?\s*%?$")
_BARE_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_PERIOD_TEXT = re.compile(r"\b(?:years?|quarters?|months?|weeks?|period|ended|ending|as of|fiscal|calendar|maturit\w*)\b"
                          r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}\b", re.I)
# A trailing footnote reference glued to a value in the output ("1,234 (1)").
_MARKER_SUFFIX = re.compile(r"(?:\s*(?:\(\d{1,2}\)|\[\d{1,2}\]|\*+))+\s*$")
_LETTER = re.compile(r"[A-Za-z]")
_NOT_LETTER = re.compile(r"[^a-z]+")
_ALPHANUMERIC = re.compile(r"[A-Za-z\d]")
_SPACES = re.compile(r"\s+")
_EXHIBIT_HEADING = re.compile(r"\s*exhibit\b", re.I)
_DESCRIPTION_HEADING = re.compile(r"\bdescription\b", re.I)
_DIGIT = re.compile(r"\d")

# Output positions each source occurrence may claim, in order of preference.
_COMPATIBLE = {
    "reference": ("reference", "text_cell", "text_rendering", "header_line"),
    "marker": ("text_cell", "text_rendering", "header_line"),
    "standalone_marker": ("numeric_cell", "header_line", "text_rendering"),
    "value_numeric": ("numeric_cell", "header_line", "text_rendering"),
    "value_text": ("text_cell", "numeric_cell", "header_line", "text_rendering"),
}
_CLAIM_ORDER = ("reference", "marker", "standalone_marker", "value_numeric", "value_text")


# --- text and tokens ---------------------------------------------------------------

@lru_cache(maxsize=65536)
def numbers(text: str) -> tuple[str, ...]:
    """Normalized numeric tokens: currency symbols unified, range dashes not minus signs."""
    if not _DIGIT.search(text):
        return ()  # most label cells: skip the token regexes entirely
    return _normalized_numbers(_RANGE_DASH.sub(" - ", text.translate(_CURRENCY)))


def merge_split_negatives(cells: list[str]) -> list[str]:
    """Rebuild accounting negatives split across adjacent non-empty cells of one row."""
    texts = [c.strip() for c in cells if c and c.strip()]
    merged, i = [], 0
    while i < len(texts):
        here = texts[i]
        nxt = texts[i + 1] if i + 1 < len(texts) else ""
        after = texts[i + 2] if i + 2 < len(texts) else ""
        if _OPEN_AMOUNT.match(here) and _CLOSE.match(nxt):
            merged.append(here + nxt.replace(" ", ""))
            i += 2
        elif _OPEN_ONLY.match(here) and _PLAIN_AMOUNT.match(nxt) and _CLOSE.match(after):
            merged.append(here + nxt + after.replace(" ", ""))
            i += 3
        else:
            merged.append(here)
            i += 1
    return merged


def output_line_numbers(line: str) -> list[str]:
    """Tokens of one output line, cell by cell, with split negatives rebuilt."""
    return [t for cell in merge_split_negatives(line.split("|")) for t in numbers(cell)]


def _self_hidden(tag: Tag) -> tuple[bool, bool]:
    """(hidden by the source-text rule, hidden by the XLSX snapshot rule) for one tag."""
    name = tag.name
    by_name = name in _NEVER_VISIBLE or name in ("ix:hidden", "hidden") or name.endswith(":hidden")
    attrs = tag.attrs
    if not attrs:
        return by_name, False
    # Both rules need a hidden/aria-hidden attribute or "none"/"hidden" in the style;
    # checking that first skips the full rules for almost every styled tag.
    style = str(attrs.get("style", "")).lower()
    if "hidden" not in attrs and "aria-hidden" not in attrs and "none" not in style and "hidden" not in style:
        return by_name, False
    return by_name or _is_hidden_tag(tag), _grid_hidden(tag)


def hidden_sets(soup) -> tuple[list[Tag], set[int], set[int]]:
    """Outermost tables and the hidden nodes inside them, from one scoped pass.

    Returns (outermost tables, hidden, grid_hidden). hidden follows
    quality._is_hidden_tag plus script, style, template and noscript, and decides what
    counts as source text. grid_hidden follows the XLSX snapshot rule, so header rows
    match the grids snapshots build. Only tables and their ancestor chains are examined.
    """
    hidden: set[int] = set()
    grid_hidden: set[int] = set()
    ancestors: dict[int, tuple[bool, bool]] = {}
    outermost = []
    for table in soup.find_all("table"):
        if table.find_parent("table") is not None:
            continue
        outermost.append(table)
        chain, flags = [], (False, False)
        for parent in table.parents:
            if not isinstance(parent, Tag):
                continue
            if id(parent) in ancestors:
                flags = ancestors[id(parent)]
                break
            chain.append(parent)
        for parent in reversed(chain):
            own = _self_hidden(parent)
            flags = (flags[0] or own[0], flags[1] or own[1])
            ancestors[id(parent)] = flags
        stack = [(table, flags)]
        while stack:
            node, (text_hidden, grid_rule) = stack.pop()
            own = _self_hidden(node)
            text_hidden, grid_rule = text_hidden or own[0], grid_rule or own[1]
            if text_hidden:
                hidden.add(id(node))
            if grid_rule:
                grid_hidden.add(id(node))
            stack.extend((child, (text_hidden, grid_rule)) for child in node.children if isinstance(child, Tag))
    return outermost, hidden, grid_hidden


def _is_marker(tag: Tag) -> bool:
    if tag.name == "sup" or _MARKER_STYLE.search(str(tag.get("style", ""))):
        return True
    return (tag.name == "a" and str(tag.get("href", "")).startswith("#")
            and bool(_MARKER_TEXT.fullmatch(tag.get_text(strip=True))))


def _walk(node: Tag, hidden: set[int], out: list, marker: bool) -> None:
    for child in node.children:
        if isinstance(child, _SKIP_STRINGS):
            continue
        if isinstance(child, NavigableString):
            out.append((str(child), marker))
            continue
        if id(child) in hidden or child.name == "table":
            continue  # nested tables are counted through their own rows
        child_marker = marker or _is_marker(child)
        separate = child.name in _BLOCK or child_marker != marker
        if separate:
            out.append((" ", marker))
        _walk(child, hidden, out, child_marker)
        if separate:
            out.append((" ", marker))


def cell_text(cell: Tag, hidden: set[int]) -> tuple[str, str]:
    """(value text, footnote-marker text) of one cell, built from its visible DOM."""
    pieces: list = []
    _walk(cell, hidden, pieces, False)
    value = _SPACES.sub(" ", "".join(" " if m else t for t, m in pieces)).strip()
    marks = _SPACES.sub(" ", " ".join(t for t, m in pieces if m)).strip()
    return value, marks


# --- classes and positions -----------------------------------------------------------

def _value_kind(text: str) -> str:
    return "value_text" if _LETTER.search(text) else "value_numeric"


def classify_cell(text: str, signature_row: bool = False) -> list[tuple[str, str]]:
    """(token, kind) for one source cell, in left-to-right order."""
    if _SIGNATURE_CELL.search(text) or (signature_row and _DATE_CELL.match(text)):
        return [(t, "reference") for t in numbers(text)]
    kind = _value_kind(text)
    tokens, last = [], 0
    for m in _IDENTIFIER.finditer(text):
        tokens += [(t, kind) for t in numbers(text[last:m.start()])]
        tokens += [(t, "reference") for t in numbers(m.group(0))]
        last = m.end()
    return tokens + [(t, kind) for t in numbers(text[last:])]


def label_key(text: str) -> str:
    """Letters of a row label plus its identifier numbers ("Note 1" -> "note#1")."""
    identifiers = [t for m in _IDENTIFIER.finditer(text) for t in numbers(m.group(0))]
    letters = _NOT_LETTER.sub("", text.lower())
    return letters + ("#" + ",".join(identifiers) if identifiers else "")


def row_label_key(texts: list[tuple[str, str]]) -> str:
    """Check 1's key of a source row: the label key of its first non-empty cell value."""
    return label_key(next((value for value, _ in texts if value), ""))


def line_label_key(cells: list[str]) -> str:
    """Check 1's key of an output line, from its cells with split negatives merged."""
    return label_key(cells[0]) if cells else ""


def is_period_row(cells: list[str], before_header_end: bool) -> bool:
    """Header or period row, decided by context, never by the shape of its numbers."""
    if before_header_end:
        return True
    texts = [c for c in cells if c]
    if not texts or not all(_PERIOD_TEXT.search(c) or _BARE_YEAR.match(c) for c in texts):
        return False
    return any(_PERIOD_TEXT.search(c) for c in texts) or all(_BARE_YEAR.match(c) for c in texts)


def is_data_row(cells: list[str], before_header_end: bool) -> bool:
    return not is_period_row(cells, before_header_end) and any(_STANDALONE_AMOUNT.match(c) for c in cells)


def _output_cell_positions(cell: str, signature_row: bool) -> list[tuple[str, str]]:
    if _SIGNATURE_CELL.search(cell) or (signature_row and _DATE_CELL.match(cell.strip())):
        return [(t, "reference") for t in numbers(cell)]
    position = "text_cell" if _LETTER.search(cell) else "numeric_cell"
    occurrences = [(t, "reference") for m in _IDENTIFIER.finditer(cell) for t in numbers(m.group(0))]
    cell = _IDENTIFIER.sub(" ", cell)
    suffix = _MARKER_SUFFIX.search(cell)
    # A trailing "(1)" is a marker only when a number remains ("1,234 (1)"); "$ (96)" is a negative.
    if suffix and _DIGIT.search(cell, 0, suffix.start()):
        core, tail = cell[:suffix.start()], cell[suffix.start():]
    else:
        core, tail = cell, ""
    occurrences += [(t, position) for t in numbers(core)]
    occurrences += [(t, "text_cell") for t in numbers(tail.replace("(", " (").replace(")", ") "))]
    return occurrences


def output_positions(segment: str, exhibit_index: bool) -> tuple[list[tuple[str, Counter]], Counter]:
    """(body lines as (label key, positioned tokens), header-line and text-rendering tokens)."""
    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    body, other = [], Counter()
    for i, line in enumerate(lines):
        if separator is None:
            last = 0
            for m in _IDENTIFIER.finditer(line):
                other.update((t, "text_rendering") for t in numbers(line[last:m.start()]))
                other.update((t, "reference") for t in numbers(m.group(0)))
                last = m.end()
            other.update((t, "text_rendering") for t in numbers(line[last:]))
            continue
        if i == separator:
            continue
        cells = merge_split_negatives(line.split("|"))
        if i < separator:
            other.update((t, "header_line") for cell in cells for t in numbers(cell))
            continue
        signature_row = any(_SIGNATURE_ROW_MARK.search(c) for c in cells)
        found: Counter = Counter()
        for cell in cells:
            if exhibit_index:
                found.update((t, "reference") for t in numbers(cell))
            else:
                found.update(_output_cell_positions(cell, signature_row))
        body.append((line_label_key(cells), found))
    return body, other


# --- header rows without building snapshots ----------------------------------------

class _GridCell:
    """A placed cell. _header_count reads only the rows it examines, so the text and
    numeric-fact flag are computed on first read rather than for every cell."""

    __slots__ = ("td", "grid_hidden", "row", "column", "rowspan", "colspan", "is_header", "_text", "_numeric")

    def __init__(self, td, grid_hidden, row, column, rowspan, colspan):
        self.td, self.grid_hidden = td, grid_hidden
        self.row, self.column, self.rowspan, self.colspan = row, column, rowspan, colspan
        self.is_header = td.name == "th"
        self._text = self._numeric = None

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = _visible_text(self.td)
        return self._text

    @property
    def is_numeric_fact(self) -> bool:
        if self._numeric is None:
            self._numeric = any(isinstance(d, Tag) and d.name in _NUMERIC_FACT_NAMES and id(d) not in self.grid_hidden
                                for d in self.td.descendants)
        return self._numeric


class _Row:
    """A tr of a table unit: whether the unit owns it, and the cells whose nearest tr it is."""

    __slots__ = ("tr", "own", "cells")

    def __init__(self, tr: Tag, own: bool):
        self.tr, self.own, self.cells = tr, own, []


def unit_rows(table: Tag) -> list[_Row]:
    """Every tr inside a table unit, in document order, from one traversal.

    Avoids per-row and per-cell BeautifulSoup searches, which dominate the cost otherwise.
    """
    rows: list[_Row] = []
    stack = [(child, table, None) for child in reversed(list(table.children)) if isinstance(child, Tag)]
    while stack:
        node, owner, row = stack.pop()
        if node.name == "table":
            owner, row = node, None
        elif node.name == "tr":
            row = _Row(node, owner is table)
            rows.append(row)
        elif node.name in ("td", "th") and row is not None:
            row.cells.append(node)
        stack.extend((child, owner, row) for child in reversed(list(node.children)) if isinstance(child, Tag))
    return rows


_NUMERIC_FACT_NAMES = {"ix:nonfraction", "ix:fraction", "nonfraction", "fraction"}


def place_unit(table: Tag, rows: list[_Row], grid_hidden: set[int]) -> tuple[list[_Row], list[list[_GridCell | None]]] | None:
    """The snapshot builder's placement of a unit's own visible rows.

    Returns (placed rows, grid): grid[r][k] is the cell covering slot (r, k), or None. Placed
    rows and columns, empty ones included, are the original coordinates. None means the
    placement is unreliable: a nested table, a bad or oversized span, an overlap, or an
    oversized grid. A unit without visible cells gives an empty grid.
    """
    if has_descendant(table, "table"):
        return None
    rows = [row for row in rows if row.own and id(row.tr) not in grid_hidden]
    # The snapshot builder's placement rules, with occupied spans kept per row so each
    # lookup only scans its own row (the builder compares every cell with every other).
    taken: list[list[tuple[int, int]]] = [[] for _ in rows]
    cells, row_widths = [], [0] * len(rows)
    for r, row in enumerate(rows):
        column = 0
        for td in row.cells:
            if id(td) in grid_hidden:
                continue
            while True:
                covering = [end for start, end in taken[r] if start <= column < end]
                if not covering:
                    break
                column = max(covering)
            spans = []
            for attr, limit in (("rowspan", 65534), ("colspan", 1000)):
                try:
                    value = int(td.get(attr, "1"))
                except (TypeError, ValueError):
                    return None
                if value <= 0 or value > limit:
                    return None
                spans.append(value)
            rowspan, colspan = spans
            bottom, end = r + rowspan, column + colspan
            if bottom > len(rows) or any(start < end and finish > column
                                         for rr in range(r, bottom) for start, finish in taken[rr]):
                return None
            cells.append(_GridCell(td, grid_hidden, r, column, rowspan, colspan))
            for rr in range(r, bottom):
                taken[rr].append((column, end))
            row_widths[r] += colspan
            column = end
    if not cells:
        return rows, []
    flat_width = max(row_widths)
    height = max(c.row + c.rowspan for c in cells)
    width = max(c.column + c.colspan for c in cells)
    if width > flat_width or height * width > 1_000_000:
        return None
    grid: list[list[_GridCell | None]] = [[None] * width for _ in range(height)]
    for c in cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                grid[r][k] = c
    return rows, grid


def placed_header_rows(placed: tuple[list[_Row], list[list[_GridCell | None]]] | None) -> int:
    """xlsx_tables._header_count over a placement from place_unit; 0 where it is unreliable or empty."""
    if placed is None or not placed[1]:
        return 0
    return _header_count(placed[1])


def header_row_count(table: Tag, rows: list[_Row], grid_hidden: set[int]) -> int:
    """xlsx_tables._header_count over the grid a snapshot would build; 0 where a snapshot is unreliable."""
    return placed_header_rows(place_unit(table, rows, grid_hidden))


# --- matching ------------------------------------------------------------------------

def _claim(occurrences: Counter, pool: Counter, shared: dict | None) -> Counter:
    left: Counter = Counter()
    for kind in _CLAIM_ORDER:
        for (token, k, role), count in sorted(occurrences.items()):
            if k != kind:
                continue
            for _ in range(count):
                position = next((p for p in _COMPATIBLE[kind] if pool[(token, p)] > 0), None)
                if position is None:
                    left[(token, k, role)] += 1
                    continue
                pool[(token, position)] -= 1
                if shared is not None and not kind.startswith("value"):
                    shared.setdefault(token, set()).add(position)
    return left


def match_occurrences(rows: list[tuple[str, Counter]], body: list[tuple[str, Counter]], other: Counter):
    """Check 1 matching: proven row pairs first, then a table-wide pass.

    Returns (missing values as (token, role, ambiguous), missing reported as (token, class)),
    where class is "reference", "marker" or "standalone_marker".
    """
    pools = [Counter(found) for _, found in body]
    source_counts = Counter(key for key, _ in rows if key)
    output_counts = Counter(key for key, _ in body if key)
    line_of = {key: i for i, (key, _) in enumerate(body) if key and output_counts[key] == 1}
    unclaimed: Counter = Counter()
    for key, occurrences in rows:
        line = line_of.get(key) if key and source_counts[key] == 1 else None
        unclaimed.update(occurrences if line is None else _claim(occurrences, pools[line], None))
    remaining = Counter(other)
    for pool in pools:
        remaining.update(+pool)
    shared: dict[str, set] = {}
    final = _claim(unclaimed, remaining, shared)
    missing_values, missing_reported = [], []
    for (token, kind, role), count in sorted(final.items()):
        for _ in range(count):
            if kind.startswith("value"):
                missing_values.append((token, role, bool(shared.get(token, set()) & set(_COMPATIBLE[kind]))))
            else:
                missing_reported.append((token, kind))
    return missing_values, missing_reported


def row_structure(source_rows: list[tuple[str, ...]], segment: str) -> list[str]:
    """Check 2 over body lines: within-row order, rows out of order, values split across rows."""
    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    if separator is None:
        return []
    body = [output_line_numbers(line) for line in lines[separator + 1:]]
    body_all = Counter(t for line in body for t in line)
    findings, pointer = [], 0
    for number, row in enumerate(source_rows, 1):
        need = Counter(row)
        hit = next((k for k in range(pointer, len(body)) if not need - Counter(body[k])), None)
        if hit is not None:
            left, projected = Counter(need), []
            for token in body[hit]:
                if left[token]:
                    projected.append(token)
                    left[token] -= 1
            if tuple(projected) != row:
                findings.append(f"source row {number}: values out of order within the row")
            pointer = hit
        elif any(not need - Counter(body[k]) for k in range(pointer)):
            findings.append(f"source row {number}: appears before an earlier source row")
        elif not need - body_all:
            findings.append(f"source row {number}: values present but split across output rows")
    return findings


# --- report ---------------------------------------------------------------------------

def unit_location(ordinal: int, snapshot_ordinal: int | None, page: int | None) -> str:
    """'table 24 (snapshot 19, page 41)': how findings name a table unit."""
    parts = [f"snapshot {snapshot_ordinal}" if snapshot_ordinal else "", f"page {page}" if page else ""]
    detail = ", ".join(p for p in parts if p)
    return f"table {ordinal}" + (f" ({detail})" if detail else "")


@dataclass(frozen=True)
class TableFinding:
    """Check 1 and check 2 results for one table unit."""

    ordinal: int
    snapshot_ordinal: int | None
    page: int | None
    missing_values: tuple[tuple[str, str, bool], ...] = ()
    missing_reported: tuple[tuple[str, str], ...] = ()
    structure: tuple[str, ...] = ()
    produced_output: bool = True

    def _where(self) -> str:
        return unit_location(self.ordinal, self.snapshot_ordinal, self.page)

    def value_message(self) -> str | None:
        if not self.missing_values:
            return None
        if not self.produced_output:
            return f"{self._where()} produced no output ({len(self.missing_values)} numbers)"
        counts = Counter(self.missing_values)
        listed = ", ".join(f"{token} x{n} [{role}{', ambiguous' if ambiguous else ''}]"
                           for (token, role, ambiguous), n in list(counts.items())[:10])
        return f"{self._where()}: missing {listed} (total {len(self.missing_values)})"

    def reported_message(self) -> str | None:
        if not self.missing_reported:
            return None
        counts = Counter(self.missing_reported)
        listed = ", ".join(f"{token} x{n} [{cls}]" for (token, cls), n in list(counts.items())[:10])
        return f"{self._where()}: missing {listed} (total {len(self.missing_reported)})"

    def structure_messages(self) -> tuple[str, ...]:
        return tuple(f"{self._where()}: {s}" for s in self.structure)

    def messages(self) -> tuple[str, ...]:
        """Every message for this table: value failures, reported tokens, then row structure."""
        return tuple(m for m in (self.value_message(), self.reported_message()) if m) + self.structure_messages()


@dataclass(frozen=True)
class TableCompletenessReport:
    """Checks 1 and 2 per table, plus the header-alignment findings and coverage counts.

    alignment_coverage holds every table_alignment.COVERAGE_KEYS key in order once
    check_tables completes; empty means the alignment check did not run.
    """

    tables_checked: int
    findings: tuple[TableFinding, ...]
    alignment: tuple[str, ...] = ()
    alignment_coverage: tuple[tuple[str, int], ...] = ()

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(m for f in self.findings if (m := f.value_message()))

    @property
    def reported(self) -> tuple[str, ...]:
        return tuple(m for f in self.findings if (m := f.reported_message()))

    @property
    def structure(self) -> tuple[str, ...]:
        return tuple(m for f in self.findings for m in f.structure_messages())


def _direct_cells(tr: Tag) -> list[Tag]:
    return [c for c in tr.children if isinstance(c, Tag) and c.name in ("td", "th")]


def check_tables(soup, table_outputs: Mapping[int, str], table_pages: Mapping[int, int],
                 snapshot_ordinals: Mapping[int, int], *,
                 cell_texts: Mapping[int, str] | None = None,
                 base_url: str | None = None) -> TableCompletenessReport:
    """Run checks 1 and 2 and the header-alignment check over every visible outermost table.

    cell_texts optionally maps id(td) to the cell's ``table_parser.extract_cell_text`` result
    already computed by the render, which the header-alignment check then reuses. base_url is
    the base URL the render resolved links against (the Parser's source URL): the
    header-alignment check resolves the links of the cells it extracts itself against it.
    """
    # Imported here: table_alignment builds on this module.
    from sec2md.table_alignment import align_table, coverage_items

    numbers.cache_clear()  # the token cache is per document
    outermost, hidden, grid_hidden = hidden_sets(soup)
    units = [t for t in outermost if id(t) not in hidden]
    findings, checked = [], 0
    alignment: list[str] = []
    alignment_coverage: Counter = Counter()
    for ordinal, table in enumerate(units, 1):
        all_rows = unit_rows(table)
        rows = [row for row in all_rows if id(row.tr) not in hidden]
        own_rows = [row for row in rows if row.own]
        own_index = {id(row.tr): i for i, row in enumerate(own_rows)}
        texts_by_row = [[cell_text(c, hidden) for c in _direct_cells(row.tr) if id(c) not in hidden] for row in rows]
        raw = table_outputs.get(id(table), "")

        # The header-alignment check covers every unit, pairing rows by check 1's keys. The
        # unit is placed at most once, for whichever of the two checks needs it first.
        placement = cache(partial(place_unit, table, all_rows, grid_hidden))
        row_keys = {id(row.tr): row_label_key(texts) for row, texts in zip(rows, texts_by_row) if row.own}
        aligned = align_table(table, all_rows, grid_hidden, raw, row_keys,
                              Counter(key for key in row_keys.values() if key), placement=placement,
                              cell_texts=cell_texts, base_url=base_url)
        alignment_coverage.update(aligned.coverage)
        alignment.extend(aligned.messages(unit_location(ordinal, snapshot_ordinals.get(id(table)),
                                                        table_pages.get(id(table)))))

        if not any(_DIGIT.search(value) or _DIGIT.search(marks) for texts in texts_by_row for value, marks in texts):
            continue  # no source tokens
        leading = [value for row, texts in zip(rows, texts_by_row) if row.own and own_index[id(row.tr)] < 3
                   for value, _ in texts]
        exhibit_index = (any(_EXHIBIT_HEADING.match(v) for v in leading)
                         and any(_DESCRIPTION_HEADING.search(v) for v in leading))
        segment = _MARKDOWN_LINK_RE.sub(lambda m: m.group(1), raw)
        body, other = output_positions(segment, exhibit_index)

        # Header rows are never data rows (check 2) and label value findings "header".
        header_rows = placed_header_rows(placement())
        row_occurrences, source_rows, total = [], [], 0
        for row, texts in zip(rows, texts_by_row):
            row_index = own_index[id(row.tr)] if row.own else -1
            row_role = "header" if row.own and row_index < header_rows else (None if row.own else "nested")
            values = merge_split_negatives([v for v, _ in texts])
            signature_row = any(_SIGNATURE_ROW_MARK.search(v) for v in values)
            occurrences: Counter = Counter()
            row_tokens = []
            for position, text in enumerate(values):
                role = row_role or ("label" if position == 0 else "body")
                for token, kind in classify_cell(text, signature_row):
                    occurrences[(token, "reference" if exhibit_index else kind, role)] += 1
                    row_tokens.append(token)
            for value, marks in texts:
                marker_kind = "marker" if _ALPHANUMERIC.search(value) else "standalone_marker"
                for token in numbers(marks.replace("(", " (").replace(")", ") ")):
                    occurrences[(token, marker_kind, row_role or "body")] += 1
            if row.own and len(row_tokens) >= 2 and is_data_row(values, row_index < header_rows):
                source_rows.append(tuple(row_tokens))
            total += sum(occurrences.values())
            row_occurrences.append((row_label_key(texts) if row.own else "", occurrences))
        if not total:
            continue
        missing_values, missing_reported = match_occurrences(row_occurrences, body, other)
        structure = row_structure(source_rows, segment)
        checked += 1
        if missing_values or missing_reported or structure:
            findings.append(TableFinding(ordinal, snapshot_ordinals.get(id(table)), table_pages.get(id(table)),
                                         tuple(missing_values), tuple(missing_reported), tuple(structure),
                                         produced_output=bool(raw.strip())))
    return TableCompletenessReport(checked, tuple(findings), tuple(alignment),
                                   coverage_items(alignment_coverage))
