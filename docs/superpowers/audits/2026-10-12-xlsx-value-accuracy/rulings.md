# XLSX value accuracy: rulings and user decisions

These are the `Ruling` and `User decision` lines of the implementation ledger for the
XLSX value accuracy work, copied verbatim and in ledger order. The ledger itself
(`.superpowers/sdd/2026-10-12-sec2md-xlsx-value-accuracy/progress.md`) is not committed.

- The spec's "Revision 3: amendments during implementation"
  ([`../../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md`](../../specs/2026-10-12-sec2md-xlsx-value-accuracy-design.md))
  restates each ruling that shapes the export in one sentence, Rulings 22 to 33, the Ruling 34 user decision and Rulings 35 and 36 included, and
  marks Rulings 5, 14 and 17 as superseded.
- Code comments and tests cite these rulings by number.
- Below are 40 ledger lines, one paragraph each: 36 `Ruling` lines (Rulings 1 to 36 and 18a,
  except 34) and four `User decision` lines, the fourth of which is Ruling 34. The file itself has
  more lines, counting this header and the blank lines between paragraphs.
- Ruling 32 replaces the currency keep-value exception of Rulings 29–31. The Ruling 31 line
  below names the scale words thousand(s), million(s), billion(s), bn, m and mm; the code it
  produced (39a71d2) also accepted trillion(s) and k. That code was removed under Ruling 32.
- Rulings 1, 2, 6, 19 and 20 govern the audit harness, commits, test counts and
  records rather than the export.
- "Spec" below means revision 2 of that spec; "T1"-"T7" and "Fix A" are tasks and
  fix rounds of the plan ([`../../plans/2026-10-12-sec2md-xlsx-value-accuracy.md`](../../plans/2026-10-12-sec2md-xlsx-value-accuracy.md)).

Ruling 1: FactAttributes.unit_measures uses the same representation as the harness — sorted numerator measures, then '/' and sorted denominator measures only for a divide unit — so pure = ('xbrli:pure',) — the plan names one example and the spec says "resolved measures as a tuple of strings" — cost if wrong: a repr change inside tests/one helper.

Ruling 2: Review fix-round commits are new commits (no history rewrite); T7's "five commits" check is read as five task commits plus any listed fix commits — the plan did not anticipate fix rounds — cost if wrong: user squashes on merge.

Ruling 3: A nested ix:nonFraction inside another counts as a second fact, so the cell is not percent-fact proof — spec says "the only fact on the cell's value origin"; conservative (stays flagged text / other proofs) — cost if wrong: some percent-fact cells stay flagged text (coverage only, never a wrong number).

Ruling 4: Under an identifier header, a `pts` cell keeps `Percentage points; verify the unit.` rather than the I2 reason — the pts reason is the cell's own, more specific evidence and the cell is text either way — cost if wrong: reason string differs on a few NVDA Year-over-Year cells. (Carry to Task 5.)

Ruling 5: Split-% attachment refuses when the marker's leaf header is non-empty and differs from the value's leaf header — the spec's principle (convert only on proof; wrong number blocks merge) governs over P4's literal "only empty origins may lie between" — cost if wrong: some split-% cells stay unattached (old behaviour), caught by T6 dispositions of the 123 manifest split cells.

Ruling 6: Fix rounds may add regression tests for review findings; downstream expected test counts (T3 14/2120, T4 60/2166, T5 71/2177, T7 2177) shift by exactly the number of such tests, tracked here — adding tests strengthens, does not weaken; the plan did not anticipate fix rounds — cost if wrong: user wanted exact plan counts; trivially visible in ledger/final report.

Ruling 7: Header percent proof (P1.3) does not apply when the declaring leaf heads two or more kept copy columns that hold values in the same row (NFLX `$ | 1,323,096 | 7 | %` under `% Change` would give 13230.96); +1 regression test — a wrong number blocks the merge; the header cannot prove which of two values it describes — cost if wrong: such cells fall back to own proof/P4 flag (coverage only). Sent back to implementer before review.

Ruling 8: `_VALUE` headers keep outranking the table-wide percent flag, as today, rather than a literal P3 reading that would divide `Amount`/`Total` columns by 100 under a table-wide declaration — never introduces a new scale change; spec requires NVDA's 495 values unchanged — cost if wrong: a true percent column headed by an amount word under a table-wide declaration keeps displayed numbers (as today).

