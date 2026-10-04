"""One-document XLSX export with optional dependencies and safe publication."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import os
from pathlib import Path
import secrets
from typing import Literal

from sec2md.core import _link_resolution_url, _resolve_source
from sec2md.parser import Parser
from sec2md.quality import ParseDiagnostics, build_diagnostics, enforce_quality
from sec2md.utils import is_url
from sec2md.xlsx_tables import prepare_table, select_export_tables
from sec2md.xlsx_writer import render_workbook

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class XlsxTableResult:
    ordinal: int
    sheet_name: str
    status: Literal['exported', 'needs_review', 'source_text_only']
    issues: tuple[str, ...]
    # This table's table-completeness findings. Phase A reports them without
    # changing status or issues.
    completeness: tuple[str, ...] = ()


@dataclass(frozen=True)
class XlsxExportResult:
    path: Path
    status: Literal['complete', 'needs_review', 'no_tables']
    tables: tuple[XlsxTableResult, ...]
    diagnostics: tuple[str, ...]
    parse_diagnostics: ParseDiagnostics | None = None


class XlsxDependencyError(ImportError):
    """The optional XLSX dependency is unavailable."""


class XlsxQualityError(ValueError):
    """Strict export rejected table reliability issues before publication."""

    def __init__(self, issues: tuple[str, ...]):
        self.issues = issues
        super().__init__('; '.join(issues))


_STAGING_ATTEMPTS = 10


def _create_staging_file(destination: Path) -> tuple[int, Path]:
    """Exclusively create a sibling staging file, failing fast when it cannot be created.

    tempfile retries PermissionError up to TMP_MAX (about 2**31) times on Windows
    whenever os.access reports the directory writable, which it does despite a
    denying ACL; that made exports to unwritable folders appear to hang.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
    last_error: OSError | None = None
    for _ in range(_STAGING_ATTEMPTS):
        candidate = destination.parent / f'.{destination.name}.{secrets.token_hex(4)}.xlsx'
        try:
            return os.open(candidate, flags, 0o600), candidate
        except (FileExistsError, PermissionError) as exc:
            # Windows also reports a name collision as PermissionError, so retry
            # a few fresh names before treating the directory as unwritable.
            last_error = exc
    raise last_error


def _remove_staging_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        # Another process (an indexer or sync client) may still hold the file.
        # Never let cleanup replace a completed publish or the original error.
        logger.warning('Could not remove XLSX staging file %s: %s', path, exc)


def _check_destination_writable(destination: Path) -> None:
    """Fail before parsing when no staging file can be created beside the destination."""
    descriptor, probe = _create_staging_file(destination)
    os.close(descriptor)
    _remove_staging_file(probe)


def _publish(payload: bytes, destination: Path, *, overwrite: bool, load_workbook) -> None:
    """Validate a sibling staging file, then link without clobber or replace."""
    descriptor, temp_path = _create_staging_file(destination)
    try:
        with os.fdopen(descriptor, 'wb') as staged:
            staged.write(payload)
        # Load all worksheets rather than merely opening the ZIP container.
        with temp_path.open('rb') as saved:
            workbook = load_workbook(saved)
            workbook.close()
        if overwrite:
            os.replace(temp_path, destination)
        else:
            # Hard-link creation fails if any destination entry already exists.
            # Unsupported filesystems fail explicitly; there is no copy fallback.
            os.link(temp_path, destination)
    finally:
        _remove_staging_file(temp_path)


def export_xlsx(
    source: str | bytes,
    destination: str | Path,
    *,
    base_url: str | None = None,
    user_agent: str | None = None,
    quality_policy: Literal['strict', 'warn', 'off'] = 'warn',
    overwrite: bool = False,
) -> XlsxExportResult:
    """Export one HTML document; read local files as bytes before calling.

    Raw input never fetches linked content. URL input fetches only that document.
    Strict quality errors occur before publication. No-overwrite publication
    requires filesystem hard-link support and raises OSError if unavailable.
    """
    if not isinstance(quality_policy, str) or quality_policy not in {'strict', 'warn', 'off'}:
        raise ValueError(f'invalid quality_policy: {quality_policy}')
    if not isinstance(source, (str, bytes)):
        raise TypeError('source must be an HTML string, bytes, or URL string')
    source_url = source if isinstance(source, str) and is_url(source) else None
    link_url = _link_resolution_url(source_url, base_url)
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise XlsxDependencyError('XLSX export requires pip install "sec2md[xlsx]"') from exc
    path = Path(destination)
    if path.is_dir():
        raise IsADirectoryError(f'XLSX destination is a directory: {path}')
    if not path.parent.exists():
        raise FileNotFoundError(f'XLSX destination parent does not exist: {path.parent}')
    if not path.parent.is_dir():
        raise NotADirectoryError(f'XLSX destination parent is not a directory: {path.parent}')
    if not overwrite and os.path.lexists(path):
        raise FileExistsError(f'XLSX destination already exists: {path}')
    _check_destination_writable(path)

    html, decode_diagnostics = _resolve_source(source, user_agent=user_agent)
    parser = Parser(html, source_url=link_url, decode_diagnostics=decode_diagnostics,
                    capture_tables=True, table_checks=quality_policy != 'off')
    pages = parser.get_pages(include_images=False)
    diagnostics = parser.diagnostics
    if diagnostics is None:
        diagnostics = build_diagnostics(
            html, '\n\n'.join(page.content for page in pages if page.content), pages,
            mapped_element_ids=tuple(key for key, nodes in parser.block_nodes_map.items() if nodes),
            trace_failures=parser.trace_numeric_failures, enforce_mappings=True,
            table_report=parser.table_report,
        )
    enforce_quality(diagnostics, quality_policy)
    tables = tuple(prepare_table(snapshot) for snapshot in select_export_tables(parser.table_snapshots))
    if quality_policy == 'strict':
        table_issues = tuple(f'Table {table.source.ordinal}: {issue}' for table in tables for issue in table.issues)
        if table_issues:
            raise XlsxQualityError(table_issues)
    messages = list(diagnostics.warnings)
    if not tables:
        messages.append('No tables were emitted by the document parser.')
    if isinstance(source, bytes):
        hash_input, hash_kind = source, 'original bytes'
    elif source_url is None:
        hash_input, hash_kind = source.encode('utf-8'), 'supplied text UTF-8'
    else:
        hash_input, hash_kind = html.encode('utf-8'), 'normalized HTML UTF-8'
    payload, worksheets = render_workbook(
        tables, source_url=link_url, source_hash=hashlib.sha256(hash_input).hexdigest(),
        hash_kind=hash_kind, document_diagnostics=messages,
    )
    # Worksheet ordinals are snapshot ordinals, which table findings also carry.
    findings = parser.table_report.findings if parser.table_report else ()
    completeness = {f.snapshot_ordinal: f.messages() for f in findings if f.snapshot_ordinal is not None}
    results = tuple(XlsxTableResult(w.ordinal, w.worksheet_name, w.status, w.issues,
                                    completeness.get(w.ordinal, ()))
                    for w in worksheets)
    issues = tuple(f'Table {table.ordinal}: {issue}' for table in results for issue in table.issues)
    if quality_policy == 'strict' and issues:
        raise XlsxQualityError(issues)
    messages.extend(issues)
    status = ('no_tables' if not results else 'needs_review'
              if messages or any(t.status != 'exported' for t in results) else 'complete')
    _publish(payload, path, overwrite=overwrite, load_workbook=load_workbook)
    return XlsxExportResult(path, status, results, tuple(messages), diagnostics)
