from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
import duckdb

from app.db import get_db
from app.models import TimeSeriesPoint, AllocationItem, ContributionPoint, PerformancePoint, PortfolioPerformanceResponse, HoldingItem

router = APIRouter()


@router.get("/value", response_model=list[TimeSeriesPoint])
def portfolio_value(
    from_date: date = Query(date(2017, 1, 1), alias="from"),
    to_date: date = Query(default_factory=date.today, alias="to"),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    account_filter = "AND account_name = ?" if account else ""
    params: list = [from_date, to_date]
    if account:
        params.append(account)

    sql = f"""
    SELECT valuation_date AS date, SUM(portfolio_value_gbp) AS value_gbp
    FROM mart_daily_portfolio_value
    WHERE valuation_date BETWEEN ? AND ?
    {account_filter}
    GROUP BY valuation_date
    ORDER BY valuation_date
    """
    rows = con.execute(sql, params).fetchall()
    return [TimeSeriesPoint(date=r[0], value_gbp=r[1]) for r in rows]


@router.get("/allocation", response_model=list[AllocationItem])
def portfolio_allocation(
    as_of: Optional[date] = Query(None, description="Date to calculate allocation (defaults to latest price date)"),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    if as_of is None:
        result = con.execute(
            "SELECT MAX(dd.date) FROM fct_daily_holdings fdh INNER JOIN dim_date dd ON dd.date_key = fdh.date_key"
        ).fetchone()
        as_of = result[0] if result and result[0] else date.today()

    account_filter = "AND da.account_name = ?" if account else ""

    sql = f"""
    WITH target_date AS (
        SELECT MAX(fdh.date_key) AS date_key
        FROM fct_daily_holdings fdh
        INNER JOIN dim_date dd ON dd.date_key = fdh.date_key
        WHERE fdh.holding_type = 'Fund'
          AND dd.date <= ?
    )
    SELECT
        df.fund_id,
        df.fund_name,
        SUM(fdh.units_held)        AS units_held,
        MAX(fdh.fund_price_gbp)    AS price_gbp,
        SUM(fdh.value_gbp)         AS value_gbp,
        ROUND(SUM(fdh.value_gbp) / SUM(SUM(fdh.value_gbp)) OVER () * 100.0, 2) AS percentage
    FROM fct_daily_holdings fdh
    INNER JOIN target_date td  ON td.date_key    = fdh.date_key
    INNER JOIN dim_fund    df  ON df.fund_key    = fdh.fund_key
    INNER JOIN dim_account da  ON da.account_key = fdh.account_key
    WHERE fdh.holding_type = 'Fund'
      AND fdh.units_held >= 0.01
      {account_filter}
    GROUP BY df.fund_id, df.fund_name
    ORDER BY value_gbp DESC
    """
    params = [as_of] + ([account] if account else [])

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
    account_filter = "AND account_name = ?" if account else ""
    params: list = [from_date, to_date]
    if account:
        params.append(account)

    sql = f"""
    SELECT
        valuation_date                                                        AS date,
        SUM(portfolio_value_gbp)                                             AS portfolio_value,
        SUM(cumulative_contributions_gbp)                                    AS cumulative_contributions,
        ROUND(SUM(portfolio_value_gbp) - SUM(cumulative_contributions_gbp), 2) AS growth
    FROM mart_portfolio_contributions
    WHERE valuation_date BETWEEN ? AND ?
    {account_filter}
    GROUP BY valuation_date
    ORDER BY valuation_date
    """
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
    Monthly portfolio value indexed to 100 at from_date, plus all three benchmark indices
    indexed to 100 at the same start date. Both series use month-end data.
    """
    account_filter = "AND account_name = ?" if account else ""
    params: list = [from_date, to_date]
    if account:
        params.append(account)

    value_sql = f"""
    SELECT month_end_date AS date, SUM(month_end_value_gbp) AS value_gbp
    FROM mart_monthly_snapshot
    WHERE month_end_date BETWEEN ? AND ?
    {account_filter}
    GROUP BY month_end_date
    ORDER BY month_end_date
    """
    value_rows = con.execute(value_sql, params).fetchall()

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
            """SELECT month_end_date, month_end_level
               FROM mart_benchmarks
               WHERE index_id = ? AND month_end_date BETWEEN ? AND ?
               ORDER BY month_end_date""",
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
    account_filter = "WHERE mch.account_name = ?" if account else ""
    params: list = [account] if account else []

    sql = f"""
    SELECT
        df.fund_id,
        mch.fund_name,
        SUM(mch.units_held)                                                                AS units_held,
        MAX(mch.fund_price_gbp)                                                            AS price_gbp,
        SUM(mch.value_gbp)                                                                 AS value_gbp,
        SUM(mch.cost_basis_gbp)                                                            AS cost_basis_gbp,
        SUM(mch.unrealised_gain_gbp)                                                       AS unrealised_gain_gbp,
        CASE WHEN SUM(mch.cost_basis_gbp) > 0
             THEN ROUND((SUM(mch.value_gbp) - SUM(mch.cost_basis_gbp))
                        / SUM(mch.cost_basis_gbp) * 100.0, 2)
             ELSE 0.0 END                                                                  AS unrealised_gain_pct,
        ROUND(SUM(mch.value_gbp) / SUM(SUM(mch.value_gbp)) OVER () * 100.0, 2)           AS percentage
    FROM mart_current_holdings mch
    INNER JOIN dim_fund df ON df.fund_name = mch.fund_name
    {account_filter}
    GROUP BY df.fund_id, mch.fund_name
    ORDER BY SUM(mch.value_gbp) DESC
    """
    rows = con.execute(sql, params).fetchall()
    return [
        HoldingItem(
            fund_id=r[0], fund_name=r[1], units_held=round(r[2], 4),
            price_gbp=round(r[3], 4), value_gbp=round(r[4], 2),
            cost_basis_gbp=round(r[5], 2), unrealised_gain_gbp=round(r[6], 2),
            unrealised_gain_pct=r[7], percentage=r[8],
        )
        for r in rows
    ]
