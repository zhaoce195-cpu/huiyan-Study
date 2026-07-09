<script setup lang="ts">
import { computed } from 'vue'
import {
  Rank,
  ZoomIn,
  Sunny,
  Crop,
  EditPen,
  Edit,
  Connection,
  CaretRight,
  Delete,
  RefreshLeft,
  RefreshRight,
  RefreshLeft as ResetIcon,
  Aim
} from '@element-plus/icons-vue'
import type { ToolName } from '../types'

const props = defineProps<{
  tool: ToolName
  canAnnotate: boolean
  canUndo: boolean
  canRedo: boolean
}>()

const emit = defineEmits<{
  (e: 'set-tool', t: ToolName): void
  (e: 'undo'): void
  (e: 'redo'): void
  (e: 'clear'): void
  (e: 'reset-view'): void
}>()

interface ToolDef {
  tool: ToolName
  label: string
  icon: any
  group: 'view' | 'mark' | 'measure'
  needAnnotate?: boolean
}

const tools: ToolDef[] = [
  { tool: 'pan', label: '平移', icon: Rank, group: 'view' },
  { tool: 'zoom', label: '缩放', icon: ZoomIn, group: 'view' },
  { tool: 'wwwc', label: '窗位', icon: Sunny, group: 'view' },
  { tool: 'rect', label: '矩形', icon: Crop, group: 'mark', needAnnotate: true },
  { tool: 'polygon', label: '多边形', icon: EditPen, group: 'mark', needAnnotate: true },
  { tool: 'freehand', label: '手绘', icon: Edit, group: 'mark', needAnnotate: true },
  { tool: 'length', label: '距离', icon: Connection, group: 'measure', needAnnotate: true },
  { tool: 'angle', label: '角度', icon: CaretRight, group: 'measure', needAnnotate: true },
  { tool: 'eraser', label: '擦除', icon: Delete, group: 'mark', needAnnotate: true }
]

const groups = computed(() => {
  const map: Record<string, ToolDef[]> = {}
  tools.forEach((t) => {
    if (!map[t.group]) map[t.group] = []
    map[t.group].push(t)
  })
  return map
})

const isActive = (t: ToolName) => props.tool === t

const handleClick = (t: ToolDef) => {
  if (t.needAnnotate && !props.canAnnotate) return
  emit('set-tool', t.tool)
}
</script>

<template>
  <aside class="toolbar">
    <div v-for="(items, key) in groups" :key="key" class="tool-group">
      <button
        v-for="t in items"
        :key="t.tool"
        class="tool-btn"
        :class="{ active: isActive(t.tool), disabled: t.needAnnotate && !canAnnotate }"
        :title="t.label + (t.needAnnotate && !canAnnotate ? '（无权限）' : '')"
        @click="handleClick(t)"
      >
        <el-icon><component :is="t.icon" /></el-icon>
        <span class="tool-label">{{ t.label }}</span>
      </button>
      <div class="group-sep" />
    </div>

    <!-- 操作按钮 -->
    <button
      class="tool-btn"
      :class="{ disabled: !canUndo }"
      title="撤销"
      @click="emit('undo')"
    >
      <el-icon><RefreshLeft /></el-icon>
      <span class="tool-label">撤销</span>
    </button>
    <button
      class="tool-btn"
      :class="{ disabled: !canRedo }"
      title="重做"
      @click="emit('redo')"
    >
      <el-icon><RefreshRight /></el-icon>
      <span class="tool-label">重做</span>
    </button>
    <button class="tool-btn" title="重置视图" @click="emit('reset-view')">
      <el-icon><Aim /></el-icon>
      <span class="tool-label">归位</span>
    </button>
    <button class="tool-btn danger" title="清空标注" @click="emit('clear')">
      <el-icon><ResetIcon /></el-icon>
      <span class="tool-label">清空</span>
    </button>
  </aside>
</template>

<style scoped>
.toolbar {
  background: #181a20;
  border-right: 1px solid #2a2a2a;
  padding: 10px 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.tool-group {
  display: contents;
}
.group-sep {
  height: 1px;
  margin: 6px 8px;
  background: #2a2a2a;
}

.tool-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  margin: 0 6px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: #c9cdd4;
  font-size: 11px;
  cursor: pointer;
  transition: 0.15s;
  user-select: none;
}
.tool-btn :deep(.el-icon) {
  font-size: 18px;
}
.tool-btn:hover:not(.disabled) {
  background: rgba(64, 145, 255, 0.12);
  color: #4091ff;
}
.tool-btn.active {
  background: rgba(64, 145, 255, 0.22);
  border-color: rgba(64, 145, 255, 0.5);
  color: #4091ff;
}
.tool-btn.danger {
  color: #ff7875;
}
.tool-btn.danger:hover:not(.disabled) {
  background: rgba(245, 63, 63, 0.14);
}
.tool-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.tool-label {
  font-size: 11px;
  letter-spacing: 0.5px;
}
</style>
