# Upstream sync

The maintained fork tracks `lucasastorian/sec2md` as its upstream. Use the following commands to inspect upstream changes and run the release gates:

```powershell
git remote add upstream https://github.com/lucasastorian/sec2md.git
git fetch upstream --tags
git log --oneline --left-right main...upstream/main
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m build
```

Upstream changes are manually reviewed and cherry-picked or merged; they are never auto-merged. `v0.1.22-rcq.N` tags are created only from a reviewed release commit.
