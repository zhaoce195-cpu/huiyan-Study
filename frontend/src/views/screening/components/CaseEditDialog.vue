<script setup lang="ts">
/**
 * 医生 / 管理员 补充修改病例弹窗
 * - 编辑文本字段（姓名 / 性别 / 年龄 / 联系电话 / 主诉 / 病史 / 备注）
 * - 上传 / 替换 / 删除 眼底图（PNG/JPG/JPEG/WEBP/BMP）
 * - 仅当 visible.value 为 true 时挂载
 *
 * 父组件用法：
 *   <CaseEditDialog
 *     v-model:visible="editVisible"
 *     :task="editTask"
 *     @saved="onCaseSaved"
 *   />
 */
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Delete as DeleteIcon,
  Picture,
  Iphone
} from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadRawFile } from 'element-plus'

import { ScreeningApi } from '@/api'
import { useCaseBindingStore } from '@/stores/case-binding'

type Task = ScreeningApi.ScreeningTask
type EyeSide = ScreeningApi.EyeSide

const props = defineProps<{
  visible: boolean
  task: Task | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved', payload: { caseId: number; task: Task | null }): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const bindingStore = useCaseBindingStore()
const phoneReg = /^1[3-9]\d{9}$/
const ALLOW_EXT = ['png', 'jpg', 'jpeg', 'webp', 'bmp']
const MAX_SIZE_MB = 20

interface FormState {
  patientName: string
  gender: '男' | '女'
  age: number | null
  patientPhone: string
  chiefComplaint: string
  medicalHistory: string
  remark: string
}

const formRef = ref<FormInstance>()
const form = ref<FormState>({
  patientName: '',
  gender: '男',
  age: null,
  patientPhone: '',
  chiefComplaint: '',
  medicalHistory: '',
  remark: ''
})

const rules: FormRules = {
  patientName: [
    { required: true, message: '请输入患者姓名', trigger: 'blur' },
    { max: 64, message: '不超过 64 个字符', trigger: 'blur' }
  ],
  age: [{ type: 'number', min: 0, max: 150, message: '0 ~ 150', trigger: 'blur' }],
  patientPhone: [
    {
      validator: (_r, v: string, cb) => {
        const val = (v || '').trim()
        if (!val) return cb()
        if (!phoneReg.test(val)) return cb(new Error('11 位手机号 / 留空'))
        cb()
      },
      trigger: 'blur'
    }
  ]
}

/* ===== 影像 ===== */
const imageEye = ref<EyeSide | 'UK'>('UK')
const images = ref<ScreeningApi.CaseImageItem[]>([])
const imageLoading = ref(false)
const uploading = ref(false)
const uploadPercent = ref(0)
const previewUrl = ref('')
const previewVisible = ref(false)

const fetchImages = async (caseId: number) => {
  imageLoading.value = true
  try {
    const res = await ScreeningApi.listCaseImages(caseId)
    images.value = res?.images || []
  } catch {
    images.value = []
  } finally {
    imageLoading.value = false
  }
}

/* ===== 弹窗打开同步表单 ===== */
watch(
  () => [props.visible, props.task] as const,
  ([v, t]) => {
    if (!v || !t) return
    form.value = {
      patientName: t.patientName || '',
      gender: (t.gender as '男' | '女') || '男',
      age: typeof t.age === 'number' ? t.age : null,
      patientPhone: t.patientPhone || '',
      chiefComplaint: '',
      medicalHistory: '',
      remark: t.remark || ''
    }
    images.value = []
    if (t.caseId) fetchImages(t.caseId)
  },
  { immediate: true }
)

/* ===== 校验上传文件 ===== */
const beforeUpload = (file: UploadRawFile): boolean => {
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (!ALLOW_EXT.includes(ext)) {
    ElMessage.warning(`仅支持 ${ALLOW_EXT.join(' / ')}`)
    return false
  }
  if (file.size / 1024 / 1024 > MAX_SIZE_MB) {
    ElMessage.warning(`单文件不超过 ${MAX_SIZE_MB}MB`)
    return false
  }
  return true
}

const customUpload = async ({ file }: { file: File }) => {
  const t = props.task
  if (!t?.caseId) {
    ElMessage.warning('未取到病例 ID，无法上传')
    return
  }
  uploading.value = true
  uploadPercent.value = 0
  try {
    const res = await ScreeningApi.addCaseImages(
      t.caseId,
      [file],
      imageEye.value,
      (p) => (uploadPercent.value = p)
    )
    images.value = res?.images || images.value
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败')
  } finally {
    uploading.value = false
    uploadPercent.value = 0
  }
}

const removeImage = async (item: ScreeningApi.CaseImageItem) => {
  const t = props.task
  if (!t?.caseId) return
  try {
    await ElMessageBox.confirm(
      '删除后无法恢复，确认删除该张眼底图？',
      '删除影像',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const res = await ScreeningApi.deleteCaseImage(t.caseId, item.url)
    images.value = res?.images || []
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

const openPreview = (url: string) => {
  previewUrl.value = url
  previewVisible.value = true
}

/* ===== 保存 ===== */
const saving = ref(false)
const onSave = async () => {
  const t = props.task
  if (!t?.caseId) {
    ElMessage.warning('未取到病例 ID')
    return
  }
  await formRef.value?.validate().catch(() => {
    throw new Error('表单校验未通过')
  })
  saving.value = true
  try {
    const phone = (form.value.patientPhone || '').trim()
    const updated = await ScreeningApi.updateCase(t.caseId, {
      patientName: form.value.patientName.trim(),
      gender: form.value.gender,
      age: form.value.age ?? undefined,
      patientPhone: phone,
      chiefComplaint: form.value.chiefComplaint.trim(),
      medicalHistory: form.value.medicalHistory.trim(),
      remark: form.value.remark.trim()
    })
    // 同步绑定状态到 store —— 让另一个列表立即生效
    if (phone) {
      bindingStore.setBinding(
        { caseId: t.caseId, patientId: t.patientId },
        phone,
        true
      )
    } else {
      bindingStore.clearBinding({ caseId: t.caseId, patientId: t.patientId })
    }
    emit('saved', { caseId: t.caseId, task: updated as Task })
    dialogVisible.value = false
  } catch (e: any) {
    if (e?.message !== '表单校验未通过') {
      ElMessage.error(e?.message || '保存失败')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="补充 / 修改病例"
    width="720"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-form
      v-if="task"
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      size="default"
      class="case-edit-form"
    >
      <el-form-item label="病例编号">
        <el-tag effect="plain" type="info">{{ task.id }}</el-tag>
        <span class="case-id-hint">数据库 ID: {{ task.caseId }}</span>
      </el-form-item>

      <div class="row-2">
        <el-form-item label="患者姓名" prop="patientName">
          <el-input v-model="form.patientName" placeholder="请输入" maxlength="64" />
        </el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="form.gender">
            <el-radio value="男">男</el-radio>
            <el-radio value="女">女</el-radio>
          </el-radio-group>
        </el-form-item>
      </div>

      <div class="row-2">
        <el-form-item label="年龄" prop="age">
          <el-input-number
            v-model="form.age"
            :min="0"
            :max="150"
            :step="1"
            placeholder="岁"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="联系电话" prop="patientPhone">
          <el-input
            v-model="form.patientPhone"
            placeholder="11 位手机号（留空可清除绑定）"
            maxlength="11"
            :prefix-icon="Iphone"
            clearable
          />
        </el-form-item>
      </div>

      <el-form-item label="主诉">
        <el-input
          v-model="form.chiefComplaint"
          type="textarea"
          :rows="2"
          maxlength="255"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="病史">
        <el-input
          v-model="form.medicalHistory"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="诊断 / 备注">
        <el-input
          v-model="form.remark"
          type="textarea"
          :rows="2"
          maxlength="512"
          show-word-limit
          placeholder="可填写医师初步诊断、备注信息"
        />
      </el-form-item>

      <el-form-item label="眼底图">
        <div class="image-block">
          <div class="image-toolbar">
            <span class="lbl">眼别：</span>
            <el-radio-group v-model="imageEye" size="small">
              <el-radio-button value="OD">OD 右眼</el-radio-button>
              <el-radio-button value="OS">OS 左眼</el-radio-button>
              <el-radio-button value="OU">OU 双眼</el-radio-button>
              <el-radio-button value="UK">自动判断</el-radio-button>
            </el-radio-group>
            <span class="hint">自动判断按视盘位置区分左眼、右眼或双眼。支持 PNG/JPG/JPEG/WEBP/BMP，单张 ≤ {{ MAX_SIZE_MB }}MB</span>
          </div>

          <div v-loading="imageLoading" class="image-grid">
            <div
              v-for="img in images"
              :key="img.url"
              class="image-cell"
            >
              <el-image
                :src="img.url"
                fit="cover"
                class="thumb"
                @click="openPreview(img.url)"
              >
                <template #error>
                  <div class="thumb-error"><el-icon><Picture /></el-icon></div>
                </template>
              </el-image>
              <div class="cell-meta">
                <el-tag size="small" effect="plain">{{ img.eye }}</el-tag>
                <el-button
                  text
                  type="danger"
                  :icon="DeleteIcon"
                  size="small"
                  @click="removeImage(img)"
                >
                  删除
                </el-button>
              </div>
            </div>

            <el-upload
              :show-file-list="false"
              :before-upload="beforeUpload"
              :http-request="customUpload"
              accept=".png,.jpg,.jpeg,.webp,.bmp"
              :disabled="uploading"
              class="upload-cell"
            >
              <div class="upload-tile">
                <template v-if="uploading">
                  <el-progress
                    type="circle"
                    :percentage="uploadPercent"
                    :width="64"
                  />
                  <div class="upload-text">上传中…</div>
                </template>
                <template v-else>
                  <el-icon :size="28"><Plus /></el-icon>
                  <div class="upload-text">添加眼底图</div>
                </template>
              </div>
            </el-upload>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">
        保存
      </el-button>
    </template>

    <!-- 预览大图 -->
    <el-dialog
      v-model="previewVisible"
      width="640"
      :show-close="true"
      :title="'眼底图预览'"
      append-to-body
    >
      <el-image :src="previewUrl" fit="contain" style="width: 100%" />
    </el-dialog>
  </el-dialog>
</template>

<style scoped>
.case-edit-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 24px;
}
.row-2 :deep(.el-form-item) {
  margin-bottom: 16px;
}
.case-id-hint {
  margin-left: 12px;
  color: #86909c;
  font-size: 12px;
}
.image-block {
  width: 100%;
}
.image-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.image-toolbar .lbl {
  color: #4e5969;
  font-size: 13px;
}
.image-toolbar .hint {
  color: #86909c;
  font-size: 12px;
}
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  width: 100%;
}
.image-cell {
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  overflow: hidden;
  background: #fafbfc;
}
.thumb {
  width: 100%;
  height: 120px;
  cursor: zoom-in;
  background: #000;
}
.thumb-error {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c9cdd4;
  background: #1d2129;
}
.cell-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: #fff;
  border-top: 1px solid #f0f1f3;
}
.upload-cell :deep(.el-upload) {
  width: 100%;
}
.upload-tile {
  width: 100%;
  height: 158px;
  border: 1px dashed #c9cdd4;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #4e5969;
  cursor: pointer;
  transition: border-color 0.15s;
}
.upload-tile:hover {
  border-color: #1677ff;
  color: #1677ff;
}
.upload-text {
  font-size: 12px;
  color: #86909c;
}
</style>
