# Kimball Dimensional Modelling — Key Principles & Conventions

Reference guide for applying Kimball-style data warehouse design to this project.

*Last modified: 2026-05-01 12:22*

---

## Core Modelling Principles

- **Star schema over snowflake.** A central fact table joins to denormalized dimension tables. Flatten hierarchies (e.g. Region, Country) directly into the dimension row — avoid normalizing into sub-dimension tables (snowflaking) unless storage is a serious concern.

- **Design around business processes, not source systems.** Identify core business events first (a sale, a transaction, a holding snapshot), then build dimensions around those. The warehouse should reflect how the business operates, not how the source system is structured.

- **Declare grain explicitly and keep it atomic.** Every fact table has a single grain — the lowest meaningful level of detail (e.g. "one row per order line item"). All facts in the table must live at that same grain. Aggregated grain loses analytical flexibility.

- **Facts are numeric and additive.** Fact table columns should be measurements you can sum, average, or count across dimensions. Semi-additive and non-additive facts (e.g. balances, prices) need special handling — document them explicitly.

- **Conformed dimensions enable cross-process analysis.** Reuse the same dimension table (with identical column names, grain, and definitions) across multiple fact tables. A `dim_date` joined to both a holdings fact and a transactions fact means those two processes can be compared consistently.

- **Slowly Changing Dimensions (SCDs) must be handled deliberately.** When a dimension attribute changes (e.g. a fund changes sector classification), decide whether to overwrite (Type 1), add a new row with effective dates (Type 2), or add a new attribute column (Type 3). Type 2 is the Kimball default for preserving history.

---

## Surrogate vs Natural Keys

- **Dimension tables use surrogate keys as their primary key.** Every dimension gets a simple, sequential integer surrogate key (e.g. `customer_key INT`). It must be meaningless — no encoded logic, no composite keys, no alphanumeric smart keys. The date dimension is a common exception (an integer like `20240101` is acceptable).

- **Natural/business keys are attributes, not primary keys.** Source system IDs (account numbers, product codes) are stored as regular columns in the dimension for traceability and SCD tracking, but joins between fact and dimension tables always go through the surrogate key. This insulates the warehouse from source system changes.

---

## Naming Conventions

### Tables

| Layer | Prefix | Example |
|---|---|---|
| Staging | `stg_` | `stg_hl_transactions` |
| Intermediate | `int_` | `int_portfolio_monthly` |
| Dimension | `dim_` | `dim_fund` |
| Fact | `fact_` | `fact_holdings` |

### Columns

| Element | Pattern | Example | Notes |
|---|---|---|---|
| Surrogate key (dimension PK) | `<dim>_key` | `fund_key` | Sequential integer |
| Foreign key (fact table) | `<dim>_key` | `fund_key` | Must match dimension PK name exactly — enables joins on same name |
| Natural / business key | `<source>_id` or `_business_key` | `hl_fund_id`, `isin_business_key` | Stored as attribute, never used in joins |
| Timestamp | `<event>_at` | `created_at`, `updated_at` | Always UTC |
| Date | `<event>_date` | `transaction_date`, `valuation_date` | Date type, no time component |
| Boolean | `is_<state>` / `has_<attr>` | `is_active`, `has_dividend` | Makes type unambiguous |
| Monetary amount | `<measure>_<currency>` | `value_gbp`, `gain_loss_gbp` | Always suffix with currency code |

### General Rules

- **`snake_case` throughout, all lowercase.** No camelCase, no mixed case.
- **Avoid abbreviations.** `monthly_recurring_revenue` not `mrr`; `transaction_date` not `txn_dt`.
- **Use business vocabulary, not source system names.** If the business says "fund", don't use `product` or `instrument` just because the source does.
- **Be explicit about units.** Monetary columns always carry a currency suffix. Quantities should indicate the unit where ambiguous (e.g. `quantity_units`, `duration_days`).

---

## Gap Analysis — Current dbt Project vs Kimball

### No dimension tables exist
`funds` and `accounts` are used as raw sources with natural keys (`id` = ISIN string, `id` = "ISA"/"SIPP" string) directly throughout every intermediate and mart model. There is no `dim_fund` or `dim_account` in the dbt models layer. `dim_date` exists only as a seed and lacks a proper integer surrogate key column.

