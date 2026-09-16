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

/**
 * 该画哪几张眼别卡。
 *
 * 以前写死 ['left','right']，只有右眼影像的病例会把那张右眼片子同时画成
 * 「左眼 OS」，还挂一个由它算出来的假左眼分级 —— 把右眼当左眼展示是错误信息。
 * 现在按后端给的真实眼别渲染；老接口没有该字段时回退成双眼。
 */
type EyeCard = 'left' | 'right' | 'ou'
const eyeCards = computed<EyeCard[]>(
  () => (result.value?.eyeCards?.length ? result.value.eyeCards : ['left', 'right']) as EyeCard[]
)

/** 眼别卡取哪一侧的数据：ou 是同一张图，取右眼即可 */
const sideOf = (card: EyeCard): 'left' | 'right' => (card === 'left' ? 'left' : 'right')

const EYE_TITLE: Record<EyeCard, string> = {
  left: '左眼 OS',
  right: '右眼 OD',
  ou: '双眼 OU（单图）',
}

const elapsed = ref(0)
let elapsedTimer: ReturnType<typeof setInterval> | null = null

const fetchOrRun = async (force = false) => {
  loading.value = true
  errMsg.value = ''
  elapsed.value = 0
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedTimer = setInterval(() => { elapsed.value += 1 }, 1000)
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
    if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
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
      <div>正在调用眼科算法服务推理…</div>
      <!-- 显示真实已用时长：此前写死「约 5~30 秒」，
           而服务异常时实际会等到超时，提示本身反而在误导 -->
      <div class="ai-loading-sub">
        已等待 {{ elapsed }} 秒{{
          elapsed > 30 ? ' · 超过预期，算法服务可能不可用，最多再等 ' + Math.max(0, 45 - elapsed) + ' 秒' : ''
        }}
      </div>
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
        v-if="eyeCards.length === 1"
        type="info"
        :closable="false"
        show-icon
        :title="
          eyeCards[0] === 'ou'
            ? '该病例只有一张双眼眼底图，AI 按该图给出结论'
            : `该病例只有${eyeCards[0] === 'left' ? '左' : '右'}眼影像，另一侧无数据、不作展示`
        "
        style="margin-bottom: 12px"
      />

      <!-- 眼别热力图：按病例实际存在的眼别渲染 -->
      <div class="eye-grid" :class="{ 'single-card': eyeCards.length === 1 }">
        <div
          v-for="card in eyeCards"
          :key="card"
          class="eye-card"
        >
          <div class="eye-head">
            <span class="eye-title">
              {{ EYE_TITLE[card] }}
              <el-tag :type="gradeTag(result[sideOf(card)].grade)" size="small" effect="dark">
                {{ result[sideOf(card)].label || ('DR ' + result[sideOf(card)].grade + ' 级') }}
              </el-tag>
            </span>
            <el-radio-group
              v-model="showHeat[sideOf(card)]"
              size="small"
              :disabled="!result[sideOf(card)].heatmapUrl"
            >
              <el-radio-button :value="false">原图</el-radio-button>
              <el-radio-button :value="true">热力图</el-radio-button>
            </el-radio-group>
          </div>
          <el-image
            class="eye-img"
            fit="contain"
            :src="
              showHeat[sideOf(card)] && result[sideOf(card)].heatmapUrl
                ? result[sideOf(card)].heatmapUrl
                : result[sideOf(card)].imageUrl
            "
            :preview-src-list="
              [result[sideOf(card)].imageUrl, result[sideOf(card)].heatmapUrl].filter(Boolean)
            "
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
.ai-loading-sub {
  margin-top: 8px;
  font-size: 12px;
  color: #86909c;
}

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
/* 单眼病例只有一张卡，撑满整行会太大，居中收窄 */
.eye-grid.single-card {
  grid-template-columns: minmax(0, 1fr);
  max-width: 50%;
  margin: 0 auto;
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
