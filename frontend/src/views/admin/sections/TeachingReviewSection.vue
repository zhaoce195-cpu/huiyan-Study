<script setup lang="ts">
/**
 * 管理后台 · 教学病例审核
 * - 列表：分页 + 状态筛选 + 关键词搜索
 * - 操作：审核通过 / 驳回（必填理由）/ 已通过的可下架
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, Check, Close, View, Bottom } from '@element-plus/icons-vue'
import { TeachingApi } from '@/api'
import TeachingDemoBody from '@/views/training/components/TeachingDemoBody.vue'
import { useReviewActions } from '@/composables/useReviewActions'

type Share = TeachingApi.TeachingShare
type ShareStatus = TeachingApi.ShareStatus

defineProps<{
  canManage: boolean
}>()

const list = ref<Share[]>([])
const loading = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const filter = reactive({
  keyword: '',
  status: '' as ShareStatus | '',
})

const statusMap: Record<string, { label: string; type: 'info' | 'success' | 'warning' | 'danger' }> = {
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '已通过', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
  SHELVED: { label: '已下架', type: 'info' },
}

const fetchList = async () => {
  loading.value = true
  try {
    const r = await TeachingApi.getAdminReviews({
      page: pagination.page,
      pageSize: pagination.pageSize,
      status: filter.status || undefined,
      keyword: filter.keyword || undefined,
    })
    list.value = r?.list || []
    pagination.total = r?.total || 0
  } catch {
    list.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const onFilter = () => {
  pagination.page = 1
  fetchList()
}

/* ========== 通过 / 驳回（共享 composable） ========== */
const { reviewing, approve, reject } = useReviewActions<unknown>({
  reviewFn: (id, payload) => TeachingApi.adminReview(id, payload),
  onAfter: () => fetchList(),
})

const onApprove = (row: Share) =>
  approve(row.id, `${row.teacherName} → ${row.desensitizedData?.title || ''}`)

const onReject = (row: Share) =>
  reject(row.id, `${row.teacherName} → ${row.desensitizedData?.title || ''}`)

const onShelve = async (row: Share) => {
  try {
    await ElMessageBox.confirm(
      `确认下架病例「${row.desensitizedData?.title || ''}」？下架后学员端不再可见。`,
      '下架教学病例',
      { type: 'warning' }
    )
  } catch {
    return
  }
  reviewing.value = row.id
  try {
    await TeachingApi.adminShelve(row.id)
    ElMessage.success('已下架')
    fetchList()
  } catch {
    /* 已弹错误 */
  } finally {
    reviewing.value = null
  }
}

const detailVisible = ref(false)
const detail = ref<Share | null>(null)
const showDetail = (row: Share) => {
  detail.value = row
  detailVisible.value = true
}

onMounted(fetchList)
</script>

