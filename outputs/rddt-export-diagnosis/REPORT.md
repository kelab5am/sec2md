# RDDT 2024 export diagnosis and recovery

Verified 2026-09-21 in `C:\Users\einstein\kelab5am\sec2md`, main at
`7e99ea6352173286c55a3ed0b2eed1830f2c92c5`.

## Improved prompt executed

Diagnose and resolve the failed RDDT 2024 Excel export in the local sec2md checkout.
Compare the earlier successful sample exports with the exact failing byte-input
workflow. Treat the previous "workbook writer slowdown" explanation as an
unverified hypothesis. Use bounded reproductions, stage timings, and stack traces
to locate the cause; increasing CPU alone does not prove progress. Apply the
smallest justified fix, preserve original filings and existing outputs, and
verify the three workbooks plus a relevant successful sample. Report the cause,
evidence, changes, and any remaining extraction warnings.

This applies the user-invoked Astra prompting skill's evidence-backed reporting,
bounded scope, autonomous follow-through, and proportional verification guidance.
No model settings or skill files were changed.

## Cause

The original export was attempted in the restricted sandbox, whose writable roots
exclude `E:\RCQWealth`. The exporter rendered its workbook and then attempted to
create a sibling temporary file for safe publication. Python 3.12's Windows
`tempfile._mkstemp_inner` repeatedly handles `PermissionError` as a possible name
collision when the directory exists and `os.access(directory, os.W_OK)` returns
true. That access check returned true here despite actual file creation failing.
The runtime's `TMP_MAX` was 2147483647, making the failure look like a CPU-bound
hang. No workbook was published because staging-file creation never succeeded.

Bounded original-helper reproduction captured this stack after 12 seconds:

```text
tempfile.py:262 _mkstemp_inner
tempfile.py:579 opener
tempfile.py:582 NamedTemporaryFile
src/sec2md/xlsx.py:51 _publish
src/sec2md/xlsx.py:141 export_xlsx
export_folder.py:160 run
export_folder.py:189 main
```

A single-attempt diagnostic intercepted the first underlying failure:

```text
directory_exists True access_W_OK True TMP_MAX 2147483647
PermissionError: [Errno 13] Permission denied:
E:\RCQWealth\RDDT\Originals\SEC\2024\.sec2md-diagnostic-42f8nd6o.tmp
```

The earlier claims that rising CPU proved progress, and that combining tables
caused a writer bottleneck, were unsupported and incorrect.

## Comparison with successful samples

The prior NVIDIA acceptance workbooks were written under the project worktree's
`outputs/xlsx-acceptance` directory. The current main source and `pyproject.toml`
have no diff against export branch commit `74107ee`. Both used Python 3.12 and
openpyxl 3.1.5. The new Q1 exact-byte probe, using the unchanged source, rendered
all 50 table sheets and published locally in 4.03 seconds:

- Enter publication: 3.62 seconds.
- Exit publication: 4.03 seconds.

The controlling difference demonstrated by the reproduction and recovery is
permission to write to the output destination, not the number of table sheets.

## Recovery

Ran the existing folder helper with approved execution outside the sandbox,
retaining its original-byte input, warn policy, and no-overwrite behavior. A
60-second diagnostic watchdog bounded execution without changing conversion.
The helper completed in 15.02 seconds, exit 0: three created workbooks, 15 review
items, no errors. The 15 review items are ancillary HTML files without an
unambiguous eligible inline-XBRL DocumentType; they were not exported.

No exporter, parser, environment, ACL, or skill modifications were necessary.
For this destination, use the tool's approved execution boundary. If a future
run appears stuck, obtain a bounded stack trace rather than polling CPU alone.

## Results and limits

| Filing | Table sheets | Exported | Needs review | Source text only | Diagnostic messages |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 Q1 | 50 | 7 | 14 | 29 | 172 |
| 2024 Q2 | 48 | 7 | 13 | 28 | 115 |
| 2024 Q3 | 48 | 5 | 12 | 31 | 115 |

Each workbook has an additional Contents sheet and overall `needs_review` quality.
Warnings include unresolved numeric roles, headers, numeric tokens, and footnote
markers. Source-text fallback is not a copy-ready financial table. No attempt was
made to rewrite accounting values or resolve these separate extraction issues.
See `folder-export.json` for each sheet's diagnostics and exact workbook path.

Read-only validation reopened all three workbooks and checked original-byte
SHA-256 against the current sibling HTML and the export report, worksheet counts,
and no frozen top rows. Repeat-run selection skips all three as identical and
does not call the exporter. Sources were not modified.

The existing NVIDIA acceptance suite was rerun against current main:
`12 passed in 21.68s`. It covers both previously successful fixtures, source
reconciliation, primary statement rows and values, notes, and workbook structure.

RDDT workbook creation and structural/source-identity validation are complete.
RDDT financial-cell fidelity and live Excel/Google Sheets acceptance were not
established. Repository source code remains unchanged; this report, the JSON,
validation script, local Q1 probe workbook, and pytest outputs are diagnostic
artifacts under this directory.
