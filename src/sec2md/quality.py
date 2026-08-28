"""Runtime diagnostics and fail-closed quality policies for parsed filings."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Collection, Literal, Sequence

from bs4 import BeautifulSoup

from sec2md.models import Page


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

    cleaned = cleaned.replace(",", "").replace("$", "").replace("%", "").strip()
    accounting = cleaned.startswith("(") and cleaned.endswith(")")
    if cleaned.startswith("(") != cleaned.endswith(")"):
        return None
    cleaned = cleaned.strip("()").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    if accounting and not cleaned.startswith("-"):
        cleaned = "-" + cleaned
    return cleaned


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


class ParseQualityError(ValueError):
    """Raised when strict quality enforcement detects possible parse loss."""

    def __init__(self, diagnostics: ParseDiagnostics):
        self.diagnostics = diagnostics
        super().__init__("; ".join(diagnostics.warnings))


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
) -> ParseDiagnostics:
    """Build immutable diagnostics for one source/output pair."""

    source_chars = len(_visible_source_text(source_text))
    output_chars = len(_visible_markdown_text(output))
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
    )


def enforce_quality(diagnostics: ParseDiagnostics, policy: QualityPolicy) -> ParseDiagnostics:
    """Apply strict, warning-only, or disabled quality enforcement."""

    if not isinstance(policy, str) or policy not in {"strict", "warn", "off"}:
        raise ValueError(f"invalid quality_policy: {policy}")
    if policy == "off":
        return diagnostics
    if policy == "warn":
        for warning in diagnostics.warnings:
            logger.warning("sec2md quality: %s", warning)
        return diagnostics
    if diagnostics.warnings:
        raise ParseQualityError(diagnostics)
    return diagnostics
