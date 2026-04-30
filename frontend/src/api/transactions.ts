import get from './client'
import type { TransactionPage } from '../types'
import type { Account } from '../types'

export const fetchTransactions = (opts: {
  page?: number
  per_page?: number
  account?: Account
  fund_id?: string
  type?: string
  from?: string
  to?: string
}) => get<TransactionPage>('/transactions', opts as Record<string, string | number | undefined>)
