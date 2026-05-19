import { useState } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { fetchFinancialYearContributions } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import type { Account } from '../types'

const fmt = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })

const COLOURS: Record<string, string> = {
  ISA: '#22d3ee',
  SIPP: '#818cf8',
  All: '#6366f1',
}

export default function FinancialYearContributions() {
  const [account, setAccount] = useState<Account | undefined>()

  const { data, loading, error } = useApi(fetchFinancialYearContributions, [])

  const barKey = account === 'ISA' ? 'isa_gbp' : account === 'SIPP' ? 'sipp_gbp' : 'total_gbp'
  const barColour = COLOURS[account ?? 'All']

  const totalIsa = data?.reduce((s, r) => s + r.isa_gbp, 0) ?? 0
  const totalSipp = data?.reduce((s, r) => s + r.sipp_gbp, 0) ?? 0
  const totalAll = data?.reduce((s, r) => s + r.total_gbp, 0) ?? 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Tax Year Contributions</h1>
        <AccountFilter value={account} onChange={setAccount} />
      </div>

      {data && data.length > 0 && (
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
        {loading || error || !data?.length ? (
          <StatusMessage loading={loading} error={error} empty={!data?.length} />
        ) : (
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={data} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="financial_year" tick={{ fill: '#6b7280', fontSize: 11 }} />
              <YAxis tickFormatter={(v) => fmt.format(v)} tick={{ fill: '#6b7280', fontSize: 11 }} width={80} />
              <Tooltip
                formatter={(v) => [fmt.format(Number(v)), account ?? 'Combined']}
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#d1d5db' }}
                cursor={{ fill: '#1f2937' }}
              />
              <Bar dataKey={barKey} radius={[3, 3, 0, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={barColour} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {data && data.length > 0 && (
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
                {[...data].reverse().map((row) => (
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
