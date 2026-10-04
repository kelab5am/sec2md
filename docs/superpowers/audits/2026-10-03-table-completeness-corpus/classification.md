# Table completeness Phase A corpus run: classification

Date: 2026-10-04. Plan Task 11, Steps 3–5. The spec's summary of this record is its
"Phase A corpus run" section.

- **Spec:** [`../../specs/2026-10-02-sec2md-table-completeness-check-design.md`](../../specs/2026-10-02-sec2md-table-completeness-check-design.md)
- **Implementation:** branch `feat/table-completeness` at `f3639c0`, run from the worktree root.
- **Figures:** all come from [`results.json`](results.json), recomputed from its `documents`, unless a part
  analysis is named. Each recomputed total equals the file's `summary`.

## Corpus

| Part | Documents | Distinct filings |
|---|---|---|
| Fixtures (`tests/fixtures/sec`) | 7 | 5 |
| RCQ primary 10-Ks and 10-Qs in `E:\RCQWealth`, read-only: META 10, RDDT 10, NVDA 12 | 32 | 32 |
| RCQ exhibits with at least two tables: NVDA 20, META 17, RDDT 15 | 52 | none new: exhibits of 34 filings counted above (32 RCQ primaries, 2 fixtures) |
| **Offline subtotal** | **91** | **37** |
| EDGAR, new issuers | 18 | 18 |
| **Total** | **109** | **55** |

- Two RCQ NVDA primaries are the same filings as fixtures, so they are skipped (`duplicates_skipped`): the FY2026
  10-K and the fiscal 2027 Q2 10-Q.
- The plan expected 107 documents and 53 filings, with 16 EDGAR issuers. The user's issuer list has 18.

### EDGAR issuers

The plan listed 16 issuers. On 2026-10-03 the user replaced that list:

- **Dropped:** XOM, BRK, PFE, WMT, JNJ, PRU and HD.
- **Kept:** JPM, KO, MSFT, TSLA, CAT, BAC, UNH, AMZN and GOOGL.
- **Added:** MU, NTRA, NFLX, CRM, CRDO, TSM, BABA, NVO and SPCX.
- TSM, BABA and NVO are foreign private issuers, so their 20-F annual reports are used.
- SPCX (SpaceX) listed in 2026 and has no 10-K yet, so its 10-Q filed in 2026 is used.

From [`edgar_manifest.json`](edgar_manifest.json):

| Ticker | EDGAR name | Form | Filed | Period | Accession |
|---|---|---|---|---|---|
| JPM | JPMORGAN CHASE & CO | 10-K | 2025-02-14 | 2024-12-31 | 0000019617-25-000270 |
| KO | COCA COLA CO | 10-K | 2025-02-20 | 2024-12-31 | 0000021344-25-000011 |
| MSFT | MICROSOFT CORP | 10-K | 2025-07-30 | 2025-06-30 | 0000950170-25-100235 |
| TSLA | Tesla, Inc. | 10-K | 2025-01-30 | 2024-12-31 | 0001628280-25-003063 |
| CAT | CATERPILLAR INC | 10-K | 2025-02-14 | 2024-12-31 | 0000018230-25-000008 |
| BAC | BANK OF AMERICA CORP /DE/ | 10-K | 2025-02-25 | 2024-12-31 | 0000070858-25-000139 |
| UNH | UNITEDHEALTH GROUP INC | 10-K | 2025-02-27 | 2024-12-31 | 0000731766-25-000063 |
| MU | MICRON TECHNOLOGY INC | 10-K | 2025-10-03 | 2025-08-28 | 0000723125-25-000028 |
| NTRA | Natera, Inc. | 10-K | 2025-02-28 | 2024-12-31 | 0001558370-25-001869 |
| NFLX | NETFLIX INC | 10-K | 2025-01-27 | 2024-12-31 | 0001065280-25-000044 |
| CRM | Salesforce, Inc. | 10-K | 2025-03-05 | 2025-01-31 | 0001108524-25-000006 |
| CRDO | Credo Technology Group Holding Ltd | 10-K | 2025-07-02 | 2025-05-03 | 0001628280-25-033813 |
| TSM | TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD | 20-F | 2025-04-17 | 2024-12-31 | 0001193125-25-083423 |
| BABA | Alibaba Group Holding Ltd | 20-F | 2025-06-26 | 2025-03-31 | 0000950170-25-090161 |
| NVO | NOVO NORDISK A S | 20-F | 2025-02-05 | 2024-12-31 | 0001628280-25-003920 |
| AMZN | AMAZON COM INC | 10-Q | 2025-10-31 | 2025-09-30 | 0001018724-25-000123 |
| GOOGL | Alphabet Inc. | 10-Q | 2025-10-30 | 2025-09-30 | 0001652044-25-000091 |
| SPCX | SPACE EXPLORATION TECHNOLOGIES CORP | 10-Q | 2026-08-04 | 2026-06-30 | 0001628280-26-052535 |

### Fetch

- **Older-filings pages.** The first fetch found 16 of the 18 filings. The JPM and BAC 10-Ks had been pushed out of
  the `recent` block of the EDGAR submissions JSON by those banks' many note prospectuses. With the user's approval,
  `fetch_edgar.py` was extended to read the older-filings pages (`filings.files`) whose date range covers the
  filing year. The rerun fetched 18, with 0 failures. No issuer had to be replaced because of a failure.
- **User-Agent:** a name and email supplied by the user. The manifest does not record it.
- **Cache:** the main checkout's ignored `outputs/table-completeness-corpus/`. The manifest records the URL, size
  and SHA-256 of each document, and all 18 hashes equal the `sha256` values in `results.json`.

## Previously reviewed

- **Documents:** the 7 fixtures and the 20 META and RDDT primaries. The spec's revision 6 evidence already
  reviewed them, so they are not classified again here.
- **Parity:** `parity_impl.py` (plan Task 12, Step 5) on the implementation reported 27 documents, finding
  mismatches 0, header-row mismatches 0. Their findings are unchanged from the reviewed evidence.
- **Their findings in `results.json`:** 114 value tables (fixtures 9, META/RDDT 105) with 130 tokens (20 and
  110), and 39 reported references (1 and 38). They have no check-2, ambiguous or no-output findings.

## Classification

**Scope.** This covers every table with a value failure, a check-2 finding, an ambiguous token or no output in
the 82 documents not previously reviewed: the 12 NVDA primaries, the 52 RCQ exhibits and the 18 EDGAR documents.
That is 775 tables. Three analyses produced the rows: Part A (JPM and BAC, 534 tables), Part B (the other 16
EDGAR documents, 214 tables) and Part C1 (offline, 27 tables).

- **Check against `results.json`:** every flagged table is covered by exactly one row. Every row's token count,
  roles, check-2 rows and no-output count equal `results.json`.
- **Ambiguous tokens:** 0 in the whole corpus.
- **Verdict:** `genuine loss` when the token's text is absent from that table's output segment, `false positive`
  otherwise.
- **v6:** every false positive was run through the v6 prototype (`completeness_v6.analyze`). v6 reports the same
  finding in every case, so each one is a definition case.

