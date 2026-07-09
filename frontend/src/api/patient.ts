/**
 * 病患账号 / 报告 API
 * 对接后端 /api/v1/auth/* 与 /api/v1/patient/*
 */
import http, { type PageResult } from '@/utils/request'

/* ========== 类型 ========== */

export interface SendCodeParams {
  phone: string
}
export interface SendCodeResult {
  phone: string
  /** 模拟环境直接返回 */
  code: string
  expiresIn: number
}

export interface RegisterParams {
  phone: string
  password: string
  code: string
  realName?: string
}
export interface RegisterResult {
  userId: string
  username: string
  phone: string
  token: string
  expiresAt: string
}

export interface PatientReport {
  caseId: number
  caseNo: string
  patientName: string
  gender: string
  age: number | null
  chiefComplaint: string
  medicalHistory: string

  images: string[]
  imageCount: number

  status: string
  statusText: string

  drGrade: string
  drGradeText: string
  riskLevel: string
  riskLevelText: string
  riskScore: number
  referralRequired: boolean
  lesions: any[]
  doctorDiagnosis: string
  doctorGrade: string
  doctorName: string

  submitAt: string | null
  reviewAt: string | null
  inferredAt: string | null
  createdAt: string | null

  /** 报告状态：pending / confirmed */
  reportStatus?: string
  /** 病患可访问的 PDF 接口路径（已由后端按 caseId 拼接，已确认且文件就绪时有值） */
  reportPdfUrl?: string
  /** 是否可预览/下载 PDF */
  pdfAvailable?: boolean
}

export interface PatientReportListQuery {
  page?: number
  pageSize?: number
  status?: string
}

/* ========== 工具 ========== */

const cleanQuery = (q: Record<string, any>) => {
  const out: Record<string, any> = {}
  Object.entries(q).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    out[k] = v
  })
  return out
}

/* ========== API：账号 ========== */

/** 发送短信验证码（模拟环境固定 1234） */
export const sendCode = (params: SendCodeParams) =>
  http.post<SendCodeResult>('/auth/send_code', params, {
    withToken: false,
    showSuccess: true,
    successText: '验证码已发送'
  })

/** 手机号注册（默认角色 PATIENT） */
export const register = (params: RegisterParams) =>
  http.post<RegisterResult>('/auth/register', params, {
    withToken: false,
    showSuccess: true,
    successText: '注册成功'
  })

/* ========== API：报告 ========== */

/** 我的体检报告列表 */
export const getMyReports = (q: PatientReportListQuery = {}) =>
  http.get<PageResult<PatientReport>>('/patient/my_reports', {
    page: 1,
    pageSize: 20,
    ...cleanQuery(q)
  })

/** 报告详情 */
export const getMyReportDetail = (caseId: number) =>
  http.get<PatientReport>(`/patient/my_reports/${caseId}`)

/** 医生 / 管理员 给病例绑定病患手机号 */
export const bindCasePhone = (caseId: number, patientPhone: string) =>
  http.post<{ caseId: string; patientPhone: string }>(
    '/patient/bind_case',
    { caseId, patientPhone },
    { showSuccess: true, successText: '已绑定' }
  )

/* ========== API：报告 PDF ========== */

/**
 * 预览体检报告 PDF（在新标签页打开）
 * - 走 axios + blob，避免在 URL 中暴露 token
 * - 调用方负责在合适时机 revokeObjectURL
 */
export const previewReportPdf = async (caseId: number): Promise<string> => {
  const blob = await http.raw.request<any, Blob>({
    url: `/patient/report-pdf/${caseId}`,
    method: 'GET',
    params: { disposition: 'inline' },
    responseType: 'blob',
    requestOptions: { showError: true }
  })
  const pdfBlob = new Blob([blob], { type: 'application/pdf' })
  return URL.createObjectURL(pdfBlob)
}

/** 下载体检报告 PDF */
export const downloadReportPdf = (caseId: number, filename?: string) =>
  http.download(
    `/patient/report-pdf/${caseId}`,
    { disposition: 'attachment' },
    filename || `体检报告_${caseId}.pdf`
  )
