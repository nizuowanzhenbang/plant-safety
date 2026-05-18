export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type HazardArea =
  | 'MAIN_PLANT' | 'BOILER' | 'TURBINE' | 'ELECTRICAL' | 'FUEL'
  | 'CHEMICAL' | 'ASH_HANDLING' | 'DESULFURIZATION' | 'COOLING_TOWER'
  | 'SWITCHYARD' | 'OFFICE' | 'OTHER'

export type HazardCategory =
  | 'ELECTRICAL_SAFETY' | 'PRESSURE_VESSEL' | 'CHEMICAL_HAZARD'
  | 'WORK_AT_HEIGHT' | 'CONFINED_SPACE' | 'HOT_WORK' | 'LIFTING'
  | 'RADIATION' | 'FIRE_PROTECTION' | 'MECHANICAL'
  | 'ENVIRONMENTAL' | 'HOUSEKEEPING' | 'OTHER'

export type HazardLevel = 'GENERAL' | 'MAJOR'
export type HazardStatus = 'PENDING' | 'IN_PROGRESS' | 'RECTIFIED' | 'VERIFIED' | 'OVERDUE'

export interface Hazard {
  id: number
  hazard_code: string
  title: string
  description: string
  area: HazardArea
  category: HazardCategory
  level: HazardLevel
  reporter: string
  department: string | null
  reported_at: string
  photo_url: string | null
  assignee: string | null
  assignee_dept: string | null
  deadline: string | null
  rectification_measure: string | null
  rectified_at: string | null
  verifier: string | null
  verified_at: string | null
  verification_notes: string | null
  status: HazardStatus
  created_at: string
  updated_at: string
}

export interface OverviewData {
  total_hazards: number
  pending_count: number
  overdue_count: number
  major_count: number
  new_this_month: number
  closed_this_month: number
  rectification_rate: number
}

export interface AreaStatItem {
  area: HazardArea
  count: number
}

export interface CategoryStatItem {
  category: HazardCategory
  count: number
}

export interface TrendItem {
  date: string
  general: number
  major: number
}
