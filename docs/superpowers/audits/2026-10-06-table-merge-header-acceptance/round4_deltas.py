"""Deltas between an earlier round's result files and the current ones (research only).

    python round4_deltas.py --out round4_deltas.json                      # round 3 -> round 4
    python round4_deltas.py --previous round4 --out round5_deltas.json    # round 4 -> round 5

Compares this folder's earlier result files (`<previous>-*`, default `round3`) with the current
ones (unprefixed):
which files are identical, every changed leaf of `summary.json`, the alignment coverage and
transitions, the retention counts, and the moved rows and the rows leaving main's header
line that appear or disappear, by (document, unit, row).
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("summary.json", "check1.json", "findings.json", "strict.json", "sections.json", "xlsx.json",
         "xlsx_detail.json", "modes.json", "alignment.json", "alignment_losses.json", "header_departures.json",
         "assignment.json", "retention.json", "class8.json", "limitations.json", "moved_rows.json",
         "shifted_tables.json", "run_check.json")
TIMING = ("seconds", "wall", "elapsed")


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        return json.load(handle)


def leaves(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, f"{path}/{key}")
    elif isinstance(value, list) and not any(isinstance(item, (dict, list)) for item in value):
        yield path, value
    elif isinstance(value, list):
        yield path + " (length)", len(value)
    else:
        yield path, value


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous", default="round3", help="prefix of the earlier round's result files")
    args = ap.parse_args()
    prefix = args.previous + "-"

    files = {}
    for name in FILES:
        if not os.path.exists(os.path.join(HERE, prefix + name)):
            files[name] = "no earlier file"
            continue
        old, new = read(prefix + name), read(name)
        same = old == new
        if not same:
            changed = [p for p, v in leaves(new) if dict(leaves(old)).get(p) != v]
            same = "timing only" if all(any(t in p for t in TIMING) for p in changed) else False
        files[name] = "identical" if same is True else (same or "differs")

    old_summary, new_summary = dict(leaves(read(prefix + "summary.json"))), dict(leaves(read("summary.json")))
    summary = {p: [old_summary.get(p), v] for p, v in new_summary.items() if old_summary.get(p) != v}

    old_al, new_al = read(prefix + "alignment.json"), read("alignment.json")
    coverage = {side: {k: [old_al["coverage"][side][k], v] for k, v in new_al["coverage"][side].items()
                       if old_al["coverage"][side][k] != v} for side in ("main", "candidate")}
    old_tr = {(a, b): n for a, b, n in old_al["transitions"]}
    new_tr = {(a, b): n for a, b, n in new_al["transitions"]}
    transitions = {f"{a} -> {b}": [old_tr.get((a, b), 0), new_tr.get((a, b), 0)]
                   for a, b in sorted(set(old_tr) | set(new_tr)) if old_tr.get((a, b), 0) != new_tr.get((a, b), 0)}

    old_ret, new_ret = read(prefix + "retention.json"), read("retention.json")
    retention = {k: [old_ret[k], v] for k, v in new_ret.items()
                 if not isinstance(v, list) and old_ret.get(k) != v}

    def keyed(items):
        return {(m["doc"], m["unit"], m["row"]): m for m in items}

    moved_old, moved_new = keyed(read(prefix + "moved_rows.json")["rows_list"]), keyed(read("moved_rows.json")["rows_list"])
    dep_old = keyed(read(prefix + "header_departures.json")["rows_list"])
    dep_new = keyed(read("header_departures.json")["rows_list"])

    def brief(m):
        return {"doc": m["doc"], "unit": m["unit"], "row": m["row"], "texts": m["texts"][:5],
                **({"reasons": m["reasons"], "signals": m["signals"]} if "reasons" in m else {})}

    out = {
        "files": files,
        "summary_changes": summary,
        "alignment_coverage_changes": coverage,
        "alignment_transition_changes": transitions,
        "retention_changes": retention,
        "moved_rows_new": [brief(moved_new[k]) for k in sorted(set(moved_new) - set(moved_old))],
        "moved_rows_gone": [brief(moved_old[k]) for k in sorted(set(moved_old) - set(moved_new))],
        "departures_new": [brief(dep_new[k]) for k in sorted(set(dep_new) - set(dep_old))],
        "departures_gone": [brief(dep_old[k]) for k in sorted(set(dep_old) - set(dep_new))],
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
