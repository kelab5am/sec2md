"""Limitation prevalence: five detectors on the source HTML, and their effect on the branch.

    PYTHONIOENCODING=utf-8 <wt>/venv/Scripts/python prevalence.py --branch-src <wt>/src \
        --recent-cache <CACHE> [--phase-a --fixtures-root <main> [--edgar-cache <cache>]] \
        --out prevalence.json [--workers N]

The five named limitations of spec 2026-10-05-sec2md-table-merge-header-rules-design.md,
revision 17. Each detector reads its source condition from the HTML, as the branch's
`Parser(html)` parses it, and records whether the branch's output shows the effect
(`affected`). The branch runs as `convert_to_markdown` runs it under the default strict
policy: `Parser(html)` (normal mode, table checks on), then `get_pages()`.

| Detector | Source condition | Effect on the branch |
|---|---|---|
| wrapped_table | An outermost table with an R0 header zone (two or more rows with text, so the branch renders it with TableParser) inside li, b, strong, i, em or a non-block element the parser reads as bold or italic | header_accounting_misses holds `<element>:missing` for the table's element |
| zero_width_number | U+200B, U+200C, U+200D, U+2060 or U+FEFF between two digits, between a digit and `,` `.` `(` `)`, or between a sign (`-`, U+2212, U+2013, not after a digit) and its digits, in a td or th's own text | a trace failure `<element>:<token>` or `<element>:header:<token>` for a token the removal joins |
| header_row_table | A table whose nearest tr ancestor (no td or th between them) is in its table's R0 header zone | a trace failure `<element>:header:<token>` for a number of the nested table |
| sub_label_currency | A body column other than R0's label column holds two or more distinct currency codes (the letter codes and US$, HK$, NT$, A$, C$, S$ of the branch's closed list), each directly before an amount: the next non-empty cell of its row is a complete number | the branch's output slot holding the code holds more than the code |
| page_top_part_table | A one-row table whose first cell is a PART label, with other non-empty cells, whose segment (or its inline wrapper's) is the first text of its page | the sections (10-K, 10-Q, 20-F, 8-K) differ from those the branch gives with these tables written as main writes them (`PART II` alone); document level |

Tables are the check_tables units: visible outermost tables, numbered from 1 in document
order (`table`). Phase A's 109 documents are loaded as the table merge acceptance tooling
loads them (corpus_phase_a.documents(edgar_cache, True), run inside a `git archive c674828`
tree); the recent corpus by corpus_recent.documents(cache).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import multiprocessing
import os
import re
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
AUDITS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(AUDITS)))
PHASE_A_DIR = os.path.join(AUDITS, "2026-10-03-table-completeness-corpus")
PHASE_A = os.path.join(PHASE_A_DIR, "corpus_phase_a.py")
PHASE_A_RESULTS = os.path.join(PHASE_A_DIR, "results.json")
DEFAULT_EDGAR_CACHE = os.path.join(ROOT, "outputs", "table-completeness-corpus")

DETECTORS = ("wrapped_table", "zero_width_number", "header_row_table", "sub_label_currency",
             "page_top_part_table")
FILING_TYPES = ("10-K", "10-Q", "20-F", "8-K")
NEAR_KEYS = ("wrapped_any", "wrapped_one_row", "wrapped_no_header_zone", "styled_not_read",
             "zero_width_cells", "zero_width_touches_digit", "nested_tables", "nested_in_row",
             "nested_row_unmapped", "code_tables", "code_before_amount", "part_one_row",
             "part_with_cells", "part_not_first", "part_page_unknown")
ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
_ZW_RUN = f"[{ZERO_WIDTH}]+"
# A zero-width run between two digits, between a digit and , . ( ) on either side, or between
# a sign (-, U+2212 minus, U+2013 en dash) and the digits after it (fix round 1); a dash after a
# digit is a range dash ("2023-2024"), not a sign (fix round 2).
_SPLIT_NUMBER = re.compile(
    rf"(?<=\d){_ZW_RUN}(?=[\d,.()])|(?<=[,.()]){_ZW_RUN}(?=\d)"
    rf"|(?<=(?<!\d)[\-\u2212\u2013]){_ZW_RUN}(?=\d)")
_REMOVE_ZW = str.maketrans(dict.fromkeys(ZERO_WIDTH))
_TOUCHES_DIGIT = re.compile(rf"\d{_ZW_RUN}|{_ZW_RUN}\d")
_STYLED = re.compile(r"font-weight\s*:\s*(?:bold|bolder|[6-9]00)|font-style\s*:\s*(?:italic|oblique)",
                     re.I)
EXCERPT = 160


# --- helpers -------------------------------------------------------------------------------

def _excerpt(text, limit=EXCERPT):
    """One line of text, zero-width characters shown as <U+XXXX>, cut to limit characters."""
    text = " ".join(text.split())
    text = "".join(f"<U+{ord(ch):04X}>" if ch in ZERO_WIDTH else ch for ch in text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _units(soup):
    """check_tables' units: visible outermost tables in document order."""
    from sec2md.table_completeness import hidden_sets

    outermost, hidden, _ = hidden_sets(soup)
    return [table for table in outermost if id(table) not in hidden]


