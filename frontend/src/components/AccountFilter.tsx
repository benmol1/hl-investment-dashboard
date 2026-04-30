import type { Account } from '../types'

interface Props {
  value: Account | undefined
  onChange: (v: Account | undefined) => void
}

export default function AccountFilter({ value, onChange }: Props) {
  return (
    <div className="flex gap-2 text-sm">
      {(['All', 'ISA', 'SIPP'] as const).map((opt) => {
        const acct = opt === 'All' ? undefined : (opt as Account)
        return (
          <button
            key={opt}
            onClick={() => onChange(acct)}
            className={`px-3 py-1 rounded-full border transition-colors ${
              value === acct
                ? 'bg-indigo-600 border-indigo-600 text-white'
                : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
            }`}
          >
            {opt}
          </button>
        )
      })}
    </div>
  )
}
