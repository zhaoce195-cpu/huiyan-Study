<script setup lang="ts">
/**
 * AI 辅助诊断弹窗（复用组件）
 * - 阅片工作台：AI 辅助诊断（分级 + GradCAM 热力图，与金标准对比）
 * - 练习工作站：AI 参考（学生 vs AI vs 金标准 三方对比）
 *
 * 后端：/training/cases/{caseId}/ai-diagnosis → CSU-EYES 真实算法服务
 */
import { computed, ref, watch } from 'vue'
import { MagicStick, Refresh } from '@element-plus/icons-vue'
import { TrainingApi } from '@/api'

const props = defineProps<{
  visible: boolean
  /** 病例编号 case_no（T2026001）或数字 ID */
  caseId: string | number
  /** 学生作答 DR 分级（练习场景，可选） */
  studentGrade?: string | number | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
}>()

const loading = ref(false)
const result = ref<TrainingApi.AiDiagnosisResult | null>(null)
const errMsg = ref('')

const GRADE_TAG: Record<number, 'success' | 'warning' | 'danger' | 'info'> = {
  0: 'success',
  1: 'success',
  2: 'warning',
  3: 'danger',
  4: 'danger'
}
const gradeTag = (g: number | null | undefined) =>
  g === null || g === undefined ? 'info' : GRADE_TAG[g] || 'info'

const studentGradeNum = computed<number | null>(() => {
  const v = props.studentGrade
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
})

/** 热力图查看：original / heatmap 切换 */
const showHeat = ref<{ left: boolean; right: boolean }>({ left: true, right: true })

const fetchOrRun = async (force = false) => {
  loading.value = true
  errMsg.value = ''
  try {
    if (!force) {
      const cached = await TrainingApi.getAiDiagnosis(props.caseId)
      if (cached) {
        result.value = cached
        return
      }
    }
    result.value = await TrainingApi.runAiDiagnosis(props.caseId, force)
  } catch (e: any) {
    errMsg.value =
      e?.msg || e?.message || 'AI 算法服务暂不可用，请稍后重试'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v && !result.value) fetchOrRun()
  }
)

// 病例切换时清空旧结果
watch(
  () => props.caseId,
  () => {
    result.value = null
    errMsg.value = ''
  }
)

