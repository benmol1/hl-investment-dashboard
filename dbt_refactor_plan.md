# dbt Refactor Plan — HL Investment Dashboard

*Status: Complete*
*Date: 2026-04-30*

---

## Goals

1. Replace the ad-hoc SQL scattered across Python routers and DuckDB views with a structured set of dbt models that have documented lineage, field descriptions, and automated tests.
2. Surface every business rule (unit delta direction, cost basis method, ASOF forward-fill) as named, testable objects rather than inline CTEs that repeat across five endpoints.
3. Keep DuckDB as the storage layer — `dbt-duckdb` runs natively against it, no infrastructure change.
4. Preserve the FastAPI endpoints unchanged — the mart models replace the inline SQL but the API signatures stay the same.

---

## Current State — What Needs Moving

### Raw source tables (seed / ingest, not changing)

| Table | Source | Notes |
|---|---|---|
| `transactions` | `ingest_transactions.py` CSV parse | Core fact table |
| `prices` | `fetch_prices.py` → Morningstar | Fund NAV in pence |
| `benchmarks` | `fetch_prices.py` → yfinance | Index close levels |
| `accounts` | `setup_db.py` seed | 2-row lookup (ISA, SIPP) |
| `funds` | `setup_db.py` seed | ISIN → name, Morningstar code |
| `dim_date` | `dim_date.csv` → **dbt seed** | Date spine with UK financial year; moved from `data/imports/` to `dbt/seeds/` |
| `transaction_type_mapping` | `setup_db.py` seed | Reference pattern → type |

### Analytical views (will be replaced by dbt models)

| View | Problem |
|---|---|
| `v_holdings` | Not account-aware — collapses ISA+SIPP; breaks the account filter |
| `v_portfolio_value` | Built on the broken `v_holdings`; not used by the API |

### Inline SQL in Python routers (the main problem)

Each of the five portfolio endpoints and the two fund endpoints re-implements the same CTEs:

- **`delta` CTE** — unit direction logic (`value_gbp < 0 → buy, else sell`). Appears in: `portfolio/value`, `portfolio/contributions`, `portfolio/holdings`, `portfolio/performance`, `funds/{id}/performance`. Five copies.
- **`running` CTE** — window function for cumulative units per `(account_id, fund_id, trade_date)`. Same five places.
- **ASOF JOIN pattern** — forward-fill unit balance to every price date. Three copies.
- **Cost basis CTEs** — `buy_cost` and `sell_proceeds` sub-queries only in `/holdings`. The method (total cost minus proceeds) is undocumented.
- **`daily_contributions` CTE** — only in `/contributions`. Contribution sign convention (positive credit) handled inline.

---

## Proposed dbt Project Structure

```
dbt/
├── dbt_project.yml
├── profiles.yml             # points at data/hl_dashboard.duckdb
├── models/
│   ├── sources.yml          # declares 6 source tables (dim_date is now a seed)
│   ├── staging/
│   │   ├── stg_transactions.sql
│   │   ├── stg_transactions.yml
│   │   ├── stg_prices.sql
│   │   ├── stg_prices.yml
│   │   ├── stg_benchmarks.sql
│   │   └── stg_benchmarks.yml
│   ├── intermediate/
│   │   ├── int_trade_unit_deltas.sql
│   │   ├── int_trade_unit_deltas.yml
│   │   ├── int_cumulative_unit_balances.sql
│   │   ├── int_cumulative_unit_balances.yml
│   │   ├── int_daily_unit_balances.sql
│   │   ├── int_daily_unit_balances.yml
│   │   ├── int_daily_fund_values.sql
│   │   ├── int_daily_fund_values.yml
│   │   ├── int_fund_cost_basis.sql
│   │   ├── int_fund_cost_basis.yml
│   │   ├── int_daily_contributions.sql
│   │   └── int_daily_contributions.yml
│   └── marts/
│       ├── mart_daily_portfolio_value.sql
│       ├── mart_daily_portfolio_value.yml
│       ├── mart_current_holdings.sql
│       ├── mart_current_holdings.yml
│       ├── mart_portfolio_contributions.sql
│       ├── mart_portfolio_contributions.yml
│       └── mart_benchmark_levels.sql
│           mart_benchmark_levels.yml
└── seeds/
    └── dim_date.csv         # moved from data/imports/; referenced via {{ ref('dim_date') }}
```

---

## Lineage Diagram

