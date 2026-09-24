<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { PracticeApi, ReadingApi, RotationApi } from '@/api'
import type { GroupSummary, RotationTask, StudentHome, StudentProgress, TeacherHome } from '@/api/rotation'
import type { PracticeRecord, PracticeStats } from '@/api/practice'
import { useUserStore } from '@/stores/user'
import { actorLabel } from '@/utils/actor'
import ReadingQualityPanel from '@/views/reading/components/ReadingQualityPanel.vue'

const router = useRouter()
const userStore = useUserStore()
const isTeacher = computed(() => userStore.isAdmin || userStore.isDoctor)

const loading = ref(false)
const student = ref<StudentHome | null>(null)
const teacher = ref<TeacherHome | null>(null)

const caseId = ref<number | undefined>()
const caseTier = ref<'REQUIRED' | 'EXTENSION'>('REQUIRED')
const caseScope = ref<'ALL' | 'YEAR' | 'GROUP'>('ALL')
const caseScopeValue = ref('')
const resourceId = ref<number | undefined>()
const knowledgeTitle = ref('')
const caseOptions = ref<{ id: number; label: string }[]>([])
const resourceOptions = ref<{ id: number; label: string }[]>([])
const dueDraft = ref('')
const passDraft = ref(60)
const titleDraft = ref('')
const yearFilter = ref('')
const batchFilter = ref('')
const mentorFilter = ref('')
const activeTeacherTab = ref('monitor')
const pendingReviewCount = ref(0)
const groupDraft = ref({ studyYear: '', rotationBatch: '', mentorGroup: '' })
const savingGroup = ref(false)

const load = async () => {
  loading.value = true
  try {
    const data = await RotationApi.getHome()
    if (data.role === 'teacher') {
      teacher.value = data
      student.value = null
      titleDraft.value = data.rotation?.title || ''
      dueDraft.value = data.rotation?.dueOn || ''
      passDraft.value = data.rotation?.passScore ?? 60
    } else {
      student.value = data
      teacher.value = null
    }
  } finally {
    loading.value = false
  }
}

const loadOptions = async () => {
  if (!isTeacher.value) return
  const data = await RotationApi.getOptions()
  caseOptions.value = data.cases || []
  resourceOptions.value = data.resources || []
}

const loadPendingReviews = async () => {
  if (!isTeacher.value) return
  try {
    const page = await ReadingApi.getReadingList({
      status: 'SUBMITTED',
      page: 1,
      pageSize: 1
    })
    pendingReviewCount.value = Number(page?.total) || 0
  } catch {
    pendingReviewCount.value = 0
  }
}

onMounted(async () => {
  await load()
  await Promise.all([loadOptions(), loadPendingReviews()])
})

const startCase = async (task: RotationTask) => {
  if (!task.caseId) return
  const rec = await PracticeApi.startPractice({ caseId: task.caseId, mode: 'SELECTED' })
  router.push({
    path: '/practice/workstation',
    query: { sessionId: String(rec.id), caseId: String(task.caseId), from: 'rotation' }
  })
}

const markLearned = async (task: RotationTask) => {
  student.value = await RotationApi.markLearned(task.id)
  ElMessage.success('已记入本轮转进度')
}

const openKnowledge = (task: RotationTask) => {
  if (task.resourceId) {
    router.push({
      path: '/training/learning',
      query: { resourceId: String(task.resourceId), taskId: String(task.id) }
    })
    return
  }
  router.push('/training/learning')
}

const openAssigned = (task: RotationTask) => {
  if (task.kind === 'CASE' && task.caseNo) {
    router.push({ path: '/training/cases', query: { keyword: task.caseNo } })
    return
  }
  if (task.resourceId) {
    router.push({ path: '/training/learning', query: { resourceId: String(task.resourceId) } })
  }
}

const taskTitle = (taskId: number) =>
  teacher.value?.tasks.find((item) => item.id === taskId)?.title || '任务'

const uniqueLabels = (values: string[]) => [...new Set(values.filter(Boolean))]

