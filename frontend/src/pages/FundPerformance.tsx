import { useParams, Link } from 'react-router-dom'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { fetchFundPerformance } from '../api/funds'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'

const fmtDate = (d: string) => d.slice(0, 7)

const BENCH_LINES = [
  { key: 'FTSE100', stroke: '#f59e0b', dash: '4 2' },
  { key: 'SP500',   stroke: '#22d3ee', dash: '4 2' },
  { key: 'NASDAQ',  stroke: '#f43f5e', dash: '4 2' },
] as const

export default function FundPerformance() {
  const { id } = useParams<{ id: string }>()

  const { data, loading, error } = useApi(
    () => fetchFundPerformance(id!),
    [id],
  )

  const merged = (() => {
    if (!data) return []
    const fundMap    = new Map(data.fund.map((p) => [p.date, p.indexed]))
    const ftse100Map = new Map(data.FTSE100.map((p) => [p.date, p.indexed]))
    const sp500Map   = new Map(data.SP500.map((p) => [p.date, p.indexed]))
    const nasdaqMap  = new Map(data.NASDAQ.map((p) => [p.date, p.indexed]))
    const dates = [...new Set([
      ...fundMap.keys(), ...ftse100Map.keys(), ...sp500Map.keys(), ...nasdaqMap.keys(),
    ])].sort()
    return dates.map((date) => ({
      date,
      fund:    fundMap.get(date),
      FTSE100: ftse100Map.get(date),
      SP500:   sp500Map.get(date),
      NASDAQ:  nasdaqMap.get(date),
    }))
  })()

  const latest = data?.fund.at(-1)
  const gainPct = latest ? (latest.indexed - 100).toFixed(1) : null

  const labelMap: Record<string, string> = { fund: data?.fund_name ?? 'Fund', FTSE100: 'FTSE 100', SP500: 'S&P 500', NASDAQ: 'Nasdaq' }

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
                formatter={(v, name) => [`${Number(v).toFixed(2)}`, labelMap[String(name)] ?? String(name)]}
                labelFormatter={(l) => `Date: ${l}`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Legend formatter={(v) => <span style={{ color: '#9ca3af', fontSize: 12 }}>{labelMap[v] ?? v}</span>} />
              <Line type="linear" dataKey="fund" stroke="#6366f1" dot={false} strokeWidth={2} />
              {BENCH_LINES.map(({ key, stroke, dash }) => (
                <Line key={key} type="linear" dataKey={key} stroke={stroke} dot={false} strokeWidth={1.5} strokeDasharray={dash} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  )
}
