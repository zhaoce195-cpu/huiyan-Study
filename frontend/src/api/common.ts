import http from '@/utils/request'

/* ========== 类型定义 ========== */

export interface DictItem {
  /** 字典编码 */
  code: string
  /** 显示名称 */
  label: string
  /** 排序值 */
  sort?: number
  /** 备注 */
  remark?: string
  /** 子项 */
  children?: DictItem[]
}

export interface Hospital {
  id: number | string
  name: string
  level?: string
  province?: string
  city?: string
}

export interface Department {
  id: number | string
  name: string
  hospitalId?: number | string
}

export interface SystemConfig {
  /** 平台名称 */
  appName: string
  /** 平台版本 */
  version: string
  /** 备案号 */
  recordNo?: string
  /** 服务条款 URL */
  termsUrl?: string
  /** 隐私政策 URL */
  privacyUrl?: string
  /** 文件上传上限（MB） */
  uploadMaxMb: number
  /** 允许的图片格式 */
  acceptImageTypes: string[]
}

export interface UploadFileResult {
  /** 文件 URL */
  url: string
  /** 完整访问路径 */
  fullUrl: string
  /** 文件名 */
  fileName: string
  /** 文件大小 */
  fileSize: number
  /** MIME 类型 */
  mimeType: string
}

export interface NotificationItem {
  id: string | number
  /** 通知类型 */
  type: 'system' | 'screening' | 'training' | 'refer'
  title: string
  content: string
  /** 公告全文，登录弹窗 / 回看详情用 */
  body?: string
  read: boolean
  isRead?: boolean
  isTop?: boolean
  publisherName?: string
  publishAt?: string
  createdAt: string
}

export interface OperationLog {
  id: string | number
  userId: string | number
  username: string
  module: string
  action: string
  detail?: string
  ip?: string
  createdAt: string
}

/* === 公告（管理） === */

export type NoticeType = 'SYSTEM' | 'TRAINING' | 'SCREENING' | 'EXAM'
export type NoticeStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'

export interface Notice {
  id: number
  title: string
  summary?: string
  content?: string
  coverUrl?: string
  noticeType: NoticeType
  status: NoticeStatus
  visibleRoles?: string
  isTop: boolean
  publisherId: number
  publisherName: string
  publishAt?: string | null
  expireAt?: string | null
  viewCount: number
  createdAt: string
  updatedAt: string
}

export interface NoticePage {
  total: number
  page: number
  pageSize: number
  list: Notice[]
}

export interface NoticeSaveParams {
  title: string
  summary?: string
  content: string
  coverUrl?: string
  noticeType?: NoticeType
  status?: NoticeStatus
  visibleRoles?: string
  isTop?: boolean
  publishAt?: string | null
  expireAt?: string | null
}

/* === 科室管理 === */

export interface DepartmentSaveParams {
  /** 所属医院；不传 = 全院通用科室（所有医院可见） */
  hospitalId?: number
  code?: string
  name: string
  shortName?: string
  leader?: string
  phone?: string
  sortOrder?: number
  isActive?: boolean
  remark?: string
}

/* === 全院培训统计 === */

export interface OverviewItem {
  label: string
  value: number
}

export interface TrainingOverview {
  totalUsers: number
  totalCases: number
  totalRecords: number
  avgIou: number
  passRate: number
  byDifficulty: OverviewItem[]
  byDrGrade: OverviewItem[]
}

export interface StudyHoursItem {
  userId: number
  username: string
  realName: string
  department: string
  totalSeconds: number
  totalHours: number
  caseCount: number
  avgIou: number
}

export interface StudyHoursResult {
  total: number
  list: StudyHoursItem[]
}

/* ========== API 方法 ========== */

/** 获取系统配置 */
export const getSystemConfig = () =>
  http.get<SystemConfig>('/common/system/config', undefined, { withToken: false })

/** 服务健康检查（用于联调测试） */
export const ping = () =>
  http.get<{ status: 'ok'; time: string }>('/common/ping', undefined, {
    withToken: false,
    showError: false
  })

/** 通用单文件上传 */
export const uploadFile = (file: File, biz?: string) => {
  const fd = new FormData()
  fd.append('file', file)
  if (biz) fd.append('biz', biz)
  return http.upload<UploadFileResult>('/common/upload', fd)
}

