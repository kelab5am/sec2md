"""Runtime diagnostics and fail-closed quality policies for parsed filings."""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Collection, Literal, Sequence

from bs4 import BeautifulSoup
from bs4.element import Tag

from sec2md.models import Element, Page

if TYPE_CHECKING:
    from sec2md.table_completeness import TableCompletenessReport


logger = logging.getLogger(__name__)

QualityPolicy = Literal["strict", "warn", "off"]

_C1_CONTROL_RE = re.compile(r"[\x80-\x9f]")
_HIDDEN_STYLE_RE = re.compile(
    r"(?:^|;)\s*(?:display\s*:\s*none\b|visibility\s*:\s*hidden\b)",
    re.IGNORECASE,
)
_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_REFERENCE_RE = re.compile(r"!?\[([^\]]+)\]\[[^\]]*\]")
_MARKDOWN_CODE_RE = re.compile(r"(`{1,3})(.*?)\1", re.DOTALL)
_TABLE_DIVIDER_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
# "1. " markers the parser generates for <ol> items; they have no source text.
_ORDERED_LIST_MARKER_RE = re.compile(r"(?m)^[ \t]*\d+\.(?=[ \t])")
_QUALITY_POLICIES = frozenset({"strict", "warn", "off"})
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_NUMBER_TOKEN_RE = re.compile(r"(?<![\w.])(?:[$€£]\s*)?\(?\s*[−–-]?\d[\d,]*(?:\.\d+)?\s*\)?%?(?!\w|\.\w)")
_CURRENCY_SYMBOLS = str.maketrans({"$": None, "\u20ac": None, "\u00a3": None})
# A number in parentheses that emphasis runs split, in the output the numeric trace reads. The
# renderer gives bold runs "(", "650", ")" as "**(** **650** **)**": the source pool reads
# "( 650 )", the accounting token -650, but the delimiters stop the tokenizer reaching the
# parentheses, so it read 650. Only such a number is closed up, to "(650)"; all other text,
# including every other asterisk and underscore, reads exactly as before. The gaps hold only
# whitespace and asterisks, and the single number group can never join two numbers. The
# tokenizer's own boundaries apply: parentheses glued to a word or digit ("USD(", ")M") stay as
# they are, because "USD(650)" or "(650)M" is no token and the number would drop out.
_SPLIT_PAREN_NUMBER_RE = re.compile(r"(?<![\w.])\(([\s*]*)([−–-]?\d[\d,]*(?:\.\d+)?)([\s*]*)\)(?!\w|\.\w)")


def normalize_numeric_token(value: str) -> str | None:
    """Normalize one complete numeric token, preserving accounting signs."""

    cleaned = value.strip().translate(str.maketrans({"−": "-", "–": "-"}))
    if cleaned in {"", "—", "-"}:
        return None

    emphasis = re.fullmatch(
        r"(?P<mark>\*{1,3}|_{1,3}|~{1,3})\s*(?P<body>.*?)\s*(?P=mark)",
        cleaned,
    )
    if emphasis:
        cleaned = emphasis.group("body").strip()

    cleaned = cleaned.translate(_CURRENCY_SYMBOLS).replace(",", "").replace("%", "").strip()
    accounting = cleaned.startswith("(") and cleaned.endswith(")")
    if cleaned.startswith("(") != cleaned.endswith(")"):
        return None
    cleaned = cleaned.strip("()").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    if accounting and not cleaned.startswith("-"):
        cleaned = "-" + cleaned
    return cleaned


def _normalized_numbers(text: str) -> tuple[str, ...]:
    """Extract normalized numeric tokens in source order."""

    text = _MARKDOWN_IMAGE_RE.sub("", text)
    normalized: list[str] = []
    for match in _NUMBER_TOKEN_RE.finditer(text):
        token = normalize_numeric_token(match.group(0))
        if token is not None:
            normalized.append(token)
    return tuple(normalized)


def _close_up_split_paren_number(match: re.Match[str]) -> str:
    """Close up "(** **650** **)" to "(650)"; leave a match whose gaps are not emphasis runs."""

    gaps = (match.group(1), match.group(3))
    if not any("*" in gap for gap in gaps):
        return match.group(0)  # plain "( 650 )" already reads as -650
    if any("*" in gap and not re.search(r"\s", gap) for gap in gaps):
        # A gap of stars with no whitespace, as in the footnote "(125*)", is literal text. A gap
        # holding both a star and whitespace closes up even when the star is literal ("(5 *)",
        # "( 5* )", "( *5 )", "(1,234 **)"); none occurs in the 179 corpus documents.
        return match.group(0)
    return f"({match.group(2)})"


