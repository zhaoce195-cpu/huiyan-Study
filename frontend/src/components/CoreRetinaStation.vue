<script setup lang="ts">
/**
 * CoreRetinaStation 共享影像画布
 *
 * 阅片 / 练习 / 教学查看 三端共用的唯一影像画布。
 * 新增 `mode` 用于在阅片 / 练习 / 教学查看 三种场景下复用：
 *
 *   - reading       默认。教师/管理员阅片标注
 *   - practice      学员练习。金标准由外层 layers.gold 控制，提交前外层保持关闭
 *   - teaching-view 学员浏览教师演示病例：强制只读，禁用标注工具
 *
 * 4 图层（Raw / AI Heatmap / My Marks / Gold）通过外部 layers 控制。
 * 主题：画布固定深色（医疗影像视觉规范），外围交互区遵循 EP token。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ensureCornerstone3D,
  ensureMetadataFor,
  loadSegmentMasks,
  makeCoordMapper,
  webImageId
} from '@/utils/cornerstone3d'
import type { SegmentMask } from '@/utils/cornerstone3d'
import type { AnnotationItem, LayerState, ToolName, ViewportState } from '@/views/reading/types'
import { LESION_LABELS, markCaption } from '@/views/reading/types'
import {
  QUAD_LABEL,
  quadAt,
  quadBounds,
  quadrantCodes,
  type LocateRequest,
  type QuadCode
} from '@/utils/finding-locate'

export type RetinaMode = 'reading' | 'practice' | 'teaching-view'

const props = withDefaults(
  defineProps<{
    /** 模式：reading（默认）/ practice / teaching-view */
    mode?: RetinaMode
    imageUrl: string
    /**
     * DICOM 影像 id（wadors:…）。给了就优先用它，
     * 未进 PACS 的遗留病例仍走 imageUrl 的 JPG。
     * 两条来源在视口内表现一致，上层无需分叉。
     */
    dicomImageId?: string
    tool: ToolName
    annotations: AnnotationItem[]
    measurements: AnnotationItem[]
    viewport: ViewportState
    layers: LayerState
    readonly: boolean
    /** 金标准（专家）标注，仅 layers.gold = true 时显示 */
    goldAnnotations?: AnnotationItem[]
    /**
     * 平时练习勾选征象后的指出位置。
     * 点选、圈选、象限只在这一步生效，不替换工具栏里的矩形和多边形。
     */
    locate?: LocateRequest | null
    /** 当前影像眼别，用来把象限画成颞侧或鼻侧 */
    laterality?: 'OD' | 'OS' | ''
    /**
     * 彩色病灶图或叠加图，与眼底图对齐后半透明叠上。
     * 同样只在 layers.gold = true 时画。提交前外层不要传入。
     */
    goldOverlayUrl?: string
    /** 病灶提示图（热力图）。只在 layers.heatmap 打开时画。 */
    heatmapOverlayUrl?: string
    /**
     * 多病灶分割叠加图（出血 / 硬性渗出 / 软性渗出）。
     * 只在带教工作台传入，不进图层存档，学员端保持空字符串。
     */
    lesionSegUrl?: string
    /**
     * DICOM SEG 病灶分割。金标准若是像素级分割，用它比矢量框精确得多；
     * 同样受 layers.gold 控制。图层关闭时不取分割，避免答题时把答案请求出去。
     */
    segmentation?: {
      sopInstanceUid: string
      segments: Array<{ number: number; label: string }>
    } | null
    /** 右侧列表悬停的那一条。图上用同一编号，并给它加一圈亮边。 */
    highlightId?: string
  }>(),
  {
    mode: 'reading',
    dicomImageId: '',
    goldAnnotations: () => [],
    locate: null,
    laterality: '',
    goldOverlayUrl: '',
    heatmapOverlayUrl: '',
    lesionSegUrl: '',
    segmentation: null,
    highlightId: ''
  }
)

const emit = defineEmits<{
  (e: 'update:annotations', v: AnnotationItem[], meta?: { history?: boolean }): void
  (e: 'update:measurements', v: AnnotationItem[]): void
  (e: 'update:viewport', v: ViewportState): void
  (e: 'ready'): void
  (e: 'error', err: any): void
  (e: 'pick-label', label: string): void
}>()

/** mode 派生的有效 readonly：teaching-view 强制 readonly */
const effectiveReadonly = computed(() => props.readonly || props.mode === 'teaching-view')

/** 金标准是否绘制完全由外层 layers.gold 决定。练习提交前外层保持关闭。 */
const effectiveLayers = computed<LayerState>(() => props.layers)

const elementRef = ref<HTMLDivElement | null>(null)
const overlayRef = ref<HTMLCanvasElement | null>(null)
const enabled = ref(false)
const loading = ref(false)
const imgSize = ref({ w: 1024, h: 1024 })

/* =========================================================
 * Cornerstone3D 初始化
 *
 * 每个组件实例用独立的 renderingEngine / toolGroup：
 * 阅片页与练习页可能同时挂载，共用一套会互相改工具状态。
 * ========================================================= */

let cs: any = null                 // @cornerstonejs/core
let csTools: any = null            // @cornerstonejs/tools
let renderingEngine: any = null
let viewport: any = null
let toolGroup: any = null
let mapper = {
  pixelToCanvas: (x: number, y: number) => ({ x, y }),
  canvasToPixel: (x: number, y: number) => ({ x, y })
}

const uid = Math.random().toString(36).slice(2, 9)
const ENGINE_ID = `huiyan-engine-${uid}`
const VIEWPORT_ID = `huiyan-viewport-${uid}`
const TOOLGROUP_ID = `huiyan-toolgroup-${uid}`

/** 自定义标注工具由 overlay 画布接管左键，此时内置工具都不能占用左键 */
const CS_TOOL_OF: Partial<Record<ToolName, string>> = {
  pan: 'Pan',
  zoom: 'Zoom',
  wwwc: 'WindowLevel',
  length: 'Length',
  angle: 'Angle'
}

const setupTools = async () => {
  csTools = await import('@cornerstonejs/tools')

  // 注意：tools 的 init() 在 ensureCornerstone3D() 里做，不在这里。
  // 它必须早于任何元素被 enable —— 而本函数是在 enableElement 之后
  // 才被调用的，放在这里就晚了。详见 utils/cornerstone3d.ts。
  const {
    PanTool, ZoomTool, WindowLevelTool, LengthTool, AngleTool,
    StackScrollTool, ToolGroupManager, Enums: csToolsEnums
  } = csTools

  // addTool 是全局注册，重复注册会抛；已注册就跳过
  for (const T of [PanTool, ZoomTool, WindowLevelTool, LengthTool, AngleTool, StackScrollTool]) {
    try {
      csTools.addTool(T)
    } catch {
      /* 已注册 */
    }
  }

  toolGroup = ToolGroupManager.createToolGroup(TOOLGROUP_ID)
  if (!toolGroup) return
  for (const name of ['Pan', 'Zoom', 'WindowLevel', 'Length', 'Angle', 'StackScroll']) {
    toolGroup.addTool(name)
  }
  toolGroup.addViewport(VIEWPORT_ID, ENGINE_ID)

  // 滚轮缩放始终可用，与工具选择无关
  toolGroup.setToolActive('Zoom', {
    bindings: [{ mouseButton: csToolsEnums.MouseBindings.Wheel }]
  })
}

const enableElement = async () => {
  if (!elementRef.value || enabled.value) return
  const bundle = await ensureCornerstone3D()
  cs = bundle.cornerstone
  dicomLoader = bundle.dicomImageLoader

  renderingEngine = new cs.RenderingEngine(ENGINE_ID)
  renderingEngine.enableElement({
    viewportId: VIEWPORT_ID,
    type: cs.Enums.ViewportType.STACK,
    element: elementRef.value
  })
  viewport = renderingEngine.getViewport(VIEWPORT_ID)
  mapper = makeCoordMapper(cs, viewport)

  await setupTools()
  enabled.value = true
}

const releaseGpuCanvases = (root: HTMLElement | null) => {
  if (!root) return
  root.querySelectorAll('canvas').forEach((canvas) => {
    try {
      const gl =
        (canvas.getContext('webgl2') as WebGL2RenderingContext | null) ||
        (canvas.getContext('webgl') as WebGLRenderingContext | null)
      gl?.getExtension('WEBGL_lose_context')?.loseContext()
      canvas.width = 1
      canvas.height = 1
    } catch {
      /* 上下文已经释放时不再抛错 */
    }
  })
}