### No surrogate keys — natural keys used everywhere for joins
`fund_id` (ISIN) and `account_id` ("ISA"/"SIPP") are used as both the de-facto primary key and as foreign keys across all 14 models. Every join in the project uses a business/natural key. This couples every model to source system identifiers. *(Full surrogate key wiring is deferred — tracked separately.)*

### No fact tables or fact layer
All consumer-facing models sit in a flat `marts/` folder with a `mart_` prefix. The project has no explicit fact layer. `mart_current_holdings` is a true periodic snapshot fact (fund × account × day grain, derived directly from intermediate models); the rest are aggregated reporting tables that belong in a marts layer downstream from the fact layer.

### No `fact_transactions`
`stg_transactions` is referenced directly by intermediate models. There is no mart-layer fact table for transaction data — consumers that want queryable transactions have no clean endpoint short of hitting staging.

### Generic `date` column used across multiple models
`stg_prices`, `stg_benchmarks`, `int_daily_unit_balances`, `int_daily_fund_values`, `mart_daily_portfolio_value`, and `mart_portfolio_contributions` all have a bare `date` column. It means different things in each model (price date, market date, valuation date).

### Other column naming issues
- `benchmarks.level` / `stg_benchmarks.level` — ambiguous; should be `index_level`
- `stg_transactions.id` — generic name; this is an MD5 content hash and should be renamed `transaction_id`
- Source tables `funds.id` and `accounts.id` use bare `id` — should be aliased to `fund_id` / `account_id` in dimension models

---

## Target State — Model Structure

```
seeds/
  dim_date                          ← existing seed; add date_key column

models/
  staging/                          ← unchanged
    stg_transactions
    stg_prices
    stg_benchmarks

  intermediate/                     ← unchanged
    int_trade_unit_deltas
    int_cumulative_unit_balances
    int_daily_unit_balances
    int_fund_cost_basis
    int_daily_fund_values
    int_daily_contributions
    int_account_month_spine

  dimensions/                       ← new folder
    dim_fund                        ← new (surrogate fund_key + ISIN natural key)
    dim_account                     ← new (surrogate account_key + ISA/SIPP natural key)

  facts/                            ← new folder
    fact_transactions               ← new (atomic event grain; one row per transaction)
    fact_daily_holdings             ← renamed from mart_current_holdings
                                       (periodic snapshot; one row per account × fund × date)

  marts/                            ← existing folder; all models keep mart_ prefix
    mart_daily_portfolio_value      ← unchanged (aggregate rollup of fact_daily_holdings)
    mart_portfolio_contributions    ← unchanged (joins portfolio value + contributions)
    mart_monthly_snapshot           ← unchanged (monthly rollup)
    mart_portfolio_returns          ← unchanged (Modified Dietz calculations)
    mart_benchmark_levels           ← unchanged for now (deferred)
```

**Why this split between facts and marts:**
- Facts sit at the atomic or snapshot grain closest to the source. `fact_daily_holdings` is the per-fund daily snapshot; `fact_transactions` is the per-transaction event. They are the stable foundation.
- Marts are derived, aggregated, or analytically enriched tables built on top of facts. `mart_daily_portfolio_value` rolls up holdings across funds; `mart_portfolio_returns` adds Modified Dietz calculations. They change shape as reporting needs evolve without touching the fact layer.

---

## Migration Plan

Each TODO is independently executable. Work through them in order as later steps depend on earlier ones.

---

### ✅ TODO 1 — Create `dim_fund` *(completed 2026-05-01 12:22)*

Create `models/dimensions/dim_fund.sql` sourced from `source('hl_dashboard', 'funds')`.

- Add a sequential integer surrogate key: `row_number() over (order by id) as fund_key`
- Alias `id` as `fund_id` (the ISIN natural key, stored as an attribute)
- Include all other fund attributes (name, Morningstar code)
- Add a `.yml` with `unique` + `not_null` tests on `fund_key` and `fund_id`
- Add a `dimensions:` folder to `dbt_project.yml` materialized as `table`

---

### ✅ TODO 2 — Create `dim_account` *(completed 2026-05-01 12:22)*

Create `models/dimensions/dim_account.sql` sourced from `source('hl_dashboard', 'accounts')`.

- Add surrogate key: `row_number() over (order by id) as account_key`
- Alias `id` as `account_id` (natural key, stored as attribute)
- Add `.yml` with `unique` + `not_null` tests on `account_key` and `account_id`

