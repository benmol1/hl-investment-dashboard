# HL Investment Dashboard — Progress & To-Dos

*Last updated: 2026-04-30*

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

---

## Morningstar Fund Codes ✅ MOSTLY COMPLETE

- [x] Ranmore Global Equity Investor (`IE00B61ZVB30`) → `0P000136HH`
- [x] Invesco Global ex-UK Enhanced Index Class Z (`GB00BZ8GWT74`) → `0P000184GO`
- [x] Baillie Gifford Managed Class B (`GB00BV0V1394`) → `0P00000QWU`
- [x] Baillie Gifford UK Equity Alpha Class B (`GB0005858195`) → `0P00000QWH`
- [x] HL UK Income Fund Class A (`GB0032033127`) → `0P00000STJ`
- [x] IFSL Evenlode Income Class B (`GB00BD0B7C49`) → `0P0001BH5V`
- [x] Liontrust UK Smaller Companies Class I (`GB00B8HWPP49`) → `0P00015BZ7`
- [x] Rathbone Global Opportunities Inclusive R Acc — ISIN resolved (`GB0030349095`) → `0P00000HST`; price fetch returning no data (see outstanding issues)
- [ ] **L&G Global 100 Index Class C** (`0P000102M0`) — Morningstar API returning no data; code may be stale or fund may have been renamed/merged
- [ ] **Rathbone Global Opportunities Inclusive R Acc** — `0P00000HST` code is correct but Morningstar API returns no prices; this may be a legacy share class no longer published via the API. Consider using the Class I or Class S price as a proxy.

---

## Immediate Next Steps (before using the dashboard)

- [x] ~~Ingest SIPP transactions~~ — done via new raw import pipeline
- [x] ~~Find Morningstar code for Ranmore~~ — resolved
- [ ] **Resolve L&G Global 100 price data** — inspect the Morningstar Network tab on `morningstar.co.uk` for the current token/endpoint, or check if fund was renamed
- [ ] **Resolve Rathbone Inclusive price data** — confirm whether `0P00000HST` is queryable; if not, decide whether to use the I or S class price as a proxy and update `dim_funds.csv`
- [ ] **Backfill all historical prices** — run a full backfill for funds that have codes but limited history:
  ```
  python backend/scripts/fetch_prices.py --backfill 2017-01-01
  ```
- [ ] **Validate unit totals** — cross-check unit counts from transactions against the current HL portfolio page to confirm ingestion is correct

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

**To run dbt:**
```bash
cd dbt
dbt seed --profiles-dir .   # load dim_date (first time only)
dbt run  --profiles-dir .   # build all models
dbt test --profiles-dir .   # run all 112 tests
```

---

## Phase 5 — Wire API to dbt Marts

- [ ] Update `GET /portfolio/value` to query `mart_daily_portfolio_value` instead of inline CTEs
- [ ] Update `GET /portfolio/contributions` to query `mart_portfolio_contributions`
- [ ] Update `GET /portfolio/holdings` to query `mart_current_holdings`
- [ ] Update `GET /portfolio/performance` to query `mart_daily_portfolio_value` + `mart_benchmark_levels`
- [ ] Update `GET /portfolio/allocation` to query `int_daily_fund_values` (point-in-time filter)
- [ ] Update `GET /funds/{id}/performance` to query `int_daily_fund_values` + `mart_benchmark_levels`
- [ ] Add `dbt run` to the APScheduler daily job (runs after `fetch_prices.py`)
- [ ] Remove old `v_holdings` / `v_portfolio_value` references from any remaining Python code

---

## Phase 6 — Deployment

- [ ] Write `docker-compose.yml` — FastAPI service + Nginx serving React build
- [ ] Write `Dockerfile` for the backend
- [ ] Write `Dockerfile` for the frontend build + Nginx
- [ ] Test Docker build locally
- [ ] Deploy to Raspberry Pi
- [ ] Configure home network DNS so it's accessible at a friendly local address
- [ ] (Optional) Set up Tailscale for access outside the home network

---

## Open Questions

| # | Question |
|---|----------|
| 1 | ~~Does the SIPP export use the same CSV column format as the ISA?~~ — Confirmed: same column structure, same 5-line metadata header. ✅ |
| 2 | Morningstar API token (`9vehuxllxs`) is unofficial — if price fetches start failing, inspect the Network tab on morningstar.co.uk to find the current token |
| 3 | Remote access outside the home network needed? If yes, add Tailscale to Phase 6 |
| 4 | Should the daily price-fetch cron run inside the backend container or as a separate Docker service? |
| 5 | L&G Global 100 (`0P000102M0`) returns no price data from Morningstar API — has this fund been renamed or merged? |
| 6 | Rathbone Global Opportunities Inclusive R Acc (`0P00000HST`) — is this share class still actively priced, or should we proxy it with I or S class NAV? |
