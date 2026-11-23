import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend, ReferenceLine,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { useChartHeight } from '../hooks/useChartHeight'
import { fetchPortfolioPerformance } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import MultiToggle from '../components/MultiToggle'
import { fmtQuarterTick, quarterTicks, quarterReferenceLines } from '../chartDates'
import type { Account, Benchmark, PerformancePoint, PortfolioPerformanceResponse, SharpeRatios } from '../types'

// 'ALL' is the combined ISA + SIPP view (the API's no-account default). PELM is only ever
// shown when selected explicitly.
type AccountKey = 'ALL' | Account

interface SeriesDef {
  key: string
  label: string
  colour: string
  dash?: string
}

const ACCOUNT_ORDER: AccountKey[] = ['ALL', 'ISA', 'SIPP', 'PELM']
const ACCOUNT_DEFS: Record<AccountKey, SeriesDef> = {
  ALL: { key: 'ALL', label: 'ISA + SIPP', colour: '#6366f1' },
  ISA: { key: 'ISA', label: 'ISA', colour: '#38bdf8' },
  SIPP: { key: 'SIPP', label: 'SIPP', colour: '#a78bfa' },
  PELM: { key: 'PELM', label: 'PELM Trust', colour: '#e879f9' },
}

const BENCH_ORDER: Benchmark[] = ['FTSE100', 'SP500', 'NASDAQ']
const BENCH_DEFS: Record<Benchmark, SeriesDef> = {
  FTSE100: { key: 'FTSE100', label: 'FTSE 100', colour: '#f59e0b', dash: '4 2' },
  SP500: { key: 'SP500', label: 'S&P 500', colour: '#10b981', dash: '4 2' },
  NASDAQ: { key: 'NASDAQ', label: 'Nasdaq 100', colour: '#f43f5e', dash: '4 2' },
}

const month = (d: string) => d.slice(0, 7)

interface MergedRow {
  date: string
  [seriesKey: string]: number | string | undefined
}

/**
 * Fetch performance for each selected account (benchmarks are indexed per response).
 *
 * useApi only clears its data after the render in which the inputs change, so for one render the
 * previous response is paired with the new account list. Each response is therefore tagged with
 * the accounts it was fetched for and treated as still loading unless they match.
 */
function usePerformance(accounts: AccountKey[], from: string | undefined) {
  const wanted = accounts.join(',')
  const state = useApi(
    async () => ({
      for: wanted,
      responses: await Promise.all(
        accounts.map((k) => fetchPortfolioPerformance(from, undefined, k === 'ALL' ? undefined : k)),
      ),
    }),
    [from, wanted],
  )
  const fresh = state.data?.for === wanted
  return {
    data: fresh ? state.data!.responses : null,
    loading: state.loading || (!!state.data && !fresh),
    error: state.error,
  }
}

/**
 * Pick the response with the longest benchmark history: the one running furthest forward (a
 * monthly-grain account like PELM stops at its last valuation), then the one starting earliest.
 */
function benchmarkSource(perf: PortfolioPerformanceResponse[]) {
  const last = (r: PortfolioPerformanceResponse) => r.FTSE100.at(-1)?.date ?? ''
  const first = (r: PortfolioPerformanceResponse) => r.FTSE100[0]?.date ?? '9999'
  return perf.reduce((a, b) => {
    if (last(b) !== last(a)) return last(b) > last(a) ? b : a
    return first(b) < first(a) ? b : a
  })
}

/**
 * Rebase every series to 100 at a common start month (the latest start among the accounts), so
 * accounts that began at different times are compared like-for-like.
 */
