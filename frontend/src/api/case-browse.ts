/**
 * 病例浏览检索 API
 * 对接后端 /api/v1/case-browse/*
 * - 多条件分页检索
 * - 病例详情
 * - 归档 / 取消归档
 */
import http, { type PageResult } from '@/utils/request'

/* ========== 枚举 ========== */
export type CaseCategory = 'DR' | 'AMD' | 'GLAUCOMA' | 'HYPERTENSION' | 'NORMAL' | 'OTHER'
export type CaseDifficulty = 'EASY' | 'MEDIUM' | 'HARD'
export type ArchiveStatus = 'ACTIVE' | 'ARCHIVED'
export type CreatorRole = 'STUDENT' | 'TEACHER' | 'ADMIN'

/* ========== 类型 ========== */

export interface CaseBrowseItem {
  id: number
  caseNo: string
  /** 全局唯一编号 case_sn（CASE+yyyymmdd+6位） */
  caseSn?: string
  title: string
  description: string
  category: CaseCategory
  categoryText: string
  difficulty: string
  difficultyText: string
  /** 盲训态下为 null（未解锁）；亦用于区分「不适用」与「0 级无 DR」 */
  drLevel: number | null
  drGradeText: string
  archiveStatus: ArchiveStatus
  isPublished: boolean
  /** 是否已加入实训库（学员端可见性闸门） */
  isTrainCase: boolean
  creatorId: number
  creatorName: string
  creatorRole: string
  thumbUrl: string | null
  /** 原始影像张数，不含派生对象 */
  imageCount: number
  /** 派生对象数（mask/overlay/金标准） */
  derivedCount?: number
  /** 影像是否完整：有眼底照相原图即为完整 */
  imageComplete?: boolean
  /** 只有眼底照相，没有 OCT、视力或其他病历 */
  fundusOnly?: boolean
  /** 缺失的 role 列表 */
  missingRoles?: string[]
  /** ============ 模拟患者信息 ============ */
  patientName?: string
  patientGender?: string
  patientAge?: number
  /** 完整或脱敏（如 138****5678），由后端按角色返回 */
  patientPhone?: string
  /** 当前用户是否可见完整手机号 */
  phoneVisible?: boolean
  /** 教学用病人编号。空表示这行没有和其他时期连在一起 */
  subjectNo?: string
  /** 检查日期。空表示没有提供 */
  examOn?: string
  visitIndex?: number
  visitCount?: number
  createdAt: string | null
  updatedAt: string | null
}

export interface CaseVisitBrief {
  id: number
  caseNo: string
  examOn: string
  visitIndex: number
}

export interface CaseBrowseDetail extends CaseBrowseItem {
  clinicalInfo: string
  imagePaths: Record<string, string[]>
  images: string[]
  /** 金标准 DR 分级：'0'~'4'；空表示不适用 */
  goldDrGrade?: string | null
  goldDiagnosis: string
  teachingPoints: string
  goldLesions?: Array<Record<string, any>>
  passScore: number
  visits?: CaseVisitBrief[]
}

export interface GoldStandardUpdate {
  goldDrGrade?: string | null
  goldDiagnosis?: string
  teachingPoints?: string
  passScore?: number
  goldLesions?: Array<Record<string, any>>
  /** true=发布并加入实训；false=仅保存草稿 */
  publish?: boolean
}

export interface CaseBrowseQuery {
  keyword?: string
  category?: CaseCategory | ''
  drLevel?: number | ''
  difficulty?: CaseDifficulty | ''
  archiveStatus?: ArchiveStatus | ''
  creatorRole?: CreatorRole | ''
  startTime?: string
  endTime?: string
  /** 只看影像不完整的病例 */
  onlyIncomplete?: boolean
  page?: number
  pageSize?: number
}

export interface CaseArchiveParams {
  archiveStatus: ArchiveStatus
  reason?: string
}

/* ========== 选项常量（前端下拉用） ========== */

export const CATEGORY_OPTIONS: { label: string; value: CaseCategory }[] = [
  { label: '糖尿病视网膜病变', value: 'DR' },
  { label: '老年性黄斑变性', value: 'AMD' },
  { label: '青光眼', value: 'GLAUCOMA' },
  { label: '高血压性视网膜病变', value: 'HYPERTENSION' },
  { label: '正常眼底', value: 'NORMAL' },
  { label: '其他', value: 'OTHER' }
]

export const DR_LEVEL_OPTIONS: { label: string; value: number }[] = [
  { label: '0 级 无 DR', value: 0 },
  { label: '1 级 轻度 NPDR', value: 1 },
  { label: '2 级 中度 NPDR', value: 2 },
  { label: '3 级 重度 NPDR', value: 3 },
  { label: '4 级 PDR（增殖性）', value: 4 }
]

