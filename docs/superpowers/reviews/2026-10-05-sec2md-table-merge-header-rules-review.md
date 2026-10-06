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

# Round 2 (revision 2)

- **Spec reviewed:** revision 2 from the working tree, dated 2026-10-05.
- **Reviewer:** Astra.
- **Checkout:** `main` at `c674828`.
- **Verdict:** **revise before writing the implementation plan.** R9 and the
  membership-based routing resolve two major Round 1 findings at design level.
  R6a still permits an extra body number to escape strict tracing, and the
  row-role and alignment contracts have reproducible counterexamples. These
  decisions should not be left for an implementer to resolve implicitly.

## Verification and Round 1 disposition

I read the working-tree revision, its review-history mapping, the dated
correction at the end of the evidence report and the complete Round 1 record.
I rechecked the relevant renderer, quality, element-building and completeness
code. `git diff c674828 -- src tests` is empty. After the interrupted turns,
I confirmed that the spec and evidence report had the same file hashes as
during the probes and that no Round 2 section had yet been appended.

The probes below used the existing code plus small process-local evaluations
of the proposed rules. They are design counterexamples, not claims that
revision 2 has been implemented. The unchanged 109-document replay was not
rerun in this round; Round 1 records its successful execution. No full suite
or performance benchmark was run, no packages were installed, and no spec,
source or test file was edited.

| Round 1 finding | Round 2 disposition |
|---|---|
| **1. Repeated headers and strict tracing** | **Partially resolved.** Selecting the allowance from the actual element-content render, including the anchor-stripped render, is correct. An unrestricted token counter does not preserve body occurrence checking; see finding 1 below. |
| **2. XLSX helper coupling** | **Resolved at design level.** Default `LEGACY`, explicit Markdown `EXTENDED`, unchanged XLSX callers and corpus-wide prepared-table equality address the verified call graph. The evidence correction is accurate. |
| **3. Header/body classification** | **Partially resolved.** R0 fixes CRM 26 in the cleaned grid, rebuilds split negatives before classification, uses link labels and freezes roles. T8 introduces a known data-to-header regression, and the checker does not specify the same coordinate cleanup; see findings 2–3. |
| **4. Structural header routing and provenance** | **Resolved at design level.** Owning members retain header identity, removed markers contribute only body text, and independent header ownership vetoes removal. The mixed-direction example now assigns `2024` through the surviving right-hand amount column, never through the closing marker's leftward action. |
| **5. Conflicting header matching** | **Partially resolved.** Exact components and sibling rejection catch the four named mutations. Literal delimiters and identical text at different hierarchy levels are not handled correctly; see finding 4. |
| **6. Output positions and numeric vocabulary** | **Resolved in the stated parser/token contract**, subject to the source-coordinate issue in finding 3. Blank cells, escaped pipes, links, numeric-core coordinates, leading-dot tokens and nil-value skips are now explicit. Verify these independently of renderer decisions. |
| **7. Acceptance and coverage** | **Partially resolved.** Baseline identity, completion evidence, assignment/header audits, reviewed residuals, F7 reconciliation, strict/XLSX controls and the timing contract are substantial improvements. Aggregate coverage still permits a changed population to pass; see finding 5. |

“Resolved at design level” requires implementation and the specified evidence
before release; it does not mean those checks have already passed.

## Findings

### 1. [P1] R6a's aggregate credit can hide an extra body amount

**Verified.** R6 skips adjacent equal header texts. R6a nevertheless adds a
credit for each extra output occurrence of a repeated source header, while
strict's available pool still includes other source header occurrences whose
text was skipped. The combination creates unused credit that body text can
consume.

The minimal source has these header rows and one body row:

```text
Metric  | 2025 spanning both value columns
blank   | 2025       | Budget
Revenue | 100        | 200
```

R6 writes the top source cell in both output columns and skips the equal
lower `2025`, producing:

```text
| Metric | 2025 | 2025 — Budget |
| --- | --- | --- |
| Revenue | 100 | 200 |
```

Strict's source pool contains two `2025` occurrences. R6a records one extra
copy for the top spanning cell. I evaluated the proposed count arithmetic
using the actual `_normalized_numbers` function. If the output body is
mutated to `Revenue | 100 2025 | 200`, the uncredited trace reports one extra
`2025`, but the R6a-credited trace reports nothing: three output occurrences
are covered by two source occurrences plus one credit. The allowance still
correctly describes the two written copies of the top header; this example
does not depend on stale metadata or a fabricated allowance.

