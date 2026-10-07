"""Strict on `main` and on the table merge branch, per recent-corpus document and mode (Task 4).

    python strict_compare.py --main-src <main>/src --branch-src <worktree>/src \
        --recent-cache <outputs/recent-filings-corpus> --out strict.json --workers N \
        [--side-dir DIR] [--manifest manifest.json] [--only ID ...] [--sequential] [--no-images]

Each side runs in its own subprocess with PYTHONPATH set to its src folder, and checks that
`sec2md.__file__` lies under it (in the side process and in every worker). Documents come from
`corpus_recent.documents(cache)`, which checks each SHA-256 against manifest.json.

Per document and mode (normal, and capture: `Parser(..., capture_tables=True)`, as the table
merge acceptance tooling's run_side.py does modes), a side converts the document as the public
`convert_to_markdown(html, quality_policy="strict")` does: decode_html, then
`Parser(html, decode_diagnostics=..., capture_tables=mode, table_checks=True).markdown()`, then
`enforce_quality(parser.diagnostics, "strict")`. `--no-images` renders with
`get_pages(include_images=False)` instead, as run_side.py does. It records `passed`, the
ParseQualityError message, the trace failures without element ids, the other strict warnings,
the branch's `header_accounting_misses`, and, per failing (element, token), the evidence the
cause classes need and short output and source excerpts.

A new failure is pass -> fail, or fail -> fail with a different failure multiset. The multiset
holds the trace tokens without element ids, one `warning:element lacks a source-node mapping`
per unmapped element, every other strict warning verbatim, and a crash's exception type. Each
item the branch adds is classified; the first match in this order wins and all matches are kept:

- zero_width_number: removing U+200B/200C/200D/2060/FEFF from the element's source text makes
  more of the token than the source pool holds;
- header_row_table: a `header:` excess whose token is in a <table> that sits in a <tr> with no
  cell between them (directly or through a wrapper such as a <div>) among the element's nodes;
- wrapped_table: the branch's header_accounting_misses holds `<failing element>:missing`;
- other.

A new failure that only removes items is `other`. Pre-existing failures fail on both sides with
the same multiset. Side dumps (with every failure's evidence) stay in --side-dir.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
MODES = ("normal", "capture")
CLASSES = ("wrapped_table", "zero_width_number", "header_row_table", "other")
PRECEDENCE = ("zero_width_number", "header_row_table", "wrapped_table")
TRACE_PREFIX = "untraceable normalized number: "
MAPPING_PREFIX = "element lacks a source-node mapping: "
MAPPING_ITEM = "warning:element lacks a source-node mapping"
ZERO_WIDTH = "​‌‍⁠﻿"
_REMOVE_ZERO_WIDTH = str.maketrans(dict.fromkeys(ZERO_WIDTH))
_SEPARATORS = r"[,\s" + ZERO_WIDTH + r"]*"
EXCERPT_RADIUS = 100
EXCERPT_LIMIT = 3
EVIDENCE_LIMIT = 5


# --- records ------------------------------------------------------------------------------

def strip_ids(failures) -> list[str]:
    """Trace failures without their element ids: '<id>:<token>' -> '<token>', sorted."""
    return sorted(failure.split(":", 1)[1] if ":" in failure else failure for failure in failures)


def failure_multiset(record: dict) -> Counter:
    """The record's strict failures, comparable across sides (element ids hash content)."""
    items: Counter = Counter()
    if record.get("crash"):
        items["crash:" + record["crash"].split(":", 1)[0]] += 1
        return items
    items.update(record.get("trace_failures") or ())
    for warning in record.get("other_warnings") or ():
        if warning.startswith(MAPPING_PREFIX):
            items[MAPPING_ITEM] += len(warning[len(MAPPING_PREFIX):].split(","))
        else:
            items["warning:" + warning] += 1
    return items


def transition(main: dict, branch: dict) -> str:
    if main["passed"] and branch["passed"]:
        return "pass->pass"
    if main["passed"]:
        return "pass->fail"
    if branch["passed"]:
        return "fail->pass"
    same = failure_multiset(main) == failure_multiset(branch)
    return "fail->fail-same" if same else "fail->fail-different"


