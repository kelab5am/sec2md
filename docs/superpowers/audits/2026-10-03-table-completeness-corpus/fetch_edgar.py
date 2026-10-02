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

# (ticker, CIK, name check, form, filing year). Chosen for layout variety: banks and an
# insurer, energy, industrials, consumer, pharma, technology, and several filing agents.
ISSUERS = [
    ("JPM", 19617, "JPMORGAN", "10-K", "2025"),
    ("XOM", 34088, "EXXON", "10-K", "2025"),
    ("BRK", 1067983, "BERKSHIRE", "10-K", "2025"),
    ("KO", 21344, "COCA COLA", "10-K", "2025"),
    ("PFE", 78003, "PFIZER", "10-K", "2025"),
    ("WMT", 104169, "WALMART", "10-K", "2025"),
    ("MSFT", 789019, "MICROSOFT", "10-K", "2025"),
    ("TSLA", 1318605, "TESLA", "10-K", "2025"),
    ("JNJ", 200406, "JOHNSON & JOHNSON", "10-K", "2025"),
    ("CAT", 18230, "CATERPILLAR", "10-K", "2025"),
    ("PRU", 1137774, "PRUDENTIAL FINANCIAL", "10-K", "2025"),
    ("BAC", 70858, "BANK OF AMERICA", "10-K", "2025"),
    ("HD", 354950, "HOME DEPOT", "10-K", "2025"),
    ("UNH", 731766, "UNITEDHEALTH", "10-K", "2025"),
    ("AMZN", 1018724, "AMAZON", "10-Q", "2025"),
    ("GOOGL", 1652044, "ALPHABET", "10-Q", "2025"),
]
PAUSE = 0.25


def get(session, url):
    time.sleep(PAUSE)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response


def resolve(session, cik, name_check, form, year):
    data = get(session, f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
    if name_check.upper() not in data["name"].upper():
        raise ValueError(f"CIK {cik} is {data['name']!r}, expected {name_check!r}")
    recent = data["filings"]["recent"]
    for i, filed_form in enumerate(recent["form"]):
        if filed_form == form and recent["filingDate"][i].startswith(year):
            accession = recent["accessionNumber"][i]
            document = recent["primaryDocument"][i]
            return {
                "company": data["name"], "cik": cik, "form": form,
                "filing_date": recent["filingDate"][i], "report_date": recent["reportDate"][i],
                "accession": accession,
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{document}",
            }
    raise ValueError(f"CIK {cik} has no {form} filed in {year} in its recent filings")


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
