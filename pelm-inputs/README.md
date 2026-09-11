# pelm-inputs

Drop folder for the raw quarterly pack from Barratt & Cooke for the P E L Molyneaux Will
Trust (account `C070982`). Contents are **not committed** — these are third-party financial
statements. Only this file and `.gitignore` are tracked.

Expected files, as sent by email roughly every 3 months:

| File | What it is | Used for |
|---|---|---|
| `C070982 End of Month Valuations.xlsx` | Two columns: month-end date, total market value | The only file that feeds the dashboard |
| `C070982 Ledger statements.pdf` | Cash ledger — trades, transfers in/out, withdrawals | Read by hand for external cash flows |
| `C070982 Breakdown <years>.pdf` | Per-transaction charges and fund OCF rates | Not used; kept for reference |

**On arrival:** save the attachments here, then append the new months to
`data/imports/pelm_monthly.csv`, adding any withdrawal or transfer found in the ledger.
Full process in [docs/pelm-integration-plan.md](../docs/pelm-integration-plan.md) §4.
