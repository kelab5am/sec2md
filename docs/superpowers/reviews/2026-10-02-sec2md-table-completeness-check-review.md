# Review: sec2md Table Completeness Check Design

- **Spec:** `../specs/2026-10-02-sec2md-table-completeness-check-design.md`
- **Reviewer:** Astra
- **Round 1:** reviewed revision 1 (merged in pull request #3); resolved in revision 2
- **Round 2:** reviewed revision 2; resolved in revision 3
- **Round 3:** reviewed revision 3; resolved in revision 4
- **Round 4:** reviewed revision 4; resolved in revision 5
- **Round 5:** reviewed revision 5; resolved in revision 6 (2026-10-02)
- **Round 6:** reviewed the Phase A corpus record on merged `main` at `8bf0c1e` (2026-10-04); Phase A complete as a report-only milestone, with Phase B prerequisites below

Each finding was reproduced before it was resolved. The reproduction scripts are in
`../audits/2026-10-02-repo-audit/prototypes/`:
- `v2/` for round 1
- `v3/` for round 2
- `v4/` for round 3
- `v5/` for round 4
- `v6/` for round 5. `review_cases_v6.py` runs every case from all five rounds,
  in both rendering modes.

# Round 1 (revision 1)

## Findings and resolutions

### 1. [P1] Nearby prose can conceal a missing table value

**Finding.** The comparison counted every number in the mapped elements, and
those elements can include preceding prose. A table lost `9,943` while nearby
prose supplied the same number, and the check reported nothing.

**Verified.** Elements group captions and prose with the table. The case gave no
finding under revision 1.

**Resolution.** Each table is now compared only with its own *output segment*:
the exact string the parser emitted for that table in the page stream. Link and
image destinations are stripped before tokenizing. Re-running the evidence
showed that their digits could also hide a lost value. Revision 2 reports
`9943` missing.

### 2. [P1] Source token extraction inherits numeric corruption

**Finding.** `get_text(" ")` turns `1,2<span>34</span>` into `12` and `34`, so the
corrupted output passes. Hidden descendants of visible cells were included.
`€123` and `£456` were dropped by the normalizer.

**Verified.** All three hold. `normalize_numeric_token` strips only `$`.

**Resolution.** Cell text is now built by walking the DOM:
- Inline pieces are concatenated, with spaces only at block boundaries.
- Hidden descendants are skipped.
- Footnote markers are separated from the value text.

Number handling changes too:
- `€` and `£` are normalized like `$`.
- A hyphen between two numbers is a range separator.
- Tokenizing never crosses a cell boundary.

Revision 2 reports `1234` missing, excludes the hidden `999`, and checks the `€`
and `£` values.

### 3. [P1] Single-digit financial values must not automatically be "minor"

**Finding.** Under D4, a lost financial value of `9` would never fail strict.

**Verified.** It was reported as minor and could not fail strict.

**Resolution.** Digit count is no longer used. Tokens are classified by source
context:
- **marker:** `<sup>`, `vertical-align: super`, or `(n)`/`[n]`/`*` fragment links.
- **reference:** item, note, exhibit, part or schedule identifiers, exhibit
  indexes, and signature dates.

Both classes are reported only. Every other token is a **value** and is
enforced. Revision 2 reports the lost `$9` as an enforced value.

### 4. [P2] Nested-table ownership and numbering are inconsistent

**Finding.** Nested tables were defined as separate, but they have no mapped
element of their own. Table ordinals did not necessarily match snapshot
ordinals: a preceding one-row table makes them diverge.

**Verified.**
- Inner tables are rendered only through their outer table.
- Snapshots exist only for HTML tables with more than one effective row
  (`parser.py:758`), plus positioned groups (`parser.py:644`).

**Resolution.**
- The unit is the visible outermost table. Nested cells belong to it and are
  counted once.
- Ordinals number those units in document order, including one-row tables.
- Findings also give the snapshot ordinal.

### 5. [P2] The row-order evidence does not implement the written algorithm

**Finding.** The prototype included header rows, which the spec excludes. With
the exclusion applied, the fixture results went from eight differences to zero.

**Verified.** The prototype compared header rows.

**Resolution.** Check 2 is redefined. Each source row with two or more tokens must
appear, in the same left-to-right order, within one output body line after the
separator. Header lines are excluded, and matching is monotonic.
- The prototype implements exactly this algorithm, and the evidence was
  regenerated from it.
- Result: 0 differences on the fixtures and on the 20 RCQ filings.
- The reversed-columns mutation is still caught in 51 of 57 AAPL tables.

### 6. [P2] XLSX diagnostics will not automatically expose the new fields

**Finding.** `XlsxExportResult.diagnostics` holds warning strings, not
`ParseDiagnostics`. Phase A keeps the new findings out of warnings, so they would
be discarded.

**Verified.** `xlsx.py` builds `diagnostics` from `diagnostics.warnings`.

**Resolution.** Trailing defaulted fields are added:
- `XlsxExportResult.parse_diagnostics`
- `XlsxTableResult.completeness`, matched by snapshot ordinal

Phase A leaves `status`, `issues` and `diagnostics` unchanged. In Phase B,
value-class failures also enter the table's `issues`.

## Other changes found while resolving

- The revision 1 statement that enforcing now would fail "all 20" RCQ filings
  was wrong. It is 18 of 20.
- Decision D5 (`include_elements=False`) is resolved: the checks no longer depend
  on elements.
- Revision 1's nvda-2002 `ITEM 8.`/`ITEM 9.` flags were element-text losses. The
  page Markdown keeps both headings, so they moved to Deferred as an
  element-divergence check.

# Round 2 (revision 2)

### 1. [P1] Reference classification exempts financial amounts

**Finding.** Revision 2 classified every token in a matching row as reference
only. `Note 1 Revenue | $ | 9,943` lost `9,943` with no enforceable finding.
Classify the identifier token itself, and keep enforcement for amounts elsewhere
in the row.

**Verified.** Reproduced: `9,943` was lost and reported only as a reference.

**Resolution.** Classification is now per token and never spreads across a row:
- Only the identifier at the start of a cell is a reference (the `1` in `Note 1`).
  Text after it keeps its own class.
- A cell that starts with `Date:`/`Dated:` or contains `/s/` is a reference cell.
- A date-shaped cell in a signature row is a reference. This rule was needed:
  without it, META 10-K signature dates in their own cell
  (`Date: | January 29, 2025 | /s/ …`) became enforced values.
- Exhibit-index units remain reference only. Detection now requires both an
  "Exhibit…" cell and a "Description" cell.

The case now reports `9943` missing as an enforced value.

### 2. [P1] Split accounting negatives become unchecked

**Finding.** The cell-boundary rule tokenized `(29` and `)` separately, and
neither yields a token, so deleting the whole amount produced no finding.
Reconstruct accounting signs across structural cells, and test deletion as well
as preservation.

**Verified.** Reproduced: preserved and deleted versions both gave no finding.

**Resolution.** Before tokenizing, adjacent non-empty cells in a row are merged in
two shapes:
- an opening amount (`(29`, `$ (29`, `(3.2`) followed by `)` or `)%`
- `(` or `$ (`, then a plain amount, then `)`

The merge applies to source cells and, after splitting on `|`, to output lines.
The preserved case gives no finding; the deleted case reports `-29` missing.

### 3. [P2] Row rearrangements still pass both checks

**Finding.** Check 2 skipped unmatched rows on the assumption that check 1 would
catch missing values. That fails when the values remain elsewhere in the table.
Swapped rows and values moved between rows produced no finding. Report such rows,
and distinguish them from legitimate header fusion.

**Verified.** Reproduced both cases with no finding.

**Resolution.** Check 2 now classifies each data row's outcome:
- **in order**, with the within-row order checked
- **rows out of order**, when a matching body line exists only before the pointer
- **values split across output rows**, when the body holds all the row's tokens
  but no single line does
- **skipped**, leaving the missing values to check 1

Header fusion is excluded in two ways: header lines (before the separator) are
never matched, and only *data rows* take part. A data row needs at least one
standalone amount cell that is not a bare year.

The data-row restriction proved necessary on real filings. Without it:
- 19 RCQ tables (272 rows) were falsely reported. A stacked META equity
  statement's first-section period row matched the second section's repeated
  header line.
- AAPL's undetected `Maturities | 2023 | 2022` header row was reported as split
  across rows.

With it, check 2 reports 0 findings on the fixtures and on the 20 RCQ filings. It
still catches reversed cells (50 of 57 AAPL units) and swapped rows (48 of 57).

### 4. [P2] The prototype changes the rendering mode being checked

**Finding.** The prototype enabled `capture_tables=True`. For the nested-table
example, normal Markdown conversion loses `12`, while capture mode keeps it
through fallback text. Test both modes, and obtain diagnostic metadata without
changing rendering.

**Verified.** Normal mode renders `| Outer Inner 77 B 88 | Inner |`, which loses
`12`. Capture mode renders fallback text that keeps it.

**Resolution.** The spec now requires the checks to evaluate the caller's own
rendering mode. Snapshot metadata comes from a read-only computation that never
registers unreliable tables in non-capture mode. A new acceptance criterion
requires non-capture rendering to be byte-identical with and without the checks.

The prototype renders in the requested mode and reads metadata from a separate
parse. The nested case now reports `12` missing in normal mode and nothing in
capture mode. The corpus figures are identical in both modes.

# Round 3 (revision 3)

### 1. [P1] A reference or footnote can still conceal a lost financial value

**Finding.** The value-first allocation let surviving numbers count for
financial values before references. Deleting the `9` from an Impairment row
while `Note 9` survived elsewhere reported only a missing reference, in both
rendering modes. A surviving `<sup>9</sup>` behaves the same way. Preserve
occurrence provenance where possible; otherwise classify the deficit as
potentially material instead of assuming the financial occurrence survived.

**Verified.** Reproduced both cases. Only a reference or marker loss was
reported.

**Resolution.** Matching now uses occurrence positions. Each source and output
number is tagged as one of:
- an identifier number (anywhere in a cell, identically on both sides)
- a number in a numeric cell (no letters)
- a number in a text cell
- a number in a header line (output)
- a number in text rendering (output)

Rules:
- A value may claim only compatible positions: never an identifier, and from a
  numeric cell never a text cell unless the unit is rendered as text.
- References and markers claim first.
- A value shortfall whose number was shared with a reference or marker in a
  compatible position is still reported, labelled `ambiguous`. That is the
  "potentially material" treatment: it is never assumed that the financial
  occurrence survived.

Both cases now report the amount `9` missing as an enforced value. The reverse
cases (identifier or marker lost, amount kept) report only the reference or
marker.

Two rules turned out to be load-bearing during the corpus run:
- **Identifier detection must be symmetric.** An output-only "anywhere" rule
  produced 28 false value losses in nvda-2002 exhibit footnotes.
- **A trailing `(n)` is split off as a marker only when a number remains.**
  Otherwise `$ (96)` lost its negative.

On the corpus, check 1 flags the same tables as revision 3, with 0 ambiguous
shortfalls.

### 2. [P2] The "bare year" filter excludes legitimate amounts

**Finding.** The data-row restriction treated unformatted numbers from 1900
through 2099 as years. Swapping `Revenue | 2000 | 1900` to `Revenue | 1900 | 2000`
produced no finding from either check. Apply year exclusion using header and
period context, not numeric shape.

**Verified.** Reproduced: no finding.

**Resolution.** A row is excluded from check 2 only when it is a *period row*,
decided by context:
- it is before the snapshot's header-row count, or
- every cell is period text or a bare year, with period text present or with
  only bare years.

`Revenue | 2000 | 1900` is a data row, and the swap is reported as values out of
order within the row. `| 2023 | 2022` and "Maturities (calendar year) | 2023 |
2022" stay period rows, so the false alarms that revision 3's filter prevented
stay prevented. Check 2 still reports 0 findings on the fixtures and the 20 RCQ
filings, and still detects all three mutations.

# Round 4 (revision 4)

### 1. A standalone marker cell still conceals a lost value

**Finding.** The matching rule stopped markers from claiming numeric-cell
output, but `<td><sup>9</sup></td>` renders as a numeric cell. Astra used this
source layout:

```html
<table>
<tr><th>Item</th><th>Amount</th></tr>
<tr><td>Impairment</td><td>9</td></tr>
<tr><td>Footnote</td><td><sup>9</sup></td></tr>
</table>
```

After the Impairment amount was deleted from the output, both modes reported
only a missing marker, with no value loss or ambiguity: the surviving footnote
still supplied the financial `9`. Even the unchanged output wrongly reported a
missing marker. Revision 4's test placed the marker inside a text label, so it
did not cover this case. Preserve standalone-marker provenance, or treat the
competing numeric occurrence as ambiguous. Test the preserved, amount-deleted
and marker-deleted variants in both modes.

**Verified.** Reproduced with the revision 4 prototype. All three variants, in
both modes, reported only a missing marker.

**Resolution.** Both remedies apply:
- **Standalone-marker provenance.** A marker that is its cell's only content is a
  *standalone marker* and may claim numeric cells.
- **Row provenance.** Each source row is paired with its own output line by row
  label (letters of the first cell, matched in order), and pass 1 matches only
  within that line. The footnote row's `9` and the Impairment row's `9` therefore
  cannot cover for each other.
- **Ambiguity fallback.** Occurrences whose row cannot be paired are matched
  table-wide in pass 2. Competition there between a value and a reference or
  marker labels the value shortfall `ambiguous`.

Results, the same in both modes:

| Variant | Result |
|---|---|
| Unchanged | no finding |
| Amount deleted | value `9` missing, enforced; not ambiguous, because row provenance decides |
| Footnote deleted | standalone marker reported only |
| Same layout without row labels, amount deleted | value `9` missing, labelled `ambiguous` |

On the corpus, revision 5 produces exactly the same findings as revision 4 for
every table of the 7 fixtures and 20 RCQ filings, so the pairing introduces no
false alarms.

# Round 5 (revision 5)

### 1. [P1] Row pairing collapses distinct labels

**Finding.** Row pairing stripped labels to letters only, so `Note 1` and
`Note 2` both became `note`. Astra reproduced it in both modes:

```html
<tr><td>Note 1</td><td>9</td></tr>
<tr><td>Note 2</td><td><sup>9</sup></td></tr>
```

Deleting the entire `Note 1` row made the checker pair its financial `9` with
the surviving footnote row, reporting only missing reference and marker tokens,
with no value loss or ambiguity. Repeated labels such as `Total` reproduce the
failure too. Smallest correction: preserve meaningful identifier digits, and
treat row pairing as proven only when the label match is unique on both sides.
Send duplicate or uncertain matches through the existing ambiguous fallback.

**Verified.** Reproduced both cases with the revision 5 prototype:
- Deleting `Note 1` reported only a reference and a marker.
- Deleting one of two `Total` rows reported only a marker.

**Resolution.** The smallest correction, as proposed:
- **Label keys keep identifier numbers.** `Note 1` becomes `note#1` and `Note 2`
  becomes `note#2`. Other digits are still dropped, so `Revenue (1)` matches
  `Revenue`.
- **Proven pairings only.** A pairing holds only when its key is unique among the
  unit's source rows and among its output body lines.
- **Fallback.** Duplicate keys, empty keys and unmatched rows go to the
  table-wide pass. There, a value shortfall that competed with a marker or
  reference is labelled `ambiguous`.

Results, the same in both modes:

| Variant | Result |
|---|---|
| `Note 1`/`Note 2`, unchanged | no finding |
| `Note 1` row deleted | value `9` missing, enforced; reference `1` reported |
| `Note 2` footnote row deleted | reference `2` and standalone marker reported only |
| Two `Total` rows, unchanged | no finding |
| First `Total` row deleted | value `9` missing, labelled `ambiguous` |

On the corpus, revision 6 produces exactly the same findings as revision 5, for
every table of the 27 documents, including check 2.

## Status

Revision 6 is ready for re-review. Its figures:
- Check 1 flags 9 fixture units and 105 RCQ units, with 0 ambiguous shortfalls.
- Check 2 has 0 findings on real data.
- All three mutations are detected.
- All 34 review cases behave as intended in both rendering modes.

No implementation plan exists yet. It should be written in `../plans/` once D1–D4
are decided.

# Round 6 (Phase A corpus record)

Date: 2026-10-04. Reviewer: Astra. Reviewed `main` at `8bf0c1e`, including
PR #4's merge `fb774fd`, the Phase A record, its classification and raw results,
the earlier reviews, the implementation plan, merged code and tests. This round
supersedes the historical Status paragraph immediately above.

**Ruling:** Phase A's report-only implementation, corpus-record and review
milestone is complete. This is not approval to enable Phase B enforcement, nor
agreement with the record's unqualified claim of zero implementation defects.
The findings and decisions below define the required follow-up. This review
changes no implementation, tests, spec or evidence files.

## Verification

- Recomputed the summary from `results.json`'s documents and groups. Every
  serialized summary field agrees. Expanded the classification's table ranges:
  all 775 newly flagged tables are covered exactly once, with no extra tables.
  The counts are 754 genuine-only, 20 false-positive-only and one mixed table;
  their 1,541 value tokens split into 1,519 genuine and 22 false positives.
- Re-ran `corpus_phase_a.py` on merged `main`, writing its output to scratch.
  The entire parsed JSON equals the recorded `results.json`, including all
  109 documents, findings, word losses, hashes and mode comparisons.
- Verified all 109 source hashes. All 18 EDGAR cached files also match the
  manifest's byte sizes and hashes; there are 18 distinct EDGAR accessions.
  The fixture manifest has five distinct accessions, and the two duplicated
  RCQ filings are excluded as recorded: 55 distinct filings in total.
- Re-ran `parity_impl.py`: **27 documents, zero finding mismatches and zero
  header-row mismatches**, covering both rendering modes.
- Re-inspected representative source DOM and rendered output for CAT 7/25/143,
  BABA 24/75, TSM 79/312/130, JPM 367, KO 50/59/110/112, NVO 34 and UNH 68.
  Also ran synthetic preservation/deletion, currency-column, header-swap,
  recall and checker-exception probes. The findings below distinguish these
  reproductions from counts inherited from the classification.
- **Full suite: 798 passed, 14 deselected, three existing XML-parsing warnings**
  in 149.49 seconds. Ran `python -m pytest -q -p no:cacheprovider --basetemp
  C:/Users/einstein/AppData/Local/Temp/sec2md-round6/pytest-unsandboxed-20261004`
  from the repository root with `PYTHONDONTWRITEBYTECODE=1`. The sandbox runs
  hit temporary-directory permission errors; the approved unsandboxed rerun
  with this fresh scratch directory passed. `python -m ruff check --no-cache
  src tests`: **passed**.
- Scratch evidence is outside the repository at
  `C:\Users\einstein\AppData\Local\Temp\sec2md-round6`. No installation,
  commit, push or write to `E:\RCQWealth` was performed.

| Recomputed measure | Offline | EDGAR | Total |
|---|---:|---:|---:|
| Documents | 91 | 18 | 109 |
| Tables checked | 2,131 | 2,489 | 4,620 |
| Check-1 value tables / tokens | 141 / 185 | 739 / 1,486 | 880 / 1,671 |
| Missing values: header / label / body | 102 / 38 / 45 | 159 / 824 / 503 | 261 / 862 / 548 |
| Reported reference / marker tokens | 41 / 0 | 60 / 14 | 101 / 14 |
| No-output tables / value tokens | 21 / 46 | 552 / 1,162 | 573 / 1,208 |
| Check-2 tables / rows | 0 / 0 | 11 / 37 | 11 / 37 |
| Documents with value failures | 32 | 12 | 44 |
| Ambiguous tokens / mode disagreements | 0 / 0 | 0 / 0 | 0 / 0 |
| Tables with word losses | 178 | 821 | 999 |
| Word-only tables / missing words | 54 / 178 | 158 / 842 | 212 / 1,020 |

## Findings

### 1. [P1] A surviving marker can conceal a deleted negative amount

**Verified.** In both rendering modes, use source rows
`Loss | (96)<sup>(1)</sup>` and `Other | (1)` under an Item/Amount header.
Keep the rendered `Loss | (96) (1)` but blank Other's amount. `check_tables()`
returns no missing value, only missing reported marker `-1`. The greedy
`_MARKER_SUFFIX` in `table_completeness.py` takes the initial short accounting
negative into its suffix match; `_output_cell_positions()` then leaves both
numbers in numeric positions. The marker supplies the deleted financial `-1`.
The corresponding `(196) (1)` case treats the marker separately.

**Required before Phase B.** Fix note (c), preserving the initial accounting
negative and separating subsequent markers irrespective of digit count. Pin
unchanged, amount-deleted and marker-deleted variants in both modes, including
duplicate/unpaired labels and split accounting cells. Do not weaken the
value-protection rule to describe the current behavior.

Note (b) also requires code correction: `cell_text()` turns
`<sup>1<span>0</span></sup>` into marker text `1 0`, not `10`. Concatenate inline
pieces within one marker, while retaining boundaries between distinct markers.
Invented marker digits must not consume a genuine amount's occurrence.

### 2. [P1] Source tokenization can leave financial quantities unchecked

**Verified.** JPM 367 contains 15 `Nbps` cells. Twelve yield no source token;
`1,097bps` yields `1` twice, and `2,717bps` yields `2`. These are missing or
fragmented source obligations, not just noisy findings. `RMB8,400` yields `400`.
Separately, `numbers("due 2029)")` returns no token at all. A quantity that never
enters the source multiset cannot be protected by check 1.

**Required before Phase B.** Implement the bounded inline letter/digit boundary
rule for F2/F8, preserving digit-to-digit joins such as `1,2<span>34</span>`.
Recognize unmatched closing prose punctuation without discarding the preceding
number or turning balanced accounting negatives positive. Require preservation
and deletion tests for full quantities, not merely disappearance of the old
false positives. Any shared-normalizer change needs numeric-trace and rendering
regressions because the euro change demonstrates its wider effects.

### 3. [P1] Passing strict and both checks does not establish header alignment

**Verified.** BABA 24 renders `2023 | 2024 | 2025` one column left of the
corresponding revenue amounts: 941,168 appears under 2025, while the FY2025 RMB
996,347 amount has a blank header. TSM 79 and 312 reproduce shifted headers.
The recorded count of 66 remains a rough heuristic count, not a verified count
of all affected tables.

A synthetic table with unchanged amounts `120 | 100` and swapped period headers
returns no findings in either mode. A second probe, with separate euro and
amount cells below spanning 2025/2024 headers, passes public strict conversion
and both checks while the period headings sit over the currency columns. It
also fuses the first data row into the header. All quantities remain traceable,
so restoring the old euro numeric-trace failure would not solve the defect.

**Required before Phase B.** Make BABA 24, TSM 79/312 and the separate-currency
layout regression cases in the prerequisite table-merge/header work. Assert
the amount's association with its period and currency, not just token presence
or successful strict conversion. Define the report-only alignment diagnostic
there using source-to-output column provenance, allowing legitimate span and
currency-column merges. Retain the public limitation until this is covered.
The strict currency test in `tests/test_quality.py` currently asserts only
that conversion does not raise; add output-content assertions, with alignment
assertions when the renderer fix lands.

### 4. [P1] Checker execution failure must not become a successful Phase B gate

**Verified.** Injecting an exception into `parser.check_tables` makes public
`convert_with_diagnostics(..., quality_policy="strict")` return nonempty output
with `warnings=()`, empty table findings, `tables_checked=0` and
`numeric_recall=None`. The exception is visible only in the ERROR log. XLSX
likewise consumes the absent report as empty completeness findings.

**Required.** Accept conversion-preserving isolation for Phase A, but document
it accurately now. Before enforcement, expose a structured distinction between
disabled checks, a completed check with zero eligible tables, and failed checks.
Phase B strict must reject an incomplete required check; warn may return output
with the failure recorded. Cover Markdown, pages and XLSX entry points, including
failure before any finding was collected. A successful zero-table result cannot
be inferred from an exception.

### 5. [P2] Prototype parity does not resolve the identifier contract violation

**Verified.** Source identifiers are split by `classify_cell()`, whereas output
header lines, exhibit-index cells and `output_line_numbers()` use whole-cell
tokenization. An unchanged `(See Exhibit 4.1)` exhibit-index cell is reported
missing. An unchanged header containing `Exhibit 10.11.2` produces a missing
value `2 [header]` and reference `10.11`. The regex recognizes only the first
two numeric components, leaving the last component enforceable.

**Required before Phase B.** Keep the spec's symmetric identifier rule and fix
the code, rather than exempting these output contexts in the wording. Recognize
complete multipart identifiers and apply the same extraction in all modes and
check-2 token streams; identifier occurrences must remain unavailable to values.
Protect genuine values elsewhere in the same cell/row and the earlier Note 1 /
Note 2 regressions. Punctuation repair alone does not fix multipart identifiers
or occurrence classification.

Correct the record's reasoning now: zero differences from v6 proves no observed
implementation drift from that prototype. It does not prove zero defects
against the written specification. F4's asymmetry and note (b)'s marker joining
are shared contract defects; F5 combines that asymmetry with incomplete
identifier syntax. The implementation followed the plan's prescribed triage,
but this review does not accept that triage as a correctness proof.

### 6. [P2] Check 2 reuses rows and mistakes a promoted data row for a loss

**Verified.** `row_structure()` searches inclusively from its last match.
Unchanged source/output rows `(1, 2)` then `(2, 1)` report row 2 out of order
because the previous line is reused. This is F6's mechanism in CAT 25 and
SPCX 41. CAT 143's exhibit 10.4 row is present as the Markdown header, which
check 2 excludes; its numbers on later lines then provoke the F7 split-row
finding. No real reordering was found among the classified 37 rows.

**Required for the Phase B diagnostic revision.** Prefer a proven row match or
a later unused output line. Do not fall back to reusing the old line merely
because its multiset fits; require provenance for a legitimate row merge. For
F7, recognize a source data row promoted into the rendered header and either
map it explicitly or report it as not evaluable by the body-order check. Do not
admit every header line into ordinary matching and resurrect the stacked-header
false alarms. Keep check 2 report-only. Carry original source-row indices in
messages, fixing note (d), instead of numbering only filtered data rows.

### 7. [P3] Documentation overstates logging and error propagation

**Verified.** `enforce_quality()` logs one WARNING and INFO detail only for
`table_completeness_failures`. A report containing only reference/marker and
check-2 findings emits no completeness log. The spec still promises
`warn`-level finding lines. `docs/usage/xlsx-export.md` says programming errors
propagate, although checker errors are swallowed. README's “Passing them” and
“They appear” obscure which checks or findings it means.

**Required.** Update the spec and usage wording to name check-1 value failures,
reported tokens and check-2 findings explicitly, and describe the Phase A
checker-error exception to propagation. Accept the one-summary-WARNING / detail-
INFO policy; if “each finding” remains the promised behavior, extend INFO logging
to reported tokens and structure findings in the Phase B update. The decision
here is to include those details at INFO, retaining a value-failure-only WARNING
summary. State the normalizer rendering/strict carve-out and the actual check-3
normalizer. Also reconcile the already-reviewed metadata optimization: normal
mode calls `header_row_count()`, not `snapshot_html_table()` for each table.

The plan still has Task 11 Step 7 unchecked at line 2743. This is stale
bookkeeping, not evidence that the corpus record is absent from `main`; reconcile
it in the documentation follow-up. No code rerun is needed just to tick it.

## Decisions

### 1. Page header and footer tables — choose (c)

Keep the units and ordinals, but classify tokens in the actual parser-discarded
page-furniture subtree as **report-only page furniture**. Record the parser's
discard decision using `_is_footer_element`; do not infer this class merely
from an empty output or broadly reclassify any similarly styled ancestor that
the parser did not discard. Other unexplained no-output tables remain value
failures. Preserve missing-token and no-output visibility, including the NVDA
effective/updated dates; report-only does not mean the discarded content is
unimportant. Keeping footer text remains separate parser work.

The current baseline is 573 tables / 1,208 value tokens. Moving precisely that
population to the new class leaves 307 check-1 value tables / 463 tokens before
any other definition or renderer fixes. Keep the original evidence immutable
and record the new counts in a subsequent run.

### 2. CAT 7 — choose (a)

The missing 2025 and 120 are genuine losses from the PART row's substantive
second cell. Keep the unit and finding; fix the PART branch to preserve that
content in the table-merge/header work. Do not exclude one-row PART tables.
Retain this exact known loss in the development expected-failure list until
fixed; such a test expectation does not automatically exempt it from strict.

### 3. BABA/TSM header shift — choose (a) plus (b)

Require the renderer regressions and a separately defined report-only
header-alignment diagnostic in the table-merge/header spec, including the euro
currency-column case in finding 3. Reject (c) as the entire response: a caveat
is necessary now but insufficient as the planned remedy. Numeric completeness
and correct period attribution remain separate claims. Do not turn the rough
66-table heuristic into an enforcement rule.

### 4. F1–F8 and the identifier wording

| Cause | Ruling |
|---|---|
| **F1, glued/raised markers** | Accept a DOM-boundary rule for letter/digit joins and **Raised digits (a)** for relative-positioned marker-like digit spans with a genuinely negative `top`. Keep ordinary relative positioning insufficient. Reject (c)'s claim that invented `20341` is a genuine lost amount; reject (b) as the permanent remedy. I extended the NVDA check to all 38 NVDA documents in this corpus: 126 fixture, 588 primary and 79 exhibit relative-positioned digit spans, **793 in total, none with negative `top`**. Pin the raised cases and no-top kerning controls, including loss of the real adjacent year/amount, before using the rule in enforcement. This is evidence for the narrow rule, not a license to classify arbitrary positioned numeric facts as markers. |
| **F2, glued currency code** | Accept separating letter/digit boundaries between inline elements, so the obligation is 8400, not 400. Apply compatible extraction to both sides. Preserve kerned digit joins and sign/decimal boundaries. |
| **F3, glued dash** | Choose **Glued dash (b)**: retain UNH 68's single `-10` as a documented known false positive. Reject (a), because a genuine minus sign may sit outside its XBRL element, and reject (c)'s semantic claim of a genuine loss here. Do not make DOM text-node boundaries decide sign. This does not authorize dropping all negative tokens or silently exempting this document from strict; absent a separately reviewed narrow exception, Phase B strict will reject this known case. |
| **F4, identifier punctuation/asymmetry** | Fix code to honor symmetric identifier extraction in every output context and check-2 line. Also repair unmatched closing prose punctuation for non-identifiers, preserving accounting negatives. Changing only the spec to excuse asymmetry is rejected. |
| **F5, multipart identifiers** | Accept extending identifier syntax to complete dotted identifiers, with identical token identity on both sides. Keep the entire identifier report-only; no suffix component becomes a financial value. Include adjacent genuine amounts in deletion tests. |
| **F6, inclusive pointer** | Accept searching strictly after the previous match first, strengthened by the row-consumption/provenance requirements in finding 6. Keep the row/column-swap mutation tests. |
| **F7, first data row in header** | Preserve source data-row identity when it is promoted into the output header; otherwise mark that comparison unevaluable. Do not report the row as split simply because only later body lines were searched. Keep ordinary period/header rows excluded. |
| **F8, glued unit suffix** | Accept the same inline-boundary correction as F2, including the full 1097 and 2717 values and the twelve currently unchecked cells. A narrow supported-unit tokenizer can supplement it, but a generic “digits inside any word” rule is not approved. A suffix-only fix is insufficient for F1/F2. |

All **11 check-2 tables / 37 rows** remain accepted as false positives in this
baseline. All 21 F1–F8 tables, including mixed BABA 75, must be represented in
regression evidence. BABA 75's genuine missing caption token 31 must survive
the false-positive fixes. The 61 falsely reported references need correction
too; their report-only class does not justify asymmetric extraction.

### 5. D3 — no enforced word check

Accept the measured **12/30 = 40% noise** and a Phase B report-only word
diagnostic as a candidate to evaluate. The recorded 30 table IDs exactly match
`word_only_tables[3::7]`. The 25–58% Wilson range is a descriptive approximation
for this systematic, issuer-clustered sample, not a guarantee for other filings.

Approve the two filters with boundaries: join proven fragments of the same
source word and tokenize Unicode letters; do not globally remove whitespace
or join arbitrary adjacent words. Ignore a header only when its **entire source
column span** has no nonempty body content. Numeric zero and X marks count as
content; spanning titles and nonempty “Filed Herewith” columns must survive.
Re-measure after the filters and page-furniture/renderer changes on this corpus,
including preserved and deleted header controls and newly sampled residual
findings. The target is **below 10% noise**. The projected elimination of 11–12
noise cases is not measured acceptance evidence. Reaching the target would
permit adoption as a report-only diagnostic, not automatic word enforcement.

### 6. Implementation notes (a)–(g) and changes beyond the plan

| Note | Decision and timing |
|---|---|
| **(a) Euro/pound normalizer** | Accept both user-approved side effects: split-negative rendering and strict numeric-trace changes, including the rare stricter layouts. Amend Purpose and “no new strict failures” wording **now** to make the narrow exception explicit. The checks-on/off rendering criterion stays unchanged. Strengthen the strict test's content assertions and fix header alignment in the prerequisite parser work; do not revert currency support to hide the gap. |
| **(b) Split marker nodes** | **Code fix before Phase B**, as in finding 1. Keep the spec's inline-concatenation rule; do not redefine a marker 10 as markers 1 and 0. |
| **(c) Marker after short negative** | **Code fix before enforcement**, with deletion tests proving that the surviving marker cannot satisfy the missing amount. No wording relaxation. |
| **(d) Check-2 row numbers** | **Code fix in Phase B**: retain actual one-based source-row indices within the table unit, including skipped/header rows in the numbering. Keep “source row” as the documented meaning. |
| **(e) Quadratic search** | **Code optimization in Phase B**, preserving multiplicities and genuine ordering detection while implementing the approved F6/F7 changes. Precompute line counters/indexes and verify a large lossy-table case plus corpus parity under the revised definitions. The recorded 2,000-row/8-second measurement was not independently retimed here. Ordinary corpus timings do not rule out quadratic behavior. |
| **(f) Recall/list markers** | **Code follow-up in Phase B**; keep recall diagnostic-only. Reproduced lossless `2. Summary of 100 and 200 and 300` returning 0.75. Distinguish real source numbering from generated Markdown list syntax; do not simply count every list bullet as a source number. Document the present limitation now. |
| **(g) Check-3 normalizer** | **Spec wording now**: name `quality._normalized_numbers()` over the existing visible-source/visible-Markdown text. Reusing runtime code is accepted; importing a helper from `tests/` is unnecessary. This does not excuse note (f)'s extraction mismatch. |

The **18-issuer replacement is accepted**, including the three 20-Fs and the
2026 SPCX 10-Q. It broadens useful format coverage and still satisfies the
50-filing criterion. Reading EDGAR's older-filings pages is consistent with the
approved fetch scope. I verified the cache/manifest, not a fresh SEC download.

The **logging levels are accepted**, with the precise scope correction and INFO
follow-up in finding 7. **Checker-error isolation is accepted for Phase A only**
under finding 4's visibility and future strict requirements. The **header-shift
caveat is accepted and must remain**; clarify README's antecedents. Amend the
XLSX propagation claim to distinguish checker errors from other programming and
filesystem errors. These are required follow-ups, not edits made by this review.

### 7. Overhead — confirm the user's decision

Accept **up to +25% in total for Phase A**, with the **10% target from Phase B**.
The spec's Where it runs, acceptance criterion and Evidence > Overhead agree
with that decision. PR #4 records baseline 4.487 s and candidate 5.408 s,
approximately **+20.5%**, using unchanged pre-feature `main` in separate Python
processes. EX-99.2's individual +25.6% does not violate the total-only Phase A
criterion. This confirms the recorded measurement and its arithmetic; I did
not rerun a performance benchmark alongside the review jobs. The +16.4% EDGAR
checks-off comparison remains indicative, not the acceptance baseline.

Phase B must use an identified unchanged pre-feature baseline again, not measure
only its increment over already-slower Phase A. Include any adopted new
diagnostics in the total cost and record per-fixture figures and the aggregate.
Correct the timing helper's stale docstring when it is next updated.

### 8. D1 — check 2 stays report-only

Confirmed. **All 37 real-corpus row findings are false positives**; passing the
synthetic mutation tests alone does not justify enforcement. Correct the known
causes and re-measure, but any future decision to enforce check 2 requires a
separate review of demonstrated real-data accuracy. Check 3 and D3 remain
diagnostic-only. Phase B's intended enforcement is check-1 value loss, including
ambiguous shortfalls, subject to the approved page-furniture class.

### 9. Phase A complete; Phase B remains gated

**Yes: this Round 6 completes the required review of the Phase A corpus record.**
The raw evidence is reproducible and satisfies the filing-count and D3
measurement requirements. Accept the report-only release with the known limits
recorded here. Do not describe this as a clean correctness review or as approval
to switch strict enforcement on.

Before enabling Phase B enforcement:

1. Reconcile the spec/record and public documentation with these decisions,
   including the narrower prototype-parity claim, currency exception, logging,
   execution-failure semantics and actual metadata/recall implementation.
2. Land the prerequisite table-merge/header fixes and regressions, including
   CAT 7, BABA/TSM, separate currency columns and genuine word/header losses.
   Define the report-only alignment diagnostic in that work.
3. Fix the marker and source-token blind spots and symmetric identifiers;
   implement page furniture as an explicit reported class. Keep genuine numeric
   losses and ambiguous shortfalls enforced regardless of digit count. Retain
   UNH 68 only as the explicitly accepted known false positive described above.
4. Make failed required checks visible and fatal to Phase B strict; revise
   check-2 matching/numbering without enabling its enforcement. Address the
   search-cost and recall follow-ups, and re-measure any proposed D3 diagnostic.
5. Re-run the full suite, both rendering modes and this corpus under the revised
   definitions. Classify changed/new findings, retain deletion mutations, update
   expected failures only with explanations, and meet the Phase B 10% overhead
   target. Land the specified minor RCQ version bump and CHANGELOG entry when
   enabling check-1 enforcement.

The present expected-failure list is a development baseline, not a blanket
runtime exemption. It must be empty or limited to explicitly reviewed residuals
at the enforcement decision. No additional implementation or commit is
authorized or performed by this read-only review.
