/**
 * 学员自主练习 API
 * 对接后端 /api/v1/practice/*
 */
import http, { type PageResult } from '@/utils/request'
import type { ReadingApi } from '.'

/* ========== 类型 ========== */

export type PracticeStatus = 'DRAFT' | 'SUBMITTED' | 'REVIEWED'
export type PracticeMode = 'RANDOM' | 'SELECTED'
export type ErrorPointType = 'missed' | 'false_positive' | 'low_iou' | 'wrong_label'

export type PracticeAnnotation = ReadingApi.AnnotationItem
export type Point2D = ReadingApi.Point2D

export interface ErrorPoint {
  type: ErrorPointType
  label: string
  expectedLabel?: string | null
  iou?: number | null
  point?: Point2D | null
  note: string
}

export interface CaseBriefForPractice {
  caseId: number
  caseNo: string
  title: string
  category: string
  categoryText: string
  difficulty: string
  difficultyText: string
  /** 盲训态下为 null：作答前不下发正确分级 */
  drLevel: number | null
  drGradeText: string
  images: string[]
  imageCount: number
  passScore: number
}

export interface GoldStandardData {
  caseId: number
  caseNo: string
  drGrade: string
  drGradeText: string
  diagnosis: string
  teachingPoints: string
  annotations: PracticeAnnotation[]
  lesions: any[]
  /** 彩色病灶图。空字符串表示这例没有金标准图像 */
  lesionMaskUrl?: string
  passScore: number
}

export interface PracticeRecord {
  id: number
  userId: number
  userName: string
  caseId: number
  caseNo: string
  caseTitle: string
  caseCategory: string
  caseDifficulty: string
  caseDrGradeText: string
  images: string[]
  mode: PracticeMode
  status: PracticeStatus

  studentDrGrade: string
  studentDiagnosis: string
  /** 结构化作答，报告页据此逐条对照 */
  studentDiagnosisForm?: Record<string, any>
  /** 这份成绩按哪套口径判的：keyword 旧自由文本 / structured 结构化 */
  scoringMode?: 'keyword' | 'structured'
  /**
   * 标注分算法版本，不同版本的总分不能直接比较：
   * 1 没有金标准框时标注分最高 70（总分封顶 85）；
   * 2 没有框时把「没标」记成 100；
   * 3 没有框且没标则标注未考。
   * 4 文字题占 20%，分级 25%、标注 40%、诊断 15%。
   * 5 病例学习：分级 40%、诊断 40%、文字题 20%。标注不计入总分。
   */
  scoreRuleVersion?: number
  studentAnnotations: PracticeAnnotation[]
  studentMeasurements: PracticeAnnotation[]
  viewport: Record<string, any> | null

  scoreTotal: number
  scoreGrade: number
  scoreAnnotation: number
  /** 假：没有金标准框且学员没画。界面应显示「未考」 */
  annotationApplicable?: boolean
  scoreDiagnosis: number
  /** 文字题得分。规则版本 4 起计入总分 */
  scoreText?: number
  /** 作答中的题面，不含答案 */
  textQuestions?: TextQuizQuestion[]
  /** 交卷后的逐题对错和讲解 */
  textItems?: TextQuizItemResult[]
  /** PRACTICE 平时练习 / EXAM 正式考试 */
  attemptKind?: 'PRACTICE' | 'EXAM'
  examIndex?: number
  examTotal?: number
  /** 正式考试要整卷交齐才为真 */
  answersOpen?: boolean
  /** 平时练习已经打开的提示，一次一则 */
  hints?: string[]
  hintsLeft?: number
  nextSessionId?: number
  nextCaseId?: number
  /** 老师发布的正式考试。0 表示旧的自行开考 */
  examPaperId?: number
  examTitle?: string
  allowBack?: boolean
  /** -1 不限时 */
  examSecondsLeft?: number
  paperClosed?: boolean
  examPassScore?: number
  prevSessionId?: number
  prevCaseId?: number
  examItems?: { index: number; sessionId: number; caseId: number; status: string }[]
  iouAvg: number
  accuracy: number
  gradeMatch: boolean
  isPassed: boolean
  missedCount: number
  falsePositiveCount: number
  errorPoints: ErrorPoint[]
  suggestion: string

  startedAt: string | null
  submittedAt: string | null
  durationSeconds: number

  teacherComment: string
  teacherId: number | null
  teacherName: string
  teacherRole: string
  createdAt: string | null
  updatedAt: string | null
}

export interface PracticeRandomQuery {
  category?: string
  difficulty?: string
  drLevel?: number
  excludeDone?: boolean
}

export interface PracticeStartParams {
  caseId: number
  mode: PracticeMode
}

export interface PracticeSubmitParams {
  sessionId: number
  studentDrGrade: string
  studentDiagnosis: string
  annotations: PracticeAnnotation[]
  measurements: PracticeAnnotation[]
  viewport?: Record<string, any> | null
  durationSeconds: number
  /** 结构化诊断作答；提供时按结构化口径评分 */
  diagnosis?: Record<string, any>
  /** 文字题作答，和阅片一起交，计入总分 */
  textAnswers?: { id: string; value: string }[]
  /** 提交幂等键：断网重试时原样带回，服务端同键回放原成绩而非报错 */
  requestId?: string
}

