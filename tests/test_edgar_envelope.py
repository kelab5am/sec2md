"""The EDGAR document envelope and head-only tags are not text.

EDGAR stores each document of a filing under an SGML envelope (<DOCUMENT>, <TYPE>,
<SEQUENCE>, <FILENAME>, <DESCRIPTION>, <TEXT>) before its own <html>. Parsed as HTML, the
envelope fields led page 1 ("EX-3.1 2 meta06302024-ex31.htm EX-3.1"), and the document's
<head> landed in the body, so its <title> and <script> text followed them
("Documentbazadebezolkohpepadr=..."). Meta's 10-Q EX-3.1 (0001326801-24-000069) is the model.
"""

import pytest

from sec2md.parser import Parser, strip_edgar_envelope

ENVELOPE = """<DOCUMENT>
<TYPE>EX-3.1
<SEQUENCE>2
<FILENAME>meta06302024-ex31.htm
<DESCRIPTION>EX-3.1
<TEXT>
"""
TRAILER = """</TEXT>
</DOCUMENT>
"""
WORKIVA_HEAD = """<html><head>
<!-- Document created using Wdesk -->
<!-- Copyright 2024 Workiva -->
<title>Document</title><script >bazadebezolkohpepadr="1742889685"</script></head><body>
<div><font>EXHIBIT 3.1</font></div>
<div><font>Body text.</font></div>
</body></html>
"""
PLAIN_HTML = """<html><body>
<div><font>EXHIBIT 3.1</font></div>
<div><font>Body text.</font></div>
</body></html>
"""
EXPECTED = "EXHIBIT 3.1\n\nBody text."


def _content(source: str) -> str:
    pages = Parser(source).get_pages(include_elements=False)
    return "\n\n".join(page.content for page in pages)


class TestEnvelope:
    @pytest.mark.parametrize(
        "source",
        [
            WORKIVA_HEAD,
            ENVELOPE + PLAIN_HTML + TRAILER,
            ENVELOPE + WORKIVA_HEAD + TRAILER,
        ],
        ids=["head-only", "envelope-only", "envelope-and-head"],
    )
    def test_envelope_title_and_script_leave_no_text(self, source):
        assert _content(source) == EXPECTED

    def test_strip_removes_the_envelope_and_its_trailer(self):
        assert strip_edgar_envelope(ENVELOPE + WORKIVA_HEAD + TRAILER) == WORKIVA_HEAD

    def test_leading_whitespace_before_the_envelope(self):
        assert _content("\r\n  " + ENVELOPE.replace("\n", "\r\n") + PLAIN_HTML + TRAILER) == EXPECTED

    def test_envelope_without_a_trailer(self):
        assert _content(ENVELOPE + PLAIN_HTML) == EXPECTED

    def test_envelope_with_only_some_fields(self):
        assert _content("<DOCUMENT>\n<TYPE>EX-99.1\n<TEXT>\n" + PLAIN_HTML + TRAILER) == EXPECTED

    def test_plain_text_document_under_an_envelope(self):
        source = ENVELOPE + "EXHIBIT 3.1\n\nBody text.\n" + TRAILER
        content = _content(source)
        assert "EXHIBIT 3.1" in content and "Body text." in content
        assert "meta06302024-ex31.htm" not in content and "EX-3.1" not in content

    @pytest.mark.parametrize("source", [PLAIN_HTML, WORKIVA_HEAD, "", "  \n"])
    def test_a_document_without_an_envelope_is_untouched(self, source):
        assert strip_edgar_envelope(source) is source

    @pytest.mark.parametrize(
        "source",
        [
            # Not at the start: only a leading envelope is an envelope.
            "<html><body>" + ENVELOPE + "<p>Body text.</p>" + TRAILER + "</body></html>",
            # A binary or XBRL document, not <TEXT>: left as it was.
            ENVELOPE.replace("<TEXT>", "<PDF>") + "begin 644 x.pdf\n" + TRAILER.replace("TEXT", "PDF"),
            ENVELOPE.replace("<TEXT>", "<XBRL>") + "<xbrl/>\n" + TRAILER.replace("TEXT", "XBRL"),
            # A field EDGAR's document header does not have: not this envelope.
            "<DOCUMENT>\n<TYPE>EX-3.1\n<OTHER>x\n<TEXT>\n" + PLAIN_HTML + TRAILER,
            # A full submission starts with <SEC-DOCUMENT>, not <DOCUMENT>.
            "<SEC-DOCUMENT>0000000000-24-000001.txt\n" + ENVELOPE + PLAIN_HTML + TRAILER,
        ],
        ids=["not-leading", "pdf", "xbrl", "unknown-field", "full-submission"],
    )
    def test_other_inputs_are_untouched(self, source):
        assert strip_edgar_envelope(source) is source

    def test_elements_map_after_the_envelope_is_stripped(self):
        from tests.accuracy.metrics import _mapping_and_trace

        parser = Parser(ENVELOPE + WORKIVA_HEAD + TRAILER)
        pages = parser.get_pages(include_elements=True)
        assert "\n\n".join(element.content for element in pages[0].elements) == EXPECTED
        assert _mapping_and_trace(pages, parser.html()) == ((), (), ())


class TestHeadOnlyTags:
    """<title>, <script>, <style> and <noscript> text is never rendered, wherever it sits."""

    LEAKS = (
        "<title>Document</title>",
        '<script>bazadebezolkohpepadr="1742889685"</script>',
        "<style>p { color: red } .x { margin: 0 }</style>",
        "<noscript>Enable scripts 42</noscript>",
    )

    @pytest.mark.parametrize("leak", LEAKS)
    @pytest.mark.parametrize(
        "template, expected",
        [
            ("<div>{leak}Body text.</div>", "Body text."),
            ("<div><span>Body {leak}text.</span></div>", "Body text."),
            ("<p><b>Bold {leak}text.</b></p>", "**Bold text.**"),
            ("<ul><li>Item {leak}text.</li></ul>", "- Item text."),
            ("<table><tr><td>Cell {leak}text.</td></tr></table>", "Cell text."),
        ],
    )
    def test_text_is_not_rendered(self, leak, template, expected):
        assert _content(f"<html><body>{template.format(leak=leak)}</body></html>") == expected

    @pytest.mark.parametrize("leak", LEAKS)
    def test_text_in_a_table_cell_is_not_rendered(self, leak):
        content = _content(
            "<html><body><table>"
            f"<tr><td>Revenue{leak}</td><td>1,234</td></tr>"
            "<tr><td>Cost</td><td>(567)</td></tr>"
            "</table></body></html>"
        )
        assert "Revenue" in content and "1,234" in content and "(567)" in content
        for word in ("Document", "bazadebezolkohpepadr", "color", "Enable"):
            assert word not in content