export const DIFFICULTY_OPTIONS: { label: string; value: CaseDifficulty }[] = [
  { label: '入门', value: 'EASY' },
  { label: '中级', value: 'MEDIUM' },
  { label: '高级', value: 'HARD' }
]

export const ARCHIVE_OPTIONS: { label: string; value: ArchiveStatus }[] = [
  { label: '在用', value: 'ACTIVE' },
  { label: '已归档', value: 'ARCHIVED' }
]

export const CREATOR_ROLE_OPTIONS: { label: string; value: CreatorRole }[] = [
  { label: '管理员', value: 'ADMIN' },
  { label: '带教医师', value: 'TEACHER' },
  { label: '住培医师', value: 'STUDENT' }
]

/* ========== API ========== */

const cleanQuery = (q: CaseBrowseQuery) => {
  const out: Record<string, any> = {}
  Object.entries(q).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    out[k] = v
  })
  return out
}

/** 病例分页检索 */
export const getCaseBrowseList = (query: CaseBrowseQuery = {}) => {
  return http.get<PageResult<CaseBrowseItem>>(
    '/case-browse/list',
    cleanQuery({ page: 1, pageSize: 20, ...query })
  )
}

/** 病例详情 */
export const getCaseBrowseDetail = (caseId: number) => {
  return http.get<CaseBrowseDetail>(`/case-browse/${caseId}`)
}

export const setCaseSubject = (
  caseId: number,
  body: { subjectNo: string; examOn: string }
) => http.put<CaseBrowseDetail>(`/case-browse/${caseId}/subject`, body)

/** 归档 / 取消归档 */
export const archiveCase = (caseId: number, params: CaseArchiveParams) => {
  return http.put<CaseBrowseDetail>(
    `/case-browse/${caseId}/archive`,
    params,
    { showSuccess: true }
  )
}

/* ========== 加入实训 ========== */

/** 加入实训接口返回结构 */
export interface JoinTrainingResult {
  /** 加入的病例 ID */
  caseId: number
  /** 是否已加入（true=新加入；false=之前已加入） */
  joined: boolean
  /** 病例编号 */
  caseNo?: string
  /** 完整病例详情（来自后端 join-training 响应） */
  detail?: CaseBrowseDetail
}

/**
 * 将病例加入实训库 —— 学员端方可见 / 可练习。
 * 后端：POST /case-browse/{caseId}/join-training
 * - 仅 TEACHER / ADMIN 可调；学员调用 → 后端 403。
 * - 幂等：已加入再次调用不报错（视作 joined=true）。
 */
export const joinTrainingCase = async (
  caseId: number
): Promise<JoinTrainingResult> => {
  // showError:false —— 由调用方组织文案，避免双重弹窗
  const detail = await http.post<CaseBrowseDetail>(
    `/case-browse/${caseId}/join-training`,
    null,
    { showError: false }
  )
  return {
    caseId: detail?.id ?? caseId,
    caseNo: detail?.caseNo,
    joined: true,
    detail
  }
}

/** 从实训库移除（撤销） */
export const leaveTrainingCase = (caseId: number) =>
  http.delete<CaseBrowseDetail>(
    `/case-browse/${caseId}/join-training`,
    undefined,
    { showError: false }
  )

/**
 * 修订金标准。
 * publish=false → 仍未发布，学员不可见
 * publish=true  → is_published + is_train_case，学员抽题 / 阅片可见
 */
export const updateGoldStandard = (caseId: number, params: GoldStandardUpdate) =>
  http.put<CaseBrowseDetail>(
    `/case-browse/${caseId}/gold-standard`,
    params,
    { showSuccess: true }
  )

export interface CaseImportRow {
  registerNo: string
  title: string
  eyes: string[]
  ok: boolean
  issues: string[]
}

export interface CaseImportReport {
  token: string
  naming: string
  total: number
  passed: number
  failed: number
  rows: CaseImportRow[]
}

export const downloadImportTemplate = () =>
  http.download('/case-browse/import/template', undefined, '病例登记表.csv')

export const checkCaseImport = (sheet: File, images: File[]) => {
  const form = new FormData()
  form.append('sheet', sheet)
  images.forEach((file) => form.append('images', file))
  return http.upload<CaseImportReport>('/case-browse/import/check', form)
}

export const commitCaseImport = (token: string) =>
  http.post<{ count: number; created: { id: number; caseNo: string; title: string }[] }>(
    '/case-browse/import/commit',
    { token },
    { showSuccess: true, successText: '已写入病例库，状态为未发布草稿' }
  )
