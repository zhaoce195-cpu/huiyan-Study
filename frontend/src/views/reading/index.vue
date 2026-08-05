<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Document, ArrowLeft, ArrowRight, MagicStick } from '@element-plus/icons-vue'

import { LoginApi, ReadingApi } from '@/api'
import { getCaseBrowseList } from '@/api/case-browse'
import {
  buildAnswerSummary,
  newRequestId,
  submitWithRetry,
  summaryHtml
} from '@/utils/submit-guard'
import { wadorsImageId } from '@/utils/cornerstone3d'
import { useUserStore } from '@/stores/user'

import ReadingToolbar from './components/ReadingToolbar.vue'
import CoreRetinaStation from '@/components/CoreRetinaStation.vue'
import ReadingSidePanel from './components/ReadingSidePanel.vue'
import ReadingSubmitDialog from './components/ReadingSubmitDialog.vue'
import ReadingSafetyBar from './components/ReadingSafetyBar.vue'
import NoteEditDialog from '@/views/learning/components/NoteEditDialog.vue'
import AiDiagnosisDialog from '@/components/AiDiagnosisDialog.vue'
import type {
  ToolName,
  CanvasState,
  AnnotationItem
} from './types'

type FrontRole = LoginApi.FrontRole
type ImageSource = ReadingApi.ImageSource
type ReadingRecord = ReadingApi.ReadingRecord

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/* ========== 角色 ========== */
const currentRole = computed<FrontRole | ''>(() => userStore.role)

const isTeacher = computed(() => currentRole.value === 'doctor')
const isAdmin = computed(() => currentRole.value === 'admin')
const canAnnotate = computed(() => true) // 学员可练习；教师/管理员同样可创建参考
const canReview = computed(() => isTeacher.value || isAdmin.value)

/* ========== 路由参数 ========== */
const caseId = computed(() => Number(route.query.caseId || 0))
const recordId = computed(() => Number(route.query.recordId || 0))

const missingCaseId = computed(() => !caseId.value && !recordId.value)

/* ========== 病例快速切换 ========== */
const caseList = ref<{ id: number; caseNo: string; title: string }[]>([])
const curIdx = computed(() =>
  caseList.value.findIndex((c) => c.id === caseId.value)
)
const loadCaseList = async () => {
  try {
    const res: any = await getCaseBrowseList({ page: 1, pageSize: 100 })
    caseList.value = (res?.list || []).map((c: any) => ({
      id: c.id,
      caseNo: c.caseNo || c.case_no || String(c.id),
      title: c.title || ''
    }))
  } catch {
    caseList.value = []
  }
}
const gotoCaseByIndex = (idx: number) => {
  if (idx < 0 || idx >= caseList.value.length) return
  const target = caseList.value[idx]
  if (!target || target.id === caseId.value) return
  const q: any = { ...route.query, caseId: target.id }
  delete q.recordId
  router.replace({ query: q })
}
const onSelectCase = (id: number) => {
  const q: any = { ...route.query, caseId: id }
  delete q.recordId
  router.replace({ query: q })
}

/* ========== 影像源 ========== */
const sourceLoading = ref(false)
const source = ref<ImageSource | null>(null)
const currentImageIndex = ref(0)

/* ===== 多 role tabs（一对多影像扩展） ===== */
const ROLE_LABEL: Record<string, string> = {
  original: '原图',
  MA: '微血管瘤',
  HE: '出血',
  EX: '硬性渗出',
  SE: '软性渗出',
  OD: '视盘',
  color_mask: '彩色 mask',
  overlay: '金标准叠加',
  class_mask: '类别 mask',
  other: '其它'
}
const ROLE_ORDER = [
  'original', 'MA', 'HE', 'EX', 'SE', 'OD',
  'color_mask', 'overlay', 'other'
]
const currentImageRole = ref<string>('original')
const availableRoles = computed<string[]>(() => {
  const groups = source.value?.imageGroups || {}
  return ROLE_ORDER.filter((r) => Array.isArray((groups as any)[r]) && (groups as any)[r].length > 0)
})
const currentRoleImages = computed<string[]>(() => {
  const groups = source.value?.imageGroups || {}
  const arr = (groups as any)[currentImageRole.value]
  if (Array.isArray(arr) && arr.length > 0) return arr
  // 回退到一维 images（与旧客户端一致）
  return source.value?.images || []
})
const currentImage = computed(() => currentRoleImages.value[currentImageIndex.value] || '')

