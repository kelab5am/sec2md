# All-table XBRL period check: base and revision 6

Output of `all_facts.py` (spec Acceptance 3b) on the two export directories of the revision 6 acceptance run: `base` (main's code) and `new6` (branch `fix/xlsx-header-detection` at `429f1fd`). Each report below is the script's report unchanged, with headings moved down one level. The classification of every mismatch, yearless period header and unlocated-fact table is in `README.md`, section "Revision 6".

## All-table XBRL period check: `base`

60 filings. Every inline XBRL fact in every table that is not `source_text_only`.

### Verdicts per group

| Group | Tables | Facts | ok | mismatch | unparsed length | no header date | label column | not placed |
|---|---|---|---|---|---|---|---|---|
| META | 456 | 6813 | 6431 | 0 | 0 | 284 | 98 | 0 |
| NVDA | 397 | 5865 | 5030 | 19 | 0 | 727 | 89 | 0 |
| RDDT | 312 | 4034 | 3666 | 0 | 0 | 232 | 136 | 0 |
| Others | 681 | 8758 | 4801 | 7 | 0 | 3833 | 117 | 0 |
| Total | 1846 | 25470 | 19928 | 26 | 0 | 5076 | 440 | 0 |

### Mismatches: 26 facts in 11 tables

- CRDO-10-K-2025-07-02.htm #44 (exported) Beginning valuation allowance: 3
- CRDO-10-K-2025-07-02.htm #46 (exported) Beginning gross unrecognized tax benefits: 2
- NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #44 (exported) Deferred Revenue: 2
- NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #53 (exported) A reconciliation of gross unrecognized tax benefits: 3
- NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #43 (exported) Deferred Revenue: 2
- NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #52 (exported) A reconciliation of gross unrecognized tax benefits: 3
- NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #39 (exported) Deferred Revenue: 2
- NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #49 (exported) A reconciliation of gross unrecognized tax benefits: 3
- NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #20 (exported) Adjustments to the carrying value of our non-marketable equi: 2
- NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #28 (exported) Deferred Revenue: 2
- TSM-20-F-2025-04-17.htm #135 (exported) Operating loss carryforward: 2

#### CRDO-10-K-2025-07-02.htm #44 (exported): Beginning valuation allowance

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r2c4 | Beginning valuation allowance | 23,258 | DeferredTaxAssetsValuationAllowance | c-5: I 2024-04-27 | May 3, 2025 |
| r2c10 | Beginning valuation allowance | 9,306 | DeferredTaxAssetsValuationAllowance | c-30: I 2023-04-29 | April 27, 2024 |
| r2c16 | Beginning valuation allowance | 5,170 | DeferredTaxAssetsValuationAllowance | c-21: I 2022-04-30 | April 29, 2023 |

#### CRDO-10-K-2025-07-02.htm #46 (exported): Beginning gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r2c4 | Beginning gross unrecognized tax benefits | 4,574 | UnrecognizedTaxBenefits | c-5: I 2024-04-27 | May 3, 2025 |
| r2c10 | Beginning gross unrecognized tax benefits | 2,865 | UnrecognizedTaxBenefits | c-30: I 2023-04-29 | April 27, 2024 |

#### NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #44 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-10: I 2023-01-29 | Jan 28, 2024 |
| r4c10 | Balance at beginning of period | 502 | ContractWithCustomerLiability | c-27: I 2022-01-30 | Jan 29, 2023 |

#### NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #53 (exported): A reconciliation of gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,238 | UnrecognizedTaxBenefits | c-10: I 2023-01-29 | Jan 28, 2024 |
| r4c10 | Balance at beginning of period | 1,013 | UnrecognizedTaxBenefits | c-27: I 2022-01-30 | Jan 29, 2023 |
| r4c16 | Balance at beginning of period | 776 | UnrecognizedTaxBenefits | c-16: I 2021-01-31 | Jan 30, 2022 |

#### NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #43 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,337 | ContractWithCustomerLiability | c-14: I 2024-01-28 | Jan 26, 2025 |
| r4c10 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-28: I 2023-01-29 | Jan 28, 2024 |

#### NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #52 (exported): A reconciliation of gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,670 | UnrecognizedTaxBenefits | c-14: I 2024-01-28 | Jan 26, 2025 |
| r4c10 | Balance at beginning of period | 1,238 | UnrecognizedTaxBenefits | c-28: I 2023-01-29 | Jan 28, 2024 |
| r4c16 | Balance at beginning of period | 1,013 | UnrecognizedTaxBenefits | c-19: I 2022-01-30 | Jan 29, 2023 |

#### NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #39 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,813 | ContractWithCustomerLiability | c-12: I 2025-01-26 | Jan 25, 2026 |
| r4c10 | Balance at beginning of period | 1,337 | ContractWithCustomerLiability | c-26: I 2024-01-28 | Jan 26, 2025 |

#### NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #49 (exported): A reconciliation of gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 2,861 | UnrecognizedTaxBenefits | c-12: I 2025-01-26 | Jan 25, 2026 |
| r4c10 | Balance at beginning of period | 1,670 | UnrecognizedTaxBenefits | c-26: I 2024-01-28 | Jan 26, 2025 |
| r4c16 | Balance at beginning of period | 1,238 | UnrecognizedTaxBenefits | c-17: I 2023-01-29 | Jan 28, 2024 |

#### NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #20 (exported): Adjustments to the carrying value of our non-marketable equi

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r3c4 | Balance at beginning of period | 1,321 | EquitySecuritiesWithoutReadilyDeterminableFairValueAmount | c-5: I 2024-01-28 | Apr 28, 2024 |
| r3c10 | Balance at beginning of period | 288 | EquitySecuritiesWithoutReadilyDeterminableFairValueAmount | c-22: I 2023-01-29 | Apr 30, 2023 |

#### NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #28 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,337 | ContractWithCustomerLiability | c-5: I 2024-01-28 | Apr 28, 2024 |
| r4c10 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-22: I 2023-01-29 | Apr 30, 2023 |

#### TSM-20-F-2025-04-17.htm #135 (exported): Operating loss carryforward

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c7 | No expiry date | 640.0 | DeductibleTemporaryDifferencesForWhichNoDeferredTaxAssetIsRecognizedWithoutExpiryDate | PAsOn12_31_2024: I 2024-12-31 | December 31, 2023 |
| r4c19 | No expiry date | 11,896.9 | DeductibleTemporaryDifferencesForWhichNoDeferredTaxAssetIsRecognizedWithoutExpiryDate | PAsOn12_31_2023: I 2023-12-31 | December 31, 2024 |

### Headers with an unparsed length: 0 headers in 0 tables

A dated header with length wording but no length this script reads. Its facts are not checked for length.

| Filing | Table | Status | Title | Column: header | Verdicts of its facts |
|---|---|---|---|---|---|

### Yearless period headers: 15 tables

| Filing | Table | Status | Title | Headers (column: header) |
|---|---|---|---|---|
| AMZN-10-Q-2025-10-31.htm | #23 | needs_review | Scheduled vesting — restricted stock units | 1: Three Months Ended December 31,; 2: Year Ended December 31,; 3: Year Ended December 31,; 4: Year Ended December 31,; 5: Year Ended December 31, |
| BABA-20-F-2025-06-26.htm | #23 | needs_review | ALIBABA GROUP HOLDING LIMITED | 3: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #33 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #37 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: Year ended March 31,; 4: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #41 | needs_review | Composition of income tax expenses | 2: Year ended March 31,; 4: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #50 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: Year ended March 31,; 4: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #61 | needs_review | For the years ended March 31, 2023, 2024 and 2025, equity me | 3: Year ended March 31, |
| CRDO-10-K-2025-07-02.htm | #26 | needs_review | Revenue | 1: Year Ended; 2: Year Ended; 3: Year Ended; 4: Year Ended |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #57 | exported | U.S. federal statutory income tax rate | 1: Year Ended December 31, |
| NTRA-10-K-2025-02-28.htm | #33 | needs_review | Contractual Commitments | 3: Year Ended December 31,; 4: Year Ended December 31,; 5: Year Ended December 31,; 6: Year Ended December 31,; 7: Year Ended December 31,; 8: Year Ended December 31,; 9: Year Ended December 31,; 10: Year Ended December 31,; 11: Year Ended December 31, |
| NTRA-10-K-2025-02-28.htm | #36 | exported | Valuation of Stock Option Grants | 3: Year ended December 31,; 7: Year ended December 31,; 11: Year ended December 31, |
| SPCX-10-Q-2026-08-04.htm | #47 | needs_review | Space | 1: Three Months Ended; 2: Three Months Ended; 3: Six Months Ended; 4: Six Months Ended |
| SPCX-10-Q-2026-08-04.htm | #48 | needs_review | (number) | 1: Three Months Ended; 2: Three Months Ended; 3: Six Months Ended; 4: Six Months Ended |
| SPCX-10-Q-2026-08-04.htm | #50 | needs_review | (dollars per month) | 1: Three Months Ended; 2: Three Months Ended; 3: Six Months Ended; 4: Six Months Ended |
| TSM-20-F-2025-04-17.htm | #99 | needs_review | Amounts recognized in respect of these defined benefit plans | 3: Years Ended December 31 |

### Tables with numeric-fact cells but no located facts: 5

| Filing | Table | Status | Provenance | Title | Fact cells |
|---|---|---|---|---|---|
| CRM-10-K-2025-03-05.htm | #69 | exported | ambiguous | Share Repurchase Program | 9 |
| CRM-10-K-2025-03-05.htm | #70 | needs_review | ambiguous | Dividends | 8 |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #56 | exported | ambiguous | Sales to direct customers which represented 10% or more of t | 4 |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #36 | exported | ambiguous | Sales to direct customers which represented 10% or more of t | 7 |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #36 | exported | ambiguous | Sales to direct customers which represented 10% or more of t | 6 |

## All-table XBRL period check: `new6`

60 filings. Every inline XBRL fact in every table that is not `source_text_only`.

### Verdicts per group

| Group | Tables | Facts | ok | mismatch | unparsed length | no header date | label column | not placed |
|---|---|---|---|---|---|---|---|---|
| META | 798 | 12958 | 10277 | 0 | 0 | 2553 | 128 | 0 |
| NVDA | 652 | 11308 | 8808 | 25 | 0 | 2224 | 251 | 0 |
| RDDT | 465 | 6002 | 5087 | 0 | 0 | 743 | 172 | 0 |
| Others | 1033 | 17889 | 11103 | 79 | 0 | 6440 | 267 | 0 |
| Total | 2948 | 48157 | 35275 | 104 | 0 | 11960 | 818 | 0 |

### Mismatches: 104 facts in 25 tables

- AMZN-10-Q-2025-10-31.htm #19 (exported) Commitments: 32
- AMZN-10-Q-2025-10-31.htm #23 (exported) Scheduled vesting — restricted stock units: 4
- CRDO-10-K-2025-07-02.htm #44 (exported) Beginning valuation allowance: 3
- CRDO-10-K-2025-07-02.htm #46 (exported) Beginning gross unrecognized tax benefits: 2
- JPM-10-K-2025-02-14.htm #297 (exported) Loans: 16
- MU-10-K-2025-10-03.htm #22 (exported) Consolidated Statements of Cash Flows: 3
- NFLX-10-K-2025-01-27.htm #70 (exported) Which $251 million and $188 million, respectively, if recogn: 3
- NTRA-10-K-2025-02-28.htm #15 (exported) Inventory: 2
- NTRA-10-K-2025-02-28.htm #16 (exported) Accumulated Other Comprehensive Income (Loss): 2
- NTRA-10-K-2025-02-28.htm #21 (exported) The following table shows the changes in the balance of defe: 2
- NTRA-10-K-2025-02-28.htm #26 (exported) Allowance for Doubtful Accounts: 3
- NTRA-10-K-2025-02-28.htm #30 (exported) Reserve balance and activities for refunds to insurance carr: 2
- NTRA-10-K-2025-02-28.htm #42 (exported) A reconciliation of the beginning and ending amount of gross: 3
- NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #44 (exported) Deferred Revenue: 2
- NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #53 (exported) A reconciliation of gross unrecognized tax benefits: 3
- NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #43 (exported) Deferred Revenue: 2
- NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #52 (exported) A reconciliation of gross unrecognized tax benefits: 3
- NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #39 (exported) Deferred Revenue: 2
- NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #49 (exported) A reconciliation of gross unrecognized tax benefits: 3
- NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm #26 (exported) Deferred Revenue: 2
- NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm #27 (exported) Deferred Revenue: 2
- NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm #27 (exported) Deferred Revenue: 2
- NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #20 (exported) Adjustments to the carrying value of our non-marketable equi: 2
- NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #28 (exported) Deferred Revenue: 2
- TSM-20-F-2025-04-17.htm #135 (exported) Operating loss carryforward: 2

#### AMZN-10-Q-2025-10-31.htm #19 (exported): Commitments

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r3c10 | Long-term debt principal and interest | 4,518 | LongTermDebtMaturitiesRepaymentsOfPrincipalAndInterestInYearOne | c-14: I 2025-09-30 | Year Ended December 31, — 2026 |
| r3c16 | Long-term debt principal and interest | 10,548 | LongTermDebtMaturitiesRepaymentsOfPrincipalAndInterestInYearTwo | c-14: I 2025-09-30 | Year Ended December 31, — 2027 |
| r3c22 | Long-term debt principal and interest | 3,688 | LongTermDebtMaturitiesRepaymentsOfPrincipalAndInterestInYearThree | c-14: I 2025-09-30 | Year Ended December 31, — 2028 |
| r3c28 | Long-term debt principal and interest | 4,388 | LongTermDebtMaturitiesRepaymentsOfPrincipalAndInterestInYearFour | c-14: I 2025-09-30 | Year Ended December 31, — 2029 |
| r4c9 | Operating lease liabilities | 13,414 | LesseeOperatingLeaseLiabilityPaymentsDueNextTwelveMonths | c-14: I 2025-09-30 | Year Ended December 31, — 2026 |
| r4c15 | Operating lease liabilities | 12,434 | LesseeOperatingLeaseLiabilityPaymentsDueYearTwo | c-14: I 2025-09-30 | Year Ended December 31, — 2027 |
| r4c21 | Operating lease liabilities | 11,312 | LesseeOperatingLeaseLiabilityPaymentsDueYearThree | c-14: I 2025-09-30 | Year Ended December 31, — 2028 |
| r4c27 | Operating lease liabilities | 10,207 | LesseeOperatingLeaseLiabilityPaymentsDueYearFour | c-14: I 2025-09-30 | Year Ended December 31, — 2029 |
| r5c9 | Finance lease liabilities, including interest | 1,665 | FinanceLeaseLiabilityPaymentsDueNextTwelveMonths | c-14: I 2025-09-30 | Year Ended December 31, — 2026 |
| r5c15 | Finance lease liabilities, including interest | 1,524 | FinanceLeaseLiabilityPaymentsDueYearTwo | c-14: I 2025-09-30 | Year Ended December 31, — 2027 |
| r5c21 | Finance lease liabilities, including interest | 1,521 | FinanceLeaseLiabilityPaymentsDueYearThree | c-14: I 2025-09-30 | Year Ended December 31, — 2028 |
| r5c27 | Finance lease liabilities, including interest | 1,187 | FinanceLeaseLiabilityPaymentsDueYearFour | c-14: I 2025-09-30 | Year Ended December 31, — 2029 |
| r6c9 | Financing obligations, including interest (1) | 532 | FinancingObligationsFutureMinimumPaymentsDueInOneYear | c-14: I 2025-09-30 | Year Ended December 31, — 2026 |
| r6c15 | Financing obligations, including interest (1) | 540 | FinancingObligationsFutureMinimumPaymentsDueInTwoYears | c-14: I 2025-09-30 | Year Ended December 31, — 2027 |
| r6c21 | Financing obligations, including interest (1) | 548 | FinancingObligationsFutureMinimumPaymentsDueInThreeYears | c-14: I 2025-09-30 | Year Ended December 31, — 2028 |
| r6c27 | Financing obligations, including interest (1) | 557 | FinancingObligationsFutureMinimumPaymentsDueInFourYears | c-14: I 2025-09-30 | Year Ended December 31, — 2029 |
| r7c9 | Leases not yet commenced | 4,856 | UnrecordedUnconditionalPurchaseObligationBalanceOnFirstAnniversary | c-61: I 2025-09-30 (dims) | Year Ended December 31, — 2026 |
| r7c15 | Leases not yet commenced | 5,868 | UnrecordedUnconditionalPurchaseObligationBalanceOnSecondAnniversary | c-61: I 2025-09-30 (dims) | Year Ended December 31, — 2027 |
| r7c21 | Leases not yet commenced | 5,089 | UnrecordedUnconditionalPurchaseObligationBalanceOnThirdAnniversary | c-61: I 2025-09-30 (dims) | Year Ended December 31, — 2028 |
| r7c27 | Leases not yet commenced | 4,995 | UnrecordedUnconditionalPurchaseObligationBalanceOnFourthAnniversary | c-61: I 2025-09-30 (dims) | Year Ended December 31, — 2029 |
| r8c9 | Unconditional purchase obligations (2) | 14,864 | UnrecordedUnconditionalPurchaseObligationBalanceOnFirstAnniversary | c-62: I 2025-09-30 (dims) | Year Ended December 31, — 2026 |
| r8c15 | Unconditional purchase obligations (2) | 8,697 | UnrecordedUnconditionalPurchaseObligationBalanceOnSecondAnniversary | c-62: I 2025-09-30 (dims) | Year Ended December 31, — 2027 |
| r8c21 | Unconditional purchase obligations (2) | 6,288 | UnrecordedUnconditionalPurchaseObligationBalanceOnThirdAnniversary | c-62: I 2025-09-30 (dims) | Year Ended December 31, — 2028 |
| r8c27 | Unconditional purchase obligations (2) | 5,722 | UnrecordedUnconditionalPurchaseObligationBalanceOnFourthAnniversary | c-62: I 2025-09-30 (dims) | Year Ended December 31, — 2029 |
| r9c9 | Other commitments (3) | 2,292 | OtherCommitmentDueInNextTwelveMonths | c-14: I 2025-09-30 | Year Ended December 31, — 2026 |
| r9c15 | Other commitments (3) | 1,330 | OtherCommitmentDueInSecondYear | c-14: I 2025-09-30 | Year Ended December 31, — 2027 |
| r9c21 | Other commitments (3) | 1,079 | OtherCommitmentDueInThirdYear | c-14: I 2025-09-30 | Year Ended December 31, — 2028 |
| r9c27 | Other commitments (3) | 1,005 | OtherCommitmentDueInFourthYear | c-14: I 2025-09-30 | Year Ended December 31, — 2029 |
| r10c10 | Total commitments | 42,141 | ContractualObligationDueInNextTwelveMonths | c-14: I 2025-09-30 | Year Ended December 31, — 2026 |
| r10c16 | Total commitments | 40,941 | ContractualObligationDueInSecondYear | c-14: I 2025-09-30 | Year Ended December 31, — 2027 |
| r10c22 | Total commitments | 29,525 | ContractualObligationDueInThirdYear | c-14: I 2025-09-30 | Year Ended December 31, — 2028 |
| r10c28 | Total commitments | 28,061 | ContractualObligationDueInFourthYear | c-14: I 2025-09-30 | Year Ended December 31, — 2029 |

#### AMZN-10-Q-2025-10-31.htm #23 (exported): Scheduled vesting — restricted stock units

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r3c9 | Scheduled vesting — restricted stock units | 112.8 | ShareBasedCompensationArrangementByShareBasedPaymentAwardEquityInstrumentsOtherThanOptionsVestingYearOne | c-148: I 2025-09-30 (dims) | Year Ended December 31, — 2026 |
| r3c15 | Scheduled vesting — restricted stock units | 70.9 | ShareBasedCompensationArrangementByShareBasedPaymentAwardEquityInstrumentsOtherThanOptionsVestingYearTwo | c-148: I 2025-09-30 (dims) | Year Ended December 31, — 2027 |
| r3c21 | Scheduled vesting — restricted stock units | 29.7 | ShareBasedCompensationArrangementByShareBasedPaymentAwardEquityInstrumentsOtherThanOptionsVestingYearThree | c-148: I 2025-09-30 (dims) | Year Ended December 31, — 2028 |
| r3c27 | Scheduled vesting — restricted stock units | 8.3 | ShareBasedCompensationArrangementByShareBasedPaymentAwardEquityInstrumentsOtherThanOptionsVestingYearFour | c-148: I 2025-09-30 (dims) | Year Ended December 31, — 2029 |

#### CRDO-10-K-2025-07-02.htm #44 (exported): Beginning valuation allowance

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r2c4 | Beginning valuation allowance | 23,258 | DeferredTaxAssetsValuationAllowance | c-5: I 2024-04-27 | May 3, 2025 |
| r2c10 | Beginning valuation allowance | 9,306 | DeferredTaxAssetsValuationAllowance | c-30: I 2023-04-29 | April 27, 2024 |
| r2c16 | Beginning valuation allowance | 5,170 | DeferredTaxAssetsValuationAllowance | c-21: I 2022-04-30 | April 29, 2023 |

#### CRDO-10-K-2025-07-02.htm #46 (exported): Beginning gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r2c4 | Beginning gross unrecognized tax benefits | 4,574 | UnrecognizedTaxBenefits | c-5: I 2024-04-27 | May 3, 2025 |
| r2c10 | Beginning gross unrecognized tax benefits | 2,865 | UnrecognizedTaxBenefits | c-30: I 2023-04-29 | April 27, 2024 |

#### JPM-10-K-2025-02-14.htm #297 (exported): Loans

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Residential real estate | 106,240 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2190: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r4c10 | Residential real estate | 92,053 | BusinessCombinationAcquiredReceivablesFairValue | c-2190: I 2024-12-31 (dims) | May 1, 2023 — Fair value |
| r5c3 | Auto and other | 3,093 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2191: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r5c9 | Auto and other | 2,030 | BusinessCombinationAcquiredReceivablesFairValue | c-2191: I 2024-12-31 (dims) | May 1, 2023 — Fair value |
| r6c3 | Total consumer | 109,333 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2192: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r6c9 | Total consumer | 94,083 | BusinessCombinationAcquiredReceivablesFairValue | c-2192: I 2024-12-31 (dims) | May 1, 2023 — Fair value |
| r7c3 | Secured by real estate | 37,117 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2193: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r7c9 | Secured by real estate | 33,602 | BusinessCombinationAcquiredReceivablesFairValue | c-2193: I 2024-12-31 (dims) | May 1, 2023 — Fair value |
| r8c3 | Commercial & industrial | 4,332 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2194: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r8c9 | Commercial & industrial | 3,932 | BusinessCombinationAcquiredReceivablesFairValue | c-2194: I 2024-12-31 (dims) | May 1, 2023 — Fair value |
| r9c3 | Other | 23,499 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2195: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r9c9 | Other | 21,625 | BusinessCombinationAcquiredReceivablesFairValue | c-2195: I 2024-12-31 (dims) | May 1, 2023 — Fair value |
| r10c3 | Total wholesale | 64,948 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2196: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r10c9 | Total wholesale | 59,159 | BusinessCombinationAcquiredReceivablesFairValue | c-2196: I 2024-12-31 (dims) | May 1, 2023 — Fair value |
| r11c4 | Total loans | 174,281 | BusinessCombinationAcquiredReceivablesGrossContractualAmount | c-2187: I 2024-12-31 (dims) | May 1, 2023 — UPB |
| r11c10 | Total loans | 153,242 | BusinessCombinationAcquiredReceivablesFairValue | c-2187: I 2024-12-31 (dims) | May 1, 2023 — Fair value |

#### MU-10-K-2025-10-03.htm #22 (exported): Consolidated Statements of Cash Flows

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r38c3 | Cash, cash equivalents, and restricted cash at beg | 7,052 | CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents | c-7: I 2024-08-29 | August 28, 2025 |
| r38c6 | Cash, cash equivalents, and restricted cash at beg | 8,656 | CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents | c-24: I 2023-08-31 | August 29, 2024 |
| r38c9 | Cash, cash equivalents, and restricted cash at beg | 8,339 | CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents | c-13: I 2022-09-01 | August 31, 2023 |

#### NFLX-10-K-2025-01-27.htm #70 (exported): Which $251 million and $188 million, respectively, if recogn

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at the beginning of the year | 327,105 | UnrecognizedTaxBenefits | c-23: I 2023-12-31 | As of December 31, — 2024 |
| r4c7 | Balance at the beginning of the year | 226,977 | UnrecognizedTaxBenefits | c-24: I 2022-12-31 | As of December 31, — 2023 |
| r4c10 | Balance at the beginning of the year | 202,557 | UnrecognizedTaxBenefits | c-25: I 2021-12-31 | As of December 31, — 2022 |

#### NTRA-10-K-2025-02-28.htm #15 (exported): Inventory

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c3 | Beginning balance | 872 | InventoryValuationReserves | As_Of_12_31_2023_o5Hbus7E402n-9NchRlmBg: I 2023-12-31 | December 31, — 2024 |
| r4c6 | Beginning balance | 748 | InventoryValuationReserves | As_Of_12_31_2022_XdrdnLrLekKkPg6SJhnpVA: I 2022-12-31 | December 31, — 2023 |

#### NTRA-10-K-2025-02-28.htm #16 (exported): Accumulated Other Comprehensive Income (Loss)

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c3 | Beginning balance | 3,085 | AccumulatedOtherComprehensiveIncomeLossNetOfTax | As_Of_12_31_2023_o5Hbus7E402n-9NchRlmBg: I 2023-12-31 | December 31, — 2024 |
| r4c6 | Beginning balance | 16,362 | AccumulatedOtherComprehensiveIncomeLossNetOfTax | As_Of_12_31_2022_XdrdnLrLekKkPg6SJhnpVA: I 2022-12-31 | December 31, — 2023 |

#### NTRA-10-K-2025-02-28.htm #21 (exported): The following table shows the changes in the balance of defe

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r5c3 | Beginning balance | 35,740 | ContractWithCustomerLiability | As_Of_12_31_2023_o5Hbus7E402n-9NchRlmBg: I 2023-12-31 | Balance at — December 31, — 2024 |
| r5c6 | Beginning balance | 30,778 | ContractWithCustomerLiability | As_Of_12_31_2022_XdrdnLrLekKkPg6SJhnpVA: I 2022-12-31 | Balance at — December 31, — 2023 |

#### NTRA-10-K-2025-02-28.htm #26 (exported): Allowance for Doubtful Accounts

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c3 | Beginning balance | 6,481 | AllowanceForDoubtfulAccountsReceivable | As_Of_12_31_2023_o5Hbus7E402n-9NchRlmBg: I 2023-12-31 | December 31, — 2024 |
| r4c6 | Beginning balance | 3,830 | AllowanceForDoubtfulAccountsReceivable | As_Of_12_31_2022_XdrdnLrLekKkPg6SJhnpVA: I 2022-12-31 | December 31, — 2023 |
| r4c9 | Beginning balance | 2,429 | AllowanceForDoubtfulAccountsReceivable | As_Of_12_31_2021_h1CgYjsT00i5OSVS0olNZA: I 2021-12-31 | December 31, — 2022 |

#### NTRA-10-K-2025-02-28.htm #30 (exported): Reserve balance and activities for refunds to insurance carr

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c3 | Beginning balance | 23,245 | AccruedInsuranceCurrentAndNoncurrent | As_Of_12_31_2023_o5Hbus7E402n-9NchRlmBg: I 2023-12-31 | December 31, — 2024 |
| r4c6 | Beginning balance | 18,948 | AccruedInsuranceCurrentAndNoncurrent | As_Of_12_31_2022_XdrdnLrLekKkPg6SJhnpVA: I 2022-12-31 | December 31, — 2023 |

#### NTRA-10-K-2025-02-28.htm #42 (exported): A reconciliation of the beginning and ending amount of gross

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c3 | Balance at beginning of year | 30,912 | UnrecognizedTaxBenefits | As_Of_12_31_2023_o5Hbus7E402n-9NchRlmBg: I 2023-12-31 | December 31, — 2024 |
| r4c6 | Balance at beginning of year | 23,844 | UnrecognizedTaxBenefits | As_Of_12_31_2022_XdrdnLrLekKkPg6SJhnpVA: I 2022-12-31 | December 31, — 2023 |
| r4c9 | Balance at beginning of year | 17,514 | UnrecognizedTaxBenefits | As_Of_12_31_2021_h1CgYjsT00i5OSVS0olNZA: I 2021-12-31 | December 31, — 2022 |

#### NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #44 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-10: I 2023-01-29 | Jan 28, 2024 |
| r4c10 | Balance at beginning of period | 502 | ContractWithCustomerLiability | c-27: I 2022-01-30 | Jan 29, 2023 |

#### NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm #53 (exported): A reconciliation of gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,238 | UnrecognizedTaxBenefits | c-10: I 2023-01-29 | Jan 28, 2024 |
| r4c10 | Balance at beginning of period | 1,013 | UnrecognizedTaxBenefits | c-27: I 2022-01-30 | Jan 29, 2023 |
| r4c16 | Balance at beginning of period | 776 | UnrecognizedTaxBenefits | c-16: I 2021-01-31 | Jan 30, 2022 |

#### NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #43 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,337 | ContractWithCustomerLiability | c-14: I 2024-01-28 | Jan 26, 2025 |
| r4c10 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-28: I 2023-01-29 | Jan 28, 2024 |

#### NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm #52 (exported): A reconciliation of gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,670 | UnrecognizedTaxBenefits | c-14: I 2024-01-28 | Jan 26, 2025 |
| r4c10 | Balance at beginning of period | 1,238 | UnrecognizedTaxBenefits | c-28: I 2023-01-29 | Jan 28, 2024 |
| r4c16 | Balance at beginning of period | 1,013 | UnrecognizedTaxBenefits | c-19: I 2022-01-30 | Jan 29, 2023 |

#### NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #39 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,813 | ContractWithCustomerLiability | c-12: I 2025-01-26 | Jan 25, 2026 |
| r4c10 | Balance at beginning of period | 1,337 | ContractWithCustomerLiability | c-26: I 2024-01-28 | Jan 26, 2025 |

#### NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm #49 (exported): A reconciliation of gross unrecognized tax benefits

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 2,861 | UnrecognizedTaxBenefits | c-12: I 2025-01-26 | Jan 25, 2026 |
| r4c10 | Balance at beginning of period | 1,670 | UnrecognizedTaxBenefits | c-26: I 2024-01-28 | Jan 26, 2025 |
| r4c16 | Balance at beginning of period | 1,238 | UnrecognizedTaxBenefits | c-17: I 2023-01-29 | Jan 28, 2024 |

#### NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm #26 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r5c4 | Balance at beginning of period | 572 | ContractWithCustomerLiability | ida5fe7c210a64de8be4c8040e87b0807_I20230129: I 2023-01-29 | April 30, — 2023 |
| r5c10 | Balance at beginning of period | 502 | ContractWithCustomerLiability | ia1cfad7af6c7442ca056c4ab36e7ef10_I20220130: I 2022-01-30 | May 1, — 2022 |

#### NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm #27 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r5c4 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-7: I 2023-01-29 | July 30, — 2023 |
| r5c10 | Balance at beginning of period | 502 | ContractWithCustomerLiability | c-47: I 2022-01-30 | July 31, — 2022 |

#### NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm #27 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r5c4 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-7: I 2023-01-29 | October 29, — 2023 |
| r5c10 | Balance at beginning of period | 502 | ContractWithCustomerLiability | c-47: I 2022-01-30 | October 30, — 2022 |

#### NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #20 (exported): Adjustments to the carrying value of our non-marketable equi

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r3c4 | Balance at beginning of period | 1,321 | EquitySecuritiesWithoutReadilyDeterminableFairValueAmount | c-5: I 2024-01-28 | Apr 28, 2024 |
| r3c10 | Balance at beginning of period | 288 | EquitySecuritiesWithoutReadilyDeterminableFairValueAmount | c-22: I 2023-01-29 | Apr 30, 2023 |

#### NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm #28 (exported): Deferred Revenue

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c4 | Balance at beginning of period | 1,337 | ContractWithCustomerLiability | c-5: I 2024-01-28 | Apr 28, 2024 |
| r4c10 | Balance at beginning of period | 572 | ContractWithCustomerLiability | c-22: I 2023-01-29 | Apr 30, 2023 |

#### TSM-20-F-2025-04-17.htm #135 (exported): Operating loss carryforward

| Source cell | Row label | Fact | Concept | Context | Header |
|---|---|---|---|---|---|
| r4c7 | No expiry date | 640.0 | DeductibleTemporaryDifferencesForWhichNoDeferredTaxAssetIsRecognizedWithoutExpiryDate | PAsOn12_31_2024: I 2024-12-31 | December 31, 2023 — NT$ (In Millions) |
| r4c19 | No expiry date | 11,896.9 | DeductibleTemporaryDifferencesForWhichNoDeferredTaxAssetIsRecognizedWithoutExpiryDate | PAsOn12_31_2023: I 2023-12-31 | December 31, 2024 — NT$ (In Millions) |

### Headers with an unparsed length: 249 headers in 79 tables

A dated header with length wording but no length this script reads. Its facts are not checked for length.

| Filing | Table | Status | Title | Column: header | Verdicts of its facts |
|---|---|---|---|---|---|
| CRM-10-K-2025-03-05.htm | #57 | needs_review | Intangible Assets Acquired Through Business Combinations | 9: Weighted Average Remaining Useful Life (Years) — January 31, 2025 | no facts |
| GOOGL-10-Q-2025-10-30.htm | #18 | exported | The following tables present fair values and gross unrealize | 1: As of December 31, 2024 — Less than 12 Months — Fair Value | {"ok": 4} |
| GOOGL-10-Q-2025-10-30.htm | #18 | exported | The following tables present fair values and gross unrealize | 2: As of December 31, 2024 — Less than 12 Months — Unrealized Loss | {"ok": 4} |
| GOOGL-10-Q-2025-10-30.htm | #18 | exported | The following tables present fair values and gross unrealize | 3: As of December 31, 2024 — 12 Months or Greater — Fair Value | {"ok": 4} |
| GOOGL-10-Q-2025-10-30.htm | #18 | exported | The following tables present fair values and gross unrealize | 4: As of December 31, 2024 — 12 Months or Greater — Unrealized Loss | {"ok": 4} |
| GOOGL-10-Q-2025-10-30.htm | #19 | exported | Government bonds | 1: As of September 30, 2025 — Less than 12 Months — Fair Value | {"ok": 4} |
| GOOGL-10-Q-2025-10-30.htm | #19 | exported | Government bonds | 2: As of September 30, 2025 — Less than 12 Months — Unrealized Loss | {"ok": 4} |
| GOOGL-10-Q-2025-10-30.htm | #19 | exported | Government bonds | 3: As of September 30, 2025 — 12 Months or Greater — Fair Value | {"ok": 4} |
| GOOGL-10-Q-2025-10-30.htm | #19 | exported | Government bonds | 4: As of September 30, 2025 — 12 Months or Greater — Unrealized Loss | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #36 | exported | Available-for-sale marketable debt securities and cash equiv | 1: December 31, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #36 | exported | Available-for-sale marketable debt securities and cash equiv | 2: December 31, 2022 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #36 | exported | Available-for-sale marketable debt securities and cash equiv | 3: December 31, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #36 | exported | Available-for-sale marketable debt securities and cash equiv | 4: December 31, 2022 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #37 | exported | U.S. government securities | 1: December 31, 2021 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #37 | exported | U.S. government securities | 2: December 31, 2021 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #37 | exported | U.S. government securities | 3: December 31, 2021 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2022-FY__c-qudma7zeix2xvhep__s-000132680123000013.htm | #37 | exported | U.S. government securities | 4: December 31, 2021 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #40 | exported | Unrealized Losses | 1: December 31, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #40 | exported | Unrealized Losses | 2: December 31, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #40 | exported | Unrealized Losses | 3: December 31, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #40 | exported | Unrealized Losses | 4: December 31, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #41 | exported | U.S. government securities | 1: December 31, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #41 | exported | U.S. government securities | 2: December 31, 2022 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #41 | exported | U.S. government securities | 3: December 31, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2023-FY__c-7psdw4p4xa53jc3b__s-000132680124000012.htm | #41 | exported | U.S. government securities | 4: December 31, 2022 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #36 | exported | Unrealized Losses | 1: December 31, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #36 | exported | Unrealized Losses | 2: December 31, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #36 | exported | Unrealized Losses | 3: December 31, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #36 | exported | Unrealized Losses | 4: December 31, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #37 | exported | U.S. government securities | 1: December 31, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #37 | exported | U.S. government securities | 2: December 31, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #37 | exported | U.S. government securities | 3: December 31, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2024-FY__c-gt2akrysowoexrow__s-000132680125000017.htm | #37 | exported | U.S. government securities | 4: December 31, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #34 | exported | Marketable Debt Securities | 1: December 31, 2025 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #34 | exported | Marketable Debt Securities | 2: December 31, 2025 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #34 | exported | Marketable Debt Securities | 3: December 31, 2025 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #34 | exported | Marketable Debt Securities | 4: December 31, 2025 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #35 | exported | U.S. government securities | 1: December 31, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #35 | exported | U.S. government securities | 2: December 31, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #35 | exported | U.S. government securities | 3: December 31, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #35 | exported | U.S. government securities | 4: December 31, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2022-Q1__c-hp42umjydbzfcs6z__s-000132680122000057.htm | #16 | exported | Available-for-sale marketable securities with unrealized los | 1: March 31, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2022-Q1__c-hp42umjydbzfcs6z__s-000132680122000057.htm | #16 | exported | Available-for-sale marketable securities with unrealized los | 2: March 31, 2022 — Less than 12 months — Unrealized losses | {"ok": 4} |
| META__10-Q__2022-Q1__c-hp42umjydbzfcs6z__s-000132680122000057.htm | #16 | exported | Available-for-sale marketable securities with unrealized los | 3: March 31, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2022-Q1__c-hp42umjydbzfcs6z__s-000132680122000057.htm | #16 | exported | Available-for-sale marketable securities with unrealized los | 4: March 31, 2022 — 12 months or greater — Unrealized losses | {"ok": 4} |
| META__10-Q__2022-Q2__c-2vkmiqyx4omewh2y__s-000132680122000082.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 1: June 30, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2022-Q2__c-2vkmiqyx4omewh2y__s-000132680122000082.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 2: June 30, 2022 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2022-Q2__c-2vkmiqyx4omewh2y__s-000132680122000082.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 3: June 30, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2022-Q2__c-2vkmiqyx4omewh2y__s-000132680122000082.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 4: June 30, 2022 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2022-Q3__c-55zdcaxviyes6avv__s-000132680122000108.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 1: September 30, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2022-Q3__c-55zdcaxviyes6avv__s-000132680122000108.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 2: September 30, 2022 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2022-Q3__c-55zdcaxviyes6avv__s-000132680122000108.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 3: September 30, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2022-Q3__c-55zdcaxviyes6avv__s-000132680122000108.htm | #16 | exported | Available-for-sale marketable debt securities and cash equiv | 4: September 30, 2022 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 1: March 31, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 2: March 31, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 3: March 31, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 4: March 31, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #22 | exported | U.S. government securities | 1: December 31, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #22 | exported | U.S. government securities | 2: December 31, 2022 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #22 | exported | U.S. government securities | 3: December 31, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q1__c-sgpypwwehekhfm7c__s-000132680123000067.htm | #22 | exported | U.S. government securities | 4: December 31, 2022 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 1: June 30, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 2: June 30, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 3: June 30, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 4: June 30, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #22 | exported | U.S. government securities | 1: December 31, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #22 | exported | U.S. government securities | 2: December 31, 2022 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #22 | exported | U.S. government securities | 3: December 31, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q2__c-x3dxgrb6mkpjefy2__s-000132680123000093.htm | #22 | exported | U.S. government securities | 4: December 31, 2022 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 1: September 30, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 2: September 30, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 3: September 30, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #21 | exported | Unrealized Losses on Marketable Debt Securities | 4: September 30, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #22 | exported | U.S. government securities | 1: December 31, 2022 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #22 | exported | U.S. government securities | 2: December 31, 2022 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #22 | exported | U.S. government securities | 3: December 31, 2022 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2023-Q3__c-zio4utq4iuxrunyf__s-000132680123000103.htm | #22 | exported | U.S. government securities | 4: December 31, 2022 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #19 | exported | Unrealized Losses | 1: March 31, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #19 | exported | Unrealized Losses | 2: March 31, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #19 | exported | Unrealized Losses | 3: March 31, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #19 | exported | Unrealized Losses | 4: March 31, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #20 | exported | U.S. government securities | 1: December 31, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #20 | exported | U.S. government securities | 2: December 31, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #20 | exported | U.S. government securities | 3: December 31, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q1__c-lvgg2eqi74yh4jxf__s-000132680124000049.htm | #20 | exported | U.S. government securities | 4: December 31, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #20 | exported | Unrealized Losses | 1: June 30, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #20 | exported | Unrealized Losses | 2: June 30, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #20 | exported | Unrealized Losses | 3: June 30, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #20 | exported | Unrealized Losses | 4: June 30, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #21 | exported | U.S. government securities | 1: December 31, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #21 | exported | U.S. government securities | 2: December 31, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #21 | exported | U.S. government securities | 3: December 31, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q2__c-2no5lru76vcj4dqx__s-000132680124000069.htm | #21 | exported | U.S. government securities | 4: December 31, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #20 | exported | Unrealized Losses | 1: September 30, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #20 | exported | Unrealized Losses | 2: September 30, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #20 | exported | Unrealized Losses | 3: September 30, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #20 | exported | Unrealized Losses | 4: September 30, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #21 | exported | U.S. government securities | 1: December 31, 2023 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #21 | exported | U.S. government securities | 2: December 31, 2023 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #21 | exported | U.S. government securities | 3: December 31, 2023 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2024-Q3__c-hv5wmqlrjrp4tsdi__s-000132680124000081.htm | #21 | exported | U.S. government securities | 4: December 31, 2023 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #17 | exported | Unrealized Losses | 1: March 31, 2025 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #17 | exported | Unrealized Losses | 2: March 31, 2025 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #17 | exported | Unrealized Losses | 3: March 31, 2025 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #17 | exported | Unrealized Losses | 4: March 31, 2025 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #18 | exported | U.S. government securities | 1: December 31, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #18 | exported | U.S. government securities | 2: December 31, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #18 | exported | U.S. government securities | 3: December 31, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q1__c-3qfr3yyk3dyj55qr__s-000132680125000054.htm | #18 | exported | U.S. government securities | 4: December 31, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #17 | exported | Marketable debt securities | 1: June 30, 2025 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #17 | exported | Marketable debt securities | 2: June 30, 2025 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #17 | exported | Marketable debt securities | 3: June 30, 2025 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #17 | exported | Marketable debt securities | 4: June 30, 2025 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #18 | exported | U.S. government securities | 1: December 31, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #18 | exported | U.S. government securities | 2: December 31, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #18 | exported | U.S. government securities | 3: December 31, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q2__c-3xx6wmf22ktxqfpq__s-000162828025036791.htm | #18 | exported | U.S. government securities | 4: December 31, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #17 | exported | Marketable Debt Securities | 1: September 30, 2025 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #17 | exported | Marketable Debt Securities | 2: September 30, 2025 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #17 | exported | Marketable Debt Securities | 3: September 30, 2025 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #17 | exported | Marketable Debt Securities | 4: September 30, 2025 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #18 | exported | U.S. government securities | 1: December 31, 2024 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #18 | exported | U.S. government securities | 2: December 31, 2024 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #18 | exported | U.S. government securities | 3: December 31, 2024 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2025-Q3__c-atqnmlwm2cpcuof2__s-000162828025047240.htm | #18 | exported | U.S. government securities | 4: December 31, 2024 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #17 | exported | Marketable Debt Securities | 1: March 31, 2026 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #17 | exported | Marketable Debt Securities | 2: March 31, 2026 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #17 | exported | Marketable Debt Securities | 3: March 31, 2026 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #17 | exported | Marketable Debt Securities | 4: March 31, 2026 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #18 | exported | U.S. government securities | 1: December 31, 2025 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #18 | exported | U.S. government securities | 2: December 31, 2025 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #18 | exported | U.S. government securities | 3: December 31, 2025 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q1__c-zkgjn5w7rlv3zs2i__s-000162828026028526.htm | #18 | exported | U.S. government securities | 4: December 31, 2025 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #17 | exported | Marketable Debt Securities | 1: June 30, 2026 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #17 | exported | Marketable Debt Securities | 2: June 30, 2026 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #17 | exported | Marketable Debt Securities | 3: June 30, 2026 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #17 | exported | Marketable Debt Securities | 4: June 30, 2026 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #18 | exported | U.S. government securities | 1: December 31, 2025 — Less than 12 months — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #18 | exported | U.S. government securities | 2: December 31, 2025 — Less than 12 months — Unrealized Losses | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #18 | exported | U.S. government securities | 3: December 31, 2025 — 12 months or greater — Fair Value | {"ok": 4} |
| META__10-Q__2026-Q2__c-wcyphwqbtmry35h3__s-000162828026050705.htm | #18 | exported | U.S. government securities | 4: December 31, 2025 — 12 months or greater — Unrealized Losses | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 1: Jan 28, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 2: Jan 28, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 3: Jan 28, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 4: Jan 28, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 1: Jan 29, 2023 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 2: Jan 29, 2023 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 3: Jan 29, 2023 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 4: Jan 29, 2023 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 1: Jan 26, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 2: Jan 26, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 3: Jan 26, 2025 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 4: Jan 26, 2025 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 2} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #33 | exported | The following tables provide the breakdown of unrealized los | 5: Jan 26, 2025 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 2} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 1: Jan 28, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 2: Jan 28, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 3: Jan 28, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #34 | exported | Debt securities issued by the U.S. Treasury | 4: Jan 28, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #32 | exported | The following tables provide the breakdown of unrealized los | 1: Jan 25, 2026 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #32 | exported | The following tables provide the breakdown of unrealized los | 2: Jan 25, 2026 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #32 | exported | The following tables provide the breakdown of unrealized los | 3: Jan 26, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #32 | exported | The following tables provide the breakdown of unrealized los | 4: Jan 26, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 1: April 30, 2023 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 2: April 30, 2023 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 3: April 30, 2023 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 4: April 30, 2023 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 1: January 29, 2023 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 2: January 29, 2023 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 3: January 29, 2023 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 4: January 29, 2023 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 1: July 30, 2023 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 2: July 30, 2023 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 3: July 30, 2023 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 4: July 30, 2023 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 1: January 29, 2023 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 2: January 29, 2023 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 3: January 29, 2023 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 4: January 29, 2023 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 1: October 29, 2023 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 2: October 29, 2023 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 3: October 29, 2023 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 4: October 29, 2023 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 1: January 29, 2023 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 2: January 29, 2023 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 3: January 29, 2023 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 4: January 29, 2023 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 1: Apr 28, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 2: Apr 28, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 3: Apr 28, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #16 | exported | The following tables provide the breakdown of unrealized los | 4: Apr 28, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 1: Jan 28, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 2: Jan 28, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 3: Jan 28, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #17 | exported | Debt securities issued by the U.S. Treasury | 4: Jan 28, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 1: Jul 28, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 2: Jul 28, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 3: Jul 28, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 4: Jul 28, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 1: Jan 28, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 2: Jan 28, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 3: Jan 28, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 4: Jan 28, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 1: Oct 27, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 2: Oct 27, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 3: Oct 27, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 4: Oct 27, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 2} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #17 | exported | The following tables provide the breakdown of unrealized los | 5: Oct 27, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 2} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 1: Jan 28, 2024 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 2: Jan 28, 2024 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 3: Jan 28, 2024 — 12 Months or Greater — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #18 | exported | Debt securities issued by the U.S. Treasury | 4: Jan 28, 2024 — 12 Months or Greater — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #14 | exported | The following table provides the breakdown of unrealized los | 1: Apr 27, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #14 | exported | The following table provides the breakdown of unrealized los | 2: Apr 27, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #14 | exported | The following table provides the breakdown of unrealized los | 3: Jan 26, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #14 | exported | The following table provides the breakdown of unrealized los | 4: Jan 26, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #15 | exported | The following table provides the breakdown of unrealized los | 1: Jul 27, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #15 | exported | The following table provides the breakdown of unrealized los | 2: Jul 27, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #15 | exported | The following table provides the breakdown of unrealized los | 3: Jan 26, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #15 | exported | The following table provides the breakdown of unrealized los | 4: Jan 26, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #15 | exported | The following table provides the breakdown of unrealized los | 1: Oct 26, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #15 | exported | The following table provides the breakdown of unrealized los | 2: Oct 26, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #15 | exported | The following table provides the breakdown of unrealized los | 3: Jan 26, 2025 — Less than 12 Months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #15 | exported | The following table provides the breakdown of unrealized los | 4: Jan 26, 2025 — Less than 12 Months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #16 | exported | The following table provides the breakdown of unrealized los | 1: Apr 26, 2026 — Less than 12 months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #16 | exported | The following table provides the breakdown of unrealized los | 2: Apr 26, 2026 — Less than 12 months — Gross Unrealized Loss | {"ok": 4} |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #16 | exported | The following table provides the breakdown of unrealized los | 3: Jan 25, 2026 — Less than 12 months — Estimated Fair Value | {"ok": 4} |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #16 | exported | The following table provides the breakdown of unrealized los | 4: Jan 25, 2026 — Less than 12 months — Gross Unrealized Loss | {"ok": 4} |
| RDDT__10-K__2024-FY__c-jizatrb5fs63nvbv__s-000171344525000018.htm | #45 | exported | Acquired Intangible Assets | 4: December 31, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-K__2024-FY__c-jizatrb5fs63nvbv__s-000171344525000018.htm | #46 | exported | Developed technology | 4: December 31, 2023 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-K__2025-FY__c-xecnnfbwds7otmem__s-000171344526000022.htm | #45 | exported | Acquired Intangible Assets | 4: December 31, 2025 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-K__2025-FY__c-xecnnfbwds7otmem__s-000171344526000022.htm | #46 | exported | Developed technology | 4: December 31, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2024-Q1__c-rppl6yjihp5tdslx__s-000171344524000006.htm | #21 | exported | Acquired Intangible Assets | 4: March 31, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2024-Q1__c-rppl6yjihp5tdslx__s-000171344524000006.htm | #22 | exported | Developed technology | 4: December 31, 2023 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2024-Q2__c-63xzxqtyzzhgyhto__s-000171344524000054.htm | #21 | exported | Acquired Intangible Assets | 4: June 30, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2024-Q2__c-63xzxqtyzzhgyhto__s-000171344524000054.htm | #22 | exported | Developed technology | 4: December 31, 2023 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2024-Q3__c-y2v6ctuwvsqookfm__s-000171344524000102.htm | #21 | exported | Acquired Intangible Assets | 4: September 30, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2024-Q3__c-y2v6ctuwvsqookfm__s-000171344524000102.htm | #22 | exported | Developed technology | 4: December 31, 2023 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2025-Q1__c-ereuzoyn3bclk6pt__s-000171344525000102.htm | #20 | exported | Acquired Intangible Assets | 4: March 31, 2025 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2025-Q1__c-ereuzoyn3bclk6pt__s-000171344525000102.htm | #21 | exported | Developed technology | 4: December 31, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2025-Q2__c-n5ue5krjop4imyfk__s-000171344525000196.htm | #21 | exported | Acquired Intangible Assets | 4: June 30, 2025 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2025-Q2__c-n5ue5krjop4imyfk__s-000171344525000196.htm | #22 | exported | Developed technology | 4: December 31, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2025-Q3__c-652ssjo5fazn2uiw__s-000171344525000227.htm | #21 | exported | Acquired Intangible Assets | 4: September 30, 2025 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2025-Q3__c-652ssjo5fazn2uiw__s-000171344525000227.htm | #22 | exported | Developed technology | 4: December 31, 2024 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2026-Q1__c-ns7p5ojalqy3dz5m__s-000171344526000069.htm | #18 | exported | Acquired Intangible Assets | 4: March 31, 2026 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2026-Q1__c-ns7p5ojalqy3dz5m__s-000171344526000069.htm | #19 | exported | Developed technology | 4: December 31, 2025 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2026-Q2__c-lttii6wghloh2qqx__s-000171344526000100.htm | #19 | exported | Acquired Intangible Assets | 4: June 30, 2026 — Weighted-average remaining useful life (years) | no facts |
| RDDT__10-Q__2026-Q2__c-lttii6wghloh2qqx__s-000171344526000100.htm | #20 | exported | Developed technology | 4: December 31, 2025 — Weighted-average remaining useful life (years) | no facts |
| SPCX-10-Q-2026-08-04.htm | #21 | needs_review | Intangible Assets | 1: June 30, 2026 — Weighted-Average Useful Life (years) | no facts |
| SPCX-10-Q-2026-08-04.htm | #22 | needs_review | Brand | 1: December 31, 2025 — Weighted-Average Useful Life (in years) | no facts |

### Yearless period headers: 112 tables

| Filing | Table | Status | Title | Headers (column: header) |
|---|---|---|---|---|
| BABA-20-F-2025-06-26.htm | #23 | needs_review | ALIBABA GROUP HOLDING LIMITED | 3: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #33 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #37 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: Year ended March 31,; 4: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #41 | needs_review | Composition of income tax expenses | 2: Year ended March 31,; 4: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #50 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: Year ended March 31,; 4: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #61 | needs_review | For the years ended March 31, 2023, 2024 and 2025, equity me | 3: Year ended March 31, |
| BABA-20-F-2025-06-26.htm | #63 | needs_review | Building, property improvements and other property | 2: As of March 31, |
| BABA-20-F-2025-06-26.htm | #64 | needs_review | User base and customer relationships | 2: As of March 31, |
| BABA-20-F-2025-06-26.htm | #67 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: As of March 31, |
| BABA-20-F-2025-06-26.htm | #73 | needs_review | ALIBABA GROUP HOLDING LIMITED NOTES TO CONSOLIDATED FINANCIA | 2: As of March 31, |
| BABA-20-F-2025-06-26.htm | #81 | needs_review | Condensed Balance Sheets | 2: As of March 31, |
| CRDO-10-K-2025-07-02.htm | #26 | needs_review | Revenue | 1: Year Ended; 2: Year Ended; 3: Year Ended; 4: Year Ended |
| CRM-10-K-2025-03-05.htm | #10 | needs_review | Cost of revenues | 2: Fiscal Year Ended January 31, — % of Total Revenues; 4: Fiscal Year Ended January 31, — % of Total Revenues; 6: Fiscal Year Ended January 31, — % of Total Revenues |
| CRM-10-K-2025-03-05.htm | #11 | needs_review | Cost of revenues | 2: Fiscal Year Ended January 31, — % of Total Revenues; 4: Fiscal Year Ended January 31, — % of Total Revenues; 6: Fiscal Year Ended January 31, — % of Total Revenues |
| CRM-10-K-2025-03-05.htm | #14 | needs_review | Subscription and Support Revenues by Service Offering | 2: Fiscal Year Ended January 31, — As a % of Total Subscription and Support Revenues; 4: Fiscal Year Ended January 31, — As a % of Total Subscription and Support Revenues |
| CRM-10-K-2025-03-05.htm | #15 | needs_review | Americas | 2: Fiscal Year Ended January 31, — As a % of Total Revenues; 4: Fiscal Year Ended January 31, — As a % of Total Revenues; 5: Fiscal Year Ended January 31, — Growth Rate |
| CRM-10-K-2025-03-05.htm | #16 | needs_review | Cost of Revenues | 2: Fiscal Year Ended January 31, — As a % of Total Revenues; 4: Fiscal Year Ended January 31, — As a % of Total Revenues |
| CRM-10-K-2025-03-05.htm | #17 | needs_review | Operating Expenses | 2: Fiscal Year Ended January 31, — As a % of Total Revenues; 4: Fiscal Year Ended January 31, — As a % of Total Revenues |
| JPM-10-K-2025-02-14.htm | #32 | exported | Non-GAAP financial measures | 0: Year ended December 31, (in millions, except ratios) |
| JPM-10-K-2025-02-14.htm | #65 | exported | Three months ended (in millions, except ratios) | 0: Three months ended (in millions, except ratios) |
| JPM-10-K-2025-02-14.htm | #69 | exported | Supplementary leverage ratio | 0: Three months ended (in millions, except ratio) |
| JPM-10-K-2025-02-14.htm | #113 | exported | Allocation of allowance for loan losses | 0: December 31, (in millions, except ratios) |
| JPM-10-K-2025-02-14.htm | #117 | needs_review | Management’s discussion and analysis | 0: December 31, (in billions) |
| JPM-10-K-2025-02-14.htm | #148 | exported | Difference between aggregate fair value and aggregate remain | 0: December 31, (in millions) |
| JPM-10-K-2025-02-14.htm | #150 | exported | Notes to consolidated financial statements | 0: December 31, (in millions) |
| JPM-10-K-2025-02-14.htm | #183 | exported | Notes to consolidated financial statements | 0: December 31, (in millions) |
| JPM-10-K-2025-02-14.htm | #243 | exported | Securitization activity | 0: Year ended December 31, (in millions) |
| JPM-10-K-2025-02-14.htm | #266 | needs_review | Note 21 – Preferred stock | 10: Dividend declared per share(d) — Year ended December 31,; 12: Dividend declared per share(d) — Year ended December 31, |
| JPM-10-K-2025-02-14.htm | #271 | exported | Year ended December 31, (in millions) | 0: Year ended December 31, (in millions) |
| JPM-10-K-2025-02-14.htm | #283 | exported | Three months ended (in millions, except ratios) | 0: Three months ended (in millions, except ratios) |
| JPM-10-K-2025-02-14.htm | #285 | exported | Standby letters of credit, other financial guarantees and ot | 0: December 31, (in millions) |
| META__10-K__2025-FY__c-24uhjfkfhood6sjj__s-000162828026003942.htm | #57 | exported | U.S. federal statutory income tax rate | 1: Year Ended December 31, |
| MU-10-K-2025-10-03.htm | #18 | exported | Consolidated Statements of Operations | 0: For the year ended |
| MU-10-K-2025-10-03.htm | #19 | exported | Consolidated Statements of Comprehensive Income (Loss) | 0: For the year ended |
| MU-10-K-2025-10-03.htm | #20 | exported | Consolidated Balance Sheets | 0: As of |
| MU-10-K-2025-10-03.htm | #22 | exported | Consolidated Statements of Cash Flows | 0: For the year ended |
| MU-10-K-2025-10-03.htm | #24 | exported | Note 6. Receivables | 0: As of |
| MU-10-K-2025-10-03.htm | #25 | exported | Note 7. Inventories | 0: As of |
| MU-10-K-2025-10-03.htm | #26 | exported | Note 8. Property, Plant, and Equipment | 0: As of |
| MU-10-K-2025-10-03.htm | #29 | exported | Supplemental balance sheet information related to leases was | 0: As of |
| MU-10-K-2025-10-03.htm | #32 | exported | Note 11. Accounts Payable and Accrued Expenses | 0: As of |
| MU-10-K-2025-10-03.htm | #52 | exported | Deferred income taxes reflect the net tax effects of tempora | 0: As of |
| MU-10-K-2025-10-03.htm | #64 | exported | Long-lived assets by geographic area | 0: As of |
| NTRA-10-K-2025-02-28.htm | #33 | needs_review | Contractual Commitments | 3: Year Ended December 31,; 4: Year Ended December 31,; 5: Year Ended December 31,; 6: Year Ended December 31,; 7: Year Ended December 31,; 8: Year Ended December 31,; 9: Year Ended December 31,; 10: Year Ended December 31,; 11: Year Ended December 31, |
| NTRA-10-K-2025-02-28.htm | #36 | needs_review | Valuation of Stock Option Grants | 3: Year ended December 31,; 7: Year ended December 31,; 11: Year ended December 31, |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #7 | needs_review | Fiscal Year 2024 Summary | 3: Year Ended — Change |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #9 | needs_review | Revenue by Reportable Segments | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #10 | needs_review | Operating Income by Reportable Segments | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #11 | needs_review | Operating Expenses | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2024-FY__c-lsdf2sig3j55ukq6__s-000104581024000029.htm | #12 | exported | Other Income (Expense), Net | 3: Year Ended — $ Change |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #7 | needs_review | Fiscal Year 2025 Summary | 3: Year Ended — Change |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #9 | needs_review | Revenue by Reportable Segments | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #10 | needs_review | Operating Income by Reportable Segments | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #12 | exported | Operating Expenses | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #13 | exported | Other Income (Expense), Net | 3: Year Ended — $ Change |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #7 | needs_review | Fiscal Year 2026 Summary | 3: Year Ended — Change |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #9 | needs_review | Revenue by Reportable Segments | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #10 | needs_review | Operating Income by Reportable Segments | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #11 | needs_review | Operating Expenses | 3: Year Ended — $ Change; 4: Year Ended — % Change |
| NVDA__10-K__2026-FY__c-ibembbpzdct6pow5__s-000104581026000021.htm | #12 | exported | Total Other Income, Net | 3: Year Ended — $ Change |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #37 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #38 | exported | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 5: Three Months Ended — % Change |
| NVDA__10-Q__2024-Q1__c-xae25irrvojjyzda__s-000104581023000093.htm | #39 | needs_review | Other Income (Expense), Net | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #38 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #39 | needs_review | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #40 | needs_review | Operating income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2024-Q2__c-irkqnfoquwhngml5__s-000104581023000175.htm | #41 | exported | Other Income (Expense), Net | 3: Three Months Ended — $ Change; 6: Six Months Ended — $ Change |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #38 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #39 | needs_review | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #40 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change; 9: Nine Months Ended — % Change |
| NVDA__10-Q__2024-Q3__c-x7j2se5j2y4gp7ca__s-000104581023000227.htm | #41 | exported | Other Income (Expense), Net | 3: Three Months Ended — $ Change; 6: Nine Months Ended — $ Change |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #40 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #41 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #42 | exported | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2025-Q1__c-t3zpon6mrpse7sws__s-000104581024000124.htm | #43 | exported | Other Income (Expense), Net | 3: Three Months Ended — $ Change |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #40 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #41 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #43 | exported | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #44 | exported | Other Income (Expense), Net | 3: Three Months Ended — $ Change; 6: Six Months Ended — $ Change |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #40 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #41 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #43 | exported | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #44 | exported | Other Income (Expense), Net | 3: Three Months Ended — $ Change; 6: Nine Months Ended — $ Change |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #37 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #38 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #39 | needs_review | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2026-Q1__c-qowiwgnnxwisj5be__s-000104581025000116.htm | #40 | exported | Total Other Income (Expense), Net | 3: Three Months Ended — $ Change |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #37 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #38 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #39 | needs_review | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2026-Q2__c-dgs2y5e5dqxiudyi__s-000104581025000209.htm | #40 | exported | Total Other Income (Expense), Net | 3: Three Months Ended — $ Change; 6: Six Months Ended — $ Change |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #36 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #37 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #38 | needs_review | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Nine Months Ended — $ Change; 8: Nine Months Ended — % Change |
| NVDA__10-Q__2026-Q3__c-dzi6ydfpysxt6noj__s-000104581025000230.htm | #39 | exported | Total Other Income, Net | 3: Three Months Ended — $ Change; 6: Nine Months Ended — $ Change |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #35 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #36 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #37 | needs_review | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change |
| NVDA__10-Q__2027-Q1__c-3djqairkgthxrvbo__s-000104581026000052.htm | #38 | exported | Total Other Income, Net | 3: Three Months Ended — $ Change |
| NVDA__10-Q__2027-Q2__c-3tn25vuxcduzrmbl__s-000104581026000075.htm | #38 | needs_review | Revenue by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2027-Q2__c-3tn25vuxcduzrmbl__s-000104581026000075.htm | #39 | needs_review | Operating Income by Reportable Segments | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2027-Q2__c-3tn25vuxcduzrmbl__s-000104581026000075.htm | #40 | needs_review | Operating Expenses | 3: Three Months Ended — $ Change; 4: Three Months Ended — % Change; 7: Six Months Ended — $ Change; 8: Six Months Ended — % Change |
| NVDA__10-Q__2027-Q2__c-3tn25vuxcduzrmbl__s-000104581026000075.htm | #41 | exported | Other Income, Net | 3: Three Months Ended — $ Change; 6: Six Months Ended — $ Change |
| SPCX-10-Q-2026-08-04.htm | #47 | needs_review | Space | 1: Three Months Ended; 2: Three Months Ended; 3: Six Months Ended; 4: Six Months Ended |
| SPCX-10-Q-2026-08-04.htm | #48 | needs_review | (number) | 1: Three Months Ended; 2: Three Months Ended; 3: Six Months Ended; 4: Six Months Ended |
| SPCX-10-Q-2026-08-04.htm | #50 | needs_review | (dollars per month) | 1: Three Months Ended; 2: Three Months Ended; 3: Six Months Ended; 4: Six Months Ended |
| TSM-20-F-2025-04-17.htm | #8 | needs_review | Results of Operations | 2: For the year ended December 31,; 4: For the year ended December 31, |
| TSM-20-F-2025-04-17.htm | #9 | needs_review | Net Revenue and Gross Margin | 2: For the year ended December 31,; 4: For the year ended December 31,; 6: For the year ended December 31,; 12: For the year ended December 31, |
| TSM-20-F-2025-04-17.htm | #10 | needs_review | Operating Expenses | 2: For the year ended December 31,; 5: For the year ended December 31,; 11: For the year ended December 31, |
| TSM-20-F-2025-04-17.htm | #11 | needs_review | Non-Operating Income and Expenses | 4: For the year ended December 31, |
| TSM-20-F-2025-04-17.htm | #12 | needs_review | Income Tax Expense | 2: For the year ended December 31,; 4: For the year ended December 31,; 6: For the year ended December 31,; 12: For the year ended December 31, |
| TSM-20-F-2025-04-17.htm | #99 | needs_review | Amounts recognized in respect of these defined benefit plans | 3: Years Ended December 31 |

### Tables with numeric-fact cells but no located facts: 7

| Filing | Table | Status | Provenance | Title | Fact cells |
|---|---|---|---|---|---|
| CRM-10-K-2025-03-05.htm | #69 | exported | ambiguous | Share Repurchase Program | 9 |
| CRM-10-K-2025-03-05.htm | #70 | exported | ambiguous | Dividends | 8 |
| GOOGL-10-Q-2025-10-30.htm | #13 | exported | ambiguous | Disaggregated Revenues | 40 |
| GOOGL-10-Q-2025-10-30.htm | #48 | exported | ambiguous | Note 14. Income Taxes | 12 |
| NVDA__10-K__2025-FY__c-cte5uccwn7g3koei__s-000104581025000023.htm | #56 | exported | ambiguous | Sales to direct customers which represented 10% or more of t | 4 |
| NVDA__10-Q__2025-Q2__c-muejjuczkhwwdcbq__s-000104581024000264.htm | #36 | exported | ambiguous | Sales to direct customers which represented 10% or more of t | 7 |
| NVDA__10-Q__2025-Q3__c-y46t24gordm6uizt__s-000104581024000316.htm | #36 | exported | ambiguous | Sales to direct customers which represented 10% or more of t | 6 |
