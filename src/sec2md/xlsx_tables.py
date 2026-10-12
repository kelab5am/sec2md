"""Source table records captured before Markdown grid cleanup (no XLSX dependency)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import re
from typing import Literal, Mapping, NamedTuple, Sequence
from urllib.parse import unquote, urljoin

from bs4 import Tag
from bs4.element import Comment, Declaration, Doctype, NavigableString, ProcessingInstruction

from sec2md.absolute_table_parser import AbsolutelyPositionedTableParser
from sec2md.table_parser import EXTENDED, LEGACY, Cell, GridCell, TableParser
from sec2md.xlsx_values import CellValue, convert_cell


@dataclass(frozen=True)
class FactAttributes:
    """An ix:nonFraction in a cell, with its unit resolved through the filing's xbrli:unit
    definitions: sorted measures, and for a divide '/' then the sorted denominator measures."""
    name: str
    unit_measures: tuple[str, ...]
    scale: int | None
    decimals: str | None
    format: str | None
    sign: str | None
    displayed: str


@dataclass(frozen=True)
class SourceCell:
    text: str
    row: int
    column: int
    rowspan: int
    colspan: int
    links: tuple[tuple[str, str], ...]
    is_header: bool
    is_numeric_fact: bool
    source_anchor: str | None = None
    numeric_markers: tuple[str, ...] = ()
    facts: tuple[FactAttributes, ...] = ()


@dataclass(frozen=True)
class TableSnapshot:
    ordinal: int
    page: int
    display_page: int | None
    element_id: str | None
    source_anchor: str | None
    source_cells: tuple[SourceCell, ...]
    original_text: str
    source_kind: Literal['html', 'positioned']
    context_before: tuple[str, ...]
    context_after: tuple[str, ...]
    issues: tuple[str, ...]
    resolved_notes: tuple[tuple[str, str], ...] = ()
    unresolved_references: tuple[str, ...] = ()
    explicit_title: str | None = None


def _hidden(node: Tag) -> bool:
    style = ''.join(str(node.get('style', '')).lower().split())
    return 'display:none' in style or 'visibility:hidden' in style or node.has_attr('hidden')


def _text_fragments(node: Tag) -> str:
    """Keep inline whitespace until all fragments have been assembled."""
    parts = []
    for child in node.children:
        if isinstance(child, (Comment, Declaration, Doctype, ProcessingInstruction)):
            continue
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag) and not _hidden(child) and child.name not in {'script', 'style'}:
            text = _text_fragments(child)
            boundary = child.name in {'br', 'p', 'div', 'tr', 'td', 'th', 'table', 'li'} or _numeric_marker(child)
            parts.append(f' {text} ' if boundary else text)
    return ''.join(parts)


def _visible_text(node: Tag) -> str:
    """Keep inline token fragments together, separating only structural boundaries."""
    return ' '.join(_text_fragments(node).split())


def _numeric_marker(node: Tag) -> bool:
    """Preserve numeric superscript/local-link boundaries, not ordinary spans."""
    return (node.name == 'sup' or (node.name == 'a' and str(node.get('href', '')).startswith('#'))) and bool(
        re.fullmatch(r'\d+', node.get_text().strip()))


def _visible_nodes(node: Tag, names):
    for child in node.find_all(names):
        if not any(_hidden(parent) for parent in (child, *child.parents) if isinstance(parent, Tag)):
            yield child


def _anchor(node: Tag, native_anchors: Mapping[int, str | None] | None) -> str | None:
    return native_anchors.get(id(node)) if native_anchors is not None else node.get('id') or node.get('name')


def _document_root(node):
    root = node
    while isinstance(root.parent, Tag):
        root = root.parent
    return root


def _measures(node) -> tuple[str, ...]:
    return tuple(sorted(measure.get_text().strip() for measure in node.find_all('xbrli:measure')))


def _unit_map(root) -> Mapping[str, tuple[str, ...]]:
    """{unit id: measures} from the document's xbrli:unit definitions, built once per
    document and kept on the root itself, so it lives and dies with that document."""
    if root is None:
        return {}
    units = vars(root).get('_sec2md_unit_map')
    if units is None:
        units = {}
        for unit in root.find_all('xbrli:unit'):
            divide = unit.find('xbrli:divide')
            if divide is not None:
                numerator, denominator = divide.find('xbrli:unitnumerator'), divide.find('xbrli:unitdenominator')
                measures = ((*_measures(numerator), '/', *_measures(denominator))
                            if numerator is not None and denominator is not None else ())
            else:
                measures = _measures(unit)
            if unit.get('id'):
                units[unit.get('id')] = measures
        root._sec2md_unit_map = units
    return units


def _scale(raw) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _fact(node: Tag, units: Mapping[str, tuple[str, ...]]) -> FactAttributes:
    unit = node.get('unitref', node.get('unitRef'))
    return FactAttributes(str(node.get('name') or ''), units.get(unit, ()), _scale(node.get('scale')),
                          node.get('decimals'), node.get('format'), node.get('sign'), _visible_text(node))


def _cell(node, row, column, rowspan, colspan, source_url, native_anchors, units=None):
    return SourceCell(
        _visible_text(node), row, column, rowspan, colspan,
        tuple((_visible_text(a), urljoin(source_url or '', a['href']))
              for a in _visible_nodes(node, 'a') if a.has_attr('href')),
        node.name == 'th', any(_visible_nodes(node, ['ix:nonfraction', 'ix:fraction', 'nonfraction', 'fraction'])),
        _anchor(node, native_anchors),
        tuple(_visible_text(marker) for marker in _visible_nodes(node, ['sup', 'a']) if _numeric_marker(marker)),
        tuple(_fact(fact, units or {}) for fact in _visible_nodes(node, ['ix:nonfraction', 'nonfraction'])),
    )


def _context_siblings(node: Tag, *, before: bool, stop_at_page_end: bool = False):
    """Walk out of presentation wrappers without crossing another table."""
    while isinstance(node, Tag) and node.name not in {'body', 'html', '[document]'}:
        # A footer can be inside a page-ending wrapper, but never beyond it.
        if stop_at_page_end and not before:
            style = ''.join(str(node.get('style', '')).lower().split())
            if re.search(r'(?:^|;)(?:page-break-after|break-after):'
                         r'(?:always|page|left|right|recto|verso)(?:!important)?(?:;|$)', style):
                return
        yield from (node.previous_siblings if before else node.next_siblings)
        node = node.parent


def _printed_footer_after(node: Tag) -> int | None:
    """Capture a nearby explicit source footer, never infer from parser pagination."""
    for index, sibling in enumerate(_context_siblings(node, before=False, stop_at_page_end=True)):
        if index >= 64:
            break
        if not isinstance(sibling, Tag) or _hidden(sibling):
            continue
        nodes = [sibling, *sibling.find_all(True)]
        styles = {id(el): ''.join(str(el.get('style', '')).lower().split()) for el in nodes}
        if any(el.name in {'table', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
               or 'page-break-before:' in styles[id(el)] or 'page-break-after:' in styles[id(el)]
               for el in nodes):
            break
        if len(_visible_text(sibling)) > 4096:
            break
        for footer in nodes:
            if any(_hidden(parent) for parent in (footer, *footer.parents) if isinstance(parent, Tag)):
                continue
            style = styles[id(footer)]
            if 'position:absolute' not in style or not re.search(r'(?:^|;)bottom:0(?:pt|px|%)?(?:;|$)', style):
                continue
            parent_style = ''.join(str(footer.parent.get('style', '')).lower().split())
            if 'position:relative' not in parent_style or not re.search(r'(?:^|;)height:[1-9]', parent_style):
                continue
            centered = any('text-align:center' in styles[id(el)] for el in [footer, *footer.find_all(True)])
            text = _visible_text(footer)
            if centered and re.fullmatch(r'[1-9]\d{0,3}', text) and not 1900 <= int(text) <= 2100:
                return int(text)
    return None


def _context(node: Tag, *, before: bool) -> tuple[str, ...]:
    """Keep nearby blocks in source order, bounded by tables, headings and size."""
    siblings = _context_siblings(node, before=before)
    context = []
    char_count = 0
    headings = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    for sibling in siblings:
        if isinstance(sibling, Tag) and not _hidden(sibling):
            if sibling.name == 'table' or sibling.find('table') is not None:
                break
            is_heading = sibling.name in headings or sibling.get('role') == 'heading'
            if (is_heading and not before) or sibling.find(list(headings)) is not None:
                break
            text = _visible_text(sibling)
            if text:
                if char_count + len(text) > 4096:
                    break
                context.append(text)
                char_count += len(text)
            if is_heading or len(context) >= 12:
                break
    return tuple(reversed(context)) if before else tuple(context)


def _references(nodes, source_url, note_targets):
    notes, unresolved = [], []
    for node in nodes:
        for anchor in _visible_nodes(node, 'a'):
            href = anchor.get('href', '')
            if not href.startswith('#'):
                continue
            if re.search(r'\b(?:accompanying|financial.statement) notes\b', _visible_text(anchor), re.I):
                continue  # A broad notes reference is not an individual note payload.
            target = note_targets.get(unquote(href[1:]))
            destination = urljoin(source_url or '', href)
            if not target:
                unresolved.append(destination)
            else:
                notes.append((destination, target))
    return tuple(dict.fromkeys(notes)), tuple(dict.fromkeys(unresolved))


def _intro_title(text: str) -> str:
    """Trim conventional introductory prose, keeping the source's subject words."""
    text = re.sub(r'^\(\d+\)\s*', '', text.strip())
    text = re.sub(r'^the following table (?:represents|presents|sets forth|summarizes) (?:our |the )?',
                  '', text, flags=re.I)
    text = re.sub(r'^includes\s+', '', text, flags=re.I)
    text = re.split(r'\s+(?:is|are|consisted of|consists of)\s+', text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r'\s+(?:as follows|were as follows)\s*:?$', '', text, flags=re.I).rstrip(':')
    return text[:1].upper() + text[1:]


