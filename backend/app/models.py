from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: date
    value_gbp: float


class AllocationItem(BaseModel):
    fund_id: str
    fund_name: str
    fund_short_name: str
    units_held: float
    price_gbp: float
    value_gbp: float
    percentage: float


class InflowPoint(BaseModel):
    date: date
    portfolio_value: float
    cumulative_inflows: float
    growth: float


class PerformancePoint(BaseModel):
    date: date
    indexed: float  # value indexed to 100 at the start date


class FundPerformanceResponse(BaseModel):
    fund_id: str
    fund_name: str
    fund_short_name: str
    start_date: date
    fund: list[PerformancePoint]
    FTSE100: list[PerformancePoint]
    SP500: list[PerformancePoint]
    NASDAQ: list[PerformancePoint]


class Fund(BaseModel):
    id: str
    name: str
    fund_short_name: Optional[str]
    isin: Optional[str]
    morningstar_code: Optional[str]
    is_active: bool


class Transaction(BaseModel):
    id: str
    account_id: str
    fund_id: Optional[str]
    fund_name: Optional[str]
    fund_short_name: Optional[str]
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


class HoldingItem(BaseModel):
    holding_type: str = "fund"  # 'fund' or 'cash'
    fund_id: Optional[str] = None
    fund_name: str
    fund_short_name: str
    units_held: Optional[float] = None
    price_gbp: Optional[float] = None
    value_gbp: float
    cost_basis_gbp: Optional[float] = None
    unrealised_gain_gbp: Optional[float] = None
    unrealised_gain_pct: Optional[float] = None
    percentage: float


class DataFreshness(BaseModel):
    transaction_date: Optional[datetime]
    price_date: Optional[datetime]


class IngestLogEntry(BaseModel):
    source: str
    latest_data_date: Optional[date]
    last_successful_at: Optional[datetime]
    last_rows_imported_at: Optional[datetime]


class FinancialYearContribution(BaseModel):
    financial_year: str
    isa_gbp: float
    sipp_gbp: float
    total_gbp: float


class SharpeRatios(BaseModel):
    trailing_12m: Optional[float]
    trailing_36m: Optional[float]


class PortfolioPerformanceResponse(BaseModel):
    start_date: date
    portfolio: list[PerformancePoint]
    FTSE100: list[PerformancePoint]
    SP500: list[PerformancePoint]
    NASDAQ: list[PerformancePoint]
    sharpe: dict[str, SharpeRatios]
