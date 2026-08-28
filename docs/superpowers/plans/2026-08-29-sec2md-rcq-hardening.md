# sec2md RCQ Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release `sec2md` `0.1.22+rcq.1` as a deterministic, fail-closed SEC HTML-to-Markdown parser with audited 10-K, 10-Q, 8-K, and exhibit accuracy.

**Architecture:** Keep `sec2md` focused on parsing one supplied HTML document. Add deterministic byte decoding before DOM construction, parser-level diagnostics and quality enforcement after page/element construction, DOM-aware table/link rendering, and source-node provenance checks; keep complete accession acquisition, storage, manifests, and orchestration in `rcq-wealth`.

**Tech Stack:** Python 3.10-3.12, BeautifulSoup/lxml, Pydantic 2, Requests, Pytest, Ruff, setuptools/build, GitHub Actions, gzip-compressed offline SEC fixtures.

**Spec:** `docs/superpowers/specs/2026-08-29-sec2md-rcq-hardening-design.md`

## Global Constraints

- Work only in `C:\Users\einstein\kelab5am\sec2md\.worktrees\rcq-hardening-v1` on branch `codex/rcq-hardening-v1`; preserve unrelated changes.
- Start from committed design HEAD `22b1220`; do not edit `rcq-wealth` or `C:\tmp\rcq-parser-merge\secrets`.
- Retain the import package name `sec2md`, MIT license, original upstream attribution, and upstream baseline `a243bd782cd9d20a6e0f69c04bc484ea069d0e51`.
- First package version is exactly `0.1.22+rcq.1`; the release tag is exactly `v0.1.22-rcq.1`.
- Support Python 3.10 through 3.12; do not claim Python 3.9 support.
- `quality_policy: Literal["strict", "warn", "off"] = "strict"` is keyword-only on public convenience APIs.
- Strict mode fails closed on catastrophic loss, replacement/C1 characters, missing element mappings, and untraceable normalized numbers.
- Tests and CI use committed offline fixtures only and make no SEC network requests.
- Do not add EDGAR crawling, complete accession retrieval, immutable storage, full XBRL inventory, PDF/OCR/Datalab parsing, or research analysis.
- Every behavior change follows RED-GREEN TDD, preserves representative statement values, and ends in an independently reviewable commit.
- Use `.\.venv\Scripts\python` commands exactly as shown from the worktree root; never tag a release until CI and independent committed-state review pass.

---

## File Responsibility Map

- `src/sec2md/encoding.py`: deterministic byte decoding and Windows-1252 legacy-character normalization only.
- `src/sec2md/quality.py`: immutable diagnostics, numeric normalization/trace comparison, policy evaluation, and `ParseQualityError` only.
- `src/sec2md/core.py`: resolve supplied input, carry the source URL, construct `Parser`, and enforce the selected quality policy.
- `src/sec2md/utils.py`: HTTP byte retrieval and existing general helpers; URL retrieval must return bytes plus response charset.
- `src/sec2md/parser.py`: DOM/page construction, source URL propagation, latest diagnostics, and element-quality input collection.
- `src/sec2md/table_parser.py`: DOM-aware cell rendering, safe accounting-column reconstruction, table-width preservation, and link resolution.
- `src/sec2md/element_builder.py`: element construction, complete source-node unions, annotations, and visible-node XBRL tags.
- `src/sec2md/models.py`: public Pydantic models, including `Exhibit.url`.
- `src/sec2md/section_extractor.py`: structured 8-K exhibit extraction from rendered Markdown.
- `tests/accuracy/fixtures.py`: immutable fixture manifest models, gzip loading, and SHA-256 verification.
- `tests/accuracy/metrics.py`: reusable deterministic text/numeric/row/table/provenance metrics.
- `tests/accuracy/test_sec_accuracy.py`: the seven-document acceptance contract.
- `tests/fixtures/sec/manifest.json`: authoritative fixture identity, provenance, hashes, floors, sections, and representative rows.

### Task 1: Establish Fork Ownership, Version, CI, and Maintenance Contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/sec2md/__init__.py`
- Modify: `tests/test_models.py`
- Modify: `README.md`
- Create: `CHANGELOG.md`
- Create: `.github/workflows/ci.yml`
- Create: `docs/maintenance/upstream-sync.md`

**Interfaces:**
- Consumes: current public import package `sec2md` and upstream version `0.1.22`.
- Produces: `sec2md.__version__ == "0.1.22+rcq.1"`; package metadata limited to Python 3.10-3.12; dev dependency `build>=1.2`; fork/upstream URLs and reproducible CI commands.

- [ ] **Step 1: Write the failing metadata tests**

Add to `tests/test_models.py`:

```python
from importlib.metadata import metadata, version


def test_internal_version_matches_distribution():
    assert version("sec2md") == "0.1.22+rcq.1"
    assert sec2md.__version__ == "0.1.22+rcq.1"


def test_distribution_points_to_maintained_fork():
    project_urls = metadata("sec2md").get_all("Project-URL") or []
    assert "Repository, https://github.com/kelab5am/sec2md" in project_urls
    assert "Upstream, https://github.com/lucasastorian/sec2md" in project_urls
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.\.venv\Scripts\python -m pytest tests/test_models.py::test_internal_version_matches_distribution tests/test_models.py::test_distribution_points_to_maintained_fork -v`

Expected: FAIL because installed/project version is `0.1.22`, and the maintained-fork/upstream URL pair is absent.

- [ ] **Step 3: Apply the minimal version and ownership metadata**

In `pyproject.toml`, set the following exact values and remove the Python 3.9 classifier:

```toml
version = "0.1.22+rcq.1"
requires-python = ">=3.10,<3.13"

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "build>=1.2",
]

[project.urls]
Homepage = "https://github.com/kelab5am/sec2md"
Repository = "https://github.com/kelab5am/sec2md"
Issues = "https://github.com/kelab5am/sec2md/issues"
Upstream = "https://github.com/lucasastorian/sec2md"

[tool.black]
target-version = ["py310"]

[tool.ruff]
target-version = "py310"
```

Set `__version__ = "0.1.22+rcq.1"` in `src/sec2md/__init__.py`. Keep Lucas Astorian in `authors`; add the fork maintainer as a project maintainer only if a non-placeholder name/email is already present in Git configuration.

- [ ] **Step 4: Add fork, release, and upstream-sync documentation**

Add a README opening note that this is the RCQ-maintained fork of `lucasastorian/sec2md`, that `sec2md` parses one supplied HTML document and does not download a complete accession, and that consumers pin `v0.1.22-rcq.1` plus its resolved commit. Add `CHANGELOG.md` with an `0.1.22+rcq.1 (unreleased)` section listing deterministic decoding, strict quality checks, table/link fixes, provenance checks, offline fixtures, and CI. In `docs/maintenance/upstream-sync.md`, document these exact commands and gates:

```powershell
git remote add upstream https://github.com/lucasastorian/sec2md.git
git fetch upstream --tags
git log --oneline --left-right main...upstream/main
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m build
```

State that upstream changes are manually reviewed and cherry-picked or merged, never auto-merged; `v0.1.22-rcq.N` tags are created only from a reviewed release commit.

- [ ] **Step 5: Add the CI skeleton**

