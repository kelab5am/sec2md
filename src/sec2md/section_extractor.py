from __future__ import annotations

import re
from typing import List, Optional, Literal, Any

LEAD_WRAP = r'(?:\*\*|__)?\s*(?:</?[^>]+>\s*)*'

PART_PATTERN = re.compile(
    # The numeral may be followed by a dash or colon with no space, as in
    # "PART I—FINANCIAL INFORMATION" (META 10-Qs).
    rf'^\s*{LEAD_WRAP}(PART\s+[IVXLC]+)\b\.?(?:\*\*|__)?(?:\s*$|\s+|\s*[—–:-]\s*)',
    re.IGNORECASE | re.MULTILINE
)
ITEM_PATTERN = re.compile(
    rf'^\s*{LEAD_WRAP}(ITEM)\s+(\d{{1,2}}[A-Z]?)\.?[ \t]*(?:[:.\-–—][ \t]*)?(.*)',
    re.IGNORECASE | re.MULTILINE
)

HEADER_FOOTER_RE = re.compile(
    r'^\s*(?:[A-Z][A-Za-z0-9 .,&\-]+)?\s*\|\s*\d{4}\s+Form\s+10-[KQ]\s*\|\s*\d+\s*$'
)
PAGE_NUM_RE = re.compile(r'^\s*Page\s+\d+\s*(?:of\s+\d+)?\s*$|^\s*\d+\s*$', re.IGNORECASE)
MD_EDGE = re.compile(r'^\s*(?:\*\*|__)\s*|\s*(?:\*\*|__)\s*$')

NBSP, NARROW_NBSP, ZWSP = '\u00A0', '\u202F', '\u200B'

DOT_LEAD_RE = re.compile(r'^.*\.{3,}\s*\d{1,4}\s*$', re.M)  # "... 123"
ITEM_ROWS_RE = re.compile(r'^\s*ITEM\s+\d{1,2}[A-Z]?\.?\b', re.I | re.M)
ITEM_BREADCRUMB_TITLE_RE = re.compile(
    r'^[,\s]*(\d{1,2}[A-Z]?)(\s*,\s*\d{1,2}[A-Z]?)*\s*$',
    re.IGNORECASE
)

FILING_STRUCTURES = {
    "10-K": {
        "PART I": ["ITEM 1", "ITEM 1A", "ITEM 1B", "ITEM 1C", "ITEM 2", "ITEM 3", "ITEM 4"],
        "PART II": ["ITEM 5", "ITEM 6", "ITEM 7", "ITEM 7A", "ITEM 8", "ITEM 9", "ITEM 9A", "ITEM 9B", "ITEM 9C"],
        "PART III": ["ITEM 10", "ITEM 11", "ITEM 12", "ITEM 13", "ITEM 14"],
        "PART IV": ["ITEM 15", "ITEM 16"]
    },
    "10-Q": {
        "PART I": ["ITEM 1", "ITEM 2", "ITEM 3", "ITEM 4"],
        "PART II": ["ITEM 1", "ITEM 1A", "ITEM 2", "ITEM 3", "ITEM 4", "ITEM 5", "ITEM 6"]
    },
    "20-F": {
        "PART I": [
            "ITEM 1", "ITEM 2", "ITEM 3", "ITEM 4", "ITEM 4A", "ITEM 5",
            # Some 20-F filings include items 6-12 in PART I without explicit PART II header
            "ITEM 6", "ITEM 7", "ITEM 8", "ITEM 9", "ITEM 10", "ITEM 11", "ITEM 12", "ITEM 12D"
        ],
        "PART II": [
            "ITEM 13", "ITEM 14", "ITEM 15",
            # include all 16X variants explicitly so validation stays strict
            "ITEM 16", "ITEM 16A", "ITEM 16B", "ITEM 16C", "ITEM 16D", "ITEM 16E", "ITEM 16F", "ITEM 16G", "ITEM 16H",
            "ITEM 16I"
        ],
        "PART III": ["ITEM 17", "ITEM 18", "ITEM 19"]
    }
}


