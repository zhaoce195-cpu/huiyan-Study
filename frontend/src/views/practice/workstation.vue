<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, MagicStick } from '@element-plus/icons-vue'

import { ReadingApi, PracticeApi } from '@/api'
import { wadorsImageId } from '@/utils/cornerstone3d'
import {
  buildAnswerSummary,
  newRequestId,
  submitWithRetry,
  summaryHtml
} from '@/utils/submit-guard'

import ReadingToolbar from '@/views/reading/components/ReadingToolbar.vue'
import CoreRetinaStation from '@/components/CoreRetinaStation.vue'
import AiDiagnosisDialog from '@/components/AiDiagnosisDialog.vue'
import DiagnosisForm from '@/views/reading/components/DiagnosisForm.vue'
import type { ToolName, AnnotationItem, CanvasState } from '@/views/reading/types'
import {
  remarkMatches,
  tasksForFindings,
  type LocateRequest,
  type LocateTask
} from '@/utils/finding-locate'

// 同 reading：显式命名，保证 TrainingPortal 的 keep-alive exclude 能匹配上
defineOptions({ name: 'PracticeWorkstation' })

const route = useRoute()
const router = useRouter()

const sessionId = computed(() => Number(route.query.sessionId || 0))
const caseId = computed(() => Number(route.query.caseId || 0))
const viewMode = computed(() => route.query.view === 'report')
const reviewMode = computed(() => route.query.review === '1')

/* ========== 影像源 ========== */
const source = ref<ReadingApi.ImageSource | null>(null)
const sourceLoading = ref(false)
const currentImageIndex = ref(0)
const currentImage = computed(() => source.value?.images?.[currentImageIndex.value] || '')


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

/* ========== 练习记录 ========== */
const record = ref<PracticeApi.PracticeRecord | null>(null)
const textAnswers = ref<Record<string, string>>({})
const textQuestions = computed(() => record.value?.textQuestions || [])
const isExam = computed(() => record.value?.attemptKind === 'EXAM')
const examContinues = computed(
  () => isExam.value && (record.value?.nextSessionId || 0) > 0
)
const goldData = ref<PracticeApi.GoldStandardData | null>(null)
const goldAnnotations = computed<AnnotationItem[]>(() => {
  if (!record.value?.answersOpen || !goldData.value) return []
  return (goldData.value.annotations || []) as AnnotationItem[]
})

/* ========== 画布状态 ========== */
const canvasState = reactive<CanvasState>({
  tool: 'pointer',
  annotations: [],
  measurements: [],
  history: [],
  redoStack: [],
  viewport: { scale: 1, x: 0, y: 0, ww: 255, wl: 127, invert: false },
  layers: { primary: true, heatmap: false, gold: false, my: true }
})

/** 提交前不把病灶图交给画布，避免答题时就把答案画出来 */
const goldOverlayUrl = computed(() => {
  if (!record.value?.answersOpen) return ''
  if (!canvasState.layers.gold) return ''
  return goldData.value?.lesionMaskUrl || ''
})

const goldLayerHint = computed(() => {
  const gold = goldData.value
  if (!gold) return '提交之后才能看到金标准。'
  const boxes = (gold.annotations || []).length
  const mask = !!gold.lesionMaskUrl
  if (boxes && mask) {
    return '这例有专家标注框，也有一张病灶着色图。勾选后会叠在眼底图上：框是绿色虚线，着色图是半透明的。'
  }
  if (boxes) {
    return '这例有专家标注框，没有单独的金标准照片。勾选后，框以绿色虚线画在眼底图上。'
  }
  if (mask) {
    return '这例没有标注框，但有一张病灶着色图。勾选后会半透明叠在眼底图上。'
  }
  return '这例没有金标准标注框，也没有病灶着色图。勾选后画面不会多出图层，不是没画出来。'
})

/* ========== 诊断表单 ========== */
const diagnosisForm = ref<any>(null)
const structuredAnswer = ref<Record<string, any>>({})

/** 与阅片端共用同一套病种表单；取不到则退回旧的自由文本表单 */
const loadDiagnosisForm = async (caseId: number) => {
  try {
    diagnosisForm.value = await ReadingApi.getDiagnosisForm(caseId)
  } catch {
    diagnosisForm.value = null
  }
}

const diagForm = ref({
  drGrade: '',
  diagnosis: ''
})
const submitting = ref(false)
// 幂等键：跨重试保持不变，提交成功后才清空
const submitRequestId = ref('')
const startTime = ref(Date.now())

/* ========== 工具操作 ========== */
const setTool = (t: ToolName) => { canvasState.tool = t }

