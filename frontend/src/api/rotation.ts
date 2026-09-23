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
  tier: 'REQUIRED' | 'EXTENSION' | string
  scope: 'ALL' | 'YEAR' | 'GROUP' | string
  scopeValue: string
  scopeText: string
}

export interface StudentTaskSnap {
  taskId: number
  status: string
  statusText: string
  score: number | null
}

export interface StudentProgress {
  userId: number
  name: string
  username: string
  studyYear: string
  rotationBatch: string
  mentorGroup: string
  done: number
  total: number
  progress: number
  practiceCount: number
  completedCases: number
  avgScore: number
  studySeconds: number
  tasks: StudentTaskSnap[]
}

export interface WeakLabelBrief {
  label: string
  missed: number
  falsePositive: number
}

export interface GroupSummary {
  studyYear: string
  rotationBatch: string
  mentorGroup: string
  studentCount: number
  done: number
  total: number
  progress: number
  weakLabels: WeakLabelBrief[]
}

export interface StudentHome {
  role: 'student'
  rotation: RotationBrief | null
  today: RotationTask[]
  tasks: RotationTask[]
  studyYear: string
  rotationBatch: string
  mentorGroup: string
}

export interface TeacherHome {
  role: 'teacher'
  rotation: RotationBrief | null
  tasks: RotationTask[]
  students: StudentProgress[]
  groups: GroupSummary[]
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
  tier?: 'REQUIRED' | 'EXTENSION'
  scope?: 'ALL' | 'YEAR' | 'GROUP'
  scopeValue?: string
}) => http.post<TeacherHome>('/rotation/tasks', body)

export const removeTask = (taskId: number) =>
  http.delete<TeacherHome>(`/rotation/tasks/${taskId}`)

export const reorderTasks = (taskIds: number[]) =>
  http.put<TeacherHome>('/rotation/tasks/order', { taskIds })

export const arrangeTasks = () => http.post<TeacherHome>('/rotation/tasks/arrange')

export const markLearned = (taskId: number) =>
  http.post<StudentHome>(`/rotation/tasks/${taskId}/learn`)

export const setStudentGroup = (
  userId: number,
  body: { studyYear?: string; rotationBatch?: string; mentorGroup?: string }
) => http.put<TeacherHome>(`/rotation/students/${userId}/group`, body)