watch(availableRoles, (roles) => {
  if (roles.length === 0) return
  if (!roles.includes(currentImageRole.value)) {
    currentImageRole.value = roles[0]
    currentImageIndex.value = 0
  }
})

const onChangeRole = (r: string) => {
  currentImageRole.value = r
  currentImageIndex.value = 0
  canvasState.annotations = []
  canvasState.measurements = []
  canvasState.history = []
  canvasState.redoStack = []
}


/** 当前影像在 PACS 中的 DICOM id；未进 PACS 的病例为空，画布自动退回 JPG */
const currentDicomImageId = computed(() => {
  const hit = source.value?.dicomInstances?.[currentImage.value]
  if (!hit) return ''
  return wadorsImageId(
    hit.studyInstanceUid,
    hit.seriesInstanceUid,
    hit.sopInstanceUid
  )
})

/* ========== 阅片记录（如果由 review 跳转过来） ========== */
const reviewMode = computed(() => recordId.value > 0)
const existingRecord = ref<ReadingRecord | null>(null)

/* ========== 画布状态 ========== */

const canvasState = reactive<CanvasState>({
  tool: 'pan',
  annotations: [],
  measurements: [],
  history: [],
  redoStack: [],
  viewport: {
    scale: 1,
    x: 0,
    y: 0,
    ww: 255,
    wl: 127,
    invert: false
  },
  layers: {
    primary: true,
    heatmap: false,
    gold: false,
    my: true
  }
})

/** Canvas 组件实例引用（用于「清空」按钮调用 clearAllTools） */
const readingCanvasRef = ref<InstanceType<typeof CoreRetinaStation> | null>(null)

const setTool = (t: ToolName) => {
  if (!canAnnotate.value) {
    ElMessage.warning('当前角色无标注权限')
    return
  }
  canvasState.tool = t
}

const undo = () => {
  if (canvasState.history.length === 0) {
    ElMessage.info('无可撤销的操作')
    return
  }
  const last = canvasState.history.pop()
  if (last) {
    canvasState.redoStack.push({
      annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
      measurements: JSON.parse(JSON.stringify(canvasState.measurements))
    })
    canvasState.annotations = last.annotations
    canvasState.measurements = last.measurements
  }
}

const redo = () => {
  if (canvasState.redoStack.length === 0) {
    ElMessage.info('无可重做的操作')
    return
  }
  const next = canvasState.redoStack.pop()
  if (next) {
    canvasState.history.push({
      annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
      measurements: JSON.parse(JSON.stringify(canvasState.measurements))
    })
    canvasState.annotations = next.annotations
    canvasState.measurements = next.measurements
  }
}

