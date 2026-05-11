from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
import duckdb

from app.db import get_db
from app.models import Transaction, TransactionPage

router = APIRouter()

VALID_TYPES = {
    "BUY", "SELL", "SWITCH_IN", "SWITCH_OUT",
    "CONTRIBUTION", "FEE", "INTEREST", "REBATE", "TRANSFER", "REJECTED", "OTHER",
}

_BASE_JOINS = """
FROM fct_transactions ft
INNER JOIN dim_account          da  ON da.account_key           = ft.account_key
LEFT JOIN  dim_fund             df  ON df.fund_key              = ft.fund_key
INNER JOIN dim_transaction_type dtt ON dtt.transaction_type_key = ft.transaction_type_key
INNER JOIN dim_date             tdd ON tdd.date_key             = ft.trade_date_key
LEFT JOIN  dim_date             sdd ON sdd.date_key             = ft.settle_date_key
"""


@router.get("", response_model=TransactionPage)
def list_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    account: Optional[Literal["ISA", "SIPP"]] = None,
    fund_id: Optional[str] = None,
    tx_type: Optional[str] = Query(None, alias="type"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """Paginated transaction log with optional filters. Results are ordered most-recent first."""
    filters = []
    params: list = []

    if account:
        filters.append("da.account_name = ?")
        params.append(account)
    if fund_id:
        filters.append("df.fund_id = ?")
        params.append(fund_id)
    if tx_type and tx_type.upper() in VALID_TYPES:
        filters.append("dtt.transaction_type = ?")
        params.append(tx_type.upper())
    if from_date:
        filters.append("tdd.date >= ?")
        params.append(from_date)
    if to_date:
        filters.append("tdd.date <= ?")
        params.append(to_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    count_sql = f"SELECT COUNT(*) {_BASE_JOINS} {where}"
    total = con.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * per_page
    rows_sql = f"""
    SELECT
        ft.transaction_id          AS id,
        da.account_name            AS account_id,
        df.fund_id,
        df.fund_name,
        tdd.date                   AS trade_date,
        sdd.date                   AS settle_date,
        ft.transaction_reference   AS reference,
        dtt.transaction_type,
        dtt.transaction_subtype,
        NULL                       AS unit_cost_pence,
        ft.quantity,
        ft.value_gbp
    {_BASE_JOINS}
    {where}
    ORDER BY tdd.date DESC, ft.transaction_id
    LIMIT ? OFFSET ?
    """
    rows = con.execute(rows_sql, params + [per_page, offset]).fetchall()

    items = [
        Transaction(
            id=r[0], account_id=r[1], fund_id=r[2], fund_name=r[3],
            trade_date=r[4], settle_date=r[5], reference=r[6],
            transaction_type=r[7], transaction_subtype=r[8],
            unit_cost_pence=r[9], quantity=r[10], value_gbp=r[11],
        )
        for r in rows
    ]

    return TransactionPage(total=total, page=page, per_page=per_page, items=items)
