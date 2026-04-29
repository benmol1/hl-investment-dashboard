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
    sql = "SELECT id, name, isin, morningstar_code, is_active FROM funds WHERE id != 'CASH'"
    if active_only:
        sql += " AND is_active = TRUE"
    sql += " ORDER BY name"
    rows = con.execute(sql).fetchall()
    return [
        Fund(id=r[0], name=r[1], isin=r[2], morningstar_code=r[3], is_active=r[4])
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
    Fund value over time, indexed to 100 at the start date, with a benchmark overlay.
    The benchmark is also indexed to 100 at the same start date.
    """
    # Verify fund exists
    fund_row = con.execute(
        "SELECT id, name FROM funds WHERE id = ?", (fund_id,)
    ).fetchone()
    if not fund_row:
        raise HTTPException(status_code=404, detail=f"Fund '{fund_id}' not found")

    fund_name = fund_row[1]

    # Default start date: first trade date for this fund
    if from_date is None:
        result = con.execute(
            "SELECT MIN(trade_date) FROM transactions WHERE fund_id = ?", (fund_id,)
        ).fetchone()
        from_date = result[0] if result and result[0] else date(2017, 1, 1)

    # Fund value series: units × price on each price date
    fund_sql = """
    WITH delta AS (
        SELECT fund_id, trade_date,
               SUM(CASE WHEN value_gbp < 0 THEN quantity ELSE -quantity END) AS unit_delta
        FROM transactions
        WHERE fund_id = ? AND transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
          AND quantity IS NOT NULL
        GROUP BY fund_id, trade_date
    ),
    running AS (
        SELECT fund_id, trade_date,
               SUM(unit_delta) OVER (ORDER BY trade_date) AS units_held
        FROM delta
    )
    SELECT p.date, r.units_held * p.price_pence / 100.0 AS value_gbp
    FROM prices p
    ASOF JOIN running r ON (p.fund_id = r.fund_id AND p.date >= r.trade_date)
    WHERE p.fund_id = ? AND p.date BETWEEN ? AND ?
    ORDER BY p.date
    """
    fund_rows = con.execute(fund_sql, [fund_id, fund_id, from_date, to_date]).fetchall()

    if not fund_rows:
        return FundPerformanceResponse(
            fund_id=fund_id, fund_name=fund_name,
            start_date=from_date, fund=[], benchmark=[],
        )

    # Index fund values to 100 at first data point
    base_value = fund_rows[0][1]
    fund_series = [
        PerformancePoint(date=r[0], indexed=round(r[1] / base_value * 100, 4))
        for r in fund_rows
        if r[1] and r[1] > 0
    ]

    # Benchmark series for the same date range
    bench_rows = con.execute(
        """
        SELECT date, level FROM benchmarks
        WHERE index_id = ? AND date BETWEEN ? AND ?
        ORDER BY date
        """,
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