def _explicit_title(node: Tag) -> str | None:
    caption = node.find('caption', recursive=False)
    if caption is not None:
        return _visible_text(caption)
    context = _context(node, before=True)
    intro = None
    for sibling in _context_siblings(node, before=True):
        if not isinstance(sibling, Tag) or _hidden(sibling):
            continue
        if sibling.name == 'table' or sibling.find('table') is not None:
            break
        text = _visible_text(sibling)
        if text and text not in context:
            break
        if sibling.name in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'} or sibling.get('role') == 'heading':
            return text
        if intro is None and len(text) <= 600 and re.search(r'\bfollowing\b.*:\s*$|\bas follows\s*:', text, re.I):
            intro = _intro_title(text)
        if not text or len(text) > 240 or any(_visible_text(a) for a in sibling.find_all('a', href=True)):
            continue
        if re.fullmatch(r'\(?unaudited\)?|\(?continued\)?', text, re.I) or re.match(
                r'^\(?(?:amounts? )?in (?:dollars|thousands|millions|billions)\b', text, re.I):
            continue
        # SEC filings commonly use bold spans inside DIVs instead of headings.
        # Require the whole block to be styled, not one emphasized word in prose.
        styled = [el for el in (sibling, *sibling.find_all(True))
                  if el.name in {'b', 'strong', 'i', 'em'} or re.search(
                      r'font-weight\s*:\s*(?:bold|[6-9]00)\b|font-style\s*:\s*italic\b',
                      el.get('style', ''), re.I)]
        if any(_visible_text(el) == text for el in styled):
            return text
    return intro


def select_export_tables(snapshots: Sequence[TableSnapshot]) -> tuple[TableSnapshot, ...]:
    """Skip front matter only with a positively identified filing contents table.

    Repeated 'Table of Contents' navigation links alone are not a boundary.
    Without a confirmed index, retain early tables rather than guess a page count.
    """
    boundary = None
    for index, table in enumerate(snapshots):
        links = {href for cell in table.source_cells for _, href in cell.links if '#' in href}
        labels = [cell.text for cell in table.source_cells]
        index_rows = sum(bool(re.search(r'\b(?:item\s+\d|part\s+[ivx]+|financial statements)\b',
                                       text, re.I)) for text in labels)
        titled = any(re.fullmatch(r'(?:table of )?contents', text, re.I)
                     for text in (table.explicit_title or '', *labels))
        continuation = boundary is not None and index == boundary + 1
        if (titled or continuation) and len(links) >= 3 and index_rows >= 2:
            boundary = index
        elif boundary is not None:
            break
    return tuple(snapshots[boundary + 1:] if boundary is not None else snapshots)


def _note_target_text(node: Tag) -> str:
    """Resolve empty anchors only within a small, single-target paragraph."""
    if any(_hidden(parent) for parent in (node, *node.parents) if isinstance(parent, Tag)):
        return ''
    text = _visible_text(node)
    if text:
        return text if len(text) <= 2048 and node.find(['table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']) is None else ''
    paragraph = node.find_parent('p')
    if paragraph is None:
        return ''
    other_targets = [target for target in paragraph.find_all(True)
                     if target is not node and (target.get('id') or target.get('name'))]
    if other_targets:
        return ''
    text = _visible_text(paragraph)
    return text if len(text) <= 2048 else ''


def native_metadata(soup: Tag):
    """Save identity and linked text before element annotation overwrites native IDs."""
    anchors, targets = {}, {}
    for node in soup.find_all(True):
        anchors[id(node)] = node.get('id') or node.get('name')
        for target in set(filter(None, (node.get('id'), node.get('name')))):
            targets[target] = '' if target in targets else _note_target_text(node)
    return anchors, targets


