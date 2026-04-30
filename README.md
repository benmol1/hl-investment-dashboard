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
- **Daily price updates** — APScheduler runs `fetch_prices.py` automatically at 18:00 inside the FastAPI process

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi (Docker)               │
│                                                      │
│  ┌──────────────┐    ┌──────────────┐               │
│  │  Ingestion   │    │   FastAPI    │               │
│  │  Scripts     │───▶│   Backend   │◀── React App  │
│  │  (Python)    │    │  :8000       │    (browser)  │
│  └──────┬───────┘    └──────┬───────┘               │
│         │                   │                        │
│         └──────────┬────────┘                        │
│                    ▼                                  │
│         ┌─────────────────────┐                      │
│         │       DuckDB        │                      │
│         │  data/hl_dashboard  │                      │
│         │      .duckdb        │                      │
│         └─────────────────────┘                      │
└─────────────────────────────────────────────────────┘
```

| Layer | Technology | Why |
|---|---|---|
| Database | **DuckDB** | Columnar, zero-server, single file — perfect for time-series aggregations |
| Backend | **Python + FastAPI** | Lightweight, async, easy APScheduler integration |
| Fund prices | **Morningstar** (unofficial JSON API) | Only source with full historical OEIC/unit trust NAV data |
| Benchmark prices | **yfinance** | `^FTSE`, `^GSPC`, `^IXIC` — exchange-listed, well-covered |
| Frontend | **React + TypeScript + Vite** | Fast build tooling, strong typing |
| Charts | **Recharts** | Flexible, composable financial charts |
| Deployment | **Docker Compose** | Clean isolation, easy to manage on a Pi |

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.10+ | [python.org](https://python.org) |
| uv | latest | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| npm | 9+ | bundled with Node |

---

## Repository Structure

```
hl-investment-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + APScheduler lifespan
│   │   ├── db.py                # DuckDB connection dependency
│   │   ├── models.py            # Pydantic response schemas
│   │   └── routers/
│   │       ├── portfolio.py     # /portfolio/* endpoints
│   │       ├── funds.py         # /funds/* endpoints
│   │       └── transactions.py  # /transactions endpoint
│   ├── migrations/
│   │   └── 001_init.sql         # Full DuckDB schema
│   ├── scripts/
│   │   ├── setup_db.py          # Create schema + seed reference data
│   │   ├── ingest_transactions.py  # Parse HL CSVs and upsert transactions
│   │   └── fetch_prices.py      # Morningstar NAV + yfinance benchmarks
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # Typed fetch wrappers for each endpoint group
│   │   ├── components/          # Layout, Card, AccountFilter, StatusMessage
│   │   ├── hooks/useApi.ts      # Generic data-fetching hook
│   │   ├── pages/               # One file per route
│   │   └── types.ts             # TypeScript interfaces mirroring API responses
│   ├── vite.config.ts           # Tailwind plugin + /api proxy to :8000
│   └── package.json
├── data/
│   ├── imports/                 # Drop HL CSV exports here
│   └── hl_dashboard.duckdb      # The database (created by setup_db.py)
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
cd backend
uv run python scripts/setup_db.py
```

This creates `data/hl_dashboard.duckdb` and seeds:
- `accounts` — ISA and SIPP rows
- `funds` — all known funds with ISINs and Morningstar codes
- `dim_date` — date dimension table from `data/imports/dim_date.csv`
- `transaction_type_mapping` — reference-pattern-to-type lookup

### 3. Ingest your ISA transactions

Download your transaction history from HL (History tab → Export) and drop the CSV into `data/imports/`. Then run:

```bash
cd backend
uv run python scripts/ingest_transactions.py \
    --file ../data/imports/<your_isa_file>.csv \
    --account ISA
