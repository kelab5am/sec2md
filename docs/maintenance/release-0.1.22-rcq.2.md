# sec2md 0.1.22+rcq.2 release evidence

This record covers the retained-bytes `base_url` prerequisite only. It does
not authorize a tag, merge, push, publication, RCQ dependency pin, or live
filing capture.

## Evidence state

- Task 3 local gates: `LOCAL_VERIFIED` — the version, focused conversion
  tests, Ruff, and diff checks passed in the isolated worktree before the
  Task 3 commit.
- Task 4 build artifacts and wheel hashes: `PENDING_NOT_RUN` — Task 4 has not
  run, so no artifact filename or hash is claimed here.
- Independent committed-state review: `REVIEW_PENDING` — the Task 3 commit
  must receive a separate SOL review before this revision is approved for RCQ
  consumption.

## Baseline and task commits

- Reviewed repository baseline: `9b7641c5854117d2348896ff9a62da623f68012c`.
- Task 1 base-URL implementation: `cccab1767f3b83ce7e8ea6f894c8234782bf3b77`.
- Task 2 compatibility tests: `c507a85fd0154d581d7849ec77d05b0bf8fe355c`.
- Task 2 repair round 1: `052d31df2f04ce7d903391009e4801051ea9391d`.
- Task 3 base: `052d31df2f04ce7d903391009e4801051ea9391d`.
- Task 3 committed HEAD: `70f218014795d6e7f5f428974179200305b414b2`.
- Task 4 evidence-finalization commit: `PENDING_NOT_RUN`.

## Task 3 RED evidence

| Command | Exit code | Result |
| --- | ---: | --- |
| `.\.venv\Scripts\python.exe -m pytest tests\test_models.py -q` | 1 | `1 failed, 19 passed`; `version("sec2md")` was still `0.1.22+rcq.1` while the test expected `0.1.22+rcq.2`. |

## Task 3 GREEN evidence

The following commands are run from the project-local worktree after the
version, documentation, changelog, and evidence edits and before the Task 3
commit:

| Command | Exit code | Result |
| --- | ---: | --- |
| `.\.venv\Scripts\python.exe -m pytest tests\test_models.py tests\test_core.py -q` | 0 | `51 passed in 0.51s`. |
| `.\.venv\Scripts\python.exe -m ruff check src tests` | 0 | `All checks passed!`. |
| `git diff --check` | 0 | No whitespace errors; Git emitted only normal line-ending warnings for changed files. |

The editable environment metadata was refreshed after the version declaration
changed so the distribution assertion evaluated the current candidate:

| Command | Exit code | Result |
| --- | ---: | --- |
| `.\.venv\Scripts\python.exe -m pip install -e . --no-deps` | 0 | Installed editable `sec2md-0.1.22+rcq.2`. |

## Task 4 evidence placeholders

These commands and values are intentionally not filled during Task 3:

| Command or evidence | State |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | `PENDING_NOT_RUN` |
| `.\.venv\Scripts\python.exe -m build` | `PENDING_NOT_RUN` |
| Wheel metadata assertion for `Version: 0.1.22+rcq.2` | `PENDING_NOT_RUN` |
| Wheel filename and SHA-256 | `PENDING_NOT_RUN`; no hash fabricated |
| Final independent SOL review verdict | `REVIEW_PENDING`; no verdict fabricated |

The final approved revision, build identity, exact full-gate output, and
independent review verdict must be recorded only after Task 4 completes.