Create `.github/workflows/ci.yml` with four required jobs: a Linux matrix for Python 3.10 and 3.12, Windows Python 3.12, Ruff on Python 3.12, and package build/metadata inspection on Python 3.12. Each test job runs `python -m pip install -e ".[dev]"` then `python -m pytest -q`; Ruff runs `python -m ruff check src tests`; build runs `python -m build` then this exact assertion:

```yaml
- name: Inspect wheel metadata
  shell: python {0}
  run: |
    from pathlib import Path
    from zipfile import ZipFile
    wheel = next(Path("dist").glob("*.whl"))
    with ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith("METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")
    assert "Version: 0.1.22+rcq.1" in metadata
    assert "Requires-Python: <3.13,>=3.10" in metadata
    assert "Project-URL: Repository, https://github.com/kelab5am/sec2md" in metadata
```

- [ ] **Step 6: Reinstall editable metadata and verify GREEN**

Run: `.\.venv\Scripts\python -m pip install -e ".[dev]"`

Run: `.\.venv\Scripts\python -m pytest tests/test_models.py -v`

Expected: all model/version tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add pyproject.toml src/sec2md/__init__.py tests/test_models.py README.md CHANGELOG.md .github/workflows/ci.yml docs/maintenance/upstream-sync.md
git commit -m "chore: establish RCQ fork release contract"
```

### Task 2: Commit the Audited SEC Corpus and Baseline Accuracy Harness

**Files:**
- Create: `tests/accuracy/__init__.py`
- Create: `tests/accuracy/fixtures.py`
- Create: `tests/accuracy/metrics.py`
- Create: `tests/accuracy/test_sec_accuracy.py`
- Create: `tests/fixtures/sec/README.md`
- Create: `tests/fixtures/sec/manifest.json`
- Create: `tests/fixtures/sec/aapl-2023-10k.html.gz`
- Create: `tests/fixtures/sec/nvda-2026-10k.html.gz`
- Create: `tests/fixtures/sec/nvda-2002-10k.html.gz`
- Create: `tests/fixtures/sec/nvda-2026-q2-10q.html.gz`
- Create: `tests/fixtures/sec/nvda-2026-08-26-8k.html.gz`
- Create: `tests/fixtures/sec/nvda-2026-ex99-1.html.gz`
- Create: `tests/fixtures/sec/nvda-2026-ex99-2.html.gz`
- Create: `tests/fixtures/sec/positioned-issue-4.html`

**Interfaces:**
- Consumes: the seven audited files in `C:\Users\einstein\AppData\Local\Temp\rcq-sec-html-bakeoff-7ae82a56c0e242d8aaa60a9adede59dd\filings` and the hashes in its two source manifests.
- Produces: frozen `FixtureContract` records; `load_fixture(fixture_id: str) -> tuple[FixtureContract, bytes]`; `audit_document(source: bytes, contract: FixtureContract, *, quality_policy: Literal["strict", "warn", "off"] = "off") -> AccuracyResult`; deterministic metric helpers used by all later tasks.

- [ ] **Step 1: Write the failing fixture integrity test**

Create `tests/accuracy/test_sec_accuracy.py`:

```python
import pytest

from tests.accuracy.fixtures import FIXTURE_IDS, load_fixture


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_fixture_hash_and_identity(fixture_id: str):
    contract, source = load_fixture(fixture_id)
    assert source
    assert contract.fixture_id == fixture_id
    assert contract.sha256 == __import__("hashlib").sha256(source).hexdigest()


def test_corpus_has_required_document_roles_and_forms():
    contracts = [load_fixture(fixture_id)[0] for fixture_id in FIXTURE_IDS]
    assert {contract.form for contract in contracts} >= {"10-K", "10-Q", "8-K"}
    assert {contract.role for contract in contracts} >= {"primary", "exhibit"}
    assert len(contracts) == 7
```

- [ ] **Step 2: Run the fixture test and verify RED**

Run: `.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py -v`

Expected: collection ERROR with `ModuleNotFoundError: No module named 'tests.accuracy.fixtures'`.

- [ ] **Step 3: Implement the immutable loader and typed contract**

Create `tests/accuracy/fixtures.py` with frozen dataclasses `RepresentativeRow(label: str, numbers: tuple[str, ...])` and `FixtureContract(fixture_id, filename, cik, accession, form, report_date, sec_url, role, sha256, expected_encoding_reason, min_word_recall, min_numeric_recall, min_financial_row_recall, expected_sections, representative_rows)`. Define:

```python
FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sec"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


def load_manifest() -> dict[str, FixtureContract]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["fixture_id"]: FixtureContract.from_dict(item) for item in raw["fixtures"]}


FIXTURE_IDS = tuple(load_manifest())


def load_fixture(fixture_id: str) -> tuple[FixtureContract, bytes]:
    contract = load_manifest()[fixture_id]
    compressed = (FIXTURE_ROOT / contract.filename).read_bytes()
    source = gzip.decompress(compressed)
    actual = hashlib.sha256(source).hexdigest()
    if actual != contract.sha256:
        raise ValueError(f"fixture hash mismatch for {fixture_id}: {actual}")
    return contract, source