@dataclass(frozen=True)
class ElementHeaderRecord:
    """One table's header record, bound to the segment its render supplied (spec R6a).

    segment is the table's Markdown exactly as it entered element content. header_line is
    the header line that render wrote, which must be the segment's first line.
    header_source and header_capacity are the render's sorted (token, count) pairs: the
    header-zone cells' tokens, and each cell's tokens times the output columns it heads.
    header_cells are those cells with text, in document order, as (text, columns headed),
    for consumers with their own tokenizer, such as the accuracy suite's trace.
    """

    segment: str
    header_line: str
    header_source: tuple[tuple[str, int], ...] = ()
    header_capacity: tuple[tuple[str, int], ...] = ()
    header_cells: tuple[tuple[str, int], ...] = ()


HeaderMiss = Literal["missing", "ambiguous"]


@dataclass(frozen=True)
class HeaderLineLocation:
    """Where a record's header line sits in element content, or why it was not located.

    span is the line's [start, end) offsets. miss is "missing" when the segment does not
    occur on whole lines or its first line is not the recorded header line, and
    "ambiguous" when the segment occurs more than once or another record claims the same
    header line.
    """

    span: tuple[int, int] | None
    miss: HeaderMiss | None = None


def _whole_line_occurrences(content: str, segment: str) -> list[int]:
    """Start offsets where segment occupies whole lines of content, overlaps included."""

    starts: list[int] = []
    start = content.find(segment)
    while start != -1:
        end = start + len(segment)
        if (start == 0 or content[start - 1] == "\n") and (end == len(content) or content[end] == "\n"):
            starts.append(start)
        start = content.find(segment, start + 1)
    return starts


def locate_header_lines(
    content: str, records: Sequence[ElementHeaderRecord]
) -> tuple[HeaderLineLocation, ...]:
    """Locate each record's header line as the first line of its own segment (spec R6a).

    The header line is never searched for on its own, so an identical prose or body line
    elsewhere in the element is never taken for it. Each header line is consumed once.
    """

    spans: list[tuple[int, int] | HeaderMiss] = []
    for record in records:
        starts = _whole_line_occurrences(content, record.segment) if record.segment else []
        if len(starts) > 1:
            spans.append("ambiguous")
        elif not starts or record.segment.split("\n", 1)[0] != record.header_line:
            spans.append("missing")
        else:
            spans.append((starts[0], starts[0] + len(record.header_line)))
    claims = Counter(span for span in spans if isinstance(span, tuple))
    return tuple(
        HeaderLineLocation(None, span) if isinstance(span, str)
        else HeaderLineLocation(None, "ambiguous") if claims[span] > 1
        else HeaderLineLocation(span)
        for span in spans
    )


def trace_numeric_failures(
    element: Element,
    nodes: Sequence[Tag],
    header_records: Sequence[ElementHeaderRecord] | None = None,
) -> tuple[str, ...]:
    """Report each expected normalized number missing from mapped source nodes.

    With header records (spec R6a), each table header line located in the element is
    checked on its own against its table's header capacity, an excess failing as
    ``<element id>:header:<token>``. Located lines then leave the output pool and their
    tables' header source tokens leave the source pool, so header-zone occurrences never
    justify a body or prose number. A record whose header line is not located grants no
    exemption and subtracts nothing. Without records the trace is unchanged.
    """

    content = element.content
    header_failures: list[str] = []
    header_source: Counter[str] = Counter()
    if header_records:
        located = [
            (record, location.span)
            for record, location in zip(header_records, locate_header_lines(content, header_records))
            if location.span is not None
        ]
        for record, (start, end) in located:
            capacity = dict(record.header_capacity)
            # Output side, read as the rest of the output is read below.
            line = _SPLIT_PAREN_NUMBER_RE.sub(_close_up_split_paren_number, content[start:end])
            for token, count in sorted(Counter(_normalized_numbers(line)).items()):
                header_failures.extend(
                    f"{element.id}:header:{token}" for _ in range(max(0, count - capacity.get(token, 0)))
                )
            header_source.update(dict(record.header_source))
        for _, (start, end) in sorted(located, key=lambda item: item[1], reverse=True):
            content = content[:start] + content[end:]
    if any(_is_or_has_ordered_list(node) for node in nodes if isinstance(node, Tag)):
        content = _ORDERED_LIST_MARKER_RE.sub("", content)
    # Output side only: the source pool below reads the mapped nodes' text unchanged.
    content = _SPLIT_PAREN_NUMBER_RE.sub(_close_up_split_paren_number, content)
    expected = Counter(_normalized_numbers(content))
    available = Counter(
        _normalized_numbers(
            " ".join(node.get_text(" ", strip=True) for node in nodes if isinstance(node, Tag))
        )
    )
    if header_source:
        available -= header_source
    failures: list[str] = []
    for token, count in sorted(expected.items()):
        failures.extend(
            f"{element.id}:{token}" for _ in range(max(0, count - available[token]))
        )
    return tuple(header_failures + failures)