<template>
  <div class="teaching-review-section">
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          教学病例审核
          <span class="muted ml8">共 {{ pagination.total }} 条</span>
        </div>
        <div class="card-actions">
          <el-input
            v-model="filter.keyword"
            placeholder="搜索教师姓名 / 账号"
            :prefix-icon="Search"
            clearable
            size="small"
            style="width: 220px"
            @change="onFilter"
            @clear="onFilter"
          />
          <el-select
            v-model="filter.status"
            placeholder="状态"
            clearable
            size="small"
            style="width: 110px"
            @change="onFilter"
          >
            <el-option label="待审核" value="PENDING" />
            <el-option label="已通过" value="APPROVED" />
            <el-option label="已驳回" value="REJECTED" />
            <el-option label="已下架" value="SHELVED" />
          </el-select>
          <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="病例" min-width="240">
          <template #default="{ row }">
            <div class="case-title">{{ row.desensitizedData?.title || '—' }}</div>
            <div class="muted small multiline">
              {{
                (row.desensitizedData?.teaching_points || row.desensitizedData?.gold_diagnosis || row.desensitizedData?.description || '').substring(0, 80)
              }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="提交医生" width="140">
          <template #default="{ row }">
            <span>{{ row.teacherName || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="140">
          <template #default="{ row }">
            {{ row.sourceType === 'SCREENING' ? '筛查' : '实训' }}#{{ row.sourceCaseId }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="提交时间" width="170" />
        <el-table-column label="审核" min-width="180">
          <template #default="{ row }">
            <div v-if="row.reviewedAt" class="small">
              {{ row.reviewedAt }}
              <span v-if="row.reviewerName" class="muted">· {{ row.reviewerName }}</span>
            </div>
            <div v-if="row.reviewComment" class="small muted multiline">
              {{ row.status === 'REJECTED' ? '驳回：' : '备注：' }}{{ row.reviewComment }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" :icon="View" @click="showDetail(row)">查看</el-button>
            <el-button
              v-if="row.status === 'PENDING' && canManage"
              text
              type="success"
              size="small"
              :icon="Check"
              :loading="reviewing === row.id"
              @click="onApprove(row)"
            >通过</el-button>
            <el-button
              v-if="row.status === 'PENDING' && canManage"
              text
              type="danger"
              size="small"
              :icon="Close"
              :loading="reviewing === row.id"
              @click="onReject(row)"
            >驳回</el-button>
            <el-button
              v-if="row.status === 'APPROVED' && canManage"
              text
              type="warning"
              size="small"
              :icon="Bottom"
              :loading="reviewing === row.id"
              @click="onShelve(row)"
            >下架</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '暂无入库申请' }}</div>
        </template>
      </el-table>

      <div v-if="pagination.total > pagination.pageSize" class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </div>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="病例详情" width="880">
      <div v-if="detail" class="detail">
        <div class="row"><span class="lbl">病例标题</span><span>{{ detail.desensitizedData?.title || '—' }}</span></div>
        <div class="row"><span class="lbl">提交医生</span><span>{{ detail.teacherName }}</span></div>
        <div class="row"><span class="lbl">来源</span>
          <span>{{ detail.sourceType === 'SCREENING' ? '筛查' : '实训' }}病例 #{{ detail.sourceCaseId }}</span>
        </div>
        <div class="row"><span class="lbl">病例分类</span>
          <span>{{ detail.desensitizedData?.category_text || detail.desensitizedData?.category || '—' }} / {{ detail.desensitizedData?.difficulty_text || detail.desensitizedData?.difficulty || '—' }}</span>
        </div>
        <TeachingDemoBody :source="detail.desensitizedData" />
        <div class="row"><span class="lbl">状态</span>
          <el-tag :type="statusMap[detail.status]?.type || 'info'" size="small">
            {{ statusMap[detail.status]?.label || detail.status }}
          </el-tag>
        </div>
        <div class="row"><span class="lbl">提交时间</span><span>{{ detail.createdAt }}</span></div>
        <div v-if="detail.reviewedAt" class="row"><span class="lbl">审核时间</span><span>{{ detail.reviewedAt }}</span></div>
        <div v-if="detail.reviewerName" class="row"><span class="lbl">审核人</span><span>{{ detail.reviewerName }}</span></div>
        <div v-if="detail.reviewComment" class="row">
          <span class="lbl">{{ detail.status === 'REJECTED' ? '驳回理由' : '审核备注' }}</span>
          <span class="multiline">{{ detail.reviewComment }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 18px 20px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}
.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.muted { color: #86909c; font-size: 12px; font-weight: 400; }
.muted.small { font-size: 11px; }
.ml8 { margin-left: 8px; }
.case-title { color: #1d2129; font-size: 13px; font-weight: 500; }
.small { font-size: 12px; }
.multiline { white-space: pre-wrap; word-break: break-word; }
.empty { padding: 36px 0; text-align: center; color: #c9cdd4; font-size: 14px; }
.pagination { margin-top: 14px; display: flex; justify-content: flex-end; }

.detail .row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
  color: #1d2129;
  border-bottom: 1px dashed #f1f2f5;
}
.detail .row:last-child { border-bottom: none; }
.detail .lbl { width: 110px; flex-shrink: 0; color: #86909c; }
</style>
