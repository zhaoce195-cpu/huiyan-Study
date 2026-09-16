<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElInput, ElInputNumber, ElMessage } from 'element-plus'
import { Delete, View, Hide } from '@element-plus/icons-vue'
import type {
  AnnotationItem,
  LayerState,
  ViewportState
} from '../types'
import type { ReadingApi } from '@/api'

type ReadingRecord = ReadingApi.ReadingRecord

const props = defineProps<{
  viewport: ViewportState
  layers: LayerState
  annotations: AnnotationItem[]
  measurements: AnnotationItem[]
  existingRecord: ReadingRecord | null
  canReview: boolean
  reviewLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:viewport', v: ViewportState): void
  (e: 'update:layers', v: LayerState): void
  (e: 'remove-annotation', idx: number): void
  (e: 'remove-measurement', idx: number): void
  (e: 'review', accept: boolean, comment: string): void
}>()

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

const reviewComment = ref(props.existingRecord?.reviewComment || '')
watch(
  () => props.existingRecord?.reviewComment,
  (val) => {
    if (val && !reviewComment.value) reviewComment.value = val
  }
)

const onReview = (accept: boolean) => {
  if (!accept && !reviewComment.value.trim()) {
    ElMessage.warning('驳回需填写审核意见')
    return
  }
  emit('review', accept, reviewComment.value)
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
      <div class="row">
        <span class="muted">反相</span>
        <el-switch
          :model-value="viewport.invert"
          size="small"
          @update:model-value="(v: any) => updateInvert(!!v)"
        />
      </div>
      <div class="row">
        <span class="muted">窗宽窗位调节</span>
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
      <div class="row">
        <span class="muted"><el-icon><View /></el-icon> 我的标注</span>
        <el-switch
          :model-value="layers.my"
          size="small"
          @update:model-value="(v: any) => updateLayer('my', !!v)"
        />
      </div>
      <div class="row">
        <span class="muted"><el-icon><Hide /></el-icon> 病灶提示图层</span>
        <el-switch
          :model-value="layers.heatmap"
          size="small"
          @update:model-value="(v: any) => updateLayer('heatmap', !!v)"
        />
      </div>
      <div class="row">
        <span class="muted"><el-icon><Hide /></el-icon> 金标准</span>
        <el-switch
          :model-value="layers.gold"
          size="small"
          @update:model-value="(v: any) => updateLayer('gold', !!v)"
        />
      </div>
    </section>

    <!-- 标注列表 -->
    <section class="block">
      <div class="block-title">
        我的标注
        <span class="muted ml6">{{ annotations.length }}</span>
      </div>
      <div v-if="annotations.length === 0" class="empty">尚未进行标注</div>
      <div v-else class="ann-list">
        <div v-for="(a, i) in annotations" :key="a.id" class="ann-row">
          <span
            class="dot"
            :style="{ background: a.color || '#4091ff' }"
          />
          <span class="ann-tool">{{ a.tool }}</span>
          <span class="ann-label">{{ a.label }}</span>
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

    <!-- 测量列表 -->
    <section class="block">
      <div class="block-title">
        测量
        <span class="muted ml6">{{ measurements.length }}</span>
      </div>
      <div v-if="measurements.length === 0" class="empty">尚无测量数据</div>
      <div v-else class="ann-list">
        <div v-for="(m, i) in measurements" :key="m.id" class="ann-row">
          <span class="dot" :style="{ background: m.color || '#52c41a' }" />
          <span class="ann-tool">{{ m.tool }}</span>
          <span class="ann-label">
            {{ m.value !== undefined ? m.value.toFixed(1) + ' ' + (m.unit || '') : m.label }}
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
        title="本次阅片被驳回"
        description="请按审核意见修改后重新提交，仍是同一份记录。"
      />
    </section>

    <!-- 教师审核 -->
    <section v-if="canReview" class="block">
      <div class="block-title">审核</div>
      <ElInput
        v-model="reviewComment"
        type="textarea"
        :rows="3"
        placeholder="审核意见（驳回必填）"
        size="small"
      />
      <div class="review-btns">
        <el-button
          type="success"
          size="small"
          :loading="reviewLoading"
          @click="onReview(true)"
        >
          通过
        </el-button>
        <el-button
          type="danger"
          size="small"
          :loading="reviewLoading"
          @click="onReview(false)"
        >
          驳回
        </el-button>
      </div>
    </section>
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
  color: #e5e6eb;
  margin-bottom: 10px;
  font-size: 13px;
  display: flex;
  align-items: center;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}
.muted {
  color: #86909c;
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
  color: #4e5969;
  font-size: 12px;
  padding: 14px 0;
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
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ann-tool {
  color: #86909c;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px;
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

.review-btns {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
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
  width: 28px;
  flex-shrink: 0;
  color: #86909c;
  font-size: 12px;
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
