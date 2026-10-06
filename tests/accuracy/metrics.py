"""Deterministic, offline quality measurements for SEC parser output."""

from __future__ import annotations

import hashlib
import json
import re
import warnings
from collections import Counter
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
from bs4.element import NavigableString, Tag

from sec2md.encoding import decode_html, normalize_legacy_characters
from sec2md.models import Page
from sec2md.parser import Parser
from sec2md.quality import ParseDiagnostics, enforce_quality
from sec2md.sections import extract_sections
from sec2md.table_parser import render_cell_content

from .fixtures import FixtureContract


WORD_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)
NUMBER_RE = re.compile(
    r"(?<!\w)(?:[$€£]\s*)?(?:\(?[−–-]?\d[\d,]*(?:\.\d+)?\)?%?)(?!\w)"
)
_C1_RE = re.compile(r"[\x80-\x9f]")
_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MARKDOWN_ANY_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_ESCAPE_RE = re.compile(r"\\(.)")
_MARKDOWN_EMPHASIS_RE = re.compile(r"[*_~`]")
_ORACLE_HIDDEN_STYLE_RE = re.compile(
    r"(?:^|;)\s*(?:display\s*:\s*none\b|visibility\s*:\s*hidden\b)",
    re.IGNORECASE,
)
_ORACLE_XBRL_FACT_TAGS = frozenset(
    {"ix:nonfraction", "nonfraction", "ix:nonnumeric", "nonnumeric"}
)


@dataclass(frozen=True)
class AccuracyResult:
    """Immutable measurements from one deterministic two-run document audit."""

    markdown_sha256: str
    pages_sha256: str
    annotated_html_sha256: str
    word_recall: float
    numeric_recall: float
    financial_row_recall: float
    table_width_errors: tuple[str, ...]
    replacement_characters: int
    c1_control_characters: int
    duplicate_element_ids: tuple[str, ...]
    missing_mappings: tuple[str, ...]
    trace_failures: tuple[str, ...]
    expected_sections: tuple[str, ...]
    invalid_visible_node_xbrl_tags: tuple[str, ...]
    representative_row_failures: tuple[str, ...] = ()
    deterministic_markdown: bool = True
    deterministic_pages: bool = True
    deterministic_annotated_html: bool = True
    exhibit_link_count: int = 0

    @property
    def markdown_hash(self) -> str:
        """Compatibility alias for consumers that call hashes simply ``*_hash``."""

        return self.markdown_sha256

    @property
    def pages_hash(self) -> str:
        return self.pages_sha256

    @property
    def annotated_html_hash(self) -> str:
        return self.annotated_html_sha256

    @property
    def duplicate_ids(self) -> tuple[str, ...]:
        return self.duplicate_element_ids

    @property
    def missing_element_mappings(self) -> tuple[str, ...]:
        return self.missing_mappings

    @property
    def trace_numeric_failures(self) -> tuple[str, ...]:
        return self.trace_failures

    @property
    def inconsistent_table_widths(self) -> tuple[str, ...]:
        return self.table_width_errors

    @property
    def invalid_xbrl_tags(self) -> tuple[str, ...]:
        return self.invalid_visible_node_xbrl_tags

    @property
    def sections(self) -> tuple[str, ...]:
        return self.expected_sections


def normalize_words(text: str) -> list[str]:
    """Return case-folded Unicode word tokens in source order."""

    return [match.group(0).casefold() for match in WORD_RE.finditer(text)]


def _normalize_number(match: str) -> str:
    token = match.strip()
    token = token.replace("$", "").replace("€", "").replace("£", "").strip()
    negative = token.startswith("(")
    if token.startswith("("):
        token = token[1:]
    if token.endswith(")"):
        token = token[:-1]
    token = token.replace("−", "-").replace("–", "-")
    token = token.replace(",", "").replace(" ", "")
    if token.endswith("%"):
        token = token[:-1]
    if negative and not token.startswith("-"):
        token = "-" + token
    return token


def normalize_numbers(text: str) -> list[str]:
    """Return normalized numeric tokens, omitting standalone dash markers."""

    # SEC tables frequently place presentation whitespace just inside accounting
    # parentheses (``$ (16,173)``). Collapse only that formatting whitespace so
    # the concrete token grammar can preserve the negative sign.
    compact = re.sub(r"([($€£])\s+(?=[(\d])", r"\1", text)
    compact = re.sub(r"\s+\)", ")", compact)
    return [_normalize_number(match.group(0)) for match in NUMBER_RE.finditer(compact)]


def multiset_recall(expected: Sequence[str], actual: Sequence[str]) -> float:
    """Measure how much of an expected token multiset appears in actual output."""

    expected_counts = Counter(expected)
    if not expected_counts:
        return 1.0
    actual_counts = Counter(actual)
    matched = sum(
        min(count, actual_counts[value]) for value, count in expected_counts.items()
    )
    return matched / sum(expected_counts.values())