const clearAll = async () => {
  if (canvasState.annotations.length === 0 && canvasState.measurements.length === 0) {
    return
  }
  try {
    await ElMessageBox.confirm('确认清空当前画布上的所有标注与测量？', '操作确认', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  canvasState.history.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  canvasState.annotations = []
  canvasState.measurements = []
  canvasState.redoStack = []
  // 同步清掉内置 Length / Angle 工具的标注状态，防止重绘时被 syncCornerstoneMeasurements 回填
  readingCanvasRef.value?.clearAllTools?.()
  // 清空也要落盘：否则刷新之后被清掉的标注又回来了，
  //「清空重来」就成了假动作
  scheduleAutosave()
}


/* ========== 自动暂存 ==========
 *
 * 阅片过程中标注只存在于内存，刷新即丢 —— 学员画了二十分钟，
 * 误触刷新就全没了。这里做防抖自动暂存。
 *
 * 三条边界：
 *   · 只暂存草稿态与被驳回态。已提交/已通过的记录是审核依据，
 *     不能被后台的自动保存悄悄改掉；
 *   · 只在用户真的改过之后才存，避免刚进页面就写一次空草稿；
 *   · 失败不打扰用户，只在状态条上如实显示「未暂存」。
 */
const AUTOSAVE_DELAY = 2500
const autosaveState = ref<'idle' | 'saving' | 'saved' | 'failed'>('idle')
const autosaveAt = ref('')
let autosaveTimer: ReturnType<typeof setTimeout> | null = null
let dirty = false

/** 当前记录是否允许被自动暂存覆盖 */
const canAutosave = computed(() => {
  // 与画布的 readonly 判断保持一致：只读时不该产生任何写入
  if (!canAnnotate.value || reviewMode.value) return false
  const st = existingRecord.value?.status
  return !st || st === 'DRAFT' || st === 'REJECTED'
})

const doAutosave = async () => {
  if (!source.value || !canAutosave.value || !dirty) return
  autosaveState.value = 'saving'
  try {
    const out = await ReadingApi.saveReading({
      caseId: source.value.caseId,
      imageIndex: currentImageIndex.value,
      imageUrl: currentImage.value,
      annotations: canvasState.annotations,
      measurements: canvasState.measurements,
      viewport: canvasState.viewport,
      layers: canvasState.layers,
      note: existingRecord.value?.note || '',
      diagnosis: existingRecord.value?.diagnosis || {},
      submit: false
    })
    existingRecord.value = out
    dirty = false
    autosaveState.value = 'saved'
    autosaveAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch {
    // 不弹窗：自动暂存失败不该打断阅片，但要让用户看得见
    autosaveState.value = 'failed'
  }
}

const scheduleAutosave = () => {
  dirty = true
  if (!canAutosave.value) return
  if (autosaveTimer) clearTimeout(autosaveTimer)
  autosaveTimer = setTimeout(doAutosave, AUTOSAVE_DELAY)
}

const autosaveText = computed(() => {
  if (!canAutosave.value) return ''
  if (autosaveState.value === 'saving') return '暂存中…'
  if (autosaveState.value === 'failed') return '未暂存（网络异常）'
  if (autosaveState.value === 'saved') return `已暂存 ${autosaveAt.value}`
  return ''
})

const onAnnotationsChange = (next: AnnotationItem[]) => {
  canvasState.history.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  if (canvasState.history.length > 50) canvasState.history.shift()
  canvasState.redoStack = []
  canvasState.annotations = next
  scheduleAutosave()
}

const onMeasurementsChange = (next: AnnotationItem[]) => {
  canvasState.history.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  if (canvasState.history.length > 50) canvasState.history.shift()
  canvasState.redoStack = []
  canvasState.measurements = next
  scheduleAutosave()
}

const onResetView = () => {
  canvasState.viewport = {
    scale: 1,
    x: 0,
    y: 0,
    ww: 255,
    wl: 127,
    invert: false
  }
}

/* ========== 加载逻辑 ========== */

const sourceError = ref<string>('')

const fetchSource = async () => {
  if (!caseId.value) {
    source.value = null
    sourceError.value = ''
    return
  }
  sourceLoading.value = true
  sourceError.value = ''
  try {
    const res = await ReadingApi.getImageSource(caseId.value)
    source.value = res || null
    loadDiagnosisForm()
    if (res && (!res.images || res.images.length === 0)) {
      sourceError.value = '该病例暂无影像数据'
    }
  } catch (e: any) {
    source.value = null
    const status = e?.response?.status
    if (status === 404) sourceError.value = '病例不存在或已被删除'
    else if (status === 403) sourceError.value = '当前账号无权访问该病例'
    else sourceError.value = e?.message || '影像数据请求失败，请稍后重试'
  } finally {
    sourceLoading.value = false
  }
}

const fetchExistingDraft = async () => {
  if (!caseId.value) return
  try {
    const d = await ReadingApi.getLatestDraft(caseId.value, currentImageIndex.value)
    if (d) {
      existingRecord.value = d
      // 不论草稿还是已提交，都把上次的成果读回来。
      //
      // 此前只在 status === 'DRAFT' 时恢复，导致「保存并提交之后再进来，
      // 画布一片空白」—— 数据一直在库里，只是没被读出来，
      // 用户会以为提交把自己的标注弄丢了。
      canvasState.annotations = (d.annotations || []) as AnnotationItem[]
      canvasState.measurements = (d.measurements || []) as AnnotationItem[]
      if (d.viewport) canvasState.viewport = d.viewport
      if (d.layers) canvasState.layers = d.layers

      const label: Record<string, string> = {
        DRAFT: '已恢复上次未提交的阅片草稿',
        SUBMITTED: '已载入你提交的阅片记录（待审核）',
        REVIEWED: '已载入你提交的阅片记录（已通过）',
        REJECTED: '已载入被驳回的阅片记录，请按审核意见修改后重新提交'
      }
      ElMessage.info(label[d.status] || '已载入上次的阅片记录')
    }
  } catch {
    /* 忽略 */
  }
}

const fetchExistingRecord = async () => {
  if (!recordId.value) return
  try {
    const d = await ReadingApi.getReadingDetail(recordId.value)
    existingRecord.value = d
    canvasState.annotations = (d.annotations || []) as AnnotationItem[]
    canvasState.measurements = (d.measurements || []) as AnnotationItem[]
    if (d.viewport) canvasState.viewport = d.viewport
    if (d.layers) canvasState.layers = d.layers
    if (!caseId.value && d.caseId) {
      // 用 record 里的 caseId 拉影像
      router.replace({ query: { ...route.query, caseId: d.caseId } })
    }
  } catch (e: any) {
    // 服务端把缺失项逐条列出，回显到表单顶部，
    // 而不是只丢一句「提交失败」让用户猜哪里没填
    const detail = e?.response?.data?.data || e?.data
    if (detail?.code === 'DIAGNOSIS_INCOMPLETE') {
      submitProblems.value = detail.problems || []
    }
  }
}

/* ========== 提交弹窗 ========== */

const submitVisible = ref(false)
const saving = ref(false)
// 提交幂等键：跨重试保持不变，提交成功后才清空
const submitRequestId = ref('')

const diagnosisForm = ref<any>(null)
const submitProblems = ref<string[]>([])

/** 按病种取表单定义；失败不阻断阅片，退化为仅备注 */
const loadDiagnosisForm = async () => {
  const cid = source.value?.caseId ?? caseId.value
  if (!cid) return
  try {
    diagnosisForm.value = await ReadingApi.getDiagnosisForm(Number(cid))
  } catch {
    diagnosisForm.value = null
  }
}

const onSave = async (
  submit: boolean,
  payload: { note: string; diagnosis: Record<string, any> }
) => {
  if (!source.value) return
  const { note, diagnosis } = payload

  // 提交前把结论摊开核对。草稿不打扰：存草稿本来就是随手的动作。
  if (submit) {
    const rows = buildAnswerSummary(diagnosisForm.value, diagnosis)
    try {
      await ElMessageBox.confirm(
        summaryHtml(
          rows,
          `另有标注 ${canvasState.annotations.length} 处、` +
            `测量 ${canvasState.measurements.length} 处。提交后进入教师审核。`
        ),
        '请核对阅片结论',
        {
          type: 'warning',
          dangerouslyUseHTMLString: true,
          confirmButtonText: '确认提交',
          cancelButtonText: '再看看'
        }
      )
    } catch { return }
    // 幂等键跨重试保持不变；提交成功后清空
    if (!submitRequestId.value) submitRequestId.value = newRequestId()
  }

  saving.value = true
  submitProblems.value = []
  try {
    const params: ReadingApi.ReadingSaveParams = {
      caseId: source.value.caseId,
      imageIndex: currentImageIndex.value,
      imageUrl: currentImage.value,
      annotations: canvasState.annotations,
      measurements: canvasState.measurements,
      viewport: canvasState.viewport,
      layers: canvasState.layers,
      note,
      diagnosis,
      submit,
      requestId: submit ? submitRequestId.value : undefined
    }
    const out = await submitWithRetry(() => ReadingApi.saveReading(params), {
      // 草稿失败不重试：学员还在页面上，下一次自动保存会补上
      attempts: submit ? 3 : 1,
      onRetry: (n) =>
        ElMessage.warning(`网络异常，正在第 ${n} 次重试提交，请勿关闭页面`)
    })
    existingRecord.value = out
    submitVisible.value = false
    if (submit) {
      submitRequestId.value = ''
      router.push('/case-browse')
    }
  } catch {
    // 保留幂等键：学员再点提交仍算同一次动作。
    // 若失败的那几次里其实有一次到达了服务端，重试会拿回原记录，
    // 不会变成两条重复的待审阅片。
  } finally {
    saving.value = false
  }
}

/* ========== 教师审核 ========== */

const reviewLoading = ref(false)
const onReview = async (accept: boolean, comment: string) => {
  if (!existingRecord.value) return
  reviewLoading.value = true
  try {
    const out = await ReadingApi.reviewReading(existingRecord.value.id, {
      reviewComment: comment,
      accept
    })
    existingRecord.value = out
    ElMessage.success(accept ? '已通过审核' : '已驳回，状态恢复为草稿')
  } catch {
    /* 已弹错误 */
  } finally {
    reviewLoading.value = false
  }
}

/* ========== 跳转 ========== */

const goBack = () => router.push('/case-browse')

const genderText = (g?: string) => {
  if (g === 'M') return '男'
  if (g === 'F') return '女'
  return '—'
}

/* ========== 生命周期 ========== */

onMounted(async () => {
  // 阅片内核由 CoreRetinaStation 自行初始化（并发调用共用同一个 Promise），
  // 页面不再需要预热
  await loadCaseList()

  // 无病例参数进入 → 直接进入第一例
  if (!caseId.value && !recordId.value && caseList.value.length) {
    onSelectCase(caseList.value[0].id)
    return
  }

  if (recordId.value) {
    await fetchExistingRecord()
  }

  await fetchSource()

  if (!recordId.value) {
    await fetchExistingDraft()
  }
})

onBeforeUnmount(() => {
  // 离开页面时清理 cornerstone 启用元素由 CoreRetinaStation 自身负责
})

watch(currentImageIndex, () => {
  // 切换影像时清空当前画布；可选择是否拉新草稿
  canvasState.annotations = []
  canvasState.measurements = []
  canvasState.history = []
  canvasState.redoStack = []
  canvasState.viewport = {
    scale: 1,
    x: 0,
    y: 0,
    ww: 255,
    wl: 127,
    invert: false
  }
  if (!recordId.value) {
    fetchExistingDraft()
  }
})

/* ========== 切换病例：路由 caseId 变化时彻底重置画布并拉取新影像 ========== */
watch(caseId, async (newId, oldId) => {
  if (newId === oldId) return
  if (!newId) {
    source.value = null
    sourceError.value = ''
    return
  }
  // 重置画布所有状态（标注 / 测量 / 历史 / 视口）
  canvasState.annotations = []
  canvasState.measurements = []
  canvasState.history = []
  canvasState.redoStack = []
  canvasState.viewport = {
    scale: 1,
    x: 0,
    y: 0,
    ww: 255,
    wl: 127,
    invert: false
  }
  // 重置影像源与选择
  source.value = null
  sourceError.value = ''
  imageLoadError.value = false
  existingRecord.value = null
  currentImageIndex.value = 0
  // 重新拉取新病例
  if (recordId.value) {
    await fetchExistingRecord()
  }
  await fetchSource()
  if (!recordId.value) {
    await fetchExistingDraft()
  }
})

/* ========== 影像加载错误兜底 ========== */
const imageLoadError = ref(false)
const onCanvasError = (err: any) => {
  imageLoadError.value = true
  console.warn('[reading] image load failed', err)
}
const onCanvasReady = () => {
  imageLoadError.value = false
}
/** 让用户主动重试当前影像（重新触发 CoreRetinaStation 的 watch） */
const reloadCurrent = () => {
  imageLoadError.value = false
  const idx = currentImageIndex.value
  // 强制改一下索引再改回来 → CoreRetinaStation 会重新调用 loadImage
  currentImageIndex.value = -1
  setTimeout(() => {
    currentImageIndex.value = idx
  }, 0)
}

/* ========== 质量门控（先质量后诊断） ========== */
const qualityChecking = ref(false)
const runQualityCheck = async () => {
  const cid = source.value?.caseId ?? caseId.value
  if (!cid) return
  qualityChecking.value = true
  try {
    const r = await ReadingApi.checkImageQuality(Number(cid))
    // 算法服务不可用时接口仍返回成功，此处如实告知失败张数，
    // 不把「未评估」说成「已质控」
    if (r.failed > 0 && r.evaluated === 0) {
      ElMessage.warning(`质量评估未完成：${r.failed} 张调用失败，质量保持「未评估」`)
    } else if (r.failed > 0) {
      ElMessage.warning(`已评估 ${r.evaluated} 张，${r.failed} 张失败`)
    } else if (r.hasUngradable) {
      ElMessage.error('检出不可判读影像，请勿据此给出阴性结论')
    } else {
      ElMessage.success(`质量评估完成，共 ${r.evaluated} 张`)
    }
    await fetchSource()
  } finally {
    qualityChecking.value = false
  }
}

/* ========== 影像安全标识（报告 P0/P1：安全条常驻） ========== */
const currentImageMeta = computed(() => {
  const metas = (source.value?.imageMeta || []) as any[]
  if (!metas.length) return null
  // 优先按当前影像 URL 匹配，避免索引错位导致「看错眼」
  const url = currentImage.value
  const byUrl = metas.find((m) => m?.url && url && m.url === url)
  return byUrl || metas[currentImageIndex.value] || null
})

const readingStatusMeta = computed(() => {
  const st = existingRecord.value?.status
  return st ? ReadingApi.READING_STATUS_META[st] : null
})
const readingStatusText = computed(
  () => readingStatusMeta.value?.label || '未开始'
)

/* ========== AI 辅助诊断（CSU-EYES 真实算法） ========== */
const aiVisible = ref(false)
const aiCaseKey = computed(() => source.value?.caseNo || String(caseId.value || ''))
const openAiDiagnosis = () => {
  if (!aiCaseKey.value) {
    ElMessage.warning('当前未加载任何病例，无法执行 AI 诊断')
    return
  }
  aiVisible.value = true
}

/* ========== 笔记联动 ========== */
const noteVisible = ref(false)
const noteBind = computed(() => ({
  caseId: source.value?.caseId ?? caseId.value,
  caseNo: source.value?.caseNo || '',
  caseTitle: '',
  imageIndex: currentImageIndex.value,
  imageUrl: currentImage.value
}))
const openNote = () => {
  if (!source.value?.caseId && !caseId.value) {
    ElMessage.warning('当前未加载任何病例，无法创建笔记')
    return
  }
  noteVisible.value = true
}

</script>

<template>
  <div class="reading-page">
    <header class="page-header">
      <div class="header-left">
        <el-button :icon="Back" text @click="goBack">返回病例库</el-button>
        <div class="divider" />
        <span class="page-title">
          <el-icon><Document /></el-icon>
          阅片工作台
        </span>
        <!-- 病例快速切换 -->
        <div v-if="caseList.length" class="case-switch">
          <el-button
            :icon="ArrowLeft"
            circle
            size="small"
            :disabled="curIdx <= 0"
            title="上一例"
            @click="gotoCaseByIndex(curIdx - 1)"
          />
          <el-select
            :model-value="caseId"
            size="small"
            class="case-select"
            filterable
            placeholder="切换病例"
            @change="onSelectCase"
          >
            <el-option
              v-for="c in caseList"
              :key="c.id"
              :value="c.id"
              :label="`${c.caseNo}｜${c.title || '未命名'}`"
            />
          </el-select>
          <el-button
            :icon="ArrowRight"
            circle
            size="small"
            :disabled="curIdx < 0 || curIdx >= caseList.length - 1"
            title="下一例"
            @click="gotoCaseByIndex(curIdx + 1)"
          />
          <span class="case-count">{{ curIdx >= 0 ? curIdx + 1 : '-' }}/{{ caseList.length }}</span>
        </div>
      </div>
      <div class="header-right">
        <el-tag size="small" type="info" effect="plain">
          {{ isAdmin ? '管理员' : isTeacher ? '带教医师' : '住培医师' }}
        </el-tag>
        <el-tag
          v-if="existingRecord"
          size="small"
          :type="readingStatusMeta?.tag || 'info'"
          effect="plain"
        >
          {{ readingStatusText }}
        </el-tag>
        <!-- 自动暂存状态：让用户看得见「已经存住了」，
             也在存不上时如实告知，而不是默默丢失 -->
        <span
          v-if="autosaveText"
          class="autosave-hint"
          :class="{ bad: autosaveState === 'failed' }"
        >
          {{ autosaveText }}
        </span>
        <el-button
          v-if="canAnnotate && !reviewMode"
          type="primary"
          size="small"
          :disabled="!source || sourceLoading"
          @click="submitVisible = true"
        >
          保存 / 提交
        </el-button>
        <el-button
          size="small"
          type="success"
          plain
          :icon="MagicStick"
          :disabled="!source || sourceLoading"
          @click="openAiDiagnosis"
        >
          AI 辅助判读
        </el-button>
        <el-button
          v-if="canAnnotate && !reviewMode"
          size="small"
          plain
          :loading="qualityChecking"
          :disabled="!source || sourceLoading"
          @click="runQualityCheck"
        >
          质量评估
        </el-button>
        <el-button
          size="small"
          :disabled="!source"
          @click="openNote"
        >
          记笔记
        </el-button>
      </div>
    </header>

    <!-- 影像安全标识条（常驻，报告 P0/P1） -->
    <ReadingSafetyBar
      v-if="source"
      :case-no="source.caseNo"
      :patient-name="source.patientName"
      :modality-text="(source as any).modalityText"
      :exam-date="(source as any).examDate"
      :exam-date-known="(source as any).examDateKnown"
      :current="currentImageMeta"
      :safety="(source as any).safety"
      :status-text="readingStatusText"
    />

    <!-- 患者信息栏 -->
    <div v-if="source" class="patient-bar">
      <div class="pb-cell">
        <span class="pb-label">姓名</span>
        <span class="pb-value">{{ source.patientName || '—' }}</span>
      </div>
      <div class="pb-cell">
        <span class="pb-label">性别</span>
        <span class="pb-value">{{ genderText(source.patientGender) }}</span>
      </div>
      <div class="pb-cell">
        <span class="pb-label">年龄</span>
        <span class="pb-value">{{ source.patientAge ? source.patientAge + ' 岁' : '—' }}</span>
      </div>
      <div v-if="source.patientPhone || source.phoneVisible !== false" class="pb-cell">
        <span class="pb-label">手机号</span>
        <span class="pb-value mono">
          {{ source.patientPhone || '—' }}
          <el-tag
            v-if="source.phoneVisible === false && source.patientPhone"
            size="small"
            type="info"
            effect="plain"
            style="margin-left: 4px"
          >已脱敏</el-tag>
        </span>
      </div>
      <div class="pb-cell pb-no">
        <span class="pb-label">病例编号</span>
        <span class="pb-value mono">{{ source.caseNo }}</span>
        <span v-if="source.caseSn" class="pb-sn">{{ source.caseSn }}</span>
      </div>
    </div>

    <div class="page-body">
      <!-- 左侧工具栏 -->
      <ReadingToolbar
        :tool="canvasState.tool"
        :can-annotate="canAnnotate"
        :can-undo="canvasState.history.length > 0"
        :can-redo="canvasState.redoStack.length > 0"
        @set-tool="setTool"
        @undo="undo"
        @redo="redo"
        @clear="clearAll"
        @reset-view="onResetView"
      />

      <!-- 中间画布 -->
      <div class="canvas-area">
        <!-- 多 role 影像 tabs -->
        <div
          v-if="!missingCaseId && source && availableRoles.length > 1"
          class="role-tabs"
        >
          <el-radio-group
            :model-value="currentImageRole"
            size="small"
            @change="onChangeRole"
          >
            <el-radio-button
              v-for="r in availableRoles"
              :key="r"
              :value="r"
            >
              {{ ROLE_LABEL[r] || r }}
              <span class="role-cnt">×{{ (source?.imageGroups as any)?.[r]?.length || 0 }}</span>
            </el-radio-button>
          </el-radio-group>
          <span v-if="source && source.imageComplete === false" class="incomplete-tip">
            该病例存在缺失影像（{{ (source.missingRoles || []).join('/') }}），请管理员补传
          </span>
        </div>

        <div v-if="missingCaseId" class="empty error">
          <el-icon><Document /></el-icon>
          <span>缺少 caseId 参数，无法加载影像</span>
          <el-button size="small" @click="goBack">返回病例库</el-button>
        </div>
        <div v-else-if="sourceLoading" v-loading="true" class="loading-mask">
          影像加载中…
        </div>
        <div
          v-else-if="!source || currentRoleImages.length === 0"
          class="empty"
        >
          <el-icon><Document /></el-icon>
          <span>{{ sourceError || '该病例暂无影像数据' }}</span>
          <div class="empty-actions">
            <el-button size="small" @click="fetchSource">重试</el-button>
            <el-button size="small" @click="goBack">返回病例库</el-button>
          </div>
        </div>
        <CoreRetinaStation
          :dicom-image-id="currentDicomImageId"
          :segmentation="source?.segmentation || null"
          v-else
          :key="caseId"
          ref="readingCanvasRef"
          mode="reading"
          :image-url="currentImage"
          :tool="canvasState.tool"
          :annotations="canvasState.annotations"
          :measurements="canvasState.measurements"
          :viewport="canvasState.viewport"
          :layers="canvasState.layers"
          :readonly="!canAnnotate || reviewMode"
          @update:annotations="onAnnotationsChange"
          @update:measurements="onMeasurementsChange"
          @update:viewport="(v) => (canvasState.viewport = v)"
          @ready="onCanvasReady"
          @error="onCanvasError"
        />

        <!-- 影像加载失败提示（cornerstone 加载阶段失败） -->
        <div v-if="imageLoadError && source && currentRoleImages.length > 0" class="img-err-tip">
          影像加载失败，请检查路径或网络后
          <el-link type="warning" :underline="false" @click="reloadCurrent">点此重试</el-link>
        </div>

        <!-- 多图切换条（当前 role 内多张时） -->
        <div v-if="source && currentRoleImages.length > 1" class="image-strip">
          <div
            v-for="(img, i) in currentRoleImages"
            :key="i"
            class="strip-cell"
            :class="{ active: i === currentImageIndex }"
            @click="currentImageIndex = i"
          >
            <img :src="img" />
            <span class="strip-label">{{ i + 1 }}</span>
          </div>
        </div>
      </div>

      <!-- 右侧信息面板 -->
      <ReadingSidePanel
        :viewport="canvasState.viewport"
        :layers="canvasState.layers"
        :annotations="canvasState.annotations"
        :measurements="canvasState.measurements"
        :existing-record="existingRecord"
        :can-review="canReview && reviewMode"
        :review-loading="reviewLoading"
        @update:viewport="(v) => (canvasState.viewport = v)"
        @update:layers="(l) => (canvasState.layers = l)"
        @remove-annotation="
          (idx) => {
            const next = [...canvasState.annotations]
            next.splice(idx, 1)
            onAnnotationsChange(next)
          }
        "
        @remove-measurement="
          (idx) => {
            const next = [...canvasState.measurements]
            next.splice(idx, 1)
            onMeasurementsChange(next)
          }
        "
        @review="onReview"
      />
    </div>

    <!-- 保存 / 提交弹窗 -->
    <ReadingSubmitDialog
      v-model:visible="submitVisible"
      :saving="saving"
      :default-note="existingRecord?.note || ''"
      :form="diagnosisForm"
      :default-diagnosis="existingRecord?.diagnosis"
      :problems="submitProblems"
      @save="(p) => onSave(false, p)"
      @submit="(p) => onSave(true, p)"
    />

    <!-- 学习笔记弹窗（绑定当前病例与影像） -->
    <NoteEditDialog
      v-model:visible="noteVisible"
      :note="null"
      :bind="noteBind"
    />

    <!-- AI 辅助诊断弹窗（CSU-EYES 真实算法服务） -->
    <AiDiagnosisDialog
      v-model:visible="aiVisible"
      :case-id="aiCaseKey"
    />
  </div>
</template>

<style scoped>
.autosave-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #86909c;
}
.autosave-hint.bad {
  color: #f56c6c;
}

.reading-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0f1014;
  color: #e5e6eb;
}

.page-header {
  height: 48px;
  padding: 0 16px;
  background: #181a20;
  border-bottom: 1px solid #2a2a2a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.divider {
  width: 1px;
  height: 16px;
  background: #2a2a2a;
}
.page-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #e5e6eb;
}
.case-no {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #4091ff;
  font-weight: 600;
}
.case-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 12px;
}
.case-select {
  width: 230px;
}
.case-count {
  font-size: 12px;
  color: #9aa4b2;
  font-variant-numeric: tabular-nums;
  min-width: 44px;
  text-align: center;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-body {
  flex: 1;
  display: grid;
  grid-template-columns: 64px 1fr 320px;
  min-height: 0;
}

.patient-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 8px 20px;
  background: linear-gradient(90deg, #161821, #1d202b);
  border-bottom: 1px solid #2a2a2a;
  color: #c9cdd4;
  font-size: 13px;
  flex-wrap: wrap;
}
.pb-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pb-label {
  color: #86909c;
  font-size: 12px;
}
.pb-value {
  color: #e5e6eb;
  font-weight: 500;
}
.pb-value.mono {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #4091ff;
}
.pb-sn {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #86909c;
  margin-left: 4px;
}
.pb-no {
  margin-left: auto;
}

.canvas-area {
  position: relative;
  background: #0e0f12;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.loading-mask,
.empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 8px;
  color: #4e5969;
  font-size: 14px;
  pointer-events: none;
}
.empty {
  pointer-events: auto;
}
.empty.error {
  color: #ff7875;
}
.empty-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.img-err-tip {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(245, 63, 63, 0.16);
  color: #ff7875;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid rgba(245, 63, 63, 0.3);
}

.image-strip {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 8px;
  padding: 6px 8px;
  background: rgba(20, 20, 24, 0.8);
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  backdrop-filter: blur(8px);
  max-width: 80%;
  overflow-x: auto;
}
.strip-cell {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  position: relative;
  border: 2px solid transparent;
  background: #0e0f12;
}
.strip-cell.active {
  border-color: #4091ff;
}
.strip-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0.8;
}
.strip-cell.active img {
  opacity: 1;
}
.strip-label {
  position: absolute;
  bottom: 2px;
  right: 4px;
  font-size: 11px;
  color: #fff;
  text-shadow: 0 1px 2px #000;
}
</style>
