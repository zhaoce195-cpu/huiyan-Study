<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ExamApi, PracticeApi } from '@/api'
import type { ExamCaseOption, ExamPaper } from '@/api/exam'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const papers = ref<ExamPaper[]>([])
const cases = ref<ExamCaseOption[]>([])
const dialog = ref(false)
const saving = ref(false)

const form = reactive({
  title: '',
  durationMinutes: 60,
  passScore: 60,
  allowBack: false,
  pickMode: 'SELECTED' as 'SELECTED' | 'DRAW',
  category: '',
  difficulty: '',
  caseIds: [] as number[],
  questionCount: 3
})

const load = async () => {
  loading.value = true
  try {
    papers.value = (await ExamApi.listExams()) || []
  } finally {
    loading.value = false
  }
}

const participantText = (row: ExamPaper) =>
  (row.participants || []).map((item) => `${item.name}（${item.state}）`).join('、')

const openCreate = async () => {
  form.title = ''
  form.durationMinutes = 60
  form.passScore = 60
  form.allowBack = false
  form.pickMode = 'SELECTED'
  form.category = ''
  form.difficulty = ''
  form.caseIds = []
  form.questionCount = 3
  dialog.value = true
  if (!cases.value.length) {
    cases.value = (await ExamApi.caseOptions()) || []
  }
}

const publish = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请填写考试名称')
    return
  }
  if (form.pickMode === 'SELECTED' && !form.caseIds.length) {
    ElMessage.warning('请至少选择一份病例')
    return
  }
  saving.value = true
  try {
    await ExamApi.createExam({
      title: form.title.trim(),
      durationMinutes: form.durationMinutes,
      passScore: form.passScore,
      allowBack: form.allowBack,
      pickMode: form.pickMode,
      category: form.category,
      difficulty: form.difficulty,
      caseIds: form.caseIds,
      questionCount: form.questionCount
    })
    dialog.value = false
    await load()
  } finally {
    saving.value = false
  }
}

const collect = async (row: ExamPaper) => {
  try {
    await ElMessageBox.confirm(
      '收卷后未交的题目按已保存内容计分，没写的按未答。收卷后才公布答案，并可以导出成绩。',
      `收卷「${row.title}」`,
      { type: 'warning', confirmButtonText: '收卷' }
    )
  } catch {
    return
  }
  await ExamApi.collectExam(row.id)
  await load()
}

const download = (row: ExamPaper) => {
  ExamApi.downloadGrades(row.id, `${row.title}-成绩.csv`)
}

const remove = async (row: ExamPaper) => {
  try {
    await ElMessageBox.confirm(`删除「${row.title}」？还没有学员进入。`, '删除考试', { type: 'warning' })
  } catch {
    return
  }
  await ExamApi.removeExam(row.id)
  await load()
}

onMounted(load)
</script>

<template>
  <div class="exam-page">
    <div class="toolbar">
      <div>
        <h2>正式考试</h2>
        <p>指定病例，或按病种和难度抽一套题。全班同一套。收卷后统一导出成绩。</p>
      </div>
      <el-button type="primary" @click="openCreate">发布考试</el-button>
    </div>

    <el-table v-loading="loading" :data="papers" border stripe>
      <el-table-column prop="title" label="考试" min-width="140" />
      <el-table-column label="发起人" width="110">
        <template #default="{ row }">{{ row.publisherName || '—' }}</template>
      </el-table-column>
      <el-table-column label="题目" min-width="180">
        <template #default="{ row }">
          {{ row.questionCount }} 题
          <span v-if="row.caseNos?.length" class="muted">{{ row.caseNos.join('、') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="90">
        <template #default="{ row }">{{ row.durationMinutes }} 分钟</template>
      </el-table-column>
      <el-table-column label="合格线" width="80">
        <template #default="{ row }">{{ row.passScore }}</template>
      </el-table-column>
      <el-table-column label="返回上一题" width="110">
        <template #default="{ row }">{{ row.allowBack ? '允许' : '不允许' }}</template>
      </el-table-column>
      <el-table-column label="交卷" width="110">
        <template #default="{ row }">{{ row.handedCount }} / {{ row.enteredCount }} 人</template>
      </el-table-column>
      <el-table-column label="作答学员" min-width="180">
        <template #default="{ row }">
          {{ participantText(row) || '还没有学员进入' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'CLOSED' ? 'info' : 'success'">
            {{ row.status === 'CLOSED' ? '已收卷' : '进行中' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'OPEN'" size="small" type="primary" @click="collect(row)">
            收卷
          </el-button>
          <el-button v-else size="small" @click="download(row)">导出成绩</el-button>
          <el-button
            v-if="row.status === 'OPEN' && !row.enteredCount"
            size="small"
            type="danger"
            plain
            @click="remove(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="发布考试" width="640px">
      <el-form label-width="120px">
        <el-form-item label="考试名称">
          <el-input v-model="form.title" maxlength="64" placeholder="例如：眼底病月考" />
        </el-form-item>
        <el-form-item label="发起人">
          <el-input :model-value="userStore.displayName" disabled />
        </el-form-item>
        <el-form-item label="考试时间">
          <el-input-number v-model="form.durationMinutes" :min="1" :max="240" />
          <span class="unit">分钟，从学员进入时起算</span>
        </el-form-item>
        <el-form-item label="合格分数">
          <el-input-number v-model="form.passScore" :min="0" :max="100" />
          <span class="unit">整卷平均分</span>
        </el-form-item>
        <el-form-item label="返回上一题">
          <el-switch v-model="form.allowBack" active-text="允许" inactive-text="不允许" />
        </el-form-item>
        <el-form-item label="组卷方式">
          <el-radio-group v-model="form.pickMode">
            <el-radio value="SELECTED">指定病例</el-radio>
            <el-radio value="DRAW">按病种、难度抽题</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.pickMode === 'SELECTED'" label="病例">
          <el-select
            v-model="form.caseIds"
            multiple
            filterable
            placeholder="按顺序选择，全班同一套"
            style="width: 100%"
          >
            <el-option
              v-for="item in cases"
              :key="item.id"
              :label="`${item.caseNo} ${item.title} · ${item.categoryText} · ${item.difficultyText}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <template v-else>
          <el-form-item label="病种">
            <el-select v-model="form.category" clearable placeholder="全部病种" style="width: 100%">
              <el-option
                v-for="item in PracticeApi.CATEGORY_FILTERS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="难度">
            <el-select v-model="form.difficulty" clearable placeholder="全部难度" style="width: 100%">
              <el-option
                v-for="item in PracticeApi.DIFFICULTY_FILTERS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="题数">
            <el-input-number v-model="form.questionCount" :min="1" :max="20" />
            <span class="unit">抽出后全班用同一套</span>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="publish">发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.exam-page {
  min-height: 100%;
  padding: 20px 24px 40px;
  background: #f5f7fa;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
.toolbar h2 {
  margin: 0 0 6px;
  font-size: 18px;
  color: #1d2129;
}
.toolbar p,
.muted,
.unit {
  color: #86909c;
  font-size: 13px;
}
.toolbar p {
  margin: 0;
}
.muted {
  margin-left: 8px;
}
.unit {
  margin-left: 8px;
}
</style>