def snapshot_html_table(node: Tag, *, ordinal: int, page: int, source_url: str | None,
                        native_anchors=None, note_targets=None) -> TableSnapshot:
    """Capture direct table ownership and report unreliable spans without clipping."""
    root = _document_root(node)
    if note_targets is None:
        _, note_targets = native_metadata(root)
    units = _unit_map(root)
    rows = [tr for tr in _visible_nodes(node, 'tr') if tr.find_parent('table') is node]
    cells, issues = [], []
    # Intervals avoid expanding a malicious or malformed huge span into a grid.
    occupied: list[tuple[int, int, int, int]] = []
    for row, tr in enumerate(rows):
        column = 0
        for td in _visible_nodes(tr, ['td', 'th']):
            if td.find_parent('tr') is not tr or td.find_parent('table') is not node:
                continue
            while True:
                covering = [end for top, bottom, start, end in occupied if top <= row < bottom and start <= column < end]
                if not covering:
                    break
                column = max(covering)
            spans = []
            for attr in ('rowspan', 'colspan'):
                raw = td.get(attr, '1')
                try:
                    value = int(raw)
                except (ValueError, TypeError):
                    value = 1
                    issues.append(f'Invalid {attr} {raw!r} at ({row}, {column}).')
                if value <= 0 or value > (65534 if attr == 'rowspan' else 1000):
                    issues.append(f'Out-of-range {attr} {raw!r} at ({row}, {column}).')
                spans.append(value)
            rowspan, colspan = spans
            bottom, end = row + max(rowspan, 1), column + max(colspan, 1)
            if bottom > len(rows):
                issues.append(f'Rowspan exceeds source rows at ({row}, {column}).')
            if any(top < bottom and stop > row and start < end and finish > column
                   for top, stop, start, finish in occupied):
                issues.append(f'Span overlap at ({row}, {column}).')
            cells.append(_cell(td, row, column, rowspan, colspan, source_url, native_anchors, units))
            occupied.append((row, bottom, column, end))
            column = end
    flattened_width = max((sum(max(cell.colspan, 1) for cell in cells if cell.row == row)
                           for row in range(len(rows))), default=0)
    if any(cell.column + max(cell.colspan, 1) > flattened_width for cell in cells):
        issues.append('Span displacement exceeds the Markdown grid width; source cells retained.')
    if node.find('table') is not None:
        issues.append('Nested table content requires source-text review.')
    notes, unresolved = _references([node], source_url, note_targets)
    return TableSnapshot(ordinal, page, _printed_footer_after(node), None, _anchor(node, native_anchors), tuple(cells),
                         _visible_text(node), 'html', _context(node, before=True),
                         _context(node, before=False), tuple(issues), notes, unresolved, _explicit_title(node))


def snapshot_positioned_table(nodes: Sequence[Tag], *, ordinal: int, page: int,
                              source_url: str | None, native_anchors=None,
                              note_targets=None) -> TableSnapshot:
    """Use the selected positioned group's grid only when every visible origin is unique."""
    parser = AbsolutelyPositionedTableParser(list(nodes))
    grid = parser.to_grid()
    units = _unit_map(_document_root(nodes[0]) if nodes else None)
    cells, issues, seen = [], [], set()
    if grid is not None:
        for row, entries in enumerate(grid):
            for column, entries_in_cell in enumerate(entries):
                visible = [el for _, _, el in entries_in_cell if _visible_text(el)]
                if len(visible) > 1:
                    issues.append('Ambiguous positioned cell geometry; source_text_only.')
                for el in visible:
                    seen.add(id(el))
                    cells.append(_cell(el, row, column, 1, 1, source_url, native_anchors, units))
    if grid is None or any(_visible_text(el) and id(el) not in seen for el in nodes):
        issues.append('Incomplete positioned grid; source_text_only.')
    if issues:
        cells = []
    if note_targets is None:
        root = nodes[0] if nodes else None
        while root is not None and isinstance(root.parent, Tag):
            root = root.parent
        note_targets = native_metadata(root)[1] if root is not None else {}
    notes, unresolved = _references(nodes, source_url, note_targets)
    return TableSnapshot(ordinal, page, None, None,
                         _anchor(nodes[0], native_anchors) if nodes else None, tuple(cells),
                         '\n'.join(_visible_text(node) for node in nodes), 'positioned',
                         _context(nodes[0], before=True) if nodes else (),
                         _context(nodes[-1], before=False) if nodes else (),
                         tuple(dict.fromkeys(issues)), notes, unresolved)


@dataclass(frozen=True)
class PreparedTable:
    source: TableSnapshot
    title: str
    units: str
    headers: tuple[str, ...]
    rows: tuple[tuple[CellValue, ...], ...]
    cell_sources: tuple[tuple[tuple[tuple[int, int], ...], ...], ...]
    original_rows: tuple[tuple[str, ...], ...]
    notes: tuple[str, ...]
    references: tuple[tuple[str, str], ...]
    issues: tuple[str, ...]
    status: Literal['exported', 'needs_review', 'source_text_only']


_UNITS = re.compile(r'\b(?:in (?:thousands|millions|billions)|per share|percentage of revenue)\b', re.I)
_UNIT_LINE = re.compile(r'^\(?(?:amounts? )?in (?:thousands|millions|billions)\b', re.I)
_UNIT_DECLARATION = re.compile(
    r'\(?(?:(?:amounts? )?in (?:thousands|millions|billions)'
    r'(?:,? except (?:for )?(?:par value|(?:(?:per[- ]share|share|percent(?:age)?)(?: and |, )?)+(?: data| amounts)?))?'
    r'|(?:(?:items |amounts )?expressed as a )?percentage of revenue'
    r'|the following table [^.!?\d]*expressed as a percentage of revenue)\)?\.?', re.I)
_PERCENT = re.compile(r'%|\bpercent(?:age)?\b', re.I)
_PERCENT_UNIT = re.compile(
    r'(?:%|percent(?:age)?|(?:expressed as (?:a )?)?percent(?:age)? of revenue|'
    r'[^\d%]+\(\s*(?:%|percent(?:age)?)\s*\))', re.I)
_ROW_UNIT = re.compile(r'\b(?:per[- ]share|dollars|shares|in (?:thousands|millions|billions))\b', re.I)
_VALUE = re.compile(r'\b(?:amount|value|revenue|income|expense|cost|assets|liabilities|cash|shares|inventory|inventories|earnings|balance|total)\b', re.I)
_IDENTIFIER = re.compile(r'\b(?:id|identifier|code|number|date|year|exhibit|section|zip|cusip|notes?|references?|refs?)\b', re.I)
_MONTH = r'(?:Jan\w*|Feb\w*|Mar\w*|Apr\w*|May|Jun\w*|Jul\w*|Aug\w*|Sep\w*|Oct\w*|Nov\w*|Dec\w*)\.?'
# A duration may name its end month and day with the year on the next header
# row ("Three Months Ended March 31," over "2026 | 2025"), the usual 10-Q layout.
_PERIOD = re.compile(rf'^(?:(?:(?:three|six|nine|twelve) months?|years?) ended(?: {_MONTH} \d{{1,2}},?)?'
                     rf'|(?:19|20)\d{{2}}|{_MONTH} \d{{1,2}},? (?:19|20)\d{{2}})$', re.I)


def _header_count(grid):
    count = 0
    has_heading = False
    for index, row in enumerate(grid):
        origins = list(dict.fromkeys(c for c in row if c is not None))
        nonempty = [c for c in origins if c.text.strip()]
        # TH evidence must describe the row, not merely a body row's label.
        numeric_body = any(c.is_numeric_fact or
                           (re.fullmatch(r'[$(\d+−-][\d,.() $%+−-]*', c.text) and not _PERIOD.fullmatch(c.text))
                           for c in nonempty)
        explicit = bool(nonempty) and all(c.is_header for c in nonempty) and not numeric_body
        # A blank label beneath established headers can belong to numeric data.
        # Unit-only rows do not establish value headings. Otherwise only the
        # initial blank-label layout or a duration span supports TD years.
        blank_label = not row[0] or not row[0].text.strip()
        period_layout = (not has_heading and blank_label) or any(
            c and c.colspan > 1 and re.search(r'\bended\b', c.text, re.I)
            for c in (grid[index - 1] if index else ()))
        periods = period_layout and not numeric_body and bool(nonempty) and all(
            _PERIOD.fullmatch(c.text.strip()) or _UNITS.search(c.text) for c in nonempty)
        unit_row = blank_label and bool(nonempty) and all(_UNIT_DECLARATION.fullmatch(c.text.strip()) for c in nonempty)
        if not (explicit or periods or unit_row or not nonempty):
            break
        if nonempty:
            count = index + 1
            has_heading |= any(not _UNIT_DECLARATION.fullmatch(c.text.strip()) for c in nonempty)
    # Trailing blank rows belong to the body. Wholly blank tables remain data.
    return count


