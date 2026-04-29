# HL Investment Dashboard — Progress & To-Dos

*Last updated: 2026-04-29*

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

## Immediate Next Steps (before Phase 2)

- [ ] **Ingest SIPP transactions** — drop SIPP CSV into `data/imports/` and run:
  ```
  python backend/scripts/ingest_transactions.py --file data/imports/<sipp_filename>.csv --account SIPP
  ```
- [ ] **Find Morningstar code for Ranmore Global Equity** — the only currently-held fund missing a `morningstar_code`. Look it up on [morningstar.co.uk](https://www.morningstar.co.uk), then update the funds table:
  ```sql
  UPDATE funds SET morningstar_code = '<code>' WHERE id = 'IE00B61ZVB30';
  ```
- [ ] **Backfill all historical prices** — once Ranmore's code is added, run:
  ```
  python backend/scripts/fetch_prices.py --backfill 2017-01-01
  ```
- [ ] **Validate unit totals** — cross-check the unit counts derived from transactions against your current HL portfolio page to confirm the ingestion is correct

---

## Phase 2 — Backend API

- [ ] Create `backend/app/main.py` — FastAPI app skeleton
- [ ] Create `backend/app/db.py` — DuckDB connection management
- [ ] Create `backend/app/models.py` — Pydantic response schemas
- [ ] Implement API endpoints:
  - [ ] `GET /portfolio/value?from=&to=` — time-series of total portfolio value
  - [ ] `GET /portfolio/allocation` — current allocation by fund
  - [ ] `GET /funds/{id}/performance` — fund value indexed to 100 at first purchase, with benchmark overlay
  - [ ] `GET /contributions` — cumulative contributions vs portfolio value over time
  - [ ] `GET /transactions` — paginated, filterable transaction log
- [ ] Add APScheduler or cron inside the app to run `fetch_prices.py` daily at ~18:00

---

## Phase 3 — React Frontend

- [ ] Scaffold with Vite + React + TypeScript (`frontend/`)
- [ ] Install Recharts for charting
- [ ] Build pages:
  - [ ] Portfolio Overview — total value line chart + allocation donut
  - [ ] Contributions vs Growth — stacked area chart
  - [ ] Fund Performance — per-fund indexed line chart with benchmark overlay
  - [ ] Benchmark Comparison — portfolio vs FTSE 100, S&P 500, Nasdaq
  - [ ] Holdings Table — current units, price, value, cost basis, unrealised gain
  - [ ] Transaction Log — searchable/filterable table
- [ ] Wire all pages up to FastAPI endpoints
- [ ] Test on mobile layout

---

## Phase 4 — Deployment

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
| 1 | Does the SIPP export use the same CSV column format as the ISA? (Parser should work, but worth confirming) |
| 2 | Morningstar API token (`9vehuxllxs`) is unofficial — if price fetches start failing, inspect the Network tab on morningstar.co.uk to find the current token |
| 3 | Remote access outside the home network needed? If yes, add Tailscale to Phase 4 |
| 4 | Should the daily price-fetch cron run inside the backend container or as a separate Docker service? |