const undo = () => {
  if (canvasState.history.length === 0) return
  const last = canvasState.history.pop()!
  canvasState.redoStack.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  canvasState.annotations = last.annotations
  canvasState.measurements = last.measurements
}

const redo = () => {
  if (canvasState.redoStack.length === 0) return
  const next = canvasState.redoStack.pop()!
  canvasState.history.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  canvasState.annotations = next.annotations
  canvasState.measurements = next.measurements
}

const clearAll = async () => {
  if (canvasState.annotations.length === 0 && canvasState.measurements.length === 0) return
  try {
    await ElMessageBox.confirm('确认清空所有标注？', '提示', { type: 'warning' })
  } catch { return }
  canvasState.history.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  canvasState.annotations = []
  canvasState.measurements = []
  canvasState.redoStack = []
}

const onAnnotationsChange = (next: AnnotationItem[], meta?: { history?: boolean }) => {
  if (meta?.history !== false) {
    canvasState.history.push({
      annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
      measurements: JSON.parse(JSON.stringify(canvasState.measurements))
    })
    if (canvasState.history.length > 50) canvasState.history.shift()
    canvasState.redoStack = []
  }
  canvasState.annotations = next
}

const onMeasurementsChange = (next: AnnotationItem[]) => {
  canvasState.history.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  if (canvasState.history.length > 50) canvasState.history.shift()
  canvasState.redoStack = []
  canvasState.measurements = next
}

const onResetView = () => {
  canvasState.viewport = { scale: 1, x: 0, y: 0, ww: 255, wl: 127, invert: false }
}

/* ========== 错误点显示 ========== */
const epTagType = (t: PracticeApi.ErrorPointType) => {
  if (t === 'missed') return 'danger'
  if (t === 'false_positive') return 'warning'
  if (t === 'wrong_label') return 'warning'
  return 'info'
}
const studentMarkCount = computed(
  () => (record.value?.studentAnnotations || []).filter((a) => a.layer !== 'finding').length
)

const locateTasks = computed(() => {
  if (isExam.value || record.value?.status !== 'DRAFT') return []
  if (structuredAnswer.value.readability === diagnosisForm.value?.ungradableValue) return []
  return tasksForFindings(structuredAnswer.value.findings)
})
const activeLocateCode = ref('')
const activeLocateTask = computed(
  () => locateTasks.value.find((task) => task.code === activeLocateCode.value) || null
)
const locateEye = computed<'OD' | 'OS' | ''>(() => {
  const eye = source.value?.imageMeta?.[currentImageIndex.value]?.eye
  return eye === 'OD' || eye === 'OS' ? eye : ''
})
const locateRequest = computed<LocateRequest | null>(() => {
  const task = activeLocateTask.value
  if (!task) return null
  return {
    code: task.code,
    method: task.method,
    label: task.markLabel,
    color: task.color,
    eye: locateEye.value
  }
})
const locateCount = (task: LocateTask) =>
  canvasState.annotations.filter(
    (item) => item.layer === 'finding' && remarkMatches(item.remark, task.code)
  ).length
const beginLocate = (task: LocateTask) => {
  activeLocateCode.value = activeLocateCode.value === task.code ? '' : task.code
}
const undoLocate = (task: LocateTask) => {
  const list = canvasState.annotations
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].layer === 'finding' && remarkMatches(list[i].remark, task.code)) {
      onAnnotationsChange(list.filter((_, index) => index !== i))
      return
    }
  }
}
const LABEL_TO_FINDING: Record<string, string> = {
  微动脉瘤: 'MA',
  出血: 'HE',
  渗出: 'EX',
  棉绒斑: 'SE',
  新生血管: 'NV'
}
const onPickLabel = (label: string) => {
  const code = LABEL_TO_FINDING[label]
  if (!code || isExam.value || record.value?.status !== 'DRAFT') return
  const current = Array.isArray(structuredAnswer.value.findings)
    ? [...structuredAnswer.value.findings]
    : []
  if (!current.includes(code)) {
    structuredAnswer.value = { ...structuredAnswer.value, findings: [...current, code] }
  }
  activeLocateCode.value = code
}
watch(
  () => locateTasks.value.map((task) => task.code).join(','),
  (now, prev) => {
    const prevCodes = new Set((prev || '').split(',').filter(Boolean))
    const added = locateTasks.value.find((task) => !prevCodes.has(task.code))
    if (added) activeLocateCode.value = added.code
    else if (!locateTasks.value.some((task) => task.code === activeLocateCode.value)) {
      activeLocateCode.value = ''
    }
  }
)
const annotationExamined = computed(() => record.value?.annotationApplicable !== false)
const gradeExamined = computed(() => !!record.value?.caseDrGradeText)

