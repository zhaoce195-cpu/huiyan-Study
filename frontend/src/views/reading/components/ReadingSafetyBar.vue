<script setup lang="ts">
/**
 * 阅片安全条（常驻）
 *
 * 对应《医学培训端评估与工作流重构报告》P0/P1：
 *   「阅片主界面没有持续显示 OD/OS、中文眼别、检查日期、模态、图像质量和方向信息」
 *   验收门槛「三秒安全核对」：打开任意病例，3 秒内能准确说出
 *   患者/病例 ID、OD/OS、日期、模态和质量。
 *
 * 设计约束：
 *   1. 常驻不折叠：全屏、切图、弹窗时均保持可见；
 *   2. 未知即显示未知：绝不用入库时间冒充检查日期、不猜眼别；
 *   3. 眼别冲突醒目告警，不静默取值；
 *   4. 颜色只作冗余提示，信息本身一律有文字。
 */
import { computed } from 'vue'
import { Warning } from '@element-plus/icons-vue'

interface ImageMeta {
  url?: string
  eye?: string
  eyeText?: string
  role?: string
  roleText?: string
  isOriginal?: boolean
  quality?: string
  qualityText?: string
  lateralityConflict?: string | null
  originalIndex?: number | null
  originalTotal?: number
}

interface SafetySummary {
  originalCount?: number
  derivedCount?: number
  ungradableCount?: number
  unevaluatedCount?: number
  hasUngradable?: boolean
  qualityChecked?: boolean
  gradedTotal?: number
  eyesText?: string
  hasLateralityConflict?: boolean
  lateralityConflicts?: string[]
}

const props = withDefaults(defineProps<{
  caseNo?: string
  patientName?: string
  modalityText?: string
  examDate?: string | null
  examDateKnown?: boolean
  current?: ImageMeta | null
  safety?: SafetySummary | null
  statusText?: string
}>(), {
  caseNo: '',
  patientName: '',
  modalityText: '眼底彩照',
  examDate: null,
  examDateKnown: false,
  current: null,
  safety: null,
  statusText: ''
})

/** 眼别：无数据时显式提示未知，不留空 */
const eyeText = computed(() => props.current?.eyeText || '眼别未知')
const eyeCode = computed(() => {
  const c = props.current?.eye || ''
  return ['OD', 'OS', 'OU'].includes(c) ? c : '—'
})
const eyeUnknown = computed(() => !['OD', 'OS', 'OU'].includes(props.current?.eye || ''))

const examDateText = computed(() => {
  if (props.examDateKnown && props.examDate) return props.examDate.slice(0, 10)
  return '检查日期未提供'
})

const qualityText = computed(() => props.current?.qualityText || '未评估')
const qualityUnknown = computed(
  () => !props.current?.quality || props.current.quality === 'unknown'
)
const qualityBad = computed(
  () => ['poor', 'ungradable'].includes(props.current?.quality || '')
)

/** 影像类别：原始影像 vs 派生对象，避免「N 张影像」混算 */
const roleText = computed(() => props.current?.roleText || '未知类型')
const isDerived = computed(() => props.current?.isOriginal === false)

const indexText = computed(() => {
  const c = props.current
  if (!c) return '—'
  if (c.isOriginal && c.originalIndex) {
    return `原图 ${c.originalIndex} / ${c.originalTotal || 0}`
  }
  return '派生对象'
})

/** 不可判读告警：报告 P0「低质量图不得默认按正常处理」 */
const ungradableWarn = computed(() => {
  const n = props.safety?.ungradableCount || 0
  if (!n) return ''
  return `本病例有 ${n} 张原图被判定为不可判读，请勿据此给出阴性结论；`
    + `应标记不可判读并进入重拍或转诊流程`
})

const conflict = computed(
  () => props.current?.lateralityConflict || props.safety?.lateralityConflicts?.[0] || ''
)
</script>

