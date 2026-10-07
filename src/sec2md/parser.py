from __future__ import annotations

import re
import logging
from copy import deepcopy
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import List, Dict, Union, Optional, Tuple, Sequence

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from sec2md.absolute_table_parser import AbsolutelyPositionedTableParser
from sec2md.utils import median, clean_text
from sec2md.table_parser import TableHeaderRecord, TableParser, render_cell_content
from sec2md.models import Page, Element
from sec2md.xlsx_tables import (
    TableSnapshot, native_metadata, snapshot_html_table, snapshot_positioned_table,
)
from sec2md.element_builder import (
    build_elements_for_pages,
    augment_html_with_ids,
    ordered_unique_nodes,
)
from sec2md.encoding import DecodeDiagnostics, normalize_legacy_characters
from sec2md.table_completeness import TableCompletenessReport, check_tables
from sec2md.quality import (
    ElementHeaderRecord,
    ParseDiagnostics,
    build_diagnostics,
    locate_header_lines,
    trace_numeric_failures as compute_trace_numeric_failures,
)

BLOCK_TAGS = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "br", "hr", "ul", "ol", "li"}
BOLD_TAGS = {"b", "strong"}
ITALIC_TAGS = {"i", "em"}

_css_decl = re.compile(r"^[a-zA-Z\-]+\s*:\s*[^;]+;\s*$")
ITEM_HEADER_CELL_RE = re.compile(r"^\s*Item\s+([0-9IVX]+)\.\s*$", re.I)
PART_HEADER_CELL_RE = re.compile(r"^\s*Part\s+([IVX]+)\s*$", re.I)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\([^)]+\)")
# A Markdown table divider row, with or without outer pipes (as quality._TABLE_DIVIDER_RE).
_MARKDOWN_TABLE_DIVIDER_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")

logger = logging.getLogger(__name__)


def _wrapped_copy_survives(
    raw: str, content: str, rendered: str, segment: str, links: Sequence[tuple[int, int, int]]
) -> bool:
    """Whether a wrapper's final segment holds a table's own copy (spec R6a, revision 18).

    raw is the wrapper segment's text, content its final segment (raw with link syntax
    reduced to labels), rendered the table's normal render, and links the reduction's
    matches in raw as (start, end, characters removed). A wrapper only adds text around a
    table's render, so the table's copy is one of rendered's occurrences in raw; any other
    occurrence is other text that reads the same, such as another table's render (or part
    of one, or a cell's literal Markdown) or an image's alt text. Every occurrence must
    keep its boundaries, crossed by no link reduction, and its reduced text must be exactly
    the record's segment. So a copy that the reduction damaged is never taken for intact, and
    the record is never left to be located on other text that only reduces to its segment.
    """

    start = raw.find(rendered)
    if start == -1:
        return False
    while start != -1:
        end = start + len(rendered)
        if any(first < boundary < last for first, last, _ in links for boundary in (start, end)):
            return False
        image_start = start - sum(removed for _, last, removed in links if last <= start)
        image_end = end - sum(removed for _, last, removed in links if last <= end)
        if content[image_start:image_end] != segment:
            return False
        start = raw.find(rendered, start + 1)
    return True


@dataclass
class TextBlockInfo:
    """Tracks XBRL TextBlock context during parsing."""
    name: str
    title: Optional[str] = None


