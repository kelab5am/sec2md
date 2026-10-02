# Spec evidence prototypes

Throwaway scripts behind the numbers in
`docs/superpowers/specs/2026-10-02-sec2md-table-completeness-check-design.md`
and the `chunk_section()` fix on branch `fix/audit-2026-10-02`. Run them from the
branch checkout root with that checkout installed (`pip install -e ".[xlsx]"`).

- `proto_tables.py`: check 1 (per-table numeric completeness) on all fixtures.
- `proto_rows_body.py <path to proto_tables.py>`: check 2 (body-row order).
- `measure_scope.py`, `foreign.py`: section/chunk consistency after the element-scoping fix.
