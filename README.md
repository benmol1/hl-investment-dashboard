# HL Investment Dashboard

A self-hosted investment analytics platform for Hargreaves Lansdowne (HL) accounts. Ingests transaction CSV exports from HL, fetches daily fund prices from Morningstar and benchmark levels from Yahoo Finance, and presents everything through an interactive React dashboard.

Designed to run on a Raspberry Pi on the home network, accessible to family members via browser.

---

## Features

- **Portfolio Overview** — total value over time (line chart) + current allocation (donut + table)
- **Contributions vs Growth** — stacked area chart separating invested capital from investment returns
- **Fund Performance** — per-fund indexed line chart (rebased to 100 at first purchase) with switchable benchmark overlay
- **Benchmark Comparison** — portfolio vs FTSE 100, S&P 500, and Nasdaq, all indexed to a common start date
- **Holdings Table** — current units, price, market value, cost basis, and unrealised gain/loss per fund
- **Transaction Log** — paginated, filterable table of all transactions across both accounts
- **ISA / SIPP filter** — every analytical view can be scoped to a single account or viewed combined
- **Daily price updates** — a dedicated cron container runs `ingest_transactions.py`, `fetch_prices.py`, and `dbt build` automatically at 18:00 every day

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Raspberry Pi (Docker Compose)               │
│                                                             │
│  ┌─────────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │   cron          │   │   backend    │   │   frontend   │  │
│  │  (Python)       │   │  (FastAPI)   │   │   (Nginx)    │  │
│  │                 │   │   :8000      │◀──│   :2048      │◀─┼── browser
│  │ ingest_txns.py  │   └──────┬───────┘   └──────────────┘  │
│  │ fetch_prices.py │          │                             │
│  │ dbt build       │          │                             │
│  │ (daily @ 18:00) │          │                             │
│  └────────┬────────┘          │                             │
│           │                   │                             │
│           └──────────┬────────┘                             │
│                      ▼                                      │
│           ┌─────────────────────┐                           │
│           │       DuckDB        │                           │
│           │  (bind-mounted from │                           │
│           │  /srv/hl-dashboard/ │                           │
│           │       data/)        │                           │
│           └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

