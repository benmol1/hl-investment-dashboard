import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { fetchPortfolioPerformance } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import type { Account, PortfolioPerformanceResponse } from '../types'

type Key = 'portfolio' | 'FTSE100' | 'SP500' | 'NASDAQ'

const SERIES: { key: Key; label: string; colour: string; dash?: string }[] = [
  { key: 'portfolio', label: 'Portfolio', colour: '#6366f1' },
  { key: 'FTSE100', label: 'FTSE 100', colour: '#f59e0b', dash: '4 2' },
  { key: 'SP500', label: 'S&P 500', colour: '#10b981', dash: '4 2' },
  { key: 'NASDAQ', label: 'Nasdaq', colour: '#f43f5e', dash: '4 2' },
]

const fmtDate = (d: string) => d.slice(0, 7)

function mergeData(data: PortfolioPerformanceResponse) {
  const maps: Record<Key, Map<string, number>> = {
    portfolio: new Map(data.portfolio.map((p) => [p.date, p.indexed])),
    FTSE100: new Map(data.FTSE100.map((p) => [p.date, p.indexed])),
    SP500: new Map(data.SP500.map((p) => [p.date, p.indexed])),
    NASDAQ: new Map(data.NASDAQ.map((p) => [p.date, p.indexed])),
  }
  const dates = [...new Set([...maps.portfolio.keys(), ...maps.FTSE100.keys()])].sort()
  return dates.map((date) => ({
    date,
    portfolio: maps.portfolio.get(date),
    FTSE100: maps.FTSE100.get(date),
    SP500: maps.SP500.get(date),
    NASDAQ: maps.NASDAQ.get(date),
  }))
}

export default function Benchmarks() {
  const [account, setAccount] = useState<Account | undefined>()
  const { data, loading, error } = useApi(() => fetchPortfolioPerformance(undefined, undefined, account), [account])

  const merged = data ? mergeData(data) : []

  const getReturn = (key: Key) => {
    const series = data?.[key]
    if (!series?.length) return null
    return (series.at(-1)!.indexed - 100).toFixed(1)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Benchmark Comparison</h1>
        <AccountFilter value={account} onChange={setAccount} />
      </div>

      {data && (
        <div className="grid grid-cols-4 gap-4">
          {SERIES.map(({ key, label, colour }) => {
            const ret = getReturn(key)
            return (
              <div key={key} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full" style={{ background: colour }} />
                  <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
                </div>
                <p className={`text-xl font-semibold ${ret == null ? 'text-gray-600' : parseFloat(ret ?? '0') >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {ret == null ? '—' : `${ret}%`}
                </p>
              </div>
            )
          })}
        </div>
      )}

      <Card title={`Performance indexed to 100 at ${data?.start_date ?? '…'}`}>
        {loading || error || !merged.length ? (
          <StatusMessage loading={loading} error={error} empty={!merged.length} />
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={merged}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: '#6b7280', fontSize: 11 }} minTickGap={60} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
              <Tooltip
                formatter={(v, name) => {
                  const s = SERIES.find((x) => x.key === String(name))
                  return [`${Number(v).toFixed(2)}`, s?.label ?? String(name)]
                }}
                labelFormatter={(l) => `Date: ${l}`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Legend formatter={(v) => {
                const s = SERIES.find((x) => x.key === v)
                return <span style={{ color: '#9ca3af', fontSize: 12 }}>{s?.label ?? v}</span>
              }} />
              {SERIES.map(({ key, colour, dash }) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={colour}
                  dot={false}
                  strokeWidth={key === 'portfolio' ? 2 : 1.5}
                  strokeDasharray={dash}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  )
}
