<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElInput, ElInputNumber, ElMessage } from 'element-plus'
import { Delete, View, Hide } from '@element-plus/icons-vue'
import type {
  AnnotationItem,
  LayerState,
  ViewportState
} from '../types'
import { markCaption } from '../types'
import type { ReadingApi } from '@/api'
import ReviewPresetChips from './ReviewPresetChips.vue'
import { EXCELLENT_PASS_COMMENT, appendReviewComment } from '../review-presets'

type ReadingRecord = ReadingApi.ReadingRecord

const props = defineProps<{
  viewport: ViewportState
  layers: LayerState
  annotations: AnnotationItem[]
  measurements: AnnotationItem[]
  existingRecord: ReadingRecord | null
  canReview: boolean
  reviewLoading: boolean
  reviewComment?: string
  diagnosisLines?: Array<{ label: string; text: string }>
  /** 开关打开但画面上没有对应内容时的说明，空字符串表示不提示 */
  layerNotes?: { primary?: string; heatmap?: string; gold?: string }
}>()

const emit = defineEmits<{
  (e: 'update:viewport', v: ViewportState): void
  (e: 'update:layers', v: LayerState): void
  (e: 'update:reviewComment', v: string): void
  (e: 'remove-annotation', idx: number): void
  (e: 'remove-measurement', idx: number): void
  (e: 'highlight', id: string): void
  (e: 'review', accept: boolean, comment: string): void
  (e: 'review-next', accept: boolean, comment: string): void
}>()

const hoverId = ref('')
const enterMark = (id: string) => {
  hoverId.value = id
  emit('highlight', id)
}
const leaveMark = () => {
  hoverId.value = ''
  emit('highlight', '')
}

const wwwc = computed({
  get: () => [props.viewport.ww, props.viewport.wl] as [number, number],
  set: (v) => {
    emit('update:viewport', { ...props.viewport, ww: v[0], wl: v[1] })
  }
})

const updateLayer = (key: keyof LayerState, val: boolean) => {
  emit('update:layers', { ...props.layers, [key]: val })
}

const updateInvert = (val: boolean) => {
  emit('update:viewport', { ...props.viewport, invert: val })
}

const advancedOpen = ref<string[]>([])
const reviewComment = computed({
  get: () => props.reviewComment ?? '',
  set: (value: string) => emit('update:reviewComment', value)
})

const onReview = (accept: boolean) => {
  if (!accept && !reviewComment.value.trim()) {
    ElMessage.warning('驳回需填写审核意见')
    return
  }
  emit('review', accept, reviewComment.value)
}

const onReviewNext = (accept: boolean) => {
  if (!accept && !reviewComment.value.trim()) {
    ElMessage.warning('驳回需填写审核意见')
    return
  }
  emit('review-next', accept, reviewComment.value)
}

const addPreset = (phrase: string) => {
  if (props.reviewLoading) return
  reviewComment.value = appendReviewComment(reviewComment.value, phrase)
}

const CUSTOM_KEY = 'huiyan_doctor_custom_presets'
const customPresets = ref<string[]>([])
onMounted(() => {
  try {
    const raw = JSON.parse(localStorage.getItem(CUSTOM_KEY) || '[]')
    customPresets.value = Array.isArray(raw) ? raw.filter((item) => typeof item === 'string') : []
  } catch {
    customPresets.value = []
  }
})
const saveCustomPreset = () => {
  const text = (reviewComment.value || '').trim()
  if (!text) {
    ElMessage.warning('请先在审核意见框中输入评语')
    return
  }
  if (customPresets.value.includes(text)) {
    ElMessage.info('该短语已在常用列表中')
    return
  }
  customPresets.value.unshift(text)
  if (customPresets.value.length > 12) customPresets.value.pop()
  localStorage.setItem(CUSTOM_KEY, JSON.stringify(customPresets.value))
  ElMessage.success('已存入常用评语')
}
const onRemoveCustom = (index: number) => {
  customPresets.value.splice(index, 1)
  localStorage.setItem(CUSTOM_KEY, JSON.stringify(customPresets.value))
}

