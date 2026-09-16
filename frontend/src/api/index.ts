/**
 * API 接口统一出口
 * 使用方式（推荐 — 命名空间，可避免类型重名冲突）：
 *   import { ScreeningApi, TrainingApi, LoginApi, CommonApi } from '@/api'
 *   ScreeningApi.getScreeningList(...)
 *
 * 也可以直接从子模块按需导入：
 *   import { login } from '@/api/login'
 *   import { getScreeningList, type ScreeningTask } from '@/api/screening'
 */
export * as LoginApi from './login'
export * as ScreeningApi from './screening'
export * as TrainingApi from './training'
export * as CommonApi from './common'
export * as CaseBrowseApi from './case-browse'
export * as CaseImageApi from './case-image'
export * as ReadingApi from './reading'
export * as PracticeApi from './practice'
export * as LearningApi from './learning'
export * as PatientApi from './patient'
export * as DiagnosisApi from './diagnosis'
// ===== PATIENT 端「机构申请 / 站内消息」（纯追加） =====
export * as OrganizationApi from './organization'
export * as UserMessageApi from './user-message'
// ===== 教学实训分享（纯追加） =====
export * as TeachingApi from './teaching'
export * as AdminUsersApi from './admin-users'
export * as StudentAppApi from './student-application'
