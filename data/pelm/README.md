# data/pelm/

Holds two gitignored CSVs. `pelm_monthly.csv` — month-end valuations for the P E L Molyneaux Will Trust (account
`C070982`, Barratt & Cooke). The CSV is gitignored (personal financial data); this README is
tracked so the folder exists in a fresh clone and on the server.

| Column | Meaning |
|---|---|
| `month_end_date` | Valuation date as supplied (last working day is fine; mapped to the calendar month-end) |
| `value_gbp` | Total market value |
| `external_flow_gbp` | Money in (+) / out (−) that month, excluding trades. Blank if none |

Example layout: [`../examples/pelm_monthly_example.csv`](../examples/pelm_monthly_example.csv).

`pelm_transactions.csv` — the ledger (trades, transfers, withdrawals), generated from the ledger PDF by
`uv run python backend/scripts/parse_pelm_ledger.py` (on the server:
`docker compose exec cron /app/.venv/bin/python backend/scripts/parse_pelm_ledger.py`, with the PDF saved
here as `C070982 Ledger statements.pdf`). The script refuses to write unless the ledger
balances, and checks its external flows against `pelm_monthly.csv`. Example layout:
[`../examples/pelm_transactions_example.csv`](../examples/pelm_transactions_example.csv).
dbt reads these files during `dbt build`; if one is missing, that part of PELM is simply absent from the
dashboard. Update steps: see the README's "Updating PELM Will Trust data" section.