# XLSX header extension (Rules 1 and 2 of the 2026-10-11 header detection spec).
# _header_count and _PERIOD stay as they are: table_completeness reads
# _header_count. A footnoted year ("2023 (2)") is a period in the export only.
_EXPORT_PERIOD = re.compile(rf'^(?:(?:(?:three|six|nine|twelve) months?|years?) ended(?: {_MONTH} \d{{1,2}},?)?'
                            rf'|(?:19|20)\d{{2}}(?: \(\d{{1,2}}\))?|{_MONTH} \d{{1,2}},? (?:19|20)\d{{2}})$', re.I)
_YEAR_TOKEN = re.compile(r'(?:19|20)\d{2}(?:\s*\(\d{1,2}\))?')
_HAS_YEAR = re.compile(r'(?:19|20)\d{2}')
_BODY_NUMBER = re.compile(r'[$(\d+−.-][\d,.() $%+−-]*')
_NIL = re.compile(r'(?:[—–-]+|n/?a|n\.a\.|nm|n/m|not meaningful|\*+)', re.I)
_PERIOD_PHRASE = re.compile(rf'\b(?:years?|months?|quarters?|weeks?|periods?) ended\b'
                            rf'|\b{_MONTH} \d{{1,2}},? (?:19|20)\d{{2}}\b', re.I)
_INSTANT = re.compile(rf'(?:as of |as at )?{_MONTH} \d{{1,2}},?', re.I)
_CURRENCY = re.compile(r'\(?(?:US\$|NT\$|HK\$|RMB|€|£|¥|\$)\)?', re.I)
_SCALE_CAPTION = re.compile(r'\((?:dollars |amounts )?in (?:thousands|millions|billions)[^)]*\)', re.I)
# A label-column caption is a period or unit caption and nothing else, so a line
# item that merely mentions a date ('Cash as of December 31, 2025') is not one.
_CAPTION_PERIOD = re.compile(
    rf'(?:(?:as of|as at|as of or for the|for the)\s+)?'
    rf'(?:(?:(?:three|six|nine|twelve) months?|(?:fiscal )?years?|quarters?) ended,?'
    rf'(?: {_MONTH} \d{{1,2}},?(?: (?:19|20)\d{{2}})?)?'
    rf'|{_MONTH} \d{{1,2}},?(?: (?:19|20)\d{{2}})?)'
    rf'(?:,? \((?:dollars |amounts )?in (?:thousands|millions|billions)[^)]*\))?', re.I)
# Column-heading words seen in the label column of real header rows.
_HEADING_WORD = re.compile(
    r'(?:description|exhibit(?: number| no\.?)?|period|issuance(?: period)?|name(?:/title| of [a-z ]+)?'
    r'|record date|payment date|plan category|instrument|fiscal year|investment type|pricing category'
    r'|range of exercise prices|type|category|item|class|security|date[a-z ]*)(?:\s*\(\d\))?', re.I)
# Period text (revision 6): footnote markers, qualifiers, dates, years, week
# counts, period words and punctuation, and nothing else. Month names are whole
# words here, so 'Market 10' is not a date.
_FOOTNOTE_MARK = re.compile(r'\([a-z\d]{1,2}\)|\*+', re.I)
_PERIOD_QUALIFIER = re.compile(
    r'\((?:unaudited|audited|restated|as restated|as adjusted|as reported|as previously reported)\)', re.I)
_PARENTHESISED = re.compile(r'\([^()]*\)')
_DATE_WORDS = re.compile(r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?'
                         r'|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.? \d{1,2}', re.I)
_NUMERIC_DATE = re.compile(r'\b\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})\b')
_WEEK_COUNT = re.compile(r'\b(?:\d{1,2}|thirteen|twenty[- ]six|thirty[- ]nine|fifty[- ]two|fifty[- ]three)'
                         r'[- ]weeks?\b', re.I)
# Every caption label that names a period is period text: 'or' covers
# 'As of or for the year ended …', which _CAPTION_PERIOD accepts.
_PERIOD_VOCABULARY = re.compile(r'\b(?:three|six|nine|twelve|fiscal|months?|years?|quarters?|weeks?|periods?'
                                r'|ended|ending|as|of|at|for|the|and|or|from|through|to)\b|[,.\-–—]', re.I)


def _row_origins(row):
    return [cell for cell in dict.fromkeys(c for c in row if c is not None) if cell.text.strip()]


def _is_data_cell(cell, digits=False):
    """A body value: a numeric fact, a number other than a bare year or, unless
    digits are required, a nil token such as 'N/A', 'NM' or a dash."""
    text = cell.text.strip()
    if cell.is_numeric_fact:
        return True
    if _YEAR_TOKEN.fullmatch(text):
        return False
    if _BODY_NUMBER.fullmatch(text):
        return not digits or bool(re.search(r'\d', text))
    return not digits and bool(_NIL.fullmatch(text))


def _period_heading(text):
    text = text.strip()
    return bool(_EXPORT_PERIOD.fullmatch(text) or _INSTANT.fullmatch(text) or _PERIOD_PHRASE.search(text))


def _caption_label(text):
    """A whole unit or period caption: '(in millions)', 'December 31,', 'As of'."""
    text = re.sub(r'\s+', ' ', text).strip()
    return bool(_UNIT_DECLARATION.fullmatch(text) or _SCALE_CAPTION.fullmatch(text)
                or re.fullmatch(r'as (?:of|at)', text, re.I) or _CAPTION_PERIOD.fullmatch(text))


def _heading_label(text):
    """A label-column cell that can head a header row ('Description', '(in millions)')."""
    return _caption_label(text) or bool(_HEADING_WORD.fullmatch(re.sub(r'\s+', ' ', text).strip()))


def _period_text(text):
    """Text that only names a period: 'Three months ended March 31, 2025',
    'December 31, 2025 (a)', '2023 (2)', 'Thirteen Weeks Ended May 3, 2025:',
    '12/31/2024', 'Year ended December 31, 2022 (in millions)'. Not 'Balance as of
    December 31, 2024' or 'Fiscal Year' (no date, year or 'ended')."""
    text = re.sub(r'\s+', ' ', text).strip()
    rest = _FOOTNOTE_MARK.sub(' ', text)
    # A unit caption in parentheses: '(in millions)', '(dollars in millions)'.
    rest = _PARENTHESISED.sub(lambda m: ' ' if _UNIT_DECLARATION.fullmatch(m[0]) or _SCALE_CAPTION.fullmatch(m[0])
                              else m[0], rest)
    rest = re.sub(r':$', '', _PERIOD_QUALIFIER.sub(' ', rest).strip())
    for pattern in (_DATE_WORDS, _NUMERIC_DATE, _HAS_YEAR, _WEEK_COUNT, _PERIOD_VOCABULARY):
        rest = pattern.sub(' ', rest)
    return not rest.strip() and bool(_DATE_WORDS.search(text) or _NUMERIC_DATE.search(text)
                                     or _HAS_YEAR.search(text) or re.search(r'\bended\b', text, re.I))