const disableElement = () => {
  try {
    renderingEngine?.disableElement?.(VIEWPORT_ID)
  } catch {
    /* ignore */
  }
  try {
    csTools?.ToolGroupManager?.destroyToolGroup?.(TOOLGROUP_ID)
  } catch {
    /* ignore */
  }
  try {
    renderingEngine?.destroy?.()
  } catch {
    /* ignore */
  }
  releaseGpuCanvases(elementRef.value)
  renderingEngine = null
  viewport = null
  toolGroup = null
  mapper = {
    pixelToCanvas: (x: number, y: number) => ({ x, y }),
    canvasToPixel: (x: number, y: number) => ({ x, y })
  }
  enabled.value = false
}

/** 离开页面时由阅片页再调一次。重复调用是空操作。 */
const releaseViewport = (purgeCache = false) => {
  disableElement()
  if (!purgeCache) return
  try {
    cs?.cache?.purgeCache?.()
  } catch {
    /* ignore */
  }
}

/* =========================================================
 * 加载影像
 * ========================================================= */

let loadSeq = 0
let dicomLoader: any = null

const loadImage = async (url: string) => {
  if (!enabled.value) await enableElement()
  if (!viewport) return

  // DICOM 优先；没有 DICOM 才回退到遗留 JPG
  const imageId = props.dicomImageId || (url ? webImageId(url) : '')
  if (!imageId) {
    emit('error', new Error('影像 URL 为空'))
    ElMessage.warning('该病例暂无影像数据')
    return
  }

  const seq = ++loadSeq
  // 换图 = 换一套测量，上一张图报上去的 UID 不能再用来判断「被删了」
  reportedUids = new Set()
  loading.value = true
  try {
    // wadors 加载器不会自己去取元数据，必须先注册；
    // 少了这一步解码时读不到 imagePixelModule
    await ensureMetadataFor(dicomLoader, imageId)
    await viewport.setStack([imageId])

    // setStack 不会因解码失败而抛异常。不显式校验的话，
    // 页面会在图根本没出来的情况下显示为加载成功。
    const data = viewport.getImageData?.()
    const dims = data?.dimensions
    if (!dims || !dims[0] || !dims[1]) {
      throw new Error('影像未能解码：视口中没有像素数据')
    }

    // 期间用户切换了图片 → 丢弃过期结果
    if (seq !== loadSeq || !elementRef.value) return
    imgSize.value = { w: dims[0], h: dims[1] }

    applyViewport()
    viewport.render()
    syncOverlaySize()
    redrawOverlay()
    emit('ready')
  } catch (err: any) {
    if (seq !== loadSeq) return
    const status = err?.error?.status || err?.status
    let reason = '影像加载失败'
    if (status === 404) reason = '影像文件不存在（404）'
    else if (status === 403) reason = '无权访问该影像（403）'
    else if (status >= 500) reason = '服务器异常，无法加载影像'
    else if (err?.message?.includes('timeout')) reason = '影像加载超时'
    else if (err?.message?.includes('解码')) reason = err.message
    else if (err?.error === 'NetworkError') reason = '网络异常，无法加载影像'
    emit('error', err)
    ElMessage.error(reason)
    console.warn('[CoreRetinaStation] loadImage failed:', { imageId, err })
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

/** 窗宽窗位 ↔ Cornerstone3D 的 voiRange */
const toVoiRange = (ww: number, wl: number) => ({
  lower: wl - ww / 2,
  upper: wl + ww / 2
})

const applyViewport = () => {
  if (!viewport) return
  try {
    const v = props.viewport || ({} as ViewportState)

    viewport.setProperties({
      voiRange: toVoiRange(v.ww || 255, v.wl || 127),
      invert: !!v.invert
    })

    // 旧内核的 scale=1 是影像 1:1，新内核的 zoom=1 是适配窗口，
    // 不是同一个量纲。缺 engine 标记的旧快照只还原窗宽窗位，
    // 缩放平移重置为适配 —— 硬套会让 4752 px 宽的眼底照
    // 放大到十倍，用户以为图坏了。
    if (v.engine === 'cs3d') {
      if (v.scale) viewport.setZoom(v.scale)
      viewport.setPan([v.x || 0, v.y || 0])
    } else {
      viewport.resetCamera()
    }
    viewport.render()
  } catch {
    /* ignore */
  }
}

const readViewport = () => {
  if (!viewport) return
  try {
    const props_ = viewport.getProperties?.() || {}
    const range = props_.voiRange
    const ww = range ? range.upper - range.lower : 255
    const wl = range ? (range.upper + range.lower) / 2 : 127
    const pan = viewport.getPan?.() || [0, 0]
    emit('update:viewport', {
      scale: viewport.getZoom?.() || 1,
      x: pan[0] || 0,
      y: pan[1] || 0,
      ww,
      wl,
      invert: !!props_.invert,
      engine: 'cs3d'
    })
  } catch {
    /* ignore */
  }
}

/* =========================================================
 * 工具切换
 * ========================================================= */

const setActiveCornerstoneTool = (t: ToolName) => {
  if (!toolGroup || !csTools) return
  const { Enums: csToolsEnums } = csTools

  // 先让内置工具全部让出左键
  for (const name of Object.values(CS_TOOL_OF)) {
    try {
      toolGroup.setToolPassive(name as string)
    } catch {
      /* ignore */
    }
  }

  // 自定义标注工具（rect/polygon/…）下不激活任何内置工具，
  // 左键留给 overlay 画布，否则画一笔就同时平移了影像
  const name = CS_TOOL_OF[t]
  if (!name) return
  try {
    toolGroup.setToolActive(name, {
      bindings: [{ mouseButton: csToolsEnums.MouseBindings.Primary }]
    })
  } catch {
    /* ignore */
  }
}

/* =========================================================
 * 自定义 overlay：rect/polygon/freehand/pen/eraser
 * ========================================================= */

const drawing = ref(false)
const currentPoints = ref<{ x: number; y: number }[]>([])
/** 多边形绘制中光标所在的影像坐标，用于橡皮筋预览 */
const hoverPoint = ref<{ x: number; y: number } | null>(null)

/**
 * 顶点拖拽。
 *
 * 画完的框往往需要微调 —— 此前只能擦掉重画，一个多边形重来一次
 * 要点七八下。这里支持抓住任一顶点拖动改形。
 */
const HANDLE_RADIUS = 10
type DragState =
  | { kind: 'vertex'; annIndex: number; ptIndex: number }
  | { kind: 'corner'; annIndex: number; anchor: { x: number; y: number } }
  | { kind: 'move'; annIndex: number; last: { x: number; y: number } }
const dragging = ref<DragState | null>(null)
/** 一次拖动只记一条撤销，避免鼠标每移动一像素就堆一条历史 */
let dragRecorded = false

/** 右键点在某一条标注上时弹出。编号和右侧列表相同。 */
const markMenu = ref<{
  kind: 'annotation' | 'measurement'
  id: string
  caption: string
  x: number
  y: number
} | null>(null)
const markMenuRef = ref<HTMLElement | null>(null)

/** 矩形存在两个对角点，画面上却画了四个角。四个角都要能抓住。 */
const hitRectCorner = (px: number, py: number) => {
  const list = props.annotations
  for (let i = list.length - 1; i >= 0; i--) {
    const ann = list[i]
    if (ann.tool !== 'rect' || (ann.points || []).length < 2) continue
    const a = ann.points[0]
    const b = ann.points[1]
    const x1 = Math.min(a.x, b.x)
    const y1 = Math.min(a.y, b.y)
    const x2 = Math.max(a.x, b.x)
    const y2 = Math.max(a.y, b.y)
    const corners = [
      { x: x1, y: y1, anchor: { x: x2, y: y2 } },
      { x: x2, y: y1, anchor: { x: x1, y: y2 } },
      { x: x1, y: y2, anchor: { x: x2, y: y1 } },
      { x: x2, y: y2, anchor: { x: x1, y: y1 } }
    ]
    for (const c of corners) {
      const s = pixelToCanvas(c.x, c.y)
      if (Math.hypot(s.x - px, s.y - py) <= HANDLE_RADIUS) {
        return { annIndex: i, anchor: c.anchor }
      }
    }
  }
  return null
}

/** 命中哪个标注的哪个顶点。矩形走四个角，这里只处理多边形和手绘。 */
const hitHandle = (px: number, py: number) => {
  const list = props.annotations
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].layer === 'finding' || list[i].tool === 'rect') continue
    const pts = list[i].points || []
    for (let j = pts.length - 1; j >= 0; j--) {
      const c = pixelToCanvas(pts[j].x, pts[j].y)
      if (Math.hypot(c.x - px, c.y - py) <= HANDLE_RADIUS) {
        return { annIndex: i, ptIndex: j }
      }
    }
  }
  return null
}

