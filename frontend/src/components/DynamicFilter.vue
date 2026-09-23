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
import {
  ElButton,
  ElInput,
  ElSelect,
  ElOption,
  ElDatePicker,
  ElSwitch,
  ElIcon,
  ElTooltip,
} from 'element-plus'
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
    /** 是否显示「查询/刷新」。「清除」始终显示。覆盖 schema.showActions。 */
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

/**
 * 就地改绑定对象，而不是 emit 一个全新对象。
 *
 * 之前每次输入都 emit `{ ...modelValue, key: val }`，父组件 `v-model="filter"`
 * 会把 `filter` 整个换成这个**普通对象** —— reactive 代理没了，此后视图再也不
 * 跟着更新：输入框打字不显示、退格无效，只有别的东西（比如翻页）触发一次重渲染
 * 才把攒下的文本刷出来。
 *
 * 就地 mutate 能保住父组件的 reactive/ref 代理；再把同一个对象 emit 回去，
 * v-model 的赋值就成了「赋回自己」，语义完整且无副作用。
 */
const commit = () => emit('update:modelValue', props.modelValue)

const setVal = (key: string, val: any) => {
  props.modelValue[key] = val
  // 改了一个字段可能让别的字段变成不适用（比如病种换成 AMD 后 DR 分级失效），
  // 顺手把它们清掉：留一个禁用但仍在生效的条件，用户只会看到「怎么什么都搜不到」
  clearDisabledFields()
  commit()
}

const isDisabled = (f: FilterFieldSchema): boolean =>
  typeof f.disabledWhen === 'function' ? !!f.disabledWhen(props.modelValue) : false

const clearDisabledFields = () => {
  props.schema.fields.forEach((f) => {
    if (!isDisabled(f)) return
    if (f.type === 'daterange' || f.type === 'datetimerange') {
      if (f.startKey) props.modelValue[f.startKey] = ''
      if (f.endKey) props.modelValue[f.endKey] = ''
    } else if (f.type === 'switch') {
      props.modelValue[f.key] = false
    } else {
      props.modelValue[f.key] = ''
    }
  })
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
  const ok = Array.isArray(range) && range.length === 2
  props.modelValue[f.startKey] = ok ? range[0] || '' : ''
  props.modelValue[f.endKey] = ok ? range[1] || '' : ''
  commit()
}

const resetAll = () => {
  props.schema.fields.forEach((f) => {
    if (f.type === 'daterange' || f.type === 'datetimerange') {
      if (f.startKey) props.modelValue[f.startKey] = ''
      if (f.endKey) props.modelValue[f.endKey] = ''
    } else if (f.type === 'switch') {
      props.modelValue[f.key] = false
    } else {
      props.modelValue[f.key] = ''
    }
  })
  commit()
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
      <el-tooltip
        v-else-if="f.type === 'select'"
        :disabled="!isDisabled(f) || !f.disabledHint"
        :content="f.disabledHint"
        placement="top"
      >
        <el-select
          :model-value="modelValue[f.key] || ''"
          :placeholder="isDisabled(f) ? '不适用' : f.label"
          clearable
          :disabled="isDisabled(f)"
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
      </el-tooltip>

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

    <!-- 一键清除始终在；查询 / 刷新由 schema 或 showActions 决定 -->
    <div class="df-actions">
      <el-button class="df-clear" size="small" :icon="RefreshLeft" @click="resetAll">
        清除
      </el-button>
      <el-button
        v-if="showActions"
        type="primary"
        size="small"
        :icon="Search"
        :loading="loading"
        @click="onSubmit"
      >
        查询
      </el-button>
      <el-button v-if="showActions" size="small" :icon="Refresh" :loading="loading" @click="onRefresh">
        刷新
      </el-button>
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
  flex-shrink: 0;
}
.df-clear {
  --el-button-text-color: #1d2129;
  --el-button-bg-color: #ffffff;
  --el-button-border-color: #c9cdd4;
  --el-button-hover-text-color: #1d2129;
  --el-button-hover-bg-color: #f2f3f5;
  --el-button-hover-border-color: #86909c;
}
</style>
