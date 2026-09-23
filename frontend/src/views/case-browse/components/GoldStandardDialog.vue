<script setup lang="ts">
/**
 * 完善 / 修订金标准
 * 保存草稿 → 仍未发布，学员不可见
 * 发布并加入实训 → is_published + is_train_case
 */
import { computed, reactive, ref, watch } from 'vue'
import { EditPen } from '@element-plus/icons-vue'
import { CaseBrowseApi } from '@/api'
import {
  TEACHING_OUTLINE,
  emptyTeachingSections,
  parseTeachingPoints,
  serializeTeachingPoints
} from '@/utils/teaching-outline'

type Detail = CaseBrowseApi.CaseBrowseDetail

const LESION_OPTIONS = [
  { label: '微动脉瘤 MA', value: 'MA' },
  { label: '出血 HE', value: 'HE' },
  { label: '硬性渗出 EX', value: 'EX' },
  { label: '软性渗出 SE', value: 'SE' }
]

const DR_OPTIONS = [
  { label: '不适用（非 DR 病种）', value: '' },
  { label: '0 级 无 DR', value: '0' },
  { label: '1 级 轻度 NPDR', value: '1' },
  { label: '2 级 中度 NPDR', value: '2' },
  { label: '3 级 重度 NPDR', value: '3' },
  { label: '4 级 PDR（增殖性）', value: '4' }
]

const props = defineProps<{
  visible: boolean
  data: Detail | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved', detail: Detail, published: boolean): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const form = reactive({
  goldDrGrade: '' as string,
  goldDiagnosis: '',
  sections: emptyTeachingSections(),
  passScore: 60,
  lesionTypes: [] as string[]
})
const legacyPoints = ref('')

const saving = ref(false)
const publishing = ref(false)

const hydrate = (d: Detail | null) => {
  form.goldDrGrade = d?.goldDrGrade ?? (d?.drLevel != null ? String(d.drLevel) : '')
  form.goldDiagnosis = d?.goldDiagnosis || ''
  const parsed = parseTeachingPoints(d?.teachingPoints || '')
  form.sections = { ...emptyTeachingSections(), ...parsed.sections }
  legacyPoints.value = parsed.legacy
  form.passScore = d?.passScore ?? 60
  form.lesionTypes = (d?.goldLesions || [])
    .map((x) => String(x?.type || x?.label || '').trim())
    .filter(Boolean)
}

watch(
  () => props.visible,
  (open) => {
    if (open) hydrate(props.data)
  }
)

const buildLesions = () => {
  const prev = new Map(
    (props.data?.goldLesions || []).map((x) => [String(x?.type || ''), x])
  )
  return form.lesionTypes.map((t) => prev.get(t) || { type: t })
}

const payload = (): CaseBrowseApi.GoldStandardUpdate => ({
  goldDrGrade: form.goldDrGrade,
  goldDiagnosis: form.goldDiagnosis.trim(),
  teachingPoints: serializeTeachingPoints(form.sections) || legacyPoints.value.trim(),
  passScore: form.passScore,
  goldLesions: buildLesions()
})

const submit = async (publish: boolean) => {
  if (!props.data?.id) return
  if (publish && !form.goldDiagnosis.trim()) {
    return
  }
  const flag = publish ? publishing : saving
  flag.value = true
  try {
    const detail = await CaseBrowseApi.updateGoldStandard(props.data.id, {
      ...payload(),
      publish
    })
    emit('saved', detail, publish)
    dialogVisible.value = false
  } catch {
    /* 拦截器已弹错 */
  } finally {
    flag.value = false
  }
}

const isDraft = computed(() => !props.data?.isPublished)
const title = computed(() =>
  isDraft.value ? '完善金标准' : '修订金标准'
)
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="title"
    width="760"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div v-if="data" class="gold-head">
      <span class="case-no">{{ data.caseNo }}</span>
      <span class="case-title">{{ data.title || '—' }}</span>
      <el-tag v-if="isDraft" type="warning" size="small" effect="plain">草稿 · 未发布</el-tag>
      <el-tag v-else-if="data.isTrainCase" type="success" size="small" effect="dark">已加入实训</el-tag>
      <el-tag v-else type="success" size="small" effect="plain">已发布</el-tag>
    </div>

    <el-form label-width="132px" class="gold-form">
      <el-form-item label="金标准分级">
        <el-select v-model="form.goldDrGrade" style="width: 100%">
          <el-option
            v-for="opt in DR_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="金标准诊断" required>
        <el-input
          v-model="form.goldDiagnosis"
          type="textarea"
          :rows="3"
          maxlength="500"
          show-word-limit
          placeholder="学员提交后对照的诊断结论，例如：中度 NPDR，可见微动脉瘤与点状出血"
        />
      </el-form-item>
      <el-form-item label="教学要点">
        <p class="outline-tip">按固定提纲填写。没写的项不会保存，学员端也只看到已填的项。</p>
        <p v-if="legacyPoints" class="legacy">
          这条还是自由文本。填进下面各项并保存后，就按提纲存放。原文：{{ legacyPoints }}
        </p>
      </el-form-item>
      <el-form-item v-for="item in TEACHING_OUTLINE" :key="item.key" :label="item.label">
        <el-input
          v-model="form.sections[item.key]"
          type="textarea"
          :rows="2"
          maxlength="400"
          show-word-limit
          :placeholder="item.placeholder"
        />
      </el-form-item>
      <el-form-item label="典型病变">
        <el-checkbox-group v-model="form.lesionTypes">
          <el-checkbox v-for="opt in LESION_OPTIONS" :key="opt.value" :label="opt.value">
            {{ opt.label }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="及格分">
        <el-input-number v-model="form.passScore" :min="0" :max="100" :step="5" />
        <span class="muted">百分制，学员自主练习按此线判定是否通过</span>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="isDraft"
      type="info"
      :closable="false"
      show-icon
      title="保存草稿后学员仍不可见；「发布并加入实训」后，学员抽题与阅片才能看到该病例。"
    />

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button :loading="saving" :disabled="publishing" @click="submit(false)">
        {{ isDraft ? '保存草稿' : '保存修订' }}
      </el-button>
      <el-button
        type="primary"
        :icon="EditPen"
        :loading="publishing"
        :disabled="saving || !form.goldDiagnosis.trim()"
        @click="submit(true)"
      >
        发布并加入实训
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.gold-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.case-no {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #1677ff;
  font-weight: 700;
}
.case-title {
  font-weight: 600;
  color: #1d2129;
}
.gold-form {
  margin-bottom: 12px;
}
.muted {
  margin-left: 10px;
  color: #86909c;
  font-size: 12px;
}
.outline-tip,
.legacy {
  margin: 0;
  line-height: 1.6;
  font-size: 13px;
  color: #4e5969;
}
.legacy {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fff7e8;
  color: #1d2129;
}
</style>
