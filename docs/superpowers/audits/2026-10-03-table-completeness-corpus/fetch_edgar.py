"""Fetch the EDGAR part of the Phase A corpus: one primary document per listed filing.

    python fetch_edgar.py --user-agent "Name email@example.com" --cache <dir> [--manifest <path>]

For each issuer below it reads https://data.sec.gov/submissions/CIK##########.json,
checks the company name, takes the most recent filing of the listed form filed in the
listed year, and downloads its primary document from www.sec.gov/Archives. SEC fair
access asks for a descriptive User-Agent and at most 10 requests a second; this script
sends one request at a time with a 0.25 s pause. Existing cached files are not fetched
again. The manifest (default <cache>/edgar_manifest.json) records the CIK, company name,
form, filing and report dates, accession, URL, size and SHA-256 of every document, so the
corpus can be rebuilt and checked exactly.

Keep the cache outside tracked files (for example the main checkout's ignored
outputs/ folder) and never in E:\\RCQWealth.
"""
import argparse
import hashlib
import json
import os
import time

import requests

# (ticker, CIK, name check, form, filing year). Issuer list chosen by the user on
# 2026-10-03, replacing the plan's original 16 (XOM, BRK, PFE, WMT, JNJ, PRU and HD
# dropped). TSM, BABA and NVO are foreign private issuers, so their 20-F annual reports
# are used. SPCX (SpaceX) listed in 2026 and has a 10-Q but no 10-K yet. CIKs come from
# https://www.sec.gov/files/company_tickers.json.
ISSUERS = [
    ("JPM", 19617, "JPMORGAN", "10-K", "2025"),
    ("KO", 21344, "COCA COLA", "10-K", "2025"),
    ("MSFT", 789019, "MICROSOFT", "10-K", "2025"),
    ("TSLA", 1318605, "TESLA", "10-K", "2025"),
    ("CAT", 18230, "CATERPILLAR", "10-K", "2025"),
    ("BAC", 70858, "BANK OF AMERICA", "10-K", "2025"),
    ("UNH", 731766, "UNITEDHEALTH", "10-K", "2025"),
    ("MU", 723125, "MICRON", "10-K", "2025"),
    ("NTRA", 1604821, "NATERA", "10-K", "2025"),
    ("NFLX", 1065280, "NETFLIX", "10-K", "2025"),
    ("CRM", 1108524, "SALESFORCE", "10-K", "2025"),
    ("CRDO", 1807794, "CREDO TECHNOLOGY", "10-K", "2025"),
    ("TSM", 1046179, "TAIWAN SEMICONDUCTOR", "20-F", "2025"),
    ("BABA", 1577552, "ALIBABA", "20-F", "2025"),
    ("NVO", 353278, "NOVO NORDISK", "20-F", "2025"),
    ("AMZN", 1018724, "AMAZON", "10-Q", "2025"),
    ("GOOGL", 1652044, "ALPHABET", "10-Q", "2025"),
    ("SPCX", 1181412, "SPACE EXPLORATION", "10-Q", "2026"),
]
PAUSE = 0.25


def get(session, url):
    time.sleep(PAUSE)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response


def _match(data, filings, cik, form, year):
    """The most recent filing of form filed in year in one columnar filings block, or None."""
    for i, filed_form in enumerate(filings["form"]):
        if filed_form == form and filings["filingDate"][i].startswith(year):
            accession = filings["accessionNumber"][i]
            document = filings["primaryDocument"][i]
            return {
                "company": data["name"], "cik": cik, "form": form,
                "filing_date": filings["filingDate"][i], "report_date": filings["reportDate"][i],
                "accession": accession,
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{document}",
            }
    return None


def resolve(session, cik, name_check, form, year):
    data = get(session, f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
    if name_check.upper() not in data["name"].upper():
        raise ValueError(f"CIK {cik} is {data['name']!r}, expected {name_check!r}")
    entry = _match(data, data["filings"]["recent"], cik, form, year)
    if entry:
        return entry
    # Frequent filers (banks issuing structured notes) push older filings out of "recent";
    # SEC lists the rest in extra pages with the same columns. Read only pages whose date
    # range covers the year, newest first.
    for page in data["filings"].get("files", []):
        if not (page.get("filingFrom", "") <= f"{year}-12-31" and page.get("filingTo", "") >= f"{year}-01-01"):
            continue
        older = get(session, f"https://data.sec.gov/submissions/{page['name']}").json()
        entry = _match(data, older, cik, form, year)
        if entry:
            return entry
    raise ValueError(f"CIK {cik} has no {form} filed in {year} in its filings")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()
    if os.path.abspath(args.cache).replace("\\", "/").upper().startswith("E:/RCQWEALTH"):
        parser.error("the cache must not be inside E:\\RCQWealth")
    os.makedirs(args.cache, exist_ok=True)
    manifest_path = args.manifest or os.path.join(args.cache, "edgar_manifest.json")
    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent, "Accept-Encoding": "gzip, deflate"})
    entries, failures = [], []
    for ticker, cik, name_check, form, year in ISSUERS:
        try:
            entry = resolve(session, cik, name_check, form, year)
            path = os.path.join(args.cache, f"{ticker}-{form}-{entry['filing_date']}.htm")
            if not os.path.exists(path):
                with open(path, "wb") as handle:
                    handle.write(get(session, entry["url"]).content)
            with open(path, "rb") as handle:
                raw = handle.read()
            entry.update(file=os.path.basename(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            entries.append(entry)
            print(f"{ticker}: {entry['form']} filed {entry['filing_date']}, {len(raw):,} bytes")
        except (requests.RequestException, ValueError, KeyError) as exc:
            failures.append(f"{ticker}: {exc}")
            print(f"{ticker}: FAILED {exc}")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump({"documents": entries, "failures": failures}, handle, indent=1)
    print(f"{len(entries)} fetched, {len(failures)} failed; manifest {manifest_path}")


if __name__ == "__main__":
    main()