const yearOptions = computed(() => uniqueLabels((teacher.value?.students || []).map((row) => row.studyYear)))
const batchOptions = computed(() => uniqueLabels((teacher.value?.students || []).map((row) => row.rotationBatch)))
const mentorOptions = computed(() => uniqueLabels((teacher.value?.students || []).map((row) => row.mentorGroup)))

const matchGroup = (row: { studyYear: string; rotationBatch: string; mentorGroup: string }) => {
  if (yearFilter.value && row.studyYear !== yearFilter.value) return false
  if (batchFilter.value && row.rotationBatch !== batchFilter.value) return false
  if (mentorFilter.value && row.mentorGroup !== mentorFilter.value) return false
  return true
}

const filteredStudents = computed(() => (teacher.value?.students || []).filter(matchGroup))
const visibleGroups = computed(() => (teacher.value?.groups || []).filter(matchGroup))

const classSummary = computed(() => {
  const rows = teacher.value?.students || []
  const practice = rows.reduce((sum, row) => sum + (row.practiceCount || 0), 0)
  const cases = rows.reduce((sum, row) => sum + (row.completedCases || 0), 0)
  const seconds = rows.reduce((sum, row) => sum + (row.studySeconds || 0), 0)
  const scoreSum = rows.reduce((sum, row) => sum + (row.avgScore || 0) * (row.practiceCount || 0), 0)
  return {
    students: rows.length,
    practiced: rows.filter((row) => (row.practiceCount || 0) > 0).length,
    practice,
    cases,
    avg: practice ? scoreSum / practice : 0,
    seconds
  }
})

const weakText = (group: GroupSummary) =>
  group.weakLabels
    .map((item) => `${item.label} 漏诊 ${item.missed}、误诊 ${item.falsePositive}`)
    .join('；')

const drawerOpen = ref(false)
const focusStudent = ref<StudentProgress | null>(null)
const detailLoading = ref(false)
const studentStats = ref<PracticeStats | null>(null)
const studentRecords = ref<PracticeRecord[]>([])
const commentDraft = ref<Record<number, string>>({})
const savingCommentId = ref(0)

const finishedRecords = computed(() =>
  studentRecords.value
    .filter((row) => row.status === 'SUBMITTED' || row.status === 'REVIEWED')
    .slice()
    .sort((a, b) => (a.submittedAt || a.createdAt || '').localeCompare(b.submittedAt || b.createdAt || ''))
)

const retryChanges = computed(() => {
  const groups = new Map<number, PracticeRecord[]>()
  finishedRecords.value.forEach((row) => {
    const list = groups.get(row.caseId) || []
    list.push(row)
    groups.set(row.caseId, list)
  })
  return [...groups.values()]
    .filter((list) => list.length >= 2)
    .map((list) => {
      const first = list[0]
      const last = list[list.length - 1]
      const delta = Math.round((last.scoreTotal - first.scoreTotal) * 10) / 10
      return {
        caseNo: last.caseNo || first.caseNo,
        times: list.length,
        first: first.scoreTotal,
        last: last.scoreTotal,
        delta
      }
    })
})

const formatMinutes = (seconds: number) => {
  if (!seconds) return '0 分钟'
  if (seconds < 60) return '不足 1 分钟'
  return `${Math.round(seconds / 60)} 分钟`
}

const openStudent = async (row: StudentProgress) => {
  focusStudent.value = row
  groupDraft.value = {
    studyYear: row.studyYear === '未分组' ? '' : row.studyYear,
    rotationBatch: row.rotationBatch === '未分组' ? '' : row.rotationBatch,
    mentorGroup: row.mentorGroup === '未分组' ? '' : row.mentorGroup
  }
  drawerOpen.value = true
  detailLoading.value = true
  studentStats.value = null
  studentRecords.value = []
  commentDraft.value = {}
  try {
    const [stats, page] = await Promise.all([
      PracticeApi.getUserStats(row.userId),
      PracticeApi.getPracticeList({ userId: row.userId, page: 1, pageSize: 200 })
    ])
    studentStats.value = stats
    studentRecords.value = page?.list || []
    const drafts: Record<number, string> = {}
    studentRecords.value.forEach((item) => {
      drafts[item.id] = item.teacherComment || ''
    })
    commentDraft.value = drafts
  } finally {
    detailLoading.value = false
  }
}

