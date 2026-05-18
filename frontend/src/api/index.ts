import axios from 'axios'
import type {
  ApiResponse, PaginatedResponse, Hazard, OverviewData,
  AreaStatItem, CategoryStatItem, TrendItem, HazardArea, HazardCategory,
  HazardLevel, HazardStatus,
} from '../types'

const api = axios.create({ baseURL: '/api', timeout: 15000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err.response?.data || err)
  },
)

export const authApi = {
  login: (username: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return api.post<unknown, { access_token: string; token_type: string }>('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
  me: () => api.get<unknown, ApiResponse<{ id: number; username: string; role: string; department: string | null }>>('/auth/me'),
}

export const hazardApi = {
  list: (params?: {
    page?: number; page_size?: number;
    area?: HazardArea; category?: HazardCategory;
    level?: HazardLevel; status?: HazardStatus; keyword?: string
  }) => api.get<unknown, ApiResponse<PaginatedResponse<Hazard>>>('/hazards', { params }),

  create: (data: Partial<Hazard>) =>
    api.post<unknown, ApiResponse<Hazard>>('/hazards', data),

  get: (id: number) =>
    api.get<unknown, ApiResponse<Hazard>>(`/hazards/${id}`),

  update: (id: number, data: Partial<Hazard>) =>
    api.put<unknown, ApiResponse<Hazard>>(`/hazards/${id}`, data),

  rectify: (id: number, rectification_measure: string) =>
    api.post<unknown, ApiResponse<Hazard>>(`/hazards/${id}/rectify`, { rectification_measure }),

  verify: (id: number, verifier: string, verification_notes: string, passed: boolean) =>
    api.post<unknown, ApiResponse<Hazard>>(`/hazards/${id}/verify`, { verifier, verification_notes, passed }),
}

export const dashboardApi = {
  overview: () => api.get<unknown, ApiResponse<OverviewData>>('/dashboard/overview'),
  byArea: () => api.get<unknown, ApiResponse<AreaStatItem[]>>('/dashboard/by-area'),
  byCategory: () => api.get<unknown, ApiResponse<CategoryStatItem[]>>('/dashboard/by-category'),
  trend: (days?: number) => api.get<unknown, ApiResponse<TrendItem[]>>('/dashboard/trend', { params: { days } }),
}

export default api
