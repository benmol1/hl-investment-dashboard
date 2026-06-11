"""Semantic layer tests: definitions load, and compiled SQL both validates
and produces correct numbers against the mini warehouse fixture."""

import pytest

from bot.semantic import (
    SemanticQueryError,
    compile_dimension_values,
    compile_query,
    load_registry,
    render_catalog,
)

REG = load_registry()


def run(warehouse, model_name: str, params: dict):
    compiled, _ = compile_query(REG.model(model_name), params)
    rows = warehouse.execute(compiled.sql).fetchall()
    return rows, compiled


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------


def test_registry_loads_all_models():
    assert REG.model_names == [
        "transactions",
        "holdings_daily",
        "holdings_latest",
        "portfolio_value",
        "portfolio_returns_monthly",
        "benchmarks_monthly",
    ]


def test_catalog_renders_without_db():
    catalog = render_catalog(db_path=None)
    assert "### transactions" in catalog
    assert "contributions_gbp" in catalog
    assert "ISA, SIPP" in catalog


def test_catalog_includes_dynamic_values(warehouse_path):
    catalog = render_catalog(db_path=warehouse_path)
    assert "Fund Alpha" in catalog


# ---------------------------------------------------------------------------
# Transactions model (filtered measures, time grains)
# ---------------------------------------------------------------------------


def test_contributions_by_account_and_financial_year(warehouse):
    rows, _ = run(warehouse, "transactions", {
        "metrics": ["contributions_gbp"],
        "filters": [
            {"field": "account_name", "op": "eq", "value": "SIPP"},
            {"field": "trade_date__financial_year", "op": "eq", "value": "FY26"},
        ],
    })
    assert rows == [(2000.0,)]  # transfer excluded


def test_inflows_includes_transfers(warehouse):
    rows, _ = run(warehouse, "transactions", {
        "metrics": ["inflows_gbp"],
        "filters": [{"field": "account_name", "op": "eq", "value": "SIPP"}],
    })
    assert rows == [(5000.0,)]


def test_fees_by_month(warehouse):
    rows, _ = run(warehouse, "transactions", {
        "metrics": ["fees_gbp"],
        "group_by": ["account_name", "trade_date__month"],
        "filters": [{"field": "trade_date__year", "op": "eq", "value": 2025}],
        "order_by": [
            {"field": "trade_date__month", "direction": "asc"},
            {"field": "account_name", "direction": "asc"},
        ],
    })
    # Rows with no FEE transactions produce NULL fee sums; the FEE months are correct.
    fee_rows = [r for r in rows if r[2] is not None]
    assert fee_rows == [
        ("ISA", "2025-04", 10.0),
        ("SIPP", "2025-04", 2.0),
        ("ISA", "2025-06", 5.0),
    ]


def test_contributions_grouped_by_financial_year(warehouse):
    rows, _ = run(warehouse, "transactions", {
        "metrics": ["contributions_gbp"],
        "group_by": ["trade_date__financial_year"],
    })
    assert dict(rows) == {"FY25": 500.0, "FY26": 3000.0}


def test_time_range_filter(warehouse):
    rows, _ = run(warehouse, "transactions", {
        "metrics": ["transaction_count"],
        "time_range": {"start": "2025-04-01", "end": "2025-04-30"},
    })
    assert rows == [(4,)]  # T1, T5, T6, T8


def test_string_escaping_in_filters(warehouse):
    rows, _ = run(warehouse, "transactions", {
        "metrics": ["transaction_count"],
        "filters": [{"field": "fund_name", "op": "eq", "value": "O'Brien; DROP TABLE x"}],
    })
    assert rows == [(0,)]


# ---------------------------------------------------------------------------
# Semi-additive measures (holdings_daily, portfolio_value)
# ---------------------------------------------------------------------------


def test_holdings_value_uses_latest_snapshot(warehouse):
    rows, _ = run(warehouse, "holdings_daily", {"metrics": ["value_gbp"]})
    assert rows == [(1190.0,)]  # 880 + 200 + 110 on 2025-05-31, not summed over time


def test_holdings_value_by_account(warehouse):
    rows, _ = run(warehouse, "holdings_daily", {
        "metrics": ["value_gbp"],
        "group_by": ["account_name"],
    })
    assert dict(rows) == {"ISA": 1080.0, "SIPP": 110.0}


def test_holdings_value_by_month_takes_period_end(warehouse):
    rows, _ = run(warehouse, "holdings_daily", {
        "metrics": ["value_gbp"],
        "group_by": ["valuation_date__month"],
    })
    assert dict(rows) == {"2025-04": 1000.0, "2025-05": 1190.0}


def test_holdings_value_as_of_past_date(warehouse):
    rows, _ = run(warehouse, "holdings_daily", {
        "metrics": ["value_gbp"],
        "time_range": {"end": "2025-04-30"},
    })
    assert rows == [(1000.0,)]


def test_mixed_additive_and_semi_additive(warehouse):
    rows, _ = run(warehouse, "portfolio_value", {
        "metrics": ["inflows_gbp", "portfolio_value_gbp"],
        "group_by": ["valuation_date__month"],
    })
    # inflows are summed over the month; value is the month-end snapshot
    assert dict((r[0], (r[1], r[2])) for r in rows) == {
        "2025-04": (1000.0, 1000.0),
        "2025-05": (0.0, 1190.0),
    }


