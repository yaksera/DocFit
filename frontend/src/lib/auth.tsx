import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, type Me } from './api'

interface AuthState {
  me: Me | null
  loading: boolean
  setMe: (me: Me | null) => void
  refresh: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>('auth/me'))
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setMe(null)
      else throw e
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh().catch(() => setLoading(false))
  }, [refresh])

  const logout = useCallback(async () => {
    await api('auth/logout', { method: 'POST' })
    setMe(null)
  }, [])

  return <AuthContext.Provider value={{ me, loading, setMe, refresh, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}

/** For pages inside the app shell, where `me` is guaranteed. */
export function useMe(): Me {
  const { me } = useAuth()
  if (!me) throw new Error('Not signed in')
  return me
}
