import type { ReadingApi } from '@/api'

export type ToolName =
  | 'pointer'
  | 'pan'
  | 'zoom'
  | 'wwwc'
  | 'rect'
  | 'polygon'
  | 'pen'
  | 'freehand'
  | 'length'
  | 'angle'
  | 'eraser'

export type AnnotationItem = ReadingApi.AnnotationItem
export type ViewportState = ReadingApi.ViewportState
export type LayerState = ReadingApi.LayerState

export interface HistorySnapshot {
  annotations: AnnotationItem[]
  measurements: AnnotationItem[]
}

export interface CanvasState {
  tool: ToolName
  annotations: AnnotationItem[]
  measurements: AnnotationItem[]
  history: HistorySnapshot[]
  redoStack: HistorySnapshot[]
  viewport: ViewportState
  layers: LayerState
}

/** 工具内部名到界面上的叫法。列表和图上的编号都用这一套。 */
export const MARK_TOOL_LABEL: Record<string, string> = {
  rect: '矩形',
  polygon: '多边形',
  freehand: '手绘',
  pen: '画笔',
  ellipse: '椭圆',
  point: '点',
  quadrant: '象限',
  length: '距离',
  angle: '角度'
}

/**
 * 同一工具按出现顺序编号。
 * 两个都叫「出血」的矩形会变成「矩形 1 · 出血」「矩形 2 · 出血」，
 * 图上的字和右侧列表用的是同一句。
 */
export function markCaption(
  list: { tool: string; label?: string }[],
  index: number
): string {
  const item = list[index]
  if (!item) return ''
  let n = 0
  for (let i = 0; i <= index; i++) {
    if (list[i].tool === item.tool) n += 1
  }
  const tool = MARK_TOOL_LABEL[item.tool] || item.tool
  const head = `${tool} ${n}`
  const label = (item.label || '').trim()
  if (!label || label === tool) return head
  return `${head} · ${label}`
}

export const LESION_LABELS: { label: string; value: string; color: string }[] = [
  { label: '出血', value: '出血', color: '#f53f3f' },
  { label: '渗出', value: '渗出', color: '#ff7d00' },
  { label: '微动脉瘤', value: '微动脉瘤', color: '#fadb14' },
  { label: '棉绒斑', value: '棉绒斑', color: '#52c41a' },
  { label: '新生血管', value: '新生血管', color: '#1677ff' }
]

export const TOOL_GROUPS: {
  title: string
  items: { tool: ToolName; label: string; iconName: string }[]
}[] = [
  {
    title: '视图',
    items: [
      { tool: 'pointer', label: '指针', iconName: 'Pointer' },
      { tool: 'pan', label: '平移', iconName: 'Rank' },
      { tool: 'zoom', label: '缩放', iconName: 'ZoomIn' },
      { tool: 'wwwc', label: '窗宽窗位', iconName: 'Brightness' }
    ]
  },
  {
    title: '标注',
    items: [
      { tool: 'rect', label: '矩形', iconName: 'Crop' },
      { tool: 'polygon', label: '多边形', iconName: 'EditPen' },
      { tool: 'freehand', label: '手绘', iconName: 'EditPen' },
      { tool: 'pen', label: '画笔', iconName: 'Edit' }
    ]
  },
  {
    title: '测量',
    items: [
      { tool: 'length', label: '距离', iconName: 'Connection' },
      { tool: 'angle', label: '角度', iconName: 'CaretRight' }
    ]
  },
  {
    title: '其他',
    items: [
      { tool: 'eraser', label: '擦除', iconName: 'Delete' }
    ]
  }
]