const gradeScoreText = computed(() => {
  if (!gradeExamined.value) return '未考'
  return Number(record.value?.scoreGrade || 0).toFixed(0)
})
const annotationScoreText = computed(() => {
  if (!annotationExamined.value) return '未考'
  if (!studentMarkCount.value && goldAnnotations.value.length > 0) return '0（未标注）'
  return Number(record.value?.scoreAnnotation || 0).toFixed(0)
})
const diagnosisScoreText = computed(() => Number(record.value?.scoreDiagnosis || 0).toFixed(0))
const iouScoreText = computed(() => {
  if (!annotationExamined.value) return '未考'
  if (!studentMarkCount.value) return '未标注'
  return Number(record.value?.iouAvg || 0).toFixed(2)
})
const foundScoreText = computed(() => {
  if (!annotationExamined.value) return '未考'
  if (!studentMarkCount.value && goldAnnotations.value.length > 0) return '0%'
  return `${(Number(record.value?.accuracy || 0) * 100).toFixed(0)}%`
})
const textScoreText = computed(() => {
  if ((record.value?.scoreRuleVersion || 1) < 4) return '未考'
  return Number(record.value?.scoreText || 0).toFixed(0)
})
/** 旧成绩把「没框可对」存成了标注 100，和现在的「未考」不是同一套数 */
const staleAnnotationCredit = computed(() => {
  const rec = record.value
  if (!rec || rec.annotationApplicable !== false) return false
  return (rec.scoreRuleVersion || 1) < 3 && Number(rec.scoreAnnotation || 0) > 0
})

const epText = (t: PracticeApi.ErrorPointType) => {
  if (t === 'missed') return '漏标'
  if (t === 'false_positive') return '误标'
  if (t === 'wrong_label') return '标签错'
  if (t === 'low_iou') return 'IoU 低'
  return '其他'
}

/* ========== 数据加载 ========== */
const fetchSource = async () => {
  // 以会话记录里的病例为准（防止 URL 里的 caseId 与实际会话病例不一致导致图文错配）
  const cid = record.value?.caseId || caseId.value
  if (!cid) return
  sourceLoading.value = true
  try {
    source.value = await ReadingApi.getImageSource(cid)
  } catch {
    source.value = null
  } finally {
    sourceLoading.value = false
  }
}

const loadRecord = async () => {
  if (!sessionId.value) return
  try {
    record.value = await PracticeApi.getPracticeDetail(sessionId.value)
    const cid = record.value?.caseId
    if (cid) loadDiagnosisForm(Number(cid))
    if (record.value) {
      diagForm.value.drGrade = record.value.studentDrGrade || ''
      diagForm.value.diagnosis = record.value.studentDiagnosis || ''
      // 结构化作答回填：不回填的话，学员刷新页面后填过的内容会凭空消失
      structuredAnswer.value = { ...(record.value.studentDiagnosisForm || {}) }
      canvasState.annotations = (record.value.studentAnnotations || []) as AnnotationItem[]
      canvasState.measurements = (record.value.studentMeasurements || []) as AnnotationItem[]
      if (record.value.viewport) canvasState.viewport = record.value.viewport as any
      const next: Record<string, string> = {}
      for (const q of record.value.textQuestions || []) {
        next[q.id] = textAnswers.value[q.id] || ''
      }
      textAnswers.value = next
    }
  } catch {
    record.value = null
  }
}

const loadGoldStandard = async () => {
  const cid = record.value?.caseId || caseId.value
  if (!cid) return
  if (!record.value?.answersOpen) return
  try {
    goldData.value = await PracticeApi.getGoldStandard(cid)
    canvasState.layers.gold = true
  } catch {
    goldData.value = null
  }
}

const onGoldToggle = async (val: any) => {
  if (val && !goldData.value) await loadGoldStandard()
}

