<script setup lang="ts">
/**
 * 教师待审核：只收阅片作业。
 * 自主练习提交后由系统评分，不进入这里。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ReadingApi } from '@/api'
import ReadingReviewDialog from '@/views/reading/components/ReadingReviewDialog.vue'

const router = useRouter()

const readingStatus = ref<ReadingApi.ReadingStatus | ''>('SUBMITTED')

const readingLoading = ref(false)
const readingList = ref<ReadingApi.ReadingRecord[]>([])
const readingPage = reactive({ page: 1, pageSize: 20, total: 0 })

const fetchReading = async () => {
  readingLoading.value = true
  try {
    const r = await ReadingApi.getReadingList({
      status: readingStatus.value || undefined,
      page: readingPage.page,
      pageSize: readingPage.pageSize
    })
    readingList.value = (r.list || []).filter((row) => row.status !== 'DRAFT')
    readingPage.total = r.total || 0
  } catch {
    readingList.value = []
    readingPage.total = 0
  } finally {
    readingLoading.value = false
  }
}

const onReadingFilter = () => {
  readingPage.page = 1
  fetchReading()
}

const reviewVisible = ref(false)
const reviewingRow = ref<ReadingApi.ReadingRecord | null>(null)

const openReadingGrade = (row: ReadingApi.ReadingRecord) => {
  reviewingRow.value = row
  reviewVisible.value = true
}

const onReadingReviewed = () => {
  reviewingRow.value = null
  fetchReading()
}

const goReadingReview = (row: ReadingApi.ReadingRecord) => {
  router.push({
    path: '/training/reading',
    query: {
      caseId: String(row.caseId),
      recordId: String(row.id),
      from: 'review'
    }
  })
}

const readingMeta = (status: ReadingApi.ReadingStatus) =>
  ReadingApi.READING_STATUS_META[status] || { label: status, tag: 'info' as const }

onMounted(() => {
  fetchReading()
})
</script>

<template>
  <div class="pending-page">
    <header class="page-head">
      <div class="head-left">
        <h2>待审核</h2>
        <div class="muted">
          这里只评定学员提交的阅片作业。自主练习提交后由系统直接评分，不送到教师端。
        </div>
      </div>
      <el-button
        :icon="Refresh"
        size="small"
        @click="fetchReading"
      >
        刷新
      </el-button>
    </header>

    <div class="kind-tabs">
        <div class="toolbar">
          <el-select
            v-model="readingStatus"
            placeholder="状态"
            clearable
            size="small"
            style="width: 140px"
            @change="onReadingFilter"
          >
            <el-option label="待审核" value="SUBMITTED" />
            <el-option label="已通过" value="REVIEWED" />
            <el-option label="已驳回" value="REJECTED" />
          </el-select>
        </div>
        <el-table v-loading="readingLoading" :data="readingList" row-key="id" size="small" stripe>
          <el-table-column prop="id" label="记录" width="80" />
          <el-table-column prop="userName" label="学员" min-width="120" />
          <el-table-column prop="caseNo" label="病例" min-width="140" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="readingMeta(row.status).tag">
                {{ readingMeta(row.status).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="updatedAt" label="提交 / 更新" width="180" />
          <el-table-column label="评语" min-width="160">
            <template #default="{ row }">
              <span class="comment">{{ row.reviewComment || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click="openReadingGrade(row)">
                评定
              </el-button>
              <el-button text size="small" @click="goReadingReview(row)">
                原卷
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty">{{ readingLoading ? '加载中…' : '暂无待审核作业' }}</div>
          </template>
        </el-table>
        <div v-if="readingPage.total > readingPage.pageSize" class="pagination">
          <el-pagination
            v-model:current-page="readingPage.page"
            v-model:page-size="readingPage.pageSize"
            :total="readingPage.total"
            :page-sizes="[10, 20, 50]"
            background
            layout="total, sizes, prev, pager, next"
            @size-change="fetchReading"
            @current-change="fetchReading"
          />
        </div>
    </div>

    <ReadingReviewDialog
      v-model="reviewVisible"
      :row="reviewingRow"
      @done="onReadingReviewed"
      @open-original="goReadingReview"
    />
  </div>
</template>

<style scoped>
.pending-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 28px 36px;
  min-height: 100vh;
  background: #ffffff;
}
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}
.head-left h2 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: #1d2129;
}
.muted {
  color: #86909c;
  font-size: 12px;
}
.toolbar {
  margin-bottom: 12px;
}
.comment {
  color: #4e5969;
  font-size: 12px;
}
.empty {
  padding: 36px 0;
  text-align: center;
  color: #c9cdd4;
  font-size: 14px;
}
.pagination {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