**Cause keys.** Genuine losses:

- **G1, column merge drops row-0 text.** `table_parser.py:TableParser._merge_grid` merges a column into its left
  neighbour when no body row has text in both. It keeps only the left column's row-0 cell
  (`merged = [current_col[0]]`, line 629). Captions, period headers, column headers and whole paragraph cells in
  row 0 of the merged-in column are lost. This is the first failure in the spec's Background.
- **G2, the same rule drops a first-row amount.** When row 0 is a data row, its amount column merges into the `$`
  column and only the `$` survives. Part A lists JPM 109, its "AAPL shape" case, under one column-merge cause with
  G1. It is filed here under G2.
- **G3, a space inserted at an inline-run boundary.** `get_text(" ")` in `Parser._one_row_table_to_text` splits
  "March 31" into "March 3 1".
- **G4, page header or footer table discarded on purpose.** `parser.py:_process_absolutely_positioned_container`
  hands an absolutely positioned `bottom:0; width:100%` child to `_is_footer_element`, and then only reads a page
  number from it (`_extract_page_number_from_footer`). The table never reaches `_process_element` and has no output.
  This is deliberate parser behaviour, so it is a definition question.
- **G5, one-row PART normalization.** The `PART_HEADER_CELL_RE` branch of `parser.py:_one_row_table_to_text`
  returns only "PART III" and drops the other cells. This is deliberate parser behaviour.

False positives, all definition cases where v6 agrees:

- **F1, unrecognized superscript glued.** A relative-positioned superscript is not a marker under the spec. In cell
  text it joins the digits or letters next to it ("Statement 11", "20341", "equivalents1,2"). TableParser renders it
  with a space.
- **F2, currency code glued.** `<span>RMB</span><span>8,400</span>` gives cell text "RMB8,400", which tokenizes as
  the fragment `400`. The output "RMB 8,400" gives 8400.
- **F3, prose dash glued.** "par value -`<ix:nonfraction>10</ix:nonfraction>`" gives -10. The output
  "par value - 10" gives 10.
- **F4, exhibit-index output tokenized by whole cell.** The source splits identifiers (`classify_cell`), but
  exhibit-index output cells (`output_positions`) and check-2 output lines (`output_line_numbers`) do not.
  "(See Exhibit 4.1)" yields `4.1)`, which `normalize_numeric_token` rejects for its unbalanced parenthesis.
- **F5, three-part exhibit number.** The source splits "Exhibit 10.11.2" into 10.11 (a reference) and 2 (a value).
  Header lines and check-2 lines yield no token for it.
- **F6, inclusive check-2 pointer.** A row whose tokens fit inside the previous row's line matches that line
  again ("a body line at or after the pointer").
- **F7, header-line exclusion.** In a headerless continuation table, the first data row becomes the Markdown header
  line, which check 2 does not read.
- **F8, glued unit suffix.** `<ix:nonfraction>1,097</ix:nonfraction>bps` gives cell text "1,097bps", which
  tokenizes as `1`. The output "1,097 bps" gives 1097.

Check-2 "source row" numbers count data rows, not source rows (review note (d) in the spec).

