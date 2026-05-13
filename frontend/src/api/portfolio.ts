import get from './client'
import type { TimeSeriesPoint, AllocationItem, ContributionPoint, PortfolioPerformanceResponse, HoldingItem, DataFreshness } from '../types'
import type { Account } from '../types'

export const fetchPortfolioValue = (from?: string, to?: string, account?: Account) =>
  get<TimeSeriesPoint[]>('/portfolio/value', { from, to, account })

export const fetchAllocation = (as_of?: string, account?: Account) =>
  get<AllocationItem[]>('/portfolio/allocation', { as_of, account })

export const fetchContributions = (from?: string, to?: string, account?: Account) =>
  get<ContributionPoint[]>('/portfolio/contributions', { from, to, account })

export const fetchPortfolioPerformance = (from?: string, to?: string, account?: Account) =>
  get<PortfolioPerformanceResponse>('/portfolio/performance', { from, to, account })

export const fetchHoldings = (account?: Account) =>
  get<HoldingItem[]>('/portfolio/holdings', { account })

export const fetchFreshness = () =>
  get<DataFreshness>('/portfolio/freshness')
