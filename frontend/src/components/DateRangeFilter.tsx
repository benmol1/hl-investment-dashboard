export type DateRange = '6M' | '1Y' | '3Y' | '5Y' | 'All'

interface Props {
  value: DateRange
  onChange: (v: DateRange) => void
}

const OPTIONS: DateRange[] = ['6M', '1Y', '3Y', '5Y', 'All']

export function dateRangeToFrom(range: DateRange): string | undefined {
  if (range === 'All') return undefined
  const d = new Date()
  if (range === '6M') d.setMonth(d.getMonth() - 6)
  else if (range === '1Y') d.setFullYear(d.getFullYear() - 1)
  else if (range === '3Y') d.setFullYear(d.getFullYear() - 3)
  else if (range === '5Y') d.setFullYear(d.getFullYear() - 5)
  return d.toISOString().slice(0, 10)
}

export default function DateRangeFilter({ value, onChange }: Props) {
  return (
    <div className="flex gap-2 text-sm">
      {OPTIONS.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={`px-3 py-1 rounded-full border transition-colors ${
            value === opt
              ? 'bg-indigo-600 border-indigo-600 text-white'
              : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
