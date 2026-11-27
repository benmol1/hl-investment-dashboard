# HL Investment Dashboard

A self-hosted investment analytics platform for Hargreaves Lansdowne (HL) accounts. Ingests transaction CSV exports, fetches daily fund prices from Morningstar and benchmark levels from Yahoo Finance, and presents everything through an interactive React dashboard — with a Telegram bot for natural language queries.

Runs on a Raspberry Pi on the home network, accessible via browser or Telegram from anywhere via Tailscale.

---

## Features

- **Portfolio Overview** — total value over time + current allocation (donut + table)
- **Inflows vs Growth** — stacked area chart separating invested capital from returns
- **Fund Performance** — per-fund indexed line chart rebased to 100 at first purchase, with benchmark overlay
- **Benchmark Comparison** — portfolios vs FTSE 100, S&P 500, and Nasdaq 100 (total return, in GBP, via accumulating index ETFs), all indexed to a common start; select any combination of accounts and switch each index on or off
- **Holdings Table** — units, price, value, cost basis, unrealised gain/loss; sortable columns; cash rows included
- **Transaction Log** — paginated, filterable across both accounts
- **ISA / SIPP filter** — every view can be scoped to a single account or combined
- **PELM Will Trust (optional)** — a family trust tracked from month-end valuations and its parsed ledgers (trades, dividends, interest, fees and income paid out), with returns reconciled against the manager's own reports, for comparison against the ISA/SIPP and benchmarks. It is not your money, so it is never in any total: the default view is ISA + SIPP and PELM appears only when selected (Overview, Benchmarks, Transactions). See [Updating PELM Will Trust data](#updating-pelm-will-trust-data)
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
│   │   ├── parse_pelm_ledger.py # PELM ledger PDFs -> data/pelm/pelm_transactions.csv
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
│   ├── macros/                  # PELM file readers (empty table if a file is absent)
│   └── models/                  # base → core → intermediate → marts
├── data/
│   ├── imports/                 # Drop HL CSV exports here
│   ├── pelm/                    # PELM Will Trust CSVs (gitignored) + ledger PDFs
│   ├── examples/                # Example CSV layouts
│   └── hl_dashboard.duckdb
├── pelm-inputs/                 # Drop folder for the Barratt & Cooke pack (gitignored)
├── docs/                        # PELM design notes and to-do
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

### Updating PELM Will Trust data

The PELM Will Trust (Barratt & Cooke, account `C070982`) is optional and manual — the quarterly pack arrives by email, not from HL. It shows only when explicitly selected (Overview, Benchmarks, Transactions), never in ISA + SIPP totals.

On the Pi (the `data/` folder is bind-mounted into the containers, so none of this needs an image rebuild):

1. Copy the email attachments into a dated folder under `/srv/hl-dashboard/data/pelm/` (e.g. `data/pelm/20261127/`). Keep the ledger filenames (`C070982 Ledgers to 31.03.26.pdf`, …): the parser picks up every `C070982 Ledger*.pdf` in `data/pelm/` and its subfolders.
2. Append the new months from `C070982 End of Month Valuations.xlsx` to `pelm_monthly.csv`. Columns: `month_end_date,value_gbp`, the same two columns as the spreadsheet. Layout: [`data/examples/pelm_monthly_example.csv`](data/examples/pelm_monthly_example.csv). External cash flows are not entered by hand any more; they come from the ledgers.
3. Append each new formal total-return performance report to `pelm_reported_returns.csv`: `period_start,period_end,return_pct,source`, with the figure from the report's header line (e.g. `2025-07-01,2025-09-30,4.48,Formal total-return performance report to 30.9.25`). Layout: [`data/examples/pelm_reported_returns_example.csv`](data/examples/pelm_reported_returns_example.csv).
4. Parse the ledgers:
   `docker compose exec cron /app/.venv/bin/python backend/scripts/parse_pelm_ledger.py`
   It reads all four sub-ledgers (capital, dividends, income account, fees) from every PDF, drops entries repeated across overlapping statements, and refuses to write unless every statement balances and each opening balance agrees with the statements before it. It writes `pelm_transactions.csv` and `pelm_ledger_coverage.csv` and prints the external cash flows by month.
5. Rebuild the models: `docker compose exec -w /app/dbt cron /app/.venv/bin/dbt build --profiles-dir .`, or wait for the 01:00 refresh. The test `assert_pelm_reported_returns_reconcile` fails the build if the dashboard's return for a fully covered report period differs from Barratt & Cooke's by more than 0.1pp.