def _is_block(element):
    """The parser's block test (Parser._stream_pages): a block tag, not inline-displayed or
    absolutely positioned."""
    from sec2md.parser import Parser

    return (Parser._is_block(element) and element.name not in {"br", "hr"}
            and not Parser._is_inline_display(element)
            and not Parser._is_absolutely_positioned(element))


def _wrapper_name(element):
    """The wrapper's name when element renders its content inline, else None."""
    from sec2md.parser import Parser

    if element.name == "li":
        return "li"
    if (Parser._is_bold(element) or Parser._is_italic(element)) and not _is_block(element):
        style = " ".join((element.get("style") or "").split())
        return element.name if element.name in {"b", "strong", "i", "em"} else f"{element.name}[{style}]"
    return None


def _cell_ancestor(node, stop):
    """The nearest td or th above node, up to (not including) stop; None when there is none."""
    for parent in node.parents:
        if parent is stop or parent is None:
            return None
        if parent.name in ("td", "th"):
            return parent
    return None


def _grid_rows(table):
    """The tr of each row of TableParser(table).cells, rebuilt as _extract_cells reads them."""
    from sec2md.table_parser import _descendants_named, _grid_hidden_within

    rows, hidden = [], {}
    for tr in _descendants_named(table, ("tr",)):
        if _grid_hidden_within(tr, table, hidden):
            continue
        cells = _descendants_named(tr, ("td", "th"))
        if cells and all(_grid_hidden_within(td, table, hidden) for td in cells):
            rows.append(tr)
            continue
        if [td for td in cells if not _grid_hidden_within(td, table, hidden)]:
            rows.append(tr)
    return rows


def _source_row(parser, tr):
    """The source-grid row index of a tr in a TableParser, or None when it has none."""
    rows = _grid_rows(parser.table_element)
    if len(rows) != len(parser.cells):
        return None
    try:
        index = next(i for i, row in enumerate(rows) if row is tr)
    except StopIteration:
        return None
    cells = parser.cells[index]
    for j, grid_row in enumerate(parser.source_grid):
        if any(slot is not None and not slot.is_spanning and any(slot.cell is cell for cell in cells)
               for slot in grid_row):
            return j
    return None


def _element_of(node, node_elements):
    """The element mapped to node or to its nearest mapped ancestor."""
    for candidate in (node, *node.parents):
        if candidate is None:
            break
        element = node_elements.get(id(candidate))
        if element is not None:
            return element
    return None


def _strip_id(failure):
    return failure.split(":", 1)[1] if ":" in failure else failure


# --- detectors on the source -----------------------------------------------------------------

def find_wrapped_tables(parser, units, near=None):
    """Outermost tables with an R0 header zone, rendered inside an inline wrapper or list item.

    near counts the looser conditions: any wrapped table (wrapped_any), one written as one
    line (wrapped_one_row) or without a header zone (wrapped_no_header_zone), and a table
    under an inline element styled bold or italic in a form the parser does not read as
    such, e.g. "font-weight: bold" (styled_not_read)."""
    from sec2md.table_parser import TableParser

    near = Counter() if near is None else near
    found = []
    for ordinal, table in enumerate(units, start=1):
        parents = [parent for parent in table.parents if getattr(parent, "name", None)]
        wrappers = [name for name in (_wrapper_name(parent) for parent in parents) if name]
        if not wrappers:
            near["styled_not_read"] += any(
                _STYLED.search(parent.get("style") or "") and not _is_block(parent)
                for parent in parents)
            continue
        near["wrapped_any"] += 1
        if len(parser._effective_rows(table)) <= 1:
            near["wrapped_one_row"] += 1
            continue  # written as one line, never through TableParser: no header zone
        header_rows = TableParser(table).roles.header_rows
        if not header_rows:
            near["wrapped_no_header_zone"] += 1
            continue
        found.append({"table": ordinal, "node": table, "wrappers": wrappers,
                      "header_rows": len(header_rows),
                      "excerpt": _excerpt(table.get_text(" ", strip=True))})
    return found


