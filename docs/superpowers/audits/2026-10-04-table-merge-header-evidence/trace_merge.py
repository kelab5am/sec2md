"""Provenance tracing for sec2md's legacy Markdown table renderer (research only).

`TracingTableParser` subclasses `sec2md.table_parser.TableParser` and only records the
raw grid that `_create_grid` builds; it never changes what the parser renders.
`shadow()` then re-runs the renderer's stages on that grid, calling TableParser's own
decision methods (`_safe_structural_actions`, `_body_start`, `_header_merge_target`,
`_join_structural_text`, `_should_merge_cells`, `_escape_table_pipes`) and keeping, for
every grid cell with text, where its text goes:

    raw grid G0 -> _clean_grid G1 -> structural pass G2 -> legacy greedy pass G3
    -> _process_headers -> _clean_empty_rows_and_cols -> Markdown

Every stage is a line-for-line replica of `src/sec2md/table_parser.py` at main 2f039c4.
The caller compares `Trace.markdown` with the text the parser actually emitted for the
table, so any drift between this replica and the source is detected per table.

Nothing in src/ or tests/ is modified. Import this module from the repository root.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sec2md.table_parser import GridCell, Cell, TableParser, _escape_table_pipes

# --- recording subclass -----------------------------------------------------------------


class TracingTableParser(TableParser):
    """TableParser that keeps the raw grid handed to `_clean_grid`. Output is unchanged."""

    registry: list = []  # (table element, instance), reset per document by the caller

    def __init__(self, table_element, *, base_url=None):
        self.raw_grid = None
        super().__init__(table_element, base_url=base_url)
        TracingTableParser.registry.append((table_element, self))

    def _clean_grid(self, grid):  # base is a staticmethod called as self._clean_grid(grid)
        if self.raw_grid is None:
            self.raw_grid = [list(row) for row in grid]
        return TableParser._clean_grid(grid)


def source_trs(table):
    """The tr elements behind TableParser.cells, row for row (same filter as _extract_cells)."""
    return [tr for tr in table.find_all("tr") if tr.find_all(["td", "th"])]


# --- token shapes -----------------------------------------------------------------------

STRUCTURAL = {"$", "(", ")", "%"}
# Standalone currency markers. ISO codes are a closed list so that words such as "N/A" or
# "YES" are not taken for currencies; measure.py also inventories unknown short tokens.
ISO_CODES = {
    "RMB", "CNY", "USD", "EUR", "GBP", "JPY", "DKK", "TWD", "HKD", "CHF", "SEK", "NOK", "INR",
    "KRW", "BRL", "CAD", "AUD", "MXN", "SGD", "ZAR", "RUB", "ILS", "PLN", "NZD", "TRY", "THB",
    "IDR", "MYR", "PHP", "CZK", "HUF", "ARS", "CLP", "COP", "PEN", "SAR", "AED", "ISK",
}
_CURRENCY_SYMBOL = re.compile(r"^(?:[A-Z]{1,3})?\$$|^[€£¥₩₹₪₽]$|^(?:R\$|Ps\.?|Rs\.?|Fr\.?|kr\.?)$")
AMOUNT = re.compile(r"^[$€£¥]?\s*\(?\s*[$€£¥]?\s*[-−]?\d[\d,]*(?:\.\d+)?\s*\)?\s*%?$")
DASH = re.compile(r"^[—–\-]+$")
OPEN_AMOUNT = re.compile(r"^(?:[A-Z]{0,3}[$€£¥])?\s*\(\s*(?:[A-Z]{0,3}[$€£¥])?\s*\d[\d,]*(?:\.\d+)?\s*%?$")
CLOSE = re.compile(r"^\)\s*%?$")
FOOTNOTE = re.compile(r"^(?:\[[A-Za-z0-9]+\]|\(\d{1,2}\)|\([a-z]\)|\*+)$")
BARE_YEAR = re.compile(r"^(?:19|20)\d{2}$")
PERIOD_TEXT = re.compile(r"\b(?:years?|quarters?|months?|weeks?|period|ended|ending|as of|fiscal|calendar)\b"
                         r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}\b"
                         r"|^(?:19|20)\d{2}\b", re.I)
DIGIT = re.compile(r"\d")
LETTER = re.compile(r"[A-Za-z]")


def vis(text: str) -> str:
    """Visible text: TableParser keeps U+200B/U+FEFF (str.strip() does not remove them); detectors do not."""
    return (text or "").replace("​", "").replace("﻿", "").strip()


def currency_marker(text: str) -> str | None:
    """The currency marker a standalone cell holds ("$", "€", "NT$", "RMB", ...), else None."""
    t = vis(text)
    if t in ISO_CODES or _CURRENCY_SYMBOL.match(t):
        return t
    return None


def is_marker(text: str) -> bool:
    t = vis(text)
    return t in STRUCTURAL or currency_marker(t) is not None


def is_value(text: str) -> bool:
    """A data value for alignment purposes: an amount, a nil dash or a fragment of one."""
    t = vis(text)
    return bool(t) and (bool(AMOUNT.match(t)) or bool(DASH.match(t)) or TableParser._is_numeric_fragment(t))


def text_kind(text: str) -> str:
    t = vis(text)
    if not t:
        return "empty"
    if is_marker(t):
        return "marker"
    if FOOTNOTE.match(t):
        return "footnote"
    if DASH.match(t):
        return "dash"
    if AMOUNT.match(t) and not BARE_YEAR.match(t):
        return "amount"
    if BARE_YEAR.match(t) or PERIOD_TEXT.search(t):
        return "period"
    return "text"


# --- shadow pipeline --------------------------------------------------------------------

Origin = tuple  # (g0 row, g0 col)


@dataclass
class Trace:
    g0: list                       # raw grid (GridCell | None)
    rows_keep: list                # G1 row -> G0 row
    cols_keep: list                # G1 col -> G0 col
    actions: dict                  # structural actions on G1 {source col: {row: target}}
    g2_cols: list                  # G2 col -> G1 col
    groups: list                   # G3 col -> list of G2 cols merged (legacy pass)
    matrix: list                   # G3 text matrix (to_matrix)
    fused: bool                    # _process_headers fused matrix rows 0 and 1
    headers: list                  # header texts before cleaning
    kept_cols: list                # G3 cols kept by _clean_empty_rows_and_cols (None = all)
    markdown: str
    final: dict = field(default_factory=dict)   # origin -> ("header", col) | ("body", line, col) | ("dropped", stage)
    legacy_merges: list = field(default_factory=list)
    row0_drops: list = field(default_factory=list)
    structural_header_drops: list = field(default_factory=list)
    clean_col_drops: list = field(default_factory=list)
    clean_all_dropped: bool = False

    def text(self, origin) -> str:
        r, c = origin
        return self.g0[r][c].text

    def cell(self, origin):
        r, c = origin
        return self.g0[r][c].cell


def _t(cell) -> str:
    return cell.text.strip() if cell else ""


def shadow(tp: TableParser, g0) -> Trace:
    """Replay TableParser's grid and Markdown stages on g0, tracking every text origin."""
    R = len(g0)
    C = len(g0[0]) if R else 0
    O0 = [[((r, c),) if g0[r][c] is not None and g0[r][c].text.strip() else () for c in range(C)]
          for r in range(R)]

    # _clean_grid
    rows_keep = [i for i, row in enumerate(g0) if any(cell is not None and cell.text.strip() for cell in row)]
    cols_keep = [j for j in range(C) if any(g0[i][j] is not None and g0[i][j].text.strip() for i in range(R))]
    G1 = [[g0[i][j] for j in cols_keep] for i in rows_keep]
    O1 = [[O0[i][j] for j in cols_keep] for i in rows_keep]

    trace = Trace(g0=g0, rows_keep=rows_keep, cols_keep=cols_keep, actions={}, g2_cols=[], groups=[],
                  matrix=[], fused=False, headers=[], kept_cols=None, markdown="")

    if not G1 or not G1[0]:
        _finish_empty(trace, O0)
        return trace

    # _merge_structural_columns
    actions = tp._safe_structural_actions(G1)
    trace.actions = actions
    n1 = len(G1[0])
    if actions:
        removed = set(actions)
        body_start = tp._body_start(G1)
        G2, O2 = [], []
        for row_index, row in enumerate(G1):
            rebuilt, rebuilt_o = [], []
            for target in range(n1):
                if target in removed:
                    continue
                prefixes, suffixes, extra = [], [], ()
                for source, source_actions in actions.items():
                    value = row[source].text.strip() if row[source] else ""
                    if not value:
                        continue
                    merge_target = source_actions.get(row_index)
                    if merge_target is None and row_index < body_start:
                        merge_target = tp._header_merge_target(source, value, source_actions, removed, n1)
                    if merge_target != target:
                        continue
                    if source < target:
                        prefixes.append(value)
                    else:
                        suffixes.append(value)
                    extra += O1[row_index][source]
                original = row[target]
                original_text = original.text.strip() if original else ""
                merged_text = tp._join_structural_text(prefixes, original_text, suffixes)
                if merged_text != original_text:
                    rebuilt.append(GridCell(Cell(text=merged_text)))
                elif original is not None:
                    rebuilt.append(original)
                else:
                    rebuilt.append(GridCell(Cell(text="")))
                rebuilt_o.append(O1[row_index][target] + extra)
            G2.append(rebuilt)
            O2.append(rebuilt_o)
        # header fragments in removed columns with no target are dropped
        for row_index, row in enumerate(G1):
            for source, source_actions in actions.items():
                value = row[source].text.strip() if row[source] else ""
                if not value:
                    continue
                merge_target = source_actions.get(row_index)
                if merge_target is None and row_index < body_start:
                    merge_target = tp._header_merge_target(source, value, source_actions, removed, n1)
                if merge_target is None:
                    trace.structural_header_drops.append(O1[row_index][source])
        g2_cols = [c for c in range(n1) if c not in removed]
    else:
        G2, O2, g2_cols = G1, O1, list(range(n1))
    trace.g2_cols = g2_cols

    if not G2 or not G2[0]:
        _finish_empty(trace, O0)
        return trace

    # _merge_grid legacy greedy pass
    groups = []  # [cells, origins, members]
    current = None
    for col_idx in range(len(G2[0])):
        col = [row[col_idx] for row in G2]
        ocol = [orow[col_idx] for orow in O2]
        if current is None:
            current = [col, ocol, [col_idx]]
            continue
        cur_col, cur_o, members = current
        pairs = list(zip(cur_col[1:], col[1:]))
        should_merge = all(tp._should_merge_cells(c1, c2) for c1, c2 in pairs)
        if should_merge:
            trace.legacy_merges.append({
                "group": len(groups), "members": list(members), "incoming": col_idx,
                "a_cells": [_t(c) for c in cur_col], "b_cells": [_t(c) for c in col],
                "a_origins": list(cur_o), "b_origins": list(ocol),
            })
            if _t(col[0]):
                trace.row0_drops.append({
                    "group": len(groups), "incoming": col_idx, "dropped_text": _t(col[0]),
                    "kept_text": _t(cur_col[0]), "origins": ocol[0],
                })
            merged, merged_o = [cur_col[0]], [cur_o[0]]
            for k, (c1, c2) in enumerate(pairs, start=1):
                if not c1:
                    merged.append(c2)
                    merged_o.append(ocol[k])
                elif not c2:
                    merged.append(c1)
                    merged_o.append(cur_o[k])
                else:
                    merged.append(GridCell(Cell(text=f"{c1.text} {c2.text}".strip())))
                    merged_o.append(cur_o[k] + ocol[k])
            current = [merged, merged_o, members + [col_idx]]
        else:
            groups.append(current)
            current = [col, ocol, [col_idx]]
    if current is not None:
        groups.append(current)
    trace.groups = [members for _, _, members in groups]
    nrows = len(G2)
    G3 = [[groups[g][0][r] for g in range(len(groups))] for r in range(nrows)]
    O3 = [[groups[g][1][r] for g in range(len(groups))] for r in range(nrows)]

    # to_matrix
    matrix = [[cell.text if cell else "" for cell in row] for row in G3]
    trace.matrix = matrix

    # row-0 drops lose their origins here
    for drop in trace.row0_drops:
        for origin in drop["origins"]:
            trace.final.setdefault(origin, ("dropped", "legacy_row0"))
    for origins in trace.structural_header_drops:
        for origin in origins:
            trace.final.setdefault(origin, ("dropped", "structural_header"))

    _markdown_stage(tp, trace, matrix, O3)
    # anything never placed (should not happen) is flagged
    for r in range(R):
        for c in range(C):
            for origin in O0[r][c]:
                trace.final.setdefault(origin, ("dropped", "untracked"))
    return trace