const passAsExcellent = () => {
  if (props.reviewLoading) return
  reviewComment.value = EXCELLENT_PASS_COMMENT
  onReview(true)
}
</script>

<template>
  <aside class="side-panel">
    <!-- 视口 -->
    <section class="block">
      <div class="block-title">视口</div>
      <div class="row">
        <span class="muted">缩放</span>
        <span class="value">{{ Math.round(viewport.scale * 100) }}%</span>
      </div>
      <div class="row">
        <span class="muted">窗宽 / 窗位</span>
        <span class="value">
          {{ Math.round(viewport.ww) }} / {{ Math.round(viewport.wl) }}
        </span>
      </div>
    </section>

    <!-- 图层 -->
    <section class="block">
      <div class="block-title">图层</div>
      <div class="row">
        <span class="muted"><el-icon><View /></el-icon> 原图</span>
        <el-switch
          :model-value="layers.primary"
          size="small"
          @update:model-value="(v: any) => updateLayer('primary', !!v)"
        />
      </div>
      <p v-if="layerNotes?.primary" class="layer-note">{{ layerNotes.primary }}</p>
      <div class="row">
        <span class="muted"><el-icon><View /></el-icon> {{ canReview ? '学员标注' : '我的标注' }}</span>
        <el-switch
          :model-value="layers.my"
          size="small"
          @update:model-value="(v: any) => updateLayer('my', !!v)"
        />
      </div>
      <div class="row">
        <span class="muted"><el-icon><Hide /></el-icon> AI 热力图</span>
        <el-switch
          :model-value="layers.heatmap"
          size="small"
          @update:model-value="(v: any) => updateLayer('heatmap', !!v)"
        />
      </div>
      <p v-if="layerNotes?.heatmap" class="layer-note">{{ layerNotes.heatmap }}</p>
      <div class="row">
        <span class="muted"><el-icon><Hide /></el-icon> 金标准</span>
        <el-switch
          :model-value="layers.gold"
          size="small"
          @update:model-value="(v: any) => updateLayer('gold', !!v)"
        />
      </div>
      <p v-if="layerNotes?.gold" class="layer-note">{{ layerNotes.gold }}</p>
    </section>

    <!-- 标注列表 -->
    <section class="block">
      <div class="block-title">
        {{ canReview ? '学员标注' : '我的标注' }}
        <span class="muted ml6">{{ annotations.length }}</span>
      </div>
      <p class="ann-hint">编号和图上左上角的字是同一条。鼠标停在某一行上，图里对应的框会亮起来。在图上右键那一条，可以直接删除。</p>
      <div v-if="annotations.length === 0" class="empty">尚未进行标注</div>
      <div v-else class="ann-list">
        <div
          v-for="(a, i) in annotations"
          :key="a.id"
          class="ann-row"
          :class="{ active: hoverId === a.id }"
          @mouseenter="enterMark(a.id)"
          @mouseleave="leaveMark"
        >
          <span
            class="dot"
            :style="{ background: a.color || '#4091ff' }"
          />
          <span class="ann-label">{{ markCaption(annotations, i) }}</span>
          <el-button
            text
            type="danger"
            size="small"
            :icon="Delete"
            @click="emit('remove-annotation', i)"
          />
        </div>
      </div>
    </section>

    <section v-if="diagnosisLines?.length" class="block">
      <div class="block-title">诊断结论</div>
      <div v-for="line in diagnosisLines" :key="line.label" class="row">
        <span class="muted">{{ line.label }}</span>
        <span class="value">{{ line.text }}</span>
      </div>
    </section>

    <!-- 已有阅片记录 -->
    <section v-if="existingRecord" class="block">
      <div class="block-title">阅片记录</div>
      <div class="row">
        <span class="muted">提交人</span>
        <span class="value">{{ existingRecord.userName || '—' }}</span>
      </div>
      <div class="row">
        <span class="muted">最后更新</span>
        <span class="value small">{{ existingRecord.updatedAt || '—' }}</span>
      </div>
      <div v-if="existingRecord.note" class="record-note">
        <div class="muted">备注：</div>
        <div>{{ existingRecord.note }}</div>
      </div>
      <div v-if="existingRecord.reviewComment" class="record-note">
        <div class="muted">审核意见：</div>
        <div>{{ existingRecord.reviewComment }}</div>
      </div>
      <!-- 驳回后要明确告诉学员「该做什么」。
           只把状态标成「已驳回」，学员未必知道可以直接改这一份再交 -->
      <el-alert
        v-if="existingRecord.status === 'REJECTED'"
        type="warning"
        :closable="false"
        show-icon
        title="已载入被驳回的记录，请按审核意见修改后重交"
      />
    </section>

    <!-- 教师审核 -->
    <section v-if="canReview" class="block">
      <div class="review-title-row">
        <span class="block-title">审核</span>
        <el-button
          v-if="reviewComment.trim()"
          text
          type="primary"
          size="small"
          @click="saveCustomPreset"
        >
          + 存为常用
        </el-button>
      </div>
      <ElInput
        v-model="reviewComment"
        type="textarea"
        :rows="3"
        placeholder="审核意见（驳回必填，可点下方短语）"
        size="small"
      />
      <ReviewPresetChips
        tone="dark"
        :disabled="reviewLoading"
        :custom-list="customPresets"
        @pick="addPreset"
        @remove-custom="onRemoveCustom"
      />
      <el-button
        class="excellent-btn"
        type="success"
        size="small"
        plain
        :loading="reviewLoading"
        @click="passAsExcellent"
      >
        标为优秀并通过
      </el-button>
      <div class="review-next">
        <el-button
          type="success"
          size="small"
          :loading="reviewLoading"
          @click="onReviewNext(true)"
        >
          通过并审下一份 (Enter)
        </el-button>
        <el-button
          type="danger"
          plain
          size="small"
          :loading="reviewLoading"
          @click="onReviewNext(false)"
        >
          驳回并审下一份
        </el-button>
      </div>
      <div class="review-btns">
        <el-button
          type="success"
          size="small"
          plain
          :loading="reviewLoading"
          @click="onReview(true)"
        >
          仅通过
        </el-button>
        <el-button
          type="danger"
          size="small"
          plain
          :loading="reviewLoading"
          @click="onReview(false)"
        >
          仅驳回
        </el-button>
      </div>
    </section>

    <el-collapse v-model="advancedOpen" class="advanced-fold">
      <el-collapse-item title="高级图像参数调节" name="advanced">
        <div class="row">
          <span class="muted">反相</span>
          <el-switch
            :model-value="viewport.invert"
            size="small"
            @update:model-value="(v: any) => updateInvert(!!v)"
          />
        </div>
        <div class="ww-row">
          <span class="ww-label">窗宽</span>
          <el-slider
            v-model="wwwc[0]"
            :min="1"
            :max="600"
            :step="1"
            size="small"
            :show-tooltip="false"
            class="ww-slider"
            @update:model-value="
              (v: any) => emit('update:viewport', { ...viewport, ww: Number(v) })
            "
          />
          <el-input-number
            :model-value="Math.round(viewport.ww)"
            :min="1"
            :max="600"
            :step="1"
            size="small"
            :controls="false"
            class="ww-input"
            @update:model-value="
              (v: any) => emit('update:viewport', {
                ...viewport,
                ww: Math.min(600, Math.max(1, Number(v) || 1))
              })
            "
          />
        </div>
        <div class="ww-row">
          <span class="ww-label">窗位</span>
          <el-slider
            v-model="wwwc[1]"
            :min="-200"
            :max="600"
            :step="1"
            size="small"
            :show-tooltip="false"
            class="ww-slider"
            @update:model-value="
              (v: any) => emit('update:viewport', { ...viewport, wl: Number(v) })
            "
          />
          <el-input-number
            :model-value="Math.round(viewport.wl)"
            :min="-200"
            :max="600"
            :step="1"
            size="small"
            :controls="false"
            class="ww-input"
            @update:model-value="
              (v: any) => emit('update:viewport', {
                ...viewport,
                wl: Math.min(600, Math.max(-200, Number(v) || 0))
              })
            "
          />
        </div>
        <div class="block-title measure-title">
          测距 / 测角
          <span class="muted ml6">{{ measurements.length }}</span>
        </div>
        <div v-if="measurements.length === 0" class="empty">尚无测量数据</div>
        <div v-else class="ann-list">
          <div
            v-for="(m, i) in measurements"
            :key="m.id"
            class="ann-row"
            :class="{ active: hoverId === m.id }"
            @mouseenter="enterMark(m.id)"
            @mouseleave="leaveMark"
          >
            <span class="dot" :style="{ background: m.color || '#52c41a' }" />
            <span class="ann-label">
              {{ markCaption(measurements, i) }}
              <template v-if="m.value !== undefined">
                · {{ m.value.toFixed(1) }} {{ m.unit || '' }}
              </template>
            </span>
            <el-button
              text
              type="danger"
              size="small"
              :icon="Delete"
              @click="emit('remove-measurement', i)"
            />
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </aside>
</template>