/* ========== 提交作答 ========== */
const handleSubmit = async () => {
  if (!record.value) return
  const grade = structuredAnswer.value.dr_grade || diagForm.value.drGrade
  const ungradable =
    structuredAnswer.value.readability === diagnosisForm.value?.ungradableValue
  if (!grade && !ungradable) {
    ElMessage.warning('请选择 DR 分级')
    return
  }
  const missingText = textQuestions.value.some((q) => !(textAnswers.value[q.id] || '').trim())
  if (missingText) {
    ElMessage.warning('文字题还有没写的')
    return
  }
  const missingLocate = locateTasks.value.filter((task) => locateCount(task) < 1)
  if (missingLocate.length) {
    activeLocateCode.value = missingLocate[0].code
    ElMessage.warning(
      `请在图上指出：${missingLocate.map((task) => `${task.label}（${task.methodText}）`).join('、')}`
    )
    return
  }
  // 最终摘要：把即将提交的结论摊开给学员核对。
  // 只问一句「确认提交吗」提供不了任何信息，学员只能盲点确定。
  const rows = buildAnswerSummary(diagnosisForm.value, structuredAnswer.value)
  const marks = canvasState.annotations.filter((item) => item.layer !== 'finding').length
  const located = locateTasks.value
    .map((task) => `${task.label} ${locateCount(task)} 处`)
    .join('、')
  const locatedNote = located ? `已指出位置：${located}。` : ''
  const submitNote = isExam.value
    ? examContinues.value
      ? `另有标注 ${marks} 处、文字题 ${textQuestions.value.length} 道。本题交卷后进入下一题，整卷交齐前不显示答案。`
      : `另有标注 ${marks} 处、文字题 ${textQuestions.value.length} 道。这是最后一题，交卷后才显示整场答案。`
    : `另有标注 ${marks} 处、测量 ${canvasState.measurements.length} 处、文字题 ${textQuestions.value.length} 道。${locatedNote}文字题计入总分。提交后将自动评分，无法再修改本次作答。`
  try {
    await ElMessageBox.confirm(
      summaryHtml(rows, submitNote),
      '请核对本次作答',
      {
        type: 'warning',
        dangerouslyUseHTMLString: true,
        confirmButtonText: '确认提交',
        cancelButtonText: '再看看'
      }
    )
  } catch { return }

  // 幂等键在这一次提交动作里固定不变：重试必须带同一个键，
  // 每次换新键等于每次都是一次新提交，幂等就白做了
  if (!submitRequestId.value) submitRequestId.value = newRequestId()

  submitting.value = true
  try {
    const duration = Math.floor((Date.now() - startTime.value) / 1000)
    const payload = {
      sessionId: record.value.id,
      // 分级仍单独上送：它是评分的独立一项（占 30%），
      // 结构化表单里的 dr_grade 与之保持同一取值
      studentDrGrade:
        structuredAnswer.value.dr_grade || diagForm.value.drGrade,
      studentDiagnosis: diagForm.value.diagnosis,
      diagnosis: structuredAnswer.value,
      annotations: canvasState.annotations,
      measurements: canvasState.measurements,
      viewport: canvasState.viewport,
      durationSeconds: duration,
      requestId: submitRequestId.value,
      textAnswers: textQuestions.value.map((q) => ({
        id: q.id,
        value: textAnswers.value[q.id] || ''
      }))
    }
    const out = await submitWithRetry(
      () => PracticeApi.submitPractice(payload),
      {
        onRetry: (n) =>
          ElMessage.warning(`网络异常，正在第 ${n} 次重试提交，请勿关闭页面`)
      }
    )
    record.value = out
    submitRequestId.value = ''
    if (out.attemptKind === 'EXAM' && out.nextSessionId) {
      ElMessage.success(
        `第 ${out.examIndex} 题已保存。答案要等 ${out.examTotal} 题全部交卷后才显示。`
      )
      textAnswers.value = {}
      structuredAnswer.value = {}
      canvasState.annotations = []
      canvasState.measurements = []
      goldData.value = null
      canvasState.layers.gold = false
      activeLocateCode.value = ''
      startTime.value = Date.now()
      await router.replace({
        path: '/practice/workstation',
        query: {
          sessionId: String(out.nextSessionId),
          caseId: String(out.nextCaseId || '')
        }
      })
      return
    }
    if (out.answersOpen) await loadGoldStandard()
    ElMessage.success(
      out.attemptKind === 'EXAM'
        ? '整卷已交，可以查看答案'
        : out.isPassed
          ? '恭喜，您已通过本次练习'
          : '提交完成，请查看错题分析'
    )
  } catch {
    // 重试用完仍失败：保留幂等键，学员再点提交仍是同一次动作。
    // 若那几次里其实有一次到达了服务端，重试会拿回原成绩而不是报重复提交。
    ElMessage.error('提交未成功，作答仍在本页面，可稍后再次点击提交')
  } finally {
    submitting.value = false
  }
}

const goBack = () => {
  router.push('/practice')
}

const retryPractice = async () => {
  if (!record.value) return
  try {
    const next = await PracticeApi.startPractice({
      caseId: record.value.caseId,
      mode: 'SELECTED'
    })
    router.replace({
      path: '/practice/workstation',
      query: { sessionId: String(next.id), caseId: String(record.value.caseId) }
    })
    record.value = next
    diagForm.value = { drGrade: '', diagnosis: '' }
    canvasState.annotations = []
    canvasState.measurements = []
    canvasState.history = []
    canvasState.redoStack = []
    canvasState.layers.gold = false
    goldData.value = null
    textAnswers.value = {}
    startTime.value = Date.now()
  } catch {
    /* ignore */
  }
}

