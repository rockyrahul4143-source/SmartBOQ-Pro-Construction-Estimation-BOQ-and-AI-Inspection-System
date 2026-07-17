import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

export interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'estimation_engineer' | 'quantity_surveyor' | 'project_manager'
  company?: string
  designation?: string
  phone?: string
  is_active: boolean
}

interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  updateUser: (u: User) => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  })

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      // Try to restore existing session
      api.get('/auth/me')
        .then(({ data }) => setState({ user: data, isLoading: false, isAuthenticated: true }))
        .catch(() => autoLogin())
    } else {
      // No token — auto login as admin for local dev
      autoLogin()
    }
  }, [])

  const autoLogin = () => {
    api.post('/auth/login', { email: 'admin@smartboq.com', password: 'Admin@1234' })
      .then(({ data }) => {
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        setState({ user: data.user, isLoading: false, isAuthenticated: true })
      })
      .catch(() => {
        // Backend not ready yet — show login page
        setState({ user: null, isLoading: false, isAuthenticated: false })
      })
  }

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    setState({ user: data.user, isLoading: false, isAuthenticated: true })
  }, [])

  const logout = useCallback(() => {
    localStorage.clear()
    setState({ user: null, isLoading: false, isAuthenticated: false })
  }, [])

  const updateUser = useCallback((u: User) => {
    setState(s => ({ ...s, user: u }))
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}

export function useIsAdmin() {
  const { user } = useAuth()
  return user?.role === 'admin'
}