@dataclass(frozen=True)
class ParseDiagnostics:
    """Immutable measurements and warnings from one parser invocation."""

    source_visible_chars: int
    output_visible_chars: int
    output_ratio: float
    replacement_characters: int
    c1_control_characters: int
    pages: int
    elements: int
    mapped_elements: int
    trace_numeric_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    # Table completeness (Phase A: reported, never enforced). Defaults keep existing
    # positional construction working.
    table_completeness_failures: tuple[str, ...] = ()
    table_completeness_reported: tuple[str, ...] = ()
    table_structure_differences: tuple[str, ...] = ()
    tables_checked: int = 0
    numeric_recall: float | None = None
    # Header alignment (report-only). An empty tuple means the check did not run (policy
    # "off", or a failure inside check_tables()); a completed run emits every coverage key.
    table_header_alignment: tuple[str, ...] = ()
    table_header_alignment_coverage: tuple[tuple[str, int], ...] = ()


def _is_or_has_ordered_list(node: Tag) -> bool:
    return node.name in {"ol", "li"} or node.find("ol") is not None or node.find_parent("ol") is not None


class ParseQualityError(ValueError):
    """Raised when strict quality enforcement detects possible parse loss."""

    def __init__(self, diagnostics: ParseDiagnostics):
        self.diagnostics = diagnostics
        super().__init__("; ".join(diagnostics.warnings))

    def __reduce__(self):
        # Rebuild from diagnostics so the error crosses process boundaries
        # (multiprocessing, concurrent.futures) intact.
        return (type(self), (self.diagnostics,))


def validate_quality_policy(policy: object) -> None:
    """Raise ValueError unless policy is ``strict``, ``warn`` or ``off``."""

    if not isinstance(policy, str) or policy not in _QUALITY_POLICIES:
        raise ValueError(f"invalid quality_policy: {policy}")


def _is_hidden_tag(tag) -> bool:
    """Return whether a DOM node is not visible filing text."""

    attrs = tag.attrs or {}
    if "hidden" in attrs:
        return True
    if str(attrs.get("aria-hidden", "")).casefold() == "true":
        return True

    style = attrs.get("style", "")
    if isinstance(style, list):
        style = " ".join(style)
    if _HIDDEN_STYLE_RE.search(str(style)):
        return True

    name = str(getattr(tag, "name", "")).casefold()
    return name in {"ix:hidden", "hidden"} or name.endswith(":hidden")


def _visible_source_text(source_text: str) -> str:
    """Extract visible source text used by the catastrophic-loss guard."""

    soup = BeautifulSoup(source_text, "lxml")
    for tag in list(soup.find_all(["script", "style", "noscript", "template"])):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if _is_hidden_tag(tag):
            tag.decompose()
    return soup.get_text(" ", strip=True)


def _visible_markdown_text(output: str) -> str:
    """Remove Markdown presentation syntax before counting visible characters."""

    visible_lines: list[str] = []
    in_fence = False
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if re.match(r"^(`{3,}|~{3,})", line):
            in_fence = not in_fence
            continue
        if in_fence or _TABLE_DIVIDER_RE.match(line):
            continue

        line = _MARKDOWN_LINK_RE.sub(r"\1", line)
        line = _MARKDOWN_REFERENCE_RE.sub(r"\1", line)
        line = _MARKDOWN_CODE_RE.sub(r"\2", line)
        line = re.sub(r"^\s{0,3}(?:#{1,6}\s+|>\s+|[-+*]\s+|\d+[.)]\s+)", "", line)
        line = re.sub(r"\s*\|\s*", " ", line)
        line = re.sub(r"[*_~]", "", line)
        if line.strip():
            visible_lines.append(line.strip())
    return " ".join(visible_lines)


