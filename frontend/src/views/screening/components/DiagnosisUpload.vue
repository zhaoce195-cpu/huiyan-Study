<script setup lang="ts">
/**
 * CSU-EYES 智能诊断 · 三选一上传入口
 * ===================================
 * 替换原「拖拽上传眼底图」单一入口，提供：
 *  - 微动脉瘤检测（MA）：单图
 *  - DR 分级：左 / 右眼各一张
 *  - 综合诊断：单图多任务
 *
 * 上传完成后：
 *  - 调对应后端接口 → CSU-EYES → 写入 ScreeningCase / ScreeningResult
 *  - 通过 emit('done') 触发父级刷新任务列表
 *  - 弹「诊断结果对话框」展示原图 + 标注图 + 结构化结果
 */
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Aim,
  DataAnalysis,
  Search,
  UploadFilled,
  View,
} from '@element-plus/icons-vue'

import { DiagnosisApi } from '@/api'

type DiagnosisType = DiagnosisApi.DiagnosisType
type DiagnosisOut = DiagnosisApi.DiagnosisOut

const props = defineProps<{
  /** 当前用户是否具备诊断权限（医生/管理员） */
  canDiagnose: boolean
}>()

const emit = defineEmits<{
  (e: 'done', payload: DiagnosisOut): void
}>()

/* ========== 三选一选项 ========== */

interface DiagOption {
  key: DiagnosisType
  label: string
  desc: string
  icon: any
  fileCount: 1 | 2
  color: string
  badge: string
}

const OPTIONS: DiagOption[] = [
  {
    key: 'MA',
    label: '微动脉瘤检测',
    desc: '检出眼底图像中的微动脉瘤位置 / 数量，输出标注叠加图',
    icon: Search,
    fileCount: 1,
    color: '#7c3aed',
    badge: 'MA',
  },
  {
    key: 'DR',
    label: 'DR 分级',
    desc: '左右眼分别评估糖尿病视网膜病变 0~4 级，输出 GradCAM',
    icon: DataAnalysis,
    fileCount: 2,
    color: '#1677ff',
    badge: 'DR',
  },
  {
    key: 'COMPREHENSIVE',
    label: '综合诊断',
    desc: '同一张图执行 MA 检测 + DR 分级，给出综合摘要',
    icon: Aim,
    fileCount: 1,
    color: '#00b42a',
    badge: '综合',
  },
]

const activeType = ref<DiagnosisType>('COMPREHENSIVE')

const activeOption = computed(
  () => OPTIONS.find((o) => o.key === activeType.value) || OPTIONS[2]
)

/* ========== 文件状态 ========== */

const singleFile = ref<File | null>(null)
const leftEyeFile = ref<File | null>(null)
const rightEyeFile = ref<File | null>(null)
const eye = ref<'OD' | 'OS' | 'OU' | 'UK'>('UK')

const previewSingle = ref('')
const previewLeft = ref('')
const previewRight = ref('')

const ALLOWED_EXT = ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff']
const MAX_SIZE_MB = 20

const validate = (file: File): boolean => {
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (!ALLOWED_EXT.includes(ext)) {
    ElMessage.warning(`仅支持：${ALLOWED_EXT.join(' / ')}`)
    return false
  }
  if (file.size / 1024 / 1024 > MAX_SIZE_MB) {
    ElMessage.warning(`单文件不超过 ${MAX_SIZE_MB}MB`)
    return false
  }
  return true
}

const setSingleFile = (f: File) => {
  if (!validate(f)) return
  singleFile.value = f
  previewSingle.value = URL.createObjectURL(f)
}

const setLeftEye = (f: File) => {
  if (!validate(f)) return
  leftEyeFile.value = f
  previewLeft.value = URL.createObjectURL(f)
}

const setRightEye = (f: File) => {
  if (!validate(f)) return
  rightEyeFile.value = f
  previewRight.value = URL.createObjectURL(f)
}

const removeSingle = () => {
  singleFile.value = null
  previewSingle.value = ''
}

const onSwitchType = (k: DiagnosisType) => {
  activeType.value = k
  // 切换时清空所有上一次状态，避免残留
  removeSingle()
  leftEyeFile.value = null
  rightEyeFile.value = null
  previewLeft.value = ''
  previewRight.value = ''
  resultData.value = null
}

/* ========== 上传 / 进度 / 调用 ========== */

const submitting = ref(false)
const progress = reactive<{ percent: number; visible: boolean; phase: string }>({
  percent: 0,
  visible: false,
  phase: '',
})

const resultData = ref<DiagnosisOut | null>(null)
const resultVisible = ref(false)

