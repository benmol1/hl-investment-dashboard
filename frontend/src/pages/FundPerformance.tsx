import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { fetchFundPerformance } from '../api/funds'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import type { Benchmark } from '../types'

const BENCHMARKS: Benchmark[] = ['FTSE100', 'SP500', 'NASDAQ']
const fmtDate = (d: string) => d.slice(0, 7)

export default function FundPerformance() {
  const { id } = useParams<{ id: string }>()
  const [benchmark, setBenchmark] = useState<Benchmark>('FTSE100')

  const { data, loading, error } = useApi(
    () => fetchFundPerformance(id!, undefined, undefined, benchmark),
    [id, benchmark],
  )

  // Merge fund + benchmark series onto a shared date axis
  const merged = (() => {
    if (!data) return []
    const fundMap = new Map(data.fund.map((p) => [p.date, p.indexed]))
    const benchMap = new Map(data.benchmark.map((p) => [p.date, p.indexed]))
    const dates = [...new Set([...fundMap.keys(), ...benchMap.keys()])].sort()
    return dates.map((date) => ({ date, fund: fundMap.get(date), bench: benchMap.get(date) }))
  })()

  const latest = data?.fund.at(-1)
  const gainPct = latest ? (latest.indexed - 100).toFixed(1) : null

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/funds" className="text-gray-500 hover:text-gray-300 text-sm">← Funds</Link>
        <h1 className="text-2xl font-bold text-white">{data?.fund_name ?? id}</h1>
      </div>

      {gainPct != null && (
        <p className="text-sm text-gray-400">
          Return since first purchase:{' '}
          <span className={parseFloat(gainPct) >= 0 ? 'text-emerald-400 font-semibold' : 'text-red-400 font-semibold'}>
            {gainPct}%
          </span>
        </p>
      )}

      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">Benchmark:</span>
        {BENCHMARKS.map((b) => (
          <button
            key={b}
            onClick={() => setBenchmark(b)}
            className={`px-3 py-1 rounded-full text-sm border transition-colors ${
              benchmark === b
                ? 'bg-indigo-600 border-indigo-600 text-white'
                : 'border-gray-700 text-gray-400 hover:border-gray-500'
            }`}
          >
            {b}
          </button>
        ))}
      </div>

      <Card title="Performance (indexed to 100 at first purchase)">
        {loading || error || !merged.length ? (
          <StatusMessage loading={loading} error={error} empty={!merged.length} />
        ) : (
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={merged}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: '#6b7280', fontSize: 11 }} minTickGap={60} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
              <Tooltip
                formatter={(v, name) => [`${Number(v).toFixed(2)}`, String(name) === 'fund' ? data!.fund_name : benchmark]}
                labelFormatter={(l) => `Date: ${l}`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Legend formatter={(v) => <span style={{ color: '#9ca3af', fontSize: 12 }}>{v === 'fund' ? (data?.fund_name ?? 'Fund') : benchmark}</span>} />
              <Line type="monotone" dataKey="fund" stroke="#6366f1" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="bench" stroke="#f59e0b" dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  )
}
