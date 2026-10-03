"""Source-to-output completeness checks for tables.

Implements docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md
(revision 6). Each visible outermost source table is compared with the exact text the
parser emitted for it. Check 1 reports source numbers missing from that text; check 2
reports rows and values that changed order. Nothing here changes rendering.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

from bs4 import NavigableString, Tag
from bs4.element import Comment, Declaration, Doctype, ProcessingInstruction

from sec2md.chunker.blocks import is_separator_row
from sec2md.quality import _MARKDOWN_LINK_RE, _is_hidden_tag, _normalized_numbers
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
        body.append((label_key(cells[0]) if cells else "", found))
    return body, other
