"""Tests for the core conversion API (core.py)."""

import pytest

from sec2md.core import convert_to_markdown, parse_filing
from sec2md.encoding import DecodeDiagnostics
from sec2md.models import Page
from sec2md.utils import FetchedHtml


@pytest.mark.parametrize(
    "source",
    [
        "<table><tr><td><a href='ex99-1.htm'>Release</a></td></tr></table>",
        b"<table><tr><td><a href='ex99-1.htm'>Release</a></td></tr></table>",
    ],
)
def test_raw_input_base_url_resolves_links_without_fetch(source, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "sec2md.core.fetch",
        lambda url, user_agent=None: calls.append(url),
    )
    result = convert_to_markdown(
        source,
        base_url="https://www.sec.gov/Archives/edgar/data/1/2/primary.htm",
        quality_policy="off",
    )
    assert "[Release](https://www.sec.gov/Archives/edgar/data/1/2/ex99-1.htm)" in result
    assert calls == []


def test_parse_filing_raw_bytes_passes_base_url_without_fetch(monkeypatch):
    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("raw bytes must not fetch")

    monkeypatch.setattr("sec2md.core.fetch", unexpected_fetch)
    pages = parse_filing(
        b"<p><a href='note.htm'>Note</a></p>",
        base_url="https://www.sec.gov/Archives/edgar/data/1/2/primary.htm",
        quality_policy="off",
    )
    assert pages


@pytest.mark.parametrize(
    "base_url",
    [
        "http://www.sec.gov/a.htm",
        "//www.sec.gov/a.htm",
        "https:///a.htm",
        "https://user@www.sec.gov/a.htm",
        "https://user:pass@www.sec.gov/a.htm",
        "https://www.sec.gov/a.htm#fragment",
    ],
)
def test_base_url_rejects_unsafe_or_nonabsolute_values(base_url):
    with pytest.raises(ValueError, match="base_url"):
        convert_to_markdown("<p>safe</p>", base_url=base_url)


def test_url_input_rejects_conflicting_base_before_fetch(monkeypatch):
    monkeypatch.setattr(
        "sec2md.core.fetch",
        lambda *args, **kwargs: pytest.fail("conflict must fail before fetch"),
    )
    with pytest.raises(ValueError, match="base_url.*source URL"):
        convert_to_markdown(
            "https://www.sec.gov/Archives/a.htm",
            base_url="https://www.sec.gov/Archives/b.htm",
        )


def test_raw_input_base_url_does_not_enable_image_fetch(monkeypatch):
    monkeypatch.setattr(
        "sec2md.core._embed_images",
        lambda *args, **kwargs: pytest.fail("raw input must not embed by fetching"),
    )
    result = convert_to_markdown(
        "<p>safe</p><img src='chart.png'>",
        base_url="https://www.sec.gov/Archives/a.htm",
        embed_images=True,
        quality_policy="off",
    )
    assert "safe" in result


def test_omitted_base_url_preserves_raw_relative_link_output():
    html = "<table><tr><td><a href='ex99.htm'>Release</a></td></tr></table>"

    assert convert_to_markdown(html, quality_policy="off") == convert_to_markdown(
        html,
        base_url=None,
        quality_policy="off",
    )


def test_base_url_does_not_change_decoding_or_strict_quality():
    source = b"<html><body><p>GPU\x92s \x9711</p></body></html>"

    without = convert_to_markdown(source, return_pages=True)
    with_context = convert_to_markdown(
        source,
        base_url="https://www.sec.gov/Archives/a.htm",
        return_pages=True,
    )

    assert [page.content for page in with_context] == [
        page.content for page in without
    ]


