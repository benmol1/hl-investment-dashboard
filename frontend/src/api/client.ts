const BASE = '/api'

// ---------------------------------------------------------------------------
// Module-level auth state — synchronised from AuthContext via setToken().
// ---------------------------------------------------------------------------

let _token: string | null = null
let _onUnauthorized: (() => void) | null = null

export function setToken(token: string | null): void {
  _token = token
}

export function setUnauthorizedHandler(fn: () => void): void {
  _onUnauthorized = fn
}

// ---------------------------------------------------------------------------
// HTTP client
// ---------------------------------------------------------------------------

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v))
    }
  }

  const headers: HeadersInit = {}
  if (_token) headers['Authorization'] = `Bearer ${_token}`

  const res = await fetch(url.toString(), { headers })

  if (res.status === 401) {
    _onUnauthorized?.()
    throw new Error('Session expired — please sign in again')
  }

  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

export default get
