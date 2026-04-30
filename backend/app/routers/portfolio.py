from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
import duckdb

from app.db import get_db
from app.models import TimeSeriesPoint, AllocationItem, ContributionPoint, PerformancePoint, PortfolioPerformanceResponse, HoldingItem

router = APIRouter()

# Reusable CTE: running unit balance per (account, fund, trade_date)
_RUNNING_UNITS_CTE = """
WITH delta AS (
    SELECT account_id, fund_id, trade_date,
           SUM(CASE WHEN value_gbp < 0 THEN quantity ELSE -quantity END) AS unit_delta
    FROM transactions
    WHERE transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
      AND fund_id IS NOT NULL AND quantity IS NOT NULL
      {account_filter}
    GROUP BY account_id, fund_id, trade_date
),
running AS (
    SELECT account_id, fund_id, trade_date,
           SUM(unit_delta) OVER (
               PARTITION BY account_id, fund_id
               ORDER BY trade_date
           ) AS units_held
    FROM delta
)
"""


@router.get("/value", response_model=list[TimeSeriesPoint])
def portfolio_value(
    from_date: date = Query(date(2017, 1, 1), alias="from"),
    to_date: date = Query(default_factory=date.today, alias="to"),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Daily total portfolio value over time.
    Uses ASOF JOIN to forward-fill unit balances from trade dates to price dates.
    """
    account_filter = "AND account_id = ?" if account else ""
    params = [account, from_date, to_date] if account else [from_date, to_date]

    sql = f"""
    {_RUNNING_UNITS_CTE.format(account_filter=account_filter)}
    SELECT p.date, ROUND(SUM(r.units_held * p.price_pence / 100.0), 2) AS value_gbp
    FROM prices p
    ASOF JOIN running r ON (
        p.fund_id = r.fund_id AND p.date >= r.trade_date
        {'AND r.account_id = ?' if account else ''}
    )
    WHERE p.date BETWEEN ? AND ?
    GROUP BY p.date
    HAVING value_gbp > 0
    ORDER BY p.date
    """

    # account param appears twice (once in CTE filter, once in ASOF condition)
    if account:
        params = [account, account, from_date, to_date]

    rows = con.execute(sql, params).fetchall()
    return [TimeSeriesPoint(date=r[0], value_gbp=r[1]) for r in rows]


@router.get("/allocation", response_model=list[AllocationItem])
def portfolio_allocation(
    as_of: Optional[date] = Query(None, description="Date to calculate allocation (defaults to latest price date)"),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Current (or historical) allocation of portfolio by fund.
    """
    if as_of is None:
        result = con.execute("SELECT MAX(date) FROM prices").fetchone()
        as_of = result[0] if result and result[0] else date.today()

    account_filter = "AND account_id = ?" if account else ""

    sql = f"""
    WITH holdings AS (
        SELECT fund_id,
               SUM(CASE WHEN value_gbp < 0 THEN quantity ELSE -quantity END) AS units_held
        FROM transactions
        WHERE transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
          AND fund_id IS NOT NULL AND quantity IS NOT NULL
          AND trade_date <= ?
          {account_filter}
        GROUP BY fund_id
        HAVING units_held > 0.0001
    ),
    valued AS (
        SELECT
            h.fund_id,
            f.name AS fund_name,
            h.units_held,
            COALESCE(p.price_pence, 0) / 100.0 AS price_gbp,
            h.units_held * COALESCE(p.price_pence, 0) / 100.0 AS value_gbp
        FROM holdings h
        JOIN funds f ON f.id = h.fund_id
        LEFT JOIN prices p ON p.fund_id = h.fund_id AND p.date = ?
    )
    SELECT *, ROUND(value_gbp / SUM(value_gbp) OVER () * 100.0, 2) AS percentage
    FROM valued
    ORDER BY value_gbp DESC
    """

    if account:
        params = [as_of, account, as_of]   # trade_date<=, account filter, price date
    else:
        params = [as_of, as_of]            # trade_date<=, price date

    rows = con.execute(sql, params).fetchall()
    return [
        AllocationItem(
            fund_id=r[0], fund_name=r[1], units_held=r[2],
            price_gbp=r[3], value_gbp=r[4], percentage=r[5],
        )
        for r in rows
    ]


@router.get("/contributions", response_model=list[ContributionPoint])
def contributions_vs_growth(
    from_date: date = Query(date(2017, 1, 1), alias="from"),
    to_date: date = Query(default_factory=date.today, alias="to"),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Daily portfolio value vs cumulative contributions — the difference is growth.
    Only returns dates where price data exists.
    """
    account_filter = "AND account_id = ?" if account else ""

    sql = f"""
    WITH delta AS (
        SELECT account_id, fund_id, trade_date,
               SUM(CASE WHEN value_gbp < 0 THEN quantity ELSE -quantity END) AS unit_delta
        FROM transactions
        WHERE transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
          AND fund_id IS NOT NULL AND quantity IS NOT NULL
          {account_filter}
        GROUP BY account_id, fund_id, trade_date
    ),
    running AS (
        SELECT account_id, fund_id, trade_date,
               SUM(unit_delta) OVER (
                   PARTITION BY account_id, fund_id ORDER BY trade_date
               ) AS units_held
        FROM delta
    ),
    portfolio_value AS (
        SELECT p.date, ROUND(SUM(r.units_held * p.price_pence / 100.0), 2) AS portfolio_value
        FROM prices p
        ASOF JOIN running r ON (
            p.fund_id = r.fund_id AND p.date >= r.trade_date
            {'AND r.account_id = ?' if account else ''}
        )
        WHERE p.date BETWEEN ? AND ?
        GROUP BY p.date
        HAVING portfolio_value > 0
    ),
    daily_contributions AS (
        SELECT trade_date AS date, SUM(value_gbp) AS amount
        FROM transactions
        WHERE transaction_type = 'CONTRIBUTION'
          {account_filter}
        GROUP BY trade_date
    )
    SELECT
        pv.date,
        pv.portfolio_value,
        ROUND(SUM(COALESCE(dc.amount, 0)) OVER (ORDER BY pv.date), 2) AS cumulative_contributions,
        ROUND(pv.portfolio_value - SUM(COALESCE(dc.amount, 0)) OVER (ORDER BY pv.date), 2) AS growth
    FROM portfolio_value pv
    LEFT JOIN daily_contributions dc ON dc.date = pv.date
    ORDER BY pv.date
    """

    if account:
        # Params: delta CTE account, ASOF account, date range, daily_contributions account
        params = [account, account, from_date, to_date, account]
    else:
        params = [from_date, to_date]

    rows = con.execute(sql, params).fetchall()
    return [
        ContributionPoint(
            date=r[0], portfolio_value=r[1],
            cumulative_contributions=r[2], growth=r[3],
        )
        for r in rows
    ]


@router.get("/performance", response_model=PortfolioPerformanceResponse)
def portfolio_performance(
    from_date: date = Query(date(2017, 1, 1), alias="from"),
    to_date: date = Query(default_factory=date.today, alias="to"),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Portfolio total value indexed to 100 at from_date, plus all three benchmark indices
    indexed to 100 at the same start date. Used for the benchmark comparison page.
    """
    account_filter = "AND account_id = ?" if account else ""
    value_params = [account, account, from_date, to_date] if account else [from_date, to_date]

    value_sql = f"""
    {_RUNNING_UNITS_CTE.format(account_filter=account_filter)}
    SELECT p.date, ROUND(SUM(r.units_held * p.price_pence / 100.0), 2) AS value_gbp
    FROM prices p
    ASOF JOIN running r ON (
        p.fund_id = r.fund_id AND p.date >= r.trade_date
        {'AND r.account_id = ?' if account else ''}
    )
    WHERE p.date BETWEEN ? AND ?
    GROUP BY p.date
    HAVING value_gbp > 0
    ORDER BY p.date
    """
    value_rows = con.execute(value_sql, value_params).fetchall()

    portfolio_series: list[PerformancePoint] = []
    start_date = from_date
    if value_rows:
        base = value_rows[0][1]
        start_date = value_rows[0][0]
        portfolio_series = [
            PerformancePoint(date=r[0], indexed=round(r[1] / base * 100, 4))
            for r in value_rows if r[1] and r[1] > 0
        ]

    def bench_series(index_id: str) -> list[PerformancePoint]:
        rows = con.execute(
            "SELECT date, level FROM benchmarks WHERE index_id = ? AND date BETWEEN ? AND ? ORDER BY date",
            [index_id, start_date, to_date],
        ).fetchall()
        if not rows:
            return []
        base = rows[0][1]
        return [PerformancePoint(date=r[0], indexed=round(r[1] / base * 100, 4)) for r in rows]

    return PortfolioPerformanceResponse(
        start_date=start_date,
        portfolio=portfolio_series,
        FTSE100=bench_series("FTSE100"),
        SP500=bench_series("SP500"),
        NASDAQ=bench_series("NASDAQ"),
    )


@router.get("/holdings", response_model=list[HoldingItem])
def portfolio_holdings(
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Current holdings with cost basis (weighted average cost) and unrealised gain.
    """
    account_filter = "AND account_id = ?" if account else ""
    params = [account] if account else []
    latest_price_date = con.execute("SELECT MAX(date) FROM prices").fetchone()
    as_of = latest_price_date[0] if latest_price_date and latest_price_date[0] else date.today()

    sql = f"""
    WITH holdings AS (
        SELECT fund_id,
               SUM(CASE WHEN value_gbp < 0 THEN quantity ELSE -quantity END) AS units_held
        FROM transactions
        WHERE transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
          AND fund_id IS NOT NULL AND quantity IS NOT NULL
          {account_filter}
        GROUP BY fund_id
        HAVING units_held > 0.0001
    ),
    buy_cost AS (
        SELECT fund_id,
               SUM(ABS(value_gbp)) AS total_cost,
               SUM(quantity)       AS total_qty
        FROM transactions
        WHERE transaction_type IN ('BUY', 'SWITCH_IN')
          AND fund_id IS NOT NULL AND quantity IS NOT NULL AND quantity > 0
          {account_filter}
        GROUP BY fund_id
    ),
    sell_proceeds AS (
        SELECT fund_id,
               SUM(ABS(value_gbp)) AS total_proceeds,
               SUM(quantity)       AS total_sold
        FROM transactions
        WHERE transaction_type IN ('SELL', 'SWITCH_OUT')
          AND fund_id IS NOT NULL AND quantity IS NOT NULL AND quantity > 0
          {account_filter}
        GROUP BY fund_id
    ),
    valued AS (
        SELECT
            h.fund_id,
            f.name AS fund_name,
            h.units_held,
            COALESCE(p.price_pence, 0) / 100.0 AS price_gbp,
            h.units_held * COALESCE(p.price_pence, 0) / 100.0 AS value_gbp,
            -- WAC: total_cost - (sold_qty / total_qty * total_cost)
            COALESCE(bc.total_cost, 0) - COALESCE(sp.total_proceeds, 0) AS cost_basis_gbp
        FROM holdings h
        JOIN funds f ON f.id = h.fund_id
        LEFT JOIN prices p ON p.fund_id = h.fund_id AND p.date = ?
        LEFT JOIN buy_cost bc ON bc.fund_id = h.fund_id
        LEFT JOIN sell_proceeds sp ON sp.fund_id = h.fund_id
    )
    SELECT
        fund_id, fund_name, units_held, price_gbp, value_gbp,
        GREATEST(cost_basis_gbp, 0) AS cost_basis_gbp,
        value_gbp - GREATEST(cost_basis_gbp, 0) AS unrealised_gain_gbp,
        CASE WHEN cost_basis_gbp > 0
             THEN ROUND((value_gbp - cost_basis_gbp) / cost_basis_gbp * 100.0, 2)
             ELSE 0.0 END AS unrealised_gain_pct,
        ROUND(value_gbp / SUM(value_gbp) OVER () * 100.0, 2) AS percentage
    FROM valued
    ORDER BY value_gbp DESC
    """

    rows = con.execute(sql, params + [as_of] + params).fetchall()
    return [
        HoldingItem(
            fund_id=r[0], fund_name=r[1], units_held=round(r[2], 4),
            price_gbp=round(r[3], 4), value_gbp=round(r[4], 2),
            cost_basis_gbp=round(r[5], 2), unrealised_gain_gbp=round(r[6], 2),
            unrealised_gain_pct=r[7], percentage=r[8],
        )
        for r in rows
    ]
