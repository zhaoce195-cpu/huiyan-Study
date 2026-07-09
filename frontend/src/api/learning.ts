/**
 * 学习资料 / 收藏 / 笔记 API
 * 对接后端 /api/v1/learning/*
 */
import http, { type PageResult } from '@/utils/request'

/* ========== 类型 ========== */

export type ResourceType =
  | 'CASE_TEMPLATE'
  | 'COURSEWARE'
  | 'KNOWLEDGE'
  | 'IMAGE_DEMO'
export type ResourceStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'

export interface LearningResource {
  id: number
  title: string
  summary: string
  content: string
  resourceType: ResourceType
  resourceTypeText: string
  tags: string
  coverUrl: string
  fileUrl: string
  fileType: string
  caseId: number | null
  status: ResourceStatus
  publisherId: number
  publisherName: string
  viewCount: number
  favoriteCount: number
  isFavorited: boolean
  favoriteLabel: string
  createdAt: string | null
  updatedAt: string | null
}

export interface ResourceCreateParams {
  title: string
  summary?: string
  content?: string
  resourceType?: ResourceType
  tags?: string
  coverUrl?: string
  fileUrl?: string
  fileType?: string
  caseId?: number | null
  status?: ResourceStatus
}

export interface ResourceUpdateParams {
  title?: string
  summary?: string
  content?: string
  resourceType?: ResourceType
  tags?: string
  coverUrl?: string
  fileUrl?: string
  fileType?: string
  caseId?: number | null
  status?: ResourceStatus
}

export interface ResourceListQuery {
  keyword?: string
  resourceType?: ResourceType | ''
  status?: ResourceStatus | ''
  onlyMine?: boolean
  page?: number
  pageSize?: number
}

export interface FavoriteParams {
  resourceId: number
  label?: string
}

export interface FavoriteListQuery {
  keyword?: string
  resourceType?: ResourceType | ''
  label?: string
  page?: number
  pageSize?: number
}

export interface LearningNote {
  id: number
  userId: number
  userName: string
  title: string
  content: string
  tags: string
  caseId: number | null
  caseNo: string
  caseTitle: string
  imageIndex: number
  imageUrl: string
  resourceId: number | null
  resourceTitle: string
  createdAt: string | null
  updatedAt: string | null
}

export interface NoteCreateParams {
  title?: string
  content?: string
  tags?: string
  caseId?: number | null
  imageIndex?: number
  imageUrl?: string
  resourceId?: number | null
}

export interface NoteUpdateParams {
  title?: string
  content?: string
  tags?: string
  caseId?: number | null
  imageIndex?: number
  imageUrl?: string
  resourceId?: number | null
}

export interface NoteListQuery {
  keyword?: string
  caseId?: number
  resourceId?: number
  userId?: number
  page?: number
  pageSize?: number
}

/* ========== 选项常量 ========== */

export const RESOURCE_TYPE_OPTIONS: { label: string; value: ResourceType }[] = [
  { label: '病例范本', value: 'CASE_TEMPLATE' },
  { label: '实训课件', value: 'COURSEWARE' },
  { label: '知识点文档', value: 'KNOWLEDGE' },
  { label: '教学影像', value: 'IMAGE_DEMO' }
]

export const RESOURCE_STATUS_OPTIONS: { label: string; value: ResourceStatus }[] = [
  { label: '草稿', value: 'DRAFT' },
  { label: '已发布', value: 'PUBLISHED' },
  { label: '已下线', value: 'ARCHIVED' }
]

export const FILE_TYPE_OPTIONS: { label: string; value: string }[] = [
  { label: 'PDF 文档', value: 'pdf' },
  { label: '视频', value: 'video' },
  { label: '图片', value: 'image' },
  { label: 'Markdown 富文本', value: 'markdown' },
  { label: '其他外链', value: 'link' }
]

/* ========== 工具 ========== */

const cleanQuery = (q: Record<string, any>): Record<string, any> => {
  const out: Record<string, any> = {}
  Object.entries(q).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    out[k] = v
  })
  return out
}

/* ========== 资料 API ========== */

export const listResources = (q: ResourceListQuery = {}) =>
  http.get<PageResult<LearningResource>>('/learning/resources', {
    page: 1,
    pageSize: 20,
    ...cleanQuery(q)
  })

export const getResource = (id: number) =>
  http.get<LearningResource>(`/learning/resources/${id}`)

export const createResource = (params: ResourceCreateParams) =>
  http.post<LearningResource>('/learning/resources', params, {
    showSuccess: true,
    successText: '资料已上传'
  })

export const updateResource = (id: number, params: ResourceUpdateParams) =>
  http.put<LearningResource>(`/learning/resources/${id}`, params, {
    showSuccess: true
  })

export const deleteResource = (id: number) =>
  http.delete<null>(`/learning/resources/${id}`, undefined, { showSuccess: true })

/* ========== 收藏 API ========== */

export const listFavorites = (q: FavoriteListQuery = {}) =>
  http.get<PageResult<LearningResource>>('/learning/favorites', {
    page: 1,
    pageSize: 20,
    ...cleanQuery(q)
  })

export const addFavorite = (params: FavoriteParams) =>
  http.post<LearningResource>('/learning/favorites', params, {
    showSuccess: true,
    successText: '已加入收藏'
  })

export const removeFavorite = (resourceId: number) =>
  http.delete<null>(`/learning/favorites/${resourceId}`, undefined, {
    showSuccess: true,
    successText: '已取消收藏'
  })

/* ========== 笔记 API ========== */

export const listNotes = (q: NoteListQuery = {}) =>
  http.get<PageResult<LearningNote>>('/learning/notes', {
    page: 1,
    pageSize: 20,
    ...cleanQuery(q)
  })

export const getNote = (id: number) =>
  http.get<LearningNote>(`/learning/notes/${id}`)

export const createNote = (params: NoteCreateParams) =>
  http.post<LearningNote>('/learning/notes', params, {
    showSuccess: true,
    successText: '笔记已创建'
  })

export const updateNote = (id: number, params: NoteUpdateParams) =>
  http.put<LearningNote>(`/learning/notes/${id}`, params, { showSuccess: true })

export const deleteNote = (id: number) =>
  http.delete<null>(`/learning/notes/${id}`, undefined, { showSuccess: true })
