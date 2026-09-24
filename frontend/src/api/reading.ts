/**
 * 影像阅片 API
 * 对接后端 /api/v1/reading/*
 */
import http, { type PageResult } from '@/utils/request'

/* ========== 类型 ========== */

export type ReadingTool =
  | 'rect'
  | 'polygon'
  | 'pen'
  | 'length'
  | 'angle'
  | 'freehand'
  | 'ellipse'
  | 'point'
  | 'quadrant'

export type ReadingStatus = 'DRAFT' | 'SUBMITTED' | 'REVIEWED' | 'REJECTED'

/**
 * 状态文案集中一处，且与后端 app/common/workflow.py 用同一套中文名。
 * 此前三个地方各写了一遍内联三元，新增状态时极易漏掉某一处，
 * 漏掉的那处会把未知状态显示成「草稿」——比不显示更糟。
 */
export const READING_STATUS_META: Record<
  ReadingStatus,
  { label: string; tag: 'info' | 'warning' | 'success' | 'danger' }
> = {
  DRAFT: { label: '草稿', tag: 'info' },
  SUBMITTED: { label: '待审核', tag: 'warning' },
  REVIEWED: { label: '已通过', tag: 'success' },
  REJECTED: { label: '已驳回', tag: 'danger' }
}

export interface Point2D {
  x: number
  y: number
}

export interface AnnotationItem {
  id: string
  tool: ReadingTool
  points: Point2D[]
  label: string
  color?: string
  layer: string
  remark?: string
  /** 测量值 */
  value?: number
  unit?: string
}

export interface ViewportState {
  scale: number
  x: number
  y: number
  /** 窗宽 */
  ww: number
  /** 窗位 */
  wl: number
  invert: boolean
  /**
   * 产生这份快照的渲染内核。
   *
   * legacy（缺省）：cornerstone-core v2，scale=1 表示影像 1:1 显示。
   * cs3d：Cornerstone3D，zoom=1 表示适配窗口。
   *
   * 两者的 scale 不是同一个量纲，直接拿旧快照按新语义还原会明显错位
   * （4752 px 宽的眼底照，适配窗口时旧口径的 scale 约为 0.11）。
   * 因此缺标记的旧快照只还原窗宽窗位与反相，缩放平移一律重置为适配。
   */
  engine?: 'legacy' | 'cs3d'
}

export interface LayerState {
  primary: boolean
  heatmap: boolean
  gold: boolean
  my: boolean
}

export interface ImageMeta {
  index: number
  url: string
  side?: 'OD' | 'OS' | 'OU'
  /** ============ 安全标识（报告 P0/P1） ============ */
  fileName?: string
  /** 眼别；UNKNOWN 表示原始数据未采集，前端须显式提示未知 */
  eye?: 'OD' | 'OS' | 'OU' | 'UNKNOWN'
  eyeText?: string
  /** 服务端按视盘位置补的眼别，没有写回数据库 */
  eyeInferred?: boolean
  /** 影像角色：original 为原始影像，其余为派生对象 */
  role?: string
  roleText?: string
  isOriginal?: boolean
  quality?: 'good' | 'usable' | 'poor' | 'ungradable' | 'unknown'
  qualityText?: string
  qualityConfidence?: number
  /** 质量为 poor/ungradable：不得据此给出默认阴性结论 */
  ungradable?: boolean
  /** 元数据眼别与文件名线索冲突时的提示；不为空即须醒目告警 */
  lateralityConflict?: string | null
  /** 原图独立编号，派生对象为 null，避免「N 张影像」混算 */
  originalIndex?: number | null
  originalTotal?: number
}

/** 病例级安全汇总 */
export interface SafetySummary {
  originalCount?: number
  derivedCount?: number
  /** 不可判读的原图张数 */
  ungradableCount?: number
  /** 尚未评估质量的原图张数 */
  unevaluatedCount?: number
  hasUngradable?: boolean
  /** 原图是否已全部完成质量评估；为 false 时不得声称已质控 */
  qualityChecked?: boolean
  /** 学员质量评估的审核状态：SUBMITTED 待教师审核，REVIEWED 才是通过 */
  qualityReviewStatus?: string
  qualityReviewText?: string
  /** 全库已成功评出等级的原图张数（跨病例累计，按影像去重） */
  gradedTotal?: number
  eyes?: string[]
  eyesText?: string
  hasLateralityConflict?: boolean
  lateralityConflicts?: string[]
}