const close = () => emit('update:visible', false)
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="AI 辅助判读 · CSU-EYES"
    width="760px"
    class="ai-diag-dialog"
    append-to-body
    @update:model-value="close"
  >
    <!-- 加载中 -->
    <div v-if="loading" v-loading="true" class="ai-loading">
      正在调用眼科算法服务推理（约 5~30 秒）…
    </div>

    <!-- 失败 -->
    <el-result
      v-else-if="errMsg"
      icon="error"
      title="AI 诊断失败"
      :sub-title="errMsg"
    >
      <template #extra>
        <el-button type="primary" :icon="Refresh" @click="fetchOrRun(true)">重试</el-button>
      </template>
    </el-result>

    <!-- 结果 -->
    <template v-else-if="result">
      <!-- 三方分级对比 -->
      <div class="grade-compare">
        <div v-if="studentGradeNum !== null" class="gc-cell">
          <div class="gc-label">我的作答</div>
          <el-tag :type="gradeTag(studentGradeNum)" size="large" effect="dark">
            DR {{ studentGradeNum }} 级
          </el-tag>
        </div>
        <div class="gc-cell">
          <div class="gc-label">AI 综合结论</div>
          <el-tag :type="gradeTag(result.overallGrade)" size="large" effect="dark">
            {{ result.overallLabel || ('DR ' + result.overallGrade + ' 级') }}
          </el-tag>
          <div v-if="result.probs && result.probs.length" class="gc-probs">
            <div v-for="pb in result.probs" :key="pb.label" class="gc-prob">
              <span class="gp-name">{{ pb.label }}</span>
              <div class="gp-bar">
                <div class="gp-fill" :style="{ width: (pb.value * 100).toFixed(1) + '%' }" />
              </div>
              <span class="gp-val">{{ (pb.value * 100).toFixed(1) }}%</span>
            </div>
          </div>
          <div v-else class="gc-sub">{{ result.overallGradeText }}</div>
        </div>
        <div v-if="result.goldGrade !== null || result.goldLabel" class="gc-cell">
          <div class="gc-label">金标准</div>
          <el-tag
            :type="result.goldGrade !== null ? gradeTag(result.goldGrade) : 'danger'"
            size="large"
            effect="plain"
          >
            {{ result.goldLabel || ('DR ' + result.goldGrade + ' 级') }}
          </el-tag>
          <div
            v-if="result.agreeWithGold !== null && result.agreeWithGold !== undefined"
            class="gc-sub"
          >
            <el-tag
              size="small"
              :type="result.agreeWithGold ? 'success' : 'warning'"
              effect="plain"
            >
              {{ result.agreeWithGold ? 'AI 与金标准一致' : 'AI 与金标准不一致' }}
            </el-tag>
          </div>
        </div>
      </div>

      <el-alert
        v-if="result.singleEye"
        type="info"
        :closable="false"
        show-icon
        title="该病例为单图病例，左右眼使用同一张眼底图送检"
        style="margin-bottom: 12px"
      />

      <!-- 双眼热力图 -->
      <div class="eye-grid">
        <div
          v-for="side in (['left', 'right'] as const)"
          :key="side"
          class="eye-card"
        >
          <div class="eye-head">
            <span class="eye-title">
              {{ side === 'left' ? '左眼 OS' : '右眼 OD' }}
              <el-tag :type="gradeTag(result[side].grade)" size="small" effect="dark">
                {{ result[side].label || ('DR ' + result[side].grade + ' 级') }}
              </el-tag>
            </span>
            <el-radio-group
              v-model="showHeat[side]"
              size="small"
              :disabled="!result[side].heatmapUrl"
            >
              <el-radio-button :value="false">原图</el-radio-button>
              <el-radio-button :value="true">热力图</el-radio-button>
            </el-radio-group>
          </div>
          <el-image
            class="eye-img"
            fit="contain"
            :src="showHeat[side] && result[side].heatmapUrl ? result[side].heatmapUrl : result[side].imageUrl"
            :preview-src-list="[result[side].imageUrl, result[side].heatmapUrl].filter(Boolean)"
            preview-teleported
          >
            <template #error>
              <div class="img-fallback">影像加载失败</div>
            </template>
          </el-image>
        </div>
      </div>

      <div class="ai-meta">
        <span>模型：{{ result.modelName }}</span>
        <span>耗时：{{ (result.inferDurationMs / 1000).toFixed(1) }}s</span>
        <span>{{ result.cached ? `缓存结果 · ${result.inferredAt}` : '实时推理' }}</span>
        <el-link
          type="primary"
          :underline="false"
          :icon="Refresh"
          @click="fetchOrRun(true)"
        >
          重新推理
        </el-link>
      </div>

      <el-alert
        type="warning"
        :closable="false"
        title="AI 结果仅供教学参考，不能替代医师诊断；请结合金标准与热力图区域自行阅片验证。"
        style="margin-top: 12px"
      />
    </template>

    <!-- 初始（未触发） -->
    <el-empty v-else description="尚未执行 AI 诊断">
      <el-button type="primary" :icon="MagicStick" @click="fetchOrRun()">
        开始 AI 诊断
      </el-button>
    </el-empty>
  </el-dialog>
</template>

<style scoped>
.ai-loading {
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.grade-compare {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}
.gc-cell {
  flex: 1;
  text-align: center;
  padding: 12px 8px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}
.gc-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.gc-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 分类概率（青光眼等） */
.gc-probs {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  max-width: 240px;
}
.gc-prob {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.gp-name {
  min-width: 60px;
  text-align: right;
  white-space: nowrap;
}
.gp-bar {
  flex: 1;
  height: 6px;
  background: var(--el-fill-color-light);
  border-radius: 3px;
  overflow: hidden;
}
.gp-fill {
  height: 100%;
  background: var(--el-color-primary);
  border-radius: 3px;
  transition: width 0.3s;
}
.gp-val {
  min-width: 46px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.eye-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.eye-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}
.eye-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: var(--el-fill-color-light);
}
.eye-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}
.eye-img {
  width: 100%;
  height: 240px;
  background: #000;
  display: block;
}
.img-fallback {
  height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.ai-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
