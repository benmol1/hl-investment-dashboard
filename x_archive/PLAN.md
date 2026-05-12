# HL Investment Dashboard — Project Plan

*Last updated: 2026-04-29*

---

## Goal

A self-hosted investment analytics platform ingesting data from Hargreaves Lansdowne (HL) accounts, enriched with daily market prices and benchmark indices, with an interactive React frontend. Hosted on a Raspberry Pi via Docker.

---

## Accounts & Holdings

| Account | Type | Holdings |
|---------|------|----------|
| ISA | Stocks & Shares ISA | ~6–7 funds + occasional cash |
| SIPP | Self-Invested Personal Pension | ~6–7 funds + occasional cash |

- History goes back to approximately **2017** (account open date)
- Assets are **OEICs / unit trusts** (GB00.../IE00... ISINs) — not exchange-listed ETFs
- Only the **Ranmore Global Equity** fund is a current holding from the historical list; all others are exited positions. Current funds need confirming from a fresh HL export.
- Price data source: **Morningstar** (unofficial JSON API, using the `morningstar_code` identifiers already captured in `dim_funds.csv`)
- Benchmark data: **Yahoo Finance / yfinance** (`^FTSE`, `^GSPC`, `^IXIC`) — indices are exchange-listed and well-covered

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi (Docker)              │
│                                                     │
│  ┌──────────────┐    ┌──────────────┐              │
│  │  Ingestion   │    │   FastAPI    │              │
│  │  Scripts     │───▶│   Backend   │◀── React App │
│  │  (Python)    │    │   (Python)   │    (browser) │
│  └──────┬───────┘    └──────┬───────┘              │
│         │                   │                       │
│         ▼                   ▼                       │
│  ┌─────────────────────────────────┐               │
│  │          DuckDB                 │               │
│  │   (analytics-optimised DB)      │               │
│  └─────────────────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

### Components

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Database | **DuckDB** | Columnar store, excellent for time-series aggregations, zero-server, single file |
| Backend API | **Python + FastAPI** | Lightweight, async, easy to add scheduled tasks |
| Fund price data | **Morningstar** (unofficial API) | Only source with full historical OEIC/unit trust NAV coverage |
| Benchmark data | **yfinance** | ^FTSE, ^GSPC, ^IXIC are exchange-listed and well-covered |
| Frontend | **React + TypeScript + Vite** | Fast build, good ecosystem |
| Charts | **Recharts** | Lower-level but more flexible; good for custom financial charts |
| Deployment | **Docker Compose** | Isolates services, easy to manage on Pi |

---

## Data Model (DuckDB)

### `accounts`
```sql
CREATE TABLE accounts (
    id    TEXT PRIMARY KEY,   -- 'ISA', 'SIPP'
    name  TEXT NOT NULL
);
```

### `funds`
```sql
CREATE TABLE funds (
    id                TEXT PRIMARY KEY,  -- ISIN (e.g. 'IE00B644PG05') or 'CASH'
    name              TEXT NOT NULL,
    isin              TEXT,
    morningstar_code  TEXT,              -- e.g. '0P0000SVHO' — used to fetch prices
    currency          TEXT DEFAULT 'GBP',
    is_active         BOOLEAN DEFAULT TRUE
);
```
Note: `ticker` removed — these are OEICs with no exchange listing. `morningstar_code` replaces it.

### `dim_date`
```sql
CREATE TABLE dim_date (
    date            DATE PRIMARY KEY,
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    day             INTEGER NOT NULL,
    year_month      TEXT NOT NULL,    -- 'YYYY-MM'
    financial_year  TEXT NOT NULL     -- 'FY17', 'FY18' etc. (Apr–Mar UK tax year)
);
```
Retained for easy financial-year grouping in analytics queries. Populated from `dim_date.csv`.

