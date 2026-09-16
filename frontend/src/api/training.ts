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

/* ========== AI 辅助诊断（真实算法服务 CSU-EYES） ========== */

export interface AiEyeResult {
  /** 分级/分类编号（DR 0~4；青光眼 0/1） */
  grade: number
  /** 分级中文描述 */
  gradeText: string
  /** 展示用文本（病种无关，如 DR 2 级 / 青光眼疑似） */
  label?: string
  /** 送检原图 URL */
  imageUrl: string
  /** GradCAM 热力图 URL */
  heatmapUrl: string
}

export interface AiDiagnosisResult {
  caseId: string
  /** 诊断病种：DR / GLAUCOMA / MA ... */
  category?: string
  /** 各类别概率（分类任务，如青光眼：青光眼疑似 / 正常） */
  probs?: { label: string; value: number }[]
  /** 分级/分类编号（DR 0~4；青光眼 0/1） */
  overallGrade: number
  overallGradeText: string
  /** 综合结论展示文本（病种无关，前端优先用它） */
  overallLabel?: string
  /** 左眼 OS */
  left: AiEyeResult
  /** 右眼 OD */
  right: AiEyeResult
  /** 单图病例（左右眼同一张图） */
  singleEye: boolean
  /**
   * 该画哪几张眼别卡：left=左眼OS / right=右眼OD / ou=双眼单图。
   * 老接口没有这个字段时回退成双眼，保持向后兼容。
   */
  eyeCards?: Array<'left' | 'right' | 'ou'>
  /** 金标准 DR 分级（青光眼为空） */
  goldGrade: number | null
  /** 金标准展示文本（病种无关） */
  goldLabel?: string
  /** AI 是否与金标准一致 */
  agreeWithGold: boolean | null
  modelName: string
  inferDurationMs: number
  /** 是否命中缓存 */
  cached: boolean
  inferredAt: string
}

export interface AiCaseDraft {
  caseId: string
  title: string
  isPublished: boolean
  ai: AiDiagnosisResult
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


/** 获取 AI 辅助诊断缓存结果（不触发推理，无结果返回 null） */
export const getAiDiagnosis = (caseId: string | number) =>
  http.get<AiDiagnosisResult | null>(`/training/cases/${caseId}/ai-diagnosis`)

/** 执行 AI 辅助诊断（调用 CSU-EYES 算法服务，约 5~30s） */
export const runAiDiagnosis = (caseId: string | number, force = false) =>
  http.post<AiDiagnosisResult>(
    `/training/cases/${caseId}/ai-diagnosis?force=${force}`,
    null,
    { showError: true },
    { timeout: 180_000 }
  )

/** AI 智能建案（教师/管理员）：上传左右眼底图，生成实训病例草稿 */
export const createAiCase = (
  leftEye: File,
  rightEye: File,
  opts: { title?: string; difficulty?: 'EASY' | 'MEDIUM' | 'HARD' } = {}
) => {
  const fd = new FormData()
  fd.append('left_eye', leftEye)
  fd.append('right_eye', rightEye)
  if (opts.title) fd.append('title', opts.title)
  if (opts.difficulty) fd.append('difficulty', opts.difficulty)
  return http.upload<AiCaseDraft>(
    '/training/ai-cases',
    fd,
    { showError: true },
    { timeout: 180_000 }
  )
}

/** 标记病例完成 */
export const markCaseDone = (caseId: string) =>
  http.put<void>(`/training/cases/${caseId}/done`, null, {
    showSuccess: true,
    successText: '已标记为完成'
  })
