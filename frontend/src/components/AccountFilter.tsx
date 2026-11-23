import type { Account } from '../types'

interface Props {
  value: Account | undefined
  onChange: (v: Account | undefined) => void
  /**
   * Offer the PELM Will Trust as an explicit choice. Off by default: it is not the user's own
   * money, so it only appears on pages where comparing it makes sense, and is never part of
   * the default (ISA + SIPP) view.
   */
  includePelm?: boolean
}

export default function AccountFilter({ value, onChange, includePelm = false }: Props) {
  const options: { label: string; acct: Account | undefined; title?: string }[] = [
    { label: includePelm ? 'ISA + SIPP' : 'All', acct: undefined },
    { label: 'ISA', acct: 'ISA' },
    { label: 'SIPP', acct: 'SIPP' },
    ...(includePelm
      ? [{ label: 'PELM Trust', acct: 'PELM' as const, title: 'Will Trust — not included in any totals unless selected' }]
      : []),
  ]
  return (
    <div className="flex gap-2 text-sm">
      {options.map(({ label, acct, title }) => (
        <button
          key={label}
          title={title}
          onClick={() => onChange(acct)}
          className={`px-3 py-1 rounded-full border transition-colors ${
            value === acct
              ? 'bg-indigo-600 border-indigo-600 text-white'
              : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
