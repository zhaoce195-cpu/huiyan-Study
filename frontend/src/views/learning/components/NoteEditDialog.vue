<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { LearningApi } from '@/api'
import {
  emptyTable,
  noteContentIsEmpty,
  parseNoteContent,
  serializeNoteContent,
  type NoteBlock
} from '@/utils/note-content'

type Note = LearningApi.LearningNote

interface BindCase {
  caseId?: number | null
  caseNo?: string
  caseTitle?: string
  imageIndex?: number
  imageUrl?: string
  resourceId?: number | null
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
const blocks = ref<NoteBlock[]>([{ type: 'text', text: '' }])
const saving = ref(false)

const rules: FormRules = {
  content: [
    { required: true, message: '请输入笔记内容，或在表格中填写至少一格', trigger: 'blur' },
    { min: 1, message: '内容至少 1 个字', trigger: 'blur' }
  ]
}

const syncContent = () => {
  form.content = serializeNoteContent(blocks.value)
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
    form.resourceId = props.bind?.resourceId ?? null
  }
  blocks.value = parseNoteContent(form.content)
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
  if (props.bind?.caseTitle) return `已关联资料：${props.bind.caseTitle}`
  return '本笔记不绑定病例'
})

const tableIndex = (blockIndex: number) =>
  blocks.value.slice(0, blockIndex + 1).filter((b) => b.type === 'table').length

const insertTable = () => {
  const table: NoteBlock = { type: 'table', table: emptyTable() }
  const list = blocks.value
  const last = list[list.length - 1]
  if (last?.type === 'text' && !last.text.trim() && list.length > 1) {
    list.splice(list.length - 1, 0, table)
  } else {
    list.push(table)
    list.push({ type: 'text', text: '' })
  }
}

const asTable = (block: NoteBlock) => (block.type === 'table' ? block : null)

const addColumn = (block: NoteBlock) => {
  const table = asTable(block)
  if (!table) return
  table.table.headers.push('')
  table.table.rows.forEach((row) => row.push(''))
}

const removeColumn = (block: NoteBlock, index: number) => {
  const table = asTable(block)
  if (!table || table.table.headers.length <= 1) return
  table.table.headers.splice(index, 1)
  table.table.rows.forEach((row) => row.splice(index, 1))
}

const addRow = (block: NoteBlock) => {
  const table = asTable(block)
  if (!table) return
  table.table.rows.push(table.table.headers.map(() => ''))
}

const removeRow = (block: NoteBlock, index: number) => {
  const table = asTable(block)
  if (!table || table.table.rows.length <= 1) return
  table.table.rows.splice(index, 1)
}

const removeTable = (index: number) => {
  blocks.value.splice(index, 1)
  if (!blocks.value.some((b) => b.type === 'text')) {
    blocks.value.push({ type: 'text', text: '' })
  }
}

const handleSave = async () => {
  if (!formRef.value) return
  syncContent()
  if (noteContentIsEmpty(blocks.value)) {
    ElMessage.warning('请输入笔记内容，或在表格中填写至少一格')
    return
  }
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
    width="760px"
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
        <div class="note-editor">
          <template v-for="(block, bi) in blocks" :key="bi">
            <el-input
              v-if="block.type === 'text'"
              v-model="block.text"
              type="textarea"
              :rows="block.text || bi === 0 ? 5 : 3"
              placeholder="记录临床观察、思考与复盘要点。需要对照时，可在下方插入表格。"
            />
            <div v-else class="table-card">
              <div class="table-toolbar">
                <span class="table-label">表格 {{ tableIndex(bi) }}</span>
                <el-button size="small" @click="addColumn(block)">加列</el-button>
                <el-button size="small" @click="addRow(block)">加行</el-button>
                <el-button size="small" type="danger" plain @click="removeTable(bi)">删除表格</el-button>
              </div>
              <div class="table-scroll">
                <table class="edit-table">
                  <thead>
                    <tr>
                      <th v-for="(_head, hi) in block.table.headers" :key="hi">
                        <div class="cell-head">
                          <el-input v-model="block.table.headers[hi]" placeholder="表头" />
                          <el-button
                            v-if="block.table.headers.length > 1"
                            link
                            type="danger"
                            @click="removeColumn(block, hi)"
                          >删列</el-button>
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, ri) in block.table.rows" :key="ri">
                      <td v-for="(_cell, ci) in row" :key="ci">
                        <el-input
                          v-model="row[ci]"
                          type="textarea"
                          :autosize="{ minRows: 1, maxRows: 4 }"
                          placeholder="填写"
                        />
                      </td>
                      <td class="row-ops">
                        <el-button
                          v-if="block.table.rows.length > 1"
                          link
                          type="danger"
                          @click="removeRow(block, ri)"
                        >删行</el-button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
          <el-button class="insert-btn" @click="insertTable">插入表格</el-button>
        </div>
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
.note-editor {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.table-card {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  padding: 8px;
  background: #fafbfc;
}
.table-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.table-label {
  margin-right: auto;
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
}
.table-scroll {
  overflow-x: auto;
}
.edit-table {
  width: 100%;
  border-collapse: collapse;
}
.edit-table th,
.edit-table td {
  border: 1px solid #e5e6eb;
  padding: 4px;
  vertical-align: top;
  background: #fff;
}
.cell-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.row-ops {
  width: 52px;
  background: #fafbfc;
  border: none !important;
}
.insert-btn {
  align-self: flex-start;
}
</style>
