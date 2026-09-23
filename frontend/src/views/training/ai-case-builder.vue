<script setup lang="ts">
/**
 * AI 智能建案（教师 / 管理员）
 * 上传左右眼底图 → CSU-EYES 算法自动 DR 分级 → 生成实训病例草稿
 * 金标准预填为 AI 结果，教师在管理后台复核修订后发布给学生。
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick, Plus, View } from '@element-plus/icons-vue'
import { TrainingApi } from '@/api'

const router = useRouter()

/* ========== 上传 ========== */
interface EyeSlot {
  file: File | null
  preview: string
}
const leftEye = ref<EyeSlot>({ file: null, preview: '' })
const rightEye = ref<EyeSlot>({ file: null, preview: '' })

const ACCEPT = ['image/jpeg', 'image/png']
const pick = (side: 'left' | 'right') => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.jpg,.jpeg,.png'
  input.onchange = () => {
    const f = input.files?.[0]
    if (!f) return
    if (!ACCEPT.includes(f.type)) {
      ElMessage.warning('算法服务仅支持 JPG / PNG 眼底图')
      return
    }
    if (f.size > 20 * 1024 * 1024) {
      ElMessage.warning('图片不能超过 20MB')
      return
    }
    const slot = side === 'left' ? leftEye : rightEye
    if (slot.value.preview) URL.revokeObjectURL(slot.value.preview)
    slot.value = { file: f, preview: URL.createObjectURL(f) }
  }
  input.click()
}

/* ========== 建案表单 ========== */
const form = ref({
  title: '',
  difficulty: 'EASY' as 'EASY' | 'MEDIUM' | 'HARD'
})

const canSubmit = computed(() => !!leftEye.value.file && !!rightEye.value.file)

/* ========== 提交 ========== */
const submitting = ref(false)
const draft = ref<TrainingApi.AiCaseDraft | null>(null)

const handleCreate = async () => {
  if (!leftEye.value.file || !rightEye.value.file) {
    ElMessage.warning('请先上传左、右眼底图各一张')
    return
  }
  submitting.value = true
  try {
    draft.value = await TrainingApi.createAiCase(
      leftEye.value.file,
      rightEye.value.file,
      { title: form.value.title, difficulty: form.value.difficulty }
    )
    ElMessage.success(`建案成功：${draft.value.caseId}（草稿，待复核发布）`)
  } catch {
    /* 拦截器已弹错 */
  } finally {
    submitting.value = false
  }
}

const resetAll = () => {
  if (leftEye.value.preview) URL.revokeObjectURL(leftEye.value.preview)
  if (rightEye.value.preview) URL.revokeObjectURL(rightEye.value.preview)
  leftEye.value = { file: null, preview: '' }
  rightEye.value = { file: null, preview: '' }
  form.value = { title: '', difficulty: 'EASY' }
  draft.value = null
}

const GRADE_TAG: Record<number, 'success' | 'warning' | 'danger'> = {
  0: 'success', 1: 'success', 2: 'warning', 3: 'danger', 4: 'danger'
}
</script>

