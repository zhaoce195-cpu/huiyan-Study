<script setup lang="ts">
/**
 * 病例分享 / 入库提交对话框
 * - share_type='TEMPORARY'：临时分享（选范围 + 有效期）
 * - share_type='PERMANENT'：入库申请（标题 + 描述）
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { TeachingApi } from '@/api'

type ShareType = TeachingApi.ShareType
type ShareSource = TeachingApi.ShareSource

const props = defineProps<{
  visible: boolean
  shareType: ShareType
  sourceType: ShareSource
  sourceCaseId: number
  caseTitle?: string
}>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'submitted'): void
}>()

const innerVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const isTemporary = computed(() => props.shareType === 'TEMPORARY')
const dialogTitle = computed(() =>
  isTemporary.value ? '分享病例至学员实训' : '提交病例入教学库'
)

const form = ref({
  shareScope: 'ALL',
  expireHours: 24,
  hideAnswers: true,
  title: '',
  description: '',
})

const submitting = ref(false)

watch(
  () => props.visible,
  (v) => {
    if (v) {
      form.value = {
        shareScope: 'ALL',
        expireHours: 24,
        hideAnswers: true,
        title: props.caseTitle || '',
        description: '',
      }
    }
  }
)

const onSubmit = async () => {
  submitting.value = true
  try {
    if (isTemporary.value) {
      await TeachingApi.createShare({
        sourceType: props.sourceType,
        sourceCaseId: props.sourceCaseId,
        shareScope: form.value.shareScope,
        expireHours: form.value.expireHours,
        hideAnswers: form.value.hideAnswers,
      })
      ElMessage.success(form.value.hideAnswers ? '已分享。学员先看不到金标准，讨论结束后再公布' : '已分享，学员现在就能看到金标准')
    } else {
      await TeachingApi.submitForReview({
        sourceType: props.sourceType,
        sourceCaseId: props.sourceCaseId,
        title: form.value.title.trim(),
        description: form.value.description.trim(),
      })
      ElMessage.success('已提交，等待管理员审核')
    }
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
    :title="dialogTitle"
    width="520"
    :close-on-click-modal="false"
    align-center
  >
    <!-- 病例信息 -->
    <div class="case-hint">
      <span class="muted">来源：</span>
      <span>{{ sourceType === 'SCREENING' ? '筛查病例' : '实训病例' }} #{{ sourceCaseId }}</span>
      <span v-if="caseTitle" class="title-text">{{ caseTitle }}</span>
    </div>

    <el-form label-width="92px" label-position="left" style="margin-top: 16px">
      <template v-if="isTemporary">
        <el-form-item label="分享范围">
          <el-radio-group v-model="form.shareScope">
            <el-radio-button value="ALL">全体学员</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="有效期">
          <el-input-number
            v-model="form.expireHours"
            :min="1"
            :max="720"
            controls-position="right"
            style="width: 160px"
          />
          <span class="muted" style="margin-left: 8px">小时</span>
        </el-form-item>
        <el-form-item label="金标准">
          <el-checkbox v-model="form.hideAnswers">先隐藏，让学员独立判断</el-checkbox>
          <div class="muted small">讨论结束后，在「我的教学分享」里点「公布金标准」。</div>
        </el-form-item>
        <el-form-item label="">
          <div class="muted small">
            分享后会自动脱敏（隐藏患者姓名、手机号等隐私信息），过期后学员端自动失效。可随时手动收回。
          </div>
        </el-form-item>
      </template>

      <template v-else>
        <el-form-item label="教学标题">
          <el-input
            v-model="form.title"
            placeholder="可填写更适合教学展示的标题"
            maxlength="128"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="教学描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="病例的教学价值、关键学习点等"
          />
        </el-form-item>
        <el-form-item label="">
          <div class="muted small">
            提交后管理员审核，通过后将永久入公共教学病例库供所有学员实训使用。审核结果会通过【我的消息】通知您。
          </div>
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="innerVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">
        {{ isTemporary ? '确认分享' : '提交审核' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.case-hint {
  background: #f5f9ff;
  border: 1px solid #e6effe;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  color: #1d2129;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.case-hint .title-text {
  font-weight: 600;
  margin-left: 6px;
}
.muted { color: #86909c; font-size: 12px; }
.muted.small { font-size: 12px; line-height: 1.7; }
</style>
