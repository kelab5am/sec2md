"""Aggregate the acceptance run into one result file per criterion and print the figures.

    python report.py --main-dir <main dumps> --candidate-dir <candidate dumps> \
        --analysis-dir <analyze_candidate.py output> --merges merges.json.gz --out-dir <this folder>

Reads only the dumps (no sec2md import). Writes, in --out-dir:
check1.json, findings.json, strict.json, sections.json, xlsx.json, modes.json,
alignment.json, alignment_losses.json, alignment_values.tsv.gz, assignment.json,
retention.json, class8.json, limitations.json, moved_rows.json, header_departures.json,
run_check.json and summary.json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402

EVALUATED = ("aligned", "misaligned")
# Phase A's false positives (classification.md, "False positives"): (document, table) -> cause.
FALSE_POSITIVES = {
    **{("edgar:KO-10-K-2025-02-20.htm", t): "F1" for t in (32, 43, 44, 50, 59, 63)},
    ("edgar:NVO-20-F-2025-02-05.htm", 34): "F1", ("edgar:CAT-10-K-2025-02-14.htm", 61): "F1",
    ("edgar:BABA-20-F-2025-06-26.htm", 75): "F2", ("edgar:UNH-10-K-2025-02-27.htm", 68): "F3",
    ("edgar:BAC-10-K-2025-02-25.htm", 358): "F4", ("edgar:AMZN-10-Q-2025-10-31.htm", 52): "F4",
    ("edgar:BABA-20-F-2025-06-26.htm", 19): "F4", ("edgar:MU-10-K-2025-10-03.htm", 68): "F4",
    ("edgar:MU-10-K-2025-10-03.htm", 69): "F4",
    ("edgar:KO-10-K-2025-02-20.htm", 110): "F5", ("edgar:KO-10-K-2025-02-20.htm", 112): "F5",
    ("edgar:CAT-10-K-2025-02-14.htm", 25): "F6", ("edgar:SPCX-10-Q-2026-08-04.htm", 41): "F6",
    ("edgar:CAT-10-K-2025-02-14.htm", 143): "F7", ("edgar:JPM-10-K-2025-02-14.htm", 367): "F8",
}
FIXTURE_TYPES = {"fixture:aapl-2023-10k": "10-K", "fixture:nvda-2026-10k": "10-K", "fixture:nvda-2002-10k": "10-K",
                 "fixture:nvda-2026-q2-10q": "10-Q", "fixture:nvda-2026-08-26-8k": "8-K"}


def own_filing_type(doc_id):
    if doc_id in FIXTURE_TYPES:
        return FIXTURE_TYPES[doc_id]
    if doc_id.startswith("rcq:"):
        return doc_id.split("__")[1]
    if doc_id.startswith("edgar:"):
        match = re.search(r"-(10-K|10-Q|20-F|8-K)-", doc_id)
        return match.group(1) if match else None
    return None


def load(directory, doc_id):
    return acc_common.read_json_gz(os.path.join(directory, acc_common.safe_name(doc_id)))


def finding_key(f):
    return f["table"]


def value_tables(findings, units):
    """{table: finding} for check-1 value failures, with the unit's path."""
    out = {}
    for f in findings:
        if f["missing_values"]:
            out[f["table"]] = {"tokens": f["missing_values"], "produced_output": f["produced_output"],
                               "path": units[f["table"] - 1]["path"]}
    return out


def strip_snapshot(findings):
    return [{k: v for k, v in f.items() if k != "snapshot"} for f in findings]


