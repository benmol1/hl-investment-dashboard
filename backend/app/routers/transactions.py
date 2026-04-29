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
    """
    Paginated transaction log with optional filters.
    Results are ordered most-recent first.
    """
    filters = []
    params: list = []

    if account:
        filters.append("t.account_id = ?")
        params.append(account)
    if fund_id:
        filters.append("t.fund_id = ?")
        params.append(fund_id)
    if tx_type and tx_type.upper() in VALID_TYPES:
        filters.append("t.transaction_type = ?")
        params.append(tx_type.upper())
    if from_date:
        filters.append("t.trade_date >= ?")
        params.append(from_date)
    if to_date:
        filters.append("t.trade_date <= ?")
        params.append(to_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    count_sql = f"SELECT COUNT(*) FROM transactions t {where}"
    total = con.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * per_page
    rows_sql = f"""
    SELECT
        t.id, t.account_id, t.fund_id, f.name AS fund_name,
        t.trade_date, t.settle_date, t.reference,
        t.transaction_type, t.transaction_subtype,
        t.unit_cost_pence, t.quantity, t.value_gbp
    FROM transactions t
    LEFT JOIN funds f ON f.id = t.fund_id
    {where}
    ORDER BY t.trade_date DESC, t.id
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
