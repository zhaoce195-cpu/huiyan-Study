/**
 * 学员开户申请（与机构申请分离）
 */
import http, { type PageResult } from '@/utils/request'

export type StudentAppStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface StudentAppItem {
  id: number
  realName: string
  phone: string
  department: string
  reason: string
  status: StudentAppStatus
  reviewerId?: number | null
  reviewerName?: string
  reviewComment?: string
  reviewedAt?: string | null
  createdUserId?: number | null
  accountUsername?: string | null
  tempPassword?: string | null
  createdAt?: string | null
}

export interface StudentAppCreate {
  realName: string
  phone: string
  department: string
  reason: string
}

export interface StudentAppStatusQuery {
  found: boolean
  status: string
  realName: string
  reviewComment: string
  accountUsername: string
  createdAt?: string | null
  reviewedAt?: string | null
}

export const applyStudentAccount = (params: StudentAppCreate) =>
  http.post<StudentAppItem>('/student-applications', params, {
    withToken: false,
    showSuccess: true,
    successText: '申请已提交，请等待管理员审核'
  })

export const queryStudentAppStatus = (phone: string) =>
  http.get<StudentAppStatusQuery>(
    '/student-applications/status',
    { phone },
    { withToken: false }
  )

export const listStudentApplications = (params: {
  keyword?: string
  status?: StudentAppStatus | ''
  page?: number
  pageSize?: number
}) =>
  http.get<PageResult<StudentAppItem>>('/student-applications', params)

export const reviewStudentApplication = (
  id: number,
  payload: { accept: boolean; comment?: string }
) =>
  http.post<StudentAppItem>(
    `/student-applications/${id}/review`,
    payload,
    { showSuccess: true }
  )
