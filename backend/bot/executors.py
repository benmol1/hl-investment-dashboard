import concurrent.futures
import logging
import re
from typing import Any

import duckdb
import requests

from .config import BACKEND_URL, DB_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _api_get(path: str, params: dict | None = None) -> Any:
    url = f"{BACKEND_URL}{path}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _summarise_series(points: list[dict], date_key: str) -> list[dict]:
    """Downsample a daily time series to monthly (last point per month)."""
    seen: dict[str, dict] = {}
    for p in points:
        month = str(p[date_key])[:7]  # YYYY-MM
        seen[month] = p
    return list(seen.values())


# ---------------------------------------------------------------------------
# Named API tool executors
# ---------------------------------------------------------------------------

def _execute_get_holdings(inputs: dict) -> Any:
    params = {}
    if inputs.get("account"):
        params["account"] = inputs["account"]
    return _api_get("/portfolio/holdings", params)


def _execute_get_portfolio_value(inputs: dict) -> Any:
    params = {k: v for k, v in {
        "from": inputs.get("from_date"),
        "to": inputs.get("to_date"),
        "account": inputs.get("account"),
    }.items() if v is not None}
    points = _api_get("/portfolio/value", params)
    return _summarise_series(points, "date")


def _execute_get_contributions(inputs: dict) -> Any:
    params = {k: v for k, v in {
        "from": inputs.get("from_date"),
        "to": inputs.get("to_date"),
        "account": inputs.get("account"),
    }.items() if v is not None}
    points = _api_get("/portfolio/contributions", params)
    monthly = _summarise_series(points, "date")
    # First point for context + last 23 months
    return (monthly[:1] + monthly[-23:]) if len(monthly) > 24 else monthly


def _execute_get_portfolio_performance(inputs: dict) -> Any:
    params = {k: v for k, v in {
        "from": inputs.get("from_date"),
        "to": inputs.get("to_date"),
        "account": inputs.get("account"),
    }.items() if v is not None}
    data = _api_get("/portfolio/performance", params)

    def compress(series: list[dict]) -> dict | None:
        if not series:
            return None
        return {"start": series[0], "end": series[-1], "points": len(series)}

    return {
        "start_date": data.get("start_date"),
        "portfolio": compress(data.get("portfolio", [])),
        "FTSE100": compress(data.get("FTSE100", [])),
        "SP500": compress(data.get("SP500", [])),
        "NASDAQ": compress(data.get("NASDAQ", [])),
        "sharpe": data.get("sharpe"),
    }


def _execute_get_portfolio_allocation(inputs: dict) -> Any:
    params = {k: v for k, v in {
        "as_of": inputs.get("as_of"),
        "account": inputs.get("account"),
    }.items() if v is not None}
    return _api_get("/portfolio/allocation", params)


def _execute_list_funds(inputs: dict) -> Any:
    params = {}
    if inputs.get("active_only"):
        params["active_only"] = "true"
    return _api_get("/funds", params)


def _execute_get_fund_performance(inputs: dict) -> Any:
    fund_id = inputs["fund_id"]
    params = {k: v for k, v in {
        "from": inputs.get("from_date"),
        "to": inputs.get("to_date"),
    }.items() if v is not None}
    data = _api_get(f"/funds/{fund_id}/performance", params)
    fund_series = data.get("fund", [])
    return {
        "fund_id": data.get("fund_id"),
        "fund_name": data.get("fund_name"),
        "start_date": data.get("start_date"),
        "fund_start": fund_series[0] if fund_series else None,
        "fund_end": fund_series[-1] if fund_series else None,
        "FTSE100_end": data.get("FTSE100", [{}])[-1] if data.get("FTSE100") else None,
        "SP500_end": data.get("SP500", [{}])[-1] if data.get("SP500") else None,
        "NASDAQ_end": data.get("NASDAQ", [{}])[-1] if data.get("NASDAQ") else None,
    }


def _execute_list_transactions(inputs: dict) -> Any:
    params = {k: v for k, v in {
        "account": inputs.get("account"),
        "fund_id": inputs.get("fund_id"),
        "type": inputs.get("tx_type"),
        "from": inputs.get("from_date"),
        "to": inputs.get("to_date"),
        "page": inputs.get("page"),
        "per_page": inputs.get("per_page"),
    }.items() if v is not None}
    return _api_get("/transactions", params)


# ---------------------------------------------------------------------------
# DuckDB fallback executor
# ---------------------------------------------------------------------------

_ALLOWED_TABLE_PATTERN = re.compile(r'\b(mart_\w+|dim_\w+)\b', re.IGNORECASE)
_DISALLOWED_TABLE_PATTERN = re.compile(
    r'\b(fct_\w+|stg_\w+|int_\w+|raw_\w+|information_schema)\b', re.IGNORECASE
)


def _execute_query_database(inputs: dict) -> Any:
    sql = inputs["sql"].strip()

    if not re.match(r'^\s*SELECT\b', sql, re.IGNORECASE):
        return {"error": "Only SELECT statements are permitted."}

    if _DISALLOWED_TABLE_PATTERN.search(sql):
        return {"error": "Query references tables outside the allowed mart_/dim_ scope."}

    if not _ALLOWED_TABLE_PATTERN.search(sql):
        return {"error": "No mart_ or dim_ tables found in query. Only those tables may be queried."}

    def _run() -> dict:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        rows = con.execute(sql).fetchall()
        cols = [desc[0] for desc in con.description]
        con.close()
        return {"columns": cols, "rows": rows[:200]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        try:
            return future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            return {"error": "Query timed out after 30 seconds. Try a more targeted query."}
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EXECUTORS = {
    "get_holdings": _execute_get_holdings,
    "get_portfolio_value": _execute_get_portfolio_value,
    "get_contributions": _execute_get_contributions,
    "get_portfolio_performance": _execute_get_portfolio_performance,
    "get_portfolio_allocation": _execute_get_portfolio_allocation,
    "list_funds": _execute_list_funds,
    "get_fund_performance": _execute_get_fund_performance,
    "list_transactions": _execute_list_transactions,
    "query_database": _execute_query_database,
}


def execute_tool(name: str, tool_input: dict) -> Any:
    fn = _EXECUTORS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(tool_input)
    except requests.HTTPError as exc:
        return {"error": f"API error {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:
        return {"error": str(exc)}
