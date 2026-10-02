"""Check an implementation of the table completeness spec against this prototype.

Reports two things:

- finding parity: per-table check 1 and check 2 results of `Parser.table_report`
  against `completeness_v6.analyze`, in normal and capture mode
- header-row parity: `table_completeness.header_row_count` against the header rows
  of the snapshot the XLSX path builds for the same table

Parse-time overhead is measured separately, against an unchanged baseline checkout,
by `overhead_vs_main.py` in this folder.

Run from the implementation checkout root, with that checkout importable:

    python <this folder>/parity_impl.py <this folder> [--fixtures-only]

Without --fixtures-only it also reads the 20 META and RDDT filings in E:\\RCQWealth
(read-only). Expected: "finding mismatches 0, header-row mismatches 0".
"""
import glob
import gzip
import importlib.util
import os
import sys
import warnings

warnings.filterwarnings("ignore")
spec = importlib.util.spec_from_file_location("completeness_v6", os.path.join(sys.argv[1], "completeness_v6.py"))
v6 = importlib.util.module_from_spec(spec)
sys.modules["completeness_v6"] = v6
spec.loader.exec_module(v6)

from sec2md.encoding import decode_html  # noqa: E402
from sec2md.parser import Parser  # noqa: E402
from sec2md.table_completeness import header_row_count, hidden_sets, unit_rows  # noqa: E402

FIXTURES = ["aapl-2023-10k", "nvda-2026-10k", "nvda-2002-10k", "nvda-2026-q2-10q",
            "nvda-2026-08-26-8k", "nvda-2026-ex99-1", "nvda-2026-ex99-2"]
# The prototype labels a row-order finding "(rows out of order)"; the implementation does not.
PROTOTYPE_SUFFIX = " (rows out of order)"


def load_documents(include_rcq):
    docs = []
    for name in FIXTURES:
        with gzip.open(f"tests/fixtures/sec/{name}.html.gz", "rb") as handle:
            docs.append((name, decode_html(handle.read())[0]))
    if include_rcq:
        for company in ("META", "RDDT"):
            for path in sorted(glob.glob(f"E:/RCQWealth/{company}/Originals/SEC/*/*.htm")):
                with open(path, "rb") as handle:
                    docs.append((os.path.basename(path)[:26], decode_html(handle.read())[0]))
    return docs


def implementation(html, capture):
    parser = Parser(html, capture_tables=capture)
    parser.get_pages(include_images=False)
    return {f.ordinal: (sorted(f.missing_values), len(f.missing_reported), list(f.structure))
            for f in parser.table_report.findings}


def prototype(html, capture):
    out = {}
    for result in v6.analyze(html, capture=capture):
        values = sorted((t[0], t[1], len(t) == 3) for t in result.missing_tokens)
        structure = [s.replace(PROTOTYPE_SUFFIX, "") for s in result.order]
        if values or result.reported or structure:
            out[result.ordinal] = (values, sum(result.reported.values()), structure)
    return out


def header_mismatches(html):
    parser = Parser(html, capture_tables=True)
    parser.get_pages(include_images=False)
    snapshots = {id(nodes[0]): snapshot for snapshot, nodes in zip(parser.table_snapshots, parser._snapshot_nodes)
                 if len(nodes) == 1}
    _, hidden, grid_hidden = hidden_sets(parser.soup)
    count = 0
    for table in parser.soup.find_all("table"):
        if id(table) in hidden or table.find_parent("table") is not None or id(table) not in snapshots:
            continue
        if header_row_count(table, unit_rows(table), grid_hidden) != v6._header_rows(snapshots[id(table)]):
            count += 1
    return count


def main():
    docs = load_documents(include_rcq="--fixtures-only" not in sys.argv)
    mismatches = headers = 0
    for name, html in docs:
        for capture in (False, True):
            actual, expected = implementation(html, capture), prototype(html, capture)
            for ordinal in sorted(set(actual) | set(expected)):
                if actual.get(ordinal) != expected.get(ordinal):
                    mismatches += 1
                    print(f"MISMATCH {name} capture={capture} table {ordinal}: "
                          f"implementation={actual.get(ordinal)} prototype={expected.get(ordinal)}")
        headers += header_mismatches(html)
    print(f"documents {len(docs)}: finding mismatches {mismatches}, header-row mismatches {headers}")


if __name__ == "__main__":
    main()