```
SEED LAYER
  dim_date
       │
       │    SOURCE LAYER
       │      transactions  prices  benchmarks  accounts  funds
       │           │            │        │          │        │
       │           ▼            ▼        ▼          │        │
       │    STAGING LAYER                           │        │
       │      stg_transactions  stg_prices  stg_benchmarks   │
       │           │                 │        │              │
       │           ▼                 │        │              │
       │    INTERMEDIATE LAYER       │        │              │
       │      int_trade_unit_deltas  │        │              │
       │           │                 │        │              │
       │           ▼                 │        │              │
       │      int_cumulative_unit_balances    │              │
       │           │                 │        │              │
       └──────────►▼                 │        │              │
              int_daily_unit_balances│        │              │
                   │                 │        │              │
                   ├──────────────── ▼        │              │
                   │       int_daily_fund_values             │
                   │                          │              │
                   ▼                          │              │
              int_fund_cost_basis             │              │
              int_daily_contributions         │              │
                   │                          │              │
                   ▼                          ▼              ▼
MART LAYER
  mart_daily_portfolio_value   ← int_daily_fund_values + accounts
  mart_current_holdings        ← int_daily_fund_values (all dates) + int_fund_cost_basis + funds
  mart_portfolio_contributions ← mart_daily_portfolio_value + int_daily_contributions
  mart_benchmark_levels        ← stg_benchmarks
```

---

## Layer-by-Layer Model Specifications

---

### Layer 0a — Seed (`seeds/dim_date.csv`)

`dim_date.csv` is moved from `data/imports/` to `dbt/seeds/` and loaded via `dbt seed`. Models reference it with `{{ ref('dim_date') }}`. The `setup_db.py` call that previously loaded it from CSV can be removed once the seed is in place.

A `dbt/seeds/dim_date.yml` schema file documents the columns (`date`, `year`, `month`, `day`, `year_month`, `financial_year`) and adds a `date` not-null + unique test.

---

### Layer 0b — Sources (`sources.yml`)

The remaining 6 raw DuckDB tables declared as a single source named `hl_dashboard`. This gives dbt lineage tracking and allows source freshness checks.

**Key source tests:**
- `transactions`: `id` not-null + unique; `account_id` references `accounts`; `fund_id` references `funds`; `transaction_type` accepted-values test
- `prices`: `(fund_id, date)` unique; `price_pence > 0`
- `benchmarks`: `(index_id, date)` unique; `index_id` accepted-values (`FTSE100`, `SP500`, `NASDAQ`)
- `funds`: `id` not-null + unique
- `accounts`: `id` accepted-values (`ISA`, `SIPP`)

---

### Layer 1 — Staging

Staging models rename columns to a consistent snake_case convention, apply type casts, derive simple columns, and do nothing else. One model per source table. All materialised as **views**.

---

#### `stg_transactions`

**Grain:** one row per transaction (same as source)

**Transforms:**
- Pass through all columns with consistent naming
- Add `is_trade BOOLEAN` — true when `transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')`
- Add `is_contribution BOOLEAN` — true when `transaction_type = 'CONTRIBUTION'`
- Add `unit_direction INTEGER` — `CASE WHEN value_gbp < 0 THEN 1 ELSE -1 END` — encodes the HL sign convention once, in one place. This is the rule that currently appears in every `delta` CTE across the codebase.

**Schema tests:**
- `id`: not-null, unique
- `account_id`: not-null, relationships to `accounts`
- `transaction_type`: accepted-values
- `value_gbp`: not-null

---

#### `stg_prices`

**Grain:** one row per `(fund_id, date)`

**Transforms:**
- Pass through source columns
- Add `price_gbp = price_pence / 100.0` — avoids the `/100.0` arithmetic scattered across every valuation query

**Schema tests:**
- `(fund_id, date)`: unique combination
- `price_pence`: not-null, > 0
- `fund_id`: relationships to `funds`

---

#### `stg_benchmarks`

**Grain:** one row per `(index_id, date)`

**Transforms:**
- Pass through; cast `level` to DOUBLE if not already
- Add `ticker` column documentation

**Schema tests:**
- `(index_id, date)`: unique combination
- `index_id`: accepted-values (`FTSE100`, `SP500`, `NASDAQ`)
- `level`: not-null, > 0

---

### Layer 2 — Intermediate

Intermediate models build the stepping stones between raw data and the mart outputs. They encapsulate the complex logic currently duplicated in Python. Materialised as **views** (or **tables** for the ASOF JOIN models, see note below).

