from unittest.mock import MagicMock

import requests

from bot.executors import (
    _execute_generate_chart,
    _execute_get_holdings,
    _execute_query_database,
    execute_tool,
)


# ---------------------------------------------------------------------------
# execute_tool dispatcher
# ---------------------------------------------------------------------------


def test_execute_tool_unknown_name():
    result = execute_tool("no_such_tool", {})
    assert result == {"error": "Unknown tool: no_such_tool"}


def test_execute_tool_wraps_http_error(mocker):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    http_err = requests.HTTPError(response=mock_response)
    mocker.patch("bot.executors._api_get", side_effect=http_err)

    result = execute_tool("get_holdings", {})
    assert "error" in result
    assert "404" in result["error"]


def test_execute_tool_wraps_generic_exception(mocker):
    mocker.patch("bot.executors._api_get", side_effect=RuntimeError("boom"))
    result = execute_tool("get_holdings", {})
    assert result == {"error": "boom"}


# ---------------------------------------------------------------------------
# _execute_query_database — SQL guard tests (no DB connection needed)
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


def test_query_database_valid_select(mocker):
    mock_con = MagicMock()
    mock_con.execute.return_value.fetchall.return_value = [("Fund Alpha", 5460.0)]
    mock_con.description = [("fund_name",), ("value_gbp",)]
    mocker.patch("bot.executors.duckdb.connect", return_value=mock_con)

    result = _execute_query_database({"sql": "SELECT fund_name, value_gbp FROM mart_holdings_latest"})
    assert "columns" in result
    assert "rows" in result
    assert result["columns"] == ["fund_name", "value_gbp"]
    assert result["rows"] == [("Fund Alpha", 5460.0)]


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


# ---------------------------------------------------------------------------
# _execute_get_holdings — param passing
# ---------------------------------------------------------------------------


def test_get_holdings_with_account(mocker):
    mock = mocker.patch("bot.executors._api_get", return_value=[])
    _execute_get_holdings({"account": "ISA"})
    mock.assert_called_once_with("/portfolio/holdings", {"account": "ISA"})


def test_get_holdings_without_account(mocker):
    mock = mocker.patch("bot.executors._api_get", return_value=[])
    _execute_get_holdings({})
    mock.assert_called_once_with("/portfolio/holdings", {})
