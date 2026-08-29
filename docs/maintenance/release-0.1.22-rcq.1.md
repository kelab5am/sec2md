# sec2md 0.1.22+rcq.1 release evidence

This record covers the release candidate only. The tag `v0.1.22-rcq.1`, push,
publication, and complete-accession capture remain separately authorized work.

## Evidence state

- Local gates: `LOCAL_VERIFIED` — all required local commands below exited `0`
  at the independently reviewed code candidate
  `4e1a8345bb6a25e2bb1d08446592a3866f291b1c`.
- GitHub Actions: `CI_PENDING` — no CI run URL is available before a remote CI
  run exists.
- Independent committed-state review: `APPROVE` — SOL High reviewed the
  exceptional encoding repair at
  `4e1a8345bb6a25e2bb1d08446592a3866f291b1c`; the prior Important finding was
  addressed, no new Critical/Important breakage was found, and the evidence was
  judged credible with no out-of-scope observations.

This is local review approval, not a release-readiness claim. Remote CI remains
mandatory and is still pending.

## Baseline and candidate

- Task 8 prerequisite baseline: `5437ee4435812e146eb3f25952cffad12a882994`
  (`test: align legacy table width expectation`).
- Upstream baseline: `a243bd782cd9d20a6e0f69c04bc484ea069d0e51`.
- Task 8 implementation candidate commit: `235814f709dbca969ff35ba735bc42f4a92a22ba`
  (`release: prepare sec2md 0.1.22+rcq.1`).
- Later prerequisite/review commit: `013bc4039c0fd5ef1b8f1670cc5769c7936273b1`
  (not part of the Task 8 implementation candidate; it addresses the
  separately reviewed accuracy-metric finding).
- Historical Task 8 evidence finalization commit:
  `69af7c8e63451db902a02235af61255c2b91346f`
  (`fix: finalize release evidence`).
- Final whole-branch fix commit:
  `bcaba0695b9fbd7ef89cee1c110c4a00d5c256f9`
  (`fix: harden final RCQ review findings`).
- Current independently reviewed code candidate:
  `4e1a8345bb6a25e2bb1d08446592a3866f291b1c`
  (`fix: bind encoding scanner to matching closers`).
- This document preserves earlier Task 8 measurements as historical evidence
  and labels the fresh final measurements separately. Its exact reviewed code
  candidate is `4e1a8345bb6a25e2bb1d08446592a3866f291b1c`;
  a later docs-only evidence commit is not represented as reviewed code.
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

Historical Task 8 pre-commit exit-code evidence:

| Command | Exit code | Result |
| --- | ---: | --- |
| `.\.venv\Scripts\python -m pytest -q` | 0 | `292 passed, 14 deselected` |
| `.\.venv\Scripts\python -m ruff check src tests` | 0 | `All checks passed!` |
| `if (Test-Path dist) { Remove-Item -LiteralPath dist -Recurse -Force }` | 0 | Resolved worktree `dist` removed before build |
| `.\.venv\Scripts\python -m build` | 0 | sdist and wheel built; setuptools emitted deprecation warnings only |
| `.\.venv\Scripts\python -c "from importlib.metadata import version; assert version('sec2md') == '0.1.22+rcq.1'"` | 0 | Version assertion passed |
| `git diff --check` | 0 | No whitespace errors |
| `git status --short` | 0 | Only scoped Task 8 paths listed |

Fresh final reviewed-code evidence at
`4e1a8345bb6a25e2bb1d08446592a3866f291b1c`:

| Command | Exit code | Result |
| --- | ---: | --- |
| `.\.venv\Scripts\python -m pytest -q` | 0 | `306 passed, 14 deselected, 1 warning in 75.71s`; no failures or xfails |
| `.\.venv\Scripts\python -m pytest tests/accuracy -q` | 0 | `41 passed, 1 warning in 74.32s` |
| `.\.venv\Scripts\python -m ruff check --no-cache src tests` | 0 | `All checks passed!` |
| `.\.venv\Scripts\python -m build --outdir 'C:\tmp\sec2md-release-evidence-4e1a834-20260829-1055'` (sandboxed attempt) | 1 | Stalled while installing isolated build dependencies and was manually interrupted; no artifact result claimed |
| Same build command outside the restricted sandbox | 0 | Fresh sdist and wheel built; isolated environments used `setuptools==84.0.0` and `wheel==0.48.0`; warnings recorded below |
| `Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\tmp\sec2md-release-evidence-4e1a834-20260829-1055\sec2md-0.1.22+rcq.1-py3-none-any.whl'` plus wheel-METADATA assertions (sandboxed attempt) | 1 | Temporary artifact was not readable from the restricted sandbox (`PermissionError` / access denied) |
| Same hash and wheel-METADATA checks outside the restricted sandbox | 0 | SHA-256 and all required embedded metadata assertions passed |
| `.\.venv\Scripts\python -c "from importlib.metadata import version; actual=version('sec2md'); assert actual == '0.1.22+rcq.1', actual; print(actual)"` | 0 | Printed `0.1.22+rcq.1` |
| `git diff --check` | 0 | No whitespace errors |
| `git status --short --branch` | 0 | Clean `codex/rcq-hardening-v1` at the reviewed code candidate before this docs-only amendment |