class SectionExtractor:
    def __init__(self, pages: List[Any], filing_type: Optional[Literal["10-K", "10-Q", "20-F", "8-K", "SC 13D", "SC 13G"]] = None,
                 desired_items: Optional[set] = None, debug: bool = False):
        """Extract sections from SEC filings."""
        self.pages = pages
        self.filing_type = filing_type
        self.structure = FILING_STRUCTURES.get(filing_type) if filing_type else None
        self.desired_items = desired_items
        self.debug = debug
        self._toc_locked = False

    def _log(self, msg: str):
        if self.debug:
            print(msg)

    @staticmethod
    def _normalize_section_key(part: Optional[str], item_num: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        part_key = re.sub(r'\s+', ' ', part.upper().strip()) if part else None
        item_key = f"ITEM {item_num.upper()}" if item_num else None
        return part_key, item_key

    @staticmethod
    def _normalize_section(text: str) -> str:
        return re.sub(r'\s+', ' ', text.upper().strip())

    def _clean_lines(self, content: str) -> List[str]:
        """Remove headers, footers, and page navigation."""
        content = content.replace(NBSP, ' ').replace(NARROW_NBSP, ' ').replace(ZWSP, '')
        lines = [ln.rstrip() for ln in content.split('\n')]
        content_str = '\n'.join(lines)

        # TODO: Breadcrumb removal - some filings have "PART II\n\nItem 7" on every page
        # as navigation breadcrumbs, but removing them here breaks section detection for
        # filings that use this pattern as actual section headers (e.g., MSFT 10-K).
        # Solution: Handle breadcrumb removal during HTML parsing stage instead of here.

        # COMMENTED OUT - breaks section detection for some filings
        # content_str = re.sub(
        #     r'^\s*PART\s+[IVXLC]+\s*$\n+^\s*Item\s+\d{1,2}[A-Z]?\s*$\n+',
        #     '',
        #     content_str,
        #     flags=re.MULTILINE
        # )
        #
        # lines_list = content_str.split('\n')
        # filtered_lines = []
        # for line in lines_list:
        #     if re.match(r'^\s*Item\s+\d{1,2}[A-Z]?(?:\s*,\s*\d{1,2}[A-Z]?)*\s*$', line, re.IGNORECASE):
        #         continue
        #     filtered_lines.append(line)
        # content_str = '\n'.join(filtered_lines)

        lines = content_str.split('\n')

        out = []
        for ln in lines:
            if HEADER_FOOTER_RE.match(ln) or PAGE_NUM_RE.match(ln):
                continue
            ln = MD_EDGE.sub('', ln)
            out.append(ln)
        return out

    def _infer_part_for_item(self, filing_type: str, item_key: str) -> Optional[str]:
        """Infer PART from ITEM number (10-K only)."""
        m = re.match(r'ITEM\s+(\d{1,2})', item_key)
        if not m:
            return None
        num = int(m.group(1))
        if filing_type == "10-K":
            if 1 <= num <= 4:
                return "PART I"
            elif 5 <= num <= 9:
                return "PART II"
            elif 10 <= num <= 14:
                return "PART III"
            elif 15 <= num <= 16:
                return "PART IV"
        return None

    @staticmethod
    def _clean_item_title(title: str) -> str:
        title = re.sub(r'^\s*[:.\-–—]\s*', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    def _is_toc(self, content: str, page_num: int = 1) -> bool:
        """Detect table of contents pages."""
        if self._toc_locked or page_num > 5:
            return False

        # Check for traditional TOC patterns (dot leaders, plain ITEM rows)
        item_hits = len(ITEM_ROWS_RE.findall(content))
        leader_hits = len(DOT_LEAD_RE.findall(content))
        if (item_hits >= 3) or (leader_hits >= 3):
            return True

        # Check for table-based TOCs (modern filings)
        # Look for markdown tables with ITEM entries and page numbers
        # Pattern: | ITEM X. | TITLE | PAGE |
        table_item_pattern = re.compile(r'\|\s*ITEM\s+\d{1,2}[A-Z]?\.?\s*\|', re.IGNORECASE)
        table_item_hits = len(table_item_pattern.findall(content))
        if table_item_hits >= 3:
            return True

        # Also check for "TABLE OF CONTENTS" header
        if re.search(r'TABLE\s+OF\s+CONTENTS', content, re.IGNORECASE) and table_item_hits >= 2:
            return True

        return False
    _ITEM_8K_RE = re.compile(
        rf'^\s*{LEAD_WRAP}(ITEM)\s+([1-9]\.\d{{2}}[A-Z]?)\.?[ \t]*(?:[:.\-–—][ \t]*)?(.*)$',
        re.IGNORECASE | re.MULTILINE
    )
    _HARD_STOP_8K_RE = re.compile(r'^\s*(SIGNATURES|EXHIBIT\s+INDEX)\b', re.IGNORECASE | re.MULTILINE)
    _PROMOTE_ITEM_8K_RE = re.compile(r'(?<!\n)(\s)(ITEM\s+[1-9]\.\d{2}[A-Z]?\s*[.:–—-])', re.IGNORECASE)
    _PIPE_ROW_RE = re.compile(r'^\s*\|?\s*([0-9]{1,4}(?:\.[0-9A-Za-z]+)?)\s*\|\s*(.+?)\s*\|?\s*$', re.MULTILINE)
    _SPACE_ROW_RE = re.compile(r'^\s*([0-9]{1,4}(?:\.[0-9A-Za-z]+)?)\s{2,}(.+?)\s*$', re.MULTILINE)
    _HTML_ROW_RE = re.compile(
        r'<tr[^>]*>\s*<t[dh][^>]*>\s*([^<]+?)\s*</t[dh]>\s*<t[dh][^>]*>\s*([^<]+?)\s*</t[dh]>\s*</tr>',
        re.IGNORECASE | re.DOTALL
    )
    _MARKDOWN_LINK_RE = re.compile(r"\[([^]]+)\]\(([^)]+)\)")

    @staticmethod
    def _normalize_8k_item_code(code: str) -> str:
        """Normalize '5.2' -> '5.02', keep suffix 'A' if present."""
        code = code.upper().strip()
        m = re.match(r'^([1-9])\.(\d{1,2})([A-Z]?)$', code)
        if not m:
            return code
        major, minor, suffix = m.groups()
        minor = f"{int(minor):02d}"
        return f"{major}.{minor}{suffix}"

    def _clean_8k_text(self, text: str) -> str:
        """Clean 8-K text and normalize whitespace."""
        text = text.replace(NBSP, " ").replace(NARROW_NBSP, " ").replace(ZWSP, "")
        text = self._PROMOTE_ITEM_8K_RE.sub(r'\n\2', text)

        header_footer_8k = re.compile(
            r'^\s*(Form\s+8\-K|Page\s+\d+(?:\s+of\s+\d+)?|UNITED\s+STATES\s+SECURITIES\s+AND\s+EXCHANGE\s+COMMISSION)\b',
            re.IGNORECASE
        )

        lines: List[str] = []
        for ln in text.splitlines():
            t = ln.strip()
            if header_footer_8k.match(t):
                continue
            t = MD_EDGE.sub("", t)
            if re.fullmatch(r'\|\s*-{3,}\s*\|\s*-{3,}\s*\|?', t):
                continue
            lines.append(t)

        out: List[str] = []
        prev_blank = False
        for ln in lines:
            blank = (ln == "")
            if blank and prev_blank:
                continue
            out.append(ln)
            prev_blank = blank

        return "\n".join(out).strip()

    def _parse_exhibits(self, block: str) -> List[Any]:
        """Parse exhibit table from 9.01 section."""
        from sec2md.models import Exhibit
        rows: List[Exhibit] = []

        def parse_description(value: str) -> tuple[str, Optional[str]]:
            value = value.strip()
            exact_link = re.fullmatch(r"\[([^]]+)\]\(([^)]+)\)", value)
            if exact_link:
                return exact_link.group(1), exact_link.group(2)

            first_link = self._MARKDOWN_LINK_RE.search(value)
            if first_link:
                description = self._MARKDOWN_LINK_RE.sub(
                    lambda match: match.group(1), value
                )
                return re.sub(r"\s+", " ", description).strip(), first_link.group(2)
            return value, None

        for m in self._PIPE_ROW_RE.finditer(block):
            left, right = m.group(1).strip(), m.group(2).strip()
            if not re.match(r'^\d', left):
                continue
            if left.startswith('---') or right.startswith('---'):
                continue
            description, url = parse_description(right)
            rows.append(Exhibit(exhibit_no=left, description=description, url=url))
        if rows:
            return rows

        for m in self._SPACE_ROW_RE.finditer(block):
            left, right = m.group(1).strip(), m.group(2).strip()
            if not re.match(r'^\d', left):
                continue
            description, url = parse_description(right)
            rows.append(Exhibit(exhibit_no=left, description=description, url=url))
        if rows:
            return rows

        for m in self._HTML_ROW_RE.finditer(block):
            left, right = m.group(1).strip(), m.group(2).strip()
            if not re.match(r'^\d', left):
                continue
            description, url = parse_description(right)
            rows.append(Exhibit(exhibit_no=left, description=description, url=url))

        return rows

    def _slice_8k_body(self, doc: str, start_after: int, next_item_start: int) -> str:
        """Slice body text up to earliest hard stop."""
        mstop = self._HARD_STOP_8K_RE.search(doc, pos=start_after, endpos=next_item_start)
        end = mstop.start() if mstop else next_item_start
        return doc[start_after:end].strip()

    def _is_8k_boilerplate_page(self, page_content: str, page_num: int) -> bool:
        """Detect cover, TOC, and signature pages."""
        if page_num == 1:
            return True

        if re.search(r'TABLE OF CONTENTS', page_content, re.IGNORECASE):
            return True

        item_with_page_count = len(re.findall(r'ITEM\s+[1-9]\.\d{2}.*?\|\s*\d+\s*\|', page_content, re.IGNORECASE))
        if item_with_page_count >= 2:
            return True

        if re.search(r'\*\*SIGNATURES\*\*', page_content) and \
           re.search(r'Pursuant to the requirements', page_content, re.IGNORECASE):
            return True

        return False

    def _get_8k_sections(self) -> List[Any]:
        """Extract 8-K sections."""
        from sec2md.models import Section, Page, ITEM_8K_TITLES

        sections = []
        current_item = None
        current_item_title = None
        current_pages: List[Page] = []

        def flush_section():
            nonlocal sections, current_item, current_item_title, current_pages
            if current_pages and current_item:
                exhibits = None
                if current_item.startswith("ITEM 9.01"):
                    content = "\n".join(p.content for p in current_pages)
                    md = re.search(r'^\s*\(?d\)?\s*Exhibits\b.*$', content, re.IGNORECASE | re.MULTILINE)
                    ex_block = content[md.end():].strip() if md else content
                    parsed_exhibits = self._parse_exhibits(ex_block)
                    exhibits = parsed_exhibits if parsed_exhibits else None

                sections.append(Section(
                    part=None,
                    item=current_item,
                    item_title=current_item_title,
                    pages=current_pages,
                    exhibits=exhibits
                ))
                current_pages = []

        for page in self.pages:
            page_num = page.number
            remaining_content = page.content

            if self._is_8k_boilerplate_page(remaining_content, page_num):
                self._log(f"DEBUG: Page {page_num} is boilerplate, skipping")
                continue

            while remaining_content:
                item_m = None
                first_idx = None

                for m in self._ITEM_8K_RE.finditer(remaining_content):
                    line_start = remaining_content.rfind('\n', 0, m.start()) + 1
                    line_end = remaining_content.find('\n', m.end())
                    if line_end == -1:
                        line_end = len(remaining_content)
                    full_line = remaining_content[line_start:line_end].strip()

                    if '|' in full_line:
                        self._log(f"DEBUG: Page {page_num} skipping table row: {full_line[:60]}")
                        continue

                    code = self._normalize_8k_item_code(m.group(2))
                    title_inline = (m.group(3) or "").strip()
                    title_inline = MD_EDGE.sub("", title_inline)

                    item_m = m
                    first_idx = m.start()
                    self._log(f"DEBUG: Page {page_num} found ITEM {code} at position {first_idx}")
                    break

                if first_idx is None:
                    if current_item and remaining_content.strip():
                        current_pages.append(Page(
                            number=page_num,
                            content=remaining_content,
                            elements=page.elements,
                            text_blocks=page.text_blocks,
                            display_page=page.display_page
                        ))
                    break

                before = remaining_content[:first_idx].strip()
                # Use header end position to skip past header and avoid infinite loop
                header_end = item_m.end()
                after = remaining_content[header_end:].strip()

                if current_item and before:
                    current_pages.append(Page(
                        number=page_num,
                        content=before,
                        elements=page.elements,
                        text_blocks=page.text_blocks,
                        display_page=page.display_page
                    ))

                flush_section()

                code = self._normalize_8k_item_code(item_m.group(2))
                title_inline = (item_m.group(3) or "").strip()
                title_inline = MD_EDGE.sub("", title_inline)
                current_item = f"ITEM {code}"
                current_item_title = title_inline if title_inline else ITEM_8K_TITLES.get(code)

                if self.desired_items and code not in self.desired_items:
                    self._log(f"DEBUG: Skipping ITEM {code} (not in desired_items)")
                    current_item = None
                    current_item_title = None
                    remaining_content = after
                    continue

                remaining_content = after

        flush_section()

        self._log(f"DEBUG: Total sections extracted: {len(sections)}")
        return sections

    def _get_13d_sections(self) -> List[Any]:
        """Extract SC 13D / SC 13G sections."""
        from sec2md.models import Section, Page, ITEM_13D_TITLES, ITEM_13G_TITLES

        if self.filing_type == "SC 13G":
            _VALID_ITEMS = {str(i) for i in range(1, 11)}
            _TITLES = ITEM_13G_TITLES
        else:
            _VALID_ITEMS = {str(i) for i in range(1, 8)}
            _TITLES = ITEM_13D_TITLES

        _HARD_STOP_RE = re.compile(
            r'^\s*(?:\*\*|__)?\s*SIGNATURE', re.IGNORECASE | re.MULTILINE
        )

        sections = []
        current_item = None
        current_item_title = None
        current_pages: List[Page] = []

        def flush_section():
            nonlocal sections, current_item, current_item_title, current_pages
            if current_pages and current_item:
                sections.append(Section(
                    part=None,
                    item=current_item,
                    item_title=current_item_title,
                    pages=current_pages
                ))
                current_pages = []

        for page in self.pages:
            page_num = page.number
            remaining_content = page.content

            # Truncate content at SIGNATURE
            hard_stop = _HARD_STOP_RE.search(remaining_content)
            last_page = False
            if hard_stop:
                remaining_content = remaining_content[:hard_stop.start()].strip()
                last_page = True
                if not remaining_content:
                    flush_section()
                    break

            while remaining_content:
                item_m = None
                first_idx = None

                for m in ITEM_PATTERN.finditer(remaining_content):
                    # Skip table rows
                    line_start = remaining_content.rfind('\n', 0, m.start()) + 1
                    line_end = remaining_content.find('\n', m.end())
                    if line_end == -1:
                        line_end = len(remaining_content)
                    full_line = remaining_content[line_start:line_end].strip()

                    if '|' in full_line:
                        self._log(f"DEBUG: Page {page_num} skipping table row: {full_line[:60]}")
                        continue

                    item_num = m.group(2).upper()
                    if item_num not in _VALID_ITEMS:
                        self._log(f"DEBUG: Page {page_num} skipping non-13D item: {item_num}")
                        continue

                    # Skip sub-items like Item 1(a), Item 2(b) — treat as content
                    title_check = (m.group(3) or "").strip()
                    title_check = MD_EDGE.sub("", title_check)
                    if re.match(r'^\([a-z]\)', title_check):
                        # If same item number as current, treat as continuation
                        if current_item == f"ITEM {item_num}":
                            self._log(f"DEBUG: Page {page_num} skipping sub-item {item_num}({title_check[:3]})")
                            continue
                        # If different item, this is the first sub-item of a new item
                        self._log(f"DEBUG: Page {page_num} found ITEM {item_num} (via sub-item)")

                    item_m = m
                    first_idx = m.start()
                    self._log(f"DEBUG: Page {page_num} found ITEM {item_num} at position {first_idx}")
                    break

                if first_idx is None:
                    if current_item and remaining_content.strip():
                        current_pages.append(Page(
                            number=page_num,
                            content=remaining_content,
                            elements=page.elements,
                            text_blocks=page.text_blocks,
                            display_page=page.display_page
                        ))
                    break

                before = remaining_content[:first_idx].strip()
                header_end = item_m.end()
                after = remaining_content[header_end:].strip()

                if current_item and before:
                    current_pages.append(Page(
                        number=page_num,
                        content=before,
                        elements=page.elements,
                        text_blocks=page.text_blocks,
                        display_page=page.display_page
                    ))

                flush_section()

                item_num = item_m.group(2).upper()
                title_inline = (item_m.group(3) or "").strip()
                title_inline = MD_EDGE.sub("", title_inline)
                current_item = f"ITEM {item_num}"
                current_item_title = title_inline if title_inline else _TITLES.get(item_num)

                if self.desired_items and item_num not in self.desired_items:
                    self._log(f"DEBUG: Skipping ITEM {item_num} (not in desired_items)")
                    current_item = None
                    current_item_title = None
                    remaining_content = after
                    continue

                remaining_content = after

            if last_page:
                flush_section()
                break

        flush_section()

        self._log(f"DEBUG: Total 13D sections extracted: {len(sections)}")
        return sections

    def get_sections(self) -> List[Any]:
        """Get sections from the filing."""
        if self.filing_type == "8-K":
            sections = self._get_8k_sections()
        elif self.filing_type in ("SC 13D", "SC 13G"):
            sections = self._get_13d_sections()
        else:
            sections = self._get_standard_sections()
        return self._scope_elements_to_slices(sections)

    def _scope_elements_to_slices(self, sections: List[Any]) -> List[Any]:
        """Give each section page only the elements whose text lies inside it.

        Section pages are slices of a filing page but are built with the whole
        page's element list, and the chunker prefers elements over slice text.
        Without scoping, a section that shares a page with its neighbours
        would chunk their content, element IDs and tags as well.
        """
        from sec2md.models import Page

        originals = {page.number: page for page in self.pages}
        located: dict[int, tuple[str, list]] = {}

        for section in sections:
            for index, page in enumerate(section.pages):
                original = originals.get(page.number)
                if original is None or not original.elements or not page.elements:
                    continue
                if [e.id for e in page.elements] != [e.id for e in original.elements]:
                    continue  # already scoped by the caller
                if page.number not in located:
                    located[page.number] = _locate_elements(original)
                page_text, element_spans = located[page.number]
                section.pages[index] = Page(
                    number=page.number,
                    content=page.content,
                    elements=_elements_in_slice(page.content, page_text, element_spans, original.elements),
                    text_blocks=page.text_blocks,
                    display_page=page.display_page,
                )
        return sections

    def _get_standard_sections(self) -> List[Any]:
        """Extract 10-K/10-Q/20-F sections."""
        from sec2md.models import Section, Page

        sections = []
        current_part = None
        current_item = None
        current_item_title = None
        current_pages: List[Page] = []

        def flush_section():
            nonlocal sections, current_part, current_item, current_item_title, current_pages
            if current_pages:
                sections.append(Section(
                    part=current_part,
                    item=current_item,
                    item_title=current_item_title,
                    pages=current_pages
                ))
                current_pages = []

        for page in self.pages:
            page_num = page.number
            content = page.content

            if self._is_toc(content, page_num):
                self._log(f"DEBUG: Page {page_num} detected as TOC, skipping")
                continue

            lines = self._clean_lines(content)
            joined = "\n".join(lines)

            if not joined.strip():
                self._log(f"DEBUG: Page {page_num} is empty after cleaning")
                continue

            part_m = None
            item_m = None
            first_idx = None
            first_kind = None

            for m in PART_PATTERN.finditer(joined):
                part_m = m
                first_idx = m.start()
                first_kind = 'part'
                self._log(f"DEBUG: Page {page_num} found PART at position {first_idx}: {m.group(1)}")
                break

            for m in ITEM_PATTERN.finditer(joined):
                if first_idx is None or m.start() < first_idx:
                    context_start = max(0, m.start() - 30)
                    context = joined[context_start:m.start()]
                    if re.search(r'\bPart\s+[IVXLC]+', context, re.IGNORECASE):
                        self._log(f"DEBUG: Page {page_num} skipping inline reference at {m.start()}")
                        continue

                    title = (m.group(3) or "").strip()
                    if not title or ITEM_BREADCRUMB_TITLE_RE.match(title):
                        self._log(f"DEBUG: Page {page_num} skipping breadcrumb ITEM {m.group(2)} with title '{title}'")
                        continue

                    item_m = m
                    first_idx = m.start()
                    first_kind = 'item'
                    self._log(f"DEBUG: Page {page_num} found ITEM at position {first_idx}: ITEM {m.group(2)}")
                break

            if first_kind is None:
                self._log(f"DEBUG: Page {page_num} - no header found. In section: {current_part or current_item}")
                if current_part or current_item:
                    if joined.strip():
                        current_pages.append(Page(
                            number=page_num,
                            content=joined,
                            elements=page.elements,
                            text_blocks=page.text_blocks,
                            display_page=page.display_page
                        ))
                continue

            before = joined[:first_idx].strip()
            after = joined[first_idx:].strip()

            if (current_part or current_item) and before:
                current_pages.append(Page(
                    number=page_num,
                    content=before,
                    elements=page.elements,
                    text_blocks=page.text_blocks,
                    display_page=page.display_page
                ))

            flush_section()

            if first_kind == 'part' and part_m:
                part_text = part_m.group(1)
                current_part, _ = self._normalize_section_key(part_text, None)
                current_item = None
                current_item_title = None
            elif first_kind == 'item' and item_m:
                item_num = item_m.group(2)
                title = (item_m.group(3) or "").strip()
                current_item_title = self._clean_item_title(title) if title else None
                if current_part is None and self.filing_type:
                    inferred = self._infer_part_for_item(self.filing_type, f"ITEM {item_num.upper()}")
                    if inferred:
                        current_part = inferred
                        self._log(f"DEBUG: Inferred {inferred} at detection time for ITEM {item_num}")
                _, current_item = self._normalize_section_key(current_part, item_num)

            if after:
                current_pages.append(Page(
                    number=page_num,
                    content=after,
                    elements=page.elements,
                    text_blocks=page.text_blocks,
                    display_page=page.display_page
                ))

                if first_kind == 'part' and part_m:
                    item_after = None
                    for m in ITEM_PATTERN.finditer(after):
                        title_after = (m.group(3) or "").strip()
                        if not title_after or ITEM_BREADCRUMB_TITLE_RE.match(title_after):
                            self._log(f"DEBUG: Page {page_num} skipping breadcrumb ITEM {m.group(2)} after PART with title '{title_after}'")
                            continue
                        item_after = m
                        break
                    if item_after:
                        start = item_after.start()
                        after = after[start:]
                        current_pages[-1] = Page(
                            number=page_num,
                            content=after,
                            elements=page.elements,
                            text_blocks=page.text_blocks,
                            display_page=page.display_page
                        )
                        item_num = item_after.group(2)
                        title = (item_after.group(3) or "").strip()
                        current_item_title = self._clean_item_title(title) if title else None
                        _, current_item = self._normalize_section_key(current_part, item_num)
                        self._log(f"DEBUG: Page {page_num} - promoted PART to ITEM {item_num} (intra-page)")

                tail = after
                while True:
                    next_kind, next_idx, next_part_m, next_item_m = None, None, None, None

                    for m in PART_PATTERN.finditer(tail):
                        if m.start() > 0:
                            next_kind, next_idx, next_part_m = 'part', m.start(), m
                            break
                    for m in ITEM_PATTERN.finditer(tail):
                        if m.start() > 0 and (next_idx is None or m.start() < next_idx):
                            title_tail = (m.group(3) or "").strip()
                            if not title_tail or ITEM_BREADCRUMB_TITLE_RE.match(title_tail):
                                self._log(f"DEBUG: Page {page_num} skipping breadcrumb ITEM {m.group(2)} in tail with title '{title_tail}'")
                                continue
                            next_kind, next_idx, next_item_m = 'item', m.start(), m

                    if next_idx is None:
                        break

                    before_seg = tail[:next_idx].strip()
                    after_seg = tail[next_idx:].strip()

                    if before_seg:
                        current_pages[-1] = Page(
                            number=page_num,
                            content=before_seg,
                            elements=page.elements,
                            text_blocks=page.text_blocks,
                            display_page=page.display_page
                        )
                    flush_section()

                    if next_kind == 'part' and next_part_m:
                        current_part, _ = self._normalize_section_key(next_part_m.group(1), None)
                        current_item = None
                        current_item_title = None
                        self._log(f"DEBUG: Page {page_num} - intra-page PART transition to {current_part}")
                    elif next_kind == 'item' and next_item_m:
                        item_num = next_item_m.group(2)
                        title = (next_item_m.group(3) or "").strip()
                        current_item_title = self._clean_item_title(title) if title else None
                        if current_part is None and self.filing_type:
                            inferred = self._infer_part_for_item(self.filing_type, f"ITEM {item_num.upper()}")
                            if inferred:
                                current_part = inferred
                                self._log(f"DEBUG: Inferred {inferred} at detection time for ITEM {item_num}")
                        _, current_item = self._normalize_section_key(current_part, item_num)
                        self._log(f"DEBUG: Page {page_num} - intra-page ITEM transition to {current_item}")

                    current_pages.append(Page(
                        number=page_num,
                        content=after_seg,
                        elements=page.elements,
                        text_blocks=page.text_blocks,
                        display_page=page.display_page
                    ))
                    tail = after_seg

        flush_section()

        self._log(f"DEBUG: Total sections before validation: {len(sections)}")
        for s in sections:
            self._log(f"  - Part: {s.part}, Item: {s.item}, Pages: {len(s.pages)}, Start: {s.pages[0].number if s.pages else 0}")

        def _section_text_len(s):
            return sum(len(p.content.strip()) for p in s.pages)

        sections = [s for s in sections if s.item is not None or _section_text_len(s) > 80]
        self._log(f"DEBUG: Sections after dropping empty PART stubs: {len(sections)}")

        if self.structure and sections:
            self._log(f"DEBUG: Validating against structure: {self.filing_type}")
            fixed = []
            for s in sections:
                part = s.part
                item = s.item

                # If part is missing or inconsistent with canonical mapping, try to infer it from the item.
                if item and self.filing_type:
                    inferred = self._infer_part_for_item(self.filing_type, item)
                    if inferred and inferred != part:
                        self._log(f"DEBUG: Rewriting part from {part} to {inferred} for {item}")
                        s = Section(
                            part=inferred,
                            item=s.item,
                            item_title=s.item_title,
                            pages=s.pages
                        )
                        part = inferred

                if (part in self.structure) and (item is None or item in self.structure.get(part, [])):
                    fixed.append(s)
                else:
                    self._log(f"DEBUG: Dropped section - Part: {part}, Item: {item}")

            sections = fixed
            self._log(f"DEBUG: Sections after validation: {len(sections)}")

        return sections

    def get_section(self, part: str, item: Optional[str] = None):
        """Get a specific section by part and item."""
        part_normalized = self._normalize_section(part)
        item_normalized = self._normalize_section(item) if item else None
        sections = self.get_sections()

        for section in sections:
            if section.part == part_normalized:
                if item_normalized is None or section.item == item_normalized:
                    return section
        return None


# ---------------------------------------------------------------------------
# Scoping page elements to section slices
#
# Slice text and element text are compared in a normalized form (lowercase
# letters and digits only), which ignores the Markdown markers, whitespace and
# removed breadcrumb lines that differ between a page, its elements and the
# cleaned section slices.
# ---------------------------------------------------------------------------

_NON_ALNUM_RE = re.compile(r'[^0-9a-z]+')
_ANCHOR_CHARS = 32
# A slice keeps its elements only if they account for this share of its text;
# otherwise it is chunked from its own text, without element IDs.
_MIN_ELEMENT_COVERAGE = 0.8
# A slice this close to the whole page keeps the page's elements as before.
_WHOLE_PAGE_SHARE = 0.95
# Ignore straddling overlaps shorter than this many normalized characters.
_MIN_PARTIAL_CHARS = 16


def _normalize_for_match(text: str) -> str:
    return _NON_ALNUM_RE.sub('', text.lower())


def _find_span(needle: str, haystack: str, start: int = 0) -> Optional[tuple[int, int, bool]]:
    """Locate normalized text exactly, else by its leading and trailing anchors.

    Returns ``(begin, end, exact)``; ``exact`` is False for an anchored match,
    whose length need not equal the needle's.
    """
    if not needle:
        return None
    exact = haystack.find(needle, start)
    if exact != -1:
        return exact, exact + len(needle), True
    if len(needle) <= 2 * _ANCHOR_CHARS:
        return None
    head, tail = needle[:_ANCHOR_CHARS], needle[-_ANCHOR_CHARS:]
    begin = haystack.find(head, start)
    if begin == -1:
        return None
    end = haystack.find(tail, begin + len(head))
    if end == -1 or end + len(tail) - begin > 2 * len(needle) + 2 * _ANCHOR_CHARS:
        return None
    return begin, end + len(tail), False


def _locate_elements(page: Any) -> tuple[str, list[Optional[tuple[int, int, bool]]]]:
    """Normalized page text and each element's span in it, in document order."""
    page_text = _normalize_for_match(page.content)
    spans: list[Optional[tuple[int, int, bool]]] = []
    cursor = 0
    for element in page.elements:
        span = _find_span(_normalize_for_match(element.content), page_text, cursor)
        spans.append(span)
        if span is not None:
            cursor = span[1]
    return page_text, spans


def _trim_element(element: Any, begin: int, end: int) -> Optional[Any]:
    """Copy of an element cut to normalized characters ``begin:end`` of its content.

    The cut widens to whole lines when only Markdown markers lie outside it, so a
    heading such as ``**Item 13. ...**`` keeps its emphasis.
    """
    raw = element.content
    positions = [i for i, ch in enumerate(raw) for low in ch.lower() if low.isascii() and low.isalnum()]
    if begin >= end or end > len(positions):
        return None
    raw_start, raw_end = positions[begin], positions[end - 1] + 1

    line_start = raw.rfind('\n', 0, raw_start) + 1
    if not _NON_ALNUM_RE.sub('', raw[line_start:raw_start].lower()):
        raw_start = line_start
    line_end = raw.find('\n', raw_end)
    line_end = len(raw) if line_end == -1 else line_end
    if not _NON_ALNUM_RE.sub('', raw[raw_end:line_end].lower()):
        raw_end = line_end

    update = {'content': raw[raw_start:raw_end].strip()}
    if element.content_start_offset is not None:
        update['content_start_offset'] = element.content_start_offset + raw_start
        update['content_end_offset'] = element.content_start_offset + raw_end
    return element.model_copy(update=update)


def _elements_in_slice(slice_content: str, page_text: str,
                       spans: list[Optional[tuple[int, int, bool]]], elements: list) -> list:
    """The elements, or the parts of elements, that lie inside one section slice."""
    slice_text = _normalize_for_match(slice_content)
    if not slice_text:
        return []
    slice_span = _find_span(slice_text, page_text)
    if slice_span is None:
        return []
    slice_start, slice_end, _ = slice_span

    selected, covered = [], 0
    for element, span in zip(elements, spans):
        if span is None:
            continue
        begin, end, exact = span
        overlap_start, overlap_end = max(begin, slice_start), min(end, slice_end)
        overlap = overlap_end - overlap_start
        if overlap <= 0:
            continue
        if overlap == end - begin:
            selected.append(element)
        elif exact:
            # An element straddling a section boundary contributes only its own part.
            if overlap < min(_MIN_PARTIAL_CHARS, end - begin):
                continue
            trimmed = _trim_element(element, overlap_start - begin, overlap_end - begin)
            if trimmed is None:
                continue
            selected.append(trimmed)
        elif 2 * overlap > end - begin:
            selected.append(element)
        else:
            continue
        covered += overlap

    if covered >= _MIN_ELEMENT_COVERAGE * len(slice_text):
        return selected
    if len(slice_text) >= _WHOLE_PAGE_SHARE * len(page_text):
        return list(elements)
    return []
