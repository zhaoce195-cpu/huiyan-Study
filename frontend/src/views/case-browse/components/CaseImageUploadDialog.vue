<script setup lang="ts">
/**
 * 病例影像 · 补传 / 追加上传 弹窗
 *
 * 父组件用法：
 *   <CaseImageUploadDialog
 *     v-model:visible="visible"
 *     :case-table="'training'"
 *     :case-id="123"
 *     :default-role="'MA'"
 *     :missing-roles="['SE','HE']"
 *     @saved="onSaved"
 *   />
 *
 * 仅医生 / 管理员可调（后端会再次校验）
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { UploadFile, UploadInstance } from 'element-plus'

import { CaseImageApi } from '@/api'

type CaseTable = CaseImageApi.CaseTable
type CaseImageRole = CaseImageApi.CaseImageRole
type EyeSide = CaseImageApi.EyeSide

const props = defineProps<{
  visible: boolean
  caseTable: CaseTable
  caseId: number
  defaultRole?: CaseImageRole
  missingRoles?: CaseImageRole[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved', payload: { caseId: number; caseTable: CaseTable }): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const uploadRef = ref<UploadInstance | null>(null)
const role = ref<CaseImageRole>('original')
const eye = ref<EyeSide>('UK')
const files = ref<File[]>([])
const previews = ref<string[]>([])
const uploading = ref(false)
const uploadPercent = ref(0)

const ROLE_OPTIONS = CaseImageApi.ROLE_ORDER.map((r) => ({
  value: r,
  label: CaseImageApi.ROLE_LABEL[r],
  highlight: (props.missingRoles || []).includes(r)
}))

const ALLOWED_EXT = ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff']
const MAX_SIZE_MB = 20

watch(
  () => [props.visible, props.defaultRole],
  ([v, def]) => {
    if (v) {
      role.value = (def as CaseImageRole) || 'original'
      eye.value = 'UK'
      files.value = []
      previews.value = []
      uploadPercent.value = 0
    }
  },
  { immediate: true }
)

/**
 * auto-upload=false 时 el-upload 不走 before-upload（那是上传流程的钩子），
 * 只会触发 on-change，所以这里挂 on-change，否则「添加文件」选完毫无反应、
 * 待上传数一直是 0。
 */
const onFileChange = (uploadFile: UploadFile): void => {
  const file = uploadFile.raw
  // 处理完清掉内部列表，否则同一个文件第二次选不会再触发 change
  uploadRef.value?.clearFiles?.()
  if (!file) return

  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (!ALLOWED_EXT.includes(ext)) {
    ElMessage.warning(`仅支持 ${ALLOWED_EXT.join(' / ')}`)
    return
  }
  if (file.size / 1024 / 1024 > MAX_SIZE_MB) {
    ElMessage.warning(`单文件不超过 ${MAX_SIZE_MB}MB`)
    return
  }
  files.value.push(file as File)
  // tif 浏览器无法直接预览
  if (ext === 'tif' || ext === 'tiff') {
    previews.value.push('')
  } else {
    previews.value.push(URL.createObjectURL(file))
  }
}

const removeFile = (i: number) => {
  files.value.splice(i, 1)
  previews.value.splice(i, 1)
}

const onSubmit = async () => {
  if (!files.value.length) {
    ElMessage.warning('请先选择要上传的影像')
    return
  }
  uploading.value = true
  uploadPercent.value = 0
  try {
    await CaseImageApi.uploadCaseImages(
      props.caseTable,
      props.caseId,
      files.value,
      role.value,
      eye.value,
      (p) => (uploadPercent.value = p)
    )
    emit('saved', { caseId: props.caseId, caseTable: props.caseTable })
    dialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败')
  } finally {
    uploading.value = false
    uploadPercent.value = 0
  }
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="补传 / 追加病例影像"
    width="560"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-form label-width="90px" size="default">
      <el-form-item label="影像类型">
        <el-select v-model="role" style="width: 100%">
          <el-option
            v-for="o in ROLE_OPTIONS"
            :key="o.value"
            :value="o.value"
            :label="o.label + (o.highlight ? '（缺失，建议补传）' : '')"
          >
            <span :style="o.highlight ? 'color:#ff7d00;font-weight:600' : ''">
              {{ o.label }}
            </span>
            <span v-if="o.highlight" style="margin-left:6px;color:#ff7d00;font-size:12px">
              缺失
            </span>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="眼别">
        <el-radio-group v-model="eye">
          <el-radio-button value="OD">OD 右眼</el-radio-button>
          <el-radio-button value="OS">OS 左眼</el-radio-button>
          <el-radio-button value="OU">OU 双眼</el-radio-button>
          <el-radio-button value="UK">自动判断</el-radio-button>
        </el-radio-group>
        <div class="hint">未指定眼别时，按视盘位置自动判断左眼、右眼或双眼；对不准则标为眼别未知。</div>
      </el-form-item>
      <el-form-item label="影像文件">
        <div class="upload-area">
          <el-upload
            ref="uploadRef"
            :show-file-list="false"
            :on-change="onFileChange"
            :auto-upload="false"
            multiple
            accept=".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
            :disabled="uploading"
          >
            <el-button :icon="Plus" :disabled="uploading">添加文件</el-button>
            <span class="hint">PNG / JPG / WEBP / BMP / TIF，单文件 ≤ {{ MAX_SIZE_MB }}MB</span>
          </el-upload>
          <div v-if="files.length" class="files-grid">
            <div
              v-for="(f, i) in files"
              :key="i"
              class="file-cell"
            >
              <img v-if="previews[i]" :src="previews[i]" alt="preview" />
              <div v-else class="file-no-preview">TIF / 无预览</div>
              <div class="file-meta">
                <span class="fname" :title="f.name">{{ f.name }}</span>
                <el-button
                  size="small"
                  text
                  type="danger"
                  :disabled="uploading"
                  @click="removeFile(i)"
                >
                  移除
                </el-button>
              </div>
            </div>
          </div>
          <el-progress
            v-if="uploading"
            :percentage="uploadPercent"
            :stroke-width="6"
            style="margin-top: 8px"
          />
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false" :disabled="uploading">取消</el-button>
      <el-button type="primary" :loading="uploading" @click="onSubmit">
        确认上传 ({{ files.length }})
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.upload-area {
  width: 100%;
}
.hint {
  margin-left: 12px;
  color: #86909c;
  font-size: 12px;
}
.files-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}
.file-cell {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  overflow: hidden;
  background: #fafbfc;
  display: flex;
  flex-direction: column;
}
.file-cell img {
  width: 100%;
  height: 80px;
  object-fit: cover;
  background: #000;
}
.file-no-preview {
  width: 100%;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #86909c;
  font-size: 12px;
  background: #2a2a2a;
  color: #c9cdd4;
}
.file-meta {
  padding: 4px 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-top: 1px solid #f0f1f3;
}
.fname {
  font-size: 12px;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