<template>
  <div class="ai-builder-page">
    <header class="page-head">
      <div>
        <h2 class="title">
          <el-icon><MagicStick /></el-icon>
          AI 智能建案
        </h2>
        <p class="subtitle">
          上传左右眼底图，CSU-EYES 算法服务自动完成 DR 分级与 GradCAM 热力图，一键生成实训病例草稿；
          金标准预填为 AI 结果，复核修订后即可发布给学生练习。
        </p>
      </div>
    </header>

    <!-- 结果态 -->
    <el-card v-if="draft" class="result-card" shadow="never">
      <el-result icon="success" :title="`建案成功：${draft.caseId}`" :sub-title="draft.title">
        <template #extra>
          <div class="result-grades">
            <el-tag :type="GRADE_TAG[draft.ai.overallGrade] || 'info'" size="large" effect="dark">
              AI 综合 DR {{ draft.ai.overallGrade }} 级
            </el-tag>
            <el-tag type="info" effect="plain">OS {{ draft.ai.left.grade }} 级</el-tag>
            <el-tag type="info" effect="plain">OD {{ draft.ai.right.grade }} 级</el-tag>
            <el-tag type="warning" effect="plain">草稿 · 未发布</el-tag>
          </div>
          <div class="result-heat">
            <el-image
              v-for="(u, i) in [draft.ai.left.heatmapUrl, draft.ai.right.heatmapUrl].filter(Boolean)"
              :key="i"
              :src="u"
              fit="cover"
              class="heat-thumb"
              :preview-src-list="[draft.ai.left.heatmapUrl, draft.ai.right.heatmapUrl].filter(Boolean)"
              preview-teleported
            />
          </div>
          <div class="result-actions">
            <el-button
              type="primary"
              :icon="View"
              @click="router.push({
                path: '/training/cases',
                query: draft.id ? { goldCaseId: String(draft.id) } : undefined
              })"
            >
              去病例库完善金标准
            </el-button>
            <el-button :icon="Plus" @click="resetAll">继续建案</el-button>
          </div>
        </template>
      </el-result>
    </el-card>

    <!-- 表单态 -->
    <el-card v-else class="form-card" shadow="never">
      <div class="upload-grid">
        <div
          v-for="side in (['left', 'right'] as const)"
          :key="side"
          class="upload-cell"
          @click="pick(side)"
        >
          <template v-if="(side === 'left' ? leftEye : rightEye).preview">
            <img :src="(side === 'left' ? leftEye : rightEye).preview" class="upload-preview" />
            <div class="upload-mask">点击更换</div>
          </template>
          <template v-else>
            <el-icon class="upload-icon"><Plus /></el-icon>
            <div class="upload-text">{{ side === 'left' ? '左眼 OS' : '右眼 OD' }} 眼底图</div>
            <div class="upload-hint">JPG / PNG，≤ 20MB</div>
          </template>
        </div>
      </div>

      <el-form label-width="88px" class="meta-form">
        <el-form-item label="病例标题">
          <el-input
            v-model="form.title"
            placeholder="缺省自动生成，如：AI 建案 · DR 2 级"
            maxlength="60"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="难度">
          <el-radio-group v-model="form.difficulty">
            <el-radio-button value="EASY">入门</el-radio-button>
            <el-radio-button value="MEDIUM">中级</el-radio-button>
            <el-radio-button value="HARD">高级</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button
          type="primary"
          size="large"
          :icon="MagicStick"
          :disabled="!canSubmit"
          :loading="submitting"
          @click="handleCreate"
        >
          {{ submitting ? 'AI 推理中（约 5~30 秒）…' : '开始 AI 建案' }}
        </el-button>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="建案后病例为「未发布」草稿，学生不可见；请到病例库该行点「完善金标准」，保存草稿或发布并加入实训。"
        style="margin-top: 16px"
      />
    </el-card>
  </div>
</template>

<style scoped>
.ai-builder-page {
  padding: 24px;
  max-width: 860px;
  margin: 0 auto;
}
.page-head .title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 6px;
  font-size: 20px;
  color: #1d2129;
}
.page-head .subtitle {
  margin: 0 0 18px;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
}

.form-card,
.result-card {
  background: var(--ap-glass, rgba(24, 26, 32, 0.7));
  border: 1px solid var(--ap-hairline, #2a2a2a);
}

.upload-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 18px;
}
.upload-cell {
  position: relative;
  height: 220px;
  border: 1.5px dashed var(--el-border-color);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  overflow: hidden;
  transition: border-color 0.2s;
}
.upload-cell:hover {
  border-color: var(--el-color-primary);
}
.upload-icon {
  font-size: 30px;
  color: var(--el-text-color-secondary);
}
.upload-text {
  font-size: 14px;
  font-weight: 600;
}
.upload-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.upload-preview {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.upload-mask {
  position: absolute;
  inset: auto 0 0;
  padding: 6px 0;
  text-align: center;
  font-size: 12px;
  color: #fff;
  background: rgba(0, 0, 0, 0.55);
}

.meta-form {
  max-width: 480px;
}
.form-actions {
  display: flex;
  justify-content: center;
  margin-top: 6px;
}

.result-grades {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.result-heat {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 16px;
}
.heat-thumb {
  width: 160px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
}
.result-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}
</style>
