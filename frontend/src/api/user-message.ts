/**
 * 用户站内消息 API
 * - getMyMessages / getUnreadCount / markRead / markAllRead
 * 全部仅需任意登录
 */
import http from '@/utils/request'

export type MessageType = 'org_application' | 'system' | string

export interface UserMessage {
  id: number
  type: MessageType
  title: string
  content: string
  refType?: string
  refId?: number | null
  isRead: boolean
  readAt?: string | null
  createdAt: string
}

export interface UserMessagePage {
  total: number
  unread: number
  page: number
  pageSize: number
  list: UserMessage[]
}

export const getMyMessages = (params: {
  type?: MessageType
  page?: number
  pageSize?: number
} = {}) => http.get<UserMessagePage>('/user-messages', params)

export const getUnreadCount = () =>
  http.get<{ unread: number }>('/user-messages/unread-count')

export const markRead = (id: number) =>
  http.post<void>(`/user-messages/${id}/read`)

export const markBatchRead = (ids: number[]) =>
  http.post<{ updated: number }>('/user-messages/read', { ids })

export const markAllRead = () =>
  http.post<{ updated: number }>('/user-messages/read-all', null, {
    showSuccess: true,
    successText: '已全部标为已读',
  })
