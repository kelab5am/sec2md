"""Regenerate the evidence's 6,616 same-header merges with their source cells (baseline only).

    PYTHONPATH=<c674828 tree>/src python merges_main.py --expect-src <tree>/src \
        --fixtures-root <tree> --edgar-cache <cache> --out merges.json.gz [--workers N]

Replays main's TableParser with the evidence report's tracer
(../2026-10-04-table-merge-header-evidence/corpus.py and trace_merge.py) on every corpus
document in normal mode, and applies measure.py's class-2 classification unchanged. For
every legacy merge step that joins value columns under the same header
("value+value|same_header"), it records the source cells of both sides' body values:
each as (TableParser row, td index in that row's find_all(['td', 'th'])), which the
candidate side maps back to the same td element. The replay must reproduce the
parser's Markdown for every table (3,707), and the merge count must be 6,616.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time
import warnings
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402

sys.path.insert(0, acc_common.EVIDENCE_DIR)


def _init():
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.CRITICAL)


def classify(record, measure):
    """measure.detect's class-2 loop, keeping each same-header value+value step's cells."""
    from trace_merge import AMOUNT, is_marker, vis

    t = record.trace
    fdr = measure.first_data_row(record)
    r_from = fdr if fdr is not None else len(t.g0)
    keys = measure.header_keys(record, r_from)
    cell_ids = {id(cell): (r, k) for r, row in enumerate(record.tracer.cells) for k, cell in enumerate(row)}
    steps, counts = [], Counter()
    for index, m in enumerate(t.legacy_merges):
        a_rows, b_rows = {}, {}
        for k in range(1, len(m["a_cells"])):
            if t.rows_keep[k] < r_from:
                continue
            a, b = vis(m["a_cells"][k]), vis(m["b_cells"][k])
            if a and not is_marker(a):
                a_rows[k] = a
            if b and not is_marker(b):
                b_rows[k] = b
        a_only = {k: v for k, v in a_rows.items() if k not in b_rows}
        b_only = {k: v for k, v in b_rows.items() if k not in a_rows}
        if not (a_only and b_only):
            continue
        a_val = all(measure.real_value(v) for v in a_only.values()) and any(AMOUNT.match(v) for v in a_only.values())
        b_val = all(measure.real_value(v) for v in b_only.values()) and any(AMOUNT.match(v) for v in b_only.values())
        a_any = any(measure.real_value(v) for v in a_only.values())
        b_any = any(measure.real_value(v) for v in b_only.values())
        kind = ("value+value" if a_val and b_val else "mixed" if (a_any or b_any) else "text+text")
        a_keys = {keys.get(c) for k in a_only for (_, c) in m["a_origins"][k]}
        b_keys = {keys.get(c) for k in b_only for (_, c) in m["b_origins"][k]}
        if None in a_keys or None in b_keys:
            headers = "no_header"
        elif not a_keys.isdisjoint(b_keys):
            headers = "same_header"
        elif len({r for r, _ in a_keys | b_keys}) == 1:
            headers = "sibling_headers"
        else:
            headers = "nested_headers"
        rows_a, rows_b = sorted(a_only), sorted(b_only)
        stacked = rows_a[-1] < rows_b[0] or rows_b[-1] < rows_a[0]
        counts[f"{kind}|{headers}|{'stacked' if stacked else 'interleaved'}"] += 1
        if kind != "value+value" or headers != "same_header":
            continue

        def side(only, origins):
            cells = []
            for k in sorted(only):
                for (r, c) in origins[k]:
                    text = t.text((r, c))
                    if measure.real_value(text):
                        cells.append({"cell": list(cell_ids[id(t.g0[r][c].cell)]), "g0": [r, c], "text": vis(text)})
            return cells

        steps.append({
            "step": index, "stacked": stacked,
            "a": side(a_only, m["a_origins"]), "b": side(b_only, m["b_origins"]),
            "header_keys": sorted({tuple(k) for k in (a_keys & b_keys)}),
            "header_texts": sorted({vis(t.text(k))[:80] for k in (a_keys & b_keys)}),
        })
    return steps, counts


def work(item):
    doc_id, group, raw = item
    import measure
    from corpus import trace_document
    from sec2md.encoding import decode_html

    parser, records = trace_document(decode_html(raw)[0])
    tables, counts, replay = [], Counter(), Counter()
    for record in records:
        if record.path != "tableparser":
            continue
        replay_ok = record.trace.markdown.strip() == (record.output or "").strip()
        replay["ok" if replay_ok else "mismatch"] += 1
        steps, table_counts = classify(record, measure)
        counts.update(table_counts)
        if steps:
            tables.append({"table": record.ordinal, "steps": steps})
    return {"id": doc_id, "tables": tables, "counts": dict(counts), "replay": dict(replay)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--expect-src", required=True)
    ap.add_argument("--fixtures-root", required=True)
    ap.add_argument("--edgar-cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    location = acc_common.sec2md_location(args.expect_src)
    started = time.perf_counter()
    docs, _ = acc_common.load_documents(args.edgar_cache, args.fixtures_root)
    hashes = acc_common.verify_hashes(docs)
    if args.only:
        docs = [d for d in docs if d[0] in args.only]
    order = sorted(docs, key=lambda d: -len(d[2]))
    results = {}
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(args.workers, initializer=_init) as pool:
        for result in pool.imap_unordered(work, order):
            results[result["id"]] = result
            print(f"{result['id']}: {sum(len(t['steps']) for t in result['tables'])} steps", file=sys.stderr,
                  flush=True)
    documents = [results[d[0]] for d in docs]
    totals, replay = Counter(), Counter()
    for doc in documents:
        totals.update(doc["counts"])
        replay.update(doc["replay"])
    same = sum(len(t["steps"]) for d in documents for t in d["tables"])
    summary = {"sec2md_file": location, "hash_check_ok": hashes["ok"], "replay": dict(replay),
               "same_header_value_steps": same,
               "same_header_value_tables": sum(len(d["tables"]) for d in documents),
               "counts": dict(sorted(totals.items())), "seconds": round(time.perf_counter() - started, 1)}
    acc_common.write_json_gz(args.out, {"summary": summary, "documents": documents})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
