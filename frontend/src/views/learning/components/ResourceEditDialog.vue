<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { LearningApi, CommonApi } from '@/api'
import UniversalUploader from '@/components/UniversalUploader.vue'

type Resource = LearningApi.LearningResource

const props = defineProps<{
  visible: boolean
  resource: Resource | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved', r: Resource): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const isEdit = computed(() => !!props.resource?.id)

const formRef = ref<FormInstance | null>(null)
const form = reactive<LearningApi.ResourceCreateParams>({
  title: '',
  summary: '',
  content: '',
  resourceType: 'KNOWLEDGE',
  tags: '',
  coverUrl: '',
  fileUrl: '',
  fileType: '',
  caseId: null,
  status: 'PUBLISHED'
})
const saving = ref(false)

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  resourceType: [{ required: true, message: '请选择分类', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const reset = () => {
  form.title = props.resource?.title || ''
  form.summary = props.resource?.summary || ''
  form.content = props.resource?.content || ''
  form.resourceType = props.resource?.resourceType || 'KNOWLEDGE'
  form.tags = props.resource?.tags || ''
  form.coverUrl = props.resource?.coverUrl || ''
  form.fileUrl = props.resource?.fileUrl || ''
  form.fileType = props.resource?.fileType || ''
  form.caseId = props.resource?.caseId ?? null
  form.status = props.resource?.status || 'PUBLISHED'
}

watch(
  () => props.visible,
  (v) => {
    if (v) reset()
  }
)

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  saving.value = true
  try {
    let out: Resource
    if (isEdit.value && props.resource) {
      out = await LearningApi.updateResource(props.resource.id, { ...form })
    } else {
      out = await LearningApi.createResource({ ...form })
    }
    emit('saved', out)
    dialogVisible.value = false
  } finally {
    saving.value = false
  }
}

/* ========== 附件上传 → 走 /common/upload ========== */
const onUploadSuccess = (r: CommonApi.UploadFileResult) => {
  form.fileUrl = r?.url || ''
  // 简单按扩展名推断 fileType
  const ext = (form.fileUrl.split('.').pop() || '').toLowerCase()
  if (ext === 'pdf') form.fileType = 'pdf'
  else if (['mp4', 'webm', 'mov', 'm4v', 'avi', 'mkv', 'wmv'].includes(ext)) form.fileType = 'video'
  else if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext)) form.fileType = 'image'
  else if (['doc', 'docx'].includes(ext)) form.fileType = 'word'
  else if (['ppt', 'pptx'].includes(ext)) form.fileType = 'ppt'
  ElMessage.success('附件已上传')
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑学习资料' : '上传学习资料'"
    width="700px"
    destroy-on-close
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="92px"
      size="default"
    >
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入资料标题" />
      </el-form-item>

      <el-form-item label="分类" prop="resourceType">
        <el-select v-model="form.resourceType" style="width: 100%">
          <el-option
            v-for="o in LearningApi.RESOURCE_TYPE_OPTIONS"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="状态" prop="status">
        <el-radio-group v-model="form.status">
          <el-radio
            v-for="o in LearningApi.RESOURCE_STATUS_OPTIONS"
            :key="o.value"
            :value="o.value"
          >
            {{ o.label }}
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="标签">
        <el-input
          v-model="form.tags"
          placeholder="多个标签用英文逗号分隔，如：DR,出血,2级"
        />
      </el-form-item>

      <el-form-item label="封面图 URL">
        <el-input v-model="form.coverUrl" placeholder="可选，建议宽高比 16:9" />
      </el-form-item>

      <el-form-item label="附件类型">
        <el-select v-model="form.fileType" clearable placeholder="可选" style="width: 100%">
          <el-option
            v-for="o in LearningApi.FILE_TYPE_OPTIONS"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="附件 URL">
        <el-input v-model="form.fileUrl" placeholder="PDF / 视频 / 图片 / 文档外链，或点击下方上传" />
      </el-form-item>

      <el-form-item label="附件上传">
        <UniversalUploader
          biz="learning"
          variant="button"
          @success="onUploadSuccess"
        >
          点击上传附件
        </UniversalUploader>
        <span style="margin-left:10px;color:var(--el-text-color-secondary);font-size:12px">
          上传成功后自动回填上方 URL；支持视频、PPT、Word、PDF、图片；≤ 50MB
        </span>
      </el-form-item>

      <el-form-item label="关联病例 ID">
        <el-input-number
          v-model="form.caseId"
          :min="1"
          :step="1"
          placeholder="可选"
          style="width: 100%"
          :controls="false"
        />
      </el-form-item>

      <el-form-item label="简介">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="2"
          placeholder="一句话简介"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="正文内容">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="6"
          placeholder="支持纯文本 / Markdown"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
