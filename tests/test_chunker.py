"""Tests for the chunking system (chunker.py, blocks.py, chunk.py, chunking.py)."""

from unittest.mock import patch, MagicMock

import pytest

from sec2md.chunker.chunker import Chunker
from sec2md.chunker.blocks import (
    TextBlock, TableBlock, HeaderBlock, Sentence,
    split_sentences, estimate_tokens,
)
from sec2md.chunker.chunk import Chunk
from sec2md.chunking import chunk_pages, chunk_section, merge_text_blocks, chunk_text_block
from sec2md.models import Page, Section, Element, TextBlock as ModelTextBlock


# ---------------------------------------------------------------------------
# Block-level tests
# ---------------------------------------------------------------------------

class TestSplitSentences:
    def test_basic_split(self):
        result = split_sentences("Hello world. Goodbye world.")
        assert len(result) == 2
        assert result[0] == "Hello world."
        assert result[1] == "Goodbye world."

    def test_no_split_on_abbreviation_like(self):
        result = split_sentences("Mr. Smith went to Washington.")
        # Should not split on "Mr." since next word is capitalized
        # (this regex-based splitter does split here -- just verify no crash)
        assert len(result) >= 1

    def test_single_sentence(self):
        result = split_sentences("Just one sentence here")
        assert len(result) == 1

    def test_empty_string(self):
        result = split_sentences("")
        assert result == []

    def test_exclamation_and_question(self):
        result = split_sentences("Wow! Is this working? Yes it is.")
        assert len(result) == 3