def find_zero_width_numbers(units, near=None):
    """Zero-width runs that split a number inside a cell's own text.

    near counts the cells whose own text holds a zero-width character (zero_width_cells) and
    those where one touches a digit (zero_width_touches_digit)."""
    from bs4.element import NavigableString

    near = Counter() if near is None else near
    found = []
    for ordinal, table in enumerate(units, start=1):
        cell_strings = defaultdict(list)
        cells = {}
        for string in table.find_all(string=True):
            if type(string) is not NavigableString:
                continue
            cell = _cell_ancestor(string, table)
            if cell is not None:
                cells[id(cell)] = cell
                cell_strings[id(cell)].append(str(string))
        for key, strings in cell_strings.items():
            text = "".join(strings)
            if not any(ch in text for ch in ZERO_WIDTH):
                continue
            near["zero_width_cells"] += 1
            near["zero_width_touches_digit"] += bool(_TOUCHES_DIGIT.search(text))
            matches = list(_SPLIT_NUMBER.finditer(text))
            if not matches:
                continue
            cell = cells[key]
            for match in matches:
                found.append({"table": ordinal, "node": table, "cell_node": cell,
                              "char": " ".join(f"U+{ord(ch):04X}" for ch in match.group(0)),
                              "cell": _excerpt(text),
                              "excerpt": _excerpt(text[max(0, match.start() - 20):match.end() + 20])})
    return found


def find_header_row_tables(units, near=None):
    """Tables whose nearest tr ancestor, with no cell between, is in its table's header zone.

    near counts every nested table (nested_tables), those in a tr with no cell between in
    any row (nested_in_row), and those whose row the grid does not map (nested_row_unmapped)."""
    from sec2md.table_parser import TableParser

    near = Counter() if near is None else near
    found = []
    parsers = {}
    for ordinal, unit in enumerate(units, start=1):
        for nested in unit.find_all("table"):
            near["nested_tables"] += 1
            path, row = [], None
            for parent in nested.parents:
                if parent.name in ("td", "th", "table"):
                    break
                if parent.name == "tr":
                    row = parent
                    break
                path.append(parent.name)
            if row is None:
                continue
            near["nested_in_row"] += 1
            outer = row.find_parent("table")
            if id(outer) not in parsers:
                parsers[id(outer)] = TableParser(outer)
            parser = parsers[id(outer)]
            index = _source_row(parser, row)
            near["nested_row_unmapped"] += index is None
            if index is None or index not in parser.roles.header_rows:
                continue
            found.append({"table": ordinal, "node": unit, "nested": nested,
                          "via": [*reversed(path), "tr"], "outer_is_unit": outer is unit,
                          "excerpt": _excerpt(nested.get_text(" ", strip=True))})
    return found


def _currency_codes():
    """The codes of the branch's closed currency list: the letter codes (EUR, RMB, ...) and the
    letter-prefixed dollar codes (US$, HK$, NT$, A$, C$, S$), not the bare symbols ($ € £ ¥),
    which R4 joins by design (fix round 1 added the dollar codes)."""
    from sec2md.table_roles import CURRENCY_MARKERS

    return frozenset(marker for marker in CURRENCY_MARKERS
                     if marker.isalpha() or (marker.endswith("$") and marker[:-1].isalpha()))


