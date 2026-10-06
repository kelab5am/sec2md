"""Shared helpers for the table merge and header rules acceptance run (research only).

The corpus is the Phase A corpus, loaded exactly as
../2026-10-03-table-completeness-corpus/corpus_phase_a.py `documents()` loads it (imported
with importlib, like the evidence scripts in ../2026-10-04-table-merge-header-evidence/).
`documents()` reads the fixtures through relative paths, so every script changes into a
checkout root that holds tests/fixtures/sec before calling it (`--fixtures-root`).

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
MODES = ("normal", "capture")
FILING_TYPES = ("10-K", "10-Q", "20-F", "8-K")


def phase_a_module():
    spec = importlib.util.spec_from_file_location("corpus_phase_a", PHASE_A)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_documents(edgar_cache: str, fixtures_root: str):
    """(docs, duplicates) from corpus_phase_a.documents(), run inside fixtures_root."""
    here = os.getcwd()
    os.chdir(fixtures_root)
    try:
        return phase_a_module().documents(edgar_cache, True)
    finally:
        os.chdir(here)


def verify_hashes(docs) -> dict:
    """Check each document's SHA-256 against results.json and, for EDGAR, the manifest."""
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
