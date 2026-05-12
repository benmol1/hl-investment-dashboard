# HL Investment Dashboard — Progress & To-Dos

*Last updated: 2026-05-11*

---

## Phase 1 — Data Foundation ✅ COMPLETE

- [x] Examine HL CSV export format and `dim_funds.csv` structure
- [x] Confirm all assets are OEICs/unit trusts (not ETFs) — price source changed to Morningstar
- [x] Write DuckDB schema (`backend/migrations/001_init.sql`) — tables + 3 analytical views
- [x] Write `backend/scripts/setup_db.py` — creates schema, seeds accounts, funds, dim_date, transaction type mappings
- [x] Write `backend/scripts/ingest_transactions.py` — parses HL CSVs, classifies all transaction types (BUY, SELL, SWITCH, CONTRIBUTION, FEE, REBATE, etc.), links trades to funds, upserts with deduplication
- [x] Write `backend/scripts/fetch_prices.py` — Morningstar NAV history + yfinance benchmark indices (FTSE 100, S&P 500, Nasdaq)
- [x] Smoke-tested against ISA transaction CSV: 491/491 rows loaded, 0 unlinked fund trades

---

## Phase 1b — Raw Transaction Import Pipeline ✅ COMPLETE

- [x] Create `data/imports/raw_transactions/ISA/` and `data/imports/raw_transactions/SIPP/` as drop folders for unmodified HL CSV exports
- [x] Rewrite `ingest_transactions.py` to auto-discover and process both folders (no CLI args needed)
- [x] Auto-renamer: any file not matching `{ACCOUNT}_{YYYY-MM-DD}.csv` is renamed on each run using file creation date; date collisions get `_1`, `_2` suffixes
- [x] Handle raw HL CSV format: skip 5 metadata header lines; remap column names (`Trade date` → `Trade_date`, `Unit cost (p)` → `Unit_cost_pence`, `Value (£)` → `Value_GBP`) with encoding-tolerant substring matching
- [x] Incremental upsert confirmed working — re-running never duplicates rows
- [x] Update `setup_db.py` to use `INSERT OR REPLACE` for funds so re-seeding always reflects `dim_funds.csv`
- [x] ISA and SIPP transactions ingested: 62 ISA rows, 159 SIPP rows
- [x] Find a way to fix the Rathbone data - it changed its fund ID in May 2019, but there isn't a clean buy/sell transaction to reflect the change

---

## Phase 2 — Backend API ✅ COMPLETE

- [x] Create `backend/app/main.py` — FastAPI app skeleton
- [x] Create `backend/app/db.py` — DuckDB connection management (read-only per request)
- [x] Create `backend/app/models.py` — Pydantic response schemas
- [x] Implement API endpoints:
  - [x] `GET /portfolio/value?from=&to=&account=` — time-series of total portfolio value
  - [x] `GET /portfolio/allocation?as_of=&account=` — current allocation by fund
  - [x] `GET /portfolio/contributions?from=&to=&account=` — cumulative contributions vs portfolio value
  - [x] `GET /portfolio/performance?from=&to=&account=` — portfolio + all 3 benchmarks indexed to 100
  - [x] `GET /portfolio/holdings?account=` — holdings with cost basis and unrealised gain
  - [x] `GET /funds` — list funds (active_only filter)
  - [x] `GET /funds/{id}/performance?from=&to=&benchmark=` — fund indexed to 100 + benchmark overlay
  - [x] `GET /transactions?page=&per_page=&account=&type=&from=&to=` — paginated, filterable transaction log
- [x] APScheduler in lifespan runs `fetch_prices.py` daily at 18:00

---

## Phase 3 — React Frontend ✅ COMPLETE

