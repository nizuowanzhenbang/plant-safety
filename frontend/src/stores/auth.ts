import { create } from 'zustand'
import type { UserRole } from '../types'

interface AuthState {
  token: string | null
  username: string | null
  role: string | null
  setAuth: (token: string, username: string, role: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  username: localStorage.getItem('username'),
  role: localStorage.getItem('role'),
  setAuth: (token, username, role) => {
    localStorage.setItem('token', token)
    localStorage.setItem('username', username)
    localStorage.setItem('role', role)
    set({ token, username, role })
  },
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
    set({ token: null, username: null, role: null })
  },
}))

const ROLE_LEVEL: Record<UserRole, number> = {
  VIEWER: 1,
  OPERATOR: 2,
  SAFETY_OFFICER: 3,
  ADMIN: 4,
}

export function hasMinRole(current: string | null | undefined, min: UserRole): boolean {
  if (!current) return false
  return (ROLE_LEVEL[current as UserRole] ?? 0) >= ROLE_LEVEL[min]
}

export const ROLE_LABEL: Record<UserRole, string> = {
  ADMIN: '管理员',
  SAFETY_OFFICER: '安全员',
  OPERATOR: '操作员',
  VIEWER: '查看者',
}
