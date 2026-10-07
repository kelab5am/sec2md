"""List, then (after the user approves the list) fetch, the recent filings corpus.

    python fetch_recent.py list --user-agent "<name> <email>" --out <folder>/manifest_draft.json
    python fetch_recent.py download --user-agent "<name> <email>"
        --draft <folder>/manifest_draft.json --cache <outputs>/recent-filings-corpus
        --manifest <folder>/manifest.json

The 18 issuers and their CIKs and name checks come from Phase A's fetch_edgar.py
(../2026-10-03-table-completeness-corpus/, imported by path). The forms are the annual
reports: 10-K, or 20-F for TSM, BABA and NVO. Every annual report filed from 2021-10-07 to
2026-10-06 (inclusive) is a candidate, one per report date (period of report): the
original over an amendment, an amendment only when it is the sole filing for its period
in the window. Accessions already in the Phase A corpus (its EDGAR manifest and the
tests/fixtures/sec fixtures) are left out.

The `list` stage makes index requests only, one at a time with Phase A's 0.25 s pause:
each issuer's submissions JSON, the older-filings pages whose date range overlaps the
window, and each selected filing's index.json (for the primary document's size). It
downloads no document. The User-Agent is given on the command line and never written to
a file. Any HTTP error stops the run with its URL, and no draft is written.

The `download` stage reads the approved draft and fetches each primary document once, with
the same pause, into the cache as `<TICKER>-<FORM>-<filing date>.htm`. Every draft entry is
checked before the first request: its URL must be a document in its own filing's folder
under https://www.sec.gov/Archives/edgar/data/, and its file name plain and unique. Redirects
are refused, so only the draft's URLs are requested. A file already in the cache with the
SHA-256 an existing manifest records for it (same file and accession) is not fetched again.
Any HTTP error stops the run with its URL; the files fetched so far stay in the cache, and
no manifest is written. Otherwise the manifest is the draft with each document's file name,
actual byte count and SHA-256, the documents whose size differs from index.json's, and the
totals recomputed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from collections import defaultdict

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
AUDITS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(AUDITS)))
PHASE_A_DIR = os.path.join(AUDITS, "2026-10-03-table-completeness-corpus")
PHASE_A_MANIFEST = os.path.join(PHASE_A_DIR, "edgar_manifest.json")
FIXTURES_MANIFEST = os.path.join(ROOT, "tests", "fixtures", "sec", "manifest.json")
WINDOW = ("2021-10-07", "2026-10-06")
SUBMISSIONS = "https://data.sec.gov/submissions/"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data/"


def _phase_a_module():
    """Phase A's fetch_edgar.py, imported by path without writing bytecode into its folder."""
    spec = importlib.util.spec_from_file_location(
        "fetch_edgar_phase_a", os.path.join(PHASE_A_DIR, "fetch_edgar.py"))
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


PHASE_A = _phase_a_module()
FOREIGN = ("TSM", "BABA", "NVO")
# (ticker, CIK, name check, form): Phase A's issuers with the annual report form. Phase A
# used 10-Qs for AMZN, GOOGL and SPCX; here they contribute their 10-Ks.
ISSUERS = [(ticker, cik, name_check, "20-F" if ticker in FOREIGN else "10-K")
           for ticker, cik, name_check, _form, _year in PHASE_A.ISSUERS]


def phase_a_accessions(edgar_manifest=PHASE_A_MANIFEST, fixtures_manifest=FIXTURES_MANIFEST):
    """Every accession already in the Phase A corpus: its EDGAR filings and the fixtures."""
    with open(edgar_manifest, encoding="utf-8") as handle:
        accessions = {d["accession"] for d in json.load(handle)["documents"]}
    with open(fixtures_manifest, encoding="utf-8") as handle:
        accessions |= {f["accession"] for f in json.load(handle)["fixtures"]}
    return accessions


def overlaps(page, window):
    """Whether an older-filings page's filingFrom/filingTo range overlaps the window."""
    return page["filingFrom"] <= window[1] and page["filingTo"] >= window[0]


def submission_blocks(data, fetch_json, window):
    """The columnar filings blocks to search: "recent", then each overlapping older page."""
    blocks = [data["filings"]["recent"]]
    for page in data["filings"].get("files", []):
        if overlaps(page, window):
            blocks.append(fetch_json(SUBMISSIONS + page["name"]))
    return blocks


