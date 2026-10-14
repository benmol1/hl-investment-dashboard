# data/imports/

Source files consumed by the ingest pipeline. All CSVs are gitignored.

| Path | Contents |
|---|---|
| `funds.csv` | **Required, create manually.** Fund metadata: `fund_ISIN`, `fund_code` (Morningstar), `fund_name`, `short_name`. See [`../examples/`](../examples/) |
| `raw_transactions/ISA/` | HL transaction history exports for the ISA account |
| `raw_transactions/SIPP/` | HL transaction history exports for the SIPP account |

Transaction CSVs are downloaded from the Hargreaves Lansdown website under *Portfolio → History*.
