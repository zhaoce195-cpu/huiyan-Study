<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, MagicStick } from '@element-plus/icons-vue'

import { PracticeApi, ReadingApi } from '@/api'
import { ensureCornerstone } from '@/utils/cornerstone'

import ReadingToolbar from '@/views/reading/components/ReadingToolbar.vue'
import ReadingCanvas from '@/views/reading/components/ReadingCanvas.vue'
import AiDiagnosisDialog from '@/components/AiDiagnosisDialog.vue'
import type { ToolName, AnnotationItem, CanvasState } from '@/views/reading/types'

const route = useRoute()
const router = useRouter()

const sessionId = computed(() => Number(route.query.sessionId || 0))
const caseId = computed(() => Number(route.query.caseId || 0))
const viewMode = computed(() => route.query.view === 'report')

/* ========== 影像源 ========== */
const source = ref<ReadingApi.ImageSource | null>(null)
const sourceLoading = ref(false)
const currentImageIndex = ref(0)
const currentImage = computed(() => source.value?.images?.[currentImageIndex.value] || '')

/* ========== 练习记录 ========== */
const record = ref<PracticeApi.PracticeRecord | null>(null)
const goldData = ref<PracticeApi.GoldStandardData | null>(null)
const goldAnnotations = computed<AnnotationItem[]>(() => {
  if (!goldData.value) return []
  return (goldData.value.annotations || []) as AnnotationItem[]
})

/* ========== 画布状态 ========== */
const canvasState = reactive<CanvasState>({
  tool: 'pan',
  annotations: [],
  measurements: [],
  history: [],
  redoStack: [],
  viewport: { scale: 1, x: 0, y: 0, ww: 255, wl: 127, invert: false },
  layers: { primary: true, heatmap: false, gold: false, my: true }
})

/* ========== 诊断表单 ========== */
const diagForm = ref({
  drGrade: '',
  diagnosis: ''
})
const submitting = ref(false)
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