- [x] Scaffold with Vite + React + TypeScript (`frontend/`)
- [x] Tailwind CSS v4 + Recharts
- [x] Pages:
  - [x] Portfolio Overview — total value line chart + allocation donut with table
  - [x] Contributions vs Growth — stacked area chart + summary KPIs
  - [x] Fund Performance — fund list page + per-fund indexed line chart with benchmark overlay
  - [x] Benchmark Comparison — portfolio vs FTSE 100, S&P 500, Nasdaq (all indexed to 100)
  - [x] Holdings Table — units, price, value, cost basis, unrealised gain, weight
  - [x] Transaction Log — paginated, filterable by account + type
- [x] All pages wired to FastAPI endpoints via `/api` Vite proxy
- [x] ISA / SIPP / All account filter on Overview, Contributions, Benchmarks, Holdings

**To run locally:**
```bash
# Terminal 1 — backend (PYTHONPATH puts backend/ on sys.path so 'from app.xxx import' works)
PYTHONPATH=backend uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend dev server
cd frontend && npm run dev
```

---

## Phase 4 — dbt Data Layer [In progress]

- [x] Add `dbt-duckdb` dependency; install `dbt-utils` package
- [x] Bootstrap dbt project (`dbt/dbt_project.yml`, `profiles.yml`, `packages.yml`)
- [x] Promote `dim_date.csv` to a dbt seed (ISO dates, snake_case headers)
- [x] Declare 6 source tables in `sources.yml` with not-null, unique, referential integrity, and accepted-values tests
- [x] Staging layer (views): `stg_transactions` (adds `is_trade`, `is_contribution`, `unit_direction`), `stg_prices` (adds `price_gbp`), `stg_benchmarks`
- [x] Intermediate layer (tables): `int_trade_unit_deltas` → `int_cumulative_unit_balances` → `int_daily_unit_balances` (ASOF JOIN, account-aware), `int_daily_fund_values`, `int_fund_cost_basis`, `int_daily_contributions`
- [x] Mart layer (tables): `mart_daily_portfolio_value`, `mart_current_holdings` (daily snapshot), `mart_portfolio_contributions`, `mart_benchmark_levels`
- [x] 112/112 data tests pass; all 13 models build successfully
- [x] Drop old `v_holdings` and `v_portfolio_value` views from DuckDB and `001_init.sql`
- [x] Review data model end-to-end. Polish, make improvements and align it with Kimball style (surrogate keeys used for joins; more explicit column names)
- [x] Understand and calculate Sharpe ratios for each account + benchmarks
- [x] Add a short_name to dim_fund


**To run dbt:**
```bash
cd dbt
dbt seed --profiles-dir .   # load dim_date (first time only)
dbt run  --profiles-dir .   # build all models
dbt test --profiles-dir .   # run all 112 tests
```

---

## Phase 5 — Wire API to dbt Core and Marts ✅ COMPLETE

- [x] Update `GET /portfolio/value` → query `mart_daily_portfolio_value`
- [x] Update `GET /portfolio/contributions` → query `mart_portfolio_contributions`
- [x] Update `GET /portfolio/performance` → query `mart_monthly_snapshot` + `mart_benchmarks` (monthly series)
- [x] Update `GET /portfolio/allocation` → query `fct_daily_holdings` joined to dims (point-in-time filter)
- [x] Build `mart_current_holdings` (cost basis in dbt — buy cost minus sell proceeds, per account+fund, floored at zero) ✅
- [x] Update `GET /portfolio/holdings` → query `mart_current_holdings`
- [x] Update `GET /funds/{id}/performance` → query `int_daily_fund_values` (monthly filter) + `mart_benchmarks`
- [x] Update `GET /funds` → query `dim_fund` (`investment_status_indicator = 'Holding'` → `is_active`; `isin` → `None`)
- [x] Update `GET /transactions` → query `fct_transactions` joined to `dim_account`, `dim_fund`, `dim_transaction_type`, `dim_date`
- [x] Add `dbt run` to the APScheduler daily job (after `fetch_prices.py`)
- [x] Delete legacy migration file `backend/migrations/002_fix_holdings_view.sql`

---

## Phase 6 — Deployment

### Architecture

