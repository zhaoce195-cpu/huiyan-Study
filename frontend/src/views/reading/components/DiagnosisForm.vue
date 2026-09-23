<script setup lang="ts">
/**
 * 结构化诊断表单
 *
 * 对应《医学培训端评估与工作流重构报告》P1：
 *   「阅片提交只有自由备注，缺少可判读性、征象、分级、置信度、处置」
 *   「结论难评分、难审计、难统计」
 *
 * 表单由后端按病种下发，前端不硬编码任何字段——
 * 新增病种只改配置，界面自动适配（报告 5.1：表单必须病种特异）。
 *
 * 渐进展开：选中「不可判读」后，分级与征象整体隐藏。
 * 此时再逼学员填分级没有意义，还会诱导他对着看不清的图硬猜。
 */
import { computed, ref, watch } from 'vue'

interface FieldOption {
  value: string
  label: string
}
interface FormField {
  key: string
  label: string
  type: 'radio' | 'select' | 'checkbox' | 'text' | 'textarea'
  required: boolean
  order: number
  options?: FieldOption[]
  hint?: string
  placeholder?: string
}
export interface DiagnosisFormDef {
  category: string
  categoryKnown: boolean
  ungradableValue: string
  skipWhenUngradable: string[]
  fields: FormField[]
}

const props = defineProps<{
  form: DiagnosisFormDef | null
  modelValue: Record<string, any>
  /** 提交失败时后端返回的缺失项 */
  problems?: string[]
  /** 深色面板上使用浅色字，避免标签落到深底上看不清 */
  tone?: 'light' | 'dark'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: Record<string, any>): void
}>()

const answers = ref<Record<string, any>>({ ...props.modelValue })

watch(
  () => props.modelValue,
  (v) => {
    answers.value = { ...v }
  },
  { deep: true }
)

const update = (key: string, value: any) => {
  answers.value = { ...answers.value, [key]: value }
  emit('update:modelValue', answers.value)
}

/** 是否已判定为不可判读 */
const isUngradable = computed(
  () => answers.value.readability === props.form?.ungradableValue
)

/** 当前应展示的字段：不可判读时隐藏诊断类字段 */
const visibleFields = computed(() => {
  const all = props.form?.fields || []
  if (!isUngradable.value) return all
  const skip = new Set(props.form?.skipWhenUngradable || [])
  return all.filter((f) => !skip.has(f.key))
})
</script>

<template>
  <div v-if="form" class="diag-form" :class="{ 'is-dark': tone === 'dark' }">
    <el-alert
      v-if="!form.categoryKnown"
      type="info"
      :closable="false"
      show-icon
      title="该病种暂无专用表单，使用通用结论字段"
      description="不套用 DR 量表，避免诱导对非 DR 病例做 DR 分级"
      class="mb"
    />

    <el-alert
      v-if="isUngradable"
      type="warning"
      :closable="false"
      show-icon
      title="已标记为不可判读"
      description="分级与征象字段已隐藏。请选择重新拍摄或转诊，不要给出阴性结论。"
      class="mb"
    />

    <el-alert
      v-if="problems && problems.length"
      type="error"
      :closable="false"
      show-icon
      title="诊断结论不完整，无法提交"
      class="mb"
    >
      <ul class="problems">
        <li v-for="p in problems" :key="p">{{ p }}</li>
      </ul>
    </el-alert>

    <div v-for="f in visibleFields" :key="f.key" class="field">
      <div class="label">
        <span v-if="f.required" class="req">*</span>{{ f.label }}
      </div>

      <el-radio-group
        v-if="f.type === 'radio'"
        :model-value="answers[f.key]"
        @update:model-value="(v: any) => update(f.key, v)"
      >
        <el-radio v-for="o in f.options" :key="o.value" :value="o.value">
          {{ o.label }}
        </el-radio>
      </el-radio-group>

      <el-select
        v-else-if="f.type === 'select'"
        :model-value="answers[f.key]"
        placeholder="请选择"
        class="ctrl"
        @update:model-value="(v: any) => update(f.key, v)"
      >
        <el-option
          v-for="o in f.options"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>

      <el-checkbox-group
        v-else-if="f.type === 'checkbox'"
        :model-value="answers[f.key] || []"
        @update:model-value="(v: any) => update(f.key, v)"
      >
        <el-checkbox v-for="o in f.options" :key="o.value" :value="o.value">
          {{ o.label }}
        </el-checkbox>
      </el-checkbox-group>

      <el-input
        v-else-if="f.type === 'textarea'"
        type="textarea"
        :rows="3"
        :model-value="answers[f.key]"
        :placeholder="f.placeholder"
        @update:model-value="(v: any) => update(f.key, v)"
      />

      <el-input
        v-else
        :model-value="answers[f.key]"
        :placeholder="f.placeholder"
        class="ctrl"
        @update:model-value="(v: any) => update(f.key, v)"
      />

      <div v-if="f.hint" class="hint">{{ f.hint }}</div>
    </div>
  </div>
</template>

<style scoped>
.diag-form {
  max-height: 56vh;
  overflow-y: auto;
  padding-right: 6px;
  font-family: var(--hy-font);
}
.mb {
  margin-bottom: 12px;
}
.field {
  margin-bottom: 16px;
}
.label {
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  color: #1d2129;
  letter-spacing: 0.2px;
}
.req {
  margin-right: 3px;
  color: #f56c6c;
}
.ctrl {
  width: 100%;
}
.diag-form :deep(.el-radio-group) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.diag-form :deep(.el-radio) {
  height: auto;
  margin-right: 0;
  white-space: normal;
  align-items: flex-start;
}
.diag-form :deep(.el-radio__label) {
  line-height: 1.5;
  white-space: normal;
}
.hint {
  margin-top: 5px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
}
.is-dark .label {
  color: #f5f7fa;
}
.is-dark .hint {
  color: #d5dae3;
}
.is-dark :deep(.el-radio__label),
.is-dark :deep(.el-checkbox__label) {
  color: #eef1f6;
  font-size: 13px;
  font-weight: 500;
}
.problems {
  margin: 4px 0 0;
  padding-left: 18px;
  line-height: 1.9;
}
</style>
