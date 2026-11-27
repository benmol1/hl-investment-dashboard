import {
  ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { useChartHeight } from '../hooks/useChartHeight'
import { fetchPelmIncome } from '../api/transactions'
import Card from './Card'
import StatusMessage from './StatusMessage'
import Cash from '../privacy/Cash'
import { usePrivacy, CASH_MASK } from '../privacy/context'

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const fmt2 = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', minimumFractionDigits: 2, maximumFractionDigits: 2 })
/** '2025-Q3' -> 'Q3 2025'; other period labels pass through unchanged. */
const fmtPeriod = (p: string) => p.replace(/^(\d{4})-(Q\d)$/, '$2 $1')
const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`

/** PELM Will Trust income received, income paid out and fees, by quarter. */
export default function PelmIncomeCard() {
  const { obscured } = usePrivacy()
  const fmtYAxis = (v: number) => (obscured ? CASH_MASK : fmt.format(v))
  const pieChartHeight = useChartHeight(200, 280)

  const income = useApi(() => fetchPelmIncome('quarter'), [])
  const incomeRows = (income.data?.periods ?? []).map((p) => ({
    ...p,
    label: fmtPeriod(p.period),
    fees_gbp: p.fx_commission_gbp + p.custody_fees_gbp,
  }))
  const anyFeesMissing = incomeRows.some((p) => !p.fees_complete)
  const anyIncomeMissing = incomeRows.some((p) => !p.income_complete)

  return (
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
  )
}
