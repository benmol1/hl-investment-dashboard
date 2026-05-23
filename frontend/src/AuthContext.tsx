import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react'
import { setToken, setUnauthorizedHandler } from './api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthState {
  token: string | null
  userId: string | null
  role: string | null
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({
    token: null,
    userId: null,
    role: null,
  })

  // Keep the API client's module-level token in sync with React state.
  useEffect(() => {
    setToken(auth.token)
  }, [auth.token])

  // When the API client receives a 401, clear the token so ProtectedRoute
  // redirects to /login, and set a flag so LoginPage shows an expiry message.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      sessionStorage.setItem('hl_session_expired', '1')
      setAuth({ token: null, userId: null, role: null })
    })
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const body = new URLSearchParams({ username, password })
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    })

    if (!res.ok) {
      // Try to parse FastAPI's error detail, fall back to generic message.
      let detail = 'Login failed'
      try {
        const err = await res.json()
        if (err.detail) detail = err.detail
      } catch {
        // ignore parse errors
      }
      throw new Error(detail)
    }

    const data: { access_token: string; token_type: string } = await res.json()

    // Decode the JWT payload (middle segment) to extract user_id and role.
    // We trust this data only for UI display — the server re-validates on every request.
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))

    setAuth({
      token: data.access_token,
      userId: payload.sub ?? null,
      role: payload.role ?? null,
    })
  }, [])

  const logout = useCallback(() => {
    setAuth({ token: null, userId: null, role: null })
  }, [])

  return (
    <AuthContext.Provider value={{ ...auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