/* ========== AI 参考诊断（CSU-EYES 真实算法） ========== */
const aiVisible = ref(false)
const aiCaseKey = computed(() => record.value?.caseNo || String(caseId.value || ''))

/* ========== 生命周期 ========== */
onMounted(async () => {
  if (!sessionId.value || !caseId.value) {
    ElMessage.warning('缺少 sessionId / caseId 参数')
    return
  }
  // 先取会话（拿到权威 caseId），再按会话病例拉影像，保证图文一致
  await loadRecord()
  await fetchSource()
  if (record.value?.answersOpen) {
    await loadGoldStandard()
  }
  startTime.value = Date.now()
})

const hintLoading = ref(false)
const revealHint = async () => {
  if (!record.value || isExam.value) return
  hintLoading.value = true
  try {
    record.value = await PracticeApi.nextHint(record.value.id)
  } finally {
    hintLoading.value = false
  }
}

watch(sessionId, async (id, prev) => {
  if (!prev || !id || id === prev) return
  textAnswers.value = {}
  structuredAnswer.value = {}
  canvasState.annotations = []
  canvasState.measurements = []
  goldData.value = null
  canvasState.layers.gold = false
  activeLocateCode.value = ''
  submitRequestId.value = ''
  startTime.value = Date.now()
  await loadRecord()
  await fetchSource()
})

watch(currentImageIndex, () => {
  // 切换影像不清空标注（练习以单张为主，兼容多张）
})
</script>

