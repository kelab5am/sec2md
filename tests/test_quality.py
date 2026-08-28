"""Tests for runtime parse diagnostics and quality enforcement."""

from pathlib import Path

import pytest

from sec2md.core import convert_to_markdown, parse_filing
from sec2md.models import Element, Page
from sec2md.parser import Parser
from sec2md.quality import (
    ParseQualityError,
    build_diagnostics,
    enforce_quality,
)


def test_strict_rejects_empty_output_from_substantial_source(monkeypatch):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    with pytest.raises(ParseQualityError) as exc:
        convert_to_markdown(source)
    assert exc.value.diagnostics.source_visible_chars >= 1000
    assert exc.value.diagnostics.output_visible_chars == 0


def test_warn_returns_output_and_logs_warning(monkeypatch, caplog):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    assert convert_to_markdown(source, quality_policy="warn") == ""
    assert "substantial source produced empty output" in caplog.text


def test_off_skips_quality_enforcement(monkeypatch):
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    assert convert_to_markdown("<p>" + ("x " * 600) + "</p>", quality_policy="off") == ""


def test_strict_rejects_catastrophic_output_ratio():
    source = "source " * 2_000
    diagnostics = build_diagnostics(
        source,
        "tiny",
        [],
        mapped_element_ids=(),
        trace_failures=(),
        enforce_mappings=False,
    )
    with pytest.raises(ParseQualityError, match="catastrophic output ratio"):
        enforce_quality(diagnostics, "strict")


@pytest.mark.parametrize(
    ("output", "mapped_ids", "trace_failures", "message"),
    [
        ("bad \ufffd text", {"e1"}, (), "replacement character"),
        ("bad \u0092 text", {"e1"}, (), "C1 control character"),
        ("Revenue 123", set(), (), "element lacks a source-node mapping"),
        ("Revenue 123", {"e1"}, ("e1:123",), "untraceable normalized number"),
    ],
)
def test_strict_hard_failures(output, mapped_ids, trace_failures, message):
    element = Element(id="e1", content=output, kind="paragraph", page_start=1, page_end=1)
    pages = [Page(number=1, content=output, elements=[element])]
    diagnostics = build_diagnostics(
        "source " * 200,
        output,
        pages,
        mapped_element_ids=mapped_ids,
        trace_failures=trace_failures,
        enforce_mappings=True,
    )
    with pytest.raises(ParseQualityError, match=message):
        enforce_quality(diagnostics, "strict")


def test_warn_logs_all_hard_failures_and_returns_diagnostics(caplog):
    diagnostics = build_diagnostics(
        "source " * 200,
        "bad \ufffd text",
        [
            Page(
                number=1,
                content="bad \ufffd text",
                elements=[Element(id="e1", content="bad \ufffd text", kind="paragraph", page_start=1, page_end=1)],
            )
        ],
        mapped_element_ids=(),
        trace_failures=("e1:123",),
        enforce_mappings=True,
    )
    with caplog.at_level("WARNING"):
        assert enforce_quality(diagnostics, "warn") is diagnostics
    assert "replacement character" in caplog.text
    assert "element lacks a source-node mapping" in caplog.text
    assert "untraceable normalized number" in caplog.text


def test_off_returns_diagnostics_without_logging(caplog):
    diagnostics = build_diagnostics(
        "source " * 200,
        "bad \ufffd text",
        [],
        mapped_element_ids=(),
        trace_failures=(),
        enforce_mappings=False,
    )
    with caplog.at_level("WARNING"):
        assert enforce_quality(diagnostics, "off") is diagnostics
    assert not caplog.records


@pytest.mark.parametrize("policy", ["invalid", "strictish", ""])
def test_invalid_quality_policy_rejected(policy):
    with pytest.raises(ValueError, match="invalid quality_policy"):
        convert_to_markdown("<p>ok</p>", quality_policy=policy)


def test_parse_filing_is_strict_by_default(monkeypatch):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "get_pages", lambda self, include_elements=True: [])
    with pytest.raises(ParseQualityError):
        parse_filing(source)


def test_parse_filing_warn_and_off_return_pages():
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    assert isinstance(parse_filing(source, quality_policy="warn"), list)
    assert isinstance(parse_filing(source, quality_policy="off"), list)


def test_include_elements_false_does_not_require_mappings():
    pages = parse_filing("<p>Content without citable elements</p>", include_elements=False)
    assert pages[0].elements is None


def test_positioned_fixture_rejects_silent_loss(monkeypatch):
    path = Path(__file__).parent / "fixtures" / "sec" / "positioned-issue-4.html"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    with pytest.raises(ParseQualityError):
        convert_to_markdown(path.read_text(encoding="utf-8"))
