"""Parse-time overhead of an implementation checkout against an unchanged baseline checkout.

Each side runs in its own Python process with only its own `src` importable, so the
baseline is the code as it was before the feature, not the feature with its checks
switched off. Sides alternate within each round to spread machine drift evenly.

    python overhead_vs_main.py --baseline <main checkout> --candidate <implementation checkout>
        [--rounds 3] [--repeats 5]

Both paths are checkout roots (the folders holding `src/` and `tests/fixtures/sec/`).
Each process times `Parser(html).get_pages()` (the default configuration of
`convert_to_markdown()`) `--repeats` times after one warm-up run and reports the best;
each side's figure is its best over all rounds. The spec's target is at most +10% on the
fixtures, per fixture and in total.
"""
import argparse
import json
import os
import subprocess
import sys

FIXTURES = ["aapl-2023-10k", "nvda-2026-10k", "nvda-2002-10k", "nvda-2026-q2-10q",
            "nvda-2026-08-26-8k", "nvda-2026-ex99-1", "nvda-2026-ex99-2"]

WORKER = r"""
import gzip, json, sys, time, warnings
warnings.filterwarnings("ignore")
from sec2md.encoding import decode_html
from sec2md.parser import Parser
root, repeats = sys.argv[1], int(sys.argv[2])
best = {}
for name in sys.argv[3:]:
    with gzip.open(f"{root}/tests/fixtures/sec/{name}.html.gz", "rb") as handle:
        html = decode_html(handle.read())[0]
    Parser(html).get_pages()
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        Parser(html).get_pages()
        times.append(time.perf_counter() - start)
    best[name] = min(times)
print(json.dumps(best))
"""


def run_side(checkout, repeats):
    env = dict(os.environ, PYTHONPATH=os.path.join(checkout, "src"), PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", WORKER, checkout, str(repeats), *FIXTURES],
                         env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    best = {"baseline": {}, "candidate": {}}
    for round_number in range(args.rounds):
        order = ("baseline", "candidate") if round_number % 2 == 0 else ("candidate", "baseline")
        for side in order:
            for name, seconds in run_side(getattr(args, side), args.repeats).items():
                best[side][name] = min(seconds, best[side].get(name, float("inf")))
    for name in FIXTURES:
        base, cand = best["baseline"][name], best["candidate"][name]
        print(f"{name:20s} baseline {base:6.3f}s  candidate {cand:6.3f}s  ({100 * (cand / base - 1):+.1f}%)")
    base_total, cand_total = sum(best["baseline"].values()), sum(best["candidate"].values())
    print(f"{'total':20s} baseline {base_total:6.3f}s  candidate {cand_total:6.3f}s  "
          f"({100 * (cand_total / base_total - 1):+.1f}%)")


if __name__ == "__main__":
    main()
