"""Show one table's renderer trace: raw grid with spans, each stage, and the Markdown.

    python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/inspect_table.py \
        --edgar-cache outputs/table-completeness-corpus "<document id>" <table ordinal> [--max-rows N]

Research only; nothing is written.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sec2md.encoding import decode_html  # noqa: E402

from corpus import documents, trace_document  # noqa: E402
from trace_merge import output_col  # noqa: E402


def show(record, max_rows):
    t = record.trace
    print(f"== table {record.ordinal}  path={record.path}  header_row_count={record.header_rows}")
    if t is None:
        print(record.output)
        return
    print(f"-- G0 {len(t.g0)} x {len(t.g0[0]) if t.g0 else 0}; kept rows {len(t.rows_keep)}, kept cols {t.cols_keep}")
    for r, row in enumerate(t.g0[:max_rows]):
        cells = []
        for c, cell in enumerate(row):
            if cell is None:
                cells.append(f"{c}:·")
            elif cell.is_spanning:
                cells.append(f"{c}:<")
            else:
                span = f"[{cell.cell.colspan}]" if cell.cell.colspan > 1 else ""
                cells.append(f"{c}:{cell.text[:28]!r}{span}")
        flag = ("H" if record.g0_is_header(r) else " ") + ("D" if record.g0_is_data(r) else " ")
        print(f"   r{r:<3}{flag} " + " ".join(cells))
    print(f"-- structural actions (G1 cols): { {s: sorted(set(a.values())) for s, a in t.actions.items()} }")
    print(f"-- G2 cols -> G1 cols: {t.g2_cols}")
    print(f"-- legacy groups (G3 col -> G2 cols): {t.groups}")
    for d in t.row0_drops:
        print(f"   row0 drop: G3 col {d['group']} absorbs G2 col {d['incoming']}: dropped {d['dropped_text'][:60]!r}"
              f" (kept {d['kept_text'][:40]!r})")
    print(f"-- fused={t.fused}  kept G3 cols={t.kept_cols}")
    for d in t.clean_col_drops:
        print(f"   header-only col dropped: G3 col {d['col']}: {d['header'][:60]!r}")
    print("-- markdown")
    print("\n".join(t.markdown.split("\n")[:max_rows + 2]))
    print(f"-- matches parser output: {t.markdown.strip() == (record.output or '').strip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("ordinal", type=int, nargs="+")
    ap.add_argument("--edgar-cache", default="outputs/table-completeness-corpus")
    ap.add_argument("--max-rows", type=int, default=14)
    args = ap.parse_args()
    docs, _ = documents(args.edgar_cache)
    raw = next(raw for d, _, raw in docs if d == args.doc)
    _, records = trace_document(decode_html(raw)[0])
    for ordinal in args.ordinal:
        show(records[ordinal - 1], args.max_rows)


if __name__ == "__main__":
    main()
