import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { fetchHoldings } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import type { Account } from '../types'

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 2 })
const fmtUnits = (n: number) => n.toLocaleString('en-GB', { maximumFractionDigits: 4 })

export default function Holdings() {
  const [account, setAccount] = useState<Account | undefined>()
  const { data, loading, error } = useApi(() => fetchHoldings(account), [account])

  const totalValue = data?.reduce((s, h) => s + h.value_gbp, 0) ?? 0
  const totalGain = data?.reduce((s, h) => s + h.unrealised_gain_gbp, 0) ?? 0
  const totalCost = data?.reduce((s, h) => s + h.cost_basis_gbp, 0) ?? 0
  const totalGainPct = totalCost > 0 ? (totalGain / totalCost) * 100 : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Current Holdings</h1>
        <AccountFilter value={account} onChange={setAccount} />
      </div>

      {data && data.length > 0 && (
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total Value', value: fmt.format(totalValue), colour: 'text-indigo-400' },
            { label: 'Cost Basis', value: fmt.format(totalCost), colour: 'text-gray-300' },
            { label: 'Unrealised Gain', value: fmt.format(totalGain), colour: totalGain >= 0 ? 'text-emerald-400' : 'text-red-400' },
            { label: 'Return', value: `${totalGainPct.toFixed(1)}%`, colour: totalGainPct >= 0 ? 'text-emerald-400' : 'text-red-400' },
          ].map(({ label, value, colour }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
              <p className={`text-xl font-semibold ${colour}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      <Card>
        {loading || error || !data?.length ? (
          <StatusMessage loading={loading} error={error} empty={!data?.length} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                  <th className="text-left pb-3">Fund</th>
                  <th className="text-right pb-3">Units</th>
                  <th className="text-right pb-3">Price</th>
                  <th className="text-right pb-3">Value</th>
                  <th className="text-right pb-3">Cost Basis</th>
                  <th className="text-right pb-3">Gain / Loss</th>
                  <th className="text-right pb-3">Return</th>
                  <th className="text-right pb-3">Weight</th>
                  <th className="text-right pb-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {data.map((h) => (
                  <tr key={h.fund_id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-3 text-gray-200 font-medium max-w-[200px] truncate" title={h.fund_name}>
                      {h.fund_short_name}
                    </td>
                    <td className="py-3 text-right text-gray-400 tabular-nums">{fmtUnits(h.units_held)}</td>
                    <td className="py-3 text-right text-gray-400 tabular-nums">{fmt.format(h.price_gbp)}</td>
                    <td className="py-3 text-right text-gray-200 tabular-nums font-medium">{fmt.format(h.value_gbp)}</td>
                    <td className="py-3 text-right text-gray-400 tabular-nums">{fmt.format(h.cost_basis_gbp)}</td>
                    <td className={`py-3 text-right tabular-nums font-medium ${h.unrealised_gain_gbp >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {h.unrealised_gain_gbp >= 0 ? '+' : ''}{fmt.format(h.unrealised_gain_gbp)}
                    </td>
                    <td className={`py-3 text-right tabular-nums ${h.unrealised_gain_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {h.unrealised_gain_pct >= 0 ? '+' : ''}{h.unrealised_gain_pct.toFixed(1)}%
                    </td>
                    <td className="py-3 text-right text-gray-500">{h.percentage.toFixed(1)}%</td>
                    <td className="py-3 text-right">
                      <Link to={`/funds/${h.fund_id}`} className="text-indigo-400 hover:text-indigo-300 text-xs">
                        Chart →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
