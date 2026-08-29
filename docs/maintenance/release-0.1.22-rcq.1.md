# sec2md 0.1.22+rcq.1 release evidence

This record covers the release candidate only. The tag `v0.1.22-rcq.1`, push,
publication, and complete-accession capture remain separately authorized work.

## Evidence state

- Local gates: `LOCAL_VERIFIED` — all required local commands below exited `0`
  on the uncommitted Task 8 candidate before commit.
- GitHub Actions: `CI_PENDING` — no CI run URL is available before a remote CI
  run exists.
- Independent committed-state review: `REVIEW_PENDING` — no review verdict is
  available before the release candidate is committed and reviewed.

## Baseline and candidate

- Task 8 prerequisite baseline: `5437ee4435812e146eb3f25952cffad12a882994`
  (`test: align legacy table width expectation`).
- Upstream baseline: `a243bd782cd9d20a6e0f69c04bc484ea069d0e51`.
- Release candidate commit: `PENDING_UNTIL_TASK_8_COMMIT` at this evidence
  revision; the final committed SHA is recorded after the commit gate.
- Proposed tag: `v0.1.22-rcq.1` (not created).

## Offline fixture identity

The loader verifies each uncompressed SHA-256 before parsing. The authoritative
sources remain gzip-compressed under `tests/fixtures/sec/`.

| Fixture | Uncompressed SHA-256 |
| --- | --- |
| `aapl-2023-10k` | `bda1f34435199672c16ecdf2034c650872d2cac8399ed0d179fc25450b080b90` |
| `nvda-2026-10k` | `73d81f5a111abcf72426c840871e76f5f5edc9631f436d495a86b6f87306d58b` |
| `nvda-2002-10k` | `04136c61bb8ea9490da4916f358a2275f019ed6536878715da412d7056a0739d` |
| `nvda-2026-q2-10q` | `e2634e509c241c5f45e3f6c115dc38a85645e5fdbee760b4a04f5e9035f6f7a9` |
| `nvda-2026-08-26-8k` | `84335b3247873da9fc91b4d9aa146be012801158183a7e9b0e98f0d31e50d0ea` |
| `nvda-2026-ex99-1` | `1809cb206590dcfeb959f3a1a64157f4e5ee42788ec51289b74f3ea299931eb7` |
| `nvda-2026-ex99-2` | `6a522635d049044b2ff9ff63cb78220cf29d960e96614c88afe30560c3ee0659` |

## Required local gates

These commands are run from the repository root in the order specified by the
Task 8 brief. Exit codes and artifact evidence are filled from the actual run.

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check src tests
if (Test-Path dist) { Remove-Item -LiteralPath dist -Recurse -Force }
.\.venv\Scripts\python -m build
.\.venv\Scripts\python -c "from importlib.metadata import version; assert version('sec2md') == '0.1.22+rcq.1'"
git diff --check
git status --short
```

Pre-commit exit-code evidence:

| Command | Exit code | Result |
| --- | ---: | --- |
| `.\.venv\Scripts\python -m pytest -q` | 0 | `292 passed, 14 deselected` |
| `.\.venv\Scripts\python -m ruff check src tests` | 0 | `All checks passed!` |
| `if (Test-Path dist) { Remove-Item -LiteralPath dist -Recurse -Force }` | 0 | Resolved worktree `dist` removed before build |
| `.\.venv\Scripts\python -m build` | 0 | sdist and wheel built; setuptools emitted deprecation warnings only |
| `.\.venv\Scripts\python -c "from importlib.metadata import version; assert version('sec2md') == '0.1.22+rcq.1'"` | 0 | Version assertion passed |
| `git diff --check` | 0 | No whitespace errors |
| `git status --short` | 0 | Only scoped Task 8 paths listed |


## Build artifact and metadata

- Wheel filename: `sec2md-0.1.22+rcq.1-py3-none-any.whl`.
- Wheel SHA-256: `9f547d1915dba35da00f47b86f66159a2b1f118389d2031616fca2ee7140cdd8`.
- Required wheel metadata assertions: `Version: 0.1.22+rcq.1`,
  `Requires-Python: <3.13,>=3.10`, and
  `Project-URL: Repository, https://github.com/kelab5am/sec2md`.
- Metadata assertion evidence: `PASS` — `Metadata-Version: 2.4`,
  `Name: sec2md`, `Version: 0.1.22+rcq.1`, `Requires-Python: <3.13,>=3.10`,
  `Project-URL: Repository, https://github.com/kelab5am/sec2md`, and
  `Project-URL: Upstream, https://github.com/lucasastorian/sec2md`.

## External gates

- CI run URL: `CI_PENDING — unavailable until a real GitHub Actions run exists`.
- Independent review verdict: `REVIEW_PENDING — unavailable until an
  independent committed-state review is completed`.

No release-readiness claim is made by this pending evidence record.