def find_sub_label_currencies(units, near=None):
    """Body columns other than R0's label column holding two or more distinct currency codes,
    each directly before an amount (the next non-empty cell of its row is a complete number).
    One occurrence per such column. Fix round 2 widened "the column next to the label column"
    to any non-label column (TSM-20-F-2023 table 278 has a Maturity Date column between).

    near counts the tables with two or more distinct codes as whole-cell text anywhere
    (code_tables) and those with at least one non-label body code directly before an amount
    (code_before_amount)."""
    from sec2md.table_parser import TableParser, _origin_cells
    from sec2md.table_roles import is_complete_number, row_values, visible_text

    near = Counter() if near is None else near
    codes = _currency_codes()
    found = []
    for ordinal, table in enumerate(units, start=1):
        present = {visible_text(cell.get_text(" ", strip=True)) for cell in table.find_all(["td", "th"])}
        if len(present & codes) < 2:
            continue
        near["code_tables"] += 1
        parser = TableParser(table)
        label = parser.roles.label_column
        if label is None:
            continue
        origin = _origin_cells(parser.source_grid)
        by_column = defaultdict(list)
        for row in range(len(parser.source_grid)):
            if parser.roles.role(row) != "body":
                continue
            values = row_values(origin[row])
            for position, (index, text) in enumerate(values):
                if (index != label and text in codes and position + 1 < len(values)
                        and is_complete_number(values[position + 1][1])):
                    by_column[index].append((row, text, values[position + 1][1]))
        near["code_before_amount"] += bool(by_column)
        for column, rows in sorted(by_column.items()):
            if len({code for _, code, _ in rows}) < 2:
                continue
            found.append({"table": ordinal, "node": table, "parser": parser, "column": column,
                          "code_rows": rows, "codes": sorted({code for _, code, _ in rows}),
                          "rows": len(rows),
                          "excerpt": _excerpt(" | ".join(f"{code} {amount}" for _, code, amount in rows))})
    return found


def _one_row_texts(parser, cells):
    """The cell texts Parser._one_row_table_to_text reads."""
    from sec2md.table_parser import render_cell_content
    from sec2md.utils import clean_text

    return [render_cell_content(cell, base_url=parser.source_url) if cell.find("a")
            else clean_text(cell.get_text(" ", strip=True)) for cell in cells]


def find_page_top_part_tables(parser, units, near=None):
    """One-row tables whose first cell is a PART label, with other non-empty cells, whose
    segment is the first text of its page. Needs get_pages() to have run.

    A table rendered inside another element (an inline wrapper) has no page of its own in
    the parser; it is first on the page whose first segment belongs to one of its ancestors and
    opens with its line, bold or italic markers aside (fix round 1).

    near counts the one-row PART tables (part_one_row), those with other non-empty cells
    (part_with_cells) and, of those, the ones not first on their known page (part_not_first)
    and the wrapped ones not found first on any page (part_page_unknown)."""
    from sec2md.parser import PART_HEADER_CELL_RE

    near = Counter() if near is None else near
    first = {}
    for page, segments in parser.page_segments.items():
        for text, source_ref, _ in segments:
            if text.strip():
                first[page] = ({id(node) for node in parser._source_nodes(source_ref)}, text)
                break
    found = []
    for ordinal, table in enumerate(units, start=1):
        rows = parser._effective_rows(table)
        if len(rows) != 1 or not rows[0]:
            continue
        texts = _one_row_texts(parser, rows[0])
        if not PART_HEADER_CELL_RE.match(texts[0]):
            continue
        near["part_one_row"] += 1
        if not any(texts[1:]):
            continue
        near["part_with_cells"] += 1
        line = parser._one_row_table_to_text(rows[0])
        page = parser._table_pages.get(id(table))
        if page is None:
            ancestors = {id(parent) for parent in table.parents}
            page = next((number for number, (nodes, text) in sorted(first.items())
                         if nodes & ancestors and text.strip().lstrip("*_ ").startswith(line)), None)
            if page is None:
                near["part_page_unknown"] += 1
                continue
        elif id(table) not in first.get(page, (set(), ""))[0]:
            near["part_not_first"] += 1
            continue
        found.append({"table": ordinal, "page": page, "line": line,
                      "excerpt": _excerpt(" | ".join(texts))})
    return found


# --- effects on the branch -------------------------------------------------------------------

def _sections(pages):
    from sec2md.sections import extract_sections

    out = {}
    for filing_type in FILING_TYPES:
        try:
            out[filing_type] = [[s.part, s.item, s.item_title, [p.number for p in s.pages]]
                                for s in extract_sections(pages, filing_type=filing_type)]
        except Exception as exc:  # recorded and compared like any result
            out[filing_type] = f"error: {type(exc).__name__}: {exc}"
    return out


