"""Shared helpers for the table merge and header rules acceptance run (research only).

The corpus is chosen with `--corpus` (`CORPORA`):

- `phase-a` (the default): the Phase A corpus, loaded exactly as
  ../2026-10-03-table-completeness-corpus/corpus_phase_a.py `documents()` loads it (imported
  with importlib, like the evidence scripts in ../2026-10-04-table-merge-header-evidence/).
  `documents()` reads the fixtures through relative paths, so every script changes into a
  checkout root that holds tests/fixtures/sec before calling it (`--fixtures-root`). With it,
  every script behaves exactly as before the switch, and writes no corpus record.
- `recent`: the recent filings corpus, loaded by
  ../2026-10-06-recent-filings-corpus/corpus_recent.py `documents()` from `--recent-cache`
  and checked against that folder's manifest.json. Its runs record `"corpus": "recent"`.

Which sec2md is imported is decided by PYTHONPATH (baseline: a `git archive c674828` tree's
src; candidate: the prototype worktree's src). Every script records `sec2md.__file__`.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import sys
from typing import Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
AUDITS = os.path.dirname(HERE)
PHASE_A_DIR = os.path.join(AUDITS, "2026-10-03-table-completeness-corpus")
EVIDENCE_DIR = os.path.join(AUDITS, "2026-10-04-table-merge-header-evidence")
PHASE_A = os.path.join(PHASE_A_DIR, "corpus_phase_a.py")
RESULTS = os.path.join(PHASE_A_DIR, "results.json")
MANIFEST = os.path.join(PHASE_A_DIR, "edgar_manifest.json")
EVENTS = os.path.join(EVIDENCE_DIR, "events.json")
RECENT_DIR = os.path.join(AUDITS, "2026-10-06-recent-filings-corpus")
RECENT = os.path.join(RECENT_DIR, "corpus_recent.py")
RECENT_MANIFEST = os.path.join(RECENT_DIR, "manifest.json")
RECENT_PREFIX = "recent:"
CORPORA = ("phase-a", "recent")
MODES = ("normal", "capture")
FILING_TYPES = ("10-K", "10-Q", "20-F", "8-K")


def phase_a_module():
    spec = importlib.util.spec_from_file_location("corpus_phase_a", PHASE_A)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recent_module():
    spec = importlib.util.spec_from_file_location("corpus_recent", RECENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check_corpus(corpus: str) -> None:
    if corpus not in CORPORA:
        raise ValueError(f"unknown corpus {corpus!r}; expected one of {', '.join(CORPORA)}")


def corpus_record(corpus: str) -> dict:
    """The corpus field a run record gets: none for phase-a (its records stay as they were)."""
    _check_corpus(corpus)
    return {} if corpus == "phase-a" else {"corpus": corpus}


def add_document_arguments(ap) -> None:
    """The corpus options of a script that loads documents (checked by check_document_arguments)."""
    ap.add_argument("--fixtures-root", help="phase-a: a checkout root holding tests/fixtures/sec (required)")
    ap.add_argument("--edgar-cache", help="phase-a: the Phase A EDGAR cache (required)")
    ap.add_argument("--corpus", choices=CORPORA, default="phase-a",
                    help="phase-a (default): the Phase A corpus, from --fixtures-root and --edgar-cache; "
                         "recent: the recent filings corpus, from --recent-cache")
    ap.add_argument("--recent-cache", help="recent: the recent filings cache, outputs/recent-filings-corpus "
                                           "(required)")


def check_document_arguments(ap, args) -> None:
    """Each corpus takes its own inputs and no other's (argparse error, exit 2, otherwise)."""
    if args.corpus == "phase-a":
        missing = [option for option, value in (("--fixtures-root", args.fixtures_root),
                                                ("--edgar-cache", args.edgar_cache)) if value is None]
        if missing:
            ap.error(f"the following arguments are required: {', '.join(missing)}")
        if args.recent_cache is not None:
            ap.error("--recent-cache is read only with --corpus recent")
    else:
        if args.recent_cache is None:
            ap.error(f"--corpus {args.corpus} needs --recent-cache")
        given = [option for option, value in (("--fixtures-root", args.fixtures_root),
                                              ("--edgar-cache", args.edgar_cache)) if value is not None]
        if given:
            ap.error(f"{', '.join(given)}: Phase A inputs, not read with --corpus {args.corpus}")


def phase_a_only(script: str, corpus: str, reason: str) -> None:
    """Stop a script tied to Phase A content when it is given another corpus (exit 1)."""
    if corpus != "phase-a":
        sys.exit(f"{script}: {reason}, so it runs on the Phase A corpus only, not with --corpus {corpus}")


