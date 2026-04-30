import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { fetchTransactions } from '../api/transactions'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import type { Account } from '../types'

const TX_TYPES = ['BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT', 'CONTRIBUTION', 'FEE', 'INTEREST', 'REBATE', 'TRANSFER', 'OTHER']
const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 2 })

const TYPE_COLOURS: Record<string, string> = {
  BUY: 'bg-emerald-900/50 text-emerald-400',
  SELL: 'bg-red-900/50 text-red-400',
  SWITCH_IN: 'bg-cyan-900/50 text-cyan-400',
  SWITCH_OUT: 'bg-orange-900/50 text-orange-400',
  CONTRIBUTION: 'bg-indigo-900/50 text-indigo-400',
  FEE: 'bg-gray-800 text-gray-500',
  INTEREST: 'bg-yellow-900/50 text-yellow-400',
  REBATE: 'bg-purple-900/50 text-purple-400',
}

export default function Transactions() {
  const [page, setPage] = useState(1)
  const [account, setAccount] = useState<Account | undefined>()
  const [txType, setTxType] = useState('')

  const { data, loading, error } = useApi(
    () => fetchTransactions({ page, per_page: 50, account, type: txType || undefined }),
    [page, account, txType],
  )

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Transaction Log</h1>

      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-2 text-sm">
          {(['All', 'ISA', 'SIPP'] as const).map((opt) => {
            const acct = opt === 'All' ? undefined : (opt as Account)
            return (
              <button
                key={opt}
                onClick={() => { setAccount(acct); setPage(1) }}
                className={`px-3 py-1 rounded-full border transition-colors ${
                  account === acct
                    ? 'bg-indigo-600 border-indigo-600 text-white'
                    : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                }`}
              >
                {opt}
              </button>
            )
          })}
        </div>

        <select
          value={txType}
          onChange={(e) => { setTxType(e.target.value); setPage(1) }}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-md px-3 py-1 focus:outline-none focus:border-indigo-500"
        >
          <option value="">All types</option>
          {TX_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        {data && (
          <span className="text-sm text-gray-500 ml-auto">
            {data.total.toLocaleString()} transactions
          </span>
        )}
      </div>

      <Card>
        {loading || error ? (
          <StatusMessage loading={loading} error={error} />
        ) : !data?.items.length ? (
          <StatusMessage empty />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                    <th className="text-left pb-3">Date</th>
                    <th className="text-left pb-3">Account</th>
                    <th className="text-left pb-3">Type</th>
                    <th className="text-left pb-3">Fund</th>
                    <th className="text-right pb-3">Units</th>
                    <th className="text-right pb-3">Unit Price</th>
                    <th className="text-right pb-3">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {data.items.map((tx) => (
                    <tr key={tx.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="py-2.5 text-gray-400 tabular-nums">{tx.trade_date}</td>
                      <td className="py-2.5 text-gray-500 text-xs">{tx.account_id}</td>
                      <td className="py-2.5">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLOURS[tx.transaction_type] ?? 'bg-gray-800 text-gray-400'}`}>
                          {tx.transaction_type}
                        </span>
                      </td>
                      <td className="py-2.5 text-gray-300 max-w-[200px] truncate" title={tx.fund_name ?? undefined}>
                        {tx.fund_name ?? <span className="text-gray-600">—</span>}
                      </td>
                      <td className="py-2.5 text-right text-gray-400 tabular-nums">
                        {tx.quantity != null ? tx.quantity.toLocaleString('en-GB', { maximumFractionDigits: 4 }) : '—'}
                      </td>
                      <td className="py-2.5 text-right text-gray-400 tabular-nums">
                        {tx.unit_cost_pence != null ? `${(tx.unit_cost_pence / 100).toFixed(4)}p` : '—'}
                      </td>
                      <td className={`py-2.5 text-right tabular-nums font-medium ${tx.value_gbp >= 0 ? 'text-gray-200' : 'text-red-400'}`}>
                        {fmt.format(Math.abs(tx.value_gbp))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-800 text-sm">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 rounded border border-gray-700 text-gray-400 disabled:opacity-40 hover:border-gray-500 hover:text-gray-200 transition-colors"
              >
                ← Previous
              </button>
              <span className="text-gray-500">Page {page} of {totalPages}</span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1 rounded border border-gray-700 text-gray-400 disabled:opacity-40 hover:border-gray-500 hover:text-gray-200 transition-colors"
              >
                Next →
              </button>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
