from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
import duckdb

from app.db import get_db
from app.models import TimeSeriesPoint, AllocationItem, ContributionPoint, PerformancePoint, PortfolioPerformanceResponse, SharpeRatios, HoldingItem, DataFreshness

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
        df.fund_short_name,
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
    GROUP BY df.fund_id, df.fund_name, df.fund_short_name
    ORDER BY value_gbp DESC
    """
    params = [as_of] + ([account] if account else [])

    rows = con.execute(sql, params).fetchall()
    return [
        AllocationItem(
            fund_id=r[0], fund_name=r[1], fund_short_name=r[2] or r[1], units_held=r[3],
            price_gbp=r[4], value_gbp=r[5], percentage=r[6],
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
    Portfolio investment return (Modified Dietz, contribution-adjusted) indexed to 100
    at from_date, plus all three benchmark indices indexed to 100 at the same start date.
    Both series use calendar month-end dates.
    """
    account_filter = "AND account_name = ?" if account else ""
    params: list = [from_date, to_date]
    if account:
        params.append(account)

    # Compound monthly Modified Dietz returns from mart_portfolio_returns.
    # Aggregate across accounts (sum weighted by BMV) when no account filter is applied.
    returns_sql = f"""
    SELECT
        month_end_date,
        CASE
            WHEN SUM(prev_month_end_value_gbp + 0.5 * month_contributions_gbp) = 0 THEN 0
            ELSE SUM(monthly_return * (prev_month_end_value_gbp + 0.5 * month_contributions_gbp))
                 / SUM(prev_month_end_value_gbp + 0.5 * month_contributions_gbp)
        END AS monthly_return
    FROM mart_portfolio_returns
    WHERE month_end_date BETWEEN ? AND ?
    {account_filter}
    GROUP BY month_end_date
    ORDER BY month_end_date
    """
    return_rows = con.execute(returns_sql, params).fetchall()

    portfolio_series: list[PerformancePoint] = []
    start_date = from_date
    if return_rows:
        start_date = return_rows[0][0]
        index = 100.0
        portfolio_series = []
        for i, r in enumerate(return_rows):
            if i > 0 and r[1] is not None:
                index = round(index * (1 + r[1]), 4)
            portfolio_series.append(PerformancePoint(date=r[0], indexed=index))

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

    # Latest Sharpe ratios — trailing windows are independent of the chart start date,
    # so we take the most recent row up to to_date.
    portfolio_sharpe_sql = f"""
    SELECT
        SUM(trailing_12m_sharpe * prev_month_end_value_gbp)
            / NULLIF(SUM(CASE WHEN trailing_12m_sharpe IS NOT NULL THEN prev_month_end_value_gbp END), 0),
        SUM(trailing_36m_sharpe * prev_month_end_value_gbp)
            / NULLIF(SUM(CASE WHEN trailing_36m_sharpe IS NOT NULL THEN prev_month_end_value_gbp END), 0)
    FROM mart_portfolio_returns
    WHERE month_end_date = (SELECT MAX(month_end_date) FROM mart_portfolio_returns WHERE month_end_date <= ?)
    {account_filter}
    """
    sharpe_params = [to_date] + ([account] if account else [])
    ps = con.execute(portfolio_sharpe_sql, sharpe_params).fetchone()

    bench_sharpe_rows = con.execute(
        """SELECT index_id, trailing_12m_sharpe, trailing_36m_sharpe
           FROM mart_benchmarks
           WHERE year_month = (SELECT MAX(year_month) FROM mart_benchmarks WHERE month_end_date <= ?)""",
        [to_date],
    ).fetchall()
    bench_sharpe = {r[0]: SharpeRatios(trailing_12m=r[1], trailing_36m=r[2]) for r in bench_sharpe_rows}

    sharpe = {
        'portfolio': SharpeRatios(trailing_12m=ps[0] if ps else None, trailing_36m=ps[1] if ps else None),
        **bench_sharpe,
    }

    return PortfolioPerformanceResponse(
        start_date=start_date,
        portfolio=portfolio_series,
        FTSE100=bench_series("FTSE100"),
        SP500=bench_series("SP500"),
        NASDAQ=bench_series("NASDAQ"),
        sharpe=sharpe,
    )


