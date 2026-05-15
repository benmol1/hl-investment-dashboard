import { useApi } from '../hooks/useApi'
import { fetchIngestLog } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'

const SOURCE_LABELS: Record<string, string> = {
  transactions: 'Transactions',
  prices: 'Prices',
}

const fmtDate = (iso: string | null) => {
  if (!iso) return <span className="text-gray-600">—</span>
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

const fmtTimestamp = (iso: string | null) => {
  if (!iso) return <span className="text-gray-600">—</span>
  const d = new Date(iso)
  const date = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  return `${date}, ${time}`
}

export default function IngestLog() {
  const { data, loading, error } = useApi(fetchIngestLog, [])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Data Ingestion Log</h1>

      <Card>
        {loading || error ? (
          <StatusMessage loading={loading} error={error} />
        ) : !data?.length ? (
          <StatusMessage empty />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                  <th className="text-left pb-3">Source</th>
                  <th className="text-left pb-3">Latest data date</th>
                  <th className="text-left pb-3">Last successful run</th>
                  <th className="text-left pb-3">Last run with rows imported</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {data.map((entry) => (
                  <tr key={entry.source} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-3 text-gray-200 font-medium">
                      {SOURCE_LABELS[entry.source] ?? entry.source}
                    </td>
                    <td className="py-3 text-gray-400 tabular-nums">
                      {fmtDate(entry.latest_data_date)}
                    </td>
                    <td className="py-3 text-gray-400 tabular-nums">
                      {fmtTimestamp(entry.last_successful_at)}
                    </td>
                    <td className="py-3 text-gray-400 tabular-nums">
                      {fmtTimestamp(entry.last_rows_imported_at)}
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