function rebase(series: Record<string, PerformancePoint[]>, accountKeys: string[]) {
  const starts = accountKeys.map((k) => series[k]?.[0]?.date).filter((d): d is string => !!d)
  if (!starts.length) return { series, startDate: undefined }
  const startMonth = month(starts.map(month).sort().at(-1)!)
  const out: Record<string, PerformancePoint[]> = {}
  for (const [key, pts] of Object.entries(series)) {
    const from = pts.findIndex((p) => month(p.date) >= startMonth)
    if (from < 0) { out[key] = []; continue }
    const base = pts[from].indexed
    out[key] = pts.slice(from).map((p) => ({ date: p.date, indexed: (p.indexed / base) * 100 }))
  }
  const startDate = accountKeys.map((k) => out[k]?.[0]?.date).find((d) => d && month(d) === startMonth)
  return { series: out, startDate }
}

/** One row per calendar month: PELM valuation dates can differ by a day from index month-ends. */
function mergeData(series: Record<string, PerformancePoint[]>, benchKeys: string[]): MergedRow[] {
  const labelDate = new Map<string, string>()
  // Prefer benchmark dates as the label so all months line up with the index calendar.
  for (const key of [...Object.keys(series).filter((k) => !benchKeys.includes(k)), ...benchKeys]) {
    for (const p of series[key] ?? []) labelDate.set(month(p.date), p.date)
  }
  const rows = new Map<string, MergedRow>()
  for (const [key, pts] of Object.entries(series)) {
    for (const p of pts) {
      const m = month(p.date)
      if (!rows.has(m)) rows.set(m, { date: labelDate.get(m)! })
      rows.get(m)![key] = p.indexed
    }
  }
  return [...rows.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, r]) => r)
}

