"""Offline tests for strict_compare.py (Task 4 of the recent filings corpus plan).

    pytest docs/superpowers/audits/2026-10-06-recent-filings-corpus/test_strict_compare.py

The classification tests use synthetic per-document records in the side runner's record
format. The evidence helpers are tested on small BeautifulSoup trees. The last test runs the
whole CLI end to end on four tiny documents built from the branch's own limitation-test inputs
(copied, not imported); it is skipped when the tmh-proto worktree or commit c674828 is absent.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from collections import Counter

import pytest
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import strict_compare as sc  # noqa: E402

TRACE = "untraceable normalized number: "


def _record(failures=(), misses=None, other_warnings=()):
    """A side runner record for one document and mode.

    failures: (element id, token, zero_width, header_row_table) per trace failure.
    """
    raw = [f"{element}:{token}" for element, token, _, _ in failures]
    warnings = list(other_warnings) + ([TRACE + ",".join(raw)] if raw else [])
    return {
        "passed": not warnings,
        "error": "; ".join(warnings) or None,
        "trace_failures": sorted(token for _, token, _, _ in failures),
        "other_warnings": list(other_warnings),
        "header_accounting_misses": misses,
        "failure_evidence": [
            {"element": element, "token": token, "zero_width": zero_width, "header_row_table": header_row,
             "output_excerpt": [], "source_excerpt": []}
            for element, token, zero_width, header_row in failures
        ],
        "seconds": 0.1,
    }


PASS_MAIN = _record()
PASS_BRANCH = _record(misses=[])


# --- transitions --------------------------------------------------------------------------

def test_pass_to_pass_is_not_a_new_failure():
    case = sc.compare_case("recent:A.htm", "normal", PASS_MAIN, PASS_BRANCH)
    assert case["transition"] == "pass->pass"
    assert case["new"] is False
    assert case["added"] == [] and case["removed"] == []


def test_pass_to_fail_is_a_new_failure():
    branch = _record([("sec2md-p1-t0-aa", "31", False, False)], misses=[])
    case = sc.compare_case("recent:A.htm", "normal", PASS_MAIN, branch)
    assert case["transition"] == "pass->fail"
    assert case["new"] is True
    assert [(a["item"], a["count"]) for a in case["added"]] == [("31", 1)]


def test_fail_to_fail_with_the_same_multiset_is_pre_existing():
    # Element ids hash element content, so they differ between the sides; they are ignored.
    main = _record([("sec2md-p3-t1-11", "2,5", False, False), ("sec2md-p3-t1-11", "7", False, False)])
    branch = _record([("sec2md-p3-t1-99", "7", False, False), ("sec2md-p3-t1-99", "2,5", False, False)],
                     misses=[])
    case = sc.compare_case("recent:A.htm", "capture", main, branch)
    assert case["transition"] == "fail->fail-same"
    assert case["new"] is False


def test_fail_to_fail_with_a_different_multiset_is_a_new_failure():
    main = _record([("sec2md-p3-t1-11", "31", False, False)])
    branch = _record([("sec2md-p3-t1-99", "31", False, False), ("sec2md-p3-t1-99", "31", False, False)],
                     misses=[])
    case = sc.compare_case("recent:A.htm", "normal", main, branch)
    assert case["transition"] == "fail->fail-different"
    assert case["new"] is True
    assert [(a["item"], a["count"]) for a in case["added"]] == [("31", 1)]
    assert case["removed"] == []


def test_fail_to_fail_with_only_removals_is_new_and_other():
    main = _record([("e1", "31", False, False), ("e1", "45", False, False)])
    branch = _record([("e2", "31", False, False)], misses=[])
    case = sc.compare_case("recent:A.htm", "normal", main, branch)
    assert case["transition"] == "fail->fail-different"
    assert case["new"] is True
    assert case["added"] == []
    assert case["removed"] == [{"item": "45", "count": 1}]
    assert case["classes"] == ["other"]


def test_fail_to_pass_is_not_a_new_failure():
    main = _record([("e1", "31", False, False)])
    case = sc.compare_case("recent:A.htm", "normal", main, PASS_BRANCH)
    assert case["transition"] == "fail->pass"
    assert case["new"] is False


def test_failure_multiset_counts_mapping_ids_and_keeps_other_warnings():
    record = _record([("e1", "5", False, False)], other_warnings=[
        "element lacks a source-node mapping: sec2md-p1-t0-a,sec2md-p2-t0-b",
        "output contains 2 replacement characters",
    ])
    assert sc.failure_multiset(record) == Counter({
        "5": 1,
        "warning:element lacks a source-node mapping": 2,
        "warning:output contains 2 replacement characters": 1,
    })


def test_a_crash_is_a_failure_item():
    record = {**PASS_BRANCH, "passed": False, "crash": "RecursionError: deep"}
    assert sc.failure_multiset(record) == Counter({"crash:RecursionError": 1})
    case = sc.compare_case("recent:A.htm", "normal", PASS_MAIN, record)
    assert case["new"] is True and case["classes"] == ["other"]


# --- cause classes ------------------------------------------------------------------------

def test_wrapped_table_class():
    branch = _record([("sec2md-p1-t0-aa", "31", False, False)], misses=["sec2md-p1-t0-aa:missing"])
    case = sc.compare_case("recent:A.htm", "normal", PASS_MAIN, branch)
    assert case["classes"] == ["wrapped_table"]
    assert case["added"][0]["class"] == "wrapped_table"


def test_zero_width_number_class():
    branch = _record([("sec2md-p2-t0-bb", "1234", True, False)], misses=[])
    case = sc.compare_case("recent:A.htm", "capture", PASS_MAIN, branch)
    assert case["classes"] == ["zero_width_number"]


def test_header_row_table_class():
    branch = _record([("sec2md-p4-t2-cc", "header:2024", False, True)], misses=[])
    case = sc.compare_case("recent:A.htm", "normal", PASS_MAIN, branch)
    assert case["classes"] == ["header_row_table"]
    assert case["added"][0]["item"] == "header:2024"


def test_other_class():
    # A plain token; a miss on another element; an ambiguous miss on the failing element; a
    # header excess without a table in a header row; a non-trace warning.
    branch = _record(
        [("e1", "77", False, False), ("e2", "88", False, False), ("e3", "header:2024", False, False)],
        misses=["e9:missing", "e2:ambiguous"],
        other_warnings=["element lacks a source-node mapping: e4"],
    )
    case = sc.compare_case("recent:A.htm", "normal", PASS_MAIN, branch)
    assert {a["item"]: a["class"] for a in case["added"]} == {
        "77": "other", "88": "other", "header:2024": "other",
        "warning:element lacks a source-node mapping": "other",
    }
    assert case["classes"] == ["other"]


def test_token_evidence_comes_before_the_element_miss():
    # A zero-width token on an element that also holds a wrapped table is a zero-width case;
    # every matching class is still listed.
    branch = _record([("e1", "1234", True, False)], misses=["e1:missing"])
    case = sc.compare_case("recent:A.htm", "normal", PASS_MAIN, branch)
    (added,) = case["added"]
    assert added["class"] == "zero_width_number"
    assert added["matches"] == ["zero_width_number", "wrapped_table"]


def test_only_the_added_items_are_classified():
    main = _record([("m1", "31", False, False)])
    branch = _record([("b1", "31", False, False), ("b2", "1234", True, False)], misses=["b1:missing"])
    case = sc.compare_case("recent:A.htm", "normal", main, branch)
    assert [(a["item"], a["class"]) for a in case["added"]] == [("1234", "zero_width_number")]


# --- summary ------------------------------------------------------------------------------

def _side(records):
    return {"documents": {doc: {"modes": modes} for doc, modes in records.items()}}


def test_compare_summarizes_sides_classes_and_pre_existing_failures():
    pre = _record([("m", "9", False, False)])
    main = _side({
        "recent:A.htm": {"normal": PASS_MAIN, "capture": PASS_MAIN},
        "recent:B.htm": {"normal": pre, "capture": pre},
    })
    branch = _side({
        "recent:A.htm": {"normal": _record([("e", "31", False, False)], misses=["e:missing"]),
                         "capture": PASS_BRANCH},
        "recent:B.htm": {"normal": _record([("x", "9", False, False)], misses=[]),
                         "capture": _record([("x", "9", False, False), ("y", "header:2024", False, True)],
                                            misses=[])},
    })
    result = sc.compare(main, branch)
    summary = result["summary"]
    assert summary["cases"] == 4
    assert summary["main"] == {"pass": 2, "fail": 2}
    assert summary["branch"] == {"pass": 1, "fail": 3}
    assert summary["pre_existing_failures"] == 1
    assert summary["new_failures"] == 2
    assert summary["new_failures_by_class"] == {"wrapped_table": 1, "zero_width_number": 0,
                                                "header_row_table": 1, "other": 0}
    assert summary["transitions"] == {"pass->pass": 1, "pass->fail": 1, "fail->fail-same": 1,
                                      "fail->fail-different": 1}
    assert [(c["doc"], c["mode"]) for c in result["new_failures"]] == [
        ("recent:A.htm", "normal"), ("recent:B.htm", "capture")]
    assert result["pre_existing_failures"] == [{"doc": "recent:B.htm", "mode": "normal", "items": {"9": 1}}]


def test_compare_refuses_different_document_lists():
    main = _side({"recent:A.htm": {"normal": PASS_MAIN, "capture": PASS_MAIN}})
    branch = _side({"recent:B.htm": {"normal": PASS_BRANCH, "capture": PASS_BRANCH}})
    with pytest.raises(ValueError, match="document lists differ"):
        sc.compare(main, branch)


# --- evidence helpers ---------------------------------------------------------------------

def _simple_numbers(text):
    return tuple(m.replace(",", "") for m in re.findall(r"(?<![\d,])\d[\d,]*\d|\d", text))


def test_zero_width_join_is_found_only_where_removal_makes_the_token():
    assert sc.zero_width_joins("Revenue 1,2​34", "1234", _simple_numbers)
    assert sc.zero_width_joins("Revenue 12‌345", "12345", _simple_numbers)
    assert sc.zero_width_joins("Revenue 1,234", "1234", _simple_numbers) is False
    assert sc.zero_width_joins("Revenue 1,2​34", "34", _simple_numbers) is False


def _tables_in_header_rows(html):
    soup = BeautifulSoup(html, "lxml")
    return [t.get_text(" ", strip=True) for t in sc.tables_in_rows([soup.body])]


def test_tables_in_rows_finds_a_table_directly_or_div_wrapped_in_a_tr():
    nested = "<table><tr><th>Fiscal</th><th>2024</th></tr></table>"
    for inner in (nested, f"<div>{nested}</div>"):
        html = f"<table><tr><th>Item</th><th>Period</th>{inner}</tr><tr><td>Revenue</td><td>100</td></tr></table>"
        assert _tables_in_header_rows(html) == ["Fiscal 2024"]


def test_tables_in_rows_skips_a_table_inside_a_cell():
    html = ("<table><tr><th>Item</th><th>Period<table><tr><th>Fiscal</th><th>2024</th></tr></table></th></tr>"
            "<tr><td>Revenue</td><td>100</td></tr></table>")
    assert _tables_in_header_rows(html) == []


def test_excerpts_find_the_token_across_separators():
    assert sc.excerpts("Revenue 1,2​34 and more", "1234") == ["Revenue 1,2​34 and more"]
    assert sc.excerpts("| 2025 — 31 | 2024 — 31 |", "header:31") == ["| 2025 — 31 | 2024 — 31 |"]
    assert sc.excerpts("no such number 12345", "1234") == []


# --- end to end ---------------------------------------------------------------------------

REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BRANCH_SRC = os.path.join(REPO, ".worktrees", "tmh-proto", "src")

# Copied from the branch's limitation tests (tests/test_parser.py TestWrappedTableHeaderLimitation,
# tests/test_table_merge_headers.py zero-width case, tests/test_quality.py tr-direct case).
SPANNING_CAPTION_TABLE = (
    "<table><tr><td></td><td colspan='2'>Year Ended December 31,</td></tr>"
    "<tr><td></td><td>2025</td><td>2024</td></tr>"
    "<tr><td>Revenue</td><td>100</td><td>90</td></tr></table>"
)
E2E_DOCUMENTS = {
    "a-plain.htm": "<html><body><p>Intro.</p>" + SPANNING_CAPTION_TABLE + "</body></html>",
    "b-wrapped.htm": "<html><body><p>Intro.</p><b>" + SPANNING_CAPTION_TABLE + "</b></body></html>",
    "c-zero-width.htm": (
        "<html><body><p>Operating results for the year.</p><table>"
        "<tr><th>Item</th><th>2025</th></tr>"
        "<tr><td>Revenue</td><td>1,2​34</td></tr>"
        "<tr><td>Costs</td><td>567</td></tr></table></body></html>"
    ),
    "d-header-row.htm": (
        "<html><body><table><tr><th>Item</th><th>Period</th>"
        "<table><tr><th>Fiscal</th><th>2024</th></tr></table></tr>"
        "<tr><td>Revenue</td><td>100</td></tr></table></body></html>"
    ),
}


def _git_archive(commit, dest):
    data = subprocess.run(["git", "-C", REPO, "archive", commit, "src"], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(dest, filter="data")
    return os.path.join(dest, "src")


@pytest.mark.skipif(not os.path.isdir(BRANCH_SRC), reason="tmh-proto worktree absent")
def test_end_to_end_on_the_branch_limitation_inputs(tmp_path):
    try:
        main_src = _git_archive("c674828", str(tmp_path / "main"))
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"git archive c674828 unavailable: {exc}")
    cache = tmp_path / "cache"
    cache.mkdir()
    entries = []
    for name, html in E2E_DOCUMENTS.items():
        raw = html.encode("utf-8")
        (cache / name).write_bytes(raw)
        entries.append({"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"documents": entries}), encoding="utf-8")
    out = tmp_path / "strict.json"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("PYTHONPATH", None)
    run = subprocess.run(
        [sys.executable, os.path.join(HERE, "strict_compare.py"), "--main-src", main_src,
         "--branch-src", BRANCH_SRC, "--recent-cache", str(cache), "--manifest", str(manifest),
         "--out", str(out), "--workers", "2", "--side-dir", str(tmp_path / "sides")],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=600,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(out.read_text(encoding="utf-8"))
    assert os.path.normcase(result["sides"]["main"]["sec2md_file"]).startswith(os.path.normcase(main_src))
    assert os.path.normcase(result["sides"]["branch"]["sec2md_file"]).startswith(os.path.normcase(BRANCH_SRC))
    assert result["summary"]["main"] == {"pass": 8, "fail": 0}
    new = {(c["doc"], c["mode"]): c["classes"] for c in result["new_failures"]}
    assert new[("recent:b-wrapped.htm", "normal")] == ["wrapped_table"]
    assert new[("recent:b-wrapped.htm", "capture")] == ["wrapped_table"]
    assert new[("recent:c-zero-width.htm", "normal")] == ["zero_width_number"]
    assert new[("recent:d-header-row.htm", "normal")] == ["header_row_table"]
    assert ("recent:a-plain.htm", "normal") not in new and ("recent:a-plain.htm", "capture") not in new
    # The branch pins: capture mode writes the nested cells once and passes.
    assert ("recent:d-header-row.htm", "capture") not in new
    assert set(new) <= {("recent:b-wrapped.htm", "normal"), ("recent:b-wrapped.htm", "capture"),
                        ("recent:c-zero-width.htm", "normal"), ("recent:c-zero-width.htm", "capture"),
                        ("recent:d-header-row.htm", "normal")}
    for classes in new.values():
        assert "other" not in classes