def _period_row(row):
    """A row without data (a cell holding only a footnote marker is not data) in
    which some origin, label included, is period text, or a heading contains a
    period phrase ('Three months ended March 31, 2025, as restated'). A label
    that only mentions a period ('… for the years ended December 31:') does not
    count, so section labels in statements do not make period rows."""
    cells = _row_origins(row)
    label = row[0] if row[0] is not None and row[0].text.strip() else None
    return (bool(cells)
            and not any(_is_data_cell(cell) and not _FOOTNOTE_MARK.fullmatch(cell.text.strip()) for cell in cells)
            and (any(_period_text(cell.text) for cell in cells)
                 or any(_PERIOD_PHRASE.search(cell.text) or _NUMERIC_DATE.search(cell.text)
                        for cell in cells if cell is not label)))


def _export_header_count(grid):
    """Header rows for the XLSX copy table.

    Starts from _header_count and extends it downward through heading rows, up to
    the first row with an amount. The header ends at the last accepted row with
    span evidence: a heading wider than an amount beneath it, as
    'December 31, 2024' spans '$' and '2,750'. Accepted rows after it stay in the
    body. Without a data row the count is unchanged, so text tables are too. If a
    period row follows the extended header, the count stays _header_count's.
    """
    base = _header_count(grid)
    data = next((r for r in range(base, len(grid))
                 if any(_is_data_cell(cell, digits=True) for cell in _row_origins(grid[r]))), None)
    if data is None:
        return base

    def above(cell, index):
        """The nearest heading above any of the cell's columns."""
        for r in range(index - 1, -1, -1):
            for col in range(cell.column, cell.column + cell.colspan):
                upper = grid[r][col]
                if upper is not None and upper is not cell and upper.text.strip():
                    return upper
        return None

    def straddles(cell, index):
        """Whether the cell is not wholly under one parent heading."""
        columns = range(cell.column, cell.column + cell.colspan)
        for r in range(index - 1, -1, -1):
            uppers = [grid[r][col] for col in columns]
            if any(u is not None and u is not cell and u.text.strip() for u in uppers):
                return len(set(uppers)) != 1 or uppers[0] is None or not uppers[0].text.strip()
        return False

    def amounts_under(cell):
        return [u for u in dict.fromkeys(grid[data][col] for col in range(cell.column, cell.column + cell.colspan))
                if u is not None and _is_data_cell(u, digits=True)]

    def year_heading_ok(year, index):
        # A year heading completes a wider period heading, or an equally wide one
        # that has no year of its own ('July 30,' over '2023').
        upper = above(year, index)
        return (upper is not None and _period_heading(upper.text)
                and (upper.colspan > year.colspan
                     or (upper.colspan == year.colspan and not _HAS_YEAR.search(upper.text))))

    def rejected(index, label, headings, cells):
        if any(_is_data_cell(cell) for cell in cells):
            return True  # a body value, including 'N/A' and '.75'
        if not headings or all(_UNIT_DECLARATION.fullmatch(cell.text.strip()) for cell in headings):
            return True  # a body label: 'Assets', 'Inventories: | (In millions)'
        if label is not None and (len(headings) < 2 or not _heading_label(label.text)):
            return True  # a labelled row must look like a header row: 'Description | ...'
        for cell in headings:
            upper = above(cell, index)
            if upper is not None and cell.colspan > upper.colspan:
                return True  # header rows narrow downward
            if (label is not None and upper is not None and cell.colspan >= upper.colspan
                    and not _CURRENCY.fullmatch(cell.text.strip())):
                return True  # a labelled row must subdivide the heading above it
            if straddles(cell, index):
                return True  # a heading across two parents would misattribute amounts
            if any(cell.colspan < amount.colspan for amount in amounts_under(cell)):
                return True
            if _CURRENCY.fullmatch(cell.text.strip()) and upper is not None and cell.colspan < upper.colspan:
                return True  # 'NT$' over part of a date column would split it
        years = [cell for cell in headings if _YEAR_TOKEN.fullmatch(cell.text.strip())]
        if label is not None and (_YEAR_TOKEN.fullmatch(label.text.strip()) or (years and not _caption_label(label.text))):
            return True  # 'Revenue | 2024 | 2025' holds amounts
        return not all(year_heading_ok(year, index) for year in years)

    evidenced = base
    for index in range(base, data):
        row = grid[index]
        cells = _row_origins(row)
        if not cells:
            continue
        label = row[0] if row[0] is not None and row[0].text.strip() else None
        headings = [cell for cell in cells if cell is not label]
        if rejected(index, label, headings, cells):
            break
        if any(cell.colspan > amount.colspan for cell in headings for amount in amounts_under(cell)):
            evidenced = index + 1
    # Period-row guard (revision 6): a period row below the header is a second
    # period block, whose amounts would sit under the first block's period, or a
    # period row stranded below the evidenced row. Keep today's header rows.
    if evidenced > base and any(_period_row(grid[r]) for r in range(evidenced, len(grid))):
        return base
    return evidenced


# Identifier columns (Rule 3). A header part keeps identifier meaning unless the
# identifier word belongs to a note reference, a maturity bucket, period wording
# or a measured quantity. Ancestor parts never clear another part.
_NOTE_REF = re.compile(r'\(?notes? \d+[a-z]?(?:\([a-z]\))?\)?', re.I)
_MATURITY_BUCKET = re.compile(r'(?:(?:less|more) than \d+ years?|\d+\s*[-–]\s*\d+ years?'
                              r'|\d+ years? or (?:more|greater|less))', re.I)
_PERIOD_WORDS = re.compile(
    rf'\b(?:for )?(?:the )?(?:(?:three|six|nine|twelve) )?(?:years?|months?|quarters?|weeks?|periods?) ended\b'
    rf'|\b{_MONTH} \d{{1,2}},?(?: (?:19|20)\d{{2}})?|\b(?:19|20)\d{{2}}\b|\bas (?:of|at)\b', re.I)
_QUANTITY = re.compile(r'\bnumber of\b|\bto date\b|\bper share\b', re.I)
# Quantity phrases a heading may wrap across two header rows.
_WRAPPED_QUANTITY = re.compile(r'\bnumber of\b|\bgrant[- ]date fair value\b', re.I)


def _identifier_column(header):
    """Whether a flattened header names an identifier column."""
    parts = [part.strip() for part in header.split(' — ') if part.strip()]
    for index, part in enumerate(parts):
        if not _IDENTIFIER.search(part):
            continue
        if _NOTE_REF.fullmatch(part) or _MATURITY_BUCKET.fullmatch(part):
            continue
        if not _IDENTIFIER.search(_PERIOD_WORDS.sub(' ', part)):
            continue  # 'Year ended March 31,' is a period, not an identifier
        if any(pattern.search(part) for pattern in (_VALUE, _ROW_UNIT, _QUANTITY)):
            continue  # the identifier word names a measured quantity: 'Number of Shares'
        if _WRAPPED_QUANTITY.search(' '.join(parts[index:index + 2])):
            continue  # a wrapped heading: 'Number — of RSUs', 'grant date — fair value'
        return True
    return False