def coverage_identities(c):
    c = dict(c)
    return (c["tables_total"] == c["tables_evaluated"] + sum(c[k] for k in (
        "table_no_output", "table_no_separator", "table_unreliable_grid", "table_no_header", "table_no_data"))
        and c["rows_data"] == c["rows_paired"] + c["row_below_repeated_header"] + c["row_unpaired"]
        and c["values_total"] == c["values_evaluated"] + sum(c[k] for k in (
            "value_nil", "value_no_discriminating_header", "value_missing_in_output",
            "value_ambiguous_position", "value_ambiguous_header", "value_unevaluated_budget"))
        and c["values_evaluated"] == c["values_aligned"] + c["values_misaligned"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--main-dir", required=True)
    ap.add_argument("--candidate-dir", required=True)
    ap.add_argument("--analysis-dir", required=True)
    ap.add_argument("--merges", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    runs = {}
    for name, directory in (("main", args.main_dir), ("candidate", args.candidate_dir),
                            ("analysis", args.analysis_dir)):
        with open(os.path.join(directory, "_run.json"), encoding="utf-8") as handle:
            runs[name] = json.load(handle)
    doc_ids = runs["main"]["documents"]
    assert doc_ids == runs["candidate"]["documents"] == runs["analysis"]["documents"], "document lists differ"
    events = json.load(open(acc_common.EVENTS, encoding="utf-8"))
    ev = {d["id"]: {t["table"]: t for t in d["tables"]} for d in events["documents"]}
    merges = acc_common.read_json_gz(args.merges)

    check1 = {"main": Counter(), "candidate": Counter(), "residual_genuine": [], "fp_tables": [],
              "furniture_changes": [], "one_row": {"main": [], "candidate": []}, "genuine_main": []}
    findings = {"new_check1_values": [], "new_check1_reported": [], "new_check2": [], "removed": Counter(),
                "f_tables": [], "tables_with_findings": {"main": 0, "candidate": 0}}
    strict = {"new_failures": [], "documents_with_warnings": {"main": {}, "candidate": {}}, "misses": [],
              "trace_failures": {"main": 0, "candidate": 0}}
    sections = {"own_type": Counter(), "all_types": Counter(), "differences": [], "pages_differences": []}
    xlsx = {"snapshots": 0, "documents": 0, "differences": [], "status": Counter()}
    modes = {"candidate_findings_disagree": [], "main_findings_disagree": [], "candidate_alignment_disagree": [],
             "candidate_coverage_disagree": [], "candidate_strict_disagree": [], "candidate_output_differs": [],
             "candidate_sections_disagree": []}
    alignment = {"coverage": {"main": Counter(), "candidate": Counter(), "main_capture": Counter(),
                              "candidate_capture": Counter()},
                 "identities_hold": True, "production_match": True, "deterministic": True, "documents": {},
                 "findings": {"main": 0, "candidate": 0}, "candidate_findings": []}
    transitions = Counter()
    losses, value_lines = [], []
    assignment = {"steps": 0, "ok": 0, "failures": [], "text_status": Counter(), "contradictions": 0,
                  "steps_text_confirmed": 0, "steps_all_located": 0, "header_exact": 0, "paths_differ": 0}
    retention = Counter()
    retention_lists = {"value_mismatches": [], "header_cell_misses": [], "header_only_misses": []}
    class8 = {"tables": [], "fixed": 0, "remaining": 0, "corpus": {"main": Counter(), "candidate": Counter()}}
    limitations = {"years_row": [], "identifier_caption": [], "year_run_no_data_after": [],
                   "year_run_data_row": []}
    moved = []
    departures, zone_cuts = [], []
    unit_flags = {}

    for doc_index, doc_id in enumerate(doc_ids):
        main, cand, an = load(args.main_dir, doc_id), load(args.candidate_dir, doc_id), load(args.analysis_dir, doc_id)
        assert main["sha256"] == cand["sha256"]
        unit_flags[doc_id] = {u["unit"]: u for u in an["units"]}
        for mode in acc_common.MODES:
            m, c = main["modes"][mode], cand["modes"][mode]
            # --- check 1 (criterion 1) and other findings (criterion 2)
            mv, cv = value_tables(m["findings"], m["units"]), value_tables(c["findings"], c["units"])
            if mode == "normal":
                for table, f in mv.items():
                    key = "with_output" if f["produced_output"] else "no_output"
                    check1["main"][f"{key}|{f['path']}"] += 1
                    is_c1 = "c1" in ev.get(doc_id, {}).get(table, {}).get("events", {})
                    if f["produced_output"] and f["path"] == "tableparser" and is_c1:
                        check1["genuine_main"].append([doc_id, table])
                        if table in cv and cv[table]["produced_output"]:
                            check1.setdefault("genuine_still_failing", []).append(
                                {"doc": doc_id, "table": table, "main_tokens": f["tokens"],
                                 "candidate_tokens": cv[table]["tokens"]})
                for table, f in cv.items():
                    key = "with_output" if f["produced_output"] else "no_output"
                    check1["candidate"][f"{key}|{f['path']}"] += 1
                    if f["produced_output"] and f["path"] == "tableparser" and (doc_id, table) not in FALSE_POSITIVES:
                        check1["residual_genuine"].append({"doc": doc_id, "table": table, "tokens": f["tokens"],
                                                           "main_tokens": mv.get(table, {}).get("tokens")})
                    if f["produced_output"] and f["path"] == "one_row":
                        check1["one_row"]["candidate"].append([doc_id, table, f["tokens"]])
                for table, f in mv.items():
                    if f["produced_output"] and f["path"] == "one_row":
                        check1["one_row"]["main"].append([doc_id, table, f["tokens"]])
                furniture_m = {t: f["tokens"] for t, f in mv.items() if not f["produced_output"]}
                furniture_c = {t: f["tokens"] for t, f in cv.items() if not f["produced_output"]}
                if furniture_m != furniture_c:
                    check1["furniture_changes"].append({"doc": doc_id, "main": furniture_m, "candidate": furniture_c})
                for (fp_doc, table), cause in FALSE_POSITIVES.items():
                    if fp_doc != doc_id:
                        continue
                    fm = next((strip_snapshot([f])[0] for f in m["findings"] if f["table"] == table), None)
                    fc = next((strip_snapshot([f])[0] for f in c["findings"] if f["table"] == table), None)
                    findings["f_tables"].append({"doc": doc_id, "table": table, "cause": cause, "main": fm,
                                                 "candidate": fc, "same": fm == fc})
                fm_by = {f["table"]: f for f in m["findings"]}
                fc_by = {f["table"]: f for f in c["findings"]}
                findings["tables_with_findings"]["main"] += len(fm_by)
                findings["tables_with_findings"]["candidate"] += len(fc_by)
                for table, f in fc_by.items():
                    g = fm_by.get(table, {"missing_values": [], "missing_reported": [], "structure": []})
                    new_values = (Counter(map(tuple, f["missing_values"])) - Counter(map(tuple, g["missing_values"])))
                    new_reported = (Counter(map(tuple, f["missing_reported"]))
                                    - Counter(map(tuple, g["missing_reported"])))
                    new_structure = [s for s in f["structure"] if s not in g["structure"]]
                    if new_values:
                        findings["new_check1_values"].append({"doc": doc_id, "table": table,
                                                              "tokens": [list(k) for k in new_values.elements()]})
                    if new_reported:
                        findings["new_check1_reported"].append({"doc": doc_id, "table": table,
                                                                "tokens": [list(k) for k in new_reported.elements()]})
                    if new_structure:
                        findings["new_check2"].append({"doc": doc_id, "table": table, "rows": new_structure,
                                                       "main_rows": g["structure"]})
                for table, g in fm_by.items():
                    f = fc_by.get(table, {"missing_values": [], "missing_reported": [], "structure": []})
                    findings["removed"]["check1_value_tokens"] += sum(
                        (Counter(map(tuple, g["missing_values"])) - Counter(map(tuple, f["missing_values"]))).values())
                    findings["removed"]["check1_reported_tokens"] += sum(
                        (Counter(map(tuple, g["missing_reported"]))
                         - Counter(map(tuple, f["missing_reported"]))).values())
                    findings["removed"]["check2_rows"] += len([s for s in g["structure"] if s not in f["structure"]])
            # --- strict (criterion 3)
            new_trace = Counter(acc_common.strip_ids(c["trace_failures"])) - Counter(
                acc_common.strip_ids(m["trace_failures"]))
            new_warnings = [w for w in c["warnings"] if w not in m["warnings"]]
            strict["trace_failures"]["main"] += len(m["trace_failures"])
            strict["trace_failures"]["candidate"] += len(c["trace_failures"])
            if m["warnings"]:
                strict["documents_with_warnings"]["main"][f"{doc_id}|{mode}"] = m["warnings"]
            if c["warnings"]:
                strict["documents_with_warnings"]["candidate"][f"{doc_id}|{mode}"] = c["warnings"]
            if new_trace or new_warnings:
                strict["new_failures"].append({"doc": doc_id, "mode": mode, "trace": sorted(new_trace.elements()),
                                               "warnings": new_warnings})
            if c["header_accounting_misses"]:
                strict["misses"].append({"doc": doc_id, "mode": mode, "misses": c["header_accounting_misses"]})
            # --- sections (criterion 4)
            own = own_filing_type(doc_id)
            for filing_type in acc_common.FILING_TYPES:
                same = m["sections"][filing_type] == c["sections"][filing_type]
                sections["all_types"]["same" if same else "different"] += 1
                if filing_type == own:
                    sections["own_type"]["same" if same else "different"] += 1
                if not same:
                    sections["differences"].append({"doc": doc_id, "mode": mode, "filing_type": filing_type,
                                                    "own_type": filing_type == own,
                                                    "main": m["sections"][filing_type],
                                                    "candidate": c["sections"][filing_type]})
            if m["pages"] != c["pages"]:
                sections["pages_differences"].append({"doc": doc_id, "mode": mode})
            # --- XLSX (criterion 5)
            if mode == "capture":
                xlsx["documents"] += 1
                xlsx["snapshots"] += len(c["xlsx"])
                xlsx["status"].update(x["status"] for x in c["xlsx"])
                if m["xlsx"] != c["xlsx"]:
                    diff = [(a, b) for a, b in zip(m["xlsx"], c["xlsx"]) if a != b]
                    xlsx["differences"].append({"doc": doc_id, "count_main": len(m["xlsx"]),
                                                "count_candidate": len(c["xlsx"]), "first": diff[:5]})
        # --- modes (criterion 6)
        cn, cc = cand["modes"]["normal"], cand["modes"]["capture"]
        mn, mc = main["modes"]["normal"], main["modes"]["capture"]
        if strip_snapshot(cn["findings"]) != strip_snapshot(cc["findings"]):
            modes["candidate_findings_disagree"].append(doc_id)
        if strip_snapshot(mn["findings"]) != strip_snapshot(mc["findings"]):
            modes["main_findings_disagree"].append(doc_id)
        if [re.sub(r"snapshot \d+, ", "", a) for a in cn["alignment"]] != [
                re.sub(r"snapshot \d+, ", "", a) for a in cc["alignment"]]:
            modes["candidate_alignment_disagree"].append(doc_id)
        if cn["alignment_coverage"] != cc["alignment_coverage"]:
            modes["candidate_coverage_disagree"].append(doc_id)
        if (cn["warnings"], acc_common.strip_ids(cn["trace_failures"]), cn["header_accounting_misses"]) != (
                cc["warnings"], acc_common.strip_ids(cc["trace_failures"]), cc["header_accounting_misses"]):
            modes["candidate_strict_disagree"].append(doc_id)
        if cn["sections"] != cc["sections"]:
            modes["candidate_sections_disagree"].append(doc_id)
        differing = [i + 1 for i, (a, b) in enumerate(zip(cn["units"], cc["units"]))
                     if a["output"] != b["output"] and b["path"] != "unreliable"]
        if differing:
            modes["candidate_output_differs"].append({"doc": doc_id, "units": differing})
        # --- alignment (criterion 7)
        alignment["deterministic"] &= an["deterministic_outputs"]
        cov_main, cov_cand = dict(an["coverage"]["main"]), dict(an["coverage"]["candidate"])
        production_ok = (an["coverage"]["candidate"] == an["candidate_dump_coverage"]["normal"]
                         and an["coverage"]["main"] == an["production"]["main_normal"]["coverage"])
        alignment["production_match"] &= production_ok
        for name, cov in (("main", cov_main), ("candidate", cov_cand),
                          ("main_capture", dict(an["production"]["main_capture"]["coverage"])),
                          ("candidate_capture", dict(an["candidate_dump_coverage"]["capture"]))):
            alignment["identities_hold"] &= coverage_identities(cov)
            alignment["coverage"][name].update(cov)
        alignment["findings"]["main"] += len([f for f in an["production"]["main_normal"]["findings"]
                                              if "misaligned values in total" not in f])
        cand_findings = [f for f in an["candidate_dump_findings"]["normal"] if "misaligned values in total" not in f]
        alignment["findings"]["candidate"] += len(cand_findings)
        alignment["candidate_findings"].extend({"doc": doc_id, "finding": f} for f in cand_findings)
        alignment["documents"][doc_id] = {"main": {k: cov_main[k] for k in ("values_evaluated", "values_aligned",
                                                                             "values_misaligned")},
                                          "candidate": {k: cov_cand[k] for k in ("values_evaluated", "values_aligned",
                                                                                  "values_misaligned")},
                                          "production_match": production_ok}
        for unit, row, column, text, mo, ml, mcol, co, cl, ccol in an["values"]:
            transitions[(mo, co)] += 1
            value_lines.append("\t".join(str(x) for x in (doc_index, unit, row, column, text.replace("\t", " "),
                                                         mo, co)))
        for loss in an["losses"]:
            loss["doc"] = doc_id
            loss["unit_flags"] = unit_flags[doc_id].get(loss["unit"])
            losses.append(loss)
        # --- assignment (criterion 8)
        for step in an["assignment"]:
            assignment["steps"] += 1
            assignment["ok"] += step["ok"]
            assignment["text_status"].update(step["text_status"])
            assignment["contradictions"] += step["contradictions"]
            assignment["header_exact"] += step["header_exact"]
            assignment["paths_differ"] += len(step["paths"]) > 1
            assignment["steps_all_located"] += step["text_located"] == step["values"]
            assignment["steps_text_confirmed"] += step["text_located"] > 0 and step["contradictions"] == 0
            if not step["ok"]:
                step["doc"] = doc_id
                step["unit_flags"] = unit_flags[doc_id].get(step["unit"])
                assignment["failures"].append(step)
        # --- retention (criterion 9)
        for key, value in an["retention"].items():
            if isinstance(value, list):
                for item in value:
                    item["doc"] = doc_id
                    item["unit_flags"] = unit_flags[doc_id].get(item["unit"])
                retention_lists[key].extend(value)
            else:
                retention[key] += value
        # --- class 8 (criterion 11)
        for name in ("main", "candidate"):
            class8["corpus"][name]["tables"] += len(an["splits"][name])
            class8["corpus"][name]["cells"] += sum(len(v) for v in an["splits"][name].values())
        for table, entry in sorted(ev.get(doc_id, {}).items()):
            if "c8" not in entry.get("events", {}):
                continue
            remaining = an["splits"]["candidate"].get(str(table), [])
            class8["tables"].append({"doc": doc_id, "table": table, "evidence_cells": len(entry["events"]["c8"]),
                                     "evidence_kinds": dict(Counter(s["kind"] for s in entry["events"]["c8"])),
                                     "main_split_cells": len(an["splits"]["main"].get(str(table), [])),
                                     "candidate_split_cells": len(remaining), "remaining": remaining})
            class8["fixed" if not remaining else "remaining"] += 1
        class8.setdefault("candidate_split_tables_outside_class8", [])
        for table, cells in an["splits"]["candidate"].items():
            if "c8" not in ev.get(doc_id, {}).get(int(table), {}).get("events", {}):
                class8["candidate_split_tables_outside_class8"].append({"doc": doc_id, "table": int(table),
                                                                        "cells": cells})
        for item in an.get("moved", []):
            item["doc"] = doc_id
            moved.append(item)
        for item in an.get("departures", []):
            item["doc"] = doc_id
            departures.append(item)
        for item in an.get("zone_cuts", []):
            item["doc"] = doc_id
            zone_cuts.append(item)
        # --- named limitations (criterion 12)
        for key in limitations:
            for item in an["limitations"][key]:
                item["doc"] = doc_id
                limitations[key].append(item)

    # Evaluated-set comparison and summaries.
    evaluated_main = sum(v for (mo, co), v in transitions.items() if mo in EVALUATED)
    evaluated_cand = sum(v for (mo, co), v in transitions.items() if co in EVALUATED)
    lost = sum(v for (mo, co), v in transitions.items() if mo in EVALUATED and co not in EVALUATED)
    gained = sum(v for (mo, co), v in transitions.items() if co in EVALUATED and mo not in EVALUATED)
    alignment_summary = {
        "identities_hold": alignment["identities_hold"],
        "production_match": alignment["production_match"],
        "deterministic_candidate_outputs": alignment["deterministic"],
        "coverage": {k: dict(v) for k, v in alignment["coverage"].items()},
        "findings_lines": alignment["findings"],
        "candidate_findings": alignment["candidate_findings"],
        "values_listed": sum(transitions.values()),
        "evaluated_main": evaluated_main, "evaluated_candidate": evaluated_cand,
        "evaluated_on_main_not_candidate": lost, "evaluated_on_candidate_not_main": gained,
        "transitions": sorted(([mo, co, v] for (mo, co), v in transitions.items()), key=lambda x: -x[2]),
        "loss_transitions": dict(Counter(f"{l['main']} -> {l['candidate']}" for l in losses)),
        "documents": alignment["documents"],
    }
    out = args.out_dir
    write = lambda name, data: json.dump(data, open(os.path.join(out, name), "w", encoding="utf-8"),  # noqa: E731
                                         ensure_ascii=False, indent=1, default=list)
    check1_summary = {
        "main": dict(check1["main"]), "candidate": dict(check1["candidate"]),
        "genuine_main_tableparser_class1": len(check1["genuine_main"]),
        "genuine_main_tables": check1["genuine_main"],
        "genuine_still_failing": check1.get("genuine_still_failing", []),
        "residual_genuine": check1["residual_genuine"],
        "one_row": check1["one_row"],
        "furniture_unchanged": not check1["furniture_changes"], "furniture_changes": check1["furniture_changes"],
    }
    write("check1.json", check1_summary)
    write("findings.json", {"new_check1_values": findings["new_check1_values"],
                            "new_check1_reported": findings["new_check1_reported"],
                            "new_check2": findings["new_check2"], "removed": dict(findings["removed"]),
                            "tables_with_findings": findings["tables_with_findings"],
                            "f_tables": findings["f_tables"]})
    write("strict.json", strict)
    write("sections.json", {"own_type": dict(sections["own_type"]), "all_types": dict(sections["all_types"]),
                            "differences": sections["differences"],
                            "pages_differences": sections["pages_differences"]})
    write("xlsx.json", {"documents": xlsx["documents"], "snapshots": xlsx["snapshots"],
                        "status": dict(xlsx["status"]), "differences": xlsx["differences"]})
    write("modes.json", modes)
    write("alignment.json", alignment_summary)
    write("alignment_losses.json", losses)
    with gzip.open(os.path.join(out, "alignment_values.tsv.gz"), "wt", encoding="utf-8") as handle:
        handle.write("# document index (see run_check.json), unit, source row, numeric-core column, value text, "
                     "outcome on main's Markdown, outcome on the candidate's Markdown\n")
        handle.write("\n".join(value_lines) + "\n")
    write("assignment.json", {"steps": assignment["steps"], "ok": assignment["ok"],
                              "merges_summary": merges["summary"],
                              "text_status": dict(assignment["text_status"]),
                              "contradictions": assignment["contradictions"],
                              "header_exact": assignment["header_exact"], "paths_differ": assignment["paths_differ"],
                              "steps_all_located": assignment["steps_all_located"],
                              "steps_text_confirmed": assignment["steps_text_confirmed"],
                              "failures": assignment["failures"]})
    write("retention.json", {**dict(retention), **retention_lists})
    class8["corpus"] = {k: dict(v) for k, v in class8["corpus"].items()}
    write("class8.json", class8)
    write("limitations.json", limitations)
    def tables(items):
        return len({(m["doc"], m["unit"]) for m in items})

    failures = [m for m in moved if not m["rule_ok"]]
    flagged = [m for m in moved if m["signals"]]
    moved_summary = {
        "rows": len(moved), "tables": tables(moved),
        "fixture_rows": sum(m["doc"].startswith("fixture:") for m in moved),
        "fixture_tables": tables([m for m in moved if m["doc"].startswith("fixture:")]),
        "first_header_row": sum(m["first_header_row"] for m in moved),
        "rule_ok": sum(m["rule_ok"] for m in moved), "rule_failures": len(failures),
        "rule_failure_tables": tables(failures),
        "reasons": dict(Counter(r for m in moved for r in m["reasons"])),
        "rows_without_reason_beyond_first": sum(not m["reasons"] and not m["first_header_row"] for m in moved),
        "signals_rows": dict(Counter(sig for m in moved for sig in m["signals"])),
        "signals_tables": {sig: tables([m for m in moved if sig in m["signals"]])
                           for sig in sorted({sig for m in moved for sig in m["signals"]})},
        "any_signal_rows": len(flagged), "any_signal_tables": tables(flagged),
        "beyond_snapshot_header_rows": sum(m["beyond_snapshot_header"] for m in moved),
        "beyond_snapshot_header_tables": tables([m for m in moved if m["beyond_snapshot_header"]]),
        # Round 3 (revision 12): rows in the zone only through main's sparse-row fusion, as
        # R0 applies it to the source grid, and moved label-only rows.
        "sparse_row_fusion_only_rows": sum(m.get("sparse_row_fusion_only", False) for m in moved),
        "sparse_row_fusion_only_tables": tables([m for m in moved if m.get("sparse_row_fusion_only")]),
        "label_only_rows": sum("label_only" in m["reasons"] for m in moved),
        "label_only_tables": tables([m for m in moved if "label_only" in m["reasons"]]),
        "sparse_row_fusion_only_list": [m for m in moved if m.get("sparse_row_fusion_only")],
        "failures": failures,
        "rows_list": moved,
    }
    stacked = [c for c in zone_cuts if c["stacked_title"]]
    departure_summary = {
        "rows": len(departures), "tables": tables(departures),
        "data_rows": sum(d["data_row"] for d in departures),
        "non_data_rows": sum(not d["data_row"] for d in departures),
        "non_data_tables": tables([d for d in departures if not d["data_row"]]),
        "non_data_label_only_rows": sum(not d["data_row"] and d["label_only"] for d in departures),
        "non_data_with_value_text_rows": sum(not d["data_row"] and not d["label_only"] for d in departures),
        "non_data_with_value_text_tables": tables([d for d in departures if not d["data_row"] and not d["label_only"]]),
        "non_data_by_document": dict(Counter(d["doc"] for d in departures if not d["data_row"])),
        "zone_cuts": len(zone_cuts),
        "zone_cuts_by_label_only_row": sum(c["cut_label_only"] for c in zone_cuts),
        "zone_cuts_inconsistent": [c for c in zone_cuts if not c.get("consistent", True)],
        "stacked_title_tables": len(stacked),
        "stacked_title_list": stacked,
        "rows_list": departures,
    }
    write("moved_rows.json", moved_summary)
    write("header_departures.json", departure_summary)
    write("run_check.json", {"documents": doc_ids, "runs": {k: {kk: vv for kk, vv in v.items()
                                                                 if kk not in ("documents", "document_seconds")}
                                                            for k, v in runs.items()}})
    summary = {
        "check1": {k: check1_summary[k] for k in ("main", "candidate", "genuine_main_tableparser_class1",
                                                  "furniture_unchanged")} | {
            "residual_genuine": len(check1["residual_genuine"]),
            "genuine_still_failing": len(check1.get("genuine_still_failing", []))},
        "findings": {"new_check1_values": len(findings["new_check1_values"]),
                     "new_check1_reported": len(findings["new_check1_reported"]),
                     "new_check2": len(findings["new_check2"]), "removed": dict(findings["removed"]),
                     "f_tables_changed": [(f["doc"], f["table"], f["cause"]) for f in findings["f_tables"]
                                          if not f["same"]]},
        "strict": {"new_failures": len(strict["new_failures"]), "misses": len(strict["misses"]),
                   "trace_failures": strict["trace_failures"],
                   "documents_with_warnings": {k: len(v) for k, v in strict["documents_with_warnings"].items()}},
        "sections": {"own_type": dict(sections["own_type"]), "all_types": dict(sections["all_types"]),
                     "pages_differences": len(sections["pages_differences"])},
        "xlsx": {"snapshots": xlsx["snapshots"], "documents_differing": len(xlsx["differences"])},
        "modes": {k: len(v) for k, v in modes.items()},
        "alignment": {k: alignment_summary[k] for k in ("identities_hold", "production_match",
                                                        "deterministic_candidate_outputs", "findings_lines",
                                                        "values_listed", "evaluated_main", "evaluated_candidate",
                                                        "evaluated_on_main_not_candidate",
                                                        "evaluated_on_candidate_not_main", "loss_transitions")},
        "assignment": {"steps": assignment["steps"], "ok": assignment["ok"],
                       "failures": len(assignment["failures"]), "contradictions": assignment["contradictions"]},
        "retention": dict(retention) | {k: len(v) for k, v in retention_lists.items()},
        "class8": {"tables": len(class8["tables"]), "fixed": class8["fixed"], "remaining": class8["remaining"],
                   "corpus": class8["corpus"],
                   "candidate_split_tables_outside_class8": len(class8["candidate_split_tables_outside_class8"])},
        "limitations": {k: len(v) for k, v in limitations.items()},
        "moved_rows": {k: moved_summary[k] for k in ("rows", "tables", "fixture_rows", "fixture_tables",
                                                     "first_header_row", "rule_ok", "rule_failures",
                                                     "rule_failure_tables", "reasons",
                                                     "rows_without_reason_beyond_first", "signals_rows",
                                                     "signals_tables", "any_signal_rows", "any_signal_tables",
                                                     "beyond_snapshot_header_rows", "beyond_snapshot_header_tables",
                                                     "sparse_row_fusion_only_rows", "sparse_row_fusion_only_tables",
                                                     "label_only_rows", "label_only_tables")},
        "header_departures": {k: v for k, v in departure_summary.items() if not k.endswith("_list")},
    }
    write("summary.json", summary)
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=list))


if __name__ == "__main__":
    main()
