"""Round 2 -> round 3 deltas for the S7 and S8 cases and the moved rows (research only).

    python round3_deltas.py --analysis-dir <s>/analysis --out round3_deltas.json

Reads this folder's round-2 results (`round2-header_departures.json`, `round2-moved_rows.json`)
and round-3 results (`header_departures.json`, `moved_rows.json`), and the round-3 analysis
dumps for each unit's header rows (the candidate checker's R0 roles, `header_row_list`).

- **S8:** round 2's rows with value-column text that left main's header line (82 rows in 80
  tables): for each, whether round 3's candidate has it in the header zone again or still
  leaves it in the body; and round 3's remaining rows leaving main's header line.
- **S7:** round 2's zone cuts by a label-only row with value-column rows below it (11
  tables): round 3's header zone of each, and whether those rows are now header rows.
- **Moved rows:** rows moved in round 3 but not round 2 and the reverse, by
  (document, unit, row), with the round-3 reasons of the new ones.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        return json.load(handle)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--analysis-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    dep2, dep3 = read("round2-header_departures.json"), read("header_departures.json")
    mov2, mov3 = read("round2-moved_rows.json"), read("moved_rows.json")
    header_rows: dict[tuple[str, int], set[int]] = {}

    def zone(doc, unit):
        if (doc, unit) not in header_rows:
            an = acc_common.read_json_gz(os.path.join(args.analysis_dir, acc_common.safe_name(doc)))
            for u in an["units"]:
                header_rows[(doc, u["unit"])] = set(u.get("header_row_list") or ())
        return header_rows.get((doc, unit), set())

    def key(item):
        return (item["doc"], item["unit"], item["row"])

    # S8: round 2's non-data rows with value-column text that left main's header line.
    s8_rows = [d for d in dep2["rows_list"] if not d["data_row"] and not d["label_only"]]
    still = {key(d) for d in dep3["rows_list"]}
    s8 = []
    for d in s8_rows:
        status = "header" if d["row"] in zone(d["doc"], d["unit"]) else (
            "still_departing" if key(d) in still else "body_not_listed")
        s8.append({**{k: d[k] for k in ("doc", "unit", "row", "texts")}, "status": status})
    s8_counts = Counter(item["status"] for item in s8)

    # Round 3's remaining departures (non-data rows with value-column text).
    remaining = [d for d in dep3["rows_list"] if not d["data_row"] and not d["label_only"]]
    remaining_label_only = [d for d in dep3["rows_list"] if not d["data_row"] and d["label_only"]]

    # S7: round 2's zone cuts by a label-only row with value-column rows below it.
    s7 = []
    for cut in dep2["stacked_title_list"]:
        rows = zone(cut["doc"], cut["unit"])
        s7.append({"doc": cut["doc"], "unit": cut["unit"], "round2_header_rows": cut["header_rows"],
                   "round3_header_rows": sorted(rows), "value_text_rows": cut["value_text_rows_after"],
                   "value_text_rows_in_header": all(r in rows for r in cut["value_text_rows_after"]),
                   "rows": cut["rows"]})

    # Moved rows.
    moved2 = {key(m): m for m in mov2["rows_list"]}
    moved3 = {key(m): m for m in mov3["rows_list"]}
    new = [moved3[k] for k in sorted(set(moved3) - set(moved2))]
    gone = [moved2[k] for k in sorted(set(moved2) - set(moved3))]

    def tables(items):
        return len({(m["doc"], m["unit"]) for m in items})

    def why(m):
        if m["first_header_row"]:
            return "first_header_row"
        if "label_only" in m["reasons"]:
            return "label_only"
        if m.get("sparse_row_fusion_only"):
            return "sparse_row_fusion_only"
        return "other:" + "+".join(m["reasons"])

    out = {
        "s8": {"round2_rows": len(s8_rows), "round2_tables": tables(s8_rows), "status_rows": dict(s8_counts),
               "status_tables": {s: tables([i for i in s8 if i["status"] == s]) for s in s8_counts},
               "rows_list": s8},
        "remaining_departures": {"non_data_with_value_text_rows": len(remaining),
                                 "non_data_with_value_text_tables": tables(remaining),
                                 "non_data_label_only_rows": len(remaining_label_only),
                                 "rows_list": remaining, "label_only_list": remaining_label_only},
        "s7": {"round2_tables": len(s7), "value_text_rows_in_header": sum(i["value_text_rows_in_header"] for i in s7),
               "tables": s7},
        "moved_rows": {"round2_rows": len(moved2), "round3_rows": len(moved3),
                       "new_rows": len(new), "new_tables": tables(new),
                       "new_by_cause": dict(Counter(why(m) for m in new)),
                       "new_fixture_rows": sum(m["doc"].startswith("fixture:") for m in new),
                       "gone_rows": len(gone), "gone_tables": tables(gone),
                       "new_list": new, "gone_list": gone},
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=1)
    printed = {k: {kk: vv for kk, vv in v.items() if not kk.endswith("_list") and kk not in ("tables",)}
               for k, v in out.items()}
    print(json.dumps(printed, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
