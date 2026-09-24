<script setup lang="ts">
import { PASS_PRESETS, REVISE_PRESETS } from '../review-presets'

withDefaults(
  defineProps<{
    disabled?: boolean
    tone?: 'dark' | 'light'
  }>(),
  { disabled: false, tone: 'light' }
)

const emit = defineEmits<{
  (e: 'pick', phrase: string): void
}>()

const pick = (phrase: string, disabled: boolean) => {
  if (disabled) return
  emit('pick', phrase)
}
</script>

<template>
  <div class="preset-box" :class="tone">
    <div class="preset-row">
      <span class="preset-kind">肯定</span>
      <el-tag
        v-for="phrase in PASS_PRESETS"
        :key="phrase"
        size="small"
        type="success"
        effect="plain"
        class="preset-chip"
        :class="{ 'is-off': disabled }"
        @click="pick(phrase, disabled)"
      >
        {{ phrase }}
      </el-tag>
    </div>
    <div class="preset-row">
      <span class="preset-kind">订正</span>
      <el-tag
        v-for="phrase in REVISE_PRESETS"
        :key="phrase"
        size="small"
        type="warning"
        effect="plain"
        class="preset-chip"
        :class="{ 'is-off': disabled }"
        @click="pick(phrase, disabled)"
      >
        {{ phrase }}
      </el-tag>
    </div>
  </div>
</template>

<style scoped>
.preset-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.preset-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.preset-kind {
  flex-shrink: 0;
  font-size: 12px;
  line-height: 20px;
}
.preset-box.dark .preset-kind {
  color: #d5dae3;
}
.preset-box.light .preset-kind {
  color: #86909c;
}
.preset-chip {
  cursor: pointer;
}
.preset-chip.is-off {
  cursor: not-allowed;
  opacity: 0.55;
}
</style>