def _rows(blocks):
    """Each filing once (by accession) across the blocks, as a dict of the columns used."""
    seen = set()
    for block in blocks:
        for i, accession in enumerate(block["accessionNumber"]):
            if accession in seen:
                continue
            seen.add(accession)
            yield {"form": block["form"][i], "filing_date": block["filingDate"][i],
                   "report_date": block["reportDate"][i], "accession": accession,
                   "document": block["primaryDocument"][i]}


def _in_window(row, window):
    return window[0] <= row["filing_date"] <= window[1]


def _entry(ticker, cik, row, **extra):
    return {"ticker": ticker, "cik": cik, "form": row["form"], "report_date": row["report_date"],
            "filing_date": row["filing_date"], "accession": row["accession"], **extra}


def select(submissions_blocks, issuer, window, phase_a_accessions):
    """(selected, excluded) for one issuer: one annual report per report date in the window.

    Candidates are the issuer's form and its amendment (form + "/A"), filed inside the
    window (inclusive). In each report-date group the first-filed original is kept, or the
    first-filed amendment when the group holds no original (and it is marked
    `amendment: True`). The others are excluded as `amendment` (an amendment beside a kept
    original) or `same_period_newer` (a later filing of the kept kind). A kept filing whose
    accession is in Phase A is excluded as `phase_a_duplicate`, with nothing substituted.
    An issuer with no candidate in the window gets one `no_annual_report` entry.
    """
    ticker, cik, _name_check, form = issuer
    amendment_form = form + "/A"
    selected, excluded, groups = [], [], defaultdict(list)
    for row in _rows(submissions_blocks):
        if row["form"] not in (form, amendment_form):
            continue
        if not _in_window(row, window):
            excluded.append(_entry(ticker, cik, row, reason="outside_window"))
            continue
        groups[row["report_date"] or "no report date " + row["accession"]].append(row)
    if not groups:
        excluded.append({"ticker": ticker, "cik": cik, "form": form, "report_date": None,
                         "filing_date": None, "accession": None, "reason": "no_annual_report"})
    for group in groups.values():
        group.sort(key=lambda r: (r["form"] == amendment_form, r["filing_date"], r["accession"]))
        kept = group[0]
        kept_is_amendment = kept["form"] == amendment_form
        for row in group[1:]:
            later_amendment = row["form"] == amendment_form and not kept_is_amendment
            reason = "amendment" if later_amendment else "same_period_newer"
            excluded.append(_entry(ticker, cik, row, reason=reason, kept=kept["accession"]))
        if kept["accession"] in phase_a_accessions:
            excluded.append(_entry(ticker, cik, kept, reason="phase_a_duplicate"))
            continue
        url = f"{ARCHIVES}{cik}/{kept['accession'].replace('-', '')}/{kept['document']}"
        selected.append(_entry(ticker, cik, kept, url=url, amendment=kept_is_amendment))
    selected.sort(key=lambda e: (e["report_date"], e["filing_date"]))
    excluded.sort(key=lambda e: (e["filing_date"] or "", e["accession"] or ""))
    return selected, excluded


def other_annual_forms(submissions_blocks, issuer, window):
    """Filings in the window whose form starts like the annual form but is neither it nor
    its amendment (a 10-KT transition report, for example): reported, never selected."""
    ticker, cik, _name_check, form = issuer
    return [_entry(ticker, cik, row) for row in _rows(submissions_blocks)
            if row["form"].startswith(form) and row["form"] not in (form, form + "/A")
            and _in_window(row, window)]


def _with_company(entry, company):
    return {"ticker": entry["ticker"], "company": company,
            **{key: value for key, value in entry.items() if key != "ticker"}}


def primary_size(index, document, index_url):
    """The primary document's size in bytes, from the filing's index.json listing."""
    for item in index["directory"]["item"]:
        if item["name"] == document:
            size = str(item.get("size", ""))
            if not size.isdigit():
                raise ValueError(f"{index_url} gives no size for {document} ({size!r})")
            return int(size)
    raise ValueError(f"{index_url} does not list {document}")


