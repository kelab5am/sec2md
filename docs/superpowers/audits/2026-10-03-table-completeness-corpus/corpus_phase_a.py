"""Phase A corpus run for the table completeness checks, with the D3 word measurement.

Run from an implementation checkout root, with that checkout importable:

    python <this folder>/corpus_phase_a.py --out <results.json> [--edgar-cache <dir>] [--no-rcq]
    python <this folder>/corpus_phase_a.py --inspect <document id> <table ordinal> [--edgar-cache <dir>]

Documents, deduplicated by content hash:

- fixture:<name>       the 7 offline fixtures in tests/fixtures/sec
- rcq:<file>           every primary 10-K and 10-Q in E:\\RCQWealth (META, RDDT, NVDA), read-only,
                       except filings that are already fixtures (same accession)
- rcq-exhibit:<file>   RCQ exhibit documents holding at least two tables
- edgar:<file>         filings fetched by fetch_edgar.py into --edgar-cache

For every document it runs `Parser(html).get_pages()` in normal and capture mode and
records each table's check 1 and check 2 findings, and whether the two modes agree.
For D3 it compares each table's source words (letters only, two or more, lowercased,
taken from the same visible cell text check 1 uses) with the words of its output
segment, and records the words that are missing. The printed summary is what the spec's
Phase A record needs; --inspect shows one table's source rows and output for review.
"""
import argparse
import glob
import gzip
import hashlib
import json
import os
import re
import sys
import warnings
from collections import Counter

warnings.filterwarnings("ignore")

from sec2md.encoding import decode_html  # noqa: E402
from sec2md.parser import Parser  # noqa: E402
from sec2md.quality import _MARKDOWN_LINK_RE  # noqa: E402
from sec2md.table_completeness import _direct_cells, cell_text, hidden_sets, unit_rows  # noqa: E402

RCQ = "E:/RCQWealth"
_WORD = re.compile(r"[a-z]{2,}")


def fixture_accessions():
    with open("tests/fixtures/sec/manifest.json", encoding="utf-8") as handle:
        fixtures = json.load(handle)["fixtures"]
    items = fixtures.values() if isinstance(fixtures, dict) else fixtures
    return {re.sub(r"\D", "", item["accession"]) for item in items}


def documents(edgar_cache, include_rcq):
    """(id, group, raw bytes) for every corpus document, first occurrence of each filing and hash only."""
    found, skipped = [], []
    fixtures = fixture_accessions()
    for path in sorted(glob.glob("tests/fixtures/sec/*.html.gz")):
        with gzip.open(path, "rb") as handle:
            found.append((f"fixture:{os.path.basename(path)[:-8]}", "fixture", handle.read()))
    if include_rcq:
        for company in ("META", "RDDT", "NVDA"):
            for path in sorted(glob.glob(f"{RCQ}/{company}/Originals/SEC/*/*.htm")):
                accession = re.search(r"__s-(\d{18})", path)
                if accession and accession.group(1) in fixtures:
                    skipped.append(f"rcq:{os.path.basename(path)} (same filing as a fixture)")
                    continue
                with open(path, "rb") as handle:
                    found.append((f"rcq:{os.path.basename(path)}", "rcq", handle.read()))
            for path in sorted(glob.glob(f"{RCQ}/{company}/Originals/SEC/*/*.assets/*.htm*")):
                with open(path, "rb") as handle:
                    raw = handle.read()
                if len(re.findall(rb"<table", raw, re.I)) >= 2:
                    name = f"{os.path.basename(os.path.dirname(path))[:-7]}/{os.path.basename(path)}"
                    found.append((f"rcq-exhibit:{name}", "rcq-exhibit", raw))
    if edgar_cache:
        for path in sorted(glob.glob(os.path.join(edgar_cache, "*.htm"))):
            with open(path, "rb") as handle:
                found.append((f"edgar:{os.path.basename(path)}", "edgar", handle.read()))
    seen, unique, duplicates = set(), [], skipped
    for doc_id, group, raw in found:
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen:
            duplicates.append(doc_id)
            continue
        seen.add(digest)
        unique.append((doc_id, group, raw))
    return unique, duplicates


def parse(html, capture):
    parser = Parser(html, capture_tables=capture)
    parser.get_pages(include_images=False)
    return parser


def finding_record(finding):
    return {
        "table": finding.ordinal, "snapshot": finding.snapshot_ordinal, "page": finding.page,
        "missing_values": [list(v) for v in finding.missing_values],
        "missing_reported": [list(r) for r in finding.missing_reported],
        "structure": list(finding.structure),
        "produced_output": finding.produced_output,
    }


def table_units(parser):
    """(ordinal, table, hidden ids) in check_tables' order."""
    outermost, hidden, _ = hidden_sets(parser.soup)
    units = [t for t in outermost if id(t) not in hidden]
    return [(ordinal, table) for ordinal, table in enumerate(units, 1)], hidden


def source_rows(table, hidden):
    rows = [row for row in unit_rows(table) if id(row.tr) not in hidden]
    return [[cell_text(c, hidden) for c in _direct_cells(row.tr) if id(c) not in hidden] for row in rows]


