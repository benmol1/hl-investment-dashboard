import get from './client'
import type { TimeSeriesPoint, AllocationItem, InflowPoint, PortfolioPerformanceResponse, HoldingItem, DataFreshness, IngestLogEntry, FinancialYearContribution, QuarterlyReturnsResponse } from '../types'
import type { Account } from '../types'

export const fetchPortfolioValue = (from?: string, to?: string, account?: Account) =>
  get<TimeSeriesPoint[]>('/portfolio/value', { from, to, account })

export const fetchAllocation = (as_of?: string, account?: Account) =>
  get<AllocationItem[]>('/portfolio/allocation', { as_of, account })

export const fetchInflows = (from?: string, to?: string, account?: Account) =>
  get<InflowPoint[]>('/portfolio/inflows', { from, to, account })

/** `estimate` uses the best-estimate return for PELM months with incomplete cash flows. */
export const fetchPortfolioPerformance = (from?: string, to?: string, account?: Account, estimate = false) =>
  get<PortfolioPerformanceResponse>('/portfolio/performance', { from, to, account, estimate })

export const fetchQuarterlyReturns = (from?: string, to?: string, account?: Account, estimate = false) =>
  get<QuarterlyReturnsResponse>('/portfolio/returns/quarterly', { from, to, account, estimate })

export const fetchHoldings = (account?: Account) =>
  get<HoldingItem[]>('/portfolio/holdings', { account })

export const fetchFreshness = () =>
  get<DataFreshness>('/portfolio/freshness')

export const fetchIngestLog = () =>
  get<IngestLogEntry[]>('/portfolio/ingest-log')

export const fetchFinancialYearContributions = () =>
  get<FinancialYearContribution[]>('/portfolio/contributions/financial-year')
