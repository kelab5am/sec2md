"""Record which source rows with visible text a baseline renderer's Markdown renders as body rows.

The accuracy suite's body-row guard (spec 2026-10-05, Acceptance, "Body rows must not drop")
compares the candidate against this record, so the normal test run needs no second checkout.
The seven fixtures audited in 2026-08 were recorded from the commit before the table merge
and header rules work:

    git archive c674828 | tar -x -C <scratch>/main-c674828
    python tests/accuracy/generate_body_row_baseline.py --src <scratch>/main-c674828/src

That records 2,485 rows across those 7 fixtures. A fixture added later is recorded from the
``main`` it was added against, so the guard holds it to what ``main`` rendered then; the file
names that commit under ``fixture_commits``. The three fixtures of the 2026-10-24 positioned
page layout spec were recorded from ``c6e120a`` (TSM's positioned pages render no rows there):

    git archive c6e120a | tar -x -C <scratch>/main-c6e120a
    python tests/accuracy/generate_body_row_baseline.py --src <scratch>/main-c6e120a/src \\
        --commit c6e120a --only tsm-2026-q2-ex99-1 baba-2026-ex99-1 asml-2025-ex99-3

``--only`` replaces those fixtures' entries and keeps every other one as it is.

The baseline's ``src`` renders the fixtures; this checkout's ``tests/accuracy`` measures them,
so both sides of the guard use the same row identities and matching rule. Rows that share a
text signature are counted, not told apart (``body_matched_rows``), so for those the record
names the first ones in document order.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = Path(__file__).with_name("body_rows_main.json")
BASE_COMMIT = "c674828"


def _write(path: Path, fixtures: dict[str, list], fixture_commits: dict[str, str]) -> None:
    lines = ["{", f'  "commit": {json.dumps(BASE_COMMIT)},']
    if fixture_commits:
        lines.append(f'  "fixture_commits": {json.dumps(fixture_commits)},')
    lines.append('  "fixtures": {')
    for position, (fixture_id, rows) in enumerate(fixtures.items()):
        entries = [json.dumps(row, ensure_ascii=False) for row in rows]
        body = ",\n".join(f"      {entry}" for entry in entries)
        closing = "," if position < len(fixtures) - 1 else ""
        lines.append(f"    {json.dumps(fixture_id)}: [\n{body}\n    ]{closing}" if entries
                     else f"    {json.dumps(fixture_id)}: []{closing}")
    lines += ["  }", "}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--src", required=True, type=Path, help="the baseline checkout's src")
    parser.add_argument("--commit", default=BASE_COMMIT, help="the baseline's commit, recorded")
    parser.add_argument("--only", nargs="+", help="record these fixtures, keep the others' entries")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    src = args.src.resolve()
    sys.path[:0] = [str(src), str(ROOT)]
    import sec2md

    if src not in Path(sec2md.__file__).resolve().parents:
        raise SystemExit(f"sec2md imported from {sec2md.__file__}, not {src}")
    from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture
    from tests.accuracy.metrics import _markdown_of, _render, body_matched_rows, text_source_rows

    existing = json.loads(args.out.read_text(encoding="utf-8")) if args.only else {}
    recorded = existing.get("fixtures", {})
    fixture_commits = dict(existing.get("fixture_commits", {}))
    fixtures: dict[str, list] = {}
    for fixture_id in FIXTURE_IDS:
        if args.only and fixture_id not in args.only:
            fixtures[fixture_id] = recorded[fixture_id]
            continue
        _, source = load_fixture(fixture_id)
        rows = body_matched_rows(source, _markdown_of(_render(source)[1]))
        fixtures[fixture_id] = [[row.table, row.row, list(row.cells)] for row in rows]
        if args.commit == BASE_COMMIT:
            fixture_commits.pop(fixture_id, None)
        else:
            fixture_commits[fixture_id] = args.commit
        print(f"{fixture_id}: {len(rows)} body-matched rows of {len(text_source_rows(source))} with text")
    _write(args.out, fixtures, fixture_commits)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