```

`FixtureContract.from_dict` must convert JSON row number lists and section lists to tuples; no fixture loader writes to disk.

- [ ] **Step 4: Import and gzip the seven exact audited sources**

Use deterministic gzip (`mtime=0`, empty embedded filename) to create the seven files. Map source to destination exactly as follows:

```text
filings/aapl-2023/source.html -> aapl-2023-10k.html.gz
filings/nvda-2026/source.html -> nvda-2026-10k.html.gz
filings/nvda-2002/source.html -> nvda-2002-10k.html.gz
filings/nvda-2026-q2-10q/source.html -> nvda-2026-q2-10q.html.gz
filings/nvda-2026-08-26-8k/source.html -> nvda-2026-08-26-8k.html.gz
filings/nvda-2026-08-26-8k/exhibits/ex99-1-earnings-release.html -> nvda-2026-ex99-1.html.gz
filings/nvda-2026-08-26-8k/exhibits/ex99-2-cfo-commentary.html -> nvda-2026-ex99-2.html.gz
```

The manifest must contain these exact uncompressed SHA-256 values:

```text
aapl-2023-10k              bda1f34435199672c16ecdf2034c650872d2cac8399ed0d179fc25450b080b90
nvda-2026-10k              73d81f5a111abcf72426c840871e76f5f5edc9631f436d495a86b6f87306d58b
nvda-2002-10k              04136c61bb8ea9490da4916f358a2275f019ed6536878715da412d7056a0739d
nvda-2026-q2-10q           e2634e509c241c5f45e3f6c115dc38a85645e5fdbee760b4a04f5e9035f6f7a9
nvda-2026-08-26-8k         84335b3247873da9fc91b4d9aa146be012801158183a7e9b0e98f0d31e50d0ea
nvda-2026-ex99-1           1809cb206590dcfeb959f3a1a64157f4e5ee42788ec51289b74f3ea299931eb7
nvda-2026-ex99-2           6a522635d049044b2ff9ff63cb78220cf29d960e96614c88afe30560c3ee0659
```

Record CIK `0000320193`, accession `0000320193-23-000106`, and report date `2023-09-30` for Apple. Record CIK `0001045810` with accession/report-date pairs `0001012870-02-002262`/`2002-01-27`, `0001045810-26-000021`/`2026-01-25`, `0001045810-26-000075`/`2026-07-26`, and `0001045810-26-000073`/`2026-08-26` for the matching NVIDIA documents. Use the exact SEC archive URLs from the audited manifests. Floors must not exceed the audited baseline: modern primary documents `word >= 0.98`, `numeric >= 0.93`, `financial rows >= 0.99`; NVIDIA 2002 `word >= 0.99`, `numeric >= 0.95`, `financial rows >= 0.89`; EX-99.1 `0.99/0.98/0.97`; EX-99.2 `0.99/0.98/0.94`.

The manifest's representative rows must include these exact normalized series: Apple total net sales `383285,394328,365817`; NVIDIA 2026 revenue `215938,130497,60922`; NVIDIA 2002 revenue `1369471,735264,374505`; Q2 10-Q revenue `96221,46743,177837,90805`; EX-99.1 revenue `96221,81615,46743`; and EX-99.2 Data Center revenue `89023,75246,41096`. Expected sections are modern 10-K Items `1,1A,1B,1C,2,3,4,5,6,7,7A,8,9,9A,9B,9C,10,11,12,13,14,15,16`; legacy 10-K Items `1,2,3,4,5,6,7,7A,8,9,10,11,12,13,14`; the nine 10-Q pairs `PART I/ITEM 1-4` and `PART II/ITEM 1, ITEM 1A, ITEM 2, ITEM 5, ITEM 6`; Items `2.02` and `9.01` for the 8-K; and an empty section tuple for the two exhibits.

- [ ] **Step 5: Add the synthetic positioned-loss fixture**

Create `tests/fixtures/sec/positioned-issue-4.html` containing more than 1,000 visible characters inside nested absolutely positioned leaves, using CSS custom properties and `pt` coordinates:

```html
<html><head><style>
:root { --left: 36pt; --top: 72pt; }
.page { position: relative; width: 612pt; height: 792pt; }
.line { position: absolute; left: var(--left); top: var(--top); }
</style></head><body><div class="page"><div class="line"><span>
POSITIONED LOSS SENTINEL repeated in complete sentences until the visible text exceeds one thousand characters.
</span></div></div></body></html>
```

Repeat the complete sentence in the committed file until BeautifulSoup-visible text is at least 1,200 characters; do not generate it during the test.

- [ ] **Step 6: Implement baseline audit metrics**

Create `tests/accuracy/metrics.py` with frozen `AccuracyResult` fields for Markdown/pages/annotated-HTML hashes, word/numeric/financial-row recall, table-width errors, replacement/C1 counts, duplicate element IDs, missing mappings, trace failures, expected sections, and invalid visible-node XBRL tags. Implement deterministic `normalize_words`, `normalize_numbers`, `extract_financial_rows`, `multiset_recall`, and `audit_document`; `audit_document` must parse the same source twice with `quality_policy="off"` during the transitional baseline, then compare Markdown, JSON-canonicalized pages, and annotated HTML byte-for-byte. Task 8 changes this harness to strict mode after every known defect is removed. Use these concrete cores:

```python
WORD_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)
NUMBER_RE = re.compile(r"(?<!\w)(?:[$€£]\s*)?(?:\(?[−–-]?\d[\d,]*(?:\.\d+)?\)?%?)(?!\w)")


def multiset_recall(expected: Sequence[str], actual: Sequence[str]) -> float:
    expected_counts = Counter(expected)
    if not expected_counts:
        return 1.0
    actual_counts = Counter(actual)
    matched = sum(min(count, actual_counts[value]) for value, count in expected_counts.items())
    return matched / sum(expected_counts.values())


def canonical_pages(pages: Sequence[Page]) -> bytes:
    payload = [page.model_dump(mode="json") for page in pages]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()
```

Use these exact normalization rules: casefold words; normalize Unicode minus to `-`; remove `$`, commas, and surrounding accounting parentheses while preserving a leading negative sign; treat standalone em dash as blank; compare row labels after collapsing whitespace. Table width validation must compare every Markdown data/header row to its delimiter row.

- [ ] **Step 7: Add baseline assertions and document corpus provenance**

Parametrize `test_sec_accuracy.py` over all seven contracts and assert each contract's recall floors, representative rows, expected sections, consistent table widths, determinism, unique element IDs, and valid visible-node XBRL tags. For this baseline commit, record known defects as explicit `pytest.xfail` assertions keyed by fixture ID: 629 C1 controls and split accounting negative for `nvda-2002-10k`, lost exhibit URLs/fragmented text for `nvda-2026-08-26-8k`, and two trace failures for `aapl-2023-10k`. `tests/fixtures/sec/README.md` must name the SEC URLs, hashes, capture date evidence, gzip immutability rule, and the command `.\.venv\Scripts\python -m pytest tests/accuracy -v`.

- [ ] **Step 8: Verify GREEN baseline harness**

Run: `.\.venv\Scripts\python -m pytest tests/accuracy -v`

Expected: PASS with only the explicitly named known-defect XFAIL cases; no network access.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 9: Commit**

```powershell
git add tests/accuracy tests/fixtures/sec
git commit -m "test: add audited SEC accuracy corpus"
```

### Task 3: Add Parse Diagnostics and Catastrophic-Loss Enforcement

**Files:**
- Create: `src/sec2md/quality.py`
- Create: `tests/test_quality.py`
- Modify: `src/sec2md/core.py`
- Modify: `src/sec2md/parser.py`
- Modify: `src/sec2md/__init__.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_parser.py`
- Modify: `tests/accuracy/test_sec_accuracy.py`

**Interfaces:**
- Consumes: `Parser.get_pages(include_elements: bool = True, include_images: bool = True) -> list[Page]`, `Parser.markdown() -> str`, and the positioned fixture.
- Produces: frozen `ParseDiagnostics`; `ParseQualityError(ValueError)` with `.diagnostics`; `build_diagnostics(source_text: str, output: str, pages: Sequence[Page], *, mapped_element_ids: Collection[str], trace_failures: Sequence[str], enforce_mappings: bool) -> ParseDiagnostics`; `enforce_quality(diagnostics: ParseDiagnostics, policy: QualityPolicy) -> ParseDiagnostics`; `Parser.diagnostics: ParseDiagnostics | None`; public keyword-only `quality_policy` on both convenience APIs.

- [ ] **Step 1: Write failing policy and catastrophic-loss tests**

Create `tests/test_quality.py` with exact hard-failure cases:

```python
def test_strict_rejects_empty_output_from_substantial_source(monkeypatch):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    with pytest.raises(ParseQualityError) as exc:
        convert_to_markdown(source)
    assert exc.value.diagnostics.source_visible_chars >= 1000
    assert exc.value.diagnostics.output_visible_chars == 0


def test_warn_returns_output_and_logs_warning(monkeypatch, caplog):
    source = "<html><body><p>" + ("loss sentinel " * 100) + "</p></body></html>"
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    assert convert_to_markdown(source, quality_policy="warn") == ""
    assert "substantial source produced empty output" in caplog.text


def test_off_skips_quality_enforcement(monkeypatch):
    monkeypatch.setattr(Parser, "markdown", lambda self: "")
    assert convert_to_markdown("<p>" + ("x " * 600) + "</p>", quality_policy="off") == ""
