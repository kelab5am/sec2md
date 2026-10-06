"""Offline tests for the recent filings corpus tooling (no network).

    python -m pytest -q -p no:cacheprovider <this folder>/test_tooling.py

Selection tests use synthetic EDGAR submissions blocks in the real columnar format: one
list per column (form, filingDate, reportDate, accessionNumber, primaryDocument, ...),
one index per filing, newest first, plus the `files` entries of the older-filings pages.
"""
import argparse
import gzip
import hashlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fr = _load("fetch_recent")

WINDOW = ("2021-10-07", "2026-10-06")
ACME = ("ACME", 1234, "ACME", "10-K")
TSMX = ("TSMX", 5678, "TAIWAN", "20-F")


def block(*rows):
    """A columnar filings block from (form, filingDate, reportDate, accession, document) rows."""
    columns = {key: [] for key in (
        "accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "act", "form",
        "fileNumber", "filmNumber", "items", "size", "isXBRL", "isInlineXBRL",
        "primaryDocument", "primaryDocDescription")}
    for form, filed, report, accession, document in rows:
        columns["accessionNumber"].append(accession)
        columns["filingDate"].append(filed)
        columns["reportDate"].append(report)
        columns["acceptanceDateTime"].append(f"{filed}T16:05:00.000Z")
        columns["act"].append("34")
        columns["form"].append(form)
        columns["fileNumber"].append("001-00000")
        columns["filmNumber"].append("00000000")
        columns["items"].append("")
        columns["size"].append(999999)
        columns["isXBRL"].append(1)
        columns["isInlineXBRL"].append(1)
        columns["primaryDocument"].append(document)
        columns["primaryDocDescription"].append(form)
    return columns


def by_accession(entries):
    return {entry["accession"]: entry for entry in entries}


# --- select -----------------------------------------------------------------------------

def test_one_filing_per_report_date():
    recent = block(
        ("8-K", "2024-05-02", "2024-05-01", "0000001234-24-000050", "acme-8k.htm"),
        ("10-K", "2024-05-01", "2023-12-31", "0000001234-24-000040", "acme-refiled.htm"),
        ("10-Q", "2024-04-30", "2024-03-31", "0000001234-24-000030", "acme-10q.htm"),
        ("10-K", "2024-02-10", "2023-12-31", "0000001234-24-000010", "acme-20231231.htm"),
        ("10-K", "2023-02-10", "2022-12-31", "0000001234-23-000010", "acme-20221231.htm"),
    )
    selected, excluded = fr.select([recent], ACME, WINDOW, set())
    assert [(e["report_date"], e["accession"]) for e in selected] == [
        ("2022-12-31", "0000001234-23-000010"),
        ("2023-12-31", "0000001234-24-000010"),
    ]
    assert selected[1]["url"] == (
        "https://www.sec.gov/Archives/edgar/data/1234/000000123424000010/acme-20231231.htm")
    assert selected[1]["ticker"] == "ACME" and selected[1]["cik"] == 1234
    assert selected[1]["form"] == "10-K" and selected[1]["filing_date"] == "2024-02-10"
    assert selected[1]["amendment"] is False
    # The second original for the same period is left out, and only 10-K forms are counted.
    assert [(e["accession"], e["reason"]) for e in excluded] == [
        ("0000001234-24-000040", "same_period_newer")]
    assert excluded[0]["kept"] == "0000001234-24-000010"


def test_original_beats_its_amendment():
    recent = block(  # newest first, so the amendment comes before its original
        ("10-K/A", "2023-04-28", "2022-12-31", "0000001234-23-000020", "acme-10ka.htm"),
        ("10-K", "2023-02-10", "2022-12-31", "0000001234-23-000010", "acme-20221231.htm"),
    )
    selected, excluded = fr.select([recent], ACME, WINDOW, set())
    assert [(e["accession"], e["form"], e["amendment"]) for e in selected] == [
        ("0000001234-23-000010", "10-K", False)]
    assert [(e["accession"], e["form"], e["reason"], e["kept"]) for e in excluded] == [
        ("0000001234-23-000020", "10-K/A", "amendment", "0000001234-23-000010")]


def test_amendment_kept_and_marked_when_it_is_the_only_filing_for_its_period():
    recent = block(
        ("10-K/A", "2022-06-01", "2021-12-31", "0000001234-22-000090", "acme-10ka2.htm"),
        ("10-K/A", "2022-03-15", "2021-12-31", "0000001234-22-000030", "acme-10ka1.htm"),
        ("10-K", "2023-02-10", "2022-12-31", "0000001234-23-000010", "acme-20221231.htm"),
    )
    selected, excluded = fr.select([recent], ACME, WINDOW, set())
    marked = by_accession(selected)
    assert set(marked) == {"0000001234-22-000030", "0000001234-23-000010"}
    assert marked["0000001234-22-000030"]["amendment"] is True
    assert marked["0000001234-22-000030"]["form"] == "10-K/A"
    assert marked["0000001234-23-000010"]["amendment"] is False
    # Of two amendments with no original, the first filed is kept.
    assert [(e["accession"], e["reason"], e["kept"]) for e in excluded] == [
        ("0000001234-22-000090", "same_period_newer", "0000001234-22-000030")]


def test_window_edges_are_inclusive():
    recent = block(
        ("10-K", "2026-10-07", "2026-06-30", "0000001234-26-000099", "late.htm"),
        ("10-K", "2026-10-06", "2025-06-30", "0000001234-26-000090", "last-day.htm"),
        ("10-K", "2021-10-07", "2021-06-30", "0000001234-21-000070", "first-day.htm"),
        ("10-K", "2021-10-06", "2020-06-30", "0000001234-21-000060", "day-before.htm"),
    )
    selected, excluded = fr.select([recent], ACME, WINDOW, set())
    assert sorted(e["filing_date"] for e in selected) == ["2021-10-07", "2026-10-06"]
    assert sorted((e["filing_date"], e["reason"]) for e in excluded) == [
        ("2021-10-06", "outside_window"), ("2026-10-07", "outside_window")]


def test_phase_a_accession_is_left_out_and_not_replaced_by_its_amendment():
    recent = block(
        ("10-K/A", "2025-04-30", "2024-12-31", "0000001234-25-000020", "acme-10ka.htm"),
        ("10-K", "2025-02-14", "2024-12-31", "0000001234-25-000010", "acme-20241231.htm"),
        ("10-K", "2024-02-14", "2023-12-31", "0000001234-24-000010", "acme-20231231.htm"),
    )
    selected, excluded = fr.select([recent], ACME, WINDOW, {"0000001234-25-000010"})
    assert [e["accession"] for e in selected] == ["0000001234-24-000010"]
    reasons = {e["accession"]: e["reason"] for e in excluded}
    assert reasons == {
        "0000001234-25-000010": "phase_a_duplicate",
        "0000001234-25-000020": "amendment",
    }