/** 根据字典类型获取字典列表 */
export const getDict = (type: string) =>
  http.get<DictItem[]>(`/common/dict/${type}`)

/** 批量获取字典 */
export const getDictBatch = (types: string[]) =>
  http.post<Record<string, DictItem[]>>('/common/dict/batch', { types })

/** 获取医院列表 */
export const getHospitalList = (keyword?: string) =>
  http.get<Hospital[]>('/common/hospitals', { keyword })

/** 获取科室列表 */
export const getDepartmentList = (hospitalId?: number | string) =>
  http.get<Department[]>('/common/departments', { hospitalId })

/** 获取我的通知列表 */
export const getNotifications = (page = 1, pageSize = 20) =>
  http.get<{ total: number; unread: number; list: NotificationItem[] }>(
    '/common/notifications',
    { page, pageSize }
  )

/** 标记通知已读 */
export const markNotificationRead = (ids: (string | number)[]) =>
  http.post<void>('/common/notifications/read', { ids })

/** 全部标记已读 */
export const markAllNotificationsRead = () =>
  http.post<void>('/common/notifications/read-all', null, {
    showSuccess: true,
    successText: '已全部标为已读'
  })

/** 操作日志查询 */
export const getOperationLogs = (params: {
  module?: string
  startTime?: string
  endTime?: string
  page?: number
  pageSize?: number
}) =>
  http.get<{ total: number; list: OperationLog[] }>(
    '/common/logs/operation',
    params
  )

/** 获取服务器当前时间（用于报告时间戳） */
export const getServerTime = () =>
  http.get<{ time: string; timezone: string }>('/common/time')

/* ========== 公告（管理类） ========== */

/** 公告分页（管理） — TEACHER/ADMIN */
export const getNoticeList = (params: {
  keyword?: string
  noticeType?: NoticeType | ''
  status?: NoticeStatus | ''
  page?: number
  pageSize?: number
}) => http.get<NoticePage>('/common/notices', params)

/** 公告详情 — 自动 +1 阅读量 */
export const getNoticeDetail = (id: number) => http.get<Notice>(`/common/notices/${id}`)

/** 新建公告 — TEACHER/ADMIN */
export const createNotice = (params: NoticeSaveParams) =>
  http.post<Notice>('/common/notices', params, {
    showSuccess: true,
    successText: '已发布，学员登录将弹出未读公告'
  })

/** 更新公告 — TEACHER/ADMIN */
export const updateNotice = (id: number, params: NoticeSaveParams) =>
  http.put<Notice>(`/common/notices/${id}`, params, {
    showSuccess: true,
    successText: '已发布，学员登录将再次弹出未读公告'
  })

/** 删除公告 — ADMIN */
export const deleteNotice = (id: number) =>
  http.delete<void>(`/common/notices/${id}`, undefined, {
    showSuccess: true,
    successText: '已删除'
  })

/* ========== 科室管理（ADMIN） ========== */

/** 新建科室 — ADMIN */
export const createDepartment = (params: DepartmentSaveParams) =>
  http.post<Department>('/common/departments', params, {
    showSuccess: true,
    successText: '创建成功'
  })

/** 更新科室 — ADMIN */
export const updateDepartment = (deptId: number | string, params: DepartmentSaveParams) =>
  http.put<Department>(`/common/departments/${deptId}`, params, {
    showSuccess: true,
    successText: '更新成功'
  })

/** 删除科室 — ADMIN */
export const deleteDepartment = (deptId: number | string) =>
  http.delete<void>(`/common/departments/${deptId}`, undefined, {
    showSuccess: true,
    successText: '已删除'
  })

/* ========== 平台统计 ========== */

/** 全院培训统计 — TEACHER/ADMIN */
export const getTrainingOverview = () =>
  http.get<TrainingOverview>('/common/stats/training')

/** 学员学时汇总 — TEACHER/ADMIN */
export const getStudyHours = (params: {
  keyword?: string
  page?: number
  pageSize?: number
} = {}) => http.get<StudyHoursResult>('/common/stats/study-hours', params)
