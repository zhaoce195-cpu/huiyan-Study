/**
 * 学习资料 / 收藏 / 笔记 API
 * 对接后端 /api/v1/learning/*（响应已 camelCase）
 */
import { get, post, put, del } from './request'

export const RESOURCE_TYPE_TEXT = {
  CASE_TEMPLATE: '病例范本',
  COURSEWARE: '实训课件',
  KNOWLEDGE: '知识点',
  IMAGE_DEMO: '教学影像',
}

export const RESOURCE_TYPE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '病例范本', value: 'CASE_TEMPLATE' },
  { label: '课件', value: 'COURSEWARE' },
  { label: '知识点', value: 'KNOWLEDGE' },
  { label: '影像', value: 'IMAGE_DEMO' },
]

function clean(q) {
  const out = {}
  Object.entries(q || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') out[k] = v
  })
  return out
}

/* ===== 资料 ===== */
export function listResources(q = {}) {
  return get('/learning/resources', { page: 1, pageSize: 20, ...clean(q) })
}
export function getResource(id) {
  return get(`/learning/resources/${id}`)
}

/* ===== 收藏 ===== */
export function listFavorites(q = {}) {
  return get('/learning/favorites', { page: 1, pageSize: 20, ...clean(q) })
}
export function addFavorite(resourceId, label) {
  return post('/learning/favorites', { resourceId, label }, { showError: true })
}
export function removeFavorite(resourceId) {
  return del(`/learning/favorites/${resourceId}`, undefined, { showError: true })
}

/* ===== 笔记 ===== */
export function listNotes(q = {}) {
  return get('/learning/notes', { page: 1, pageSize: 20, ...clean(q) })
}
export function createNote(params) {
  return post('/learning/notes', params, { showError: true })
}
export function updateNote(id, params) {
  return put(`/learning/notes/${id}`, params, { showError: true })
}
export function deleteNote(id) {
  return del(`/learning/notes/${id}`, undefined, { showError: true })
}
