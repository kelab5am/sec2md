"""Run one side (baseline or candidate) over the Phase A corpus in both rendering modes.

    PYTHONPATH=<side>/src python run_side.py --side main|candidate --expect-src <side>/src \
        --fixtures-root <checkout with tests/fixtures/sec> --edgar-cache <cache> --out-dir <dir> [--workers N]

For every document and mode it runs `Parser(html, capture_tables=mode).get_pages(include_images=False)`
(table checks on, as Phase A) and writes <out-dir>/<document>.json.gz with:

- each check_tables unit's output segment and how it was rendered (tableparser, one_row,
  unreliable capture text, no_output);
- check 1 and check 2 findings in Phase A's record format, tables_checked, check 3's recall;
- strict: the diagnostics warnings, the trace failures, and header_accounting_misses
  (candidate only);
- the header-alignment findings and coverage (candidate only);
- page numbers and display pages, and the sections extract_sections() returns for each
  filing type in acc_common.FILING_TYPES;
- capture mode only: every table snapshot's prepared XLSX table (xlsx_tables.prepare_table),
  as a SHA-256 of its full repr with the snapshot's element_id cleared (element ids hash
  element content, which table rendering changes), plus its status.

It also writes <out-dir>/_run.json: sec2md.__file__, the document hash check against
results.json and edgar_manifest.json, and the run time.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import multiprocessing
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402

_ARGS = None


def _init(args):
    global _ARGS
    _ARGS = args
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.CRITICAL)


def parse(html, capture):
    """Parse one document; return (parser, pages, rendered tables by identity)."""
    import sec2md.parser as parser_module
    from sec2md.parser import Parser

    registry = []
    base = parser_module.TableParser

    class Recording(base):
        def __init__(self, table_element, *, base_url=None):
            super().__init__(table_element, base_url=base_url)
            registry.append(table_element)

    parser_module.TableParser = Recording
    try:
        parser = Parser(html, capture_tables=capture)
        pages = parser.get_pages(include_images=False)
    finally:
        parser_module.TableParser = base
    return parser, pages, {id(t) for t in registry}


def section_records(pages):
    from sec2md.sections import extract_sections

    out = {}
    for filing_type in acc_common.FILING_TYPES:
        try:
            sections = extract_sections(pages, filing_type=filing_type)
            out[filing_type] = [[s.part, s.item, s.item_title, [p.number for p in s.pages]] for s in sections]
        except Exception as exc:  # recorded, compared like any result
            out[filing_type] = f"error: {type(exc).__name__}: {exc}"
    return out


def xlsx_records(parser):
    from sec2md.xlsx_tables import prepare_table, select_export_tables

    selected = {id(s) for s in select_export_tables(parser.table_snapshots)}
    out = []
    for snapshot in parser.table_snapshots:
        prepared = prepare_table(snapshot)
        neutral = dataclasses.replace(prepared, source=dataclasses.replace(prepared.source, element_id=None))
        out.append({
            "ordinal": snapshot.ordinal,
            "sha": hashlib.sha256(repr(neutral).encode("utf-8")).hexdigest(),
            "status": prepared.status,
            "export": id(snapshot) in selected,
            "headers": len(prepared.headers),
            "rows": len(prepared.rows),
        })
    return out


def mode_record(phase_a, html, capture):
    started = time.perf_counter()
    parser, pages, rendered = parse(html, capture)
    elapsed = time.perf_counter() - started
    units = acc_common.table_units(parser.soup)
    unit_records = []
    for table in units:
        output = parser.table_outputs.get(id(table))
        if id(table) in parser._unreliable_tables:
            path = "unreliable"
        elif id(table) in rendered:
            path = "tableparser"
        elif output is not None:
            path = "one_row"
        else:
            path = "no_output"
        unit_records.append({"path": path, "output": output})
    diagnostics = parser.diagnostics
    report = parser.table_report
    record = {
        "seconds": round(elapsed, 3),
        "units": unit_records,
        "tables_checked": report.tables_checked if report else None,
        "findings": [phase_a.finding_record(f) for f in report.findings] if report else None,
        "numeric_recall": diagnostics.numeric_recall,
        "warnings": [w if not w.startswith("untraceable normalized number: ")
                     else "untraceable normalized number: <see trace_failures>" for w in diagnostics.warnings],
        "trace_failures": list(diagnostics.trace_numeric_failures),
        "header_accounting_misses": (list(parser.header_accounting_misses)
                                     if hasattr(parser, "header_accounting_misses") else None),
        "alignment": list(getattr(diagnostics, "table_header_alignment", ()) or ()) if hasattr(
            diagnostics, "table_header_alignment") else None,
        "alignment_coverage": ([list(item) for item in diagnostics.table_header_alignment_coverage]
                               if hasattr(diagnostics, "table_header_alignment_coverage") else None),
        "pages": [[p.number, p.display_page] for p in pages],
        "page_content_sha": hashlib.sha256("\n\x00".join(p.content for p in pages).encode("utf-8")).hexdigest(),
        "sections": section_records(pages),
    }
    if capture:
        record["xlsx"] = xlsx_records(parser)
    return record


def work(item):
    doc_id, group, raw = item
    from sec2md.encoding import decode_html

    phase_a = acc_common.phase_a_module()
    html = decode_html(raw)[0]
    started = time.perf_counter()
    data = {"id": doc_id, "group": group, "sha256": hashlib.sha256(raw).hexdigest(), "side": _ARGS.side,
            "modes": {}}
    for mode in acc_common.MODES:
        data["modes"][mode] = mode_record(phase_a, html, mode == "capture")
    data["seconds"] = round(time.perf_counter() - started, 3)
    acc_common.write_json_gz(os.path.join(_ARGS.out_dir, acc_common.safe_name(doc_id)), data)
    return doc_id, data["seconds"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--side", required=True, choices=("main", "candidate"))
    ap.add_argument("--expect-src", required=True)
    ap.add_argument("--fixtures-root", required=True)
    ap.add_argument("--edgar-cache", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    location = acc_common.sec2md_location(args.expect_src)
    started = time.perf_counter()
    docs, duplicates = acc_common.load_documents(args.edgar_cache, args.fixtures_root)
    hashes = acc_common.verify_hashes(docs)
    print(json.dumps({"sec2md": location, "hash_check_ok": hashes["ok"]}), flush=True)
    if args.only:
        docs = [d for d in docs if d[0] in args.only]
    order = sorted(docs, key=lambda d: -len(d[2]))  # largest first, for balance
    times = {}
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(args.workers, initializer=_init, initargs=(args,)) as pool:
        for doc_id, seconds in pool.imap_unordered(work, order):
            times[doc_id] = seconds
            print(f"{doc_id}: {seconds:.1f}s", file=sys.stderr, flush=True)
    run = {"side": args.side, "sec2md_file": location, "hash_check": hashes, "duplicates_skipped": duplicates,
           "documents": [d[0] for d in docs], "document_seconds": times,
           "wall_seconds": round(time.perf_counter() - started, 1), "workers": args.workers}
    with open(os.path.join(args.out_dir, "_run.json"), "w", encoding="utf-8") as handle:
        json.dump(run, handle, indent=1)
    print(json.dumps({k: v for k, v in run.items() if k in ("side", "sec2md_file", "wall_seconds")}))


if __name__ == "__main__":
    main()