def classify_item(item: str, count: int, branch: dict) -> dict:
    """One added failure item's cause class, from the branch record's evidence."""
    entries = [e for e in branch.get("failure_evidence") or () if e["token"] == item]
    misses = set(branch.get("header_accounting_misses") or ())
    found = set()
    if any(e["zero_width"] for e in entries):
        found.add("zero_width_number")
    if item.startswith("header:") and any(e["header_row_table"] for e in entries):
        found.add("header_row_table")
    if any(f"{e['element']}:missing" in misses for e in entries):
        found.add("wrapped_table")
    matches = [name for name in PRECEDENCE if name in found]
    return {"item": item, "count": count, "class": matches[0] if matches else "other", "matches": matches,
            "candidates": sum(e.get("count", 1) for e in entries), "evidence": entries[:EVIDENCE_LIMIT]}


def compare_case(doc: str, mode: str, main: dict, branch: dict) -> dict:
    """The transition for one document and mode, and the branch's added items, classified."""
    kind = transition(main, branch)
    new = kind in ("pass->fail", "fail->fail-different")
    main_items, branch_items = failure_multiset(main), failure_multiset(branch)
    added = [classify_item(item, count, branch) for item, count in sorted((branch_items - main_items).items())]
    removed = [{"item": item, "count": count} for item, count in sorted((main_items - branch_items).items())]
    if not new:
        classes = []
    elif added:
        classes = sorted({a["class"] for a in added}, key=CLASSES.index)
    else:
        classes = ["other"]
    return {"doc": doc, "mode": mode, "transition": kind, "new": new, "classes": classes, "added": added,
            "removed": removed}


def _side_meta(side: dict) -> dict:
    return {key: value for key, value in side.items() if key != "documents"}


def _brief(record: dict) -> dict:
    """A record for strict.json's per-document table: everything but the evidence."""
    return {key: value for key, value in record.items() if key != "failure_evidence"}


def compare(main_side: dict, branch_side: dict) -> dict:
    """strict.json's content from the two side dumps."""
    main_docs, branch_docs = main_side["documents"], branch_side["documents"]
    if sorted(main_docs) != sorted(branch_docs):
        raise ValueError(f"document lists differ: main only {sorted(set(main_docs) - set(branch_docs))},"
                         f" branch only {sorted(set(branch_docs) - set(main_docs))}")
    sha_differs = [doc for doc in main_docs if main_docs[doc].get("sha256") != branch_docs[doc].get("sha256")]
    if sha_differs:
        raise ValueError(f"document bytes differ between the sides: {sha_differs}")
    cases, documents = [], {}
    for doc in sorted(main_docs):
        documents[doc] = {}
        for mode in MODES:
            main, branch = main_docs[doc]["modes"][mode], branch_docs[doc]["modes"][mode]
            case = compare_case(doc, mode, main, branch)
            cases.append((case, main, branch))
            documents[doc][mode] = {"transition": case["transition"], "main": _brief(main), "branch": _brief(branch)}
    new = [case for case, _, _ in cases if case["new"]]
    pre_existing = [{"doc": case["doc"], "mode": case["mode"], "items": dict(sorted(failure_multiset(main).items()))}
                    for case, main, _ in cases if case["transition"] == "fail->fail-same"]
    fixed = [{"doc": case["doc"], "mode": case["mode"], "removed": case["removed"]}
             for case, _, _ in cases if case["transition"] == "fail->pass"]
    summary = {
        "documents": len(main_docs),
        "modes": list(MODES),
        "cases": len(cases),
        "main": {"pass": sum(m["passed"] for _, m, _ in cases), "fail": sum(not m["passed"] for _, m, _ in cases)},
        "branch": {"pass": sum(b["passed"] for _, _, b in cases),
                   "fail": sum(not b["passed"] for _, _, b in cases)},
        "transitions": dict(Counter(case["transition"] for case, _, _ in cases)),
        "new_failures": len(new),
        "new_failures_by_class": {name: sum(name in case["classes"] for case in new) for name in CLASSES},
        "new_failure_items_by_class": {name: sum(a["count"] for case in new for a in case["added"]
                                                 if a["class"] == name) for name in CLASSES},
        "pre_existing_failures": len(pre_existing),
        "fixed": len(fixed),
    }
    return {"summary": summary, "sides": {"main": _side_meta(main_side), "branch": _side_meta(branch_side)},
            "new_failures": new, "pre_existing_failures": pre_existing, "fixed": fixed, "documents": documents}


