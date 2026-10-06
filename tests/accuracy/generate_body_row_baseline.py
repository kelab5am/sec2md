"""Record which source rows with visible text a baseline renderer's Markdown renders as body rows.

The accuracy suite's body-row guard (spec 2026-10-05, Acceptance, "Body rows must not drop")
compares the candidate against this record, so the normal test run needs no second checkout.
The record was generated from the commit before the table merge and header rules work:

    git archive c674828 | tar -x -C <scratch>/main-c674828
    python tests/accuracy/generate_body_row_baseline.py --src <scratch>/main-c674828/src

The baseline's ``src`` renders the fixtures; this checkout's ``tests/accuracy`` measures them,
so both sides of the guard use the same row identities and matching rule. From ``c674828`` it
records 2,485 rows across the 7 fixtures. Rows that share a text signature are counted, not
told apart (``body_matched_rows``), so for those the record names the first ones in document
order.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = Path(__file__).with_name("body_rows_main.json")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--src", required=True, type=Path, help="the baseline checkout's src")
    parser.add_argument("--commit", default="c674828", help="the baseline's commit, recorded")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    src = args.src.resolve()
    sys.path[:0] = [str(src), str(ROOT)]
    import sec2md

    if src not in Path(sec2md.__file__).resolve().parents:
        raise SystemExit(f"sec2md imported from {sec2md.__file__}, not {src}")
    from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture
    from tests.accuracy.metrics import _markdown_of, _render, body_matched_rows, text_source_rows

    lines = ["{", f'  "commit": {json.dumps(args.commit)},', '  "fixtures": {']
    for position, fixture_id in enumerate(FIXTURE_IDS):
        _, source = load_fixture(fixture_id)
        rows = body_matched_rows(source, _markdown_of(_render(source)[1]))
        entries = [
            json.dumps([row.table, row.row, list(row.cells)], ensure_ascii=False)
            for row in rows
        ]
        body = ",\n".join(f"      {entry}" for entry in entries)
        closing = "," if position < len(FIXTURE_IDS) - 1 else ""
        lines.append(f"    {json.dumps(fixture_id)}: [\n{body}\n    ]{closing}" if entries
                     else f"    {json.dumps(fixture_id)}: []{closing}")
        print(f"{fixture_id}: {len(rows)} body-matched rows of {len(text_source_rows(source))} with text")
    lines += ["  }", "}", ""]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