def _main_part_lines_sections(html, ordinals):
    """Sections when the given unit tables are written as main writes a PART table."""
    from sec2md.parser import PART_HEADER_CELL_RE, Parser

    class MainPartLines(Parser):
        targets: set = set()

        def _one_row_table_to_text(self, cells):
            if cells and id(cells[0].find_parent("table")) in self.targets:
                match = PART_HEADER_CELL_RE.match(_one_row_texts(self, cells[:1])[0])
                if match:
                    return f"PART {match.group(1).upper()}"
            return super()._one_row_table_to_text(cells)

    parser = MainPartLines(html)
    units = _units(parser.soup)
    parser.targets = {id(units[ordinal - 1]) for ordinal in ordinals}
    return _sections(parser.get_pages())


def analyse(html, context=None):
    """{detector: [occurrence]} for one document; each occurrence has table, affected,
    excerpt and its detector's evidence.

    A context dict, when given, receives the detectors' near-miss counts ("near") and the
    branch's own counts for the document ("branch"): units, pages, trace failures, header
    excesses and header-accounting misses, whichever table caused them."""
    from sec2md.parser import Parser

    near = Counter(dict.fromkeys(NEAR_KEYS, 0))
    parser = Parser(html)
    units = _units(parser.soup)
    found = {
        "wrapped_table": find_wrapped_tables(parser, units, near),
        "zero_width_number": find_zero_width_numbers(units, near),
        "header_row_table": find_header_row_tables(units, near),
        "sub_label_currency": find_sub_label_currencies(units, near),
    }
    pages = parser.get_pages()
    found["page_top_part_table"] = find_page_top_part_tables(parser, units, near)
    if context is not None:
        context["near"] = dict(sorted(near.items()))
        failures_all = [_strip_id(f) for f in parser.trace_numeric_failures]
        misses_all = [_strip_id(m) for m in parser.header_accounting_misses]
        context["branch"] = {
            "units": len(units), "pages": len(pages), "trace_failures": len(failures_all),
            "header_failures": sum(f.startswith("header:") for f in failures_all),
            "missing": misses_all.count("missing"), "ambiguous": misses_all.count("ambiguous"),
            "failure_tokens": sorted(failures_all)[:20]}

    node_elements = {id(node): element_id
                     for element_id, nodes in parser.block_nodes_map.items() for node in nodes}
    failures, misses = defaultdict(list), defaultdict(list)
    for failure in parser.trace_numeric_failures:
        element_id, rest = failure.split(":", 1)
        failures[element_id].append(rest)
    for miss in parser.header_accounting_misses:
        element_id, rest = miss.split(":", 1)
        misses[element_id].append(rest)

    out = {name: [] for name in DETECTORS}
    for item in found["wrapped_table"]:
        element = _element_of(item["node"], node_elements)
        out["wrapped_table"].append({
            "table": item["table"], "affected": "missing" in misses.get(element, ()),
            "wrappers": item["wrappers"], "header_rows": item["header_rows"], "element": element,
            "misses": misses.get(element, []), "trace_failures": failures.get(element, []),
            "excerpt": item["excerpt"]})

    from sec2md.quality import _normalized_numbers

    for item in found["zero_width_number"]:
        element = _element_of(item["node"], node_elements)
        spaced = item["cell_node"].get_text(" ", strip=True)
        joined = Counter(_normalized_numbers(spaced.translate(_REMOVE_ZW))) - Counter(
            _normalized_numbers(spaced))
        element_failures = failures.get(element, ())
        hits = [failure for token in sorted(joined) for failure in (token, f"header:{token}")
                if failure in element_failures]
        out["zero_width_number"].append({
            "table": item["table"], "affected": bool(hits), "char": item["char"],
            "joined": sorted(joined), "element": element, "failures": hits,
            "cell": item["cell"], "excerpt": item["excerpt"]})

    for item in found["header_row_table"]:
        element = _element_of(item["node"], node_elements)
        numbers = set(_normalized_numbers(item["nested"].get_text(" ", strip=True)))
        excess = [f for f in failures.get(element, ())
                  if f.startswith("header:") and f.split(":", 1)[1] in numbers]
        out["header_row_table"].append({
            "table": item["table"], "affected": bool(excess), "via": item["via"],
            "outer_is_unit": item["outer_is_unit"], "element": element, "header_failures": excess,
            "excerpt": item["excerpt"]})

    from sec2md.table_roles import visible_text

    for item in found["sub_label_currency"]:
        parser_t = item["parser"]
        joined = []
        for row, code, _ in item["code_rows"]:
            source = parser_t.source_grid[row][item["column"]].cell
            for column in parser_t.columns:
                slot = column.slots[row]
                if any(cell is source for cell in slot.cells):
                    if visible_text(slot.text) != code:
                        joined.append(visible_text(slot.text))
                    break
        out["sub_label_currency"].append({
            "table": item["table"], "affected": bool(joined), "column": item["column"],
            "codes": item["codes"],
            "rows": item["rows"], "joined": joined, "excerpt": item["excerpt"]})

    page_top = found["page_top_part_table"]
    if page_top:
        branch = _sections(pages)
        # Free the first parse (its soup) before the second one.
        del parser, pages, units, found, node_elements
        reverted = _main_part_lines_sections(html, [item["table"] for item in page_top])
        differ = [t for t in FILING_TYPES if branch[t] != reverted[t]]
        for item in page_top:
            out["page_top_part_table"].append({
                "table": item["table"], "affected": bool(differ), "page": item["page"],
                "line": item["line"], "sections_differ": differ, "excerpt": item["excerpt"]})
    return out


