"""Corpus check for the positioned page layout spec (2026-10-24, "Corpus check").

Every document is converted by `main` and by the branch, each side in its own process with
its own PYTHONPATH, and the two are compared: each page's content, number and display page,
and the table completeness report. Three steps:

    python compare.py list --out <docs.json> [--phase-a-cache <dir>] [--recent-cache <dir>]
                           [--fixtures <dir>] [--vault <dir>]
    PYTHONPATH=<side>/src python compare.py run --docs <docs.json> --out <side.jsonl>
                           --dumps <dir> [--workers N]
    python compare.py diff --main <main.jsonl> --branch <branch.jsonl> --out <results.json>

`list` records paths only. Every document is read in place and nothing is written next to it.
The vault (E:\\RCQWealth) is read only. `run` writes one JSON line per document, and each
document's Markdown to --dumps for review. `diff` writes the comparison.
"""
import argparse
import glob
import gzip
import hashlib
import json
import os
import sys
import time
import warnings
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))


# --- list ----------------------------------------------------------------------------------

def _recent_entries(cache):
    with open(os.path.join(HERE, "..", "2026-10-06-recent-filings-corpus", "manifest.json"),
              encoding="utf-8") as handle:
        entries = json.load(handle)["documents"]
    return [(f"recent:{e['file']}", os.path.join(cache, e["file"]), e["sha256"]) for e in entries]


def list_documents(args):
    docs = []
    if args.fixtures:
        for path in sorted(glob.glob(os.path.join(args.fixtures, "*.html.gz"))):
            docs.append((f"fixture:{os.path.basename(path)[:-8]}", path, None))
    if args.phase_a_cache:
        for path in sorted(glob.glob(os.path.join(args.phase_a_cache, "*.htm"))):
            docs.append((f"edgar:{os.path.basename(path)}", path, None))
    if args.recent_cache:
        docs.extend(_recent_entries(args.recent_cache))
    if args.vault:
        for company in sorted(os.listdir(args.vault)):
            originals = os.path.join(args.vault, company, "Originals", "SEC")
            if not os.path.isdir(originals):
                continue
            for path in sorted(glob.glob(os.path.join(originals, "*", "*.htm"))):
                docs.append((f"vault:{company}/{os.path.basename(path)}", path, None))
            for path in sorted(glob.glob(os.path.join(originals, "*", "*.assets", "*.htm*"))):
                name = f"{os.path.basename(os.path.dirname(path))[:-7]}/{os.path.basename(path)}"
                docs.append((f"vault-exhibit:{company}/{name}", path, None))
    # The same bytes under two ids are converted once, under the first id.
    seen, unique, duplicates = set(), [], []
    for doc_id, path, expected in docs:
        digest = hashlib.sha256(_read(path)).hexdigest()
        if expected and digest != expected:
            raise ValueError(f"{doc_id}: SHA-256 {digest} is not the manifest's {expected}")
        if digest in seen:
            duplicates.append(doc_id)
            continue
        seen.add(digest)
        unique.append({"id": doc_id, "path": path, "sha256": digest})
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"documents": unique, "duplicates": duplicates}, handle, indent=1)
    print(f"{len(unique)} documents, {len(duplicates)} duplicates")


