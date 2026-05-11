from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
import duckdb

from app.db import get_db
from app.models import Fund, FundPerformanceResponse, PerformancePoint

router = APIRouter()


@router.get("", response_model=list[Fund])
def list_funds(
    active_only: bool = Query(False),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """List all funds, optionally filtered to currently active (held) ones."""
    sql = """
    SELECT fund_id, fund_name, NULL AS isin, morningstar_code,
           (investment_status_indicator = 'Holding') AS is_active
    FROM dim_fund
    WHERE fund_id != 'CASH'
    """
    if active_only:
        sql += " AND investment_status_indicator = 'Holding'"
    sql += " ORDER BY fund_name"
    rows = con.execute(sql).fetchall()
    return [
        Fund(id=r[0], name=r[1], isin=r[2], morningstar_code=r[3], is_active=bool(r[4]))
        for r in rows
    ]


@router.get("/{fund_id}/performance", response_model=FundPerformanceResponse)
def fund_performance(
    fund_id: str,
    from_date: Optional[date] = Query(None, alias="from", description="Defaults to first purchase date"),
    to_date: date = Query(default_factory=date.today, alias="to"),
    benchmark: Literal["FTSE100", "SP500", "NASDAQ"] = Query("FTSE100"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Fund NAV indexed to 100 at the start date (monthly), with a benchmark overlay.
    Uses fund price rather than portfolio value so the series reflects fund performance
    independent of when units were bought.
    """
    fund_row = con.execute(
        "SELECT fund_id, fund_name, first_investment_date FROM dim_fund WHERE fund_id = ?", (fund_id,)
    ).fetchone()
    if not fund_row:
        raise HTTPException(status_code=404, detail=f"Fund '{fund_id}' not found")

    fund_name = fund_row[1]

    if from_date is None:
        from_date = fund_row[2] if fund_row[2] else date(2017, 1, 1)

    # Monthly fund price at each month-end date
    fund_sql = """
    SELECT dd.date, idv.fund_price_gbp
    FROM int_daily_fund_values idv
    INNER JOIN dim_date dd ON dd.date_key = idv.date_key
    INNER JOIN dim_fund df ON df.fund_key = idv.fund_key
    WHERE df.fund_id = ?
      AND dd.date BETWEEN ? AND ?
      AND dd.month_end_indicator = 'Month End'
    GROUP BY dd.date, idv.fund_price_gbp
    ORDER BY dd.date
    """
    fund_rows = con.execute(fund_sql, [fund_id, from_date, to_date]).fetchall()

    if not fund_rows:
        return FundPerformanceResponse(
            fund_id=fund_id, fund_name=fund_name,
            start_date=from_date, fund=[], benchmark=[],
        )

    base_price = fund_rows[0][1]
    fund_series = [
        PerformancePoint(date=r[0], indexed=round(r[1] / base_price * 100, 4))
        for r in fund_rows if r[1] and r[1] > 0
    ]

    bench_rows = con.execute(
        """SELECT month_end_date, month_end_level
           FROM mart_benchmarks
           WHERE index_id = ? AND month_end_date BETWEEN ? AND ?
           ORDER BY month_end_date""",
        [benchmark, from_date, to_date],
    ).fetchall()

    benchmark_series: list[PerformancePoint] = []
    if bench_rows:
        base_level = bench_rows[0][1]
        benchmark_series = [
            PerformancePoint(date=r[0], indexed=round(r[1] / base_level * 100, 4))
            for r in bench_rows
        ]

    return FundPerformanceResponse(
        fund_id=fund_id,
        fund_name=fund_name,
        start_date=fund_series[0].date if fund_series else from_date,
        fund=fund_series,
        benchmark=benchmark_series,
    )
