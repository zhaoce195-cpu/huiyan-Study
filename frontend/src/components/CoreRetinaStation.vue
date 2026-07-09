<script setup lang="ts">
/**
 * CoreRetinaStation 共享影像画布
 *
 * 由原 views/reading/components/ReadingCanvas.vue 升格为公共组件。
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
  cornerstone,
  cornerstoneTools,
  ensureCornerstone,
  toImageId
} from '@/utils/cornerstone'
import type { AnnotationItem, LayerState, ToolName, ViewportState } from '@/views/reading/types'
import { LESION_LABELS } from '@/views/reading/types'

export type RetinaMode = 'reading' | 'practice' | 'teaching-view'

const props = withDefaults(
  defineProps<{
    /** 模式：reading（默认）/ practice / teaching-view */
    mode?: RetinaMode
    imageUrl: string
    tool: ToolName
    annotations: AnnotationItem[]
    measurements: AnnotationItem[]
    viewport: ViewportState
    layers: LayerState
    readonly: boolean
    /** 金标准（专家）标注，仅 layers.gold = true 时显示 */
    goldAnnotations?: AnnotationItem[]
  }>(),
  {
    mode: 'reading',
    goldAnnotations: () => []
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
 * Cornerstone 初始化
 * ========================================================= */

const enableElement = () => {
  if (!elementRef.value || enabled.value) return
  cornerstone.enable(elementRef.value, { renderer: 'canvas' })
  registerCornerstoneTools()
  enabled.value = true
}

const disableElement = () => {
  if (!elementRef.value || !enabled.value) return
  try {
    cornerstone.disable(elementRef.value)
  } catch {
    /* ignore */
  }
  enabled.value = false
}

/* 注册工具：内置 cornerstone-tools 工具用于 平移/缩放/窗宽窗位/距离/角度 */
const registerCornerstoneTools = () => {
  if (!elementRef.value) return

  cornerstoneTools.addTool(cornerstoneTools.PanTool)
  cornerstoneTools.addTool(cornerstoneTools.ZoomTool)
  cornerstoneTools.addTool(cornerstoneTools.ZoomMouseWheelTool)
  cornerstoneTools.addTool(cornerstoneTools.WwwcTool)
  cornerstoneTools.addTool(cornerstoneTools.LengthTool)
  cornerstoneTools.addTool(cornerstoneTools.AngleTool)

  // 滚轮缩放始终激活
  cornerstoneTools.setToolActive('ZoomMouseWheel', {})
}

/* =========================================================
 * 加载影像
 * ========================================================= */

let loadSeq = 0

const loadImage = async (url: string) => {
  if (!elementRef.value) return
  if (!url) {
    emit('error', new Error('影像 URL 为空'))
    ElMessage.warning('该病例暂无影像数据')
    return
  }
  // 不是 http(s) / data: / blob: 也得提示
  const imageId = toImageId(url)
  if (!/^https?:|^data:|^blob:/i.test(imageId)) {
    emit('error', new Error(`不支持的影像协议：${imageId}`))
    ElMessage.error(`不支持的影像协议：${url}`)
    return
  }

  const seq = ++loadSeq
  loading.value = true
  try {
    const image = await cornerstone.loadAndCacheImage(imageId)
    // 期间用户切换了图片 → 丢弃过期结果
    if (seq !== loadSeq || !elementRef.value) return
    imgSize.value = { w: image.width || 1024, h: image.height || 1024 }
    cornerstone.displayImage(elementRef.value, image)
    applyViewport()
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
    else if (err?.error === 'NetworkError') reason = '网络异常，无法加载影像'
    emit('error', err)
    ElMessage.error(reason)
    console.warn('[ReadingCanvas] loadImage failed:', { imageId, err })
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

const applyViewport = () => {
  if (!elementRef.value || !enabled.value) return
  try {
    const v = cornerstone.getViewport(elementRef.value)
    if (!v) return
    v.scale = props.viewport.scale || 1
    v.translation = { x: props.viewport.x || 0, y: props.viewport.y || 0 }
    v.voi = {
      windowWidth: props.viewport.ww || 255,
      windowCenter: props.viewport.wl || 127
    }
    v.invert = !!props.viewport.invert
    cornerstone.setViewport(elementRef.value, v)
  } catch {
    /* ignore */
  }
}

const readViewport = () => {
  if (!elementRef.value) return
  try {
    const v = cornerstone.getViewport(elementRef.value)
    if (!v) return
    emit('update:viewport', {
      scale: v.scale || 1,
      x: v.translation?.x || 0,
      y: v.translation?.y || 0,
      ww: v.voi?.windowWidth || 255,
      wl: v.voi?.windowCenter || 127,
      invert: !!v.invert
    })
  } catch {
    /* ignore */
  }
}

/* =========================================================
 * 工具切换
 * ========================================================= */

const setActiveCornerstoneTool = (t: ToolName) => {
  // 关闭可能激活的内置工具
  ;['Pan', 'Zoom', 'Wwwc', 'Length', 'Angle'].forEach((name) => {
    try {
      cornerstoneTools.setToolPassive(name)
    } catch {
      /* ignore */
    }
  })

  if (t === 'pan') cornerstoneTools.setToolActive('Pan', { mouseButtonMask: 1 })
  else if (t === 'zoom') cornerstoneTools.setToolActive('Zoom', { mouseButtonMask: 1 })
  else if (t === 'wwwc') cornerstoneTools.setToolActive('Wwwc', { mouseButtonMask: 1 })
  else if (t === 'length') cornerstoneTools.setToolActive('Length', { mouseButtonMask: 1 })
  else if (t === 'angle') cornerstoneTools.setToolActive('Angle', { mouseButtonMask: 1 })
  else {
    // 自定义标注工具下，左键交给 overlay 画布；其他 cornerstone 工具进 passive
    cornerstoneTools.setToolPassive('Pan')
  }
}

/* =========================================================
 * 自定义 overlay：rect/polygon/freehand/pen/eraser
 * ========================================================= */

const drawing = ref(false)
const currentPoints = ref<{ x: number; y: number }[]>([])
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

const pixelToCanvas = (x: number, y: number) => {
  if (!elementRef.value) return { x, y }
  try {
    return cornerstone.pixelToCanvas(elementRef.value, { x, y })
  } catch {
    return { x, y }
  }
}

const canvasToPixel = (x: number, y: number) => {
  if (!elementRef.value) return { x, y }
  try {
    return cornerstone.pageToPixel(
      elementRef.value,
      x + elementRef.value.getBoundingClientRect().left,
      y + elementRef.value.getBoundingClientRect().top
    )
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

  // 金标准图层（专家标注）
  if (effectiveLayers.value.gold && props.goldAnnotations.length > 0) {
    props.goldAnnotations.forEach((g) => drawGoldAnnotation(ctx, g))
  }

  // 已落地的标注
  if (effectiveLayers.value.my) {
    props.annotations.forEach((a) => drawAnnotation(ctx, a))
    props.measurements.forEach((m) => drawMeasurement(ctx, m))
  }

  // 正在绘制的临时图形
  if (drawing.value && currentPoints.value.length > 0) {
    const tmp: AnnotationItem = {
      id: '_tmp',
      tool: props.tool === 'eraser' ? 'rect' : props.tool === 'pan' ? 'rect' : (props.tool as any),
      points: currentPoints.value,
      label: currentLabel.value,
      color: colorOf(currentLabel.value),
      layer: 'primary'
    }
    drawAnnotation(ctx, tmp, true)
  }
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
    if (pts.length < 2) return
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
  } else if (ann.tool === 'polygon' || ann.tool === 'pen' || ann.tool === 'freehand') {
    ctx.beginPath()
    ctx.moveTo(pts[0].x, pts[0].y)
    pts.slice(1).forEach((p) => ctx.lineTo(p.x, p.y))
    if (ann.tool === 'polygon' && !preview) {
      ctx.closePath()
      ctx.fill()
    }
    ctx.stroke()
  }

  if (!preview && pts.length > 0 && ann.label) {
    ctx.fillStyle = color
    ctx.font = '12px sans-serif'
    ctx.fillText(ann.label, pts[0].x + 4, pts[0].y - 4)
  }
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

  if (props.tool === 'rect' || props.tool === 'pen' || props.tool === 'freehand') {
    drawing.value = true
    currentPoints.value = [pixel]
  } else if (props.tool === 'polygon') {
    if (!drawing.value) {
      drawing.value = true
      currentPoints.value = [pixel]
    } else {
      currentPoints.value.push(pixel)
    }
  }
  redrawOverlay()
}

const onMouseMove = (e: MouseEvent) => {
  // 视口相关变化时重绘 overlay
  if (!isCustomTool() && enabled.value) {
    redrawOverlay()
    readViewport()
    return
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
    // 多边形预览跟随鼠标
    if (currentPoints.value.length >= 1) {
      currentPoints.value = [...currentPoints.value]
      // 不入栈，只重绘
    }
  }
  redrawOverlay()
}

const onMouseUp = (_e: MouseEvent) => {
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

const syncCornerstoneMeasurements = () => {
  if (!elementRef.value) return
  const lengthState = cornerstoneTools.getToolState(elementRef.value, 'Length')
  const angleState = cornerstoneTools.getToolState(elementRef.value, 'Angle')

  const measurements: AnnotationItem[] = []

  if (lengthState && Array.isArray(lengthState.data)) {
    lengthState.data.forEach((d: any, i: number) => {
      const start = d.handles?.start
      const end = d.handles?.end
      if (!start || !end) return
      measurements.push({
        id: `L_${i}`,
        tool: 'length',
        points: [
          { x: start.x, y: start.y },
          { x: end.x, y: end.y }
        ],
        label: '距离',
        color: '#52c41a',
        layer: 'primary',
        value: d.length || Math.hypot(end.x - start.x, end.y - start.y),
        unit: 'px'
      })
    })
  }

  if (angleState && Array.isArray(angleState.data)) {
    angleState.data.forEach((d: any, i: number) => {
      const s = d.handles?.start
      const m = d.handles?.middle
      const e = d.handles?.end
      if (!s || !m || !e) return
      measurements.push({
        id: `A_${i}`,
        tool: 'angle',
        points: [
          { x: s.x, y: s.y },
          { x: m.x, y: m.y },
          { x: e.x, y: e.y }
        ],
        label: '角度',
        color: '#52c41a',
        layer: 'primary',
        value: d.rAngle || 0,
        unit: '°'
      })
    })
  }

  if (measurements.length !== props.measurements.length) {
    emit('update:measurements', measurements)
  }
}

/* =========================================================
 * 对外暴露：清空全部标注 / 测量（含 cornerstone-tools 内部状态）
 * 父组件「清空」按钮调用，避免 Length / Angle 留在 toolStateManager
 * 中被 syncCornerstoneMeasurements 重新回填。
 * ========================================================= */

const clearAllTools = () => {
  if (!elementRef.value) return
  // 1. 清掉 cornerstone-tools 自带工具（Length / Angle）的所有 measurement
  ;['Length', 'Angle'].forEach((toolName) => {
    try {
      const stateManager =
        cornerstoneTools.getElementToolStateManager?.(elementRef.value)
      stateManager?.clear?.(elementRef.value)
    } catch {
      /* 某些版本无 stateManager.clear；走兜底 */
    }
    try {
      const st = cornerstoneTools.getToolState(elementRef.value, toolName)
      if (st && Array.isArray(st.data)) {
        st.data.length = 0
      }
    } catch {
      /* ignore */
    }
  })

  // 2. 重置自定义 overlay 的临时绘制状态
  drawing.value = false
  currentPoints.value = []

  // 3. 触发一次重绘，让画布上残留的尺标/标注立即消失
  try {
    cornerstone.updateImage(elementRef.value)
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
  if (!elementRef.value || !enabled.value) return
  cornerstone.resize(elementRef.value, false)
  syncOverlaySize()
  redrawOverlay()
}

let resizeObserver: ResizeObserver | null = null

onMounted(async () => {
  ensureCornerstone()
  enableElement()
  if (elementRef.value) {
    elementRef.value.addEventListener('cornerstoneimagerendered', onCsRendered)
  }
  setActiveCornerstoneTool(props.tool)
  syncOverlaySize()

  if (props.imageUrl) {
    await loadImage(props.imageUrl)
  }

  resizeObserver = new ResizeObserver(onResize)
  if (elementRef.value) resizeObserver.observe(elementRef.value)
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
  if (elementRef.value) {
    elementRef.value.removeEventListener('cornerstoneimagerendered', onCsRendered)
  }
  disableElement()
})

watch(
  () => props.imageUrl,
  (next) => {
    if (next) loadImage(next)
  }
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
