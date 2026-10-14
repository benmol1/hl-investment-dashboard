# HL Investment Dashboard

A self-hosted investment analytics platform for Hargreaves Lansdowne (HL) accounts. Ingests transaction CSV exports, fetches daily fund prices from Morningstar and benchmark levels from Yahoo Finance, and presents everything through an interactive React dashboard — with a Telegram bot for natural language queries.

Runs on a Raspberry Pi on the home network, accessible via browser or Telegram from anywhere via Tailscale.

---

## Features

- **Portfolio Overview** — total value over time + current allocation (donut + table)
- **Inflows vs Growth** — stacked area chart separating invested capital from returns
- **Fund Performance** — per-fund indexed line chart rebased to 100 at first purchase, with benchmark overlay
- **Benchmark Comparison** — portfolio vs FTSE 100, S&P 500, and Nasdaq, all indexed to a common start
- **Holdings Table** — units, price, value, cost basis, unrealised gain/loss; sortable columns; cash rows included
- **Transaction Log** — paginated, filterable across both accounts
- **ISA / SIPP filter** — every view can be scoped to a single account or combined
- **Weekly HL download** — cron container logs in to HL with Playwright and downloads fresh ISA/SIPP transaction CSVs on Sundays at 00:00 (optional; manual CSV drop also works)
- **Daily refresh** — cron container runs ingest + prices + `dbt build` automatically at 01:00
- **Telegram notifications** — failure alerts, daily success confirmation, and a monthly portfolio summary
- **Telegram query bot** — ask natural language questions ("what's my ISA up this year?") and get answers via Claude tool use; falls back to a read-only DuckDB query for anything the API can't answer directly

---

## Architecture

Four Docker services share a bind-mounted data directory (`/srv/hl-dashboard/data/`):

| Service | Role | Port |
|---|---|---|
| `backend` | FastAPI read-only API server | 8000 (internal) |
| `cron` | Scheduled ETL — downloads HL CSVs (weekly), ingests transactions, fetches prices, runs `dbt build` to write marts into the shared DuckDB file; sends Telegram alerts. Image includes Playwright + Chromium | — |
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
│   │   ├── eval.py              # Eval harness (results in eval_results/)
│   │   ├── handlers.py          # Telegram message handlers
│   │   └── __main__.py          # Entry point: python -m backend.bot
│   ├── scripts/
│   │   ├── setup_db.py          # Create schema + seed reference data
│   │   ├── download_transactions.py  # Playwright download of HL CSVs
│   │   ├── ingest_transactions.py
│   │   ├── fetch_prices.py      # --backfill YYYY-MM-DD, --all
│   │   ├── cleanup_db.py
│   │   ├── run_ground_truth.py  # Bot eval ground-truth answers
│   │   └── summarise_evals.py   # Summarise bot eval results
│   ├── migrations/              # DB migrations
│   ├── cron.py                  # APScheduler: download + ingest + prices + dbt + Telegram alerts
│   └── Dockerfile
├── cron/
│   └── Dockerfile               # Cron image (adds Playwright/Chromium)
├── tests/                       # pytest suites for api/ and bot/
├── run_local.ps1                # Load .env and run a script locally via uv
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
# 0. Create your env file and fill in values (see comments inside)
cp .env.example .env

# 1. Install Python dependencies (and the Chromium browser if using the HL download)
uv sync
uv run playwright install chromium

# 1b. Create data/imports/funds.csv — the only file you must write by hand.
#     Copy data/examples/funds.csv and list your own funds (see data/examples/README.md).
#     The date dimension seed (dbt/seeds/seed_date.csv) is committed; nothing to do.

# 2. Create the database and seed reference data
uv run python backend/scripts/setup_db.py

# 3. Get transactions: either download automatically (needs HL_* vars in .env)...
.\run_local.ps1 backend/scripts/download_transactions.py
#    ...or drop HL CSV exports into data/imports/raw_transactions/ISA/ or SIPP/
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

```bash
# Bot eval harness (requires backend running first)
$env:BACKEND_URL="http://localhost:8000"; uv run python -m backend.bot.eval

# Tests
uv run pytest
```

### HL automatic download

`download_transactions.py` needs `HL_USERNAME`, `HL_DATE_OF_BIRTH`, `HL_PASSWORD`, `HL_SECURE_NUMBER`, `HL_ISA_ACCOUNT_ID` and `HL_SIPP_ACCOUNT_ID` (see `.env.example`).

**Finding your account IDs:** log in to hl.co.uk, open your ISA (or SIPP), go to *Transaction history* and export to CSV. The download URL contains `/account/XX/` — `XX` is the numeric account ID. Repeat for the other account.

On the first login HL may ask for an SMS code: the script exits with instructions, then re-run with `HL_OTP=<code>`. The trusted session is saved to `data/hl_session.json` (gitignored — keep it private). If `HL_USERNAME` is unset, the cron job skips the download.

---

## Deployment (Raspberry Pi)

```bash
# On the Pi — first time
cd /srv/hl-dashboard/app
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY and the HL_* credentials
docker compose up -d --build

# Redeploy after a git pull
docker compose up -d --build

# Manually trigger a dbt build
docker compose exec -w /app/dbt cron /app/.venv/bin/dbt run --profiles-dir .
```

**Access:**
- Home network: `http://<PI-LOCAL-IP>:2048`
- Remote (via Tailscale): `http://<PI-TAILSCALE-IP>:2048`

**Updating transaction data:** with HL credentials configured, the cron job downloads new CSVs on Sundays at 00:00. Otherwise drop new HL CSV exports into `/srv/hl-dashboard/data/imports/raw_transactions/{ISA,SIPP}/`. Either way the 01:00 daily refresh ingests them.

---

## API Reference

All endpoints are read-only (GET). Interactive docs at `http://localhost:8000/docs`.

| Endpoint | Description |
|---|---|
| `GET /portfolio/value` | Daily total portfolio value |
| `GET /portfolio/allocation` | Current fund allocation |
| `GET /portfolio/inflows` | Portfolio value vs cumulative inflows (contributions + transfers) |
| `GET /portfolio/performance` | Portfolio + benchmarks indexed to 100 |
| `GET /portfolio/contributions/financial-year` | New-money contributions per UK tax year (ISA, SIPP, combined; excludes transfers) |
| `GET /portfolio/holdings` | Holdings with cost basis and unrealised gain/loss |
| `GET /portfolio/freshness` | Latest data dates (data freshness) |
| `GET /portfolio/ingest-log` | Recent ingest log entries |
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
| `marts` | `mart_portfolio_value_daily`, `mart_holdings_latest`, `mart_portfolio_inflows_daily`, `mart_portfolio_returns_monthly`, `mart_fund_snapshot_monthly`, `mart_fund_returns_monthly`, `mart_benchmarks_monthly`, `mart_portfolio_snapshot_monthly`, `mart_contributions_by_financial_year` | API-ready aggregates |

Key conventions: `value_gbp` is negative for debits (buys, fees) and positive for credits (contributions, sells). Fund prices are stored in pence (`price_pence`) to match HL's raw format.