def _finish_empty(trace: Trace, O0):
    trace.markdown = ""
    for row in O0:
        for origins in row:
            for origin in origins:
                trace.final.setdefault(origin, ("dropped", "empty_grid"))


def _norm(text) -> str:
    if text is None:
        return ""
    return str(text).replace("\xa0", " ").strip()


def _markdown_stage(tp, trace: Trace, matrix, O3):
    if not matrix:
        trace.markdown = ""
        return
    nrows = len(matrix)
    ncols = len(matrix[0]) if matrix else 0

    # _process_headers
    if nrows < 2:
        headers = [_norm(v) for v in matrix[0]]
        header_o = [O3[0][j] for j in range(ncols)]
        data, data_o = [], []
    else:
        row0 = [_norm(v) for v in matrix[0]]
        row1 = [_norm(v) for v in matrix[1]]
        nonempty_row1 = sum(1 for v in row1 if v)
        many_blanks_in_row0 = sum(1 for v in row0 if v == "") >= max(2, ncols // 2)
        if nonempty_row1 >= max(2, ncols // 2) and many_blanks_in_row0:
            trace.fused = True
            headers, header_o = [], []
            for j in range(ncols):
                top = row0[j] if j < len(row0) else ""
                bot = row1[j] if j < len(row1) else ""
                if top and bot:
                    headers.append(f"{top} — {bot}")
                elif top:
                    headers.append(top)
                elif bot:
                    headers.append(bot)
                else:
                    headers.append("")
                header_o.append(O3[0][j] + O3[1][j])
            data, data_o = matrix[2:], O3[2:]
        else:
            headers, header_o = row0, [O3[0][j] for j in range(ncols)]
            data, data_o = matrix[1:], O3[1:]
    trace.headers = list(headers)

    # _clean_empty_rows_and_cols
    kept = list(range(len(headers)))
    if data:
        hn = len(headers)
        rows = [(row, o) for row, o in zip(data, data_o) if any(_norm(cell) for cell in row)]
        if not rows:
            data, data_o = [], []
        else:
            with_content = set()
            for row, _ in rows:
                for j, cell in enumerate(row):
                    if j < hn and _norm(cell):
                        with_content.add(j)
            if not with_content:
                trace.clean_all_dropped = True
                for j, origins in enumerate(header_o):
                    for origin in origins:
                        trace.final.setdefault(origin, ("dropped", "clean_all"))
                headers, header_o, data, data_o, kept = [], [], [], [], []
            else:
                kept = sorted(with_content)
                for j in range(hn):
                    if j not in with_content and headers[j]:
                        trace.clean_col_drops.append({"col": j, "header": headers[j], "origins": header_o[j]})
                        for origin in header_o[j]:
                            trace.final.setdefault(origin, ("dropped", "clean_header_only_col"))
                headers = [headers[j] for j in kept if j < len(headers)]
                header_o = [header_o[j] for j in kept if j < len(header_o)]
                data = [[row[j] if j < len(row) else "" for j in kept] for row, _ in rows]
                data_o = [[o[j] if j < len(o) else () for j in kept] for _, o in rows]
    trace.kept_cols = kept

    if not headers and not data:
        trace.markdown = ""
        return
    lines = []
    if headers:
        lines.append("| " + " | ".join(_escape_table_pipes(str(h)) for h in headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for j, origins in enumerate(header_o):
        for origin in origins:
            trace.final.setdefault(origin, ("header", j))
    for i, (row, o) in enumerate(zip(data, data_o)):
        row = list(row)
        while len(row) < len(headers):
            row.append("")
        lines.append("| " + " | ".join(_escape_table_pipes(str(cell)) for cell in row[:len(headers)]) + " |")
        for j, origins in enumerate(o[:len(headers)]):
            for origin in origins:
                trace.final.setdefault(origin, ("body", i, j))
        for origins in o[len(headers):]:
            for origin in origins:
                trace.final.setdefault(origin, ("dropped", "truncated"))
    trace.markdown = "\n".join(lines)


def output_col(place) -> int | None:
    if place is None or place[0] == "dropped":
        return None
    return place[-1]
