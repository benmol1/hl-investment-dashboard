# pelm-inputs

Drop folder for the raw quarterly pack from Barratt & Cooke for the P E L Molyneaux Will Trust
(account `C070982`). Contents are **not committed**: these are third-party financial
statements. Only this file and `.gitignore` are tracked. Keep each pack in a dated subfolder
(e.g. `20261127/`).

Files in a pack:

| File | What it is | Used for |
|---|---|---|
| `C070982 End of Month Valuations.xlsx` | Two columns: month-end date, total market value (full history each time) | New months appended to `data/pelm/pelm_monthly.csv` |
| `C070982 Ledgers to <date>.pdf` (first pack: `C070982 Ledger statements.pdf`) | One statement per sub-ledger: capital (trades, sweeps, withdrawals), dividends and claims (dividends, FX commission, BACS income payments), income account (interest), fees (custody fee + VAT) | Parsed by `parse_pelm_ledger.py`: transactions, income, fees, external cash flows |
| `C070982 Formal total-return performance report to <date>.xlsx` | B&C's daily total-return calculation for the quarter; the header line gives the quarter's return | Header figure typed into `data/pelm/pelm_reported_returns.csv` |
| `C070982 Tax Cert to <date>.pdf` | Consolidated tax report: income by payment date, gross / withholding tax | Not parsed; a cross-check on the dividends ledger |
| `C070982 Breakdown <years>.pdf` | Per-transaction charges and fund OCF rates | Not used; kept for reference |

**On arrival:** follow the README's "Updating PELM Will Trust data" section. Full design:
[docs/pelm-integration-plan.md](../docs/pelm-integration-plan.md).
