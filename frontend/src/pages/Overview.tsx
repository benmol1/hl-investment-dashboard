import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, BarChart, Bar, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { useChartHeight } from '../hooks/useChartHeight'
import { fetchPortfolioValue, fetchAllocation } from '../api/portfolio'
import { fetchPelmComposition, fetchPelmIncome, fetchPelmReconciliation } from '../api/transactions'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import { fmtQuarterTick, quarterTicks, quarterReferenceLines } from '../chartDates'
import Cash from '../privacy/Cash'
import { usePrivacy, CASH_MASK } from '../privacy/context'
import DateRangeFilter, { dateRangeToFrom } from '../components/DateRangeFilter'
import type { DateRange } from '../components/DateRangeFilter'
import type { Account } from '../types'

const COLOURS = ['#6366f1', '#22d3ee', '#f59e0b', '#10b981', '#f43f5e', '#a78bfa', '#fb923c']

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const fmt2 = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtDate = (d: string) => d.slice(0, 7) // YYYY-MM
/** '2025-Q3' -> 'Q3 2025'; other period labels pass through unchanged. */
const fmtPeriod = (p: string) => p.replace(/^(\d{4})-(Q\d)$/, '$2 $1')
const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`
const fmtPp = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}`
const quarterLabel = (start: string, end: string) => {
  const sm = parseInt(start.slice(5, 7))
  const em = parseInt(end.slice(5, 7))
  const sameQuarter = start.slice(0, 4) === end.slice(0, 4) && (sm - 1) % 3 === 0 && em === sm + 2
  return sameQuarter ? `Q${(sm + 2) / 3} ${start.slice(0, 4)}` : `${start} – ${end}`
}

const COVERAGE_BADGE: Record<string, string> = {
  Complete: 'bg-emerald-900/50 text-emerald-400',
  Incomplete: 'bg-yellow-900/50 text-yellow-400',
  'Missing months': 'bg-red-900/50 text-red-400',
}

