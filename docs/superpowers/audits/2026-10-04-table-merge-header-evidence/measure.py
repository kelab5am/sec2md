"""Measure table-merge and header-rule events over the Phase A corpus (research only).

    python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/measure.py \
        --edgar-cache outputs/table-completeness-corpus \
        --out docs/superpowers/audits/2026-10-04-table-merge-header-evidence/events.json [--only <doc id> ...]

For every check_tables unit that Parser renders through TableParser (normal mode) it
replays the renderer with provenance (trace_merge.shadow), verifies the replay against
the parser's real output, and records the event classes of the table-merge and
header-rules evidence report (see REPORT.md, "Method and limits"). One-row units
(Parser._one_row_table_to_text) are recorded for class 7. Writes events.json and prints
a summary. Nothing outside this folder is written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sec2md.encoding import decode_html  # noqa: E402
from sec2md.parser import ITEM_HEADER_CELL_RE, PART_HEADER_CELL_RE  # noqa: E402
from sec2md.table_parser import render_cell_content  # noqa: E402
from sec2md.utils import clean_text  # noqa: E402

from corpus import documents, trace_document  # noqa: E402
from trace_merge import (  # noqa: E402
    AMOUNT, BARE_YEAR, CLOSE, FOOTNOTE, OPEN_AMOUNT, PERIOD_TEXT, STRUCTURAL, currency_marker, is_marker, is_value,
    output_col, text_kind, vis,
)

UNITS = re.compile(r"\b(?:in (?:thousands|millions|billions)|thousands|millions|billions|except (?:per|share))\b"
                   r"|^\(?\s*(?:NT\$|US\$|RMB|\$|€|%)\s*\)?$", re.I)


# --- helpers ---------------------------------------------------------------------------

def compact_row(record, g0_row, cols=None):
    """Source row as TableParser sees it: 'text[colspan]' per origin cell, empties run-length coded."""
    out, empties = [], 0
    for c, cell in enumerate(record.trace.g0[g0_row]):
        if cols is not None and c not in cols:
            continue
        if cell is None or cell.is_spanning:
            continue
        span = cell.cell.colspan
        text = cell.text.strip().replace("​", "<ZWSP>")
        if not text and span == 1:
            empties += 1
            continue
        if empties:
            out.append(f"·×{empties}" if empties > 1 else "·")
            empties = 0
        out.append((text[:70] + ("…" if len(text) > 70 else "")) + (f" [cs{span}]" if span > 1 else ""))
    if empties:
        out.append(f"·×{empties}" if empties > 1 else "·")
    return " | ".join(out)


def md_excerpt(markdown, body_lines=4, around=None):
    lines = markdown.split("\n")
    if around is None:
        keep = lines[: 2 + body_lines]
    else:
        keep = lines[:2] + [lines[i + 2] for i in around if 0 <= i + 2 < len(lines)]
    return [line if len(line) <= 400 else line[:400] + " …" for line in keep]


def first_data_row(record):
    for r in range(len(record.trace.g0)):
        if record.g0_is_body(r):
            return r
    return None


def header_like(text):
    """Header-zone text that can head a column: not a marker, footnote, dash or non-year amount."""
    t = vis(text)
    if not t or is_marker(t) or FOOTNOTE.match(t):
        return False
    return not is_value(t) or bool(BARE_YEAR.match(t))


def header_keys(record, r_from):
    """{g0 col: origin of the lowest header-zone, header-like cell whose span covers it}."""
    t = record.trace
    keys = {}
    for r in range(min(r_from, len(t.g0))):
        for c, cell in enumerate(t.g0[r]):
            if cell is None or cell.is_spanning or not header_like(cell.text):
                continue
            for k in range(c, c + cell.cell.colspan):
                keys[k] = (r, c)   # later (lower) rows overwrite earlier ones
    return keys


def real_value(text):
    """A body value for class 2: an amount, nil dash or fragment, not a marker or footnote reference."""
    t = vis(text)
    return bool(t) and not is_marker(t) and not FOOTNOTE.match(t) and is_value(t)


def value_columns(record, r_from):
    """{g0 col: set(output cols)} and {output col: set(g0 cols)} for data-zone value origins."""
    t = record.trace
    by_src, by_out = defaultdict(set), defaultdict(set)
    for (r, c), place in t.final.items():
        if r < r_from or not is_value(t.text((r, c))):
            continue
        col = output_col(place)
        if col is None:
            continue
        by_src[c].add(col)
        by_out[col].add(c)
    return by_src, by_out


def column_body(record, c, r_from):
    t = record.trace
    return [vis(t.g0[r][c].text) for r in range(r_from, len(t.g0))
            if t.g0[r][c] is not None and not t.g0[r][c].is_spanning and vis(t.g0[r][c].text)]


def slot_type(record, c, r_from):
    """What the body of G0 column c holds: 'empty', 'dollar', 'currency:<m>', 'paren', 'percent', 'value', 'text'."""
    body = column_body(record, c, r_from)
    if not body:
        return "empty"
    if all(is_marker(v) for v in body):
        currencies = {currency_marker(v) for v in body if currency_marker(v)}
        if currencies == {"$"}:
            return "dollar"
        if currencies:
            return "currency:" + "/".join(sorted(currencies))
        if set(body) <= {"(", ")"}:
            return "paren"
        return "percent" if set(body) <= {"%"} else "marker"
    if any(is_value(v) for v in body):
        return "value"
    return "text"


# --- detectors -------------------------------------------------------------------------

def detect(record):
    """Event dict for one TableParser unit."""
    t = record.trace
    ev = {}
    fdr = first_data_row(record)
    r_from = fdr if fdr is not None else len(t.g0)

    # Class 1: legacy pass drops the merged-in column's row-0 text
    drops = []
    g0_row0 = t.rows_keep[0] if t.rows_keep else None
    for d in t.row0_drops:
        header = record.g0_is_header(g0_row0)
        kinds = Counter(text_kind(t.text(o)) for o in d["origins"])
        drops.append({
            "text": d["dropped_text"], "kept": d["kept_text"], "row0_header": header,
            "row0_has_amount": record.g0_has_amount(g0_row0), "row0_is_data_row": record.g0_is_data(g0_row0),
            "kinds": dict(kinds), "has_digit": bool(re.search(r"\d", d["dropped_text"])),
        })
    if drops:
        ev["c1"] = drops

    # Class 2: complementary value columns fused by the legacy pass
    keys = header_keys(record, r_from)
    fused_pairs = []
    for m in t.legacy_merges:
        a_rows, b_rows = {}, {}
        for k in range(1, len(m["a_cells"])):
            g0r = t.rows_keep[k]
            if g0r < r_from:
                continue  # header zone
            a, b = vis(m["a_cells"][k]), vis(m["b_cells"][k])
            if a and not is_marker(a):
                a_rows[k] = a
            if b and not is_marker(b):
                b_rows[k] = b
        a_only = {k: v for k, v in a_rows.items() if k not in b_rows}
        b_only = {k: v for k, v in b_rows.items() if k not in a_rows}
        if not (a_only and b_only):
            continue
        a_val = all(real_value(v) for v in a_only.values()) and any(AMOUNT.match(v) for v in a_only.values())
        b_val = all(real_value(v) for v in b_only.values()) and any(AMOUNT.match(v) for v in b_only.values())
        a_any = any(real_value(v) for v in a_only.values())
        b_any = any(real_value(v) for v in b_only.values())
        kind = ("value+value" if a_val and b_val else "mixed" if (a_any or b_any) else "text+text")
        a_keys = {keys.get(c) for k in a_only for (_, c) in m["a_origins"][k]}
        b_keys = {keys.get(c) for k in b_only for (_, c) in m["b_origins"][k]}
        if None in a_keys or None in b_keys:
            headers = "no_header"
        elif not a_keys.isdisjoint(b_keys):
            headers = "same_header"
        elif len({r for r, _ in a_keys | b_keys}) == 1:
            headers = "sibling_headers"     # e.g. "2024" and "2023", or "Debit" and "Credit", in one row
        else:
            headers = "nested_headers"      # keys at different header depths: often a source cell offset
        rows_a, rows_b = sorted(a_only), sorted(b_only)
        stacked = rows_a[-1] < rows_b[0] or rows_b[-1] < rows_a[0]
        fused_pairs.append({
            "kind": kind, "headers": headers, "stacked": stacked, "a_rows": len(a_only), "b_rows": len(b_only),
            "group": m["group"],
            "a_header": sorted({t.text(k)[:40] for k in a_keys if k}), "b_header": sorted({t.text(k)[:40] for k in b_keys if k}),
            "a_example": list(a_only.items())[:3], "b_example": list(b_only.items())[:3],
        })
    if fused_pairs:
        ev["c2_counts"] = dict(Counter(f"{p['kind']}|{p['headers']}|{'stacked' if p['stacked'] else 'interleaved'}"
                                       for p in fused_pairs))
    harmful = [p for p in fused_pairs if p["headers"] == "sibling_headers" and p["kind"] == "value+value"]
    if harmful:
        ev["c2"] = harmful
    unknown = [p for p in fused_pairs if p["headers"] in ("no_header", "nested_headers") and p["kind"] == "value+value"]
    if unknown:
        ev["c2_noheader"] = unknown
    other = [p for p in fused_pairs if p["headers"] in ("sibling_headers", "nested_headers") and p["kind"] != "value+value"]
    if other:
        ev["c2_text"] = other

    # Header alignment (classes 3 and the generic diagnostic)
    if fdr is not None:
        by_src, by_out = value_columns(record, r_from)
        label_cols = {c for c in range(len(t.g0[0])) if slot_type(record, c, r_from) == "text"}
        aligned = []
        for (r, c), place in t.final.items():
            if r >= r_from:
                continue
            text = t.text((r, c))
            if not header_like(text):
                continue
            cell = t.cell((r, c))
            span = set(range(c, c + cell.colspan))
            if span & label_cols:
                continue  # a title or label-column header: it spans the row labels, so column 0 is right
            own = set().union(*(by_src.get(k, set()) for k in span)) if span else set()
            if not own:
                continue  # header over no values (label column, text columns)
            p = output_col(place)
            if p is None:
                status = "dropped"
            elif p in own:
                status = "aligned"
            elif by_out.get(p):
                status = "shifted"     # over other columns' values
            else:
                status = "detached"    # over a column with no values of any span
            # a caption whose span covers every value column ("(In millions)", "Year ended ...")
            wide = own >= set(by_out)
            if status == "detached" and wide:
                status = "caption_moved"
            aligned.append({
                "origin": [r, c], "text": vis(text), "colspan": cell.colspan, "status": status, "wide": wide,
                "first_slot": slot_type(record, c, r_from), "out_col": p, "own_cols": sorted(own),
                "over": sorted(by_out.get(p, ())) if p is not None else [],
            })
        if aligned:
            ev["align_counts"] = dict(Counter(f"{'span' if a['colspan'] > 1 else 'single'}|{a['first_slot']}|{a['status']}"
                                              for a in aligned))
        bad = [a for a in aligned if a["status"] in ("shifted", "detached")]
        spanning = [a for a in bad if a["colspan"] > 1]
        # 3: the spanning header's first grid column is a marker column ($, other currency, paren, %)
        c3 = [a for a in spanning if a["first_slot"] not in ("value", "text", "empty")]
        if c3:
            ev["c3"] = c3
        # 3 (empty slot): first grid column has no body content at all (BABA/TSM currency slot or spacer)
        c3_empty = [a for a in spanning if a["first_slot"] == "empty"]
        if c3_empty:
            ev["c3_empty"] = c3_empty
        if bad:
            ev["misaligned"] = bad

    # Class 4: currency marker columns (data zone) and whether they stay separate
    cur_cols = []
    if fdr is not None:
        g0 = t.g0
        for c in range(len(g0[0]) if g0 else 0):
            body = column_body(record, c, r_from)
            markers = [currency_marker(v) for v in body]
            if not body or not all(markers):
                continue
            separate = joined = 0
            for r in range(r_from, len(g0)):
                cell = g0[r][c]
                if cell is None or cell.is_spanning or not cell.text.strip():
                    continue
                # nearest value origin to the right in the same row
                partner = next(((r, k) for k in range(c + 1, len(g0[r]))
                                if g0[r][k] is not None and not g0[r][k].is_spanning and g0[r][k].text.strip()), None)
                if partner is None or not is_value(g0[partner[0]][partner[1]].text):
                    continue
                pm, pv = t.final.get((r, c)), t.final.get(partner)
                if pm is not None and pv is not None and pm[0] != "dropped" and pm == pv:
                    joined += 1
                else:
                    separate += 1
            if separate or joined:
                cur_cols.append({"col": c, "markers": dict(Counter(markers)), "separate": separate, "joined": joined})
    if cur_cols:
        ev["currency_cols"] = cur_cols
    # zero-width-space-only cells: invisible, but TableParser treats them as content
    zw = sum(1 for row in t.g0 for cell in row
             if cell is not None and not cell.is_spanning and cell.text.strip() and not vis(cell.text))
    if zw:
        ev["zwsp_cells"] = zw
    nondollar_sep = [cc for cc in cur_cols if set(cc["markers"]) != {"$"} and cc["separate"]]
    if nondollar_sep:
        ev["c4"] = nondollar_sep
    # inventory: every standalone currency-marker cell, by zone
    inventory = Counter()
    for r, row in enumerate(t.g0):
        for cell in row:
            if cell is None or cell.is_spanning:
                continue
            marker = currency_marker(cell.text)
            if marker:
                inventory[("header" if r < r_from else "data") + "|" + marker] += 1
    if inventory:
        ev["currency_cells"] = dict(inventory)

    # Class 5: header structure
    matrix_header_rows = sum(1 for g0r in t.rows_keep if record.g0_is_header(g0r))
    shape_header_rows = sum(1 for g0r in t.rows_keep if g0r < r_from)
    ev["c5"] = {
        "hrc": record.header_rows, "fused": t.fused,
        "matrix_rows": len(t.rows_keep), "matrix_hrc_rows": matrix_header_rows,
        "matrix_shape_header_rows": shape_header_rows,
    }
    if t.fused and len(t.rows_keep) > 1:
        r1 = t.rows_keep[1]
        ev["c5"]["row1_hrc_data"] = not record.g0_is_header(r1)
        ev["c5"]["row1_has_amount"] = record.g0_has_amount(r1)
        ev["c5"]["row1_is_data_row"] = record.g0_is_data(r1)
        if record.g0_has_amount(r1):
            ev["c5_fusion_data"] = True
    taken = 2 if t.fused else 1
    body_header_rows = []
    for k, g0r in enumerate(t.rows_keep):
        if k >= taken and record.g0_is_header(g0r):
            texts = [x for x in record.g0_texts(g0r) if x]
            joined = " | ".join(texts)
            kind = ("units" if texts and all(UNITS.search(x) for x in texts) else
                    "period" if texts and all(PERIOD_TEXT.search(x) or BARE_YEAR.match(x) for x in texts) else "other")
            body_header_rows.append({"matrix_row": k, "kind": kind, "text": joined[:120]})
    if body_header_rows:
        ev["c5"]["body_header_rows"] = body_header_rows
    if body_header_rows:
        ev["c5_header_rows_in_body"] = len(body_header_rows)

    # Class 6: header-only columns dropped by _clean_empty_rows_and_cols
    if t.clean_col_drops:
        ev["c6"] = [{"header": d["header"], "kinds": dict(Counter(text_kind(t.text(o)) for o in d["origins"])),
                     "has_digit": bool(re.search(r"\d", d["header"]))} for d in t.clean_col_drops]
    if t.clean_all_dropped:
        ev["c6_all"] = True

    # Class 8: split accounting negatives in the output
    splits = []
    data_cols = defaultdict(list)    # output col -> data-zone cell texts that land in it
    header_cols = defaultdict(list)  # output col -> header-zone texts that land in it (header line or body)
    out_cells = {}
    for (r, c), place in t.final.items():
        if place[0] == "body":
            out_cells.setdefault((place[1], place[2]), []).append((r, c))
        col = output_col(place)
        if col is None:
            continue
        (data_cols if r >= r_from else header_cols)[col].append(vis(t.text((r, c))))
    rendered = _body_cells(t.markdown)
    for li, cells in enumerate(rendered):
        for j, text in enumerate(cells):
            if not OPEN_AMOUNT.match(text.strip()):
                continue
            # where did the matching close go? look in the same source row
            origins = out_cells.get((li, j), [])
            close_place = None
            for (r, c) in origins:
                row = t.g0[r]
                nxt = next(((r, k) for k in range(c + 1, len(row)) if row[k] is not None and not row[k].is_spanning
                            and row[k].text.strip()), None)
                if nxt and CLOSE.match(row[nxt[1]].text.strip()):
                    close_place = t.final.get(nxt)
            if close_place is None:
                kind = "no_close_in_source"
            elif close_place[0] == "dropped":
                kind = "close_dropped"
            elif close_place[0] == "body" and close_place[1] == li and close_place[2] == j + 1:
                col_texts = {x for x in data_cols[j + 1] if x}
                kind = "adjacent_dedicated" if col_texts <= {")", ")%", "%", ") %"} else "adjacent_shared"
            else:
                kind = "nonadjacent"
            headed = bool([x for x in header_cols.get(j + 1, []) if x and not is_marker(x)]) if kind.startswith("adjacent") else False
            splits.append({"line": li, "col": j, "text": text.strip(), "kind": kind, "close_col_headed": headed,
                           "close_col_shares": sorted({x for x in data_cols[j + 1] if x} - {")", ")%", "%", ") %"})[:4]})
    splits = [s for s in splits if s["kind"] != "no_close_in_source"]
    if splits:
        ev["c8"] = splits
    return ev


def _body_cells(markdown):
    lines = markdown.split("\n")
    sep = next((i for i, line in enumerate(lines) if re.fullmatch(r"\|(?: --- \|)+", line)), None)
    body = lines[sep + 1:] if sep is not None else lines
    out = []
    for line in body:
        inner = line[2:-2] if line.startswith("| ") and line.endswith(" |") else line.strip("|")
        out.append(re.split(r"(?<!\\) \| ", inner))
    return out


def one_row(parser, record):
    """Class 7: how _one_row_table_to_text renders this unit."""
    eff = parser._effective_rows(record.table)
    cells = eff[0] if eff else []
    texts = [render_cell_content(c, base_url=parser.source_url) if c.find("a") else clean_text(c.get_text(" ", strip=True))
             for c in cells]
    info = {"rows": len(eff), "cells": len(texts), "texts": [x[:120] for x in texts if x][:6]}
    if not texts:
        info["branch"] = "empty"
        return info
    first = texts[0]
    if ITEM_HEADER_CELL_RE.match(first):
        nonempty = [x for x in texts[1:] if x]
        info["branch"] = "item"
        info["dropped"] = nonempty[1:]
    elif PART_HEADER_CELL_RE.match(first):
        info["branch"] = "part"
        info["dropped"] = [x for x in texts[1:] if x]
    else:
        info["branch"] = "join"
        info["dropped"] = []
    info["dropped_digits"] = any(re.search(r"\d", x) for x in info["dropped"])
    return info


def example(record, doc_id, ev_key, payload):
    """A compact, minimal example: relevant source rows and the Markdown head."""
    t = record.trace
    fdr = first_data_row(record)
    upto = (fdr + 1) if fdr is not None else min(len(t.g0), 4)
    src = [compact_row(record, r) for r in range(upto) if any(
        cell is not None and not cell.is_spanning and cell.text.strip() for cell in t.g0[r])]
    return {
        "doc": doc_id, "table": record.ordinal, "class": ev_key, "hrc": record.header_rows,
        "g0_shape": [len(t.g0), len(t.g0[0]) if t.g0 else 0], "source_rows": src[:8],
        "markdown": md_excerpt(t.markdown, 3), "detail": payload,
    }


# --- driver ----------------------------------------------------------------------------

def run(args):
    docs, _ = documents(args.edgar_cache)
    if args.only:
        docs = [d for d in docs if d[0] in args.only]
    out_docs = []
    totals = Counter()
    for doc_id, group, raw in docs:
        html = decode_html(raw)[0]
        parser, records = trace_document(html)
        tables = []
        for rec in records:
            entry = {"table": rec.ordinal, "path": rec.path, "hrc": rec.header_rows}
            if rec.path == "tableparser":
                t = rec.trace
                entry["replay_ok"] = t.markdown.strip() == (rec.output or "").strip()
                totals["replay_ok" if entry["replay_ok"] else "replay_mismatch"] += 1
                ev = detect(rec)
                entry["events"] = ev
                entry["examples"] = {}
                for key in ("c1", "c2", "c2_noheader", "c3", "c3_empty", "misaligned", "c4", "c6", "c8"):
                    if key in ev:
                        entry["examples"][key] = example(rec, doc_id, key, ev[key][:4])
                if "c5_fusion_data" in ev or "c5_header_rows_in_body" in ev:
                    entry["examples"]["c5"] = example(rec, doc_id, "c5", ev["c5"])
                entry["size"] = len(t.g0) * (len(t.g0[0]) if t.g0 else 0)
                entry["unknown_short"] = _unknown_short_tokens(rec)
            elif rec.path == "one_row":
                entry["one_row"] = one_row(parser, rec)
                entry["output"] = (rec.output or "")[:300]
            tables.append(entry)
        report = parser.table_report
        findings = {f.ordinal: [list(v) for v in f.missing_values] for f in report.findings if f.missing_values}
        out_docs.append({"id": doc_id, "group": group, "tables": tables, "check1": findings,
                         "tables_checked": report.tables_checked})
        n_tp = sum(1 for e in tables if e["path"] == "tableparser")
        print(f"{doc_id}: units {len(tables)}, TableParser {n_tp}", file=sys.stderr)
    data = {"documents": out_docs, "replay": dict(totals)}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(dict(totals)))


def _unknown_short_tokens(rec):
    """Short all-caps or symbol cells directly left of an amount, not recognised as markers."""
    t = rec.trace
    found = Counter()
    for r, row in enumerate(t.g0):
        for c, cell in enumerate(row):
            if cell is None or cell.is_spanning:
                continue
            text = cell.text.strip()
            if not text or is_marker(text) or text in STRUCTURAL:
                continue
            if not re.fullmatch(r"[A-Z]{2,4}\$?|[^\w\s]{1,2}|[A-Z]{1,3}[^\w\s]", text):
                continue
            nxt = next((row[k].text.strip() for k in range(c + 1, len(row))
                        if row[k] is not None and not row[k].is_spanning and row[k].text.strip()), "")
            if is_value(nxt):
                found[text] += 1
    return dict(found)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--edgar-cache", default="outputs/table-completeness-corpus")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
