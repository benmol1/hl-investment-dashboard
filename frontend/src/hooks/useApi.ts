import { useEffect, useState } from 'react'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

const LOADING = { data: null, loading: true, error: null }

const sameDeps = (a: unknown[], b: unknown[]) =>
  a.length === b.length && a.every((v, i) => Object.is(v, b[i]))

/**
 * Fetch on mount and whenever deps change. Data is only returned for the deps it was fetched
 * with: on the render where deps change, the hook reports loading instead of handing back the
 * previous response. (Otherwise a page can briefly render one account's data with another
 * account's settings, e.g. 3,500 daily points drawn as a monthly chart with a dot and gridline
 * per point, which stalls the browser for seconds.)
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): ApiState<T> {
  const [result, setResult] = useState<{ deps: unknown[]; state: ApiState<T> } | null>(null)

  useEffect(() => {
    let cancelled = false
    fetcher()
      .then((data) => { if (!cancelled) setResult({ deps, state: { data, loading: false, error: null } }) })
      .catch((e: Error) => { if (!cancelled) setResult({ deps, state: { data: null, loading: false, error: e.message } }) })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return result && sameDeps(result.deps, deps) ? result.state : LOADING
}