def word_losses(parser):
    """{ordinal: (source word count, missing words Counter)} for tables that lost words."""
    units, hidden = table_units(parser)
    losses = {}
    for ordinal, table in units:
        source = Counter(w for row in source_rows(table, hidden) for value, _ in row
                         for w in _WORD.findall(value.lower()))
        if not source:
            continue
        segment = _MARKDOWN_LINK_RE.sub(lambda m: m.group(1), parser.table_outputs.get(id(table), ""))
        missing = source - Counter(_WORD.findall(segment.lower()))
        if missing:
            losses[ordinal] = (sum(source.values()), missing)
    return losses


def run(args):
    docs, duplicates = documents(args.edgar_cache, not args.no_rcq)
    results, mode_mismatches = [], 0
    for doc_id, group, raw in docs:
        html = decode_html(raw)[0]
        normal = parse(html, capture=False)
        capture = parse(html, capture=True)
        normal_findings = [finding_record(f) for f in normal.table_report.findings]
        capture_findings = [finding_record(f) for f in capture.table_report.findings]
        strip = lambda records: [{k: v for k, v in r.items() if k != "snapshot"} for r in records]  # noqa: E731
        disagree = strip(normal_findings) != strip(capture_findings)
        mode_mismatches += disagree
        value_tables = {f["table"] for f in normal_findings if f["missing_values"]}
        words = word_losses(normal)
        results.append({
            "id": doc_id, "group": group, "sha256": hashlib.sha256(raw).hexdigest(),
            "tables_checked": normal.table_report.tables_checked,
            "findings": normal_findings, "modes_disagree": disagree,
            "word_losses": [{"table": o, "source_words": n, "missing": dict(m.most_common()),
                             "check1_value_failure": o in value_tables}
                            for o, (n, m) in sorted(words.items())],
        })
        print(f"{doc_id}: {normal.table_report.tables_checked} tables, "
              f"{sum(1 for f in normal_findings if f['missing_values'])} with value failures"
              f"{', MODES DISAGREE' if disagree else ''}", file=sys.stderr)

    summary = summarize(results, duplicates, mode_mismatches)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "documents": results}, handle, indent=1)
    print(json.dumps(summary, indent=1))


def summarize(results, duplicates, mode_mismatches):
    groups = Counter(r["group"] for r in results)
    findings = [(r["id"], f) for r in results for f in r["findings"]]
    word_tables = [(r["id"], w) for r in results for w in r["word_losses"]]
    only_words = [(d, w) for d, w in word_tables if not w["check1_value_failure"]]
    return {
        "documents": dict(groups), "documents_total": len(results), "duplicates_skipped": duplicates,
        "tables_checked": sum(r["tables_checked"] for r in results),
        "check1_value_tables": sum(1 for _, f in findings if f["missing_values"]),
        "check1_value_tokens": sum(len(f["missing_values"]) for _, f in findings),
        "check1_value_tokens_by_role": dict(Counter(v[1] for _, f in findings for v in f["missing_values"])),
        "check1_ambiguous_tokens": sum(1 for _, f in findings for v in f["missing_values"] if v[2]),
        "check1_reported_tokens_by_class": dict(Counter(r[1] for _, f in findings for r in f["missing_reported"])),
        "check2_tables": sum(1 for _, f in findings if f["structure"]),
        "tables_without_output": sum(1 for _, f in findings if not f["produced_output"]),
        "documents_with_value_failures": sum(1 for r in results if any(f["missing_values"] for f in r["findings"])),
        "mode_mismatched_documents": mode_mismatches,
        "d3_tables_with_word_losses": len(word_tables),
        "d3_tables_with_word_losses_and_no_check1_failure": len(only_words),
        "d3_missing_words_total": sum(sum(w["missing"].values()) for _, w in word_tables),
        "d3_top_missing_words": _top_words(word_tables),
    }


def _top_words(word_tables):
    total = Counter()
    for _, w in word_tables:
        total.update(w["missing"])
    return total.most_common(25)


def inspect(args):
    docs, _ = documents(args.edgar_cache, include_rcq=True)
    doc_id, ordinal = args.inspect[0], int(args.inspect[1])
    raw = next(raw for d, _, raw in docs if d == doc_id)
    parser = parse(decode_html(raw)[0], capture=False)
    units, hidden = table_units(parser)
    table = dict(units)[ordinal]
    print(f"== {doc_id} table {ordinal}")
    for finding in parser.table_report.findings:
        if finding.ordinal == ordinal:
            for message in finding.messages():
                print(f"   finding: {message}")
    print("-- source rows (value [marker])")
    for row in source_rows(table, hidden):
        print("   | " + " | ".join(v + (f" [{m}]" if m else "") for v, m in row) + " |")
    print("-- output segment")
    print(parser.table_outputs.get(id(table), "(no output)"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out")
    parser.add_argument("--edgar-cache")
    parser.add_argument("--no-rcq", action="store_true")
    parser.add_argument("--inspect", nargs=2, metavar=("DOCUMENT", "TABLE"))
    args = parser.parse_args()
    if args.inspect:
        inspect(args)
    elif args.out:
        run(args)
    else:
        parser.error("pass --out or --inspect")


if __name__ == "__main__":
    main()
