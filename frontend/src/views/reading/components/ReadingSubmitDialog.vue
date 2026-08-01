<script setup lang="ts">
/**
 * 保存 / 提交阅片
 *
 * 对应《医学培训端评估与工作流重构报告》P1：
 *   原先只有一个自由备注框，结论难评分、难审计、难统计。
 *   现改为结构化诊断表单（按病种由服务端下发），自由文本退居补充说明。
 *
 * 草稿允许不完整；正式提交由服务端校验结构化完备性，
 * 缺失项回显在表单顶部，而不是只报一句「提交失败」。
 */
import { computed, ref, watch } from 'vue'
import DiagnosisForm from './DiagnosisForm.vue'
import type { DiagnosisFormDef } from './DiagnosisForm.vue'

const props = defineProps<{
  visible: boolean
  saving: boolean
  defaultNote: string
  form: DiagnosisFormDef | null
  defaultDiagnosis?: Record<string, any>
  problems?: string[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'save', payload: { note: string; diagnosis: Record<string, any> }): void
  (e: 'submit', payload: { note: string; diagnosis: Record<string, any> }): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const diagnosis = ref<Record<string, any>>({})

watch(
  () => props.visible,
  (v) => {
    if (!v) return
    diagnosis.value = { ...(props.defaultDiagnosis || {}) }
    // 兼容历史记录：旧数据只有自由备注，迁进表单的补充说明字段
    if (!diagnosis.value.note && props.defaultNote) {
      diagnosis.value.note = props.defaultNote
    }
  }
)

const payload = () => ({
  note: diagnosis.value.note || '',
  diagnosis: diagnosis.value
})

const close = () => {
  dialogVisible.value = false
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="阅片结论"
    width="640"
    :close-on-click-modal="false"
    align-center
  >
    <DiagnosisForm v-model="diagnosis" :form="form" :problems="problems" />

    <template #footer>
      <div class="footer">
        <span class="muted">草稿可以不完整；提交时会校验结论完整性</span>
        <div>
          <el-button @click="close">取消</el-button>
          <el-button :loading="saving" @click="emit('save', payload())">
            保存草稿
          </el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="emit('submit', payload())"
          >
            提交阅片
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.muted {
  color: #86909c;
  font-size: 12px;
  line-height: 1.6;
}
</style>
