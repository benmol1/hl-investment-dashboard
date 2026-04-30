import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { fetchPortfolioValue, fetchAllocation } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import type { Account } from '../types'

const COLOURS = ['#6366f1', '#22d3ee', '#f59e0b', '#10b981', '#f43f5e', '#a78bfa', '#fb923c']

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const fmtDate = (d: string) => d.slice(0, 7) // YYYY-MM

export default function Overview() {
  const [account, setAccount] = useState<Account | undefined>()

  const value = useApi(() => fetchPortfolioValue(undefined, undefined, account), [account])
  const allocation = useApi(() => fetchAllocation(undefined, account), [account])

  const latestValue = value.data?.at(-1)?.value_gbp

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Portfolio Overview</h1>
          {latestValue != null && (
            <p className="text-3xl font-semibold text-indigo-400 mt-1">{fmt.format(latestValue)}</p>
          )}
        </div>
        <AccountFilter value={account} onChange={setAccount} />
      </div>

      <Card title="Portfolio Value">
        {value.loading || value.error || !value.data?.length ? (
          <StatusMessage loading={value.loading} error={value.error} empty={!value.data?.length} />
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={value.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: '#6b7280', fontSize: 11 }} minTickGap={60} />
              <YAxis tickFormatter={(v) => fmt.format(v)} tick={{ fill: '#6b7280', fontSize: 11 }} width={80} />
              <Tooltip
                formatter={(v) => [fmt.format(Number(v)), 'Value']}
                labelFormatter={(l) => `Date: ${l}`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Line type="monotone" dataKey="value_gbp" stroke="#6366f1" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Card title="Current Allocation">
        {allocation.loading || allocation.error || !allocation.data?.length ? (
          <StatusMessage loading={allocation.loading} error={allocation.error} empty={!allocation.data?.length} />
        ) : (
          <div className="flex flex-col lg:flex-row gap-6 items-center">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={allocation.data}
                  dataKey="value_gbp"
                  nameKey="fund_name"
                  cx="50%"
                  cy="50%"
                  outerRadius={110}
                  label={(props) => `${((props.percent ?? 0) * 100).toFixed(1)}%`}
                  labelLine={false}
                >
                  {allocation.data.map((_, i) => (
                    <Cell key={i} fill={COLOURS[i % COLOURS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v, name) => [fmt.format(Number(v)), String(name)]}
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                />
                <Legend formatter={(v) => <span style={{ color: '#9ca3af', fontSize: 12 }}>{v}</span>} />
              </PieChart>
            </ResponsiveContainer>

            <div className="w-full lg:w-72 shrink-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase">
                    <th className="text-left pb-2">Fund</th>
                    <th className="text-right pb-2">Value</th>
                    <th className="text-right pb-2">%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {allocation.data.map((a, i) => (
                    <tr key={a.fund_id}>
                      <td className="py-2 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: COLOURS[i % COLOURS.length] }} />
                        <span className="text-gray-300 truncate max-w-[160px]" title={a.fund_name}>{a.fund_name}</span>
                      </td>
                      <td className="py-2 text-right text-gray-300">{fmt.format(a.value_gbp)}</td>
                      <td className="py-2 text-right text-gray-400">{a.percentage.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
