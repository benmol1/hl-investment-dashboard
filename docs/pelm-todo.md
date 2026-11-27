# PELM Will Trust — To-Do

*Feature-scoped list. Main project to-dos live in [TODO.md](../TODO.md).*
*Phases 1–7 done. Second pack (Nov 2026) loaded: 38 months of valuations, four sub-ledgers, three B&C performance reports. Q3 2025 – Q1 2026 returns reconcile to B&C within 0.03pp; inception to May 2026 now 21.95% (B&C 23.4%; the rest is months without a dividends ledger).*
*Plan: [docs/pelm-integration-plan.md](pelm-integration-plan.md) §7 · Last updated: 2026-11-27*

---

## Phase 0 — Unblock

- [x] ~~Email Alastair: do the month-end valuations include income?~~ — answered by the second pack: income stays in the valuation until paid out by BACS (plan §7.1)
- [x] ~~Email Alastair: request the deposit account ledger~~ — not needed: the deposit account is inside the valuation (plan §7.1)
- [x] Valuations file keeps arriving in the same two-column format (confirmed by the Nov 2026 pack)
- [x] ~~Agree the reference total-return figure for a validation check~~ — dropped, see Phase 4

*Remaining questions for Alastair are in Phase 8.*

---

## Phase 1 — Input file

- [x] Create `data/pelm/pelm_monthly.csv` (gitignored; read by a macro, not a dbt seed — see plan §3.2) with columns `month_end_date,value_gbp,external_flow_gbp`. Holds the 33 real months; example layout in `data/examples/pelm_monthly_example.csv`
- [x] Convert all 33 rows from `pelm-inputs/C070982 End of Month Valuations.xlsx`
- [x] Add external flows read off the ledger PDF:
  - [x] 2023-10-31 → `+4774.78` (transfers from C028801 / M028801, 24 Oct 2023)
  - [x] 2025-05-30 → `-157000.00` (BACS Payment *3850, 21 May 2025)
  - [x] Re-scan the ledger (done: only other external items are the 21 Sep 2023 cash and in-specie transfers, before the first valuation) for any flow missed — everything else should be internal (trades, deposit transfers) and net to zero