| Layer | Technology | Why |
|---|---|---|
| Database | **DuckDB** | Columnar, zero-server, single file — perfect for time-series aggregations |
| Data layer | **dbt-duckdb** | Base → core → mart models |
| Backend | **Python + FastAPI** | Lightweight, async, read-only API server |
| Scheduler | **APScheduler** in a dedicated cron container | Decoupled from the API; runs ingest + prices + dbt daily |
| Fund prices | **Morningstar** (unofficial JSON API) | Only source with full historical OEIC/unit trust NAV data |
| Benchmark prices | **yfinance** | `^FTSE`, `^GSPC`, `^IXIC` — exchange-listed, well-covered |
| Frontend | **React + TypeScript + Vite** | Fast build tooling, strong typing |
| Charts | **Recharts** | Flexible, composable financial charts |
| Deployment | **Docker Compose on Raspberry Pi** | Clean isolation, easy to manage; accessible via Tailscale |

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.10+ | [python.org](https://python.org) |
| uv | latest | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| npm | 9+ | bundled with Node |
| Docker | latest | [docs.docker.com](https://docs.docker.com/get-docker/) — only needed for deployment |

---

## Repository Structure

```
hl-investment-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app — read-only API server
│   │   ├── db.py                # DuckDB connection dependency
│   │   ├── models.py            # Pydantic response schemas
│   │   └── routers/
│   │       ├── portfolio.py     # /portfolio/* endpoints
│   │       ├── funds.py         # /funds/* endpoints
│   │       └── transactions.py  # /transactions endpoint
│   ├── scripts/
│   │   ├── setup_db.py          # Create schema + seed reference data
│   │   ├── ingest_transactions.py  # Parse HL CSVs and upsert transactions
│   │   └── fetch_prices.py      # Morningstar NAV + yfinance benchmarks
│   ├── cron.py                  # Standalone APScheduler: ingest + prices + dbt daily at 18:00
│   └── Dockerfile               # Python slim + uv; runs dbt deps during build
├── frontend/
│   ├── src/
│   │   ├── api/                 # Typed fetch wrappers for each endpoint group
│   │   ├── components/          # Layout, Card, AccountFilter, StatusMessage
│   │   ├── hooks/useApi.ts      # Generic data-fetching hook
│   │   ├── pages/               # One file per route
│   │   └── types.ts             # TypeScript interfaces mirroring API responses
│   ├── nginx.conf               # Proxies /api/ to backend:8000; SPA fallback routing
│   ├── vite.config.ts           # Tailwind plugin + /api proxy to :8000 (dev only)
│   ├── Dockerfile               # Multi-stage: Node build → Nginx alpine
│   └── package.json
├── dbt/
│   ├── models/
│   │   ├── base/                # Raw source views (transactions, prices, benchmarks)
│   │   ├── core/                # dims + fcts (dim_fund, fct_transactions, fct_daily_holdings, …)
│   │   ├── intermediate/        # int_daily_fund_values, int_daily_cash_values
│   │   └── marts/               # mart_daily_portfolio_value, mart_current_holdings, …
│   ├── seeds/                   # seed_dates.csv
│   ├── dbt_project.yml
│   └── profiles.yml
├── data/
│   ├── imports/                 # Drop HL CSV exports here
│   └── hl_dashboard.duckdb      # The database (created by setup_db.py)
├── docker-compose.yml           # Three-service stack; DATA_DIR env var for bind mount
├── .dockerignore
├── pyproject.toml               # Python dependencies (managed by uv)
└── TODO.md                      # Phase-by-phase progress tracker
```

---

## First-Time Setup

### 1. Install Python dependencies

```bash
uv sync
```

### 2. Create the database and seed reference data

```bash
uv run python backend/scripts/setup_db.py
```

This creates `data/hl_dashboard.duckdb` and seeds:
- `accounts` — ISA and SIPP rows
- `funds` — all known funds with ISINs and Morningstar codes
- `dim_date` — date dimension table from `data/imports/dim_date.csv`
- `transaction_type_mapping` — reference-pattern-to-type lookup

### 3. Ingest your transactions

Download your transaction history from HL (History tab → Export) and drop the CSV into `data/imports/raw_transactions/ISA/` or `data/imports/raw_transactions/SIPP/`. Then run:

```bash
uv run python backend/scripts/ingest_transactions.py
```

The script auto-discovers both folders and upserts all transactions — re-running is safe and never duplicates rows.

### 4. Backfill historical prices

```bash
uv run python backend/scripts/fetch_prices.py --backfill 2017-01-01
```

This fetches NAV history for all funds with a `morningstar_code` and closes/index levels for all three benchmarks, from the given date to today. Expect it to take a few minutes on first run.

### 5. Build the dbt models

```bash
cd dbt
dbt seed --profiles-dir .   # load dim_date (first time only)
dbt run  --profiles-dir .   # build all models
dbt test --profiles-dir .   # run all tests
```

### 6. Validate unit totals

Cross-check the unit counts derived from transactions against your current HL portfolio page to confirm that ingestion is correct before relying on the dashboard values.

### 7. Install frontend dependencies

```bash
cd frontend
npm install
```

---

## Running Locally

Open two terminals from the project root.

**Terminal 1 — backend API**

```bash
PYTHONPATH=backend uv run uvicorn app.main:app --reload --port 8000
```

The API will be at [http://localhost:8000](http://localhost:8000). Interactive docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

**Terminal 2 — frontend dev server**

```bash
cd frontend
npm run dev
```

The dashboard will be at [http://localhost:5173](http://localhost:5173). All `/api/*` requests are proxied to the FastAPI backend via Vite's dev server proxy.

---

## Updating Transaction Data

HL doesn't offer a live API, so transaction data is updated manually:

1. Log in to HL and download the transaction history CSV for each account (History → Export)
2. Copy the file to the Pi's drop folder via `scp`:
   ```powershell
   scp "export.csv" pi@<PI-IP>:/srv/hl-dashboard/data/imports/raw_transactions/ISA/
   # or SIPP/ for the SIPP account
   ```
3. The daily cron job (18:00) will automatically pick up the file, ingest it, fetch the latest prices, and rebuild the dbt models.

To trigger a manual refresh immediately without waiting for 18:00:

```bash
# On the Pi
cd /srv/hl-dashboard/app
DATA_DIR=/srv/hl-dashboard/data docker compose exec cron /app/.venv/bin/python backend/scripts/ingest_transactions.py
DATA_DIR=/srv/hl-dashboard/data docker compose exec cron /app/.venv/bin/python backend/scripts/fetch_prices.py
DATA_DIR=/srv/hl-dashboard/data docker compose exec cron sh -c "cd dbt && /app/.venv/bin/dbt build --profiles-dir ."
```

The auto-renamer in `ingest_transactions.py` handles any filename — files are renamed to `{ACCOUNT}_{YYYY-MM-DD}.csv` on ingestion, and re-running never duplicates rows.

---

## API Reference

The API runs on port 8000. All endpoints are read-only (GET). Interactive docs: `http://localhost:8000/docs`.

### Portfolio

| Endpoint | Query params | Description |
|---|---|---|
| `GET /portfolio/value` | `from`, `to`, `account` | Daily total portfolio value (time series) |
| `GET /portfolio/allocation` | `as_of`, `account` | Current fund allocation — units, price, value, % |
| `GET /portfolio/contributions` | `from`, `to`, `account` | Portfolio value vs cumulative contributions over time |
| `GET /portfolio/performance` | `from`, `to`, `account` | Portfolio + all 3 benchmarks indexed to 100 at `from` |
| `GET /portfolio/holdings` | `account` | Holdings with cost basis and unrealised gain/loss |

### Funds

| Endpoint | Query params | Description |
|---|---|---|
| `GET /funds` | `active_only` | List all funds |
| `GET /funds/{id}/performance` | `from`, `to`, `benchmark` | Fund value indexed to 100 + benchmark overlay |

`benchmark` accepts: `FTSE100`, `SP500`, `NASDAQ` (default: `FTSE100`).

### Transactions

| Endpoint | Query params | Description |
|---|---|---|
| `GET /transactions` | `page`, `per_page`, `account`, `fund_id`, `type`, `from`, `to` | Paginated transaction log |

### Utility

| Endpoint | Description |
|---|---|
| `GET /health` | Returns `{"status": "ok"}` |

---

## Data Model

### Raw / source tables

| Table | Key columns | Notes |
|---|---|---|
| `accounts` | `id` (`ISA`, `SIPP`) | Static seed data |
| `funds` | `id` (ISIN), `morningstar_code`, `is_active` | `morningstar_code` drives price fetching |
| `transactions` | `account_id`, `fund_id`, `trade_date`, `transaction_type`, `quantity`, `value_gbp` | `value_gbp` negative = debit; `quantity` always positive |
| `prices` | `fund_id`, `date`, `price_pence` | NAV in pence to match HL's raw format |
| `benchmarks` | `index_id` (`FTSE100`/`SP500`/`NASDAQ`), `date`, `level` | Index closing level |
| `date` | `date`, `financial_year` | Pre-populated; enables UK tax year grouping |

### dbt model layers

| Layer | Models | Notes |
|---|---|---|
| `base` | `base__hl_transactions`, `base__hl_prices`, `base__hl_benchmarks` | Typed, renamed views over raw tables |
| `core` | `dim_fund`, `dim_account`, `dim_date`, `dim_transaction_type`, `fct_transactions`, `fct_daily_holdings`, `fct_daily_cash_position`, `fct_fund_prices_daily`, `fct_benchmarks_monthly` | Kimball-style dims and fcts |
| `intermediate` | `int_daily_fund_values`, `int_daily_cash_values` | Pre-aggregated inputs for marts |
| `marts` | `mart_daily_portfolio_value`, `mart_current_holdings`, `mart_portfolio_contributions`, `mart_portfolio_returns`, `mart_benchmarks`, `mart_monthly_snapshot` | API-ready aggregates |

### Transaction types

| Type | Trigger |
|---|---|
| `BUY` | Reference matches `B[digits]` |
| `SELL` | Reference matches `S[digits]` |
| `SWITCH_IN` | Reference matches `BX[digits]` |
| `SWITCH_OUT` | Reference matches `X[digits]` |
| `CONTRIBUTION` | `REG. SAVER`, `Card Web`, `FPC` references |
| `REBATE` | Reference matches `URIB...` |
| `FEE` | `MANAGE FEE` reference |
| `INTEREST` | `INTEREST` reference |
| `REJECTED` | `REG. SAVER` with negative value |

---

## Deployment

The dashboard runs on a Raspberry Pi via Docker Compose. Three services share a bind-mounted data directory (`/srv/hl-dashboard/data/` on the Pi):

| Service | Role | Port |
|---|---|---|
| `backend` | FastAPI read-only API server | 8000 (internal only) |
| `cron` | Daily refresh: ingest → prices → dbt build at 18:00 | — |
| `frontend` | Nginx serving the Vite build; proxies `/api/` to backend | 2048 (host) |

**Access:**
- Home network: `http://192.168.1.220:2048`
- Remote (via Tailscale): `http://<PI-TAILSCALE-IP>:2048`

**Tailscale** is installed natively on the Pi (not in Docker), so the entire Pi is reachable over the tailnet.

**To start the stack on the Pi:**
```bash
cd /srv/hl-dashboard/app
DATA_DIR=/srv/hl-dashboard/data docker compose up -d
```

---