import type { ReactNode } from 'react'
import { usePrivacy } from './context'

interface Props {
  children: ReactNode
  className?: string
}

/**
 * Wraps a cash amount so it can be visually obscured when privacy mode is on.
 * The underlying value is never changed — only blurred via CSS.
 */
export default function Cash({ children, className = '' }: Props) {
  const { obscured } = usePrivacy()
  return (
    <span className={`${obscured ? 'pv-blur' : ''} ${className}`.trim()}>
      {children}
    </span>
  )
}