const nearStroke = (
  px: number,
  py: number,
  pts: { x: number; y: number }[],
  closed: boolean,
  limit = 8
) => {
  if (pts.length < 2) return false
  const n = closed ? pts.length : pts.length - 1
  for (let i = 0; i < n; i++) {
    const a = pts[i]
    const b = pts[(i + 1) % pts.length]
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len2 = dx * dx + dy * dy
    const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - a.x) * dx + (py - a.y) * dy) / len2))
    const dist = Math.hypot(a.x + dx * t - px, a.y + dy * t - py)
    if (dist <= limit) return true
  }
  return false
}

const pointInPolygon = (px: number, py: number, pts: { x: number; y: number }[]) => {
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const yi = pts[i].y
    const yj = pts[j].y
    const intersect =
      yi > py !== yj > py &&
      px < ((pts[j].x - pts[i].x) * (py - yi)) / (yj - yi || 1e-6) + pts[i].x
    if (intersect) inside = !inside
  }
  return inside
}

/** 点在框内或贴着边线：用来整框平移，而不是只拽一个角 */
const hitBody = (px: number, py: number) => {
  const list = props.annotations
  for (let i = list.length - 1; i >= 0; i--) {
    const ann = list[i]
    if (ann.layer === 'finding') continue
    const pts = ann.points || []
    if (pts.length === 0) continue
    const screen = pts.map((p) => pixelToCanvas(p.x, p.y))
    if (ann.tool === 'rect' && screen.length >= 2) {
      const x = Math.min(screen[0].x, screen[1].x) - 6
      const y = Math.min(screen[0].y, screen[1].y) - 6
      const w = Math.abs(screen[1].x - screen[0].x) + 12
      const h = Math.abs(screen[1].y - screen[0].y) + 12
      if (px >= x && px <= x + w && py >= y && py <= y + h) return i
    } else if (ann.tool === 'polygon' && screen.length >= 3 && pointInPolygon(px, py, screen)) {
      return i
    } else if (nearStroke(px, py, screen, ann.tool === 'polygon')) {
      return i
    }
  }
  return null
}

/** 右键落在测量线上。比拖动框的命中宽一点，细线不好点。 */
const hitMeasurement = (px: number, py: number) => {
  const list = props.measurements
  for (let i = list.length - 1; i >= 0; i--) {
    const pts = (list[i].points || []).map((p) => pixelToCanvas(p.x, p.y))
    if (nearStroke(px, py, pts, false, 14)) return i
  }
  return null
}

/** 光标是否落在首点附近（屏幕距离），用于「点回首点闭合」 */
const CLOSE_RADIUS = 10
const nearFirstPoint = (px: number, py: number): boolean => {
  if (currentPoints.value.length < 3) return false
  const first = pixelToCanvas(currentPoints.value[0].x, currentPoints.value[0].y)
  return Math.hypot(first.x - px, first.y - py) <= CLOSE_RADIUS
}
const currentLabel = ref(LESION_LABELS[0].value)
const chooseLesionLabel = (label: string) => {
  currentLabel.value = label
  emit('pick-label', label)
}

const syncOverlaySize = () => {
  if (!elementRef.value || !overlayRef.value) return
  const rect = elementRef.value.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  overlayRef.value.style.width = rect.width + 'px'
  overlayRef.value.style.height = rect.height + 'px'
  overlayRef.value.width = rect.width * dpr
  overlayRef.value.height = rect.height * dpr
  const ctx = overlayRef.value.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
}

const colorOf = (label: string): string => {
  const hit = LESION_LABELS.find((l) => l.value === label)
  return hit?.color || '#4091ff'
}

// 标注一律以影像像素坐标存库，与显示无关：换缩放、换内核、换屏幕
// 都不影响既有标注的位置。这两个函数是像素与屏幕之间唯一的桥。
const pixelToCanvas = (x: number, y: number) => {
  if (!viewport) return { x, y }
  try {
    return mapper.pixelToCanvas(x, y)
  } catch {
    return { x, y }
  }
}

const canvasToPixel = (x: number, y: number) => {
  if (!viewport) return { x, y }
  try {
    return mapper.canvasToPixel(x, y)
  } catch {
    return { x, y }
  }
}

const redrawOverlay = () => {
  if (!overlayRef.value) return
  const canvas = overlayRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const w = canvas.width / (window.devicePixelRatio || 1)
  const h = canvas.height / (window.devicePixelRatio || 1)
  ctx.clearRect(0, 0, w, h)

  // 病灶提示图在金标准之下，原图由视口本身控制显隐
  if (effectiveLayers.value.heatmap && heatmapOverlay.value) {
    drawOverlayImage(ctx, heatmapOverlay.value, 0.5)
  }
  if (lesionSegOverlay.value) {
    drawOverlayImage(ctx, lesionSegOverlay.value, 0.45)
  }
  // 金标准图像与分割掩码：像素级，画在矢量标注之下
  if (effectiveLayers.value.gold && goldOverlay.value) {
    drawGoldOverlay(ctx)
  }
  if (effectiveLayers.value.gold && segmentMasks.value.length > 0) {
    drawSegmentMasks(ctx)
  }

  // 金标准图层（专家标注）
  if (effectiveLayers.value.gold && props.goldAnnotations.length > 0) {
    props.goldAnnotations.forEach((g) => drawGoldAnnotation(ctx, g))
  }

  if (props.locate?.method === 'quadrant' && !effectiveReadonly.value) {
    drawQuadrantGuides(ctx)
  }

  // 已落地的标注
  if (effectiveLayers.value.my) {
    props.annotations.forEach((a, i) => {
      const hot = a.id === props.highlightId || a.id === markMenu.value?.id
      ctx.save()
      if (hot) {
        ctx.shadowColor = '#ffffff'
        ctx.shadowBlur = 16
      }
      drawAnnotation(ctx, a, false, markCaption(props.annotations, i))
      ctx.restore()
    })
    // 只画 Cornerstone3D 自己没在画的那些测量。
    //
    // 内置 Length / Angle 工具会自行渲染手柄与数值；overlay 若再画一遍，
    // 一条测量就有两套端点，看起来像「点一次出现两个点」。
    // 但从数据库恢复的历史测量并不在 Cornerstone3D 的标注状态里，
    // 那些仍然要由 overlay 负责画出来。
    const live = liveAnnotationUids()
    props.measurements.forEach((m, i) => {
      if (live.has(m.id)) return
      const hot = m.id === props.highlightId || m.id === markMenu.value?.id
      ctx.save()
      if (hot) {
        ctx.shadowColor = '#ffffff'
        ctx.shadowBlur = 16
      }
      drawMeasurement(ctx, m, markCaption(props.measurements, i))
      ctx.restore()
    })
  }

  // 正在绘制的临时图形
  if (drawing.value && currentPoints.value.length > 0) {
    const locatingCircle = props.locate?.method === 'circle'
    const tmp: AnnotationItem = {
      id: '_tmp',
      tool: locatingCircle
        ? 'ellipse'
        : props.tool === 'eraser'
          ? 'rect'
          : props.tool === 'pan'
            ? 'rect'
            : (props.tool as any),
      // 多边形把光标位置作为临时末点，形成跟随鼠标的橡皮筋
      points:
        props.tool === 'polygon' && hoverPoint.value
          ? [...currentPoints.value, hoverPoint.value]
          : currentPoints.value,
      label: locatingCircle ? props.locate?.label || '' : currentLabel.value,
      color: locatingCircle ? props.locate?.color || '#ff7d00' : colorOf(currentLabel.value),
      layer: locatingCircle ? 'finding' : 'primary'
    }
    drawAnnotation(ctx, tmp, true)

    // 满足闭合条件时把首点高亮出来，告诉用户「点这里就能收尾」
    if (props.tool === 'polygon' && currentPoints.value.length >= 3) {
      const f = pixelToCanvas(currentPoints.value[0].x, currentPoints.value[0].y)
      ctx.save()
      ctx.beginPath()
      ctx.arc(f.x, f.y, CLOSE_RADIUS, 0, Math.PI * 2)
      ctx.strokeStyle = '#00e676'
      ctx.lineWidth = 2
      ctx.setLineDash([3, 3])
      ctx.stroke()
      ctx.restore()
    }
  }
}

