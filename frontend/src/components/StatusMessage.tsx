interface Props {
  loading?: boolean
  error?: string | null
  empty?: boolean
}

export default function StatusMessage({ loading, error, empty }: Props) {
  if (loading) return <p className="text-gray-500 text-sm py-8 text-center">Loading…</p>
  if (error) return <p className="text-red-400 text-sm py-8 text-center">Error: {error}</p>
  if (empty) return <p className="text-gray-500 text-sm py-8 text-center">No data available</p>
  return null
}
