import React, { createContext, useState, useEffect, useCallback } from 'react'
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

export interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
}

export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  updateUser: (u: User) => void
}

export const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  })

  useEffect(() => {
    // Restore session from stored token only — never auto-login with hardcoded credentials
    const token = localStorage.getItem('access_token')
    if (token) {
      api.get('/auth/me')
        .then(({ data }) => setState({ user: data, isLoading: false, isAuthenticated: true }))
        .catch(() => {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          setState({ user: null, isLoading: false, isAuthenticated: false })
        })
    } else {
      setState({ user: null, isLoading: false, isAuthenticated: false })
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    setState({ user: data.user, isLoading: false, isAuthenticated: true })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
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