Months without a dividends ledger are flagged as having incomplete cash flows: the BACS income payments to the beneficiary are missing, so their returns are understated. The Benchmarks page says which months are affected, and its "Best estimate" toggle fills them in by adding the average uplift the income data adds in the months that have it. The reconciliation against Barratt & Cooke's reports has its own PELM Reconciliation page.

The parser's `pdfplumber` is installed in the images, so after pulling a change that adds it, run `docker compose up -d --build` once. Locally, the same steps work with the files in `pelm-inputs/` and `data/pelm/`, using `uv run python backend/scripts/parse_pelm_ledger.py`.

The files are read from the bind-mounted `data/` folder. If one is absent that part of PELM is simply left out and the nightly build still passes; a malformed file (e.g. a duplicated month) fails `dbt build` and triggers the usual Telegram alert. Full design: [docs/pelm-integration-plan.md](docs/pelm-integration-plan.md).

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
| `GET /portfolio/ingest-log` | Recent ingest log entries, plus latest data dates for the PELM files |
| `GET /funds` | List all funds |
| `GET /funds/{id}/performance` | Fund indexed to 100 + benchmark overlay |
| `GET /transactions` | Paginated, filterable transaction log |
| `GET /pelm/transactions` | PELM Will Trust ledger lines from all four sub-ledgers (trades, dividends, interest, fees, income paid out, transfers); filter by `type` or `category`; deposit and settlement sweeps hidden unless `include_internal=true` |
| `GET /pelm/income?grain=quarter\|month` | PELM income received, FX commission, custody fees and income paid out per quarter or month, with ledger-coverage flags and trailing-12m yield |
| `GET /portfolio/returns/quarterly` | Total return per calendar quarter (linked monthly returns) with the three benchmarks over the same months; `estimate=true` fills PELM months with incomplete cash flows with the best estimate |
| `GET /pelm/reconciliation` | Barratt & Cooke's reported total return per report period beside the dashboard's own figure |

All portfolio/transaction endpoints accept an `account` query param (`ISA`, `SIPP`, or omit for combined ISA + SIPP). The `/portfolio/*` endpoints also accept `PELM`, which has month-end valuations only: `/portfolio/value` and `/portfolio/performance` serve it, while holdings, allocation and inflows return a 400. PELM is never part of the combined default.

---

## Data Model

Raw source tables (`accounts`, `funds`, `transactions`, `prices`, `benchmarks`) are built by `setup_db.py` and the ingestion scripts. dbt transforms these through four layers:

| Layer | Models | Notes |
|---|---|---|
| `base` | `base__hl_transactions`, `base__hl_prices`, `base__hl_benchmarks`, `base__pelm_valuations`, `base__pelm_transactions`, `base__pelm_ledger_coverage`, `base__pelm_reported_returns` | Typed, renamed views over raw tables; the PELM models are tables read from `data/pelm/*.csv` |
| `core` | `dim_fund`, `dim_account`, `dim_date`, `dim_transaction_type`, `fct_transactions`, `fct_holdings_daily`, `fct_cash_position_daily`, `fct_fund_prices_daily`, `fct_benchmarks_monthly`, `fct_pelm_transactions` | Kimball-style dims and facts |
| `intermediate` | `int_fund_values_daily`, `int_cash_values_daily`, `int_pelm_ledger_coverage_monthly` | Pre-aggregated inputs for marts |
| `marts` | `mart_portfolio_value_daily`, `mart_holdings_latest`, `mart_portfolio_inflows_daily`, `mart_portfolio_returns_monthly`, `mart_fund_snapshot_monthly`, `mart_fund_returns_monthly`, `mart_benchmarks_monthly`, `mart_portfolio_snapshot_monthly`, `mart_contributions_by_financial_year`, `mart_pelm_income_monthly`, `mart_pelm_return_reconciliation` | API-ready aggregates |

`dim_account.data_grain` is `daily` for ISA/SIPP (full holdings and transactions) and `monthly` for PELM (month-end valuations only); daily-only models and endpoints filter on it. PELM is unioned into `mart_portfolio_snapshot_monthly`, with its external cash flows (including income paid out to the beneficiary) derived from the ledgers, so the returns and benchmark marts pick it up unchanged. `cash_flow_coverage_indicator` marks the PELM months whose flows are incomplete. Design notes: [docs/pelm-integration-plan.md](docs/pelm-integration-plan.md).

Key conventions: `value_gbp` is negative for debits (buys, fees) and positive for credits (contributions, sells). Fund prices are stored in pence (`price_pence`) to match HL's raw format.