def _identifier_heading(header):
    """An identifier column whose heading is not wholly period text: its cells stay text."""
    return _identifier_column(header) and not all(_PERIOD.fullmatch(part) for part in header.split(' — '))


def _numeric_role(text, header, label, cells, units, financial, table_percent, proof=None):
    """The cell's role. proof is the role a cell-, row- or column-level proof gives (spec
    P1-P3); a table-wide percent declaration applies only without one."""
    if _identifier_heading(header):
        return 'text'
    if proof:
        return proof
    # Amount headings keep plain values as displayed under a table-wide percent description.
    if _VALUE.search(header):
        return 'number'
    if table_percent:
        return 'percent'
    if any(c.is_numeric_fact for c in cells) or '$' in text or '%' in text:
        return 'number'
    if units or _VALUE.search(label) or financial:
        return 'number'
    return 'text'


# Rule P (2026-10-12 value-accuracy spec): a digit cell converts as a percent only on proof.
_NOT_PERCENT_LABEL = re.compile(r'\$|\bpoints?\b|\bpts\b', re.I)
# A number's own percent sign ('21%', 'LTV under 80 %') is not a '%' word; a year
# before one is ('2024 vs 2023 % change').
_NUMBER_PERCENT = re.compile(r'(?<![\d.,])(?!(?:19|20)\d{2}\s?%)\d[\d,.]*\s?%')
_PERCENT_SYMBOL = re.compile(r'^%|%\s+(?:of|change)\b|(?:\(\s*%\s*\)|%)$', re.I)
_PERCENT_BASE = r'(?:(?:total )?(?:net )?revenues?|net sales|sales)'
_PERCENT_WORDS = re.compile(
    rf'(?:percent|percentages?|percent(?:age)? change|(?:as a )?percent(?:age)? of {_PERCENT_BASE}'
    rf'|percent of retained loans to total retained loans)(?:\s*(?:\([a-z\d]{{1,2}}\)|\*+))?', re.I)
_TABLE_PERCENT = re.compile(r'\(?(?:in percent(?:ages)?|as a percentage of (?:total )?revenue)\)?\.?', re.I)
_PERCENT_FACT_FORMATS = frozenset({None, 'ixt:num-dot-decimal', 'ixt:numdotdecimal'})
_UNPROVEN = 'Percent sign on other rows of this column; verify the scale.'


def _percent_declaration(text: str) -> bool:
    """A header or row label declaring its values percents (spec Definitions): '% Change',
    'Total % of IG', 'Gross margin %', 'Percent of net sales (1)', 'Margin (%)'. Never with
    a '$', 'point(s)' or 'pts': 'Percentage point change', '$ and % Change'."""
    text = re.sub(r'\s+', ' ', text).strip()
    if _NOT_PERCENT_LABEL.search(text):
        return False
    return bool(_PERCENT_SYMBOL.search(_NUMBER_PERCENT.sub(' ', text).strip())
                or _PERCENT_WORDS.fullmatch(text) or _PERCENT_UNIT.fullmatch(text))


def _table_percent_declaration(line: str) -> bool:
    """A unit line declaring the whole table percents (spec Definitions): '(in percentages)',
    NVDA's 'The following table … expressed as a percentage of revenue.' A percent word in
    an except clause never is: '(In thousands, except share, per share and percentage data)'."""
    line = line.strip()
    return bool(_TABLE_PERCENT.fullmatch(line)
                or (_UNIT_DECLARATION.fullmatch(line) and re.search(r'percentage of revenue', line, re.I)))


def _value_facts(origins):
    """The inline XBRL facts on the copy cell's value origins, the origins holding digits."""
    return [fact for origin in origins if re.search(r'\d', origin.text) for fact in origin.facts]


def _percent_fact(origins) -> bool:
    """The only fact on the value origin proves a percent (spec Definitions): a pure unit,
    scale -2, a plain US number format, and the token's displayed digits and sign."""
    values = [origin for origin in origins if re.search(r'\d', origin.text)]
    if len(values) != 1 or len(values[0].facts) != 1:
        return False
    fact, text = values[0].facts[0], _joined(origins)
    shown = _convert_prepared(text, 'number', origins).value
    return (isinstance(shown, Decimal) and fact.unit_measures == ('xbrli:pure',) and fact.scale == -2
            and fact.format in _PERCENT_FACT_FORMATS
            and re.sub(r'[^\d.]', '', fact.displayed) == re.sub(r'[^\d.]', '', text)
            and (fact.sign == '-') == shown.is_signed())


def _amount_fact(origins) -> bool:
    """A fact on the value origin measured in a currency or in shares (spec Definitions)."""
    return any(measure.lower().startswith('iso4217:') or measure.lower() == 'xbrli:shares'
               for fact in _value_facts(origins) for measure in fact.unit_measures)


class _Proof(NamedTuple):
    role: str | None  # 'percent' or 'number' when a local proof applies (spec P1.1-P1.4, P2)
    conflict: bool  # spec P3: percent and non-percent proofs, or two percent proofs disagree
    marks_column: bool  # P1.1, P1.2 or P1.4: its copy column is a percent column (spec P4)
    by_fact: bool  # the percent fact proves it without a percent heading or row label


_NO_PROOF = _Proof(None, False, False, False)


def _cell_proof(text, header, labels, label, origins) -> _Proof:
    """Rule P's cell-, row- and column-level proofs for a digit copy cell (spec P1-P3)."""
    reading = _convert_prepared(text, 'number', origins)
    own_percent = isinstance(reading.value, Decimal) and '%' in reading.number_format
    fact = _percent_fact(origins)
    heading = any(_percent_declaration(part) for part in labels)
    row = _percent_declaration(label)
    amount = _amount_fact(origins)
    percent = own_percent or fact or heading or row
    not_percent = '$' in text or amount or bool(_ROW_UNIT.search(header) or _ROW_UNIT.search(label))
    # Today's explicit-unit conflicts stay conflicts: a percent heading, label or sign
    # beside a '$' or a unit word anywhere on the cell's axes.
    shown_percent = bool(_PERCENT.search(text)) or any(_PERCENT_UNIT.fullmatch(part.strip())
                                                       for part in (*labels, label))
    local = f'{header} {label} {text}'
    disagree = '%' in text and any(item.unit_measures == ('xbrli:pure',) and item.scale != -2
                                   for item in _value_facts(origins))
    conflict = disagree or ((percent or shown_percent)
                            and (amount or bool(_ROW_UNIT.search(local)) or '$' in local))
    return _Proof('percent' if percent else 'number' if not_percent else None, conflict,
                  own_percent or fact or row, fact and not (heading or row))


class _BodyCell(NamedTuple):
    """A copy cell once its role is decided, before the percent-column pass (spec P4)."""
    text: str
    origins: list
    role: str
    value: CellValue
    marks_column: bool
    unproven: bool
    by_fact: bool


def _unproven_value(text, origins):
    """An unproven digit cell in a percent column keeps its source text (spec P4). A zero
    the converter accepts converts; a token it rejects keeps its reason ('(0)')."""
    reading = _convert_prepared(text, 'number', origins)
    if reading.review_reason or reading.value.is_zero():
        return reading
    return CellValue(text, '@', text, _UNPROVEN)


