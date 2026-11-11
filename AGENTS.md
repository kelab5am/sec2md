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
- **Design specs and plans are committed on `main`** (`docs/superpowers/specs/`, `docs/superpowers/plans/`), not on a feature branch or in a feature worktree, so the owner has one copy to find. Write them in the checkout that has `main` checked out: this repository's own folder, or `.worktrees/main` when that folder is on another branch (create it with `git worktree add .worktrees/main main` if it is missing; never switch the branch of a folder that has work in progress). Run `git pull --ff-only` there first. Uploading `main` is the owner's step: say that the document is committed on this PC and still needs `git push`. Code changes still go in their own worktree and through a pull request. These documents are public like everything else here.

## Before opening a pull request

1. Run the tests and Ruff, and paste the commands and their output into the pull request.
2. Run `/code-review` on the diff, then fix each finding or say why it doesn't apply.
3. Fill in the pull request template: how it was tested, the risk, how to undo it.

A bad change here looks like: a number, sign, unit, period or column header in the Markdown that differs from the filing; a table dropped, split or merged wrongly; text silently lost; a filing that used to convert now failing.
