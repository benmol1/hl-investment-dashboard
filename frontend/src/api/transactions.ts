import get from './client'
import type {
  PelmCompositionPoint, PelmIncomeResponse, PelmReconciliationRow, PelmTransactionPage, TransactionPage,
} from '../types'
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

export const fetchPelmTransactions = (opts: {
  page?: number
  per_page?: number
  type?: string
  category?: string
  include_internal?: boolean
  from?: string
  to?: string
}) => get<PelmTransactionPage>('/pelm/transactions', opts as Record<string, string | number | boolean | undefined>)

export const fetchPelmComposition = () => get<PelmCompositionPoint[]>('/pelm/composition')

export const fetchPelmIncome = (grain: 'quarter' | 'month' = 'quarter') =>
  get<PelmIncomeResponse>('/pelm/income', { grain })

export const fetchPelmReconciliation = () => get<PelmReconciliationRow[]>('/pelm/reconciliation')
