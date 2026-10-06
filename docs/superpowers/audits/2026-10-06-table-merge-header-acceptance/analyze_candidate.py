"""Candidate-side analyses that need the parsed document (research only).

    PYTHONPATH=<worktree>/src python analyze_candidate.py --expect-src <worktree>/src \
        --fixtures-root <checkout> --edgar-cache <cache> --main-dir <main dumps> \
        --candidate-dir <candidate dumps> --merges merges.json.gz --out-dir <dir> [--workers N]

Per document it parses the candidate once in normal mode (`get_pages(include_images=False)`,
checks on), checks that its table outputs equal the candidate dump's, and runs:

- **Alignment (criterion 7).** The candidate's header-alignment checker on unchanged main's
  Markdown and on the candidate's Markdown, unit by unit with the same inputs
  `check_tables` gives `align_table`, keeping every value's outcome (`TableAlignment.outcomes`).
  The summed coverage of each run must equal production's: the candidate dump's
  diagnostics and `check_tables` on main's outputs (both modes). Every value of every data
  row of a unit with a reliable placed grid is listed by (unit ordinal, source row,
  numeric-core column) with its outcome in each run; a value of a skipped table gets that
  run's table key.
- **Header retention (criterion 9)**, on the candidate: every uniquely located value in a
  paired row of an evaluated table has a column header equal to its emitted path's
  rendering; every header-zone cell is represented by some output column rendering an
  emitted path that holds it; every header-only column is rendered.
- **Assignment (criterion 8)**: for each of main's same-header merge steps (merges_main.py),
  the output column of each side's body values, from the candidate renderer's membership and,
  independently, from the value's tokens in its output line, and that column's header
  against the shared emitted path.
- **Split negatives (criterion 11)**: open-parenthesis amounts whose close sits in another
  output cell, in main's and the candidate's Markdown, for every table.
- **Named limitations (criterion 12)**: tables whose first data row is data only through
  bare years beside a label (`Segment | 2025 | 2024`), and tables whose first row with
  origin text is data only through an identifier-column number (T8's caption number).
  Round 2 (spec revision 11): every year run followed by no data row (the new named
  limitation, `Units | 2024 | 2025`), and year runs that are data rows anyway.
- **Moved rows (round 2)**: every source row that main's Markdown holds as a body line and
  the candidate writes into its header line, each checked against the header-like rule by
  an implementation in this file (it never imports table_roles), with content signals for
  review (words in value cells, values with units, identifiers, links). Round 3 (spec
  revision 12): label-only rows are header-like, the second row with origin text is also
  header-like when main's sparse-row fusion applies, and a moved label-only row must not
  be a trailing label-only row of the zone. Round 4 (revision 13): the fusion's n and both
  rows' counts leave out marker-only columns.
- **Rows leaving main's header line (round 2)**: candidate body rows whose texts all sit in
  main's header line but not in the candidate's, and the zone cuts: the row that ends the
  zone before the first data row under this file's implementation of the rule (round 3:
  revision 12's), with the rows holding value-column text it leaves in the body.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import sys
import time
import warnings
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402

_STATE = {}
# trace_merge.OPEN_AMOUNT: an open-parenthesis amount without its close.
OPEN_AMOUNT = re.compile(r"^(?:[A-Z]{0,3}[$€£¥])?\s*\(\s*(?:[A-Z]{0,3}[$€£¥])?\s*\d[\d,]*(?:\.\d+)?\s*%?$")
CLOSE = re.compile(r"^\)\s*%?")
EVALUATED = ("aligned", "misaligned")
# Moved-row signals: exhibit-style identifiers that are not complete numbers ("10.5.22",
# "10.1+", "32.1#", "101.INS"), digits, and a month-day date.
_IDENTIFIER_LABEL = re.compile(r"\d+(?:\.\d+)+[A-Za-z+#*†]*|\d+(?:\.\d+)*[+#*†]+|\d+\.[A-Z]{2,4}")
_DIGIT = re.compile(r"\d")
_DATE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b", re.I)

# --- the header-like rule (revisions 11 and 12), implemented independently of table_roles ----
# Spec "Header zone": past its first row the zone continues only through rows whose label cell
# has no origin text, or holds period text, unit text or a year-like value, through year runs,
# explicit header rows and (revision 12) label-only rows, and through the second row with
# origin text when main's sparse-row fusion applies to the first two. Period text is
# table_completeness._PERIOD_TEXT and unit text starts with xlsx_tables._UNIT_LINE (the spec
# names both); the rest is written here from the spec's words.
_IND_ZERO_WIDTH = str.maketrans(dict.fromkeys("\u200b\u200c\u200d\u2060\ufeff"))
_IND_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_IND_BARE_YEAR = re.compile(r"(?:19|20)\d\d")
_IND_MARK = r"(?:\(\s*(?:\d{1,2}|[A-Za-z])\s*\)|\[\s*\d{1,2}\s*\]|\*{1,2}|[\u2020\u2021])"
_IND_YEAR_LIKE = re.compile(
    rf"(?:19|20)\d\d(?:\s*{_IND_MARK})*"                              # a bare year, footnoted or not
    r"|(?:19|20)\d\d(?:\s*[-\u2013\u2014]\s*|\s+to\s+)(?:19|20)\d\d"     # a range of two bare years
    r"|(?:19|20)\d\d\s*[-\u2013\u2014]\s*\d\d")                         # a fiscal-year range "2024-25"
# Round 5 (spec revision 14), "Complete number": one currency marker of the spec's closed list,
# before or inside the parentheses; digits in thousands groups of three or plain digits, an
# optional decimal or a leading-dot decimal; parentheses and a sign; one trailing "%"; then
# footnote markers, or a second standalone number joined by a dash or "to" (a range).
_IND_CURRENCY = "(?:" + "|".join(re.escape(c) for c in sorted((
    "$", "\u20ac", "\u00a3", "\u00a5", "US$", "NT$", "HK$", "A$", "C$", "S$",
    "USD", "EUR", "GBP", "JPY", "CNY", "RMB", "CHF", "DKK", "SEK", "NOK", "HKD", "TWD", "CAD", "AUD",
    "INR", "KRW", "SGD"), key=len, reverse=True)) + r")\s*"
_IND_DIGITS = r"(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
_IND_SIGN = r"[-+\u2212\u2013]?\s*"
_IND_STANDALONE = (
    rf"(?:{_IND_CURRENCY}\(\s*{_IND_SIGN}{_IND_DIGITS}\s*(?:%\s*\)|\)(?:\s*%)?)"
    rf"|\(\s*(?:{_IND_CURRENCY})?{_IND_SIGN}{_IND_DIGITS}\s*(?:%\s*\)|\)(?:\s*%)?)"
    rf"|(?:{_IND_CURRENCY})?{_IND_SIGN}{_IND_DIGITS}(?:\s*%)?)"
)
_IND_NUMBER = re.compile(
    rf"{_IND_STANDALONE}(?:\s*{_IND_MARK})*"
    rf"|{_IND_STANDALONE}(?:\s*[-\u2013\u2014]\s*|\s+to\s+){_IND_STANDALONE}")
_IND_CAPTION_STARTS = ("dollars in thousands", "dollars in millions", "dollars in billions",
                       "u.s. dollars in thousands", "u.s. dollars in millions", "u.s. dollars in billions",
                       "us dollars in millions", "$ in thousands", "$ in millions", "$ in billions",
                       "thousands of dollars", "millions of dollars", "billions of dollars",
                       "thousands of u.s. dollars", "millions of u.s. dollars", "billions of u.s. dollars")


def ind_visible(text):
    return " ".join(_IND_LINK.sub(r"\1", text or "").translate(_IND_ZERO_WIDTH).replace("\xa0", " ").split())


def ind_unit_text(text):
    from sec2md.xlsx_tables import _UNIT_LINE

    if _UNIT_LINE.search(text):
        return True
    words = " ".join(text.lower().lstrip("( ").split())
    if any(words.startswith(start) and (len(words) == len(start) or not words[len(start)].isalnum())
           for start in _IND_CAPTION_STARTS):
        return True
    return text.replace(" ", "").lower() in ("(unaudited)", "(audited)")


def ind_year_like(text):
    return bool(_IND_YEAR_LIKE.fullmatch(text))


def ind_rows(placed):
    """Per placed row, its origin cells as (column, visible text, th) with text."""
    from sec2md.table_parser import extract_cell_text

    rows = []
    for r, row in enumerate(placed[1]):
        cells, seen = [], set()
        for k, slot in enumerate(row):
            if slot is None or id(slot) in seen or (slot.row, slot.column) != (r, k):
                continue
            seen.add(id(slot))
            text = ind_visible(extract_cell_text(slot.td))
            if text:
                cells.append((k, text, slot.is_header))
        rows.append(cells)
    return rows


def ind_label_column(rows):
    columns = [cells[0][0] for cells in rows if cells]
    return min(columns) if columns else None


def ind_year_run(cells, label):
    numbers = [t for k, t, _ in cells if k != label and (ind_year_like(t) or _IND_NUMBER.fullmatch(t))]
    if len(numbers) < 2 or not all(_IND_BARE_YEAR.fullmatch(t) for t in numbers):
        return False
    years = [int(t) for t in numbers]
    return all(abs(b - a) <= 1 for a, b in zip(years, years[1:]))


def ind_label_only(cells, label):
    """Revision 12: origin text in the label column only."""
    return bool(cells) and all(k == label for k, _, _ in cells)


# Revision 13: the spec's closed currency list ("Currency markers") and the split-negative
# and percent markers; a column whose every origin text is one of them is marker-only.
_IND_MARKERS = frozenset({
    "$", "\u20ac", "\u00a3", "\u00a5", "US$", "NT$", "HK$", "A$", "C$", "S$",
    "USD", "EUR", "GBP", "JPY", "CNY", "RMB", "CHF", "DKK", "SEK", "NOK", "HKD", "TWD", "CAD", "AUD",
    "INR", "KRW", "SGD", "%", ")", ")%", "(",
})


def ind_fuses_like_main(rows, first, second):
    """Revisions 12 and 13: main's sparse-row fusion of the first two rows with origin text.
    n is the number of columns holding origin text, leaving out marker-only columns (every
    origin text a currency marker, "%", ")", ")%" or "("); the first row has no origin text
    in at least max(2, n // 2) of the counted columns and the second row has origin text in
    at least max(2, n // 2) of them."""
    texts = {}
    for cells in rows:
        for k, t, _ in cells:
            texts.setdefault(k, []).append(t.replace(" ", ""))
    counted = {k for k, held in texts.items() if not all(t in _IND_MARKERS for t in held)}
    threshold = max(2, len(counted) // 2)
    first_count = sum(k in counted for k, _, _ in rows[first])
    second_count = sum(k in counted for k, _, _ in rows[second])
    return len(counted) - first_count >= threshold and second_count >= threshold


def ind_header_like(cells, label):
    """(header-like?, the reasons that hold) for one row under revision 12's per-row rule
    (the table-level sparse-row fusion is ind_fuses_like_main)."""
    from sec2md.table_completeness import _PERIOD_TEXT

    label_text = next((t for k, t, _ in cells if k == label), "")
    reasons = []
    if not label_text:
        reasons.append("label_empty")
    else:
        if _PERIOD_TEXT.search(label_text):
            reasons.append("label_period_text")
        if ind_unit_text(label_text):
            reasons.append("label_unit_text")
        if ind_year_like(label_text):
            reasons.append("label_year_like")
    if ind_year_run(cells, label):
        reasons.append("year_run")
    if cells and all(th for _, _, th in cells):
        reasons.append("explicit_header_row")
    if ind_label_only(cells, label):
        reasons.append("label_only")
    return bool(reasons), reasons


def ind_zone_row(rows, label, text_rows, row):
    """(header-like past the first row?, reasons) under revision 12, sparse-row fusion
    included for the second row with origin text."""
    passes, reasons = ind_header_like(rows[row], label)
    if len(text_rows) > 1 and row == text_rows[1] and ind_fuses_like_main(rows, text_rows[0], row):
        reasons = reasons + ["sparse_row_fusion"]
    return bool(reasons), reasons


def _init(args):
    warnings.filterwarnings("ignore")
    import logging

    logging.disable(logging.CRITICAL)
    _STATE["args"] = args
    merges = acc_common.read_json_gz(args.merges)
    _STATE["merges"] = {d["id"]: d for d in merges["documents"]}


def parse(html):
    import sec2md.parser as parser_module
    from sec2md.parser import Parser

    registry = []
    base = parser_module.TableParser

    class Recording(base):
        def __init__(self, table_element, *, base_url=None):
            super().__init__(table_element, base_url=base_url)
            registry.append((table_element, self))

    parser_module.TableParser = Recording
    try:
        parser = Parser(html, capture_tables=False)
        pages = parser.get_pages(include_images=False)
    finally:
        parser_module.TableParser = base
    instances = {}
    for element, instance in registry:
        instances.setdefault(id(element), []).append((element, instance))
    return parser, pages, instances


def own_instance(instances, table):
    found = [instance for element, instance in instances.get(id(table), []) if element is table]
    return found[-1] if found else None


def table_key(segment, grid, analysis):
    """The table-level skip key a run gives a unit (align_table's precedence)."""
    from sec2md.table_alignment import parse_output

    if not segment.strip():
        return "table_no_output"
    if parse_output(segment) is None:
        return "table_no_separator"
    if grid is None:
        return "table_unreliable_grid"
    if not analysis.roles.header_rows:
        return "table_no_header"
    if not analysis.roles.data_rows:
        return "table_no_data"
    return None


def split_negatives(segment):
    """Open-parenthesis amounts whose close is the next non-empty cell of the line."""
    from sec2md.table_alignment import parse_output

    output = parse_output(segment) if segment else None
    if output is None:
        return []
    found = []
    for line, cells in enumerate(output.cells):
        for index, text in enumerate(cells):
            if not OPEN_AMOUNT.match(text.strip()):
                continue
            following = next((t for t in cells[index + 1:] if t.strip()), "")
            if CLOSE.match(following.strip()):
                found.append({"line": line, "cell": index, "text": text.strip(), "close": following.strip(),
                              "row": output.body[line][:300]})
    return found


def audit_pairing(analysis, output, key_of_row):
    """Source data row -> output body line, in order: the next line with the row's label key
    holding every token of the row's values (a forward match; duplicates stay in order)."""
    from sec2md.table_alignment import cell_tokens

    line_tokens = []
    for cells in output.cells:
        total = Counter()
        for counter in cell_tokens(cells):
            total.update(counter)
        line_tokens.append(total)
    pairs, pointer = {}, 0
    for row in analysis.roles.data_rows:
        key = key_of_row.get(row, "")
        need = Counter(token for value in analysis.values[row] for token in value.tokens)
        for line in range(pointer, len(output.cells)):
            if output.keys[line] == key and not (need - line_tokens[line]):
                pairs[row] = line
                pointer = line + 1
                break
    return pairs


def analyze_unit(ordinal, table, inputs, main_segment, candidate_segment, instance, merges_steps, state):
    from sec2md.table_alignment import (
        SourceAnalysis,
        align_table,
        cell_tokens,
        label_text_key,
        locate,
        parse_output,
        source_grid,
    )
    from sec2md.table_roles import _slot_text, is_complete_number, is_nil_value, is_year_like, visible_text

    all_rows, grid_hidden, row_keys, key_counts, placed = inputs
    grid = source_grid(placed)
    analysis = SourceAnalysis(grid) if grid is not None else None
    runs = {}
    for name, segment in (("main", main_segment), ("candidate", candidate_segment)):
        aligned = align_table(table, all_rows, grid_hidden, segment, row_keys, key_counts, placement=lambda: placed)
        runs[name] = aligned
        state["coverage"][name].update(aligned.coverage)
    out = {"unit": ordinal}
    state["units"].append({
        "unit": ordinal,
        "hidden_tds": sum(1 for td in table.find_all(["td", "th"]) if id(td) in grid_hidden),
        "hidden_trs": sum(1 for tr in table.find_all("tr") if id(tr) in grid_hidden),
        "nested": table.find("table") is not None,
        "grid": grid is not None,
        "header_rows": len(analysis.roles.header_rows) if analysis is not None else None,
        "header_row_list": list(analysis.roles.header_rows) if analysis is not None else None,
        "data_rows": len(analysis.roles.data_rows) if analysis is not None else None,
        "changed": main_segment != candidate_segment,
    })

    # Per-value identities (criterion 7).
    outputs = {"main": parse_output(main_segment) if main_segment.strip() else None,
               "candidate": parse_output(candidate_segment) if candidate_segment.strip() else None}
    if analysis is not None:
        keys = {name: table_key(seg, grid, analysis) for name, seg in
                (("main", main_segment), ("candidate", candidate_segment))}
        found = {name: {(o.row, o.column): o for o in runs[name].outcomes} for name in runs}
        for row in analysis.roles.data_rows:
            for value in analysis.values[row]:
                identity = (row, value.column)
                record = [ordinal, row, value.column, value.text]
                for name in ("main", "candidate"):
                    outcome = found[name].get(identity)
                    if outcome is None:
                        record += [keys[name] or "unlisted", None, None]
                    else:
                        record += [outcome.outcome, outcome.line, outcome.output_column]
                state["values"].append(record)
                main_outcome, candidate_outcome = record[4], record[7]
                if main_outcome in EVALUATED and candidate_outcome not in EVALUATED:
                    main_out, cand_out = outputs["main"], outputs["candidate"]
                    loss = {"unit": ordinal, "row": row, "column": value.column, "text": value.text,
                            "main": main_outcome, "candidate": candidate_outcome,
                            "expected": analysis.expectation(value.column).rendering(),
                            "main_header": main_out.header_text(record[6]) if main_out else None,
                            "main_line": main_out.body[record[5]][:400] if main_out else None,
                            "candidate_header_line": (" | ".join(cand_out.header))[:400] if cand_out else None,
                            "candidate_line": (cand_out.body[record[8]][:400]
                                               if cand_out and record[8] is not None else None),
                            "source_label": next((s.text for s in analysis.origin[row] if s is not None and s.text),
                                                 ""),
                            "row_key": row_keys.get(id(grid.row_trs[row]), "")}
                    state["losses"].append(loss)

    # Header retention (criterion 9), on the candidate's Markdown.
    cand_out = outputs["candidate"]
    if analysis is not None and cand_out is not None and analysis.roles.header_rows:
        retention = state["retention"]
        header_keys = {label_text_key(h) for h in cand_out.header}
        evaluated_table = bool(analysis.roles.data_rows)
        if evaluated_table:
            for o in runs["candidate"].outcomes:
                column = o.output_column
                if o.outcome == "value_no_discriminating_header" and o.line is not None:
                    value = next(v for v in analysis.values[o.row] if v.column == o.column)
                    cells = locate(value.tokens, cell_tokens(cand_out.cells[o.line]))
                    column = cells[0] if len(cells) == 1 else None
                if column is None:
                    continue
                expectation = analysis.expectation(o.column)
                expected = expectation.rendering()
                header = cand_out.header_text(column)
                retention["values"] += 1
                word_only = not re.search(r"\d", expected)
                literal = any(" — " in entry.text for entry in expectation.path)
                retention["word_only_values"] += word_only
                retention["literal_separator_values"] += literal
                retention["no_discriminating_values"] += o.outcome == "value_no_discriminating_header"
                if label_text_key(header) == label_text_key(expected):
                    retention["values_equal"] += 1
                    retention["values_exact_case"] += " ".join(visible_text(header).split()) == expected
                else:
                    retention["value_mismatches"].append({
                        "unit": ordinal, "row": o.row, "column": o.column, "outcome": o.outcome,
                        "header": header, "expected": expected, "word_only": word_only, "literal": literal})
        for cell in analysis.header_cells:
            retention["header_cells"] += 1
            retention["literal_separator_cells"] += " — " in cell.text
            renderings = {label_text_key(analysis.expectation(k).rendering()) for k in cell.columns()
                          if k < grid.width}
            if renderings & header_keys:
                retention["header_cells_represented"] += 1
            else:
                retention["header_cell_misses"].append({
                    "unit": ordinal, "row": cell.row, "column": cell.column, "text": cell.text[:200],
                    "renderings": sorted(renderings)[:6], "header": [h[:120] for h in cand_out.header]})
        header_rows = set(analysis.roles.header_rows)
        origin = analysis.origin
        for k in range(grid.width):
            in_header = any(origin[r][k] is not None and visible_text(_slot_text(origin[r][k]))
                            for r in header_rows)
            in_body = any(origin[r][k] is not None and visible_text(_slot_text(origin[r][k]))
                          for r in range(grid.height) if r not in header_rows)
            if not in_header or in_body:
                continue
            retention["header_only_columns"] += 1
            expected = analysis.expectation(k).rendering()
            if label_text_key(expected) in header_keys:
                retention["header_only_rendered"] += 1
            else:
                retention["header_only_misses"].append({"unit": ordinal, "column": k, "expected": expected,
                                                        "header": [h[:120] for h in cand_out.header]})

    # Assignment audit (criterion 8).
    if merges_steps:
        state["assignment"].extend(assignment_audit(ordinal, table, placed, grid, analysis, instance,
                                                    cand_out, row_keys, merges_steps))

    # Split negatives (criterion 11): every table, both runs.
    for name, segment in (("main", main_segment), ("candidate", candidate_segment)):
        found_splits = split_negatives(segment)
        if found_splits:
            state["splits"][name][str(ordinal)] = found_splits

    # Rows main wrote as body lines that the candidate writes into the header line (R0/R5),
    # and the reverse: rows main had in its header line that the candidate keeps in its body.
    main_out = outputs["main"]
    if analysis is not None and main_out is not None and cand_out is not None:
        from sec2md.table_completeness import placed_header_rows

        snapshot_header_rows = placed_header_rows(placed)
        if analysis.roles.header_rows:
            for item in moved_rows(ordinal, analysis, main_out, cand_out, placed):
                item["snapshot_header_rows"] = snapshot_header_rows
                item["beyond_snapshot_header"] = item["row"] >= snapshot_header_rows
                state["moved"].append(item)
        state["departures"].extend(departures(ordinal, analysis, main_out, cand_out))
    if analysis is not None and placed is not None:
        cut = zone_cut(ordinal, analysis, placed, candidate_segment)
        if cut is not None:
            state["zone_cuts"].append(cut)

    # Named limitations (criterion 12).
    if analysis is not None and analysis.roles.data_rows:
        roles = analysis.roles
        first = roles.data_rows[0]
        label = roles.label_column
        texts = [(k, visible_text(_slot_text(slot))) for k, slot in enumerate(analysis.origin[first])
                 if slot is not None and visible_text(_slot_text(slot))]
        others = [(k, t) for k, t in texts if k != label]
        label_text = next((t for k, t in texts if k == label), "")
        head = [" | ".join(visible_text(_slot_text(s)) for s in analysis.origin[r] if s is not None
                           and visible_text(_slot_text(s)))[:200] for r in range(min(grid.height, first + 2))]
        if (label_text and others and all(is_year_like(t) for _, t in others)
                and not any(is_complete_number(t) or is_nil_value(t) for _, t in others)):
            state["limitations"]["years_row"].append({
                "unit": ordinal, "row": first, "label": label_text, "years": [t for _, t in others],
                "header_zone_empty": not roles.header_rows, "header_rows": list(roles.header_rows),
                "rows": head, "candidate_head": candidate_segment.split("\n")[:4]})
        # Round 2: year runs (independent implementation) followed by no data row, and year
        # runs that are data rows anyway (a nil value or an identifier-column label number).
        ind = ind_rows(placed)
        ind_label = ind_label_column(ind)
        for r in range(grid.height):
            if not ind[r] or not ind_year_run(ind[r], ind_label):
                continue
            entry = {"unit": ordinal, "row": r, "texts": [t[:60] for _, t, _ in ind[r]],
                     "header_row": r in roles.header_rows, "data_row": r in roles.data_rows,
                     "rows": head, "candidate_head": candidate_segment.split("\n")[:4]}
            if not any(d > r for d in roles.data_rows):
                state["limitations"]["year_run_no_data_after"].append(entry)
            if r in roles.data_rows:
                state["limitations"]["year_run_data_row"].append(entry)
        text_rows = [r for r in range(grid.height) if r not in roles.empty_rows]
        if (roles.identifier_column and text_rows and first == text_rows[0]
                and not any(is_complete_number(t) or is_nil_value(t) for _, t in others)):
            state["limitations"]["identifier_caption"].append({
                "unit": ordinal, "row": first, "label": label_text, "others": [t[:80] for _, t in others],
                "rows": head, "candidate_head": candidate_segment.split("\n")[:4]})
    return out


def moved_rows(ordinal, analysis, main_out, cand_out, placed):
    """Header-zone rows of the candidate that main's Markdown holds as a body line.

    A row matches a body line when its non-empty visible texts, joined with spaces, equal
    the line's non-empty cells joined the same way. Each moved row is checked against
    the header-like rule with this file's implementation (round 3: revision 12): the zone
    starts at the first row with origin text; every later zone row up to the moved one must
    be header-like (the second row also through main's sparse-row fusion); a moved label-only
    row must have a zone row below it that is not label-only (trailing label-only rows leave
    the zone). Content signals mark rows for review.
    """
    from sec2md.table_roles import _slot_text, visible_text

    def joined(texts):
        return " ".join(" ".join(t.split()) for t in texts if t.strip())

    main_lines = {joined(cells) for cells in main_out.cells}
    cand_lines = {joined(cells) for cells in cand_out.cells}
    label = analysis.roles.label_column
    rows = ind_rows(placed)
    ind_label = ind_label_column(rows)
    text_rows = [r for r, cells in enumerate(rows) if cells]
    data_labels = {" ".join(visible_text(_slot_text(analysis.origin[r][label])).split()).casefold()
                   for r in analysis.roles.data_rows
                   if label is not None and analysis.origin[r][label] is not None}
    data_labels.discard("")
    header_rows = list(analysis.roles.header_rows)
    found = []
    for row in header_rows:
        texts = [visible_text(_slot_text(slot)) for slot in analysis.origin[row] if slot is not None]
        texts = [t for t in texts if t]
        key = joined(texts)
        if not key or key not in main_lines or key in cand_lines:
            continue
        first = row == header_rows[0]
        passes, reasons = ind_zone_row(rows, ind_label, text_rows, row)
        chain = [r for r in header_rows[1:header_rows.index(row) + 1]]
        chain_ok = all(ind_zone_row(rows, ind_label, text_rows, r)[0] for r in chain)
        starts_ok = bool(text_rows) and header_rows[0] == text_rows[0]
        trailing_ok = not ind_label_only(rows[row], ind_label) or any(
            not ind_label_only(rows[r], ind_label) for r in header_rows if r > row)
        label_text = next((t for k, t, _ in rows[row] if k == ind_label), "")
        values = [t for k, t, _ in rows[row] if k != ind_label]
        cells = [cell for cell in dict.fromkeys(analysis.grid.slots[row]) if cell is not None and cell.row == row]
        signals = []
        if any(re.search(r"[A-Za-z]{2,}", v) and not _DATE.search(v) and not ind_unit_text(v)
               and not re.fullmatch(r"(?:[A-Z]{2,3}|[A-Z]?\$|NT\$|US\$|HK\$|RMB)", v.strip()) for v in values):
            signals.append("words_in_value_cells")
        if any(re.fullmatch(r"[$(]*\s*[\d.,]+\s*\)?\s*(?:years?|months?|days?|weeks?|x|times|shares?|million|billion)s?\b.*",
                            v, re.I) for v in values):
            signals.append("value_with_unit")
        if label_text and _IDENTIFIER_LABEL.fullmatch(label_text.strip()):
            signals.append("identifier_label")
        if any(cell.links for cell in cells):
            signals.append("link")
        if label_text and " ".join(label_text.split()).casefold() in data_labels:
            signals.append("label_repeats_in_data_rows")
        found.append({"unit": ordinal, "row": row, "texts": [t[:120] for t in texts],
                      "label": label_text[:120], "values": [v[:80] for v in values],
                      "first_header_row": first, "header_like": passes, "reasons": reasons,
                      "chain_ok": chain_ok, "starts_ok": starts_ok, "trailing_ok": trailing_ok,
                      "rule_ok": (first or passes) and chain_ok and starts_ok and trailing_ok,
                      "sparse_row_fusion_only": reasons == ["sparse_row_fusion"],
                      "signals": signals})
    return found


def departures(ordinal, analysis, main_out, cand_out):
    """Candidate body rows whose every non-empty text sits in main's header line and not in
    the candidate's (spaces removed, case folded)."""
    from sec2md.table_roles import _slot_text, visible_text

    def squash(text):
        return re.sub(r"\s+", "", text).casefold()

    main_header = squash(" ".join(main_out.header))
    cand_header = squash(" ".join(cand_out.header))
    header = set(analysis.roles.header_rows)
    data = set(analysis.roles.data_rows)
    found = []
    for row in range(analysis.grid.height):
        if row in header or row in analysis.roles.empty_rows:
            continue
        texts = [visible_text(_slot_text(slot)) for slot in analysis.origin[row] if slot is not None]
        texts = [squash(t) for t in texts if t]
        if not texts or not main_header:
            continue
        if all(t in main_header for t in texts) and not all(t in cand_header for t in texts):
            found.append({"unit": ordinal, "row": row, "data_row": row in data,
                          "texts": [visible_text(_slot_text(s))[:100] for s in analysis.origin[row]
                                    if s is not None and visible_text(_slot_text(s))],
                          "label_only": all(slot is None or not visible_text(_slot_text(slot))
                                            for k, slot in enumerate(analysis.origin[row])
                                            if k != analysis.roles.label_column),
                          "main_header": [h[:100] for h in main_out.header][:8],
                          "candidate_header": [h[:100] for h in cand_out.header][:8]})
    return found


def zone_cut(ordinal, analysis, placed, candidate_segment):
    """The row that ends the candidate's header zone before the first data row under this
    file's implementation of the rule (round 3: revision 12, so a label-only row never cuts),
    with the rows holding value-column text it leaves in the body. consistent: the candidate's
    R0 zone ends above the cut row."""
    roles = analysis.roles
    if not roles.data_rows:
        return None
    rows = ind_rows(placed)
    label = ind_label_column(rows)
    candidates = [r for r in range(roles.data_rows[0]) if rows[r]]
    for position, r in enumerate(candidates[1:], start=1):
        if ind_zone_row(rows, label, candidates, r)[0]:
            continue
        label_only = ind_label_only(rows[r], label)
        later = [q for q in candidates[position + 1:] if any(k != label for k, _, _ in rows[q])]
        return {"unit": ordinal, "cut_row": r, "cut_label_only": label_only,
                "value_text_rows_after": later, "header_rows": list(roles.header_rows),
                "consistent": all(h < r for h in roles.header_rows),
                "stacked_title": bool(label_only and later),
                "rows": [" | ".join(t for _, t, _ in rows[q])[:150] for q in candidates[:position + 1 + len(later)]],
                "candidate_head": candidate_segment.split("\n")[:3]}
    return None


def assignment_audit(ordinal, table, placed, grid, analysis, instance, output, row_keys, steps):
    from sec2md.table_alignment import cell_tokens, label_text_key, locate
    from sec2md.table_roles import visible_text

    results = []
    trs = [tr for tr in table.find_all("tr") if tr.find_all(["td", "th"])]
    td_position = {}
    if placed is not None:
        for row in placed[1]:
            for slot in row:
                if slot is not None:
                    td_position[id(slot.td)] = (slot.row, slot.column)
    where, final, header_text = {}, {}, None
    if instance is not None:
        for index, column in enumerate(instance.columns):
            for slot in column.slots:
                for cell in slot.cells:
                    where[id(cell)] = index
        cells_by_node = {id(cell.node): cell for row in instance.cells for cell in row}
        matrix = instance.to_matrix()
        headers, data = instance._process_headers(matrix)
        final = {column: n for n, column in enumerate(instance._kept_columns(headers, data))}
    pairs = {}
    if analysis is not None and output is not None:
        key_of_row = {row: row_keys.get(id(grid.row_trs[row]), "") for row in analysis.roles.data_rows}
        pairs = audit_pairing(analysis, output, key_of_row)
    for step in steps:
        values = []
        for side in ("a", "b"):
            for item in step[side]:
                r, k = item["cell"]
                td = trs[r].find_all(["td", "th"])[k]
                cell = cells_by_node.get(id(td)) if instance is not None else None
                member = where.get(id(cell)) if cell is not None else None
                j_member = final.get(member) if member is not None else None
                position = td_position.get(id(td))
                j_text, text_status, path = None, "unplaced", None
                if position is not None and analysis is not None:
                    row, column = position
                    source_value = next((v for v in analysis.values.get(row, ()) if v.column == column), None)
                    path = analysis.expectation(column).rendering()
                    if source_value is None:
                        text_status = "not_a_value"
                    elif not source_value.tokens:
                        text_status = "nil"
                    elif row not in pairs:
                        text_status = "unpaired"
                    else:
                        located = locate(source_value.tokens, cell_tokens(output.cells[pairs[row]]))
                        if len(located) == 1:
                            j_text, text_status = located[0], "located"
                        else:
                            text_status = "ambiguous" if located else "missing"
                values.append({"side": side, "text": item["text"], "member": j_member, "text_column": j_text,
                               "text_status": text_status, "path": path, "position": position})
        members = {v["member"] for v in values}
        paths = {v["path"] for v in values if v["path"] is not None}
        column = next(iter(members)) if len(members) == 1 else None
        header = output.header_text(column) if output is not None and column is not None else None
        contradictions = [v for v in values if v["text_status"] == "located" and v["text_column"] != v["member"]]
        shared = next(iter(paths)) if len(paths) == 1 else None
        result = {
            "unit": ordinal, "step": step["step"],
            "same_column": column is not None,
            "values": len(values),
            "text_located": sum(v["text_status"] == "located" for v in values),
            "text_status": dict(Counter(v["text_status"] for v in values)),
            "contradictions": len(contradictions),
            "shared_path": shared, "paths": sorted(paths),
            "header": header,
            "header_matches": (header is not None and shared is not None
                               and label_text_key(header) == label_text_key(shared)),
            "header_exact": (header is not None and shared is not None
                             and " ".join(visible_text(header).split()) == shared),
        }
        result["ok"] = (result["same_column"] and result["header_matches"] and not contradictions)
        if not result["ok"]:
            result["detail"] = values
            result["header_texts"] = step["header_texts"]
        results.append(result)
    return results


def unit_inputs(table, hidden, grid_hidden):
    """align_table's inputs as check_tables builds them, and the shared placement."""
    from sec2md.table_completeness import _direct_cells, cell_text, place_unit, row_label_key, unit_rows

    all_rows = unit_rows(table)
    rows = [row for row in all_rows if id(row.tr) not in hidden]
    row_keys = {id(row.tr): row_label_key([cell_text(c, hidden) for c in _direct_cells(row.tr) if id(c) not in hidden])
                for row in rows if row.own}
    key_counts = Counter(key for key in row_keys.values() if key)
    return all_rows, grid_hidden, row_keys, key_counts, place_unit(table, all_rows, grid_hidden)


def work(item):
    doc_id, group, raw = item
    from sec2md.encoding import decode_html
    from sec2md.table_completeness import check_tables, hidden_sets

    args = _STATE["args"]
    started = time.perf_counter()
    name = acc_common.safe_name(doc_id)
    main = acc_common.read_json_gz(os.path.join(args.main_dir, name))
    candidate = acc_common.read_json_gz(os.path.join(args.candidate_dir, name))
    parser, pages, instances = parse(decode_html(raw)[0])
    soup = parser.soup
    outermost, hidden, grid_hidden = hidden_sets(soup)
    units = [t for t in outermost if id(t) not in hidden]
    candidate_outputs = [parser.table_outputs.get(id(t)) for t in units]
    main_normal = [u["output"] for u in main["modes"]["normal"]["units"]]
    main_capture = [u["output"] for u in main["modes"]["capture"]["units"]]
    if len(units) != len(main_normal):
        raise RuntimeError(f"{doc_id}: {len(units)} units, main has {len(main_normal)}")
    deterministic = candidate_outputs == [u["output"] for u in candidate["modes"]["normal"]["units"]]

    production = {}
    for label, outputs in (("main_normal", main_normal), ("main_capture", main_capture)):
        report = check_tables(soup, {id(t): o for t, o in zip(units, outputs) if o is not None},
                              parser._table_pages, parser._snapshot_ordinals)
        production[label] = {"coverage": [list(i) for i in report.alignment_coverage],
                             "findings": list(report.alignment)}
    state = {"coverage": {"main": Counter(), "candidate": Counter()}, "values": [], "losses": [],
             "retention": Counter(value_mismatches=[], header_cell_misses=[], header_only_misses=[]),
             "assignment": [], "splits": {"main": {}, "candidate": {}}, "units": [], "moved": [],
             "departures": [], "zone_cuts": [],
             "limitations": {"years_row": [], "identifier_caption": [], "year_run_no_data_after": [],
                             "year_run_data_row": []}}
    for key in ("value_mismatches", "header_cell_misses", "header_only_misses"):
        state["retention"][key] = []
    merges = {t["table"]: t["steps"] for t in _STATE["merges"].get(doc_id, {}).get("tables", [])}
    for ordinal, table in enumerate(units, 1):
        analyze_unit(ordinal, table, unit_inputs(table, hidden, grid_hidden), main_normal[ordinal - 1] or "",
                     candidate_outputs[ordinal - 1] or "", own_instance(instances, table),
                     merges.get(ordinal), state)
    from sec2md.table_alignment import coverage_items

    retention = dict(state["retention"])
    data = {
        "id": doc_id, "deterministic_outputs": deterministic,
        "coverage": {name: [list(i) for i in coverage_items(c)] for name, c in state["coverage"].items()},
        "production": production,
        "candidate_dump_coverage": {mode: candidate["modes"][mode]["alignment_coverage"] for mode in acc_common.MODES},
        "candidate_dump_findings": {mode: candidate["modes"][mode]["alignment"] for mode in acc_common.MODES},
        "values": state["values"], "losses": state["losses"], "retention": retention,
        "assignment": state["assignment"], "splits": state["splits"], "limitations": state["limitations"],
        "units": state["units"], "moved": state["moved"], "departures": state["departures"],
        "zone_cuts": state["zone_cuts"],
        "seconds": round(time.perf_counter() - started, 2),
    }
    acc_common.write_json_gz(os.path.join(args.out_dir, name), data)
    return doc_id, data["seconds"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--expect-src", required=True)
    ap.add_argument("--fixtures-root", required=True)
    ap.add_argument("--edgar-cache", required=True)
    ap.add_argument("--main-dir", required=True)
    ap.add_argument("--candidate-dir", required=True)
    ap.add_argument("--merges", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    location = acc_common.sec2md_location(args.expect_src)
    started = time.perf_counter()
    docs, _ = acc_common.load_documents(args.edgar_cache, args.fixtures_root)
    hashes = acc_common.verify_hashes(docs)
    if args.only:
        docs = [d for d in docs if d[0] in args.only]
    order = sorted(docs, key=lambda d: -len(d[2]))
    times = {}
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(args.workers, initializer=_init, initargs=(args,)) as pool:
        for doc_id, seconds in pool.imap_unordered(work, order):
            times[doc_id] = seconds
            print(f"{doc_id}: {seconds:.1f}s", file=sys.stderr, flush=True)
    run = {"sec2md_file": location, "hash_check_ok": hashes["ok"], "documents": [d[0] for d in docs],
           "document_seconds": times, "wall_seconds": round(time.perf_counter() - started, 1)}
    with open(os.path.join(args.out_dir, "_run.json"), "w", encoding="utf-8") as handle:
        json.dump(run, handle, indent=1)
    print(json.dumps({k: run[k] for k in ("sec2md_file", "hash_check_ok", "wall_seconds")}))


if __name__ == "__main__":
    main()
