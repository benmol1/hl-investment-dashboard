import get from './client'
import type { Fund, FundPerformanceResponse } from '../types'

export const fetchFunds = (active_only?: boolean) =>
  get<Fund[]>('/funds', { active_only })

export const fetchFundPerformance = (fund_id: string, from?: string, to?: string) =>
  get<FundPerformanceResponse>(`/funds/${fund_id}/performance`, { from, to })
