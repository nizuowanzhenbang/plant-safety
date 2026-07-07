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

export type UserRole = 'ADMIN' | 'SAFETY_OFFICER' | 'OPERATOR' | 'VIEWER'

// ============== 工作票 ==============
export type WorkTicketType =
  | 'ELECTRICAL_FIRST' | 'ELECTRICAL_SECOND' | 'THERMAL'
  | 'HOT_WORK' | 'CONFINED_SPACE' | 'HIGH_ALTITUDE'

export type WorkTicketStatus =
  | 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED'
  | 'IN_PROGRESS' | 'SUSPENDED' | 'COMPLETED' | 'CANCELLED'

export interface WorkTicket {
  id: number
  ticket_code: string
  ticket_type: WorkTicketType
  title: string
  work_content: string
  work_location: string
  issuer: string
  work_leader: string
  work_members: string | null
  supervisor: string | null
  permitter: string | null
  planned_start: string
  planned_end: string
  actual_start: string | null
  actual_end: string | null
  safety_measures: string
  risk_points: string | null
  approver: string | null
  approved_at: string | null
  approval_notes: string | null
  closer: string | null
  closed_at: string | null
  close_notes: string | null
  status: WorkTicketStatus
  created_at: string
  updated_at: string
}

// ============== 操作票 ==============
export type OperationTicketStatus =
  | 'DRAFT' | 'PENDING_REVIEW' | 'READY' | 'EXECUTING' | 'COMPLETED' | 'CANCELLED'

export interface OperationStep {
  step: number
  content: string
  done: boolean
  checked_at?: string | null
  notes?: string | null
}

export interface OperationTicket {
  id: number
  ticket_code: string
  title: string
  operation_target: string
  operator: string
  supervisor: string
  issuer: string
  reviewer: string | null
  planned_at: string
  started_at: string | null
  completed_at: string | null
  steps: OperationStep[]
  reviewed_at: string | null
  review_notes: string | null
  status: OperationTicketStatus
  created_at: string
  updated_at: string
}

// ============== 安全检查 ==============
export type CheckFrequency = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'YEARLY' | 'ADHOC'
export type CheckPlanStatus = 'ACTIVE' | 'PAUSED' | 'ARCHIVED'
export type CheckRecordStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'OVERDUE'

export interface CheckItemTemplate {
  seq: number
  content: string
  standard?: string | null
  weight?: number | null
}

export interface SafetyCheckPlan {
  id: number
  name: string
  area: HazardArea
  frequency: CheckFrequency
  owner_dept: string
  description: string | null
  item_template: CheckItemTemplate[]
  status: CheckPlanStatus
  created_at: string
  updated_at: string
}

export interface CheckResultItem {
  seq: number
  content: string
  standard?: string | null
  conformant: boolean
  notes?: string | null
  hazard_id?: number | null
}

export interface SafetyCheckRecord {
  id: number
  record_code: string
  plan_id: number
  plan_name: string | null
  area: HazardArea | null
  scheduled_date: string
  inspector: string | null
  started_at: string | null
  completed_at: string | null
  result_items: CheckResultItem[]
  total_items: number
  nonconformant_count: number
  summary: string | null
  status: CheckRecordStatus
  created_at: string
  updated_at: string
}

// ============== WebSocket ==============
export interface WSEvent {
  event: string
  title: string
  message: string
  payload?: Record<string, unknown>
  ts: string
}
