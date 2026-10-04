"""Corpus loading and per-document tracing shared by measure.py (research only).

Loads the Phase A corpus exactly as ../2026-10-03-table-completeness-corpus/corpus_phase_a.py
does (its `documents()`, imported with importlib), parses each document in normal mode
with `sec2md.parser.TableParser` replaced by the recording subclass, and yields one
record per check_tables unit (visible outermost table, same ordinal). Run from the
repository root so the fixture paths in corpus_phase_a resolve.
"""
from __future__ import annotations

import importlib.util
import os
import warnings

import sec2md.parser as parser_module
from sec2md.encoding import decode_html
from sec2md.parser import Parser
from sec2md.table_completeness import (
    _direct_cells, cell_text, header_row_count, hidden_sets, is_data_row, merge_split_negatives, unit_rows,
)

from trace_merge import AMOUNT, BARE_YEAR, DASH, DIGIT, TracingTableParser, shadow, source_trs, vis

HERE = os.path.dirname(os.path.abspath(__file__))
PHASE_A = os.path.join(HERE, "..", "2026-10-03-table-completeness-corpus", "corpus_phase_a.py")
RESULTS = os.path.join(HERE, "..", "2026-10-03-table-completeness-corpus", "results.json")
CLASSIFICATION = os.path.join(HERE, "..", "2026-10-03-table-completeness-corpus", "classification.md")


def phase_a_module():
    spec = importlib.util.spec_from_file_location("corpus_phase_a", PHASE_A)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def documents(edgar_cache, include_rcq=True):
    return phase_a_module().documents(edgar_cache, include_rcq)


class UnitRecord:
    """One check_tables unit: the source table, how it was rendered and, if TableParser ran, its trace."""

    def __init__(self, ordinal, table, output, tracer, trace, trs, header_trs, header_rows, src_rows, path):
        self.ordinal = ordinal
        self.table = table
        self.output = output            # text the parser emitted for this unit (None: no output entry)
        self.tracer = tracer
        self.trace = trace
        self.trs = trs                  # TableParser row -> tr
        self.header_trs = header_trs    # ids of the tr elements header_row_count calls header rows
        self.header_rows = header_rows  # header_row_count
        self.src_rows = src_rows        # {id(tr): cell texts as check_tables reads them}
        self.path = path                # "tableparser" | "one_row" | "no_output"

    # G0 row helpers -------------------------------------------------------------------
    def g0_tr(self, g0_row):
        return self.trs[g0_row] if g0_row < len(self.trs) else None

    def g0_is_header(self, g0_row):
        tr = self.g0_tr(g0_row)
        return tr is not None and id(tr) in self.header_trs

    def g0_texts(self, g0_row):
        """Visible cell texts of a raw-grid row (zero-width spaces removed; see trace_merge.vis)."""
        return [vis(cell.text) if cell is not None and not cell.is_spanning else "" for cell in self.trace.g0[g0_row]]

    def g0_is_data(self, g0_row):
        """check_tables' data-row test on this row's TableParser cell texts."""
        values = merge_split_negatives([t for t in self.g0_texts(g0_row) if t.strip()])
        return is_data_row(values, False)

    def g0_has_amount(self, g0_row):
        """Stricter body test: a cell holding an amount that is not a bare year or a one-digit number.

        check_tables' is_data_row calls "2023 | Change | 2022" a data row (the years are standalone
        amounts and "Change" is not period text), so the header zone is found with this test.
        """
        for text in self.g0_texts(g0_row):
            t = text.strip()
            if AMOUNT.match(t) and not BARE_YEAR.match(t) and (len(DIGIT.findall(t)) >= 2 or "." in t):
                return True
        return False

    def g0_is_body(self, g0_row):
        """Where the body starts: an amount (g0_has_amount) or a nil dash ("$ —" rows are data)."""
        return self.g0_has_amount(g0_row) or any(DASH.match(t.strip()) for t in self.g0_texts(g0_row))


def trace_document(html):
    """Parse one document in normal mode with tracing; return (parser, [UnitRecord])."""
    TracingTableParser.registry = []
    original = parser_module.TableParser
    parser_module.TableParser = TracingTableParser
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parser = Parser(html, capture_tables=False)
            parser.get_pages(include_images=False)
    finally:
        parser_module.TableParser = original
    tracers = {}
    for element, tracer in TracingTableParser.registry:
        tracers.setdefault(id(element), []).append((element, tracer))

    outermost, hidden, grid_hidden = hidden_sets(parser.soup)
    units = [t for t in outermost if id(t) not in hidden]
    records = []
    for ordinal, table in enumerate(units, 1):
        output = parser.table_outputs.get(id(table))
        found = [tr for el, tr in tracers.get(id(table), []) if el is table]
        tracer = found[-1] if found else None
        all_rows = unit_rows(table)
        header_rows = header_row_count(table, all_rows, grid_hidden)
        own = [row for row in all_rows if row.own and id(row.tr) not in grid_hidden]
        header_trs = {id(row.tr) for row in own[:header_rows]}
        visible = [row for row in all_rows if id(row.tr) not in hidden]
        src_rows = {id(row.tr): [cell_text(c, hidden)[0] for c in _direct_cells(row.tr) if id(c) not in hidden]
                    for row in visible}
        if tracer is not None:
            trs = source_trs(table)
            trace = shadow(tracer, tracer.raw_grid)
            path = "tableparser"
        else:
            trs, trace = [], None
            path = "one_row" if output is not None else "no_output"
        records.append(UnitRecord(ordinal, table, output, tracer, trace, trs, header_trs, header_rows,
                                  src_rows, path))
    return parser, records
