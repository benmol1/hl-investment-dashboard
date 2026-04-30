import { useState } from 'react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { fetchContributions } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import type { Account } from '../types'

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const fmtDate = (d: string) => d.slice(0, 7)

export default function Contributions() {
  const [account, setAccount] = useState<Account | undefined>()
  const { data, loading, error } = useApi(() => fetchContributions(undefined, undefined, account), [account])

  const latest = data?.at(-1)
  const totalGrowth = latest ? latest.portfolio_value - latest.cumulative_contributions : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Contributions vs Growth</h1>
        <AccountFilter value={account} onChange={setAccount} />
      </div>

      {latest && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Portfolio Value', value: latest.portfolio_value, colour: 'text-indigo-400' },
            { label: 'Total Contributed', value: latest.cumulative_contributions, colour: 'text-cyan-400' },
            { label: 'Investment Growth', value: totalGrowth!, colour: totalGrowth! >= 0 ? 'text-emerald-400' : 'text-red-400' },
          ].map(({ label, value, colour }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
              <p className={`text-2xl font-semibold ${colour}`}>{fmt.format(value)}</p>
            </div>
          ))}
        </div>
      )}

      <Card title="Portfolio Value vs Cumulative Contributions">
        {loading || error || !data?.length ? (
          <StatusMessage loading={loading} error={error} empty={!data?.length} />
        ) : (
          <ResponsiveContainer width="100%" height={380}>
            <AreaChart data={data}>
              <defs>
                <linearGradient id="contrib" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="portfolio" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: '#6b7280', fontSize: 11 }} minTickGap={60} />
              <YAxis tickFormatter={(v) => fmt.format(v)} tick={{ fill: '#6b7280', fontSize: 11 }} width={80} />
              <Tooltip
                formatter={(v, name) => [fmt.format(Number(v)), String(name) === 'portfolio_value' ? 'Portfolio Value' : String(name) === 'cumulative_contributions' ? 'Contributions' : 'Growth']}
                labelFormatter={(l) => `Date: ${l}`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Legend formatter={(v) => {
                const map: Record<string, string> = { portfolio_value: 'Portfolio Value', cumulative_contributions: 'Contributions', growth: 'Growth' }
                return <span style={{ color: '#9ca3af', fontSize: 12 }}>{map[v] ?? v}</span>
              }} />
              <Area type="monotone" dataKey="cumulative_contributions" stroke="#22d3ee" fill="url(#contrib)" strokeWidth={2} />
              <Area type="monotone" dataKey="portfolio_value" stroke="#6366f1" fill="url(#portfolio)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  )
}