| Document | Table | Tokens (role) | Verdict | Cause |
|---|---|---|---|---|
| edgar:JPM-10-K-2025-02-14.htm | 6-12, 15-44, 46, 48-49, 51, 53, 55, 58, 61, 64, 67-68 (48 tables) | no output (1 number each; 48 label) | genuine loss | G4. A bare page-number footer ("1", "2") in `div style="bottom:0;position:absolute;width:100%"` inside a `height:45pt;position:relative` page block. |
| edgar:JPM-10-K-2025-02-14.htm | 70, 75, 78, 82, 86, 90, 93, 99, 102, 107, 113, 116, 123, 127, 134, 138, 144, 149, 156, 162, 167, 171, 173, 176, 180, 182, 185, 191, 198, 204, 208, 211, 217, 222, 226, 232, 237, 241, 245, 251, 255, 260, 266, 270, 276, 280, 285, 288, 292, 294, 299, 303, 307, 309, 312, 316, 320, 323, 327, 331, 334, 336, 340, 345, 348, 350, 353, 356, 360, 364, 366, 369, 372, 376, 378, 384, 388, 391, 395, 398, 401, 404, 408, 411, 416, 420, 426, 429, 434, 441, 446, 452, 455, 459, 464, 468, 472, 477, 479, 486, 491, 495, 501, 506, 512, 517, 526, 532, 538, 540, 544, 549, 554, 558, 561, 568, 572, 577, 584, 592, 596, 599, 603, 608, 614, 619, 626, 629, 633, 635, 640, 642, 645, 648, 653, 656, 661, 665, 669, 672, 674, 676, 678 (143 tables) | no output (3 numbers each; 286 label: "2024" and "10" of "JPMorgan Chase & Co./2024 Form 10-K"; 143 body: the page number) | genuine loss | G4, footer variant "JPMorgan Chase & Co./2024 Form 10-K \| N". |
| edgar:JPM-10-K-2025-02-14.htm | 72, 77, 81, 85, 87, 91, 96, 101, 104, 111, 115, 119, 124, 129, 137, 141, 147, 153, 160, 166, 169, 172, 174, 178, 181, 184, 188, 195, 200, 206, 209, 215, 220, 224, 227, 234, 239, 244, 248, 253, 257, 263, 267, 272, 278, 283, 287, 291, 293, 297, 301, 305, 308, 310, 314, 318, 322, 324, 329, 332, 335, 338, 343, 347, 349, 352, 354, 358, 362, 365, 368, 370, 374, 377, 380, 386, 390, 393, 397, 400, 402, 406, 409, 413, 418, 423, 427, 432, 438, 444, 449, 454, 458, 461, 466, 469, 476, 478, 484, 488, 493, 498, 503, 509, 513, 522, 529, 535, 539, 542, 547, 552, 556, 560, 565, 571, 574, 579, 588, 594, 597, 600, 605, 612, 617, 622, 627, 631, 634, 639, 641, 644, 646, 650, 655, 658, 663, 667, 671, 673, 675, 677, 681 (143 tables) | no output (3 numbers each; 143 label: the page number; 286 body: "2024", "10") | genuine loss | G4, mirrored footer variant "N \| JPMorgan Chase & Co./2024 Form 10-K". |
| edgar:JPM-10-K-2025-02-14.htm | 103 | 1 (body): 31 | genuine loss | G1. The row-0 period header "Year ended December 31," merges into the "(in millions)" column. The output header is "(in millions) \| 2024 \| 2023 \| 2022". |
| edgar:JPM-10-K-2025-02-14.htm | 106 | 1 (header): 2022 | genuine loss | G1. The spanning year "2022" merges into a neighbour with an empty row-0 cell. The headers read "2024 — Reported", "2023 — Reported", then a bare "Reported", so the 2022 block is unlabelled. |
| edgar:JPM-10-K-2025-02-14.htm | 109 | 3 (body): 84973, 68837, 61985 | genuine loss | G2. Each row-0 amount column merges into its "$" column. The row renders "Noninterest revenue – reported (c) \| $ \| $ \| $". Material: the reported noninterest revenue for 2024, 2023 and 2022. |
| edgar:JPM-10-K-2025-02-14.htm | 367 | 2 (body): "1" ×2; check 2: source rows 9 and 29, values present but split across output rows | false positive | F8. Cells `<ix:nonfraction>1,097</ix:nonfraction>bps` tokenize as `1`. The output "1,097 bps" gives 1097. Check 2 finds the spurious `1` only on the "Interest rate curve \| 1 %" line. Data rows 9 and 29 are table rows 12 and 35. |
| edgar:JPM-10-K-2025-02-14.htm | 482, 483, 485 | 1 (header) each: 2024, 2023, 2022 | genuine loss | G1. Each row-0 year merges into column 1, whose row-0 cell is empty. The three stacked loan purchase and sale tables lose their only year label. |
| edgar:BAC-10-K-2025-02-25.htm | 13, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 37, 42, 45, 51, 54, 58, 61, 67, 71, 76, 80, 83, 85, 87, 92, 96, 100, 104, 108, 113, 119, 125, 129, 134, 138, 142, 144, 148, 152, 154, 157, 162, 166, 168, 173, 177, 179, 181, 183, 185, 189, 193, 199, 203, 209, 213, 217, 223, 228, 234, 239, 246, 250, 254, 263, 268, 272, 275, 277, 282, 287, 291, 297, 303, 310, 313, 317, 321, 325, 329, 334, 337, 342, 347, 353, 355, 359, 363, 368 (90 tables) | no output (1 number each; 90 label) | genuine loss | G4, footer "N Bank of America" (odd pages), the same DOM shape as JPM. |
| edgar:BAC-10-K-2025-02-25.htm | 14, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 39, 43, 49, 52, 56, 60, 63, 69, 73, 78, 82, 84, 86, 89, 94, 98, 102, 105, 110, 117, 122, 127, 132, 136, 140, 143, 146, 150, 153, 155, 159, 165, 167, 171, 175, 178, 180, 182, 184, 187, 191, 196, 201, 206, 211, 215, 219, 225, 231, 236, 245, 248, 252, 259, 266, 270, 274, 276, 280, 285, 289, 294, 300, 307, 311, 315, 319, 323, 327, 332, 335, 339, 345, 349, 354, 357, 361, 365, 370 (90 tables) | no output (1 number each; 90 label) | genuine loss | G4, footer "Bank of America N" (even pages). |
| edgar:BAC-10-K-2025-02-25.htm | 88, 90, 91, 93, 101, 112, 130, 135, 137, 147, 160, 161 (12 tables) | 13 (body): 1 each, 2 in table 147 | genuine loss | G1. Row 0 is "Table N \| caption", and the caption column is empty below row 0, so only "Table N" survives. Lost caption numbers: "Basel 3" (88, 90, 91, 93); a plain-text "(1)", read as -1 (101, 112, 130, 137, 160, 161); "Top 20" (135); "99 percent and 95 percent" (147). In 135 and 147 other occurrences of the number survive, but the caption occurrence does not. |
| edgar:BAC-10-K-2025-02-25.htm | 358 | check 2: 9 × values present but split across output rows (data rows 4-11 and 20 = exhibits 4.2-4.9 and 4.18); no value tokens; 9 reported references (4.1 ×8, 4.17 ×1) | false positive | F4. The descriptions end "(See Exhibit 4.1)" or "(See Exhibit 4.17)", and both are present in the output. |
| edgar:AMZN-10-Q-2025-10-31.htm | 52 | check 2: values present but split across output rows ×1 (data row 9 = exhibit 104); 1 reported (reference: 101) | false positive | F4. "(included as Exhibit 101)." gives the output token `101)`, which is rejected, so 101 is found only on the "101" line. |
| edgar:BABA-20-F-2025-06-26.htm | 8-15, 17, 24-27, 31-35, 38-41, 43-45, 51-55, 57-58, 61, 63-66, 69-73, 77-85 (51 tables) | 63: 41 (label), 22 (header). 31 ×1 in every table, plus the caption year (2025, 2024 or 2023) in 8-15, 54, 55, 57, 58 | genuine loss | G1. The period caption ("For the year ended March 31, 2025", "Year ended March 31,", "As of March 31,") is dropped. In most of these tables the same merge also moves the year and currency headers one column left of their values (see the notes). |
| edgar:BABA-20-F-2025-06-26.htm | 19 | check 2: values present but split across output rows ×8 (data rows 2, 7-9, 15-18); 10 reported (reference: 2.18, 2.19, 2.24, 2.27-2.29, 2.34-2.37) | false positive | F4. "(included in Exhibit 2.18)" and similar. The 8 split rows are exactly the data rows that carry such a reference. |
| edgar:BABA-20-F-2025-06-26.htm | 75 | 5 (label): 31 genuine; 000, 100, 400, 500 false positive. Check 2: values present but split across output rows ×1 (data row 9) | mixed (1 genuine, 4 false positive; check 2 false positive) | 31: G1 ("As of March 31," dropped). The rest: F2. RMB8,400, 5,000, 2,500 and 1,100 give the fragments 400, 000, 500 and 100. Check-2 row 9 (RMB2,500) is the same artefact. US$ amounts are not affected. |
| edgar:CAT-10-K-2025-02-14.htm | 7 | 2 (body): 2025, 120 | genuine loss | G5. The one-row cover-page table "Part III \| 2025 Annual Meeting Proxy Statement … within 120 days …" renders as "PART III" only (`_one_row_table_to_text`, line 1080). The ITEM branch keeps the title; the PART branch does not. |
| edgar:CAT-10-K-2025-02-14.htm | 25 | check 2: values out of order within the row ×1 (data row 8) | false positive | F6. Data row 8 (`(1) \| 1`) matches data row 7's line `— \| — \| 1 \| (1)` again and projects (1, -1). Its own line is in order. |
| edgar:CAT-10-K-2025-02-14.htm | 33 | 2 (body): 13050, 2781 | genuine loss | G2. The first row "Twelve Months Ended December 31, 2023 - U.S. GAAP \| $ 13,050 \| $ 2,781 \| 21.3 %" becomes the header line "\| … \| $ \| $ \| 21.3 \|". |
| edgar:CAT-10-K-2025-02-14.htm | 34 | 1 (body): 31 | genuine loss | G1. "Twelve Months Ended December 31," is dropped. The header is "\| Millions of dollars \| 2024 \| 2023 \|". |
| edgar:CAT-10-K-2025-02-14.htm | 61 | 1 (label): 11 | false positive | F1. "Statement 1" plus a relative-positioned "1" gives cell text "Statement 11". The output is "Statement 1 1". |
| edgar:CAT-10-K-2025-02-14.htm | 143 | check 2: values present but split across output rows ×1 (data row 1) | false positive | F7. The first data row (exhibit 10.4) of a headerless exhibit-list continuation becomes the header line. Its tokens recur in later body lines. Nothing is reordered. |
| edgar:CRM-10-K-2025-03-05.htm | 15-17, 26, 34-37, 39-40, 42-44, 51, 68-69, 82-83 (18 tables) | 19: 12 (label), 7 (body). 31 ×18, plus 2025 in 68 | genuine loss | G1. "Fiscal Year Ended January 31," (68: "… January 31, 2025") is dropped. |
| edgar:CRM-10-K-2025-03-05.htm | 65 | 1 (body): 48568 | genuine loss | G2. "Balance at January 31, 2023 $ 48,568" becomes "\| Balance at January 31, 2023 \| $ \|". |
| edgar:KO-10-K-2025-02-20.htm | 10 | 2 (body): 1, 2 | genuine loss | G1. Header-row footnote cells "1" and "2" (relative-positioned spans in their own cells, so values under the spec) stand in row-0 columns that merge into their left neighbours. They are footnote references, not amounts. |
| edgar:KO-10-K-2025-02-20.htm | 32, 43, 44, 50, 59, 63 | 7 (label): 2 (32), 2 (43), 2 (44), 311 (50), 20982 and 5 (59), 20242 (63) | false positive | F1. "equivalents1,2", "Fair Value1,2" and "Total4,5" give the fragments 2 and 5; "December 31,1" gives 311; "2024" plus "2" gives 20242. The output has "1,2", "4,5", "31, 1" and "2024 2". All the digits are present. |
| edgar:KO-10-K-2025-02-20.htm | 110 | check 2: values present but split across output rows ×1 (data row 2 = exhibit 10.7) | false positive | F5. The source splits "Exhibit 10.10.6" into 10.10 and 6. The check-2 line yields nothing for it, and 10.10 and 6 exist on other lines. |
| edgar:KO-10-K-2025-02-20.htm | 112 | 1 (body): 2; 1 reported (reference: 10.11) | false positive | F5 on a header line. The first row (exhibit 10.10.2, "… Exhibit 10.11.2 …") is the header line, where "10.11.2" yields no token. The source yields 10.11 and 2. |
| edgar:MSFT-10-K-2025-07-30.htm | 51, 55, 69 | 8 (body): 2025, 30 (51); 2025, 2024, 2023 (55, 69) | genuine loss | G1. The column headers "June 30, 2025" (51) and 2025/2024/2023 (55, 69) are dropped. `_process_headers` then fuses the first body row into the header line, so the reader cannot tell which column is which year. |
| edgar:MU-10-K-2025-10-03.htm | 68, 69 | check 2: values present but split across output rows ×10 (68: data rows 5, 7, 9-11, 14, 16, 18, 19, 23) and ×2 (69: data rows 2, 3); 10 + 2 reported (reference: 4.2, 4.4, 4.6 ×3, 4.11, 4.13, 4.15 ×2, 4.20; 4.22 ×2) | false positive | F4. "(included in Exhibit 4.2)" and similar. "(… from Exhibit 4.18 hereto)" is not flagged, because "4.18" is not followed by ")". |
| edgar:NVO-20-F-2025-02-05.htm | 7, 9, 11, 14, 16, 19, 21, 23, 26, 28, 30, 32, 35, 37, 40, 43, 45, 47, 50, 52, 54, 56, 58, 61, 63, 65, 68, 70, 72, 74, 76, 78, 80, 82, 84, 88, 91, 94 (38 tables) | no output (2 numbers: 20, 2024) ×38 = 76 (label) | genuine loss | G4. The running page header "Novo Nordisk Form 20-F 2024" sits in `div style="bottom:0;position:absolute;width:100%"` inside a `height:54pt;position:relative` div. `_extract_page_number_from_footer` finds 2024 and rejects it as a year. The text appears nowhere in the Markdown. This is not Task 6's positioned-group flattening: the text is discarded, not flattened. |
| edgar:NVO-20-F-2025-02-05.htm | 34 | 6 (body): 20341, 20355, 20372 ×2, 20393, 20404 | false positive | F1. Patent-expiry years such as "2034" are followed by a relative-positioned "1", giving "20341". The output is "2034 1". |
| edgar:SPCX-10-Q-2026-08-04.htm | 28, 33, 46, 51 | 4 (body): 11809, 944, 2728, 443 | genuine loss | G2. Opening balances and first-year maturities are lost from the header line: "Balance at December 31, 2025 $ 11,809", "2026 (remaining six months) $ 944", "… $ 2,728", "Restructuring liabilities as of December 31, 2025 $ 443". |
| edgar:SPCX-10-Q-2026-08-04.htm | 41 | check 2: values out of order within the row ×1 (data row 3) | false positive | F6. Data row 3 (1, 0, 1, 0) fits inside data row 2's line (21, 1, 1, 0, 29, 0), which is still at the pointer. Its own line is in order. |
| edgar:SPCX-10-Q-2026-08-04.htm | 44 | 1 (label): 30 | genuine loss | G1. "As of June 30," is dropped. |
| edgar:TSLA-10-K-2025-01-30.htm | 38, 65 | 2 (body): 487, 531 | genuine loss | G2. "Beginning balance at fair value $ 487" and "December 31, 2021 $ 531" become "\| … \| $ \|". |
| edgar:TSM-20-F-2025-04-17.htm | 79-80, 82-85, 94-95, 193, 312, 315, 326, 332, 354, 388, 390-391, 393-394, 397-399, 403-405, 411-412, 432, 434-437, 441-442, 474-475, 487, 494, 496, 514 (40 tables) | 45: 27 (header), 18 (label). 31 ×40, plus the year in 94, 95, 403-405 | genuine loss | G1. The caption "For the year ended December 31," or "Years Ended December 31" is dropped (94, 95, 403-405 carry a year). In 487 the first of two identical captions is lost. |
| edgar:TSM-20-F-2025-04-17.htm | 293, 295, 298, 300, 302, 310-311, 314, 318, 320, 325, 328-329, 336, 346, 355, 362, 364, 401-402, 407, 471-472, 481-482, 488, 490, 492 (28 tables) | 106 (header). 2023, 2024 and 31 ×2 per table; 320 adds 2022 and a third 31; 471, 472, 481 and 482 have one date | genuine loss | G1. The date column headers "December 31, 2023 \| December 31, 2024" are dropped. The output header is only "\| \| NT$ \| NT$ \|", so the periods cannot be told apart. |
| edgar:TSM-20-F-2025-04-17.htm | 248, 427, 462-464 (5 tables) | 24: 19 (body), 5 (label) | genuine loss | G1. Column headers are dropped: "2022" (248, where "Notes — NT$" now heads the 2022 column), "2021 RSAs … 2024 RSAs" (427), and the maturity buckets "Less Than 1 Year \| 1-3 Years \| 3-5 Years \| More Than 5 Years" and "5-10 … More Than 20 Years" (462-464). |
| edgar:UNH-10-K-2025-02-27.htm | 68 | 1 (label): -10 | false positive | F3. The XBRL fact is +10; the output "par value - 10" gives 10. |
| rcq:NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | 18 | 2 (header) | genuine loss | G1. The period header "Jan 26, 2025" (26, 2025) is dropped, and the second "Less than 12 Months" moves one column left. A reader cannot tell which two columns are Jan 26, 2025. |
| rcq:NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | 19 | 2 (header) | genuine loss | G1, the same fair-value table. |
| rcq:NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | 19 | 2 (header) | genuine loss | G1, the same fair-value table. |
| rcq-exhibit:META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049/a-5q6r23ydgpjcersy.htm | 26 | 1 (body) | genuine loss | G3. "March 31" renders as "March 3 1": a one-row table, two inline `<font>` runs. Source has `31` four times and the output three. |
| rcq-exhibit:META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791/a-3xxtfn45xh6zkzu2.htm | 1 | 1 (body) | genuine loss | G1. The whole "Taxes … Section 6 …" paragraph cell (about 1,900 characters) is dropped. This is the plan's preview case. |
| rcq-exhibit:META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526/a-k2zvkosva2n6op3z.htm | 1 | 1 (body) | genuine loss | G1, the same award-agreement table. |
| rcq-exhibit:NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316/a-walml4cmkenotpwh.htm | 1-10 | no output (2 numbers each: 16, 2024; label) | genuine loss | G4. "Effective Date: September 16, 2024" has 0 matches in the Markdown. This is the plan's preview case. |
| rcq-exhibit:NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023/a-it652ipldyycssve.htm | 3, 5, 7, 9, 11, 13, 15, 17, 19 | no output (2 numbers each: 23, 2025; label) | genuine loss | G4. "Effective Date: January 23, 2025" has 0 matches in the Markdown. Table 1 and the even-numbered tables are empty footer spacers without tokens. |
| rcq-exhibit:NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023/a-rhom5vow6zyepsio.htm | 1, 2 | no output (4 numbers each: 20, 2025, 22, 2021; body) | genuine loss | G4. "Policy Name … Last Updated: 20 FEB 2025; Effective: 22 SEP 2021" has 0 matches in the Markdown. |

