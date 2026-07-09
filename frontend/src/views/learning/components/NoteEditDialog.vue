<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { LearningApi } from '@/api'

type Note = LearningApi.LearningNote

interface BindCase {
  caseId?: number | null
  caseNo?: string
  caseTitle?: string
  imageIndex?: number
  imageUrl?: string
}

const props = defineProps<{
  visible: boolean
  /** 已有笔记则进入编辑模式 */
  note?: Note | null
  /** 新建时绑定的病例上下文 */
  bind?: BindCase | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved', note: Note): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})
const isEdit = computed(() => !!props.note?.id)

const formRef = ref<FormInstance | null>(null)
const form = reactive<LearningApi.NoteCreateParams>({
  title: '',
  content: '',
  tags: '',
  caseId: null,
  imageIndex: -1,
  imageUrl: '',
  resourceId: null
})
const saving = ref(false)

const rules: FormRules = {
  content: [
    { required: true, message: '请输入笔记内容', trigger: 'blur' },
    { min: 1, message: '内容至少 1 个字', trigger: 'blur' }
  ]
}

const reset = () => {
  if (props.note) {
    form.title = props.note.title || ''
    form.content = props.note.content || ''
    form.tags = props.note.tags || ''
    form.caseId = props.note.caseId
    form.imageIndex = props.note.imageIndex
    form.imageUrl = props.note.imageUrl
    form.resourceId = props.note.resourceId
  } else {
    form.title = ''
    form.content = ''
    form.tags = ''
    form.caseId = props.bind?.caseId ?? null
    form.imageIndex = props.bind?.imageIndex ?? -1
    form.imageUrl = props.bind?.imageUrl ?? ''
    form.resourceId = null
  }
}

watch(() => props.visible, (v) => {
  if (v) reset()
})

const bindHint = computed(() => {
  if (isEdit.value) return ''
  if (props.bind?.caseNo) {
    const idxText = props.bind.imageIndex !== undefined && props.bind.imageIndex >= 0
      ? `· 影像 #${props.bind.imageIndex + 1}` : ''
    return `已绑定病例 ${props.bind.caseNo}${props.bind.caseTitle ? ` (${props.bind.caseTitle})` : ''} ${idxText}`
  }
  if (form.caseId) return `已绑定病例 ID #${form.caseId}`
  return '本笔记不绑定病例'
})

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  saving.value = true
  try {
    let out: Note
    if (isEdit.value && props.note) {
      out = await LearningApi.updateNote(props.note.id, { ...form })
    } else {
      out = await LearningApi.createNote({ ...form })
    }
    emit('saved', out)
    dialogVisible.value = false
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑学习笔记' : '新建学习笔记'"
    width="640px"
    destroy-on-close
  >
    <div class="bind-line" v-if="bindHint">{{ bindHint }}</div>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="80px"
      size="default"
    >
      <el-form-item label="标题">
        <el-input v-model="form.title" placeholder="可选，便于检索" />
      </el-form-item>

      <el-form-item label="标签">
        <el-input v-model="form.tags" placeholder="多标签英文逗号分隔" />
      </el-form-item>

      <el-form-item label="正文" prop="content">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="8"
          placeholder="记录你的临床观察、思考与复盘要点…"
        />
      </el-form-item>

      <el-form-item label="病例 ID" v-if="!isEdit && !props.bind?.caseId">
        <el-input-number
          v-model="form.caseId"
          :min="1"
          :step="1"
          placeholder="可选"
          style="width: 100%"
          :controls="false"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">
        保存笔记
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bind-line {
  background: #eef4ff;
  color: #1677ff;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 12px;
}
</style>