/** 顶点标记。首点画大一圈：多边形要靠点回首点来闭合，得让它显眼 */
const drawNode = (
  ctx: CanvasRenderingContext2D,
  p: { x: number; y: number },
  color: string,
  isFirst = false
) => {
  const r = isFirst ? 6 : 4
  ctx.save()
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
  ctx.fillStyle = '#fff'
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = color
  ctx.stroke()
  ctx.restore()
}

const findingEye = () => props.locate?.eye || props.laterality || ''

const drawQuadrantFill = (ctx: CanvasRenderingContext2D, ann: AnnotationItem) => {
  const size = imgSize.value
  const code = (ann.remark || '').split(':')[1] as QuadCode
  if (!size.w || !size.h || !QUAD_LABEL[code]) return
  const box = quadBounds(code, size.w, size.h, findingEye())
  const a = pixelToCanvas(box.x, box.y)
  const b = pixelToCanvas(box.x + box.w, box.y + box.h)
  const x = Math.min(a.x, b.x)
  const y = Math.min(a.y, b.y)
  const w = Math.abs(b.x - a.x)
  const h = Math.abs(b.y - a.y)
  ctx.fillRect(x, y, w, h)
  ctx.strokeRect(x, y, w, h)
  ctx.fillStyle = ann.color || '#ffffff'
  ctx.font = '13px sans-serif'
  ctx.fillText(QUAD_LABEL[code], x + 8, y + 18)
}

const drawQuadrantGuides = (ctx: CanvasRenderingContext2D) => {
  const size = imgSize.value
  if (!size.w || !size.h) return
  const eye = findingEye()
  ctx.save()
  ctx.setLineDash([6, 4])
  ctx.lineWidth = 1
  ctx.strokeStyle = 'rgba(255,255,255,0.75)'
  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.font = '13px sans-serif'
  for (const code of quadrantCodes(eye)) {
    const box = quadBounds(code, size.w, size.h, eye)
    const a = pixelToCanvas(box.x, box.y)
    const b = pixelToCanvas(box.x + box.w, box.y + box.h)
    const x = Math.min(a.x, b.x)
    const y = Math.min(a.y, b.y)
    ctx.strokeRect(x, y, Math.abs(b.x - a.x), Math.abs(b.y - a.y))
    ctx.fillText(QUAD_LABEL[code], x + 8, y + 18)
  }
  ctx.restore()
}

/** 编号贴在框的左上角，白字黑底，和右侧列表里的句子一致。 */
const drawMarkCaption = (
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  color: string
) => {
  ctx.save()
  ctx.font = '12px sans-serif'
  ctx.setLineDash([])
  const width = ctx.measureText(text).width
  const left = x + 6
  const top = Math.max(16, y - 8)
  ctx.fillStyle = 'rgba(0, 0, 0, 0.78)'
  ctx.fillRect(left - 4, top - 13, width + 8, 18)
  ctx.strokeStyle = color
  ctx.lineWidth = 1
  ctx.strokeRect(left - 4, top - 13, width + 8, 18)
  ctx.fillStyle = '#fff'
  ctx.fillText(text, left, top)
  ctx.restore()
}