def test_filings_from_several_blocks_are_merged_once():
    recent = block(("10-K", "2026-02-10", "2025-12-31", "0000001234-26-000010", "a.htm"))
    older = block(
        ("10-K", "2026-02-10", "2025-12-31", "0000001234-26-000010", "a.htm"),
        ("10-K", "2022-02-10", "2021-12-31", "0000001234-22-000010", "b.htm"),
    )
    selected, excluded = fr.select([recent, older], ACME, WINDOW, set())
    assert [e["accession"] for e in selected] == [
        "0000001234-22-000010", "0000001234-26-000010"]
    assert excluded == []


def test_20f_issuer():
    recent = block(
        ("6-K", "2025-04-20", "", "0001234567-25-000300", "tsmx-6k.htm"),
        ("20-F/A", "2025-05-01", "2024-12-31", "0001234567-25-000200", "tsmx-20fa.htm"),
        ("20-F", "2025-04-17", "2024-12-31", "0001234567-25-000100", "tsmx-20f.htm"),
        ("10-K", "2024-03-01", "2023-12-31", "0001234567-24-000100", "odd-10k.htm"),
        ("20-F", "2024-04-18", "2023-12-31", "0001234567-24-000090", "tsmx-20f-2023.htm"),
    )
    selected, excluded = fr.select([recent], TSMX, WINDOW, set())
    assert [(e["form"], e["report_date"]) for e in selected] == [
        ("20-F", "2023-12-31"), ("20-F", "2024-12-31")]
    assert [(e["form"], e["reason"]) for e in excluded] == [("20-F/A", "amendment")]


def test_issuer_with_no_annual_report_is_listed_with_a_reason():
    recent = block(
        ("10-Q", "2026-08-04", "2026-06-30", "0001181412-26-052535", "spcx-10q.htm"),
        ("424B4", "2026-06-12", "", "0001181412-26-040000", "prospectus.htm"),
        ("S-1", "2026-04-01", "", "0001181412-26-030000", "s1.htm"),
    )
    spcx = ("SPCX", 1181412, "SPACE EXPLORATION", "10-K")
    selected, excluded = fr.select([recent], spcx, WINDOW, set())
    assert selected == []
    assert len(excluded) == 1
    assert excluded[0]["ticker"] == "SPCX" and excluded[0]["form"] == "10-K"
    assert excluded[0]["reason"] == "no_annual_report"
    assert excluded[0]["accession"] is None


def test_only_outside_window_filings_also_means_no_annual_report():
    recent = block(("10-K", "2021-02-10", "2020-12-31", "0000001234-21-000010", "old.htm"))
    selected, excluded = fr.select([recent], ACME, WINDOW, set())
    assert selected == []
    assert sorted(e["reason"] for e in excluded) == ["no_annual_report", "outside_window"]


# --- older-filings pages ----------------------------------------------------------------

def test_older_filings_page_read_only_when_its_dates_overlap_the_window():
    pages = [
        {"name": "CIK0000001234-submissions-001.json", "filingCount": 2000,
         "filingFrom": "2023-01-02", "filingTo": "2024-06-30"},   # inside
        {"name": "CIK0000001234-submissions-002.json", "filingCount": 2000,
         "filingFrom": "2021-01-01", "filingTo": "2021-10-07"},   # touches the first day
        {"name": "CIK0000001234-submissions-003.json", "filingCount": 2000,
         "filingFrom": "2020-01-01", "filingTo": "2021-10-06"},   # ends the day before
        {"name": "CIK0000001234-submissions-004.json", "filingCount": 2000,
         "filingFrom": "2026-10-06", "filingTo": "2026-12-31"},   # starts the last day
        {"name": "CIK0000001234-submissions-005.json", "filingCount": 2000,
         "filingFrom": "2026-10-07", "filingTo": "2027-03-31"},   # starts the day after
        {"name": "CIK0000001234-submissions-006.json", "filingCount": 2000,
         "filingFrom": "2001-01-01", "filingTo": "2030-01-01"},   # spans the window
    ]
    recent = block(("10-K", "2026-02-10", "2025-12-31", "0000001234-26-000010", "a.htm"))
    older = block(("10-K", "2024-02-10", "2023-12-31", "0000001234-24-000010", "b.htm"))
    data = {"cik": "1234", "name": "ACME CORP", "filings": {"recent": recent, "files": pages}}
    requested = []

    def fetch(url):
        requested.append(url)
        return older

    blocks = fr.submission_blocks(data, fetch, WINDOW)
    assert requested == [
        "https://data.sec.gov/submissions/CIK0000001234-submissions-001.json",
        "https://data.sec.gov/submissions/CIK0000001234-submissions-002.json",
        "https://data.sec.gov/submissions/CIK0000001234-submissions-004.json",
        "https://data.sec.gov/submissions/CIK0000001234-submissions-006.json",
    ]
    assert blocks[0] is recent and len(blocks) == 5
    selected, _ = fr.select(blocks, ACME, WINDOW, set())
    assert [e["accession"] for e in selected] == [
        "0000001234-24-000010", "0000001234-26-000010"]


def test_no_older_pages_means_no_extra_request():
    recent = block(("10-K", "2026-02-10", "2025-12-31", "0000001234-26-000010", "a.htm"))
    data = {"name": "ACME CORP", "filings": {"recent": recent}}

    def fetch(url):
        raise AssertionError(url)

    assert fr.submission_blocks(data, fetch, WINDOW) == [recent]


# --- issuers and Phase A ------------------------------------------------------------------

def test_issuers_come_from_phase_a_with_annual_forms():
    assert len(fr.ISSUERS) == 18
    phase_a = {ticker: cik for ticker, cik, *_ in fr.PHASE_A.ISSUERS}
    assert {ticker: cik for ticker, cik, _name, _form in fr.ISSUERS} == phase_a
    forms = {ticker: form for ticker, _cik, _name, form in fr.ISSUERS}
    assert {t for t, f in forms.items() if f == "20-F"} == {"TSM", "BABA", "NVO"}
    assert {t for t, f in forms.items() if f != "20-F"} == set(phase_a) - {"TSM", "BABA", "NVO"}
    assert set(forms.values()) == {"10-K", "20-F"}
    assert forms["AMZN"] == forms["GOOGL"] == forms["SPCX"] == "10-K"