Ruling 9: A `$` in a header/row label beside a percent proof stays conflict text (today's rule kept alongside P3); unproven cells the converter rejects keep the converter's reason, not the P4 reason — both conservative, cell is text either way — cost if wrong: reason strings differ.

Ruling 10 (amends 7): A copy column whose header proof is withheld by the shared-leaf guard and whose header labels include a percent declaration is a percent column: digit cells without own cell/row-level proof become P4-reason text — Ruling 7 removed proof without saying what replaces it; text is the only no-guess outcome — cost if wrong: coverage (two-value % columns become flagged text), measured in T6. Ruling 7 test expectation for 1,323,096 changes (my own ruling's test, not a plan result). +1 regression test → 65 / 2171.

Ruling 11 (amends 7, 10): in shared-leaf columns withholding removes proof, never conflict — a withheld % declaration still feeds the P3 conflict test; P1.5 table-wide proof is also withheld there and such columns become Ruling-10 percent columns (P4 text) — these are wrong/unflagged numbers inside this task's own code, so they enter the loop as round 2 rather than deferred minors — cost if wrong: more flagged text in shared-leaf columns (coverage), measured in T6. +4 tests → 69 / 2175.

User decision (2026-10-13): Exempt footnote marks — a whole-cell footnote mark ((1), (12), (a), via _FOOTNOTE_MARK) is not accounting parentheses for I2's amount-format test; existing test passes unchanged; T6 dispositions verify no misread flag lost. Expected T5 counts unchanged: 80 / 130 / 1F 2186P.

Ruling 12: Under an identifier heading, a conflicting-units reason (like the points reason, Ruling 4) takes precedence over the I2 reason — keeps HEAD's behaviour; cell is text either way — cost if wrong: reason string differs.

User decision (2026-10-13): fix TSM split-% gate failure with BOTH (1) attach when the marker's leaf heading also spans the value's column (amends Ruling 5) and (2) safety net — a marker refused only by the leaf rule turns the value into P4 text. Ruling 5's own regression test expectation (1,000 kept) changes to P4 text under the safety net.

Ruling 13: The safety net applies literally (user's words), including a refused value with its own `$` or under a percent heading — text is never a wrong number — cost if wrong: coverage on `$`-amounts beside refused markers, visible in T6 changes.

Ruling 14 (narrows user's Fix A attach rule to its intent): attaching through an ancestor heading is refused when any column between value and marker has a leaf other than the value's or the marker's; refusal goes to the safety net — the user's goal was TSM conversion with no wrong numbers; TSM unaffected — cost if wrong: some non-adjacent ancestor-heading markers flag instead of convert.

Ruling 15: a refused zero stays 0 via spec P4's zero exception (not flagged) — zero is right at any scale — cost if wrong: an unflagged 0 beside a stray %.

Ruling 16 (narrows P4 "only empty origins or $/( between" and Rulings 5/14): split-% markers attach only when directly adjacent to the value (no origin between), plus the leaf rules; anything the old search reached but now refused goes to the safety net (P4 text) — every gap-crossing variant found so far is a wrong number; all 63 TSM widened attachments are adjacent — cost if wrong: manifest split cells with spacer columns between value and % become P4 text (coverage), measured by the T6 rerun; primary-statement fact counts gate any statement impact.

Ruling 17: in the ancestor-heading case only, refuse attachment (→ P4 text) when any column the marker occupies holds a digit value origin in another body row — such a marker is that column's sign, not the value's; TSM unaffected — cost if wrong: coverage in odd layouts. Entered as fix round 3 (wrong numbers in this fix's own code), with stale-comment and test-exactness minors.

Ruling 18 (generalizes 17): a split % attaches only from a marker-only position — in every other body row incl. period rows, the marker's columns hold only empty or %/)% origins — in every case (same leaf, ancestor, no heading); refusals → safety net — each per-shape patch kept leaving a sibling shape; this closes the whole class — cost if wrong: 2 TSM #9 split cells become P4 text instead of conflict text; any layout with stray content in a % column flags its neighbours.

Ruling 18a (amends 18): in the marker-only check, `)` / `%)` closing fragments and a body row whose only content is a non-digit spanning caption (unit caption) do not count as content — neither is a value of the marker column, so they cannot make the marker belong elsewhere — cost if wrong: a marker column whose only other content is such a fragment/caption could still attach; TSM returns to 63 kept / 0 refused, the 8 new wrong-number tests still pass.

Ruling 19: the column-grouping category stands (pre-existing `_column_groups` same-leaf join the spec keeps; 144 independently verified) but is tightened to its exact conditions and disclosed in the README — it fixed the checker's model of a legitimate mechanism, not an expectation — cost if wrong: a grouping-joined value outside those conditions would fail the gate (safe).

Ruling 20: the `except` claim stays in the CHANGELOG (the plan's Step 1 requires it), supported by the fact pack in the same audit directory, code and tests, and reworded to the latent singular `except … percentage data` case — the README covers the corpus, where the case does not occur — cost if wrong: a CHANGELOG claim backed by tests rather than the corpus record.

Ruling 21: a percent proof never overrides contrary evidence in the same column, row or cell (other-unit row label, `$`/amount fact in the column, pure fact scale≠-2) — those cells become flagged text; also amends Ruling 8 (under a table-wide declaration a _VALUE-headed column's unproven cells become P4 text) and flags digit cells under non-declaration % headings — the user's principle is no unflagged scale change on contested evidence; constructed paths only — cost if wrong: coverage, verified by an acceptance rerun (NVDA unchanged is a stop gate).

Ruling 22: A2 stays per copy column (a `$` cell withholds table-wide proof only for its own column), so `(in percentages)` with `Revenue | $ 1,000 | 100` in distinct leaves still gives 100 → 1.00 — spec P1.5 makes the declaration proof where no local proof exists, and a `$` is local to its column; recorded as a known gap — cost if wrong: one constructed shape (0 in corpus) converts on the table's own declaration.

User decision (2026-10-13): do one more fix round for the residuals (Codex C1-C4 confirmed, _OTHER_UNIT misfires, Ruling 22 in record, B1 nits), then acceptance rerun on the final commit.

Ruling 23: apply R1 (the A6 test is this wave's own; the cell stays text, reason becomes the more accurate P4) — closes an unflagged 0.04; REJECT the `(x)` part of R5: `(x)` stays a unit (times) — dropping it would let `Net leverage ratio (x) | 2.4` under a percent claim become 0.024; a footnote `(x)` beside a `%` only loses coverage (conflict text) — accuracy over coverage — cost if wrong: `Net interest margin (x)`-style footnotes give conflict text.

Ruling 24 (amends R5): restore e02bb44's broad unit matching, ignoring only bps after a signed number and a leading years/months/days before a digit range or `of`; extend the vocabulary to the never-recognised unit labels in row labels and headings; must-keep list for maturity buckets/period headings/NVDA verified by tests — accuracy over coverage (as Ruling 23) — cost if wrong: more conflict text on unit-ish labels.

Ruling 25 (amends 24): drop the `of` exemption entirely (Days/Months/Years of … name a measure; e02bb44 was right); keep only a leading digit-range exemption; fix _SIGNED_POINTS boundary/order; add hyphenated and ppt/yrs/mos spellings; record the closed-vocabulary limit as a known gap — accuracy over coverage — cost if wrong: conflict text on `Months of supply`-style labels beside percent claims.

Ruling 26 (amends 24/25): remove the signed-points exemption entirely — any bps/basis/percentage point(s) in a label is contrary evidence; each refinement reopened a wrong number; rate-shock scenario labels lose coverage (conflict text), recorded as a known gap — cost if wrong: coverage on rate-sensitivity tables.

Ruling 27 (completes 26's "any spelling"): a points word glued to a digit counts (`_OTHER_UNIT` leading boundary becomes a no-letter lookbehind), with tests for `+50bps Years`, `+100bps`, `Change 25bp`, `Change 2024-25bps` → conflict text — one-line, closes the regression and the glued-spelling gap — cost if wrong: coverage only.

Ruling 28: display/fact sign disagreement is not flagged — the value comes from the displayed token (spec P1.2), the export shows what the filing displays — recorded as a known gap — cost if wrong: a mis-tagged sign goes unflagged.

Ruling 29: a `$`/currency/dollars in a row or header label is a local non-percent unit against a table-wide declaration (keeps the displayed value; conflict if a local percent proof also applies); `pp` glued to a digit counts — both close confirmed unflagged scale changes — cost if wrong: coverage only.

Ruling 30 (amends 29, option a): only a unit-position currency symbol (`($)`, `(€)`, trailing `US$`) keeps the displayed value under a table-wide declaration (P3 precedent); any other currency symbol in a label (amount or descriptive) gives conflict text — the spec's local-unit precedence covers units, not amounts or descriptions — cost if wrong: coverage.

Ruling 31 (amends 30): the trailing-token unit position does not apply when the token directly follows a digit or a scale word (thousand(s), million(s), billion(s), bn, m, mm) — that is an amount → conflict text; `Price, US$` and `Notes due 2030, $` keep their value — cost if wrong: coverage.

Ruling 32 (replaces the currency keep-value exception of Rulings 29-31): under a table-wide percent declaration ANY currency symbol in a row or header label gives conflict text; word units (_ROW_UNIT) keep P3 behaviour; outside table-wide nothing changes — every unit-vs-amount refinement left a wrong-number shape; text is the no-guess outcome — cost if wrong: coverage (`Price ($) | 26` under a percent caption becomes conflict text; 0 such cells in corpus). Ruling 29/30/31 tests pinning a kept value change (authorized).

Ruling 33 (completes 32's "any currency"): ISO 4217 currency codes as whole upper-case words (USD, EUR, GBP, JPY, CNY, RMB, TWD, NTD, HKD, CHF, CAD, AUD, INR, KRW, SGD, BRL, MXN, SEK, NOK, DKK, ZAR, plus a generic `\b[A-Z]{3}\b` is NOT used) in a row or header label under a table-wide declaration give conflict text, like symbols — same class as Ruling 32; coverage only — cost if wrong: coverage.

User decision (2026-10-13): table-level rule (Ruling 34) — a table-wide percent declaration proves nothing in a table with any unit or currency evidence anywhere; such cells become P4 text; tables without evidence (NVDA) unchanged.

Ruling 35 (completes 34): a caption-shaped context line (the positions `units` are collected from, wholly parenthesised or a short unit line) naming a currency, scale or other unit counts as unit evidence; prose context lines do not — STOP if any NVDA cell would change — closes the reported shape without letting prose sentences flip NVDA — cost if wrong: coverage.

Ruling 36 (completes 34's "anywhere"): scan every cell, every non-percent fact, and currency words; NVDA must stay unchanged (stop gate).