export default function Benchmarks() {
  const currentYear = new Date().getFullYear()
  const yearEndPresets = [currentYear - 3, currentYear - 2, currentYear - 1].map((y) => ({
    label: `Dec '${String(y).slice(2)}`,
    value: `${y}-12-31`,
  }))

  const [selectedAccounts, setSelectedAccounts] = useState<string[]>(['ALL'])
  const [selectedBenchmarks, setSelectedBenchmarks] = useState<string[]>([...BENCH_ORDER])
  const [startDate, setStartDate] = useState(`${currentYear - 3}-12-31`)

  const accounts = ACCOUNT_ORDER.filter((k) => selectedAccounts.includes(k))
  const benchmarks = BENCH_ORDER.filter((k) => selectedBenchmarks.includes(k))
  const series: SeriesDef[] = [...accounts.map((k) => ACCOUNT_DEFS[k]), ...benchmarks.map((k) => BENCH_DEFS[k])]
  const accountKeys: string[] = accounts

  const { data: perf, loading, error } = usePerformance(accounts, startDate)
  const { data: allPerf } = usePerformance(accounts, undefined)

  const rawSeries = (responses: PortfolioPerformanceResponse[] | null) => {
    if (!responses?.length) return {}
    const bench = benchmarkSource(responses)
    const out: Record<string, PerformancePoint[]> = {}
    accounts.forEach((k, i) => { out[k] = responses[i].portfolio })
    benchmarks.forEach((b) => { out[b] = bench[b] })
    return out
  }

  const { series: chartSeries, startDate: commonStart } = rebase(rawSeries(perf), accountKeys)
  const merged = perf ? mergeData(chartSeries, benchmarks) : []
  const chartHeight = useChartHeight(240, 400)

  const dates = merged.map((d) => d.date)
  const xTicks = quarterTicks(dates)
  const fmtXTick = fmtQuarterTick

  const yTicks = (() => {
    if (!merged.length) return [50, 100, 150]
    const vals = merged.flatMap((d) => series.map(({ key }) => d[key]).filter((v): v is number => typeof v === 'number'))
    if (!vals.length) return [50, 100, 150]
    const min = Math.floor(Math.min(...vals) / 50) * 50
    const max = Math.ceil(Math.max(...vals) / 50) * 50
    const ticks: number[] = []
    for (let t = min; t <= max; t += 50) ticks.push(t)
    return ticks
  })()

  const getReturn = (key: string) => {
    const pts = chartSeries[key]
    if (!pts?.length) return null
    return (pts.at(-1)!.indexed - 100).toFixed(1)
  }

  const getAnnualisedReturn = (key: string) => {
    const pts = chartSeries[key]
    if (!pts?.length) return null
    const years = (new Date(pts.at(-1)!.date).getTime() - new Date(pts[0].date).getTime()) / (365.25 * 24 * 60 * 60 * 1000)
    if (years < 1) return null
    return ((Math.pow(pts.at(-1)!.indexed / 100, 1 / years) - 1) * 100).toFixed(1)
  }

  const annualReturns = (() => {
    if (!allPerf) return []
    const currentYear = new Date().getFullYear()
    const allSeries = rawSeries(allPerf)

    // Build map: year -> last indexed value in that year, per series
    const yearEndMap = (key: string): Map<number, number> => {
      const map = new Map<number, number>()
      for (const pt of allSeries[key] ?? []) {
        map.set(new Date(pt.date).getFullYear(), pt.indexed)
      }
      return map
    }
    const maps = Object.fromEntries(series.map(({ key }) => [key, yearEndMap(key)])) as Record<string, Map<number, number>>

    const allYears = [...new Set(series.flatMap(({ key }) => [...maps[key].keys()]))].sort().reverse()

    return allYears.flatMap(year => {
      const isYTD = year === currentYear
      const returns = Object.fromEntries(
        series.map(({ key }) => {
          const end = maps[key].get(year)
          const start = maps[key].get(year - 1)
          if (end == null || start == null) return [key, null]
          return [key, (end / start - 1) * 100]
        })
      ) as Record<string, number | null>
      // Skip rows where every series is null (no prior year-end reference)
      if (series.every(({ key }) => returns[key] == null)) return []
      return [{ year, isYTD, returns }]
    })
  })()

  // Benchmark Sharpe ratios come from a response that is not cut short by a monthly-grain account.
  const sharpeSource = perf?.length
    ? (perf.find((_, i) => accounts[i] !== 'PELM') ?? perf[0])
    : undefined
  const sharpeFor = (key: string): SharpeRatios | undefined => {
    if (!perf) return undefined
    const i = accounts.indexOf(key as AccountKey)
    return i >= 0 ? perf[i].sharpe.portfolio : sharpeSource?.sharpe[key]
  }
  const pelmLastDate = accounts.includes('PELM') && perf ? perf[accounts.indexOf('PELM')].portfolio.at(-1)?.date : undefined

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h1 className="text-2xl font-bold text-white">Benchmark Comparison</h1>
        <div className="flex flex-col items-start sm:items-end gap-2">
          <MultiToggle
            options={ACCOUNT_ORDER.map((k) => ({
              ...ACCOUNT_DEFS[k],
              title: k === 'PELM' ? 'Will Trust — not included in any totals unless selected' : undefined,
            }))}
            selected={selectedAccounts}
            onChange={setSelectedAccounts}
            requireOne
          />
          <MultiToggle
            options={BENCH_ORDER.map((k) => BENCH_DEFS[k])}
            selected={selectedBenchmarks}
            onChange={setSelectedBenchmarks}
          />
          <div className="flex items-center gap-2 text-sm flex-wrap sm:justify-end">
            <span className="text-gray-500">Start date:</span>
            {yearEndPresets.map(({ label, value }) => (
              <button
                key={value}
                onClick={() => setStartDate(value)}
                className={`px-2 py-1 rounded text-xs font-medium border transition-colors ${
                  startDate === value
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300'
                }`}
              >
                {label}
              </button>
            ))}
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-gray-900 border border-gray-700 text-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>
      </div>

      {perf && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {series.map(({ key, label, colour }) => {
            const ret = getReturn(key)
            const ann = getAnnualisedReturn(key)
            const retColour = (v: string | null) => v == null ? 'text-gray-600' : parseFloat(v) >= 0 ? 'text-emerald-400' : 'text-red-400'
            return (
              <div key={key} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-2 h-2 rounded-full" style={{ background: colour }} />
                  <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
                </div>
                <div className="flex gap-6">
                  <div>
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Total</p>
                    <p className={`text-xl font-semibold ${retColour(ret)}`}>
                      {ret == null ? '—' : `${ret}%`}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-0.5">Annual</p>
                    <p className={`text-xl font-semibold ${retColour(ann)}`}>
                      {ann == null ? '—' : `${ann}%`}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Card title={`Performance indexed to 100 at ${commonStart ? fmtXTick(commonStart) : '…'}`}>
        {loading || error || !merged.length ? (
          <StatusMessage loading={loading} error={error} empty={!merged.length} />
        ) : (
          <ResponsiveContainer width="100%" height={chartHeight}>
            <LineChart data={merged}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="date" ticks={xTicks} tickFormatter={fmtXTick} tick={{ fill: '#6b7280', fontSize: 11 }} />
              <YAxis ticks={yTicks} domain={[yTicks[0], yTicks[yTicks.length - 1]]} tick={{ fill: '#6b7280', fontSize: 11 }} />
              <Tooltip
                formatter={(v, name) => {
                  const s = series.find((x) => x.key === String(name))
                  return [`${Number(v).toFixed(2)}`, s?.label ?? String(name)]
                }}
                labelFormatter={(l) => `Date: ${l}`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Legend formatter={(v) => {
                const s = series.find((x) => x.key === v)
                return <span style={{ color: '#9ca3af', fontSize: 12 }}>{s?.label ?? v}</span>
              }} />
              <ReferenceLine y={100} stroke="#4b5563" strokeDasharray="4 2" />
              {quarterReferenceLines(dates)}
              {series.map(({ key, colour, dash }) => (
                <Line
                  key={key}
                  type="linear"
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

      {annualReturns.length > 0 && (
        <Card title="Annual Returns">
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase">
                <th className="text-left pb-3 w-20"></th>
                {series.map(({ key, label, colour }) => (
                  <th key={key} className="text-right pb-3">
                    <span className="flex items-center justify-end gap-1.5">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colour }} />
                      {label}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {annualReturns.map(({ year, isYTD, returns }) => (
                <tr key={year}>
                  <td className="py-3 text-gray-500 text-xs uppercase tracking-wider">
                    {year}{isYTD ? ' YTD' : ''}
                  </td>
                  {series.map(({ key }) => {
                    const v = returns[key]
                    return (
                      <td key={key} className="py-3 text-right font-semibold">
                        {v == null
                          ? <span className="text-gray-600">—</span>
                          : <span className={v >= 0 ? 'text-emerald-400' : 'text-red-400'}>{v.toFixed(1)}%</span>
                        }
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </Card>
      )}

      {perf && (
        <Card title="Sharpe Ratios (annualised, risk-free rate = 0)">
          <p className="text-xs text-gray-500 mb-4">Trailing windows ending today — fixed, not affected by the start date picker.{pelmLastDate && ` PELM Trust figures end at its last valuation (${pelmLastDate}).`}</p>
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase">
                <th className="text-left pb-3 w-28"></th>
                {series.map(({ key, label, colour }) => (
                  <th key={key} className="text-right pb-3">
                    <span className="flex items-center justify-end gap-1.5">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colour }} />
                      {label}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {(['trailing_12m', 'trailing_36m'] as const).map((field) => (
                <tr key={field}>
                  <td className="py-3 text-gray-500 text-xs uppercase tracking-wider">
                    {field === 'trailing_12m' ? '12-month' : '36-month'}
                  </td>
                  {series.map(({ key }) => {
                    const v = sharpeFor(key)?.[field]
                    return (
                      <td key={key} className="py-3 text-right font-semibold">
                        {v == null
                          ? <span className="text-gray-600">—</span>
                          : <span className={v >= 0 ? 'text-emerald-400' : 'text-red-400'}>{v.toFixed(2)}</span>
                        }
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </Card>
      )}
    </div>
  )
}
