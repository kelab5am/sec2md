# Review: sec2md Table Merge and Header Rules Design

- **Spec:** `../specs/2026-10-05-sec2md-table-merge-header-rules-design.md`
- **Reviewer:** Astra
- **Round:** 1, revision 1, 2026-10-05
- **Checkout:** `C:\Users\einstein\kelab5am\sec2md`, `main` at `3498ff3`

# Round 1 (revision 1)

**Decision: revise before implementation approval.** The evidence supports repairing
the existing renderer, and R1, R7 and R8 address verified losses. The proposed
header-zone rule, structural-header handling and compatibility boundaries need
correction. The alignment diagnostic is a useful independent approach, but its
current matching contract and zero-findings acceptance gate are insufficient.
This review does not approve Phase B enforcement.

## Verification

I read the spec, evidence report and its measurement/replay scripts, the two
renderer paths, the completeness implementation and Round 6 rulings. I also
followed the relevant calls through quality diagnostics, XLSX preparation,
section extraction and chunking.

The actual checkout is later than the requested baseline: `3498ff3` commits the
spec and evidence scripts; `git diff 2f039c4 HEAD -- src` is empty. At review
start, only the existing evidence `events.json` was untracked.

From the repository root, with `PYTHONIOENCODING=utf-8`, I reran:

```powershell
python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/measure.py --edgar-cache outputs/table-completeness-corpus --out "$env:TEMP/sec2md-merge-review-r1-events.json"
python docs/superpowers/audits/2026-10-04-table-merge-header-evidence/summarize.py --events "$env:TEMP/sec2md-merge-review-r1-events.json"
```

Results: **3,707 exact Markdown replays**, **109/109 documents with matching
check-1 findings**, 1,042 one-row units and 583 no-output units. The merge
buckets reproduce **5,929 + 687 = 6,616** same-header value merges. The class-1
intersection with check-1 failures is **294 tables**. These validate the
baseline measurements, not the proposed rules.

I inspected CRM 26 and MSFT 43 with `inspect_table.py` and ran small in-memory
probes of the existing helper calls and the specified output. Probe overrides
were process-local; no source, test or spec files were changed. The full test
suite and performance benchmark were not run: this is a design review, not
verification of an implemented renderer. No packages were installed and
`E:\RCQWealth` was only read.

## Findings

### 1. [P1] Repeated numeric headers make existing strict conversion fail

**Verified.** R6/T1 intentionally repeats a spanning year in multiple output
headers. `quality.trace_numeric_failures()` counts output numeric occurrences
against source occurrences, so one source `2025` cannot justify two rendered
copies. `_hard_failure_messages()` turns that extra occurrence into a strict
failure. This is independent of the proposed alignment field's report-only
status.

I used a source table with `2025` spanning `Actual` and `Budget`, followed by
`Revenue | 100 | 200`. Current rendering passes strict. Substituting only the
R6-required Markdown through a process-local `TableParser.to_markdown` override:

```text
| Metric | 2025 — Actual | 2025 — Budget |
| --- | --- | --- |
| Revenue | 100 | 200 |
```

causes `enforce_quality(parser.diagnostics, 'strict')` to raise
`untraceable normalized number: <element-id>:2025`. I reproduced this with
`capture_tables=False` and `True`.

**Required change.** Include a narrowly defined compatibility change for
source-backed header repetition. Preserve occurrence-sensitive checking of
body numbers and reject invented header numbers; do not turn numeric tracing
into set membership or exempt all headers. Specify how repeated header
occurrences remain attributable to the original source span, including the
anchor-stripped citation rendering in `_element_segment_content`. Add strict
parser tests in both modes for legitimate repetition, an invented year and an
extra body amount. T1 is acceptable only with this compatibility work.

### 2. [P1] The proposed helper changes also change XLSX output

**Verified.** The Markdown-only boundary is not enforced by the current call
graph. Contrary to the evidence report's final statement that XLSX uses only
`_join_structural_text`, `xlsx_tables.prepare_table()` creates a `TableParser`
without initialization and calls `_safe_structural_actions()` and
`_validated_structural_actions()`. These transitively use `_body_start`,
`_classify_structural_column`, `_is_numeric_fragment` and the joining logic
that R3/R4 change. The XLSX sentinel header is also designed around today's
body-start behavior.

