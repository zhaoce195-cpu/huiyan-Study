<script setup lang="ts">
/**
 * 来源编号是原数据或外部系统里的号（如 IDRiD）。
 * 平台病例号是本平台生成的 CASE 号，只在本系统内对照。
 * 单击其中一条，只复制这一条。
 */
import { ElMessage } from 'element-plus'
import { copyText } from '@/utils/copy-text'

withDefaults(
  defineProps<{
    sourceNo?: string
    platformNo?: string
    tone?: 'light' | 'dark'
  }>(),
  {
    sourceNo: '',
    platformNo: '',
    tone: 'light'
  }
)

const copy = async (text: string | undefined, name: string) => {
  const value = (text || '').trim()
  if (!value) return
  const ok = await copyText(value)
  if (ok) ElMessage.success(`已复制${name}`)
  else ElMessage.error('复制失败，请手动选择编号')
}
</script>

<template>
  <div class="case-ids" :class="tone">
    <button
      type="button"
      class="id-line"
      title="来源编号：原数据或外部系统中的编号，对外沟通时复制这一条。单击复制。"
      @click.stop="copy(sourceNo, '来源编号')"
    >
      <span class="id-k">来源编号</span>
      <span class="id-v">{{ sourceNo || '—' }}</span>
    </button>
    <button
      v-if="platformNo"
      type="button"
      class="id-line"
      title="平台病例号：本平台生成的唯一号，只在本系统内对照。单击复制。"
      @click.stop="copy(platformNo, '平台病例号')"
    >
      <span class="id-k">平台病例号</span>
      <span class="id-v">{{ platformNo }}</span>
    </button>
  </div>
</template>

<style scoped>
.case-ids {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 0;
}
.id-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  max-width: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.id-k {
  flex-shrink: 0;
  font-size: 11px;
  line-height: 1.4;
  color: #4e5969;
}
.id-v {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.4;
  color: #1677ff;
  word-break: break-all;
}
.id-line:hover .id-v {
  text-decoration: underline;
}
.case-ids.dark .id-k {
  color: #d5dae3;
}
.case-ids.dark .id-v {
  color: #9ec1ff;
}
</style>
