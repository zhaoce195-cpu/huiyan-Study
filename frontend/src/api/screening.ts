import http, { type PageResult } from '@/utils/request'
import type { AxiosProgressEvent } from 'axios'

/* ========== 公共枚举 ========== */

export type RiskLevel = 'red' | 'yellow' | 'green'
export type ScreeningStatus = 'queued' | 'analyzing' | 'done' | 'failed'
export type EyeSide = 'OD' | 'OS' | 'OU'
export type Gender = '男' | '女'

/* ========== 类型定义 ========== */

export interface PatientMeta {
  patientId: string
  patientName?: string
  gender?: Gender
  age?: number
  eye?: EyeSide
  hospital?: string
  doctor?: string
  remark?: string
  /** 体检病患账号手机号 — 用于绑定到 patient 用户，便于其登录后查看本人报告 */
  patientPhone?: string
}

export interface UploadFundusResult {
  /** 任务ID */
  taskId: string
  /** 文件存储路径 */
  fileUrl: string
  /** 文件名 */
  fileName: string
  /** 文件大小（字节） */
  fileSize: number
  /** 是否已加入分析队列 */
  queued: boolean
}

export interface BatchUploadResult {
  total: number
  success: number
  failed: number
  items: UploadFundusResult[]
}

export interface ScreeningTask {
  /** 任务ID（业务编号 case_no，形如 T20260521-0001） */
  id: string
  /** 数据库主键（用于 patient/bind_case 等需要数字 ID 的接口） */
  caseId?: number
  /** 患者ID */
  patientId: string
  /** 姓名 */
  patientName: string
  /** 患者手机号（绑定病患账号用） */
  patientPhone?: string
  /** 眼别 */
  eye: EyeSide
  /** 年龄 */
  age: number
  /** 性别 */
  gender: Gender
  /** 任务状态 */
  status: ScreeningStatus
  /** 风险等级 */
  risk: RiskLevel | null
  /** DR 分级文本 */
  dr: string
  /** AI 置信度 0~1 */
  confidence: number
  /** 提交时间 */
  createdAt: string
  /** 文件名 */
  fileName: string
  /** 文件 URL */
  fileUrl?: string
  /** 缩略图 URL */
  thumbUrl?: string
  /** 送检机构 */
  hospital: string
  /** 送检医师 */
  doctor: string
  /** AI 备注 / 建议 */
  remark: string
  /** 是否已绑定病患账号（patient_phone 命中 sys_user.phone） */
  patientBound?: boolean
  /** 是否已医生确认 */
  confirmed?: boolean
  /** 复核医生 */
  reviewer?: string
  /** 复核时间 */
  reviewedAt?: string
  /** ============ CSU-EYES 智能诊断 ============ */
  /** MA / DR / COMPREHENSIVE，未做诊断为 null/undefined */
  diagnosisType?: 'MA' | 'DR' | 'COMPREHENSIVE' | null
  /** 一句话摘要：如 'DR 3级' / 'MA 12 个' */
  diagnosisSummary?: string
  /** 任一只眼的热力图 / 标注图 URL */
  heatmapUrl?: string | null
}

export interface ScreeningQuery {
  /** 关键词（病例编号/姓名/身份证/手机号） */
  keyword?: string
  /** 风险等级 */
  risk?: RiskLevel | ''
  /** 任务状态 */
  status?: ScreeningStatus | ''
  /** 起始时间 */
  startTime?: string
  /** 结束时间 */
  endTime?: string
  /** 送检机构 */
  hospital?: string
  /** 病例编号（独立精筛字段） */
  caseNo?: string
  /** 患者姓名（独立精筛字段） */
  patientName?: string
  /** 手机号（独立精筛字段） */
  phone?: string
  /** 页码 */
  page?: number
  /** 每页数量 */
  pageSize?: number
  /** 排序字段 */
  sortBy?: 'risk' | 'createdAt' | 'confidence'
  /** 排序方向 */
  sortOrder?: 'asc' | 'desc'
  /**
   * 列表场景：
   * - queue   分析任务队列（仅排队中/处理中/失败）
   * - archive 病例检索（仅已完成/已复核）
   * - 省略    全部（向下兼容）
   */
  scope?: 'queue' | 'archive'
  /** 诊断类型筛选：MA / DR / COMPREHENSIVE */
  diagnosisType?: 'MA' | 'DR' | 'COMPREHENSIVE' | ''
}