def _read(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    return gzip.decompress(raw) if path.endswith(".gz") else raw


# --- run -----------------------------------------------------------------------------------

def _convert(task):
    doc, dumps = task
    warnings.filterwarnings("ignore")
    from sec2md.encoding import decode_html
    from sec2md.parser import Parser

    flow = [0]
    original = getattr(Parser, "_process_positioned_flow", None)
    if original is not None:
        def counted(self, container, page_num):
            flow[0] += 1
            return original(self, container, page_num)
        Parser._process_positioned_flow = counted
    started = time.perf_counter()
    try:
        html = decode_html(_read(doc["path"]))[0]
        parser = Parser(html)
        pages = parser.get_pages(include_elements=False, include_images=False)
    except Exception as error:  # recorded, never hidden
        return {"id": doc["id"], "error": f"{type(error).__name__}: {error}"}
    finally:
        if original is not None:
            Parser._process_positioned_flow = original
    markdown = "".join(f"\n<<<page {p.number} display={p.display_page}>>>\n{p.content}" for p in pages)
    name = hashlib.sha256(doc["id"].encode()).hexdigest()[:16] + ".md"
    with open(os.path.join(dumps, name), "w", encoding="utf-8") as handle:
        handle.write(markdown)
    report = parser.table_report
    return {
        "id": doc["id"],
        "seconds": round(time.perf_counter() - started, 2),
        "pages": [[p.number, p.display_page, hashlib.sha256(p.content.encode()).hexdigest()] for p in pages],
        "chars": sum(len(p.content) for p in pages),
        "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
        "dump": name,
        "tables_checked": report.tables_checked,
        "failures": list(report.failures),
        "reported": list(report.reported),
        "structure": list(report.structure),
        "flow_containers": flow[0] if original is not None else None,
    }


def run(args):
    import sec2md
    print(f"sec2md from {sec2md.__file__}", flush=True)
    with open(args.docs, encoding="utf-8") as handle:
        docs = json.load(handle)["documents"]
    os.makedirs(args.dumps, exist_ok=True)
    done = 0
    with Pool(args.workers) as pool, open(args.out, "w", encoding="utf-8") as out:
        for result in pool.imap_unordered(_convert, [(doc, args.dumps) for doc in docs], chunksize=1):
            out.write(json.dumps(result) + "\n")
            out.flush()
            done += 1
            if done % 100 == 0:
                print(f"{done}/{len(docs)}", flush=True)
    print(f"{done}/{len(docs)} done", flush=True)


# --- diff ----------------------------------------------------------------------------------

_COMPARED = ("pages", "tables_checked", "failures", "reported", "structure", "error")


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return {row["id"]: row for row in map(json.loads, handle)}


def diff(args):
    main, branch = _load(args.main), _load(args.branch)
    assert set(main) == set(branch), "the two sides converted different documents"
    differing = []
    for doc_id in sorted(main):
        a, b = main[doc_id], branch[doc_id]
        changed = [key for key in _COMPARED if a.get(key) != b.get(key)]
        if changed or b.get("flow_containers"):
            differing.append({
                "id": doc_id,
                "changed": changed,
                "flow_containers": b.get("flow_containers"),
                "chars": [a.get("chars"), b.get("chars")],
                "pages": [len(a.get("pages") or ()), len(b.get("pages") or ())],
                "failures": [len(a.get("failures") or ()), len(b.get("failures") or ())],
                "reported": [len(a.get("reported") or ()), len(b.get("reported") or ())],
                "structure": [len(a.get("structure") or ()), len(b.get("structure") or ())],
                "tables_checked": [a.get("tables_checked"), b.get("tables_checked")],
                "dumps": [a.get("dump"), b.get("dump")],
            })
    groups = {}
    for doc_id in main:
        group = doc_id.split(":", 1)[0]
        groups[group] = groups.get(group, 0) + 1
    result = {
        "documents": len(main),
        "by_group": groups,
        "errors": {"main": sorted(k for k, v in main.items() if "error" in v),
                   "branch": sorted(k for k, v in branch.items() if "error" in v)},
        "identical": len(main) - sum(1 for d in differing if d["changed"]),
        "differing": differing,
        "seconds": {"main": round(sum(v.get("seconds", 0) for v in main.values())),
                    "branch": round(sum(v.get("seconds", 0) for v in branch.values()))},
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)
    print(f"{result['documents']} documents: {result['identical']} identical, "
          f"{len(differing)} listed (changed or with a flow container)")


def main_cli():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--out", required=True)
    listing.add_argument("--fixtures")
    listing.add_argument("--phase-a-cache")
    listing.add_argument("--recent-cache")
    listing.add_argument("--vault")
    running = sub.add_parser("run")
    running.add_argument("--docs", required=True)
    running.add_argument("--out", required=True)
    running.add_argument("--dumps", required=True)
    running.add_argument("--workers", type=int, default=8)
    comparing = sub.add_parser("diff")
    comparing.add_argument("--main", required=True)
    comparing.add_argument("--branch", required=True)
    comparing.add_argument("--out", required=True)
    args = parser.parse_args()
    {"list": list_documents, "run": run, "diff": diff}[args.command](args)


if __name__ == "__main__":
    main_cli()