export interface ImageSource {
  caseId: number
  caseNo: string
  caseSn?: string
  width: number
  height: number
  images: string[]
  imageMeta: ImageMeta[]
  /** 按 role 分组的影像（一对多扩展） */
  imageGroups?: Partial<Record<
    'original' | 'MA' | 'HE' | 'EX' | 'SE' | 'OD' |
    'color_mask' | 'overlay' | 'class_mask' | 'other',
    string[]
  >>
  /** 影像是否完整（按 IDRiD 必备 role 集合判断） */
  /**
   * 影像 URL → PACS 中对应 DICOM 实例的 UID。
   * 只收录服务端核对确认存在的那些；缺席即表示该图未进 PACS，
   * 前端退回 JPG。宁可某个病例暂时不走 DICOM，也不能把图配错。
   */
  dicomInstances?: Record<
    string,
    { studyInstanceUid: string; seriesInstanceUid: string; sopInstanceUid: string }
  >
  /** 金标准的像素级分割；学员未解锁金标准时服务端不下发 */
  segmentation?: {
    sopInstanceUid: string
    segments: Array<{ number: number; label: string }>
  } | null
  imageComplete?: boolean
  missingRoles?: string[]
  /** 当前用户是否可见金标准图层（mask / overlay） */
  showGoldLayers?: boolean
  /** 已解锁时才有内容；未解锁为空数组 */
  goldAnnotations?: AnnotationItem[]
  lesionMaskUrl?: string
  heatmapUrl?: string
  /** ============ 安全标识（报告 P0/P1：安全条常驻） ============ */
  modality?: string
  modalityText?: string
  /** 检查日期，来自病例 exam_on。为空表示没有提供 */
  examDate?: string | null
  /** exam_on 能解析时才为真，不能用入库时间代替 */
  examDateKnown?: boolean
  subjectNo?: string
  examOn?: string
  visitIndex?: number
  visitCount?: number
  visits?: Array<{ id: number; caseNo: string; examOn: string; visitIndex: number }>
  /** 只有眼底照相，没有 OCT、视力或其他病历 */
  fundusOnly?: boolean
  safety?: SafetySummary
  /** ============ 模拟患者信息（按角色脱敏） ============ */
  patientName?: string
  patientGender?: string
  patientAge?: number
  patientPhone?: string
  phoneVisible?: boolean
}

export interface ReadingRecord {
  id: number
  caseId: number
  caseNo: string
  userId: number
  userName: string
  imageIndex: number
  imageUrl: string
  viewport: ViewportState | null
  annotations: AnnotationItem[]
  measurements: AnnotationItem[]
  layers: LayerState | null
  status: ReadingStatus
  /** READING 阅片作业；QUALITY 送教师审核的影像质量评估 */
  recordKind?: 'READING' | 'QUALITY' | string
  /** 结构化诊断结论 */
  diagnosis?: Record<string, any>
  note: string
  reviewComment: string
  reviewerId: number | null
  reviewerName: string
  reviewerRole: string
  createdAt: string | null
  updatedAt: string | null
}

export interface ReadingSaveParams {
  caseId: number
  imageIndex: number
  imageUrl: string
  annotations: AnnotationItem[]
  measurements: AnnotationItem[]
  viewport?: ViewportState | null
  layers?: LayerState | null
  /** 结构化诊断结论，键为病种表单的字段 key */
  diagnosis?: Record<string, any>
  note?: string
  submit?: boolean
  /** 提交幂等键：断网重试时原样带回，同键回放原记录而非新建一条 */
  requestId?: string
}

export interface ReadingReviewParams {
  reviewComment: string
  accept: boolean
}

export interface ReadingListQuery {
  caseId?: number
  userId?: number
  status?: ReadingStatus | ''
  page?: number
  pageSize?: number
}

/* ========== API ========== */

/** 获取病例影像源 */
export const getImageSource = (caseId: number) => {
  return http.get<ImageSource>(`/reading/cases/${caseId}/source`)
}

/** 恢复当前用户在该病例的最新阅片草稿 */
export const getLatestDraft = (caseId: number, imageIndex = 0) => {
  return http.get<ReadingRecord | null>(
    `/reading/cases/${caseId}/draft`,
    { imageIndex }
  )
}

