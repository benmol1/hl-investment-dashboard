import get from './client'
import type { Fund, FundPerformanceResponse } from '../types'
import type { Benchmark } from '../types'

export const fetchFunds = (active_only?: boolean) =>
  get<Fund[]>('/funds', { active_only })

export const fetchFundPerformance = (fund_id: string, from?: string, to?: string, benchmark?: Benchmark) =>
  get<FundPerformanceResponse>(`/funds/${fund_id}/performance`, { from, to, benchmark })