# --- evidence helpers ---------------------------------------------------------------------

def _zero_width_counts(text: str, normalize) -> tuple[Counter, Counter]:
    return Counter(normalize(text)), Counter(normalize(text.translate(_REMOVE_ZERO_WIDTH)))


def zero_width_joins(text: str, token: str, normalize) -> bool:
    """Whether removing zero-width characters from text makes more of token than text holds."""
    bare = token.removeprefix("header:")
    plain, joined = _zero_width_counts(text, normalize)
    return joined[bare] > plain[bare]


def tables_in_rows(nodes) -> list:
    """<table> elements among nodes (and their descendants) that sit in a <tr> outside any cell."""
    found, seen = [], set()
    for node in nodes:
        if not hasattr(node, "find_all"):
            continue
        candidates = ([node] if node.name == "table" else []) + node.find_all("table")
        for table in candidates:
            if id(table) in seen:
                continue
            seen.add(id(table))
            for parent in table.parents:
                if parent.name in ("td", "th", "table"):
                    break
                if parent.name == "tr":
                    found.append(table)
                    break
    return found


def _token_pattern(token: str) -> re.Pattern:
    bare = token.removeprefix("header:").lstrip("-")
    return re.compile(r"(?<!\d)" + _SEPARATORS.join(re.escape(ch) for ch in bare) + r"(?!\d)")


def excerpts(text: str, token: str, radius: int = EXCERPT_RADIUS, limit: int = EXCERPT_LIMIT) -> list[str]:
    """Up to `limit` merged windows of text around the token's digits (separators allowed)."""
    windows: list[list[int]] = []
    for match in _token_pattern(token).finditer(text):
        start, end = max(0, match.start() - radius), min(len(text), match.end() + radius)
        if windows and start <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
        if len(windows) > limit:
            break
    return [text[start:end] for start, end in windows[:limit]]


def failure_evidence(parser, pages, raw_failures, normalize) -> list[dict]:
    """Per failing (element, token): the class evidence and short output and source excerpts."""
    elements = {element.id: element for page in pages for element in (page.elements or ())}
    grouped: dict[str, Counter] = defaultdict(Counter)
    for failure in raw_failures:
        element_id, token = failure.split(":", 1)
        grouped[element_id][token] += 1
    out = []
    for element_id, tokens in grouped.items():
        nodes = [node for node in parser.block_nodes_map.get(element_id, ()) if hasattr(node, "get_text")]
        source_text = " ".join(node.get_text(" ", strip=True) for node in nodes)
        plain, joined = _zero_width_counts(source_text, normalize)
        inner = Counter(normalize(" ".join(t.get_text(" ", strip=True) for t in tables_in_rows(nodes))))
        element = elements.get(element_id)
        content = element.content if element is not None else ""
        for token, count in sorted(tokens.items()):
            bare = token.removeprefix("header:")
            out.append({
                "element": element_id,
                "token": token,
                "count": count,
                "zero_width": joined[bare] > plain[bare],
                "header_row_table": token.startswith("header:") and inner[bare] > 0,
                "output_excerpt": excerpts(content, token),
                "source_excerpt": excerpts(source_text, token),
            })
    return out


# --- one side -----------------------------------------------------------------------------

def sec2md_location(src: str) -> str:
    """sec2md.__file__, which must lie under src."""
    import sec2md

    location = os.path.normcase(os.path.abspath(sec2md.__file__))
    expected = os.path.normcase(os.path.abspath(src))
    if not location.startswith(expected + os.sep):
        raise RuntimeError(f"sec2md imported from {location}, expected under {expected}")
    return sec2md.__file__


