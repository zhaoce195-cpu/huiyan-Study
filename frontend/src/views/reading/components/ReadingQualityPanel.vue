<script setup lang="ts">
/**
 * 教师在阅片工作台里的「质量评估」：列出学员已提交作业，并当场通过/驳回。
 */
import { onMounted, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ReadingApi } from '@/api'
import ReadingReviewDialog from './ReadingReviewDialog.vue'

const props = defineProps<{
  caseId?: number
}>()

const emit = defineEmits<{
  (e: 'review', row: ReadingApi.ReadingRecord): void
}>()

const loading = ref(false)
const list = ref<ReadingApi.ReadingRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const status = ref<ReadingApi.ReadingStatus | ''>('SUBMITTED')
const dialogVisible = ref(false)
const current = ref<ReadingApi.ReadingRecord | null>(null)

const fetchList = async () => {
  loading.value = true
  try {
    const r = await ReadingApi.getReadingList({
      status: status.value || undefined,
      caseId: props.caseId || undefined,
      page: page.value,
      pageSize: pageSize.value
    })
    list.value = (r.list || []).filter((row) => row.status !== 'DRAFT')
    total.value = r.total || 0
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const onFilter = () => {
  page.value = 1
  fetchList()
}

const openReview = (row: ReadingApi.ReadingRecord) => {
  current.value = row
  dialogVisible.value = true
}

const onReviewed = (out: ReadingApi.ReadingRecord) => {
  status.value = out.status
  page.value = 1
  fetchList()
}

const meta = (st: ReadingApi.ReadingStatus) =>
  ReadingApi.READING_STATUS_META[st] || { label: st, tag: 'info' as const }

onMounted(fetchList)
watch(() => props.caseId, () => {
  page.value = 1
  fetchList()
})
</script>

<template>
  <div class="quality-panel">
    <header class="qp-head">
      <div>
        <h3>质量评估</h3>
        <p>对学员已提交的阅片作业评定：通过或驳回后，记录从「待审核」变为「已通过 / 已驳回」。</p>
      </div>
      <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
    </header>

    <div class="qp-toolbar">
      <el-select
        v-model="status"
        size="small"
        clearable
        placeholder="状态"
        style="width: 140px"
        @change="onFilter"
      >
        <el-option label="待审核" value="SUBMITTED" />
        <el-option label="已通过" value="REVIEWED" />
        <el-option label="已驳回" value="REJECTED" />
      </el-select>
      <span v-if="caseId" class="qp-hint">仅看当前病例</span>
    </div>

    <el-table v-loading="loading" :data="list" size="small" stripe>
      <el-table-column prop="userName" label="学员" min-width="120" />
      <el-table-column prop="caseNo" label="病例" min-width="140" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="meta(row.status).tag">
            {{ meta(row.status).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updatedAt" label="提交 / 更新" width="180" />
      <el-table-column label="评语" min-width="160">
        <template #default="{ row }">
          {{ row.reviewComment || '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" size="small" @click="openReview(row)">
            评定
          </el-button>
          <el-button text size="small" @click="emit('review', row)">
            原卷
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="qp-empty">
          {{ loading ? '加载中…' : '暂无学员提交的待审核记录' }}
        </div>
      </template>
    </el-table>

    <div v-if="total > pageSize" class="qp-pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        background
        layout="total, sizes, prev, pager, next"
        @size-change="fetchList"
        @current-change="fetchList"
      />
    </div>

    <ReadingReviewDialog
      v-model="dialogVisible"
      :row="current"
      @done="onReviewed"
      @open-original="emit('review', $event)"
    />
  </div>
</template>

<style scoped>
.quality-panel {
  flex: 1;
  min-height: 0;
  padding: 20px 24px 28px;
  background: #fff;
  overflow: auto;
}
.qp-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.qp-head h3 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: #1d2129;
}
.qp-head p {
  margin: 0;
  font-size: 12px;
  color: #86909c;
}
.qp-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.qp-hint {
  font-size: 12px;
  color: #86909c;
}
.qp-empty {
  padding: 36px 0;
  text-align: center;
  color: #c9cdd4;
}
.qp-pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