<template>
  <div class="safety-bar" role="status" aria-label="影像安全标识">
    <!-- 眼别冲突：最高优先级，横贯整条 -->
    <div v-if="conflict" class="conflict-strip">
      <el-icon><Warning /></el-icon>
      <span>{{ conflict }}　请核对后再判读，系统不会自动选择其中一侧</span>
    </div>

    <!-- 不可判读告警：次于眼别冲突，但同样不可关闭 -->
    <div v-if="ungradableWarn" class="ungradable-strip">
      <el-icon><Warning /></el-icon>
      <span>{{ ungradableWarn }}</span>
    </div>

    <div class="bar-row">
      <div class="cell">
        <span class="label">病例</span>
        <span class="value strong">{{ caseNo || '—' }}</span>
      </div>

      <div class="cell" :class="{ 'is-warn': eyeUnknown }">
        <span class="label">眼别</span>
        <span class="value strong">{{ eyeCode }}　{{ eyeText }}</span>
      </div>

      <div class="cell" :class="{ 'is-warn': !examDateKnown }">
        <span class="label">检查日期</span>
        <span class="value">{{ examDateText }}</span>
      </div>

      <div class="cell">
        <span class="label">模态</span>
        <span class="value">{{ modalityText }}</span>
      </div>

      <div class="cell" :class="{ 'is-warn': qualityUnknown, 'is-bad': qualityBad }">
        <span class="label">图像质量</span>
        <span class="value">{{ qualityText }}</span>
      </div>

      <div class="cell" :class="{ 'is-derived': isDerived }">
        <span class="label">影像</span>
        <span class="value">{{ indexText }}　{{ roleText }}</span>
      </div>

      <div v-if="safety" class="cell">
        <span class="label">构成</span>
        <span class="value">
          原图 {{ safety.originalCount ?? 0 }} 张 · 派生 {{ safety.derivedCount ?? 0 }} 项
        </span>
      </div>

      <div v-if="safety" class="cell" :class="{ 'is-warn': !safety.qualityChecked }">
        <span class="label">质控</span>
        <span class="value">
          {{ safety.qualityReviewText
            || (safety.qualityChecked
              ? '本病例已完成'
              : `本病例未完成（${safety.unevaluatedCount ?? 0} 张未评估）`) }}
          <template v-if="safety.gradedTotal != null">
            · 累计 {{ safety.gradedTotal }} 张
          </template>
        </span>
      </div>

      <div v-if="statusText" class="cell status">
        <span class="value">{{ statusText }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 常驻：不随内容滚动，全屏态下依然置顶可见 */
.safety-bar {
  position: sticky;
  top: 0;
  z-index: 30;
  flex-shrink: 0;
  background: #14161c;
  border-bottom: 1px solid #2a2a2a;
}

.conflict-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: #7a1f1f;
  color: #ffe9e9;
  font-size: 13px;
  font-weight: 600;
}

.ungradable-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: #6b4a12;
  color: #ffeccd;
  font-size: 13px;
  font-weight: 600;
}

.bar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 20px;
  padding: 7px 16px;
}

.cell {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
}

.label {
  color: #d5dae3;
  font-size: 13px;
  font-weight: 500;
}

.value {
  color: #e5e6eb;
  font-size: 13px;
}

.value.strong {
  font-weight: 700;
  letter-spacing: 0.02em;
}

/* 颜色只作冗余提示：文字本身已完整表达信息 */
.cell.is-warn .value {
  color: #f5c34b;
}

.cell.is-bad .value {
  color: #ff7875;
  font-weight: 700;
}

.cell.is-derived .value {
  color: #7cc4ff;
}

.cell.status .value {
  padding: 1px 8px;
  border: 1px solid #3a3f4a;
  border-radius: 10px;
  color: #e8eaed;
  font-size: 13px;
}

@media (max-width: 1366px) {
  .bar-row {
    gap: 3px 12px;
    padding: 6px 10px;
  }
  .label,
  .value {
    font-size: 12px;
  }
}
</style>