/** 阅片记录分页 */
export const getReadingList = (query: ReadingListQuery = {}) => {
  const cleaned: Record<string, any> = {}
  Object.entries(query).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    cleaned[k] = v
  })
  return http.get<PageResult<ReadingRecord>>('/reading/list', {
    page: 1,
    pageSize: 20,
    ...cleaned
  })
}

/** 阅片记录详情 */
export const getReadingDetail = (recordId: number) => {
  return http.get<ReadingRecord>(`/reading/${recordId}`)
}

/** 保存 / 提交阅片标注 */
export const saveReading = (params: ReadingSaveParams) => {
  return http.post<ReadingRecord>('/reading/save', params, {
    showSuccess: true,
    successText: params.submit ? '已提交' : '已保存'
  })
}

/** 教师审核 */
export const reviewReading = (recordId: number, params: ReadingReviewParams) => {
  return http.post<ReadingRecord>(`/reading/${recordId}/review`, params)
}

/** 删除阅片记录（自己 DRAFT 或 ADMIN） */
export const deleteReading = (recordId: number) => {
  return http.delete<null>(`/reading/${recordId}`, undefined, { showSuccess: true })
}

/** 影像质量评估结果汇总 */
export interface QualityCheckResult {
  total: number
  evaluated: number
  failed: number
  /** 含本次在内，已成功评出等级的原图累计张数 */
  gradedTotal?: number
  hasUngradable: boolean
  /** 学员提交后为 SUBMITTED，教师通过后才是 REVIEWED */
  reviewStatus?: string
  readingId?: number | null
  items: Array<{
    imageId: number
    quality: string
    confidence?: number
    error?: string
  }>
}

/**
 * 触发病例原始影像的质量评估（先质量后诊断门控）。
 * 算法服务不可用时不会报错，失败张数计入 failed，质量保持「未评估」。
 */
export const checkImageQuality = (caseId: number) =>
  http.post<QualityCheckResult>(`/reading/cases/${caseId}/quality-check`)

/* ============ DICOMweb：影像与分割分离（报告 P1） ============ */

/** 单个分段（如「微动脉瘤」「视盘」） */
export interface DicomSegment {
  number: number
  label: string
}

/** 一个 SEG 实例，可含多个分段 */
export interface DicomSegmentation {
  sopInstanceUid: string
  seriesInstanceUid: string
  studyInstanceUid: string
  modality: string
  segments: DicomSegment[]
  segmentCount: number
  frameCount: number
  /** 形如 /dicomweb/instances/{uid}/frames/{frame}，按需替换 {frame} */
  frameUrlTemplate: string
}

/** PACS 中的原始影像实例 */
export interface DicomImageInstance {
  sopInstanceUid: string
  seriesInstanceUid: string
  /** wadors 需要完整的 study/series/instance 三级路径 */
  studyInstanceUid: string
  eye: 'OD' | 'OS' | 'UNKNOWN'
  eyeText: string
  modality: string
  rows: number
  columns: number
  acquisitionDateTime: string
  instanceNumber: number
  frameUrl: string
}

/** 病例级汇总：影像与分割分开计数，不再混算 */
export interface DicomCaseSummary {
  /** 原始影像张数——不含任何派生对象 */
  imageCount: number
  segmentationCount: number
  segmentTotal: number
  eyes: string[]
  eyesText: string
  examDateKnown: boolean
  examDate: string | null
  images: DicomImageInstance[]
  segmentations: DicomSegmentation[]
}

/** 按病种取结构化诊断表单定义 */
export const getDiagnosisForm = (caseId: number) =>
  http.get<any>(`/reading/cases/${caseId}/diagnosis-form`)

export const getPacsStatus = () =>
  http.get<{ enabled: boolean; available: boolean }>('/dicomweb/status')

export const getCaseDicom = (caseNo: string) =>
  http.get<DicomCaseSummary>(`/dicomweb/cases/${encodeURIComponent(caseNo)}/instances`)

/**
 * 单独取分割清单。
 * 分割体积远大于原图（单个 SEG 约 5.8 MB、原图约 0.4 MB），
 * 因此与影像分开请求，按需加载。
 */
export const getCaseSegmentations = (caseNo: string) =>
  http.get<{ segmentations: DicomSegmentation[]; count: number }>(
    `/dicomweb/cases/${encodeURIComponent(caseNo)}/segmentations`
  )
