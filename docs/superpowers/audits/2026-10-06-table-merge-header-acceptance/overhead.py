"""Overhead measurement: candidate vs main `Parser.get_pages(include_images=False)` on the 7 fixtures.

    python overhead.py --main-src <c674828 tree>/src --candidate-src <worktree>/src \
        --fixtures-root <checkout with tests/fixtures/sec> --runs 9 --out overhead.json

The contract (spec "Acceptance criteria", Overhead): both sides use the same settings,
normal mode and checks on (`Parser(html)` defaults: capture_tables=False, table_checks=True);
each figure is the median of at least five runs, each run a separate process; per-fixture
outliers are recorded.

Each run is one child process (`--child`) with PYTHONPATH set to one side's src. The
child decodes all 7 fixtures (identical bytes for both sides, from --fixtures-root), then
for each fixture in a fixed order builds `Parser(html)` (untimed) and times
`get_pages(include_images=False)` with time.perf_counter. Rounds alternate the side that
runs first (main, candidate / candidate, main / ...), so drift affects both sides alike.

Reported: per fixture and side, every run's time and the median; the total of the
per-fixture medians and the median of per-run totals; the ratio candidate/main for both;
and outliers (a run more than 15% from its fixture's median).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import statistics
import subprocess
import sys
import time


def child(args):
    import warnings

    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.CRITICAL)
    import sec2md
    from sec2md.encoding import decode_html
    from sec2md.parser import Parser

    paths = sorted(glob.glob(os.path.join(args.fixtures_root, "tests", "fixtures", "sec", "*.html.gz")))
    texts = []
    for path in paths:
        with gzip.open(path, "rb") as handle:
            texts.append((os.path.basename(path)[:-8], decode_html(handle.read())[0]))
    times, construct = {}, {}
    for name, html in texts:
        started = time.perf_counter()
        parser = Parser(html)
        built = time.perf_counter()
        parser.get_pages(include_images=False)
        finished = time.perf_counter()
        times[name] = finished - built
        construct[name] = built - started
        if parser.table_report is None or parser.diagnostics is None:
            raise SystemExit(f"{name}: checks did not run")
    print(json.dumps({"sec2md": sec2md.__file__, "get_pages": times, "construct": construct}))


def run_child(src, args):
    env = dict(os.environ, PYTHONPATH=src, PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", "--fixtures-root",
                             args.fixtures_root], env=env, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip().splitlines()[-1])
    expected = os.path.normcase(os.path.abspath(src))
    if not os.path.normcase(os.path.abspath(data["sec2md"])).startswith(expected):
        raise SystemExit(f"child imported {data['sec2md']}, expected under {src}")
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--fixtures-root", required=True)
    ap.add_argument("--main-src")
    ap.add_argument("--candidate-src")
    ap.add_argument("--runs", type=int, default=9)
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.child:
        child(args)
        return
    if args.runs < 5:
        raise SystemExit("the contract needs at least five runs per side")
    sides = {"main": args.main_src, "candidate": args.candidate_src}
    runs = {"main": [], "candidate": []}
    started = time.time()
    for index in range(args.runs):
        order = ("main", "candidate") if index % 2 == 0 else ("candidate", "main")
        for side in order:
            data = run_child(sides[side], args)
            runs[side].append(data)
            print(f"round {index + 1} {side}: total {sum(data['get_pages'].values()):.3f}s", file=sys.stderr, flush=True)
    fixtures = list(runs["main"][0]["get_pages"])
    per_fixture, outliers = {}, []
    for name in fixtures:
        entry = {}
        for side in sides:
            values = [r["get_pages"][name] for r in runs[side]]
            median = statistics.median(values)
            entry[side] = {"runs": [round(v, 4) for v in values], "median": round(median, 4),
                           "min": round(min(values), 4), "max": round(max(values), 4)}
            for number, value in enumerate(values, 1):
                if abs(value - median) > 0.15 * median:
                    outliers.append({"fixture": name, "side": side, "run": number, "seconds": round(value, 4),
                                     "median": round(median, 4)})
        entry["ratio"] = round(entry["candidate"]["median"] / entry["main"]["median"], 4)
        per_fixture[name] = entry
    totals = {side: [sum(r["get_pages"].values()) for r in runs[side]] for side in sides}
    sum_of_medians = {side: sum(per_fixture[n][side]["median"] for n in fixtures) for side in sides}
    median_totals = {side: statistics.median(totals[side]) for side in sides}
    result = {
        "contract": "get_pages(include_images=False), Parser(html) defaults (normal mode, checks on), "
                    f"{args.runs} runs per side, one process per run, rounds alternating the first side",
        "sec2md": {side: runs[side][0]["sec2md"] for side in sides},
        "python": sys.version,
        "per_fixture": per_fixture,
        "total_of_fixture_medians": {k: round(v, 4) for k, v in sum_of_medians.items()},
        "ratio_total_of_fixture_medians": round(sum_of_medians["candidate"] / sum_of_medians["main"], 4),
        "median_of_run_totals": {k: round(v, 4) for k, v in median_totals.items()},
        "ratio_median_of_run_totals": round(median_totals["candidate"] / median_totals["main"], 4),
        "run_totals": {side: [round(v, 4) for v in totals[side]] for side in sides},
        "construct_median_total": {side: round(sum(statistics.median(r["construct"][n] for r in runs[side])
                                                   for n in fixtures), 4) for side in sides},
        "outliers_15pct": outliers,
        "wall_seconds": round(time.time() - started, 1),
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)
    print(json.dumps({k: result[k] for k in ("total_of_fixture_medians", "ratio_total_of_fixture_medians",
                                             "median_of_run_totals", "ratio_median_of_run_totals")}, indent=1))


if __name__ == "__main__":
    main()
