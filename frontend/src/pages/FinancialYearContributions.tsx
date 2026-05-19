import { useState } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { fetchFinancialYearContributions } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })

const SELECT = 'bg-gray-900 border border-gray-700 text-gray-200 rounded px-2 py-1 text-sm'

export default function FinancialYearContributions() {
  const [fromYear, setFromYear] = useState('')
  const [toYear, setToYear] = useState('')

  const { data, loading, error } = useApi(fetchFinancialYearContributions, [])

  const years = data?.map(r => r.financial_year) ?? []

  const filteredData = data?.filter(r => {
    if (fromYear && r.financial_year < fromYear) return false
    if (toYear && r.financial_year > toYear) return false
    return true
  }) ?? []

  const totalIsa = filteredData.reduce((s, r) => s + r.isa_gbp, 0)
  const totalSipp = filteredData.reduce((s, r) => s + r.sipp_gbp, 0)
  const totalAll = filteredData.reduce((s, r) => s + r.total_gbp, 0)

  const yMax = filteredData.length
    ? Math.ceil(Math.max(...filteredData.map(r => r.total_gbp)) / 10000) * 10000
    : 10000
  const yTicks = Array.from({ length: yMax / 10000 + 1 }, (_, i) => i * 10000)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Tax Year Contributions</h1>
        {years.length > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-400">From</span>
            <select
              value={fromYear}
              onChange={e => {
                setFromYear(e.target.value)
                if (toYear && e.target.value > toYear) setToYear('')
              }}
              className={SELECT}
            >
              <option value="">All</option>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            <span className="text-gray-400">to</span>
            <select
              value={toYear}
              onChange={e => setToYear(e.target.value)}
              className={SELECT}
            >
              <option value="">All</option>
              {years.filter(y => !fromYear || y >= fromYear).map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        )}
      </div>

      {filteredData.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Total ISA Contributions', value: totalIsa, colour: 'text-cyan-400' },
            { label: 'Total SIPP Contributions', value: totalSipp, colour: 'text-indigo-400' },
            { label: 'Combined Total', value: totalAll, colour: 'text-white' },
          ].map(({ label, value, colour }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
              <p className={`text-2xl font-semibold ${colour}`}>{fmt.format(value)}</p>
            </div>
          ))}
        </div>
      )}

      <Card title="Annual Contributions by Tax Year">
        {loading || error || !filteredData.length ? (
          <StatusMessage loading={loading} error={error} empty={!data?.length} />
        ) : (
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={filteredData} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="financial_year" tick={{ fill: '#6b7280', fontSize: 11 }} />
              <YAxis ticks={yTicks} domain={[0, yMax]} tickFormatter={(v) => fmt.format(v)} tick={{ fill: '#6b7280', fontSize: 11 }} width={80} />
              <Tooltip
                formatter={(v, name) => [fmt.format(Number(v)), name === 'isa_gbp' ? 'ISA' : 'SIPP']}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
                cursor={{ fill: '#1f2937' }}
              />
              <Legend formatter={(v) => (
                <span style={{ color: '#9ca3af', fontSize: 12 }}>{v === 'isa_gbp' ? 'ISA' : 'SIPP'}</span>
              )} />
              <Bar dataKey="isa_gbp" stackId="a" fill="#22d3ee" />
              <Bar dataKey="sipp_gbp" stackId="a" fill="#818cf8" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {filteredData.length > 0 && (
        <Card title="Contributions by Tax Year">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase tracking-wider border-b border-gray-800">
                  <th className="text-left py-2 pr-4">Tax Year</th>
                  <th className="text-right py-2 pr-4">ISA</th>
                  <th className="text-right py-2 pr-4">SIPP</th>
                  <th className="text-right py-2">Combined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {[...filteredData].reverse().map((row) => (
                  <tr key={row.financial_year} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-2 pr-4 text-gray-300 font-medium">{row.financial_year}</td>
                    <td className="py-2 pr-4 text-right text-cyan-400">{fmt.format(row.isa_gbp)}</td>
                    <td className="py-2 pr-4 text-right text-indigo-400">{fmt.format(row.sipp_gbp)}</td>
                    <td className="py-2 text-right text-white">{fmt.format(row.total_gbp)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-gray-700">
                <tr className="text-sm font-semibold">
                  <td className="py-2 pr-4 text-gray-400">Total</td>
                  <td className="py-2 pr-4 text-right text-cyan-400">{fmt.format(totalIsa)}</td>
                  <td className="py-2 pr-4 text-right text-indigo-400">{fmt.format(totalSipp)}</td>
                  <td className="py-2 text-right text-white">{fmt.format(totalAll)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
