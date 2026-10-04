"""Summarize events.json into the figures REPORT.md quotes (research only).

    python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/summarize.py \
        --events docs/superpowers/audits/2026-10-04-table-merge-header-evidence/events.json [--examples]

Reads events.json (from measure.py), the Phase A results.json and classification.md
(cause keys G1-G5, F1-F8 per table), and prints per-class counts, overlaps, the mapping
to Phase A check-1 findings, fixture tables per class and, with --examples, the smallest
candidate examples per class. Prints only; writes nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus import CLASSIFICATION, RESULTS  # noqa: E402


def parse_classification(path):
    """{(doc id, table): cause key} from classification.md's per-table rows."""
    causes = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("| edgar:") and not line.startswith("| rcq"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            doc, tables, cause = cells[0], cells[1], cells[-1]
            key = re.search(r"\b([GF]\d)\b", cause)
            key = key.group(1) if key else "?"
            spec = tables.split(" (")[0]
            for part in spec.split(","):
                part = part.strip()
                m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
                if not m:
                    continue
                lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
                for n in range(lo, hi + 1):
                    causes[(doc, n)] = key
    return causes


def class_tables(entry):
    """The set of event classes one TableParser table shows (the report's class keys)."""
    ev = entry.get("events", {})
    out = set()
    if "c1" in ev:
        out.add("1")
        if any(d["row0_header"] for d in ev["c1"]):
            out.add("1h")
        if any(not d["row0_header"] for d in ev["c1"]):
            out.add("1d")
        if any(not d["row0_header"] and d["row0_has_amount"] for d in ev["c1"]):
            out.add("1d_amount")
    if "c2" in ev:
        out.add("2")
    if "c2_noheader" in ev:
        out.add("2?")
    if "c2_text" in ev:
        out.add("2t")
    if any(a["status"] in ("shifted", "detached") for a in ev.get("c3", [])):
        out.add("3")
    if any(a["status"] == "shifted" for a in ev.get("c3", [])):
        out.add("3s")
    if any(a["status"] in ("shifted", "detached") for a in ev.get("c3_empty", [])):
        out.add("3e")
    if any(a["status"] == "shifted" for a in ev.get("c3_empty", [])):
        out.add("3es")
    if "misaligned" in ev:
        out.add("M")
    if any(a["status"] == "shifted" for a in ev.get("misaligned", [])):
        out.add("Ms")
    if "c4" in ev:
        out.add("4")
    if any(set(c["markers"]) == {"$"} and c["separate"] for c in ev.get("currency_cols", [])):
        out.add("4$")
    if "c5_fusion_data" in ev:
        out.add("5f")
    c5 = ev.get("c5", {})
    if c5.get("matrix_hrc_rows", 0) >= 3:
        out.add("5x")
    if c5.get("matrix_hrc_rows", 0) >= 2 and not c5.get("fused"):
        out.add("5u")
    if "c6" in ev:
        out.add("6")
    if "zwsp_cells" in ev:
        out.add("Z")
    if "c8" in ev:
        out.add("8")
        if any(s["kind"] != "adjacent_dedicated" or s.get("close_col_headed") for s in ev["c8"]):
            out.add("8m")
    return out


LABELS = {
    "1": "1 legacy merge drops row-0 text", "1h": "1 ... row 0 is a header row (header_row_count)",
    "1d": "1 ... row 0 is not a header row (header_row_count)", "1d_amount": "1 ... row 0 holds an amount (data)",
    "2": "2 complementary value columns under different headers fused",
    "2?": "2 complementary value columns fused, no or nested header evidence",
    "2t": "2 complementary columns under different headers fused, not both amounts",
    "3": "3 spanning header on a marker column, not over its values",
    "3s": "3 ... and over another span's values",
    "3e": "3 spanning header on an empty slot, not over its values", "3es": "3e ... and over another span's values",
    "M": "header not over its own values (any header)", "Ms": "... over another span's values",
    "4": "4 non-$ currency column separate from its amounts", "4$": "4 $ column separate from its amounts",
    "5f": "5 header fusion swallows a data row", "5x": "5 header rows k>=3 (non-empty) rendered as body",
    "5u": "5 second header row rendered as body (no fusion)",
    "6": "6 header-only column dropped", "Z": "zero-width-space-only cells present (U+200B)", "8": "8 split negative in output", "8m": "8 ... ) column shares data or carries another span's header",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--examples", action="store_true")
    args = ap.parse_args()
    with open(args.events, encoding="utf-8") as handle:
        data = json.load(handle)
    with open(RESULTS, encoding="utf-8") as handle:
        results = {d["id"]: d for d in json.load(handle)["documents"]}
    causes = parse_classification(CLASSIFICATION)
    docs = data["documents"]

    print("== replay", data["replay"])
    # Phase A agreement
    agree = sum(1 for d in docs if {str(k): v for k, v in d["check1"].items()} ==
                {str(f["table"]): f["missing_values"] for f in results[d["id"]]["findings"] if f["missing_values"]})
    print(f"== check-1 value findings equal to results.json: {agree} of {len(docs)} documents")

    paths = Counter(t["path"] for d in docs for t in d["tables"])
    tp_docs = sum(1 for d in docs if any(t["path"] == "tableparser" for t in d["tables"]))
    print(f"== units by path {dict(paths)}; documents with TableParser tables {tp_docs}")

    per_class = defaultdict(list)  # class -> [(doc, table)]
    table_classes = {}
    for d in docs:
        for t in d["tables"]:
            if t["path"] != "tableparser":
                continue
            cls = class_tables(t)
            table_classes[(d["id"], t["table"])] = cls
            for c in cls:
                per_class[c].append((d["id"], t["table"]))
    print("== per class: tables / documents")
    for c in LABELS:
        rows = per_class.get(c, [])
        print(f"   {c:9} {len(rows):5} / {len({d for d, _ in rows}):3}  {LABELS[c]}")
    print("== per class, tables by document (RCQ grouped by issuer)")
    for c in LABELS:
        by = Counter(re.sub(r"__.*", "", d) for d, _ in per_class.get(c, []))
        if by:
            print(f"   {c:9} " + ", ".join(f"{k} {v}" for k, v in by.most_common()))

    # class 1 details
    c1 = Counter()
    c1_tables = defaultdict(set)
    for d in docs:
        for t in d["tables"]:
            for e in t.get("events", {}).get("c1", []):
                side = "header" if e["row0_header"] else ("data_amount" if e["row0_has_amount"] else "nonheader_text")
                kind = max(e["kinds"], key=e["kinds"].get) if e["kinds"] else "?"
                c1[(side, kind)] += 1
                c1_tables[side].add((d["id"], t["table"]))
                c1[("digit" if e["has_digit"] else "words_only", side)] += 1
    print("== class 1 events by (row-0 side, dropped kind):", dict(sorted(c1.items())))
    print("   tables by side:", {k: (len(v), len({x for x, _ in v})) for k, v in c1_tables.items()})

    # class 2 details
    c2 = Counter()
    c2_tables = defaultdict(set)
    for d in docs:
        for t in d["tables"]:
            for k, v in t.get("events", {}).get("c2_counts", {}).items():
                c2[k] += v
                c2_tables[k].add((d["id"], t["table"]))
    print("== class 2 legacy merge steps by kind|header evidence|row layout: steps; tables; documents")
    for k in sorted(c2):
        print(f"   {k}: {c2[k]}; {len(c2_tables[k])}; {len({x for x, _ in c2_tables[k]})}")
    for key in ("c2", "c2_noheader", "c2_text"):
        print(f"   -- {key} entries")
        for d in docs:
            for t in d["tables"]:
                for p in t.get("events", {}).get(key, []):
                    did = d["id"] if "rcq" not in d["id"] else d["id"][:34]
                    print(f"      {did} {t['table']} {p['kind']} {p['headers']} {'stacked' if p['stacked'] else 'interleaved'}"
                          f" |A {p['a_header']} {p['a_example'][:2]} |B {p['b_header']} {p['b_example'][:2]}")

    # class 3 / alignment
    c3 = Counter()
    single = Counter()
    for d in docs:
        for t in d["tables"]:
            for k, v in t.get("events", {}).get("align_counts", {}).items():
                span, slot, status = k.split("|")
                (c3 if span == "span" else single)[(slot, status)] += v
    print("== spanning headers over values by (first slot, status):")
    for k, v in sorted(c3.items()):
        print(f"   {k}: {v}")
    print("== single-column headers over values by (slot, status):", dict(sorted(single.items())))
    m = Counter()
    for d in docs:
        for t in d["tables"]:
            for a in t.get("events", {}).get("misaligned", []):
                m[("span" if a["colspan"] > 1 else "single", a["first_slot"], a["status"])] += 1
    print("== misaligned header cells by (span, first slot, status):", dict(sorted(m.items())))

    # class 4 inventory
    cur = Counter()
    cur_tables = defaultdict(set)
    for d in docs:
        for t in d["tables"]:
            for cc in t.get("events", {}).get("currency_cols", []):
                key = "/".join(sorted(cc["markers"]))
                state = "separate" if cc["separate"] and not cc["joined"] else ("joined" if not cc["separate"] else "mixed")
                cur[(key, state)] += 1
                cur_tables[(key, state)].add((d["id"], t["table"]))
                cur[(key, "marker_cells")] += sum(cc["markers"].values())
    print("== currency marker columns (data zone) by (markers, outcome): columns; tables; documents")
    for k in sorted(cur):
        if k[1] == "marker_cells":
            continue
        tabs = cur_tables[k]
        print(f"   {k}: {cur[k]} cols; {len(tabs)} tables; {len({x for x, _ in tabs})} docs; cells {cur[(k[0], 'marker_cells')]}")
    inv = Counter()
    for d in docs:
        for t in d["tables"]:
            for k, v in t.get("events", {}).get("currency_cells", {}).items():
                inv[k] += v
    print("== standalone currency cells (zone|marker):", dict(inv.most_common()))
    unk = Counter()
    for d in docs:
        for t in d["tables"]:
            unk.update(t.get("unknown_short", {}))
    print("== unrecognised short tokens left of an amount:", unk.most_common(25))

    # class 5
    hrc = Counter()
    fused = Counter()
    extra = Counter()
    for d in docs:
        for t in d["tables"]:
            if t["path"] != "tableparser":
                continue
            c5 = t["events"]["c5"]
            h = c5["hrc"]
            hrc["≥4" if h >= 4 else str(h)] += 1
            if c5["fused"]:
                fused["fused"] += 1
                fused["row1_has_amount"] += c5.get("row1_has_amount", False)
                fused["row1_not_hrc_header"] += c5.get("row1_hrc_data", False)
                fused["row1_is_data_row"] += c5.get("row1_is_data_row", False)
                fused["row1_has_amount_and_hrc_header"] += c5.get("row1_has_amount", False) and not c5.get("row1_hrc_data", False)
            m = c5["matrix_hrc_rows"]  # non-empty header rows (header_row_count) left after _clean_grid
            extra[f"nonempty_header_rows={'≥4' if m >= 4 else m}"] += 1
            if m >= 3:
                extra["tables_k3plus_header_rows_in_body"] += 1
                extra["k3plus_rows_in_body"] += m - 2
                extra["k3plus_docs:" + d["id"]] = 1
            if m >= 2 and not c5["fused"]:
                extra["tables_second_header_row_in_body_unfused"] += 1
                extra["unfused_docs:" + d["id"]] = 1
            if m >= 2 and c5["fused"]:
                extra["tables_header_rows_0_1_fused"] += 1
    print("== header_row_count distribution:", dict(hrc))
    print("== fusion:", dict(fused))
    docs_k3 = sum(1 for k in extra if k.startswith("k3plus_docs:"))
    docs_unfused = sum(1 for k in extra if k.startswith("unfused_docs:"))
    kinds = Counter()
    kind_tables = defaultdict(set)
    for d in docs:
        for t in d["tables"]:
            for row in t.get("events", {}).get("c5", {}).get("body_header_rows", []):
                tag = "k>=3" if row["matrix_row"] >= 2 else "k=2"
                kinds[(tag, row["kind"])] += 1
                kind_tables[(tag, row["kind"])].add((d["id"], t["table"]))
    print("== header rows rendered as body rows, by (position, text kind): rows; tables:",
          {k: (v, len(kind_tables[k])) for k, v in sorted(kinds.items())})
    print("== header rows in the body:", {k: v for k, v in extra.items() if ":" not in k},
          f"documents k3+ {docs_k3}, documents unfused second row {docs_unfused}")

    # class 6
    c6 = Counter()
    for d in docs:
        for t in d["tables"]:
            for e in t.get("events", {}).get("c6", []):
                kind = max(e["kinds"], key=e["kinds"].get) if e["kinds"] else "?"
                c6[kind] += 1
                c6["with_digit" if e["has_digit"] else "words_only"] += 1
    print("== class 6 dropped header cells by kind:", dict(c6))

    # class 7
    c7 = Counter()
    c7_examples = []
    for d in docs:
        for t in d["tables"]:
            if t["path"] != "one_row":
                continue
            o = t["one_row"]
            c7[o["branch"]] += 1
            if o.get("dropped"):
                c7[o["branch"] + "_dropping"] += 1
                c7[o["branch"] + "_dropped_cells"] += len(o["dropped"])
                if o.get("dropped_digits"):
                    c7[o["branch"] + "_dropping_digits"] += 1
                c7_examples.append((d["id"], t["table"], o["branch"], o["texts"], o["dropped"], t.get("output")))
    c7_docs = {d["id"] for d in docs for t in d["tables"] if t["path"] == "one_row"}
    print("== class 7 one-row units:", dict(c7), "documents", len(c7_docs))
    for e in c7_examples[:12]:
        print("   ", e)

    # class 8
    c8 = Counter()
    c8_tables = defaultdict(set)
    shares = Counter()
    for d in docs:
        for t in d["tables"]:
            for s in t.get("events", {}).get("c8", []):
                key = s["kind"] + ("+headed_by_other_span" if s.get("close_col_headed") else "")
                c8[key] += 1
                c8_tables[key].add((d["id"], t["table"]))
                shares.update(s.get("close_col_shares", []))
    print("== class 8 tables by kind:", {k: (len(v), len({x for x, _ in v})) for k, v in c8_tables.items()})
    print("== class 8 what shares the ) column:", shares.most_common(10))
    print("== class 8 split negative cells by kind:", dict(c8))

    # overlaps
    keys = ["1h", "1d_amount", "1d", "2", "2?", "2t", "3", "3e", "M", "4", "4$", "5f", "5x", "5u", "6", "8", "Z"]
    print("== overlap (tables in both)")
    for a, b in combinations(keys, 2):
        n = len(set(per_class.get(a, [])) & set(per_class.get(b, [])))
        if n:
            print(f"   {a} & {b}: {n}")

    # mapping to Phase A check-1
    print("== Phase A check-1 value tables (with output) by cause and covering class")
    cover = defaultdict(Counter)
    uncovered = defaultdict(list)
    for d in docs:
        res = results[d["id"]]
        for f in res["findings"]:
            if not f["missing_values"] or not f["produced_output"]:
                continue
            key = (d["id"], f["table"])
            cause = causes.get(key, "rev6" if d["group"] == "fixture" or re.match(r"rcq:(META|RDDT)", d["id"]) else "?")
            cls = table_classes.get(key)
            path = next((t["path"] for t in d["tables"] if t["table"] == f["table"]), "?")
            cover[cause]["tables"] += 1
            if cls is None:
                cover[cause]["path:" + path] += 1
                uncovered[cause].append(key)
                continue
            for c in ("1h", "1d", "1d_amount", "3", "3e", "M", "5f", "6", "8"):
                if c in cls:
                    cover[cause][c] += 1
            if not cls & {"1", "3", "3e", "M", "6"}:
                cover[cause]["none_of_1_3_6"] += 1
                uncovered[cause].append(key)
    for cause, counter in sorted(cover.items()):
        print(f"   {cause}: {dict(counter)}")
    for cause, keys_ in sorted(uncovered.items()):
        print(f"   uncovered {cause}: {keys_[:12]}")

    # per class: how many of its tables have a check-1 value failure, by cause
    print("== class tables with a Phase A check-1 value failure, by cause")
    value_tables = {(d["id"], f["table"]) for d in docs for f in results[d["id"]]["findings"]
                    if f["missing_values"] and f["produced_output"]}
    for c in LABELS:
        rows = set(per_class.get(c, []))
        hit = rows & value_tables
        by = Counter(causes.get(k, "rev6" if (k[0].startswith("fixture") or re.match(r"rcq:(META|RDDT)", k[0])) else "?")
                     for k in hit)
        print(f"   {c:9} {len(hit):4} of {len(rows):4}  {dict(by)}")

    # fixtures
    print("== fixture tables per class")
    for c in LABELS:
        rows = sorted((d[8:], t) for d, t in per_class.get(c, []) if d.startswith("fixture:"))
        if rows:
            grouped = defaultdict(list)
            for d, t in rows:
                grouped[d].append(t)
            print(f"   {c:9} " + "; ".join(f"{d} {v}" for d, v in grouped.items()))
    ones = defaultdict(list)
    for d in docs:
        if d["id"].startswith("fixture:"):
            for t in d["tables"]:
                if t["path"] == "one_row" and t["one_row"].get("dropped"):
                    ones[d["id"][8:]].append(t["table"])
    print("   7 (dropping):", dict(ones))

    if args.examples:
        print("== smallest examples per class")
        for key in ("c1", "c2", "c2_noheader", "c3", "c3_empty", "misaligned", "c4", "c5", "c6", "c8"):
            cands = []
            for d in docs:
                for t in d["tables"]:
                    ex = t.get("examples", {}).get(key)
                    if ex:
                        cands.append((t["size"], d["id"], t["table"]))
            cands.sort()
            seen, picked = set(), []
            for size, doc, table in cands:
                if doc in seen:
                    continue
                seen.add(doc)
                picked.append((doc, table, size))
            print(f"   {key}: {picked[:12]}")


if __name__ == "__main__":
    main()
