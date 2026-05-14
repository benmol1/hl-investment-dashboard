# HL Investment Dashboard — Progress & To-Dos

*Last updated: 2026-05-14 20:15*

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

## Phase 4 — dbt Data Layer ✅ COMPLETE

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

## Phase 6 — Deployment ✅ COMPLETE

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
- **Port conflict**: Pi-Hole's web interface uses lighttpd on port 80, and Unifi Network Controller uses port 8080. The frontend container exposes on host port `2048`. Access the dashboard at `http://hl-dashboard:2048`.

### Tasks

#### Docker

- [x] Write `backend/Dockerfile` — Python slim + uv, runs `dbt deps` during build; entrypoint: `uvicorn app.main:app`
- [x] Write `cron/Dockerfile` — reuses backend image with overridden command: `python backend/cron.py`
- [x] Write `backend/cron.py` — standalone APScheduler script that runs `fetch_prices.py` then `dbt build` daily at 18:00; no FastAPI dependency
- [x] Remove APScheduler and `_run_daily_refresh` from `backend/app/main.py` — API becomes a pure read-only server
- [x] Write `frontend/Dockerfile` — multi-stage: Node build stage (`npm run build`) → Nginx alpine serving `dist/`; `nginx.conf` proxies `/api/` → `http://backend:8000/` and handles SPA routing
- [x] Write `docker-compose.yml` — three services (`backend`, `cron`, `frontend`); shared bind mount via `DATA_DIR` env var (defaults to `/srv/hl-dashboard/data`); frontend exposes host port 8080
- [x] Add `.dockerignore` — excludes `.venv`, `dbt/dbt_packages`, `dbt/target`, `data/`, `frontend/node_modules`
- [x] Strip dev-only deps (jupyter, matplotlib, ipykernel) from the backend/cron image — add a `[tool.uv]` dev group or use `--no-dev` flag
- [x] Install Docker Desktop on Windows dev machine
- [x] Test full Docker build locally (`docker compose up --build`)
- [x] Verify daily refresh fires correctly in the cron container (check logs)

#### Raspberry Pi setup

- [x] Install Docker + Docker Compose on the Pi
- [x] Create bind mount directory: `sudo mkdir -p /srv/hl-dashboard/data/imports/raw_transactions/{ISA,SIPP}`
- [x] Copy initial `hl_dashboard.duckdb` to `/srv/hl-dashboard/data/` (one-time seed from dev machine)
- [x] Clone repo to Pi and run `docker compose up -d`
- [x] Install Tailscale on the Pi (`curl -fsSL https://tailscale.com/install.sh | sh`) and authenticate
- [x] Verify end-to-end: open `http://192.168.1.220:2048` from another device on the home network
- [x] Verify Tailscale access: open the dashboard from a device off the home network

---

## Phase 7 — Notifications & Bot Interface ✅ COMPLETE

### 7a — Push Notifications (cron alerts) ✅ COMPLETE

- [x] Add failure notifications to `backend/cron.py` via Telegram bot — when any step of the daily refresh fails, send a message to your personal chat.
- [x] Add a daily success notification confirming the refresh ran cleanly (prices updated, dbt build passed).
- [x] Add a monthly summary notification: total portfolio value, change vs last month, and a brief breakdown by account.
- [x] Fix `dbt build` step in `cron.py` — `FileNotFoundError` because `"dbt"` wasn't on PATH in the container; replace with `Path(sys.executable).parent / "dbt"` so it resolves correctly in both Docker and local dev. Deploy with `docker compose up -d --build cron`.

### 7b — Two-Way Query Bot ✅ COMPLETE

- [x] Create a Telegram bot via BotFather; store the bot token and your chat ID in `.env` / Docker secrets.
- [x] Add `backend/bot/` — a long-polling Telegram bot service (using `python-telegram-bot`), structured as a package: `config.py`, `tools.py`, `executors.py`, `claude.py`, `handlers.py`, `__main__.py`.
- [x] Add a `bot` service to `docker-compose.yml` running `bot/` alongside the existing backend/cron/frontend services.
- [x] Add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `ANTHROPIC_API_KEY` to `.env` on the Raspberry Pi, then run `docker compose up -d --build bot`.
- [x] Wire the bot to the Claude API (Anthropic SDK) with tool use — expose the existing FastAPI endpoints as Claude tools so natural language messages like "what's my ISA up this month?" are translated into API calls and returned as readable answers. Falls back to a read-only DuckDB query tool for questions the API can't answer.
- [x] Restrict the bot to your own chat ID so it rejects messages from anyone else.
- [x] Audit number formatting in bot replies — ensure all pound figures (including those from the DuckDB fallback tool) consistently round to the nearest pound for amounts £10+.

