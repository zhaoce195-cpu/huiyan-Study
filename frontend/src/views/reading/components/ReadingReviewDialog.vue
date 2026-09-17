<script setup lang="ts">
/**
 * 教师当场评定学员阅片：通过 / 驳回写进记录，状态从待审核变为已通过或已驳回。
 * 不走影像质控接口，避免「调用失败」被当成评定失败。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ReadingApi } from '@/api'

const props = defineProps<{
  modelValue: boolean
  row: ReadingApi.ReadingRecord | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'done', row: ReadingApi.ReadingRecord): void
  (e: 'open-original', row: ReadingApi.ReadingRecord): void
}>()

const comment = ref('')
const submitting = ref(false)
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

watch(
  () => props.row,
  (row) => {
    comment.value = row?.reviewComment || ''
  },
  { immediate: true }
)

const statusMeta = computed(() => {
  const st = props.row?.status
  return st ? ReadingApi.READING_STATUS_META[st] : null
})

const canSubmit = computed(() => props.row?.status === 'SUBMITTED')

const submit = async (accept: boolean) => {
  const row = props.row
  const recordId = row?.id
  if (!row || !recordId) return
  if (row.status !== 'SUBMITTED') {
    ElMessage.warning('只有待审核记录可以评定')
    return
  }
  if (!accept && !comment.value.trim()) {
    ElMessage.warning('驳回需填写审核意见')
    return
  }
  submitting.value = true
  try {
    const out = await ReadingApi.reviewReading(recordId, {
      reviewComment: comment.value.trim(),
      accept
    })
    const who = row.userName || `用户${row.userId}`
    ElMessage.success(
      accept
        ? `已通过：${who} · ${row.caseNo}（记录 #${recordId}）。其它记录未改动。`
        : `已驳回：${who} · ${row.caseNo}（记录 #${recordId}）。其它记录未改动。`
    )
    emit('done', out)
    visible.value = false
  } catch {
    /* 拦截器已提示 */
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="质量评估 · 评定作业"
    width="520px"
    destroy-on-close
  >
    <template v-if="row">
      <div class="rev-meta">
        <div><span class="k">记录</span>#{{ row.id }}</div>
        <div><span class="k">学员</span>{{ row.userName || row.userId }}</div>
        <div><span class="k">病例</span>{{ row.caseNo }}</div>
        <div>
          <span class="k">状态</span>
          <el-tag v-if="statusMeta" size="small" :type="statusMeta.tag">
            {{ statusMeta.label }}
          </el-tag>
        </div>
      </div>
      <el-input
        v-model="comment"
        type="textarea"
        :rows="4"
        :disabled="!canSubmit"
        placeholder="评定意见（驳回必填）"
      />
      <p v-if="!canSubmit" class="rev-hint">该记录已评定，不能再次提交。</p>
    </template>
    <template #footer>
      <el-button
        v-if="row"
        text
        type="primary"
        @click="row && emit('open-original', row)"
      >
        查看原卷
      </el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        type="danger"
        :disabled="!canSubmit"
        :loading="submitting"
        @click="submit(false)"
      >
        驳回
      </el-button>
      <el-button
        type="primary"
        :disabled="!canSubmit"
        :loading="submitting"
        @click="submit(true)"
      >
        通过并提交
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.rev-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #1d2129;
}
.k {
  display: inline-block;
  width: 40px;
  color: #86909c;
}
.rev-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #86909c;
}
</style>
