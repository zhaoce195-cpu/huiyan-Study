<script setup lang="ts">
/**
 * 学员看教师对阅片作业的评定。自主练习不经过这里。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ReadingApi } from '@/api'

const router = useRouter()
const loading = ref(false)
const readings = ref<ReadingApi.ReadingRecord[]>([])

const fetchAll = async () => {
  loading.value = true
  try {
    const r = await ReadingApi.getReadingList({ page: 1, pageSize: 50 })
    readings.value = (r.list || []).filter((row) => row.status !== 'DRAFT')
  } catch {
    readings.value = []
  } finally {
    loading.value = false
  }
}

const readingMeta = (st: ReadingApi.ReadingStatus) =>
  ReadingApi.READING_STATUS_META[st] || { label: st, tag: 'info' as const }

const openReading = (row: ReadingApi.ReadingRecord) => {
  router.push({
    path: '/training/reading',
    query: { caseId: String(row.caseId), recordId: String(row.id), from: 'my-reviews' }
  })
}

onMounted(fetchAll)
</script>

<template>
  <div class="reviews-page">
    <header class="page-head">
      <div>
        <h2>教师评定</h2>
        <p>这里是教师对阅片作业的通过、驳回和评语。自主练习提交后由系统直接评分，成绩在「自主练习与自评」里查看。</p>
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
