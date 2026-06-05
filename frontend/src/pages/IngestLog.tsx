import { useApi } from '../hooks/useApi'
import { fetchIngestLog } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import DateDisplay from '../components/DateDisplay'

const SOURCE_LABELS: Record<string, string> = {
  transactions: 'Transactions',
  prices: 'Prices',
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
                  <th className="text-left pb-3">
                    <span className="sm:hidden">Latest date</span>
                    <span className="hidden sm:inline">Latest data date</span>
                  </th>
                  <th className="text-left pb-3">
                    <span className="sm:hidden">Last run</span>
                    <span className="hidden sm:inline">Last successful run</span>
                  </th>
                  <th className="text-left pb-3 hidden sm:table-cell">Last run with rows imported</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {data.map((entry) => (
                  <tr key={entry.source} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-3 text-gray-200 font-medium">
                      {SOURCE_LABELS[entry.source] ?? entry.source}
                    </td>
                    <td className="py-3 text-gray-400 tabular-nums whitespace-nowrap">
                      <DateDisplay iso={entry.latest_data_date} />
                    </td>
                    <td className="py-3 text-gray-400 tabular-nums whitespace-nowrap">
                      <DateDisplay iso={entry.last_successful_at} includeTime />
                    </td>
                    <td className="py-3 text-gray-400 tabular-nums whitespace-nowrap hidden sm:table-cell">
                      <DateDisplay iso={entry.last_rows_imported_at} includeTime />
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
