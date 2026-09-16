<script setup lang="ts">
/**
 * 教师待审核：把阅片提交和练习提交收成一个入口。
 * 点「评定」带上 recordId / sessionId，工作站才能打开审核侧栏。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { PracticeApi, ReadingApi } from '@/api'

type Kind = 'reading' | 'practice'

const router = useRouter()
const activeKind = ref<Kind>('reading')

const readingStatus = ref<ReadingApi.ReadingStatus | ''>('SUBMITTED')
const practiceStatus = ref<PracticeApi.PracticeStatus | ''>('SUBMITTED')

const readingLoading = ref(false)
const practiceLoading = ref(false)
const readingList = ref<ReadingApi.ReadingRecord[]>([])
const practiceList = ref<PracticeApi.PracticeRecord[]>([])
const readingPage = reactive({ page: 1, pageSize: 20, total: 0 })
const practicePage = reactive({ page: 1, pageSize: 20, total: 0 })

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

const fetchPractice = async () => {
  practiceLoading.value = true
  try {
    const r = await PracticeApi.getPracticeList({
      status: practiceStatus.value || undefined,
      page: practicePage.page,
      pageSize: practicePage.pageSize
    })
    practiceList.value = (r.list || []).filter((row) => row.status !== 'DRAFT')
    practicePage.total = r.total || 0
  } catch {
    practiceList.value = []
    practicePage.total = 0
  } finally {
    practiceLoading.value = false
  }
}

const onReadingFilter = () => {
  readingPage.page = 1
  fetchReading()
}
const onPracticeFilter = () => {
  practicePage.page = 1
  fetchPractice()
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

const goPracticeReview = (row: PracticeApi.PracticeRecord) => {
  router.push({
    path: '/training/practice/workstation',
    query: {
      caseId: String(row.caseId),
      sessionId: String(row.id),
      review: '1'
    }
  })
}

const readingMeta = (status: ReadingApi.ReadingStatus) =>
  ReadingApi.READING_STATUS_META[status] || { label: status, tag: 'info' as const }

const practiceReviewText = (row: PracticeApi.PracticeRecord) => {
  if (row.status === 'SUBMITTED') return { label: '待审核', type: 'warning' as const }
  if (row.status === 'REVIEWED') return { label: '已点评', type: 'success' as const }
  return { label: '草稿', type: 'info' as const }
}

onMounted(() => {
  fetchReading()
  fetchPractice()
})
</script>

<template>
  <div class="pending-page">
    <header class="page-head">
      <div class="head-left">
        <h2>待审核</h2>
        <div class="muted">学员提交的阅片作业与练习自评，点「评定」打开原卷写评语</div>
      </div>
      <el-button
        :icon="Refresh"
        size="small"
        @click="activeKind === 'reading' ? fetchReading() : fetchPractice()"
      >
        刷新
      </el-button>
    </header>

    <el-tabs v-model="activeKind" class="kind-tabs">
      <el-tab-pane label="阅片作业" name="reading">
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
        <el-table v-loading="readingLoading" :data="readingList" size="small" stripe>
          <el-table-column prop="userName" label="学员" min-width="120" />
          <el-table-column prop="caseNo" label="病例" min-width="140" />
          <el-table-column label="类型" width="90">
            <template #default>
              <el-tag size="small" effect="plain">阅片</el-tag>
            </template>
          </el-table-column>
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
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click="goReadingReview(row)">
                评定
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
      </el-tab-pane>

      <el-tab-pane label="练习自评" name="practice">
        <div class="toolbar">
          <el-select
            v-model="practiceStatus"
            placeholder="状态"
            clearable
            size="small"
            style="width: 140px"
            @change="onPracticeFilter"
          >
            <el-option label="待审核" value="SUBMITTED" />
            <el-option label="已点评" value="REVIEWED" />
          </el-select>
        </div>
        <el-table v-loading="practiceLoading" :data="practiceList" size="small" stripe>
          <el-table-column prop="userName" label="学员" min-width="120" />
          <el-table-column label="病例" min-width="180">
            <template #default="{ row }">
              <div>{{ row.caseTitle || row.caseNo }}</div>
              <div class="muted">{{ row.caseNo }}</div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default>
              <el-tag size="small" type="warning" effect="plain">练习</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="系统分" width="90">
            <template #default="{ row }">
              {{ Number(row.scoreTotal || 0).toFixed(1) }}
            </template>
          </el-table-column>
          <el-table-column label="是否通过" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.isPassed ? 'success' : 'danger'">
                {{ row.isPassed ? '合格' : '不合格' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="教师评定" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="practiceReviewText(row).type">
                {{ practiceReviewText(row).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="submittedAt" label="提交时间" width="180" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click="goPracticeReview(row)">
                评定
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty">{{ practiceLoading ? '加载中…' : '暂无待审核作业' }}</div>
          </template>
        </el-table>
        <div v-if="practicePage.total > practicePage.pageSize" class="pagination">
          <el-pagination
            v-model:current-page="practicePage.page"
            v-model:page-size="practicePage.pageSize"
            :total="practicePage.total"
            :page-sizes="[10, 20, 50]"
            background
            layout="total, sizes, prev, pager, next"
            @size-change="fetchPractice"
            @current-change="fetchPractice"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
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
