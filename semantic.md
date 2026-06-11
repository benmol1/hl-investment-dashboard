# A Semantic Layer for the HL Investment Dashboard Bot

*Research notes, design choices, and implementation plan — June 2026*

---

## 1. Why a semantic layer?

Today the Telegram bot answers questions through ~9 pre-curated tools, each wrapping one
FastAPI endpoint, plus a raw-SQL escape hatch (`query_database`). This works well for the
exact question shapes the endpoints were designed for, and badly for everything adjacent
("fees by month last year", "value of just Fundsmith in 2023", "contributions in calendar
year 2024 rather than tax year"). Every new question shape means a new endpoint and a new
tool.

A semantic layer inverts this: instead of N tools answering N question shapes, we define
the **primitives** of the warehouse — entities, dimensions, and measures — once, and give
the bot a single compositional query tool. The bot picks metrics and dimensions; a
deterministic compiler turns that into SQL. The combinatorial space of answerable
questions grows multiplicatively, while the SQL the model can produce stays constrained
to validated, pre-approved building blocks.

### What Anthropic does internally

Anthropic's writeup of its self-service analytics agent
([blog post](https://claude.com/blog/how-anthropic-enables-self-service-data-analytics-with-claude))
is the reference design here. The load-bearing points:

1. **A human-curated semantic layer is a source of truth.** Metric definitions live in
   version-controlled files in the *same repo* as the data models, so CI can catch a
   modelling change that would break a metric definition.
2. **The agent is structurally required to use the semantic layer first.** When a
   question maps to a defined metric, the agent calls a function and gets *the* number —
   the same number every other surface produces. Free-form SQL is the fallback, not the
   default.
3. **Curation beats generation.** They tried bootstrapping the semantic layer by having
   an LLM auto-generate metric definitions from raw tables and query logs. It produced
   plausible-looking definitions that encoded exactly the ambiguities a semantic layer
   exists to eliminate, and was **net negative on their evals** versus a smaller,
   hand-curated layer. Lesson: keep the layer small and write it by hand.
4. **Skills + validation do the rest.** Procedural knowledge (markdown skills) and
   multi-layer validation push accuracy from ~21% to 95%+. The semantic layer is
   necessary but not sufficient.

This project is a miniature of that architecture: dbt models are the data foundation,
the semantic layer becomes the source of truth, the bot's system prompt is the "skill",
and the eval harness is the validation loop.

---

## 2. Options considered

### 2.1 ktx ([github.com/Kaelio/ktx](https://github.com/Kaelio/ktx))

The open-source recreation of Anthropic's internal stack: ingests warehouse metadata,
BI definitions and docs into wiki markdown + semantic-layer YAML, serves it to agents
over MCP, and compiles approved metrics into read-only SQL.

- **Pros:** closest to the reference architecture; self-improving context; combined
  full-text + semantic search over the catalogue.
- **Cons (decisive):**
  - **No DuckDB support.** Supported warehouses are PostgreSQL, Snowflake, BigQuery,
    ClickHouse, MySQL, SQL Server, and SQLite. This project is DuckDB-native.
  - It runs as a local **MCP daemon** (`ktx mcp start`) designed for interactive coding
    agents (Claude Code, Codex). Our bot is a headless `python-telegram-bot` process with
    a fixed Anthropic-SDK tool loop — wiring an MCP client into it adds a process, a
    protocol, and a failure mode to a Raspberry Pi deployment.
  - Its strength — auto-building context from many sources (BI tools, Notion, query
    history) — solves a problem we don't have. There is one warehouse, ~15 tables, one
    user, and the dbt YAML is already excellent documentation.

**Verdict: overkill, and currently incompatible.** But its *file format philosophy*
(reviewable YAML in-repo, compiled to read-only SQL) is exactly what we'll build.

### 2.2 dbt Semantic Layer / MetricFlow

The industry-standard spec: `semantic_models` (entities, dimensions, measures) defined
in YAML next to dbt models, with `metrics` built on top. The Open Semantic Interchange
(OSI) initiative adopted MetricFlow as its declarative baseline, so this vocabulary is
the closest thing to a lingua franca.

- **Pros:** best-practice spec for exactly our shape of warehouse (Kimball star);
  definitions live in the dbt project; entity-based automatic joins.
- **Cons:** the *queryable* semantic layer API requires dbt Cloud. Open-source MetricFlow
  can compile queries, but it's a heavyweight dependency designed to be driven through
  dbt's CLI/manifest machinery, not embedded in a small bot process. On a Pi, this is a
  lot of moving parts for ~20 measures.

**Verdict: adopt the spec vocabulary, not the engine.**

### 2.3 Cube

A full semantic-layer *server* (Node) with REST/SQL/GraphQL APIs and pre-aggregations.
Built for high-concurrency embedded analytics and multi-tenant data products.

**Verdict: wrong weight class.** A fifth Docker container and a Node runtime to serve one
Telegram user is not a trade worth making.

### 2.4 boring-semantic-layer ([github.com/boringdata/boring-semantic-layer](https://github.com/boringdata/boring-semantic-layer))

A lightweight Python semantic layer built on Ibis, explicitly designed for LLM/MCP use
cases, DuckDB-native. Semantic models declare dimensions and measures as Ibis
expressions; queries are JSON-friendly.

- **Pros:** genuinely lightweight; right abstraction; could be embedded directly in the
  bot process (no daemon needed); active development.
- **Cons:** pulls in Ibis (a large dependency for a Pi image); young project with a
  fast-moving API (v2 recently restructured the core); and the expressiveness we need —
  filtered sums, ratio-of-sums, last-value-per-period — is small enough that owning the
  compiler outright is cheaper than owning the dependency.

**Verdict: the strongest off-the-shelf option, and the documented fallback if the
hand-rolled compiler ever feels limiting.**

### 2.5 Hand-rolled: MetricFlow-style YAML + a small deterministic compiler ✅ CHOSEN

Define the semantic layer in one reviewable YAML file using MetricFlow's vocabulary
(semantic models with dimensions and measures; derived metrics on top). Implement a
~400-line dependency-free Python compiler that turns a structured query —
`{model, metrics, group_by, filters, time_range, order_by, limit}` — into DuckDB SQL,
executes it read-only, and returns rows plus provenance.

- **Pros:**
  - Zero new runtime dependencies (PyYAML already ships transitively with dbt).
  - Full control over SQL generation — crucial for the Kimball-specific subtleties
    below (semi-additive facts, ratio-of-sums) and for debugging eval regressions.
  - The whole layer is reviewable in one sitting: one YAML file + one compiler module.
  - Security by construction: the model can only reference whitelisted identifiers;
    every value is escaped; the connection is read-only.
- **Cons:**
  - We own the compiler. Mitigated by keeping scope deliberately small (one fact table
    per query — no cross-model joins; the bot composes across models with multiple
    tool calls) and a thorough test suite against an in-memory fixture warehouse.
  - Not a standard engine. Mitigated by using MetricFlow vocabulary so a future
    migration to BSL or the dbt SL is a translation, not a rewrite.

### Decision matrix

| | ktx | dbt SL / MetricFlow | Cube | boring-semantic-layer | Hand-rolled |
|---|---|---|---|---|---|
| DuckDB support | ✗ | ⚠ (OSS only) | ✓ | ✓ | ✓ |
| Embeds in bot process | ✗ (MCP daemon) | ✗ | ✗ (server) | ✓ | ✓ |
| New dependencies | daemon | heavy | Node server | Ibis | none |
| Fits a Pi | ⚠ | ⚠ | ✗ | ✓ | ✓ |
| Standard spec | own | ✓ (OSI) | own | own | borrows MetricFlow vocab |
| Effort to adopt | medium | high | high | low–medium | medium |
| Control / debuggability | low | low | low | medium | **high** |

---

## 3. Design

### 3.1 The primitives

Following MetricFlow vocabulary, the layer defines **semantic models**, each bound to one
warehouse table (fact or mart) with its dimension-table joins declared once:

- **Semantic model** — name, description, base table, joins, primary time dimension.
- **Dimension** — a named, typed attribute the user can group or filter by. Categorical
  dimensions may carry an enumerated value list (ISA/SIPP, transaction types, fund
  names) that is surfaced to the bot so it filters on exact values.
- **Time dimension** — resolves to a DATE column; queryable at grains `day`, `month`,
  `quarter`, `year`, and `financial_year` (UK tax year, matching `dim_date`,
  e.g. `FY26` = April 2025 – March 2026). Grain is requested with MetricFlow's dunder
  syntax: `trade_date__month`.
- **Measure** — a named aggregation. Aggregation types:
  - `sum`, `avg`, `min`, `max`, `count`, `count_distinct` — the additive workhorses.
  - `last` — *non-additive point-in-time statistic*: take the value at the latest time
    point in each group, ignoring NULLs (compiled to
    `arg_max(x, t) FILTER (WHERE x IS NOT NULL)`). Used for pre-computed trailing
    returns and Sharpe ratios, where summing or averaging across months is meaningless.
  - Measures may carry a row-level `filter` (e.g. *gross fee amount* =
    `SUM(ABS(value_gbp))` over FEE rows only).
- **Semi-additive measures** — the classic Kimball balance-fact problem. Portfolio
  value and cumulative inflows are additive across accounts and funds but **not across
  time**: "value in 2024" is not the sum of 365 daily values. Measures declare
  `additivity: semi`, and the compiler snapshots the fact table to the **last available
  date per requested time period** (per period when a time grain is grouped; latest
  date overall when not) before aggregating. This is the textbook treatment of periodic
  snapshot facts. If a query mixes semi-additive and fully additive measures, the
  compiler computes each set in its own subquery and joins on the group keys.
- **Derived metrics** — expressions over already-aggregated measures, computed in an
  outer SELECT. This gives correct *ratio-of-sums* semantics (e.g.
  `unrealised_gain_pct = 100 × (Σvalue − Σcost) / Σcost`) rather than the
  sum-of-ratios bug that plagues naive metric layers. Window expressions are allowed,
  enabling share-of-total metrics.

### 3.2 The semantic models

Six models cover the warehouse. Where a mart already encodes hard-won business logic
(Modified Dietz returns, trailing Sharpe, cost basis), the semantic model sits on the
mart rather than re-deriving it — the semantic layer's job is *naming and access*, not
re-implementing finance.

| Model | Base table | What it answers |
|---|---|---|
| `transactions` | `fct_transactions` + account/fund/type/date dims | buys, sells, fees, contributions, transfers — any money-movement question, at any grain incl. financial year |
| `holdings_daily` | `fct_holdings_daily` + dims | per-fund and cash positions/values *over time* (semi-additive value) |
| `holdings_latest` | `mart_holdings_latest` | current positions: value, cost basis, unrealised gain £/%, account weight |
| `portfolio_value` | `mart_portfolio_inflows_daily` | total value over time, inflows, cumulative invested capital, growth = value − invested |
| `portfolio_returns_monthly` | `mart_portfolio_returns_monthly` | Modified Dietz monthly/trailing returns, Sharpe ratios per account |
| `benchmarks_monthly` | `mart_benchmarks_monthly` | FTSE100/S&P500/NASDAQ levels, returns, Sharpe — for comparisons |

Deliberate exclusions, to keep the catalogue unambiguous (Anthropic's "smaller curated
layer wins" lesson): `mart_portfolio_value_daily` (subsumed by `portfolio_value`),
`mart_contributions_by_financial_year` (subsumed by `transactions` filtered to
contributions at the `financial_year` grain), `mart_portfolio_snapshot_monthly` and the
price/benchmark core facts (no eval-relevant question needs them directly).

Cross-model questions ("my ISA return vs the FTSE") are answered by the bot making one
`query_metrics` call per model and composing in prose — same pattern as Anthropic's
function-per-metric design — rather than by a cross-model join engine, which is where
hand-rolled semantic layers go to die.

### 3.3 The bot's tool surface

| Tool | Role |
|---|---|
| `query_metrics` | **Primary.** Structured semantic query: model, metrics, group_by (with `__grain`), filters, time_range, order_by, limit. Returns rows + the compiled SQL. |
| `get_dimension_values` | Distinct values of a dimension (e.g. exact fund names) when the catalogue's enum list isn't enough. |
| `query_database` | **Demoted last resort**, unchanged guardrails (SELECT-only, `mart_`/`dim_` tables only). For questions the semantic layer cannot express. |
| `generate_chart` | Unchanged. |

The full catalogue (models → dimensions → measures, with descriptions and enum values,
including fund names loaded from `dim_fund` at startup) is rendered into the **system
prompt**, not fetched through a discovery tool. At this catalogue size (~2–3k tokens)
that saves a tool round-trip per conversation, which directly helps eval latency and
gives the model global awareness of what is answerable.

The nine named API tools are removed from the bot. The FastAPI endpoints stay — the
React frontend uses them — but the bot path is now: question → semantic query → SQL →
DuckDB.

### 3.4 Provenance footer

Every reply that touched data carries a deterministic footer, assembled in code (not by
the model, so it cannot be hallucinated):

- Semantic-layer queries:
  `📐 semantic layer · holdings_latest · metrics: value_gbp · by: fund_name · filter: account_name = ISA`
- SQL fallback:
  `🛠 SQL fallback · tables: mart_portfolio_value_daily, dim_date`

Executors record provenance as they run (same pattern as pending charts); the Claude
loop appends the deduplicated footer after the model's prose.

### 3.5 Security model

Unchanged in spirit from `query_database`, but stronger: in `query_metrics` every
identifier (model, metric, dimension, grain, order key) must resolve against the YAML
registry or the query is rejected before SQL is built; filter values are the only
user-influenced strings and are escaped (numbers validated, strings single-quote
doubled, dates regex-validated). Connections are read-only with the existing 30s
timeout. The raw-SQL fallback keeps its existing table-pattern guards.

### 3.6 Testing

- A dedicated in-memory DuckDB fixture builds a miniature star schema with known values.
- Compiler unit tests: identifier validation, escaping, grain expressions, measure
  filters, semi-additive snapshotting, mixed-additivity queries, derived metrics.
- Executor tests: end-to-end `query_metrics` → rows against the fixture, provenance
  recording, error shapes.
- The existing eval harness (`backend/bot/eval.py`) is intentionally untouched — it is
  the A/B instrument for old-vs-new bot.

### 3.7 Risks / trade-offs accepted

- **One model per query.** No automatic cross-fact joins. Accepted: composition happens
  in the agent loop; this is the single biggest complexity cliff in semantic layers and
  the eval set doesn't need it.
- **FY/grain logic exists in two places** (dim_date seed and the compiler's grain
  expressions). Accepted: the UK tax year rule is fixed; tests pin both.
- **Catalogue in the system prompt** costs ~2–3k input tokens per turn on Haiku.
  Accepted: cheaper than discovery round-trips at this scale; revisit if the catalogue
  grows.
- **`weight_pct` is only meaningful at its natural grain** (per holding within one
  account). Documented in the measure description rather than engineered around.
- If the compiler's expressiveness ceiling is hit, the migration path is
  boring-semantic-layer (same conceptual model, Ibis-backed) rather than growing a
  query planner here.

---

## 4. Implementation plan

1. `backend/bot/semantic/definitions.yml` — the curated semantic layer (the primitives).
2. `backend/bot/semantic/loader.py` — parse + validate YAML into frozen dataclasses at import time (fail fast on a bad layer).
3. `backend/bot/semantic/compiler.py` — structured query → SQL string (pure, testable).
4. `backend/bot/semantic/catalog.py` — render the catalogue for the system prompt; load enum values (fund names) from DuckDB at startup with a safe fallback.
5. `backend/bot/tools.py` — new tool surface (3.3).
6. `backend/bot/executors.py` — `query_metrics` / `get_dimension_values` executors, provenance log, removal of the API executors.
7. `backend/bot/claude.py` + `config.py` — catalogue injection, provenance footer.
8. Tests as per 3.6; README data-flow note.

Sources: [Anthropic — How Anthropic enables self-service data analytics with Claude](https://claude.com/blog/how-anthropic-enables-self-service-data-analytics-with-claude) · [Kaelio/ktx](https://github.com/Kaelio/ktx) · [ktx docs](https://docs.kaelio.com/ktx/docs/getting-started/introduction) · [dbt Semantic Layer / MetricFlow](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works) · [boring-semantic-layer](https://github.com/boringdata/boring-semantic-layer) · [MotherDuck — Why semantic layers matter](https://motherduck.com/blog/semantic-layer-duckdb-tutorial/) · [Semantic layer tool comparison 2026](https://www.stackfyi.com/guides/semantic-layer-tools-dbt-cube-metricflow-lightdash-2026)
