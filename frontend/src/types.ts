export interface TimeSeriesPoint {
  date: string
  value_gbp: number
}

export interface AllocationItem {
  fund_id: string
  fund_name: string
  units_held: number
  price_gbp: number
  value_gbp: number
  percentage: number
}

export interface ContributionPoint {
  date: string
  portfolio_value: number
  cumulative_contributions: number
  growth: number
}

export interface PerformancePoint {
  date: string
  indexed: number
}

export interface FundPerformanceResponse {
  fund_id: string
  fund_name: string
  start_date: string
  fund: PerformancePoint[]
  FTSE100: PerformancePoint[]
  SP500: PerformancePoint[]
  NASDAQ: PerformancePoint[]
}

export interface Fund {
  id: string
  name: string
  isin: string | null
  morningstar_code: string | null
  is_active: boolean
}

export interface Transaction {
  id: string
  account_id: string
  fund_id: string | null
  fund_name: string | null
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

export interface HoldingItem {
  fund_id: string
  fund_name: string
  units_held: number
  price_gbp: number
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
}

export type Account = 'ISA' | 'SIPP'
export type Benchmark = 'FTSE100' | 'SP500' | 'NASDAQ'