<template>
  <div class="workstation-page">
    <header class="ws-header">
      <div class="left">
        <el-button :icon="Back" text @click="goBack">
          返回练习
        </el-button>
        <span class="ws-title">
          {{ isExam ? '正式考试' : '自主练习工作站' }}
          <span v-if="isExam && record" class="case-no">
            · 第 {{ record.examIndex }} / {{ record.examTotal }} 题
          </span>
          <span v-else-if="record" class="case-no">· {{ record.caseNo }}</span>
        </span>
      </div>
      <div class="right">
        <el-tag v-if="record?.answersOpen" size="small" type="success">
          得分 {{ Number(record.scoreTotal || 0).toFixed(1) }}
          {{ record.isPassed ? '(通过)' : '(未通过)' }}
        </el-tag>
        <el-button
          v-if="!viewMode && !reviewMode && record?.status === 'DRAFT'"
          type="primary"
          size="small"
          :loading="submitting"
          @click="handleSubmit"
        >
          {{ examContinues ? '交本题，继续下一题' : isExam ? '交卷' : '提交作答' }}
        </el-button>
      </div>
    </header>

    <div class="ws-body">
      <!-- 左侧工具栏 -->
      <ReadingToolbar
        v-if="!viewMode && !reviewMode"
        :tool="canvasState.tool"
        :can-annotate="!viewMode && !reviewMode && record?.status === 'DRAFT'"
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
        <div v-if="activeLocateTask" class="locate-banner">{{ activeLocateTask.prompt }}</div>
        <div v-if="sourceLoading" v-loading="true" class="loading-mask">影像加载中…</div>
        <CoreRetinaStation
          v-else-if="currentImage"
          :dicom-image-id="currentDicomImageId"
          mode="practice"
          :image-url="currentImage"
          :tool="canvasState.tool"
          :annotations="canvasState.annotations"
          :measurements="canvasState.measurements"
          :viewport="canvasState.viewport"
          :layers="canvasState.layers"
          :readonly="viewMode || reviewMode || record?.status !== 'DRAFT'"
          :gold-annotations="goldAnnotations"
          :gold-overlay-url="goldOverlayUrl"
          :locate="locateRequest"
          :laterality="locateEye"
          :segmentation="record?.answersOpen ? (source?.segmentation || null) : null"
          @update:annotations="onAnnotationsChange"
          @pick-label="onPickLabel"
          @update:measurements="onMeasurementsChange"
          @update:viewport="(v: any) => (canvasState.viewport = v)"
        />
        <div v-else class="empty">暂无影像</div>

        <!-- 多图切换 -->
        <div v-if="source && source.images.length > 1" class="image-strip">
          <div
            v-for="(img, i) in source.images"
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

      <!-- 右侧面板 -->
      <aside class="side-panel">
        <div
          v-if="!viewMode && !reviewMode && record?.status === 'DRAFT' && !isExam"
          class="panel-section"
        >
          <h3>提示</h3>
          <p class="score-legend">平时练习可以一则一则看。点一次多看一则，不会一次把后面的都打开。</p>
          <p v-for="(hint, i) in record?.hints || []" :key="i" class="score-legend">
            {{ i + 1 }}. {{ hint }}
          </p>
          <el-button
            size="small"
            :loading="hintLoading"
            :disabled="!(record?.hintsLeft)"
            @click="revealHint"
          >
            {{ record?.hintsLeft ? '查看下一则提示' : '没有更多提示了' }}
          </el-button>
        </div>
        <div
          v-if="!viewMode && !reviewMode && isExam && record?.status === 'DRAFT'"
          class="panel-section"
        >
          <h3>正式考试</h3>
          <p class="score-legend">
            第 {{ record?.examIndex }} / {{ record?.examTotal }} 题。本场不能看提示，全部交卷后才显示答案和金标准。
          </p>
        </div>
        <!-- 诊断表单（答题模式） -->
        <div v-if="!viewMode && !reviewMode && record?.status === 'DRAFT'" class="panel-section">
          <h3>诊断作答</h3>
          <!-- 与阅片端共用同一套病种表单，保证两边结论口径一致 -->
          <DiagnosisForm
            v-if="diagnosisForm"
            v-model="structuredAnswer"
            :form="diagnosisForm"
            tone="dark"
          />
          <el-form v-else label-position="top" size="default">
            <el-form-item label="DR 分级">
              <el-radio-group v-model="diagForm.drGrade">
                <el-radio
                  v-for="o in PracticeApi.DR_GRADE_OPTIONS"
                  :key="o.value"
                  :value="o.value"
                  style="display: block; margin-bottom: 6px"
                >
                  {{ o.label }}
                </el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="诊断描述">
              <el-input
                v-model="diagForm.diagnosis"
                type="textarea"
                :rows="4"
                placeholder="请描述您的诊断意见…"
              />
            </el-form-item>
          </el-form>
        </div>

        <div v-if="locateTasks.length" class="panel-section">
          <h3>指出位置</h3>
          <p class="score-legend">
            勾选这些征象后，要在图上指出至少一处。微动脉瘤用点选，出血、渗出和新生血管用圈选，静脉串珠和 IRMA 标出象限。
          </p>
          <div v-for="task in locateTasks" :key="task.code" class="locate-row">
            <div>
              <strong>{{ task.label }}</strong>
              <span class="locate-method">{{ task.methodText }}</span>
              <span>{{ locateCount(task) ? `已指出 ${locateCount(task)} 处` : '还没指出' }}</span>
            </div>
            <div class="locate-actions">
              <el-button
                size="small"
                :type="activeLocateCode === task.code ? 'primary' : 'default'"
                @click="beginLocate(task)"
              >
                {{ activeLocateCode === task.code ? '结束指出' : task.action }}
              </el-button>
              <el-button size="small" :disabled="!locateCount(task)" @click="undoLocate(task)">
                去掉最后一处
              </el-button>
            </div>
          </div>
        </div>

        <div
          v-if="!viewMode && !reviewMode && record?.status === 'DRAFT' && textQuestions.length"
          class="panel-section"
        >
          <h3>文字题</h3>
          <p class="score-legend">知识点、选择、填空。交卷后计入这次总分。</p>
          <div v-for="(q, i) in textQuestions" :key="q.id" class="quiz-item">
            <div class="quiz-stem">
              <el-tag size="small" effect="plain">{{ q.kindText }}</el-tag>
              <span>{{ i + 1 }}. {{ q.stem }}</span>
            </div>
            <el-radio-group
              v-if="q.options?.length"
              v-model="textAnswers[q.id]"
              class="quiz-options"
            >
              <el-radio v-for="opt in q.options" :key="opt" :value="opt">{{ opt }}</el-radio>
            </el-radio-group>
            <el-input
              v-else
              v-model="textAnswers[q.id]"
              placeholder="填在横线上的内容"
              maxlength="40"
            />
          </div>
        </div>

        <!-- 报告模式 -->
        <div v-if="record?.answersOpen" class="panel-section report">
          <h3>
            评分报告
            <!-- 两套口径的分数不可直接横向比较，界面上必须说清是哪一套 -->
            <el-tag size="small" :type="record?.scoringMode === 'structured' ? 'success' : 'info'">
              {{ record?.scoringMode === 'structured' ? '结构化评分' : '关键词评分（旧口径）' }}
            </el-tag>
            <!-- 旧版标注分规则在无病灶病例上把总分封顶到 85，
                 与新记录不可直接比较，须标出来 -->
            <el-tooltip
              v-if="(record?.scoreRuleVersion || 1) < 2"
              content="该成绩按旧版标注分规则计算：无金标准标注框的病例上，全对也只有 70 分，总分封顶 85。与新记录不可直接比较。"
              placement="top"
            >
              <el-tag size="small" type="warning">旧版标注分规则</el-tag>
            </el-tooltip>
          </h3>
          <div class="score-grid">
            <div class="score-item">
              <span class="label">总分</span>
              <span class="value big" :class="{ pass: record?.isPassed }">
                {{ Number(record?.scoreTotal || 0).toFixed(1) }}
              </span>
            </div>
            <div class="score-item">
              <span class="label">分级</span>
              <span class="value">{{ gradeScoreText }}</span>
            </div>
            <div class="score-item">
              <span class="label">标注</span>
              <span class="value">{{ annotationScoreText }}</span>
            </div>
            <div class="score-item">
              <span class="label">诊断</span>
              <span class="value">{{ diagnosisScoreText }}</span>
            </div>
            <div class="score-item">
              <span class="label">文字题</span>
              <span class="value">{{ textScoreText }}</span>
            </div>
            <div class="score-item">
              <span class="label">框重合</span>
              <span class="value">{{ iouScoreText }}</span>
            </div>
            <div class="score-item">
              <span class="label">找到比例</span>
              <span class="value">{{ foundScoreText }}</span>
            </div>
          </div>
          <p class="score-legend">
            分级：你判的 DR 等级和标准答案差几级。一致是 100，每差 1 级扣 25。这例不考分级时显示「未考」。
            标注：金标准框有没有标到。没有框就显示「未考」，不会因为没画框给 100。有框但没标是 0。
            诊断：结论和标准答案对上了多少。没写是 0。
            框重合：你画的框和标准框重叠多少，1 是完全重合。没画框时显示「未标注」。
            找到比例：标准框里你标中了几成，不是整张图的诊断对错。
            文字题：知识点、选择和填空答对的比例。这次练习里它占总分的 20%，分级 25%、标注 40%、诊断 15%。没写算错。更早的成绩没有这项，显示「未考」。
          </p>
          <div v-if="record?.textItems?.length" class="text-result">
            <h4>文字题</h4>
            <div v-for="item in record.textItems" :key="item.id" class="text-result-item">
              <div class="quiz-stem">
                <el-tag size="small" effect="plain">{{ item.kindText }}</el-tag>
                <span :class="item.correct ? 'ok' : 'bad'">{{ item.correct ? '对' : '错' }}</span>
              </div>
              <p>{{ item.stem }}</p>
              <p>你的答案：{{ item.yours || '未写' }}。标准答案：{{ item.expected }}。{{ item.explanation }}</p>
            </div>
          </div>
          <p v-if="staleAnnotationCredit" class="score-legend">
            这份是较早的成绩：当时没有金标准框，没画标注也被记成 100 并算进了总分。上面已改成「未考」。再练一次提交后，总分不再把这项算成满分。
          </p>

          <div v-if="record?.errorPoints?.length" class="error-list">
            <h4>错误点</h4>
            <div v-for="(ep, i) in record.errorPoints" :key="i" class="error-item">
              <el-tag size="small" :type="epTagType(ep.type)">{{ epText(ep.type) }}</el-tag>
              <span class="ep-label">{{ ep.label }}</span>
              <span v-if="ep.note" class="ep-note">{{ ep.note }}</span>
            </div>
          </div>

          <div v-if="record?.suggestion" class="suggestion">
            <h4>学习建议</h4>
            <p>{{ record.suggestion }}</p>
          </div>

          <p v-if="record && record.status !== 'DRAFT'" class="score-legend">
            {{ record.isPassed ? '系统判定合格' : '系统判定不合格' }}。
            {{
              isExam
                ? '正式考试在全部题目交卷后才公布答案，不送教师评定。'
                : '自主练习在提交时就算完分，不送教师评定。'
            }}
          </p>

          <div class="layer-toggle">
            <el-checkbox v-model="canvasState.layers.gold" @change="onGoldToggle">
              显示金标准图层
            </el-checkbox>
            <p class="gold-hint">{{ goldLayerHint }}</p>
            <el-checkbox v-model="canvasState.layers.my">
              显示我的标注
            </el-checkbox>
          </div>

          <!-- AI 参考：学生 vs AI vs 金标准 三方对比 -->
          <div class="ai-ref">
            <el-button
              type="success"
              plain
              :icon="MagicStick"
              style="width: 100%"
              @click="aiVisible = true"
            >
              查看 AI 参考判读（对比热力图）
            </el-button>
            <p class="ai-ref-tip">
              由 CSU-EYES 算法服务实时推理，展示 AI 分级与 GradCAM 关注区域
            </p>
          </div>

          <div class="report-actions">
            <el-button type="primary" @click="retryPractice">再练一次</el-button>
            <el-button @click="goBack">返回列表</el-button>
          </div>
        </div>
      </aside>
    </div>

    <!-- AI 参考诊断弹窗 -->
    <AiDiagnosisDialog
      v-model:visible="aiVisible"
      :case-id="aiCaseKey"
      :student-grade="record?.studentDrGrade"
    />
  </div>
