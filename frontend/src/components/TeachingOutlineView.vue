<script setup lang="ts">
import { computed } from 'vue'
import { parseTeachingPoints } from '@/utils/teaching-outline'

const props = defineProps<{
  text?: string
  tone?: 'light' | 'dark'
}>()

const parsed = computed(() => parseTeachingPoints(props.text || ''))
</script>

<template>
  <dl v-if="parsed.items.length" class="outline" :class="{ dark: tone === 'dark' }">
    <div v-for="item in parsed.items" :key="item.label" class="row">
      <dt>{{ item.label }}</dt>
      <dd>{{ item.text }}</dd>
    </div>
  </dl>
  <p v-else-if="parsed.legacy" class="plain" :class="{ dark: tone === 'dark' }">{{ parsed.legacy }}</p>
</template>

<style scoped>
.outline {
  margin: 0;
}
.row + .row {
  margin-top: 8px;
}
dt {
  font-size: 13px;
  font-weight: 700;
  color: #1d2129;
}
dd,
.plain {
  margin: 2px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  font-size: 14px;
  color: #1d2129;
}
.dark dt,
.dark dd,
.plain.dark {
  color: #e5e6eb;
}
</style>