def canonical_pages(pages: Sequence[Page]) -> bytes:
    """Serialize pages canonically for a stable byte-level comparison/hash."""

    payload = [page.model_dump(mode="json") for page in pages]
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def sha256_bytes(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _oracle_is_hidden_tag(tag: Tag) -> bool:
    attrs = tag.attrs or {}
    if "hidden" in attrs:
        return True
    if str(attrs.get("aria-hidden", "")).casefold() == "true":
        return True
    style = attrs.get("style", "")
    if isinstance(style, list):
        style = " ".join(style)
    if _ORACLE_HIDDEN_STYLE_RE.search(str(style)):
        return True
    name = str(getattr(tag, "name", "")).casefold()
    return name in {"ix:hidden", "hidden"} or name.endswith(":hidden")


def _oracle_is_hidden_or_under_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while isinstance(current, Tag):
        if _oracle_is_hidden_tag(current):
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _oracle_visible_xbrl_tags(nodes: Sequence[Tag]) -> tuple[str, ...]:
    """Extract visible mapped-node concepts without using production helpers."""

    tags: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, Tag) or _oracle_is_hidden_or_under_hidden(node):
            continue
        candidates = [node, *node.find_all(_ORACLE_XBRL_FACT_TAGS)]
        for candidate in candidates:
            if not isinstance(candidate, Tag):
                continue
            if candidate.name not in _ORACLE_XBRL_FACT_TAGS:
                continue
            if _oracle_is_hidden_or_under_hidden(candidate):
                continue
            concept = candidate.get("name", "")
            if concept and concept not in seen:
                seen.add(concept)
                tags.append(concept)
    return tuple(tags)


def _oracle_whole_line_starts(content: str, segment: str) -> list[int]:
    """Offsets where segment occupies whole lines of content."""

    starts: list[int] = []
    start = content.find(segment) if segment else -1
    while start != -1:
        end = start + len(segment)
        if (start == 0 or content[start - 1] == "\n") and (end == len(content) or content[end] == "\n"):
            starts.append(start)
        start = content.find(segment, start + 1)
    return starts


def _oracle_header_line_spans(content: str, records: Sequence) -> list[tuple[int, int] | None]:
    """Locate each record's header line in element content, independently of production.

    A header line is located only as the first line of its own table segment: the segment
    must occupy whole lines exactly once and start with the recorded header line. A line
    two records would claim is located for neither, so each is consumed once (spec R6a).
    """

    spans: list[tuple[int, int] | None] = []
    for record in records:
        starts = _oracle_whole_line_starts(content, record.segment)
        first_line = record.segment.split("\n", 1)[0]
        located = len(starts) == 1 and first_line == record.header_line
        spans.append((starts[0], starts[0] + len(first_line)) if located else None)
    claimed = Counter(span for span in spans if span is not None)
    return [span if span is not None and claimed[span] == 1 else None for span in spans]


def _oracle_header_tokens(record) -> tuple[Counter, Counter]:
    """A table's header source and capacity, tokenized with the harness normalizer.

    The source joins the header-zone cell texts with single spaces, as the mapped-node
    pool is joined, and tokenizes them once; the capacity counts each cell's tokens once
    per output column whose header the cell covers.
    """

    source = Counter(normalize_numbers(" ".join(text for text, _ in record.header_cells)))
    capacity: Counter = Counter()
    for text, columns in record.header_cells:
        for token, count in Counter(normalize_numbers(text)).items():
            capacity[token] += count * columns
    return source, capacity


def _oracle_trace_numeric_failures(
    element, nodes: Sequence[Tag], header_records: Sequence = ()
) -> tuple[str, ...]:
    """Compare numeric multisets using only the accuracy harness normalizer.

    With the element's table header records, R6a's header accounting applies, tokenized
    with this harness's normalizer rather than strict's. Each located header line is
    checked on its own against its table's header capacity, an excess failing as
    ``<element id>:header:<token>``. Located lines then leave the output pool, and their
    tables' header-zone tokens leave the source pool. A record whose header line is not
    located grants no exemption and subtracts nothing.
    """

    content = element.content
    header_failures: list[str] = []
    header_source: Counter = Counter()
    spans = _oracle_header_line_spans(content, header_records) if header_records else []
    located = [(record, span) for record, span in zip(header_records, spans) if span is not None]
    for record, (start, end) in located:
        source, capacity = _oracle_header_tokens(record)
        for token, count in sorted(Counter(normalize_numbers(content[start:end])).items()):
            header_failures.extend(
                f"{element.id}:header:{token}" for _ in range(max(0, count - capacity[token]))
            )
        header_source += source
    for _, (start, end) in sorted(located, key=lambda item: item[1], reverse=True):
        content = content[:start] + content[end:]

    expected = Counter(normalize_numbers(re.sub(r"!\[[^\]]*\]\([^)]*\)", "", content)))
    available = Counter(
        normalize_numbers(
            " ".join(node.get_text(" ", strip=True) for node in nodes if isinstance(node, Tag))
        )
    ) - header_source
    failures: list[str] = []
    for token, count in sorted(expected.items()):
        failures.extend(
            f"{element.id}:{token}" for _ in range(max(0, count - available[token]))
        )
    return tuple(header_failures + failures)


