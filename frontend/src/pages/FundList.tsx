import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { fetchFunds } from '../api/funds'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'

export default function FundList() {
  const [activeOnly, setActiveOnly] = useState(true)
  const { data, loading, error } = useApi(() => fetchFunds(activeOnly), [activeOnly])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-white">Fund Performance</h1>
        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => setActiveOnly(e.target.checked)}
            className="accent-indigo-500"
          />
          Active funds only
        </label>
      </div>

      <Card>
        {loading || error || !data?.length ? (
          <StatusMessage loading={loading} error={error} empty={!data?.length} />
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                <th className="text-left pb-3">Fund Name</th>
                <th className="text-left pb-3 hidden sm:table-cell">ISIN</th>
                <th className="text-left pb-3">Status</th>
                <th className="text-right pb-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {data.map((f) => (
                <tr key={f.id} className="hover:bg-gray-800/40 transition-colors">
                  <td className="py-3 text-gray-200 font-medium">{f.name}</td>
                  <td className="py-3 text-gray-500 font-mono text-xs hidden sm:table-cell">{f.isin ?? '—'}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${f.is_active ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-800 text-gray-500'}`}>
                      {f.is_active ? 'Active' : 'Closed'}
                    </span>
                  </td>
                  <td className="py-3 text-right">
                    <Link
                      to={`/funds/${f.id}`}
                      className="text-indigo-400 hover:text-indigo-300 text-xs font-medium"
                    >
                      View chart →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </Card>
    </div>
  )
}
