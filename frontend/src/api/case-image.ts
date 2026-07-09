/**
 * 病例影像（一对多）API
 * 对接后端 /api/v1/case-images/*
 */
import http, { type PageResult } from '@/utils/request'

/* ========== 类型 ========== */

export type CaseTable = 'screening' | 'training'
export type CaseImageRole =
  | 'original'
  | 'MA'
  | 'HE'
  | 'EX'
  | 'SE'
  | 'OD'
  | 'color_mask'
  | 'overlay'
  | 'class_mask'
  | 'other'
export type EyeSide = 'OD' | 'OS' | 'OU'

export interface CaseImageItem {
  id: number
  caseTable: CaseTable
  caseId: number
  role: CaseImageRole
  roleText: string
  eye: EyeSide
  fileUrl: string
  fileName: string
  fileSize: number
  width: number
  height: number
  sortOrder: number
  uploadedBy: number | null
  uploaderName: string
  createdAt: string | null
}

export interface CaseImagesGrouped {
  caseTable: CaseTable
  caseId: number
  caseSn: string
  caseNo: string
  imageGroups: Partial<Record<CaseImageRole, string[]>>
  items: CaseImageItem[]
  imageComplete: boolean
  missingRoles: CaseImageRole[]
}

export interface IncompleteCaseRow {
  caseTable: CaseTable
  caseId: number
  caseNo: string
  caseSn: string
  title: string
  missingRoles: CaseImageRole[]
  imageCount: number
}

export interface IdridImportParams {
  sourcePath?: string
  limit?: number
  dryRun?: boolean
  skipExisting?: boolean
}

export interface IdridImportResult {
  importedCases: number
  appendedImages: number
  skippedCases: number
  incompleteCases: number
  gradeDistribution: Record<string, number>
  elapsedSec: number
  dryRun: boolean
  sampleCaseSns: string[]
}

/* ========== 中文展示工具 ========== */

export const ROLE_LABEL: Record<CaseImageRole, string> = {
  original: '原图',
  MA: '微血管瘤 (MA)',
  HE: '出血 (HE)',
  EX: '硬性渗出 (EX)',
  SE: '软性渗出 (SE)',
  OD: '视盘 (OD)',
  color_mask: '彩色 mask',
  overlay: '金标准叠加',
  class_mask: '类别 mask',
  other: '其它'
}

export const ROLE_ORDER: CaseImageRole[] = [
  'original',
  'MA',
  'HE',
  'EX',
  'SE',
  'OD',
  'color_mask',
  'overlay',
  'class_mask',
  'other'
]

/* ========== API ========== */

/** 列出某病例所有影像（按 role 分组 + items 数组） */
export const listCaseImages = (caseTable: CaseTable, caseId: number, roles?: CaseImageRole[]) =>
  http.get<CaseImagesGrouped>('/case-images', {
    caseTable,
    caseId,
    roles: roles?.join(',') || undefined
  })

/**
 * 病例补传 / 追加影像（医生 / 管理员）
 * @param onProgress 进度回调（0~100）
 */
export const uploadCaseImages = (
  caseTable: CaseTable,
  caseId: number,
  files: File[],
  role: CaseImageRole,
  eye: EyeSide = 'OU',
  onProgress?: (percent: number) => void
) => {
  const fd = new FormData()
  fd.append('caseTable', caseTable)
  fd.append('caseId', String(caseId))
  fd.append('role', role)
  fd.append('eye', eye)
  for (const f of files) fd.append('files', f)
  return http.upload<{ items: CaseImageItem[] }>(
    '/case-images/upload',
    fd,
    { showSuccess: true, successText: '已上传' },
    {
      onUploadProgress: (e) => {
        if (!onProgress) return
        const total = e.total || 0
        if (total > 0) onProgress(Math.round(((e.loaded || 0) * 100) / total))
      }
    }
  )
}

/** 删除一张影像 */
export const deleteCaseImage = (imageId: number) =>
  http.delete<null>(`/case-images/${imageId}`, undefined, {
    showSuccess: true,
    successText: '已删除'
  })

/** 列出影像不完整的病例（管理员） */
export const listIncompleteCases = (
  caseTable: CaseTable = 'training',
  page = 1,
  pageSize = 20
) =>
  http.get<PageResult<IncompleteCaseRow>>('/case-images/incomplete', {
    caseTable,
    page,
    pageSize
  })

/** 批量导入 IDRiD（管理员） */
export const importIdrid = (params: IdridImportParams) =>
  http.post<IdridImportResult>('/admin/import/idrid', params, {
    showError: true
  })

/* ========== 一键补齐旧病例的模拟患者信息 ========== */
// 已移除：前端没有任何按钮调用此 API；后端端点 /admin/import/backfill-patient-info 同步下线