def _hard_failure_messages(
    source_chars: int,
    output_chars: int,
    replacement_count: int,
    c1_count: int,
    missing_mapping_ids: Sequence[str],
    trace_failures: Sequence[str],
) -> tuple[str, ...]:
    """Return deterministic messages for each strict quality failure."""

    failures: list[str] = []
    ratio = output_chars / source_chars if source_chars else 1.0
    if source_chars >= 1_000 and output_chars == 0:
        failures.append("substantial source produced empty output")
    if source_chars >= 10_000 and ratio < 0.10:
        failures.append(f"catastrophic output ratio {ratio:.6f} below 0.10")
    if replacement_count:
        failures.append(f"output contains {replacement_count} replacement characters")
    if c1_count:
        failures.append(f"output contains {c1_count} C1 control characters")
    if missing_mapping_ids:
        failures.append(
            "element lacks a source-node mapping: " + ",".join(missing_mapping_ids)
        )
    if trace_failures:
        failures.append("untraceable normalized number: " + ",".join(trace_failures))
    return tuple(failures)


def build_diagnostics(
    source_text: str,
    output: str,
    pages: Sequence[Page],
    *,
    mapped_element_ids: Collection[str],
    trace_failures: Sequence[str],
    enforce_mappings: bool,
    table_report: "TableCompletenessReport | None" = None,
) -> ParseDiagnostics:
    """Build immutable diagnostics for one source/output pair."""

    source_visible = _visible_source_text(source_text)
    output_visible = _visible_markdown_text(output)
    source_chars = len(source_visible)
    output_chars = len(output_visible)
    replacement_count = output.count("\ufffd")
    c1_count = len(_C1_CONTROL_RE.findall(output))

    elements = [element for page in pages for element in (page.elements or ())]
    mapped_ids = set(mapped_element_ids)
    missing_mapping_ids = (
        tuple(element.id for element in elements if element.id not in mapped_ids)
        if enforce_mappings
        else ()
    )
    mapped_count = sum(element.id in mapped_ids for element in elements)
    normalized_trace_failures = tuple(trace_failures)
    warnings = _hard_failure_messages(
        source_chars,
        output_chars,
        replacement_count,
        c1_count,
        missing_mapping_ids,
        normalized_trace_failures,
    )
    return ParseDiagnostics(
        source_visible_chars=source_chars,
        output_visible_chars=output_chars,
        output_ratio=output_chars / source_chars if source_chars else 1.0,
        replacement_characters=replacement_count,
        c1_control_characters=c1_count,
        pages=len(pages),
        elements=len(elements),
        mapped_elements=mapped_count,
        trace_numeric_failures=normalized_trace_failures,
        warnings=warnings,
        table_completeness_failures=table_report.failures if table_report else (),
        table_completeness_reported=table_report.reported if table_report else (),
        table_structure_differences=table_report.structure if table_report else (),
        tables_checked=table_report.tables_checked if table_report else 0,
        # Checks 1-3 run together: Parser skips them all under quality_policy="off".
        numeric_recall=_numeric_recall(source_visible, output_visible) if table_report is not None else None,
        table_header_alignment=table_report.alignment if table_report else (),
        table_header_alignment_coverage=table_report.alignment_coverage if table_report else (),
    )


def _numeric_recall(source_visible: str, output_visible: str) -> float | None:
    """Share of visible source numbers present in the visible output (check 3, diagnostic only)."""

    expected = Counter(_normalized_numbers(source_visible))
    if not expected:
        return None
    available = Counter(_normalized_numbers(output_visible))
    matched = sum(min(count, available[token]) for token, count in expected.items())
    return matched / sum(expected.values())


def enforce_quality(diagnostics: ParseDiagnostics, policy: QualityPolicy) -> ParseDiagnostics:
    """Apply strict, warning-only, or disabled quality enforcement."""

    validate_quality_policy(policy)
    if policy == "off":
        return diagnostics
    # Phase A: table completeness findings are reported, never enforced. One summary
    # warning per document; each finding at INFO so large filings do not flood logs.
    failures = diagnostics.table_completeness_failures
    if failures:
        logger.warning(
            "sec2md table completeness: %d table(s) with missing values; "
            "see ParseDiagnostics.table_completeness_failures",
            len(failures),
        )
        for finding in failures:
            logger.info("sec2md table completeness: %s", finding)
    if policy == "warn":
        for warning in diagnostics.warnings:
            logger.warning("sec2md quality: %s", warning)
        return diagnostics
    if diagnostics.warnings:
        raise ParseQualityError(diagnostics)
    return diagnostics
