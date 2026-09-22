<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { PracticeApi, RotationApi } from '@/api'
import type { RotationTask, StudentHome, TeacherHome } from '@/api/rotation'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const isTeacher = computed(() => userStore.isAdmin || userStore.isDoctor)

const loading = ref(false)
const student = ref<StudentHome | null>(null)
const teacher = ref<TeacherHome | null>(null)

const caseId = ref<number | undefined>()
const resourceId = ref<number | undefined>()
const knowledgeTitle = ref('')
const caseOptions = ref<{ id: number; label: string }[]>([])
const resourceOptions = ref<{ id: number; label: string }[]>([])
const dueDraft = ref('')
const passDraft = ref(60)
const titleDraft = ref('')

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

onMounted(async () => {
  await load()
  await loadOptions()
})

const startCase = async (task: RotationTask) => {
  if (!task.caseId) return
  const rec = await PracticeApi.startPractice({ caseId: task.caseId, mode: 'SELECTED' })
  router.push({
    path: '/practice/workstation',
    query: { sessionId: String(rec.id), caseId: String(task.caseId) }
  })
}

const markLearned = async (task: RotationTask) => {
  student.value = await RotationApi.markLearned(task.id)
  ElMessage.success('已记入本轮转进度')
}

const openKnowledge = () => {
  router.push('/training/learning')
}

const saveRotation = async () => {
  teacher.value = await RotationApi.updateRotation({
    title: titleDraft.value,
    dueOn: dueDraft.value,
    passScore: passDraft.value
  })
  ElMessage.success('轮转要求已保存')
}

const addCase = async () => {
  if (!caseId.value) {
    ElMessage.warning('请选择病例')
    return
  }
  teacher.value = await RotationApi.addTask({ kind: 'CASE', caseId: caseId.value, passScore: passDraft.value })
  caseId.value = undefined
  ElMessage.success('已加入本轮转')
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

const statusType = (task: RotationTask) => {
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
          <p>{{ student.rotation?.title || '本轮转' }}。这里是老师布置的必做病例和必学知识点。</p>
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
          {{ student.tasks.length ? '今日必做已完成。' : '老师还没有布置本轮转任务。' }}
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
            <el-button v-if="task.kind === 'CASE'" type="primary" @click="startCase(task)">去做</el-button>
            <template v-else>
              <el-button @click="openKnowledge">去学习</el-button>
              <el-button type="primary" @click="markLearned(task)">标记已学</el-button>
            </template>
          </div>
        </article>
      </section>

      <section class="block">
        <h3>本轮转全部必做</h3>
        <el-table :data="student.tasks" empty-text="还没有必做项">
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
      <header class="page-head">
        <div>
          <h2>教学首页</h2>
          <p>布置本轮转必须完成的病例和知识点。学员首页只看到任务、截止日期和自己的进度。</p>
        </div>
      </header>

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
        <h3>加入必做</h3>
        <div class="assign">
          <el-select v-model="caseId" clearable filterable placeholder="选择必做病例" style="width: 320px">
            <el-option v-for="item in caseOptions" :key="item.id" :label="item.label" :value="item.id" />
          </el-select>
          <el-button type="primary" @click="addCase">加入病例</el-button>
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
          全班完成 {{ teacher.rotation.done }} / {{ teacher.rotation.total }} 项，
          进度 {{ teacher.rotation.progress }}%。
        </p>
        <el-table :data="teacher.tasks" empty-text="还没有布置">
          <el-table-column prop="kindText" label="类型" width="120" />
          <el-table-column prop="title" label="内容" min-width="240" />
          <el-table-column prop="dueOn" label="截止日期" width="140" />
          <el-table-column label="合格要求" width="120">
            <template #default="{ row }">
              {{ row.kind === 'CASE' ? `${row.passScore} 分` : '阅读完成' }}
            </template>
          </el-table-column>
          <el-table-column prop="statusText" label="完成人数" width="140" />
          <el-table-column label="" width="100">
            <template #default="{ row }">
              <el-button link type="danger" @click="removeTask(row)">撤下</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="block">
        <h3>学员进度</h3>
        <el-table :data="teacher.students" empty-text="还没有学员">
          <el-table-column prop="name" label="学员" min-width="160" />
          <el-table-column label="完成" width="140">
            <template #default="{ row }">{{ row.done }} / {{ row.total }}</template>
          </el-table-column>
          <el-table-column label="进度" min-width="200">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="8" />
            </template>
          </el-table-column>
        </el-table>
      </section>
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
@media (max-width: 800px) {
  .stats {
    grid-template-columns: 1fr;
  }
  .task {
    flex-direction: column;
  }
}
</style>
