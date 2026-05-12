# data/imports/

Source files consumed by the ingest pipeline. All CSVs are gitignored.

| Path | Contents |
|---|---|
| `funds.csv` | Fund metadata (name, HL ticker, Morningstar code, account) |
| `dates.csv` | Calendar/trading-day reference table |
| `raw_transactions/ISA/` | HL transaction history exports for the ISA account |
| `raw_transactions/SIPP/` | HL transaction history exports for the SIPP account |

Transaction CSVs are downloaded from the Hargreaves Lansdown website under *Portfolio → History*.
