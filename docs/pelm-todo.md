# PELM Will Trust — To-Do

*Feature-scoped list. Main project to-dos live in [TODO.md](../TODO.md).*
*Plan: [docs/pelm-integration-plan.md](pelm-integration-plan.md) · Last updated: 2026-09-11*

---

## Phase 0 — Unblock

- [ ] Email Alastair: do the month-end valuations include accrued/uninvested income, or is income swept to the deposit account? (decides whether PELM returns are comparable to ISA/SIPP — see plan §1 finding 3)
- [ ] Email Alastair: request the deposit account ledger (16 transfers went into it, no visibility)
- [ ] Email Alastair: confirm the valuations file will keep arriving quarterly in the same two-column format
- [ ] Once answered, agree the reference total-return figure the validation check asserts against (currently 23.4%)

*Phases 1–4 can start before these land; only the validation check in Phase 4 is truly blocked.*

---

## Phase 1 — Input file

- [ ] Create `data/imports/pelm_monthly.csv` with columns `month_end_date,value_gbp,external_flow_gbp`
- [ ] Convert all 33 rows from `pelm-inputs/C070982 End of Month Valuations.xlsx`
- [ ] Add external flows read off the ledger PDF:
  - [ ] 2023-10-31 → `+4774.78` (transfers from C028801 / M028801, 24 Oct 2023)
  - [ ] 2025-05-30 → `-157000.00` (BACS Payment *3850, 21 May 2025)
  - [ ] Re-scan the ledger for any flow missed — everything else should be internal (trades, deposit transfers) and net to zero
- [ ] Decide whether the £20,679.81 transfer of 21 Sep 2023 is inside the 29 Sep opening valuation (it should be — confirm, don't double-count)
- [ ] Add a short README note or header comment recording the sign convention: positive in, negative out

---

## Phase 2 — dbt

- [ ] Register `pelm_monthly.csv` as a dbt seed (same pattern as `seed_date.csv`)
- [ ] Add `dbt/models/base/base__pelm_valuations.sql` + `.yml` — typed view over the seed
- [ ] Add `PELM` row to `dim_account` with `account_open_date = 2023-09-29`
- [ ] Add `data_grain` column to `dim_account` (`'daily'` for ISA/SIPP, `'monthly'` for PELM)
- [ ] Add PELM union CTE to `mart_portfolio_snapshot_monthly` (`value_gbp` → `month_end_value_gbp`, `external_flow_gbp` → `monthly_inflows_gbp`, null net fund purchases)
- [ ] Confirm `mart_portfolio_returns_monthly` picks PELM up with no changes
- [ ] Confirm `mart_benchmarks_monthly` comparison works for PELM
- [ ] Confirm `mart_portfolio_value_daily` / `mart_holdings_latest` / `mart_fund_*` return zero PELM rows rather than erroring
- [ ] Add dbt tests: unique+not_null on `(account_name, year_month)` in the snapshot mart; not_null on PELM `month_end_value_gbp`

---

## Phase 3 — Backend

- [ ] Widen `Optional[Literal["ISA", "SIPP"]]` to include `"PELM"` across the five signatures in `backend/app/routers/portfolio.py`
- [ ] Read `data_grain` from `dim_account` and return an explicit "not available at this grain" response for PELM on `/portfolio/holdings`, `/portfolio/allocation` and the daily value series
- [ ] Leave PELM out of `/portfolio/contributions` (hardcoded ISA/SIPP columns at `portfolio.py:150`) — trust, not a contribution account
- [ ] Check the aggregate (no-account-filter) paths still behave now a third account exists — especially the BMV-weighted returns aggregation
- [ ] Check the Telegram bot's semantic layer surfaces PELM sensibly, and that `query_database` mart/dim restrictions still hold

---

## Phase 4 — Frontend & validation

- [ ] Add PELM to the account selector on Overview and Benchmarks
- [ ] Render PELM as a monthly step/point series on the value chart (not an interpolated daily line)
- [ ] Hide or disable PELM on Holdings, Transactions, Fund Performance, FY Contributions
- [ ] Write the single validation check: chain-linked TWR over the full seed reproduces the agreed reference figure (blocked on Phase 0)
- [ ] Run `uv run ruff format .` and `uv run ruff check . --fix`

---

## Phase 5 — Process

- [ ] Document the quarterly update steps in `README.md` (or link to plan §4)
- [ ] Confirm the nightly cron skips PELM and does not fail on unchanged data
- [ ] Decide whether `pelm-inputs/` should be gitignored (contains third-party financial statements)

---

## Deferred — do not do yet

- Security-level PELM holdings — no valued position data exists in the source
- Parsing the costs/charges PDFs — fees are already netted into the valuations
- An xlsx ingest script or ledger PDF parser — three hand-typed rows a quarter
- PELM in the nightly cron — source updates quarterly, by email, by hand