```

Also test the `<0.10` ratio at 10,000 source-visible characters, U+FFFD, C1 controls, missing mappings when elements are requested, untraceable numbers, invalid policy values, and `parse_filing` strict-by-default behavior. The positioned fixture test must assert `ParseQualityError` rather than accepting an empty result.

Use a parametrized unit test for the character and trace failures:

```python
@pytest.mark.parametrize(
    ("output", "mapped_ids", "trace_failures", "message"),
    [
        ("bad \ufffd text", {"e1"}, (), "replacement character"),
        ("bad \u0092 text", {"e1"}, (), "C1 control character"),
        ("Revenue 123", set(), (), "element lacks a source-node mapping"),
        ("Revenue 123", {"e1"}, ("e1:123",), "untraceable normalized number"),
    ],
)
def test_strict_hard_failures(output, mapped_ids, trace_failures, message):
    element = Element(id="e1", content=output, kind="paragraph", page_start=1, page_end=1)
    pages = [Page(number=1, content=output, elements=[element])]
    diagnostics = build_diagnostics(
        "source " * 200,
        output,
        pages,
        mapped_element_ids=mapped_ids,
        trace_failures=trace_failures,
        enforce_mappings=True,
    )
    with pytest.raises(ParseQualityError, match=message):
        enforce_quality(diagnostics, "strict")
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.\.venv\Scripts\python -m pytest tests/test_quality.py tests/test_core.py -v`

Expected: collection ERROR because `sec2md.quality` and `ParseQualityError` do not exist and public APIs reject `quality_policy`.

- [ ] **Step 3: Implement immutable diagnostics and policy evaluation**

In `src/sec2md/quality.py`, add:

```python
QualityPolicy = Literal["strict", "warn", "off"]


@dataclass(frozen=True)
class ParseDiagnostics:
    source_visible_chars: int
    output_visible_chars: int
    output_ratio: float
    replacement_characters: int
    c1_control_characters: int
    pages: int
    elements: int
    mapped_elements: int
    trace_numeric_failures: tuple[str, ...]
    warnings: tuple[str, ...]


class ParseQualityError(ValueError):
    def __init__(self, diagnostics: ParseDiagnostics):
        self.diagnostics = diagnostics
        super().__init__("; ".join(diagnostics.warnings))
```

`build_diagnostics` counts visible source text with BeautifulSoup after removing `script`, `style`, `noscript`, and hidden inline-XBRL nodes. It counts output visible characters after removing Markdown syntax. It records the six exact hard failures from the spec. `enforce_quality` validates the policy, returns unchanged diagnostics for `off`, logs every warning for `warn`, and raises one `ParseQualityError` for any warning in `strict`.

Implement the decision core explicitly:

```python
def _hard_failure_messages(
    source_chars: int,
    output_chars: int,
    replacement_count: int,
    c1_count: int,
    missing_mapping_ids: Sequence[str],
    trace_failures: Sequence[str],
) -> tuple[str, ...]:
    failures: list[str] = []
    ratio = output_chars / source_chars if source_chars else 1.0
    if source_chars >= 1_000 and output_chars == 0:
        failures.append("substantial source produced empty output")
    if source_chars >= 10_000 and ratio < 0.10:
        failures.append(f"catastrophic output ratio {ratio:.6f} below 0.10")
    if replacement_count:
        failures.append(f"output contains {replacement_count} replacement characters")
    if c1_count:
        failures.append(f"output contains {c1_count} C1 control characters")
    if missing_mapping_ids:
        failures.append("element lacks a source-node mapping: " + ",".join(missing_mapping_ids))
    if trace_failures:
        failures.append("untraceable normalized number: " + ",".join(trace_failures))
    return tuple(failures)


def enforce_quality(diagnostics: ParseDiagnostics, policy: QualityPolicy) -> ParseDiagnostics:
    if policy not in {"strict", "warn", "off"}:
        raise ValueError(f"invalid quality_policy: {policy}")
    if policy == "off":
        return diagnostics
    if policy == "warn":
        for warning in diagnostics.warnings:
            logger.warning("sec2md quality: %s", warning)
        return diagnostics
    if diagnostics.warnings:
        raise ParseQualityError(diagnostics)
    return diagnostics
```

- [ ] **Step 4: Wire diagnostics through Parser and convenience APIs**

Initialize `Parser.diagnostics = None`. Add keyword-only `quality_policy: QualityPolicy = "strict"` to every `convert_to_markdown` overload/implementation and to `parse_filing`. Construct pages before enforcement when `return_pages` or `include_elements` requires them; pass `include_elements=False` into diagnostic mapping checks when the caller explicitly disables elements. After output construction, set `parser.diagnostics`, call `enforce_quality`, then return output. Export `ParseDiagnostics` and `ParseQualityError` from `sec2md.__init__`.

- [ ] **Step 5: Verify GREEN focused and regression tests**

Run: `.\.venv\Scripts\python -m pytest tests/test_quality.py tests/test_core.py tests/test_parser.py -v`

Expected: PASS, including strict/warn/off and positioned-loss behavior.

Run: `.\.venv\Scripts\python -m pytest -q`

Expected: all pre-existing tests PASS; accuracy known defects remain XFAIL, not unexpected failures.

- [ ] **Step 6: Commit**

```powershell
git add src/sec2md/quality.py src/sec2md/core.py src/sec2md/parser.py src/sec2md/__init__.py tests/test_quality.py tests/test_core.py tests/test_parser.py tests/accuracy/test_sec_accuracy.py
git commit -m "feat: fail closed on catastrophic parse loss"
```

### Task 4: Make Byte Decoding Deterministic and Normalize Legacy Characters

**Files:**
- Create: `src/sec2md/encoding.py`
- Create: `tests/test_encoding.py`
- Modify: `src/sec2md/core.py`
- Modify: `src/sec2md/utils.py`
- Modify: `src/sec2md/parser.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_utils.py`
- Modify: `tests/accuracy/test_sec_accuracy.py`

**Interfaces:**
- Consumes: byte input and HTTP `response.content`, optional response `Content-Type` charset, `ParseDiagnostics` character checks.
- Produces: frozen `DecodeDiagnostics(encoding: str, reason: str)`; `decode_html(data: bytes, *, http_charset: str | None = None) -> tuple[str, DecodeDiagnostics]`; `normalize_legacy_characters(text: str) -> str`; `FetchedHtml(content: bytes, charset: str | None)` from `fetch`.

- [ ] **Step 1: Write the decoder precedence tests**

Create `tests/test_encoding.py` with parametrized cases proving BOM beats HTTP/declaration, recognized HTTP charset beats declaration, declaration in only the first 8 KiB beats strict UTF-8, strict UTF-8 beats fallback, Windows-1252 is the last fallback, and unknown explicit HTTP/declaration encodings raise `ValueError`. Include:

```python
def test_windows_1252_fallback_and_legacy_entity_normalization():
    decoded, diagnostics = decode_html(b"<p>GPU\x92s &#151; outlook</p>")
    assert diagnostics == DecodeDiagnostics("windows-1252", "windows-1252-fallback")
    assert normalize_legacy_characters(decoded) == "<p>GPU’s — outlook</p>"