def test_phase_a_accessions_cover_the_edgar_manifest_and_the_fixtures():
    accessions = fr.phase_a_accessions()
    with open(fr.PHASE_A_MANIFEST, encoding="utf-8") as handle:
        edgar = {d["accession"] for d in json.load(handle)["documents"]}
    with open(fr.FIXTURES_MANIFEST, encoding="utf-8") as handle:
        fixtures = {f["accession"] for f in json.load(handle)["fixtures"]}
    assert len(edgar) == 18 and len(fixtures) == 5
    assert accessions == edgar | fixtures
    assert "0000019617-25-000270" in accessions      # JPM 10-K filed 2025-02-14
    assert "0000320193-23-000106" in accessions      # fixture aapl-2023-10k


def test_other_annual_forms_in_the_window_are_reported():
    recent = block(
        ("10-KT", "2023-03-01", "2022-12-31", "0000001234-23-000030", "acme-10kt.htm"),
        ("10-K/A", "2023-04-01", "2022-06-30", "0000001234-23-000040", "acme-10ka.htm"),
        ("10-KT", "2020-03-01", "2019-12-31", "0000001234-20-000030", "old-10kt.htm"),
        ("NT 10-K", "2023-02-28", "2022-12-31", "0000001234-23-000020", "nt.htm"),
    )
    others = fr.other_annual_forms([recent], ACME, WINDOW)
    assert [(e["form"], e["accession"]) for e in others] == [("10-KT", "0000001234-23-000030")]


# --- list stage (fake fetcher, no network) ------------------------------------------------

def _index(*files):
    return {"directory": {"name": "/Archives/edgar/data/x", "parent-dir": "/Archives/edgar/data",
                          "item": [{"last-modified": "2024-02-10 16:05:00", "name": name,
                                    "type": "text.gif", "size": size} for name, size in files]}}


def _fake_edgar():
    acme_recent = block(
        ("10-K", "2025-02-14", "2024-12-31", "0000001234-25-000010", "acme-20241231.htm"),
        ("10-K/A", "2024-04-30", "2023-12-31", "0000001234-24-000020", "acme-10ka.htm"),
        ("10-K", "2024-02-14", "2023-12-31", "0000001234-24-000010", "acme-20231231.htm"),
    )
    acme_older = block(
        ("10-K", "2022-02-14", "2021-12-31", "0000001234-22-000010", "acme-20211231.htm"),
        ("10-K", "2021-02-14", "2020-12-31", "0000001234-21-000010", "acme-20201231.htm"),
    )
    none_recent = block(("10-Q", "2026-08-04", "2026-06-30", "0000009999-26-000001", "q.htm"))
    return {
        "https://data.sec.gov/submissions/CIK0000001234.json": {
            "name": "ACME CORP", "filings": {"recent": acme_recent, "files": [
                {"name": "CIK0000001234-submissions-001.json", "filingCount": 3,
                 "filingFrom": "2019-01-01", "filingTo": "2022-12-31"},
                {"name": "CIK0000001234-submissions-002.json", "filingCount": 3,
                 "filingFrom": "1999-01-01", "filingTo": "2018-12-31"}]}},
        "https://data.sec.gov/submissions/CIK0000001234-submissions-001.json": acme_older,
        "https://data.sec.gov/submissions/CIK0000009999.json": {
            "name": "NONE INC", "filings": {"recent": none_recent, "files": []}},
        "https://www.sec.gov/Archives/edgar/data/1234/000000123424000010/index.json": _index(
            ("acme-20231231.htm", "2345678"), ("R1.htm", "1000"), ("Financial_Report.xlsx", "9")),
        "https://www.sec.gov/Archives/edgar/data/1234/000000123422000010/index.json": _index(
            ("acme-20211231.htm", "1000000"), ("FilingSummary.xml", "50")),
        # Only requested when the 2025 filing is not a Phase A duplicate.
        "https://www.sec.gov/Archives/edgar/data/1234/000000123425000010/index.json": _index(
            ("acme-20241231.htm", "3000000")),
    }


def test_list_draft_uses_index_requests_only_and_sizes_from_index_json():
    responses = _fake_edgar()
    requested = []

    def fetch(url):
        requested.append(url)
        return responses[url]

    issuers = [("ACME", 1234, "ACME", "10-K"), ("NONE", 9999, "NONE", "10-K")]
    draft = fr.build_draft(issuers, fetch, WINDOW, {"0000001234-25-000010"})
    assert requested == [
        "https://data.sec.gov/submissions/CIK0000001234.json",
        "https://data.sec.gov/submissions/CIK0000001234-submissions-001.json",
        "https://www.sec.gov/Archives/edgar/data/1234/000000123422000010/index.json",
        "https://www.sec.gov/Archives/edgar/data/1234/000000123424000010/index.json",
        "https://data.sec.gov/submissions/CIK0000009999.json",
    ]
    assert draft["window"] == {"from": "2021-10-07", "to": "2026-10-06"}
    docs = draft["documents"]
    assert [list(d) for d in docs][0] == [
        "ticker", "company", "cik", "form", "report_date", "filing_date", "accession", "url",
        "bytes", "amendment"]
    assert [(d["ticker"], d["company"], d["report_date"], d["bytes"]) for d in docs] == [
        ("ACME", "ACME CORP", "2021-12-31", 1000000),
        ("ACME", "ACME CORP", "2023-12-31", 2345678),
    ]
    assert draft["totals"] == {"documents": 2, "bytes": 3345678}
    reasons = sorted((e["ticker"], e["reason"]) for e in draft["excluded"])
    assert reasons == [
        ("ACME", "amendment"), ("ACME", "outside_window"), ("ACME", "phase_a_duplicate"),
        ("NONE", "no_annual_report")]
    assert all(e["company"] for e in draft["excluded"])
    assert draft["other_annual_forms"] == []


def test_list_stops_when_the_company_name_does_not_match():
    responses = _fake_edgar()
    with pytest.raises(ValueError, match="ACME CORP"):
        fr.build_draft([("ACME", 1234, "WIDGETS", "10-K")], responses.__getitem__, WINDOW, set())


def test_list_stops_when_the_primary_document_is_missing_from_index_json():
    responses = _fake_edgar()
    url = "https://www.sec.gov/Archives/edgar/data/1234/000000123424000010/index.json"
    responses[url] = _index(("other.htm", "5"))
    with pytest.raises(ValueError, match="acme-20231231.htm"):
        fr.build_draft([("ACME", 1234, "ACME", "10-K")], responses.__getitem__, WINDOW, set())