**Required change.** Attribute credits to actual repeated header occurrences
and account for the original source occurrences they use. Do not expose the
credit as general availability for the element's body or surrounding prose.
One acceptable design is to validate source-backed header emissions
separately, consume their source occurrence budget, and apply the existing
occurrence-sensitive trace to the remaining output and source pools. The
precise representation can be chosen in the revision, but the above body
mutation must fail.

Retain the correct rule that the anchor-stripped re-render supplies the
element allowance. Bind its provenance back to the original table node;
discard allowances from renders that did not supply element content. Test
this counterexample with and without links, in both capture modes, as well
as a table grouped with nearby prose. A per-table counter summed into an
element-wide pool is not, by itself, header-occurrence attribution.

### 2. [P2] T8 promotes ordinary integer exhibit entries into the header

**Verified.** The decimal-only label rule fixes CRM's `4`, but cannot distinguish
that caption number from an integer exhibit entry. Applying the exact R0
conditions to:

```text
Exhibit Number | Description
1              | Agreement
3.1            | Articles
```

gives roles `header, header, body`. R6 consequently emits
`Exhibit Number — 1 | Description — Agreement` as the header and removes the
first exhibit from the body. I reproduced those roles and assembled texts
with a small literal evaluation of the specified rule. Changing the third
row to another integer selects the no-data fallback and keeps row 1 in the
body, so an unrelated later decimal changes the treatment of an earlier
entry.

This risk is disclosed under T8, but measuring it later is not a decision
that authorizes the regression. Text retention and numeric completeness
cannot establish correct row roles here; the entry's words and number still
exist in the wrong place.

**Required change.** Reject the decimal-only rule as the complete label-column
decision. Add a bounded contextual rule for an established identifier column
or another explicit way to distinguish a caption number from an exhibit
entry. Preserve CRM 26's caption and year rows while keeping both integer and
decimal exhibit entries in the body. Pin the three-row example, the all-integer
variant, and a caption-number control with independent expected roles. If a
specific unresolved shape must remain a limitation, name and review that
residual rather than granting a blanket exception for integer entries.

### 3. [P2] The checker applies R0 to a different column-zero convention

**Verified.** The renderer's “source grid” is explicitly after `_clean_grid`,
which drops wholly empty columns and renumbers the survivors. R0's label
exception uses column 0. The alignment source-side steps instead specify
snapshot placement followed directly by R0. The snapshot placement used by
`header_row_count` retains wholly empty columns; it does not perform the
renderer cleanup.

I constructed a CRM-shaped table with an empty leading cell in every row:

```text
blank | 4       | Fiscal Year Ended January 31, spanning two columns
blank | blank   | 2025 | 2024
blank | Revenue | 100  | 200
```

Using the existing grid builder and `_clean_grid`, then evaluating R0 on
each representation, the raw grid gives `body, body, body`: `4` is outside
column 0. The cleaned grid gives `header, header, body`: `4` is the label.
Thus the renderer can produce correct headers while the checker skips the
table as `no_header`. Merely sharing the predicate does not make the input
coordinate conventions identical.

**Required change.** Specify equivalent visible empty-row/column treatment
before checker classification, or define the logical label column without
depending on physical column 0. Keep an explicit map to original source
coordinates for span coverage and value identities. Implement that source
analysis independently of renderer merge decisions. Pin leading spacers,
blank rows, span-covered slots and linked labels so classification and header
coverage agree without losing provenance. The independent checker need not
reuse the renderer's cleanup implementation, but its semantics must be stated.

### 4. [P2] Whole-component matching rejects valid literal and hierarchical headers

**Verified.** Two valid cases fail the new matching contract:

1. A single source header `Income — net` is rendered unchanged by R6. Step 10
   splits it into components `Income` and `net`; step 11 requires the entire
   source text `Income — net` to equal one component. It therefore reports a
   mismatch on faithful output. The header-retention audit has the same
   problem. I evaluated this exact split/equality operation.
2. Suppose one source header row has sibling spans `2025` and `2024`, and a
   lower row under the `2025` group legitimately labels a comparison column
   `2024`. That column's expected path is `2025 — 2024`. Both expected
   components are present, yet step 11 rejects `2024` because it also names
   the top row's conflicting sibling. I evaluated the presence and conflict
   predicates; both return true. The flat text search cannot tell which
   source level justified the second component.

