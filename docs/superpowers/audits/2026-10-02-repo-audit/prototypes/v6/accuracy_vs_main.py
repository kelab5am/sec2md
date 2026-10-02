"""Accuracy-suite scores and output hashes of an implementation checkout against an unchanged baseline.

Each side runs the accuracy suite's `audit_document()` on the 7 fixtures in its own Python
process, with only its own `src` and `tests` importable:

    python accuracy_vs_main.py --baseline <main checkout> --candidate <implementation checkout>

Both paths are checkout roots. For each fixture it prints word, numeric and
financial-row recall on both sides, the fixture's pass marks, and whether the Markdown
and page hashes are the same. The table completeness checks only report, so every score
must be unchanged and every hash the same; the script exits with status 1 otherwise.
"""
import argparse
import json
import os
import subprocess
import sys

WORKER = r"""
import json, warnings
warnings.filterwarnings("ignore")
from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture
from tests.accuracy.metrics import audit_document
out = {}
for fixture_id in FIXTURE_IDS:
    contract, source = load_fixture(fixture_id)
    result = audit_document(source, contract)
    out[fixture_id] = {
        "word": result.word_recall, "numeric": result.numeric_recall,
        "financial_rows": result.financial_row_recall,
        "markdown": result.markdown_sha256, "pages": result.pages_sha256,
        "floors": [contract.min_word_recall, contract.min_numeric_recall, contract.min_financial_row_recall],
    }
print(json.dumps(out))
"""


def run_side(checkout):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.path.join(checkout, "src"), checkout]),
               PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", WORKER], cwd=checkout, env=env,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    base, cand = run_side(args.baseline), run_side(args.candidate)
    if set(base) != set(cand):
        sys.exit(f"fixture sets differ: {sorted(base)} vs {sorted(cand)}")

    def pair(name, metric):
        return f"{100 * base[name][metric]:.2f} -> {100 * cand[name][metric]:.2f}"

    print(f"{'fixture':20s} {'words':>17s} {'numbers':>17s} {'financial rows':>17s}  "
          f"{'pass marks':>12s}  markdown  pages")
    differences = 0
    for name in base:
        same_md = base[name]["markdown"] == cand[name]["markdown"]
        same_pages = base[name]["pages"] == cand[name]["pages"]
        scores_same = all(base[name][m] == cand[name][m] for m in ("word", "numeric", "financial_rows"))
        differences += not (same_md and same_pages and scores_same)
        marks = "/".join(f"{100 * v:.0f}" for v in base[name]["floors"])
        print(f"{name:20s} {pair(name, 'word'):>17s} {pair(name, 'numeric'):>17s} "
              f"{pair(name, 'financial_rows'):>17s}  {marks:>12s}  {'same' if same_md else 'DIFF':8s}  "
              f"{'same' if same_pages else 'DIFF'}")
    print(f"fixtures {len(base)}: {differences} with a changed score or hash")
    sys.exit(1 if differences else 0)


if __name__ == "__main__":
    main()
