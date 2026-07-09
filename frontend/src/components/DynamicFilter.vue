<script setup lang="ts">
/**
 * DynamicFilter 共享筛选条
 * - 给一份 FilterSchema，自动渲染对应控件
 * - 通过 v-model 双向绑定一个 plain object（key 与 schema.fields[].key 对应）
 * - daterange 字段会把 [start, end] 拆到 modelValue 的 startKey / endKey
 *
 * 主题适配：仅使用 Element Plus tokens，浅/深主题自动跟随
 */
import { computed, type Component } from 'vue'
import { ElButton, ElInput, ElSelect, ElOption, ElDatePicker, ElSwitch, ElIcon } from 'element-plus'
import {
  Search,
  Calendar,
  Iphone,
  Document,
  User,
  Refresh,
  RefreshLeft,
} from '@element-plus/icons-vue'
import type { FilterSchema, FilterFieldSchema } from '@/utils/filter-presets'

const props = withDefaults(
  defineProps<{
    modelValue: Record<string, any>
    schema: FilterSchema
    loading?: boolean
    /** 是否显示「查询/重置/刷新」按钮组（覆盖 schema.showActions） */
    showActions?: boolean
  }>(),
  {
    loading: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', v: Record<string, any>): void
  (e: 'submit'): void
  (e: 'reset'): void
  (e: 'refresh'): void
}>()

const showActions = computed(() => {
  if (props.showActions !== undefined) return props.showActions
  return props.schema.showActions ?? true
})

const ICON_MAP: Record<string, Component> = {
  Search,
  Calendar,
  Iphone,
  Document,
  User,
}

const setVal = (key: string, val: any) => {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}

/** 取 daterange 在 modelValue 中的当前值，组合成 [start, end] */
const getRange = (f: FilterFieldSchema): string[] => {
  if (!f.startKey || !f.endKey) return []
  const s = props.modelValue[f.startKey]
  const e = props.modelValue[f.endKey]
  if (!s && !e) return []
  return [s || '', e || '']
}

const setRange = (f: FilterFieldSchema, range: any) => {
  if (!f.startKey || !f.endKey) return
  const next = { ...props.modelValue }
  if (Array.isArray(range) && range.length === 2) {
    next[f.startKey] = range[0] || ''
    next[f.endKey] = range[1] || ''
  } else {
    next[f.startKey] = ''
    next[f.endKey] = ''
  }
  emit('update:modelValue', next)
}

const resetAll = () => {
  const next: Record<string, any> = {}
  props.schema.fields.forEach((f) => {
    if (f.type === 'daterange') {
      if (f.startKey) next[f.startKey] = ''
      if (f.endKey) next[f.endKey] = ''
    } else if (f.type === 'switch') {
      next[f.key] = false
    } else {
      next[f.key] = ''
    }
  })
  emit('update:modelValue', next)
  emit('reset')
}

const onSubmit = () => emit('submit')
const onRefresh = () => emit('refresh')

const widthOf = (f: FilterFieldSchema): string => {
  if (f.width) return f.width
  switch (f.type) {
    case 'text':
      return '220px'
    case 'select':
      return '140px'
    case 'daterange':
      return '320px'
    case 'switch':
      return 'auto'
    default:
      return '180px'
  }
}
</script>

<template>
  <div class="dynamic-filter">
    <template v-for="f in schema.fields" :key="f.key">
      <!-- 文本输入 -->
      <el-input
        v-if="f.type === 'text'"
        :model-value="modelValue[f.key] || ''"
        :placeholder="f.label"
        clearable
        size="small"
        :style="{ width: widthOf(f) }"
        @update:model-value="(v) => setVal(f.key, v)"
        @keyup.enter="onSubmit"
        @clear="onSubmit"
      >
        <template v-if="f.prefixIcon" #prefix>
          <el-icon><component :is="ICON_MAP[f.prefixIcon]" /></el-icon>
        </template>
      </el-input>

      <!-- 下拉选择 -->
      <el-select
        v-else-if="f.type === 'select'"
        :model-value="modelValue[f.key] || ''"
        :placeholder="f.label"
        clearable
        :multiple="!!f.multiple"
        size="small"
        :style="{ width: widthOf(f) }"
        @update:model-value="(v) => setVal(f.key, v)"
        @change="onSubmit"
      >
        <el-option
          v-for="opt in f.options"
          :key="String(opt.value)"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <!-- 日期 / 日期时间 区间 -->
      <el-date-picker
        v-else-if="f.type === 'daterange' || f.type === 'datetimerange'"
        :model-value="getRange(f)"
        :type="f.type"
        range-separator="至"
        :start-placeholder="`${f.label || '开始'}时间`"
        :end-placeholder="'结束时间'"
        :value-format="f.type === 'datetimerange' ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD'"
        size="small"
        :style="{ width: widthOf(f) }"
        @update:model-value="(v) => setRange(f, v)"
        @change="onSubmit"
      />

      <!-- 开关 -->
      <label v-else-if="f.type === 'switch'" class="df-switch">
        <el-switch
          :model-value="!!modelValue[f.key]"
          size="small"
          @update:model-value="(v) => { setVal(f.key, v); onSubmit() }"
        />
        <span class="df-switch-label">{{ f.label || f.key }}</span>
      </label>
    </template>

    <!-- 操作按钮组 -->
    <div v-if="showActions" class="df-actions">
      <el-button type="primary" size="small" :icon="Search" :loading="loading" @click="onSubmit">
        查询
      </el-button>
      <el-button size="small" :icon="RefreshLeft" @click="resetAll">重置</el-button>
      <el-button size="small" :icon="Refresh" :loading="loading" @click="onRefresh">刷新</el-button>
    </div>
  </div>
</template>

<style scoped>
.dynamic-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.df-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  height: 32px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  user-select: none;
}
.df-switch-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.df-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
</style>
