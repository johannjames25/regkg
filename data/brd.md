# BRD: Large Exposures Report (LE-1), Release 1

## Glossary
- CBS: Core Banking System, holding loan accounts, deposits and liens.
- CRM: Customer Relationship Management system, holding the customer master.
- TF: Trade Finance system.
- CAR return: the capital adequacy return submitted to the Authority.
- PAN: Permanent Account Number, the tax identifier of a customer.
- GL: General Ledger.
- LE-1: the Authority's prescribed large exposures template.

## Requirements
BR-01 Frequency and submission: The LE-1 report shall be generated quarterly and submitted through the Authority's reporting portal no later than T+12 business days after quarter end.
BR-02 Funded exposure: Funded exposure per customer shall be the sum of OUTSTANDING_BAL and ACCR_INT from CBS table LN_ACCT_DAILY as of the quarter-end date.
BR-03 Non-funded exposure: Non-funded exposure shall be computed as SANCTION_LIMIT from TF table TF_CONTINGENT multiplied by the CCF, where the CCF is taken from the CCF master in Credit Risk Policy v4.2, Annexure 3.
BR-04 Grouping of counterparties: Counterparties shall be grouped using the GROUP_ID field in the CRM customer master. Where GROUP_ID is null, customers sharing the same PAN or the same registered address shall be treated as a group of connected counterparties.
BR-05 Eligible capital base: The eligible capital base shall be the Tier 1 capital figure from the CAR return for the same reporting quarter.
BR-06 Reporting threshold: The report shall include every counterparty or group with total exposure equal to or above 10 percent of the eligible capital base, and additionally the 20 largest exposures.
BR-07 Exempt exposures: Exposures to customers with SECTOR_CODE 101 or 102 shall be flagged as exempt and included in the report.
BR-08 Collateral: Exposure shall be reduced by cash collateral held under lien in the CBS lien module. Government securities collateral is not considered in this release.
BR-09 Interbank exposures: Interbank placements from the Murex treasury system shall be included. Intraday placements shall be excluded where SETTLE_DATE equals MATURITY_DATE.
BR-10 Output format: Amounts shall be reported in INR lakhs, rounded to two decimals, in the LE-1 layout.
BR-11 Reconciliation: Total funded exposure shall reconcile to GL heads 1101-1199 within a tolerance of 0.5 percent.
