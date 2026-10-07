"""Field-by-field XLSX and display-page detail for documents whose prepared-table hash differs.

    PYTHONPATH=<side>/src python xlsx_detail.py dump --fixtures-root <checkout> --edgar-cache <cache> \
        --out <side>.json <document id>...
    PYTHONPATH=<side>/src python xlsx_detail.py dump --corpus recent --recent-cache <recent filings cache> \
        --out <side>.json <document id>...
    python xlsx_detail.py compare <main>.json <candidate>.json --out xlsx_detail.json

`dump` parses each document in capture mode and writes every prepared table
(dataclasses.asdict, values as strings) and each page's display page. `compare` lists,
per document, the pages whose display page differs and, per snapshot, every differing
field except the snapshot's element_id (which hashes element content).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402


def dump(args):
    warnings.filterwarnings("ignore")
    from sec2md.encoding import decode_html
    from sec2md.parser import Parser
    from sec2md.xlsx_tables import prepare_table

    docs, _ = acc_common.load_documents(args.edgar_cache, args.fixtures_root, args.corpus, args.recent_cache)
    out = {}
    for doc_id, _, raw in docs:
        if doc_id not in args.documents:
            continue
        parser = Parser(decode_html(raw)[0], capture_tables=True)
        pages = parser.get_pages(include_images=False)
        tables = [json.loads(json.dumps(dataclasses.asdict(prepare_table(s)), default=str))
                  for s in parser.table_snapshots]
        out[doc_id] = {"pages": [[p.number, p.display_page] for p in pages], "tables": tables}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False)


def compare(args):
    main = json.load(open(args.main, encoding="utf-8"))
    cand = json.load(open(args.candidate, encoding="utf-8"))
    result = {}
    for doc in main:
        pages = [{"page": a[0], "main": a[1], "candidate": b[1]}
                 for a, b in zip(main[doc]["pages"], cand[doc]["pages"]) if a != b]
        tables = []
        for tm, tc in zip(main[doc]["tables"], cand[doc]["tables"]):
            fields = []
            for key in tm:
                if key == "source":
                    fields += [{"field": f"source.{k}", "main": tm["source"][k], "candidate": tc["source"][k]}
                               for k in tm["source"] if k != "element_id" and tm["source"][k] != tc["source"][k]]
                elif tm[key] != tc[key]:
                    fields.append({"field": key, "main": str(tm[key])[:300], "candidate": str(tc[key])[:300]})
            if fields:
                tables.append({"ordinal": tm["source"]["ordinal"], "fields": fields})
        result[doc] = {"pages": pages, "tables": tables,
                       "tables_compared": len(main[doc]["tables"]),
                       "only_display_page_differs": all(f["field"] == "source.display_page"
                                                        for t in tables for f in t["fields"])}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    d = sub.add_parser("dump")
    acc_common.add_document_arguments(d)
    d.add_argument("--out", required=True)
    d.add_argument("documents", nargs="+")
    c = sub.add_parser("compare")
    c.add_argument("main")
    c.add_argument("candidate")
    c.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.command == "dump":
        acc_common.check_document_arguments(d, args)
        dump(args)
    else:
        compare(args)


if __name__ == "__main__":
    main()
