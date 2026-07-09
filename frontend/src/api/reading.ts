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

export type ReadingStatus = 'DRAFT' | 'SUBMITTED' | 'REVIEWED'

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
  imageComplete?: boolean
  missingRoles?: string[]
  /** 当前用户是否可见金标准图层（mask / overlay） */
  showGoldLayers?: boolean
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
  note: string
  reviewComment: string
  reviewerId: number | null
  reviewerName: string
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
  note?: string
  submit?: boolean
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
  return http.post<ReadingRecord>(`/reading/${recordId}/review`, params, {
    showSuccess: true
  })
}

/** 删除阅片记录（自己 DRAFT 或 ADMIN） */
export const deleteReading = (recordId: number) => {
  return http.delete<null>(`/reading/${recordId}`, undefined, { showSuccess: true })
}