- [x] Decide whether the £20,679.81 (confirmed: 21 Sep is before the 29 Sep opening valuation, so it is inside it; no flow row) transfer of 21 Sep 2023 is inside the 29 Sep opening valuation (it should be — confirm, don't double-count)
- [x] Sign convention (positive in, negative out) recorded in `data/pelm/README.md` and the example README
- [x] Mention `pelm_monthly.csv` in `data/examples/README.md`

---

## Phase 2 — dbt

- [x] Load `pelm_monthly.csv` via the `pelm_monthly_source` macro (empty table if the file is absent)
- [x] Add `dbt/models/base/base__pelm_valuations.sql` + `.yml` — typed table over the CSV
- [x] Add `PELM` row to `dim_account` with `account_open_date = 2023-09-29`
- [x] Add `data_grain` column to `dim_account` (`'daily'` for ISA/SIPP, `'monthly'` for PELM)
- [x] Add PELM union CTE to `mart_portfolio_snapshot_monthly` (`value_gbp` → `month_end_value_gbp`, `external_flow_gbp` → `monthly_inflows_gbp`, null net fund purchases)
- [x] Confirm `mart_portfolio_returns_monthly` picks PELM up with no changes
- [x] Confirm `mart_benchmarks_monthly` comparison works for PELM (account-independent; the account comparison happens in the API — Phase 3)
- [x] Confirm `mart_portfolio_value_daily` / `mart_holdings_latest` / `mart_fund_*` return zero PELM rows rather than erroring
- [x] Add dbt tests: unique+not_null on `(account_name, year_month)` in the snapshot mart; not_null on PELM `month_end_value_gbp`

---

## Phase 3 — Backend

- [x] Widen `Optional[Literal["ISA", "SIPP"]]` to include `"PELM"` across the five signatures in `backend/app/routers/portfolio.py`
- [x] Read `data_grain` from `dim_account` and return an explicit "not available at this grain" response for PELM on `/portfolio/holdings`, `/portfolio/allocation` and the daily value series
- [x] Leave PELM out of `/portfolio/contributions` (hardcoded ISA/SIPP columns at `portfolio.py:150`) — trust, not a contribution account
- [x] Check the aggregate (no-account-filter) paths still behave now a third account exists — especially the BMV-weighted returns aggregation (decision: the no-account aggregate is ISA + SIPP only; PELM appears only when selected)
- [x] Check the Telegram bot's semantic layer surfaces PELM sensibly, and that `query_database` mart/dim restrictions still hold (named tools stay ISA/SIPP; PELM reachable via `query_database`, mentioned in the system prompt; monthly summary excludes PELM)

---

## Phase 4 — Frontend & validation

- [x] Add PELM to the account selector on Overview and Benchmarks (explicit opt-in only; Benchmarks supports multi-select and benchmark toggles)
- [x] Render PELM as a monthly step/point series on the value chart (not an interpolated daily line)
- [x] Hide or disable PELM on Holdings, Fund Performance, FY Contributions (Transactions later got its own PELM ledger view, Phase 6)
- [x] ~~Write the single validation check~~ — **dropped (2026-11-23):** its failure modes are covered by the parser's flow reconciliation against the ledger and the dbt uniqueness / not-null tests
- [x] Ran ruff format/check over all changed Python (the repo has older unformatted files, e.g. `backend/cron.py`, left alone)

---

## Phase 5 — Process

- [x] Document the quarterly update steps in `README.md` (now all on the Pi; one image rebuild needed after deploying the `pdfplumber` dependency)
- [x] Confirm the nightly cron does not fail on PELM: `dbt build` reads the bind-mounted file, and is verified to pass with the file present and absent
- [x] `pelm-inputs/` is gitignored (only its README and `.gitignore` are tracked)

---

## Phase 6 — PELM transactions view (built 2026-11-23)

Caveats shown on the page: no dividends/fees in the ledger; in-specie transfers have quantity but no value; ledger omits the deposit account.

- [x] Parse the ledger PDF by word position (`backend/scripts/parse_pelm_ledger.py`; `pdfplumber` is a main dependency so it also runs in the cron container, with the PDF dropped into `data/pelm/`) into gitignored `data/pelm/pelm_transactions.csv`; refuses to write unless opening + credits − debits = closing (verified: 132 rows, £817,243.38 each side)
- [x] Add `base__pelm_transactions` and `fct_pelm_transactions` (separate from HL's `fct_transactions`), via the same tolerant macro
- [x] Reconcile ledger external flows against the hand-entered `external_flow_gbp` (done by the script; currently agree)
- [x] Backend: `/pelm/transactions` (deposit sweeps hidden unless `include_internal`)
- [x] Frontend: PELM Trust toggle on the Transactions page with its own columns and caveat note

## Phase 7 — Income, fees and return reconciliation (built 2026-11-27)

Plan §7. Months without a dividends ledger are flagged, not estimated (decision 2026-11-27).

- [x] Append Jun–Oct 2026 valuations; `pelm_monthly.csv` reduced to the spreadsheet's two columns (flows now come from the ledger)
- [x] Parser reads all `C070982 Ledger*.pdf` (subfolders too), splits capital / dividends / income / fees statements, balances each, dedupes overlaps, checks opening-balance continuity, writes `pelm_ledger_coverage.csv`
- [x] New tx types: `DIVIDEND`, `INTEREST`, `FX_COMMISSION`, `FEE`, `FEE_VAT`, `INCOME_DISTRIBUTION`, `SETTLEMENT_TRANSFER`, `BALANCE_ADJUSTMENT`; the £108 "TO SETTLEMENT" is now internal
- [x] dbt: tolerant CSV macro; PELM flows derived from ledger external flows; `int_pelm_ledger_coverage_monthly`; `cash_flow_coverage_indicator` on snapshot and returns marts
- [x] dbt: `mart_pelm_income_monthly` and `mart_pelm_return_reconciliation`, plus the singular test `assert_pelm_reported_returns_reconcile` (0.1pp). All three quarters pass at ≤0.03pp
- [x] Hand-entered `pelm_reported_returns.csv` (Q3 2025, Q4 2025, Q1 2026)
- [x] API: `ledger` + `category` on `/pelm/transactions`; `/pelm/income`; `/pelm/reconciliation`; `incomplete_flow_dates` on `/portfolio/performance`; `pelm_income_ledgers` ingest-log row; bot prompt names the new marts
- [x] Frontend: Overview Income & Fees card and B&C reconciliation table; Transactions new types, ledger column, updated caveat; Benchmarks caveat and shading for incomplete months; ingest-log label
- [x] Tests: parser unit tests (classification, dedupe, continuity, gap adjustment) and API tests; 89 pass; dbt 248 nodes pass
- [ ] Check the new Overview cards and Benchmarks shading in a browser (desktop and phone width)
- [ ] On the Pi: rebuild images (`docker compose up -d --build`), copy the pack into `data/pelm/20261127/`, copy the updated `pelm_monthly.csv` and new `pelm_reported_returns.csv`, run the parser, `dbt build`

---

## Phase 7b — Quarterly returns and best-estimate toggle (plan §7.6)

- [x] Reconciliation table moved to its own PELM Reconciliation page
- [x] `/portfolio/returns/quarterly` and a quarterly total-returns table on Benchmarks (every quarter, benchmarks over the same months, partial quarters marked)
- [x] `estimated_monthly_return` / `avg_income_uplift` in `mart_portfolio_returns_monthly`; `estimate=true` on `/portfolio/performance` and the quarterly endpoint; Actual / Best estimate toggle on Benchmarks
- [ ] Decide whether to keep the estimate method: it gives 30.5% inception to May 2026 against B&C's 23.4% (the recent income payout rate overstates earlier months)

## Phase 8 — Ask Barratt & Cooke (plan §7.5)

- [ ] Dividends, income and fees ledgers for Sep 2023 – Jun 2025 (closes the remaining gap to 23.4%)
- [ ] All four ledgers for Apr – Oct 2026, to match the new valuations
- [ ] Formal total-return reports for Q4 2023 – Q2 2025, so the reconciliation test covers the full history
- [ ] Is the custody fee annual or quarterly? (one charge in nine months; no fees page in Q3/Q4 2025)

## Deferred — do not do yet

- Security-level PELM holdings — no valued position data exists in the source
- Parsing the costs/charges PDFs — fees are already netted into the valuations; custody fee now comes from the fees ledger
- Parsing tax certificates and performance-report xlsx — a hand-typed headline figure a quarter is enough
- An xlsx ingest script — three hand-typed rows a quarter (ledger transcription is now Phase 6)
- PELM in the nightly cron — source updates quarterly, by email, by hand
