import { useState, useEffect } from 'react'

/**
 * Returns a responsive chart height — smaller on mobile (< 640px) so charts
 * don't consume the full viewport before the user can scroll to other content.
 */
export function useChartHeight(mobile: number, desktop: number): number {
  const [height, setHeight] = useState(() =>
    typeof window !== 'undefined' && window.innerWidth < 640 ? mobile : desktop,
  )

  useEffect(() => {
    const update = () => setHeight(window.innerWidth < 640 ? mobile : desktop)
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [mobile, desktop])

  return height
}
