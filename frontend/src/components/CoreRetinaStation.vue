<script setup lang="ts">
/**
 * CoreRetinaStation 共享影像画布
 *
 * 阅片 / 练习 / 教学查看 三端共用的唯一影像画布。
 * 新增 `mode` 用于在阅片 / 练习 / 教学查看 三种场景下复用：
 *
 *   - reading       默认。教师/管理员阅片标注
 *   - practice      学员练习模式：强制隐藏金标准（提交前不能偷看）
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
import { LESION_LABELS } from '@/views/reading/types'

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
     * DICOM SEG 病灶分割。金标准若是像素级分割，用它比矢量框精确得多；
     * 同样受 layers.gold 控制，练习模式下强制不显示。
     */
    segmentation?: {
      sopInstanceUid: string
      segments: Array<{ number: number; label: string }>
    } | null
  }>(),
  {
    mode: 'reading',
    dicomImageId: '',
    goldAnnotations: () => [],
    segmentation: null
  }
)

const emit = defineEmits<{
  (e: 'update:annotations', v: AnnotationItem[]): void
  (e: 'update:measurements', v: AnnotationItem[]): void
  (e: 'update:viewport', v: ViewportState): void
  (e: 'ready'): void
  (e: 'error', err: any): void
}>()

/** mode 派生的有效 readonly：teaching-view 强制 readonly */
const effectiveReadonly = computed(() => props.readonly || props.mode === 'teaching-view')

/** mode 派生的有效 layers：practice 模式下强制隐藏金标准 */
const effectiveLayers = computed<LayerState>(() => {
  if (props.mode === 'practice') {
    return { ...props.layers, gold: false }
  }
  return props.layers
})

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

