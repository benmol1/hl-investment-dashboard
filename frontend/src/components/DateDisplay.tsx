import type { ReactNode } from 'react'

function fmtShort(iso: string): string {
  const d = new Date(iso)
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yy = String(d.getFullYear()).slice(2)
  return `${dd}/${mm}/${yy}`
}

function fmtLong(iso: string, includeTime: boolean): string {
  const d = new Date(iso)
  const date = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  if (!includeTime) return date
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  return `${date}, ${time}`
}

interface Props {
  iso: string | null
  includeTime?: boolean
  fallback?: ReactNode
}

/**
 * Renders a date in short dd/mm/yy format on mobile (< 640px) and in full
 * localised format on tablet/desktop. Both elements are always in the DOM —
 * visibility is toggled via Tailwind's sm: breakpoint so no JS resize logic
 * is needed.
 */
export default function DateDisplay({
  iso,
  includeTime = false,
  fallback = <span className="text-gray-600">—</span>,
}: Props) {
  if (!iso) return <>{fallback}</>
  return (
    <>
      <span className="sm:hidden">{fmtShort(iso)}</span>
      <span className="hidden sm:inline">{fmtLong(iso, includeTime)}</span>
    </>
  )
}
