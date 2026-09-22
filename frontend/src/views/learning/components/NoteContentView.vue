<script setup lang="ts">
import { computed } from 'vue'
import { parseNoteContent } from '@/utils/note-content'

const props = defineProps<{
  content?: string
}>()

const blocks = computed(() => parseNoteContent(props.content || ''))
</script>

<template>
  <div class="note-view">
    <template v-for="(block, i) in blocks" :key="i">
      <p v-if="block.type === 'text' && block.text.trim()" class="note-text">{{ block.text }}</p>
      <div v-else-if="block.type === 'table'" class="note-table-wrap">
        <table class="note-table">
          <thead>
            <tr>
              <th v-for="(head, hi) in block.table.headers" :key="hi">
                {{ head || ' ' }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in block.table.rows" :key="ri">
              <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.note-view {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.note-text {
  margin: 0;
  white-space: pre-wrap;
  color: #4e5969;
  line-height: 1.7;
  font-size: 13px;
}
.note-table-wrap {
  overflow-x: auto;
}
.note-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  color: #1d2129;
}
.note-table th,
.note-table td {
  border: 1px solid #e5e6eb;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
  line-height: 1.5;
  white-space: pre-wrap;
}
.note-table th {
  background: #f2f3f5;
  font-weight: 600;
}
</style>