export interface ScreeningStats {
  total: number
  red: number
  yellow: number
  green: number
  pending: number
  failed: number
  todayCount: number
  weekCount: number
}

export interface ScreeningReport {
  taskId: string
  patientId: string
  patientName: string
  gender: Gender
  age: number
  eye: EyeSide
  hospital: string
  doctor: string
  examTime: string
  reportTime: string
  /** 报告编号 */
  reportNo: string
  /** AI 风险等级 */
  risk: RiskLevel
  /** DR 分级 */
  dr: string
  /** AI 置信度 */
  confidence: number
  /** AI 诊断意见 */
  conclusion: string
  /** 建议处置 */
  suggestion: string
  /** 检出病灶列表 */
  lesions: { type: string; count: number; location?: string }[]
  /** 报告图片 URL（含原图、热力图） */
  imageUrls: { origin: string; heatmap?: string }
  /** 审核医师 */
  reviewer?: string
  /** 审核时间 */
  reviewedAt?: string
}

export interface ReanalyzeParams {
  taskId: string
  /** 强制重跑（忽略缓存） */
  force?: boolean
}

export interface ConfirmReportParams {
  taskId: string
  /** 医生确认的诊断意见（留空使用 AI 结论） */
  diagnosis?: string
  /** 医生确认的建议处置 */
  suggestion?: string
}

export interface ConfirmReportResult {
  taskId: string
  caseId: number
  status: ScreeningStatus
  reviewer: string
  reviewedAt: string
  patientBound: boolean
  patientPhone: string
  patientUserId?: number | null
  /** 报告确认状态：pending / confirmed */
  reportStatus?: string
  /** 病患可访问的 PDF 接口路径 */
  reportPdfUrl?: string
}

/* ========== API 方法 ========== */

/** 单张眼底图上传 */
export const uploadFundus = (
  file: File,
  meta?: PatientMeta,
  onProgress?: (e: AxiosProgressEvent) => void
) => {
  const fd = new FormData()
  fd.append('file', file)
  if (meta) {
    Object.entries(meta).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') fd.append(k, String(v))
    })
  }
  return http.upload<UploadFundusResult>(
    '/screening/upload',
    fd,
    { showError: true },
    { onUploadProgress: onProgress }
  )
}

/** 批量上传眼底图（支持文件夹） */
export const batchUploadFundus = (
  files: File[],
  meta?: PatientMeta,
  onProgress?: (e: AxiosProgressEvent) => void
) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f, f.name))
  if (meta) {
    Object.entries(meta).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') fd.append(k, String(v))
    })
  }
  return http.upload<BatchUploadResult>(
    '/screening/upload/batch',
    fd,
    { showError: true },
    { onUploadProgress: onProgress, timeout: 5 * 60 * 1000 }
  )
}

/** 获取筛查任务分页列表 */
export const getScreeningList = (query: ScreeningQuery = {}) =>
  http.get<PageResult<ScreeningTask>>('/screening/tasks', query)

/** 获取单个筛查任务详情 */
export const getScreeningTask = (taskId: string) =>
  http.get<ScreeningTask>(`/screening/tasks/${taskId}`)

/** 删除（移除）筛查任务 */
export const deleteScreeningTask = (taskId: string) =>
  http.delete<void>(`/screening/tasks/${taskId}`, undefined, {
    showSuccess: true,
    successText: '已移除'
  })

/** 批量操作返回结果 */
export interface BatchTaskOpResult {
  successCount: number
  skippedCount: number
  failedCount: number
  failedIds: string[]
}

/** 批量删除筛查任务 / 病例 */
export const batchDeleteScreeningTasks = (taskIds: string[]) =>
  http.post<BatchTaskOpResult>(
    '/screening/tasks/batch-delete',
    { taskIds },
    { showSuccess: true }
  )

