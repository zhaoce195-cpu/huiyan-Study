<script setup lang="ts">
/**
 * 体检筛查端工作区包装组件
 * - 复用 views/screening/index.vue 整个监控大屏（包含统计/批量上传/筛查列表/报告预览）
 * - 通过 props.section 切换时滚动到对应区块，不修改原页面
 */
import { nextTick, onMounted, ref, watch } from 'vue'
import ScreeningPage from '@/views/screening/index.vue'

const props = defineProps<{ section?: 'upload' | 'list' | 'reports' }>()

const containerRef = ref<HTMLDivElement | null>(null)

const SELECTOR_MAP: Record<string, string> = {
  upload: '.upload-card',
  list: '.task-card',
  reports: '.report'
}

const scrollToSection = () => {
  const sel = SELECTOR_MAP[props.section || 'upload']
  if (!sel || !containerRef.value) return
  const el = containerRef.value.querySelector(sel) as HTMLElement | null
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => nextTick(scrollToSection))
watch(() => props.section, () => nextTick(scrollToSection))
</script>

<template>
  <div ref="containerRef" class="screening-workspace">
    <ScreeningPage />
  </div>
</template>

<style scoped>
.screening-workspace {
  width: 100%;
  min-height: 100vh;
}
</style>
