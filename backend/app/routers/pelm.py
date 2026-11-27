from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
import duckdb

from app.db import get_db
from app.models import (
    PelmCompositionPoint,
    PelmIncomePeriod,
    PelmIncomeResponse,
    PelmReconciliationRow,
    PelmTransaction,
    PelmTransactionPage,
)

router = APIRouter()

PELM_TX_TYPES = {
    "BUY",
    "SELL",
    "CASH_TRANSFER_IN",
    "WITHDRAWAL",
    "INCOME_DISTRIBUTION",
    "DIVIDEND",
    "INTEREST",
    "FX_COMMISSION",
    "FEE",
    "FEE_VAT",
    "DEPOSIT_TRANSFER_IN",
    "DEPOSIT_TRANSFER_OUT",
    "SETTLEMENT_TRANSFER",
    "STOCK_TRANSFER_IN",
    "CORPORATE_ACTION",
    "CASH_FRACTION",
    "OTHER",
}
PELM_CATEGORIES = {
    "trade",
    "external_flow",
    "income",
    "fee",
    "internal_transfer",
    "corporate_action",
    "other",
}


@router.get("/composition", response_model=list[PelmCompositionPoint])
def pelm_composition(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    """Month-end split of the trust between cash and investments (ledger months only)."""
    rows = con.execute(
        """
        SELECT month_end_date, cash_balance_gbp, invested_value_gbp
        FROM mart_portfolio_snapshot_monthly
        WHERE account_name = 'PELM'
          AND cash_balance_gbp IS NOT NULL AND invested_value_gbp IS NOT NULL
        ORDER BY month_end_date
        """
    ).fetchall()
    return [
        PelmCompositionPoint(date=r[0], cash_gbp=r[1], invested_gbp=r[2]) for r in rows
    ]


@router.get("/transactions", response_model=PelmTransactionPage)
def list_pelm_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    tx_type: Optional[str] = Query(None, alias="type"),
    category: Optional[str] = Query(
        None, description="trade, external_flow, income, fee, corporate_action, other"
    ),
    include_internal: bool = Query(
        False,
        description="Include the deposit and settlement sweeps, which move cash within the trust.",
    ),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    PELM Will Trust ledger lines from all four sub-ledgers, most recent first. Dividends,
    interest and fees exist only for the periods whose ledgers were supplied. Deposit and
    settlement sweeps are hidden unless include_internal is set.
    """
    filters: list[str] = []
    params: list = []

    filters.append("category <> 'opening_balance'")
    if not include_internal:
        filters.append("category <> 'internal_transfer'")
    if tx_type and tx_type.upper() in PELM_TX_TYPES:
        filters.append("tx_type = ?")
        params.append(tx_type.upper())
    if category and category.lower() in PELM_CATEGORIES:
        filters.append("category = ?")
        params.append(category.lower())
    if from_date:
        filters.append("tx_date >= ?")
        params.append(from_date)
    if to_date:
        filters.append("tx_date <= ?")
        params.append(to_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    total = con.execute(
        f"SELECT COUNT(*) FROM fct_pelm_transactions {where}", params
    ).fetchone()[0]

    rows = con.execute(
        f"""
        SELECT transaction_id, tx_date, reference, tx_type, category, security,
               quantity, amount_gbp, notes, ledger
        FROM fct_pelm_transactions
        {where}
        ORDER BY tx_date DESC, reference DESC, security
        LIMIT ? OFFSET ?
        """,
        params + [per_page, (page - 1) * per_page],
    ).fetchall()

    return PelmTransactionPage(
        total=total,
        page=page,
        per_page=per_page,
        items=[
            PelmTransaction(
                id=r[0],
                tx_date=r[1],
                reference=r[2],
                tx_type=r[3],
                category=r[4],
                security=r[5],
                quantity=r[6],
                amount_gbp=r[7],
                notes=r[8],
                ledger=r[9],
            )
            for r in rows
        ],
    )


@router.get("/income", response_model=PelmIncomeResponse)
def pelm_income(
    grain: Literal["quarter", "month"] = "quarter",
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    PELM income (dividends, interest), costs (FX commission, custody fee) and income paid out to
    the beneficiary, by calendar quarter or month. Only periods with at least one month of
    income ledgers are returned; *_complete says whether every month in the period is covered.
    """
    period_sql = (
        "strftime(month_end_date, '%Y') || '-Q' || cast(quarter(month_end_date) AS VARCHAR)"
        if grain == "quarter"
        else "year_month"
    )
    rows = con.execute(
        f"""
        SELECT
            {period_sql}                                         AS period,
            date_trunc('quarter', MIN(month_end_date))           AS q_start,
            MIN(date_trunc('month', month_end_date))             AS m_start,
            MAX(month_end_date)                                  AS period_end,
            SUM(dividends_gbp), SUM(interest_gbp), SUM(income_gbp),
            SUM(fx_commission_gbp), SUM(custody_fees_gbp), SUM(income_distributed_gbp),
            BOOL_AND(income_coverage_indicator = 'Complete')
                AND COUNT(*) = {3 if grain == "quarter" else 1}  AS income_complete,
            BOOL_AND(fees_coverage_indicator = 'Complete')
                AND COUNT(*) = {3 if grain == "quarter" else 1}  AS fees_complete
        FROM mart_pelm_income_monthly
        GROUP BY 1
        HAVING BOOL_OR(income_coverage_indicator = 'Complete')
        ORDER BY 1
        """
    ).fetchall()
    latest = con.execute(
        """SELECT trailing_12m_income_gbp, trailing_12m_income_yield
           FROM mart_pelm_income_monthly ORDER BY year_month DESC LIMIT 1"""
    ).fetchone()
    return PelmIncomeResponse(
        periods=[
            PelmIncomePeriod(
                period=r[0],
                period_start=r[1] if grain == "quarter" else r[2],
                period_end=r[3],
                dividends_gbp=r[4],
                interest_gbp=r[5],
                income_gbp=r[6],
                fx_commission_gbp=r[7],
                custody_fees_gbp=r[8],
                income_distributed_gbp=r[9],
                income_complete=bool(r[10]),
                fees_complete=bool(r[11]),
            )
            for r in rows
        ],
        trailing_12m_income_gbp=latest[0] if latest else None,
        trailing_12m_income_yield=latest[1] if latest else None,
    )


@router.get("/reconciliation", response_model=list[PelmReconciliationRow])
def pelm_reconciliation(con: duckdb.DuckDBPyConnection = Depends(get_db)):
    """Barratt & Cooke's reported total return per report period beside the dashboard's own."""
    rows = con.execute(
        """
        SELECT period_start, period_end, source, reported_return, dashboard_return,
               difference_pp, net_outflows_gbp, cash_flow_coverage_indicator
        FROM mart_pelm_return_reconciliation
        ORDER BY period_start
        """
    ).fetchall()
    return [
        PelmReconciliationRow(
            period_start=r[0],
            period_end=r[1],
            source=r[2],
            reported_return=r[3],
            dashboard_return=r[4],
            difference_pp=r[5],
            net_outflows_gbp=r[6],
            coverage=r[7],
        )
        for r in rows
    ]
