"""Show one unit: the checker's placed grid with R0 roles, the candidate renderer's cleaned
source grid with its roles and output columns, and the Markdown (research only).

    PYTHONPATH=<side>/src python inspect_unit.py --fixtures-root <checkout> --edgar-cache <cache> <document id> <unit>...

Works on either side; the renderer details print only for the candidate (it has roles and
membership). The Markdown is the unit's output in normal mode.
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acc_common  # noqa: E402


def compact(cells):
    out, empties = [], 0
    for text, span in cells:
        if not text and span == 1:
            empties += 1
            continue
        if empties:
            out.append(f"·×{empties}" if empties > 1 else "·")
            empties = 0
        out.append((text[:60] + ("…" if len(text) > 60 else "")) + (f" [cs{span}]" if span > 1 else ""))
    if empties:
        out.append(f"·×{empties}" if empties > 1 else "·")
    return " | ".join(out)


def main():
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures-root", required=True)
    ap.add_argument("--edgar-cache", required=True)
    ap.add_argument("document")
    ap.add_argument("units", nargs="+", type=int)
    ap.add_argument("--lines", type=int, default=12)
    args = ap.parse_args()
    docs, _ = acc_common.load_documents(args.edgar_cache, args.fixtures_root)
    raw = next(raw for d, _, raw in docs if d == args.document)
    import sec2md.parser as parser_module
    from sec2md.encoding import decode_html
    from sec2md.table_completeness import hidden_sets, place_unit, unit_rows

    registry = []
    base = parser_module.TableParser

    class Recording(base):
        def __init__(self, table_element, *, base_url=None):
            super().__init__(table_element, base_url=base_url)
            registry.append((table_element, self))

    parser_module.TableParser = Recording
    try:
        parser = parser_module.Parser(decode_html(raw)[0])
        parser.get_pages(include_images=False)
    finally:
        parser_module.TableParser = base
    outermost, hidden, grid_hidden = hidden_sets(parser.soup)
    units = [t for t in outermost if id(t) not in hidden]
    for ordinal in args.units:
        table = units[ordinal - 1]
        print(f"===== {args.document} unit {ordinal}")
        placed = place_unit(table, unit_rows(table), grid_hidden)
        try:
            from sec2md.table_alignment import SourceAnalysis, source_grid

            grid = source_grid(placed)
            analysis = SourceAnalysis(grid) if grid is not None else None
        except ImportError:
            grid = analysis = None
        if grid is None:
            print("-- checker: placement unreliable or not available")
        else:
            roles = analysis.roles
            print(f"-- checker placed grid {grid.height}x{grid.width}; label column {roles.label_column}; "
                  f"identifier {roles.identifier_column}; header rows {roles.header_rows}; "
                  f"first data rows {roles.data_rows[:3]}")
            for r, row in enumerate(grid.slots):
                cells = [(c.text if c is not None and (c.row, c.column) == (r, k) else None, c.colspan if c is not None else 1)
                         for k, c in enumerate(row)]
                cells = [(t, s) for t, s in cells if t is not None or True]
                shown = []
                k = 0
                while k < len(row):
                    c = row[k]
                    if c is not None and (c.row, c.column) == (r, k):
                        shown.append((c.text, c.colspan))
                        k += c.colspan
                    elif c is not None:
                        shown.append(("^", 1))
                        k += 1
                    else:
                        shown.append(("", 1))
                        k += 1
                role = "H" if r in roles.header_rows else ("D" if r in roles.data_rows else ".")
                print(f"  {role} r{r}: {compact(shown)}")
        found = [inst for el, inst in registry if el is table]
        if found and hasattr(found[-1], "roles"):
            inst = found[-1]
            print(f"-- renderer source grid {len(inst.source_grid)}x{len(inst.source_grid[0]) if inst.source_grid else 0};"
                  f" header rows {inst.roles.header_rows}; data rows {inst.roles.data_rows[:3]}")
            for r, row in enumerate(inst.source_grid):
                shown = [("^" if slot is not None and slot.is_spanning else (slot.text if slot is not None else "∅"))[:40]
                         for slot in row]
                role = "H" if r in inst.roles.header_rows else ("D" if r in inst.roles.data_rows else ".")
                print(f"  {role} g{r}: " + " | ".join(shown))
            for i, column in enumerate(inst.columns):
                print(f"   out col {i}: owners {column.owners} markers {column.markers}")
        output = parser.table_outputs.get(id(table))
        print("-- output")
        print("\n".join((output or "(none)").split("\n")[: args.lines]))


if __name__ == "__main__":
    main()