export default function Overview() {
  const { obscured } = usePrivacy()
  const [account, setAccount] = useState<Account | undefined>()
  const [dateRange, setDateRange] = useState<DateRange>('All')

  const fmtYAxis = (v: number) => (obscured ? CASH_MASK : fmt.format(v))
  const fmtCashTooltip = (v: number) => (obscured ? CASH_MASK : fmt.format(v))

  const from = dateRangeToFrom(dateRange)
  const isMonthly = account === 'PELM' // valuation-only account: month-end points, no holdings
  const value = useApi(() => fetchPortfolioValue(from, undefined, account), [from, account])
  const allocation = useApi(
    () => (isMonthly ? Promise.resolve([]) : fetchAllocation(undefined, account)),
    [account],
  )

  const composition = useApi(
    () => (isMonthly ? fetchPelmComposition() : Promise.resolve([])),
    [account],
  )
  const income = useApi(
    () => (isMonthly ? fetchPelmIncome('quarter') : Promise.resolve(null)),
    [account],
  )
  const reconciliation = useApi(
    () => (isMonthly ? fetchPelmReconciliation() : Promise.resolve([])),
    [account],
  )
  const incomeRows = (income.data?.periods ?? []).map((p) => ({
    ...p,
    label: fmtPeriod(p.period),
    fees_gbp: p.fx_commission_gbp + p.custody_fees_gbp,
  }))
  const anyFeesMissing = incomeRows.some((p) => !p.fees_complete)
  const anyIncomeMissing = incomeRows.some((p) => !p.income_complete)

  const valueDates = (value.data ?? []).map((p) => p.date)
  const compositionDates = (composition.data ?? []).map((p) => p.date)

  const latestPoint = value.data?.at(-1)
  const latestValue = latestPoint?.value_gbp
  const lineChartHeight = useChartHeight(220, 320)
  const pieChartHeight = useChartHeight(200, 280)
  const pieRadius = Math.min(pieChartHeight / 2 - 20, 110)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Portfolio Overview</h1>
          {latestValue != null && (
            <p className="text-3xl font-semibold text-indigo-400 mt-1"><Cash>{fmt.format(latestValue)}</Cash></p>
          )}
          {isMonthly && latestPoint && (
            <p className="text-xs text-gray-500 mt-1">Will Trust · month-end valuation as at {latestPoint.date}</p>
          )}
        </div>
        <div className="flex flex-col items-start sm:items-end gap-2">
          <AccountFilter value={account} onChange={setAccount} includePelm />
          <DateRangeFilter value={dateRange} onChange={setDateRange} />
        </div>
      </div>

      <Card title="Portfolio Value">
        {value.loading || value.error || !value.data?.length ? (
          <StatusMessage loading={value.loading} error={value.error} empty={!value.data?.length} />
        ) : (
          <ResponsiveContainer width="100%" height={lineChartHeight}>
            <LineChart data={value.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={!isMonthly} />
              <XAxis
                dataKey="date"
                ticks={isMonthly ? quarterTicks(valueDates) : undefined}
                tickFormatter={isMonthly ? fmtQuarterTick : fmtDate}
                tick={{ fill: '#6b7280', fontSize: 11 }}
                minTickGap={isMonthly ? 0 : 60}
              />
              <YAxis tickFormatter={fmtYAxis} tick={{ fill: '#6b7280', fontSize: 11 }} width={80} />
              {isMonthly && quarterReferenceLines(valueDates)}
              <Tooltip
                formatter={(v) => [fmtCashTooltip(Number(v)), 'Value']}
                labelFormatter={(l) => `Date: ${l}`}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Line type="linear" dataKey="value_gbp" stroke="#6366f1" dot={isMonthly} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      {isMonthly ? (
        <Card title="Investments vs Cash">
          {composition.loading || composition.error || !composition.data?.length ? (
            <StatusMessage loading={composition.loading} error={composition.error} empty={!composition.data?.length} />
          ) : (
            <ResponsiveContainer width="100%" height={lineChartHeight}>
              <BarChart data={composition.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="date"
                  ticks={quarterTicks(compositionDates)}
                  tickFormatter={fmtQuarterTick}
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  interval={0}
                />
                <YAxis tickFormatter={fmtYAxis} tick={{ fill: '#6b7280', fontSize: 11 }} width={80} />
                <Tooltip
                  formatter={(v) => fmtCashTooltip(Number(v))}
                  labelFormatter={(l) => `Month-end: ${l}`}
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                  labelStyle={{ color: '#d1d5db' }}
                />
                <Legend />
                <Bar dataKey="invested_gbp" name="Investments" stackId="a" fill="#6366f1" />
                <Bar dataKey="cash_gbp" name="Cash" stackId="a" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          )}
          <p className="text-xs text-gray-500 mt-3">
            Estimate: cash is built up from the Barratt &amp; Cooke ledgers (including the deposit account).
            Dividends, interest and fees are included only where those ledgers were supplied (currently
            Jul 2025 – Mar 2026). Real cash may differ from the official statements, typically by a small
            amount, with investments making up the difference.
          </p>
        </Card>
      ) : (
      <Card title="Current Allocation">
        {allocation.loading || allocation.error || !allocation.data?.length ? (
          <StatusMessage loading={allocation.loading} error={allocation.error} empty={!allocation.data?.length} />
        ) : (
          <div className="flex flex-col lg:flex-row gap-6 items-center">
            <ResponsiveContainer width="100%" height={pieChartHeight}>
              <PieChart>
                <Pie
                  data={allocation.data}
                  dataKey="value_gbp"
                  nameKey="fund_short_name"
                  cx="50%"
                  cy="50%"
                  outerRadius={pieRadius}
                  label={(props) => `${((props.percent ?? 0) * 100).toFixed(1)}%`}
                  labelLine={false}
                >
                  {allocation.data.map((_, i) => (
                    <Cell key={i} fill={COLOURS[i % COLOURS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v, _name, props) => [fmtCashTooltip(Number(v)), props.payload.fund_name]}
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                />
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
                        <span className="text-gray-300 truncate max-w-[160px]" title={a.fund_name}>{a.fund_short_name}</span>
                      </td>
                      <td className="py-2 text-right text-gray-300"><Cash>{fmt.format(a.value_gbp)}</Cash></td>
                      <td className="py-2 text-right text-gray-400">{a.percentage.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>
      )}

      {isMonthly && (
        <Card title="Income & Fees">
          {income.loading || income.error || !incomeRows.length ? (
            <StatusMessage loading={income.loading} error={income.error} empty={!incomeRows.length} />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={pieChartHeight}>
                <BarChart data={incomeRows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 11 }} interval={0} />
                  <YAxis tickFormatter={fmtYAxis} tick={{ fill: '#6b7280', fontSize: 11 }} width={80} />
                  <Tooltip
                    formatter={(v) => (obscured ? CASH_MASK : fmt2.format(Number(v)))}
                    contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                    labelStyle={{ color: '#d1d5db' }}
                    cursor={{ fill: '#1f2937' }}
                  />
                  <Legend />
                  <Bar dataKey="income_gbp" name="Income received" fill="#10b981" />
                  <Bar dataKey="income_distributed_gbp" name="Paid out" fill="#f59e0b" />
                  <Bar dataKey="fees_gbp" name="Fees" fill="#6b7280" />
                </BarChart>
              </ResponsiveContainer>

              <div className="overflow-x-auto mt-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                      <th className="text-left pb-2">Quarter</th>
                      <th className="text-right pb-2">Dividends</th>
                      <th className="text-right pb-2 hidden sm:table-cell">Interest</th>
                      <th className="text-right pb-2">Paid out</th>
                      <th className="text-right pb-2 hidden sm:table-cell">FX comm.</th>
                      <th className="text-right pb-2">Custody</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800">
                    {incomeRows.map((p) => {
                      const incomeMark = p.income_complete ? '' : '*'
                      const feeMark = p.fees_complete ? '' : '†'
                      return (
                        <tr key={p.period}>
                          <td className="py-2 text-gray-400 whitespace-nowrap">{p.label}</td>
                          <td className="py-2 text-right text-gray-300 tabular-nums">
                            <Cash>{fmt2.format(p.dividends_gbp)}</Cash>{incomeMark && <span className="text-yellow-500">{incomeMark}</span>}
                          </td>
                          <td className="py-2 text-right text-gray-300 tabular-nums hidden sm:table-cell">
                            <Cash>{fmt2.format(p.interest_gbp)}</Cash>{incomeMark && <span className="text-yellow-500">{incomeMark}</span>}
                          </td>
                          <td className="py-2 text-right text-gray-300 tabular-nums">
                            <Cash>{fmt2.format(p.income_distributed_gbp)}</Cash>{incomeMark && <span className="text-yellow-500">{incomeMark}</span>}
                          </td>
                          <td className="py-2 text-right text-gray-400 tabular-nums hidden sm:table-cell">
                            <Cash>{fmt2.format(p.fx_commission_gbp)}</Cash>
                          </td>
                          <td className="py-2 text-right text-gray-400 tabular-nums">
                            <Cash>{fmt2.format(p.custody_fees_gbp)}</Cash>{feeMark && <span className="text-yellow-500">{feeMark}</span>}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className="text-xs text-gray-500 mt-3 space-y-1">
                {anyIncomeMissing && <p>* Income ledgers only partly supplied for this quarter, so the figures are incomplete.</p>}
                {anyFeesMissing && (
                  <p>† No fees ledger supplied for this quarter. Barratt &amp; Cooke seem to send one only when fees are charged, so 0 probably means none, but it is not confirmed.</p>
                )}
                {income.data?.trailing_12m_income_gbp != null ? (
                  <p className="text-gray-400">
                    Trailing 12 months: <Cash>{fmt2.format(income.data.trailing_12m_income_gbp)}</Cash> income
                    {income.data.trailing_12m_income_yield != null && ` · ${fmtPct(income.data.trailing_12m_income_yield)} yield`}
                  </p>
                ) : (
                  <p>Trailing 12-month income and yield need 12 months of complete ledgers.</p>
                )}
              </div>
            </>
          )}
        </Card>
      )}

      {isMonthly && (
        <Card title="Return vs Barratt & Cooke">
          {reconciliation.loading || reconciliation.error || !reconciliation.data?.length ? (
            <StatusMessage loading={reconciliation.loading} error={reconciliation.error} empty={!reconciliation.data?.length} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                    <th className="text-left pb-2">Period</th>
                    <th className="text-right pb-2">B&amp;C</th>
                    <th className="text-right pb-2">Dashboard</th>
                    <th className="text-right pb-2">Diff (pp)</th>
                    <th className="text-right pb-2 pl-2">Coverage</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {reconciliation.data.map((r) => (
                    <tr key={`${r.period_start}-${r.period_end}`}>
                      <td className="py-2 text-gray-400 whitespace-nowrap" title={r.source}>{quarterLabel(r.period_start, r.period_end)}</td>
                      <td className="py-2 text-right text-gray-300 tabular-nums">{fmtPct(r.reported_return)}</td>
                      <td className="py-2 text-right text-gray-300 tabular-nums">
                        {r.dashboard_return != null ? fmtPct(r.dashboard_return) : <span className="text-gray-600">—</span>}
                      </td>
                      <td className="py-2 text-right text-gray-400 tabular-nums">
                        {r.difference_pp != null ? fmtPp(r.difference_pp) : <span className="text-gray-600">—</span>}
                      </td>
                      <td className="py-2 text-right pl-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${COVERAGE_BADGE[r.coverage] ?? 'bg-gray-800 text-gray-400'}`}>
                          {r.coverage}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-gray-500 mt-3">
            Barratt &amp; Cooke link daily returns; the dashboard links monthly ones, so differences of a
            few hundredths of a point are expected.
          </p>
        </Card>
      )}
    </div>
  )
}