The first case needs no ambiguous source layout. The second demonstrates
that the promise that parent and child components coexist is not enforced
by the conflict rule. These problems do not invalidate exact matching or
sibling rejection; they require an unambiguous composition contract.

**Required change.** Define how literal source delimiters remain distinguishable
from renderer-added separators, or match whole source labels as ordered
segments against independently derived source paths. Associate sibling
conflicts with a candidate source level/path rather than rejecting a string
that has a legitimate expected use at another level. When text admits several
assignments, use an explicit ambiguity skip; do not guess a conflict or call
it aligned. Keep the four Round 1 mutations as failing controls, and add
faithful literal-delimiter and repeated-label parent/child controls. Apply
the same component semantics to the independent header-retention audit.

### 5. [P2] Aggregate coverage can conceal replacement of the evaluated population

**Verified.** Acceptance compares total `values_evaluated` and requires
explanations for lost values only when that total falls. A baseline can
evaluate values A and B, while a candidate skips A and newly evaluates C:
both totals are two. Per-reason skip totals can also stay equal if a different
value ceases to be skipped. The proposed counts therefore do not establish
that every formerly evaluated value remains evaluated. The assignment audit
covers the selected 6,616 merges, not the entire alignment population.

T9 also leaves the counting units and boundaries unspecified: `no_header`
skips a table, `unpaired` skips a row, and `missing_in_output` skips a value.
The rule does not say what `tables_eligible`/`tables_evaluated` mean, whether
skip reasons are mutually exclusive, or how to count a unit with no Markdown
separator. Implementations could emit the same field shape with different
denominators.

**Required change.** Keep the compact runtime field, but require the acceptance
artifact to compare stable per-value identities, such as document, unit,
source row and numeric-core coordinate. Compare the evaluated sets and report
every lost identity even when total coverage grows. A skip reason explains
why a comparison was lost; it does not by itself approve that loss. Require
individual review and retained rendering/Phase B consequences for regressions.

Define a stable counter schema: units for every skip key, eligibility and
evaluation boundaries, deterministic keys/order, reason precedence, and
reconciliation identities such as
`values_evaluated = values_aligned + values_misaligned`. Include the no-output
or no-separator path explicitly. It is acceptable for `()` to mean “no
completed diagnostic” in this report-only phase; it must never be interpreted
as a successful zero. The separate Phase B requirement to distinguish
disabled and failed required checks remains in force.

## Accepted design changes and implementation constraints

**R9:** accept the policy boundary and identical-XLSX acceptance. All transitive
helpers, including final validation and joining, must propagate the policy;
`LEGACY` must work on the bare `object.__new__(TableParser)` used by XLSX,
without depending on new Markdown instance state. The singleton, currency,
decimal and sentinel controls plus corpus prepared-table comparisons are the
right evidence. This does not authorize changing XLSX behavior to make its
results resemble the new Markdown output.

**Membership:** accept the owning/marker distinction for the mixed-direction
case. Keep the independent-header veto and revalidate complete numeric tokens
after any actions are vetoed. R6's claim of at most one header cell per row
should be an internal invariant with a regression test. Its fallback of
joining conflicting texts must not be considered successful acceptance merely
because a report-only checker might notice it; that checker can skip values.

**R0 and numeric parsing:** accept freezing roles before merging and classifying
visible link labels. The specified split-negative reconstruction resolves
Round 1's complete-number/fragment ambiguity, provided the local decimal and
currency vocabulary applies consistently to both fragment recognition and
final validation. CRM 26 is fixed under the stated cleaned-grid convention;
findings 2–3 identify what still needs revision.

**Acceptance:** retain the strict, XLSX, original-content pin-removal,
word-header, known-shift and class-8 audits. The F7 wording is now reconciled.
The fixed normal-mode benchmark with checks on and at least five separate
process runs is a sufficiently explicit contract for T7. Section and chunking
integration tests now cover the relevant changes; no additional section-regex
or chunker behavior change is justified by this review.

## Decisions