---

#### `int_trade_unit_deltas`

**Grain:** one row per `(account_id, fund_id, trade_date)`

**Source:** `stg_transactions`

**Logic:** Consolidates all trade events on the same fund × account × date into a single net unit movement. This is the `delta` CTE from the Python routers, promoted to a named model.

```sql
SELECT
    account_id,
    fund_id,
    trade_date,
    SUM(quantity * unit_direction) AS unit_delta
FROM {{ ref('stg_transactions') }}
WHERE is_trade = TRUE
  AND fund_id IS NOT NULL
  AND quantity IS NOT NULL
GROUP BY account_id, fund_id, trade_date
```

**Schema tests:**
- `account_id`, `fund_id`, `trade_date`: not-null
- `(account_id, fund_id, trade_date)`: unique combination

---

#### `int_cumulative_unit_balances`

**Grain:** one row per `(account_id, fund_id, trade_date)` — one entry per trade event, not per calendar day

**Source:** `int_trade_unit_deltas`

**Logic:** Running total of units held per fund per account up to and including each trade date. This is the `running` CTE from the Python routers.

```sql
SELECT
    account_id,
    fund_id,
    trade_date,
    SUM(unit_delta) OVER (
        PARTITION BY account_id, fund_id
        ORDER BY trade_date
    ) AS units_held
FROM {{ ref('int_trade_unit_deltas') }}
```

**Schema tests:**
- `(account_id, fund_id, trade_date)`: unique combination

---

#### `int_daily_unit_balances`

**Grain:** one row per `(account_id, fund_id, date)` — every calendar day from first trade to today

**Sources:** `int_cumulative_unit_balances`, `dim_date`

**Logic:** Forward-fills the sparse trade-date balances to every calendar day using a DuckDB ASOF JOIN. This is the equivalent of the existing `v_holdings` view, but with `account_id` preserved in the grain.

> **DuckDB note:** ASOF JOIN is a DuckDB-specific syntax. This is fine since the project is DuckDB-only. The model should be clearly noted in its schema file as using a DuckDB-specific feature.

```sql
WITH fund_dates AS (
    SELECT d.date, r.account_id, r.fund_id
    FROM {{ ref('dim_date') }} d  -- dbt seed; not a source()
    CROSS JOIN (
        SELECT DISTINCT account_id, fund_id FROM {{ ref('int_cumulative_unit_balances') }}
    ) r
    WHERE d.date >= (
        SELECT MIN(trade_date) FROM {{ ref('int_cumulative_unit_balances') }}
    )
    AND d.date <= CURRENT_DATE
)
SELECT
    fd.date,
    fd.account_id,
    fd.fund_id,
    r.units_held
FROM fund_dates fd
ASOF JOIN {{ ref('int_cumulative_unit_balances') }} r
    ON (fd.account_id = r.account_id
    AND fd.fund_id = r.fund_id
    AND fd.date >= r.trade_date)
```

**Materialisation:** **Table** — the cross-join of all account × fund × date combinations will be large for a long history; materialising avoids recomputing the ASOF JOIN on every downstream query.

**Schema tests:**
- `(account_id, fund_id, date)`: unique combination
- `units_held`: not-null

---

#### `int_daily_fund_values`

**Grain:** one row per `(account_id, fund_id, date)` — only dates where a price exists

**Sources:** `int_daily_unit_balances`, `stg_prices`, `funds`

**Logic:** Joins unit balances with the daily price to produce a GBP value for each fund, account, and day. Only rows where `units_held > 0.0001` and a price exists are included — this matches the existing `v_portfolio_value` view but is account-aware.

```sql
SELECT
    h.date,
    h.account_id,
    h.fund_id,
    f.name AS fund_name,
    h.units_held,
    p.price_gbp,
    ROUND(h.units_held * p.price_gbp, 2) AS value_gbp
FROM {{ ref('int_daily_unit_balances') }} h
JOIN {{ ref('stg_prices') }} p
    ON p.fund_id = h.fund_id AND p.date = h.date
JOIN {{ source('hl_dashboard', 'funds') }} f
    ON f.id = h.fund_id
WHERE h.units_held > 0.0001
```

**Materialisation:** **Table** (downstream of the large ASOF table; kept materialised to avoid chain of expensive joins).

**Schema tests:**
- `(account_id, fund_id, date)`: unique combination
- `value_gbp`: not-null
- `price_gbp`: not-null, > 0

