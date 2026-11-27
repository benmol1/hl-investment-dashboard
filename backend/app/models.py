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


class PelmTransaction(BaseModel):
    id: str
    ledger: str  # capital, dividends, income or fees
    tx_date: date
    reference: Optional[str]
    tx_type: str
    category: str
    security: str
    quantity: Optional[float]
    amount_gbp: Optional[float]
    notes: str


class PelmTransactionPage(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[PelmTransaction]


class PelmCompositionPoint(BaseModel):
    date: date
    cash_gbp: float
    invested_gbp: float


class PelmIncomePeriod(BaseModel):
    period: str  # "2025-Q3" or "2025-07"
    period_start: date
    period_end: date
    dividends_gbp: float
    interest_gbp: float
    income_gbp: float
    fx_commission_gbp: float
    custody_fees_gbp: float
    income_distributed_gbp: float
    income_complete: bool  # dividends + income ledgers cover every month in the period
    fees_complete: bool  # a fees ledger covers every month in the period


class PelmIncomeResponse(BaseModel):
    periods: list[PelmIncomePeriod]
    trailing_12m_income_gbp: Optional[float]  # null until 12 complete months exist
    trailing_12m_income_yield: Optional[float]


class PelmReconciliationRow(BaseModel):
    period_start: date
    period_end: date
    source: str
    reported_return: float
    dashboard_return: Optional[float]
    difference_pp: Optional[float]
    net_outflows_gbp: Optional[float]
    coverage: str  # Complete, Incomplete or Missing months


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


class QuarterlyReturn(BaseModel):
    quarter: str  # "2025-Q3"
    start_date: date  # month-end before the quarter's first return month
    end_date: date
    months: int  # monthly returns linked; fewer than 3 means a partial quarter
    portfolio: float  # total return as a fraction
    flows_complete: bool  # every month's external cash flows are known
    estimated: bool  # incomplete months were filled with the best estimate
    FTSE100: Optional[float]
    SP500: Optional[float]
    NASDAQ: Optional[float]


class QuarterlyReturnsResponse(BaseModel):
    quarters: list[QuarterlyReturn]


class PortfolioPerformanceResponse(BaseModel):
    start_date: date
    portfolio: list[PerformancePoint]
    FTSE100: list[PerformancePoint]
    SP500: list[PerformancePoint]
    NASDAQ: list[PerformancePoint]
    sharpe: dict[str, SharpeRatios]
    # Month-ends whose external cash flows are not fully known (PELM months without a dividends
    # ledger): the portfolio return for those months is understated.
    incomplete_flow_dates: list[date] = []
