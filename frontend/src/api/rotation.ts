import http from '@/utils/request'

export interface RotationBrief {
  id: number
  title: string
  startOn: string
  dueOn: string
  passScore: number
  total: number
  done: number
  progress: number
}

export interface RotationTask {
  id: number
  kind: 'CASE' | 'KNOWLEDGE' | string
  kindText: string
  title: string
  summary: string
  dueOn: string
  passScore: number
  status: string
  statusText: string
  score: number | null
  overdue: boolean
  dueToday: boolean
  caseId: number | null
  caseNo: string
  resourceId: number | null
  doneCount: number
  studentCount: number
}

export interface StudentProgress {
  userId: number
  name: string
  done: number
  total: number
  progress: number
}

export interface StudentHome {
  role: 'student'
  rotation: RotationBrief | null
  today: RotationTask[]
  tasks: RotationTask[]
}

export interface TeacherHome {
  role: 'teacher'
  rotation: RotationBrief | null
  tasks: RotationTask[]
  students: StudentProgress[]
}

export type HomePayload = StudentHome | TeacherHome

export interface OptionItem {
  id: number
  label: string
}

export const getHome = () => http.get<HomePayload>('/rotation/home')

export const getOptions = () =>
  http.get<{ cases: OptionItem[]; resources: OptionItem[] }>('/rotation/options')

export const updateRotation = (body: { title?: string; dueOn?: string; passScore?: number }) =>
  http.put<TeacherHome>('/rotation/current', body)

export const addTask = (body: {
  kind: 'CASE' | 'KNOWLEDGE'
  caseId?: number
  resourceId?: number
  title?: string
  summary?: string
  passScore?: number
  dueOn?: string
}) => http.post<TeacherHome>('/rotation/tasks', body)

export const removeTask = (taskId: number) =>
  http.delete<TeacherHome>(`/rotation/tasks/${taskId}`)

export const markLearned = (taskId: number) =>
  http.post<StudentHome>(`/rotation/tasks/${taskId}/learn`)