def build_draft(issuers, fetch_json, window, phase_a):
    """The manifest draft. fetch_json(url) makes every request; only index requests are made:
    submissions JSON, the overlapping older-filings pages and each selected index.json."""
    documents, excluded, others = [], [], []
    for issuer in issuers:
        ticker, cik, name_check, form = issuer
        data = fetch_json(f"{SUBMISSIONS}CIK{cik:010d}.json")
        company = data["name"]
        if name_check.upper() not in company.upper():
            raise ValueError(f"CIK {cik} is {company!r}, expected {name_check!r}")
        blocks = submission_blocks(data, fetch_json, window)
        selected, dropped = select(blocks, issuer, window, phase_a)
        for entry in selected:
            folder, document = entry["url"].rsplit("/", 1)
            index_url = folder + "/index.json"
            size = primary_size(fetch_json(index_url), document, index_url)
            documents.append({
                "ticker": ticker, "company": company, "cik": cik, "form": entry["form"],
                "report_date": entry["report_date"], "filing_date": entry["filing_date"],
                "accession": entry["accession"], "url": entry["url"], "bytes": size,
                "amendment": entry["amendment"]})
        excluded += [_with_company(entry, company) for entry in dropped]
        others += [_with_company(entry, company)
                   for entry in other_annual_forms(blocks, issuer, window)]
        print(f"{ticker}: {form}, {len(selected)} selected, {len(dropped)} excluded,"
              f" {len(blocks) - 1} older-filings page(s) read")
    return {
        "window": {"from": window[0], "to": window[1]},
        "documents": documents,
        "excluded": excluded,
        "other_annual_forms": others,
        "totals": {"documents": len(documents), "bytes": sum(d["bytes"] for d in documents)},
    }


def file_name(entry):
    """The cache file name of a draft document: <TICKER>-<FORM>-<filing date>.htm."""
    return f"{entry['ticker']}-{entry['form']}-{entry['filing_date']}.htm"


def check_draft(documents):
    """Raise ValueError unless every entry's URL is a document in its own filing's folder
    under sec.gov Archives, and every file name is plain (no path) and unique."""
    names = set()
    for entry in documents:
        folder = f"{ARCHIVES}{entry['cik']}/{entry['accession'].replace('-', '')}/"
        document = entry["url"][len(folder):]
        if not entry["url"].startswith(folder) or not re.fullmatch(r"[\w.-]+", document):
            raise ValueError(f"{entry['url']} is not a document in {folder}")
        name = file_name(entry)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*\.htm", name):
            raise ValueError(f"{name!r} is not a plain file name (form {entry['form']!r})")
        if name in names:
            raise ValueError(f"two documents would both be saved as {name}")
        names.add(name)


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _cached(path):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def download(draft, cache, previous, fetch_bytes):
    """The manifest for the approved draft, each document fetched at most once into cache.

    previous: the documents of an existing manifest ([] if none). A file in the cache whose
    SHA-256 is the one `previous` records for the same file and accession is not fetched.
    fetch_bytes(url) makes every request, and its errors propagate: the caller stops. A new
    file is written as <name>.part and then renamed, so a stopped run leaves no partial file
    under a document's name.
    """
    check_draft(draft["documents"])
    known = {(e["file"], e["accession"]): e["sha256"] for e in previous}
    documents, mismatches, fetched = [], [], 0
    for entry in draft["documents"]:
        name = file_name(entry)
        path = os.path.join(cache, name)
        recorded = known.get((name, entry["accession"]))
        raw = _cached(path)
        if raw is not None and _sha256(raw) == recorded:
            status = "cached"
        else:
            raw = fetch_bytes(entry["url"])
            with open(path + ".part", "wb") as handle:
                handle.write(raw)
            os.replace(path + ".part", path)
            fetched += 1
            status = "downloaded"
        digest = _sha256(raw)
        notes = []
        if len(raw) != entry["bytes"]:
            mismatches.append({"file": name, "index_bytes": entry["bytes"], "bytes": len(raw)})
            notes.append(f"index.json said {entry['bytes']:,}")
        if recorded and digest != recorded:
            notes.append(f"SHA-256 differs from the previous manifest's {recorded}")
        print(f"{name}: {status}, {len(raw):,} bytes" + "".join(f"; {n}" for n in notes))
        documents.append({**entry, "bytes": len(raw), "file": name, "sha256": digest})
    manifest = {**draft, "documents": documents,
                "totals": {"documents": len(documents),
                           "bytes": sum(d["bytes"] for d in documents)},
                "size_mismatches": mismatches}
    return manifest, fetched


