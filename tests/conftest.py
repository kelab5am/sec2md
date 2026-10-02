"""Refuse to run against a sec2md other than this checkout's src tree."""

from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"


def pytest_configure(config):
    import sec2md

    imported = Path(sec2md.__file__).resolve()
    if _SRC.resolve() not in imported.parents:
        raise pytest.UsageError(
            f"tests would import sec2md from {imported}, not {_SRC}; "
            "install this checkout (pip install -e .) or run pytest from its root"
        )