class Parser:
    """Document parser with support for regular tables and pseudo-tables."""

    def __init__(
        self,
        content: str,
        *,
        source_url: str | None = None,
        decode_diagnostics: DecodeDiagnostics | None = None,
        capture_tables: bool = False,
        table_checks: bool = True,
    ):
        content = normalize_legacy_characters(content)
        self.source_text = content
        self.source_url = source_url
        self.decode_diagnostics = decode_diagnostics
        self.soup = BeautifulSoup(content, "lxml")
        self.capture_tables = capture_tables
        self.table_checks = table_checks
        # Table completeness inputs, recorded during rendering without changing it.
        self.table_outputs: dict[int, str] = {}
        # Link-free cell texts of the Markdown render by id(td), reused by the alignment check.
        self._cell_texts: dict[int, str] = {}
        self._table_pages: dict[int, int] = {}
        self._snapshot_ordinals: dict[int, int] = {}
        self._snapshot_ordinal = 0
        self._root_table_rows: dict[int, list[list[Tag]]] = {}
        self.table_report: TableCompletenessReport | None = None
        self.table_snapshots: list[TableSnapshot] = []
        self._snapshot_nodes: list[Sequence[Tag]] = []
        self._unreliable_tables: dict[int, TableSnapshot] = {}
        self._native_anchors, self._note_targets = (
            native_metadata(self.soup) if capture_tables else ({}, {})
        )
        self.includes_table = False
        self.include_images = True
        self.pages: Dict[int, List[str]] = defaultdict(list)
        self.page_segments: Dict[
            int,
            List[Tuple[str, Optional[Tag] | Sequence[Tag], Optional[TextBlockInfo]]],
        ] = defaultdict(list)
        self.input_char_count = len(self.soup.get_text())
        self.current_text_block: Optional[TextBlockInfo] = None
        self.continuation_map: Dict[str, TextBlockInfo] = {}
        self.footer_page_numbers: Dict[int, int] = {}
        self.block_nodes_map: Dict[str, List[Tag]] = {}
        self.trace_numeric_failures: tuple[str, ...] = ()
        # R6a header accounting: the normal render's header record per table node until
        # that render supplies element content, then the record bound to the node.
        self._render_header_records: dict[int, tuple[Tag, TableHeaderRecord | None]] = {}
        self._header_records: dict[int, ElementHeaderRecord] = {}
        # Revision 18: tables rendered inside a list item or an inline wrapper. While a wrapper
        # renders, _render_table collects its tables and their normal renders; the wrapper's
        # segment position is noted when it is appended; after streaming, each record is bound
        # from the wrapper's final segment, and the wrapper maps to its bound tables.
        self._table_collector: list[tuple[Tag, str]] | None = None
        self._wrapped_renders: list[tuple[int, int, Tag, list[tuple[Tag, str]]]] = []
        self._wrapped_tables: dict[int, list[Tag]] = {}
        self.header_accounting_misses: tuple[str, ...] = ()
        self.diagnostics: Optional[ParseDiagnostics] = None
        self._last_pages: Optional[List[Page]] = None

    @staticmethod
    def _is_text_block_tag(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        if el.name not in ('ix:nonnumeric', 'nonnumeric'):
            return False
        name = el.get('name', '')
        if 'TextBlock' not in name:
            return False
        return name.startswith('us-gaap:') or name.startswith('cyd:')

    @staticmethod
    def _find_text_block_tag_in_children(el: Tag) -> Optional[Tag]:
        """Search up to 2 levels deep for a TextBlock tag."""
        if not isinstance(el, Tag):
            return None
        if Parser._is_text_block_tag(el):
            return el
        for child in el.children:
            if isinstance(child, Tag):
                if Parser._is_text_block_tag(child):
                    return child
                for grandchild in child.children:
                    if isinstance(grandchild, Tag) and Parser._is_text_block_tag(grandchild):
                        return grandchild
        return None

    @staticmethod
    def _extract_text_block_info(el: Tag) -> Optional[TextBlockInfo]:
        if not isinstance(el, Tag):
            return None
        name = el.get('name', '')
        if not name or 'TextBlock' not in name:
            return None

        tag_text = el.get_text(strip=True) or ''

        if tag_text and len(tag_text) < 200:
            title = tag_text
        else:
            name_part = name.split(':')[-1].replace('TextBlock', '')
            title = re.sub(r'([A-Z])', r' \1', name_part).strip()
            title = re.sub(r'\s+', ' ', title)

        return TextBlockInfo(name=name, title=title)

    @staticmethod
    def _is_continuation_tag(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        return el.name in ('ix:continuation', 'continuation')

    @staticmethod
    def _is_bold(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        style = (el.get("style") or "").lower()
        return (
                "font-weight:700" in style
                or "font-weight:bold" in style
                or el.name in BOLD_TAGS
        )

    @staticmethod
    def _is_italic(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        style = (el.get("style") or "").lower()
        return (
                "font-style:italic" in style
                or el.name in ITALIC_TAGS
        )

    @staticmethod
    def _is_block(el: Tag) -> bool:
        return isinstance(el, Tag) and el.name in BLOCK_TAGS

    @staticmethod
    def _is_absolutely_positioned(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        style = (el.get("style") or "").lower().replace(" ", "")
        return "position:absolute" in style

    @staticmethod
    def _extract_top_px(el: Tag, fallback_height: float = 10000.0) -> Optional[float]:
        """Extract Y position from top: or bottom: CSS."""
        if not isinstance(el, Tag):
            return None
        style = el.get("style", "")
        m_top = re.search(r'top:\s*(\d+(?:\.\d+)?)px', style)
        if m_top:
            return float(m_top.group(1))
        m_bot = re.search(r'bottom:\s*(\d+(?:\.\d+)?)px', style)
        if m_bot:
            return fallback_height - float(m_bot.group(1))
        return None

    @staticmethod
    def _is_inline_display(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        style = (el.get("style") or "").lower().replace(" ", "")
        return "display:inline-block" in style or "display:inline;" in style

    @staticmethod
    def _has_break_before(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        style = (el.get("style") or "").lower().replace(" ", "")
        return (
                "page-break-before:always" in style
                or "break-before:page" in style
                or "break-before:always" in style
        )

    @staticmethod
    def _has_break_after(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        style = (el.get("style") or "").lower().replace(" ", "")
        return (
                "page-break-after:always" in style
                or "break-after:page" in style
                or "break-after:always" in style
        )

    @staticmethod
    def _is_hidden(el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False
        style = (el.get("style") or "").lower().replace(" ", "")
        return "display:none" in style

    @staticmethod
    def _wrap_markdown(el: Tag) -> str:
        bold = Parser._is_bold(el)
        italic = Parser._is_italic(el)
        if bold and italic:
            return "***"
        if bold:
            return "**"
        if italic:
            return "*"
        return ""

    @staticmethod
    def _is_plausible_page_number(num: int, min_val: int = 1) -> bool:
        return min_val <= num <= 9999 and not (1900 <= num <= 2100)

    @staticmethod
    def _is_markdown_table_line(line: str) -> bool:
        """A Markdown table row (it starts with '|') or a table divider row."""
        stripped = line.strip()
        return stripped.startswith("|") or bool(_MARKDOWN_TABLE_DIVIDER_RE.match(stripped))

    def _try_merge_inline_spans(self, last_text: str, current_text: str, last_source: Optional[Tag],
                                 current_source: Optional[Tag]) -> Optional[str]:
        if not (last_source and current_source and
                isinstance(last_source, Tag) and isinstance(current_source, Tag)):
            return None

        if last_source.parent is not current_source.parent:
            return None

        last_stripped = last_text.rstrip()
        current_stripped = current_text.lstrip()

        # Merge **text** **text** -> **text text**
        if last_stripped.endswith('**') and current_stripped.startswith('**'):
            last_ws = last_text[len(last_stripped):]
            current_ws = current_text[:len(current_text) - len(current_stripped)]
            return last_stripped[:-2] + last_ws + current_ws + current_stripped[2:]

        # Merge *text* *text* -> *text text* (but not bold)
        if (last_stripped.endswith('*') and current_stripped.startswith('*') and
            not last_stripped.endswith('**')):
            last_ws = last_text[len(last_stripped):]
            current_ws = current_text[:len(current_text) - len(current_stripped)]
            return last_stripped[:-1] + last_ws + current_ws + current_stripped[1:]

        return None

    @staticmethod
    def _last_source_node(source_ref: Optional[Tag] | Sequence[Tag]) -> Optional[Tag]:
        if isinstance(source_ref, Tag):
            return source_ref
        if source_ref:
            return source_ref[-1]
        return None

    @staticmethod
    def _source_nodes(source_ref: Optional[Tag] | Sequence[Tag]) -> Sequence[Tag]:
        if isinstance(source_ref, Tag):
            return (source_ref,)
        return source_ref or ()

    def _append(
        self,
        page_num: int,
        s: str,
        source_node: Optional[Tag] = None,
        text_block: Optional[TextBlockInfo] = None,
        source_nodes: Sequence[Tag] | None = None,
    ) -> None:
        if not s:
            return

        tb = text_block if text_block is not None else self.current_text_block

        buf = self.pages[page_num]
        seg_buf = self.page_segments[page_num]

        if buf and seg_buf:
            last_text = buf[-1]
            last_seg = seg_buf[-1]
            last_source_ref = last_seg[1]
            last_source = self._last_source_node(last_source_ref)
            current_source_nodes = (
                source_nodes if source_nodes is not None
                else ((source_node,) if source_node else ())
            )

            merged = self._try_merge_inline_spans(last_text, s, last_source, source_node)
            if merged:
                buf[-1] = merged
                seg_buf[-1] = (
                    self._element_segment_content(merged, source_node),
                    ordered_unique_nodes(self._source_nodes(last_source_ref), current_source_nodes),
                    last_seg[2],
                )
                return

        self.pages[page_num].append(s)
        current_nodes = ordered_unique_nodes(
            (source_node,) if source_node else (),
            source_nodes or (),
        )
        source_ref: Optional[Tag] | Sequence[Tag] = (
            current_nodes if source_nodes is not None else source_node
        )
        self.page_segments[page_num].append((self._element_segment_content(s, source_node), source_ref, tb))

    def _blankline_before(self, page_num: int) -> None:
        buf = self.pages[page_num]
        seg_buf = self.page_segments[page_num]
        if not buf:
            return
        if not buf[-1].endswith("\n"):
            buf.append("\n")
            seg_buf.append(("\n", None, self.current_text_block))
        if len(buf) >= 2 and buf[-1] == "\n" and buf[-2] == "\n":
            return
        buf.append("\n")
        seg_buf.append(("\n", None, self.current_text_block))

    def _blankline_after(self, page_num: int) -> None:
        self._blankline_before(page_num)

    def _process_text_node(self, node: NavigableString) -> str:
        text = clean_text(str(node))
        if text and _css_decl.match(text):
            return ""
        return text

    def _element_segment_content(self, text: str, source_node: Optional[Tag] = None) -> str:
        """Keep link labels in citation content but exclude non-visible destinations.

        A table's header record is bound here, from the render that supplies the content:
        the anchor-stripped re-render for a table with links, else the normal render.
        """

        if source_node is not None and id(source_node) in self._unreliable_tables:
            return self._unreliable_tables[id(source_node)].original_text

        if source_node is not None and source_node.name == "table":
            content, record = self._table_segment(source_node, text)
            self._render_header_records.pop(id(source_node), None)
            self._bind_header_record(source_node, content, record)
            return content

        return MARKDOWN_LINK_RE.sub(r"\1", text)

    def _table_segment(self, table: Tag, rendered: str) -> tuple[str, TableHeaderRecord | None]:
        """A table's own segment, and the record of the render that supplies it (R6a step 2).

        For a table with links, the anchor-stripped re-render and its record. Otherwise the
        normal render ``rendered`` with link syntax reduced to labels, and that render's
        pending record. Nothing is bound or discarded here.
        """

        if table.find("a") is not None:
            legacy_table = deepcopy(table)
            for anchor in legacy_table.find_all("a"):
                anchor.unwrap()
            legacy_parser = TableParser(legacy_table)
            return legacy_parser.md().strip(), legacy_parser.header_record
        _, record = self._render_header_records.get(id(table), (table, None))
        return MARKDOWN_LINK_RE.sub(r"\1", rendered), record

    def _bind_header_record(
        self, table: Tag, segment: str, record: TableHeaderRecord | None, *, wrapped: bool = False
    ) -> None:
        """Bind a render's header record to its original table node (spec R6a).

        A table without a written header line has nothing to account for.
        """

        if record is None or record.header_line is None:
            return
        self._header_records[id(table)] = ElementHeaderRecord(
            segment=segment,
            header_line=record.header_line,
            header_source=record.header_source,
            header_capacity=record.header_capacity,
            header_cells=record.header_cells,
            wrapped=wrapped,
        )

    def _process_wrapper(self, wrapper: Tag) -> tuple[str, list[tuple[Tag, str]]]:
        """Render a list or an inline wrapper, with the tables rendered inside it.

        Each table that left a pending header record comes with its normal render, which the
        wrapper's text holds verbatim (revision 18).
        """

        previous, self._table_collector = self._table_collector, []
        try:
            return self._process_element(wrapper), self._table_collector
        finally:
            self._table_collector = previous

    def _note_wrapped_tables(self, page_num: int, wrapper: Tag, tables: list[tuple[Tag, str]]) -> None:
        """Note where the wrapper just appended (or merged) its segment, to bind its tables.

        ``_append`` adds a segment or merges into the last one in place, so the position
        stays the wrapper's segment while later appends merge into it or follow it.
        """

        if tables:
            index = len(self.page_segments[page_num]) - 1
            self._wrapped_renders.append((page_num, index, wrapper, tables))

    def _bind_wrapped_header_records(self) -> None:
        """Bind the header records of tables rendered inside wrappers (spec R6a, revision 18).

        Each table takes its record by the step-2 rule, as a table segment does. It is bound,
        marked wrapped, only when the wrapper's final segment still holds the table's own
        copy (``_wrapped_copy_survives``). Otherwise its record stays unbound, so it is a
        missing association and strict keeps the ordinary trace. Runs once, after streaming,
        when no later append can merge into a wrapper's segment.
        """

        for page_num, index, wrapper, tables in self._wrapped_renders:
            raw = self.pages[page_num][index]
            content = self.page_segments[page_num][index][0]
            links = [
                (match.start(), match.end(), len(match.group(0)) - len(match.group(1)))
                for match in MARKDOWN_LINK_RE.finditer(raw)
            ]
            # The final segment must be the link reduction of the wrapper's text and nothing else.
            only_reduced = MARKDOWN_LINK_RE.sub(r"\1", raw) == content
            for table, rendered in tables:
                segment, record = self._table_segment(table, rendered)
                if record is None or record.header_line is None:
                    self._render_header_records.pop(id(table), None)
                elif only_reduced and _wrapped_copy_survives(raw, content, rendered, segment, links):
                    self._render_header_records.pop(id(table), None)
                    self._bind_header_record(table, segment, record, wrapped=True)
                    self._wrapped_tables.setdefault(id(wrapper), []).append(table)
                else:
                    self._render_header_records[id(table)] = (table, record)

    def element_header_records(self, element_id: str) -> tuple[ElementHeaderRecord, ...]:
        """The bound header records (spec R6a) of the tables mapped to one element.

        A mapped table's own record, and for a mapped list or inline wrapper the records of
        the tables rendered inside it (revision 18), in document order. In mapped-node
        order; empty for an unknown element or one without a table record. Valid after
        ``get_pages(include_elements=True)``.
        """

        records: list[ElementHeaderRecord] = []
        for node in self.block_nodes_map.get(element_id, ()):
            if id(node) in self._header_records:
                records.append(self._header_records[id(node)])
            records.extend(
                self._header_records[id(table)] for table in self._wrapped_tables.get(id(node), ())
            )
        return tuple(records)

    @staticmethod
    def _img_to_markdown(el: Tag) -> str:
        """Convert an <img> tag to markdown image syntax."""
        src = el.get("src", "")
        alt = el.get("alt", "")
        if not src:
            return ""
        return f"![{alt}]({src})"

    def _render_table(self, element: Tag) -> str:
        # A stream-root table's rows were already computed for its snapshot ordinal.
        eff_rows = self._root_table_rows.pop(id(element), None)
        if id(element) in self._unreliable_tables:
            self.includes_table = True
            return self._unreliable_tables[id(element)].original_text
        if eff_rows is None:
            eff_rows = self._effective_rows(element)
        if len(eff_rows) <= 1:
            cells = eff_rows[0] if eff_rows else []
            return self._one_row_table_to_text(cells)

        self.includes_table = True
        table_parser = TableParser(element, base_url=self.source_url)
        if self.table_checks:
            # A cell with a link is extracted by the check itself, against the same base URL.
            self._cell_texts.update(
                (id(cell.node), cell.text)
                for row in table_parser.cells for cell in row
                if cell.node is not None and "](" not in cell.text
            )
        rendered = table_parser.md().strip()
        self._render_header_records[id(element)] = (element, table_parser.header_record)
        if self._table_collector is not None:
            self._table_collector.append((element, rendered))
        return rendered

    def _process_element(self, element: Union[Tag, NavigableString]) -> str:
        if isinstance(element, NavigableString):
            return self._process_text_node(element)

        if element.name == "img":
            if self.include_images:
                return self._img_to_markdown(element)
            return ""

        if element.name == "table":
            rendered = self._render_table(element)
            if self.table_checks and element.find_parent("table") is None:
                self.table_outputs[id(element)] = rendered
            return rendered

        if element.name in {"ul", "ol"}:
            items = []
            for li in element.find_all("li", recursive=False):
                item_text = self._process_element(li).strip()
                if item_text:
                    item_text = item_text.lstrip("•·∙◦▪▫-").strip()
                    items.append(item_text)
            if not items:
                return ""
            if element.name == "ol":
                return "\n".join(f"{i + 1}. {t}" for i, t in enumerate(items))
            return "\n".join(f"- {t}" for t in items)

        if element.name == "li":
            parts = [self._process_element(c) for c in element.children]
            return " ".join(p for p in parts if p).strip()

        parts: List[str] = []
        for child in element.children:
            if isinstance(child, NavigableString):
                t = self._process_text_node(child)
                if t:
                    parts.append(t)
            else:
                t = self._process_element(child)
                if t:
                    parts.append(t)

        text = " ".join(p for p in parts if p).strip()
        if not text:
            return ""

        wrap = self._wrap_markdown(element)
        return f"{wrap}{text}{wrap}" if wrap else text

    def _extract_page_number_from_footer(self, footer_el: Tag) -> Optional[int]:
        text = footer_el.get_text(" ", strip=True)
        if not text:
            return None

        m = re.search(r'\|\s*(\d{1,4})\s*$', text)
        if m:
            num = int(m.group(1))
            if self._is_plausible_page_number(num):
                return num

        m = re.search(r'\bPage\s+(\d{1,4})\b', text, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            if self._is_plausible_page_number(num):
                return num

        m = re.search(r'\b(\d{1,4})\s*$', text)
        if m:
            num = int(m.group(1))
            if self._is_plausible_page_number(num, min_val=10):
                return num

        return None

    def _is_footer_element(self, el: Tag) -> bool:
        if not isinstance(el, Tag):
            return False

        style = (el.get("style") or "").lower().replace(" ", "")

        if not ("position:absolute" in style and "bottom:0" in style):
            return False

        if "width:100%" in style:
            return True

        text = el.get_text(" ", strip=True)
        if text and len(text) < 200:
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in ["form 10-k", "form 10-q", "form 8-k", "page"]):
                return True

        return False

    def _extract_absolutely_positioned_children(self, container: Tag) -> List[Tag]:
        positioned_children = []
        for child in container.children:
            if isinstance(child, Tag) and self._is_absolutely_positioned(child):
                if child.get_text(strip=True) or AbsolutelyPositionedTableParser._is_spacer(child):
                    positioned_children.append(child)
        return positioned_children

    def _compute_line_gaps(self, elements: List[Tag]) -> List[float]:
        y_positions = []
        for el in elements:
            y = self._extract_top_px(el)
            if y is not None:
                y_positions.append(y)

        if len(y_positions) < 2:
            return []

        y_positions.sort()
        gaps = [y_positions[i + 1] - y_positions[i] for i in range(len(y_positions) - 1)]
        return [g for g in gaps if 5 < g < 100]

    def _split_positioned_groups(self, elements: List[Tag], gap_threshold: Optional[float] = None) -> List[List[Tag]]:
        """Split positioned elements into groups using adaptive gap threshold."""
        if not elements:
            return []

        if gap_threshold is None:
            line_gaps = self._compute_line_gaps(elements)
            if line_gaps:
                median_gap = median(line_gaps)
                gap_threshold = min(1.2 * median_gap, 30.0)
                logger.debug(f"Adaptive gap threshold: {gap_threshold:.1f}px (median line gap: {median_gap:.1f}px)")
            else:
                gap_threshold = 30.0

        element_positions = []
        for el in elements:
            y = self._extract_top_px(el)
            if y is not None:
                element_positions.append((y, el))

        if not element_positions:
            return [elements]

        element_positions.sort(key=lambda x: x[0])

        groups = []
        current_group = [element_positions[0][1]]
        last_y = element_positions[0][0]

        for y, el in element_positions[1:]:
            if y - last_y > gap_threshold:
                if current_group:
                    groups.append(current_group)
                current_group = [el]
            else:
                current_group.append(el)
            last_y = y

        if current_group:
            groups.append(current_group)

        final_groups = []
        for group in groups:
            final_groups.extend(self._split_by_column_transition(group))

        logger.debug(f"Split {len(elements)} elements into {len(final_groups)} groups (threshold: {gap_threshold:.1f}px)")
        return final_groups

    def _split_by_column_transition(self, elements: List[Tag]) -> List[List[Tag]]:
        """Split a group if it transitions from multi-column to single-column."""
        if len(elements) < 6:
            return [elements]

        element_data = []
        for el in elements:
            style = el.get("style", "")
            left_match = re.search(r'left:\s*(\d+(?:\.\d+)?)px', style)
            y = self._extract_top_px(el)
            if left_match and y is not None:
                element_data.append((float(left_match.group(1)), y, el))

        if not element_data:
            return [elements]

        element_data.sort(key=lambda x: x[1])

        rows = []
        current_row = [element_data[0]]
        last_y = element_data[0][1]

        for left, top, el in element_data[1:]:
            if abs(top - last_y) <= 15:
                current_row.append((left, top, el))
            else:
                rows.append(current_row)
                current_row = [(left, top, el)]
                last_y = top

        if current_row:
            rows.append(current_row)

        def count_columns(row):
            return len(set(left for left, _, _ in row))

        split_point = None
        for i in range(len(rows) - 3):
            current_cols = count_columns(rows[i])
            next_cols = count_columns(rows[i + 1])

            if current_cols >= 2 and next_cols == 1:
                following_single = sum(1 for j in range(i + 1, min(i + 4, len(rows)))
                                       if count_columns(rows[j]) == 1)
                if following_single >= 2:
                    split_point = i + 1
                    logger.debug(f"Column transition at row {i + 1} ({current_cols} cols -> {next_cols} col)")
                    break

        if split_point is None:
            return [elements]

        split_y = rows[split_point][0][1]

        group1 = [el for left, top, el in element_data if top < split_y]
        group2 = [el for left, top, el in element_data if top >= split_y]

        result = []
        if group1:
            result.append(group1)
        if group2:
            result.append(group2)

        return result if result else [elements]

    def _process_absolutely_positioned_container(self, container: Tag, page_num: int) -> int:
        positioned_children = self._extract_absolutely_positioned_children(container)

        if not positioned_children:
            current = page_num
            for child in container.children:
                current = self._stream_pages(child, current)
            return current

        content_elements = []

        for child in positioned_children:
            if self._is_footer_element(child):
                display_page = self._extract_page_number_from_footer(child)
                if display_page is not None:
                    self.footer_page_numbers[page_num] = display_page
                    logger.debug(f"Extracted display_page={display_page} from footer on page {page_num}")
            else:
                content_elements.append(child)

        if not content_elements:
            return page_num

        groups = self._split_positioned_groups(content_elements)

        for i, group in enumerate(groups):
            table_parser = AbsolutelyPositionedTableParser(group)

            if table_parser.is_table_like():
                self.includes_table = True
                self._snapshot_ordinal += 1
                if self.capture_tables:
                    self.table_snapshots.append(snapshot_positioned_table(
                        group, ordinal=self._snapshot_ordinal, page=page_num,
                        source_url=self.source_url, native_anchors=self._native_anchors,
                        note_targets=self._note_targets,
                    ))
                    self._snapshot_nodes.append(tuple(group))
                markdown_table = table_parser.to_markdown()
                if markdown_table:
                    self._append(
                        page_num,
                        markdown_table,
                        source_node=group[0] if group else None,
                        source_nodes=group,
                    )
                    self._blankline_after(page_num)
            else:
                text = table_parser.to_text()
                if text:
                    if i > 0:
                        self._blankline_before(page_num)
                    self._append(
                        page_num,
                        text,
                        source_node=group[0] if group else None,
                        source_nodes=group,
                    )

        return page_num

    def _restore_text_block(self, started: bool, has_continuation: bool,
                            ends_block: bool, previous: Optional[TextBlockInfo]) -> None:
        if started and not has_continuation:
            self.current_text_block = None if ends_block else previous

    def _stream_pages(self, root: Union[Tag, NavigableString], page_num: int = 1) -> int:
        """Walk the DOM once; split only on CSS break styles."""
        if isinstance(root, Tag) and self._has_break_before(root):
            page_num += 1

        if isinstance(root, NavigableString):
            t = self._process_text_node(root)
            if t:
                parent = root.parent if isinstance(root.parent, Tag) else None
                self._append(page_num, t + " ", source_node=parent)
            return page_num

        if not isinstance(root, Tag):
            return page_num

        if self._is_hidden(root):
            return page_num

        if root.name == "img" and self.include_images:
            md = self._img_to_markdown(root)
            if md:
                self._blankline_before(page_num)
                self._append(page_num, md, source_node=root)
                self._blankline_after(page_num)
            return page_num

        text_block_started = False
        text_block_has_continuation = False
        continuation_ends_text_block = False
        previous_text_block = self.current_text_block

        if self._is_continuation_tag(root):
            cont_id = root.get('id')
            if cont_id and cont_id in self.continuation_map:
                self.current_text_block = self.continuation_map[cont_id]
                text_block_started = True
                continuedat = root.get('continuedat')
                if continuedat:
                    text_block_has_continuation = True
                    self.continuation_map[continuedat] = self.current_text_block
                else:
                    continuation_ends_text_block = True

        is_absolutely_positioned = self._is_absolutely_positioned(root)
        has_positioned_children = not is_absolutely_positioned and any(
            isinstance(child, Tag) and self._is_absolutely_positioned(child)
            for child in root.children
        )

        if has_positioned_children and root.name == "div":
            current = self._process_absolutely_positioned_container(root, page_num)
            if self._has_break_after(root):
                current += 1
            self._restore_text_block(text_block_started, text_block_has_continuation,
                                     continuation_ends_text_block, previous_text_block)
            return current

        is_inline_display = self._is_inline_display(root)
        is_block = (self._is_block(root) and root.name not in {"br", "hr"}
                    and not is_inline_display and not is_absolutely_positioned)

        # Check block elements for new TextBlocks (allows new notes to replace old ones across pages)
        if is_block:
            tb_tag = self._find_text_block_tag_in_children(root)
            if tb_tag:
                tb_info = self._extract_text_block_info(tb_tag)
                if tb_info:
                    is_new = (self.current_text_block is None or
                              self.current_text_block.name != tb_info.name)
                    if is_new:
                        self.current_text_block = tb_info
                        text_block_started = True
                        continuedat = tb_tag.get('continuedat')
                        if continuedat:
                            text_block_has_continuation = True
                            self.continuation_map[continuedat] = tb_info

        if is_block:
            self._blankline_before(page_num)

        if root.name in {"table", "ul", "ol"}:
            # Ordinals count the tables that get a snapshot in capture mode, in every
            # mode, so table-completeness findings name the same snapshot either way.
            snapshot_ordinal = None
            if root.name == 'table' and (self.capture_tables or self.table_checks):
                self._table_pages.setdefault(id(root), page_num)
                rows = self._effective_rows(root)
                self._root_table_rows[id(root)] = rows
                if len(rows) > 1:
                    self._snapshot_ordinal += 1
                    snapshot_ordinal = self._snapshot_ordinal
                    self._snapshot_ordinals[id(root)] = snapshot_ordinal
            if self.capture_tables and snapshot_ordinal is not None:
                snapshot = snapshot_html_table(
                    root, ordinal=snapshot_ordinal, page=page_num,
                    source_url=self.source_url, native_anchors=self._native_anchors,
                    note_targets=self._note_targets,
                )
                self.table_snapshots.append(snapshot)
                self._snapshot_nodes.append((root,))
                # Every HTML structural issue invalidates legacy grid safety,
                # including nested descendants outside direct-cell validation.
                if snapshot.issues:
                    self._unreliable_tables[id(root)] = snapshot
            # A table's record is bound with its own segment; a list's tables, from its segment.
            if root.name == "table":
                t, tables = self._process_element(root), []
            else:
                t, tables = self._process_wrapper(root)
            if t:
                self._append(page_num, t, source_node=root)
                self._note_wrapped_tables(page_num, root, tables)
            self._blankline_after(page_num)
            if self._has_break_after(root):
                page_num += 1
            self._restore_text_block(text_block_started, text_block_has_continuation,
                                     continuation_ends_text_block, previous_text_block)
            return page_num

        wrap = self._wrap_markdown(root)
        if wrap and not is_block:
            t, tables = self._process_wrapper(root)
            if t:
                self._append(page_num, t + " ", source_node=root)
                self._note_wrapped_tables(page_num, root, tables)
            if self._has_break_after(root):
                page_num += 1
            self._restore_text_block(text_block_started, text_block_has_continuation,
                                     continuation_ends_text_block, previous_text_block)
            return page_num

        current = page_num
        for child in root.children:
            current = self._stream_pages(child, current)

        if is_block:
            self._blankline_after(current)

        if self._has_break_after(root):
            current += 1

        self._restore_text_block(text_block_started, text_block_has_continuation,
                                 continuation_ends_text_block, previous_text_block)
        return current

    def _detect_display_page_numbers(self, pages: List[Page]) -> List[Page]:
        if not pages:
            return pages

        if self.footer_page_numbers:
            logger.debug(f"Using {len(self.footer_page_numbers)} footer-extracted page numbers")
            for page in pages:
                if page.number in self.footer_page_numbers:
                    page.display_page = self.footer_page_numbers[page.number]
            return pages

        candidates: List[Tuple[int, Optional[int]]] = []

        for page in pages:
            candidate = self._extract_page_number_from_content(page.content)
            candidates.append((page.number, candidate))

        if self._validate_page_number_sequence(candidates):
            for page in pages:
                idx = page.number - 1
                if idx < len(candidates):
                    page.display_page = candidates[idx][1]

        return pages

    def _extract_page_number_from_content(self, content: str) -> Optional[int]:
        if not content:
            return None

        # Table cells are not page numbers ("| 304 | 1,234 |" would read as 304), and table lines
        # must not take the first/last three lines' places either, or rendering a table
        # differently would move the guess.
        lines = [line for line in content.split('\n') if not self._is_markdown_table_line(line)]

        check_lines = []
        if len(lines) >= 3:
            check_lines.extend(lines[:3])
            check_lines.extend(lines[-3:])
        else:
            check_lines = lines

        for line in check_lines:
            line = line.strip()

            if len(line) > 100:
                continue

            if re.match(r'^\d{1,4}$', line):
                num = int(line)
                if self._is_plausible_page_number(num, min_val=10):
                    return num

            patterns = [
                r'\bPage\s+(\d{1,4})\b',
                r'\b(\d{1,4})\s*\|',
                r'\|\s*(\d{1,4})\b',
            ]

            for pattern in patterns:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    num = int(m.group(1))
                    if self._is_plausible_page_number(num):
                        return num

        return None

    def _validate_page_number_sequence(self, candidates: List[Tuple[int, Optional[int]]]) -> bool:
        valid_pairs = [(pnum, dpage) for pnum, dpage in candidates if dpage is not None]

        if len(valid_pairs) < 5:
            return False

        prev_display = None
        increasing_count = 0
        total_transitions = 0

        for _, display_page in valid_pairs:
            if prev_display is not None:
                total_transitions += 1
                if display_page == prev_display + 1:
                    increasing_count += 2
                elif display_page > prev_display:
                    increasing_count += 1
            prev_display = display_page

        if total_transitions == 0:
            return False

        return increasing_count / total_transitions >= 0.8

    @staticmethod
    def _strip_page_breadcrumbs(content: str) -> str:
        """Remove repeated bare PART/ITEM breadcrumbs from page tops."""
        if not content:
            return content

        lines = content.split("\n")
        idx = 0

        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        if idx >= len(lines):
            return content

        part_line = lines[idx].strip()
        if not re.match(r"^(?:\*\*|__)?\s*PART\s+[IVXLC]+\s*(?:\*\*|__)?$", part_line, re.IGNORECASE):
            return content

        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        if idx >= len(lines):
            return content

        item_line = lines[idx].strip()
        # e.g., "ITEM 2" or "ITEM 2, 3, 4" or "ITEM 9, 9A"
        if not re.match(r'^(?:\*\*|__)?\s*ITEM\s+\d{1,2}[A-Z]?(?:\s*,\s*\d{1,2}[A-Z]?)*\s*(?:\*\*|__)?$',
                        item_line,
                        re.IGNORECASE):
            return content

        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        return "\n".join(lines[idx:])

    def get_pages(self, include_elements: bool = True, include_images: bool = True) -> List[Page]:
        self.include_images = include_images
        self.pages = defaultdict(list)
        self.page_segments = defaultdict(list)
        self.includes_table = False
        self.block_nodes_map = {}
        self.trace_numeric_failures = ()
        self._render_header_records = {}
        self._header_records = {}
        self._table_collector = None
        self._wrapped_renders = []
        self._wrapped_tables = {}
        self.header_accounting_misses = ()
        self.table_snapshots = []
        self._snapshot_nodes = []
        self._unreliable_tables = {}
        self.table_outputs = {}
        self._cell_texts = {}
        self._table_pages = {}
        self._snapshot_ordinals = {}
        self._snapshot_ordinal = 0
        self._root_table_rows = {}
        self.table_report = None
        root = self.soup.body if self.soup.body else self.soup
        self._stream_pages(root, page_num=1)
        self._bind_wrapped_header_records()

        result: List[Page] = []
        for page_num in sorted(self.pages.keys()):
            raw = "".join(self.pages[page_num])
            raw = re.sub(r"\n{3,}", "\n\n", raw)

            lines: List[str] = []
            for line in raw.split("\n"):
                line = line.strip()
                if line or (lines and lines[-1]):
                    lines.append(line)
            content = "\n".join(lines).strip()
            content = self._strip_page_breadcrumbs(content).strip()

            result.append(Page(number=page_num, content=content, elements=None))

        total_output_chars = sum(len(p.content) for p in result)
        if self.input_char_count > 0:
            retention = total_output_chars / self.input_char_count
            if retention >= 0.95:
                logger.debug(f"Content retention: {100 * retention:.1f}%")

        result = self._detect_display_page_numbers(result)

        if include_elements:
            result = self._add_elements_to_pages(result)
            self._trace_elements(result)

        if self.capture_tables:
            node_elements = {
                id(node): element_id
                for element_id, nodes in self.block_nodes_map.items()
                for node in nodes
            }
            display_pages = {page.number: page.display_page for page in result}
            self.table_snapshots = [
                replace(snapshot, display_page=(snapshot.display_page if snapshot.display_page is not None
                                                else display_pages.get(snapshot.page)),
                        element_id=next((node_elements[id(node)] for node in nodes
                                         if id(node) in node_elements), None))
                for snapshot, nodes in zip(self.table_snapshots, self._snapshot_nodes)
            ]

        if self.table_checks:
            try:
                self.table_report = check_tables(
                    self.soup, self.table_outputs, self._table_pages, self._snapshot_ordinals,
                    cell_texts=self._cell_texts, base_url=self.source_url,
                )
            except Exception:
                # Phase A is report-only: a defect in the checks must never fail a conversion.
                logger.exception("sec2md table completeness: the checks failed; no table report")
                self.table_report = None

        markdown = "\n\n".join(page.content for page in result if page.content)
        self._last_pages = result
        self.diagnostics = build_diagnostics(
            self.source_text,
            markdown,
            result,
            mapped_element_ids=tuple(
                element_id
                for element_id, nodes in self.block_nodes_map.items()
                if nodes
            ),
            trace_failures=self.trace_numeric_failures,
            enforce_mappings=include_elements,
            table_report=self.table_report,
        )

        return result

    def _trace_elements(self, pages: List[Page]) -> None:
        """Run strict's numeric trace per element, with its tables' header records (R6a).

        A record whose header line cannot be located grants no exemption and is recorded
        in ``header_accounting_misses`` as ``<element id>:<missing|ambiguous>``.
        """

        unbound = self._unbound_header_tables()
        failures: list[str] = []
        misses: list[str] = []
        for page in pages:
            for element in page.elements or ():
                nodes = self.block_nodes_map.get(element.id, ())
                records = list(self.element_header_records(element.id))
                if records:
                    misses.extend(
                        f"{element.id}:{location.miss}"
                        for location in locate_header_lines(element.content, records)
                        if location.miss is not None
                    )
                misses.extend([f"{element.id}:missing"] * unbound[element.id])
                failures.extend(compute_trace_numeric_failures(element, nodes, records))
        self.trace_numeric_failures = tuple(failures)
        self.header_accounting_misses = tuple(misses)

    def _unbound_header_tables(self) -> Counter[str]:
        """Per element, the tables whose header record was never bound: missing associations.

        A table rendered inside a list item or an inline wrapper is bound from the wrapper's
        segment (revision 18), unless the wrapper's final segment does not show the table's
        own copy intact: the final segment is not the link reduction of the wrapper's text (a
        later inline-block table with a link merged into it), a link reduction ran across the
        table's boundaries, or the reduced copy is not the record's segment (a padded link
        label). Every occurrence of the table's render in the wrapper's text is checked, so
        another occurrence that fails the check also leaves it unbound (Codex's
        counterexample: an identical table before it, whose copy a link reduction
        damaged). Such a table, or one whose header line reached content outside any table
        segment, is counted against the element mapped to its nearest ancestor.
        """

        unbound: Counter[str] = Counter()
        if not self._render_header_records:
            return unbound
        node_elements = {
            id(node): element_id for element_id, nodes in self.block_nodes_map.items() for node in nodes
        }
        for table, record in self._render_header_records.values():
            if record is None or record.header_line is None:
                continue
            element_id = next(
                (node_elements[id(parent)] for parent in table.parents if id(parent) in node_elements),
                None,
            )
            if element_id is not None:
                unbound[element_id] += 1
        return unbound

    def _effective_rows(self, table: Tag) -> list[list[Tag]]:
        rows = []
        for tr in table.find_all('tr', recursive=True):
            cells = tr.find_all(['td', 'th'], recursive=False) or tr.find_all(['td', 'th'], recursive=True)
            texts = [clean_text(c.get_text(" ", strip=True)) for c in cells]
            if any(texts):
                rows.append(cells)
        return rows

    def _one_row_table_to_text(self, cells: list[Tag]) -> str:
        """Flatten a one-row table to one line.

        An ITEM label keeps its first non-empty later cell as the title. A PART label is
        normalized and keeps every non-empty later cell (spec R8). Other rows join their
        non-empty cells.
        """
        texts = [
            render_cell_content(c, base_url=self.source_url)
            if c.find("a")
            else clean_text(c.get_text(" ", strip=True))
            for c in cells
        ]
        if not texts:
            return ""

        first = texts[0]
        if (m := ITEM_HEADER_CELL_RE.match(first)):
            num = m.group(1).upper()
            title = next((t for t in texts[1:] if t), "")
            return f"ITEM {num}. {title}".strip()

        if (m := PART_HEADER_CELL_RE.match(first)):
            roman = m.group(1).upper()
            return " ".join([f"PART {roman}", *(t for t in texts[1:] if t)])

        return " ".join(t for t in texts if t).strip()

    def _add_elements_to_pages(self, pages: List[Page]) -> List[Page]:
        result, block_nodes_map = build_elements_for_pages(pages, self.page_segments)
        self.block_nodes_map = block_nodes_map
        page_elements = {}
        for page in result:
            if page.elements:
                page_elements[page.number] = page.elements
        augment_html_with_ids(page_elements, block_nodes_map, self.soup)
        return result

    def markdown(self) -> str:
        pages = self.get_pages()
        return "\n\n".join(page.content for page in pages if page.content)

    def html(self) -> str:
        return str(self.soup)
