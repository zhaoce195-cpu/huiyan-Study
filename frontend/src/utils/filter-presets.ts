/**
 * DynamicFilter 共享筛选条 · 字段 schema 预设
 *
 * 三个查询页（screening 队列 / screening 归档 / case-browse）的字段定义集中在此，
 * 修改字段只改这一份 schema；DynamicFilter.vue 按 schema 自动渲染。
 */

export type FieldType = 'text' | 'select' | 'daterange' | 'datetimerange' | 'switch'

export interface FilterFieldSchema {
  /** 绑到 modelValue 的字段名（daterange 用 startKey/endKey 分别绑） */
  key: string
  type: FieldType
  /** 占位 / switch 显示文字 */
  label?: string
  /** 控件宽度，CSS 值（不传按 type 默认） */
  width?: string
  options?: { label: string; value: string | number | boolean }[]
  multiple?: boolean
  prefixIcon?: 'Search' | 'Calendar' | 'Iphone' | 'Document' | 'User'
  /** daterange 专用：把数组 [start,end] 拆到 modelValue 的两个键 */
  startKey?: string
  endKey?: string
  /**
   * 何时禁用本字段：拿到当前整份筛选值，返回 true 则禁用。
   * DynamicFilter 会在禁用时顺手清空该字段，避免留下一个看不见却仍在生效的条件。
   */
  disabledWhen?: (values: Record<string, any>) => boolean
  /** 禁用时鼠标悬停给出的解释 */
  disabledHint?: string
}

/**
 * DR 分级只对糖网和正常眼底有意义。
 *
 * AMD / 青光眼 / 高血压视网膜这些非 DR 病种，库里 gold_dr_grade 存的是空串
 * 「不适用」（见后端 common/dr_grade.py：「不适用」与「0 级无 DR」是两个不同结论）。
 * 所以「病种 = 黄斑变性 + DR 等级 = 任意值」这个组合永远筛不出东西 ——
 * 用户测试报告 D-3：「选了黄斑还是可以选择 DR 严重等级，逻辑不对」。
 */
export const DR_GRADED_CATEGORIES = ['DR', 'NORMAL']

export const isDrGradeNotApplicable = (category: unknown): boolean => {
  const c = String(category ?? '').trim().toUpperCase()
  return c !== '' && !DR_GRADED_CATEGORIES.includes(c)
}

export interface FilterSchema {
  fields: FilterFieldSchema[]
  /** 是否在末尾自动渲染「查询 / 重置 / 刷新」按钮组（默认 true） */
  showActions?: boolean
}

/* ============================================================
 * 1. 体检筛查 · 分析队列（views/screening/index.vue）
 * ============================================================ */
export const SCREENING_QUEUE_FILTER: FilterSchema = {
  fields: [
    {
      key: 'keyword',
      type: 'text',
      label: '搜索患者ID / 姓名 / 文件名',
      prefixIcon: 'Search',
      width: '260px',
    },
    {
      key: 'risk',
      type: 'select',
      label: '风险等级',
      width: '130px',
      options: [
        { label: '高风险（红）', value: 'red' },
        { label: '中风险（黄）', value: 'yellow' },
        { label: '低风险（绿）', value: 'green' },
      ],
    },
    {
      key: 'status',
      type: 'select',
      label: '任务状态',
      width: '130px',
      options: [
        { label: '排队中', value: 'queued' },
        { label: '处理中', value: 'analyzing' },
        { label: '已完成', value: 'done' },
        { label: '失败', value: 'failed' },
      ],
    },
    {
      key: 'diagnosisType',
      type: 'select',
      label: '诊断类型',
      width: '140px',
      options: [
        { label: 'MA 检测', value: 'MA' },
        { label: 'DR 分级', value: 'DR' },
        { label: '综合诊断', value: 'COMPREHENSIVE' },
      ],
    },
  ],
}