---

#### `int_fund_cost_basis`

**Grain:** one row per `(account_id, fund_id)`

**Source:** `stg_transactions`

**Logic:** Computes the simplified cost basis used on the Holdings page. This is the `buy_cost` and `sell_proceeds` CTEs from `portfolio/holdings`, pulled out and documented.

The method: cost basis = total purchase cost (BUY + SWITCH_IN value) minus total sale proceeds (SELL + SWITCH_OUT value). This is explicitly documented as an approximation — it does not use a true FIFO or weighted average cost. Switching events are excluded from cost basis tracking (a known caveat in the README).

```sql
WITH buys AS (
    SELECT account_id, fund_id,
           SUM(ABS(value_gbp)) AS total_buy_cost,
           SUM(quantity)       AS total_units_bought
    FROM {{ ref('stg_transactions') }}
    WHERE transaction_type IN ('BUY', 'SWITCH_IN')
      AND fund_id IS NOT NULL AND quantity IS NOT NULL
    GROUP BY account_id, fund_id
),
sells AS (
    SELECT account_id, fund_id,
           SUM(ABS(value_gbp)) AS total_sell_proceeds,
           SUM(quantity)       AS total_units_sold
    FROM {{ ref('stg_transactions') }}
    WHERE transaction_type IN ('SELL', 'SWITCH_OUT')
      AND fund_id IS NOT NULL AND quantity IS NOT NULL
    GROUP BY account_id, fund_id
)
SELECT
    b.account_id,
    b.fund_id,
    b.total_buy_cost,
    b.total_units_bought,
    COALESCE(s.total_sell_proceeds, 0) AS total_sell_proceeds,
    COALESCE(s.total_units_sold, 0)    AS total_units_sold,
    GREATEST(b.total_buy_cost - COALESCE(s.total_sell_proceeds, 0), 0) AS cost_basis_gbp
FROM buys b
LEFT JOIN sells s ON s.account_id = b.account_id AND s.fund_id = b.fund_id
```

**Schema tests:**
- `(account_id, fund_id)`: unique combination
- `cost_basis_gbp`: not-null, >= 0

---

#### `int_daily_contributions`

**Grain:** one row per `(account_id, date)` — cumulative total as of each date

**Source:** `stg_transactions`

**Logic:** Running sum of all `CONTRIBUTION` transactions per account over time. Used by the Contributions vs Growth page.

```sql
WITH daily AS (
    SELECT account_id, trade_date AS date,
           SUM(value_gbp) AS contributed_today
    FROM {{ ref('stg_transactions') }}
    WHERE is_contribution = TRUE
    GROUP BY account_id, trade_date
)
SELECT
    account_id,
    date,
    contributed_today,
    SUM(contributed_today) OVER (
        PARTITION BY account_id ORDER BY date
    ) AS cumulative_contributions_gbp
FROM daily
```

**Schema tests:**
- `(account_id, date)`: unique combination
- `cumulative_contributions_gbp`: not-null

---

### Layer 3 — Marts

Mart models are the final outputs queried by the FastAPI endpoints. They are account-granular (the API applies the `ISA`/`SIPP`/`All` filter at query time by adding `WHERE account_id = ?`). Materialised as **tables**.

---

#### `mart_daily_portfolio_value`

**Grain:** one row per `(account_id, date)`

**Replaces:** inline SQL in `GET /portfolio/value`

**Source:** `int_daily_fund_values`

**Logic:** Sums value across all funds for each account and date. The API filters by `account_id` and date range and can `SUM` across accounts for the "All" view.

```sql
SELECT
    account_id,
    date,
    ROUND(SUM(value_gbp), 2) AS portfolio_value_gbp
FROM {{ ref('int_daily_fund_values') }}
GROUP BY account_id, date
HAVING portfolio_value_gbp > 0
```

**Schema tests:**
- `(account_id, date)`: unique combination
- `portfolio_value_gbp`: not-null, > 0

**API change:** `GET /portfolio/value` query simplifies to:
```sql
SELECT date, SUM(portfolio_value_gbp) AS value_gbp
FROM mart_daily_portfolio_value
WHERE date BETWEEN ? AND ?
  [AND account_id = ?]
GROUP BY date
ORDER BY date
```

---

#### `mart_current_holdings`

**Grain:** one row per `(account_id, fund_id, date)` — a daily snapshot for every day a price exists

