"""Deterministic, offline quality measurements for SEC parser output."""

from __future__ import annotations

import hashlib
import json
import re
import warnings
from collections import Counter
from dataclasses import dataclass
from typing import Literal, Sequence

from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning

from sec2md.encoding import decode_html, normalize_legacy_characters
from sec2md.element_builder import _extract_xbrl_tags
from sec2md.models import Page
from sec2md.parser import Parser
from sec2md.quality import _is_hidden_tag, trace_numeric_failures
from sec2md.sections import extract_sections

from .fixtures import FixtureContract


WORD_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)
NUMBER_RE = re.compile(
    r"(?<!\w)(?:[$€£]\s*)?(?:\(?[−–-]?\d[\d,]*(?:\.\d+)?\)?%?)(?!\w)"
)
_C1_RE = re.compile(r"[\x80-\x9f]")


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


def _visible_text(soup: BeautifulSoup) -> str:
    """Extract visible text while excluding style/script and hidden subtrees."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        clone = BeautifulSoup(str(soup), "lxml")
    for tag in clone.find_all(["script", "style", "template"]):
        tag.decompose()
    for tag in list(clone.find_all(True)):
        if _is_hidden_tag(tag) and tag.parent is not None:
            tag.decompose()
    return clone.get_text(" ", strip=True)


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


def _normalized_label(label: str) -> str:
    return _normalized_row_label(label)


def _financial_row_recall(
    source: Sequence[tuple[str, tuple[str, ...]]],
    actual: Sequence[tuple[str, tuple[str, ...]]],
) -> float:
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
    return len(expected & available) / len(expected)


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
    pages: Sequence[Page], annotated_html: str
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
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
            failures.extend(trace_numeric_failures(element, nodes))
            element_tags = set(element.tags or [])
            visible_tags = set(_extract_xbrl_tags(nodes) or ())
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


def _parse_once(source: bytes) -> tuple[str, bytes, str, list[Page]]:
    text, _ = decode_html(source)
    text = normalize_legacy_characters(text)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        parser = Parser(text)
        pages = parser.get_pages(include_elements=True)
        annotated_html = parser.html()
    markdown = "\n\n".join(page.content for page in pages if page.content)
    return markdown, canonical_pages(pages), annotated_html, pages


def audit_document(
    source: bytes,
    contract: FixtureContract,
    *,
    quality_policy: Literal["strict", "warn", "off"] = "off",
) -> AccuracyResult:
    """Run two identical offline parses and return deterministic accuracy metrics."""

    if quality_policy not in {"strict", "warn", "off"}:
        raise ValueError(f"unknown quality policy: {quality_policy}")
    first = _parse_once(source)
    second = _parse_once(source)
    markdown, pages_bytes, annotated_html, pages = first
    markdown_2, pages_bytes_2, annotated_html_2, _ = second
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        source_text, _ = decode_html(source)
        source_soup = BeautifulSoup(normalize_legacy_characters(source_text), "lxml")
    source_visible = _visible_text(source_soup)
    output_visible = BeautifulSoup(markdown, "lxml").get_text(" ", strip=True)

    element_ids = _element_ids(pages)
    counts = Counter(element_ids)
    duplicates = tuple(sorted(element_id for element_id, count in counts.items() if count > 1))
    missing, trace_failures, invalid_tags = _mapping_and_trace(pages, annotated_html)
    expected_sections = _section_keys(pages, contract.form)
    exhibit_link_count = len(re.findall(r"\[[^\]]+\]\([^)]*\)", markdown))
    output_rows = extract_financial_rows(markdown)
    return AccuracyResult(
        markdown_sha256=sha256_bytes(markdown),
        pages_sha256=sha256_bytes(pages_bytes),
        annotated_html_sha256=sha256_bytes(annotated_html),
        word_recall=multiset_recall(normalize_words(source_visible), normalize_words(output_visible)),
        numeric_recall=multiset_recall(normalize_numbers(source_visible), normalize_numbers(markdown)),
        financial_row_recall=_financial_row_recall(
            extract_financial_rows(source), extract_financial_rows(markdown)
        ),
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