const drawAnnotation = (
  ctx: CanvasRenderingContext2D,
  ann: AnnotationItem,
  preview = false,
  caption = ''
) => {
  if (ann.points.length === 0) return
  const color = ann.color || colorOf(ann.label)
  ctx.lineWidth = 2
  ctx.strokeStyle = color
  ctx.fillStyle = color + '24'
  ctx.setLineDash(preview ? [4, 4] : [])

  const pts = ann.points.map((p) => pixelToCanvas(p.x, p.y))

  if (ann.tool === 'rect') {
    // 只有一个点时也要看得见：否则用户按下鼠标后画面毫无反应，
    // 会以为工具没生效
    if (pts.length < 2) {
      drawNode(ctx, pts[0], color)
      return
    }
    const x1 = pts[0].x
    const y1 = pts[0].y
    const x2 = pts[1].x
    const y2 = pts[1].y
    const x = Math.min(x1, x2)
    const y = Math.min(y1, y2)
    const w = Math.abs(x2 - x1)
    const h = Math.abs(y2 - y1)
    ctx.fillRect(x, y, w, h)
    ctx.strokeRect(x, y, w, h)
    // 四角节点：让用户看清框到底落在哪，也便于确认是否画歪
    for (const p of [{ x, y }, { x: x + w, y }, { x, y: y + h }, { x: x + w, y: y + h }]) {
      drawNode(ctx, p, color)
    }
  } else if (ann.tool === 'ellipse') {
    if (pts.length < 2) {
      if (pts.length === 1) drawNode(ctx, pts[0], color)
    } else {
    const x = Math.min(pts[0].x, pts[1].x)
    const y = Math.min(pts[0].y, pts[1].y)
    const w = Math.abs(pts[1].x - pts[0].x)
    const h = Math.abs(pts[1].y - pts[0].y)
    ctx.beginPath()
    ctx.lineWidth = 3
    ctx.ellipse(x + w / 2, y + h / 2, Math.max(w / 2, 1), Math.max(h / 2, 1), 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
    }
  } else if (ann.tool === 'point' && pts.length >= 1) {
    ctx.save()
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.arc(pts[0].x, pts[0].y, 10, 0, Math.PI * 2)
    ctx.fillStyle = '#fff'
    ctx.fill()
    ctx.lineWidth = 3
    ctx.strokeStyle = color
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(pts[0].x - 16, pts[0].y)
    ctx.lineTo(pts[0].x + 16, pts[0].y)
    ctx.moveTo(pts[0].x, pts[0].y - 16)
    ctx.lineTo(pts[0].x, pts[0].y + 16)
    ctx.stroke()
    ctx.restore()
  } else if (ann.tool === 'quadrant') {
    drawQuadrantFill(ctx, ann)
  } else if (ann.tool === 'polygon' || ann.tool === 'pen' || ann.tool === 'freehand') {
    if (pts.length >= 2) {
      ctx.beginPath()
      ctx.moveTo(pts[0].x, pts[0].y)
      pts.slice(1).forEach((p) => ctx.lineTo(p.x, p.y))
      if (ann.tool === 'polygon' && !preview) {
        ctx.closePath()
        ctx.fill()
      }
      ctx.stroke()
    }
    // 多边形逐点点击，必须能看到已落的每个点。
    // 此前单点时 moveTo 后直接 stroke，画布上什么都不出现，
    // 用户以为第一次点击没生效。
    if (ann.tool === 'polygon') {
      pts.forEach((p, i) => drawNode(ctx, p, color, i === 0))
    } else if (preview && pts.length === 1) {
      drawNode(ctx, pts[0], color)
    } else if (!preview) {
      // 手绘/自由曲线点很密，全画会糊成一片，只标出两端
      drawNode(ctx, pts[0], color)
      if (pts.length > 1) drawNode(ctx, pts[pts.length - 1], color)
    }
  }

  if (!preview && pts.length > 0) {
    const text = caption || ann.label
    if (text) {
      let ax = pts[0].x
      let ay = pts[0].y
      if (ann.tool === 'rect' && pts.length >= 2) {
        ax = Math.min(pts[0].x, pts[1].x)
        ay = Math.min(pts[0].y, pts[1].y)
      } else {
        for (const p of pts) {
          if (p.y < ay) {
            ax = p.x
            ay = p.y
          }
        }
      }
      drawMarkCaption(ctx, text, ax, ay, color)
    }
  }
}

/* =========================================================
 * 金标准分割掩码
 * ========================================================= */

const segmentMasks = ref<SegmentMask[]>([])
const segmentError = ref('')
const goldOverlay = ref<HTMLImageElement | null>(null)
const heatmapOverlay = ref<HTMLImageElement | null>(null)
const lesionSegOverlay = ref<HTMLImageElement | null>(null)

/** 彩色病灶图与眼底图同一画幅，拉伸到影像矩形上即可对齐。 */
const drawOverlayImage = (
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  alpha: number
) => {
  const tl = pixelToCanvas(0, 0)
  const br = pixelToCanvas(imgSize.value.w, imgSize.value.h)
  const w = br.x - tl.x
  const h = br.y - tl.y
  if (!(w > 0 && h > 0)) return
  const prev = ctx.globalAlpha
  ctx.globalAlpha = alpha
  try {
    ctx.drawImage(img, tl.x, tl.y, w, h)
  } catch {
    /* 单张掩码画失败不影响标注框 */
  }
  ctx.globalAlpha = prev
}

const drawGoldOverlay = (ctx: CanvasRenderingContext2D) => {
  if (!goldOverlay.value) return
  drawOverlayImage(ctx, goldOverlay.value, 0.55)
}

/**
 * 掩码与影像同一像素网格，所以只要把「影像左上角」和「影像右下角」
 * 换算到屏幕坐标，再把整张掩码拉伸到这个矩形即可，逐像素对齐。
 * 走的是与标注同一套坐标变换，缩放平移自动跟随，不需要单独同步。
 */
const drawSegmentMasks = (ctx: CanvasRenderingContext2D) => {
  const tl = pixelToCanvas(0, 0)
  const br = pixelToCanvas(imgSize.value.w, imgSize.value.h)
  const w = br.x - tl.x
  const h = br.y - tl.y
  if (!(w > 0 && h > 0)) return

  const prev = ctx.globalAlpha
  // 掩码是不透明色块，压在原图上会挡住底层纹理；
  // 半透明才能同时看清病灶范围与影像本身
  ctx.globalAlpha = 0.45
  for (const m of segmentMasks.value) {
    try {
      ctx.drawImage(m.image, tl.x, tl.y, w, h)
    } catch {
      /* 单个掩码画失败不影响其它图层 */
    }
  }
  ctx.globalAlpha = prev
}

const refreshSegmentMasks = async () => {
  const seg = props.segmentation
  // 图层关闭时不取分割。练习提交前外层不会打开金标准，
  // 请求本身会留在浏览器网络面板里，等于把答案递出去了。
  if (!seg?.sopInstanceUid || !effectiveLayers.value.gold) {
    if (!seg?.sopInstanceUid) segmentMasks.value = []
    return
  }
  try {
    segmentMasks.value = await loadSegmentMasks(seg.sopInstanceUid, seg.segments || [])
    segmentError.value = ''
  } catch (e: any) {
    segmentMasks.value = []
    segmentError.value = e?.message || String(e)
  }
  redrawOverlay()
}

const drawGoldAnnotation = (ctx: CanvasRenderingContext2D, ann: AnnotationItem) => {
  if (ann.points.length === 0) return
  const color = '#00e676'
  ctx.lineWidth = 2.5
  ctx.strokeStyle = color
  ctx.fillStyle = color + '18'
  ctx.setLineDash([6, 4])

  const pts = ann.points.map((p) => pixelToCanvas(p.x, p.y))

  if (ann.tool === 'rect') {
    if (pts.length < 2) return
    const x = Math.min(pts[0].x, pts[1].x)
    const y = Math.min(pts[0].y, pts[1].y)
    const w = Math.abs(pts[1].x - pts[0].x)
    const h = Math.abs(pts[1].y - pts[0].y)
    ctx.fillRect(x, y, w, h)
    ctx.strokeRect(x, y, w, h)
  } else {
    ctx.beginPath()
    ctx.moveTo(pts[0].x, pts[0].y)
    pts.slice(1).forEach((p) => ctx.lineTo(p.x, p.y))
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
  }

  ctx.setLineDash([])
  if (pts.length > 0 && ann.label) {
    ctx.fillStyle = color
    ctx.font = 'bold 12px sans-serif'
    ctx.fillText(`[金] ${ann.label}`, pts[0].x + 4, pts[0].y - 6)
  }
}

/** 当前由 Cornerstone3D 自行渲染的测量标注 UID */
const liveAnnotationUids = (): Set<string> => {
  const out = new Set<string>()
  const getAnns = csTools?.annotation?.state?.getAnnotations
  if (typeof getAnns !== 'function' || !elementRef.value) return out
  for (const toolName of ['Length', 'Angle']) {
    try {
      for (const a of getAnns(toolName, elementRef.value) || []) {
        if (a?.annotationUID) out.add(a.annotationUID)
      }
    } catch {
      /* ignore */
    }
  }
  return out
}

const drawMeasurement = (ctx: CanvasRenderingContext2D, m: AnnotationItem, caption = '') => {
  if (m.points.length < 2) return
  const pts = m.points.map((p) => pixelToCanvas(p.x, p.y))
  const color = m.color || '#52c41a'
  ctx.lineWidth = 2
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.setLineDash([])

  ctx.beginPath()
  ctx.moveTo(pts[0].x, pts[0].y)
  pts.slice(1).forEach((p) => ctx.lineTo(p.x, p.y))
  ctx.stroke()
  // 端点标记
  pts.forEach((p) => {
    ctx.beginPath()
    ctx.arc(p.x, p.y, 3, 0, Math.PI * 2)
    ctx.fill()
  })
  if (m.value !== undefined) {
    const last = pts[pts.length - 1]
    ctx.font = '12px sans-serif'
    ctx.fillText(`${m.value.toFixed(1)} ${m.unit || ''}`, last.x + 6, last.y - 6)
  }
  if (caption) drawMarkCaption(ctx, caption, pts[0].x, pts[0].y, color)
}

/* =========================================================
 * 鼠标事件 — 自定义工具
 * ========================================================= */

const customTools: ToolName[] = ['rect', 'polygon', 'freehand', 'pen', 'eraser']
const isCustomTool = () => customTools.includes(props.tool)
const isPointerTool = () => props.tool === 'pointer'

/**
 * 深色眼底上系统默认黑箭头几乎看不见。指针用白底黑边的箭头，
 * 画图工具用十字，保证离开标注工具后光标还在。
 */
const POINTER_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M5.5 2.5v16l3.7-3.9 3.6 6.6 2.6-1.2-3.7-6.7 6.1 0z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>'
)}") 5 2, auto`

const cursorFor = (kind: 'handle' | 'body' | null) => {
  if (locating()) return 'crosshair'
  if (dragging.value) return 'grabbing'
  if (kind === 'handle') return 'grab'
  if (kind === 'body') return 'move'
  if (props.tool === 'pointer') return POINTER_CURSOR
  if (props.tool === 'pan') return 'grab'
  if (props.tool === 'zoom') return 'zoom-in'
  if (props.tool === 'wwwc') return 'ns-resize'
  return 'crosshair'
}

const paintCursor = (kind: 'handle' | 'body' | null) => {
  const cur = cursorFor(kind)
  if (overlayRef.value) overlayRef.value.style.cursor = cur
  if (elementRef.value) elementRef.value.style.cursor = cur
}

const hoverKind = (px: number, py: number): 'handle' | 'body' | null => {
  if (hitRectCorner(px, py) || hitHandle(px, py)) return 'handle'
  if (hitBody(px, py) != null) return 'body'
  return null
}

const applyDrag = (pixel: { x: number; y: number }) => {
  const drag = dragging.value
  if (!drag) return
  const recordHistory = !dragRecorded
  dragRecorded = true
  const next = props.annotations.map((a, i) => {
    if (i !== drag.annIndex) return a
    if (drag.kind === 'vertex') {
      const pts = a.points.slice()
      pts[drag.ptIndex] = pixel
      return { ...a, points: pts }
    }
    if (drag.kind === 'corner') {
      return { ...a, points: [{ ...drag.anchor }, { x: pixel.x, y: pixel.y }] }
    }
    const dx = pixel.x - drag.last.x
    const dy = pixel.y - drag.last.y
    drag.last = pixel
    return {
      ...a,
      points: a.points.map((p) => ({ x: p.x + dx, y: p.y + dy }))
    }
  })
  emit('update:annotations', next, { history: recordHistory })
  redrawOverlay()
}