### 7c — Chart Generation in Bot Replies ✅ COMPLETE

- [x] Research approach: generate charts server-side (e.g. with `matplotlib` or `plotly`) as PNG images and send via Telegram's `send_photo` API rather than as text.
- [x] Add a `generate_chart` tool that Claude can call — accepts a chart type (line, bar, donut) and a data payload, renders a PNG in memory, and returns a file path or byte buffer.
- [x] Implement at least two chart types to start: portfolio value over time (line) and current allocation (donut/pie).
- [x] Update `handlers.py` to detect when the bot response includes a chart and send it as a photo message rather than (or alongside) a text reply.
- [x] Test on iPhone — confirm images render at a readable size in the Telegram chat.
- [x] Show interim tool feedback in Telegram while the response is being generated (edits the "Thinking…" message to show which tools are being called).

---

## Phase 8 — Dashboard UI Improvements ✅ COMPLETE

- [x] Make the sidebar collapsible so the dashboard is usable on a mobile screen
- [x] Round all monetary values in the Holdings table to the nearest pound (no pennies)
- [x] Make all columns in the Holdings table sortable (name, value, cost basis, unrealised gain, weight, etc.)
- [x] Include cash balances alongside fund holdings in the Holdings table

---

## Phase 9 — Refresh Automation ⏳ IN PROGRESS

### Basic — shared drop folder ✅ COMPLETE

- [x] Set up a shared network folder on the Pi (e.g. via Samba) so HL CSV exports can be dropped directly from any device on the home network without using `scp`
- [x] The existing daily cron job already picks up files from the drop folders automatically — no further changes needed once the share is in place

### Advanced — automated HL download (research spike)

- [ ] Research using [BrowserUse](https://github.com/browser-use/browser-use) to automate logging in to the HL website and downloading transaction CSVs on a schedule
- [ ] Investigate credential security options — e.g. storing the HL password in a secrets manager or using a read-only HL API key if one exists, to avoid hardcoding credentials in config
- [ ] If viable, wire the downloader into `backend/cron.py` as the first step before `ingest_transactions.py`

### Cron Fixes ✅ COMPLETE

- [x] Change cron job schedule back to daily at 01:00 (was changed from the regular cadence during testing)
- [x] Investigate why the cron job timestamp logs in GMT rather than BST — Pi system clock is set to British Summer Time, so the container may not be inheriting the host timezone

---

## Phase 10 — User Accounts & Authentication (Research Spike)

Two motivations: (1) a demo/dummy dataset so the app can be shown to others without exposing real positions; (2) multi-user support so family members (e.g. brother, dad) can each have their own accounts with data isolated by user.

### Data model

- [ ] Research spike: decide on a user model — likely a `users` table with `id`, `username`, `hashed_password`, and a `role` (e.g. `owner`, `viewer`, `demo`).
- [ ] Add a `user_id` foreign key to the `accounts` table (ISA, SIPP) so every account belongs to a specific user.
- [ ] Assess dbt impact: marts and intermediate models may need to be filtered by `user_id` or kept user-agnostic with filtering pushed to the API layer (preferred — simpler dbt models).

### Demo dataset

- [ ] Create a script to generate a plausible synthetic dataset (transactions, prices, holdings) that mirrors the real schema but uses fake figures — stored as a separate DuckDB file or a flagged user account.
- [ ] Ensure the demo user is read-only and cannot trigger ingestion or refresh.

### Authentication

- [ ] Research options: simple JWT-based auth in FastAPI (e.g. `python-jose` + `passlib`) vs. a lightweight provider like Authelia in front of the Docker stack.
- [ ] Implement login flow: `POST /auth/login` returns a JWT; all other endpoints require a valid token.
- [ ] Add user context to API requests so each endpoint filters data to the authenticated user's accounts only.

### Frontend

- [ ] Add a login page to the React app (username + password form).
- [ ] Store JWT in memory (not localStorage) and attach it to all API requests.
- [ ] Handle token expiry gracefully — redirect to login on 401.

### Deployment

- [ ] Decide whether to expose the app publicly (requires HTTPS — e.g. Caddy reverse proxy with Let's Encrypt) or keep it Tailscale-only (simpler, no public exposure).

---