---

### ✅ TODO 3 — Add `date_key` to `dim_date` seed *(completed 2026-05-01 12:22)*

The `dim_date` seed has no integer surrogate key. Kimball's standard for date dimensions is an integer in `YYYYMMDD` format.

- Add a `date_key` column to the seed CSV: `cast(strftime(date, '%Y%m%d') as integer)`
- Add `date_key: integer` to the seed column types in `dbt_project.yml`
- Add `unique` + `not_null` tests on `date_key` in the seed `.yml`

---

### ✅ TODO 4 — Create `facts/` folder and rename `mart_current_holdings` → `fact_daily_holdings` *(completed 2026-05-01 12:22)*

`mart_current_holdings` is a true Kimball periodic snapshot fact (grain: account × fund × date). Move it to a new `facts/` folder under its new name.

- Create `models/facts/` directory
- Rename `mart_current_holdings.sql` → `fact_daily_holdings.sql` and `mart_current_holdings.yml` → `fact_daily_holdings.yml`
- Update the `name:` field and all descriptions in the `.yml`
- Update `dbt_project.yml` to add `facts: +materialized: table`
- No `ref()` calls in other models currently point to `mart_current_holdings`, so no downstream updates needed

---

### ✅ TODO 5 — Create `fact_transactions` *(completed 2026-05-01 12:22)*

Create `models/facts/fact_transactions.sql` as the mart-layer representation of transaction data. Carries the `fund_key` and `account_key` foreign keys from the dimension models (TODOs 1 & 2 must be done first).

- Source from `{{ ref('stg_transactions') }}`
- Join to `dim_fund` on `fund_id` to bring in `fund_key` and `fund_name`
- Join to `dim_account` on `account_id` to bring in `account_key`
- Select: `transaction_id`, `fund_key`, `account_key`, `fund_id`, `account_id`, `trade_date`, `settle_date`, `transaction_type`, `transaction_subtype`, `quantity`, `value_gbp`, `is_trade`, `is_contribution`
- Declare grain in `.yml`: one row per transaction (each unique `transaction_id`)

---

### ✅ TODO 6 — Rename the generic `date` column to context-specific names *(completed 2026-05-01 12:22)*

Replace the bare `date` column with a descriptive name in every model that uses it.

| Model | Old column | New column |
|---|---|---|
| `stg_prices` | `date` | `price_date` |
| `stg_benchmarks` | `date` | `market_date` |
| `int_daily_unit_balances` | `date` | `valuation_date` |
| `int_daily_fund_values` | `date` | `valuation_date` |
| `mart_daily_portfolio_value` | `date` | `valuation_date` |
| `mart_portfolio_contributions` | `date` | `valuation_date` |
| `fact_daily_holdings` | `date` | `valuation_date` |

Note: ASOF JOINs in `int_daily_fund_values` use `p.date <= h.date` — update both sides when renaming.

---

### ✅ TODO 7 — Rename `level` → `index_level` in benchmarks *(completed 2026-05-01 12:22)*

In `stg_benchmarks.sql` and `stg_benchmarks.yml`, rename `level` → `index_level`. Update `mart_benchmark_levels` and its `.yml` to match.

---

### ✅ TODO 8 — Rename `stg_transactions.id` → `transaction_id` *(completed 2026-05-01 12:22)*

Rename `id` to `transaction_id` in:
- `sources.yml` (source column description)
- `stg_transactions.sql` and `stg_transactions.yml`

Document in the `.yml` that `transaction_id` is an MD5 content-hash (a natural deduplication key, not a sequential integer surrogate).

---

### ✅ TODO 9 — Alias `funds.id` and `accounts.id` in dimension models *(completed 2026-05-01 12:22)*

The source tables use bare `id`. The dimension models created in TODOs 1 & 2 should alias these clearly:

- `dim_fund.sql`: `id as fund_id`
- `dim_account.sql`: `id as account_id`
- Update `sources.yml` column descriptions to note the alias convention

---

### ✅ TODO 10 — Add explicit grain declarations to all fact `.yml` files *(completed 2026-05-01 12:22)*

Each fact model's `.yml` description should open with a one-line grain statement. Example format:

```
Grain: one row per (account_id, fund_id, valuation_date).
```

Models to update: `fact_daily_holdings`, `fact_transactions`.