const onWindowMouseMove = (e: MouseEvent) => {
  if (!dragging.value || !overlayRef.value) return
  const rect = overlayRef.value.getBoundingClientRect()
  applyDrag(canvasToPixel(e.clientX - rect.left, e.clientY - rect.top))
  paintCursor(null)
}

const finishDrag = () => {
  if (!dragging.value && !dragRecorded) return
  dragging.value = null
  dragRecorded = false
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', finishDrag)
}

const beginDrag = (state: DragState) => {
  dragging.value = state
  dragRecorded = false
  window.addEventListener('mousemove', onWindowMouseMove)
  window.addEventListener('mouseup', finishDrag)
}

/** 角点改大小，点在框身上则整框平移。返回 true 表示这次点击被标注吃掉了。 */
const tryDragAnnotation = (px: number, py: number) => {
  const corner = hitRectCorner(px, py)
  if (corner) {
    beginDrag({ kind: 'corner', annIndex: corner.annIndex, anchor: corner.anchor })
    return true
  }
  const vertex = hitHandle(px, py)
  if (vertex) {
    beginDrag({ kind: 'vertex', annIndex: vertex.annIndex, ptIndex: vertex.ptIndex })
    return true
  }
  const body = hitBody(px, py)
  if (body != null) {
    beginDrag({
      kind: 'move',
      annIndex: body,
      last: canvasToPixel(px, py)
    })
    return true
  }
  return false
}

const locating = () => !!props.locate && !effectiveReadonly.value

const placeFinding = (ann: Omit<AnnotationItem, 'id' | 'layer'>) => {
  emit('update:annotations', [
    ...props.annotations,
    {
      id: 'F_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      layer: 'finding',
      ...ann
    }
  ])
  redrawOverlay()
}

const pixelFromEvent = (e: MouseEvent) => {
  const box = overlayRef.value?.getBoundingClientRect()
  if (!box) return { x: 0, y: 0 }
  return canvasToPixel(e.clientX - box.left, e.clientY - box.top)
}

const finishCircle = (e: MouseEvent) => {
  window.removeEventListener('mouseup', finishCircle)
  if (!drawing.value || props.locate?.method !== 'circle') {
    drawing.value = false
    currentPoints.value = []
    return
  }
  const pixel = pixelFromEvent(e)
  if (currentPoints.value.length === 1) currentPoints.value.push(pixel)
  else currentPoints.value[1] = pixel
  const [a, b] = currentPoints.value
  drawing.value = false
  currentPoints.value = []
  hoverPoint.value = null
  if (!a || !b || !props.locate) {
    redrawOverlay()
    return
  }
  if (Math.hypot(a.x - b.x, a.y - b.y) < 12) {
    ElMessage.warning('圈选请按住并拖出一块区域')
    redrawOverlay()
    return
  }
  placeFinding({
    tool: 'ellipse',
    points: [a, b],
    label: props.locate.label,
    color: props.locate.color,
    remark: props.locate.code
  })
}

const onLocateDown = (e: MouseEvent) => {
  const locate = props.locate
  if (!locate) return
  e.preventDefault()
  e.stopPropagation()
  const pixel = pixelFromEvent(e)
  if (locate.method === 'point') {
    placeFinding({
      tool: 'point',
      points: [pixel],
      label: locate.label,
      color: locate.color,
      remark: locate.code
    })
    return
  }
  if (locate.method === 'quadrant') {
    const size = imgSize.value
    if (!size.w || !size.h) return
    const quad = quadAt(pixel.x, pixel.y, size.w, size.h, locate.eye)
    const remark = `${locate.code}:${quad}`
    const idx = props.annotations.findIndex(
      (item) => item.layer === 'finding' && item.remark === remark
    )
    if (idx >= 0) {
      emit(
        'update:annotations',
        props.annotations.filter((_, i) => i !== idx)
      )
      redrawOverlay()
      return
    }
    placeFinding({
      tool: 'quadrant',
      points: [pixel],
      label: `${locate.label} · ${QUAD_LABEL[quad]}`,
      color: locate.color,
      remark
    })
    return
  }
  drawing.value = true
  currentPoints.value = [pixel]
  window.addEventListener('mouseup', finishCircle)
  redrawOverlay()
}

const onMouseDown = (e: MouseEvent) => {
  if (e.button !== 0) return
  if (locating()) {
    onLocateDown(e)
    return
  }
  if (isPointerTool()) {
    if (effectiveReadonly.value) return
    e.preventDefault()
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    tryDragAnnotation(e.clientX - rect.left, e.clientY - rect.top)
    return
  }
  if (effectiveReadonly.value || !isCustomTool()) return
  e.preventDefault()
  e.stopPropagation()

  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const px = e.clientX - rect.left
  const py = e.clientY - rect.top
  const pixel = canvasToPixel(px, py)

  if (props.tool === 'eraser') {
    eraseAt(pixel.x, pixel.y)
    return
  }

  // 先看是不是抓住了已有的框。放在新建之前判断：
  // 否则想挪一个框，反而会在它上面又画一个新的。
  if (!drawing.value && props.tool !== 'eraser' && tryDragAnnotation(px, py)) {
    return
  }

  if (props.tool === 'rect' || props.tool === 'pen' || props.tool === 'freehand') {
    drawing.value = true
    currentPoints.value = [pixel]
  } else if (props.tool === 'polygon') {
    if (!drawing.value) {
      drawing.value = true
      currentPoints.value = [pixel]
    } else if (nearFirstPoint(px, py)) {
      // 点回首点即闭合。此前只能靠双击，界面上没有任何提示，
      // 用户不知道怎么收尾
      finalizeAnnotation()
      return
    } else {
      currentPoints.value.push(pixel)
    }
  }
  redrawOverlay()
}

const onMouseMove = (e: MouseEvent) => {
  // 拖动由 window 监听处理，避免和这里各算一次位移
  if (dragging.value) return

  const box = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const kind = !drawing.value ? hoverKind(e.clientX - box.left, e.clientY - box.top) : null
  paintCursor(kind)

  // 视口相关变化时重绘 overlay
  if (!isCustomTool() && !isPointerTool() && enabled.value) {
    redrawOverlay()
    readViewport()
    return
  }
  if (locating() && props.locate?.method === 'circle' && drawing.value) {
    const pixel = canvasToPixel(e.clientX - box.left, e.clientY - box.top)
    if (currentPoints.value.length === 1) currentPoints.value.push(pixel)
    else currentPoints.value[1] = pixel
    redrawOverlay()
    return
  }
  if (isPointerTool()) return

  if (!drawing.value) return

  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const px = e.clientX - rect.left
  const py = e.clientY - rect.top
  const pixel = canvasToPixel(px, py)

  if (props.tool === 'rect') {
    if (currentPoints.value.length === 1) currentPoints.value.push(pixel)
    else currentPoints.value[1] = pixel
  } else if (props.tool === 'pen' || props.tool === 'freehand') {
    currentPoints.value.push(pixel)
  } else if (props.tool === 'polygon') {
    // 橡皮筋：让最后一段跟着光标走，用户才知道下一笔会落在哪。
    // 此前这里只是原样复制数组，等于什么都没做。
    hoverPoint.value = pixel
  }
  redrawOverlay()
}

const onContextMenu = (e: MouseEvent) => {
  e.preventDefault()
  if (effectiveReadonly.value) {
    markMenu.value = null
    return
  }
  const wrap = e.currentTarget as HTMLElement
  const bounds = wrap.getBoundingClientRect()
  const px = e.clientX - bounds.left
  const py = e.clientY - bounds.top
  const annIndex = hitBody(px, py)
  const measIndex = annIndex == null ? hitMeasurement(px, py) : null
  if (annIndex == null && measIndex == null) {
    markMenu.value = null
    return
  }
  const item = annIndex != null ? props.annotations[annIndex] : props.measurements[measIndex as number]
  const caption =
    annIndex != null
      ? markCaption(props.annotations, annIndex)
      : markCaption(props.measurements, measIndex as number)
  const menuW = 210
  const menuH = 86
  markMenu.value = {
    kind: annIndex != null ? 'annotation' : 'measurement',
    id: item.id,
    caption,
    x: Math.max(8, Math.min(px, bounds.width - menuW)),
    y: Math.max(8, Math.min(py, bounds.height - menuH))
  }
}

