# Task 3 Report: Parse Diagnostics and Catastrophic-Loss Enforcement

## Result

Implemented immutable parse diagnostics, strict/warn/off quality policy
enforcement, public quality-policy parameters, and fail-closed catastrophic
loss checks. Parser instances now retain their latest diagnostics and
provisional element source-node mapping IDs.

## RED verification

Before implementation, the required focused command was run:

```text
.\.venv\Scripts\python -m pytest tests/test_quality.py tests/test_core.py -v
```

It failed during collection with:

```text
ModuleNotFoundError: No module named 'sec2md.quality'
```

This confirmed the new diagnostics module and public quality-policy surface
were absent before implementation.

## Implementation

- Added frozen `ParseDiagnostics` and `ParseQualityError` in
  `src/sec2md/quality.py`.
- Added visible-source and Markdown-visible-character measurements.
- Added the six strict hard-failure messages: substantial empty output,
  catastrophic ratio, replacement characters, C1 controls, missing mappings,
  and untraceable normalized numbers.
- Added strict, warning-only, and disabled policy behavior with deterministic
  warning logging and runtime policy validation.
- Added keyword-only `quality_policy="strict"` to both convenience APIs and
  exported the public diagnostic types.
- Added parser diagnostics state and provisional mapping retention.
- Added focused unit, core API, parser-state, and positioned-fixture tests.

## GREEN verification

Focused quality/core/parser/accuracy command:

```text
.\.venv\Scripts\python -m pytest tests/test_quality.py tests/test_core.py tests/test_parser.py tests/accuracy/test_sec_accuracy.py -q
```

Result: `92 passed, 4 xfailed`.

Full suite command:

```text
.\.venv\Scripts\python -m pytest -q
```

Result: `239 passed, 14 deselected, 4 xfailed`.

The four XFAIL results are the pre-existing, explicitly bounded Task 2
accuracy defects. The only test warning was the environment's inability to
write pytest's cache under the worktree.

Lint and whitespace checks:

```text
.\.venv\Scripts\ruff check src tests
git diff --check
```

Result: Ruff passed and no diff whitespace errors were reported. Ruff used a
task-specific cache directory under the system temporary directory because
the worktree cache directory was permission-restricted.

## Self-review

- All public policy parameters remain keyword-only and default to strict.
- `include_elements=False` disables mapping enforcement while preserving the
  other quality checks.
- `off` returns diagnostics without logging or raising; `warn` returns output
  and logs every warning; `strict` raises one error carrying all diagnostics.
- Source measurement excludes script, style, noscript, template, hidden, and
  hidden inline-XBRL subtrees.
- Task 2 fixture hashes, quality-off corpus behavior, exact XFAILs, and
  offline test behavior were preserved.
- No files outside the Task 3 scope were changed.

## Commit

The implementation is committed as:

`feat: fail closed on catastrophic parse loss`

## Fix Round 1: Empty Source-Node Lists

### Finding

The independent review found that an element ID present in
`block_nodes_map` was counted as mapped even when its node collection was
empty. This could let strict mode accept an element without a source node.

### RED verification

Added `test_strict_rejects_element_with_empty_source_node_mapping`, which
injects an element mapped to `[]` through the public `convert_to_markdown`
API. Before the fix:

```text
.\.venv\Scripts\python -m pytest tests/test_quality.py::test_strict_rejects_element_with_empty_source_node_mapping -q
```

Result: failed because `ParseQualityError` was not raised.

### Fix and GREEN verification

Parser and all core fallback diagnostics builders now pass only IDs whose
mapped node collections are non-empty. The regression also asserts
`diagnostics.mapped_elements == 0` and the required missing-mapping message.

Focused command:

```text
.\.venv\Scripts\python -m pytest tests/test_quality.py::test_strict_rejects_element_with_empty_source_node_mapping tests/test_quality.py tests/test_core.py tests/test_parser.py -q
```

Result: `60 passed`.

Full command:

```text
.\.venv\Scripts\python -m pytest -q
```

Result: `240 passed, 14 deselected, 4 xfailed`.

Ruff and whitespace checks passed:

```text
.\.venv\Scripts\ruff check src tests
git diff --check
```

Self-review confirms that only non-empty source-node mappings are counted in
the parser diagnostics path and each of the three core fallback paths;
`build_diagnostics` retains its documented ID-based interface, and no Task 2
fixture or XFAIL behavior changed.