# Standalone structural fragments. ')%' reaches a copy cell only through the
# attachment pass, which joins '(4.5' and ')%' as '(4.5)%' (the EXTENDED rule).
_FRAGMENTS = frozenset({'$', '(', ')', '%', ')%'})
# Percentage points (spec P4): a value '26.6 pts', or its unit in a cell of its own.
_POINTS = re.compile(r'[+\-−]?\(?(?:\d[\d,]*)?\.?\d+\)?\s*(?:pts|pt|points)', re.I)
_POINTS_UNIT = re.compile(r'pts|pt|points', re.I)


def _joined(cells):
    """Only standalone structural fragments may be joined without a space."""
    parts = [c.text for c in cells if c.text]
    values = [i for i, part in enumerate(parts) if part not in _FRAGMENTS]
    if len(values) == 1:
        i = values[0]
        return TableParser._join_structural_text(parts[:i], parts[i], parts[i + 1:],
                                                 policy=EXTENDED if ')%' in parts else LEGACY)
    return ' '.join(parts)


def _leaf(grid, header_count, col):
    """The lowest header cell with text above a column, unit lines excluded."""
    return next((grid[r][col] for r in reversed(range(header_count))
                 if grid[r][col] and grid[r][col].text and not _UNIT_LINE.search(grid[r][col].text)), None)


def _attached_percent_signs(grid, header_count):
    """The attachment pass (spec P4): {value origin: marker origin}.

    A body origin whose whole text is '%' or ')%' attaches to the nearest value
    origin on its left in the same source row. Only empty origins or '$' and '('
    fragments may lie between them, so two values are never joined. The row
    label, a value spanning from another row and a value that already shows a
    '%' take no marker. Neither does period text or any origin of a period row
    (heading rows left in the body: '| | 2025 | 2024 | $ | % |'), nor a value
    under a different leaf header than a headed marker ('2025' over an amount,
    '% change' over the '%').
    """
    attached = {}
    for r in range(header_count, len(grid)):
        row = grid[r]
        if _period_row(row):
            continue
        for col, marker in enumerate(row):
            if marker is None or (marker.row, marker.column) != (r, col) or marker.text not in {'%', ')%'}:
                continue
            value = next((c for c in reversed(row[:col]) if c is not None and c.text not in {'', '$', '('}), None)
            if (value is None or value.row != r or value.column == 0 or not re.search(r'\d', value.text)
                    or '%' in value.text or _period_text(value.text)):
                continue
            marker_leaf = _leaf(grid, header_count, col)
            if marker_leaf is None or marker_leaf is _leaf(grid, header_count, value.column + value.colspan - 1):
                attached[value] = marker
    return attached


def _with_attached(origins, attached):
    """A copy cell's origins after the attachment pass: each attached marker
    follows its value and leaves its own copy position."""
    markers = set(attached.values())
    cells = []
    for origin in origins:
        if origin in markers:
            continue
        cells.append(origin)
        if origin in attached:
            cells.append(attached[origin])
    return list(dict.fromkeys(cells))


def _convert_prepared(text, role, origins):
    if role != 'text' and any(c.numeric_markers for c in origins):
        return CellValue(text, '@', text, 'Numeric footnote marker retained; verify the source amount and marker before conversion.')
    # The Markdown structural join produces '$ (120)'. Relocate only a proven
    # standalone dollar fragment for the strict converter, preserving the display.
    token = text
    if role != 'text' and text.startswith('$ (') and text.endswith(')') and any(c.text == '$' for c in origins):
        token = '($ ' + text[3:]
    return replace(convert_cell(token, role=role), original=text)


def _column_groups(grid, original, header_count, attached):
    """Consolidate a leaf header's source span only when it contains one value.

    Financial HTML often alternates '$' + value with a value spanning the same
    two positions. A leaf span establishes their common column, while a duration
    spanning several leaf dates does not. Independent values veto consolidation.
    """
    width = len(grid[0])
    active = {col for col in range(width) if any(row[col] for row in original)}
    if not active:
        active = set(range(width))
    groups = []
    for col in sorted(active):
        if any(col in group for group in groups):
            continue
        leaf = _leaf(grid, header_count, col)
        candidates = tuple(c for c in sorted(active) if leaf and leaf.column <= c < leaf.column + leaf.colspan)
        safe = len(candidates) > 1 and all(_leaf(grid, header_count, c) is leaf for c in candidates)
        evidence = False
        for r in range(header_count, len(grid)):
            origins = _with_attached(dict.fromkeys(grid[r][c] for c in candidates if grid[r][c] and original[r][c]),
                                     attached)
            # A points unit beside its value is not a second value (spec P4).
            nonmarkers = [c for c in origins if c.text not in _FRAGMENTS and not _POINTS_UNIT.fullmatch(c.text)]
            if len(nonmarkers) > 1:
                safe = False
            text = _joined(origins)
            if (any(c.text in _FRAGMENTS for c in origins) and not _POINTS.fullmatch(text)
                    and _convert_prepared(text, 'number', origins).review_reason):
                safe = False
            evidence |= bool(nonmarkers and re.search(r'\d', nonmarkers[0].text))
        groups.append(candidates if safe and evidence else (col,))
    return groups


