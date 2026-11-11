# sec2md: agent instructions

Converts SEC filings to faithful Markdown. This repository is a fork of `lucasastorian/sec2md`, carrying its own fixes as `+rcq.N` versions.

## Commands

- Install: `python -m pip install -e ".[dev,xlsx]"`
- All tests: `python -m pytest -q`
- One file: `python -m pytest tests/<file>.py -q`
- Lint: `python -m ruff check src tests`
- Tests that hit EDGAR are deselected by default; run them with `python -m pytest -m integration`.

CI (`.github/workflows/ci.yml`) runs the tests on Linux and Windows, Ruff, and a package build on every push.

## Things the code won't tell you

- **Pull requests go to this fork, not upstream.** For a fork, `gh pr create` targets the parent repository unless told otherwise: always pass `--repo kelab5am/sec2md --base main`.
- **This repository is public.** Nothing private goes into code, tests, fixtures, docs, commit messages or pull requests.
- **A downstream project pins this repository by commit,** so `main` has to stay green and every behaviour change gets a `CHANGELOG.md` entry under the current `+rcq.N` version.

## Before opening a pull request

1. Run the tests and Ruff, and paste the commands and their output into the pull request.
2. Run `/code-review` on the diff, then fix each finding or say why it doesn't apply.
3. Fill in the pull request template: how it was tested, the risk, how to undo it.

A bad change here looks like: a number, sign, unit, period or column header in the Markdown that differs from the filing; a table dropped, split or merged wrongly; text silently lost; a filing that used to convert now failing.
