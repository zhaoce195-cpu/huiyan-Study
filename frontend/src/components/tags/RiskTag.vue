<script setup lang="ts">
/**
 * 风险等级标签
 * - 内部用 el-tag + utils/dr-format 的 riskTagType 映射
 * - 用法：<RiskTag :level="r.riskLevel" :text="r.riskLevelText" />
 */
import { computed } from 'vue'
import { ElTag } from 'element-plus'
import { riskTagType } from '@/utils/dr-format'

const props = withDefaults(
  defineProps<{
    level?: string | null
    /** 显示文本，不传走默认映射 */
    text?: string
    size?: 'small' | 'default' | 'large'
    effect?: 'plain' | 'dark' | 'light'
  }>(),
  {
    size: 'small',
    effect: 'plain',
  },
)

const TYPE_TEXT: Record<string, string> = {
  URGENT: '紧急',
  HIGH: '高风险',
  MEDIUM: '中风险',
  LOW: '低风险',
  red: '高风险',
  yellow: '中风险',
  green: '低风险',
}

const tagType = computed(() => riskTagType(props.level))
const display = computed(() => props.text || TYPE_TEXT[props.level || ''] || props.level || '—')
</script>

<template>
  <el-tag :type="tagType" :size="size" :effect="effect">
    {{ display }}
  </el-tag>
</template>
