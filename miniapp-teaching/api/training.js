/**
 * 医学培训 / 阅片标注 API
 * 对接后端 /api/v1/training/*（响应已 camelCase）
 */
import { get, post, put } from './request'

/** 病灶分类（与后端 LesionLiteral 一致） */
export const LESION_OPTIONS = [
  { label: '出血', value: '出血', color: '#dc2626' },
  { label: '渗出', value: '渗出', color: '#d97706' },
  { label: '微动脉瘤', value: '微动脉瘤', color: '#2563eb' },
  { label: '棉绒斑', value: '棉绒斑', color: '#7c3aed' },
  { label: '新生血管', value: '新生血管', color: '#db2777' },
]

export const DIFFICULTY_OPTIONS = ['入门', '初级', '中级', '高级']

export const DR_LEVEL_TEXT = {
  0: '0 级 无 DR',
  1: '1 级 轻度',
  2: '2 级 中度',
  3: '3 级 重度',
  4: '4 级 PDR',
}

export const GRADE_COLOR = {
  'A+': '#16a34a',
  A: '#16a34a',
  B: '#d97706',
  C: '#dc2626',
}

/** 病例分页列表 query: { keyword, drLevel, difficulty, done, page, pageSize } */
export function getCaseList(query = {}) {
  return get('/training/cases', query)
}

/** 病例详情 */
export function getCaseDetail(caseId) {
  return get(`/training/cases/${caseId}`)
}

/** AI 热力图 */
export function getHeatmap(caseId) {
  return get(`/training/cases/${caseId}/heatmap`)
}

/** 金标准标注 */
export function getGoldStandard(caseId) {
  return get(`/training/cases/${caseId}/gold`)
}

/** 历史 IoU 评分 */
export function getIouHistory(caseId) {
  return get(`/training/cases/${caseId}/iou-history`)
}

/** 提交标注 → 计算 IoU 评分入库 */
export function submitAnnotation(params) {
  return post('/training/annotations/submit', params, { showError: true })
}

/** 试算 IoU（不入库） */
export function calculateIoU(params) {
  return post('/training/iou/calculate', params, { showError: true })
}

/** 标记病例完成 */
export function markCaseDone(caseId) {
  return put(`/training/cases/${caseId}/done`, null, { showError: false })
}

/** 个人培训统计 */
export function getTrainingStats() {
  return get('/training/stats')
}
