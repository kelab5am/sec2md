# Positioned page layout: corpus check

The acceptance step the user added to [the spec](../../specs/2026-10-24-sec2md-positioned-page-layout-design.md) ("Corpus check"): branch `fix/positioned-layout` against `main` at `c6e120a` on every document we hold, to show that the change does not alter filings that convert correctly today.

## Corpus

2,217 distinct documents (by SHA-256), all read in place:

| Group | Documents | Source |
|---|---|---|
| `fixture` | 10 | `tests/fixtures/sec`, including the three this spec adds |
| `edgar` | 18 | Phase A's EDGAR cache (`outputs/table-completeness-corpus`) |
| `recent` | 70 | the recent filings corpus (`outputs/recent-filings-corpus`), each checked against its manifest SHA-256 |
| `vault` | 461 | every primary SEC original in `E:\RCQWealth` (AAPL, CRDO, CRM, META, MSFT, NVDA, RDDT, SPCX), read only |
| `vault-exhibit` | 1,658 | every retained exhibit and filing-index page beside them |

## Method

`compare.py` converts each document on both sides, each in its own process with its own `PYTHONPATH`. It then compares:
- every page's content hash, number and display page;
- the table completeness report: failures, reported tokens, structure messages and tables checked.

The branch side also counts the containers that took the flow path. The steps are:

```bash
python compare.py list --out docs.json --fixtures tests/fixtures/sec --phase-a-cache <main>/outputs/table-completeness-corpus --recent-cache <main>/outputs/recent-filings-corpus --vault E:/RCQWealth
PYTHONPATH=<git archive c6e120a>/src python compare.py run --docs docs.json --out main.jsonl --dumps <scratch>/dumps-main --workers 12
PYTHONPATH=<this worktree>/src python compare.py run --docs docs.json --out branch.jsonl --dumps <scratch>/dumps-branch --workers 12
python compare.py diff --main main.jsonl --branch branch.jsonl --out results.json
```

The Markdown dumps used to explain each difference stay in a scratch folder. [`results.json`](results.json) holds the comparison.

## Result

**Overall.** No conversion errors on either side. 1,695 documents are identical in output and check results. No document's failures, reported tokens or structure findings rose.

**Rendered output changed in 480 documents**, all explained:

| Cause | Documents | What changed |
|---|---|---|
| Flow path (D2–D5) | 461 vault index pages | Each EDGAR filing-index page's banner (`SEC.gov`, `EDGAR`, `Latest Filings`, `Filings search tools`, `Filing Detail`) sits in a `position:absolute` box without coordinates. `main` dropped it silently; the branch reads it. Identical in all 461. |
| Flow path | 1 (TSM fixture) | 107 → 166,481 characters on 66 pages: the cover page, the auditor's report, the statements and the notes. |
| D8 merge | 18 | Split percent and paren negatives join their values, and the empty marker columns go. Filings: BABA's exhibit and 20-Fs, TSM's 20-Fs, TSLA's 10-Ks, three META and four NVDA filings from 2019–20, one CRM 8-K exhibit. Examples: META `(61 \| )%` → `(61)%`, NVDA `(0.5 \| )` → `(0.5)`, CRM `94 \| %` → `94 %`. |

For all 18 D8 documents, the multiset of numbers in table bodies is unchanged. The only numbers and words that go are copies of spanning header text (`Year Ended December 31,`) that sat over the removed marker columns. The independent-header veto keeps a column that owns header text of its own.

**Check results changed without a render change in 42 documents**, from the D7 fixes:

| | `main` | branch |
|---|---|---|
| Value failures | 935 | 935 |
| Reported tokens | 74 | 55 |
| Structure messages | 413 | 221 |

The structure messages that go are check 2's false "values present but split across output rows" on rows labelled `(Note N)` (D7.3). The reported tokens that go are identifier references in header lines (D7.2).

Across the whole corpus, value failures fall only in the two fixtures this spec targets: TSM 125 → 0 tables and BABA 1 → 0.
