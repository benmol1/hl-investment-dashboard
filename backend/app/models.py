from datetime import date
from typing import Optional
from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: date
    value_gbp: float


class AllocationItem(BaseModel):
    fund_id: str
    fund_name: str
    units_held: float
    price_gbp: float
    value_gbp: float
    percentage: float


class ContributionPoint(BaseModel):
    date: date
    portfolio_value: float
    cumulative_contributions: float
    growth: float


class PerformancePoint(BaseModel):
    date: date
    indexed: float  # value indexed to 100 at the start date


class FundPerformanceResponse(BaseModel):
    fund_id: str
    fund_name: str
    start_date: date
    fund: list[PerformancePoint]
    benchmark: list[PerformancePoint]


class Fund(BaseModel):
    id: str
    name: str
    isin: Optional[str]
    morningstar_code: Optional[str]
    is_active: bool


class Transaction(BaseModel):
    id: str
    account_id: str
    fund_id: Optional[str]
    fund_name: Optional[str]
    trade_date: date
    settle_date: Optional[date]
    reference: str
    transaction_type: str
    transaction_subtype: Optional[str]
    unit_cost_pence: Optional[float]
    quantity: Optional[float]
    value_gbp: float


class TransactionPage(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[Transaction]
