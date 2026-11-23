# data/pelm/

Holds `pelm_monthly.csv` — month-end valuations for the P E L Molyneaux Will Trust (account
`C070982`, Barratt & Cooke). The CSV is gitignored (personal financial data); this README is
tracked so the folder exists in a fresh clone and on the server.

| Column | Meaning |
|---|---|
| `month_end_date` | Valuation date as supplied (last working day is fine; mapped to the calendar month-end) |
| `value_gbp` | Total market value |
| `external_flow_gbp` | Money in (+) / out (−) that month, excluding trades. Blank if none |

Example layout: [`../examples/pelm_monthly_example.csv`](../examples/pelm_monthly_example.csv).
dbt reads this file during `dbt build`; if it is missing, PELM is simply absent from the
dashboard. Update steps: see the README's "Updating PELM Will Trust data" section.