def _failed_url(exc):
    for part in (getattr(exc, "request", None), getattr(exc, "response", None)):
        if getattr(part, "url", None):
            return part.url
    return "(no URL)"


def _in_rcq(path):
    return os.path.abspath(path).replace("\\", "/").upper().startswith("E:/RCQWEALTH")


def _run_download(args, session):
    """The download stage: approved draft -> cache files and the manifest. Returns the exit code."""
    with open(args.draft, "rb") as handle:
        draft_raw = handle.read()
    draft = json.loads(draft_raw)
    previous = []
    if os.path.exists(args.manifest):
        with open(args.manifest, encoding="utf-8") as handle:
            previous = json.load(handle)["documents"]
    print(f"draft {args.draft}: {len(draft['documents'])} documents,"
          f" SHA-256 {_sha256(draft_raw)}; {len(previous)} in the existing manifest")
    os.makedirs(args.cache, exist_ok=True)
    session.max_redirects = 0  # a redirect raises: only the draft's own URLs are requested

    def fetch_bytes(url):
        return PHASE_A.get(session, url).content  # Phase A's 0.25 s pause, raise_for_status

    start = time.monotonic()
    try:
        manifest, fetched = download(draft, args.cache, previous, fetch_bytes)
    except requests.RequestException as exc:
        print(f"STOPPED: HTTP error at {_failed_url(exc)}: {exc}", file=sys.stderr)
        return 1
    except (ValueError, KeyError) as exc:
        print(f"STOPPED: {exc!r}", file=sys.stderr)
        return 1
    with open(args.manifest, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
        handle.write("\n")
    totals = manifest["totals"]
    print(f"{totals['documents']} documents ({fetched} downloaded,"
          f" {totals['documents'] - fetched} already cached), {totals['bytes']:,} bytes"
          f" ({totals['bytes'] / 1e6:.1f} MB) in {time.monotonic() - start:.1f} s;"
          f" {len(manifest['size_mismatches'])} size difference(s) from index.json;"
          f" manifest {args.manifest}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    stages = parser.add_subparsers(dest="stage", required=True)
    lister = stages.add_parser("list", help="index requests only; writes the manifest draft")
    lister.add_argument("--user-agent", required=True, help="never written to any file")
    lister.add_argument("--out", required=True, help="the manifest draft (JSON)")
    getter = stages.add_parser("download", help="the approved draft's documents; writes the"
                               " manifest")
    getter.add_argument("--user-agent", required=True, help="never written to any file")
    getter.add_argument("--draft", required=True, help="the manifest draft the user approved")
    getter.add_argument("--cache", required=True, help="the documents' folder")
    getter.add_argument("--manifest", required=True,
                        help="written once every document is in the cache")
    args = parser.parse_args(argv)
    if args.stage == "download":
        for path in (args.cache, args.manifest):
            if _in_rcq(path):
                parser.error(f"{path} must not be inside E:\\RCQWealth")
    elif _in_rcq(args.out):
        parser.error("the draft must not be inside E:\\RCQWealth")
    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent, "Accept-Encoding": "gzip, deflate"})
    if args.stage == "download":
        return _run_download(args, session)

    def fetch_json(url):
        return PHASE_A.get(session, url).json()  # Phase A's 0.25 s pause, raise_for_status

    try:
        draft = build_draft(ISSUERS, fetch_json, WINDOW, phase_a_accessions())
    except requests.RequestException as exc:
        print(f"STOPPED: HTTP error at {_failed_url(exc)}: {exc}", file=sys.stderr)
        return 1
    except (ValueError, KeyError) as exc:
        print(f"STOPPED: {exc!r}", file=sys.stderr)
        return 1
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(draft, handle, indent=1)
        handle.write("\n")
    totals = draft["totals"]
    print(f"{totals['documents']} documents, {totals['bytes']:,} bytes"
          f" ({totals['bytes'] / 1e6:.1f} MB); {len(draft['excluded'])} excluded;"
          f" draft {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