const handleProgress = (p: number) => {
  progress.percent = Math.min(99, p)
}

const ready = computed(() => {
  if (!props.canDiagnose) return false
  if (activeOption.value.fileCount === 1) return !!singleFile.value
  return !!leftEyeFile.value && !!rightEyeFile.value
})

const onSubmit = async () => {
  if (!props.canDiagnose) {
    ElMessage.warning('当前账号无诊断权限，请联系管理员')
    return
  }
  if (!ready.value) {
    ElMessage.warning('请先选择待诊断的眼底图')
    return
  }
  submitting.value = true
  progress.visible = true
  progress.percent = 0
  progress.phase = '上传中…'
  try {
    let res: DiagnosisOut
    if (activeType.value === 'MA') {
      res = await DiagnosisApi.diagnoseMa(
        singleFile.value as File,
        eye.value,
        undefined,
        handleProgress
      )
    } else if (activeType.value === 'DR') {
      res = await DiagnosisApi.diagnoseDr(
        leftEyeFile.value as File,
        rightEyeFile.value as File,
        undefined,
        handleProgress
      )
    } else {
      res = await DiagnosisApi.diagnoseComprehensive(
        singleFile.value as File,
        ['ma_detection', 'dr_grading'],
        handleProgress
      )
    }
    progress.percent = 100
    progress.phase = '完成'
    resultData.value = res
    resultVisible.value = true
    emit('done', res)
  } catch (e: any) {
    // CSU-EYES 上游错误（后端会把 405 / 415 / 422 / 5xx 都包成 502 + 中文提示）
    const status = e?.response?.status
    const respData = e?.response?.data
    const upstreamMsg =
      (respData && (respData.msg || respData.detail)) ||
      e?.message ||
      ''
    let tip = '诊断失败，请稍后再试'
    const lowerMsg = String(upstreamMsg).toLowerCase()
    if (
      status === 400 ||
      lowerMsg.includes('invalid file type') ||
      lowerMsg.includes('文件格式')
    ) {
      tip = '文件格式不支持，请上传 JPG/PNG 格式的眼底图'
    } else if (status === 405) {
      tip =
        '请求方法不允许 (405) — 上游 CSU-EYES API 地址或端口配置错误，' +
        '请联系管理员检查 CSU_EYES_BASE_URL（应为 9050，不是 9080）。'
    } else if (status === 502 || (typeof upstreamMsg === 'string' && upstreamMsg.includes('CSU-EYES'))) {
      tip = `上游 AI 平台返回错误：${upstreamMsg || '请稍后再试'}`
    } else if (status === 401) {
      tip = '登录已过期，请重新登录后再发起诊断'
    } else if (status === 403) {
      tip = '当前账号无诊断权限'
    } else if (status === 413) {
      tip = '上传文件过大，请压缩后再试（单文件 ≤ 20MB）'
    } else if (upstreamMsg) {
      tip = upstreamMsg
    }
    ElMessage.error(tip)
    progress.phase = '失败'
  } finally {
    submitting.value = false
    setTimeout(() => {
      progress.visible = false
      progress.percent = 0
      progress.phase = ''
    }, 600)
  }
}

const closeResult = () => {
  resultVisible.value = false
}

/* ========== 渲染辅助 ========== */

const RISK_LABEL = DiagnosisApi.RISK_LABEL
const RISK_TYPE = DiagnosisApi.RISK_TAG_TYPE

import { drGradeColorNum as drGradeColor } from '@/utils/dr-format'
</script>