const saveGroup = async () => {
  if (!focusStudent.value) return
  savingGroup.value = true
  try {
    const home = await RotationApi.setStudentGroup(focusStudent.value.userId, { ...groupDraft.value })
    teacher.value = home
    const latest = home.students.find((item) => item.userId === focusStudent.value?.userId)
    if (latest) focusStudent.value = latest
    ElMessage.success('分组已保存，完成情况和常见问题已按新组计算')
  } finally {
    savingGroup.value = false
  }
}

const saveComment = async (row: PracticeRecord) => {
  const text = (commentDraft.value[row.id] || '').trim()
  if (!text) {
    ElMessage.warning('请先写评语')
    return
  }
  savingCommentId.value = row.id
  try {
    const saved = await PracticeApi.reviewPractice(row.id, text)
    const index = studentRecords.value.findIndex((item) => item.id === row.id)
    if (index >= 0) studentRecords.value[index] = saved
    commentDraft.value[row.id] = saved.teacherComment || text
  } finally {
    savingCommentId.value = 0
  }
}

const saveRotation = async () => {
  teacher.value = await RotationApi.updateRotation({
    title: titleDraft.value,
    dueOn: dueDraft.value,
    passScore: passDraft.value
  })
  ElMessage.success('轮转要求已保存')
}

const assignTargets = computed(() =>
  (caseScope.value === 'YEAR' ? yearOptions.value : mentorOptions.value).filter((item) => item !== '未分组')
)

const addCase = async () => {
  if (!caseId.value) {
    ElMessage.warning('请选择病例')
    return
  }
  if (caseScope.value !== 'ALL' && !caseScopeValue.value) {
    ElMessage.warning(caseScope.value === 'YEAR' ? '请选择年级' : '请选择轮转组')
    return
  }
  teacher.value = await RotationApi.addTask({
    kind: 'CASE',
    caseId: caseId.value,
    passScore: passDraft.value,
    tier: caseTier.value,
    scope: caseScope.value,
    scopeValue: caseScope.value === 'ALL' ? '' : caseScopeValue.value
  })
  caseId.value = undefined
  ElMessage.success(caseTier.value === 'EXTENSION' ? '已标为拓展病例' : '已标为必做病例')
}

const moveTask = async (index: number, delta: number) => {
  const rows = [...(teacher.value?.tasks || [])]
  const next = index + delta
  if (next < 0 || next >= rows.length) return
  const [item] = rows.splice(index, 1)
  rows.splice(next, 0, item)
  teacher.value = await RotationApi.reorderTasks(rows.map((row) => row.id))
}

const arrangeBySpectrum = async () => {
  teacher.value = await RotationApi.arrangeTasks()
  ElMessage.success('已按从正常到重症排列，必做在前、拓展在后')
}

const addKnowledge = async () => {
  if (!resourceId.value && !knowledgeTitle.value.trim()) {
    ElMessage.warning('请选择资料或填写知识点')
    return
  }
  teacher.value = await RotationApi.addTask({
    kind: 'KNOWLEDGE',
    resourceId: resourceId.value,
    title: knowledgeTitle.value.trim()
  })
  resourceId.value = undefined
  knowledgeTitle.value = ''
  ElMessage.success('已加入本轮转')
}

const removeTask = async (task: RotationTask) => {
  await ElMessageBox.confirm(`撤下「${task.title}」？已有的练习成绩不会删除。`, '撤下必做', {
    type: 'warning'
  })
  teacher.value = await RotationApi.removeTask(task.id)
}

const statusType = (task: { status: string; overdue?: boolean; dueToday?: boolean }) => {
  if (task.status === 'DONE' || task.status === 'LEARNED') return 'success'
  if (task.overdue || task.status === 'SHORT') return 'danger'
  if (task.dueToday || task.status === 'DOING') return 'warning'
  return 'info'
}
</script>

