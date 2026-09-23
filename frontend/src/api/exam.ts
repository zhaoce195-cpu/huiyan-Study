/**
 * 正式考试。老师组卷，学员限时作答，收卷后导出成绩。
 */
import http from '@/utils/request'
import type { PracticeRecord } from './practice'

export interface ExamPaper {
  id: number
  title: string
  status: 'OPEN' | 'CLOSED' | string
  durationMinutes: number
  passScore: number
  allowBack: boolean
  pickMode: 'SELECTED' | 'DRAW' | string
  category: string
  difficulty: string
  caseIds: number[]
  questionCount: number
  caseNos: string[]
  enteredCount: number
  handedCount: number
  openedAt?: string | null
  closedAt?: string | null
  /** READY 未进入 / DOING 作答中 / HANDED 已交卷 / ABSENT 缺考 */
  mineStatus?: string
}

export interface ExamCaseOption {
  id: number
  caseNo: string
  title: string
  category: string
  categoryText: string
  difficulty: string
  difficultyText: string
}

export interface ExamCreateBody {
  title: string
  durationMinutes: number
  passScore: number
  allowBack: boolean
  pickMode: 'SELECTED' | 'DRAW'
  category?: string
  difficulty?: string
  caseIds?: number[]
  questionCount?: number
}

const answerBody = (paperId: number, payload: Record<string, unknown>) =>
  http.post<PracticeRecord>(`/exams/${paperId}/hand-in`, payload, { showSuccess: false })

export const listExams = () => http.get<ExamPaper[]>('/exams')

export const caseOptions = () => http.get<ExamCaseOption[]>('/exams/case-options')

export const createExam = (body: ExamCreateBody) => http.post<ExamPaper>('/exams', body)

export const startExam = (paperId: number) =>
  http.post<PracticeRecord>(`/exams/${paperId}/start`, {}, { showSuccess: false })

export const saveDraft = (paperId: number, payload: Record<string, unknown>) =>
  http.post<PracticeRecord>(`/exams/${paperId}/draft`, payload, { showSuccess: false })

export const handIn = answerBody

export const collectExam = (paperId: number) =>
  http.post<{ collected: number; entered: number; message: string }>(`/exams/${paperId}/collect`)

export const downloadGrades = (paperId: number, filename: string) =>
  http.download(`/exams/${paperId}/grades`, undefined, filename)

export const removeExam = (paperId: number) => http.delete(`/exams/${paperId}`)
