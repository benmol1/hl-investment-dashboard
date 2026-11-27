import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend, ReferenceLine, ReferenceArea,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { useChartHeight } from '../hooks/useChartHeight'
import { fetchPortfolioPerformance, fetchQuarterlyReturns } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import MultiToggle from '../components/MultiToggle'
import { fmtQuarterTick, quarterTicks, quarterReferenceLines } from '../chartDates'
import type { Account, Benchmark, PerformancePoint, PortfolioPerformanceResponse, QuarterlyReturn, SharpeRatios } from '../types'

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

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const fmtMonth = (m: string) => `${MONTH_NAMES[parseInt(m.slice(5, 7)) - 1]} ${m.slice(0, 4)}`
const prevMonth = (m: string) => {
  const y = parseInt(m.slice(0, 4))
  const mo = parseInt(m.slice(5, 7))
  return mo === 1 ? `${y - 1}-12` : `${y}-${String(mo - 1).padStart(2, '0')}`
}

/** '2025-Q3' -> 'Q3 2025'. */
const fmtQuarter = (q: string) => q.replace(/^(\d{4})-(Q\d)$/, '$2 $1')
const fmtPct2 = (v: number) => `${(v * 100).toFixed(2)}%`

/** Group month-end dates into runs of consecutive months, as [firstMonth, lastMonth] (YYYY-MM). */
function monthRanges(dates: string[]): [string, string][] {
  const months = [...new Set(dates.map(month))].sort()
  const ranges: [string, string][] = []
  for (const m of months) {
    const last = ranges.at(-1)
    if (last && prevMonth(m) === last[1]) last[1] = m
    else ranges.push([m, m])
  }
  return ranges
}

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
 *
 * `pelmEstimate` requests the best-estimate return for PELM (it has no effect on ISA/SIPP).
 */
function usePerformance(accounts: AccountKey[], from: string | undefined, pelmEstimate: boolean) {
  return usePerAccount(accounts, from, pelmEstimate, fetchPortfolioPerformance)
}

/** Quarterly returns for each selected account, with the same staleness handling as usePerformance. */
function useQuarterlyReturns(accounts: AccountKey[], from: string | undefined, pelmEstimate: boolean) {
  return usePerAccount(accounts, from, pelmEstimate, fetchQuarterlyReturns)
}