def test_decoder_never_drops_invalid_bytes():
    decoded, _ = decode_html(b"<p>\x81</p>")
    assert "\ufffd" not in decoded
    with pytest.raises(ValueError, match="undefined Windows-1252 byte"):
        normalize_legacy_characters(decoded)
```

Add an HTTP mock test asserting `fetch` reads `response.content`, not `response.text`, and passes the explicit charset separately.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.\.venv\Scripts\python -m pytest tests/test_encoding.py tests/test_utils.py tests/test_core.py -v`

Expected: collection ERROR because `sec2md.encoding` and `DecodeDiagnostics` do not exist.

- [ ] **Step 3: Implement deterministic decoding**

In `src/sec2md/encoding.py`, implement the precedence exactly: UTF-8/16/32 BOM; recognized explicit HTTP charset; case-insensitive HTML `<meta charset>` or `<meta http-equiv=...charset=...>` and XML declaration within `data[:8192]`; strict UTF-8; strict Windows-1252. Canonicalize codec labels via `codecs.lookup`; reject an explicit unknown codec. Never use `errors="ignore"` or `errors="replace"`.

The selector must have one exit per precedence level:

```python
def decode_html(data: bytes, *, http_charset: str | None = None) -> tuple[str, DecodeDiagnostics]:
    bom = _detect_bom(data)
    if bom is not None:
        encoding, prefix = bom
        return data[len(prefix):].decode(encoding), DecodeDiagnostics(encoding, "bom")
    if http_charset is not None:
        encoding = _canonical_explicit_encoding(http_charset)
        return data.decode(encoding), DecodeDiagnostics(encoding, "http-charset")
    declared = _find_declared_encoding(data[:8192])
    if declared is not None:
        encoding = _canonical_explicit_encoding(declared)
        return data.decode(encoding), DecodeDiagnostics(encoding, "document-declaration")
    try:
        return data.decode("utf-8"), DecodeDiagnostics("utf-8", "strict-utf-8")
    except UnicodeDecodeError:
        decoded = _decode_windows_1252_preserving_undefined(data)
        return decoded, DecodeDiagnostics("windows-1252", "windows-1252-fallback")
```

Normalize numeric character references `&#128;` through `&#159;` before BeautifulSoup parses them, then map remaining literal U+0080-U+009F characters with the Windows-1252 table. Raise `ValueError` for undefined bytes `0x81`, `0x8d`, `0x8f`, `0x90`, and `0x9d`; preserve ordinary Unicode punctuation, Unicode minus, and em-dash blank markers.

- [ ] **Step 4: Route direct and HTTP bytes through one decoder**

Change `utils.fetch` to return:

```python
@dataclass(frozen=True)
class FetchedHtml:
    content: bytes
    charset: str | None


def fetch(url: str, user_agent: str | None = None) -> FetchedHtml:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return FetchedHtml(response.content, _content_type_charset(response.headers.get("Content-Type")))
```

Change `_resolve_source` to return `(html: str, decode_diagnostics: DecodeDiagnostics | None)`. Raw `str` input keeps `decode_diagnostics=None` but still runs legacy-character normalization. Byte and URL inputs call `decode_html` then normalization. Preserve the existing PDF guard before decoding. Store the latest decode diagnostics on `Parser` without changing `ParseDiagnostics` fields.

- [ ] **Step 5: Turn the legacy C1 XFAIL into a passing assertion**

In `tests/accuracy/test_sec_accuracy.py`, remove only the `nvda-2002-10k` C1 XFAIL and assert `replacement_characters == 0` and `c1_control_characters == 0` for all seven fixtures. Assert the legacy contract reports the Windows-1252 fallback/declaration path recorded in its manifest.

- [ ] **Step 6: Verify GREEN focused, legacy, and full tests**

Run: `.\.venv\Scripts\python -m pytest tests/test_encoding.py tests/test_utils.py tests/test_core.py -v`

Run: `.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py -k "nvda_2002 or character" -v`

Expected: PASS; the legacy Markdown contains zero U+FFFD and zero U+0080-U+009F.

Run: `.\.venv\Scripts\python -m pytest -q`

Expected: PASS with only the remaining accounting/link/provenance XFAILs.

- [ ] **Step 7: Commit**

```powershell
git add src/sec2md/encoding.py src/sec2md/core.py src/sec2md/utils.py src/sec2md/parser.py tests/test_encoding.py tests/test_utils.py tests/test_core.py tests/accuracy/test_sec_accuracy.py tests/fixtures/sec/manifest.json
git commit -m "feat: decode SEC HTML deterministically"
```

### Task 5: Reconstruct Accounting Columns Without Changing Signs

**Files:**
- Modify: `src/sec2md/table_parser.py`
- Modify: `src/sec2md/quality.py`
- Modify: `tests/test_table_parser.py`
- Modify: `tests/test_quality.py`
- Modify: `tests/accuracy/test_sec_accuracy.py`

**Interfaces:**
- Consumes: `TableParser.grid`, structural cell strings, and the numeric trace normalizer.
- Produces: `normalize_numeric_token(value: str) -> str | None`; `_classify_structural_column(values: Sequence[str]) -> Literal["currency", "open_paren", "close_paren", "percent"] | None`; safe column-wide structural merging.

- [ ] **Step 1: Write failing accounting-grid tests**

Add to `tests/test_table_parser.py`:

```python
def test_accounting_parentheses_merge_into_one_markdown_cell():
    html = """
    <table><tr><th>Item</th><th></th><th>2022</th><th></th></tr>
    <tr><td>Net loss</td><td>(</td><td>16,173</td><td>)</td></tr>
    <tr><td>Operating loss</td><td>(</td><td>9,501</td><td>)</td></tr></table>
    """
    matrix = TableParser(_make_table(html)).to_matrix()
    assert matrix[1] == ["Net loss", "(16,173)"]
    assert matrix[2] == ["Operating loss", "(9,501)"]


def test_mixed_parenthesis_column_does_not_merge():
    html = """
    <table><tr><th>Label</th><th>Qualifier</th><th>Value</th></tr>
    <tr><td>A</td><td>(unaudited)</td><td>10</td></tr>
    <tr><td>B</td><td>note</td><td>20</td></tr></table>
    """
    assert len(TableParser(_make_table(html)).to_matrix()[0]) == 3
```