const onAnnotationsChange = (next: AnnotationItem[]) => {
  canvasState.history.push({
    annotations: JSON.parse(JSON.stringify(canvasState.annotations)),
    measurements: JSON.parse(JSON.stringify(canvasState.measurements))
  })
  if (canvasState.history.length > 50) canvasState.history.shift()
  canvasState.redoStack = []
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
const epText = (t: PracticeApi.ErrorPointType) => {
  if (t === 'missed') return '漏标'
  if (t === 'false_positive') return '误标'
  if (t === 'wrong_label') return '标签错'
  if (t === 'low_iou') return 'IoU 低'
  return '其他'
}

/* ========== 数据加载 ========== */
const fetchSource = async () => {
  if (!caseId.value) return
  sourceLoading.value = true
  try {
    source.value = await ReadingApi.getImageSource(caseId.value)
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
    if (record.value) {
      diagForm.value.drGrade = record.value.studentDrGrade || ''
      diagForm.value.diagnosis = record.value.studentDiagnosis || ''
      canvasState.annotations = (record.value.studentAnnotations || []) as AnnotationItem[]
      canvasState.measurements = (record.value.studentMeasurements || []) as AnnotationItem[]
      if (record.value.viewport) canvasState.viewport = record.value.viewport as any
    }
  } catch {
    record.value = null
  }
}

const loadGoldStandard = async () => {
  if (!caseId.value) return
  if (record.value?.status === 'DRAFT') return
  try {
    goldData.value = await PracticeApi.getGoldStandard(caseId.value)
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
  if (!diagForm.value.drGrade) {
    ElMessage.warning('请选择 DR 分级')
    return
  }
  try {
    await ElMessageBox.confirm(
      '提交后将自动评分，且无法再修改本次作答，确认提交？',
      '提交确认',
      { type: 'warning' }
    )
  } catch { return }

  submitting.value = true
  try {
    const duration = Math.floor((Date.now() - startTime.value) / 1000)
    const out = await PracticeApi.submitPractice({
      sessionId: record.value.id,
      studentDrGrade: diagForm.value.drGrade,
      studentDiagnosis: diagForm.value.diagnosis,
      annotations: canvasState.annotations,
      measurements: canvasState.measurements,
      viewport: canvasState.viewport,
      durationSeconds: duration
    })
    record.value = out
    await loadGoldStandard()
    ElMessage.success(out.isPassed ? '恭喜，您已通过本次练习' : '提交完成，请查看错题分析')
  } catch {
    /* error already shown */
  } finally {
    submitting.value = false
  }
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
  ensureCornerstone()
  if (!sessionId.value || !caseId.value) {
    ElMessage.warning('缺少 sessionId / caseId 参数')
    return
  }
  await Promise.all([fetchSource(), loadRecord()])
  if (record.value && record.value.status !== 'DRAFT') {
    await loadGoldStandard()
  }
  startTime.value = Date.now()
})

watch(currentImageIndex, () => {
  // 切换影像不清空标注（练习以单张为主，兼容多张）
})
</script>

<template>
  <div class="workstation-page">
    <header class="ws-header">
      <div class="left">
        <el-button :icon="Back" text @click="router.push('/practice')">返回练习</el-button>
        <span class="ws-title">
          自主练习工作站
          <span v-if="record" class="case-no">· {{ record.caseNo }}</span>
        </span>
      </div>
      <div class="right">
        <el-tag v-if="record && record.status !== 'DRAFT'" size="small" type="success">
          得分 {{ Number(record.scoreTotal || 0).toFixed(1) }}
          {{ record.isPassed ? '(通过)' : '(未通过)' }}
        </el-tag>
        <el-button
          v-if="!viewMode && record?.status === 'DRAFT'"
          type="primary"
          size="small"
          :loading="submitting"
          @click="handleSubmit"
        >
          提交作答
        </el-button>
      </div>
    </header>

    <div class="ws-body">
      <!-- 左侧工具栏 -->
      <ReadingToolbar
        v-if="!viewMode"
        :tool="canvasState.tool"
        :can-annotate="!viewMode && record?.status === 'DRAFT'"
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
        <div v-if="sourceLoading" v-loading="true" class="loading-mask">影像加载中…</div>
        <ReadingCanvas
          v-else-if="currentImage"
          :image-url="currentImage"
          :tool="canvasState.tool"
          :annotations="canvasState.annotations"
          :measurements="canvasState.measurements"
          :viewport="canvasState.viewport"
          :layers="canvasState.layers"
          :readonly="viewMode || record?.status !== 'DRAFT'"
          :gold-annotations="goldAnnotations"
          @update:annotations="onAnnotationsChange"
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
        <!-- 诊断表单（答题模式） -->
        <div v-if="!viewMode && record?.status === 'DRAFT'" class="panel-section">
          <h3>诊断作答</h3>
          <el-form label-position="top" size="default">
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

        <!-- 报告模式 -->
        <div v-if="viewMode || (record && record.status !== 'DRAFT')" class="panel-section report">
          <h3>评分报告</h3>
          <div class="score-grid">
            <div class="score-item">
              <span class="label">总分</span>
              <span class="value big" :class="{ pass: record?.isPassed }">
                {{ Number(record?.scoreTotal || 0).toFixed(1) }}
              </span>
            </div>
            <div class="score-item">
              <span class="label">分级</span>
              <span class="value">{{ Number(record?.scoreGrade || 0).toFixed(0) }}</span>
            </div>
            <div class="score-item">
              <span class="label">标注</span>
              <span class="value">{{ Number(record?.scoreAnnotation || 0).toFixed(0) }}</span>
            </div>
            <div class="score-item">
              <span class="label">诊断</span>
              <span class="value">{{ Number(record?.scoreDiagnosis || 0).toFixed(0) }}</span>
            </div>
            <div class="score-item">
              <span class="label">IoU</span>
              <span class="value">{{ Number(record?.iouAvg || 0).toFixed(2) }}</span>
            </div>
            <div class="score-item">
              <span class="label">准确率</span>
              <span class="value">{{ (Number(record?.accuracy || 0) * 100).toFixed(0) }}%</span>
            </div>
          </div>

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

          <div v-if="record?.teacherComment" class="teacher-comment">
            <h4>教师点评</h4>
            <p>{{ record.teacherComment }}</p>
          </div>

          <div class="layer-toggle">
            <el-checkbox v-model="canvasState.layers.gold" @change="onGoldToggle">
              显示金标准图层
            </el-checkbox>
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
            <el-button @click="router.push('/practice')">返回列表</el-button>
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
.canvas-area {
  position: relative;
  background: #0e0f12;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.loading-mask, .empty {
  color: #4e5969;
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
  font-size: 14px;
  font-weight: 600;
  color: #e5e6eb;
}
.panel-section h4 {
  margin: 14px 0 6px;
  font-size: 13px;
  color: #c9cdd4;
}

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
  font-size: 11px;
  color: #86909c;
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
.ep-note { color: #86909c; }

.suggestion p, .teacher-comment p {
  font-size: 13px;
  color: #c9cdd4;
  line-height: 1.6;
  margin: 0;
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
  font-size: 11px;
  color: #86909c;
  line-height: 1.5;
}

.report-actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>
