import { useEffect, useState } from 'react'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    setState({ data: null, loading: true, error: null })
    fetcher()
      .then((data) => { if (!cancelled) setState({ data, loading: false, error: null }) })
      .catch((e: Error) => { if (!cancelled) setState({ data: null, loading: false, error: e.message }) })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