const disableElement = () => {
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
  renderingEngine = null
  viewport = null
  toolGroup = null
  enabled.value = false
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
const HANDLE_RADIUS = 8
const dragging = ref<{ annIndex: number; ptIndex: number } | null>(null)

/** 命中哪个标注的哪个顶点。倒序遍历：后画的在上层，应优先抓到 */
const hitHandle = (px: number, py: number) => {
  const list = props.annotations
  for (let i = list.length - 1; i >= 0; i--) {
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

/** 光标是否落在首点附近（屏幕距离），用于「点回首点闭合」 */
const CLOSE_RADIUS = 10
const nearFirstPoint = (px: number, py: number): boolean => {
  if (currentPoints.value.length < 3) return false
  const first = pixelToCanvas(currentPoints.value[0].x, currentPoints.value[0].y)
  return Math.hypot(first.x - px, first.y - py) <= CLOSE_RADIUS
}
const currentLabel = ref(LESION_LABELS[0].value)

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

  // 金标准分割掩码：像素级，画在矢量标注之下
  if (effectiveLayers.value.gold && segmentMasks.value.length > 0) {
    drawSegmentMasks(ctx)
  }

  // 金标准图层（专家标注）
  if (effectiveLayers.value.gold && props.goldAnnotations.length > 0) {
    props.goldAnnotations.forEach((g) => drawGoldAnnotation(ctx, g))
  }

  // 已落地的标注
  if (effectiveLayers.value.my) {
    props.annotations.forEach((a) => drawAnnotation(ctx, a))
    // 只画 Cornerstone3D 自己没在画的那些测量。
    //
    // 内置 Length / Angle 工具会自行渲染手柄与数值；overlay 若再画一遍，
    // 一条测量就有两套端点，看起来像「点一次出现两个点」。
    // 但从数据库恢复的历史测量并不在 Cornerstone3D 的标注状态里，
    // 那些仍然要由 overlay 负责画出来。
    const live = liveAnnotationUids()
    props.measurements.forEach((m) => {
      if (!live.has(m.id)) drawMeasurement(ctx, m)
    })
  }

  // 正在绘制的临时图形
  if (drawing.value && currentPoints.value.length > 0) {
    const tmp: AnnotationItem = {
      id: '_tmp',
      tool: props.tool === 'eraser' ? 'rect' : props.tool === 'pan' ? 'rect' : (props.tool as any),
      // 多边形把光标位置作为临时末点，形成跟随鼠标的橡皮筋
      points:
        props.tool === 'polygon' && hoverPoint.value
          ? [...currentPoints.value, hoverPoint.value]
          : currentPoints.value,
      label: currentLabel.value,
      color: colorOf(currentLabel.value),
      layer: 'primary'
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

const drawAnnotation = (
  ctx: CanvasRenderingContext2D,
  ann: AnnotationItem,
  preview = false
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

  if (!preview && pts.length > 0 && ann.label) {
    ctx.fillStyle = color
    ctx.font = '12px sans-serif'
    ctx.fillText(ann.label, pts[0].x + 4, pts[0].y - 4)
  }
}

/* =========================================================
 * 金标准分割掩码
 * ========================================================= */

const segmentMasks = ref<SegmentMask[]>([])
const segmentError = ref('')

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
  // 练习模式强制隐藏金标准，连取都不该取——
  // 请求本身会留在浏览器网络面板里，等于把答案递出去了
  if (!seg?.sopInstanceUid || props.mode === 'practice') {
    segmentMasks.value = []
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

const drawMeasurement = (ctx: CanvasRenderingContext2D, m: AnnotationItem) => {
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
}

/* =========================================================
 * 鼠标事件 — 自定义工具
 * ========================================================= */

const customTools: ToolName[] = ['rect', 'polygon', 'freehand', 'pen', 'eraser']
const isCustomTool = () => customTools.includes(props.tool)

const onMouseDown = (e: MouseEvent) => {
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

  // 先看是不是抓住了已有图形的顶点。放在新建之前判断：
  // 否则想调整一个框，反而会在它上面又画一个新的。
  if (!drawing.value) {
    const hit = hitHandle(px, py)
    if (hit) {
      dragging.value = hit
      return
    }
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
  // 顶点拖拽优先于其它一切
  if (dragging.value) {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const pixel = canvasToPixel(e.clientX - rect.left, e.clientY - rect.top)
    const next = props.annotations.map((a, i) => {
      if (i !== dragging.value!.annIndex) return a
      const pts = a.points.slice()
      pts[dragging.value!.ptIndex] = pixel
      return { ...a, points: pts }
    })
    emit('update:annotations', next)
    redrawOverlay()
    return
  }

  // 视口相关变化时重绘 overlay
  if (!isCustomTool() && enabled.value) {
    redrawOverlay()
    readViewport()
    return
  }
  // 悬停在顶点上给出可抓取的光标：没有这个提示，用户不会想到能拖
  if (!drawing.value && overlayRef.value) {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
    overlayRef.value.style.cursor =
      hitHandle(e.clientX - r.left, e.clientY - r.top) ? 'grab' : ''
  }

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

const onMouseUp = (_e: MouseEvent) => {
  if (dragging.value) {
    dragging.value = null
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
  if (a.tool === 'rect' && a.points.length >= 2) {
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

defineExpose({ clearAllTools })

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
  syncOverlaySize()

  if (props.dicomImageId || props.imageUrl) {
    await loadImage(props.imageUrl)
  }

  resizeObserver = new ResizeObserver(onResize)
  if (elementRef.value) resizeObserver.observe(elementRef.value)

  refreshSegmentMasks()
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
  if (elementRef.value && renderedEventName) {
    elementRef.value.removeEventListener(renderedEventName, onCsRendered)
  }
  disableElement()
})

watch(
  () => [props.imageUrl, props.dicomImageId],
  ([nextUrl, nextDicom]) => {
    if (nextUrl || nextDicom) loadImage(nextUrl as string)
  }
)

watch(
  () => [props.segmentation?.sopInstanceUid, props.mode],
  () => refreshSegmentMasks()
)

watch(
  () => props.tool,
  (t) => {
    setActiveCornerstoneTool(t)
    drawing.value = false
    currentPoints.value = []
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
  () => [props.annotations, props.measurements, effectiveLayers.value, props.goldAnnotations],
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
  <div class="canvas-wrap">
    <!-- Cornerstone 视口 -->
    <div
      ref="elementRef"
      class="cs-element"
      @contextmenu.prevent
      @mousemove="onMouseMove"
    />
    <!-- 自定义 overlay 用于矩形/多边形/手绘/擦除 -->
    <canvas
      ref="overlayRef"
      class="overlay"
      :style="{ pointerEvents: isCustomTool() ? 'auto' : 'none' }"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @dblclick="onDoubleClick"
    />

    <!-- 标签选择浮窗 -->
    <div v-if="!readonly && isCustomTool()" class="label-picker">
      <span class="picker-title">病灶标签：</span>
      <button
        v-for="l in LESION_LABELS"
        :key="l.value"
        class="picker-chip"
        :class="{ active: currentLabel === l.value }"
        :style="{ '--c': l.color } as any"
        @click="currentLabel = l.value"
      >
        {{ l.label }}
      </button>
    </div>

    <div v-if="loading" class="loader">影像加载中…</div>
  </div>
</template>

<style scoped>
.canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.cs-element {
  position: absolute;
  inset: 0;
  background: #000;
}
.overlay {
  position: absolute;
  inset: 0;
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

.label-picker {
  position: absolute;
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
