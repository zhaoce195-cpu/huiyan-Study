/**
 * 筛查病例 / 报告 API
 * 对接后端 /api/v1/screening/*
 * 后端响应已是 camelCase（alias_generator=to_camel）
 */
import { get, post, del } from './request'

export const RISK_TEXT = { red: '高危', yellow: '中危', green: '正常' }
export const RISK_COLOR = { red: '#dc2626', yellow: '#d97706', green: '#16a34a' }
export const STATUS_TEXT = {
  queued: '排队中',
  analyzing: '分析中',
  done: '已完成',
  failed: '失败',
}

/** 病例 / 任务分页列表  query: { keyword, risk, status, scope, page, pageSize } */
export function getScreeningList(query = {}) {
  return get('/screening/tasks', query)
}

/** 单个任务详情 */
export function getScreeningTask(taskId) {
  return get(`/screening/tasks/${taskId}`)
}

/** 删除任务 */
export function deleteScreeningTask(taskId) {
  return del(`/screening/tasks/${taskId}`, undefined, { showError: true })
}

/** 风险 / 状态统计 */
export function getScreeningStats(scope) {
  return get('/screening/stats', scope ? { scope } : {})
}

/** 报告详情 */
export function getScreeningReport(taskId) {
  return get(`/screening/reports/${taskId}`)
}

/** 医生确认报告 */
export function confirmReport(params) {
  return post('/screening/reports/confirm', params, { showError: true })
}
