/**
 * DR 分级 / 风险等级 共享格式化工具
 * - drGradeColor(g)        DR 等级 → 颜色（字符串 '0'~'4'，未知返回灰）
 * - drGradeColorNum(g)     DR 等级（number） → 颜色（用于 AI 输出 0~4 数值）
 * - riskTagType(level)     风险等级标签（el-tag 的 type）
 */

export const drGradeColor = (g: string | number | null | undefined): string => {
  const s = String(g ?? '')
  if (s === '4') return '#a8071a'
  if (s === '3') return '#cf1322'
  if (s === '2') return '#fa8c16'
  if (s === '1') return '#faad14'
  if (s === '0') return '#52c41a'
  return '#86909c'
}

export const drGradeColorNum = (g: number | null | undefined): string => {
  const n = Number(g ?? -1)
  if (n >= 4) return '#f53f3f'
  if (n >= 3) return '#ff7d00'
  if (n >= 2) return '#faad14'
  if (n >= 1) return '#1677ff'
  if (n >= 0) return '#00b42a'
  return '#86909c'
}

export type RiskTagType = 'info' | 'success' | 'warning' | 'danger'
export const riskTagType = (level: string | null | undefined): RiskTagType => {
  if (level === 'URGENT' || level === 'HIGH') return 'danger'
  if (level === 'MEDIUM') return 'warning'
  if (level === 'LOW') return 'success'
  return 'info'
}
