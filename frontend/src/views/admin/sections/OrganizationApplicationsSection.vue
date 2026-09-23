<script setup lang="ts">
/**
 * 管理后台 · 机构申请审核
 * - 列表：分页 + 关键词 + 状态筛选 + 机构筛选
 * - 操作：通过 / 驳回（驳回必填理由）
 * - 仅 ADMIN 可点「通过/驳回」（后端二次校验）
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, Check, Close, View } from '@element-plus/icons-vue'
import { OrganizationApi } from '@/api'
import { useReviewActions } from '@/composables/useReviewActions'

type App = OrganizationApi.OrgApplication
type Status = OrganizationApi.AppStatus

const props = defineProps<{
  /** 是否具有审核权限（ADMIN） */
  canManage: boolean
}>()

const list = ref<App[]>([])
const loading = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const filter = reactive({
  keyword: '',
  status: '' as Status | '',
})

const statusMap: Record<Status, { label: string; type: 'info' | 'success' | 'danger' | 'warning' }> = {
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '已通过', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await OrganizationApi.listApplications({
      keyword: filter.keyword || undefined,
      status: filter.status || undefined,
      page: pagination.page,
      pageSize: pagination.pageSize,
    })
    list.value = res?.list || []
    pagination.total = res?.total || 0
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

const clearFilters = () => {
  filter.keyword = ''
  filter.status = ''
  onFilter()
}

/* ========== 通过 / 驳回（共享 composable） ========== */
const { reviewing, approve, reject } = useReviewActions<unknown>({
  reviewFn: (id, payload) => OrganizationApi.reviewApplication(id, payload),
  onAfter: () => fetchList(),
})

const guardManage = (): boolean => {
  if (!props.canManage) {
    ElMessage.warning('仅管理员可审核')
    return false
  }
  return true
}

const onApprove = (row: App) => {
  if (!guardManage()) return
  approve(row.id, `${row.applicantName} → ${row.organizationName}`)
}

const onReject = (row: App) => {
  if (!guardManage()) return
  reject(row.id, `${row.applicantName} → ${row.organizationName}`)
}

/* ========== 详情查看 ========== */
const detailVisible = ref(false)
const detail = ref<App | null>(null)
const showDetail = (row: App) => {
  detail.value = row
  detailVisible.value = true
}

onMounted(fetchList)
</script>

<template>
  <div class="org-apps-section">
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          机构申请审核
          <span class="muted ml8">共 {{ pagination.total }} 条</span>
        </div>
        <div class="card-actions">
          <el-input
            v-model="filter.keyword"
            placeholder="搜索申请人 / 手机号 / 机构 / 理由"
            :prefix-icon="Search"
            clearable
            size="small"
            style="width: 260px"
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
          </el-select>
          <el-button size="small" @click="clearFilters">清除</el-button>
          <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="申请人" width="180">
          <template #default="{ row }">
            <div class="name">{{ row.applicantName || '—' }}</div>
            <div class="muted small">{{ row.applicantPhone || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="organizationName" label="目标机构" min-width="180" show-overflow-tooltip />
        <el-table-column prop="reason" label="申请理由" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status as Status]?.type || 'info'" size="small">
              {{ statusMap[row.status as Status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核人" width="120">
          <template #default="{ row }">
            <span class="muted small">{{ row.reviewerName || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="提交时间" width="170" />
        <el-table-column prop="reviewedAt" label="审核时间" width="170">
          <template #default="{ row }">{{ row.reviewedAt || '—' }}</template>
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
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '暂无申请' }}</div>
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
    <el-dialog v-model="detailVisible" title="申请详情" width="540">
      <div v-if="detail" class="detail">
        <div class="row"><span class="lbl">申请人</span><span>{{ detail.applicantName }}（{{ detail.applicantPhone }}）</span></div>
        <div class="row"><span class="lbl">目标机构</span><span>{{ detail.organizationName }}</span></div>
        <div class="row"><span class="lbl">状态</span>
          <el-tag :type="statusMap[detail.status as Status]?.type || 'info'" size="small">
            {{ statusMap[detail.status as Status]?.label || detail.status }}
          </el-tag>
        </div>
        <div class="row"><span class="lbl">申请理由</span><span class="multiline">{{ detail.reason || '—' }}</span></div>
        <div class="row"><span class="lbl">提交时间</span><span>{{ detail.createdAt }}</span></div>
        <div v-if="detail.reviewedAt" class="row"><span class="lbl">审核时间</span><span>{{ detail.reviewedAt }}</span></div>
        <div v-if="detail.reviewerName" class="row"><span class="lbl">审核人</span><span>{{ detail.reviewerName }}</span></div>
        <div v-if="detail.reviewComment" class="row"><span class="lbl">审核备注</span><span class="multiline">{{ detail.reviewComment }}</span></div>
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
.name { color: #1d2129; font-size: 13px; font-weight: 500; }
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
.detail .lbl { width: 80px; flex-shrink: 0; color: #86909c; }
.detail .multiline { white-space: pre-wrap; word-break: break-word; }
</style>
