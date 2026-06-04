from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
import duckdb

from app.db import get_db
from app.models import (
    TimeSeriesPoint,
    AllocationItem,
    InflowPoint,
    PerformancePoint,
    PortfolioPerformanceResponse,
    SharpeRatios,
    HoldingItem,
    DataFreshness,
    IngestLogEntry,
    FinancialYearContribution,
)

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
    FROM mart_portfolio_value_daily
    WHERE valuation_date BETWEEN ? AND ?
    {account_filter}
    GROUP BY valuation_date
    ORDER BY valuation_date
    """
    rows = con.execute(sql, params).fetchall()
    return [TimeSeriesPoint(date=r[0], value_gbp=r[1]) for r in rows]


@router.get("/allocation", response_model=list[AllocationItem])
def portfolio_allocation(
    as_of: Optional[date] = Query(
        None, description="Date to calculate allocation (defaults to latest price date)"
    ),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    if as_of is None:
        result = con.execute(
            "SELECT MAX(dd.date) FROM fct_holdings_daily fdh INNER JOIN dim_date dd ON dd.date_key = fdh.date_key"
        ).fetchone()
        as_of = result[0] if result and result[0] else date.today()

    account_filter = "AND da.account_name = ?" if account else ""

    sql = f"""
    WITH target_date AS (
        SELECT MAX(fdh.date_key) AS date_key
        FROM fct_holdings_daily fdh
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
    FROM fct_holdings_daily fdh
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
            fund_id=r[0],
            fund_name=r[1],
            fund_short_name=r[2] or r[1],
            units_held=r[3],
            price_gbp=r[4],
            value_gbp=r[5],
            percentage=r[6],
        )
        for r in rows
    ]