<style scoped>
.side-panel {
  background: #181a20;
  border-left: 1px solid #2a2a2a;
  padding: 14px 14px 20px;
  overflow-y: auto;
  font-size: 13px;
}

.block {
  background: #1f2129;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.block-title {
  font-weight: 600;
  color: #f5f7fa;
  margin-bottom: 10px;
  font-size: 14px;
  letter-spacing: 0.2px;
  display: flex;
  align-items: center;
}
.review-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.review-title-row .block-title {
  margin-bottom: 0;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}
.layer-note {
  margin: 2px 0 8px;
  font-size: 12px;
  line-height: 1.45;
  color: #ffd58a;
}
.muted {
  color: #d5dae3;
  font-size: 13px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.value {
  color: #e5e6eb;
  font-family: 'Consolas', 'Monaco', monospace;
}
.value.small {
  font-size: 11px;
}
.ml6 {
  margin-left: 6px;
}

.empty {
  text-align: center;
  color: #c5cad3;
  font-size: 13px;
  padding: 14px 0;
}

.ann-hint {
  margin: 0 0 8px;
  color: #d5dae3;
  font-size: 12px;
  line-height: 1.5;
}
.ann-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ann-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #25272f;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: default;
}
.ann-row.active {
  background: #1d4f91;
  outline: 1px solid #8eb7ff;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ann-tool {
  color: #d5dae3;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  flex-shrink: 0;
}
.ann-label {
  flex: 1;
  color: #e5e6eb;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-note {
  margin-top: 8px;
  font-size: 12px;
  color: #c9cdd4;
}