The two pytest runs emitted only the known `PytestCacheWarning`: the restricted
environment could not create `.pytest_cache\v\cache\nodeids` (`[WinError 5]
Access is denied`).


## Build artifact and metadata

- Historical Task 8 pre-commit wheel filename:
  `sec2md-0.1.22+rcq.1-py3-none-any.whl`.
- Historical Task 8 pre-commit wheel SHA-256:
  `9f547d1915dba35da00f47b86f66159a2b1f118389d2031616fca2ee7140cdd8`.
- Historical Task 8 committed-state wheel filename:
  `sec2md-0.1.22+rcq.1-py3-none-any.whl`.
- Historical Task 8 committed-state wheel SHA-256:
  `44106d792577a5847b7053efd37dc1cb2ab1fb011d5b622899ee35828ca1cbd3`.
- Fresh final reviewed-code wheel filename:
  `sec2md-0.1.22+rcq.1-py3-none-any.whl`.
- Fresh final reviewed-code wheel SHA-256:
  `ea7229983093941be658d481ea9d38551deadc5a9fecf789f12d41a899734577`.
- Fresh artifact output directory:
  `C:\tmp\sec2md-release-evidence-4e1a834-20260829-1055`.
- Required wheel metadata assertions: `Version: 0.1.22+rcq.1`,
  `Requires-Python: <3.13,>=3.10`, and
  `Project-URL: Repository, https://github.com/kelab5am/sec2md`.
- Metadata assertion evidence: `PASS` — `Metadata-Version: 2.4`,
  `Name: sec2md`, `Version: 0.1.22+rcq.1`, `Requires-Python: <3.13,>=3.10`,
  `Project-URL: Repository, https://github.com/kelab5am/sec2md`, and
  `Project-URL: Upstream, https://github.com/lucasastorian/sec2md`.

Both the historical committed-state build and the fresh final reviewed-code
build emitted these exact setuptools warning categories/counts and exited `0`:

- 4 occurrences of `SetuptoolsDeprecationWarning: \`project.license\` as a
  TOML table is deprecated`, with the accompanying notice: `Please use a
  simple string containing a SPDX expression for \`project.license\`. You can
  also use \`project.license-files\`. (Both options available on
  setuptools>=77.0.0).`
- 8 occurrences of `SetuptoolsDeprecationWarning: License classifiers are
  deprecated.`

Remediation state: `DEFERRED_OUT_OF_SCOPE` — the inherited `pyproject.toml`
license table and license classifier remain unchanged because Task 8 is bound
to its nine named paths. A warning-free build requires a separately authorized
packaging-metadata change.

## Historical Task 8 committed-state commands

These commands were run after the Task 8 implementation candidate commit
`235814f709dbca969ff35ba735bc42f4a92a22ba`:

| Command | Exit code | Result |
| --- | ---: | --- |
| `git status --short --branch` | 0 | Clean `codex/rcq-hardening-v1` |
| `git log -8 --oneline` | 0 | Eight expected implementation/review commits listed |
| `.\.venv\Scripts\python -m pytest -q` | 0 | `292 passed, 14 deselected`; zero failed and zero xfailed |
| `.\.venv\Scripts\python -m ruff check src tests` | 0 | `All checks passed!` |
| `.\.venv\Scripts\python -m build` | 0 | sdist and committed-state wheel built; warnings recorded above |

The committed-state wheel and metadata evidence are the values recorded above;
the pre-commit and committed-state hashes are labeled separately because the
wheel ZIP entry timestamps differ between builds.

The fresh final artifact hash is separately labeled for the same reason. Its
embedded wheel metadata was read directly from the wheel and asserted to
contain `Metadata-Version: 2.4`, `Name: sec2md`,
`Version: 0.1.22+rcq.1`, `Requires-Python: <3.13,>=3.10`, and both required
Repository and Upstream project URLs.

## External gates

- CI run URL: `CI_PENDING — unavailable until a real GitHub Actions run exists`.
- Independent review verdict: `APPROVE — independent SOL High review of
  4e1a8345bb6a25e2bb1d08446592a3866f291b1c found the prior Important encoding
  issue addressed, no new Critical/Important breakage, credible evidence, and
  no out-of-scope observations`.

No release-readiness claim is made while `CI_PENDING` remains unresolved.
