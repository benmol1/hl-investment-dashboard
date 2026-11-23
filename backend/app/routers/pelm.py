from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
import duckdb

from app.db import get_db
from app.models import PelmTransaction, PelmTransactionPage

router = APIRouter()

PELM_TX_TYPES = {
    "BUY",
    "SELL",
    "CASH_TRANSFER_IN",
    "WITHDRAWAL",
    "DEPOSIT_TRANSFER_IN",
    "DEPOSIT_TRANSFER_OUT",
    "STOCK_TRANSFER_IN",
    "CORPORATE_ACTION",
    "CASH_FRACTION",
    "OTHER",
}


@router.get("/transactions", response_model=PelmTransactionPage)
def list_pelm_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    tx_type: Optional[str] = Query(None, alias="type"),
    include_internal: bool = Query(
        False,
        description="Include the deposit-account sweeps, which are internal and net to ~zero.",
    ),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    PELM Will Trust ledger lines, most recent first. Trades and cash movements only: the ledger
    has no dividends or fees. Deposit sweeps are hidden unless include_internal is set.
    """
    filters: list[str] = []
    params: list = []

    if not include_internal:
        filters.append("category <> 'internal_transfer'")
    if tx_type and tx_type.upper() in PELM_TX_TYPES:
        filters.append("tx_type = ?")
        params.append(tx_type.upper())
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
               quantity, amount_gbp, notes
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
            )
            for r in rows
        ],
    )
