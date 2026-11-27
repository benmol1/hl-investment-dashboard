import { useApi } from '../hooks/useApi'
import { fetchPelmReconciliation } from '../api/transactions'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import PelmIncomeCard from '../components/PelmIncomeCard'

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

export default function PelmReconciliation() {
  const reconciliation = useApi(fetchPelmReconciliation, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">PELM Reconciliation</h1>
        <p className="text-sm text-gray-400 mt-2 max-w-3xl">
          Barratt &amp; Cooke&apos;s formal quarterly total-return reports for the PELM Will Trust, compared
          with the dashboard&apos;s own figures. A quarter appears only when Barratt &amp; Cooke sent a report,
          and months whose income ledgers are missing are not reconciled.
        </p>
      </div>

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

      <PelmIncomeCard />
    </div>
  )
}