def test_list_cli_never_writes_the_user_agent(monkeypatch):
    responses = _fake_edgar()
    sessions = []

    class FakeResponse:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            pass

        def json(self):
            return responses[self.url]

    class FakeSession:
        def __init__(self):
            self.headers = {}
            sessions.append(self)

        def get(self, url, timeout=None):
            return FakeResponse(url)

    monkeypatch.setattr(fr.requests, "Session", FakeSession)
    monkeypatch.setattr(fr.PHASE_A, "PAUSE", 0)
    monkeypatch.setattr(fr, "ISSUERS", [("ACME", 1234, "ACME", "10-K")])
    agent = "Test Person test.person@example.com"
    # tempfile, not pytest's tmp_path: a stale pytest-current link in this machine's temp
    # folder breaks tmp_path's clean-up.
    with tempfile.TemporaryDirectory() as folder:
        out = os.path.join(folder, "manifest_draft.json")
        assert fr.main(["list", "--user-agent", agent, "--out", out]) == 0
        with open(out, encoding="utf-8") as handle:
            text = handle.read()
    assert sessions[0].headers["User-Agent"] == agent
    assert agent not in text and "example.com" not in text
    assert json.loads(text)["totals"]["documents"] == 3


# --- loader (synthetic cache and manifest) ---------------------------------------------------

@pytest.fixture(scope="module")
def cr():
    return _load("corpus_recent")