def test_derived_growth_metric(warehouse):
    rows, _ = run(warehouse, "portfolio_value", {
        "metrics": ["portfolio_value_gbp", "cumulative_inflows_gbp", "growth_gbp"],
    })
    assert rows == [(1190.0, 6500.0, -5310.0)]


# ---------------------------------------------------------------------------
# Derived metrics + ordering (holdings_latest)
# ---------------------------------------------------------------------------


def test_unrealised_gain_pct_ratio_of_sums(warehouse):
    rows, _ = run(warehouse, "holdings_latest", {
        "metrics": ["unrealised_gain_pct", "unrealised_gain_gbp"],
        "group_by": ["fund_name"],
        "filters": [{"field": "holding_type", "op": "eq", "value": "Fund"}],
        "order_by": [{"field": "unrealised_gain_pct", "direction": "desc"}],
        "limit": 1,
    })
    assert rows == [("Fund Alpha", 10.0, 80.0)]


def test_derived_metric_alone_pulls_hidden_measures(warehouse):
    rows, compiled = run(warehouse, "holdings_latest", {
        "metrics": ["unrealised_gain_pct"],
        "filters": [{"field": "fund_name", "op": "eq", "value": "Fund Beta"}],
    })
    assert compiled.columns == ["unrealised_gain_pct"]
    assert rows == [(5.0,)]


def test_weights_within_account(warehouse):
    rows, _ = run(warehouse, "holdings_latest", {
        "metrics": ["value_gbp", "weight_pct"],
        "group_by": ["fund_name"],
        "filters": [
            {"field": "account_name", "op": "eq", "value": "ISA"},
            {"field": "holding_type", "op": "eq", "value": "Fund"},
        ],
    })
    assert rows == [("Fund Alpha", 880.0, 81.5)]


# ---------------------------------------------------------------------------
# agg: last (returns + benchmarks)
# ---------------------------------------------------------------------------


def test_last_skips_nulls_per_measure(warehouse):
    rows, _ = run(warehouse, "portfolio_returns_monthly", {
        "metrics": ["trailing_12m_return", "trailing_12m_sharpe"],
        "filters": [{"field": "account_name", "op": "eq", "value": "ISA"}],
    })
    # return: latest month (May = 0.12); sharpe: May is NULL so April's 1.1
    assert rows == [(0.12, 1.1)]


def test_benchmark_sharpe_by_index(warehouse):
    rows, _ = run(warehouse, "benchmarks_monthly", {
        "metrics": ["trailing_12m_sharpe"],
        "group_by": ["index_id"],
        "filters": [{"field": "index_id", "op": "in", "value": ["SP500", "NASDAQ"]}],
    })
    assert dict(rows) == {"SP500": 1.4, "NASDAQ": 1.6}


# ---------------------------------------------------------------------------
# Dimension values
# ---------------------------------------------------------------------------


def test_compile_dimension_values(warehouse):
    sql = compile_dimension_values(REG.model("holdings_latest"), "fund_name")
    values = [r[0] for r in warehouse.execute(sql).fetchall()]
    assert values == ["Fund Alpha", "Fund Beta"]


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params,message",
    [
        ({"metrics": []}, "non-empty list"),
        ({"metrics": ["nope"]}, "Unknown metric 'nope'"),
        ({"metrics": ["fees_gbp"], "group_by": ["nope"]}, "Unknown dimension 'nope'"),
        ({"metrics": ["fees_gbp"], "group_by": ["trade_date__decade"]}, "Unknown grain"),
        ({"metrics": ["fees_gbp"], "group_by": ["account_name__month"]}, "not a time dimension"),
        ({"metrics": ["fees_gbp"], "group_by": ["account_name", "account_name"]}, "Duplicate"),
        ({"metrics": ["fees_gbp"], "filters": [{"field": "account_name", "op": "magic", "value": 1}]}, "Unknown filter op"),
        ({"metrics": ["fees_gbp"], "filters": [{"field": "account_name", "op": "in", "value": "ISA"}]}, "non-empty list"),
        ({"metrics": ["fees_gbp"], "filters": [{"field": "trade_date", "op": "gte", "value": "April"}]}, "YYYY-MM-DD"),
        ({"metrics": ["fees_gbp"], "time_range": {"start": "01/04/2025"}}, "YYYY-MM-DD"),
        ({"metrics": ["fees_gbp"], "order_by": [{"field": "net_value_gbp"}]}, "not in the selected columns"),
        ({"metrics": ["fees_gbp"], "limit": -1}, "positive integer"),
    ],
)
def test_invalid_queries_rejected(params, message):
    with pytest.raises(SemanticQueryError, match=message):
        compile_query(REG.model("transactions"), params)


def test_compiled_sql_has_no_unescaped_input():
    compiled, _ = compile_query(REG.model("transactions"), {
        "metrics": ["net_value_gbp"],
        "filters": [{"field": "fund_name", "op": "eq", "value": "x'; DELETE FROM y; --"}],
    })
    assert "DELETE FROM y" not in compiled.sql.replace("x''; DELETE FROM y; --", "")
