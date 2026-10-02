# Review: sec2md Table Completeness Check Design

- **Spec:** `../specs/2026-10-02-sec2md-table-completeness-check-design.md`
- **Reviewer:** Astra
- **Round 1:** reviewed revision 1 (merged in pull request #3); resolved in revision 2
- **Round 2:** reviewed revision 2; resolved in revision 3
- **Round 3:** reviewed revision 3; resolved in revision 4
- **Round 4:** reviewed revision 4; resolved in revision 5
- **Round 5:** reviewed revision 5; resolved in revision 6 (2026-10-02)

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
