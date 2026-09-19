# sec2md 0.1.22+rcq.2 release evidence

This record covers the retained-bytes `base_url` prerequisite only. It does
not authorize a tag, merge, push, publication, RCQ dependency pin, or live
filing capture.

## Evidence state

- Task 3 local gates: `LOCAL_VERIFIED` — the version, focused conversion
  tests, Ruff, and diff checks passed in the isolated worktree before the
  Task 3 commit.
- Task 4 build artifacts and wheel hashes: `VERIFIED` — the repaired committed
  candidate was rebuilt and its wheel metadata and SHA-256 were verified.
- Independent committed-state review: `APPROVE` — replacement review task
  `01a04d27-0a6f-72f1-8fc5-71d0def826ee` (`gpt-5.6-sol`, High) approved the
  repaired committed candidate with no Critical, Important, or Minor findings.

## Baseline and task commits

- Reviewed repository baseline: `9b7641c5854117d2348896ff9a62da623f68012c`.
- Task 1 base-URL implementation: `cccab1767f3b83ce7e8ea6f894c8234782bf3b77`.
- Task 2 compatibility tests: `c507a85fd0154d581d7849ec77d05b0bf8fe355c`.
- Task 2 repair round 1: `052d31df2f04ce7d903391009e4801051ea9391d`.
- Task 3 base: `052d31df2f04ce7d903391009e4801051ea9391d`.
- Task 3 committed HEAD: `70f218014795d6e7f5f428974179200305b414b2`.
- Task 3 evidence repair: `3ff8f89869406ce07e29d3f1796dc34f834ff463`.
- Final README repair and independently approved code state:
  `eba3bbbd9c404241df45112b973f7ed05cc6703c`.
- Task 4 evidence-finalization commit: the commit containing this document;
  its SHA is resolved by `git rev-parse HEAD` after the evidence-only commit
  and is not self-recorded here.

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

## Task 4 full verification and artifact identity

The controller repeated the full gates after the final README repair at
`eba3bbbd9c404241df45112b973f7ed05cc6703c`:

| Command or evidence | Exit code | Result |
| --- | ---: | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | 0 | `322 passed, 14 deselected in 73.53s`. |
| `.\.venv\Scripts\python.exe -m ruff check src tests` | 0 | `All checks passed!`. |
| `.\.venv\Scripts\python.exe -m build` | 0 | Built the sdist and wheel; setuptools emitted only license-metadata deprecation warnings. |
| Wheel metadata assertion | 0 | `Version: 0.1.22+rcq.2`; corrected commit-pinning guidance present; stale `v0.1.22-rcq.1` guidance absent. |
| `Get-FileHash -Algorithm SHA256 dist\sec2md-0.1.22+rcq.2-*.whl` | 0 | `e78ac170da6296cc60480344c9806ad38871528d6291721fef749eaa69d03dc6`. |
| `git diff --check` | 0 | No whitespace errors. |
| `git status --short --branch` | 0 | Clean branch `codex/retained-bytes-base-url`. |

Wheel filename: `sec2md-0.1.22+rcq.2-py3-none-any.whl`.

## Independent final review

- Verdict: `APPROVE`.
- Reviewer: task `01a04d27-0a6f-72f1-8fc5-71d0def826ee`,
  `gpt-5.6-sol` with High reasoning.
- Reviewed baseline: `9b7641c5854117d2348896ff9a62da623f68012c`.
- Initially blocked candidate: `3ff8f89869406ce07e29d3f1796dc34f834ff463`.
- Approved repaired candidate: `eba3bbbd9c404241df45112b973f7ed05cc6703c`.
- Fresh reviewer verification: `322 passed, 14 deselected in 72.65s`, Ruff
  passed, targeted acquisition and URL-validation probes passed, rebuilt
  wheel metadata and SHA-256 matched, history was linear and plan-authorized,
  and worktree/index/diff checks were clean.
- Findings after repair: no Critical, Important, or Minor findings.

This approval authorizes only the evidence-finalization commit. It does not
authorize merge, tag, push, publication, RCQ dependency pinning, RCQ
implementation work, or live filing capture.
