import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { fetchPelmTransactions } from '../api/transactions'
import Card from './Card'
import StatusMessage from './StatusMessage'
import DateDisplay from './DateDisplay'
import Cash from '../privacy/Cash'

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 2 })

const TYPE_LABELS: Record<string, string> = {
  BUY: 'Buy',
  SELL: 'Sell',
  CASH_TRANSFER_IN: 'Cash in',
  WITHDRAWAL: 'Withdrawal',
  STOCK_TRANSFER_IN: 'Stock in',
  DEPOSIT_TRANSFER_IN: 'From deposit',
  DEPOSIT_TRANSFER_OUT: 'To deposit',
  CORPORATE_ACTION: 'Corporate action',
  CASH_FRACTION: 'Cash fraction',
  OTHER: 'Other',
}

const TYPE_COLOURS: Record<string, string> = {
  BUY: 'bg-emerald-900/50 text-emerald-400',
  SELL: 'bg-red-900/50 text-red-400',
  CASH_TRANSFER_IN: 'bg-indigo-900/50 text-indigo-400',
  WITHDRAWAL: 'bg-orange-900/50 text-orange-400',
  STOCK_TRANSFER_IN: 'bg-cyan-900/50 text-cyan-400',
  CORPORATE_ACTION: 'bg-purple-900/50 text-purple-400',
  CASH_FRACTION: 'bg-yellow-900/50 text-yellow-400',
}

/** Ledger view for the PELM Will Trust: trades and cash movements only. */
export default function PelmTransactions() {
  const [page, setPage] = useState(1)
  const [txType, setTxType] = useState('')
  const [includeInternal, setIncludeInternal] = useState(false)

  const { data, loading, error } = useApi(
    () => fetchPelmTransactions({ page, per_page: 50, type: txType || undefined, include_internal: includeInternal }),
    [page, txType, includeInternal],
  )
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={txType}
          onChange={(e) => { setTxType(e.target.value); setPage(1) }}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-md px-3 py-1 focus:outline-none focus:border-indigo-500"
        >
          <option value="">All types</option>
          {Object.entries(TYPE_LABELS)
            .filter(([t]) => includeInternal || !t.startsWith('DEPOSIT_'))
            .map(([t, label]) => <option key={t} value={t}>{label}</option>)}
        </select>

        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
          <input
            type="checkbox"
            checked={includeInternal}
            onChange={(e) => {
              setIncludeInternal(e.target.checked)
              if (!e.target.checked && txType.startsWith('DEPOSIT_')) setTxType('')
              setPage(1)
            }}
          />
          Show deposit-account transfers
        </label>

        {data && (
          <span className="text-sm text-gray-500 ml-auto">{data.total.toLocaleString()} entries</span>
        )}
      </div>

      <p className="text-xs text-gray-500">
        Will Trust ledger: trades and cash movements only. It records no dividends or fees, and stock
        transferred in carries a quantity but no value.
      </p>

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
                    <th className="text-left pb-3">Type</th>
                    <th className="text-left pb-3">Security</th>
                    <th className="text-right pb-3 hidden sm:table-cell">Quantity</th>
                    <th className="text-right pb-3">Amount</th>
                    <th className="text-left pb-3 pl-4 hidden lg:table-cell">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {data.items.map((tx) => (
                    <tr key={tx.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="py-2.5 text-gray-400 tabular-nums whitespace-nowrap">
                        <DateDisplay iso={tx.tx_date} />
                      </td>
                      <td className="py-2.5 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLOURS[tx.tx_type] ?? 'bg-gray-800 text-gray-400'}`}>
                          {TYPE_LABELS[tx.tx_type] ?? tx.tx_type}
                        </span>
                      </td>
                      <td className="py-2.5 text-gray-300 max-w-[140px] sm:max-w-[240px] truncate" title={tx.security || undefined}>
                        {tx.security || <span className="text-gray-600">—</span>}
                      </td>
                      <td className="py-2.5 text-right text-gray-400 tabular-nums hidden sm:table-cell">
                        {tx.quantity != null ? tx.quantity.toLocaleString('en-GB', { maximumFractionDigits: 4 }) : '—'}
                      </td>
                      <td className={`py-2.5 text-right tabular-nums font-medium ${tx.amount_gbp != null && tx.amount_gbp < 0 ? 'text-red-400' : 'text-gray-200'}`}>
                        {tx.amount_gbp != null
                          ? <Cash>{fmt.format(Math.abs(tx.amount_gbp))}</Cash>
                          : <span className="text-gray-600">—</span>}
                      </td>
                      <td className="py-2.5 pl-4 text-gray-500 text-xs max-w-[260px] truncate hidden lg:table-cell" title={tx.notes || undefined}>
                        {tx.notes}
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
