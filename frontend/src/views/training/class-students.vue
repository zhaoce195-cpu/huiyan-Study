<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { RotationApi } from '@/api'
import type { StudentProgress } from '@/api/rotation'
import { actorLabel } from '@/utils/actor'

interface Draft {
  userId: number
  name: string
  username: string
  studyYear: string
  rotationBatch: string
  mentorGroup: string
  groupEditorName: string
  groupEditorRole: string
  groupEditedAt: string
}

const router = useRouter()
const loading = ref(false)
const keyword = ref('')
const savingId = ref(0)
const rows = ref<Draft[]>([])

const blank = (value: string) => (value === '未分组' ? '' : value)

const load = async () => {
  loading.value = true
  try {
    const home = await RotationApi.getHome()
    if (home.role !== 'teacher') {
      router.replace('/training/home')
      return
    }
    rows.value = home.students.map((row) => ({
      userId: row.userId,
      name: row.name,
      username: row.username || '',
      studyYear: blank(row.studyYear),
      rotationBatch: blank(row.rotationBatch),
      mentorGroup: blank(row.mentorGroup),
      groupEditorName: row.groupEditorName || '',
      groupEditorRole: row.groupEditorRole || '',
      groupEditedAt: row.groupEditedAt || ''
    }))
  } finally {
    loading.value = false
  }
}

const visible = computed(() => {
  const text = keyword.value.trim()
  if (!text) return rows.value
  return rows.value.filter((row) => row.name.includes(text) || row.username.includes(text))
})

const groupActor = (row: Draft) => {
  const who = actorLabel(row.groupEditorName, row.groupEditorRole)
  if (who) return row.groupEditedAt ? `${who} · ${row.groupEditedAt}` : who
  if (row.studyYear || row.rotationBatch || row.mentorGroup) return '尚未记录'
  return '—'
}

const ungrouped = computed(
  () => rows.value.filter((row) => !row.studyYear && !row.rotationBatch && !row.mentorGroup).length
)

const save = async (row: Draft) => {
  savingId.value = row.userId
  try {
    const home = await RotationApi.setStudentGroup(row.userId, {
      studyYear: row.studyYear.trim(),
      rotationBatch: row.rotationBatch.trim(),
      mentorGroup: row.mentorGroup.trim()
    })
    const latest = home.students.find((item: StudentProgress) => item.userId === row.userId)
    if (latest) {
      row.studyYear = blank(latest.studyYear)
      row.rotationBatch = blank(latest.rotationBatch)
      row.mentorGroup = blank(latest.mentorGroup)
      row.groupEditorName = latest.groupEditorName || ''
      row.groupEditorRole = latest.groupEditorRole || ''
      row.groupEditedAt = latest.groupEditedAt || ''
    }
    ElMessage.success('已保存。学员情况和推荐病例按这个分组计算')
  } finally {
    savingId.value = 0
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="class-page">
    <header class="page-head">
      <div>
        <h2>班级学生</h2>
        <p>
          把学员分到年级、轮转批次和带教组。学员情况里的按组查看，以及推荐病例的范围，都用这里的分组。
          账号由管理员开通，这里不新建账号。
        </p>
      </div>
      <el-button @click="router.push('/training/home')">返回学员情况</el-button>
    </header>

    <section class="toolbar">
      <el-input v-model="keyword" clearable placeholder="按姓名或账号查找" style="width: 240px" />
      <span>{{ rows.length }} 名学员<span v-if="ungrouped">，{{ ungrouped }} 名还没分组</span></span>
    </section>

    <el-table :data="visible" empty-text="还没有学员账号">
      <el-table-column prop="name" label="学员" min-width="120" />
      <el-table-column prop="username" label="账号" min-width="120" />
      <el-table-column label="年级" min-width="160">
        <template #default="{ row }">
          <el-input v-model="row.studyYear" placeholder="如 2024级" />
        </template>
      </el-table-column>
      <el-table-column label="轮转批次" min-width="180">
        <template #default="{ row }">
          <el-input v-model="row.rotationBatch" placeholder="如 2026年上半年" />
        </template>
      </el-table-column>
      <el-table-column label="带教组" min-width="160">
        <template #default="{ row }">
          <el-input v-model="row.mentorGroup" placeholder="如 眼底一组" />
        </template>
      </el-table-column>
      <el-table-column label="最近修改" min-width="200">
        <template #default="{ row }">
          <span class="muted">{{ groupActor(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="" width="100">
        <template #default="{ row }">
          <el-button type="primary" link :loading="savingId === row.userId" @click="save(row)">
            保存
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.class-page {
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
.page-head p {
  margin: 0;
  color: #4e5969;
  font-size: 14px;
  line-height: 1.6;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 20px 0 12px;
  color: #4e5969;
  font-size: 14px;
}
.muted {
  color: #4e5969;
  font-size: 13px;
}
</style>
