interface Option {
  key: string
  label: string
  colour?: string
  title?: string
}

interface Props {
  options: Option[]
  selected: string[]
  onChange: (selected: string[]) => void
  /** Prevent deselecting the last remaining option. */
  requireOne?: boolean
}

/** Row of toggle chips allowing any number of options to be on at once. */
export default function MultiToggle({ options, selected, onChange, requireOne = false }: Props) {
  const toggle = (key: string) => {
    if (selected.includes(key)) {
      if (requireOne && selected.length === 1) return
      onChange(selected.filter((k) => k !== key))
    } else {
      onChange([...selected, key])
    }
  }
  return (
    <div className="flex gap-2 text-sm flex-wrap sm:justify-end">
      {options.map(({ key, label, colour, title }) => {
        const on = selected.includes(key)
        return (
          <button
            key={key}
            title={title}
            aria-pressed={on}
            onClick={() => toggle(key)}
            className={`px-3 py-1 rounded-full border transition-colors flex items-center gap-1.5 ${
              on
                ? 'bg-gray-800 border-gray-500 text-white'
                : 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'
            }`}
          >
            {colour && (
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: on ? colour : 'transparent', border: `1px solid ${colour}` }}
              />
            )}
            {label}
          </button>
        )
      })}
    </div>
  )
}