/* ============================================================
 * 2. 体检筛查 · 归档检索（views/screening/case-search.vue）
 * ============================================================ */
export const SCREENING_ARCHIVE_FILTER: FilterSchema = {
  fields: [
    {
      key: 'caseNo',
      type: 'text',
      label: '病例编号',
      prefixIcon: 'Document',
      width: '180px',
    },
    {
      key: 'patientName',
      type: 'text',
      label: '患者姓名',
      prefixIcon: 'User',
      width: '160px',
    },
    {
      key: 'phone',
      type: 'text',
      label: '手机号',
      prefixIcon: 'Iphone',
      width: '160px',
    },
    {
      key: 'risk',
      type: 'select',
      label: '风险等级',
      width: '130px',
      options: [
        { label: '高风险', value: 'red' },
        { label: '中风险', value: 'yellow' },
        { label: '低风险', value: 'green' },
      ],
    },
    {
      key: 'status',
      type: 'select',
      label: '状态',
      width: '120px',
      options: [
        { label: '已完成', value: 'done' },
        { label: '失败', value: 'failed' },
      ],
    },
    {
      key: 'diagnosisType',
      type: 'select',
      label: '诊断类型',
      width: '130px',
      options: [
        { label: 'MA', value: 'MA' },
        { label: 'DR', value: 'DR' },
        { label: '综合', value: 'COMPREHENSIVE' },
      ],
    },
    {
      key: 'range',
      type: 'datetimerange',
      label: '上传时间',
      startKey: 'startTime',
      endKey: 'endTime',
      prefixIcon: 'Calendar',
    },
  ],
}

/* ============================================================
 * 3. 培训端 · 病例浏览检索（views/case-browse/index.vue）
 * ============================================================ */
export const CASE_BROWSE_FILTER: FilterSchema = {
  fields: [
    {
      key: 'keyword',
      type: 'text',
      label: '来源编号 / 平台病例号 / 患者姓名 / 标题',
      prefixIcon: 'Search',
      width: '280px',
    },
    {
      key: 'category',
      type: 'select',
      label: '病种分类',
      width: '140px',
      options: [
        { label: 'DR 糖尿病', value: 'DR' },
        { label: 'AMD 黄斑变性', value: 'AMD' },
        { label: '青光眼', value: 'GLAUCOMA' },
        { label: '高血压视网膜', value: 'HYPERTENSION' },
        { label: '正常眼底', value: 'NORMAL' },
        { label: '其他', value: 'OTHER' },
      ],
    },
    {
      key: 'drLevel',
      type: 'select',
      label: 'DR 严重等级',
      width: '140px',
      options: [
        { label: '0 级', value: '0' },
        { label: '1 级', value: '1' },
        { label: '2 级', value: '2' },
        { label: '3 级', value: '3' },
        { label: '4 级', value: '4' },
      ],
      disabledWhen: (v) => isDrGradeNotApplicable(v.category),
      disabledHint: '所选病种不做 DR 分级（DR 分级仅适用于糖网与正常眼底）',
    },
    {
      key: 'difficulty',
      type: 'select',
      label: '难度',
      width: '120px',
      options: [
        { label: 'EASY', value: 'EASY' },
        { label: 'MEDIUM', value: 'MEDIUM' },
        { label: 'HARD', value: 'HARD' },
      ],
    },
    {
      key: 'creatorRole',
      type: 'select',
      label: '创建人角色',
      width: '130px',
      options: [
        { label: '管理员', value: 'ADMIN' },
        { label: '医师', value: 'TEACHER' },
        { label: '学员', value: 'STUDENT' },
      ],
    },
    {
      key: 'range',
      type: 'daterange',
      label: '上传时间',
      startKey: 'startTime',
      endKey: 'endTime',
      prefixIcon: 'Calendar',
    },
    {
      key: 'onlyIncomplete',
      type: 'switch',
      label: '仅看没有眼底照',
    },
  ],
}