def load_documents(edgar_cache: str, fixtures_root: str, corpus: str = "phase-a", recent_cache: str | None = None):
    """(docs, duplicates) from corpus_phase_a.documents(), run inside fixtures_root; with
    corpus="recent", (docs, skipped) from corpus_recent.documents(recent_cache), every file
    checked against RECENT_MANIFEST (a missing file or a SHA-256 mismatch raises)."""
    _check_corpus(corpus)
    if corpus == "recent":
        if not recent_cache:
            raise ValueError("corpus 'recent' needs recent_cache (the recent filings cache)")
        return recent_module().documents(recent_cache, manifest=RECENT_MANIFEST)
    here = os.getcwd()
    os.chdir(fixtures_root)
    try:
        return phase_a_module().documents(edgar_cache, True)
    finally:
        os.chdir(here)


def verify_hashes(docs, corpus: str = "phase-a") -> dict:
    """Check each document's SHA-256 against results.json and, for EDGAR, the manifest; with
    corpus="recent", against the recent corpus's manifest.json instead (verify_recent_hashes)."""
    _check_corpus(corpus)
    if corpus == "recent":
        return verify_recent_hashes(docs)
    with open(RESULTS, encoding="utf-8") as handle:
        results = {d["id"]: d["sha256"] for d in json.load(handle)["documents"]}
    with open(MANIFEST, encoding="utf-8") as handle:
        manifest = {d["file"]: d["sha256"] for d in json.load(handle)["documents"]}
    record = {"documents": len(docs), "results_json_documents": len(results), "matched_results": 0,
              "edgar_documents": 0, "matched_manifest": 0, "mismatches": [], "missing": []}
    for doc_id, group, raw in docs:
        digest = hashlib.sha256(raw).hexdigest()
        if doc_id not in results:
            record["missing"].append(doc_id)
        elif results[doc_id] != digest:
            record["mismatches"].append((doc_id, "results.json", results[doc_id], digest))
        else:
            record["matched_results"] += 1
        if group == "edgar":
            record["edgar_documents"] += 1
            name = doc_id.split(":", 1)[1]
            if manifest.get(name) == digest:
                record["matched_manifest"] += 1
            else:
                record["mismatches"].append((doc_id, "edgar_manifest.json", manifest.get(name), digest))
    record["extra_in_results"] = sorted(set(results) - {d for d, _, _ in docs})
    record["ok"] = (not record["mismatches"] and not record["missing"] and not record["extra_in_results"]
                    and record["matched_results"] == len(docs) == 109
                    and record["matched_manifest"] == record["edgar_documents"] == 18)
    return record


def verify_recent_hashes(docs) -> dict:
    """Check each document's SHA-256 against the recent corpus's manifest.json (RECENT_MANIFEST).

    The documents must be exactly the manifest's: each `recent:<file>` id in group `recent`
    listed once, with its SHA-256, and as many as the manifest has entries (and its
    `totals.documents`, when it records one), at least one.
    """
    with open(RECENT_MANIFEST, encoding="utf-8") as handle:
        data = json.load(handle)
    entries = data["documents"]
    manifest = {d["file"]: d["sha256"] for d in entries}
    totals = data.get("totals", {}).get("documents")
    record = {"corpus": "recent", "documents": len(docs), "manifest_documents": len(entries),
              "manifest_totals_documents": totals, "matched_manifest": 0, "mismatches": [], "missing": []}
    names = set()
    for doc_id, group, raw in docs:
        digest = hashlib.sha256(raw).hexdigest()
        name = doc_id[len(RECENT_PREFIX):] if doc_id.startswith(RECENT_PREFIX) and group == "recent" else None
        if name not in manifest:
            record["missing"].append(doc_id)
            continue
        names.add(name)
        if manifest[name] != digest:
            record["mismatches"].append((doc_id, "manifest.json", manifest[name], digest))
        else:
            record["matched_manifest"] += 1
    record["extra_in_manifest"] = sorted(set(manifest) - names)
    record["ok"] = (not record["mismatches"] and not record["missing"] and not record["extra_in_manifest"]
                    and record["matched_manifest"] == len(docs) == len(entries) > 0
                    and totals in (None, len(entries)))
    return record


def safe_name(doc_id: str) -> str:
    """A file name for one document's dump."""
    digest = hashlib.sha1(doc_id.encode("utf-8")).hexdigest()[:10]
    stem = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in doc_id)[:90]
    return f"{stem}.{digest}.json.gz"


def write_json_gz(path: str, data) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))


def read_json_gz(path: str):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def sec2md_location(expect_src: str | None) -> str:
    """sec2md.__file__, checked against the expected src folder when given."""
    import sec2md

    location = os.path.normcase(os.path.abspath(sec2md.__file__))
    if expect_src:
        expected = os.path.normcase(os.path.abspath(expect_src))
        if not location.startswith(expected + os.sep):
            sys.exit(f"sec2md imported from {location}, expected under {expected}")
    return sec2md.__file__


def table_units(soup):
    """check_tables' units: visible outermost tables in document order, numbered from 1."""
    from sec2md.table_completeness import hidden_sets

    outermost, hidden, _ = hidden_sets(soup)
    return [t for t in outermost if id(t) not in hidden]


def strip_ids(failures: Iterable[str]) -> list[str]:
    """Strict trace failures without their element ids: '<id>:<token>' -> '<token>'."""
    return sorted(failure.split(":", 1)[1] if ":" in failure else failure for failure in failures)