.review-next,
.review-btns {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}
.review-next {
  flex-direction: column;
}
.review-next :deep(.el-button) {
  margin-left: 0;
}
.advanced-fold {
  border: none;
  margin-bottom: 12px;
}
.advanced-fold :deep(.el-collapse-item__header) {
  background: #1f2129;
  color: #d5dae3;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 0 12px;
  height: 40px;
  font-size: 13px;
  font-weight: 600;
}
.advanced-fold :deep(.el-collapse-item__wrap) {
  background: #1f2129;
  border: 1px solid #2a2a2a;
  border-top: none;
  border-radius: 0 0 8px 8px;
}
.advanced-fold :deep(.el-collapse-item__content) {
  color: #d5dae3;
  padding: 4px 12px 12px;
}
.advanced-fold :deep(.el-collapse-item__arrow) {
  color: #9aa1af;
}
.measure-title {
  margin-top: 12px;
}
.excellent-btn {
  width: 100%;
  margin-top: 10px;
}

/* 窗宽 / 窗位：滑块 + 数值输入框 同行 */
.ww-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.ww-label {
  width: 32px;
  flex-shrink: 0;
  color: #d5dae3;
  font-size: 13px;
  font-weight: 500;
}
.ww-slider {
  flex: 1;
  min-width: 0;
}
.ww-input {
  width: 64px;
  flex-shrink: 0;
}
.ww-input :deep(.el-input__inner) {
  text-align: center;
  font-family: 'Consolas', 'Monaco', monospace;
}
</style>
