"""Source table records captured before Markdown grid cleanup (no XLSX dependency)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence
from urllib.parse import unquote, urljoin

from bs4 import Tag
from bs4.element import Comment, Declaration, Doctype, NavigableString, ProcessingInstruction

from sec2md.absolute_table_parser import AbsolutelyPositionedTableParser


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
            parts.append(f' {text} ' if child.name in {'br', 'p', 'div', 'tr', 'td', 'th', 'table', 'li'} else text)
    return ''.join(parts)


def _visible_text(node: Tag) -> str:
    """Keep inline token fragments together, separating only structural boundaries."""
    return ' '.join(_text_fragments(node).split())


def _visible_nodes(node: Tag, names):
    for child in node.find_all(names):
        if not any(_hidden(parent) for parent in (child, *child.parents) if isinstance(parent, Tag)):
            yield child


def _anchor(node: Tag, native_anchors: Mapping[int, str | None] | None) -> str | None:
    return native_anchors.get(id(node)) if native_anchors is not None else node.get('id') or node.get('name')


def _cell(node, row, column, rowspan, colspan, source_url, native_anchors):
    return SourceCell(
        _visible_text(node), row, column, rowspan, colspan,
        tuple((_visible_text(a), urljoin(source_url or '', a['href']))
              for a in _visible_nodes(node, 'a') if a.has_attr('href')),
        node.name == 'th', any(_visible_nodes(node, ['ix:nonfraction', 'ix:fraction', 'nonfraction', 'fraction'])),
        _anchor(node, native_anchors),
    )


def _context(node: Tag, *, before: bool) -> tuple[str, ...]:
    """Keep nearby blocks in source order, bounded by tables, headings and size."""
    siblings = node.previous_siblings if before else node.next_siblings
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
            target = note_targets.get(unquote(href[1:]))
            destination = urljoin(source_url or '', href)
            if not target:
                unresolved.append(destination)
            else:
                notes.append((destination, target))
    return tuple(dict.fromkeys(notes)), tuple(dict.fromkeys(unresolved))


def _note_target_text(node: Tag) -> str:
    """Resolve empty anchors only within a small, single-target paragraph."""
    if any(_hidden(parent) for parent in (node, *node.parents) if isinstance(parent, Tag)):
        return ''
    text = _visible_text(node)
    if text:
        return text
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
        for key in ('id', 'name'):
            if node.get(key):
                targets.setdefault(node[key], _note_target_text(node))
    return anchors, targets


def snapshot_html_table(node: Tag, *, ordinal: int, page: int, source_url: str | None,
                        native_anchors=None, note_targets=None) -> TableSnapshot:
    """Capture direct table ownership and report unreliable spans without clipping."""
    if note_targets is None:
        root = node
        while isinstance(root.parent, Tag):
            root = root.parent
        _, note_targets = native_metadata(root)
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
            cells.append(_cell(td, row, column, rowspan, colspan, source_url, native_anchors))
            occupied.append((row, bottom, column, end))
            column = end
    flattened_width = max((sum(max(cell.colspan, 1) for cell in cells if cell.row == row)
                           for row in range(len(rows))), default=0)
    if any(cell.column + max(cell.colspan, 1) > flattened_width for cell in cells):
        issues.append('Span displacement exceeds the Markdown grid width; source cells retained.')
    if node.find('table') is not None:
        issues.append('Nested table content requires source-text review.')
    notes, unresolved = _references([node], source_url, note_targets)
    return TableSnapshot(ordinal, page, None, None, _anchor(node, native_anchors), tuple(cells),
                         _visible_text(node), 'html', _context(node, before=True),
                         _context(node, before=False), tuple(issues), notes, unresolved)


def snapshot_positioned_table(nodes: Sequence[Tag], *, ordinal: int, page: int,
                              source_url: str | None, native_anchors=None,
                              note_targets=None) -> TableSnapshot:
    """Use the selected positioned group's grid only when every visible origin is unique."""
    parser = AbsolutelyPositionedTableParser(list(nodes))
    grid = parser.to_grid()
    cells, issues, seen = [], [], set()
    if grid is not None:
        for row, entries in enumerate(grid):
            for column, entries_in_cell in enumerate(entries):
                visible = [el for _, _, el in entries_in_cell if _visible_text(el)]
                if len(visible) > 1:
                    issues.append('Ambiguous positioned cell geometry; source_text_only.')
                for el in visible:
                    seen.add(id(el))
                    cells.append(_cell(el, row, column, 1, 1, source_url, native_anchors))
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