_ORACLE_PAGE_BREAK_RE = re.compile(
    r"(?:^|;)\s*(?:page-)?break-(before|after)\s*:\s*(?:always|page)\b", re.IGNORECASE
)
_ORACLE_BLOCK_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "body", "br", "caption", "center", "dd",
    "div", "dl", "dt", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "header", "hr", "html", "li", "main", "nav", "ol", "p", "pre", "section", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
})
_ORACLE_INLINE_TAGS = frozenset({
    "a", "abbr", "b", "big", "cite", "code", "em", "font", "i", "small", "span", "strong",
    "sub", "sup", "u",
})
_ORACLE_RUNNING_LINE_RE = re.compile(r"(?:(.*\S)\s+)?(\d{1,4})")
_ORACLE_RENDERED_EMPTY_TAGS = frozenset({"hr", "img"})


def _oracle_page_ends(soup: BeautifulSoup, visible: Sequence[NavigableString]) -> list:
    """The last visible string of each page, one entry per page, in document order.

    A page ends at a break point: before an element whose inline style sets
    ``page-break-before: always``/``break-before: page``, after one whose style sets
    ``page-break-after: always``/``break-after: page``, and at the end of the document. A break
    point is a position among the document's rendered leaves (its visible strings and its
    ``hr``/``img`` elements) in document order, and break points at one position are one
    physical break (an after-break rule followed directly by a before-break page). A page
    whose leaves hold no visible string (a blank page with only a rule) repeats the previous
    page's last string, so a page's index here is its ordinal.
    """

    visible_ids = {id(node) for node in visible}

    def is_leaf(node) -> bool:
        if isinstance(node, Tag):
            return node.name in _ORACLE_RENDERED_EMPTY_TAGS
        return id(node) in visible_ids

    leaves_before: dict[int, int] = {}
    last_string_after: list[NavigableString | None] = []
    last: NavigableString | None = None
    for node in soup.descendants:
        if isinstance(node, Tag):
            leaves_before[id(node)] = len(last_string_after)
        if is_leaf(node):
            if not isinstance(node, Tag):
                last = node
            last_string_after.append(last)
    positions = {len(last_string_after)}
    for tag in soup.find_all(style=_ORACLE_PAGE_BREAK_RE):
        side = _ORACLE_PAGE_BREAK_RE.search(str(tag["style"])).group(1).casefold()
        position = leaves_before[id(tag)]
        if side == "after":
            position += is_leaf(tag) + sum(1 for node in tag.descendants if is_leaf(node))
        positions.add(position)
    return [
        last_string_after[position - 1]
        for position in sorted(positions)
        if position and last_string_after[position - 1] is not None
    ]


def _oracle_is_block(tag: Tag) -> bool:
    return tag.name in _ORACLE_BLOCK_TAGS


def _oracle_is_xbrl(tag: Tag) -> bool:
    return tag.name.startswith("ix:")


def _oracle_closing_block(node: NavigableString) -> Tag | None:
    """The block that closes a page: the nearest block element around its last string, when that
    block is outside any table, holds no other block (it is one line) and holds no inline XBRL
    element (a tagged fact is content)."""

    block = node.parent
    while isinstance(block, Tag) and block.name not in _ORACLE_BLOCK_TAGS:
        block = block.parent
    if not isinstance(block, Tag) or block.name in {"body", "html"} or block.name in {
        "caption", "table", "tbody", "td", "tfoot", "th", "thead", "tr"
    }:
        return None
    if block.find_parent("table") is not None or block.find(_oracle_is_block) is not None:
        return None
    if block.find(_oracle_is_xbrl) is not None:
        return None
    return block


def _oracle_page_footers(soup: BeautifulSoup) -> list[Tag]:
    """Page footers by the harness's own rule (recall audit 2026-10-06), not the parser's.

    A page's closing block (``_oracle_closing_block`` of its last visible string, see
    ``_oracle_page_ends``) is a footer candidate when its whole text, whitespace collapsed, is a
    page number of 1-4 digits, alone or after running text and whitespace: "Apple Inc. | 2023
    Form 10-K | 23" (running text "Apple Inc. | 2023 Form 10-K |"), "47" (no running text), but
    never the tail of a longer number ("Total 1,100", "Rate 1.5", "12345"). Candidates with the
    same running text are page footers when they close at least two pages and at least half of
    the document's pages, and their page numbers advance with the pages: page number minus
    page-end ordinal (from zero, see ``_oracle_page_ends``) is one constant, so pages without a
    footer are tolerated but skipped or unrelated numbers are not, and that constant is smaller
    in magnitude than the number of page ends, so the numbers fall within the document's own
    pages (the fixtures' offsets are -1 and +1) and a year series such as "Fiscal 2024 / 2025 /
    2026" closing consecutive pages is never a footer. Anything else at a page end,
    such as a table's last cell, a tagged XBRL fact or a paragraph ending in a number, is
    content and stays counted.
    """

    visible = [node for node in soup.strings if node.strip()]
    ends = _oracle_page_ends(soup, visible)
    groups: dict[str, list[tuple[int, Tag]]] = {}
    seen: set[int] = set()
    for ordinal, node in enumerate(ends):
        block = _oracle_closing_block(node)
        if block is None or id(block) in seen:
            continue
        seen.add(id(block))
        line = _SPACE_RE.sub(" ", block.get_text(" ", strip=True))
        if match := _ORACLE_RUNNING_LINE_RE.fullmatch(line):
            groups.setdefault(match.group(1) or "", []).append((int(match.group(2)) - ordinal, block))
    footers: list[Tag] = []
    for candidates in groups.values():
        offsets = {offset for offset, _ in candidates}
        if (len(candidates) >= 2 and 2 * len(candidates) >= len(ends) and len(offsets) == 1
                and abs(next(iter(offsets))) < len(ends)):
            footers.extend(block for _, block in candidates)
    return footers