def summarize(records):
    """Per detector: documents, tables and occurrences found, and those affected."""
    summary = {}
    for name in DETECTORS:
        documents = tables = occurrences = affected = affected_tables = affected_documents = 0
        for record in records.values():
            items = record.get(name) or []
            if not items:
                continue
            documents += 1
            tables += len({item["table"] for item in items})
            occurrences += len(items)
            hit = [item for item in items if item["affected"]]
            affected += len(hit)
            affected_tables += len({item["table"] for item in hit})
            affected_documents += bool(hit)
        summary[name] = {"documents": documents, "tables": tables, "occurrences": occurrences,
                         "affected": affected, "affected_tables": affected_tables,
                         "affected_documents": affected_documents}
    return summary


# --- corpora and the run ---------------------------------------------------------------------

def _check_src(branch_src):
    import sec2md

    location = os.path.normcase(os.path.abspath(sec2md.__file__))
    expected = os.path.normcase(os.path.abspath(branch_src))
    if not location.startswith(expected + os.sep):
        raise SystemExit(f"sec2md imported from {location}, expected under {expected}")
    return sec2md.__file__


def _init(branch_src):
    import logging
    import warnings

    if branch_src not in sys.path:
        sys.path.insert(0, branch_src)
    warnings.filterwarnings("ignore")
    logging.disable(logging.CRITICAL)
    _check_src(branch_src)


def _work(item):
    doc_id, raw = item
    from sec2md.encoding import decode_html

    started = time.perf_counter()
    try:
        context = {}
        record = analyse(decode_html(raw)[0], context)
        record["context"] = context
        error = None
    except Exception as exc:  # recorded per document and reported
        record, error = None, f"{type(exc).__name__}: {exc}"
    return doc_id, record, error, round(time.perf_counter() - started, 1)


def run(docs, branch_src, workers):
    """{doc id: record}, {doc id: error}, {doc id: seconds} over (id, group, raw) documents."""
    records, errors, seconds = {}, {}, {}
    order = sorted(((doc_id, raw) for doc_id, _, raw in docs), key=lambda d: -len(d[1]))
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(workers, initializer=_init, initargs=(branch_src,)) as pool:
        for doc_id, record, error, took in pool.imap_unordered(_work, order):
            seconds[doc_id] = took
            if error:
                errors[doc_id] = error
            else:
                records[doc_id] = record
            print(f"{doc_id}: {took:.1f}s{' ERROR ' + error if error else ''}", file=sys.stderr,
                  flush=True)
    ids = [doc_id for doc_id, _, _ in docs]
    return ({k: records[k] for k in ids if k in records}, {k: errors[k] for k in ids if k in errors},
            {k: seconds[k] for k in ids})