**Replaces:** inline SQL in `GET /portfolio/holdings`

**Sources:** `int_daily_fund_values`, `int_fund_cost_basis`, `funds`

**Logic:** Joins all rows from `int_daily_fund_values` with the cost basis per fund. Cost basis is static (it only changes when a trade occurs) so the same `int_fund_cost_basis` values are applied across all dates. The `GET /portfolio/holdings` endpoint queries this mart filtered to the latest available price date; the daily history is available for future drill-down features.

> Note: The `percentage` (portfolio weight) column is not pre-computed here because it depends on the account filter applied at query time. The API computes it as a window function on the result set.

```sql
SELECT
    v.account_id,
    v.fund_id,
    v.fund_name,
    v.date,
    v.units_held,
    v.price_gbp,
    v.value_gbp,
    COALESCE(cb.cost_basis_gbp, 0)                AS cost_basis_gbp,
    v.value_gbp - COALESCE(cb.cost_basis_gbp, 0)  AS unrealised_gain_gbp,
    CASE WHEN COALESCE(cb.cost_basis_gbp, 0) > 0
         THEN ROUND(
             (v.value_gbp - cb.cost_basis_gbp) / cb.cost_basis_gbp * 100.0, 2
         )
         ELSE 0.0
    END AS unrealised_gain_pct
FROM {{ ref('int_daily_fund_values') }} v
LEFT JOIN {{ ref('int_fund_cost_basis') }} cb
    ON cb.account_id = v.account_id AND cb.fund_id = v.fund_id
```

**Schema tests:**
- `(account_id, fund_id, date)`: unique combination
- `units_held`: not-null, > 0
- `price_gbp`: not-null, > 0
- `value_gbp`: not-null

---

#### `mart_portfolio_contributions`

**Grain:** one row per `(account_id, date)`

**Replaces:** inline SQL in `GET /portfolio/contributions`

**Sources:** `mart_daily_portfolio_value`, `int_daily_contributions`

**Logic:** Joins portfolio value with cumulative contributions. Growth = portfolio_value − cumulative_contributions.

```sql
SELECT
    pv.account_id,
    pv.date,
    pv.portfolio_value_gbp,
    COALESCE(dc.cumulative_contributions_gbp, 0) AS cumulative_contributions_gbp,
    ROUND(
        pv.portfolio_value_gbp - COALESCE(dc.cumulative_contributions_gbp, 0), 2
    ) AS growth_gbp
FROM {{ ref('mart_daily_portfolio_value') }} pv
LEFT JOIN {{ ref('int_daily_contributions') }} dc
    ON dc.account_id = pv.account_id AND dc.date = pv.date
```

**Schema tests:**
- `(account_id, date)`: unique combination
- `portfolio_value_gbp`: not-null

---

#### `mart_benchmark_levels`

**Grain:** one row per `(index_id, date)`

**Replaces:** the benchmark sub-queries in `GET /portfolio/performance` and `GET /funds/{id}/performance`

**Source:** `stg_benchmarks`

**Logic:** Passthrough of cleaned benchmark levels. The "indexed to 100" calculation stays in the API because the base date varies per request.

```sql
SELECT
    index_id,
    date,
    level,
    ticker
FROM {{ ref('stg_benchmarks') }}
```

**Schema tests:**
- `(index_id, date)`: unique combination
- `level`: not-null, > 0

---

## Schema File Conventions

Each `.yml` file follows this structure:

```yaml
version: 2

models:
  - name: <model_name>
    description: |
      One-paragraph description of what this model represents,
      its grain, and any caveats (e.g. DuckDB-specific syntax,
      approximation methods).
    config:
      materialized: table   # or view
    columns:
      - name: account_id
        description: "ISA or SIPP — the HL account this row belongs to."
        tests:
          - not_null
          - accepted_values:
              values: ['ISA', 'SIPP']
      - name: fund_id
        description: "ISIN of the fund, or CASH for cash positions."
        tests:
          - not_null
      # ... etc
    tests:
      - unique:
          column_name: "(account_id, fund_id)"  # composite key
```

---

## Models Not Needing a Mart Counterpart