### `transaction_type_mapping`
```sql
CREATE TABLE transaction_type_mapping (
    reference_pattern   TEXT PRIMARY KEY,
    transaction_type    TEXT NOT NULL,
    transaction_subtype TEXT
);
```
Lookup seeded from `mapping_transaction_type.csv`. Covers named reference values (REG. SAVER, MANAGE FEE, etc.). Patterned references (B..., BX..., X..., URIB...) are classified in code.

### `transactions`
```sql
CREATE TABLE transactions (
    id                  TEXT PRIMARY KEY,   -- hash of (account_id, trade_date, reference, value_gbp)
    account_id          TEXT NOT NULL REFERENCES accounts(id),
    fund_id             TEXT REFERENCES funds(id),
    trade_date          DATE NOT NULL,
    settle_date         DATE,
    reference           TEXT NOT NULL,      -- raw HL reference; deduplication key
    raw_description     TEXT,
    transaction_type    TEXT NOT NULL,      -- see types below
    transaction_subtype TEXT,
    unit_cost_pence     DOUBLE,             -- price per unit in pence (as-is from HL); NULL for cash rows
    quantity            DOUBLE,             -- units (always positive; direction from value_gbp sign)
    value_gbp           DOUBLE NOT NULL     -- negative = debit (buy/fee), positive = credit (contribution/sell)
);
```

**Transaction types:**

| Type | Description | Reference pattern |
|------|-------------|-------------------|
| `BUY` | Fund purchase | `B[digits]` |
| `SELL` | Fund sale / partial redemption | `S[digits]` |
| `SWITCH_OUT` | Sell side of fund class switch | `X[digits]` |
| `SWITCH_IN` | Buy side of fund class switch | `BX[digits]` |
| `CONTRIBUTION` | Cash added to account | `REG. SAVER` (positive), `Card Web`, `FPC` |
| `REBATE` | Unit rebate reinvestment cash credit | `URIB...` |
| `FEE` | Platform management charge | `MANAGE FEE` |
| `INTEREST` | Cash interest | `INTEREST` |
| `TRANSFER` | Miscellaneous cash transfer | `Transfer` |
| `REJECTED` | Rejected regular saver | `REG. SAVER` (negative value) |
| `OTHER` | Anything unclassified | — |

**Key parsing notes:**
- `unit_cost_pence` is in **pence** (divide by 100 for GBP price per unit)
- `value_gbp` sign convention: negative = money leaving account, positive = money entering
- `quantity` is always positive; direction implied by `value_gbp`
- Some `value_gbp` values are quoted with commas in the CSV (e.g. `"1,145.16"`) — parser must strip quotes and commas
- Dates in CSV are DD/MM/YYYY
- Fund name is embedded in `Description` field: `{fund_name} (GBP) {quantity} @ {price}` — parsed to link to `funds.id`

### `prices`
```sql
CREATE TABLE prices (
    fund_id     TEXT NOT NULL REFERENCES funds(id),
    date        DATE NOT NULL,
    price_pence DOUBLE NOT NULL,    -- NAV in pence (consistent with HL raw data)
    source      TEXT DEFAULT 'morningstar',
    PRIMARY KEY (fund_id, date)
);
```

### `benchmarks`
```sql
CREATE TABLE benchmarks (
    index_id  TEXT NOT NULL,   -- 'FTSE100', 'SP500', 'NASDAQ'
    date      DATE NOT NULL,
    level     DOUBLE NOT NULL,
    ticker    TEXT,            -- Yahoo Finance ticker (^FTSE, ^GSPC, ^IXIC)
    PRIMARY KEY (index_id, date)
);
```

### Key derived views (computed at query time)

- **Holdings over time**: running unit sum from `transactions` joined to `dim_date`
- **Portfolio value**: holdings × `prices.price_pence / 100`
- **Contributions**: sum of `value_gbp` where `transaction_type = 'CONTRIBUTION'`
- **Growth**: portfolio value − cumulative contributions
- **Fund performance**: value indexed to 100 at first purchase, vs benchmark over same window

---

## Data Ingestion