const removeMarked = () => {
  const menu = markMenu.value
  if (!menu) return
  if (menu.kind === 'annotation') {
    emit(
      'update:annotations',
      props.annotations.filter((a) => a.id !== menu.id)
    )
  } else {
    emit(
      'update:measurements',
      props.measurements.filter((m) => m.id !== menu.id)
    )
  }
  markMenu.value = null
}

const closeMarkMenu = (e: MouseEvent) => {
  if (!markMenu.value || !markMenuRef.value) return
  if (markMenuRef.value.contains(e.target as Node)) return
  markMenu.value = null
}

const onMouseUp = (e: MouseEvent) => {
  if (e.button !== 0) return
  if (locating() && props.locate?.method === 'circle') return
  if (dragging.value) {
    finishDrag()
    return
  }
  if (effectiveReadonly.value || !isCustomTool()) return
  if (props.tool === 'polygon') return // polygon 由双击结束
  if (!drawing.value) return

  finalizeAnnotation()
}

const onDoubleClick = (_e: MouseEvent) => {
  if (effectiveReadonly.value) return
  if (props.tool === 'polygon' && drawing.value) {
    finalizeAnnotation()
  }
}

const finalizeAnnotation = () => {
  if (currentPoints.value.length === 0) {
    drawing.value = false
    return
  }
  const tool = props.tool
  if (tool === 'rect' && currentPoints.value.length < 2) {
    drawing.value = false
    currentPoints.value = []
    return
  }
  if (tool === 'polygon' && currentPoints.value.length < 3) {
    drawing.value = false
    currentPoints.value = []
    return
  }

  const ann: AnnotationItem = {
    id: 'A_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
    tool: tool as any,
    points: currentPoints.value.slice(),
    label: currentLabel.value,
    color: colorOf(currentLabel.value),
    layer: 'primary'
  }
  emit('update:annotations', [...props.annotations, ann])
  drawing.value = false
  currentPoints.value = []
  hoverPoint.value = null
  redrawOverlay()
}

const eraseAt = (x: number, y: number) => {
  const HIT_R = 12
  const next = props.annotations.filter((a) => !pointHits(a, x, y, HIT_R))
  if (next.length !== props.annotations.length) {
    emit('update:annotations', next)
  } else {
    const next2 = props.measurements.filter((m) => !pointHits(m, x, y, HIT_R))
    if (next2.length !== props.measurements.length) {
      emit('update:measurements', next2)
    }
  }
}

const pointHits = (
  a: AnnotationItem,
  x: number,
  y: number,
  r: number
): boolean => {
  if (a.tool === 'quadrant') {
    const size = imgSize.value
    const code = (a.remark || '').split(':')[1] as QuadCode
    if (!size.w || !QUAD_LABEL[code]) return false
    const box = quadBounds(code, size.w, size.h, findingEye())
    return x >= box.x && x <= box.x + box.w && y >= box.y && y <= box.y + box.h
  }
  if (a.tool === 'point') {
    return a.points.some((p) => Math.hypot(p.x - x, p.y - y) <= r + 8)
  }
  if ((a.tool === 'rect' || a.tool === 'ellipse') && a.points.length >= 2) {
    const [p1, p2] = a.points
    const x1 = Math.min(p1.x, p2.x) - r
    const y1 = Math.min(p1.y, p2.y) - r
    const x2 = Math.max(p1.x, p2.x) + r
    const y2 = Math.max(p1.y, p2.y) + r
    return x >= x1 && x <= x2 && y >= y1 && y <= y2
  }
  return a.points.some((p) => Math.hypot(p.x - x, p.y - y) <= r)
}

/* =========================================================
 * cornerstone 内置工具的测量结果同步到我们的 measurements
 * ========================================================= */

/**
 * 把内置 Length / Angle 工具的结果同步成我们的 measurements。
 *
 * Cornerstone3D 的标注存的是世界坐标（handles.points），
 * 必须转回影像像素坐标再入库 —— 世界坐标依赖当前影像的
 * 原点与间距，换一张图就没有意义了。
 */
const worldToPixel = (world: number[]): { x: number; y: number } => {
  const id = viewport?.getCurrentImageId?.()
  if (!id || !cs) return { x: 0, y: 0 }
  const p = cs.utilities.worldToImageCoords(id, world)
  return p ? { x: p[0], y: p[1] } : { x: 0, y: 0 }
}

/** 已经同步给上层的测量 UID —— 用来区分「刚画的」和「上层删掉的」 */
let reportedUids = new Set<string>()

const syncCornerstoneMeasurements = () => {
  if (!elementRef.value || !csTools) return
  const getAnns = csTools.annotation?.state?.getAnnotations
  if (typeof getAnns !== 'function') return

  const measurements: AnnotationItem[] = []
  const pull = (toolName: string) => {
    try {
      return getAnns(toolName, elementRef.value) || []
    } catch {
      return []
    }
  }

  pull('Length').forEach((a: any, i: number) => {
    const pts = a?.data?.handles?.points
    if (!pts || pts.length < 2) return
    const p0 = worldToPixel(pts[0])
    const p1 = worldToPixel(pts[1])
    measurements.push({
      id: a.annotationUID || `L_${i}`,
      tool: 'length',
      points: [p0, p1],
      label: '距离',
      color: '#52c41a',
      layer: 'primary',
      // 眼底照没有真实物理间距，一律按像素报，不冒充毫米
      value: Math.hypot(p1.x - p0.x, p1.y - p0.y),
      unit: 'px'
    })
  })

  pull('Angle').forEach((a: any, i: number) => {
    const pts = a?.data?.handles?.points
    if (!pts || pts.length < 3) return
    const p = pts.slice(0, 3).map(worldToPixel)
    const v1 = { x: p[0].x - p[1].x, y: p[0].y - p[1].y }
    const v2 = { x: p[2].x - p[1].x, y: p[2].y - p[1].y }
    const dot = v1.x * v2.x + v1.y * v2.y
    const mag = Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y)
    const deg = mag ? (Math.acos(Math.max(-1, Math.min(1, dot / mag))) * 180) / Math.PI : 0
    measurements.push({
      id: a.annotationUID || `A_${i}`,
      tool: 'angle',
      points: p,
      label: '角度',
      color: '#52c41a',
      layer: 'primary',
      value: deg,
      unit: '°'
    })
  })

  reportedUids = new Set(measurements.map((m) => m.id))

  if (measurements.length !== props.measurements.length) {
    emit('update:measurements', measurements)
  }
}


/**
 * 上层把某条测量从数组里删掉之后，Cornerstone 内部的 Length / Angle 标注状态还在，
 * 下一次 IMAGE_RENDERED 会被 syncCornerstoneMeasurements 原样回填 —— 表现就是
 * 「右下角列表删了、橡皮擦了、撤销了，线都还在，刷新浏览器才消失」。
 * 这里按 UID 把内部状态一并删掉。
 *
 * 只删「曾经同步上去、现在不见了」的那些：刚画完还没来得及 sync 的新标注不在
 * reportedUids 里，不能误伤。
 */
const pruneRemovedToolAnnotations = () => {
  const state = csTools?.annotation?.state
  if (!state || !elementRef.value || reportedUids.size === 0) return

  const kept = new Set(props.measurements.map((m) => m.id))
  let removed = false
  for (const uid of reportedUids) {
    if (kept.has(uid)) continue
    try {
      state.removeAnnotation(uid)
      removed = true
    } catch {
      /* ignore */
    }
  }
  if (!removed) return

  reportedUids = new Set([...reportedUids].filter((u) => kept.has(u)))
  try {
    viewport?.render()
  } catch {
    /* ignore */
  }
  redrawOverlay()
}

/* =========================================================
 * 对外暴露：清空全部标注 / 测量（含内置工具的标注状态）
 * 父组件「清空」按钮调用，避免 Length / Angle 留在 toolStateManager
 * 中被 syncCornerstoneMeasurements 重新回填。
 * ========================================================= */