@router.get("/inflows", response_model=list[InflowPoint])
def inflows_vs_growth(
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
        valuation_date                                                    AS date,
        SUM(portfolio_value_gbp)                                         AS portfolio_value,
        SUM(cumulative_inflows_gbp)                                      AS cumulative_inflows,
        ROUND(SUM(portfolio_value_gbp) - SUM(cumulative_inflows_gbp), 2) AS growth
    FROM mart_portfolio_inflows_daily
    WHERE valuation_date BETWEEN ? AND ?
    {account_filter}
    GROUP BY valuation_date
    ORDER BY valuation_date
    """
    rows = con.execute(sql, params).fetchall()
    return [
        InflowPoint(
            date=r[0],
            portfolio_value=r[1],
            cumulative_inflows=r[2],
            growth=r[3],
        )
        for r in rows
    ]


@router.get(
    "/contributions/financial-year", response_model=list[FinancialYearContribution]
)
def contributions_by_financial_year(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    sql = """
    SELECT
        financial_year,
        SUM(CASE WHEN account_name = 'ISA'  THEN contributions_gbp ELSE 0 END) AS isa_gbp,
        SUM(CASE WHEN account_name = 'SIPP' THEN contributions_gbp ELSE 0 END) AS sipp_gbp,
        SUM(contributions_gbp)                                                  AS total_gbp
    FROM mart_contributions_by_financial_year
    GROUP BY financial_year
    ORDER BY financial_year
    """
    rows = con.execute(sql).fetchall()
    return [
        FinancialYearContribution(
            financial_year=r[0], isa_gbp=r[1], sipp_gbp=r[2], total_gbp=r[3]
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
    Portfolio investment return (Modified Dietz, inflow-adjusted) indexed to 100
    at from_date, plus all three benchmark indices indexed to 100 at the same start date.
    Both series use calendar month-end dates.
    """
    account_filter = "AND account_name = ?" if account else ""
    params: list = [from_date, to_date]
    if account:
        params.append(account)

    # Compound monthly Modified Dietz returns from mart_portfolio_returns_monthly.
    # Aggregate across accounts (sum weighted by BMV) when no account filter is applied.
    returns_sql = f"""
    SELECT
        month_end_date,
        CASE
            WHEN SUM(prev_month_end_value_gbp + 0.5 * month_inflows_gbp) = 0 THEN 0
            ELSE SUM(monthly_return * (prev_month_end_value_gbp + 0.5 * month_inflows_gbp))
                 / SUM(prev_month_end_value_gbp + 0.5 * month_inflows_gbp)
        END AS monthly_return
    FROM mart_portfolio_returns_monthly
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
               FROM mart_benchmarks_monthly
               WHERE index_id = ? AND month_end_date BETWEEN ? AND ?
               ORDER BY month_end_date""",
            [index_id, start_date, to_date],
        ).fetchall()
        if not rows:
            return []
        base = rows[0][1]
        return [
            PerformancePoint(date=r[0], indexed=round(r[1] / base * 100, 4))
            for r in rows
        ]

    # Latest Sharpe ratios — trailing windows are independent of the chart start date,
    # so we take the most recent row up to to_date.
    portfolio_sharpe_sql = f"""
    SELECT
        SUM(trailing_12m_sharpe * prev_month_end_value_gbp)
            / NULLIF(SUM(CASE WHEN trailing_12m_sharpe IS NOT NULL THEN prev_month_end_value_gbp END), 0),
        SUM(trailing_36m_sharpe * prev_month_end_value_gbp)
            / NULLIF(SUM(CASE WHEN trailing_36m_sharpe IS NOT NULL THEN prev_month_end_value_gbp END), 0)
    FROM mart_portfolio_returns_monthly
    WHERE month_end_date = (SELECT MAX(month_end_date) FROM mart_portfolio_returns_monthly WHERE month_end_date <= ?)
    {account_filter}
    """
    sharpe_params = [to_date] + ([account] if account else [])
    ps = con.execute(portfolio_sharpe_sql, sharpe_params).fetchone()

    bench_sharpe_rows = con.execute(
        """SELECT index_id, trailing_12m_sharpe, trailing_36m_sharpe
           FROM mart_benchmarks_monthly
           WHERE year_month = (SELECT MAX(year_month) FROM mart_benchmarks_monthly WHERE month_end_date <= ?)""",
        [to_date],
    ).fetchall()
    bench_sharpe = {
        r[0]: SharpeRatios(trailing_12m=r[1], trailing_36m=r[2])
        for r in bench_sharpe_rows
    }

    sharpe = {
        "portfolio": SharpeRatios(
            trailing_12m=ps[0] if ps else None, trailing_36m=ps[1] if ps else None
        ),
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
    account_filter = "WHERE mhl.account_name = ?" if account else ""
    params: list = [account] if account else []

    sql = f"""
    SELECT
        mhl.holding_type                                                                        AS holding_type,
        df.fund_id,
        COALESCE(mhl.fund_name, mhl.account_name || ' Cash')                                    AS fund_name,
        COALESCE(df.fund_short_name, mhl.account_name || ' Cash')                               AS fund_short_name,
        SUM(mhl.units_held)                                                                     AS units_held,
        MAX(mhl.fund_price_gbp)                                                                 AS price_gbp,
        SUM(mhl.value_gbp)                                                                      AS value_gbp,
        SUM(mhl.cost_basis_gbp)                                                                 AS cost_basis_gbp,
        SUM(mhl.unrealised_gain_gbp)                                                            AS unrealised_gain_gbp,
        CASE
            WHEN mhl.holding_type = 'Cash' THEN NULL
            WHEN SUM(mhl.cost_basis_gbp) > 0
                 THEN ROUND((SUM(mhl.value_gbp) - SUM(mhl.cost_basis_gbp))
                            / SUM(mhl.cost_basis_gbp) * 100.0, 2)
            ELSE 0.0
        END                                                                                     AS unrealised_gain_pct
    FROM mart_holdings_latest mhl
    LEFT JOIN dim_fund df ON df.fund_name = mhl.fund_name
    {account_filter}
    GROUP BY mhl.holding_type, df.fund_id,
             COALESCE(mhl.fund_name, mhl.account_name || ' Cash'),
             COALESCE(df.fund_short_name, mhl.account_name || ' Cash')
    ORDER BY CASE WHEN mhl.holding_type = 'Fund' THEN 0 ELSE 1 END,
             SUM(mhl.value_gbp) DESC
    """
    rows = con.execute(sql, params).fetchall()

    total_value = sum(r[6] for r in rows)

    def pct(v: float) -> float:
        return round(v / total_value * 100, 2) if total_value > 0 else 0.0

    return [
        HoldingItem(
            holding_type=r[0].lower(),
            fund_id=r[1],
            fund_name=r[2],
            fund_short_name=r[3],
            units_held=round(r[4], 4) if r[4] is not None else None,
            price_gbp=round(r[5], 4) if r[5] is not None else None,
            value_gbp=round(r[6], 2),
            cost_basis_gbp=r[7],
            unrealised_gain_gbp=r[8],
            unrealised_gain_pct=r[9],
            percentage=pct(r[6]),
        )
        for r in rows
    ]


@router.get("/freshness", response_model=DataFreshness)
def portfolio_freshness(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    tx = con.execute(
        "SELECT MAX(run_at) FROM ingest_log WHERE source = 'transactions' AND status = 'success' AND rows_inserted > 0"
    ).fetchone()
    prices = con.execute(
        "SELECT MAX(run_at) FROM ingest_log WHERE source = 'prices' AND status = 'success' AND rows_inserted > 0"
    ).fetchone()
    return DataFreshness(
        transaction_date=tx[0] if tx else None,
        price_date=prices[0] if prices else None,
    )


@router.get("/ingest-log", response_model=list[IngestLogEntry])
def ingest_log_summary(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    def _log_stats(source: str):
        last_successful = con.execute(
            "SELECT MAX(run_at) FROM ingest_log WHERE source = ? AND status = 'success'",
            (source,),
        ).fetchone()[0]
        last_rows_imported = con.execute(
            "SELECT MAX(run_at) FROM ingest_log WHERE source = ? AND status = 'success' AND rows_inserted > 0",
            (source,),
        ).fetchone()[0]
        return last_successful, last_rows_imported

    tx_last_successful, tx_last_rows = _log_stats("transactions")
    tx_latest_date = con.execute("SELECT MAX(trade_date) FROM transactions").fetchone()[
        0
    ]

    pr_last_successful, pr_last_rows = _log_stats("prices")
    pr_latest_date = con.execute("SELECT MAX(date) FROM prices").fetchone()[0]

    return [
        IngestLogEntry(
            source="transactions",
            latest_data_date=tx_latest_date,
            last_successful_at=tx_last_successful,
            last_rows_imported_at=tx_last_rows,
        ),
        IngestLogEntry(
            source="prices",
            latest_data_date=pr_latest_date,
            last_successful_at=pr_last_successful,
            last_rows_imported_at=pr_last_rows,
        ),
    ]
