<script setup lang="ts">
/**
 * 学员看教师评定：独立入口，不再埋在自主练习的子 Tab 里。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { PracticeApi, ReadingApi } from '@/api'

const router = useRouter()
const loading = ref(false)
const readings = ref<ReadingApi.ReadingRecord[]>([])
const practices = ref<PracticeApi.PracticeRecord[]>([])

const fetchAll = async () => {
  loading.value = true
  try {
    const [r, p] = await Promise.all([
      ReadingApi.getReadingList({ page: 1, pageSize: 50 }),
      PracticeApi.getPracticeList({ page: 1, pageSize: 50 })
    ])
    readings.value = (r.list || []).filter((row) => row.status !== 'DRAFT')
    practices.value = (p.list || []).filter((row) => row.status !== 'DRAFT')
  } catch {
    readings.value = []
    practices.value = []
  } finally {
    loading.value = false
  }
}

const readingMeta = (st: ReadingApi.ReadingStatus) =>
  ReadingApi.READING_STATUS_META[st] || { label: st, tag: 'info' as const }

const practiceReview = (row: PracticeApi.PracticeRecord) => {
  if (row.status === 'SUBMITTED') return { label: '待审核', type: 'warning' as const, comment: '' }
  return {
    label: row.isPassed ? '合格' : '不合格',
    type: (row.isPassed ? 'success' : 'danger') as const,
    comment: row.teacherComment || ''
  }
}

const openReading = (row: ReadingApi.ReadingRecord) => {
  router.push({
    path: '/training/reading',
    query: { caseId: String(row.caseId), recordId: String(row.id), from: 'my-reviews' }
  })
}

const openPractice = (row: PracticeApi.PracticeRecord) => {
  router.push({
    path: '/training/practice/workstation',
    query: { caseId: String(row.caseId), sessionId: String(row.id), view: 'report' }
  })
}

onMounted(fetchAll)
</script>

<template>
  <div class="reviews-page">
    <header class="page-head">
      <div>
        <h2>教师评定</h2>
        <p>教师对你提交的阅片作业和练习自评的等级与评语。未评的显示「待审核」。</p>
      </div>
      <el-button :icon="Refresh" size="small" @click="fetchAll">刷新</el-button>
    </header>

    <section class="block">
      <h3>阅片作业</h3>
      <el-table v-loading="loading" :data="readings" size="small" stripe>
        <el-table-column prop="caseNo" label="病例" min-width="140" />
        <el-table-column label="评定结果" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="readingMeta(row.status).tag">
              {{ readingMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="教师评语" min-width="240">
          <template #default="{ row }">
            <span v-if="row.status === 'SUBMITTED'" class="muted">待教师评定</span>
            <span v-else>{{ row.reviewComment || '（无评语）' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="180" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openReading(row)">
              查看
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '还没有已提交的阅片作业' }}</div>
        </template>
      </el-table>
    </section>

    <section class="block">
      <h3>练习自评</h3>
      <el-table v-loading="loading" :data="practices" size="small" stripe>
        <el-table-column label="病例" min-width="180">
          <template #default="{ row }">
            <div>{{ row.caseTitle || row.caseNo }}</div>
            <div class="muted">{{ row.caseNo }}</div>
          </template>
        </el-table-column>
        <el-table-column label="系统分" width="90">
          <template #default="{ row }">
            {{ Number(row.scoreTotal || 0).toFixed(1) }}
          </template>
        </el-table-column>
        <el-table-column label="教师评定" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="practiceReview(row).type">
              {{ practiceReview(row).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="教师评语" min-width="220">
          <template #default="{ row }">
            <span v-if="row.status === 'SUBMITTED'" class="muted">待教师评定</span>
            <span v-else>{{ practiceReview(row).comment || '（无评语）' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="submittedAt" label="提交时间" width="180" />
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openPractice(row)">
              查看报告
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '还没有已提交的练习记录' }}</div>
        </template>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.reviews-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 28px 36px;
  min-height: 100vh;
  background: #fff;
}
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.page-head h2 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
}
.page-head p,
.muted {
  margin: 0;
  color: #86909c;
  font-size: 12px;
}
.block {
  margin-bottom: 28px;
}
.block h3 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}
.empty {
  padding: 36px 0;
  text-align: center;
  color: #c9cdd4;
}
</style>