### HL Transaction CSV (semi-manual, ~weekly)

HL export columns (confirmed from sample data):
```
Trade_date, Settle_date, Reference, Description, Unit_cost_pence, Quantity, Value_GBP
```

**Workflow:**
1. Download transaction history CSV from HL (History tab → Export) for each account
2. Drop file(s) into `data/imports/`
3. Run `python backend/scripts/ingest_transactions.py --file data/imports/<filename>.csv --account ISA` (or `SIPP`)
4. Script deduplicates on `id` hash and upserts — safe to re-run

### Fund prices (automated, daily)

```
python backend/scripts/fetch_prices.py
```
- Fetches daily NAV for each fund with a `morningstar_code` via Morningstar's unofficial JSON API
- Backfills from 2017 on first run
- Funds missing a `morningstar_code` log a warning — require manual price upload
- Runs via cron at ~18:00 weekdays (fund NAVs typically published by 17:00)

### Benchmark prices (automated, daily, same script)
- Fetches `^FTSE`, `^GSPC`, `^IXIC` via yfinance

---

## Frontend — Analytics Views

| View | Description |
|------|-------------|
| **Portfolio Overview** | Total value over time (line chart), current allocation donut |
| **Contributions vs Growth** | Stacked area chart — contributions base, growth on top |
| **Fund Performance** | Per-fund line chart indexed to 100 at first purchase date, with benchmark overlay |
| **Benchmark Comparison** | Portfolio total vs FTSE 100, S&P 500, Nasdaq — indexed to common start |
| **Holdings Table** | Current units, price, value, cost basis, unrealised gain/loss per fund |
| **Transaction Log** | Paginated, filterable table of all transactions |

Multi-user access (owner + family) via home network. No auth initially; basic auth can be added later.

---

## Phased Implementation

### Phase 1 — Data Foundation *(current)*
1. ✅ Examine HL CSV format and dim_funds structure
2. Write DuckDB schema (`001_init.sql`)
3. Write `setup_db.py` — create schema, seed accounts/funds/dim_date/type mappings
4. Write `ingest_transactions.py` — parse HL CSV, classify types, link to funds, upsert
5. Write `fetch_prices.py` — Morningstar NAV + yfinance benchmarks, backfill from 2017
6. Validate: cross-check unit totals from transactions against current HL portfolio values

### Phase 2 — Backend API
1. FastAPI app with endpoints:
   - `GET /portfolio/value?from=&to=`
   - `GET /portfolio/allocation`
   - `GET /funds/{id}/performance`
   - `GET /contributions`
   - `GET /transactions`
2. Cron / APScheduler for daily price fetch

### Phase 3 — React Frontend
1. Vite + React + TypeScript scaffold
2. Recharts chart components
3. Wire up to FastAPI
4. Responsive layout

### Phase 4 — Deployment
1. Docker Compose (FastAPI + Nginx serving React build)
2. Deploy to Raspberry Pi
3. Home network DNS (optionally Tailscale for remote access)

---

## Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Morningstar API token in URL — verify it still works and document refresh process | Price fetch reliability |
| 2 | Funds missing `morningstar_code` in dim_funds (Baillie Gifford, Liontrust, HL UK Income, Ranmore) — need to find Ranmore's code as it's still held | Ranmore price history |
| 3 | Does HL export SIPP transactions in the same CSV format as ISA? | Parser compatibility |
| 4 | Remote access (outside home network) needed? | Docker/networking config |
| 5 | Cron inside backend container or separate service? | Docker Compose design |

---

## Repository Structure

```
hl-investment-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── models.py
│   │   └── routers/
│   ├── scripts/
│   │   ├── setup_db.py          # create schema + seed reference data
│   │   ├── ingest_transactions.py
│   │   └── fetch_prices.py
│   ├── migrations/
│   │   └── 001_init.sql
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── imports/                 # drop HL CSVs here
│   └── hl_dashboard.duckdb
├── docker-compose.yml
└── PLAN.md
```
