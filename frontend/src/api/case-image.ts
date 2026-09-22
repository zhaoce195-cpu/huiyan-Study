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
export type EyeSide = 'OD' | 'OS' | 'OU' | 'UK'

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

export interface BackfillPatientParams {
  /** 只补空字段 */
  onlyEmpty?: boolean
  /** 强制覆盖已有的模拟患者信息（筛查病例始终不受影响） */
  overwrite?: boolean
}

export interface BackfillPatientResult {
  trainingTotal: number
  trainingFilled: number
  /** 恒为 0：筛查病例对应真实受检者，不生成也不覆盖 */
  screeningTotal: number
  screeningFilled: number
  caseSnFilled: number
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
  sourcePath?: string
}

export interface IdridProbeResult {
  sourcePath: string
  defaultPath: string
  exists: boolean
  ready: boolean
  missingSubdirs: string[]
  imageCount: number
  trainCount: number
  testCount: number
  hint: string
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
  eye: EyeSide = 'UK',
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

/** 探测服务器约定目录是否已放好数据集（不写库） */
export const probeIdrid = (sourcePath?: string) =>
  http.get<IdridProbeResult>('/admin/import/idrid/probe', {
    sourcePath: sourcePath || undefined
  })

/** 批量导入 IDRiD（管理员） */
export const importIdrid = (params: IdridImportParams) =>
  http.post<IdridImportResult>('/admin/import/idrid', params, {
    showError: true
  }, {
    timeout: 10 * 60 * 1000
  })

/* ========== 一键补齐旧病例的模拟患者信息 ========== */

/**
 * 补齐教学病例的模拟患者信息。
 *
 * 此前这个函数被删掉了，但管理后台的按钮一直留着 —— 点了必定报错，
 * 功能从未可用（遗留清单 D-001）。现补回实现，后端路由同步补齐。
 *
 * 训练病例来自公开数据集，本就没有患者身份；筛查病例对应真实受检者，
 * 一律不生成也不覆盖。
 */
export const backfillPatientInfo = (params: BackfillPatientParams) =>
  http.post<BackfillPatientResult>('/admin/import/backfill-patient', params, {
    showError: true
  })