function usePerAccount<T>(
  accounts: AccountKey[],
  from: string | undefined,
  pelmEstimate: boolean,
  fetcher: (from?: string, to?: string, account?: Account, estimate?: boolean) => Promise<T>,
) {
  const estimate = pelmEstimate && accounts.includes('PELM')
  const wanted = `${accounts.join(',')}|${estimate}`
  const state = useApi(
    async () => ({
      for: wanted,
      responses: await Promise.all(
        accounts.map((k) => fetcher(from, undefined, k === 'ALL' ? undefined : k, k === 'PELM' && estimate)),
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
  const [pelmEstimate, setPelmEstimate] = useState(false)

  const accounts = ACCOUNT_ORDER.filter((k) => selectedAccounts.includes(k))
  const benchmarks = BENCH_ORDER.filter((k) => selectedBenchmarks.includes(k))
  const series: SeriesDef[] = [...accounts.map((k) => ACCOUNT_DEFS[k]), ...benchmarks.map((k) => BENCH_DEFS[k])]
  const accountKeys: string[] = accounts

  const pelmSelected = accounts.includes('PELM')
  const estimateOn = pelmSelected && pelmEstimate
  const { data: perf, loading, error } = usePerformance(accounts, startDate, pelmEstimate)
  const { data: allPerf } = usePerformance(accounts, undefined, pelmEstimate)
  const quarterly = useQuarterlyReturns(accounts, startDate, pelmEstimate)

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
  // PELM months whose return is understated because the income paid out to the beneficiary is unknown.
  const pelmIncomplete = accounts.includes('PELM') && perf ? perf[accounts.indexOf('PELM')].incomplete_flow_dates ?? [] : []
  const pelmIncompleteRanges = monthRanges(pelmIncomplete)
  // Shade each range on the chart: a month's return runs from the previous month-end to its own.
  const rowDateByMonth = new Map(merged.map((r) => [month(r.date), r.date]))
  const pelmShading = pelmIncompleteRanges.flatMap(([a, b]) => {
    const x1 = rowDateByMonth.get(prevMonth(a)) ?? rowDateByMonth.get(a)
    const x2 = rowDateByMonth.get(b)
    return x1 && x2 && x1 !== x2 ? [{ x1, x2 }] : []
  })
  const pelmLastDate = accounts.includes('PELM') && perf ? perf[accounts.indexOf('PELM')].portfolio.at(-1)?.date : undefined

  // Quarterly returns: one row per quarter (newest first), one column per account then benchmark.
  const quarterRows = (() => {
    const responses = quarterly.data
    if (!responses?.length) return []
    const byAccount = responses.map((r) => new Map(r.quarters.map((q) => [q.quarter, q])))
    const quarters = [...new Set(responses.flatMap((r) => r.quarters.map((q) => q.quarter)))].sort().reverse()
    return quarters.map((quarter) => {
      const cells = accounts.map((_, i) => byAccount[i].get(quarter))
      // Benchmarks come from the first account's response, falling back to the next account
      // that has this quarter (e.g. when the first account started later).
      const bench = cells.find((c): c is QuarterlyReturn => !!c)
      const present = cells.filter((c): c is QuarterlyReturn => !!c)
      const monthsSet = new Set(present.map((c) => c.months))
      // If every account covers the same part-quarter, say so once on the row label.
      const rowMonths = monthsSet.size === 1 && present[0].months < 3 ? present[0].months : undefined
      return { quarter, cells, bench, rowMonths }
    })
  })()
  const anyCellPartial = quarterRows.some((r) => r.rowMonths == null && r.cells.some((c) => c && c.months < 3))
  const anyRowPartial = quarterRows.some((r) => r.rowMonths != null)
  const anyIncompleteQuarter = quarterRows.some((r) => r.cells.some((c) => c && !c.flows_complete))
  const retClass = (v: number) => (v >= 0 ? 'text-emerald-400' : 'text-red-400')
  const quarterlyTitle = estimateOn
    ? 'Best estimate: includes estimated income paid out'
    : 'Understated: income paid out data missing'

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
          {pelmSelected && (
            <div className="flex items-center gap-2 text-sm flex-wrap sm:justify-end">
              <span className="text-gray-500">PELM returns:</span>
              <div className="inline-flex rounded-md border border-gray-700 overflow-hidden" role="group" aria-label="PELM returns">
                {([false, true] as const).map((on) => (
                  <button
                    key={String(on)}
                    onClick={() => setPelmEstimate(on)}
                    aria-pressed={pelmEstimate === on}
                    className={`px-2 py-1 text-xs font-medium transition-colors ${on ? 'border-l border-gray-700' : ''} ${
                      pelmEstimate === on
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-900 text-gray-400 hover:text-gray-300'
                    }`}
                  >
                    {on ? 'Best estimate' : 'Actual data'}
                  </button>
                ))}
              </div>
            </div>
          )}
          {estimateOn && (
            <p className="text-xs text-gray-500 max-w-md sm:text-right">
              Best estimate: for months without income data, adds the average monthly uplift that income
              paid out adds in the months that have it (Jul 2025 – Mar 2026).
            </p>
          )}
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
              {pelmShading.map(({ x1, x2 }) => (
                <ReferenceArea key={x1} x1={x1} x2={x2} fill="#e879f9" fillOpacity={0.06} stroke="none" ifOverflow="hidden" />
              ))}
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
        {pelmIncompleteRanges.length > 0 && (
          <p className="text-xs text-gray-500 mt-3">
            PELM Trust: {pelmIncomplete.length} month{pelmIncomplete.length === 1 ? ' is' : 's are'} missing
            income payment data from Barratt &amp; Cooke
            ({pelmIncompleteRanges.map(([a, b]) => (a === b ? fmtMonth(a) : `${fmtMonth(a)} – ${fmtMonth(b)}`)).join(', ')}),
            so its return for those months is {estimateOn ? 'a best estimate' : 'understated'}
            {pelmShading.length > 0 && ' (shaded on the chart)'}.
          </p>
        )}
      </Card>

      <Card title="Quarterly total returns">
        {quarterly.loading || quarterly.error || !quarterRows.length ? (
          <StatusMessage loading={quarterly.loading} error={quarterly.error} empty={!quarterRows.length} />
        ) : (
          <>
            <div className="max-h-[28rem] overflow-auto -mx-1 px-1">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-gray-900">
                  <tr className="text-gray-500 text-xs uppercase">
                    <th className="text-left py-2 pr-2"></th>
                    {series.map(({ key, label, colour }) => (
                      <th key={key} className="text-right py-2 pl-3 whitespace-nowrap">
                        <span className="flex items-center justify-end gap-1.5">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colour }} />
                          {label}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {quarterRows.map(({ quarter, cells, bench, rowMonths }) => (
                    <tr key={quarter}>
                      <td className="py-2 pr-2 text-gray-500 text-xs uppercase tracking-wider whitespace-nowrap">
                        {fmtQuarter(quarter)}
                        {rowMonths != null && <span className="normal-case text-gray-600"> ({rowMonths} mo)</span>}
                      </td>
                      {accounts.map((k, i) => {
                        const c = cells[i]
                        return (
                          <td key={k} className="py-2 pl-3 text-right font-semibold tabular-nums whitespace-nowrap">
                            {c == null ? (
                              <span className="text-gray-600">—</span>
                            ) : (
                              <>
                                <span className={retClass(c.portfolio)}>{fmtPct2(c.portfolio)}</span>
                                {!c.flows_complete && (
                                  <sup className="text-yellow-500 ml-0.5" title={quarterlyTitle}>
                                    {estimateOn ? 'e' : '*'}
                                  </sup>
                                )}
                                {rowMonths == null && c.months < 3 && (
                                  <sup className="text-gray-500 font-normal ml-0.5" title={`Partial quarter: ${c.months} month${c.months === 1 ? '' : 's'}`}>
                                    {c.months}m
                                  </sup>
                                )}
                              </>
                            )}
                          </td>
                        )
                      })}
                      {benchmarks.map((b) => {
                        const v = bench?.[b]
                        return (
                          <td key={b} className="py-2 pl-3 text-right font-semibold tabular-nums whitespace-nowrap">
                            {v == null
                              ? <span className="text-gray-600">—</span>
                              : <span className={retClass(v)}>{fmtPct2(v)}</span>}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="text-xs text-gray-500 mt-3 space-y-1">
              <p>Benchmarks are measured over the same months as {accounts.length > 1 ? 'the first selected account' : 'the account'}.</p>
              {anyRowPartial && <p>(n mo): partial quarter, covering only n months (the first quarter, or the one in progress).</p>}
              {anyCellPartial && <p><sup>1m</sup>, <sup>2m</sup>: this account covers only 1 or 2 months of the quarter (its first quarter, or its latest valuation).</p>}
              {anyIncompleteQuarter && (estimateOn ? (
                <p><sup className="text-yellow-500">e</sup> PELM Trust: estimated, because income paid out data is missing for some months.</p>
              ) : (
                <p><sup className="text-yellow-500">*</sup> PELM Trust: understated, because income paid out data is missing for some months.</p>
              ))}
            </div>
          </>
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
