/**
 * 教学实训分享 API
 */
import http from '@/utils/request'

export type ShareType = 'TEMPORARY' | 'PERMANENT'
export type ShareSource = 'SCREENING' | 'TRAINING'
export type ShareStatus = 'SHARING' | 'EXPIRED' | 'REVOKED' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'SHELVED'

export interface TeachingShare {
  id: number
  shareType: ShareType
  sourceType: ShareSource
  sourceCaseId: number
  teachingCaseId?: number | null
  desensitizedData: Record<string, any>
  shareScope: string
  expireHours: number
  expiredAt?: string | null
  status: ShareStatus
  reviewComment: string
  reviewedAt?: string | null
  reviewerName: string
  teacherId: number
  teacherName: string
  answersRevealed?: boolean
  createdAt?: string
  updatedAt?: string
}

export interface TeachingSharePage {
  total: number
  page: number
  pageSize: number
  list: TeachingShare[]
}

export interface StudentCase {
  id: number
  shareType: ShareType
  title: string
  description: string
  patientAge?: number | null
  patientGender: string
  clinicalInfo: string
  category: string
  difficulty: string
  imagePaths?: Record<string, string[]> | null
  imageCount: number
  teacherName: string
  teachingPoints?: string
  goldDiagnosis?: string
  goldGradeText?: string
  categoryText?: string
  difficultyText?: string
  lesions?: { name: string; detail: string }[]
  annotations?: Record<string, any>[]
  lesionMaskUrl?: string
  answersRevealed?: boolean
  expiredAt?: string | null
  teachingCaseId?: number | null
}

export interface StudentCasePage {
  total: number
  page: number
  pageSize: number
  list: StudentCase[]
}

export interface ShareCreateParams {
  sourceType: ShareSource
  sourceCaseId: number
  shareScope?: string
  expireHours?: number
  hideAnswers?: boolean
}

export interface SubmitCreateParams {
  sourceType: ShareSource
  sourceCaseId: number
  title?: string
  description?: string
}

export interface ReviewParams {
  accept: boolean
  comment?: string
}

export const createShare = (params: ShareCreateParams) =>
  http.post<TeachingShare>('/teaching/share', params)

export const revokeShare = (id: number) =>
  http.post<TeachingShare>(`/teaching/share/${id}/revoke`)

export const revealShare = (id: number) =>
  http.post<TeachingShare>(`/teaching/share/${id}/reveal`)

export const submitForReview = (params: SubmitCreateParams) =>
  http.post<TeachingShare>('/teaching/submit', params)

export const getMyShares = (params: {
  page?: number
  pageSize?: number
  shareType?: ShareType
  status?: ShareStatus
} = {}) => http.get<TeachingSharePage>('/teaching/my-shares', params)

export const getStudentCases = (params: {
  page?: number
  pageSize?: number
} = {}) => http.get<StudentCasePage>('/teaching/student/cases', params)

export const getStudentCaseDetail = (id: number) =>
  http.get<StudentCase>(`/teaching/student/cases/${id}`)

export const getAdminReviews = (params: {
  page?: number
  pageSize?: number
  status?: ShareStatus
  keyword?: string
} = {}) => http.get<TeachingSharePage>('/teaching/admin/reviews', params)

export const adminReview = (id: number, params: ReviewParams) =>
  http.post<TeachingShare>(`/teaching/admin/reviews/${id}`, params)

export const adminShelve = (id: number) =>
  http.post<TeachingShare>(`/teaching/admin/shelve/${id}`)