Add numeric tests asserting `normalize_numeric_token("$ (16,173)") == "-16173"`, `normalize_numeric_token("−42") == "-42"`, `normalize_numeric_token("65%") == "65"`, and `normalize_numeric_token("—") is None`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.\.venv\Scripts\python -m pytest tests/test_table_parser.py tests/test_quality.py -v`

Expected: FAIL because the closing parenthesis remains in a separate column and `normalize_numeric_token` is absent.

- [ ] **Step 3: Implement numeric normalization and safe structural-column classification**

In `quality.py`, normalize only complete numeric tokens: strip Markdown emphasis, whitespace, currency markers, commas, and percent; translate Unicode minus; turn balanced accounting parentheses into one leading `-`; reject partial tokens such as `"("`, `")"`, and mixed prose.

Use this exact return contract:

```python
def normalize_numeric_token(value: str) -> str | None:
    cleaned = value.strip().translate(str.maketrans({"−": "-", "–": "-"}))
    if cleaned in {"", "—", "-"}:
        return None
    accounting = cleaned.startswith("(") and cleaned.endswith(")")
    if cleaned.startswith("(") != cleaned.endswith(")"):
        return None
    cleaned = cleaned.strip("()").replace(",", "").replace("$", "").replace("%", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    if accounting and not cleaned.startswith("-"):
        cleaned = "-" + cleaned
    return cleaned
```

In `table_parser.py`, classify a column only when every non-empty body cell belongs to the same structural class and at least two body rows demonstrate the pattern. Merge currency/open-parenthesis columns to the right numeric column; merge closing-parenthesis/percent columns to the left related numeric column. Keep one header cell for the merged span, preserve row width, and do not merge a column containing prose or unmatched mixed markers.

Implement classification with a closed marker map and a two-row floor:

```python
StructuralColumn = Literal["currency", "open_paren", "close_paren", "percent"]
STRUCTURAL_MARKERS: dict[str, StructuralColumn] = {
    "$": "currency",
    "(": "open_paren",
    ")": "close_paren",
    "%": "percent",
}


def _classify_structural_column(values: Sequence[str]) -> StructuralColumn | None:
    nonempty = [value.strip() for value in values if value.strip()]
    if len(nonempty) < 2:
        return None
    classes = {STRUCTURAL_MARKERS.get(value) for value in nonempty}
    if None in classes or len(classes) != 1:
        return None
    return cast(StructuralColumn, classes.pop())
```

- [ ] **Step 4: Turn the legacy accounting XFAIL into a passing assertion**

Replace the `nvda-2002-10k` accounting XFAIL with assertions that the representative row containing `16,173` has one cell containing `(16,173)`, no neighboring cell equal to `)`, and normalized value `-16173`. Retain all fixture-specific recall floors and consistent-width checks.

- [ ] **Step 5: Verify GREEN focused, legacy, and full tests**

Run: `.\.venv\Scripts\python -m pytest tests/test_table_parser.py tests/test_quality.py -v`

Run: `.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py -k nvda_2002 -v`

Expected: PASS with correct sign and consistent Markdown widths.

Run: `.\.venv\Scripts\python -m pytest -q`

Expected: PASS with only link and Apple provenance XFAILs.

- [ ] **Step 6: Commit**

```powershell
git add src/sec2md/table_parser.py src/sec2md/quality.py tests/test_table_parser.py tests/test_quality.py tests/accuracy/test_sec_accuracy.py
git commit -m "fix: reconstruct SEC accounting columns"
```

### Task 6: Render Inline Links Correctly and Preserve 8-K Exhibit URLs

**Files:**
- Modify: `src/sec2md/table_parser.py`
- Modify: `src/sec2md/parser.py`
- Modify: `src/sec2md/core.py`
- Modify: `src/sec2md/models.py`
- Modify: `src/sec2md/section_extractor.py`
- Modify: `tests/test_table_parser.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_section_extractor.py`
- Modify: `tests/test_core.py`
- Modify: `tests/accuracy/test_sec_accuracy.py`

**Interfaces:**
- Consumes: a table cell DOM node and optional document source URL.
- Produces: `render_cell_content(cell: Tag, *, base_url: str | None = None) -> str`; `TableParser(table_element: Tag, *, base_url: str | None = None)`; `Parser(html: str, *, source_url: str | None = None)`; `Exhibit.url: str | None`.

- [ ] **Step 1: Write failing inline-renderer and exhibit tests**

Add to `tests/test_table_parser.py`:

```python
def test_adjacent_fragments_with_same_href_coalesce():
    html = '<table><tr><td><a href="ex99.htm">Augu</a><a href="ex99.htm">st 26</a></td></tr></table>'
    parser = TableParser(_make_table(html), base_url="https://www.sec.gov/Archives/a/filing.htm")
    assert parser.to_matrix()[0][0] == "[August 26](https://www.sec.gov/Archives/a/ex99.htm)"


def test_distinct_links_remain_distinct_and_pipe_is_escaped():
    html = '<table><tr><td><a href="a.htm">First</a> | <a href="b.htm">Second</a></td></tr></table>'
    rendered = TableParser(_make_table(html), base_url=None).to_matrix()[0][0]
    assert rendered == "[First](a.htm) \\| [Second](b.htm)"
```

Add a section-extractor test with `| 99.1 | [Earnings Release](q2fy27pr.htm) |` asserting `Exhibit(exhibit_no="99.1", description="Earnings Release", url="q2fy27pr.htm")`, plus an absolute-source-URL integration test asserting resolution to the SEC archive URL. Add a raw-HTML test asserting relative URLs remain relative.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.\.venv\Scripts\python -m pytest tests/test_table_parser.py tests/test_section_extractor.py tests/test_models.py tests/test_core.py -v`

Expected: FAIL because fragments are separated, `TableParser`/`Parser` do not accept a base/source URL, and `Exhibit` rejects `url`.

- [ ] **Step 3: Implement DOM-aware inline rendering**

Walk direct descendants in DOM order. Preserve whitespace already present in `NavigableString`; concatenate inline descendants with no invented separator; insert one space or line break around block descendants (`div`, `p`, `br`, `li`, headings); render `<a>` as Markdown; coalesce consecutive anchors only when their resolved `href` values are identical; resolve relative links with `urljoin(base_url, href)` only when `base_url` exists. Collapse duplicate whitespace after structural rendering, not between same-link fragments. Escape `|` only in visible table text, never inside the link destination.

Represent rendered fragments before joining so link destinations are never escaped:

```python
@dataclass(frozen=True)
class InlineFragment:
    text: str
    href: str | None = None
    boundary: bool = False


def render_cell_content(cell: Tag, *, base_url: str | None = None) -> str:
    fragments = _inline_fragments(cell, base_url=base_url)
    merged = _coalesce_same_href(fragments)
    rendered: list[str] = []
    for fragment in merged:
        text = fragment.text.replace("|", r"\|")
        rendered.append(f"[{text}]({fragment.href})" if fragment.href else text)
    return _collapse_structural_whitespace("".join(rendered)).strip()
```

- [ ] **Step 4: Propagate the document URL and add structured exhibit URLs**

Pass `source_url` from `core.py` into `Parser`, and from `Parser` into every `TableParser`. Add `url: str | None = Field(None, description="Resolved or source-relative exhibit URL")` to `Exhibit`. In `_parse_exhibits`, parse the right cell with `re.fullmatch(r"\[([^]]+)]\(([^)]+)\)")`; store group 1 as description and group 2 as URL. When the description contains surrounding prose, retain the full human-readable description and the first Markdown-link URL.

- [ ] **Step 5: Turn the 8-K link XFAILs into passing assertions**

Require the primary 8-K Markdown to exclude `Augu st 2 6` and `Se cond`, include readable `August 26` and `Second`, and expose EX-99.1/EX-99.2 URLs ending in `q2fy27pr.htm` and `q2fy27cfocommentary.htm`. Keep a separate assertion that `sec2md` did not fetch either exhibit.

- [ ] **Step 6: Verify GREEN focused, 8-K, and full tests**

Run: `.\.venv\Scripts\python -m pytest tests/test_table_parser.py tests/test_section_extractor.py tests/test_models.py tests/test_core.py -v`