| Decision | Round 2 ruling |
|---|---|
| **T1. Repeated spanning headers** | **Keep the approved layout choice; revise R6a.** Finding 1 blocks approval of the proposed strict-credit mechanism. Preserve header-specific attribution and the anchor-stripped render association. |
| **T2. Data-cell/row-role test** | **Partially accepted.** Freezing roles, split reconstruction and link-label classification are sound. Resolve findings 2–3 before treating the rule as complete. |
| **T3. No data row** | **Accepted unchanged.** Row 0 alone is the fallback; it must not conceal the integer-entry inconsistency in finding 2. |
| **T4. Headerless tables** | **Accepted unchanged.** Empty headers preserve first-row body identity; retain F7 and chunk-continuation tests. |
| **T5. Alignment check** | **Revise matching and population accounting.** The named Round 1 mutations are addressed, but findings 3–5 remain. Skipping values below repeated headers is an acceptable explicit limitation, with those skips counted. |
| **T6. Currency markers** | **Accepted with R9.** Keep whole-cell matching, local complete-token validation, unknown-code controls and unchanged XLSX behavior. |
| **T7. Overhead** | **Accepted.** The new measurement contract is adequate; performance has not yet been demonstrated. |
| **T8. Decimal-only label rule** | **Not accepted as the complete rule.** Preserve integer exhibit rows using bounded context while retaining CRM 26's caption handling. A future corpus measurement does not authorize the known regression. |
| **T9. Coverage field shape** | **Accept the tuple-of-pairs representation, conditional on a defined schema.** No new dataclass is required. Runtime aggregate counts must be supplemented by the per-value acceptance comparison in finding 5. Empty coverage is not a completed zero-result run. |

**Plan verdict:** do not write the implementation plan against revision 2 as
currently specified. Revise R6a, the label/coordinate rules, header-component
matching and coverage accounting first, then review those bounded changes.
R9, membership routing and the accepted integration/benchmark requirements
need not be reopened. Phase B enforcement remains separately gated by the
completeness review's outstanding prerequisites.

Only this review record was changed by the Round 2 review. The existing spec
and evidence-report edits were preserved, and the review is left uncommitted.

# Round 3 (revision 3)

- **Spec reviewed:** revision 3 from the working tree, dated 2026-10-05.
- **Reviewer:** Astra.
- **Checkout:** `main` at `c674828`.
- **Verdict:** **not ready for an implementation plan as written.** Four of
  the five Round 2 findings are resolved at design level. Two bounded defects
  remain in the revised label-occurrence matcher: it disagrees with R6's
  duplicate suppression, and a compound label elsewhere in the table can
  conceal the correct column's parent/child labels. Correct those rules before
  planning implementation. No further architecture change is requested.

## Verification and Round 2 disposition

I read revision 3 from disk, including its Round 2 history, R6a, identifier and
visible-content definitions, matching rules, coverage schema, tests and
acceptance criteria. I compared them with the Round 2 findings and rechecked
the existing strict tokenizer and source-trace behavior. Source and tests
remain unchanged relative to `c674828`.

I ran process-local evaluations of the specified accounting and matching
rules, using the existing `_normalized_numbers` for the numeric trace probe.
These are design-rule probes, not tests of an implemented revision 3. No
source or test file was written, no packages were installed, and no corpus
replay, full suite or benchmark was rerun. Their implementation acceptance
requirements remain in force.

| Round 2 finding | Round 3 disposition |
|---|---|
| **1. Aggregate strict credit hides a body amount** | **Resolved at design level.** Removing `header_source` from the body/prose pool closes the counterexample. The normal body gives no excess; `Revenue | 100 2025 | 200` gives body excess `2025: 1`. The header passes its separate capacity check in both cases. Binding the record from the actual element-content render to the original table node addresses the anchor-stripped path. |
| **2. Integer exhibit entries become headers** | **Resolved for the named cases.** The identifier rule gives `header, body, body` for both `1 / 3.1` and `1 / 2`, while the CRM caption control remains `header, header, body`. The replacement is a documented heuristic; its caption-plus-numbered-label limitation remains subject to individual corpus review, not a blanket exemption. |
| **3. Different column-zero conventions** | **Resolved at design level.** Origin-text semantics, the logical leftmost label column, ignored empty rows/columns and retained original checker coordinates provide the missing common contract. The checker still derives it independently of renderer merges. |
| **4. Literal and hierarchical header matching** | **Partially resolved.** Whole-label boundaries address a standalone literal delimiter, and `need(s)` prevents a legitimate child label from automatically becoming a sibling conflict. Findings 1–2 below expose interactions the new tests must cover. |
| **5. Coverage hides replacement of evaluated values** | **Resolved at design level.** Stable per-value identities and evaluated-set differences catch losses despite growing totals. The fixed units, precedence, complete key set and reconciliation identities define the runtime schema. Every loss requires review; a skip reason alone does not approve it. |