@router.get("/holdings", response_model=list[HoldingItem])
def portfolio_holdings(
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    account_filter = "WHERE mch.account_name = ?" if account else ""
    params: list = [account] if account else []

    fund_sql = f"""
    SELECT
        df.fund_id,
        mch.fund_name,
        df.fund_short_name,
        SUM(mch.units_held)                                                                AS units_held,
        MAX(mch.fund_price_gbp)                                                            AS price_gbp,
        SUM(mch.value_gbp)                                                                 AS value_gbp,
        SUM(mch.cost_basis_gbp)                                                            AS cost_basis_gbp,
        SUM(mch.unrealised_gain_gbp)                                                       AS unrealised_gain_gbp,
        CASE WHEN SUM(mch.cost_basis_gbp) > 0
             THEN ROUND((SUM(mch.value_gbp) - SUM(mch.cost_basis_gbp))
                        / SUM(mch.cost_basis_gbp) * 100.0, 2)
             ELSE 0.0 END                                                                  AS unrealised_gain_pct
    FROM mart_current_holdings mch
    INNER JOIN dim_fund df ON df.fund_name = mch.fund_name
    {account_filter}
    GROUP BY df.fund_id, mch.fund_name, df.fund_short_name
    ORDER BY SUM(mch.value_gbp) DESC
    """
    fund_rows = con.execute(fund_sql, params).fetchall()

    cash_account_filter = "AND da.account_name = ?" if account else ""
    cash_params: list = [account] if account else []
    cash_sql = f"""
    SELECT da.account_name, cp.cash_balance_gbp
    FROM fct_daily_cash_position cp
    INNER JOIN dim_account da ON da.account_key = cp.account_key
    WHERE 1=1 {cash_account_filter}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY cp.account_key ORDER BY cp.date_key DESC) = 1
    ORDER BY da.account_name
    """
    cash_rows = con.execute(cash_sql, cash_params).fetchall()

    total_fund_value = sum(r[5] for r in fund_rows)
    total_cash_value = sum(r[1] for r in cash_rows if r[1] is not None and r[1] > 0.01)
    total_value = total_fund_value + total_cash_value

    def pct(v: float) -> float:
        return round(v / total_value * 100, 2) if total_value > 0 else 0.0

    fund_items = [
        HoldingItem(
            holding_type='fund',
            fund_id=r[0], fund_name=r[1], fund_short_name=r[2] or r[1],
            units_held=round(r[3], 4), price_gbp=round(r[4], 4),
            value_gbp=round(r[5], 2), cost_basis_gbp=round(r[6], 2),
            unrealised_gain_gbp=round(r[7], 2), unrealised_gain_pct=r[8],
            percentage=pct(r[5]),
        )
        for r in fund_rows
    ]

    cash_items = [
        HoldingItem(
            holding_type='cash',
            fund_id=None,
            fund_name=f'{r[0]} Cash',
            fund_short_name=f'{r[0]} Cash',
            units_held=None, price_gbp=None,
            value_gbp=round(r[1], 2),
            cost_basis_gbp=round(r[1], 2),
            unrealised_gain_gbp=0.0, unrealised_gain_pct=0.0,
            percentage=pct(r[1]),
        )
        for r in cash_rows
        if r[1] is not None and r[1] > 0.01
    ]

    return fund_items + cash_items


@router.get("/freshness", response_model=DataFreshness)
def portfolio_freshness(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    tx_date = con.execute(
        "SELECT MAX(dd.date) FROM fct_transactions ft INNER JOIN dim_date dd ON dd.date_key = ft.trade_date_key"
    ).fetchone()
    price_date = con.execute(
        "SELECT MAX(dd.date) FROM fct_fund_prices_daily fp INNER JOIN dim_date dd ON dd.date_key = fp.date_key"
    ).fetchone()
    return DataFreshness(
        transaction_date=tx_date[0] if tx_date else None,
        price_date=price_date[0] if price_date else None,
    )