class TestConvertToMarkdown:
    """Tests for convert_to_markdown function."""

    def test_quality_policy_is_keyword_only(self):
        with pytest.raises(TypeError):
            convert_to_markdown("<p>Content</p>", "warn")

    def test_returns_string_by_default(self):
        html = "<html><body><p>Hello world</p></body></html>"
        result = convert_to_markdown(html)
        assert isinstance(result, str)
        assert "Hello world" in result

    def test_returns_pages_when_requested(self):
        html = "<html><body><p>Hello world</p></body></html>"
        result = convert_to_markdown(html, return_pages=True)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], Page)

    def test_bytes_input(self):
        html = b"<html><body><p>Bytes input</p></body></html>"
        result = convert_to_markdown(html)
        assert "Bytes input" in result

    def test_bytes_input_uses_lossless_legacy_normalization(self):
        result = convert_to_markdown(b"<html><body><p>GPU\x92s &#151; outlook</p></body></html>")

        assert "GPU’s — outlook" in result
        assert "\ufffd" not in result

    def test_url_input_uses_response_content_and_retains_decode_diagnostics(self, monkeypatch):
        fetched = FetchedHtml(
            b'<html><body><p>caf\xe9</p></body></html>', "windows-1252"
        )
        monkeypatch.setattr("sec2md.core.fetch", lambda url, user_agent=None: fetched)

        result = convert_to_markdown("https://example.test/filing.htm")

        assert "café" in result
        assert isinstance(result, str)

        pages = parse_filing("https://example.test/filing.htm", quality_policy="off")
        assert pages

    def test_url_input_resolves_relative_table_links(self, monkeypatch):
        fetched = FetchedHtml(
            b"<html><body><table><tr><th>Exhibit</th></tr><tr><td><a href='q2fy27pr.htm'>Earnings Release</a></td></tr></table></body></html>",
            "utf-8",
        )
        monkeypatch.setattr("sec2md.core.fetch", lambda url, user_agent=None: fetched)

        result = convert_to_markdown(
            "https://www.sec.gov/Archives/a/filing.htm", quality_policy="off"
        )

        assert "[Earnings Release](https://www.sec.gov/Archives/a/q2fy27pr.htm)" in result

    def test_raw_html_keeps_relative_table_links(self):
        html = "<html><body><table><tr><th>Exhibit</th></tr><tr><td><a href='q2fy27pr.htm'>Earnings Release</a></td></tr></table></body></html>"

        result = convert_to_markdown(html, quality_policy="off")

        assert "[Earnings Release](q2fy27pr.htm)" in result

    def test_parser_stores_decode_diagnostics(self):
        from sec2md.parser import Parser

        diagnostics = DecodeDiagnostics("utf-8", "strict-utf-8")
        parser = Parser("<p>Text</p>", decode_diagnostics=diagnostics)

        assert parser.decode_diagnostics == diagnostics

    def test_pdf_rejected(self):
        with pytest.raises(ValueError, match="PDF content detected"):
            convert_to_markdown(b"%PDF-1.4 fake pdf content")
        with pytest.raises(ValueError, match="PDF content detected"):
            convert_to_markdown("%PDF-1.4 fake pdf content")

    def test_empty_html(self):
        result = convert_to_markdown("<html><body></body></html>")
        assert isinstance(result, str)

    def test_preserves_bold(self):
        html = "<html><body><p><b>Bold text</b></p></body></html>"
        result = convert_to_markdown(html)
        assert "**Bold text**" in result

    def test_preserves_italic(self):
        html = "<html><body><p><i>Italic text</i></p></body></html>"
        result = convert_to_markdown(html)
        assert "*Italic text*" in result

    def test_preserves_headers(self):
        html = "<html><body><h1>Title</h1><p>Body</p></body></html>"
        # h1 tags are not converted to markdown headers -- they're treated as bold block text
        result = convert_to_markdown(html)
        assert "Title" in result

    def test_hidden_elements_removed(self):
        html = '<html><body><p>Visible</p><p style="display:none">Hidden</p></body></html>'
        result = convert_to_markdown(html)
        assert "Visible" in result
        assert "Hidden" not in result

    def test_page_break_splits_pages(self):
        html = """<html><body>
        <p>Page one</p>
        <div style="page-break-before:always"><p>Page two</p></div>
        </body></html>"""
        pages = convert_to_markdown(html, return_pages=True)
        assert len(pages) == 2
        assert "Page one" in pages[0].content
        assert "Page two" in pages[1].content

class TestParseFiling:
    """Tests for parse_filing function."""

    def test_returns_pages_with_elements(self):
        html = "<html><body><p>Paragraph one</p><p>Paragraph two</p></body></html>"
        pages = parse_filing(html, include_elements=True)
        assert isinstance(pages, list)
        assert len(pages) >= 1
        assert pages[0].elements is not None

    def test_returns_pages_without_elements(self):
        html = "<html><body><p>Content</p></body></html>"
        pages = parse_filing(html, include_elements=False)
        assert isinstance(pages, list)
        assert pages[0].elements is None