<template>
  <div v-loading="loading" class="home-page">
    <template v-if="student">
      <header class="page-head">
        <div>
          <h2>今日学习任务</h2>
          <p>
            {{ student.studyYear }} · {{ student.rotationBatch }} · {{ student.mentorGroup }}。
            <template v-if="actorLabel(student.groupEditorName, student.groupEditorRole)">
              分组由 {{ actorLabel(student.groupEditorName, student.groupEditorRole) }}
              <template v-if="student.groupEditedAt">于 {{ student.groupEditedAt }}</template>
              填写。
            </template>
            {{ student.rotation?.title || '本轮转' }}。必做计入进度。拓展病例是老师另外推荐的，做完不改变必做进度。
          </p>
        </div>
      </header>

      <section v-if="student.rotation" class="stats">
        <article>
          <span>截止日期</span>
          <strong>{{ student.rotation.dueOn || '未设置' }}</strong>
        </article>
        <article>
          <span>合格要求</span>
          <strong>{{ student.rotation.passScore }} 分</strong>
        </article>
        <article>
          <span>完成进度</span>
          <strong>{{ student.rotation.done }} / {{ student.rotation.total }}</strong>
          <el-progress :percentage="student.rotation.progress" :stroke-width="8" />
        </article>
      </section>

      <section class="block">
        <h3>尚未完成</h3>
        <div v-if="!student.today.length" class="empty">
          {{
            student.tasks.some((item) => item.tier !== 'EXTENSION')
              ? '今日必做已完成。'
              : '老师还没有布置必做病例。'
          }}
        </div>
        <article v-for="task in student.today" :key="task.id" class="task">
          <div class="task-main">
            <div class="task-title">
              <el-tag size="small" :type="task.kind === 'CASE' ? 'primary' : 'success'" effect="plain">
                {{ task.kindText }}
              </el-tag>
              <strong>{{ task.title }}</strong>
              <el-tag v-if="task.overdue" size="small" type="danger">已逾期</el-tag>
              <el-tag v-else-if="task.dueToday" size="small" type="warning">今日到期</el-tag>
            </div>
            <p>{{ task.summary }}</p>
            <p class="meta">
              截止 {{ task.dueOn || '随轮转' }}
              <template v-if="task.kind === 'CASE'"> · 合格分 {{ task.passScore }}</template>
              <template v-if="task.score != null"> · 当前 {{ task.score }} 分</template>
              · {{ task.statusText }}
            </p>
          </div>
          <div class="task-actions">
            <el-button v-if="task.kind === 'CASE'" type="primary" @click="startCase(task)">学习这例</el-button>
            <template v-else>
              <el-button @click="openKnowledge(task)">去学习</el-button>
              <el-button v-if="!task.resourceId" type="primary" @click="markLearned(task)">标记已学</el-button>
            </template>
          </div>
        </article>
      </section>

      <section class="block">
        <h3>拓展病例</h3>
        <p class="lead">老师按你的年级或轮转组推荐的选做。做完不计入上面的必做进度。</p>
        <div v-if="!student.tasks.some((item) => item.tier === 'EXTENSION')" class="empty">
          还没有拓展病例。
        </div>
        <article
          v-for="task in student.tasks.filter((item) => item.tier === 'EXTENSION')"
          :key="task.id"
          class="task"
        >
          <div class="task-main">
            <div class="task-title">
              <el-tag size="small" type="warning" effect="plain">拓展病例</el-tag>
              <strong>{{ task.title }}</strong>
            </div>
            <p class="meta">{{ task.statusText }}<template v-if="task.score != null"> · {{ task.score }} 分</template></p>
          </div>
          <div class="task-actions">
            <el-button v-if="task.kind === 'CASE'" type="primary" @click="startCase(task)">学习这例</el-button>
          </div>
        </article>
      </section>

      <section class="block">
        <h3>本轮转全部必做</h3>
        <el-table :data="student.tasks.filter((item) => item.tier !== 'EXTENSION')" empty-text="还没有必做项">
          <el-table-column prop="kindText" label="类型" width="120" />
          <el-table-column prop="title" label="内容" min-width="220" />
          <el-table-column prop="dueOn" label="截止日期" width="140" />
          <el-table-column label="合格要求" width="120">
            <template #default="{ row }">
              {{ row.kind === 'CASE' ? `${row.passScore} 分` : '阅读完成' }}
            </template>
          </el-table-column>
          <el-table-column label="进度" width="140">
            <template #default="{ row }">
              <el-tag size="small" :type="statusType(row)" effect="plain">{{ row.statusText }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </template>

    <template v-else-if="teacher">
      <div class="teacher-board">
      <header class="page-head">
        <div>
          <h2>学员情况</h2>
          <p>先看全班概况，再按页签处理学情、布置和待批改。</p>
        </div>
        <el-button type="primary" @click="router.push('/training/class')">管理班级</el-button>
      </header>

      <section class="teacher-metrics" aria-label="全班核心指标">
        <article>
          <span>学员数</span>
          <strong>{{ classSummary.students }}</strong>
          <span>已交卷 {{ classSummary.practiced }} 人</span>
        </article>
        <article>
          <span>练习次数</span>
          <strong>{{ classSummary.practice }}</strong>
        </article>
        <article>
          <span>平均分</span>
          <strong>{{ classSummary.avg.toFixed(1) }}</strong>
        </article>
        <article>
          <span>学时</span>
          <strong>{{ formatMinutes(classSummary.seconds) }}</strong>
        </article>
      </section>

      <el-tabs v-model="activeTeacherTab" type="border-card" class="teacher-tabs">
        <el-tab-pane label="学情监控与督学" name="monitor">
        <h3 class="subhead">按组查看</h3>
        <p class="lead">按年级、轮转批次和带教组分别看完成情况和常见漏诊、误诊。还没填写的学员先算在「未分组」。</p>
        <div class="assign">
          <el-select v-model="yearFilter" clearable placeholder="全部年级" style="width: 160px">
            <el-option v-for="item in yearOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="batchFilter" clearable placeholder="全部轮转批次" style="width: 180px">
            <el-option v-for="item in batchOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="mentorFilter" clearable placeholder="全部带教组" style="width: 160px">
            <el-option v-for="item in mentorOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
        <div class="group-grid">
          <article v-for="group in visibleGroups" :key="`${group.studyYear}-${group.rotationBatch}-${group.mentorGroup}`">
            <strong>{{ group.studyYear }} · {{ group.rotationBatch }} · {{ group.mentorGroup }}</strong>
            <p>{{ group.studentCount }} 名学员，完成 {{ group.done }} / {{ group.total }} 项，进度 {{ group.progress }}%。</p>
            <p>{{ weakText(group) || '这一组还没有汇总出漏诊或误诊。' }}</p>
          </article>
        </div>

        <h3 class="subhead">学员进度</h3>
        <el-table :data="filteredStudents" empty-text="这一组还没有学员">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div v-for="item in row.tasks || []" :key="item.taskId" class="snap">
                <span>{{ taskTitle(item.taskId) }}</span>
                <el-tag size="small" :type="statusType(item)" effect="plain">{{ item.statusText }}</el-tag>
                <span v-if="item.score != null">{{ item.score }} 分</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="学员" min-width="120" />
          <el-table-column prop="studyYear" label="年级" width="110" />
          <el-table-column prop="rotationBatch" label="轮转批次" width="130" />
          <el-table-column prop="mentorGroup" label="带教组" width="120" />
          <el-table-column label="分组修改人" min-width="180">
            <template #default="{ row }">
              {{ actorLabel(row.groupEditorName, row.groupEditorRole) || '尚未记录' }}
            </template>
          </el-table-column>
          <el-table-column label="练习次数" width="100">
            <template #default="{ row }">{{ row.practiceCount }}</template>
          </el-table-column>
          <el-table-column label="完成病例" width="100">
            <template #default="{ row }">{{ row.completedCases }}</template>
          </el-table-column>
          <el-table-column label="平均成绩" width="100">
            <template #default="{ row }">{{ row.avgScore.toFixed(1) }}</template>
          </el-table-column>
          <el-table-column label="学时" width="120">
            <template #default="{ row }">{{ formatMinutes(row.studySeconds) }}</template>
          </el-table-column>
          <el-table-column label="必做" width="120">
            <template #default="{ row }">{{ row.done }} / {{ row.total }}</template>
          </el-table-column>
          <el-table-column label="进度" min-width="200">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="8" />
            </template>
          </el-table-column>
          <el-table-column label="" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="openStudent(row)">查看学情</el-button>
            </template>
          </el-table-column>
        </el-table>
        </el-tab-pane>

        <el-tab-pane label="任务与病例布置" name="assign">
      <h3 class="subhead">轮转要求</h3>
      <section v-if="teacher.rotation" class="stats">
        <article>
          <span>轮转</span>
          <el-input v-model="titleDraft" />
        </article>
        <article>
          <span>截止日期</span>
          <el-date-picker v-model="dueDraft" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
        </article>
        <article>
          <span>合格要求</span>
          <el-input-number v-model="passDraft" :min="0" :max="100" />
          <el-button type="primary" @click="saveRotation">保存</el-button>
        </article>
      </section>

      <section class="block">
        <h3>推荐病例</h3>
        <p class="lead">必做计入该年级或轮转组的完成进度。拓展是选做。同一例可以分别推荐给不同范围。</p>
        <div class="assign">
          <el-select v-model="caseId" clearable filterable placeholder="选择病例" style="width: 320px">
            <el-option v-for="item in caseOptions" :key="item.id" :label="item.label" :value="item.id" />
          </el-select>
          <el-select v-model="caseTier" style="width: 120px">
            <el-option label="必做病例" value="REQUIRED" />
            <el-option label="拓展病例" value="EXTENSION" />
          </el-select>
          <el-select v-model="caseScope" style="width: 140px" @change="caseScopeValue = ''">
            <el-option label="全部学员" value="ALL" />
            <el-option label="按年级" value="YEAR" />
            <el-option label="按轮转组" value="GROUP" />
          </el-select>
          <el-select
            v-if="caseScope !== 'ALL'"
            v-model="caseScopeValue"
            filterable
            :placeholder="caseScope === 'YEAR' ? '选择年级' : '选择轮转组'"
            style="width: 180px"
          >
            <el-option v-for="item in assignTargets" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" @click="addCase">标记推荐</el-button>
        </div>
        <div class="assign">
          <el-select v-model="resourceId" clearable filterable placeholder="选择已发布资料" style="width: 320px">
            <el-option v-for="item in resourceOptions" :key="item.id" :label="item.label" :value="item.id" />
          </el-select>
          <el-input v-model="knowledgeTitle" placeholder="或直接写知识点标题" style="width: 280px" />
          <el-button type="primary" @click="addKnowledge">加入知识点</el-button>
        </div>
      </section>

      <section class="block">
        <h3>本轮转任务</h3>
        <p v-if="teacher.rotation" class="lead">
          必做完成 {{ teacher.rotation.done }} / {{ teacher.rotation.total }} 项，
          进度 {{ teacher.rotation.progress }}%。顺序就是学员看到的顺序。
        </p>
        <el-button @click="arrangeBySpectrum">按病谱排列</el-button>
        <el-table :data="teacher.tasks" empty-text="还没有布置">
          <el-table-column label="顺序" width="110">
            <template #default="{ $index }">
              <el-button link :disabled="$index === 0" @click="moveTask($index, -1)">上移</el-button>
              <el-button
                link
                :disabled="$index === teacher.tasks.length - 1"
                @click="moveTask($index, 1)"
              >
                下移
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="kindText" label="类型" width="120" />
          <el-table-column prop="scopeText" label="对象" width="140" />
          <el-table-column prop="title" label="内容" min-width="240" />
          <el-table-column prop="dueOn" label="截止日期" width="140" />
          <el-table-column label="合格要求" width="120">
            <template #default="{ row }">
              {{ row.kind === 'CASE' ? `${row.passScore} 分` : '阅读完成' }}
            </template>
          </el-table-column>
          <el-table-column prop="statusText" label="完成人数" width="140" />
          <el-table-column label="" width="160">
            <template #default="{ row }">
              <el-button
                v-if="row.kind === 'CASE' ? row.caseNo : row.resourceId"
                link
                type="primary"
                @click="openAssigned(row)"
              >
                打开
              </el-button>
              <el-button link type="danger" @click="removeTask(row)">撤下</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
        </el-tab-pane>

        <el-tab-pane label="待审概况" name="review" lazy>
          <p class="review-guide">
            当前有 {{ pendingReviewCount }} 份作业待评定。点击可就地审阅，或点击侧栏「作业审核与质控」进行全屏深度判读。
          </p>
          <ReadingQualityPanel />
        </el-tab-pane>
      </el-tabs>

      <el-drawer v-model="drawerOpen" :title="focusStudent ? `${focusStudent.name}的学情` : '学情'" size="720px">
        <div v-loading="detailLoading">
          <section class="block">
            <h3>分组</h3>
            <div class="assign">
              <el-input v-model="groupDraft.studyYear" placeholder="年级，如 2024级" style="width: 180px" />
              <el-input v-model="groupDraft.rotationBatch" placeholder="轮转批次，如 2026年上半年" style="width: 220px" />
              <el-input v-model="groupDraft.mentorGroup" placeholder="带教组" style="width: 160px" />
              <el-button type="primary" :loading="savingGroup" @click="saveGroup">保存分组</el-button>
            </div>
            <p v-if="focusStudent" class="lead">
              {{
                actorLabel(focusStudent.groupEditorName, focusStudent.groupEditorRole)
                  ? `最近由 ${actorLabel(focusStudent.groupEditorName, focusStudent.groupEditorRole)}${focusStudent.groupEditedAt ? ` 于 ${focusStudent.groupEditedAt}` : ''} 修改`
                  : '这次保存会记下修改人'
              }}
            </p>
          </section>
          <div v-if="studentStats" class="stats detail-stats">
            <article>
              <span>练习次数</span>
              <strong>{{ studentStats.submittedSessions }}</strong>
            </article>
            <article>
              <span>完成病例</span>
              <strong>{{ studentStats.completedCases }}</strong>
            </article>
            <article>
              <span>平均成绩</span>
              <strong>{{ studentStats.avgScore.toFixed(1) }}</strong>
            </article>
            <article>
              <span>学时</span>
              <strong>{{ formatMinutes(studentStats.totalDuration) }}</strong>
            </article>
          </div>

          <section class="block">
            <h3>常见漏诊和误诊</h3>
            <el-table v-if="studentStats?.weakLabels?.length" :data="studentStats.weakLabels" size="small">
              <el-table-column prop="label" label="病灶" min-width="140" />
              <el-table-column prop="missed" label="漏诊" width="90" />
              <el-table-column prop="falsePositive" label="误诊" width="90" />
            </el-table>
            <p v-else class="empty">还没有汇总出漏诊或误诊。</p>
          </section>

          <section class="block">
            <h3>复练后的变化</h3>
            <div v-if="retryChanges.length">
              <p v-for="item in retryChanges" :key="item.caseNo" class="lead">
                {{ item.caseNo }} 练了 {{ item.times }} 次，{{ item.first }} 分到 {{ item.last }} 分，
                {{ item.delta > 0 ? `提高 ${item.delta} 分` : item.delta < 0 ? `下降 ${Math.abs(item.delta)} 分` : '分数持平' }}。
              </p>
            </div>
            <p v-else class="empty">同一病例还没有第二次已交卷的练习。</p>
          </section>

          <section class="block">
            <h3>已完成病例和得分</h3>
            <el-table :data="finishedRecords" size="small" empty-text="还没有交卷记录">
              <el-table-column label="交卷时间" width="150">
                <template #default="{ row }">{{ (row.submittedAt || '').slice(0, 16) || '—' }}</template>
              </el-table-column>
              <el-table-column prop="caseNo" label="病例" width="120" />
              <el-table-column label="得分" width="80">
                <template #default="{ row }">{{ row.scoreTotal }}</template>
              </el-table-column>
              <el-table-column label="用时" width="110">
                <template #default="{ row }">{{ formatMinutes(row.durationSeconds) }}</template>
              </el-table-column>
              <el-table-column label="漏诊 / 误诊" width="120">
                <template #default="{ row }">{{ row.missedCount }} / {{ row.falsePositiveCount }}</template>
              </el-table-column>
              <el-table-column label="教师评语" min-width="220">
                <template #default="{ row }">
                  <div class="comment-line">
                    <el-input v-model="commentDraft[row.id]" size="small" placeholder="写一句评语" />
                    <el-button
                      size="small"
                      type="primary"
                      :loading="savingCommentId === row.id"
                      @click="saveComment(row)"
                    >
                      保存
                    </el-button>
                  </div>
                  <p v-if="row.teacherName" class="lead">
                    点评人 {{ actorLabel(row.teacherName, row.teacherRole) }}
                  </p>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </div>
      </el-drawer>
      </div>
    </template>
  </div>
</template>

<style scoped>
.home-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 28px 32px 48px;
  color: #1d2129;
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.page-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 650;
}
.page-head p,
.lead,
.task p,
.meta {
  margin: 0;
  color: #4e5969;
  font-size: 14px;
  line-height: 1.6;
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin: 20px 0 8px;
}
.stats article {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stats span {
  color: #4e5969;
  font-size: 13px;
}
.stats strong {
  font-size: 22px;
  color: #1d2129;
}
.block {
  margin-top: 28px;
}
.block h3 {
  margin: 0 0 12px;
  font-size: 16px;
}
.students-entry {
  margin-top: 20px;
  background: #f7f8fa;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 18px 18px 8px;
}
.subhead {
  margin-top: 22px;
}
.class-stats {
  margin-top: 12px;
}
.task {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  margin-bottom: 12px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
}
.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.task-title strong {
  color: #1d2129;
}
.task-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.assign {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.empty {
  padding: 28px 0;
  color: #4e5969;
}
.snap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  color: #1d2129;
}
.detail-stats {
  margin-top: 0;
}
.detail-stats strong {
  font-size: 18px;
}
.comment-line {
  display: flex;
  gap: 8px;
  align-items: center;
}
.group-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.group-grid article {
  background: #f7f9fb;
  border: 1px solid #d5dee8;
  border-radius: 12px;
  padding: 14px 16px;
}
.group-grid strong {
  color: #1d2129;
}
.group-grid p {
  margin: 6px 0 0;
  color: #4e5969;
  font-size: 13px;
  line-height: 1.5;
}
.teacher-board {
  background: #eef2f6;
  border: 1px solid #d5dee8;
  border-radius: 16px;
  padding: 20px 22px 24px;
}
.teacher-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0 18px;
}
.teacher-metrics article {
  background: #f7f9fb;
  border: 1px solid #d5dee8;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.teacher-metrics span {
  color: #4e5969;
  font-size: 13px;
}
.teacher-metrics strong {
  font-size: 22px;
  color: #1d2129;
}
.review-guide {
  margin: 0 0 12px;
  padding: 10px 14px;
  background: #f7f9fb;
  border: 1px solid #dfe3ea;
  border-radius: 8px;
  color: #1d2129;
  font-size: 14px;
  line-height: 1.6;
}
.teacher-board :deep(.el-tabs--border-card) {
  background: #eef2f6;
  border-color: #d5dee8;
  box-shadow: none;
}
.teacher-board :deep(.el-tabs--border-card > .el-tabs__header) {
  background: #e4eaf1;
  border-bottom-color: #d5dee8;
}
.teacher-board :deep(.el-tabs--border-card > .el-tabs__content) {
  background: #eef2f6;
}
.teacher-board :deep(.el-table),
.teacher-board :deep(.el-table tr),
.teacher-board :deep(.el-table th.el-table__cell),
.teacher-board :deep(.el-table td.el-table__cell) {
  background: #f7f9fb;
}
@media (max-width: 800px) {
  .teacher-metrics {
    grid-template-columns: 1fr 1fr;
  }
  .stats {
    grid-template-columns: 1fr;
  }
  .task {
    flex-direction: column;
  }
}
</style>
