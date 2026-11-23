# Example import files

Anonymised samples showing the format of the files you must supply yourself.
The real files are gitignored because they contain personal financial data.

| Example | Copy to | Notes |
|---|---|---|
| `funds.csv` | `data/imports/funds.csv` | Required. Read by `setup_db.py`. |
| `ISA_example.csv` | `data/imports/raw_transactions/ISA/` | HL transaction export format |
| `SIPP_example.csv` | `data/imports/raw_transactions/SIPP/` | Same format as ISA |

## funds.csv

One row per fund you hold (or held).

- `fund_ISIN` — becomes the fund ID. Use `No_ISIN` or blank if none (an ID is generated from the name).
- `fund_code` — Morningstar code (e.g. `0P0000SVHO`); `fetch_prices.py` uses it to get prices. Find it in the URL of the fund's page on morningstar.co.uk.
- `fund_name` — **must match the fund name in HL transaction descriptions exactly** (case/whitespace-insensitive), i.e. the text before `(GBP)`. Otherwise transactions won't link to the fund.
- `short_name` — optional label used in the Telegram monthly summary.
- Rows with a blank name, `??` as the ISIN, or the name `Not a fund` are skipped.

Re-run `setup_db.py` after editing; it is safe to repeat.

## Transaction CSVs

Normally downloaded by `download_transactions.py` or exported from HL. Format: 5 metadata lines, then the header row, then data rows. Dates are `DD/MM/YYYY`; `Quantity` is always positive and direction comes from the sign of `Value (£)`. The `Reference` prefix determines the type (`B…` buy, `S…` sell, `BX…`/`X…` switch in/out, `Card Web`/`FPC` contribution, `REG. SAVER`, `MANAGE FEE`, `INTEREST`, `Transfer`/`BACS`, `URIB…` rebate). Files are renamed to `{ACCOUNT}_{YYYY-MM-DD}.csv` on ingest; duplicates are skipped.

## `pelm_monthly_example.csv`

Layout for the PELM Will Trust valuations file, which lives at `data/pelm/pelm_monthly.csv` (gitignored). Columns: `month_end_date`, `value_gbp`, `external_flow_gbp` — the flow is positive for money in, negative for money out, blank if none. dbt reads it during `dbt build` (run from the `dbt/` directory); there is no seed step. See [docs/pelm-integration-plan.md](../../docs/pelm-integration-plan.md).

## `pelm_transactions_example.csv`

Layout of `data/pelm/pelm_transactions.csv` (gitignored), which is generated — not hand-written — by `backend/scripts/parse_pelm_ledger.py` from the Barratt & Cooke ledger PDF, on the laptop or inside the cron container. `amount_gbp` is the cash effect on the ledger (positive in, negative out, blank if none).