```

For the SIPP, repeat with `--account SIPP`.

The script classifies all transaction types (BUY, SELL, SWITCH, CONTRIBUTION, FEE, REBATE, etc.), links trades to funds by name matching, and upserts with deduplication — safe to re-run on the same file.

### 4. Find the Morningstar code for Ranmore Global Equity

Ranmore Global Equity is the one currently-held fund whose `morningstar_code` is missing. Look it up on [morningstar.co.uk](https://www.morningstar.co.uk), then update the database:

```bash
cd backend
uv run python -c "
import duckdb
con = duckdb.connect('../data/hl_dashboard.duckdb')
con.execute(\"UPDATE funds SET morningstar_code = '<code>' WHERE id = 'IE00B61ZVB30'\")
con.close()
"
```

### 5. Backfill historical prices

```bash
cd backend
uv run python scripts/fetch_prices.py --backfill 2017-01-01
```

This fetches NAV history for all funds with a `morningstar_code` and closes/index levels for all three benchmarks, from the given date to today. Expect it to take a few minutes on first run.

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
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

The API will be at [http://localhost:8000](http://localhost:8000). Interactive docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

**Terminal 2 — frontend dev server**

```bash
cd frontend
npm run dev
```

The dashboard will be at [http://localhost:5173](http://localhost:5173). All `/api/*` requests are proxied to the FastAPI backend via Vite's dev server proxy.

---

## Weekly Data Update

HL doesn't offer a live API, so data is updated manually:

1. Log in to HL and download the transaction history CSV for each account (History → Export)
2. Drop the file(s) into `data/imports/`
3. Run the ingest script for each file:
   ```bash
   cd backend
   uv run python scripts/ingest_transactions.py --file ../data/imports/<filename>.csv --account ISA
   ```

Fund prices and benchmark levels update automatically at 18:00 daily via the APScheduler job inside the FastAPI process. You can also trigger a manual update:

```bash
cd backend
uv run python scripts/fetch_prices.py
```

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

### Core tables

| Table | Key columns | Notes |
|---|---|---|
| `accounts` | `id` (`ISA`, `SIPP`) | Static seed data |
| `funds` | `id` (ISIN), `morningstar_code`, `is_active` | `morningstar_code` drives price fetching |
| `transactions` | `account_id`, `fund_id`, `trade_date`, `transaction_type`, `quantity`, `value_gbp` | `value_gbp` negative = debit; `quantity` always positive |
| `prices` | `fund_id`, `date`, `price_pence` | NAV in pence to match HL's raw format |
| `benchmarks` | `index_id` (`FTSE100`/`SP500`/`NASDAQ`), `date`, `level` | Index closing level |
| `dim_date` | `date`, `financial_year` | Pre-populated; enables UK tax year grouping |

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

## Morningstar API Note

Fund prices are fetched from Morningstar's **unofficial** JSON API. The API token embedded in requests (`9vehuxllxs` as of writing) is extracted from Morningstar's own web pages and has been stable for years — but it can change.

If price fetching starts returning 401/403 errors, open [morningstar.co.uk](https://www.morningstar.co.uk), find a fund, open your browser's Network tab, and look for requests to `lt.morningstar.com/api/rest.svc/...` to find the current token. Update the `MORNINGSTAR_API_TOKEN` constant in [backend/scripts/fetch_prices.py](backend/scripts/fetch_prices.py).

---

## Deployment (Phase 4 — in progress)

Deployment to a Raspberry Pi via Docker Compose is planned. The target setup is:

- **FastAPI** container serving the backend API on port 8000
- **Nginx** container serving the pre-built React frontend and proxying `/api` to FastAPI
- Home network DNS for a friendly local URL (e.g. `http://dashboard.local`)
- Optional: Tailscale for access outside the home network

Docker configuration will be added when Phase 4 is implemented.

---

## Known Issues / Caveats

- **SIPP CSV format** — assumed to match the ISA export format; confirm before ingesting
- **Ranmore Global Equity** — missing `morningstar_code`; prices will not be fetched until this is added (see setup step 4)
- **Morningstar token** — unofficial and subject to change (see note above)
- **Cost basis approximation** — the Holdings page uses a simplified cost basis calculation (total purchase cost minus proceeds from sales). It does not account for switching events; use it as a guide, not a tax record
- **No authentication** — the app is designed for trusted home network use; do not expose it to the public internet without adding authentication