| Endpoint | Approach |
|---|---|
| `GET /portfolio/allocation` | Query `int_daily_fund_values` directly filtered to a specific `as_of` date — point-in-time queries don't benefit from pre-aggregation |
| `GET /portfolio/performance` | Query `mart_daily_portfolio_value` for portfolio series; query `mart_benchmark_levels` for benchmarks; index-to-100 logic stays in Python since the base date is a request parameter |
| `GET /funds/{id}/performance` | Query `int_daily_fund_values` filtered to `fund_id`; query `mart_benchmark_levels` for overlay; same indexing rationale |
| `GET /transactions` | Passthrough to `stg_transactions`; no pre-aggregation needed |
| `GET /funds` | Query source `funds` table directly |

---

## Tests Summary

| Model | Key tests |
|---|---|
| `sources` | Unique PKs, not-null keys, referential integrity, accepted-values for type enums |
| `stg_transactions` | `id` unique + not-null; `transaction_type` accepted-values; `value_gbp` not-null |
| `stg_prices` | `(fund_id, date)` unique; `price_pence > 0`; `price_gbp = price_pence / 100` (expression test) |
| `int_trade_unit_deltas` | `(account_id, fund_id, trade_date)` unique |
| `int_cumulative_unit_balances` | `(account_id, fund_id, trade_date)` unique |
| `int_daily_unit_balances` | `(account_id, fund_id, date)` unique; `units_held` not-null |
| `int_daily_fund_values` | `(account_id, fund_id, date)` unique; `value_gbp` not-null; `price_gbp > 0` |
| `int_fund_cost_basis` | `(account_id, fund_id)` unique; `cost_basis_gbp >= 0` |
| `int_daily_contributions` | `(account_id, date)` unique; `cumulative_contributions_gbp >= 0` |
| `mart_daily_portfolio_value` | `(account_id, date)` unique; `portfolio_value_gbp > 0` |
| `mart_current_holdings` | `(account_id, fund_id, date)` unique; `value_gbp > 0` |
| `mart_portfolio_contributions` | `(account_id, date)` unique |
| `mart_benchmark_levels` | `(index_id, date)` unique; `level > 0` |

---

## Migration Approach

### Step 1 — Bootstrap the dbt project ✅

- `dbt/` directory created; `profiles.yml` configured to connect to `data/hl_dashboard.duckdb`
- `data/imports/dim_date.csv` converted (ISO dates, snake_case headers) and moved to `dbt/seeds/dim_date.csv`; loaded via `dbt seed` (4,997 rows)
- 6 source tables registered in `sources.yml`
- `dbt-duckdb 1.10.1` and `dbt-utils 1.3.3` installed

### Step 2 — Staging layer ✅

- `stg_transactions`, `stg_prices`, `stg_benchmarks` written and tested
- All materialised as views

### Step 3 — Intermediate layer ✅

Built and tested in dependency order:
1. `int_trade_unit_deltas`
2. `int_cumulative_unit_balances`
3. `int_daily_unit_balances` (ASOF JOIN; account-aware replacement for `v_holdings`)
4. `int_daily_fund_values` (replacement for `v_portfolio_value`)
5. `int_fund_cost_basis`
6. `int_daily_contributions`

`v_holdings` and `v_portfolio_value` dropped from DuckDB and removed from `001_init.sql`.

### Step 4 — Mart layer ✅

1. `mart_daily_portfolio_value`
2. `mart_current_holdings` (daily snapshot grain)
3. `mart_portfolio_contributions`
4. `mart_benchmark_levels`

**112/112 data tests pass. 13/13 models build successfully.**

### Step 5 — Update FastAPI routers ⏳ pending

For each endpoint, replace the inline CTE SQL with a simpler query against the mart or intermediate model. The API signatures don't change. Inline account filter and date range WHERE clauses remain in Python.

### Step 6 — Schedule dbt in the daily refresh ⏳ pending

Add `dbt run` to the daily 18:00 job (after `fetch_prices.py` completes) so the mart tables are always fresh.

---

## Design Decisions

| Decision | Resolution |
|---|---|
| "All accounts" grain | Keep `account_id` as a column in all marts; API sums across accounts for the combined view |
| `int_daily_unit_balances` partitioning | Not needed — volume is not large enough to warrant it |
| `mart_current_holdings` snapshot | Daily grain `(account_id, fund_id, date)` — enables future historical drill-down; API filters to latest date for current view |
| `dim_date` ownership | Promoted to a dbt seed; moved from `data/imports/` to `dbt/seeds/`; referenced via `{{ ref('dim_date') }}` |
| Indexed-to-100 calculation | Stays in Python — base date varies per request and pre-computing it would reduce flexibility |
