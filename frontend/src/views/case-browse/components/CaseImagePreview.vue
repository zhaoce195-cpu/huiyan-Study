<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ZoomIn, ZoomOut, RefreshLeft, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  images: string[]
  initialIndex?: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const currentIndex = ref(props.initialIndex || 0)
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const dragging = ref(false)

const MIN_SCALE = 0.25
const MAX_SCALE = 4

let dragOriginX = 0
let dragOriginY = 0
let pointerOriginX = 0
let pointerOriginY = 0

const resetView = () => {
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      currentIndex.value = props.initialIndex || 0
      resetView()
    }
  }
)

const currentImage = computed(() => props.images[currentIndex.value] || '')

const selectImage = (index: number) => {
  currentIndex.value = index
  resetView()
}

const prev = () => {
  if (currentIndex.value > 0) selectImage(currentIndex.value - 1)
}
const next = () => {
  if (currentIndex.value < props.images.length - 1) selectImage(currentIndex.value + 1)
}

const zoomIn = () => {
  scale.value = Math.min(MAX_SCALE, +(scale.value + 0.25).toFixed(2))
}
const zoomOut = () => {
  scale.value = Math.max(MIN_SCALE, +(scale.value - 0.25).toFixed(2))
}

const isControlTarget = (target: EventTarget | null) =>
  target instanceof Element && !!target.closest('button')

const onPointerDown = (event: PointerEvent) => {
  if (event.button !== 0 || isControlTarget(event.target)) return
  dragging.value = true
  pointerOriginX = event.clientX
  pointerOriginY = event.clientY
  dragOriginX = offsetX.value
  dragOriginY = offsetY.value
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}

const onPointerMove = (event: PointerEvent) => {
  if (!dragging.value) return
  offsetX.value = dragOriginX + (event.clientX - pointerOriginX)
  offsetY.value = dragOriginY + (event.clientY - pointerOriginY)
}

const onPointerUp = () => {
  dragging.value = false
}

const onWheel = (event: WheelEvent) => {
  if (isControlTarget(event.target)) return
  const factor = event.deltaY < 0 ? 1.1 : 0.9
  const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale.value * factor))
  scale.value = +next.toFixed(2)
}

const onDblClick = (event: MouseEvent) => {
  if (isControlTarget(event.target)) return
  resetView()
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="影像预览"
    width="900"
    top="5vh"
    :close-on-click-modal="false"
    align-center
    destroy-on-close
  >
    <div class="viewer-wrap">
      <!-- 主视图 -->
      <div
        class="stage"
        :class="{ dragging }"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @dblclick="onDblClick"
        @wheel.prevent="onWheel"
      >
        <img
          v-if="currentImage"
          :src="currentImage"
          class="viewer-img"
          draggable="false"
          :style="{ transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})` }"
        />
        <div v-else class="empty">暂无影像</div>

        <el-button
          v-if="images.length > 1"
          class="nav nav-left"
          circle
          :icon="ArrowLeft"
          :disabled="currentIndex === 0"
          @click="prev"
        />
        <el-button
          v-if="images.length > 1"
          class="nav nav-right"
          circle
          :icon="ArrowRight"
          :disabled="currentIndex === images.length - 1"
          @click="next"
        />
      </div>

      <!-- 工具栏 -->
      <div class="toolbar">
        <span class="counter">
          {{ images.length === 0 ? '0 / 0' : `${currentIndex + 1} / ${images.length}` }}
        </span>
        <div class="tools">
          <el-button :icon="ZoomOut" size="small" @click="zoomOut">缩小</el-button>
          <el-button size="small" @click="resetView">{{ Math.round(scale * 100) }}%</el-button>
          <el-button :icon="ZoomIn" size="small" @click="zoomIn">放大</el-button>
          <el-button :icon="RefreshLeft" size="small" @click="resetView">重置</el-button>
          <span class="pan-hint">按住拖动可平移，双击回到整图</span>
        </div>
      </div>

      <!-- 缩略图条 -->
      <div v-if="images.length > 1" class="thumb-strip">
        <div
          v-for="(img, i) in images"
          :key="i"
          class="strip-cell"
          :class="{ active: i === currentIndex }"
          @click="selectImage(i)"
        >
          <img :src="img" />
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.viewer-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.stage {
  position: relative;
  background: #0e0f12;
  border-radius: 8px;
  overflow: hidden;
  height: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.stage.dragging {
  cursor: grabbing;
}
.viewer-img {
  max-width: 100%;
  max-height: 100%;
  transform-origin: center center;
  transition: transform 0.2s;
  user-select: none;
  pointer-events: none;
}
.stage.dragging .viewer-img {
  transition: none;
}
.empty {
  color: #c5cad3;
  font-size: 14px;
}
.nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.85);
}
.nav-left { left: 14px; }
.nav-right { right: 14px; }

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 4px;
}
.counter {
  font-size: 13px;
  color: #4e5969;
  font-family: 'Consolas', 'Monaco', monospace;
}
.tools {
  display: flex;
  align-items: center;
  gap: 6px;
}
.pan-hint {
  margin-left: 4px;
  font-size: 12px;
  color: #86909c;
}

.thumb-strip {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 4px 0;
}
.strip-cell {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  border-radius: 6px;
  overflow: hidden;
  border: 2px solid transparent;
  cursor: pointer;
  background: #f5f6fa;
}
.strip-cell.active {
  border-color: #1677ff;
}
.strip-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
</style>
