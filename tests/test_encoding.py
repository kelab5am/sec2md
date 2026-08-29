"""Tests for deterministic SEC HTML decoding and legacy character handling."""

import pytest

from sec2md.encoding import (
    DecodeDiagnostics,
    decode_html,
    normalize_legacy_characters,
)
from sec2md.utils import FetchedHtml, fetch


def test_bom_precedes_http_charset_and_document_declaration():
    data = b'\xef\xbb\xbf<meta charset="windows-1252"><p>caf\xc3\xa9</p>'

    decoded, diagnostics = decode_html(data, http_charset="ascii")

    assert decoded == '<meta charset="windows-1252"><p>café</p>'
    assert diagnostics == DecodeDiagnostics("utf-8", "bom")


def test_http_charset_precedes_document_declaration():
    data = b'<meta charset="utf-8"><p>caf\xe9</p>'

    decoded, diagnostics = decode_html(data, http_charset="windows-1252")

    assert decoded == '<meta charset="utf-8"><p>café</p>'
    assert diagnostics == DecodeDiagnostics("cp1252", "http-charset")


def test_document_declaration_is_limited_to_first_8_kib():
    prefix = b" " * 100 + b'<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=ISO-8859-1">'
    data = prefix + b"\n<p>caf\xe9</p>"

    decoded, diagnostics = decode_html(data)

    assert decoded.endswith("<p>café</p>")
    assert diagnostics == DecodeDiagnostics("iso8859-1", "document-declaration")


@pytest.mark.parametrize(
    "declaration",
    [
        b'<meta charset="windows-1252">',
        b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">',
    ],
)
def test_valid_meta_declarations_are_honored(declaration):
    decoded, diagnostics = decode_html(declaration + b"<p>caf\xe9</p>")

    assert decoded.endswith("<p>café</p>")
    assert diagnostics == DecodeDiagnostics("cp1252", "document-declaration")


@pytest.mark.parametrize(
    "data",
    [
        b'<!-- <meta charset="windows-1252"> --><p>caf\xc3\xa9</p>',
        b'<script>const fake = \'<meta charset="windows-1252">\';</script><p>caf\xc3\xa9</p>',
        b'<style>/* <meta charset="windows-1252"> */</style><p>caf\xc3\xa9</p>',
    ],
)
def test_commented_and_raw_text_meta_declarations_are_ignored(data):
    decoded, diagnostics = decode_html(data)

    assert decoded.endswith("<p>caf" + chr(0xE9) + "</p>")
    assert diagnostics == DecodeDiagnostics("utf-8", "strict-utf-8")


@pytest.mark.parametrize(
    ("encoding", "bom"),
    [
        ("utf-16-le", b"\xff\xfe"),
        ("utf-16-be", b"\xfe\xff"),
        ("utf-32-le", b"\xff\xfe\x00\x00"),
        ("utf-32-be", b"\x00\x00\xfe\xff"),
    ],
)
def test_all_unicode_boms_precede_conflicting_transport_and_document_declarations(
    encoding, bom
):
    text = '<meta charset="windows-1252"><p>caf' + chr(0xE9) + '</p>'
    data = bom + text.encode(encoding)

    decoded, diagnostics = decode_html(data, http_charset="ascii")

    assert decoded == text
    assert diagnostics == DecodeDiagnostics(encoding, "bom")


@pytest.mark.parametrize(
    "declaration",
    [
        b'<meta name="note" content="charset=windows-1252">',
        b'<meta data-charset="windows-1252">',
    ],
)
def test_descriptive_meta_attributes_are_not_encoding_declarations(declaration):
    decoded, diagnostics = decode_html(declaration + b"<p>caf\xc3\xa9</p>")

    assert decoded.endswith("<p>café</p>")
    assert diagnostics == DecodeDiagnostics("utf-8", "strict-utf-8")


def test_declaration_after_first_8_kib_does_not_override_strict_utf8():
    data = b" " * 8192 + b'<meta charset="windows-1252"><p>caf\xc3\xa9</p>'

    decoded, diagnostics = decode_html(data)

    assert decoded.endswith('<meta charset="windows-1252"><p>café</p>')
    assert diagnostics == DecodeDiagnostics("utf-8", "strict-utf-8")


def test_strict_utf8_precedes_windows_1252_fallback():
    decoded, diagnostics = decode_html("<p>café — résumé</p>".encode("utf-8"))

    assert decoded == "<p>café — résumé</p>"
    assert diagnostics == DecodeDiagnostics("utf-8", "strict-utf-8")


def test_windows_1252_fallback_and_legacy_entity_normalization():
    decoded, diagnostics = decode_html(b"<p>GPU\x92s &#151; outlook</p>")
    assert diagnostics == DecodeDiagnostics("windows-1252", "windows-1252-fallback")
    assert normalize_legacy_characters(decoded) == "<p>GPU’s — outlook</p>"


def test_decoder_never_drops_invalid_bytes():
    decoded, _ = decode_html(b"<p>\x81</p>")
    assert "\ufffd" not in decoded
    with pytest.raises(ValueError, match="undefined Windows-1252 byte"):
        normalize_legacy_characters(decoded)


@pytest.mark.parametrize(
    "data, http_charset",
    [
        (b'<meta charset="not-a-real-codec"><p>text</p>', None),
        (b"<p>text</p>", "not-a-real-codec"),
    ],
)
def test_unknown_explicit_encodings_are_rejected(data, http_charset):
    with pytest.raises(ValueError, match="unknown encoding"):
        decode_html(data, http_charset=http_charset)


def test_normalization_preserves_unicode_financial_punctuation():
    text = "<p>Loss − $1,000 — not disclosed</p>"

    assert normalize_legacy_characters(text) == text


def test_fetch_returns_response_content_and_charset(monkeypatch):
    class Response:
        content = b"<p>caf\xe9</p>"
        headers = {"Content-Type": "text/html; charset=ISO-8859-1"}

        @property
        def text(self):
            raise AssertionError("fetch must not read response.text")

        def raise_for_status(self):
            return None

    def fake_get(url, *, headers, timeout):
        assert url == "https://example.test/filing.htm"
        assert headers == {}
        assert timeout == 30
        return Response()

    monkeypatch.setattr("sec2md.utils.requests.get", fake_get)

    result = fetch("https://example.test/filing.htm")

    assert result == FetchedHtml(b"<p>caf\xe9</p>", "ISO-8859-1")
