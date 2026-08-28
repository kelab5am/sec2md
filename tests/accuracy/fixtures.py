"""Immutable loading of the audited, offline SEC HTML corpus."""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepresentativeRow:
    """A hand-audited financial row and its normalized numeric series."""

    label: str
    numbers: tuple[str, ...]


@dataclass(frozen=True)
class FixtureContract:
    """Identity and minimum-quality contract for one immutable SEC fixture."""

    fixture_id: str
    filename: str
    cik: str
    accession: str
    form: str
    report_date: str
    sec_url: str
    role: str
    sha256: str
    expected_encoding_reason: str
    min_word_recall: float
    min_numeric_recall: float
    min_financial_row_recall: float
    expected_sections: tuple[str, ...]
    representative_rows: tuple[RepresentativeRow, ...]

    @classmethod
    def from_dict(cls, item: dict) -> "FixtureContract":
        rows = tuple(
            RepresentativeRow(
                label=row["label"],
                numbers=tuple(str(number) for number in row["numbers"]),
            )
            for row in item.get("representative_rows", ())
        )
        return cls(
            fixture_id=item["fixture_id"],
            filename=item["filename"],
            cik=item["cik"],
            accession=item["accession"],
            form=item["form"],
            report_date=item["report_date"],
            sec_url=item["sec_url"],
            role=item["role"],
            sha256=item["sha256"],
            expected_encoding_reason=item["expected_encoding_reason"],
            min_word_recall=float(item["min_word_recall"]),
            min_numeric_recall=float(item["min_numeric_recall"]),
            min_financial_row_recall=float(item["min_financial_row_recall"]),
            expected_sections=tuple(item.get("expected_sections", ())),
            representative_rows=rows,
        )


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sec"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


def load_manifest() -> dict[str, FixtureContract]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["fixture_id"]: FixtureContract.from_dict(item) for item in raw["fixtures"]}


FIXTURE_IDS = tuple(load_manifest())


def load_fixture(fixture_id: str) -> tuple[FixtureContract, bytes]:
    """Load and hash-check one fixture without modifying the corpus."""

    contract = load_manifest()[fixture_id]
    compressed = (FIXTURE_ROOT / contract.filename).read_bytes()
    source = gzip.decompress(compressed)
    actual = hashlib.sha256(source).hexdigest()
    if actual != contract.sha256:
        raise ValueError(f"fixture hash mismatch for {fixture_id}: {actual}")
    return contract, source