const clearAllTools = () => {
  // 1. 清掉内置工具（Length / Angle）留在标注状态里的记录。
  //    不清的话，下一次 IMAGE_RENDERED 会把它们重新同步回 measurements，
  //    表现为「清空了又自己长回来」。
  try {
    const state = csTools?.annotation?.state
    if (state && elementRef.value) {
      for (const toolName of ['Length', 'Angle']) {
        const list = state.getAnnotations?.(toolName, elementRef.value) || []
        // 边删边遍历会漏，先拷一份
        for (const a of [...list]) {
          if (a?.annotationUID) state.removeAnnotation(a.annotationUID)
        }
      }
    }
  } catch {
    /* ignore */
  }

  // 2. 重置自定义 overlay 的临时绘制状态
  reportedUids = new Set()
  drawing.value = false
  currentPoints.value = []

  // 3. 立即重绘，让画布上残留的尺标/标注消失
  try {
    viewport?.render()
  } catch {
    /* ignore */
  }
  redrawOverlay()
}

defineExpose({ clearAllTools, releaseViewport })

/* =========================================================
 * 事件监听 / watch
 * ========================================================= */

const onCsRendered = () => {
  redrawOverlay()
  readViewport()
  syncCornerstoneMeasurements()
}

const onResize = () => {
  if (!enabled.value) return
  try {
    renderingEngine?.resize(true, false)
  } catch {
    /* ignore */
  }
  syncOverlaySize()
  redrawOverlay()
}

let resizeObserver: ResizeObserver | null = null
/** Cornerstone3D 的渲染完成事件名，init 之后才拿得到 */
let renderedEventName = ''

onMounted(async () => {
  try {
    await enableElement()
  } catch (err) {
    emit('error', err)
    ElMessage.error('阅片内核初始化失败')
    return
  }

  if (elementRef.value && cs) {
    renderedEventName = cs.Enums.Events.IMAGE_RENDERED
    elementRef.value.addEventListener(renderedEventName, onCsRendered)
  }
  setActiveCornerstoneTool(props.tool)
  paintCursor(null)
  syncOverlaySize()

  if (props.dicomImageId || props.imageUrl) {
    await loadImage(props.imageUrl)
  }

  resizeObserver = new ResizeObserver(onResize)
  if (elementRef.value) resizeObserver.observe(elementRef.value)
  window.addEventListener('mousedown', closeMarkMenu)

  refreshSegmentMasks()
})

onBeforeUnmount(() => {
  finishDrag()
  window.removeEventListener('mousedown', closeMarkMenu)
  window.removeEventListener('mouseup', finishCircle)
  if (resizeObserver) resizeObserver.disconnect()
  if (elementRef.value && renderedEventName) {
    elementRef.value.removeEventListener(renderedEventName, onCsRendered)
  }
  disableElement()
})

watch(
  () => props.locate?.code + (props.locate?.method || ''),
  () => redrawOverlay()
)

watch(
  () => [props.imageUrl, props.dicomImageId],
  ([nextUrl, nextDicom]) => {
    if (nextUrl || nextDicom) loadImage(nextUrl as string)
  }
)

watch(
  () => [props.segmentation?.sopInstanceUid, effectiveLayers.value.gold],
  () => refreshSegmentMasks()
)

const loadOverlay = (
  url: string,
  target: { value: HTMLImageElement | null }
) => {
  target.value = null
  if (!url) {
    redrawOverlay()
    return
  }
  const img = new Image()
  img.onload = () => {
    target.value = img
    redrawOverlay()
  }
  img.onerror = () => {
    target.value = null
    redrawOverlay()
  }
  img.src = url
}

watch(
  () => props.goldOverlayUrl,
  (url) => loadOverlay(url || '', goldOverlay),
  { immediate: true }
)

watch(
  () => props.heatmapOverlayUrl,
  (url) => loadOverlay(url || '', heatmapOverlay),
  { immediate: true }
)

watch(
  () => props.lesionSegUrl,
  (url) => loadOverlay(url || '', lesionSegOverlay),
  { immediate: true }
)

watch(
  () => props.tool,
  (t) => {
    setActiveCornerstoneTool(t)
    drawing.value = false
    currentPoints.value = []
    paintCursor(null)
    redrawOverlay()
  }
)

watch(
  () => props.viewport,
  () => {
    applyViewport()
    redrawOverlay()
  },
  { deep: true }
)

watch(
  () => [props.annotations, props.measurements, effectiveLayers.value, props.goldAnnotations, props.goldOverlayUrl, props.heatmapOverlayUrl, props.lesionSegUrl, props.highlightId, markMenu.value?.id],
  () => redrawOverlay(),
  { deep: true }
)

// 上层删掉测量后，把 Cornerstone 内部对应的 Length / Angle 标注也删掉，
// 否则下一帧就被回填回来。只看 id 列表，避免 deep 比较的开销。
watch(
  () => props.measurements.map((m) => m.id).join('|'),
  () => pruneRemovedToolAnnotations()
)
</script>

<template>
  <div class="canvas-wrap" @contextmenu="onContextMenu">
    <!-- Cornerstone 视口 -->
    <div
      ref="elementRef"
      class="cs-element"
      :class="{ 'is-off': !effectiveLayers.primary }"
      @contextmenu.prevent
      @mousemove="onMouseMove"
    />
    <!-- 自定义 overlay 用于矩形/多边形/手绘/擦除；指针工具也接管，才能画出看得见的箭头 -->
    <canvas
      ref="overlayRef"
      class="overlay"
      :style="{ pointerEvents: isCustomTool() || isPointerTool() || locating() ? 'auto' : 'none' }"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @dblclick="onDoubleClick"
    />

    <!-- 病灶名称一直放在图上。不必先点「手绘」，点名称就能开始标这一处。 -->
    <div v-if="!effectiveReadonly" class="label-picker">
      <span class="picker-title">病灶：</span>
      <button
        v-for="l in LESION_LABELS"
        :key="l.value"
        class="picker-chip"
        :class="{ active: currentLabel === l.value }"
        :style="{ '--c': l.color } as any"
        @click="chooseLesionLabel(l.value)"
      >
        {{ l.label }}
      </button>
    </div>

    <div v-if="loading" class="loader">影像加载中…</div>

    <div
      v-if="markMenu"
      ref="markMenuRef"
      class="mark-menu"
      :style="{ left: markMenu.x + 'px', top: markMenu.y + 'px' }"
      @mousedown.stop
      @contextmenu.prevent
    >
      <div class="mark-menu-title">{{ markMenu.caption }}</div>
      <button type="button" class="mark-menu-del" @click="removeMarked">删除</button>
    </div>
  </div>
</template>

<style scoped>
.canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #000;
}
.cs-element {
  position: absolute;
  inset: 0;
  background: #000;
}
.cs-element.is-off {
  opacity: 0;
}
.overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
}
.loader {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #c9cdd4;
  font-size: 13px;
  background: rgba(0, 0, 0, 0.6);
  padding: 8px 16px;
  border-radius: 6px;
}

.mark-menu {
  position: absolute;
  z-index: 8;
  min-width: 168px;
  padding: 8px;
  border-radius: 8px;
  background: #1c1f27;
  border: 1px solid #5c6574;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
}
.mark-menu-title {
  color: #f2f4f8;
  font-size: 13px;
  font-weight: 650;
  margin-bottom: 8px;
}
.mark-menu-del {
  width: 100%;
  border: 0;
  border-radius: 6px;
  background: #a61d24;
  color: #fff;
  font-size: 13px;
  padding: 6px 10px;
  cursor: pointer;
}
.mark-menu-del:hover {
  background: #d4380d;
}

.label-picker {
  position: absolute;
  z-index: 4;
  top: 14px;
  right: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  background: rgba(20, 20, 24, 0.85);
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #2a2a2a;
  backdrop-filter: blur(8px);
  max-width: 360px;
}
.picker-title {
  font-size: 12px;
  color: #c9cdd4;
  margin-right: 4px;
}
.picker-chip {
  background: transparent;
  color: var(--c, #4091ff);
  border: 1px solid var(--c, #4091ff);
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 12px;
  cursor: pointer;
}
.picker-chip.active {
  background: var(--c, #4091ff);
  color: #fff;
}
</style>
