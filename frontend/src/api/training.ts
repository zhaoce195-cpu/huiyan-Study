import http, { type PageResult } from '@/utils/request'

/* ========== 公共枚举 ========== */

export type DRLevel = 0 | 1 | 2 | 3 | 4
export type Difficulty = '入门' | '初级' | '中级' | '高级'
export type LesionType = '出血' | '渗出' | '微动脉瘤' | '棉绒斑' | '新生血管'
export type AnnotationType = 'rect' | 'polygon' | 'pen'
export type EyeSide = 'OD' | 'OS'

/* ========== 类型定义 ========== */

export interface Lesion {
  type: LesionType
  count: number
  /** 病灶位置描述（黄斑/视盘/上方/下方等） */
  location?: string
}

export interface TrainingCase {
  /** 病例编号 CASE001 */
  id: string
  /** 患者姓名（脱敏） */
  name: string
  age: number
  gender: '男' | '女'
  eye: EyeSide
  /** DR 分级文本：4 级 PDR */
  drGrade: string
  /** DR 分级数值：0~4 */
  drLevel: DRLevel
  /** 难度等级 */
  difficulty: Difficulty
  /** 是否已完成训练 */
  done: boolean
  /** 缩略图 URL */
  thumbUrl?: string
  /** 原图 URL */
  imageUrl?: string
  /** 糖尿病病程（年） */
  diabetesYears: number
  /** 来源机构 */
  hospital: string
  /** 历史最佳 IoU */
  bestIou: number | null
  /** 金标准病灶清单 */
  lesions: Lesion[]
  /** 创建时间 */
  createdAt?: string
}

export interface CaseQuery {
  keyword?: string
  /** DR 分级数值（'' 表示全部） */
  drLevel?: DRLevel | ''
  /** 难度 */
  difficulty?: Difficulty | ''
  /** 是否已完成 */
  done?: boolean
  page?: number
  pageSize?: number
}

export interface AnnotationPoint {
  x: number
  y: number
}

export interface Annotation {
  /** 客户端临时 ID（提交后由后端生成 serverId） */
  id: string
  serverId?: string
  /** 标注类型 */
  type: AnnotationType
  /** 像素坐标点（rect 用 2 个点，polygon/pen 任意） */
  points: AnnotationPoint[]
  /** 病灶分类 */
  label: LesionType
  /** 颜色（前端展示用） */
  color?: string
  /** 备注 */
  remark?: string
}

export interface SubmitAnnotationParams {
  caseId: string
  /** 画布尺寸（用于反归一化） */
  canvasWidth: number
  canvasHeight: number
  /** 标注列表 */
  annotations: Annotation[]
  /** 用时（秒） */
  durationSec?: number
}

export interface IoUDetail {
  /** 病灶分类 */
  label: LesionType
  /** 该类 IoU */
  iou: number
  /** 召回数 */
  recall: number
  /** 漏标数 */
  missed: number
  /** 误标数 */
  falsePositive: number
}

export interface IoUResult {
  caseId: string
  /** 总 IoU 评分 0~1 */
  iou: number
  /** 各类病灶分项评分 */
  details: IoUDetail[]
  /** 等级评价：A+ / A / B / C */
  grade: 'A+' | 'A' | 'B' | 'C'
  /** 教师点评 */
  comment: string
  /** 提交时间 */
  submittedAt: string
}

export interface HeatmapResult {
  caseId: string
  /** 热力图 URL（PNG，与原图同尺寸） */
  heatmapUrl: string
  /** 热点信息 */
  hotspots: {
    x: number
    y: number
    radius: number
    score: number
    label?: LesionType
  }[]
}

export interface GoldStandardResult {
  caseId: string
  /** 金标准标注列表 */
  annotations: Annotation[]
}

export interface TrainingStats {
  totalCases: number
  doneCases: number
  avgIoU: number
  bestIoU: number
  totalAnnotations: number
  totalDuration: number
}

/* ========== API 方法 ========== */

/** 获取病例分页列表 */
export const getCaseList = (query: CaseQuery = {}) =>
  http.get<PageResult<TrainingCase>>('/training/cases', query)

/** 获取病例详情 */
export const getCaseDetail = (caseId: string) =>
  http.get<TrainingCase>(`/training/cases/${caseId}`)

/** 提交标注（计算 IoU） */
export const submitAnnotation = (params: SubmitAnnotationParams) =>
  http.post<IoUResult>('/training/annotations/submit', params, {
    showError: true
  })

/** 获取 AI 热力图 */
export const getHeatmap = (caseId: string) =>
  http.get<HeatmapResult>(`/training/cases/${caseId}/heatmap`)

/** 获取金标准标注 */
export const getGoldStandard = (caseId: string) =>
  http.get<GoldStandardResult>(`/training/cases/${caseId}/gold`)

/** 获取历史 IoU 评分 */
export const getIouHistory = (caseId: string) =>
  http.get<IoUResult[]>(`/training/cases/${caseId}/iou-history`)

/** 计算 IoU（不入库，仅试算） */
export const calculateIoU = (params: SubmitAnnotationParams) =>
  http.post<IoUResult>('/training/iou/calculate', params)

/** 获取个人培训统计 */
export const getTrainingStats = () => http.get<TrainingStats>('/training/stats')

/** 标记病例完成 */
export const markCaseDone = (caseId: string) =>
  http.put<void>(`/training/cases/${caseId}/done`, null, {
    showSuccess: true,
    successText: '已标记为完成'
  })