For a source with headers `Metric | 2025 | blank` and rows
`A | (29 | )`, `B | 40 | blank`, `prepare_table()` currently returns three
columns. A process-local change permitting one nonempty structural marker,
exactly the R3 threshold change, makes it return two columns and `(29)` in
the first value column. No XLSX code was changed in that probe.

**Required change.** Specify an explicit boundary that preserves XLSX's current
structural rules while enabling the new Markdown rules. A separate policy or
isolated helper path is sufficient; unchanged public signatures alone are
not. Add XLSX prepared-grid regression controls for singleton markers,
currency codes, leading-dot decimals and the sentinel/header-start case.
Compare values, column groups, source coordinates and issues, not merely
workbook file bytes. Correct the evidence report's call-graph claim.

### 3. [P1] T2 misclassifies a named real header and has no complete rule for split amounts

**Verified.** CRM 26's first cleaned row is a standalone `4` in its first
cell beside `Fiscal Year Ended January 31,`; the next row carries
`2025 | 2024 | 2023`, followed by the cash-flow values. I reproduced this
with the inspection script. Under the proposed definition, that `4` makes
row 0 a data row and the entire header zone empty. R5 consequently emits
an empty header and retains the caption and year rows as body. The alignment
check skips the table. This contradicts the named CRM regression's purpose;
it is not only the hypothetical `(1)` risk listed under T2.

The evidence's body test excludes one-digit integers; T2 includes them. Its
header-key measurement also selects the lowest header-like cell, whereas R2
checks every header row. The 6,616 count therefore does not establish that
the proposed combination preserves all those alignments.

There is a second boundary ambiguity: a first body row consisting of
`Loss | (29 | ) | (40 | )` contains no complete standalone number under
the stated definition. If a later row contains `50` and `60`, R5 promotes
the loss row into the header. If no later complete number exists, the
no-data fallback happens to avoid that promotion. R3's fragment recognition
does not fix a header zone already computed before structural merging.
The distinction between complete numbers and fragments must be explicit.

**Required change.** Revise T2 into a contextual header/body decision that
handles CRM 26 while retaining genuine single-digit first data rows. Define
split-negative recognition before header classification, the treatment of
year-shaped amounts, and whether linked numbers are classified from visible
labels rather than serialized `[label](destination)` text. Compute and retain
the source header boundary before destructive merges; do not let it change
when column text is concatenated. Pin these cases with expected source row
roles and expected output headers independently of the shared helper. Sharing
the predicate is reasonable, but cannot be the only correctness oracle.

### 4. [P1] Structural merging can move a header across periods before R2 runs

**Verified.** `_merge_structural_columns()` precedes the legacy pass. Its
`_header_merge_target()` chooses the first surviving body target when a
marker column has targets on both sides. Numeric validation verifies the
body tokens, not that choice of header.

A minimal source has headers `Metric`, `2025` spanning columns 1–2 and
`2024` spanning columns 3–4. Its body is:

```text
A | 100 | blank | $ | 200
B | 110 | blank | $ | 210
C | (30 | blank | ) | 400
D | (40 | blank | ) | 500
```

After empty-column cleanup, the mixed marker column has valid actions to
the right for `$` and left for `)`. With the correct one-row header boundary,
the existing structural pass produces header texts
`Metric | 2025 2024 | blank` and valid body tokens. I reproduced the actions
and result directly. The new R3 changes do not revise this routing; R6
explicitly permits joining two headers combined by the careful pass.
That permission preserves the wrong period attribution.

The current structural and legacy mergers also allocate new `Cell` objects
for joined text. A merged cell's single identity no longer records the set
of original cells needed by R1/R2/R6. Original `GridCell.cell` identity is
useful at input, but does not by itself survive the pipeline.

**Required change.** Define source-column membership and header provenance
through cleanup and both merge passes. Route body markers separately from
header ownership: the example's `2024` must remain over its original amounts,
without contaminating `2025`. Do not move headers merely in the direction of
a closing marker or concatenate incompatible sibling headers. Specify the
case where a marker column must remain because it owns independent header
content. Apply R2 against original header identities, including after a
structural merge, and deduplicate by original source identity.

Add positive tests for offset values under the same span (AAPL 15 and the
other measured legitimate shapes), negative tests for sibling spans, this
mixed-direction case, and the marker exception on both sides of a period
boundary. The exception must require actual marker evidence and retain the
body-validity condition; an empty group must not qualify vacuously.

### 5. [P2] Substring inclusion accepts conflicting sibling headers as aligned