## Findings

### 1. [P2] The matcher requires duplicate labels that R6 deliberately suppresses

**Verified.** R6 still skips a header text equal to the preceding one.
Matching step 12 defines `need(x)` as the number of entries in the original
source path, without applying that suppression. A faithfully rendered column
therefore fails the checker when an adjacent repeated label is required at
one of its levels.

Use the same header shape already present in the R6a regression:

```text
Metric  | 2025 spanning both value columns
blank   | 2025       | Budget
Revenue | 100        | 200
```

For `100`, the source path is `[2025, 2025]`. The lower `2025` is
discriminating because its sibling is `Budget`. R6 correctly writes just
`2025` in that column. The literal matching calculation gives:

```text
need(2025)  = 2
found(2025) = 1
aligned    = false
```

I reproduced that calculation. The strict-accounting control can now pass,
yet the alignment control reports an error on the same correct output.
Repeating the header text to satisfy the checker would violate R6.

**Required change.** Define expected emitted occurrences independently from
the raw path entries. Account explicitly for R6's adjacent-equal suppression
while retaining which source levels/cells a surviving occurrence satisfies.
Use that representation consistently for requirements and sibling-conflict
accounting. Do not simply reduce every label to a set: non-adjacent repeated
labels may require multiple occurrences. Preserve source-cell identity for
rowspan cases as well.

Add passing alignment controls for this exact R6a source and an adjacent
duplicate header, plus a control that still requires both occurrences in a
non-adjacent path such as `A — B — A`. The independent header-retention audit
must permit the documented suppression without accepting unrelated losses.

### 2. [P2] A longer label in another column overrides a valid parent/child path

**Verified.** Step 11 builds one inventory from all header-zone cells and takes
the longest matching label first, never overlapping. Consider this source
header hierarchy over three value columns:

```text
Metric  | Income spanning two columns | Other
blank   | net       | gross           | Income — net
Revenue | 100       | 200             | 300
```

R6 faithfully renders the header above `100` as `Income — net`. Its source
path is `[Income, net]`; both labels are discriminating. However, the table's
inventory also contains the single literal label `Income — net`, from the
third value column. Longest-first selection takes that unrelated label and
excludes both legitimate path occurrences.

I evaluated the specified boundary and non-overlap rules. The selected
occurrence is `(0, 12, 'Income — net')`; `found(Income)` and `found(net)` are
both zero, so the correct output is reported as misaligned. Under a sum of
matched-label lengths, the long label covers 12 characters while the two
short labels total 9; the equal-total-length ambiguity clause does not rescue
the case. If “explain the same text” instead includes separator characters,
that interpretation needs to be explicit and cannot follow an irreversible
longest-first choice.

**Required change.** Resolve label segmentation against independently derived
source paths before discarding competing occurrences. A longer label from
another column must not automatically displace the expected parent and child.
Define ambiguity by materially different viable label/path assignments, not
only equal sums of label lengths. Accept the faithful expected path when it
is distinguishable; otherwise record `value_ambiguous_header` rather than a
false misalignment. Keep the required sibling-contamination mutations failing
when their source paths are unambiguous.

Test all three columns of the example together, a standalone literal label,
and the existing merged-sibling and swapped-value mutations. Apply the same
semantics to the header-retention audit. A test with `Income — net` in an
otherwise unrelated one-level table does not exercise this collision.

## Accepted boundaries and plan requirements

**R6a:** accept separate header and body/prose accounting. The implementation
plan must preserve the exact table-to-output association when locating header
lines, consume each located occurrence once, and define failure behavior for
a missing or ambiguous association. Do not use an unrestricted text
replacement that could remove an identical body/prose line. Header-source
subtraction must use the same token accounting as the mapped source pool.
These are implementation requirements for the accepted attribution boundary,
not a request to return to aggregate credits. Keep the with-links,
without-links, both-mode and grouped-prose tests.

**R0/T8:** accept the revised identifier heuristic for planning once the
matching findings are corrected. It resolves the concrete exhibit regression
and preserves the single caption-number control. The named limitation is a
case to identify, pin and review in the corpus; it does not prove general
semantic identification of exhibit columns. Retain independent expected-role
fixtures and the no-new-loss acceptance requirements.

