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

watch(
  () => props.visible,
  (v) => {
    if (v) {
      currentIndex.value = props.initialIndex || 0
      scale.value = 1
    }
  }
)

const currentImage = computed(() => props.images[currentIndex.value] || '')

const prev = () => {
  if (currentIndex.value > 0) {
    currentIndex.value -= 1
    scale.value = 1
  }
}
const next = () => {
  if (currentIndex.value < props.images.length - 1) {
    currentIndex.value += 1
    scale.value = 1
  }
}

const zoomIn = () => {
  scale.value = Math.min(4, scale.value + 0.25)
}
const zoomOut = () => {
  scale.value = Math.max(0.25, scale.value - 0.25)
}
const resetZoom = () => {
  scale.value = 1
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
      <div class="stage">
        <img
          v-if="currentImage"
          :src="currentImage"
          class="viewer-img"
          :style="{ transform: `scale(${scale})` }"
          @dblclick="resetZoom"
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
          <el-button size="small" @click="resetZoom">{{ Math.round(scale * 100) }}%</el-button>
          <el-button :icon="ZoomIn" size="small" @click="zoomIn">放大</el-button>
          <el-button :icon="RefreshLeft" size="small" @click="resetZoom">重置</el-button>
        </div>
      </div>

      <!-- 缩略图条 -->
      <div v-if="images.length > 1" class="thumb-strip">
        <div
          v-for="(img, i) in images"
          :key="i"
          class="strip-cell"
          :class="{ active: i === currentIndex }"
          @click="currentIndex = i; scale = 1"
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
}
.viewer-img {
  max-width: 100%;
  max-height: 100%;
  transition: transform 0.2s;
  user-select: none;
  pointer-events: none;
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
  gap: 6px;
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
