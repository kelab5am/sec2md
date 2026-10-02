"""Optional XLSX rendering. No spreadsheet dependency is imported at module import."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from io import BytesIO
import math
import re
from typing import Sequence
from urllib.parse import quote, urldefrag

from sec2md.xlsx_tables import PreparedTable

MAX_ROWS = 1048576
MAX_COLUMNS = 16384
INVALID_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')


@dataclass(frozen=True)
class WorksheetResult:
    ordinal: int
    worksheet_name: str
    status: str
    issues: tuple[str, ...]
    copy_range: str | None = None
    original_range: str | None = None


def _sheet_name(table, used):
    title = re.sub(r'[\x00-\x1f\[\]:*?/\\]', '', INVALID_XML.sub('', table.title)).strip(" '") or 'Table'
    base = title[:31].rstrip("'")
    name, index = base, 2
    while name.lower() in used or name.lower() in {'contents', 'history'}:
        suffix = f'_{index}'
        name = base[:31-len(suffix)] + suffix
        index += 1
    used.add(name.lower())
    return name


def render_workbook(tables: Sequence[PreparedTable], *, source_url: str | None,
                    source_hash: str, hash_kind: str,
                    document_diagnostics: Sequence[str] = ()) -> tuple[bytes, tuple[WorksheetResult, ...]]:
    """Render in supplied traversal order; report writer safeguards for strict callers."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.worksheet.hyperlink import Hyperlink
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ImportError('XLSX export requires pip install "sec2md[xlsx]"') from exc

    wb = Workbook()
    contents = wb.active
    contents.title = 'Contents'
    navy = '253D55'
    used = {'contents'}
    writer_issues = {}

    def safe_text(ws, text):
        if INVALID_XML.search(text):
            writer_issues.setdefault(ws.title, set()).add(
                'XML-incompatible characters escaped as \\uXXXX; backslashes doubled in affected text.')
            text = INVALID_XML.sub(lambda m: f'\\u{ord(m[0]):04x}', text.replace('\\', '\\\\'))
        return text

    def put(ws, row, col, value, *, heading=False, title=False, number_format='@'):
        cell = ws.cell(row, col)
        if isinstance(value, str):
            # Force type after assignment: source formulas and error tokens stay text.
            cell.value = safe_text(ws, value)
            cell.data_type = 's'
        else:
            cell.value = value
        cell.number_format = number_format
        cell.font = Font(name='Arial', size=17 if title else 11,
                         bold=heading or title, color='FFFFFF' if heading else navy)
        cell.alignment = Alignment(vertical='top', wrap_text=True,
                                   horizontal='right' if number_format != '@' else 'left')
        if heading:
            cell.fill = PatternFill('solid', fgColor=navy)
        elif row % 2 == 0:
            cell.fill = PatternFill('solid', fgColor='F5F7F9')
        width = ws.column_dimensions[get_column_letter(col)].width or 25
        lines = sum(max(1, math.ceil(len(line) / max(1, int(width * .85))))
                    for line in str(value or '').split('\n'))
        height = min(409, max(24, lines * (23 if title else 16) + 8))
        ws.row_dimensions[row].height = max(ws.row_dimensions[row].height or 0, height)
        return cell

    def link(cell, *, target=None, location=None):
        cell.hyperlink = Hyperlink(ref=cell.coordinate, target=target, location=location)
        cell.font = Font(name='Arial', size=11, color='0563C1', underline='single')

    def internal(name, coordinate):
        return f"'{name.replace(chr(39), chr(39)*2)}'!{coordinate}"

    def setup(ws, columns):
        ws.sheet_view.showGridLines = False
        ws.column_dimensions['A'].width = 65
        for col in range(2, columns + 1):
            ws.column_dimensions[get_column_letter(col)].width = 25

    # Retain source identity in hidden rows for existing folder deduplication.
    # No technical metadata is shown in the normal workbook view.
    setup(contents, 2)
    for row, (label, value) in enumerate([
        ('Source', source_url or 'Supplied document'), ('SHA-256 kind', hash_kind),
        ('SHA-256', source_hash), ('sec2md version', version('sec2md')),
        ('Export schema', '1'), ('Layout', 'tables-only')], 1):
        put(contents, row, 1, label)
        put(contents, row, 2, value)
        contents.row_dimensions[row].hidden = True
    put(contents, 8, 1, 'Filing tables', title=True)
    put(contents, 10, 1, 'Table', heading=True)
    put(contents, 10, 2, 'Page', heading=True)
    contents.sheet_view.topLeftCell = 'A8'
    records = []

    def checked_put(ws, row, col, value, **kwargs):
        # Excel silently truncates long cells; reject instead of losing source text
        # or moving it into the diagnostic sections this workbook intentionally omits.
        if isinstance(value, str) and len(safe_text(ws, value)) > 32767:
            raise ValueError('Table cell exceeds Excel character limit (32767); export not published.')
        if row > MAX_ROWS or col > MAX_COLUMNS:
            raise ValueError('Table exceeds Excel dimension limit; export not published.')
        return put(ws, row, col, value, **kwargs)

    def named_range(ws, label, area):
        from openpyxl.workbook.defined_name import DefinedName
        ws.defined_names.add(DefinedName(label, attr_text=internal(ws.title, area)))

    for index, table in enumerate(tables, 11):
        name = _sheet_name(table, used)
        ws = wb.create_sheet(name)
        width = max(len(table.headers), max((len(r) for r in table.rows), default=0))
        original_width = max((len(r) for r in table.original_rows), default=0)
        if max(width, original_width) > MAX_COLUMNS:
            raise ValueError('Table exceeds Excel dimension limit; export not published.')
        setup(ws, max(width, original_width, 2))
        checked_put(ws, 1, 1, table.title, title=True)
        # The title itself provides navigation without another instruction row.
        link(ws.cell(1, 1), location="'Contents'!A8")
        ws.cell(1, 1).font = Font(name='Arial', size=17, bold=True, color=navy)
        checked_put(ws, 2, 1, table.units or '')
        r = 3
        copy_range = None
        if table.status != 'source_text_only':
            for col, header in enumerate(table.headers, 1):
                # Positional labels are exporter scaffolding, not source headers.
                value = '' if header == f'Column {col}' else header
                checked_put(ws, r, col, value, heading=True)
            r += 1
            for body in table.rows:
                for col, item in enumerate(body, 1):
                    checked_put(ws, r, col, item.value, number_format=item.number_format)
                r += 1
            copy_range = f'A2:{get_column_letter(max(1, width))}{r-1}'
            named_range(ws, 'CopyTable', copy_range)
            r += 2
            checked_put(ws, r, 1, 'Original table', heading=True)
            if source_url:
                destination = urldefrag(source_url)[0] + '#' + quote(table.source.source_anchor, safe='') if table.source.source_anchor else source_url
                link(ws.cell(r, 1), target=destination)
            r += 1
        original_start = r
        original_range = None
        cells = table.source.source_cells
        valid_grid = bool(cells) and not table.source.issues and max(
            (c.row + max(1, c.rowspan) for c in cells), default=0) * max(
            (c.column + max(1, c.colspan) for c in cells), default=0) <= 1_000_000
        if valid_grid:
            for body in table.original_rows:
                for col, value in enumerate(body, 1):
                    checked_put(ws, r, col, value)
                r += 1
            for cell in cells:
                saved = ws.cell(original_start + cell.row, cell.column + 1)
                if cell.links and cell.links[0][1]:
                    link(saved, target=cell.links[0][1])
                if cell.is_header:
                    saved.font = Font(name='Arial', size=11, bold=True, color=navy)
                if cell.rowspan > 1 or cell.colspan > 1:
                    ws.merge_cells(start_row=original_start + cell.row, start_column=cell.column + 1,
                                   end_row=original_start + cell.row + cell.rowspan - 1,
                                   end_column=cell.column + cell.colspan)
            original_range = f'A{original_start}:{get_column_letter(max(1, original_width))}{r-1}'
            named_range(ws, 'OriginalTable', original_range)
            if table.status == 'source_text_only':
                # Match source geometry; narrow empty gutters instead of making
                # each currency/spacing fragment a full-width value column.
                for col in range(original_width):
                    texts = [c.text for c in cells if c.column == col and c.text]
                    ws.column_dimensions[get_column_letter(col + 1)].width = (
                        65 if col == 0 else 3 if not texts or all(t in {'$', '(', ')', '%'} for t in texts)
                        else 16)
        else:
            raise ValueError(f'Table {table.source.ordinal}: source grid unavailable; export not published.')
        issues = tuple(dict.fromkeys((*table.issues, *sorted(writer_issues.get(name, ())))))
        status = table.status
        if issues and status == 'exported':
            status = 'needs_review'
        records.append(WorksheetResult(table.source.ordinal, name, status, issues,
                                       copy_range, original_range))
        checked_put(contents, index, 1, table.title)
        link(contents.cell(index, 1), location=internal(name, 'A1'))
        put(contents, index, 2, table.source.display_page if table.source.display_page is not None
            else table.source.page, number_format='0')
    if not records:
        put(contents, 11, 1, 'No tables detected')
    output = BytesIO()
    wb.save(output)
    return output.getvalue(), tuple(records)
