<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  saving: boolean
  defaultNote: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'save', note: string): void
  (e: 'submit', note: string): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const note = ref(props.defaultNote || '')

watch(
  () => props.visible,
  (v) => {
    if (v) note.value = props.defaultNote || ''
  }
)

const close = () => {
  dialogVisible.value = false
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="保存阅片标注"
    width="520"
    :close-on-click-modal="false"
    align-center
  >
    <el-form label-width="80px">
      <el-form-item label="阅片备注">
        <el-input
          v-model="note"
          type="textarea"
          :rows="4"
          placeholder="例如：左眼黄斑区可见点状出血，建议复查"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="提示">
        <span class="muted">
          保存：仅存为草稿（DRAFT），可随时回到此页继续修改。
          <br />
          提交：标注集合状态变为 SUBMITTED，等待教师审核后不可再编辑。
        </span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button :loading="saving" @click="emit('save', note)">保存草稿</el-button>
      <el-button type="primary" :loading="saving" @click="emit('submit', note)">
        提交阅片
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.muted {
  color: #86909c;
  font-size: 12px;
  line-height: 1.6;
}
</style>
