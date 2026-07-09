<script setup lang="ts">
/**
 * 机构申请对话框
 * - 通过 v-model:visible 控制显隐
 * - 提交成功后 emit('submitted')，由父组件刷新「我的申请」状态
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { OrganizationApi } from '@/api'

type Org = OrganizationApi.Organization

const props = defineProps<{
  visible: boolean
}>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'submitted'): void
}>()

const innerVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const orgs = ref<Org[]>([])
const orgLoading = ref(false)
const selectedOrgId = ref<number | undefined>(undefined)
const reason = ref('')
const submitting = ref(false)

const fetchOrgs = async () => {
  orgLoading.value = true
  try {
    const list = await OrganizationApi.listOrgs()
    orgs.value = Array.isArray(list) ? list : []
  } catch {
    orgs.value = []
  } finally {
    orgLoading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      selectedOrgId.value = undefined
      reason.value = ''
      fetchOrgs()
    }
  },
)

const onSubmit = async () => {
  if (!selectedOrgId.value) {
    ElMessage.warning('请选择目标机构')
    return
  }
  submitting.value = true
  try {
    await OrganizationApi.applyOrg({
      organizationId: selectedOrgId.value,
      reason: reason.value.trim(),
    })
    emit('submitted')
    innerVisible.value = false
  } catch {
    /* 已弹错误 */
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="innerVisible"
    title="申请加入机构"
    width="520"
    :close-on-click-modal="false"
    align-center
  >
    <el-form label-width="84px" label-position="left">
      <el-form-item label="目标机构" required>
        <el-select
          v-model="selectedOrgId"
          placeholder="请选择要加入的机构"
          filterable
          style="width: 100%"
          :loading="orgLoading"
        >
          <el-option
            v-for="o in orgs"
            :key="o.id"
            :label="o.name"
            :value="o.id"
          >
            <span style="float: left">{{ o.name }}</span>
            <span v-if="o.category" style="float: right; color: #86909c; font-size: 12px">
              {{ o.category }}
            </span>
          </el-option>
          <template #empty>
            <div style="padding: 12px; color: #c9cdd4; text-align: center; font-size: 13px">
              暂无可选机构，请联系管理员开通
            </div>
          </template>
        </el-select>
      </el-form-item>
      <el-form-item label="申请理由">
        <el-input
          v-model="reason"
          type="textarea"
          :rows="4"
          maxlength="500"
          show-word-limit
          placeholder="可填写期望加入该机构的原因（选填）"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="innerVisible = false">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!selectedOrgId"
        @click="onSubmit"
      >
        提交申请
      </el-button>
    </template>
  </el-dialog>
</template>