Run: `.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py -k "8k or ex99" -v`

Expected: PASS with readable link text and retained absolute exhibit URLs for URL input; relative links remain relative for raw HTML.

Run: `.\.venv\Scripts\python -m pytest -q`

Expected: PASS with only Apple provenance XFAILs.

- [ ] **Step 7: Commit**

```powershell
git add src/sec2md/table_parser.py src/sec2md/parser.py src/sec2md/core.py src/sec2md/models.py src/sec2md/section_extractor.py tests/test_table_parser.py tests/test_models.py tests/test_section_extractor.py tests/test_core.py tests/accuracy/test_sec_accuracy.py
git commit -m "feat: preserve SEC exhibit links"
```

### Task 7: Enforce Source-Node Provenance and Repair Merged-Block Traces

**Files:**
- Modify: `src/sec2md/element_builder.py`
- Modify: `src/sec2md/parser.py`
- Modify: `src/sec2md/quality.py`
- Modify: `tests/test_parser.py`
- Modify: `tests/test_quality.py`
- Modify: `tests/accuracy/metrics.py`
- Modify: `tests/accuracy/test_sec_accuracy.py`

**Interfaces:**
- Consumes: `(Element, list[Tag], text_block)` tuples from `_group_segments_into_blocks` and `_merge_small_blocks`, annotated source-node IDs, and `normalize_numeric_token`.
- Produces: `trace_numeric_failures(element: Element, nodes: Sequence[Tag]) -> tuple[str, ...]`; complete stable source-node unions for every emitted element; visible-node-only XBRL tags.

- [ ] **Step 1: Write failing provenance and numeric-trace tests**

Add focused tests that construct two small paragraphs which merge into one element, with a repeated proxy paragraph and a generated table heading. Assert the merged element maps to the ordered union of every contributing source node, each source node contains the element ID annotation, and XBRL tags come only from visible mapped nodes. Add:

```python
def test_untraceable_normalized_number_is_reported():
    element = Element(id="e1", content="Revenue $1,234", kind="paragraph", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<p>Revenue 999</p>", "lxml").p]
    assert trace_numeric_failures(element, nodes) == ("e1:1234",)


def test_accounting_format_change_remains_traceable():
    element = Element(id="e1", content="Loss (16,173)", kind="table", page_start=1, page_end=1)
    nodes = [BeautifulSoup("<td>(</td><td>16,173</td><td>)</td>", "lxml").body]
    assert trace_numeric_failures(element, nodes) == ()
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.\.venv\Scripts\python -m pytest tests/test_parser.py tests/test_quality.py -v`

Expected: FAIL because `trace_numeric_failures` is absent or the merged element omits one or more contributing nodes.

- [ ] **Step 3: Preserve ordered node unions through every merge**

Introduce one helper `ordered_unique_nodes(*groups: Sequence[Tag]) -> list[Tag]` keyed by object identity. Use it in segment grouping, `_merge_small_blocks`, repeated proxy-reference handling, and generated headings derived from table nodes. Reject element construction with non-empty content and an empty node list. Annotate all mapped nodes with the final element ID after merges, removing stale pre-merge IDs.

Use object identity, not BeautifulSoup tag equality:

```python
def ordered_unique_nodes(*groups: Sequence[Tag]) -> list[Tag]:
    result: list[Tag] = []
    seen: set[int] = set()
    for group in groups:
        for node in group:
            identity = id(node)
            if identity not in seen:
                seen.add(identity)
                result.append(node)
    return result
```

- [ ] **Step 4: Implement normalized numeric tracing and visible-node XBRL boundary**

Extract normalized numeric tokens from each element and the concatenated text of its mapped nodes. Compare as multisets so duplicate values are accounted for. Report `element-id:token` once per missing occurrence. Ignore standalone blank em dashes and formatting-only currency/percent/parenthesis differences. `_extract_xbrl_tags` must ignore hidden nodes (`display:none`, `visibility:hidden`, `hidden`, or ancestors under `ix:hidden`) and must never advertise a filing-wide XBRL inventory.

Implement multiset trace accounting directly:

```python
def trace_numeric_failures(element: Element, nodes: Sequence[Tag]) -> tuple[str, ...]:
    expected = Counter(_normalized_numbers(element.content))
    available = Counter(_normalized_numbers(" ".join(node.get_text(" ", strip=True) for node in nodes)))
    failures: list[str] = []
    for token, count in sorted(expected.items()):
        failures.extend(f"{element.id}:{token}" for _ in range(max(0, count - available[token])))
    return tuple(failures)


def _normalized_numbers(text: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for match in re.finditer(r"(?:[$€£]\s*)?\(?[−–-]?\d[\d,]*(?:\.\d+)?\)?%?", text):
        token = normalize_numeric_token(match.group(0))
        if token is not None:
            normalized.append(token)
    return tuple(normalized)
```

- [ ] **Step 5: Make diagnostics use actual mappings and turn Apple XFAILs GREEN**

Have `Parser` retain the final element-to-node mapping used by annotated HTML. Feed actual `elements`, `mapped_elements`, and `trace_numeric_failures` to `build_diagnostics`; do not infer mappings from element counts. Remove the two Apple provenance XFAILs and require zero missing mappings and zero numeric trace failures for all seven fixtures.

- [ ] **Step 6: Verify GREEN focused, Apple, and full tests**

Run: `.\.venv\Scripts\python -m pytest tests/test_parser.py tests/test_quality.py -v`

Run: `.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py -k aapl_2023 -v`

Expected: PASS with complete mappings, zero trace failures, unique element IDs, and no invalid visible-node XBRL concepts.

Run: `.\.venv\Scripts\python -m pytest -q`

Expected: PASS with no accuracy XFAILs remaining.

- [ ] **Step 7: Commit**

```powershell
git add src/sec2md/element_builder.py src/sec2md/parser.py src/sec2md/quality.py tests/test_parser.py tests/test_quality.py tests/accuracy/metrics.py tests/accuracy/test_sec_accuracy.py
git commit -m "fix: enforce element source provenance"
```

### Task 8: Lock Full Accuracy Gates, Release Documentation, and Build Evidence

**Files:**
- Modify: `tests/accuracy/test_sec_accuracy.py`
- Modify: `tests/fixtures/sec/manifest.json`
- Modify: `tests/fixtures/sec/README.md`
- Modify: `README.md`
- Modify: `docs/api/convert_to_markdown.md`
- Modify: `docs/usage/direct-conversion.md`
- Modify: `CHANGELOG.md`
- Modify: `.github/workflows/ci.yml`
- Create: `docs/maintenance/release-0.1.22-rcq.1.md`

**Interfaces:**
- Consumes: all prior public interfaces, the seven fixture contracts, and required local/CI commands.
- Produces: zero-XFAIL release acceptance suite; documented strict/warn/off and exhibit-link semantics; reproducible build/metadata evidence; independent committed-state review gate.

- [ ] **Step 1: Write the failing release-contract test**

Add a session fixture plus one unmarked test that loads all seven results twice and asserts the complete release contract:

