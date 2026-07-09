<script setup lang="ts">
/**
 * DR 分级标签
 * - 字符串 / 数字均可，颜色由 utils/dr-format 提供
 * - 用法：<DRGradeTag :grade="r.drGrade" :text="r.drGradeText" />
 */
import { computed } from 'vue'
import { ElTag } from 'element-plus'
import { drGradeColor, drGradeColorNum } from '@/utils/dr-format'

const props = withDefaults(
  defineProps<{
    grade?: string | number | null
    text?: string
    /** 输入是否为 number 模式（AI 数值 0~4），决定用哪个色阶函数 */
    numeric?: boolean
    size?: 'small' | 'default' | 'large'
    /** 默认 effect=plain（浅色背景）；外部可覆盖 */
    effect?: 'plain' | 'dark' | 'light'
  }>(),
  {
    size: 'small',
    effect: 'plain',
  },
)

const GRADE_TEXT: Record<string, string> = {
  '0': '0 级（无 DR）',
  '1': '1 级（轻度）',
  '2': '2 级（中度）',
  '3': '3 级（重度 NPDR）',
  '4': '4 级（PDR）',
}

const color = computed(() =>
  props.numeric ? drGradeColorNum(Number(props.grade)) : drGradeColor(props.grade as any),
)

const display = computed(() => {
  if (props.text) return props.text
  const s = String(props.grade ?? '')
  return GRADE_TEXT[s] || (s ? `DR ${s} 级` : '—')
})
</script>

<template>
  <el-tag
    :size="size"
    :effect="effect"
    :style="{ color, borderColor: color, background: 'transparent' }"
  >
    {{ display }}
  </el-tag>
</template>
