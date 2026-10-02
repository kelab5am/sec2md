"""Prototype of the revised table completeness checks (spec revision 2).

Implements exactly the revised spec definitions:
- unit: each visible outermost <table>; nested tables belong to it; ordinal over all such tables,
  with the TableSnapshot ordinal reported separately when one exists
- source text: DOM-aware (inline pieces concatenated, block boundaries spaced), hidden descendants
  excluded, footnote markers separated; $, EUR and GBP symbols normalized
- output: the exact string the parser emitted for that table in the page stream (exclusive segment)
- classes: marker / reference (reported only) vs value (enforced), value broken down by row role
- check 2: snapshot header rows excluded via xlsx_tables._header_count, compared row by row
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
# A hyphen or en dash between two numbers is a range separator, not a minus sign.
RANGE_DASH = re.compile(r"(?<=[\d%])\s*[-–]\s*(?=[$(]?\d)")
# A bare digit in a fragment link is not enough: NVDA splits dates across such links.
MARKER_TEXT = re.compile(r"\(\*?\d{1,2}\)|\*+|\[\d{1,2}\]")
REFERENCE_CELL = re.compile(r"^\s*(?:item|note|exhibit|part|schedule)\s+[\dA-Z]|^\s*dated?\s*:", re.I)
CURRENCY = str.maketrans({"€": "$", "£": "$"})


def numbers(text: str) -> list[str]:
    return list(_normalized_numbers(RANGE_DASH.sub(" - ", text.translate(CURRENCY))))


def output_numbers(line: str) -> list[str]:
    """Tokens of one output line, cell by cell, so no rule spans a column boundary."""
    return [token for cell in line.split("|") for token in numbers(cell)]


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
        if id(child) in hid or child.name == "table":  # nested tables are counted via their own rows
            continue
        child_marker = marker or is_marker(child)
        separate = child.name in BLOCK or child_marker != marker
        if separate:
            out.append((" ", marker))
        _walk(child, hid, out, child_marker)
        if separate:
            out.append((" ", marker))


def cell_text(cell, hid) -> tuple[str, str]:
    """Visible value text and footnote-marker text of one cell."""
    pieces: list = []
    _walk(cell, hid, pieces, False)
    value = re.sub(r"\s+", " ", "".join(" " if m else t for t, m in pieces)).strip()
    marks = re.sub(r"\s+", " ", " ".join(t for t, m in pieces if m)).strip()
    return value, marks


@dataclass
class TableResult:
    ordinal: int
    snapshot_ordinal: int | None
    missing: Counter = field(default_factory=Counter)   # enforced value tokens, by row role
    reported: Counter = field(default_factory=Counter)  # marker / reference tokens
    order: str | None = None
    has_numbers: bool = False
    missing_tokens: list = field(default_factory=list)


def _snapshot_header_rows(snap) -> int:
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


def analyze(html, mutate=None) -> list[TableResult]:
    parser = Parser(html, capture_tables=True)
    segments: dict[int, str] = {}
    original = parser._process_element

    def recording(element):
        out = original(element)
        if isinstance(element, Tag) and element.name == "table" and element.find_parent("table") is None:
            segments[id(element)] = mutate(out) if mutate else out
        return out

    parser._process_element = recording
    parser.get_pages(include_images=False)
    snapshots = {id(nodes[0]): snap for snap, nodes in zip(parser.table_snapshots, parser._snapshot_nodes)
                 if len(nodes) == 1}
    hid = hidden_ids(parser.soup)
    tables = [t for t in parser.soup.find_all("table") if id(t) not in hid and t.find_parent("table") is None]
    results = []
    for ordinal, table in enumerate(tables, 1):
        snap = snapshots.get(id(table))
        res = TableResult(ordinal, snap.ordinal if snap else None)
        rows = [tr for tr in table.find_all("tr") if id(tr) not in hid]
        own_rows = [tr for tr in rows if tr.find_parent("table") is table]
        header_rows = _snapshot_header_rows(snap)
        leading_text = " ".join(cell_text(c, hid)[0] for tr in own_rows[:3]
                                for c in tr.find_all(["td", "th"], recursive=False))
        reference_table = bool(re.search(r"\bexhibit\b", leading_text, re.I))
        expected: Counter = Counter()
        source_data_rows = []
        for tr in rows:
            cells = [c for c in tr.find_all(["td", "th"], recursive=False) if id(c) not in hid]
            texts = [cell_text(c, hid) for c in cells]
            label_index = next((i for i, (v, _) in enumerate(texts) if v and v not in {"$", "€", "£"}), None)
            reference_row = reference_table or any(REFERENCE_CELL.search(v) or "/s/" in v for v, _ in texts)
            own = tr.find_parent("table") is table
            row_index = own_rows.index(tr) if own else -1
            row_role = "header" if own and row_index < header_rows else (None if own else "nested")
            row_tokens, row_markers = [], []
            for i, (value, marks) in enumerate(texts):
                role = row_role or ("label" if i == label_index else "body")
                for token in numbers(value):
                    expected[(token, "reference" if reference_row else "value", role)] += 1
                    row_tokens.append(token)
                for token in numbers(marks.replace("(", " (").replace(")", ") ")):
                    expected[(token, "marker", role)] += 1
                    row_markers.append(token)
            if len(row_tokens) >= 2:
                source_data_rows.append(tuple(row_tokens))
        # Link destinations are not visible text; their digits must not supply missing values.
        segment = _MARKDOWN_LINK_RE.sub(lambda m: m.group(1), segments.get(id(table), ""))
        if expected:
            res.has_numbers = True
        available = Counter(t for line in segment.split("\n") for t in output_numbers(line))
        # Enforced value tokens claim output tokens first, then reported classes.
        for (token, cls, role), count in sorted(expected.items(), key=lambda kv: kv[0][1] != "value"):
            take = min(count, available[token])
            available[token] -= take
            if count - take:
                if cls == "value":
                    res.missing[role] += count - take
                    res.missing_tokens.append((token, role))
                else:
                    res.reported[cls] += count - take
        # Check 2: each source row with two or more values must appear, in the same
        # left-to-right order, within one output line. Matching is monotonic through
        # the output; other tokens on that line (markers, fused header text) are ignored.
        # Only body lines (after the Markdown separator) take part: header fusion
        # legitimately reorders header tokens. Text-rendered tables are not checked.
        seg_lines = segment.split("\n")
        separator = next((i for i, line in enumerate(seg_lines) if is_separator_row(line)), None)
        out_lines = [output_numbers(line) for line in seg_lines[separator + 1:]] if separator is not None else []
        pointer = 0
        for row_number, values in enumerate(source_data_rows, 1):
            need = Counter(values)
            hit = next((k for k in range(pointer, len(out_lines)) if not need - Counter(out_lines[k])), None)
            if hit is None:
                continue  # values missing: check 1 reports them
            left, projected = Counter(need), []
            for token in out_lines[hit]:
                if left[token]:
                    projected.append(token)
                    left[token] -= 1
            if tuple(projected) != values and res.order is None:
                res.order = f"row order differs at source row {row_number}"
            pointer = hit
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
        for cls, n in r.reported.items():
            s[f"reported_{cls}"] += n
        if r.order:
            s["order_differs" if "differs" in r.order else "order_extra_rows"] += 1
    return s