```python
@pytest.fixture(scope="session")
def all_accuracy_results():
    results = []
    for fixture_id in FIXTURE_IDS:
        contract, source = load_fixture(fixture_id)
        first = audit_document(source, contract, quality_policy="strict")
        second = audit_document(source, contract, quality_policy="strict")
        results.append((contract, first, second))
    return tuple(results)


def test_rcq_release_contract(all_accuracy_results):
    assert len(all_accuracy_results) == 7
    for contract, first, second in all_accuracy_results:
        assert first.markdown_sha256 == second.markdown_sha256
        assert first.pages_sha256 == second.pages_sha256
        assert first.annotated_html_sha256 == second.annotated_html_sha256
        assert first.word_recall >= contract.min_word_recall
        assert first.numeric_recall >= contract.min_numeric_recall
        assert first.financial_row_recall >= contract.min_financial_row_recall
        assert first.inconsistent_table_widths == ()
        assert first.replacement_characters == 0
        assert first.c1_control_characters == 0
        assert first.duplicate_element_ids == ()
        assert first.missing_element_mappings == ()
        assert first.trace_numeric_failures == ()
        assert first.invalid_xbrl_tags == ()
        assert set(contract.expected_sections) <= set(first.sections)
```

Add explicit assertions for legacy `-16173`, Items 2.02 and 9.01, both EX-99 URLs, and representative 10-K/10-Q statement rows from the manifest. Assert `not list(Path("tests").rglob("*.html"))` except `positioned-issue-4.html`, so authoritative SEC sources stay gzip-compressed.

- [ ] **Step 2: Run the release contract and verify RED if any known defect remains**

Run: `.\.venv\Scripts\python -m pytest tests/accuracy/test_sec_accuracy.py::test_rcq_release_contract -v`

Expected before final cleanup: FAIL if any XFAIL marker, missing manifest expectation, nondeterministic serialization, or unresolved release criterion remains. Do not lower a recall floor or delete a representative row to make this pass; repair the owning implementation task instead.

- [ ] **Step 3: Remove transitional XFAILs and finalize fixture contracts**

Remove every accuracy `xfail`; change `audit_document` from the transitional `quality_policy="off"` to `quality_policy="strict"`; set the final manifest encoding reasons, expected sections, representative rows/signs, and floors to the already-audited values from Task 2. Keep runtime ratio at `0.10`; do not substitute aggregate recall for representative-row or provenance assertions.

- [ ] **Step 4: Finalize public documentation**

Document public signatures with keyword-only `quality_policy`, strict default behavior, `ParseQualityError.diagnostics`, deterministic decode precedence, supported HTML-only input, and the raw-HTML versus URL relative-link rule. State verbatim in README/API docs: “Exhibit parsing extracts exhibit entries and preserves their links; sec2md does not download those exhibits automatically. Complete accession capture is the caller's responsibility.” Mark `0.1.22+rcq.1` released in `CHANGELOG.md` only after all local gates pass.

- [ ] **Step 5: Record release evidence without creating the tag**

Create `docs/maintenance/release-0.1.22-rcq.1.md` containing baseline commit, final commit, fixture hashes, exact commands, exit codes, wheel filename/hash, wheel metadata assertions, CI run URL once available, and independent review verdict. Until CI and review exist, use explicit state labels `LOCAL_VERIFIED`, `CI_PENDING`, and `REVIEW_PENDING`; do not write empty fields or claim release readiness.

- [ ] **Step 6: Run the complete local release gates**

Run in order:

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check src tests
if (Test-Path dist) { Remove-Item -LiteralPath dist -Recurse -Force }
.\.venv\Scripts\python -m build
.\.venv\Scripts\python -c "from importlib.metadata import version; assert version('sec2md') == '0.1.22+rcq.1'"
git diff --check
git status --short
```

Expected: tests PASS with `0 failed` and `0 xfailed`; Ruff PASS; sdist and wheel build; metadata assertion PASS; no whitespace errors; status lists only the intended Task 8 files before commit.

- [ ] **Step 7: Commit the release candidate**

```powershell
git add tests/accuracy/test_sec_accuracy.py tests/fixtures/sec/manifest.json tests/fixtures/sec/README.md README.md docs/api/convert_to_markdown.md docs/usage/direct-conversion.md CHANGELOG.md .github/workflows/ci.yml docs/maintenance/release-0.1.22-rcq.1.md
git commit -m "release: prepare sec2md 0.1.22+rcq.1"
```

- [ ] **Step 8: Verify the committed state**

Run:

```powershell
git status --short --branch
git log -8 --oneline
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m build
```

Expected: clean `codex/rcq-hardening-v1`; eight independently reviewable implementation commits after the design; all gates PASS from committed state.

- [ ] **Step 9: Obtain independent committed-state review**

Give the reviewer the spec path, this plan path, baseline `a243bd782cd9d20a6e0f69c04bc484ea069d0e51`, release-candidate commit, full test/Ruff/build output, and fixture manifest. Require a written `APPROVE` or `BLOCK` verdict covering: spec scope, strict failure behavior, decode precedence, accounting signs, 8-K URLs, provenance/numeric trace, fixture integrity, CI matrix, metadata, and no accession-crawler scope leakage. If blocked, add a new RED-GREEN fix commit and repeat Steps 6-9.

- [ ] **Step 10: Stop before tag/push and request release authorization**

Do not create `v0.1.22-rcq.1`, push the branch, publish a package, or update `rcq-wealth` in this plan. Report the clean release-candidate commit, independent verdict, CI status, and exact proposed tag command for separate user authorization.

---

## Spec Coverage Self-Review

- Scope boundary: Tasks 1 and 8 document one-document parsing and explicitly exclude accession acquisition, full XBRL, PDF/OCR/Datalab, and research systems.
- Compatibility/versioning: Task 1 fixes fork URLs, upstream attribution, Python 3.10-3.12, `0.1.22+rcq.1`, and tag rules without changing the import name.
- Input resolution/normalization: Task 4 implements all five decode-precedence steps, `response.content`, no lossy error mode, numeric entities, C1 mapping, and undefined-byte failure.
- Diagnostics/fail-closed: Task 3 covers every threshold, strict/warn/off, parser diagnostics, keyword-only APIs, and positioned catastrophic loss.
- Table fidelity: Tasks 5 and 6 separate safe accounting-column reconstruction from DOM-aware inline/link rendering and retain header/table widths.
- Links/exhibits: Task 6 propagates source URLs, keeps raw relative links relative, adds `Exhibit.url`, and explicitly does not fetch exhibits.
- Provenance/XBRL: Task 7 enforces complete node unions, numeric trace multisets, and visible-node-only concepts without claiming a full filing inventory.
- Regression corpus: Task 2 fixes seven authoritative hashes, identities, roles, floors, determinism, sections, rows, mappings, and the positioned synthetic case.
- CI/docs/release: Tasks 1 and 8 cover Linux 3.10/3.12, Windows 3.12, Ruff, build metadata, public docs, changelog, exact local gates, and independent committed-state review.
- Placeholder scan: passed; every action names concrete code, commands, assertions, and expected outcomes.
- Type consistency: `DecodeDiagnostics`, `ParseDiagnostics`, `ParseQualityError`, `QualityPolicy`, `FixtureContract`, `AccuracyResult`, `FetchedHtml`, `normalize_numeric_token`, `trace_numeric_failures`, `Exhibit.url`, and public `quality_policy` names/signatures are consistent across producing and consuming tasks.