def _corpus(folder, files):
    """A cache holding files ({name: bytes}) and a manifest listing each with its SHA-256,
    in the given (unsorted) order. Returns (cache, manifest path)."""
    cache = os.path.join(folder, "cache")
    os.makedirs(cache)
    entries = []
    for name, raw in files.items():
        with open(os.path.join(cache, name), "wb") as handle:
            handle.write(raw)
        entries.append({"file": name, "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest()})
    manifest = os.path.join(folder, "manifest.json")
    with open(manifest, "w", encoding="utf-8") as handle:
        json.dump({"documents": entries}, handle)
    return cache, manifest


FILES = {
    "TSLA-10-K-2022-02-07.htm": b"<html>tesla</html>",
    "BAC-10-K-2023-02-22.htm": b"<html>bank</html>",
    "AMZN-10-K-2022-02-04.htm": b"<html>amazon</html>",
}


def test_loader_returns_recent_ids_in_sorted_file_order(cr):
    with tempfile.TemporaryDirectory() as folder:
        cache, manifest = _corpus(folder, FILES)
        docs, skipped = cr.documents(cache, manifest=manifest)
    assert [doc_id for doc_id, _group, _raw in docs] == [
        "recent:AMZN-10-K-2022-02-04.htm",
        "recent:BAC-10-K-2023-02-22.htm",
        "recent:TSLA-10-K-2022-02-07.htm",
    ]
    assert {group for _id, group, _raw in docs} == {"recent"}
    assert {doc_id: raw for doc_id, _group, raw in docs} == {
        f"recent:{name}": raw for name, raw in FILES.items()}
    assert skipped == []


def test_loader_raises_on_a_sha256_mismatch(cr):
    with tempfile.TemporaryDirectory() as folder:
        cache, manifest = _corpus(folder, FILES)
        with open(os.path.join(cache, "BAC-10-K-2023-02-22.htm"), "wb") as handle:
            handle.write(b"<html>bank, edited</html>")
        with pytest.raises(ValueError, match="BAC-10-K-2023-02-22.htm"):
            cr.documents(cache, manifest=manifest)


def test_loader_raises_on_a_missing_file(cr):
    with tempfile.TemporaryDirectory() as folder:
        cache, manifest = _corpus(folder, FILES)
        os.remove(os.path.join(cache, "TSLA-10-K-2022-02-07.htm"))
        with pytest.raises(FileNotFoundError, match="TSLA-10-K-2022-02-07.htm"):
            cr.documents(cache, manifest=manifest)


def test_loader_reports_cache_files_missing_from_the_manifest_as_skipped(cr):
    with tempfile.TemporaryDirectory() as folder:
        cache, manifest = _corpus(folder, FILES)
        with open(os.path.join(cache, "KO-10-K-2099-01-01.htm"), "wb") as handle:
            handle.write(b"<html>stray</html>")
        docs, skipped = cr.documents(cache, manifest=manifest)
    assert len(docs) == 3
    assert skipped == ["recent:KO-10-K-2099-01-01.htm (not in manifest.json)"]


def test_loader_reads_this_folders_manifest_by_default(cr):
    assert cr.MANIFEST == os.path.join(HERE, "manifest.json")


# --- download stage (fake requests.Session, no network) --------------------------------------

ACME_2021 = "https://www.sec.gov/Archives/edgar/data/1234/000000123422000010/acme-20211231.htm"
ACME_2023 = "https://www.sec.gov/Archives/edgar/data/1234/000000123424000010/acme-20231231.htm"
TSMX_2024 = "https://www.sec.gov/Archives/edgar/data/5678/000123456725000100/tsmx-20f.htm"
BODIES = {ACME_2021: b"<html>acme 2021</html>", ACME_2023: b"<html>acme 2023</html>",
          TSMX_2024: b"<html>tsmx 2024, longer than its index size</html>"}


def _doc(ticker, cik, form, report, filed, accession, url, size):
    return {"ticker": ticker, "company": f"{ticker} CORP", "cik": cik, "form": form,
            "report_date": report, "filing_date": filed, "accession": accession, "url": url,
            "bytes": size, "amendment": False}


def _write_draft(folder, documents):
    draft = {"window": {"from": WINDOW[0], "to": WINDOW[1]}, "documents": documents,
             "excluded": [{"ticker": "ACME", "reason": "phase_a_duplicate"}],
             "other_annual_forms": [],
             "totals": {"documents": len(documents), "bytes": sum(d["bytes"] for d in documents)}}
    path = os.path.join(folder, "manifest_draft.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(draft, handle)
    return path


def _draft_documents():
    return [
        _doc("ACME", 1234, "10-K", "2021-12-31", "2022-02-14", "0000001234-22-000010",
             ACME_2021, len(BODIES[ACME_2021])),
        _doc("ACME", 1234, "10-K", "2023-12-31", "2024-02-14", "0000001234-24-000010",
             ACME_2023, len(BODIES[ACME_2023])),
        _doc("TSMX", 5678, "20-F", "2024-12-31", "2025-04-17", "0001234567-25-000100",
             TSMX_2024, 20),  # index.json said 20 bytes: a size difference to report
    ]


@pytest.fixture
def fake_sec(monkeypatch):
    """requests.Session replaced by a fake serving BODIES. Returns (requested urls, sessions,
    failing urls); a url added to `failing` answers 404."""
    requested, sessions, failing = [], [], set()

    class FakeResponse:
        def __init__(self, url):
            self.url = url
            self.status_code = 404 if url in failing else 200
            self.content = BODIES.get(url, b"")

        def raise_for_status(self):
            if self.status_code != 200:
                raise fr.requests.HTTPError(
                    f"{self.status_code} Client Error for url: {self.url}", response=self)

    class FakeSession:
        def __init__(self):
            self.headers = {}
            sessions.append(self)

        def get(self, url, timeout=None):
            requested.append(url)
            return FakeResponse(url)

    monkeypatch.setattr(fr.requests, "Session", FakeSession)
    monkeypatch.setattr(fr.PHASE_A, "PAUSE", 0)
    return requested, sessions, failing


def _download(folder, draft, agent="Test Person test.person@example.com"):
    cache = os.path.join(folder, "cache")
    manifest = os.path.join(folder, "manifest.json")
    code = fr.main(["download", "--user-agent", agent, "--draft", draft, "--cache", cache,
                    "--manifest", manifest])
    return code, cache, manifest


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


def test_download_fetches_each_document_once_then_skips_files_cached_with_the_manifest_hash(
        fake_sec):
    requested, sessions, _failing = fake_sec
    agent = "Test Person test.person@example.com"
    with tempfile.TemporaryDirectory() as folder:
        draft = _write_draft(folder, _draft_documents())
        cache = os.path.join(folder, "cache")
        os.makedirs(cache)
        # Already in the cache, but no manifest records its hash yet: fetched all the same.
        with open(os.path.join(cache, "ACME-10-K-2022-02-14.htm"), "wb") as handle:
            handle.write(BODIES[ACME_2021])

        code, cache, manifest_path = _download(folder, draft, agent)
        assert code == 0
        assert requested == [ACME_2021, ACME_2023, TSMX_2024]
        assert sessions[0].headers["User-Agent"] == agent
        assert sorted(os.listdir(cache)) == [
            "ACME-10-K-2022-02-14.htm", "ACME-10-K-2024-02-14.htm", "TSMX-20-F-2025-04-17.htm"]
        assert _read(os.path.join(cache, "TSMX-20-F-2025-04-17.htm")) == BODIES[TSMX_2024]
        text = _read(manifest_path).decode("utf-8")
        assert agent not in text and "example.com" not in text
        manifest = json.loads(text)
        docs = manifest["documents"]
        assert list(docs[0]) == [
            "ticker", "company", "cik", "form", "report_date", "filing_date", "accession", "url",
            "bytes", "amendment", "file", "sha256"]
        assert [(d["file"], d["bytes"], d["sha256"]) for d in docs] == [
            (f"{d['ticker']}-{d['form']}-{d['filing_date']}.htm", len(BODIES[d["url"]]),
             hashlib.sha256(BODIES[d["url"]]).hexdigest()) for d in _draft_documents()]
        assert manifest["size_mismatches"] == [
            {"file": "TSMX-20-F-2025-04-17.htm", "index_bytes": 20,
             "bytes": len(BODIES[TSMX_2024])}]
        assert manifest["totals"] == {"documents": 3,
                                      "bytes": sum(len(body) for body in BODIES.values())}
        assert manifest["excluded"] == [{"ticker": "ACME", "reason": "phase_a_duplicate"}]
        assert manifest["window"] == {"from": WINDOW[0], "to": WINDOW[1]}

        # A second run finds every file cached with the manifest's hash: no request at all.
        requested.clear()
        assert _download(folder, draft, agent)[0] == 0
        assert requested == []
        assert json.loads(_read(manifest_path)) == manifest

        # An edited file and a deleted file are fetched again; the third is still skipped.
        with open(os.path.join(cache, "ACME-10-K-2024-02-14.htm"), "wb") as handle:
            handle.write(b"<html>edited</html>")
        os.remove(os.path.join(cache, "TSMX-20-F-2025-04-17.htm"))
        assert _download(folder, draft, agent)[0] == 0
        assert requested == [ACME_2023, TSMX_2024]
        assert _read(os.path.join(cache, "ACME-10-K-2024-02-14.htm")) == BODIES[ACME_2023]
        assert json.loads(_read(manifest_path)) == manifest


def test_download_stops_at_the_first_http_error_with_its_url_and_writes_no_manifest(
        fake_sec, capsys):
    requested, _sessions, failing = fake_sec
    failing.add(ACME_2023)
    with tempfile.TemporaryDirectory() as folder:
        draft = _write_draft(folder, _draft_documents())
        code, cache, manifest = _download(folder, draft)
        assert code == 1
        assert requested == [ACME_2021, ACME_2023]  # nothing after the failure
        assert not os.path.exists(manifest)
        assert sorted(os.listdir(cache)) == ["ACME-10-K-2022-02-14.htm"]  # no partial file
    assert ACME_2023 in capsys.readouterr().err


@pytest.mark.parametrize("field, value", [
    ("url", "https://example.com/Archives/edgar/data/1234/000000123424000010/acme-20231231.htm"),
    ("url", "http://www.sec.gov/Archives/edgar/data/1234/000000123424000010/acme-20231231.htm"),
    ("url", "https://www.sec.gov/Archives/edgar/data/9999/000000123424000010/acme-20231231.htm"),
    ("form", "10-K/A"),
    ("filing_date", "2022-02-14"),  # the same file name as the first document
])
def test_download_checks_every_draft_entry_before_any_request(fake_sec, field, value):
    requested, _sessions, _failing = fake_sec
    documents = _draft_documents()
    documents[1][field] = value
    with tempfile.TemporaryDirectory() as folder:
        draft = _write_draft(folder, documents)
        code, _cache, manifest = _download(folder, draft)
        assert code == 1
        assert requested == []
        assert not os.path.exists(manifest)


def test_download_refuses_a_cache_or_manifest_in_rcqwealth(fake_sec):
    with tempfile.TemporaryDirectory() as folder:
        draft = _write_draft(folder, _draft_documents())
        for cache, manifest in (("E:/RCQWealth/x", os.path.join(folder, "m.json")),
                                (os.path.join(folder, "c"), "E:\\RCQWealth\\m.json")):
            with pytest.raises(SystemExit):
                fr.main(["download", "--user-agent", "a b@c.d", "--draft", draft,
                         "--cache", cache, "--manifest", manifest])
    assert fake_sec[0] == []


# --- the acceptance tooling's --corpus switch (../2026-10-06-table-merge-header-acceptance) ---

ACC = os.path.join(os.path.dirname(HERE), "2026-10-06-table-merge-header-acceptance")
NOT_APPLICABLE = "not applicable"


@pytest.fixture(scope="module")
def acc():
    spec = importlib.util.spec_from_file_location("acc_common", os.path.join(ACC, "acc_common.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recent_docs(files):
    """(id, group, raw) in corpus_recent.documents()'s form for files ({name: bytes})."""
    return [(f"recent:{name}", "recent", raw) for name, raw in sorted(files.items())]


def _with_totals(manifest, documents):
    """Give a synthetic manifest fetch_recent.py's `totals`, with the given document count."""
    with open(manifest, encoding="utf-8") as handle:
        data = json.load(handle)
    data["totals"] = {"documents": documents, "bytes": sum(d["bytes"] for d in data["documents"])}
    with open(manifest, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def test_acc_reads_this_folders_loader_and_manifest(acc, cr):
    assert os.path.normcase(acc.RECENT_MANIFEST) == os.path.normcase(cr.MANIFEST)
    assert os.path.normcase(acc.RECENT) == os.path.normcase(os.path.join(HERE, "corpus_recent.py"))


def test_acc_corpus_defaults_to_phase_a(acc):
    assert acc.CORPORA == ("phase-a", "recent")
    for function in (acc.load_documents, acc.verify_hashes):
        assert inspect.signature(function).parameters["corpus"].default == "phase-a"
    assert inspect.signature(acc.load_documents).parameters["recent_cache"].default is None


@pytest.mark.parametrize("totals", [3, None])
def test_verify_hashes_recent_accepts_a_matching_manifest(acc, monkeypatch, totals):
    with tempfile.TemporaryDirectory() as folder:
        _cache, manifest = _corpus(folder, FILES)
        if totals is not None:
            _with_totals(manifest, totals)
        monkeypatch.setattr(acc, "RECENT_MANIFEST", manifest)
        record = acc.verify_hashes(_recent_docs(FILES), corpus="recent")
    assert record == {"corpus": "recent", "documents": 3, "manifest_documents": 3,
                      "manifest_totals_documents": totals, "matched_manifest": 3, "mismatches": [],
                      "missing": [], "extra_in_manifest": [], "ok": True}


def test_verify_hashes_recent_rejects_a_sha256_mismatch(acc, monkeypatch):
    docs = _recent_docs(FILES)
    edited = b"<html>bank, edited</html>"
    assert docs[1][0] == "recent:BAC-10-K-2023-02-22.htm"
    docs[1] = (docs[1][0], "recent", edited)
    with tempfile.TemporaryDirectory() as folder:
        _cache, manifest = _corpus(folder, FILES)
        _with_totals(manifest, 3)
        monkeypatch.setattr(acc, "RECENT_MANIFEST", manifest)
        record = acc.verify_hashes(docs, corpus="recent")
    assert record["ok"] is False
    assert record["matched_manifest"] == 2
    assert record["mismatches"] == [(
        "recent:BAC-10-K-2023-02-22.htm", "manifest.json",
        hashlib.sha256(FILES["BAC-10-K-2023-02-22.htm"]).hexdigest(), hashlib.sha256(edited).hexdigest())]


@pytest.mark.parametrize("case", ["left_out", "not_in_manifest", "phase_a_id", "duplicate", "totals",
                                  "empty"])
def test_verify_hashes_recent_requires_exactly_the_manifests_documents(acc, monkeypatch, case):
    docs, files, totals = _recent_docs(FILES), dict(FILES), 3
    if case == "left_out":
        docs = docs[:2]
    elif case == "not_in_manifest":
        docs.append(("recent:KO-10-K-2099-01-01.htm", "recent", b"<html>stray</html>"))
    elif case == "phase_a_id":  # the right bytes, under a Phase A id and group
        docs[0] = ("edgar:AMZN-10-K-2022-02-04.htm", "edgar", docs[0][2])
    elif case == "duplicate":
        docs.append(docs[0])
    elif case == "totals":
        totals = 4
    else:
        docs, files, totals = [], {}, 0
    with tempfile.TemporaryDirectory() as folder:
        _cache, manifest = _corpus(folder, files)
        _with_totals(manifest, totals)
        monkeypatch.setattr(acc, "RECENT_MANIFEST", manifest)
        record = acc.verify_hashes(docs, corpus="recent")
    assert record["ok"] is False
    assert record["mismatches"] == []
    expected = {"left_out": ("extra_in_manifest", ["TSLA-10-K-2022-02-07.htm"]),
                "not_in_manifest": ("missing", ["recent:KO-10-K-2099-01-01.htm"]),
                "phase_a_id": ("missing", ["edgar:AMZN-10-K-2022-02-04.htm"])}
    if case in expected:
        key, value = expected[case]
        assert record[key] == value


def test_verify_hashes_phase_a_record_keeps_its_keys(acc, monkeypatch):
    """The default record flows into run_check.json, which must not change."""
    raw = b"<html>ko</html>"
    digest = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as folder:
        results = os.path.join(folder, "results.json")
        manifest = os.path.join(folder, "edgar_manifest.json")
        with open(results, "w", encoding="utf-8") as handle:
            json.dump({"documents": [{"id": "edgar:KO-10-K-2025-02-20.htm", "sha256": digest}]}, handle)
        with open(manifest, "w", encoding="utf-8") as handle:
            json.dump({"documents": [{"file": "KO-10-K-2025-02-20.htm", "sha256": digest}]}, handle)
        monkeypatch.setattr(acc, "RESULTS", results)
        monkeypatch.setattr(acc, "MANIFEST", manifest)
        record = acc.verify_hashes([("edgar:KO-10-K-2025-02-20.htm", "edgar", raw)])
    assert list(record) == ["documents", "results_json_documents", "matched_results", "edgar_documents",
                            "matched_manifest", "mismatches", "missing", "extra_in_results", "ok"]
    assert record["matched_results"] == record["matched_manifest"] == 1
    assert record["ok"] is False  # Phase A's check still requires its 109 documents and 18 EDGAR ones


def test_load_documents_recent_returns_corpus_recents_documents(acc, cr, monkeypatch):
    here = os.getcwd()
    with tempfile.TemporaryDirectory() as folder:
        cache, manifest = _corpus(folder, FILES)
        with open(os.path.join(cache, "KO-10-K-2099-01-01.htm"), "wb") as handle:
            handle.write(b"<html>stray</html>")
        monkeypatch.setattr(acc, "RECENT_MANIFEST", manifest)
        loaded = acc.load_documents(None, None, corpus="recent", recent_cache=cache)
        expected = cr.documents(cache, manifest=manifest)
    assert os.getcwd() == here
    assert loaded == expected
    assert [doc_id for doc_id, _group, _raw in loaded[0]] == [
        "recent:AMZN-10-K-2022-02-04.htm", "recent:BAC-10-K-2023-02-22.htm",
        "recent:TSLA-10-K-2022-02-07.htm"]
    assert loaded[1] == ["recent:KO-10-K-2099-01-01.htm (not in manifest.json)"]


def test_load_documents_recent_checks_each_file_against_the_manifest(acc, monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        cache, manifest = _corpus(folder, FILES)
        with open(os.path.join(cache, "BAC-10-K-2023-02-22.htm"), "wb") as handle:
            handle.write(b"<html>bank, edited</html>")
        monkeypatch.setattr(acc, "RECENT_MANIFEST", manifest)
        with pytest.raises(ValueError, match="BAC-10-K-2023-02-22.htm"):
            acc.load_documents(None, None, corpus="recent", recent_cache=cache)


def test_load_documents_recent_needs_its_cache_and_unknown_corpora_are_refused(acc):
    with pytest.raises(ValueError, match="recent_cache"):
        acc.load_documents(None, None, corpus="recent")
    with pytest.raises(ValueError, match="phase-b"):
        acc.load_documents("cache", "root", corpus="phase-b")
    with pytest.raises(ValueError, match="phase-b"):
        acc.verify_hashes([], corpus="phase-b")


def _document_parser(acc):
    ap = argparse.ArgumentParser(prog="script.py")
    acc.add_document_arguments(ap)
    return ap


@pytest.mark.parametrize("argv, message", [
    ([], "the following arguments are required: --fixtures-root, --edgar-cache"),
    (["--fixtures-root", "f"], "the following arguments are required: --edgar-cache"),
    (["--fixtures-root", "f", "--edgar-cache", "e", "--recent-cache", "r"], "--recent-cache"),
    (["--corpus", "recent"], "--recent-cache"),
    (["--corpus", "recent", "--recent-cache", "r", "--edgar-cache", "e"], "--edgar-cache"),
    (["--corpus", "recent", "--recent-cache", "r", "--fixtures-root", "f"], "--fixtures-root"),
    (["--corpus", "phase-b", "--recent-cache", "r"], "invalid choice"),
])
def test_document_arguments_refuse_the_other_corpus_inputs(acc, capsys, argv, message):
    ap = _document_parser(acc)
    with pytest.raises(SystemExit) as raised:
        acc.check_document_arguments(ap, ap.parse_args(argv))
    assert raised.value.code == 2
    assert message in capsys.readouterr().err


def test_document_arguments_accept_each_corpus(acc):
    ap = _document_parser(acc)
    args = ap.parse_args(["--fixtures-root", "f", "--edgar-cache", "e"])
    acc.check_document_arguments(ap, args)
    assert (args.corpus, args.recent_cache) == ("phase-a", None)
    args = ap.parse_args(["--corpus", "recent", "--recent-cache", "r"])
    acc.check_document_arguments(ap, args)
    assert (args.corpus, args.fixtures_root, args.edgar_cache) == ("recent", None, None)


def _script(*argv):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, *argv], capture_output=True, text=True, encoding="utf-8",
                          env=env, timeout=300)


@pytest.mark.parametrize("script", [
    ["run_side.py"], ["merges_main.py"], ["analyze_candidate.py"], ["review_sample.py"],
    ["inspect_unit.py"], ["xlsx_detail.py", "dump"]], ids=lambda s: " ".join(s))
def test_every_document_loading_script_takes_the_corpus_options(script):
    result = _script(os.path.join(ACC, script[0]), *script[1:], "--help")
    assert result.returncode == 0, result.stderr
    assert "--corpus {phase-a,recent}" in result.stdout
    assert "--recent-cache" in result.stdout


@pytest.mark.parametrize("argv", [
    ["shifted_tables.py", "--main-dir", "m", "--candidate-dir", "c"],
    ["review_sample.py", "--recent-cache", "r", "--main-dir", "m", "--candidate-dir", "c"],
    ["overhead.py", "--main-src", "m", "--candidate-src", "c", "--fixtures-root", "f"],
], ids=lambda a: a[0])
def test_phase_a_only_scripts_refuse_the_recent_corpus(argv):
    with tempfile.TemporaryDirectory() as folder:
        out = os.path.join(folder, "out")
        result = _script(os.path.join(ACC, argv[0]), *argv[1:], "--out", out, "--corpus", "recent")
        assert not os.path.exists(out)
    assert result.returncode == 1
    assert "Phase A" in result.stderr and "--corpus recent" in result.stderr


# report.py on synthetic dumps of one document: every value check_tables' coverage has, at 0.
COVERAGE = [[key, 0] for key in (
    "tables_total", "tables_evaluated", "table_no_output", "table_no_separator", "table_unreliable_grid",
    "table_no_header", "table_no_data", "rows_data", "rows_paired", "row_below_repeated_header",
    "row_unpaired", "values_total", "values_evaluated", "value_nil", "value_no_discriminating_header",
    "value_missing_in_output", "value_ambiguous_position", "value_ambiguous_header",
    "value_unevaluated_budget", "values_aligned", "values_misaligned")]
SPLIT = {"row": 2, "cell": "(1,234"}


def _mode_dump(capture):
    record = {"units": [{"path": "tableparser", "output": "| Revenue | 7 |"}],
              "findings": [{"table": 1, "snapshot": None, "page": 1, "missing_values": [["7", "x"]],
                            "missing_reported": [], "structure": [], "produced_output": True}],
              "warnings": [], "trace_failures": [], "header_accounting_misses": [], "alignment": [],
              "alignment_coverage": COVERAGE, "pages": [[1, None]],
              "sections": {filing_type: [] for filing_type in ("10-K", "10-Q", "20-F", "8-K")}}
    if capture:
        record["xlsx"] = []
    return record


def _report_inputs(acc, folder, doc_id, corpus, merges_corpus):
    """The three dump folders and the merges file report.py reads, for one document. `corpus`
    and `merges_corpus` are the recorded corpus (None: no record, as in every Phase A run)."""
    dirs = {}
    for name in ("main", "candidate", "analysis"):
        dirs[name] = os.path.join(folder, name)
        os.makedirs(dirs[name])
        run = {"sec2md_file": f"{name}/sec2md/__init__.py", "documents": [doc_id], "document_seconds": {}}
        with open(os.path.join(dirs[name], "_run.json"), "w", encoding="utf-8") as handle:
            json.dump(run if corpus is None else {"corpus": corpus, **run}, handle)
    side = {"id": doc_id, "sha256": "0" * 64,
            "modes": {"normal": _mode_dump(False), "capture": _mode_dump(True)}}
    for name in ("main", "candidate"):
        acc.write_json_gz(os.path.join(dirs[name], acc.safe_name(doc_id)), side)
    analysis = {
        "id": doc_id, "units": [{"unit": 1}], "deterministic_outputs": True,
        "coverage": {"main": COVERAGE, "candidate": COVERAGE},
        "production": {"main_normal": {"coverage": COVERAGE, "findings": []},
                       "main_capture": {"coverage": COVERAGE, "findings": []}},
        "candidate_dump_coverage": {"normal": COVERAGE, "capture": COVERAGE},
        "candidate_dump_findings": {"normal": [], "capture": []},
        "values": [], "losses": [], "retention": {}, "assignment": [],
        "splits": {"main": {"1": [SPLIT]}, "candidate": {"1": [SPLIT]}},
        "limitations": {key: [] for key in ("years_row", "identifier_caption", "year_run_no_data_after",
                                            "year_run_data_row")},
        "moved": [], "departures": [], "zone_cuts": []}
    acc.write_json_gz(os.path.join(dirs["analysis"], acc.safe_name(doc_id)), analysis)
    merges = os.path.join(folder, "merges.json.gz")
    summary = {"same_header_value_steps": 0}
    if merges_corpus is not None:
        summary = {"corpus": merges_corpus, **summary}
    acc.write_json_gz(merges, {"summary": summary, "documents": []})
    return dirs, merges


def _report(acc, folder, doc_id, recorded, merges_recorded, given):
    """Run report.py on synthetic inputs; (the completed process, {result file: parsed JSON})."""
    dirs, merges = _report_inputs(acc, folder, doc_id, recorded, merges_recorded)
    out = os.path.join(folder, "out")
    os.makedirs(out)
    result = _script(os.path.join(ACC, "report.py"), "--main-dir", dirs["main"], "--candidate-dir",
                     dirs["candidate"], "--analysis-dir", dirs["analysis"], "--merges", merges,
                     "--out-dir", out, *(["--corpus", given] if given else []))
    files = {}
    for name in sorted(os.listdir(out)):
        files[name] = None
        if name.endswith(".json"):
            with open(os.path.join(out, name), encoding="utf-8") as handle:
                files[name] = json.load(handle)
    return result, files


def test_report_recent_records_the_corpus_and_marks_phase_a_evidence_not_applicable(acc):
    doc_id = "recent:ACME-10-K-2024-02-14.htm"
    with tempfile.TemporaryDirectory() as folder:
        result, files = _report(acc, folder, doc_id, "recent", "recent", "recent")
    assert result.returncode == 0, result.stderr
    run_check, summary = files["run_check.json"], files["summary.json"]
    assert run_check["corpus"] == "recent" and summary["corpus"] == "recent"
    assert run_check["documents"] == [doc_id]
    assert {run["corpus"] for run in run_check["runs"].values()} == {"recent"}
    class8 = files["class8.json"]
    for key in ("tables", "fixed", "remaining"):
        assert class8[key].startswith(NOT_APPLICABLE)
        assert summary["class8"][key].startswith(NOT_APPLICABLE)
    assert class8["corpus"] == {"main": {"tables": 1, "cells": 1},
                                "candidate": {"tables": 1, "cells": 1}}
    assert class8["candidate_split_tables"] == [{"doc": doc_id, "table": 1, "cells": [SPLIT]}]
    assert summary["class8"]["candidate_split_tables"] == 1
    assert "candidate_split_tables_outside_class8" not in class8
    check1 = files["check1.json"]
    for key in ("genuine_main_tableparser_class1", "genuine_main_tables", "genuine_still_failing",
                "false_positives"):
        assert check1[key].startswith(NOT_APPLICABLE)
    for key in ("genuine_main_tableparser_class1", "genuine_still_failing"):
        assert summary["check1"][key].startswith(NOT_APPLICABLE)
    assert check1["residual_genuine"] == [
        {"doc": doc_id, "table": 1, "tokens": [["7", "x"]], "main_tokens": [["7", "x"]]}]
    assert files["findings.json"]["f_tables"].startswith(NOT_APPLICABLE)
    assert summary["findings"]["f_tables_changed"].startswith(NOT_APPLICABLE)
    assert files["sections.json"]["own_type"] == {"same": 2}  # 10-K, read from the recent id


def test_report_phase_a_writes_no_corpus_key_and_keeps_its_class8_and_class1_figures(acc):
    doc_id = "edgar:ACME-10-K-2024-02-14.htm"
    with tempfile.TemporaryDirectory() as folder:
        result, files = _report(acc, folder, doc_id, None, None, None)
    assert result.returncode == 0, result.stderr
    run_check, summary, class8, check1 = (
        files[name] for name in ("run_check.json", "summary.json", "class8.json", "check1.json"))
    assert list(run_check) == ["documents", "runs"]
    assert "corpus" not in summary and all("corpus" not in run for run in run_check["runs"].values())
    assert (class8["tables"], class8["fixed"], class8["remaining"]) == ([], 0, 0)
    assert class8["candidate_split_tables_outside_class8"] == [
        {"doc": doc_id, "table": 1, "cells": [SPLIT]}]
    assert (check1["genuine_main_tableparser_class1"], check1["genuine_still_failing"]) == (0, [])
    assert "false_positives" not in check1
    assert files["findings.json"]["f_tables"] == []
    assert files["sections.json"]["own_type"] == {"same": 2}


@pytest.mark.parametrize("recorded, merges_recorded, given", [
    ("recent", "recent", None),  # recent dumps, report run as phase-a
    (None, None, "recent"),  # Phase A dumps, report run as recent
    ("recent", None, "recent"),  # merges from a Phase A run
])
def test_report_refuses_inputs_made_with_another_corpus(acc, recorded, merges_recorded, given):
    with tempfile.TemporaryDirectory() as folder:
        result, files = _report(acc, folder, "recent:ACME-10-K-2024-02-14.htm", recorded,
                                merges_recorded, given)
    assert result.returncode == 1
    assert "corpus" in result.stderr
    assert files == {}
