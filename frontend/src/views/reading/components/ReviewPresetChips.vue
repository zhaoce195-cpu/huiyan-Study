<script setup lang="ts">
import { PASS_PRESETS, REVISE_PRESETS } from '../review-presets'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    tone?: 'dark' | 'light'
    customList?: string[]
  }>(),
  { disabled: false, tone: 'light', customList: () => [] }
)

const emit = defineEmits<{
  (e: 'pick', phrase: string): void
  (e: 'remove-custom', index: number): void
}>()

const pick = (phrase: string, disabled: boolean) => {
  if (disabled) return
  emit('pick', phrase)
}

const removeCustom = (index: number) => {
  if (props.disabled) return
  emit('remove-custom', index)
}
</script>

<template>
  <div class="preset-box" :class="tone">
    <!-- 肯定预设 -->
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
    <!-- 订正预设 -->
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
    <!-- 教师个人常用自定义预设 -->
    <div v-if="customList && customList.length" class="preset-row">
      <span class="preset-kind is-custom">常用</span>
      <el-tag
        v-for="(phrase, idx) in customList"
        :key="phrase"
        size="small"
        type="info"
        effect="plain"
        closable
        class="preset-chip custom-tag"
        :class="{ 'is-off': disabled }"
        @click="pick(phrase, disabled)"
        @close="removeCustom(idx)"
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
  width: 28px;
}
.preset-kind.is-custom {
  color: #409eff;
}
.preset-box.dark .preset-kind {
  color: #9aa1af;
}
.preset-box.light .preset-kind {
  color: #86909c;
}
.preset-chip {
  cursor: pointer;
  user-select: none;
  transition: all 0.15s ease;
}
.preset-chip:hover {
  transform: translateY(-1px);
}
.preset-chip.is-off {
  cursor: not-allowed;
  opacity: 0.55;
}
.custom-tag {
  background: rgba(64, 158, 255, 0.1) !important;
  border-color: rgba(64, 158, 255, 0.3) !important;
  color: #79bbff !important;
}
</style>
