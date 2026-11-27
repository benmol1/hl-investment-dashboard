# data/pelm/

Files for the P E L Molyneaux Will Trust (account `C070982`, Barratt & Cooke). The CSVs and PDFs
are gitignored (personal financial data); this README is tracked so the folder exists in a fresh
clone and on the server. dbt reads the CSVs during `dbt build`; if one is missing, that part of
PELM is simply absent from the dashboard. Update steps: the README's "Updating PELM Will Trust
data" section.

| File | Written by | Columns |
|---|---|---|
| `pelm_monthly.csv` | Hand, from `C070982 End of Month Valuations.xlsx` | `month_end_date` (last working day is fine; mapped to the calendar month-end), `value_gbp` |
| `pelm_reported_returns.csv` | Hand, from each formal total-return performance report's header line | `period_start`, `period_end`, `return_pct` (4.48 = 4.48%), `source` |
| `pelm_transactions.csv` | `parse_pelm_ledger.py` | `ledger`, `tx_date`, `reference`, `tx_type`, `security`, `quantity`, `amount_gbp`, `notes` |
| `pelm_ledger_coverage.csv` | `parse_pelm_ledger.py` | `ledger`, `period_start`, `period_end`, `opening_gbp`, `closing_gbp`, `source_file` |

The ledger PDFs (`C070982 Ledger*.pdf`) can sit here or in dated subfolders. The parser reads all
of them:

    uv run python backend/scripts/parse_pelm_ledger.py
    # on the server:
    docker compose exec cron /app/.venv/bin/python backend/scripts/parse_pelm_ledger.py

It refuses to write unless every statement balances. External cash flows (money in, capital
withdrawals, BACS income payments to the beneficiary) come from the ledger, so they are no longer
typed into `pelm_monthly.csv`. An older `pelm_monthly.csv` with a third `external_flow_gbp`
column still loads; the column is ignored.

Example layouts are in [`../examples/`](../examples/).
