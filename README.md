# HL Investment Dashboard

A self-hosted investment analytics platform for Hargreaves Lansdowne (HL) accounts. Ingests transaction CSV exports, fetches daily fund prices from Morningstar and benchmark levels from Yahoo Finance, and presents everything through an interactive React dashboard — with a Telegram bot for natural language queries.

Runs on a Raspberry Pi on the home network, accessible via browser or Telegram from anywhere via Tailscale.

---

## Features

- **Portfolio Overview** — total value over time + current allocation (donut + table)
- **Contributions vs Growth** — stacked area chart separating invested capital from returns
- **Fund Performance** — per-fund indexed line chart rebased to 100 at first purchase, with benchmark overlay
- **Benchmark Comparison** — portfolio vs FTSE 100, S&P 500, and Nasdaq, all indexed to a common start
- **Holdings Table** — units, price, value, cost basis, unrealised gain/loss; sortable columns; cash rows included
- **Transaction Log** — paginated, filterable across both accounts
- **ISA / SIPP filter** — every view can be scoped to a single account or combined
- **Daily refresh** — cron container runs ingest + prices + `dbt build` automatically at 18:00
- **Telegram notifications** — failure alerts, daily success confirmation, and a monthly portfolio summary
- **Telegram query bot** — ask natural language questions ("what's my ISA up this year?") and get answers via Claude tool use; falls back to a read-only DuckDB query for anything the API can't answer directly

---

## Architecture

Four Docker services share a bind-mounted data directory (`/srv/hl-dashboard/data/`):

| Service | Role | Port |
|---|---|---|
| `backend` | FastAPI read-only API server | 8000 (internal) |
| `cron` | Daily refresh + Telegram push notifications | — |
| `bot` | Long-polling Telegram query bot (Claude-powered) | — |
| `frontend` | Nginx serving the Vite build; proxies `/api/` to backend | 2048 (host) |

| Layer | Technology |
|---|---|
| Database | DuckDB (single file, columnar) |
| Data layer | dbt-duckdb (staging → core → marts) |
| Backend | Python + FastAPI |
| Bot | python-telegram-bot + Anthropic SDK (Claude Haiku) |
| Frontend | React + TypeScript + Vite + Recharts + Tailwind CSS v4 |
| Deployment | Docker Compose on Raspberry Pi + Tailscale |

---

## Repository Structure

```
hl-investment-dashboard/
├── backend/
│   ├── app/                     # FastAPI app (main.py, db.py, routers/)
│   ├── bot/                     # Telegram query bot package
│   │   ├── config.py            # Tokens, system prompt
│   │   ├── tools.py             # Claude tool definitions (one per API endpoint)
│   │   ├── executors.py         # Tool call → FastAPI / DuckDB execution
│   │   ├── claude.py            # Agentic tool-use loop (Anthropic SDK)
│   │   ├── handlers.py          # Telegram message handlers
│   │   └── __main__.py          # Entry point: python -m backend.bot
│   ├── scripts/
│   │   ├── setup_db.py          # Create schema + seed reference data
│   │   ├── ingest_transactions.py
│   │   └── fetch_prices.py
│   ├── cron.py                  # APScheduler: ingest + prices + dbt + Telegram alerts
│   └── Dockerfile
├── frontend/
│   ├── src/                     # React pages, components, hooks, API clients
│   ├── nginx.conf
│   └── Dockerfile
├── dbt/
│   └── models/                  # base → core → intermediate → marts
├── data/
│   ├── imports/                 # Drop HL CSV exports here
│   └── hl_dashboard.duckdb
├── docker-compose.yml
├── pyproject.toml               # Python deps (managed by uv)
└── TODO.md
```

---

## First-Time Setup

```bash
# 1. Install Python dependencies
uv sync

# 2. Create the database and seed reference data
uv run python backend/scripts/setup_db.py

# 3. Drop HL CSV exports into data/imports/raw_transactions/ISA/ or SIPP/
uv run python backend/scripts/ingest_transactions.py

# 4. Backfill historical prices
uv run python backend/scripts/fetch_prices.py --backfill 2017-01-01

# 5. Build dbt models
cd dbt && dbt seed --profiles-dir . && dbt run --profiles-dir . && dbt test --profiles-dir .

# 6. Install frontend dependencies
cd frontend && npm install
```

---

## Running Locally

```bash
# Terminal 1 — backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Dashboard: [http://localhost:5173](http://localhost:5173) — API proxied to `:8000` via Vite.

---

## Deployment (Raspberry Pi)

```bash
# On the Pi — first time
cd /srv/hl-dashboard/app
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY
docker compose up -d --build

# Redeploy after a git pull
docker compose up -d --build
```

**Access:**
- Home network: `http://<PI-LOCAL-IP>:2048`
- Remote (via Tailscale): `http://<PI-TAILSCALE-IP>:2048`

**Updating transaction data:** drop new HL CSV exports into `/srv/hl-dashboard/data/imports/raw_transactions/{ISA,SIPP}/` — the 18:00 cron job picks them up automatically.

---

## API Reference

All endpoints are read-only (GET). Interactive docs at `http://localhost:8000/docs`.

| Endpoint | Description |
|---|---|
| `GET /portfolio/value` | Daily total portfolio value |
| `GET /portfolio/allocation` | Current fund allocation |
| `GET /portfolio/contributions` | Portfolio value vs cumulative contributions |
| `GET /portfolio/performance` | Portfolio + benchmarks indexed to 100 |
| `GET /portfolio/holdings` | Holdings with cost basis and unrealised gain/loss |
| `GET /funds` | List all funds |
| `GET /funds/{id}/performance` | Fund indexed to 100 + benchmark overlay |
| `GET /transactions` | Paginated, filterable transaction log |

All portfolio/transaction endpoints accept an `account` query param (`ISA`, `SIPP`, or omit for combined).

---

## Data Model

Raw source tables (`accounts`, `funds`, `transactions`, `prices`, `benchmarks`) are built by `setup_db.py` and the ingestion scripts. dbt transforms these through four layers:

| Layer | Models | Notes |
|---|---|---|
| `base` | `base__hl_transactions`, `base__hl_prices`, `base__hl_benchmarks` | Typed, renamed views over raw tables |
| `core` | `dim_fund`, `dim_account`, `dim_date`, `dim_transaction_type`, `fct_transactions`, `fct_holdings_daily`, `fct_cash_position_daily`, `fct_fund_prices_daily`, `fct_benchmarks_monthly` | Kimball-style dims and facts |
| `intermediate` | `int_fund_values_daily`, `int_cash_values_daily` | Pre-aggregated inputs for marts |
| `marts` | `mart_portfolio_value_daily`, `mart_holdings_latest`, `mart_portfolio_contributions_daily`, `mart_portfolio_returns_monthly`, `mart_benchmarks_monthly`, `mart_portfolio_snapshot_monthly` | API-ready aggregates |

Key conventions: `value_gbp` is negative for debits (buys, fees) and positive for credits (contributions, sells). Fund prices are stored in pence (`price_pence`) to match HL's raw format.
