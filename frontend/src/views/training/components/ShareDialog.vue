<script setup lang="ts">
/**
 * 病例分享 / 入库提交对话框
 * - share_type='TEMPORARY'：临时分享（选范围 + 有效期）
 * - share_type='PERMANENT'：入库申请（标题 + 描述）
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
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
const router = useRouter()
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

type ScopeName = 'ALL' | 'YEAR' | 'BATCH' | 'GROUP' | 'PEOPLE'

const emptyTargets = (): TeachingApi.ShareTargets => ({
  years: [],
  batches: [],
  groups: [],
  students: [],
})

const form = ref({
  shareScope: 'ALL' as ScopeName,
  picks: [] as string[],
  expireHours: 24,
  hideAnswers: true,
  title: '',
  description: '',
})

const targets = ref<TeachingApi.ShareTargets>(emptyTargets())
const submitting = ref(false)

const groupField = computed(() => {
  if (form.value.shareScope === 'BATCH') return 'rotationBatch' as const
  if (form.value.shareScope === 'GROUP') return 'mentorGroup' as const
  return 'studyYear' as const
})

const groupNames = computed(() => {
  if (form.value.shareScope === 'BATCH') return targets.value.batches
  if (form.value.shareScope === 'GROUP') return targets.value.groups
  return targets.value.years
})

const optionGroups = computed(() =>
  groupNames.value.map((value) => ({
    value,
    label: value,
    members: targets.value.students.filter((item) => item[groupField.value] === value),
  }))
)

const scopePlaceholder = computed(() => {
  if (form.value.shareScope === 'BATCH') return '选择轮转批次或其中的学员'
  if (form.value.shareScope === 'GROUP') return '选择带教组或其中的学员'
  return '选择年级或其中的学员'
})

const resolvePicks = () => {
  const allValues = form.value.picks.filter((item) => item.startsWith('all:')).map((item) => item.slice(4))
  const userIds = form.value.picks
    .filter((item) => item.startsWith('user:'))
    .map((item) => Number(item.slice(5)))
    .filter((item) => Number.isFinite(item))
  if (allValues.length === 1 && userIds.length === 0) {
    return {
      shareScope: form.value.shareScope,
      scopeValue: allValues[0],
      audienceIds: [] as number[],
    }
  }
  const ids = new Set(userIds)
  for (const value of allValues) {
    for (const student of targets.value.students) {
      if (student[groupField.value] === value) ids.add(student.id)
    }
  }
  return {
    shareScope: 'PEOPLE' as const,
    scopeValue: '',
    audienceIds: [...ids],
  }
}

const loadTargets = () => {
  TeachingApi.getShareTargets()
    .then((data) => {
      targets.value = {
        years: data?.years || [],
        batches: data?.batches || [],
        groups: data?.groups || [],
        students: data?.students || [],
      }
    })
    .catch(() => {
      targets.value = emptyTargets()
    })
}

watch(
  () => props.visible,
  (v) => {
    if (!v) return
    form.value = {
      shareScope: 'ALL',
      picks: [],
      expireHours: 24,
      hideAnswers: true,
      title: props.caseTitle || '',
      description: '',
    }
    loadTargets()
  },
  { immediate: true }
)

const onSubmit = async () => {
  submitting.value = true
  try {
    if (isTemporary.value) {
      if (form.value.shareScope !== 'ALL' && form.value.picks.length === 0) {
        ElMessage.warning(scopePlaceholder.value)
        return
      }
      const chosen = form.value.shareScope === 'ALL'
        ? { shareScope: 'ALL' as const, scopeValue: '', audienceIds: [] as number[] }
        : resolvePicks()
      if (chosen.shareScope === 'PEOPLE' && chosen.audienceIds.length === 0) {
        ElMessage.warning('请选择要分享的学员')
        return
      }
      await TeachingApi.createShare({
        sourceType: props.sourceType,
        sourceCaseId: props.sourceCaseId,
        shareScope: chosen.shareScope,
        scopeValue: chosen.scopeValue,
        audienceIds: chosen.audienceIds,
        expireHours: form.value.expireHours,
        hideAnswers: form.value.hideAnswers,
      })
      ElMessage.success(form.value.hideAnswers ? '已分享。学员先看不到金标准，讨论结束后再公布' : '已分享，学员现在就能看到金标准')
    } else {
      const saved = await TeachingApi.submitForReview({
        sourceType: props.sourceType,
        sourceCaseId: props.sourceCaseId,
        title: form.value.title.trim(),
        description: form.value.description.trim(),
      })
      if (saved?.status === 'APPROVED') {
        ElMessage.success('已转为教学病例，无需再审核')
        router.push({ path: '/training/admin', query: { tab: 'teaching-review', notice: 'approved' } })
      } else {
        ElMessage.success('已提交，等待管理员审核')
      }
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
    width="640"
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
        <el-form-item label="分享对象">
          <div class="scope-row">
            <el-select
              v-model="form.shareScope"
              style="width: 160px"
              @change="form.picks = []"
            >
              <el-option label="全体学员" value="ALL" />
              <el-option label="指定年级" value="YEAR" />
              <el-option label="指定轮转批次" value="BATCH" />
              <el-option label="指定带教组" value="GROUP" />
            </el-select>
            <el-select
              v-if="form.shareScope !== 'ALL'"
              v-model="form.picks"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              :placeholder="optionGroups.length ? scopePlaceholder : '还没有可选项'"
              style="width: 360px"
            >
              <el-option-group
                v-for="group in optionGroups"
                :key="group.value"
                :label="group.label"
              >
                <el-option
                  :label="`全部 ${group.members.length} 人`"
                  :value="`all:${group.value}`"
                />
                <el-option
                  v-for="item in group.members"
                  :key="item.id"
                  :label="item.name"
                  :value="`user:${item.id}`"
                />
              </el-option-group>
            </el-select>
          </div>
          <div class="muted small">
            每一组里都可以选「全部」，发给这一组的所有人；也可以只勾其中几个人。
          </div>
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
.scope-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.muted { color: #86909c; font-size: 12px; }
.muted.small { font-size: 12px; line-height: 1.7; }
</style>
