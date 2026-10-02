"""Prototype of the table completeness checks, spec revision 4.

Revision 4 adds to revision 3:
- occurrence provenance: each source and output number has a position (standalone amount
  cell, text, identifier, header line); a value may only be matched by a compatible output
  occurrence, and non-value occurrences claim first, so a surviving "Note 9" or <sup>9</sup>
  never stands in for a lost amount 9; shortfalls where provenance is shared are "ambiguous"
- period rows decided by period context (header rows, period text, period captions),
  never by the numeric shape of a value

Implements exactly the revision 3 definitions, plus the above:
- unit: each visible outermost <table>; nested tables belong to it; ordinal over all units,
  with the TableSnapshot ordinal reported alongside
- rendering: the caller's mode (normal or capture); snapshot metadata comes from a separate
  read-only parse, so it never changes the rendering being checked
- cell text: DOM-aware; hidden descendants skipped; footnote markers separated
- tokens: $/EUR/GBP normalized; range dashes; per cell; split accounting negatives such as
  "(29" + ")" rebuilt across adjacent cells on both sides
- classes per token: marker, reference (identifier prefix, signature/date cell, exhibit index),
  value (everything else, enforced)
- check 2: rows matched within one body line, out-of-order rows, values split across rows
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from bs4 import NavigableString, Tag
from bs4.element import Comment, Declaration, Doctype, ProcessingInstruction

from sec2md.chunker.blocks import is_separator_row
from sec2md.parser import Parser
from sec2md.quality import _MARKDOWN_LINK_RE, _is_hidden_tag, _normalized_numbers
from sec2md.xlsx_tables import _header_count

BLOCK = {"p", "div", "br", "li", "tr", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"}
SKIP_STRINGS = (Comment, Declaration, Doctype, ProcessingInstruction)
# Relative positioning is not a marker signal: NVDA uses it to kern individual digits.
MARKER_STYLE = re.compile(r"vertical-align\s*:\s*super", re.I)
# A bare digit in a fragment link is not enough: NVDA splits dates across such links.
MARKER_TEXT = re.compile(r"\(\*?\d{1,2}\)|\*+|\[\d{1,2}\]")
# A hyphen or en dash between two numbers is a range separator, not a minus sign.
RANGE_DASH = re.compile(r"(?<=[\d%])\s*[-–]\s*(?=[$(]?\d)")
CURRENCY = str.maketrans({"€": "$", "£": "$"})
SIGNATURE_CELL = re.compile(r"^\s*dated?\s*:|/s/", re.I)
# In a signature row only date-shaped cells are references; other cells keep their class.
SIGNATURE_ROW_MARK = re.compile(r"/s/|^\s*dated?\s*:\s*$", re.I)
DATE_CELL = re.compile(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s+(?:19|20)\d{2}$"
                       r"|^\d{1,2}/\d{1,2}/\d{2,4}$", re.I)
# Split accounting negatives: "(29" + ")", "(3.2" + ")%", "(" + "29" + ")".
OPEN_AMOUNT = re.compile(r"^[$€£]?\s*\(\s*[$€£]?\s*\d[\d,]*(?:\.\d+)?$")
OPEN_ONLY = re.compile(r"^[$€£]?\s*\($")
PLAIN_AMOUNT = re.compile(r"^[$€£]?\s*\d[\d,]*(?:\.\d+)?$")
CLOSE = re.compile(r"^\)\s*%?$")
STANDALONE_AMOUNT = re.compile(r"^[$€£]?\s*\(?\s*[$€£]?\s*[-−]?\d[\d,]*(?:\.\d+)?\s*\)?\s*%?$")
BARE_YEAR = re.compile(r"^(?:19|20)\d{2}$")
# Period context: duration words, period captions and month-day dates.
PERIOD_TEXT = re.compile(r"\b(?:years?|quarters?|months?|weeks?|period|ended|ending|as of|fiscal|calendar|maturit\w*)\b"
                         r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}\b", re.I)


def is_period_row(cells: list[str], before_header_end: bool) -> bool:
    """A header or period row, decided by context rather than by the shape of its numbers.

    Rows before the snapshot's header-row count are period rows. Otherwise every cell must
    be period text or a bare year, with at least one cell carrying period text or the label
    cell missing: "Three Months Ended June 30, 2025 | ... 2024", "Maturities (calendar year)
    | 2023 | 2022" and "| 2023 | 2022" qualify; "Revenue | 2000 | 1900" does not.
    """
    if before_header_end:
        return True
    texts = [c for c in cells if c]
    if not texts or not all(PERIOD_TEXT.search(c) or BARE_YEAR.match(c) for c in texts):
        return False
    return any(PERIOD_TEXT.search(c) for c in texts) or all(BARE_YEAR.match(c) for c in texts)


def is_data_row(cells: list[str], before_header_end: bool) -> bool:
    """Check 2 rows: not a period row, and with at least one standalone amount cell."""
    return not is_period_row(cells, before_header_end) and any(STANDALONE_AMOUNT.match(c) for c in cells)


def numbers(text: str) -> list[str]:
    return list(_normalized_numbers(RANGE_DASH.sub(" - ", text.translate(CURRENCY))))


def merge_split_negatives(cells: list[str]) -> list[str]:
    """Rebuild accounting negatives split across adjacent non-empty cells."""
    texts = [c.strip() for c in cells if c and c.strip()]
    merged, i = [], 0
    while i < len(texts):
        here = texts[i]
        nxt = texts[i + 1] if i + 1 < len(texts) else ""
        after = texts[i + 2] if i + 2 < len(texts) else ""
        if OPEN_AMOUNT.match(here) and CLOSE.match(nxt):
            merged.append(here + nxt.replace(" ", ""))
            i += 2
        elif OPEN_ONLY.match(here) and PLAIN_AMOUNT.match(nxt) and CLOSE.match(after):
            merged.append(here + nxt + after.replace(" ", ""))
            i += 3
        else:
            merged.append(here)
            i += 1
    return merged


def output_numbers(line: str) -> list[str]:
    """Tokens of one output line, per cell, with split negatives rebuilt."""
    return [t for cell in merge_split_negatives(line.split("|")) for t in numbers(cell)]


def hidden_ids(soup) -> set[int]:
    ids: set[int] = set()
    for tag in soup.find_all(True):
        if id(tag) in ids:
            continue
        if _is_hidden_tag(tag) or tag.name in ("script", "style", "template", "noscript"):
            ids.add(id(tag))
            ids.update(id(d) for d in tag.find_all(True))
    return ids


def is_marker(tag: Tag) -> bool:
    if tag.name == "sup" or MARKER_STYLE.search(str(tag.get("style", ""))):
        return True
    return (tag.name == "a" and str(tag.get("href", "")).startswith("#")
            and bool(MARKER_TEXT.fullmatch(tag.get_text(strip=True))))


def _walk(node, hid, out, marker):
    for child in node.children:
        if isinstance(child, SKIP_STRINGS):
            continue
        if isinstance(child, NavigableString):
            out.append((str(child), marker))
            continue
        if id(child) in hid or child.name == "table":
            continue
        child_marker = marker or is_marker(child)
        separate = child.name in BLOCK or child_marker != marker
        if separate:
            out.append((" ", marker))
        _walk(child, hid, out, child_marker)
        if separate:
            out.append((" ", marker))


def cell_text(cell, hid) -> tuple[str, str]:
    pieces: list = []
    _walk(cell, hid, pieces, False)
    value = re.sub(r"\s+", " ", "".join(" " if m else t for t, m in pieces)).strip()
    marks = re.sub(r"\s+", " ", " ".join(t for t, m in pieces if m)).strip()
    return value, marks


# A footnote reference glued to a value in the output ("1,234 (1)") does not make the
# value part of text.
MARKER_SUFFIX = re.compile(r"(?:\s*(?:\(\d{1,2}\)|\[\d{1,2}\]|\*+))+\s*$")
OUTPUT_IDENTIFIER = re.compile(r"\b(?:item|note|exhibit|part|schedule)\s+\d+[A-Z]?(?:\.\d+)?\.?", re.I)

# Output contexts a source occurrence may claim, in order of preference. Non-value
# occurrences claim first; a value may never claim an identifier or footnote position.
COMPATIBLE = {
    "reference": ("reference", "embedded", "text", "header"),
    "marker": ("embedded", "text", "header"),
    "value_standalone": ("standalone", "header", "text"),
    "value_embedded": ("embedded", "standalone", "header", "text"),
}
CLAIM_ORDER = ("reference", "marker", "value_standalone", "value_embedded")


LETTER = re.compile(r"[A-Za-z]")


def _value_kind(text: str) -> str:
    """A number in a numeric cell (no letters) or in a text cell."""
    return "value_embedded" if LETTER.search(text) else "value_standalone"


def _split_identifiers(text: str) -> tuple[str, list[str]]:
    """Cell text with identifiers ("Note 9", "Exhibit 2.1") blanked out, and the identifiers.

    Identifiers are found anywhere in the cell, identically for source and output, and only
    their own number becomes a reference; the rest of the cell keeps its class.
    """
    identifiers = [m.group(0) for m in OUTPUT_IDENTIFIER.finditer(text)]
    return OUTPUT_IDENTIFIER.sub(" ", text), identifiers


def classify_cell(text: str, signature_row: bool = False) -> list[tuple[str, str]]:
    """(token, kind) for one source cell; kind is reference, value_standalone or value_embedded."""
    if SIGNATURE_CELL.search(text) or (signature_row and DATE_CELL.match(text)):
        return [(t, "reference") for t in numbers(text)]
    kind = _value_kind(text)
    tokens, last = [], 0
    # Keep left-to-right order: check 2 compares row order.
    for m in OUTPUT_IDENTIFIER.finditer(text):
        tokens += [(t, kind) for t in numbers(text[last:m.start()])]
        tokens += [(t, "reference") for t in numbers(m.group(0))]
        last = m.end()
    return tokens + [(t, kind) for t in numbers(text[last:])]


def _output_cell_contexts(cell: str, signature_row: bool) -> list[tuple[str, str]]:
    if SIGNATURE_CELL.search(cell) or (signature_row and DATE_CELL.match(cell.strip())):
        return [(t, "reference") for t in numbers(cell)]
    # Same rule as the source side: a number is in a text cell if the cell has letters.
    ctx = "embedded" if LETTER.search(cell) else "standalone"
    cell, identifiers = _split_identifiers(cell)
    occurrences = [(t, "reference") for ident in identifiers for t in numbers(ident)]
    suffix = MARKER_SUFFIX.search(cell)
    # Strip a trailing "(1)" as a marker only when a number remains ("1,234 (1)"); "$ (96)"
    # is an accounting negative, not a marker.
    if suffix and re.search(r"\d", cell[:suffix.start()]):
        core, tail = cell[:suffix.start()], cell[suffix.start():]
    else:
        core, tail = cell, ""
    occurrences += [(t, ctx) for t in numbers(core)]
    occurrences += [(t, "embedded") for t in numbers(tail.replace("(", " (").replace(")", ") "))]
    return occurrences


def output_occurrences(segment: str, exhibit_index: bool) -> Counter:
    """Every output number with its position: reference, standalone, embedded, header or text."""
    lines = segment.split("\n")
    separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
    found: Counter = Counter()
    for i, line in enumerate(lines):
        if separator is None:
            # Text rendering: only identifiers can be told apart.
            last = 0
            for m in OUTPUT_IDENTIFIER.finditer(line):
                found.update((t, "text") for t in numbers(line[last:m.start()]))
                found.update((t, "reference") for t in numbers(m.group(0)))
                last = m.end()
            found.update((t, "text") for t in numbers(line[last:]))
            continue
        if i == separator:
            continue
        cells = merge_split_negatives(line.split("|"))
        if i < separator:
            found.update((t, "header") for cell in cells for t in numbers(cell))
            continue
        signature_row = any(SIGNATURE_ROW_MARK.search(c) for c in cells)
        for cell in cells:
            if exhibit_index:
                found.update((t, "reference") for t in numbers(cell))
            else:
                found.update(_output_cell_contexts(cell, signature_row))
    return found


def allocate(expected: Counter, available: Counter):
    """Match source occurrences to compatible output occurrences.

    Returns (value_missing, reported_missing). value_missing items are
    (token, role, ambiguous): ambiguous when a reference or marker occurrence of the
    same number claimed a position this value could also have used.
    """
    pool = Counter(available)
    shared: dict[str, set] = {}
    value_missing, reported_missing = [], []
    for kind in CLAIM_ORDER:
        for (token, k, role), count in sorted(expected.items()):
            if k != kind:
                continue
            for _ in range(count):
                ctx = next((c for c in COMPATIBLE[kind] if pool[(token, c)] > 0), None)
                if ctx is not None:
                    pool[(token, ctx)] -= 1
                    if not kind.startswith("value"):
                        shared.setdefault(token, set()).add(ctx)
                elif kind.startswith("value"):
                    value_missing.append((token, role, bool(shared.get(token, set()) & set(COMPATIBLE[kind]))))
                else:
                    reported_missing.append((token, kind))
    return value_missing, reported_missing


@dataclass
class TableResult:
    ordinal: int
    snapshot_ordinal: int | None
    has_numbers: bool = False
    missing: Counter = field(default_factory=Counter)   # enforced value tokens, by row role
    reported: Counter = field(default_factory=Counter)  # marker / reference tokens
    missing_tokens: list = field(default_factory=list)
    ambiguous: int = 0                                  # value shortfalls with shared provenance
    order: list = field(default_factory=list)           # check 2 findings


def _units(soup, hid):
    return [t for t in soup.find_all("table") if id(t) not in hid and t.find_parent("table") is None]


def _header_rows(snap) -> int:
    if not snap or not snap.source_cells or snap.issues:
        return 0
    height = max(c.row + max(c.rowspan, 1) for c in snap.source_cells)
    width = max(c.column + max(c.colspan, 1) for c in snap.source_cells)
    if height * width > 1_000_000:
        return 0
    grid = [[None] * width for _ in range(height)]
    for c in snap.source_cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.column, c.column + c.colspan):
                grid[r][k] = c
    return _header_count(grid)


def _snapshot_metadata(html) -> list:
    """Snapshot per unit index from a separate capture-mode parse (read-only for the checked rendering)."""
    meta = Parser(html, capture_tables=True)
    meta.get_pages(include_images=False)
    by_node = {id(nodes[0]): snap for snap, nodes in zip(meta.table_snapshots, meta._snapshot_nodes) if len(nodes) == 1}
    return [by_node.get(id(t)) for t in _units(meta.soup, hidden_ids(meta.soup))]


def analyze(html, capture=False, mutate=None) -> list[TableResult]:
    parser = Parser(html, capture_tables=capture)
    segments: dict[int, str] = {}
    original = parser._process_element

    def recording(element):
        out = original(element)
        if isinstance(element, Tag) and element.name == "table" and element.find_parent("table") is None:
            segments[id(element)] = mutate(out) if mutate else out
        return out

    parser._process_element = recording
    parser.get_pages(include_images=False)
    snapshots = _snapshot_metadata(html)
    hid = hidden_ids(parser.soup)
    results = []
    for index, table in enumerate(_units(parser.soup, hid)):
        snap = snapshots[index] if index < len(snapshots) else None
        res = TableResult(index + 1, snap.ordinal if snap else None)
        rows = [tr for tr in table.find_all("tr") if id(tr) not in hid]
        own_rows = [tr for tr in rows if tr.find_parent("table") is table]
        header_rows = _header_rows(snap)
        leading = [cell_text(c, hid)[0] for tr in own_rows[:3] for c in tr.find_all(["td", "th"], recursive=False)]
        exhibit_index = (any(re.match(r"\s*exhibit\b", v, re.I) for v in leading)
                         and any(re.search(r"\bdescription\b", v, re.I) for v in leading))
        expected: Counter = Counter()
        source_rows = []
        for tr in rows:
            cells = [c for c in tr.find_all(["td", "th"], recursive=False) if id(c) not in hid]
            texts = [cell_text(c, hid) for c in cells]
            own = tr.find_parent("table") is table
            row_index = own_rows.index(tr) if own else -1
            row_role = "header" if own and row_index < header_rows else (None if own else "nested")
            label_index = next((i for i, (v, _) in enumerate(texts) if v and v not in {"$", "€", "£"}), None)
            values = merge_split_negatives([v for v, _ in texts])
            signature_row = any(SIGNATURE_ROW_MARK.search(v) for v in values)
            row_tokens = []
            for position, text in enumerate(values):
                role = row_role or ("label" if position == 0 and label_index is not None else "body")
                for token, kind in classify_cell(text, signature_row):
                    if exhibit_index:
                        kind = "reference"
                    expected[(token, kind, role)] += 1
                    row_tokens.append(token)
            for _, marks in texts:
                for token in numbers(marks.replace("(", " (").replace(")", ") ")):
                    expected[(token, "marker", row_role or "body")] += 1
            if own and len(row_tokens) >= 2 and is_data_row(values, row_index < header_rows):
                source_rows.append(tuple(row_tokens))
        if expected:
            res.has_numbers = True
        segment = _MARKDOWN_LINK_RE.sub(lambda m: m.group(1), segments.get(id(table), ""))
        value_missing, reported_missing = allocate(expected, output_occurrences(segment, exhibit_index))
        for token, role, ambiguous in value_missing:
            res.missing[role] += 1
            res.missing_tokens.append((token, role) + (("ambiguous",) if ambiguous else ()))
            if ambiguous:
                res.ambiguous += 1
        for token, kind in reported_missing:
            res.reported[kind] += 1
        # Check 2 over body lines only (header lines may be legitimately fused).
        lines = segment.split("\n")
        separator = next((i for i, line in enumerate(lines) if is_separator_row(line)), None)
        if separator is not None:
            body = [output_numbers(line) for line in lines[separator + 1:]]
            body_all = Counter(t for line in body for t in line)
            pointer = 0
            for row_number, row in enumerate(source_rows, 1):
                need = Counter(row)
                hit = next((k for k in range(pointer, len(body)) if not need - Counter(body[k])), None)
                if hit is not None:
                    left, projected = Counter(need), []
                    for token in body[hit]:
                        if left[token]:
                            projected.append(token)
                            left[token] -= 1
                    if tuple(projected) != row:
                        res.order.append(f"source row {row_number}: values out of order within the row")
                    pointer = hit
                elif any(not need - Counter(body[k]) for k in range(pointer)):
                    res.order.append(f"source row {row_number}: appears before an earlier source row (rows out of order)")
                elif not need - body_all:
                    res.order.append(f"source row {row_number}: values present but split across output rows")
        results.append(res)
    return results


def summarize(results) -> Counter:
    s: Counter = Counter()
    for r in results:
        s["tables"] += 1
        s["tables_with_numbers"] += r.has_numbers
        if r.missing:
            s["flagged"] += 1
        for role, n in r.missing.items():
            s[f"missing_{role}"] += n
        s["missing_ambiguous"] += r.ambiguous
        for cls, n in r.reported.items():
            s[f"reported_{cls}"] += n
        if r.order:
            s["order_tables"] += 1
            for finding in r.order:
                kind = ("within_row" if "within" in finding else "rows_out_of_order" if "out of order)" in finding
                        else "split_across_rows")
                s[f"order_{kind}"] += 1
    return s
