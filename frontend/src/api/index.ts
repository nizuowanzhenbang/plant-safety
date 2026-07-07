import axios from 'axios'
import type {
  ApiResponse, PaginatedResponse, Hazard, OverviewData,
  AreaStatItem, CategoryStatItem, TrendItem, HazardArea, HazardCategory,
  HazardLevel, HazardStatus,
  WorkTicket, WorkTicketStatus, WorkTicketType,
  OperationTicket, OperationTicketStatus,
  SafetyCheckPlan, SafetyCheckRecord, CheckRecordStatus, CheckResultItem,
  CheckItemTemplate, CheckFrequency, CheckPlanStatus,
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

export const workTicketApi = {
  list: (params?: { page?: number; page_size?: number; ticket_type?: WorkTicketType; status?: WorkTicketStatus; keyword?: string }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<WorkTicket>>>('/work-tickets', { params }),
  get: (id: number) => api.get<unknown, ApiResponse<WorkTicket>>(`/work-tickets/${id}`),
  create: (data: Partial<WorkTicket>) => api.post<unknown, ApiResponse<WorkTicket>>('/work-tickets', data),
  update: (id: number, data: Partial<WorkTicket>) => api.put<unknown, ApiResponse<WorkTicket>>(`/work-tickets/${id}`, data),
  submit: (id: number) => api.post<unknown, ApiResponse<WorkTicket>>(`/work-tickets/${id}/submit`),
  approve: (id: number, approved: boolean, notes?: string) =>
    api.post<unknown, ApiResponse<WorkTicket>>(`/work-tickets/${id}/approve`, { approved, approval_notes: notes }),
  start: (id: number, permitter: string) =>
    api.post<unknown, ApiResponse<WorkTicket>>(`/work-tickets/${id}/start`, { permitter }),
  finish: (id: number, closer: string, close_notes?: string) =>
    api.post<unknown, ApiResponse<WorkTicket>>(`/work-tickets/${id}/finish`, { closer, close_notes }),
  cancel: (id: number, notes?: string) =>
    api.post<unknown, ApiResponse<WorkTicket>>(`/work-tickets/${id}/cancel`, { notes }),
}

export const operationTicketApi = {
  list: (params?: { page?: number; page_size?: number; status?: OperationTicketStatus; keyword?: string }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<OperationTicket>>>('/operation-tickets', { params }),
  get: (id: number) => api.get<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}`),
  create: (data: Partial<OperationTicket>) =>
    api.post<unknown, ApiResponse<OperationTicket>>('/operation-tickets', data),
  update: (id: number, data: Partial<OperationTicket>) =>
    api.put<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}`, data),
  submit: (id: number) =>
    api.post<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}/submit`),
  review: (id: number, reviewer: string, approved: boolean, review_notes?: string) =>
    api.post<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}/review`, { reviewer, approved, review_notes }),
  start: (id: number) =>
    api.post<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}/start`),
  checkStep: (id: number, step: number, notes?: string) =>
    api.post<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}/check-step`, { step, notes }),
  complete: (id: number) =>
    api.post<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}/complete`),
  cancel: (id: number) =>
    api.post<unknown, ApiResponse<OperationTicket>>(`/operation-tickets/${id}/cancel`),
}

export const safetyCheckApi = {
  listPlans: (params?: { page?: number; page_size?: number; area?: HazardArea; frequency?: CheckFrequency; status?: CheckPlanStatus }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<SafetyCheckPlan>>>('/safety-checks/plans', { params }),
  getPlan: (id: number) =>
    api.get<unknown, ApiResponse<SafetyCheckPlan>>(`/safety-checks/plans/${id}`),
  createPlan: (data: { name: string; area: HazardArea; frequency: CheckFrequency; owner_dept: string; description?: string; item_template: CheckItemTemplate[] }) =>
    api.post<unknown, ApiResponse<SafetyCheckPlan>>('/safety-checks/plans', data),
  updatePlan: (id: number, data: Partial<SafetyCheckPlan>) =>
    api.put<unknown, ApiResponse<SafetyCheckPlan>>(`/safety-checks/plans/${id}`, data),

  listRecords: (params?: { page?: number; page_size?: number; plan_id?: number; status?: CheckRecordStatus }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<SafetyCheckRecord>>>('/safety-checks/records', { params }),
  getRecord: (id: number) =>
    api.get<unknown, ApiResponse<SafetyCheckRecord>>(`/safety-checks/records/${id}`),
  generateRecords: (plan_id: number, scheduled_dates: string[]) =>
    api.post<unknown, ApiResponse<SafetyCheckRecord[]>>('/safety-checks/records/generate', { plan_id, scheduled_dates }),
  startRecord: (id: number, inspector: string) =>
    api.post<unknown, ApiResponse<SafetyCheckRecord>>(`/safety-checks/records/${id}/start`, { inspector }),
  submitRecord: (id: number, inspector: string, result_items: CheckResultItem[], summary?: string) =>
    api.post<unknown, ApiResponse<SafetyCheckRecord>>(`/safety-checks/records/${id}/submit`, { inspector, result_items, summary }),
  convertHazard: (record_id: number, seq: number, category: HazardCategory, level: HazardLevel, assignee?: string, assignee_dept?: string, deadline_days?: number) =>
    api.post<unknown, ApiResponse<{ hazard_id: number; hazard_code: string; record: SafetyCheckRecord }>>(
      `/safety-checks/records/${record_id}/convert-hazard`,
      { seq, category, level, assignee, assignee_dept, deadline_days },
    ),
}

export default api
