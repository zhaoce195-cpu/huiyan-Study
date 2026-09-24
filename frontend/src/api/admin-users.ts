/**
 * 管理员 · 用户账号
 * 对接 /api/v1/admin/users/*
 */
import http, { type PageResult } from '@/utils/request'

export type AdminRole = 'STUDENT' | 'TEACHER' | 'ADMIN'

export interface AdminUserItem {
  id: number
  username: string
  realName: string
  role: AdminRole | string
  roleName: string
  department: string
  hospitalName: string
  isActive: boolean
  mustChangePassword: boolean
  lastLoginAt?: string | null
  createdAt?: string | null
}

export interface AdminUserQuery {
  keyword?: string
  role?: AdminRole | ''
  isActive?: boolean | ''
  page?: number
  pageSize?: number
}

export interface AdminUserCreate {
  username: string
  realName: string
  role: AdminRole
  department?: string
  departmentId?: number
  password: string
}

export interface AdminResetPasswordResult {
  userId: number
  username: string
  tempPassword: string
  mustChangePassword: boolean
}

const cleanQuery = (q: AdminUserQuery) => {
  const out: Record<string, any> = {}
  Object.entries(q).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    out[k] = v
  })
  return out
}

export const getAdminUserList = (query: AdminUserQuery = {}) =>
  http.get<PageResult<AdminUserItem>>(
    '/admin/users',
    cleanQuery({ page: 1, pageSize: 20, ...query })
  )

export const createAdminUser = (params: AdminUserCreate) =>
  http.post<AdminUserItem>('/admin/users', params, { showSuccess: true })

export const resetAdminUserPassword = (userId: number) =>
  http.post<AdminResetPasswordResult>(
    `/admin/users/${userId}/reset-password`,
    null,
    { showSuccess: true }
  )

export const setAdminUserActive = (userId: number, isActive: boolean) =>
  http.put<AdminUserItem>(
    `/admin/users/${userId}/active`,
    { isActive },
    { showSuccess: true }
  )