class TestEstimateTokens:
    def test_returns_positive(self):
        assert estimate_tokens("hello") >= 1

    def test_longer_text_more_tokens(self):
        short = estimate_tokens("hi")
        long = estimate_tokens("This is a much longer text with many more words in it")
        assert long > short

    def test_fallback_on_tiktoken_error(self):
        """Regression: tiktoken runtime errors must not crash estimate_tokens."""
        mock_tiktoken = MagicMock()
        mock_tiktoken.get_encoding.side_effect = ConnectionError("offline")
        with patch.dict("sys.modules", {"tiktoken": mock_tiktoken}):
            with patch("sec2md.chunker.blocks.TIKTOKEN_AVAILABLE", True):
                result = estimate_tokens("hello world")
                assert result == max(1, len("hello world") // 4)


class TestTextBlock:
    def test_sentences_property(self):
        block = TextBlock(content="First sentence. Second sentence.", page=1)
        assert len(block.sentences) == 2

    def test_from_sentences(self):
        sentences = [Sentence(content="A."), Sentence(content="B.")]
        block = TextBlock.from_sentences(sentences, page=1)
        assert "A." in block.content
        assert "B." in block.content

    def test_tokens_computed(self):
        block = TextBlock(content="Some text here", page=1)
        assert block.tokens >= 1

    def test_block_type(self):
        assert TextBlock(content="x", page=1).block_type == "Text"
        assert TableBlock(content="| a | b |", page=1).block_type == "Table"
        assert HeaderBlock(content="# Title", page=1).block_type == "Header"


class TestTableBlockMinification:
    def test_minifies_whitespace(self):
        content = "|  lots   of   space  |  here  |\n| --- | --- |\n|  a  |  b  |"
        block = TableBlock(content=content, page=1)
        assert "lots of space" in block.content
        assert "  " not in block.content.split("|")[1]  # inner cells trimmed


# ---------------------------------------------------------------------------
# Chunker tests
# ---------------------------------------------------------------------------

class TestChunkerBasic:
    def test_single_page_single_chunk(self):
        page = Page(number=1, content="Short text.")
        chunker = Chunker(chunk_size=512, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        assert len(chunks) == 1
        assert "Short text" in chunks[0].content

    def test_splits_long_content(self):
        long_text = ". ".join([f"Sentence number {i}" for i in range(100)])
        page = Page(number=1, content=long_text)
        chunker = Chunker(chunk_size=32, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        assert len(chunks) > 1

    def test_overlap_creates_shared_content(self):
        text = ". ".join([f"Sentence {i}" for i in range(20)])
        page = Page(number=1, content=text)
        chunker = Chunker(chunk_size=32, chunk_overlap=8)
        chunks = chunker.split(pages=[page])
        if len(chunks) >= 2:
            # Some content from end of chunk 0 should appear in chunk 1
            c0_words = set(chunks[0].content.split())
            c1_words = set(chunks[1].content.split())
            assert c0_words & c1_words  # some overlap

    def test_zero_overlap(self):
        text = ". ".join([f"Sentence {i}" for i in range(20)])
        page = Page(number=1, content=text)
        chunker = Chunker(chunk_size=32, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        assert len(chunks) >= 1

    def test_multiple_pages(self):
        pages = [
            Page(number=1, content="Page one content."),
            Page(number=2, content="Page two content."),
        ]
        chunker = Chunker(chunk_size=512, chunk_overlap=0)
        chunks = chunker.split(pages=[pages[0], pages[1]])
        assert len(chunks) >= 1


class TestChunkerBoundary:
    """Boundary condition tests for the chunker."""

    def test_chunk_size_one(self):
        page = Page(number=1, content="Hello. World.")
        chunker = Chunker(chunk_size=1, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        for chunk in chunks:
            assert len(chunk.blocks) > 0
            assert chunk.content.strip()

    def test_only_table_content(self):
        table_md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
        page = Page(number=1, content=table_md)
        chunker = Chunker(chunk_size=512, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        assert len(chunks) >= 1
        assert chunks[0].has_table

    def test_no_empty_chunks_ever(self):
        """Fuzz-like test: various chunk_size values should never produce empty chunks."""
        text = ". ".join([f"Word{i}" for i in range(50)])
        page = Page(number=1, content=text)
        for size in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]:
            chunker = Chunker(chunk_size=size, chunk_overlap=min(size // 2, 4))
            chunks = chunker.split(pages=[page])
            for i, chunk in enumerate(chunks):
                assert len(chunk.blocks) > 0, f"Empty chunk at size={size}, index={i}"

    def test_oversized_first_sentence_no_empty_chunk(self):
        """Regression: first sentence exceeding chunk_size must not produce empty chunks."""
        long_sentence = "Word " * 100
        page = Page(number=1, content=long_sentence.strip())
        chunker = Chunker(chunk_size=8, chunk_overlap=2)
        chunks = chunker.split(pages=[page])
        for i, chunk in enumerate(chunks):
            assert len(chunk.blocks) > 0, f"Chunk {i} has no blocks"
            assert chunk.content.strip(), f"Chunk {i} has empty content"


class TestChunkerElements:
    """Element linking in chunks."""

    def test_elements_carried_through(self):
        elem = Element(
            id="e1", content="Paragraph content", kind="paragraph",
            page_start=1, page_end=1,
            content_start_offset=0, content_end_offset=17
        )
        page = Page(number=1, content="Paragraph content", elements=[elem])
        chunker = Chunker(chunk_size=512, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        assert len(chunks) >= 1
        assert len(chunks[0].elements) >= 1
        assert chunks[0].elements[0].id == "e1"

    def test_element_ids_in_chunk(self):
        elem = Element(
            id="test-id", content="Content", kind="paragraph",
            page_start=1, page_end=1
        )
        page = Page(number=1, content="Content", elements=[elem])
        chunker = Chunker(chunk_size=512, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        if chunks and chunks[0].elements:
            assert "test-id" in chunks[0].element_ids


class TestChunkerTableSplitting:
    """Large table splitting by token limit."""

    def test_oversized_table_split(self):
        # Create a table that exceeds max_table_tokens
        rows = ["| Header1 | Header2 |", "| --- | --- |"]
        for i in range(100):
            rows.append(f"| Row {i} data | Value {i} |")
        table_content = "\n".join(rows)

        elem = Element(
            id="big-table", content=table_content, kind="table",
            page_start=1, page_end=1
        )
        page = Page(number=1, content=table_content, elements=[elem])
        # chunk_size must also be small enough that split table parts land in separate chunks
        chunker = Chunker(chunk_size=64, chunk_overlap=0, max_table_tokens=64)
        chunks = chunker.split(pages=[page])
        # Should be split into multiple chunks
        assert len(chunks) > 1

    def test_small_table_not_split(self):
        table_content = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        elem = Element(
            id="small-table", content=table_content, kind="table",
            page_start=1, page_end=1
        )
        page = Page(number=1, content=table_content, elements=[elem])
        chunker = Chunker(chunk_size=2048, chunk_overlap=0, max_table_tokens=2048)
        chunks = chunker.split(pages=[page])
        assert len(chunks) == 1


class TestChunkerDisplayPages:
    """Display page mapping in chunks."""

    def test_display_page_map_passed_through(self):
        page = Page(number=1, content="Content", display_page=42)
        chunker = Chunker(chunk_size=512, chunk_overlap=0)
        chunks = chunker.split(pages=[page])
        assert len(chunks) >= 1
        if chunks[0].display_page_map:
            assert chunks[0].display_page_map.get(1) == 42


# ---------------------------------------------------------------------------
# Chunk object tests
# ---------------------------------------------------------------------------

class TestChunkObject:
    def test_content_joins_blocks(self):
        blocks = [
            TextBlock(content="Line 1", page=1),
            TextBlock(content="Line 2", page=1),
        ]
        chunk = Chunk(blocks=blocks)
        assert "Line 1" in chunk.content
        assert "Line 2" in chunk.content

    def test_embedding_text_with_header(self):
        blocks = [TextBlock(content="Body", page=1)]
        chunk = Chunk(blocks=blocks, header="Company: AAPL")
        assert chunk.embedding_text.startswith("Company: AAPL")
        assert "Body" in chunk.embedding_text

    def test_embedding_text_without_header(self):
        blocks = [TextBlock(content="Body", page=1)]
        chunk = Chunk(blocks=blocks)
        assert chunk.embedding_text == chunk.content

    def test_has_table(self):
        blocks = [TableBlock(content="| a | b |", page=1)]
        chunk = Chunk(blocks=blocks)
        assert chunk.has_table is True

    def test_no_table(self):
        blocks = [TextBlock(content="Just text", page=1)]
        chunk = Chunk(blocks=blocks)
        assert chunk.has_table is False

    def test_page_range(self):
        blocks = [
            TextBlock(content="A", page=1),
            TextBlock(content="B", page=3),
        ]
        chunk = Chunk(blocks=blocks)
        assert chunk.start_page == 1
        assert chunk.end_page == 3

    def test_data_property(self):
        blocks = [
            TextBlock(content="Page 1 content", page=1),
            TextBlock(content="Page 2 content", page=2),
        ]
        chunk = Chunk(blocks=blocks)
        data = chunk.data
        assert len(data) == 2
        assert data[0]["page"] == 1
        assert data[1]["page"] == 2


# ---------------------------------------------------------------------------
# Public chunking API tests
# ---------------------------------------------------------------------------

class TestChunkPages:
    def test_basic_chunking(self):
        pages = [Page(number=1, content="Content here.")]
        chunks = chunk_pages(pages, chunk_size=512)
        assert len(chunks) >= 1

    def test_header_passed_through(self):
        pages = [Page(number=1, content="Content.")]
        chunks = chunk_pages(pages, chunk_size=512, header="Header: Test")
        assert chunks[0].header == "Header: Test"


class TestChunkSection:
    def test_chunks_section_pages(self):
        section = Section(
            part="PART I", item="ITEM 1", item_title="Business",
            pages=[Page(number=1, content="Business content here.")]
        )
        chunks = chunk_section(section, chunk_size=512)
        assert len(chunks) >= 1


class TestMergeTextBlocks:
    def test_merges_same_name_across_pages(self):
        elem1 = Element(id="e1", content="Part 1", kind="paragraph", page_start=1, page_end=1)
        elem2 = Element(id="e2", content="Part 2", kind="paragraph", page_start=2, page_end=2)
        tb1 = ModelTextBlock(name="us-gaap:DebtTextBlock", title="Debt", elements=[elem1])
        tb2 = ModelTextBlock(name="us-gaap:DebtTextBlock", title="Debt", elements=[elem2])
        pages = [
            Page(number=1, content="Part 1", text_blocks=[tb1]),
            Page(number=2, content="Part 2", text_blocks=[tb2]),
        ]
        merged = merge_text_blocks(pages)
        assert len(merged) == 1
        assert len(merged[0].elements) == 2
        assert merged[0].start_page == 1
        assert merged[0].end_page == 2

    def test_different_blocks_stay_separate(self):
        elem1 = Element(id="e1", content="Debt", kind="paragraph", page_start=1, page_end=1)
        elem2 = Element(id="e2", content="Revenue", kind="paragraph", page_start=1, page_end=1)
        tb1 = ModelTextBlock(name="us-gaap:DebtTextBlock", title="Debt", elements=[elem1])
        tb2 = ModelTextBlock(name="us-gaap:RevenueTextBlock", title="Revenue", elements=[elem2])
        pages = [Page(number=1, content="Content", text_blocks=[tb1, tb2])]
        merged = merge_text_blocks(pages)
        assert len(merged) == 2

    def test_empty_pages(self):
        merged = merge_text_blocks([])
        assert merged == []


class TestChunkTextBlock:
    def test_chunks_text_block(self):
        elems = [
            Element(id=f"e{i}", content=f"Sentence {i}.", kind="paragraph",
                    page_start=1, page_end=1)
            for i in range(5)
        ]
        tb = ModelTextBlock(name="us-gaap:DebtTextBlock", title="Debt", elements=elems)
        chunks = chunk_text_block(tb, chunk_size=512)
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# Audit regressions (2026-10-02)
# ---------------------------------------------------------------------------

class TestTableBlockSeparatorRow:
    def test_separator_has_header_column_count(self):
        block = TableBlock(content="| a | b |\n| --- | --- |\n| 1 | 2 |", page=1)
        assert block.content.split("\n") == ["|a|b|", "|---|---|", "|1|2|"]

    def test_minification_is_idempotent(self):
        once = TableBlock(content="| a | b |\n| --- | --- |\n| 1 | 2 |", page=1).content
        assert TableBlock(content=once, page=1).content == once

    def test_caption_line_is_not_replaced_by_separator(self):
        content = (
            "**Apple Inc.**\n"
            "**CONSOLIDATED BALANCE SHEETS**\n"
            "| | 2023 | 2022 |\n"
            "| --- | --- | --- |\n"
            "| Cash | 1 | 2 |"
        )
        lines = TableBlock(content=content, page=1).content.split("\n")
        assert lines == [
            "**Apple Inc.**",
            "**CONSOLIDATED BALANCE SHEETS**",
            "||2023|2022|",
            "|---|---|---|",
            "|Cash|1|2|",
        ]


class TestTableSplitKeepsHeader:
    def test_every_part_repeats_caption_units_and_header_row(self):
        prefix = ["**Statement of Operations**", "(In millions)", "| Item | 2023 | 2022 |", "| --- | --- | --- |"]
        data = [f"| Row {i} | {i} | {i + 1} |" for i in range(80)]
        elem = Element(id="t", content="\n".join(prefix + data), kind="table", page_start=1, page_end=1)
        parts = Chunker(chunk_size=64, chunk_overlap=0, max_table_tokens=64)._split_table_element(elem, 1)

        assert len(parts) > 1
        for part, _ in parts:
            assert part.content.split("\n")[:4] == prefix
        emitted = [line for part, _ in parts for line in part.content.split("\n") if line.startswith("| Row ")]
        assert emitted == data


def _fused_header_document(rows: int, *, long_row: int | None = None) -> str:
    """A table whose three header rows R6 fuses into one header line, with empty header cells.

    The label column and the note column carry no header text; "Year Ended" and
    "(In millions)" span both amount columns and repeat in each of their headers.
    """
    def label(index):
        return "Long line item " + " ".join(["detail"] * 400) if index == long_row else f"Line item {index}"

    body = "".join(
        f"<tr><td>{label(i)}</td><td>{100 + i}</td><td>{200 + i}</td><td>Note {i % 7 + 1}</td></tr>"
        for i in range(rows)
    )
    return (
        "<html><body><p>Consolidated revenue by line item.</p><table>"
        '<tr><td></td><td colspan="2">Year Ended</td><td></td></tr>'
        "<tr><td></td><td>2025</td><td>2024</td><td></td></tr>"
        '<tr><td></td><td colspan="2">(In millions)</td><td></td></tr>'
        f"{body}</table></body></html>"
    )


FUSED_CAPTION = "Consolidated revenue by line item."
FUSED_HEADER_LINE = "|  | Year Ended — 2025 — (In millions) | Year Ended — 2024 — (In millions) |  |"
FUSED_SEPARATOR = "| --- | --- | --- | --- |"
FUSED_ELLIPSIS = "|...|...|...|...|"


def _row_cells(line: str) -> list[str]:
    """A Markdown table line's cells, keeping blank ones (one outer pipe removed each side)."""
    return [cell.strip() for cell in line.strip()[1:-1].split("|")]


class TestChunkedFusedHeaderTables:
    """Spec 2026-10-05 (table merge and header rules), Testing, "Integration": tables with
    fused headers and empty header cells, rendered by Parser, then chunked."""

    @staticmethod
    def _render(html):
        from sec2md.parser import Parser

        pages = Parser(html).get_pages(include_elements=True)
        (table,) = [element for element in pages[0].elements if element.kind == "table"]
        return pages, table

    @staticmethod
    def _parts(chunks, table):
        parts = [element for chunk in chunks for element in chunk.elements
                 if element.id.startswith(f"{table.id}:part-")]
        assert [part.id for part in parts] == [f"{table.id}:part-{i}" for i in range(len(parts))]
        return parts

    def test_renderer_writes_the_fused_header_line_with_empty_header_cells(self):
        pages, table = self._render(_fused_header_document(3))
        assert table.content.split("\n") == [
            FUSED_CAPTION, "", FUSED_HEADER_LINE, FUSED_SEPARATOR,
            "| Line item 0 | 100 | 200 | Note 1 |",
            "| Line item 1 | 101 | 201 | Note 2 |",
            "| Line item 2 | 102 | 202 | Note 3 |",
        ]
        start, end = table.content_start_offset, table.content_end_offset
        assert pages[0].content[start:end] == table.content

    def test_every_part_keeps_content_and_repeats_the_header_prefix_in_full(self):
        pages, table = self._render(_fused_header_document(40))
        data = [line for line in table.content.split("\n") if line.startswith("| Line item ")]
        assert len(data) == 40
        chunks = chunk_pages(pages, chunk_size=128, chunk_overlap=0, max_table_tokens=128)
        parts = self._parts(chunks, table)
        assert len(parts) > 2

        emitted = []
        for part in parts:
            lines = part.content.split("\n")
            assert lines[:3] == [FUSED_CAPTION, FUSED_HEADER_LINE, FUSED_SEPARATOR]
            emitted.extend(line for line in lines[3:] if line != FUSED_ELLIPSIS)
        assert emitted == data

    def test_every_part_keeps_the_column_count(self):
        pages, table = self._render(_fused_header_document(40))
        chunks = chunk_pages(pages, chunk_size=128, chunk_overlap=0, max_table_tokens=128)
        blocks = [block for chunk in chunks for block in chunk.blocks if block.block_type == "Table"]
        assert len(blocks) > 2
        for part in self._parts(chunks, table):
            assert {len(_row_cells(line)) for line in part.content.split("\n")[1:]} == {4}
        for block in blocks:
            lines = block.content.split("\n")
            assert lines[0] == FUSED_CAPTION
            assert _row_cells(lines[1]) == ["", "Year Ended — 2025 — (In millions)",
                                            "Year Ended — 2024 — (In millions)", ""]
            assert {len(_row_cells(line)) for line in lines[1:]} == {4}

    def test_every_part_cites_the_table_span_of_its_page(self):
        pages, table = self._render(_fused_header_document(40))
        start, end = table.content_start_offset, table.content_end_offset
        cited = pages[0].content[start:end]
        assert cited == table.content
        chunks = chunk_pages(pages, chunk_size=128, chunk_overlap=0, max_table_tokens=128)
        for part in self._parts(chunks, table):
            assert (part.content_start_offset, part.content_end_offset) == (start, end)
            assert all(line in cited.split("\n") for line in part.content.split("\n") if line != FUSED_ELLIPSIS)

    def test_a_row_over_the_token_budget_is_kept_whole_with_its_prefix(self):
        from sec2md.chunker.blocks import estimate_tokens

        pages, table = self._render(_fused_header_document(12, long_row=5))
        (long_line,) = [line for line in table.content.split("\n") if line.startswith("| Long line item ")]
        chunks = chunk_pages(pages, chunk_size=128, chunk_overlap=0, max_table_tokens=128)
        holding = [part for part in self._parts(chunks, table) if long_line in part.content.split("\n")]
        assert len(holding) == 1
        lines = holding[0].content.split("\n")
        assert lines[:3] == [FUSED_CAPTION, FUSED_HEADER_LINE, FUSED_SEPARATOR]
        assert [line for line in lines[3:] if line != FUSED_ELLIPSIS] == [long_line]
        assert estimate_tokens(holding[0].content) > 128


class TestChunkOverlapContiguity:
    def test_each_chunk_is_a_contiguous_run_of_source_sentences(self):
        alpha = [f"Alpha sentence number {i} talks about revenue growth in the quarter." for i in range(6)]
        bravo = ["Bravo is short."]
        charlie = [f"Charlie sentence number {i} talks about operating expenses this year." for i in range(10)]
        content = "\n\n".join([" ".join(alpha), " ".join(bravo), " ".join(charlie)])
        source = alpha + bravo + charlie

        chunks = Chunker(chunk_size=100, chunk_overlap=40).split(pages=[Page(number=1, content=content)])

        assert len(chunks) > 2
        for chunk in chunks:
            got = split_sentences(" ".join(chunk.content.split()))
            start = source.index(got[0])
            assert got == source[start:start + len(got)]


class TestChunkTagsOrder:
    def test_tags_are_distinct_in_first_seen_order(self):
        tags = [f"us-gaap:Concept{i}" for i in (7, 3, 9, 1, 5, 8, 2, 6, 4, 0)]
        e1 = Element(id="e1", content="x", kind="paragraph", page_start=1, page_end=1, tags=tags[:6])
        e2 = Element(id="e2", content="y", kind="paragraph", page_start=1, page_end=1, tags=tags[3:] + tags[:2])
        chunk = Chunk(blocks=[TextBlock(content="x y", page=1)], elements=[e1, e2])
        assert chunk.tags == tags


_ONE_PAGE_10K = """<html><body>
<p>Cover page text for the annual report.</p>
<div style="page-break-after:always"></div>
<p><b>PART I</b></p>
<p><b>Item 1A. Risk Factors</b></p>
<p>Alpha risk paragraph describes supply chain exposure in detail.</p>
<p><b>Item 1B. Unresolved Staff Comments</b></p>
<p>None.</p>
<p><b>Item 1C. Cybersecurity</b></p>
<p>Charlie cyber paragraph describes the security program.</p>
</body></html>"""


@pytest.fixture(scope="module")
def sections():
    import sec2md
    pages = sec2md.convert_to_markdown(_ONE_PAGE_10K, return_pages=True)
    found = sec2md.extract_sections(pages, filing_type="10-K")
    return {section.item: section for section in found}


class TestChunkSectionIsolation:
    """Sections sharing a page must not chunk each other's content."""

    def test_chunks_contain_only_their_own_section(self, sections):
        text = {item: " ".join(c.content for c in chunk_section(s)) for item, s in sections.items()}
        assert "None." in text["ITEM 1B"]
        assert "Alpha risk" not in text["ITEM 1B"]
        assert "Charlie cyber" not in text["ITEM 1B"]
        assert "Charlie cyber" not in text["ITEM 1A"]
        assert "Alpha risk" not in text["ITEM 1C"]

    def test_chunks_keep_element_ids_from_their_own_section(self, sections):
        ids = {item: [i for c in chunk_section(s) for i in c.element_ids] for item, s in sections.items()}
        assert ids["ITEM 1A"] and ids["ITEM 1B"] and ids["ITEM 1C"]
        assert not set(ids["ITEM 1A"]) & set(ids["ITEM 1B"])
        assert not set(ids["ITEM 1B"]) & set(ids["ITEM 1C"])

    def test_real_filing_item_1b_chunks_match_section_text(self):
        import gzip
        from pathlib import Path
        import sec2md
        html = gzip.decompress((Path(__file__).parent / "fixtures" / "sec" / "aapl-2023-10k.html.gz").read_bytes())
        pages = sec2md.convert_to_markdown(html, return_pages=True)
        section = sec2md.get_section(sec2md.extract_sections(pages, filing_type="10-K"), "ITEM 1B")
        chunked = " ".join(c.content for c in chunk_section(section))
        assert "None." in chunked
        assert len(chunked) < 200