**Verified.** The proposed check only requires expected header strings to be
present. With source sibling headers `2025` and `2024`, an output column
headed `2025 — 2024` containing both unique amounts satisfies every expected
substring. The values are attributed to incompatible periods, but the check
reports nothing. Giving both output columns that combined header also passes,
including after a value swap. This directly overlaps the structural-header
failure above.

Substring matching additionally treats expected `Adjusted` as present in
`Unadjusted`, even when those are distinct source sibling labels. Whitespace
collapse and case folding do not resolve either problem.

**Required change.** Keep normalization, but define matching of complete
header components and rejection of conflicting discriminating sibling
contexts where the source makes that distinction unambiguous. Respect
legitimate parent/child header composition. If an assignment is genuinely
ambiguous, record it as unevaluated rather than aligned. Add mutations for
merged sibling headers, both columns carrying all period labels, a value
swap under those labels, and overlapping label strings. A test for one
simple shifted header is insufficient for T5.

### 6. [P2] Alignment needs a position-preserving output parser and an explicit token boundary

**Verified.** `merge_split_negatives()` returns a compacted list: it removes
empty cells and combines multiple source cells without retaining indices.
For example:

```text
['Revenue', '', '(29', ')', '', '40']
    -> ['Revenue', '(29)', '40']
```

Those new list positions are not Markdown column numbers. Check 1 can use
that list because it counts tokens within rows; the alignment check needs
the original value column to select a header. Reusing the transformation
without a coordinate contract can check the wrong header. A plain
`line.split('|')`, as used in check 1, also splits escaped visible pipes
and cannot reliably retain output cell positions.

I also verified that `numbers('.75')`, `numbers('(.62)')` and `numbers('—')`
all return `()`, and that `merge_split_negatives(['Revenue', '(.62', ')',
'40'])` leaves the decimal negative split. These are inside the renderer's
new data-cell vocabulary. The current skip list does not explain this token
coverage gap. An empty token tuple cannot identify a value column.

**Required change.** Define independent Markdown cell parsing that preserves
blank columns, escaped pipes and links. Reconstruct split numeric tokens
with original column indices, assigning an accounting token to its numeric
core rather than the marker cell. State how source split amounts retain
their span coordinates too. Either support leading-dot decimals locally
in this diagnostic or explicitly report them as unsupported coverage; do
not silently count them as checked. Nil dashes need a stated unevaluated
rule if the numeric diagnostic cannot identify them. None of this requires
changing the global strict numeric normalizer. Add aligned and shifted
controls with blanks, split negatives, leading-dot decimals and linked or
pipe-containing labels.

### 7. [P2] Acceptance can reach zero by losing coverage and does not yet prove the prerequisite

**Verified.** An empty header zone skips a table; a lost value, duplicated
value or unpaired label skips an individual comparison. Thus CRM 26's T2
failure can reduce alignment findings without improving alignment. A failure
inside the enclosing `check_tables()` call can currently also leave no
table report. The proposed diagnostic exposes findings only, so an empty
tuple does not establish that the baseline population was evaluated.

The existing three Phase A mutations test other completeness properties.
Neither they nor unchanged aggregate words/numbers/financial-row scores
prove preservation of the 6,616 correct realignments, word-only header
ownership, or the new diagnostic's coverage. The acceptance wording also
says F1–F8 are unaffected while the interaction section intentionally fixes
F7; those requirements need reconciliation.

**Required change.** Make acceptance a comparison of a fixed, identified
population, with at least these additions:

- Pin the baseline commit and corpus identities. Record alignment-eligible,
  paired, evaluated and skipped counts with reasons, plus successful check
  completion. Reuse the same independent diagnostic on baseline and candidate
  output. A checker exception or reduced coverage is not a zero-finding pass.
- Audit before/after source-to-output assignments for the measured correct
  merges. Require preservation of values and header attribution, not the
  exact old number of merges. Independently assert word-only header retention
  and the known shifted-table cases, including ones the checker cannot pair.
- Keep genuine losses as failures. Replace “classified residuals” with
  individually documented, reviewed residuals and their Phase B consequences;
  classification alone is not approval to pass. Record intentional F7 changes
  and any other interactions with the unchanged completeness definitions.
- Add the strict and XLSX controls above, diagnostic mutations from findings
  5–6, and focused integration cases for PART content/section boundaries and
  chunked tables with fused headers and empty header cells.