def strict_record(html: str, decoded, capture: bool, images: bool = True) -> dict:
    """Strict, as convert_to_markdown(html, quality_policy="strict") runs it, in one mode.

    images=False renders with get_pages(include_images=False), as run_side.py does.
    """
    from sec2md.parser import Parser
    from sec2md.quality import ParseQualityError, _normalized_numbers, enforce_quality

    started = time.perf_counter()
    try:
        parser = Parser(html, decode_diagnostics=decoded, capture_tables=capture, table_checks=True)
        if images:
            parser.markdown()
            pages = parser._last_pages
        else:
            pages = parser.get_pages(include_images=False)
        diagnostics = parser.diagnostics
        error = None
        try:
            enforce_quality(diagnostics, "strict")
        except ParseQualityError as exc:
            error = str(exc)
    except Exception as exc:  # recorded as a failure item, never hidden
        return {"passed": False, "crash": f"{type(exc).__name__}: {exc}", "error": None, "trace_failures": [],
                "other_warnings": [], "header_accounting_misses": None, "failure_evidence": [],
                "seconds": round(time.perf_counter() - started, 3)}
    raw_failures = list(diagnostics.trace_numeric_failures)
    return {
        "passed": error is None,
        "error": error,
        "trace_failures": strip_ids(raw_failures),
        "other_warnings": [w for w in diagnostics.warnings if not w.startswith(TRACE_PREFIX)],
        "header_accounting_misses": (list(parser.header_accounting_misses)
                                     if hasattr(parser, "header_accounting_misses") else None),
        "failure_evidence": failure_evidence(parser, pages, raw_failures, _normalized_numbers) if raw_failures else [],
        "pages": diagnostics.pages,
        "elements": diagnostics.elements,
        "tables_checked": diagnostics.tables_checked,
        "output_ratio": round(diagnostics.output_ratio, 6),
        "seconds": round(time.perf_counter() - started, 3),
    }


_SRC = None
_IMAGES = True


def _init(src: str, images: bool = True) -> None:
    global _SRC, _IMAGES
    _SRC, _IMAGES = src, images
    import logging
    import warnings

    warnings.filterwarnings("ignore")
    logging.disable(logging.CRITICAL)


def _work(item):
    doc_id, raw = item
    import hashlib

    from sec2md.encoding import decode_html

    location = sec2md_location(_SRC)
    started = time.perf_counter()
    html, decoded = decode_html(raw)
    modes = {mode: strict_record(html, decoded, mode == "capture", _IMAGES) for mode in MODES}
    return doc_id, {"sha256": hashlib.sha256(raw).hexdigest(), "seconds": round(time.perf_counter() - started, 3),
                    "modes": modes}, location


def run_side(args) -> None:
    started = time.perf_counter()
    location = sec2md_location(args.src)
    sys.path.insert(0, HERE)
    import corpus_recent

    manifest = args.manifest or corpus_recent.MANIFEST
    docs, skipped = corpus_recent.documents(args.recent_cache, manifest)
    if args.only:
        docs = [d for d in docs if d[0] in args.only]
    order = sorted(docs, key=lambda d: -len(d[2]))  # largest first, for balance
    print(json.dumps({"side": args.run_side, "sec2md": location, "documents": len(docs)}), file=sys.stderr, flush=True)
    results, workers_seen = {}, set()
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(args.workers, initializer=_init, initargs=(args.src, not args.no_images)) as pool:
        for done, (doc_id, data, worker_location) in enumerate(
                pool.imap_unordered(_work, [(d[0], d[2]) for d in order]), 1):
            results[doc_id] = data
            workers_seen.add(worker_location)
            passed = "/".join("pass" if data["modes"][m]["passed"] else "FAIL" for m in MODES)
            print(f"[{args.run_side}] {done}/{len(order)} {doc_id}: {data['seconds']:.1f}s {passed}",
                  file=sys.stderr, flush=True)
    dump = {"side": args.run_side, "src": args.src, "sec2md_file": location, "images": not args.no_images,
            "worker_sec2md_files": sorted(workers_seen), "manifest": manifest, "recent_cache": args.recent_cache,
            "skipped": skipped, "workers": args.workers, "wall_seconds": round(time.perf_counter() - started, 1),
            "documents": dict(sorted(results.items()))}
    with open(args.side_out, "w", encoding="utf-8") as handle:
        json.dump(dump, handle, ensure_ascii=False, indent=1)