def _oracle_splits_a_number(left: str, right: str) -> bool:
    """Whether two touching strings are fragments of one number: digits meet digits, or a
    decimal or thousands separator between digits."""

    return bool(
        (re.search(r"\d\Z", left) and re.match(r"[.,]?\d", right))
        or (re.search(r"\d[.,]\Z", left) and re.match(r"\d", right))
    )


def _oracle_same_target_split(left: NavigableString, right: NavigableString) -> bool:
    """Whether a number is split across consecutive links to one target (nvda-2026-10k's
    ``<a href="#x">January 2</a><a href="#x">5</a>``), which a reader sees as one number.

    The raw strings must be number fragments that touch: nothing lies between them but the
    opening tags of the right string's own ancestors (no whitespace, comment or other element),
    every element they close or open on the way is inline, and their nearest ``a`` ancestors
    are two elements with one non-empty href. Any other boundary keeps its space: an untagged
    ``3.5%-``/``4.3%`` junction never reads as -4.3.
    """

    if not _oracle_splits_a_number(left, right):
        return False
    first, second = left.find_parent("a"), right.find_parent("a")
    if first is None or second is None or first is second:
        return False
    if not first.get("href") or first.get("href") != second.get("href"):
        return False
    left_ancestors = {id(tag) for tag in left.parents}
    right_ancestors = {id(tag) for tag in right.parents}
    node = left.next_element
    while node is not right:
        if node is None or id(node) not in right_ancestors:
            return False
        node = node.next_element
    for start, other in ((left, right_ancestors), (right, left_ancestors)):
        for tag in start.parents:
            if id(tag) in other:
                break
            if tag.name not in _ORACLE_INLINE_TAGS:
                return False
    return True


def _visible_text(soup: BeautifulSoup) -> str:
    """The source's visible text, as a reader sees the pages (see ``_source_visible``)."""

    return _source_visible(soup)[0]


def _source_visible(soup: BeautifulSoup) -> tuple[str, Counter]:
    """The source's visible text, as a reader sees the pages, and the page-footer lines left out
    of it (their whitespace-collapsed texts, counted).

    Left out: style/script/template, hidden subtrees, the ``<head>`` (its ``<title>`` is the
    file name, which no browser draws on the page) and page footers by the harness's own rule
    (``_oracle_page_footers``). Strings are joined with one space, as ``get_text(" ",
    strip=True)`` joins them, except a number split across consecutive links to one target,
    joined as it reads (``_oracle_same_target_split``).
    """

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        clone = BeautifulSoup(str(soup), "lxml")
    for tag in clone.find_all("head"):
        tag.decompose()
    for tag in clone.find_all(["script", "style", "template"]):
        tag.decompose()
    for tag in list(clone.find_all(True)):
        if _oracle_is_hidden_tag(tag) and tag.parent is not None:
            tag.decompose()
    footers = _oracle_page_footers(clone)
    footer_lines = Counter(_SPACE_RE.sub(" ", block.get_text(" ", strip=True)) for block in footers)
    for block in footers:
        block.decompose()
    parts: list[str] = []
    previous: NavigableString | None = None
    for node in clone.strings:
        text = node.strip()
        if not text:
            continue
        if previous is not None:
            parts.append("" if _oracle_same_target_split(previous, node) else " ")
        parts.append(text)
        previous = node
    return "".join(parts), footer_lines


def _cell_text(cell) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def _has_label_text(text: str) -> bool:
    """Return whether a cell contains at least one Unicode letter."""

    return bool(re.search(r"[^\W\d_]", text, re.UNICODE))


def _normalized_row_label(label: str) -> str:
    """Normalize a financial-row label without discarding its content."""

    return re.sub(r"\s+", " ", label).strip()


def _label_words(label: str) -> list[str]:
    """Count alphabetic words only for deciding whether a row is eligible."""

    return re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", label, re.UNICODE)


def _row_key(cells: Sequence[str]) -> tuple[str, tuple[str, ...]] | None:
    label = next((cell for cell in cells if _has_label_text(cell)), "")
    numbers = tuple(normalize_numbers(" | ".join(cells)))
    if len(_label_words(label)) < 2 or len(numbers) < 2:
        return None
    return (_normalized_row_label(label), numbers)