- Define the +10% measurement as candidate total divided by unchanged-main
  total for the same seven fixtures, settings and modes, with checks enabled
  on both sides. Record repeated-run timing and per-fixture outliers. This is
  separate from the completeness spec's Phase B budget and baseline.

## Other rules and integrations

**R1 and R7:** accept the preservation intent. Combining row 0 closes the
measured loss mechanism; considering header content during cleanup prevents
the later header-only deletion. These guarantees still depend on the
provenance and header-boundary changes above. Removing a pin must demonstrate
that its original content survives, not merely that a checker stopped
matching its row.

**R3/R4:** accept zero-width normalization, local leading-dot support, singleton
negative markers and the closed currency vocabulary, subject to findings 2–4.
Specify complete-token validation as well as fragment recognition: accepting
`.75` as a fragment is insufficient if the final validator still rejects it.
The evidence includes `)` columns also containing nil dashes; retaining
whole-column validation can leave residual splits. Record which class-8
cases are actually fixed and explicitly review any remaining mixed-column
cases rather than assuming all 80 disappear.

**R8:** accept preserving all trailing PART cells. I checked `PART_PATTERN`;
`PART III` followed by whitespace and the retained sentence remains a match.
There is no demonstrated need to change the section regex. Require a parser
and section-extraction regression for CAT 7, including the retained `2025`
and `120`, to verify content and boundaries through the full path. The
unchanged ITEM branch still intentionally keeps only the first later
nonempty cell; do not claim universal one-row preservation beyond this scope.

**Chunking:** `_split_table_element()` repeats the prefix before the separator
and gets width from that separator. Both fused and empty headers fit this
mechanism. Repeated long titles can increase chunk sizes: the existing
splitter deliberately accepts a single row even when prefix plus row exceeds
the token budget. Test content preservation, full header repetition,
column count and citation offsets on split output; retain that documented
oversize behavior rather than claiming a new hard token cap.

**Checker independence:** building the source grid separately and reading the
actual Markdown is the right boundary. Reusing check 1's unique-label pairing
is acceptable as a deliberately limited matching rule. Sharing a small
data-cell predicate is acceptable only with independent expected-role
fixtures and measured coverage. Do not share the renderer's merge decisions
or output-column mapping as the alignment oracle. Check 1's
`header_row_count` can remain distinct, with explicit tests for resulting
role differences. The previous Round 6 prerequisites, including failed-check
visibility and the source-token/marker fixes, remain outstanding for Phase B.

## Decisions

| Decision | Ruling |
|---|---|
| **T1. Repeating spanning headers** | **Accept the user's layout choice, conditional on finding 1.** Preserve full per-column context and repair strict trace attribution for legitimate repeated source headers. Do not silently exempt other numeric duplication. |
| **T2. Data-cell test** | **Revise.** The unconditional any-column single-number rule fails CRM 26 now, and the pre-merge split-negative boundary is incomplete. Retain genuine single-digit values; resolve context and pin independent row-role expectations as in finding 3. |
| **T3. No data row** | **Accept row 0 alone as the fallback header.** Do not fuse row 1 merely for sparsity. Test signatures and all-text tables, and ensure misclassified numeric fragments do not accidentally select this fallback. |
| **T4. Headerless tables** | **Accept empty header cells.** Keep all source data rows in the body. Verify check-2/F7 behavior and continuation chunks; headerless output must not become a way to pass alignment acceptance by skipping it. |
| **T5. Alignment scope** | **Accept report-only, discriminating-header scope and conservative pairing; revise matching and coverage.** Findings 5–7 are required. Resolve the contradictory stacked-table limit: explicitly state which repeated headers/rows are skipped and whether later blocks are evaluated against the top context or marked unsupported. Zero findings is not proof of alignment for skipped values. |
| **T6. Currency markers** | **Accept the closed list.** Require whole-cell matching, a validated amount on the attachment side, preservation of header-row currency labels and the XLSX boundary. Parameterize synthetic coverage across symbols, prefixed dollars and ISO codes, including unknown-code controls and all supported negative/decimal forms. |
| **T7. Overhead** | **Accept +10% relative to unchanged main for this work.** Pin the measurement contract in finding 7 and retain the separate Phase B target. No new benchmark was run in this review. |

The requested review file is the only repository artifact written by this
review. It is left uncommitted; no implementation, commit or push is authorized
or performed here.