Three Docker services, one shared bind mount:

| Service | Image | Role |
|---------|-------|------|
| `backend` | Python slim + uv | FastAPI/uvicorn — read-only API server |
| `cron` | same as backend | Runs `fetch_prices.py` + `dbt build` daily at 18:00 |
| `frontend` | Nginx alpine | Serves Vite build; proxies `/api/*` → backend |

- **DuckDB + data**: bind-mounted from `/srv/hl-dashboard/data/` on the Pi into both `backend` and `cron` containers. New HL CSV exports are dropped into `/srv/hl-dashboard/data/imports/raw_transactions/{ISA,SIPP}/` directly on the Pi filesystem.
- **Tailscale**: installed natively on the Pi (not in Docker) so the whole Pi is reachable over the tailnet, not just the dashboard port.
- **Local DNS**: Pi-Hole's Local DNS (Settings → Local DNS → DNS Records) — add an A record pointing `hl-dashboard` → Pi's LAN IP. Since Pi-Hole is already the network DNS resolver, this works for every device on the network instantly, no mDNS/Avahi needed.
- **Port conflict**: Pi-Hole's web interface uses lighttpd on port 80. The frontend container must expose on a different host port (e.g. `8080`) to avoid the clash. Access the dashboard at `http://hl-dashboard:8080`.

### Tasks

#### Docker

- [ ] Write `backend/Dockerfile` — Python slim base, install deps via `uv sync --no-dev`, copy `backend/`, `dbt/`, `data/` structure; entrypoint: `uvicorn app.main:app`
- [ ] Write `cron/Dockerfile` (or reuse backend image) — same deps; entrypoint: `python cron.py`
- [x] Write `backend/cron.py` — standalone APScheduler script that runs `fetch_prices.py` then `dbt build` daily at 18:00; no FastAPI dependency
- [x] Remove APScheduler and `_run_daily_refresh` from `backend/app/main.py` — API becomes a pure read-only server
- [ ] Write `frontend/Dockerfile` — multi-stage: Node build stage (`npm run build`) → Nginx alpine serving `dist/`; Nginx config proxies `/api/` → `http://backend:8000/`
- [ ] Write `docker-compose.yml` — three services (`backend`, `cron`, `frontend`); shared bind mount for `data/`; `backend` and `cron` depend on the same volume; `frontend` exposes host port 8080 (Pi-Hole owns port 80)
- [ ] Strip dev-only deps (jupyter, matplotlib, ipykernel) from the backend/cron image — add a `[tool.uv]` dev group or use `--no-dev` flag
- [ ] Test full Docker build locally (`docker compose up --build`)
- [ ] Verify daily refresh fires correctly in the cron container (check logs)

#### Raspberry Pi setup

- [ ] Install Docker + Docker Compose on the Pi
- [ ] Create bind mount directory: `sudo mkdir -p /srv/hl-dashboard/data/imports/raw_transactions/{ISA,SIPP}`
- [ ] Copy initial `hl_dashboard.duckdb` to `/srv/hl-dashboard/data/` (one-time seed from dev machine)
- [ ] Clone repo to Pi and run `docker compose up -d`
- [ ] Install Tailscale on the Pi (`curl -fsSL https://tailscale.com/install.sh | sh`) and authenticate
- [ ] Add Local DNS record in Pi-Hole admin: `hl-dashboard` → Pi's LAN IP (Settings → Local DNS → DNS Records)
- [ ] Verify end-to-end: open `http://hl-dashboard:8080` from another device on the home network
- [ ] Verify Tailscale access: open the dashboard from a device off the home network

---

## Phase 7 — Alerting

- [ ] Add failure notifications to `backend/cron.py` using [ntfy.sh](https://ntfy.sh) — a free push notification service requiring no account or API key. When `fetch_prices.py` or `dbt build` fails, POST to a private ntfy topic; the ntfy app on your phone receives the alert instantly. Optionally send a daily success notification too.

---