/** 批量从分析队列移出（仅排队中 / 处理中 / 失败的任务会被删除） */
export const batchRemoveFromQueue = (taskIds: string[]) =>
  http.post<BatchTaskOpResult>(
    '/screening/tasks/batch-remove-queue',
    { taskIds },
    { showSuccess: true }
  )

/** 重新分析 */
export const reanalyzeTask = (params: ReanalyzeParams) =>
  http.post<ScreeningTask>('/screening/tasks/reanalyze', params, {
    showSuccess: true,
    successText: '已加入重新分析队列'
  })

/** 获取风险/状态统计数据 */
export const getScreeningStats = (scope?: 'queue' | 'archive') =>
  http.get<ScreeningStats>('/screening/stats', scope ? { scope } : undefined)

/** 获取筛查报告详情 */
export const getScreeningReport = (taskId: string) =>
  http.get<ScreeningReport>(`/screening/reports/${taskId}`)

/** 导出单份筛查报告 PDF */
export const exportReportPdf = (taskId: string, fileName?: string) =>
  http.download(`/screening/reports/${taskId}/pdf`, undefined, fileName || `report_${taskId}.pdf`)

/** 导出汇总报告 PDF（按查询条件） */
export const exportSummaryPdf = (query: ScreeningQuery = {}, fileName?: string) =>
  http.download('/screening/reports/summary/pdf', query, fileName || `summary_${Date.now()}.pdf`)

/** 导出筛查列表 Excel */
export const exportScreeningExcel = (query: ScreeningQuery = {}, fileName?: string) =>
  http.download('/screening/tasks/export', query, fileName || `screening_${Date.now()}.xlsx`)

/** 高危病例一键转诊 */
export const referHighRisk = (taskId: string, targetHospital: string, note?: string) =>
  http.post<void>(
    '/screening/refer',
    { taskId, targetHospital, note },
    { showSuccess: true, successText: '转诊申请已提交' }
  )

/** 医生确认报告（自动同步至病患账号） */
export const confirmReport = (params: ConfirmReportParams) =>
  http.post<ConfirmReportResult>('/screening/reports/confirm', params, {
    showError: true
  })

/* ========== 病例补充修改 + 上传眼底图（医生 / 管理员） ========== */

export interface CaseUpdateParams {
  patientName?: string
  gender?: '男' | '女'
  age?: number | null
  patientPhone?: string
  chiefComplaint?: string
  medicalHistory?: string
  remark?: string
}

export interface CaseImageItem {
  eye: EyeSide
  url: string
  fileName?: string
}

export interface CaseImagesResult {
  caseId: number
  imageCount: number
  images: CaseImageItem[]
}

/** 补充修改病例（PUT /screening/cases/{caseId}） */
export const updateCase = (caseId: number, params: CaseUpdateParams) =>
  http.put<ScreeningTask>(`/screening/cases/${caseId}`, params, {
    showSuccess: true,
    successText: '已保存'
  })

/** 列出病例所有眼底图 */
export const listCaseImages = (caseId: number) =>
  http.get<CaseImagesResult>(`/screening/cases/${caseId}/images`)

/**
 * 补充上传眼底图（多文件，可选眼别）
 * @param onProgress 进度回调（0~100）
 */
export const addCaseImages = (
  caseId: number,
  files: File[],
  eye: EyeSide = 'OU',
  onProgress?: (percent: number) => void
) => {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  fd.append('eye', eye)
  return http.upload<CaseImagesResult>(
    `/screening/cases/${caseId}/images`,
    fd,
    { showSuccess: true, successText: '影像已补充' },
    {
      onUploadProgress: (e) => {
        if (!onProgress) return
        const total = e.total || 0
        if (total > 0) {
          onProgress(Math.round(((e.loaded || 0) * 100) / total))
        }
      }
    }
  )
}

/** 删除病例某张眼底图 */
export const deleteCaseImage = (caseId: number, url: string) =>
  http.delete<CaseImagesResult>(
    `/screening/cases/${caseId}/images`,
    undefined,
    { showSuccess: true, successText: '已删除' },
    { data: { url } }
  )