<template>
  <section class="diagnosis-upload">
    <!-- 顶部三选一 -->
    <div class="diag-types">
      <div
        v-for="o in OPTIONS"
        :key="o.key"
        class="diag-tile"
        :class="{ active: activeType === o.key }"
        :style="{ '--tile-color': o.color }"
        @click="onSwitchType(o.key)"
      >
        <div class="tile-head">
          <el-icon class="tile-icon"><component :is="o.icon" /></el-icon>
          <span class="tile-badge">{{ o.badge }}</span>
        </div>
        <div class="tile-title">{{ o.label }}</div>
        <div class="tile-desc">{{ o.desc }}</div>
        <div v-if="activeType === o.key" class="tile-active-tag">已选择</div>
      </div>
    </div>

    <!-- 上传区 -->
    <div class="diag-stage">
      <div v-if="!canDiagnose" class="readonly-tip">
        <el-icon><View /></el-icon>
        当前账号为只读身份，无法发起诊断 — 请使用医生 / 管理员账号
      </div>

      <!-- 单图模式：MA / 综合 -->
      <div
        v-else-if="activeOption.fileCount === 1"
        class="single-upload"
      >
        <el-upload
          drag
          :show-file-list="false"
          :auto-upload="false"
          accept=".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
          :on-change="(f: any) => setSingleFile(f.raw)"
        >
          <div v-if="!singleFile" class="empty-drop">
            <el-icon class="big-icon"><UploadFilled /></el-icon>
            <div class="drop-title">拖拽眼底图至此 · 或 点击选择</div>
            <div class="drop-sub">
              支持 PNG / JPG / WEBP / BMP / TIF · 单张 ≤ {{ MAX_SIZE_MB }}MB
            </div>
          </div>
          <div v-else class="filled-drop">
            <img :src="previewSingle" alt="preview" class="preview-img" />
            <div class="file-meta">
              <div class="fname" :title="singleFile.name">{{ singleFile.name }}</div>
              <el-button
                size="small"
                type="danger"
                text
                @click.stop="removeSingle"
              >
                重新选择
              </el-button>
            </div>
          </div>
        </el-upload>

        <div v-if="activeType === 'MA'" class="extra-form">
          <span class="lbl">眼别</span>
          <el-radio-group v-model="eye" size="default">
            <el-radio-button value="OD">OD 右眼</el-radio-button>
            <el-radio-button value="OS">OS 左眼</el-radio-button>
            <el-radio-button value="OU">OU 双眼</el-radio-button>
            <el-radio-button value="UK">自动判断</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <!-- 双眼模式：DR -->
      <div v-else class="dual-upload">
        <div class="eye-cell">
          <div class="eye-title">左眼（OS）</div>
          <el-upload
            drag
            :show-file-list="false"
            :auto-upload="false"
            accept=".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
            :on-change="(f: any) => setLeftEye(f.raw)"
          >
            <div v-if="!leftEyeFile" class="empty-drop small">
              <el-icon><UploadFilled /></el-icon>
              <div class="drop-title">点击 / 拖拽 · 左眼</div>
            </div>
            <div v-else class="filled-drop small">
              <img :src="previewLeft" alt="OS" class="preview-img" />
              <div class="file-meta">
                <div class="fname" :title="leftEyeFile.name">{{ leftEyeFile.name }}</div>
              </div>
            </div>
          </el-upload>
        </div>
        <div class="eye-cell">
          <div class="eye-title">右眼（OD）</div>
          <el-upload
            drag
            :show-file-list="false"
            :auto-upload="false"
            accept=".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
            :on-change="(f: any) => setRightEye(f.raw)"
          >
            <div v-if="!rightEyeFile" class="empty-drop small">
              <el-icon><UploadFilled /></el-icon>
              <div class="drop-title">点击 / 拖拽 · 右眼</div>
            </div>
            <div v-else class="filled-drop small">
              <img :src="previewRight" alt="OD" class="preview-img" />
              <div class="file-meta">
                <div class="fname" :title="rightEyeFile.name">{{ rightEyeFile.name }}</div>
              </div>
            </div>
          </el-upload>
        </div>
      </div>

      <!-- 操作 -->
      <div class="diag-actions">
        <el-button
          type="primary"
          :icon="Aim"
          :loading="submitting"
          :disabled="!ready"
          size="large"
          @click="onSubmit"
        >
          {{ submitting ? progress.phase || '诊断中…' : `开始 ${activeOption.label}` }}
        </el-button>

        <span v-if="progress.visible" class="progress-line">
          <el-progress
            :percentage="progress.percent"
            :stroke-width="8"
            :status="progress.percent >= 100 ? 'success' : undefined"
            style="width: 280px; display: inline-block; vertical-align: middle"
          />
        </span>
      </div>
    </div>

    <!-- 结果弹窗 -->
    <el-dialog
      v-model="resultVisible"
      :title="`诊断完成 · ${activeOption.label}`"
      width="900"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div v-if="resultData" class="result-body">
        <!-- 头部摘要 -->
        <div class="rs-header">
          <div class="rs-title">
            <span class="case-no">{{ resultData.taskId }}</span>
            <span v-if="resultData.caseSn" class="case-sn">/ {{ resultData.caseSn }}</span>
            <el-tag :type="RISK_TYPE[resultData.riskLevel]" effect="dark">
              {{ RISK_LABEL[resultData.riskLevel] }}
            </el-tag>
          </div>
          <div class="rs-patient">
            患者：<b>{{ resultData.patientName }}</b>
          </div>
        </div>

        <!-- MA 结果 -->
        <div v-if="resultData.ma" class="rs-block">
          <div class="rs-row">
            <span class="rs-label">检出 MA 数量</span>
            <span class="rs-value big" :style="{ color: resultData.ma.maCount > 10 ? '#ff7d00' : '#00b42a' }">
              {{ resultData.ma.maCount }}
            </span>
          </div>
          <div class="rs-row">
            <span class="rs-label">推理耗时</span>
            <span class="rs-value">{{ resultData.ma.inferenceTime.toFixed(2) }} 秒</span>
          </div>
          <div class="rs-images">
            <div class="rs-img-cell">
              <div class="rs-img-title">原图</div>
              <img :src="resultData.primaryImageUrl" alt="origin" />
            </div>
            <div v-if="resultData.ma.overlayUrl" class="rs-img-cell">
              <div class="rs-img-title">病灶标注图</div>
              <img :src="resultData.ma.overlayUrl" alt="overlay" />
            </div>
            <div v-if="resultData.ma.heatmapUrl" class="rs-img-cell">
              <div class="rs-img-title">热力图</div>
              <img :src="resultData.ma.heatmapUrl" alt="heat" />
            </div>
          </div>
        </div>

        <!-- DR 结果 -->
        <div v-if="resultData.dr" class="rs-block">
          <div class="rs-row">
            <span class="rs-label">综合分级</span>
            <span class="rs-value big" :style="{ color: drGradeColor(resultData.dr.overallGrade) }">
              {{ resultData.dr.overallGrade }} 级 · {{ resultData.dr.overallGradeName || '—' }}
            </span>
          </div>
          <div class="rs-row">
            <span class="rs-label">推理耗时</span>
            <span class="rs-value">{{ resultData.dr.inferenceTime.toFixed(2) }} 秒</span>
          </div>
          <div class="rs-images">
            <div class="rs-img-cell">
              <div class="rs-img-title">
                左眼（OS）
                <el-tag size="small" :type="resultData.dr.left.grade > 2 ? 'danger' : 'success'">
                  {{ resultData.dr.left.grade }} 级 · {{ resultData.dr.left.gradeName || '' }}
                </el-tag>
              </div>
              <img :src="resultData.dr.left.imageUrl" alt="OS" />
              <div v-if="resultData.dr.left.heatmapUrl" class="overlay-line">GradCAM</div>
              <img v-if="resultData.dr.left.heatmapUrl" :src="resultData.dr.left.heatmapUrl" alt="OS heat" />
            </div>
            <div class="rs-img-cell">
              <div class="rs-img-title">
                右眼（OD）
                <el-tag size="small" :type="resultData.dr.right.grade > 2 ? 'danger' : 'success'">
                  {{ resultData.dr.right.grade }} 级 · {{ resultData.dr.right.gradeName || '' }}
                </el-tag>
              </div>
              <img :src="resultData.dr.right.imageUrl" alt="OD" />
              <div v-if="resultData.dr.right.heatmapUrl" class="overlay-line">GradCAM</div>
              <img v-if="resultData.dr.right.heatmapUrl" :src="resultData.dr.right.heatmapUrl" alt="OD heat" />
            </div>
          </div>
        </div>

        <!-- 综合诊断 -->
        <div v-if="resultData.comprehensive" class="rs-block">
          <div class="rs-row">
            <span class="rs-label">DR 分级</span>
            <span class="rs-value big" :style="{ color: drGradeColor(resultData.comprehensive.overallGrade) }">
              {{ resultData.comprehensive.overallGrade }} 级
            </span>
          </div>
          <div class="rs-row">
            <span class="rs-label">MA 数量</span>
            <span class="rs-value big">{{ resultData.comprehensive.maCount }}</span>
          </div>
          <div v-if="resultData.comprehensive.summary" class="rs-row">
            <span class="rs-label">综合摘要</span>
            <span class="rs-value">{{ resultData.comprehensive.summary }}</span>
          </div>
          <div class="rs-images">
            <div class="rs-img-cell">
              <div class="rs-img-title">原图</div>
              <img :src="resultData.primaryImageUrl" alt="origin" />
            </div>
            <div v-if="resultData.comprehensive.maOverlayUrl" class="rs-img-cell">
              <div class="rs-img-title">MA 标注图</div>
              <img :src="resultData.comprehensive.maOverlayUrl" alt="ma overlay" />
            </div>
            <div v-if="resultData.comprehensive.drHeatmapUrl" class="rs-img-cell">
              <div class="rs-img-title">DR 热力图</div>
              <img :src="resultData.comprehensive.drHeatmapUrl" alt="dr heat" />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeResult">关闭</el-button>
        <el-button
          type="primary"
          @click="closeResult"
        >
          已知悉，去病例列表查看
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.diagnosis-upload {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 16px;
  padding: 22px;
  margin-bottom: 16px;
}