## Summaries

### By part

| Part | Scope | Tables | Genuine loss | False positive | Mixed | Value tokens (genuine / false positive) | Check-2 tables |
|---|---|---|---|---|---|---|---|
| A | JPM, BAC | 534 | 532 | 2 | 0 | 1,109 (1,107 / 2) | 2 |
| B | the other 16 EDGAR documents (12 with flagged tables) | 214 | 195 | 18 | 1 | 377 (357 / 20) | 9 |
| C1 | 12 NVDA primaries, 52 RCQ exhibits | 27 | 27 | 0 | 0 | 55 (55 / 0) | 0 |
| **Total** | 82 documents | **775** | **754** | **20** | **1** | **1,541 (1,519 / 22)** | **11** |

- **Value tables in `results.json`:** Part A 533, Part B 206 and Part C1 27, together 766. The other 9 rows are
  tables with only check-2 findings (BAC 358 and 8 in Part B).
- **Roles:** Part A 657 label, 448 body and 4 header; Part B 167 label, 155 header and 55 body; Part C1 38 label,
  11 body and 6 header.
- **Flagged tables:** CRDO, GOOGL, NFLX and NTRA have none. Their reported-only tokens are scanned below.

### Genuine-loss causes (tables / value tokens)

Table counts here include the mixed BABA 75, so Part B shows 196 tables with a genuine loss.

