export interface TimeSeriesPoint {
  date: string
  value_gbp: number
}

export interface AllocationItem {
  fund_id: string
  fund_name: string
  fund_short_name: string
  units_held: number
  price_gbp: number
  value_gbp: number
  percentage: number
}

export interface InflowPoint {
  date: string
  portfolio_value: number
  cumulative_inflows: number
  growth: number
}

export interface PerformancePoint {
  date: string
  indexed: number
}

export interface FundPerformanceResponse {
  fund_id: string
  fund_name: string
  fund_short_name: string
  start_date: string
  fund: PerformancePoint[]
  FTSE100: PerformancePoint[]
  SP500: PerformancePoint[]
  NASDAQ: PerformancePoint[]
}

export interface Fund {
  id: string
  name: string
  fund_short_name: string | null
  isin: string | null
  morningstar_code: string | null
  is_active: boolean
}

export interface Transaction {
  id: string
  account_id: string
  fund_id: string | null
  fund_name: string | null
  fund_short_name: string | null
  trade_date: string
  settle_date: string | null
  reference: string
  transaction_type: string
  transaction_subtype: string | null
  unit_cost_pence: number | null
  quantity: number | null
  value_gbp: number
}

export interface TransactionPage {
  total: number
  page: number
  per_page: number
  items: Transaction[]
}

export interface PelmTransaction {
  id: string
  tx_date: string
  reference: string | null
  tx_type: string
  category: string
  ledger: string  // 'capital' | 'dividends' | 'income' | 'fees'
  security: string
  quantity: number | null
  amount_gbp: number | null
  notes: string
}

export interface PelmTransactionPage {
  total: number
  page: number
  per_page: number
  items: PelmTransaction[]
}

export interface HoldingItem {
  holding_type: string  // 'fund' | 'cash'
  fund_id: string | null
  fund_name: string
  fund_short_name: string
  units_held: number | null
  price_gbp: number | null
  value_gbp: number
  cost_basis_gbp: number
  unrealised_gain_gbp: number
  unrealised_gain_pct: number
  percentage: number
}

export interface SharpeRatios {
  trailing_12m: number | null
  trailing_36m: number | null
}

export interface PortfolioPerformanceResponse {
  start_date: string
  portfolio: PerformancePoint[]
  FTSE100: PerformancePoint[]
  SP500: PerformancePoint[]
  NASDAQ: PerformancePoint[]
  sharpe: Record<string, SharpeRatios>
  /** Month-end dates whose return is understated because cash flows are unknown (PELM only). */
  incomplete_flow_dates?: string[]
}

export interface DataFreshness {
  transaction_date: string | null  // ISO datetime string
  price_date: string | null        // ISO datetime string
}

export interface IngestLogEntry {
  source: string
  latest_data_date: string | null
  last_successful_at: string | null
  last_rows_imported_at: string | null
}

export interface FinancialYearContribution {
  financial_year: string
  isa_gbp: number
  sipp_gbp: number
  total_gbp: number
}

export type Account = 'ISA' | 'SIPP' | 'PELM'
export type Benchmark = 'FTSE100' | 'SP500' | 'NASDAQ'

export interface PelmCompositionPoint {
  date: string
  cash_gbp: number
  invested_gbp: number
}

export interface PelmIncomePeriod {
  period: string        // '2025-Q3' or '2025-07'
  period_start: string
  period_end: string
  dividends_gbp: number
  interest_gbp: number
  income_gbp: number
  fx_commission_gbp: number
  custody_fees_gbp: number
  income_distributed_gbp: number
  income_complete: boolean
  fees_complete: boolean
}

export interface PelmIncomeResponse {
  periods: PelmIncomePeriod[]
  trailing_12m_income_gbp: number | null
  trailing_12m_income_yield: number | null
}

export interface PelmReconciliationRow {
  period_start: string
  period_end: string
  source: string
  reported_return: number    // fraction
  dashboard_return: number | null  // fraction
  difference_pp: number | null     // percentage points
  net_outflows_gbp: number | null
  coverage: string           // 'Complete' | 'Incomplete' | 'Missing months'
}