</template>

<style scoped>
.workstation-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0f1014;
  color: #e5e6eb;
}
.ws-header {
  height: 48px;
  padding: 0 16px;
  background: #181a20;
  border-bottom: 1px solid #2a2a2a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.ws-header .left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ws-title {
  font-size: 14px;
  font-weight: 600;
}
.ws-header :deep(.el-button.is-text) {
  color: #e8eaed;
  font-weight: 500;
}
.ws-header :deep(.el-button.is-text:hover) {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}
.case-no {
  color: #4091ff;
  font-family: 'Consolas', monospace;
}
.ws-header .right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ws-body {
  flex: 1;
  display: grid;
  grid-template-columns: 64px 1fr 340px;
  min-height: 0;
}
.locate-banner {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 6;
  max-width: 72%;
  background: rgba(20, 22, 28, 0.92);
  color: #f5f7fa;
  border: 1px solid #3a3f4b;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  line-height: 1.5;
  pointer-events: none;
}
.locate-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
  color: #e8eaed;
  font-size: 13px;
}
.locate-method {
  margin: 0 8px;
  color: #c5cad3;
}
.locate-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.canvas-area {
  position: relative;
  background: #0e0f12;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.loading-mask, .empty {
  color: #c5cad3;
  font-size: 14px;
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
}
.strip-cell {
  width: 48px;
  height: 48px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  position: relative;
  border: 2px solid transparent;
}
.strip-cell.active { border-color: #4091ff; }
.strip-cell img { width: 100%; height: 100%; object-fit: cover; }
.strip-label {
  position: absolute;
  bottom: 2px;
  right: 4px;
  font-size: 10px;
  color: #fff;
  text-shadow: 0 1px 2px #000;
}

.side-panel {
  background: #181a20;
  border-left: 1px solid #2a2a2a;
  overflow-y: auto;
  padding: 16px;
}
.panel-section h3 {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #f5f7fa;
  letter-spacing: 0.3px;
}
.side-panel :deep(.el-form-item__label) {
  color: #f5f7fa;
  font-size: 14px;
  font-weight: 600;
}
.side-panel :deep(.el-radio__label),
.side-panel :deep(.el-checkbox__label) {
  color: #eef1f6;
  font-size: 13px;
  font-weight: 500;
}
.panel-section h4 {
  margin: 14px 0 6px;
  font-size: 13px;
  color: #c9cdd4;
}
.quiz-item { margin-bottom: 14px; }
.quiz-stem {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 8px;
  color: #eef1f6;
  line-height: 1.55;
  font-size: 13px;
}
.quiz-options {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.text-result-item {
  margin-bottom: 10px;
  color: #d5dae3;
  font-size: 13px;
  line-height: 1.55;
}
.text-result-item p { margin: 4px 0; }
.text-result-item .ok { color: #7be0a2; }
.text-result-item .bad { color: #ffb4b4; }

.score-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}
.score-item {
  background: #1e2028;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}
.score-item .label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #d5dae3;
}
.score-item .value {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #e5e6eb;
  margin-top: 4px;
}
.score-item .value.big {
  font-size: 24px;
}
.score-item .value.pass {
  color: #00e676;
}
.score-legend,
.gold-hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.55;
  color: #d5dae3;
}

.error-list {
  max-height: 200px;
  overflow-y: auto;
}
.error-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 12px;
}
.ep-label { color: #e5e6eb; }
.ep-note { color: #d5dae3; }

.suggestion p, .teacher-comment p {
  font-size: 13px;
  color: #c9cdd4;
  line-height: 1.6;
  margin: 0;
}
.teacher-review {
  margin-top: 8px;
}
.review-hint {
  margin: 0 0 8px;
  font-size: 13px;
  color: #d5dae3;
  line-height: 1.5;
}
.review-grade {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #c9cdd4;
}

.layer-toggle {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-ref {
  margin-top: 16px;
}
.ai-ref-tip {
  margin: 6px 0 0;
  font-size: 13px;
  color: #d5dae3;
  line-height: 1.5;
}

.report-actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>