def _canonical_row(row: tuple[str, tuple[str, ...]]) -> tuple[str, tuple[str, ...]] | None:
    label, numbers = row
    if len(_label_words(label)) < 2 or len(numbers) < 2:
        return None
    return (_normalized_row_label(label), numbers)


def _html_rows(text: str | bytes) -> list[tuple[str, tuple[str, ...]]]:
    if isinstance(text, bytes):
        decoded, _ = decode_html(text)
        text = normalize_legacy_characters(decoded)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(text, "lxml")
    result: list[tuple[str, tuple[str, ...]]] = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            values = [_cell_text(cell) for cell in cells]
            numbers = tuple(normalize_numbers(" | ".join(values)))
            label = next((value for value in values if _has_label_text(value)), "")
            if numbers:
                result.append((label, numbers))
    return result


def _markdown_cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith(">"):
        line = line[1:].lstrip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if char == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    cells.append("".join(current).strip())
    return cells


def _is_delimiter_row(cells: Sequence[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _markdown_rows(markdown: str) -> list[tuple[str, tuple[str, ...]]]:
    result: list[tuple[str, tuple[str, ...]]] = []
    lines = markdown.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") and not stripped.startswith("> |"):
            continue
        cells = _markdown_cells(line)
        if len(cells) < 2 or _is_delimiter_row(cells):
            continue
        numbers = tuple(normalize_numbers(" | ".join(cells)))
        label = next((cell for cell in cells if _has_label_text(cell)), "")
        if numbers and label:
            result.append((label, numbers))
    return result


def extract_financial_rows(text: str | bytes) -> list[tuple[str, tuple[str, ...]]]:
    """Extract normalized numeric rows from HTML tables or Markdown tables."""

    if isinstance(text, bytes) or "<table" in text.lower():
        return _html_rows(text)
    return _markdown_rows(text)


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") or stripped.startswith("> |")


def _header_line_indexes(lines: Sequence[str]) -> set[int]:
    """Indexes of Markdown table header lines: a table line right before a delimiter row."""

    return {
        index
        for index, (line, following) in enumerate(zip(lines, lines[1:]))
        if _is_table_line(line)
        and not _is_delimiter_row(_markdown_cells(line))
        and _is_table_line(following)
        and _is_delimiter_row(_markdown_cells(following))
    }


def extract_header_lines(markdown: str) -> list[tuple[str, tuple[str, ...]]]:
    """Each Markdown table header line as (its cells' text, its normalized numbers).

    The text is the cells joined with `` | ``, whitespace collapsed, so a source row's
    label can be looked up in it; the numbers are the line's normalized numeric tokens.
    """

    lines = markdown.splitlines()
    result: list[tuple[str, tuple[str, ...]]] = []
    for index in sorted(_header_line_indexes(lines)):
        text = " | ".join(_markdown_cells(lines[index]))
        result.append((_normalized_row_label(text), tuple(normalize_numbers(text))))
    return result


def _body_markdown(markdown: str) -> str:
    """The Markdown without its table header lines."""

    lines = markdown.splitlines()
    header = _header_line_indexes(lines)
    return "\n".join(line for index, line in enumerate(lines) if index not in header)


def _strip_markdown_link_destinations(text: str) -> str:
    """Remove non-visible destinations while retaining rendered link labels."""

    return _MARKDOWN_LINK_RE.sub(r"\1", text)


def _output_visible_text(markdown: str, footer_lines: Mapping[str, int] | None = None) -> str:
    """The Markdown as a reader sees it, measured against ``_source_visible``.

    Each Markdown line whose visible text is a page footer the source side left out (both read
    by ``_oracle_plain_line``, so ``**2**`` is the footer ``2``) is dropped, once per such
    footer: the parser keeps some footers (nvda-2002's page numbers) as lines of their own, and
    those must not stand in for a lost body value with the same digits. Dropping output never hides a loss. Then each image (alt text and source)
    becomes a space and each link reads as its label, so digits in a URL or an alt text never
    stand in for a lost value either; the source side counts neither (it reads no attributes).
    """

    if footer_lines:
        left: Counter = Counter()
        for text, count in footer_lines.items():
            left[_oracle_plain_line(text)] += count
        kept = []
        for line in markdown.split("\n"):
            key = _oracle_plain_line(_markdown_visible(line))
            if left[key] > 0:
                left[key] -= 1
                continue
            kept.append(line)
        markdown = "\n".join(kept)
    return _markdown_visible(markdown)


def _markdown_visible(text: str) -> str:
    """Markdown with each image (alt text and source) as a space and each link as its label."""

    return _MARKDOWN_ANY_LINK_RE.sub(r"\1", _MARKDOWN_IMAGE_RE.sub(" ", text))


def _oracle_plain_line(text: str) -> str:
    """A line's text as a footer line is compared on both sides: backslash escapes resolved,
    emphasis and code marks (``*``, ``_``, ``~``, backticks) removed, whitespace collapsed. A
    page number the parser keeps as ``**2**`` or ``*2*`` is the footer line ``2``."""

    text = _MARKDOWN_EMPHASIS_RE.sub("", _MARKDOWN_ESCAPE_RE.sub(r"\1", text))
    return _SPACE_RE.sub(" ", text).strip()


def source_soup(source: bytes) -> BeautifulSoup:
    """The source document as every source-side row measurement here reads it."""

    decoded, _ = decode_html(source)
    source_text = normalize_legacy_characters(decoded)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        return BeautifulSoup(source_text, "lxml")


def _link_aware_source_rows(source: bytes) -> list[tuple[str, tuple[str, ...]]]:
    """Use DOM-aware labels only for tables with split same-destination anchors."""

    return [(label, numbers) for _, _, label, numbers in _link_aware_source_row_positions(source)]


def _link_aware_source_row_positions(
    source: bytes,
) -> list[tuple[int, int, str, tuple[str, ...]]]:
    """``_link_aware_source_rows`` with each row's position.

    A position is (index of the table among the document's ``table`` elements, index of
    the row among that table's ``tr`` elements), both from zero in document order. A
    nested table's rows appear under the outer table too, as they always have.
    """

    soup = source_soup(source)
    rows: list[tuple[int, int, str, tuple[str, ...]]] = []
    for table_index, table in enumerate(soup.find_all("table")):
        table_has_split_link = any(
            left.get("href")
            and left.get("href") == right.get("href")
            for cell in table.find_all(["td", "th"])
            for left, right in zip(cell.find_all("a"), cell.find_all("a")[1:])
        )
        for row_index, row in enumerate(table.find_all("tr")):
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            values = []
            for cell in cells:
                if table_has_split_link and cell.find("a"):
                    value = render_cell_content(cell)
                else:
                    value = re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
                values.append(_strip_markdown_link_destinations(value))

            numbers = tuple(normalize_numbers(" | ".join(values)))
            label = next(
                (value for value in values if re.search(r"[^\W\d_]", value, re.UNICODE)),
                "",
            )
            if numbers:
                rows.append((table_index, row_index, label, numbers))
    return rows


def _normalized_label(label: str) -> str:
    return _normalized_row_label(label)


def _in_header_line(
    row: tuple[str, tuple[str, ...]], header_lines: Sequence[tuple[str, tuple[str, ...]]]
) -> bool:
    """Whether one header line holds the row's label text and its numbers as a sub-multiset."""

    label, numbers = row
    need = Counter(numbers)
    return any(label in text and not need - Counter(have) for text, have in header_lines)


def _financial_row_recall(
    source: Sequence[tuple[str, tuple[str, ...]]],
    actual: Sequence[tuple[str, tuple[str, ...]]],
    header_lines: Sequence[tuple[str, tuple[str, ...]]] = (),
) -> float:
    """Share of eligible source rows (2+ label words, 2+ numbers) present in the output.

    A row is present when an output row has its exact label and numbers, or (spec
    2026-10-05: R6 fuses header rows into one header line) when one output header line
    contains its label text and its numbers as a sub-multiset.
    """

    expected = {
        key
        for row in source
        if (key := _canonical_row(row)) is not None
    }
    available = {
        key
        for row in actual
        if (key := _canonical_row(row)) is not None
    }
    if not expected:
        return 1.0
    present = expected & available
    if header_lines:
        present |= {key for key in expected - present if _in_header_line(key, header_lines)}
    return len(present) / len(expected)


@dataclass(frozen=True, order=True)
class SourceRow:
    """One source row with visible text, with its position (spec 2026-10-05 revision 11:
    the body-row guard covers every such row).

    table and row index every ``table`` element and each table's ``tr`` elements in document
    order, from zero, as ``_link_aware_source_row_positions`` does (a nested table's rows also
    appear under the outer table). cells are the row's non-empty visible cell texts.
    """

    table: int
    row: int
    cells: tuple[str, ...]

    @property
    def key(self) -> str:
        return _row_signature(self.cells)


_ZERO_WIDTH = str.maketrans(dict.fromkeys("\u200b\u200c\u200d\u2060\ufeff"))
_SPACE_RE = re.compile(r"\s+")


def _row_signature(cells: Sequence[str]) -> str:
    """A row's text with every space removed, so cell boundaries and joins do not matter:
    ``$`` + ``1,234`` and ``$ 1,234``, ``(29`` + ``)`` and ``(29)`` sign alike."""

    return _SPACE_RE.sub("", "".join(cells).translate(_ZERO_WIDTH))


def _snapshot_hidden(node: Tag) -> bool:
    """The snapshot builder's rule for a hidden element (xlsx_tables._hidden)."""

    from sec2md.xlsx_tables import _hidden

    return _hidden(node)


def _grid_hidden(node: Tag, table: Tag) -> bool:
    """Grid-hidden (spec revision 11): hidden by the snapshot rule, itself or through an
    ancestor inside the table."""

    current: Tag | None = node
    while current is not None and current is not table:
        if _snapshot_hidden(current):
            return True
        current = current.parent
    return False


def _visible_cell_text(cell: Tag) -> str:
    """A source cell's visible text: its strings joined, links read by their labels, and a
    cell holding only an image read as a bullet, as the renderer writes it."""

    text = _SPACE_RE.sub(" ", cell.get_text(" ", strip=True).translate(_ZERO_WIDTH)).strip()
    if not text and cell.find("img") is not None:
        return "\u25cf"
    return text


def text_source_rows(source: bytes) -> tuple[SourceRow, ...]:
    """Every source row with visible text, in document order (grid-hidden rows and cells left
    out)."""

    rows: list[SourceRow] = []
    for table_index, table in enumerate(source_soup(source).find_all("table")):
        for row_index, row in enumerate(table.find_all("tr")):
            if _grid_hidden(row, table):
                continue
            cells = row.find_all(["td", "th"], recursive=False) or row.find_all(["td", "th"])
            texts = tuple(
                text
                for cell in cells
                if not _grid_hidden(cell, table) and (text := _visible_cell_text(cell))
            )
            if texts:
                rows.append(SourceRow(table_index, row_index, texts))
    return tuple(rows)


def _output_cells(line: str) -> list[str]:
    """A Markdown table line's non-empty cells: link labels only, pipes unescaped."""

    cells = (cell.replace("\\|", "|") for cell in _markdown_cells(_strip_markdown_link_destinations(line)))
    return [cell for cell in cells if cell.strip()]


def body_line_counts(markdown: str) -> Counter:
    """How many table body lines of the Markdown carry each row signature (header lines and
    delimiters left out)."""

    lines = markdown.splitlines()
    header = _header_line_indexes(lines)
    return Counter(
        _row_signature(_output_cells(line))
        for index, line in enumerate(lines)
        if index not in header and _is_table_line(line) and not _is_delimiter_row(_markdown_cells(line))
    )


def body_matched_rows(source: bytes, markdown: str) -> tuple[SourceRow, ...]:
    """The source rows with visible text that output body lines render: the same text in the
    same order, spaces and cell boundaries aside. A row present only in a header line is not
    body-matched.

    Rows sharing a signature are counted, not told apart: with n source rows and m body lines
    of one signature, the first min(n, m) of those rows in document order are returned.
    """

    available = body_line_counts(markdown)
    matched: list[SourceRow] = []
    for row in text_source_rows(source):
        if available[row.key] > 0:
            available[row.key] -= 1
            matched.append(row)
    return tuple(matched)


def _in_header_line_cells(cells: Sequence[str], markdown: str) -> bool:
    """Whether one header line of the Markdown holds every cell text of a source row."""

    lines = markdown.splitlines()
    wanted = [_row_signature([cell]) for cell in cells]
    for index in _header_line_indexes(lines):
        have = _row_signature(_output_cells(lines[index]))
        if all(part in have for part in wanted):
            return True
    return False


def _representative_row_failures(
    contract: FixtureContract,
    actual: Sequence[tuple[str, tuple[str, ...]]],
) -> tuple[str, ...]:
    failures = []
    for representative in contract.representative_rows:
        expected_label = _normalized_label(representative.label)
        found = any(
            expected_label in _normalized_label(label)
            and _has_label_text(label)
            and multiset_recall(representative.numbers, numbers) == 1.0
            for label, numbers in actual
        )
        if not found:
            failures.append(representative.label)
    return tuple(failures)


def _table_width_errors(markdown: str) -> tuple[str, ...]:
    errors: list[str] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith(("|", "> |")):
            index += 1
            continue
        block: list[tuple[int, list[str]]] = []
        while index < len(lines) and lines[index].strip().startswith(("|", "> |")):
            block.append((index + 1, _markdown_cells(lines[index])))
            index += 1
        delimiter_positions = [i for i, (_, cells) in enumerate(block) if _is_delimiter_row(cells)]
        for delimiter_position in delimiter_positions:
            expected_width = len(block[delimiter_position][1])
            for position, (line_number, cells) in enumerate(block):
                if position == delimiter_position:
                    continue
                if len(cells) != expected_width:
                    errors.append(
                        f"line {line_number}: expected {expected_width} columns, got {len(cells)}"
                    )
    return tuple(errors)


def _element_ids(pages: Sequence[Page]) -> list[str]:
    return [element.id for page in pages for element in (page.elements or [])]


def _mapping_and_trace(
    pages: Sequence[Page],
    annotated_html: str,
    header_records: Mapping[str, Sequence] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Check element mappings, trace numbers and visible XBRL tags per element.

    header_records maps an element ID to its tables' header records (spec R6a); the
    numeric trace accounts for those tables' header lines.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(annotated_html, "lxml")
    mapping: dict[str, list] = {}
    for node in soup.find_all(attrs={"data-sec2md-block": True}):
        mapping.setdefault(node["data-sec2md-block"], []).append(node)

    missing: list[str] = []
    failures: list[str] = []
    invalid_tags: set[str] = set()
    for page in pages:
        for element in page.elements or []:
            nodes = mapping.get(element.id, [])
            if not nodes:
                missing.append(element.id)
                continue
            records = header_records.get(element.id, ()) if header_records else ()
            failures.extend(_oracle_trace_numeric_failures(element, nodes, records))
            element_tags = set(element.tags or [])
            visible_tags = set(_oracle_visible_xbrl_tags(nodes))
            invalid_tags.update(element_tags - visible_tags)
    return tuple(sorted(set(missing))), tuple(failures), tuple(sorted(invalid_tags))


def _section_keys(pages: Sequence[Page], form: str) -> tuple[str, ...]:
    if form not in {"10-K", "10-Q", "8-K"}:
        return ()
    sections = extract_sections(list(pages), filing_type=form)
    keys = []
    for section in sections:
        if section.item is None:
            continue
        keys.append(f"{section.part}/{section.item}" if section.part else section.item)
    return tuple(keys)


def _render(source: bytes) -> tuple[Parser, list[Page]]:
    """Parse one document, with elements, as every measurement here does."""

    text, _ = decode_html(source)
    text = normalize_legacy_characters(text)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        parser = Parser(text)
        pages = parser.get_pages(include_elements=True)
    return parser, pages


def _markdown_of(pages: Sequence[Page]) -> str:
    return "\n\n".join(page.content for page in pages if page.content)


def _parse_document(
    source: bytes,
) -> tuple[str, bytes, str, list[Page], ParseDiagnostics, dict[str, tuple]]:
    """Parse once; also return each element's table header records (spec R6a)."""

    parser, pages = _render(source)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        annotated_html = parser.html()
    if parser.diagnostics is None:
        raise RuntimeError("Parser did not provide parse diagnostics")
    header_records = {
        element.id: records
        for page in pages
        for element in page.elements or ()
        if (records := parser.element_header_records(element.id))
    }
    return (_markdown_of(pages), canonical_pages(pages), annotated_html, pages,
            parser.diagnostics, header_records)


def _parse_once(source: bytes) -> tuple[str, bytes, str, list[Page], ParseDiagnostics]:
    return _parse_document(source)[:5]


def _link_aware_financial_row_recall(source: bytes, markdown: str) -> float:
    """Compare visible source and Markdown table content without link syntax."""

    visible = _strip_markdown_link_destinations(markdown)
    return _financial_row_recall(
        _link_aware_source_rows(source),
        extract_financial_rows(visible),
        extract_header_lines(visible),
    )


def audit_document(
    source: bytes,
    contract: FixtureContract,
    *,
    quality_policy: Literal["strict", "warn", "off"] = "off",
) -> AccuracyResult:
    """Run two identical offline parses and return deterministic accuracy metrics."""

    if quality_policy not in {"strict", "warn", "off"}:
        raise ValueError(f"unknown quality policy: {quality_policy}")
    first = _parse_document(source)
    second = _parse_document(source)
    markdown, pages_bytes, annotated_html, pages, diagnostics, header_records = first
    markdown_2, pages_bytes_2, annotated_html_2, _, _, _ = second
    enforce_quality(diagnostics, quality_policy)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        source_text, _ = decode_html(source)
        source_soup = BeautifulSoup(normalize_legacy_characters(source_text), "lxml")
    source_visible, footer_lines = _source_visible(source_soup)
    output_visible = _output_visible_text(markdown, footer_lines)
    output_words = BeautifulSoup(output_visible, "lxml").get_text(" ", strip=True)

    element_ids = _element_ids(pages)
    counts = Counter(element_ids)
    duplicates = tuple(sorted(element_id for element_id, count in counts.items() if count > 1))
    missing, trace_failures, invalid_tags = _mapping_and_trace(pages, annotated_html, header_records)
    expected_sections = _section_keys(pages, contract.form)
    exhibit_link_count = len(re.findall(r"\[[^\]]+\]\([^)]*\)", markdown))
    output_rows = extract_financial_rows(markdown)
    return AccuracyResult(
        markdown_sha256=sha256_bytes(markdown),
        pages_sha256=sha256_bytes(pages_bytes),
        annotated_html_sha256=sha256_bytes(annotated_html),
        word_recall=multiset_recall(normalize_words(source_visible), normalize_words(output_words)),
        numeric_recall=multiset_recall(
            normalize_numbers(source_visible), normalize_numbers(output_visible)
        ),
        financial_row_recall=_link_aware_financial_row_recall(source, markdown),
        table_width_errors=_table_width_errors(markdown),
        replacement_characters=markdown.count("\ufffd"),
        c1_control_characters=len(_C1_RE.findall(markdown)),
        duplicate_element_ids=duplicates,
        missing_mappings=missing,
        trace_failures=trace_failures,
        expected_sections=expected_sections,
        invalid_visible_node_xbrl_tags=invalid_tags,
        representative_row_failures=_representative_row_failures(contract, output_rows),
        deterministic_markdown=markdown == markdown_2,
        deterministic_pages=pages_bytes == pages_bytes_2,
        deterministic_annotated_html=annotated_html == annotated_html_2,
        exhibit_link_count=exhibit_link_count,
    )