def phase_a_documents(edgar_cache, fixtures_root):
    """(docs, duplicates) from corpus_phase_a.documents(edgar_cache, True), run inside
    fixtures_root, as acc_common.load_documents does."""
    spec = importlib.util.spec_from_file_location("corpus_phase_a", PHASE_A)
    module = importlib.util.module_from_spec(spec)
    here = os.getcwd()
    os.chdir(fixtures_root)
    try:
        spec.loader.exec_module(module)
        return module.documents(edgar_cache, True)
    finally:
        os.chdir(here)


def phase_a_hash_check(docs):
    with open(PHASE_A_RESULTS, encoding="utf-8") as handle:
        expected = {d["id"]: d["sha256"] for d in json.load(handle)["documents"]}
    matched = sum(expected.get(doc_id) == hashlib.sha256(raw).hexdigest() for doc_id, _, raw in docs)
    return {"documents": len(docs), "results_json_documents": len(expected), "matched": matched,
            "ok": matched == len(docs) == len(expected) == 109}


def corpus_record(docs, skipped, branch_src, workers):
    started = time.perf_counter()
    records, errors, seconds = run(docs, branch_src, workers)
    occurrences = {
        name: [{"doc": doc_id, **item} for doc_id, record in records.items() for item in record[name]]
        for name in DETECTORS
    }
    context = {}
    for part in ("near", "branch"):
        keys = sorted({key for record in records.values()
                       for key, value in record["context"][part].items() if not isinstance(value, list)})
        context[part] = {
            key: {"total": sum(r["context"][part].get(key, 0) for r in records.values()),
                  "documents": sum(bool(r["context"][part].get(key)) for r in records.values())}
            for key in keys}
    context["branch_effects"] = {
        doc_id: record["context"]["branch"] for doc_id, record in records.items()
        if any(record["context"]["branch"][key] for key in ("trace_failures", "missing", "ambiguous"))}
    context["near_documents"] = {
        doc_id: record["context"]["near"] for doc_id, record in records.items()
        if any(value for key, value in record["context"]["near"].items()
               if key not in ("nested_tables", "zero_width_cells", "code_tables"))}
    return {"documents": len(docs), "analysed": len(records), "skipped": skipped, "errors": errors,
            "summary": summarize(records), "occurrences": occurrences, "context": context,
            "wall_seconds": round(time.perf_counter() - started, 1), "document_seconds": seconds}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--branch-src", required=True, help="the tmh-proto worktree's src")
    ap.add_argument("--recent-cache", required=True, help="outputs/recent-filings-corpus")
    ap.add_argument("--phase-a", action="store_true", help="also run the 109 Phase A documents")
    ap.add_argument("--fixtures-root", help="a git archive c674828 tree (with --phase-a)")
    ap.add_argument("--edgar-cache", default=DEFAULT_EDGAR_CACHE, help="Phase A's EDGAR cache")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--only", nargs="*", help="document ids to run (debugging)")
    args = ap.parse_args(argv)
    if args.phase_a and not args.fixtures_root:
        ap.error("--phase-a needs --fixtures-root")
    branch_src = os.path.abspath(args.branch_src)
    sys.path.insert(0, branch_src)
    sys.path.insert(0, HERE)
    location = _check_src(branch_src)

    import corpus_recent

    result = {"tool": "prevalence.py", "sec2md_file": location, "branch_src": branch_src,
              "run": "Parser(html) (normal mode, table checks on), get_pages(): as convert_to_markdown "
                     "under the default strict policy",
              "detectors": list(DETECTORS), "corpora": {}}
    docs, skipped = corpus_recent.documents(args.recent_cache)
    if args.only:
        docs = [d for d in docs if d[0] in args.only]
    result["corpora"]["recent"] = corpus_record(docs, skipped, branch_src, args.workers)
    if args.phase_a:
        docs, duplicates = phase_a_documents(args.edgar_cache, os.path.abspath(args.fixtures_root))
        hashes = phase_a_hash_check(docs)
        if not hashes["ok"]:
            raise SystemExit(f"Phase A hash check failed: {hashes}")
        if args.only:
            docs = [d for d in docs if d[0] in args.only]
        record = corpus_record(docs, duplicates, branch_src, args.workers)
        record["hash_check"] = hashes
        result["corpora"]["phase_a"] = record
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(json.dumps({name: corpus["summary"] for name, corpus in result["corpora"].items()}, indent=1))


if __name__ == "__main__":
    main()
