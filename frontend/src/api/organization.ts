/**
 * 机构 / 机构申请 API
 * - applyOrg / listOrgs / listMyApplications              （任意登录）
 * - listApplications                                       （TEACHER/ADMIN）
 * - reviewApplication                                      （ADMIN）
 */
import http from '@/utils/request'

export type AppStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface Organization {
  id: number
  name: string
  code?: string
  category?: string
  address?: string
  contact?: string
  phone?: string
  description?: string
  isActive?: boolean
}

export interface OrgApplication {
  id: number
  applicantId: number
  applicantName: string
  applicantPhone: string
  organizationId: number
  organizationName: string
  reason: string
  status: AppStatus
  reviewerId?: number | null
  reviewerName?: string
  reviewComment?: string
  reviewedAt?: string | null
  createdAt: string
  updatedAt: string
}

export interface OrgApplicationPage {
  total: number
  page: number
  pageSize: number
  list: OrgApplication[]
}

export interface ApplyParams {
  organizationId: number
  reason?: string
}

export interface ReviewParams {
  accept: boolean
  comment?: string
}

/** 机构列表（用于申请下拉） */
export const listOrgs = (keyword?: string) =>
  http.get<Organization[]>('/organization/orgs', { keyword })

/** 普通用户：提交申请 */
export const applyOrg = (params: ApplyParams) =>
  http.post<OrgApplication>('/organization/apply', params, {
    showSuccess: true,
    successText: '申请已提交，请等待审核',
  })

/** 我的申请历史 */
export const listMyApplications = (page = 1, pageSize = 20) =>
  http.get<OrgApplicationPage>('/organization/applications/mine', { page, pageSize })

/** 后台：申请分页列表 */
export const listApplications = (params: {
  keyword?: string
  status?: AppStatus | ''
  organizationId?: number
  page?: number
  pageSize?: number
}) => http.get<OrgApplicationPage>('/organization/applications', params)

/** 后台：审核（通过 / 驳回） */
export const reviewApplication = (id: number, params: ReviewParams) =>
  http.post<OrgApplication>(`/organization/applications/${id}/review`, params, {
    showSuccess: true,
    successText: params.accept ? '已通过' : '已驳回',
  })