def prepare_table(snapshot: TableSnapshot) -> PreparedTable:
    """Build a conservative copy grid from source origins, never Markdown cleanup."""
    cells = snapshot.source_cells
    label = next((c.text.rstrip(':') for c in cells if c.column == 0 and not c.is_header
                  and 3 < len(c.text) <= 160 and re.search(r'[A-Za-z]{3}', c.text)
                  and not _PERIOD.fullmatch(c.text) and not _UNIT_DECLARATION.fullmatch(c.text)), None)
    title = snapshot.explicit_title or label or f'Table {snapshot.ordinal}'
    unit_texts = [text for text in snapshot.context_before if _UNIT_DECLARATION.fullmatch(text.strip())]
    units = '\n'.join(unit_texts)
    notes = [f'Context: {text}' for text in (*snapshot.context_before, *snapshot.context_after)
             if text != snapshot.explicit_title and text not in unit_texts]
    notes.extend(f'Linked note ({href}): {text}' for href, text in snapshot.resolved_notes)
    references = tuple(link for cell in cells for link in cell.links)
    issues = list(snapshot.issues)
    issues.extend(f'Unresolved or ambiguous note target: {href}' for href in snapshot.unresolved_references)
    height = max((c.row + max(c.rowspan, 1) for c in cells), default=0)
    width = max((c.column + max(c.colspan, 1) for c in cells), default=0)
    # Never allocate a hostile span grid or pretend a capture failure is reliable.
    if snapshot.issues or not cells or height * width > 1_000_000:
        original = tuple((f'({c.row}, {c.column}) span {c.rowspan}x{c.colspan}', c.text) for c in cells)
        if not original:
            original = ((snapshot.original_text,),)
        if not issues:
            issues.append('Source grid unavailable or too large; review source text.')
        return PreparedTable(snapshot, title, units, (), (), (), original, tuple(notes), references,
                             tuple(issues), 'source_text_only')
    grid = [[None for _ in range(width)] for _ in range(height)]
    for cell in cells:
        for row in range(cell.row, cell.row + cell.rowspan):
            for col in range(cell.column, cell.column + cell.colspan):
                grid[row][col] = cell
    original = tuple(tuple(c.text if c and (c.row, c.column) == (r, col) else ''
                           for col, c in enumerate(row)) for r, row in enumerate(grid))
    notes.append('Original text uses source columns and header levels; span-covered positions are blank. '
                 'Source span origins and symbol coordinates are retained in the table snapshot and cell_sources.')
    header_count = _export_header_count(grid)
    # Body labels and individual column units retain their local scope. A source
    # declaration must precede data and span all value columns, including the
    # common first grouping row (e.g. Inventories: / (In millions)).
    first_body_row = next((r for r in range(header_count, height) if any(original[r])), height)
    captions = [c for c in cells if c.row <= first_body_row
                and (c.column == 0 or (grid[c.row][0] and c.column == grid[c.row][0].colspan))
                and c.column + c.colspan == width and c.colspan > 1]
    unit_texts.extend(c.text for c in captions
                      if _UNIT_DECLARATION.fullmatch(c.text.strip()) and c.text not in unit_texts)
    units = '\n'.join(unit_texts)
    # Spec P1.5: a table-wide percent declaration comes from the positions units do.
    table_percent = any(_table_percent_declaration(text)
                        for text in (*snapshot.context_before, *(c.text for c in captions)))
    attached = _attached_percent_signs(grid, header_count)
    groups = _column_groups(grid, original, header_count, attached)
    group_origins = [[list(dict.fromkeys(grid[r][col] for col in group
                                        if grid[r][col] and (grid[r][col].row, grid[r][col].column) == (r, col)))
                      for group in groups] for r in range(height)]
    raw = [[GridCell(Cell(_joined(origins))) for origins in row] for row in group_origins]
    # A numeric cell spanning independently headed values cannot be assigned to
    # its left edge. Keep the entire original table rather than duplicate it.
    for cell in cells:
        if cell.row < header_count or not re.search(r'\d', cell.text):
            continue
        crossed = [group for group in groups if any(cell.column <= col < cell.column + cell.colspan for col in group)]
        if len(crossed) > 1 and (cell.is_numeric_fact or re.fullmatch(r'[\d,.() $%+−-]+', cell.text)):
            issues.append(f'Unresolved value span at ({cell.row}, {cell.column}); review column alignment.')
            return PreparedTable(snapshot, title, units, (), (), (), original, tuple(notes), references,
                                 tuple(issues), 'source_text_only')
    # The existing validated structural rules operate on body rows after a sentinel
    # header, so their legacy header heuristic cannot consume the first data row.
    structural_grid = [[GridCell(Cell('')) for _ in groups], *raw[header_count:]]
    parser = object.__new__(TableParser)
    actions = parser._safe_structural_actions(structural_grid)
    # A marker column carrying independent header text must remain visible.
    actions = {col: moves for col, moves in actions.items()
               if all(not grid[r][groups[col][0]] or not grid[r][groups[col][0]].text or
                      any(grid[r][groups[target][0]] is grid[r][groups[col][0]] for target in moves.values())
                      for r in range(header_count))}
    # Revalidate after the header veto: removing one part must not leave an
    # accounting fragment whose original successful validation used that part.
    actions = parser._validated_structural_actions(structural_grid, actions)
    kept = [col for col in range(len(groups)) if col not in actions]
    headers, header_labels = [], []
    for index, col in enumerate(kept):
        header_cells = list(dict.fromkeys(grid[r][groups[col][0]] for r in range(header_count)))
        labels = [c.text for c in header_cells if c and c.text and not _UNIT_LINE.search(c.text)]
        # Unit declarations belong to source components and their spans, not
        # the flattened display label (which can also contain period headings).
        header_labels.append(labels)
        headers.append(' — '.join(labels) or f'Column {index + 1}')
        if not labels:
            notes.append(f'Column {index + 1} is an exporter-generated positional header.')
            if index > 0 and header_count:
                issues.append(f'Missing source header for Column {index + 1}; verify its meaning.')
    if not header_count:
        issues.append('No explicit headers; positional column names generated and every source row retained.')
    financial = sum(bool(_VALUE.search(row[0])) for row in original[header_count:] if row) >= 2
    body = []
    for r in range(header_count, height):
        decided = []
        for index, col in enumerate(kept):
            contributors = [col] + [src for src, moves in actions.items() if moves.get(r - header_count + 1) == col]
            contributors.sort()
            origins = _with_attached(dict.fromkeys(c for src in contributors for c in group_origins[r][src]), attached)
            text = _joined(origins)
            digits = bool(re.search(r'\d', text))
            # Labels are never promoted merely because they look numeric.
            label_column = index == 0 and not (_VALUE.search(headers[index]) or _PERCENT.search(headers[index]))
            points = not label_column and bool(_POINTS.fullmatch(text))
            proof = (_cell_proof(text, headers[index], header_labels[index], original[r][0], origins)
                     if digits and not label_column else _NO_PROOF)
            role = 'text' if label_column else _numeric_role(
                text, headers[index], original[r][0], origins, units, financial, table_percent, proof.role)
            value = _convert_prepared(text, role, origins)
            # Explicit units on either axis (or on the value itself) must agree.
            # Broader table units can still have specific row/column exceptions.
            if proof.conflict:
                value = CellValue(text, '@', text, 'Conflicting explicit units; verify the row, column and displayed value units.')
            elif points:
                value = CellValue(text, '@', text, 'Percentage points; verify the unit.')
            elif role == 'text' and index > 0 and digits and not _identifier_column(headers[index]):
                value = CellValue(text, '@', text, 'Numeric role unresolved; verify the column heading and units.')
            # Spec P4: no proof of either kind, and no table-wide declaration proving it.
            unproven = (digits and not label_column and not points and proof.role is None and not proof.conflict
                        and role != 'percent' and not _identifier_heading(headers[index]))
            decided.append(_BodyCell(text, origins, role, value, proof.marks_column and not points,
                                     unproven, proof.by_fact))
        body.append(decided)
    # Spec P4: a cell's own '%', its percent fact or its row label makes its copy
    # column a percent column, where unproven digit cells stay source text.
    percent_columns = {index for decided in body for index, cell in enumerate(decided) if cell.marks_column}
    rows, sources = [], []
    for r, decided in enumerate(body, start=header_count):
        row_values = []
        for index, cell in enumerate(decided):
            value = (_unproven_value(cell.text, cell.origins) if cell.unproven and index in percent_columns
                     else cell.value)
            column = groups[kept[index]][0]
            if value.review_reason:
                issues.append(f'Source row {r}, column {column}: {value.review_reason}')
            if (cell.role == 'percent' and '%' not in cell.text and value.value is not None
                    and not isinstance(value.value, str)):
                meaning = "the cell's inline XBRL fact" if cell.by_fact else 'the displayed heading or units'
                notes.append(f'Source ({r}, {column}): percentage meaning comes from {meaning}.')
            row_values.append(value)
        rows.append(tuple(row_values))
        sources.append(tuple(tuple((c.row, c.column) for c in cell.origins) for cell in decided))
    return PreparedTable(snapshot, title, units, tuple(headers), tuple(rows), tuple(sources), original,
                         tuple(notes), references, tuple(issues), 'needs_review' if issues else 'exported')