.diag-types {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
  gap: 14px;
  margin-bottom: 18px;
}
.diag-tile {
  --tile-color: #1677ff;
  position: relative;
  padding: 16px 18px;
  border: 1.5px solid #e5e6eb;
  border-radius: 14px;
  background: #fafbfc;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
  overflow: hidden;
  box-sizing: border-box;
  min-height: 132px;
  display: flex;
  flex-direction: column;
  transform: none;
}
.diag-tile:hover {
  border-color: var(--tile-color);
  background: #fff;
  box-shadow: 0 4px 14px rgba(22, 119, 255, 0.08);
  transform: none;
}
.diag-tile.active {
  border-color: var(--tile-color);
  background: linear-gradient(180deg, #fff, color-mix(in srgb, var(--tile-color) 6%, #fff));
  box-shadow: 0 4px 14px color-mix(in srgb, var(--tile-color) 22%, transparent);
  transform: none;
}
.tile-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.tile-icon {
  font-size: 28px;
  color: var(--tile-color);
}
.tile-badge {
  background: color-mix(in srgb, var(--tile-color) 14%, #fff);
  color: var(--tile-color);
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.tile-title {
  font-size: 15px;
  font-weight: 700;
  color: #1d2129;
  margin-bottom: 4px;
}
.tile-desc {
  font-size: 12px;
  color: #4e5969;
  line-height: 1.5;
}
.tile-active-tag {
  position: absolute;
  top: 8px;
  right: -22px;
  transform: rotate(35deg);
  background: var(--tile-color);
  color: #fff;
  font-size: 11px;
  padding: 2px 22px;
  letter-spacing: 1px;
}

.diag-stage {
  border: 1px dashed #e5e6eb;
  border-radius: 12px;
  padding: 18px;
  background: #fafbfc;
}
.readonly-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #86909c;
  padding: 24px;
  justify-content: center;
}

.single-upload :deep(.el-upload) {
  width: 100%;
}
.single-upload :deep(.el-upload-dragger) {
  width: 100%;
  border-radius: 10px;
  background: #fff;
  border-color: #c9cdd4;
}
.empty-drop {
  padding: 28px 0;
  text-align: center;
}
.empty-drop .big-icon {
  font-size: 48px;
  color: #c9cdd4;
}
.empty-drop .drop-title {
  font-size: 14px;
  color: #1d2129;
  margin: 8px 0 4px;
}
.empty-drop .drop-sub {
  color: #86909c;
  font-size: 12px;
}
.empty-drop.small {
  padding: 18px 0;
}
.empty-drop.small .drop-title {
  font-size: 13px;
}

.filled-drop {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
}
.filled-drop.small {
  flex-direction: column;
  align-items: stretch;
}
.preview-img {
  width: 120px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  background: #000;
}
.filled-drop.small .preview-img {
  width: 100%;
  height: 130px;
}
.file-meta {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.fname {
  font-size: 13px;
  color: #1d2129;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.extra-form {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.extra-form .lbl {
  color: #4e5969;
  font-size: 13px;
}

.dual-upload {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.eye-cell {
  background: #fff;
  border-radius: 10px;
  padding: 8px;
}
.eye-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
  color: #4e5969;
}

.diag-actions {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.progress-line {
  display: inline-flex;
  align-items: center;
}

/* ========== 结果弹窗 ========== */
.result-body {
  max-height: 70vh;
  overflow-y: auto;
}
.rs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.rs-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rs-title .case-no {
  font-family: 'Consolas', 'Monaco', monospace;
  font-weight: 700;
  color: #1677ff;
}
.rs-title .case-sn {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #86909c;
  font-size: 13px;
}
.rs-patient {
  font-size: 13px;
  color: #4e5969;
}

.rs-block {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #fafbfc;
}
.rs-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}
.rs-label {
  width: 100px;
  color: #86909c;
  font-size: 13px;
}
.rs-value {
  font-size: 14px;
  color: #1d2129;
}
.rs-value.big {
  font-size: 22px;
  font-weight: 700;
}

.rs-images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
  margin-top: 10px;
}
.rs-img-cell {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 6px;
}
.rs-img-cell img {
  width: 100%;
  border-radius: 6px;
  display: block;
}
.rs-img-title {
  font-size: 12px;
  color: #4e5969;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.overlay-line {
  font-size: 11px;
  color: #86909c;
  margin: 4px 0 2px;
}

@media (max-width: 1024px) {
  .diag-types {
    grid-template-columns: 1fr;
  }
  .dual-upload {
    grid-template-columns: 1fr;
  }
}
</style>
