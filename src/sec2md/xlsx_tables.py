"""Source table records captured before Markdown grid cleanup (no XLSX dependency)."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Literal, Mapping, Sequence
from urllib.parse import unquote, urljoin

from bs4 import Tag
from bs4.element import Comment, Declaration, Doctype, NavigableString, ProcessingInstruction

from sec2md.absolute_table_parser import AbsolutelyPositionedTableParser
from sec2md.table_parser import Cell, GridCell, TableParser
from sec2md.xlsx_values import CellValue, convert_cell


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


def _context_siblings(node: Tag, *, before: bool):
    """Walk out of presentation wrappers without crossing another table."""
    while isinstance(node, Tag) and node.name not in {'body', 'html', '[document]'}:
        yield from (node.previous_siblings if before else node.next_siblings)
        node = node.parent


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


def _explicit_title(node: Tag) -> str | None:
    caption = node.find('caption', recursive=False)
    if caption is not None:
        return _visible_text(caption)
    context = _context(node, before=True)
    for sibling in _context_siblings(node, before=True):
        if not isinstance(sibling, Tag) or _hidden(sibling):
            continue
        if sibling.name == 'table' or sibling.find('table') is not None:
            break
        if _visible_text(sibling) and _visible_text(sibling) not in context:
            break
        if sibling.name in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'} or sibling.get('role') == 'heading':
            return _visible_text(sibling)
    return None


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
                         _context(node, before=False), tuple(issues), notes, unresolved, _explicit_title(node))


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
_PERCENT = re.compile(r'%|\bpercent(?:age)?\b', re.I)
_ROW_UNIT = re.compile(r'\b(?:per[- ]share|dollars|shares|in (?:thousands|millions|billions))\b', re.I)
_VALUE = re.compile(r'\b(?:amount|value|revenue|income|expense|cost|assets|liabilities|cash|shares|inventory|inventories|earnings|balance|total)\b', re.I)
_IDENTIFIER = re.compile(r'\b(?:id|identifier|code|number|date|year|exhibit|section|zip|cusip)\b', re.I)
_PERIOD = re.compile(r'^(?:(?:three|six|nine|twelve) months? ended|years? ended|(?:19|20)\d{2}|(?:Jan\w*|Feb\w*|Mar\w*|Apr\w*|May|Jun\w*|Jul\w*|Aug\w*|Sep\w*|Oct\w*|Nov\w*|Dec\w*)\.? \d{1,2},? (?:19|20)\d{2})$', re.I)


def _header_count(grid):
    count = 0
    for index, row in enumerate(grid):
        origins = list(dict.fromkeys(c for c in row if c is not None))
        nonempty = [c for c in origins if c.text.strip()]
        # TH evidence must describe the row, not merely a body row's label.
        numeric_body = any(c.is_numeric_fact or
                           (re.fullmatch(r'[$(\d+−-][\d,.() $%+−-]*', c.text) and not _PERIOD.fullmatch(c.text))
                           for c in nonempty)
        explicit = bool(nonempty) and all(c.is_header for c in nonempty) and not numeric_body
        periods = bool(nonempty) and all(_PERIOD.fullmatch(c.text.strip()) or _UNITS.search(c.text) for c in nonempty)
        if not (explicit or periods or not nonempty):
            break
        if nonempty:
            count = index + 1
    # Trailing blank rows belong to the body. Wholly blank tables remain data.
    return count


def _numeric_role(text, header, label, cells, units, financial):
    period_header = all(_PERIOD.fullmatch(part) for part in header.split(' — '))
    if _IDENTIFIER.search(header) and not period_header:
        return 'text'
    if _PERCENT.search(header) or _PERCENT.search(label):
        return 'percent'
    # Specific currency/count headings override a table-wide percent description.
    if _VALUE.search(header) or _ROW_UNIT.search(header) or _ROW_UNIT.search(label):
        return 'number'
    if _PERCENT.search(units):
        return 'percent'
    if any(c.is_numeric_fact for c in cells) or '$' in text or '%' in text:
        return 'number'
    if units or _VALUE.search(label) or financial:
        return 'number'
    return 'text'


def _joined(cells):
    """Only standalone structural fragments may be joined without a space."""
    parts = [c.text for c in cells if c.text]
    values = [i for i, part in enumerate(parts) if part not in {'$', '(', ')', '%'}]
    if len(values) == 1:
        i = values[0]
        return TableParser._join_structural_text(parts[:i], parts[i], parts[i + 1:])
    return ' '.join(parts)


def _convert_prepared(text, role, origins):
    # The Markdown structural join produces '$ (120)'. Relocate only a proven
    # standalone dollar fragment for the strict converter, preserving the display.
    token = text
    if role != 'text' and text.startswith('$ (') and text.endswith(')') and any(c.text == '$' for c in origins):
        token = '($ ' + text[3:]
    return replace(convert_cell(token, role=role), original=text)


def _column_groups(grid, original, header_count):
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
        leaf = next((grid[r][col] for r in reversed(range(header_count))
                     if grid[r][col] and grid[r][col].text and not _UNIT_LINE.search(grid[r][col].text)), None)
        candidates = tuple(c for c in sorted(active) if leaf and leaf.column <= c < leaf.column + leaf.colspan)
        safe = len(candidates) > 1 and all(
            next((grid[r][c] for r in reversed(range(header_count))
                  if grid[r][c] and grid[r][c].text and not _UNIT_LINE.search(grid[r][c].text)), None) is leaf for c in candidates)
        evidence = False
        for r in range(header_count, len(grid)):
            origins = list(dict.fromkeys(grid[r][c] for c in candidates if grid[r][c] and original[r][c]))
            nonmarkers = [c for c in origins if c.text not in {'$', '(', ')', '%'}]
            if len(nonmarkers) > 1:
                safe = False
            text = _joined(origins)
            if any(c.text in {'$', '(', ')', '%'} for c in origins) and _convert_prepared(text, 'number', origins).review_reason:
                safe = False
            evidence |= bool(nonmarkers and re.search(r'\d', nonmarkers[0].text))
        groups.append(candidates if safe and evidence else (col,))
    return groups


def prepare_table(snapshot: TableSnapshot) -> PreparedTable:
    """Build a conservative copy grid from source origins, never Markdown cleanup."""
    cells = snapshot.source_cells
    title = snapshot.explicit_title or f'Table {snapshot.ordinal}'
    unit_texts = [text for text in snapshot.context_before if _UNITS.search(text)]
    unit_texts.extend(c.text for c in cells if re.search(r'\bin (?:thousands|millions|billions)\b', c.text, re.I)
                      and c.text not in unit_texts)
    units = '\n'.join(unit_texts)
    notes = [f'Context: {text}' for text in (*snapshot.context_before, *snapshot.context_after)
             if text != snapshot.explicit_title and text not in unit_texts]
    notes.extend(f'Linked note ({href}): {text}' for href, text in snapshot.resolved_notes)
    references = tuple(link for cell in cells for link in cell.links)
    issues = list(snapshot.issues)
    issues.extend(f'Unresolved or ambiguous note target: {href}' for href in snapshot.unresolved_references)
    height = max((c.row + 1 for c in cells), default=0)
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
    header_count = _header_count(grid)
    groups = _column_groups(grid, original, header_count)
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
    headers = []
    for index, col in enumerate(kept):
        header_cells = list(dict.fromkeys(grid[r][groups[col][0]] for r in range(header_count)))
        labels = [c.text for c in header_cells if c and c.text and not _UNIT_LINE.search(c.text)]
        headers.append(' — '.join(labels) or f'Column {index + 1}')
        if not labels:
            notes.append(f'Column {index + 1} is an exporter-generated positional header.')
            if index > 0 and header_count:
                issues.append(f'Missing source header for Column {index + 1}; verify its meaning.')
    if not header_count:
        issues.append('No explicit headers; positional column names generated and every source row retained.')
    rows, sources = [], []
    financial = sum(bool(_VALUE.search(row[0])) for row in original[header_count:] if row) >= 2
    for r in range(header_count, height):
        row_values, row_sources = [], []
        for index, col in enumerate(kept):
            contributors = [col] + [src for src, moves in actions.items() if moves.get(r - header_count + 1) == col]
            contributors.sort()
            origins = list(dict.fromkeys(c for src in contributors for c in group_origins[r][src]))
            text = _joined(origins)
            # Labels are never promoted merely because they look numeric.
            label_column = index == 0 and not (_VALUE.search(headers[index]) or _PERCENT.search(headers[index]))
            role = 'text' if label_column else _numeric_role(text, headers[index], original[r][0], origins, units, financial)
            value = _convert_prepared(text, role, origins)
            if role == 'text' and index > 0 and re.search(r'\d', text) and not _IDENTIFIER.search(headers[index]):
                value = CellValue(text, '@', text, 'Numeric role unresolved; verify the column heading and units.')
            if value.review_reason:
                issues.append(f'Source row {r}, column {groups[col][0]}: {value.review_reason}')
            if role == 'percent' and '%' not in text and value.value is not None and not isinstance(value.value, str):
                notes.append(f'Source ({r}, {groups[col][0]}): percentage meaning comes from the displayed heading or units.')
            row_values.append(value)
            row_sources.append(tuple((c.row, c.column) for c in origins))
        rows.append(tuple(row_values))
        sources.append(tuple(row_sources))
    return PreparedTable(snapshot, title, units, tuple(headers), tuple(rows), tuple(sources), original,
                         tuple(notes), references, tuple(issues), 'needs_review' if issues else 'exported')
