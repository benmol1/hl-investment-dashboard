import pytest

from bot import executors
from bot.executors import (
    _execute_generate_chart,
    _execute_query_database,
    _execute_query_metrics,
    execute_tool,
    pop_pending_provenance,
)


@pytest.fixture
def live_db(warehouse_path, mocker):
    """Point the executors at the mini warehouse fixture."""
    mocker.patch.object(executors, "DB_PATH", warehouse_path)
    pop_pending_provenance()
    yield
    pop_pending_provenance()


# ---------------------------------------------------------------------------
# execute_tool dispatcher
# ---------------------------------------------------------------------------


def test_execute_tool_unknown_name():
    result = execute_tool("no_such_tool", {})
    assert result == {"error": "Unknown tool: no_such_tool"}


def test_execute_tool_wraps_generic_exception(mocker):
    mocker.patch.object(executors, "_run_sql", side_effect=RuntimeError("boom"))
    result = execute_tool("query_metrics", {"model": "holdings_latest", "metrics": ["value_gbp"]})
    assert result == {"error": "boom"}


# ---------------------------------------------------------------------------
# _execute_query_metrics
# ---------------------------------------------------------------------------


def test_query_metrics_end_to_end(live_db):
    result = _execute_query_metrics(
        {
            "model": "holdings_latest",
            "metrics": ["value_gbp"],
            "group_by": ["account_name"],
        }
    )
    assert result["columns"] == ["account_name", "value_gbp"]
    assert dict(result["rows"]) == {"ISA": 1080.0, "SIPP": 105.0}
    assert "SELECT" in result["sql"]


def test_query_metrics_records_provenance(live_db):
    _execute_query_metrics(
        {
            "model": "holdings_latest",
            "metrics": ["value_gbp"],
            "filters": [{"field": "account_name", "op": "eq", "value": "ISA"}],
        }
    )
    records = pop_pending_provenance()
    assert records == [
        {
            "source": "semantic",
            "model": "holdings_latest",
            "metrics": ["value_gbp"],
            "group_by": [],
            "filters": ["account_name = ISA"],
            "time_range": None,
        }
    ]
    assert pop_pending_provenance() == []  # popped


def test_query_metrics_unknown_model():
    result = _execute_query_metrics({"model": "nope", "metrics": ["x"]})
    assert "Unknown model" in result["error"]


def test_query_metrics_invalid_query_no_provenance(live_db):
    result = _execute_query_metrics({"model": "holdings_latest", "metrics": ["nope"]})
    assert "Unknown metric" in result["error"]
    assert pop_pending_provenance() == []


def test_get_dimension_values(live_db):
    result = execute_tool(
        "get_dimension_values", {"model": "holdings_latest", "dimension": "fund_name"}
    )
    assert result["values"] == ["Fund Alpha", "Fund Beta"]
    assert pop_pending_provenance() == [
        {"source": "semantic_values", "model": "holdings_latest", "dimension": "fund_name"}
    ]


def test_get_dimension_values_rejects_time_dimension(live_db):
    result = execute_tool(
        "get_dimension_values", {"model": "portfolio_value", "dimension": "valuation_date"}
    )
    assert "Unknown dimension" in result["error"]


# ---------------------------------------------------------------------------
# _execute_query_database — SQL guard tests
# ---------------------------------------------------------------------------


def test_query_database_rejects_non_select():
    result = _execute_query_database({"sql": "UPDATE mart_holdings_latest SET value_gbp = 0"})
    assert "error" in result
    assert "SELECT" in result["error"]


def test_query_database_rejects_disallowed_tables():
    result = _execute_query_database({"sql": "SELECT * FROM fct_transactions"})
    assert "error" in result
    assert "mart_/dim_" in result["error"]


def test_query_database_rejects_no_mart_or_dim():
    result = _execute_query_database({"sql": "SELECT 1"})
    assert "error" in result
    assert "mart_" in result["error"]


def test_query_database_valid_select_records_tables(live_db):
    result = _execute_query_database(
        {"sql": "SELECT fund_name, value_gbp FROM mart_holdings_latest ORDER BY value_gbp DESC"}
    )
    assert result["columns"] == ["fund_name", "value_gbp"]
    assert result["rows"][0] == ("Fund Alpha", 880.0)
    assert pop_pending_provenance() == [
        {"source": "sql_fallback", "tables": ["mart_holdings_latest"]}
    ]


# ---------------------------------------------------------------------------
# _execute_generate_chart
# ---------------------------------------------------------------------------

_LINE_DATA = [
    {"date": "2024-01", "value": 100.0},
    {"date": "2024-02", "value": 105.0},
]


def test_generate_chart_line():
    result = _execute_generate_chart({
        "chart_type": "line",
        "title": "Portfolio",
        "data": _LINE_DATA,
        "x_key": "date",
        "series": [{"label": "Value", "y_key": "value"}],
    })
    assert result.get("success") is True
    assert "chart_id" in result


def test_generate_chart_bar():
    result = _execute_generate_chart({
        "chart_type": "bar",
        "title": "Contributions",
        "data": _LINE_DATA,
        "x_key": "date",
        "y_key": "value",
    })
    assert result.get("success") is True
    assert "chart_id" in result


def test_generate_chart_donut():
    data = [{"fund": "Alpha", "pct": 60.0}, {"fund": "Beta", "pct": 40.0}]
    result = _execute_generate_chart({
        "chart_type": "donut",
        "title": "Allocation",
        "data": data,
        "label_key": "fund",
        "value_key": "pct",
    })
    assert result.get("success") is True
    assert "chart_id" in result


def test_generate_chart_missing_required_key():
    result = _execute_generate_chart({
        "chart_type": "bar",
        "title": "Bad",
        "data": _LINE_DATA,
        # missing x_key and y_key
    })
    assert "error" in result


def test_generate_chart_unknown_type():
    result = _execute_generate_chart({
        "chart_type": "scatter",
        "title": "Bad",
        "data": _LINE_DATA,
    })
    assert "error" in result
    assert "scatter" in result["error"]


def test_generate_chart_empty_data():
    result = _execute_generate_chart({
        "chart_type": "line",
        "title": "Empty",
        "data": [],
        "x_key": "date",
        "y_key": "value",
    })
    assert "error" in result