**R9 and membership:** remain accepted. The added revalidation-after-veto and
R6 invariant tests are appropriate. An incompatible-header fallback is not
an acceptable successful outcome merely because the checker is report-only.
XLSX equality remains a required acceptance result, not an assumption.

**Coverage/T9:** accept the tuple schema and per-value artifact. The table,
row and value denominators and their skip precedence are now explicit. A
completed run has all keys, and `()` cannot satisfy a completed-run gate.
Preserve the original placed-grid coordinates in identities across both
baseline and candidate evaluations. Phase B still requires its separate
distinction between disabled and failed required checks.

## Decisions

| Decision | Round 3 ruling |
|---|---|
| **Round 2 finding 1 / T1** | **Resolved at design level.** Keep repeated spanning headers and the new separate header accounting. The named extra-body-year mutation now fails. |
| **Round 2 findings 2–3 / T2 and T8** | **Resolved for planning**, with the stated heuristic limitation individually audited. Preserve identifier, caption, split-negative, link and coordinate-equivalence controls. |
| **Round 2 finding 4 / T5** | **Still open.** Correct duplicate-occurrence accounting and table-wide label collisions as specified in findings 1–2 above. |
| **Round 2 finding 5 / T9** | **Resolved at design level.** Accept the fixed schema and per-value evaluated-set comparison. |
| **T3, T4, T6 and T7** | **Remain accepted.** No change to fallback/headerless layout, the currency boundary or the benchmark contract is requested. |
| **Implementation plan** | **Not yet against revision 3 as written.** Incorporate the two bounded matching corrections first. R6a, R0, R9, membership, integration tests and the benchmark contract need not be redesigned. |

This verdict concerns readiness to plan the renderer work. It does not approve
implementation, release or Phase B enforcement. Only this requested review
append was written; the spec, evidence correction, code and tests were
preserved, and the review remains uncommitted.

# Round 4 (revision 4)

- **Spec reviewed:** revision 4 from the working tree, dated 2026-10-05.
- **Reviewer:** Astra.
- **Checkout:** `main` at `c674828`.
- **Verdict:** **an implementation plan may now be written.** Both Round 3
  matcher findings are resolved at design level. The two notes below belong
  in that plan; they do not require another design-review round before planning.
  This approves planning, not implementation acceptance or Phase B enforcement.

## Verification and Round 3 disposition

I read the revised emitted-path definition, matching steps 10–15, R6a,
header-retention audit and regression controls, and compared them with the
Round 3 record. The checkout remains at the requested baseline and
`git diff c674828 -- src tests` is empty.

I ran a small, process-local evaluation of the revision 4 matching contract.
It deduplicates source identities, collapses adjacent equal labels, takes the
exact-path shortcut, and otherwise evaluates the segmentations of the small
test headers. All **14 assertions passed**:

| Control | Verified verdict |
|---|---|
| Adjacent duplicate `2025`, including the R6a header shape | Aligned |
| One source cell repeated through a rowspan | Aligned |
| Complete `A — B — A` | Aligned |
| `A — B — A` with the final `A` missing | Misaligned |
| Each of the three `Income` / `net` / `gross` / `Other` / literal `Income — net` columns | Aligned, three assertions |
| Standalone literal `Income — net` | Aligned |
| Legitimate child `2024` under parent `2025` | Aligned |
| Combined `2025 — 2024` over either period's amounts | Misaligned, two assertions |
| Swapped period header | Misaligned |
| `Unadjusted` substituted for `Adjusted` | Misaligned |
| A non-exact header whose segmentations disagree | `value_ambiguous_header` |

These verify the stated rules on the review cases; they are not tests of a
production implementation, which does not yet exist. No full suite, corpus
replay or performance benchmark was rerun. No packages were installed and
no source, test, spec or evidence file was changed.

| Round 3 finding | Disposition |
|---|---|
| **1. Matcher demands duplicates suppressed by R6** | **Resolved.** Requirements and conflicts use the emitted path. Collapsed entries retain their represented source cells/levels, while non-adjacent repeats retain their multiplicity. The faithful adjacent case passes and the missing non-adjacent occurrence fails. |
| **2. Another column's longer label overrides the correct path** | **Resolved.** Exact rendering of the value's independently derived emitted path takes precedence over other inventory labels. All three columns in the collision example pass together. Non-exact cases retain explicit ambiguity handling rather than a table-wide greedy choice. |