| Cause | Part A | Part B | Part C1 | Total |
|---|---|---|---|---|
| G4, page header or footer table discarded (`_is_footer_element`) | 514 / 1,086 (JPM 334 / 906, BAC 180 / 180) | 38 / 76 (NVO) | 21 / 46 (3 NVDA exhibits) | 573 / 1,208 |
| G1, column merge drops row-0 text (`_merge_grid`) | 17 / 18 | 149 / 270 (148 / 269, plus BABA 75's 31) | 5 / 8 | 171 / 296 |
| G2, column merge drops a first-row amount (`_merge_grid`) | 1 / 3 (JPM 109) | 8 / 9 | 0 | 9 / 12 |
| G5, one-row PART normalization (`_one_row_table_to_text`) | 0 | 1 / 2 (CAT 7) | 0 | 1 / 2 |
| G3, space at an inline-run boundary (`get_text(" ")`) | 0 | 0 | 1 / 1 | 1 / 1 |
| **Total** | 532 / 1,107 | 196 / 357 | 27 / 55 | **755 / 1,519** |

- **Column-merge split by part.** Part A gives its column-merge cause as one figure, 18 tables and 21 tokens.
  Part B gives G1 and G2 together as 156 tables and 279 tokens, counting BABA 75's genuine 31 but not the table.
- **Merge by issuer in Part B:** TSM 73 tables / 175 tokens, BABA 51 / 63, CRM 18 / 19, MSFT 3 / 8, KO, CAT and
  SPCX 1 each (G1). G2: SPCX 28, 33, 46 and 51, TSLA 38 and 65, CRM 65, and CAT 33.
- **No-output tables:** all 573 in the corpus are G4 tables. Their 1,208 tokens equal the no-output tokens in
  `results.json`.

### False positives

| Cause | Tables | Value tokens | Check-2 rows | Reported tokens | v6 result |
|---|---|---|---|---|---|
| F1, unrecognized superscript glued | 8 (KO 32, 43, 44, 50, 59, 63; NVO 34; CAT 61) | 14 | 0 | 0 | same findings: definition case |
| F2, currency code glued | 1 (BABA 75) | 4 | 1 | 0 | same: definition case |
| F3, prose dash glued | 1 (UNH 68) | 1 | 0 | 0 | same: definition case |
| F4, exhibit-index output by whole cell | 5 (BAC 358, AMZN 52, BABA 19, MU 68, MU 69) | 0 | 30 | 32 | same: definition case |
| F5, three-part exhibit number | 2 (KO 110, 112) | 1 | 1 | 1 | same: definition case |
| F6, inclusive check-2 pointer | 2 (CAT 25, SPCX 41) | 0 | 2 | 0 | same: definition case |
| F7, header-line exclusion | 1 (CAT 143) | 0 | 1 | 0 | same: definition case |
| F8, glued unit suffix | 1 (JPM 367) | 2 | 2 | 0 | same: definition case |
| **Total** | **21** (incl. mixed BABA 75) | **22** | **37** | **33** | |

- **Check 2:** all 11 check-2 tables and all 37 check-2 rows in the corpus are false positives. In none of them
  did the renderer reorder or split values.
- **Whole-document parity with v6:**
  - Part A: v6 agrees on every finding (JPM 341 of 341, BAC 195 of 195).
  - Part B: v6 agrees on all 214 flagged tables, except one role label. On TSM 487, a genuine loss, the
    implementation labels the missing 31 [label] and v6 labels it [header]. That is a v6 defect: v6 numbers rows
    with `list.index`, and BeautifulSoup tags compare by markup, so the second of two byte-identical caption rows
    gets the first one's index.
  - Part C1: v6 agrees on all 64 documents in scope.
  - CRDO, GOOGL, NFLX and NTRA, which have no flagged table (added in fix round 1). `completeness_v6.analyze(html,
    capture=False)` was compared with `results.json` on every table: 0 differences in value tokens, roles,
    reported classes, check-2 messages or ambiguous counts. The counts of tables with numbers also match (57, 70, 79
    and 83). v6 has thus been compared on all 82 documents classified here.
- **Minimal reproductions** of JPM 367 and BAC 358 give the same result in the implementation and in v6
  (Part A).

### Implementation defects

None.

### Notes for the spec owner

1. **Page header and footer tables (G4).** All 573 no-output tables in the corpus are page furniture that the
   parser removes on purpose: JPM 334, BAC 180, NVO 38 and the NVDA exhibits 21.
   - **Under D1,** filings whose page headers or footers are HTML tables (here JPM, BAC, NVO and three NVDA
     exhibits) would fail strict on "produced no output" findings.
   - **What they hold:** in JPM, BAC and NVO, page numbers and running titles. A page number survives only as
     `Page.display_page`, and only when `_extract_page_number_from_footer` matches a trailing number (Part A: "of
     10 or more"). The left-number variants ("1 Bank of America", "49 JPMorgan Chase …") never yield one. In the
     three NVDA policy exhibits, the footer is the only place that states the effective or last-updated date, so
     that loss is real.
   - **Not covered by the deferral:** these are HTML tables inside positioned divs, so the "positioned-div tables"
     deferral does not cover them.
   - **Non-table footers:** the walml exhibit's first-page footer is a `<div>`. It is lost the same way, with no
     finding.
   - **Task 6's concern:** a table inside a positioned container might be reported as "no output" while its text
     still reaches the Markdown. No such case was found: all 573 tables are genuinely absent.
2. **Silent column misattribution in BABA and TSM (Part B, material).** The `_merge_grid` merge that drops captions
   also merges a header-only column into the column to its left. Year and currency headers then sit one column left
   of their values.
   - **BABA 24 (income statement):** "\| \| 2023 \| 2024 \| 2025 \| \| \|" stands over
     "\| Revenue \| 5, 24 \| 868,687 \| 941,168 \| 996,347 \| 137,300 \|". FY2023 revenue sits under "2024", and
     FY2024 revenue under "2025". FY2025's RMB 996,347 sits under a blank header. A reader would take 941,168 as
     FY2025 revenue.
   - **Other examples:** in BABA 17, 147,521 (FY2024 audit fees) sits under "2025". In BABA 8, "Parent" stands over
     the row labels. In TSM 79 and 312, "2022" stands over the label column, and TSM 312 also splits "$ \| 331.6".
   - **Extent:** a rough heuristic flags 66 tables (36 BABA, 30 TSM; not each one verified), and it misses cases
     such as BABA 8 and 24.
   - **Detection:** check 1 flags these tables only for the lost caption token ("missing 31"), which understates
     the defect. Check 2 never sees it, because it excludes header lines. Part B rates this its most material
     finding for trading use.
3. **G2 removes real amounts:** opening balances, a first maturity bucket, and JPM 109's reported noninterest
   revenue (84,973 / 68,837 / 61,985). It happens whenever a table has no header row and its first row has a
   separate `$` cell.
4. **Identifier asymmetry (F4, F5, and 61 reported references).** The spec says the identifier rule "applies on
   the source and output sides". The implementation and v6 both skip the split in exhibit-index output cells, on
   header lines and in check-2 output lines.
   - **Where it changes tokens:** only in two shapes. Either the number is directly followed by ")"
     ("(See Exhibit 4.1)"), or it has three parts ("Exhibit 10.11.2").
   - **Truncation:** `_IDENTIFIER` also stops at "Exhibit 10.11." and leaves the final "2" as an enforceable value.
   - **Fixes:** split identifiers on the output side in every mode, or treat an unmatched trailing ")" as
     punctuation.
   - **Count discrepancy in Part B's note 4.** Part B estimates that the output-side split would remove "27 of the
     28" findings in its six F4/F5 tables, "23 reported tokens, 1 value token and 22 check-2 rows". In
     `results.json` those six tables (AMZN 52, BABA 19, MU 68, MU 69, KO 110, KO 112) hold 24 reported tokens,
     1 value token and 22 check-2 rows, 47 findings in all. Part B's own cause summary (F4 23, F5 1) agrees with
     `results.json`. The note's arithmetic does not.
5. **Tokenizer blind spot.** `_NUMBER_TOKEN_RE` takes a closing ")" without an opening "(" ("Exhibit 4.2)",
   "March 31, 2024)", "due 2029)"). `normalize_numeric_token` then drops the number on both sides, so a genuine loss
   of such a number goes undetected.
6. **Glued text (F1, F2, F3, F8).** Cell text joins inline nodes without a space, while TableParser joins them with
   one.
   - **Unchecked values:** in JPM 367, 12 of its 15 "Nbps" cells ("9bps", "115bps") yield no source token, so those
     values are never checked. "2,717bps" yields `2`, which another row's "2 bps" happens to satisfy.
   - **Candidates (Part A):** insert a space where an inline-element boundary separates a digit from a letter, or
     let the tokenizer accept a number followed by a unit suffix. Any change must keep NVDA's kerned digits
     (`1,2<span>34</span>`) concatenated, which is a review case.
   - **Reach of the candidates** (added in fix round 1): they cover F2, F8 and 4 of the 14 F1 tokens (KO 32, 43
     and 44, and KO 59's `5`). They do not cover the other 10 F1 tokens or F3.
     - The other 10 F1 tokens join a digit or comma to a digit: KO 50, KO 59 "20982", KO 63, NVO 34 ×6 and
       CAT 61.
     - Their superscripts are relative-positioned spans with a negative `top` (-2.44 to -3.15 pt). In the six NVDA
       fixtures, the 126 relative-positioned digit spans carry no `top`.
     - The spec's "Phase A corpus run" lists options for these cases ("Raised digits") and for F3 ("Glued dash").
   - **Two readings:** these are false positives if "text present" means the source characters are present,
     separated only by whitespace the parser inserts. Under a strictly literal token reading, some of them (KO 50
     "311", NVO 34 "20341") would count as genuine.
7. **Check-2 matching (F6, F7).** "At or after the pointer" lets a row match the previous row's line again. Searching
   strictly after the pointer first would avoid that. In headerless continuation tables, the first data row lands
   on the header line (CAT 143, also KO 110 and 112).
8. **Plain-text footnote references.** A "(1)" typed as text in a caption is a value token, -1 (BAC 101, 112, 130,
   137, 160 and 161).
9. **Row roles.** Row-0 captions and period headers are reported as "body" when the header-row count is 0 (BAC's 12
   caption tables, JPM 103). This affects reporting only.
10. **CAT 7.** Should the PART branch of `_one_row_table_to_text` keep the other cells, as the ITEM branch keeps
    the title?
11. **Foreign formats.** NT$ (TSM), US$ (BABA) and DKK (NVO) tokenize correctly, and so do TSM's one-decimal amounts
    and BABA's "0.000003125". A glued RMB is misread (F2). No comma-decimal convention appears in any flagged
    table.

## Reported-only scan (Part C2)

54 tables carry reported tokens: 48 have only reported tokens, and 6 also have value or check-2 findings (AMZN 52,
BABA 19, BAC 358, KO 112, MU 68 and MU 69). The token counts by group come from `results.json`. The "in output"
split comes from Part C's literal count of each token in the source cells and in the output segment.

| Group | Tables | Reference | of which in output | of which absent | Marker (absent) |
|---|---|---|---|---|---|
| fixture | 1 | 1 | 1 | 0 | 0 |
| RCQ META/RDDT primaries | 23 | 38 | 10 | 28 | 0 |
| RCQ NVDA primaries | 0 | 0 | 0 | 0 | 0 |
| RCQ exhibits | 1 | 2 | 0 | 2 | 0 |
| EDGAR | 29 | 60 | 50 | 10 | 14 |
| **Total** | **54** | **101** | **61** | **40** | **14** |

Where the tokens come from:

- **59 references:** identifier numbers inside exhibit-index descriptions, all present in the output.
  - `101` in "(included as Exhibit 101)": fixture nvda-2026-08-26-8k t4, 10 META primaries, AMZN 52, BAC 364,
    CRM 86, GOOGL 87, MU 70 and NTRA 210, 17 tokens in all.
  - BABA 18 and 19: 18 tokens. BAC 358 and 360: 12. MU 68 and 69: 12.
- **2 more references, present:** NVO 90 ("Item 19.B") and KO 112 ("Exhibit 10.11.2").
- **36 references, absent:** signature dates in 18 signature blocks (META 10-K 2024 t69 and 10-K 2025 t71, META
  exhibit a-vbntpulu4esivtpj t1, 10 RDDT tables, CRDO 61, GOOGL 89 and 90, MU 71 and SPCX 70).
  - Mechanism: `TableParser._process_headers` fuses the company row with the "Dated: … \| By: \| /s/ …" row, and
    `_clean_empty_rows_and_cols` then drops the date column.
- **4 references, absent:** RDDT 10-K 2024 t70, exhibit-index metadata ("10-Q", "5/7/2024", "dated as of March 19,
  2024"), dropped the same way.
- **14 markers, absent:** TSM 108, 109, 113, 114, 116, 117, 119, 120, 122 and 130. These are header footnote markers
  such as "Bonus (2)", lost with the column headers that carry them (G1).

Findings:

- **No value hides in a reported class.** Of the 115 reported tokens, none is a real value classed as a reference
  or marker. Every number after Exhibit or Item is an exhibit or item number. No signature-date cell holds an
  amount, and every marker is genuine footnote text.
  - Rule (d) does make exhibit-description rates ("4.500% Senior Notes due 2034", "5.327% Senior Notes") into
    references. None is missing.
- **61 of the 101 references are false positives:** the text is in the output. The cause is the same identifier
  asymmetry as F4 and F5, in exhibit-index output cells and on header lines.
  - v6 agrees on all 14 EDGAR tables involved; parity_impl covers the 10 META `101` tables. This is a definition
    case.
  - These tokens are reported only, so they never fail a table.
- **The 40 absent references are genuine renderer losses** that the spec deliberately reports only.

## D3 measurement (Part C3)

**Population.** The tables whose `word_losses` entry has `check1_value_failure: false`: 212 tables with 1,020
missing words. That is 212 of the 999 tables with any word loss; the other 787 also fail check 1. By group:
fixtures 7, META/RDDT primaries 41, RCQ exhibits 6, EDGAR 158, NVDA primaries 0.

**Sample.** Every 7th table in `results.json` document order, starting at index 3: k = 7, offset 3, indexes 3, 10,
…, 206. That gives 30 tables: fixture 1, META/RDDT 6, RCQ exhibit 1 and EDGAR 22, so every group with word-only
tables is sampled. Recomputing the selection from `results.json` gives the same 30 tables.

| # | Document | Table | Missing words | Verdict | Mechanism |
|---|---|---|---|---|---|
| 1 | fixture:nvda-2002-10k | 171 | jen, hsun, huang | noise | Small caps split into inline runs: "/s/ J EN -H SUN H UANG". The typed name "Jen-Hsun Huang" follows intact. |
| 2 | rcq:META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | 66 | filed, herewith | noise | The "Filed Herewith" column is empty in every row of this segment and is removed with its header. |
| 3 | rcq:META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | 68 | filed, herewith | noise | Same as #2. |
| 4 | rcq-exhibit:META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049/a-5q6r23ydgpjcersy.htm | 11 | blica | noise | "República" rendered "Repúblic a" (inline-run split). |
| 5 | rcq:RDDT__10-Q__2024-Q2__c-63xzxqtyzzhgyhto__s-000171344524000054.htm | 52 | filed, herewith | genuine | The "Filed Herewith" header is dropped and its X marks merge into the "Number" column (`_merge_grid` row-0 drop). An X now reads as an exhibit number. |
| 6 | rcq:RDDT__10-K__2024-FY__c-jizatrb5fs63nvbv__s-000171344525000018.htm | 71 | dated, february | genuine | The signature date "Dated: February 12, 2025" is dropped (header fusion, then `_clean_empty_rows_and_cols`). |
| 7 | rcq:RDDT__10-K__2025-FY__c-xecnnfbwds7otmem__s-000171344526000022.htm | 67 | filed, herewith | genuine | Same as #5: exhibit 4.4's X sits under "Number". |
| 8 | rcq:RDDT__10-Q__2026-Q2__c-lttii6wghloh2qqx__s-000171344526000100.htm | 55 | dated, july | genuine | Signature date dropped, as in #6. |
| 9 | edgar:BABA-20-F-2025-06-26.htm | 62 | amounts | genuine (low information) | The column header "Amounts" is dropped (`_merge_grid` row-0 drop). "RMB (in millions)" remains. |
| 10 | edgar:BAC-10-K-2025-02-25.htm | 47 | noninterest, expense | genuine | The table title "Noninterest Expense" is dropped; only "Table 3" is left (`_merge_grid`). |
| 11 | edgar:BAC-10-K-2025-02-25.htm | 95 | bank … debt (12 words) | genuine | The title "Bank of America Corporation Total Loss-Absorbing Capacity and Long-Term Debt" is dropped. |
| 12 | edgar:BAC-10-K-2025-02-25.htm | 111 | residential, mortgage, state, concentrations | genuine | The title "Residential Mortgage State Concentrations" is dropped. |
| 13 | edgar:BAC-10-K-2025-02-25.htm | 123 | commercial … ratios (7 words) | genuine | The title "Commercial Net Charge-offs and Related Ratios" is dropped. |
| 14 | edgar:BAC-10-K-2025-02-25.htm | 141 | allowance, for, credit, losses | genuine | The title "Allowance for Credit Losses" is dropped. |
| 15 | edgar:BAC-10-K-2025-02-25.htm | 358 | notes | noise | The "Notes" column is empty in every row and is removed with its header. |
| 16 | edgar:CRM-10-K-2025-03-05.htm | 84 | provided, herewith | noise | The "Provided Herewith" column is empty in every row of this segment. |
| 17 | edgar:GOOGL-10-Q-2025-10-30.htm | 89 | october, by | genuine | The signature date "October 29, 2025" and "By:" are dropped, as in #6. |
| 18 | edgar:MSFT-10-K-2025-07-30.htm | 4 | none | noise | "None" rendered "N one" (inline-run split). |
| 19 | edgar:MSFT-10-K-2025-07-30.htm | 16 | percentage, change | genuine | The column header "Percentage Change" is dropped, leaving the 10% / 0ppt column unlabelled (`_merge_grid`). |
| 20 | edgar:MSFT-10-K-2025-07-30.htm | 45 | average, life, weighted | genuine | The column header "Weighted Average Life" is dropped, leaving the "24 years" column unlabelled (`_merge_grid`). |
| 21 | edgar:MSFT-10-K-2025-07-30.htm | 80 | incorporated … ending (7 words) | noise (borderline) | The empty "Filed Herewith" and "Period Ending" columns are removed with their headers. The group header "Incorporated by Reference" goes too, but "Form \| Exhibit \| Filing Date" remain readable. |
| 22 | edgar:MU-10-K-2025-10-03.htm | 68 | filed, herewith | noise | The "Filed Herewith" column is empty in every row. |
| 23 | edgar:NFLX-10-K-2025-01-27.htm | 79 | filed, herewith | genuine | The "Filed Herewith" header is dropped and its X marks merge into "Filing Date", as in #5. |
| 24 | edgar:NTRA-10-K-2025-02-28.htm | 189 | procedures | noise | "PROCEDURES" rendered "PROCEDURE S" (one-row text, inline-run split). |
| 25 | edgar:TSLA-10-K-2025-01-30.htm | 73 | filed, herewith | noise | The "Filed Herewith" column is empty in every row. |
| 26 | edgar:TSLA-10-K-2025-01-30.htm | 81 | filed, herewith | noise | Same as #25. |
| 27 | edgar:TSM-20-F-2025-04-17.htm | 113 | common, shares, …, expiration (11 words) | genuine | All column headers are dropped: "Common Shares Underlying Outstanding RSAs", "Exercise Price", "Grant Date", "Expiration Date" (`_merge_grid`). |
| 28 | edgar:TSM-20-F-2025-04-17.htm | 130 | salary … total (8 words) | genuine | The compensation column headers are dropped (`_merge_grid`). |
| 29 | edgar:TSM-20-F-2025-04-17.htm | 306 | change … ineffectiveness (8 words) | genuine | The value-column header "Change in Value Used for Calculating Hedge Ineffectiveness" is dropped. |
| 30 | edgar:TSM-20-F-2025-04-17.htm | 343 | total … rate (8 words) | genuine | The headers "Total Issue Amount US$ (In Millions)" and "Coupon Rate" are dropped, and the first data row is fused into the header. |

**Counts.** 18 genuine text losses and 12 noise: a **noise rate of 40%** (12 of 30; 95% Wilson interval about
25–58%).

- **Borderline calls:** #9 is a low-information genuine loss, and #21 is borderline noise. Flipping either one
  moves the rate to 37–43%.
- **Projection:** roughly 127 of the 212 tables are genuine text losses (about 90–160 at the interval ends). All
  of them are invisible to check 1.
- **Genuine mechanisms (18):**
  - row-0 header or title cell dropped by `_merge_grid`: 12 (5 BAC titles, 6 column headers, BABA "Amounts");
  - "Filed Herewith" header dropped, with its X marks fused into a neighbouring column: 3;
  - signature date dropped by header fusion and `_clean_empty_rows_and_cols`: 3.
- **Noise mechanisms (12):**
  - header of an all-empty column removed with the column: 8;
  - word split at an inline-run boundary by `get_text(" ")`: 4;
  - header fusion reordering, the noise the spec anticipated: 0. A word multiset ignores order.

**Top missing words.**

- **All 999 tables** (`d3_top_missing_words`): form 331, jpmorgan 286, chase 286, co 286, of 250, ended 186,
  bank 183, america 183, march 140, december 99, months 94, three 88, the 76, year 67, filed 47, herewith 47, or 46,
  date 40, years 40, and 39, novo 38, nordisk 38, by 36, for 33, as 31.
  - Page header and footer tables dominate the list: "JPMorgan Chase & Co./… Form 10-K", "Bank of America",
    "Novo Nordisk". The rest are lost period headers.
  - Both kinds already fail check 1.
- **The 212 word-only tables:** herewith 47, filed 46, by 31, date 21, of 21, shares 20, incorporated 19,
  reference 19, total 17, and 16, common 16. These come from exhibit-index column headers, signature blocks and
  dropped column headers.

**Examples.**

- **Genuine 1: TSM 20-F table 130 (executive compensation).**
  - Source header: "Name/Title \| Salary \| Bonus (2) \| Stock Awards \| All Other Compensation (3) \| Total".
  - Output header: "Name/Title — NT$ \| NT$ \| NT$ \| NT$ \| NT$ \| US$".
  - The amounts 16.0 / 635.8 / 287.8 / 6.8 / 946.4 are unlabelled. Check 1 sees only the reported markers (2) and
    (3).
- **Genuine 2: RDDT 10-Q 2024 Q2 table 52 (exhibit index).** The "Filed Herewith" header is lost, and the X marks
  of exhibits 31.1–104 now sit under "Incorporated by Reference — … Number". NFLX table 79 is the same, with the X
  under "Filing Date".
- **Noise 1: MSFT 10-K table 4.** "None" renders as "N one", so "none" counts as missing.
- **Noise 2: META 10-K 2024 table 66.** The "Filed Herewith" column has no entry in this segment, and the renderer
  removes it with its header.

**Recommendation (Part C), for Astra and the user.**

- **No enforced word check.** 40% noise is far too high for a gate, and word losses are not value losses: D1 and
  D4 enforce values only.
- **A report-only word-multiset diagnostic in Phase B, with two noise filters.** It finds real losses that check 1
  cannot see because they have no digits: column headers, table titles, misattributed X marks and signature dates.
  - Filter (a): compare letters with intra-word spaces removed, or join adjacent output fragments, and tokenize
    Unicode letters rather than `[a-z]`. This removes the inline-split noise.
  - Filter (b): ignore source header words whose header cell spans only columns with no non-empty body cell.
    Defining the filter on the cell's full span keeps spanning titles such as BAC's.
  - On this sample the filters would remove 11–12 of the 12 noise cases and keep all 18 genuine ones. That is a
    projection: re-measure on this corpus before adopting, with a target below 10% noise.
- **Priority.** Every genuine loss in the sample shares its root cause with check 1's header losses: `_merge_grid`'s
  row-0 drop and the header-only-column drop in `_clean_empty_rows_and_cols`. Fixing those in the table-merge and
  header-rules spec removes most losses that either check sees. The word measure then serves mainly as a regression
  net.