export interface PracticeListQuery {
  userId?: number
  caseId?: number
  status?: PracticeStatus | ''
  isPassed?: boolean
  startTime?: string
  endTime?: string
  page?: number
  pageSize?: number
}

export interface WeakLabelItem {
  label: string
  missed: number
  falsePositive: number
  avgIou: number
}

export interface PracticeStats {
  totalSessions: number
  submittedSessions: number
  completedCases: number
  passRate: number
  avgScore: number
  avgIou: number
  totalDuration: number
  weakLabels: WeakLabelItem[]
  byDifficulty: { label: string; value: number }[]
}

/* ========== 选项常量 ========== */

export const DR_GRADE_OPTIONS: { label: string; value: string }[] = [
  { label: '0 级 无 DR', value: '0' },
  { label: '1 级 轻度 NPDR', value: '1' },
  { label: '2 级 中度 NPDR', value: '2' },
  { label: '3 级 重度 NPDR', value: '3' },
  { label: '4 级 PDR（增殖性）', value: '4' }
]

export const CATEGORY_FILTERS: { label: string; value: string }[] = [
  { label: '糖尿病视网膜病变', value: 'DR' },
  { label: '老年性黄斑变性', value: 'AMD' },
  { label: '青光眼', value: 'GLAUCOMA' },
  { label: '高血压性视网膜病变', value: 'HYPERTENSION' },
  { label: '正常眼底', value: 'NORMAL' }
]

export const DIFFICULTY_FILTERS: { label: string; value: string }[] = [
  { label: '入门', value: 'EASY' },
  { label: '中级', value: 'MEDIUM' },
  { label: '高级', value: 'HARD' }
]

/* ========== API ========== */

const cleanQuery = (q: Record<string, any>) => {
  const out: Record<string, any> = {}
  Object.entries(q).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    out[k] = v
  })
  return out
}

/** 随机抽取一份病例 */
export const getRandomCase = (q: PracticeRandomQuery = {}) =>
  http.get<CaseBriefForPractice>('/practice/random', cleanQuery(q))

/** 指定病例摘要 */
export const getCaseBrief = (caseId: number) =>
  http.get<CaseBriefForPractice>(`/practice/cases/${caseId}`)

/** 病例金标准（学员需先提交才能查看） */
export const getGoldStandard = (caseId: number) =>
  http.get<GoldStandardData>(`/practice/cases/${caseId}/gold`)

/** 开始练习 */
export const startPractice = (params: PracticeStartParams) =>
  http.post<PracticeRecord>('/practice/start', params)

/** 开始或继续正式考试。进行中的一场会接着做，不会另开。 */
export const startExam = () => http.post<PracticeRecord>('/practice/exam/start')

/** 平时练习打开下一则提示。正式考试会拒绝。 */
export const nextHint = (recordId: number) =>
  http.post<PracticeRecord>(`/practice/${recordId}/hint`)

/** 提交练习（自动评分）。页面自己决定提示文案。 */
export const submitPractice = (params: PracticeSubmitParams) =>
  http.post<PracticeRecord>('/practice/submit', params, { showSuccess: false })

/** 练习台账分页 */
export const getPracticeList = (q: PracticeListQuery = {}) =>
  http.get<PageResult<PracticeRecord>>('/practice/list', {
    page: 1,
    pageSize: 20,
    ...cleanQuery(q)
  })

/** 练习记录详情 */
export const getPracticeDetail = (recordId: number) =>
  http.get<PracticeRecord>(`/practice/${recordId}`)

/** 教师点评 */
export const reviewPractice = (recordId: number, teacherComment: string) =>
  http.post<PracticeRecord>(
    `/practice/${recordId}/review`,
    { teacherComment },
    { showSuccess: true }
  )

/** 删除练习记录 */
export const deletePractice = (recordId: number) =>
  http.delete<null>(`/practice/${recordId}`, undefined, { showSuccess: true })

/** 个人统计 */
export const getMyStats = () => http.get<PracticeStats>('/practice/stats/me')

/** 指定学员统计（教师/管理员） */
export const getUserStats = (userId: number) =>
  http.get<PracticeStats>(`/practice/stats/user/${userId}`)

/** 全班级统计（教师/管理员） */
export const getAllStats = () => http.get<PracticeStats>('/practice/stats/all')

export type TextQuizKind = 'knowledge' | 'choice' | 'blank'

export interface TextQuizQuestion {
  id: string
  kind: TextQuizKind
  kindText: string
  stem: string
  options: string[]
}

export interface TextQuizItemResult {
  id: string
  kind: TextQuizKind
  kindText: string
  stem: string
  yours: string
  expected: string
  correct: boolean
  explanation: string
}

export interface TextQuizResult {
  score: number
  correctCount: number
  questionCount: number
  passed: boolean
  items: TextQuizItemResult[]
}

/** 抽一组文字题：知识点、选择、填空。题面不含答案。 */
export const getTextQuiz = (size = 4) =>
  http.get<{ questions: TextQuizQuestion[] }>('/practice/text-quiz', { size })

/** 交一组文字题，返回对错和讲解 */
export const submitTextQuiz = (answers: { id: string; value: string }[]) =>
  http.post<TextQuizResult>('/practice/text-quiz', { answers })