## Findings to carry into the implementation plan

### 1. [P2] Do not implement the segmentation contract as unbounded exhaustive enumeration

**Verified.** Revision 4 states that headers have few separators, then defines
`2^k` segmentations. There is no corresponding input bound. A header with 32
separators has **4,294,967,296** segmentations. This is a count of the search
space, not a measured runtime; I did not attempt to enumerate it. The exact
path shortcut avoids this work for faithful output, but baseline output and
regression cases also need to be checked and can take the non-exact path.

**Required plan treatment.** Treat “every segmentation” as a semantic
quantifier, not a requirement to materialize all partitions. Specify an
evaluation strategy with pruning, reuse of repeated subproblems and early
termination once both consistent and inconsistent interpretations have been
established. Include a stress case with many separators and a non-exact header,
including an all-inconsistent case that cannot use the mixed-verdict shortcut.
Document the work bound. If a bound prevents a completed verdict, expose an
incomplete check through the existing failure/coverage contract; never turn
budget exhaustion into aligned or a successful zero-findings result.

This is an implementation-algorithm requirement under the accepted matching
semantics. The seven-fixture timing gate remains necessary, but does not by
itself establish bounded behavior for long headers.

### 2. [P3] R6a's fallback restores the old trace; it does not guarantee a strict error

**Verified.** The exact segment association, first-line check and once-only
consumption address the Round 3 attribution requirements. However, the claim
that falling back makes “any repeated header number” fail is too broad.

In the accepted source with a spanning `2025` above a lower `2025` and
`Budget`, the source contains two `2025` tokens and the faithful output also
contains two. I evaluated the ordinary trace counts with the existing
`_normalized_numbers`; the excess is empty. If association fails and R6a is
disabled, ordinary tracing therefore need not raise, even though a spanning
header was repeated.

**Required plan treatment.** Describe the fallback precisely as **granting no
header exemption and retaining the existing trace behavior**. For a rejected
record, leave both its output header and its source tokens in the ordinary
pools: do not perform `header_source` subtraction for a table whose header
was not successfully accounted for. Test missing and ambiguous association
with both a genuine ordinary-trace excess and the no-excess example above.
Record association failures in verification so they cannot be presented as
successful header accounting. An unconditional strict error for association
failure would be a different policy, not a consequence of the specified
fallback.

Also carry the final source-pool tokenization wording through implementation:
`header_source` must represent the same source occurrences being subtracted;
do not mix the earlier visible-text description with a different source-pool
tokenizer. No change to the accepted separate header/body accounting is
requested.

## Decisions

| Decision | Round 4 ruling |
|---|---|
| **Round 3 finding 1** | **Resolved at design level.** Accept emitted-path identity handling, adjacent suppression and retained non-adjacent multiplicity. |
| **Round 3 finding 2 / T5** | **Resolved at design level.** Accept exact-path precedence and the stated conservative segmentation verdicts. Carry the bounded-evaluation requirement into the plan. |
| **R6a / T1** | **Accepted for planning.** Preserve exact table-segment attribution, once-only consumption and separate pools. Apply the fallback clarification above. |
| **R0 / T2 and T8** | **Remain accepted**, with independently pinned row roles and individual review of the identifier heuristic's documented limitation. |
| **R9 and membership routing** | **Remain accepted.** Keep the XLSX policy boundary, source ownership, post-veto validation and invariant tests. |
| **Coverage / T9** | **Remains accepted.** Preserve the fixed schema, completion distinction and stable per-value baseline/candidate comparison. |
| **T3, T4, T6 and T7** | **Remain accepted.** No change to fallback/headerless rendering, currency scope or the benchmark contract is requested. |
| **Implementation plan** | **Approved to be written now.** Include the two findings above as explicit implementation and verification requirements. No further design revision is required before starting the plan. |

The plan must retain the full acceptance work: original-content pin checks,
strict behavior in both modes, identical XLSX prepared tables, assignment and
header-retention audits, all 109 corpus documents, stable alignment coverage,
mutation controls, section/chunk integration and the timing gate. Those are
future acceptance results, not outcomes established by this design review.

Phase B enforcement remains separately gated by the completeness review's
outstanding prerequisites. Only this requested review append was written;
the review remains uncommitted, with no commit or push performed.