# --- both sides ---------------------------------------------------------------------------

def _git(src: str, *argv: str) -> str | None:
    try:
        run = subprocess.run(["git", "-C", src, *argv], capture_output=True, text=True, timeout=30)
    except OSError:
        return None
    return run.stdout.strip() if run.returncode == 0 else None


def _side_command(args, name: str, src: str, out: str) -> list[str]:
    command = [sys.executable, os.path.abspath(__file__), "--run-side", name, "--src", src,
               "--recent-cache", args.recent_cache, "--side-out", out, "--workers", str(args.workers)]
    if args.manifest:
        command += ["--manifest", args.manifest]
    if args.only:
        command += ["--only", *args.only]
    if args.no_images:
        command += ["--no-images"]
    return command


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--main-src")
    ap.add_argument("--branch-src")
    ap.add_argument("--recent-cache", required=True)
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=8, help="worker processes per side")
    ap.add_argument("--side-dir", help="where the side dumps go (default: a new temporary folder)")
    ap.add_argument("--manifest", help="default: manifest.json next to corpus_recent.py")
    ap.add_argument("--only", nargs="*", help="document ids to run (default: all)")
    ap.add_argument("--sequential", action="store_true", help="run the sides one after the other")
    ap.add_argument("--no-images", action="store_true",
                    help="render with get_pages(include_images=False), as run_side.py does (default: as"
                         " convert_to_markdown, with images)")
    ap.add_argument("--run-side", help=argparse.SUPPRESS)
    ap.add_argument("--src", help=argparse.SUPPRESS)
    ap.add_argument("--side-out", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.run_side:
        run_side(args)
        return
    if not (args.main_src and args.branch_src and args.out):
        ap.error("--main-src, --branch-src and --out are required")
    started = time.perf_counter()
    side_dir = args.side_dir or tempfile.mkdtemp(prefix="strict_compare_")
    os.makedirs(side_dir, exist_ok=True)
    sides = {"main": os.path.abspath(args.main_src), "branch": os.path.abspath(args.branch_src)}
    outs = {name: os.path.join(side_dir, f"{name}.json") for name in sides}
    running = []
    for name, src in sides.items():
        env = {**os.environ, "PYTHONPATH": src, "PYTHONIOENCODING": "utf-8"}
        running.append((name, subprocess.Popen(_side_command(args, name, src, outs[name]), env=env)))
        if args.sequential:
            if running[-1][1].wait():
                sys.exit(f"the {name} side failed (exit code {running[-1][1].returncode})")
    for name, process in running:
        if process.wait():
            sys.exit(f"the {name} side failed (exit code {process.returncode})")
    loaded = {}
    for name, path in outs.items():
        with open(path, encoding="utf-8") as handle:
            loaded[name] = json.load(handle)
    result = compare(loaded["main"], loaded["branch"])
    for name, src in sides.items():
        result["sides"][name]["git_toplevel"] = _git(src, "rev-parse", "--show-toplevel")
        result["sides"][name]["git_head"] = _git(src, "rev-parse", "HEAD")
        result["sides"][name]["git_status_src"] = _git(src, "status", "--porcelain", "--", ".")
    result["run"] = {"wall_seconds": round(time.perf_counter() - started, 1), "workers_per_side": args.workers,
                     "sequential": args.sequential, "images": not args.no_images, "side_dir": side_dir,
                     "python": sys.executable}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(json.dumps(result["summary"], indent=1))


if __name__ == "__main__":
    main()
