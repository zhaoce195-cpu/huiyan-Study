<script setup lang="ts">
/**
 * 管理后台 · 学员开户审核（与机构申请并列，独立表）
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, Check, Close, View } from '@element-plus/icons-vue'
import { StudentAppApi } from '@/api'

type App = StudentAppApi.StudentAppItem
type Status = StudentAppApi.StudentAppStatus

const props = defineProps<{
  canManage: boolean
}>()

const list = ref<App[]>([])
const loading = ref(false)
const reviewing = ref<number | null>(null)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filter = reactive({
  keyword: '',
  status: '' as Status | ''
})

const statusMap: Record<Status, { label: string; type: 'info' | 'success' | 'danger' | 'warning' }> = {
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '已通过', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' }
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await StudentAppApi.listStudentApplications({
      keyword: filter.keyword || undefined,
      status: filter.status || undefined,
      page: pagination.page,
      pageSize: pagination.pageSize
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

const guardManage = (): boolean => {
  if (!props.canManage) {
    ElMessage.warning('仅管理员可审核')
    return false
  }
  return true
}

const onApprove = async (row: App) => {
  if (!guardManage()) return
  let comment = ''
  try {
    const result = await ElMessageBox.prompt(
      `确认通过「${row.realName} / ${row.phone}」的开户申请？将生成学员账号并通过短信告知初密。`,
      '审核通过',
      {
        confirmButtonText: '通过并开户',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '审核备注（选填）',
        type: 'success'
      }
    )
    comment = (result.value || '').trim()
  } catch {
    return
  }
  reviewing.value = row.id
  try {
    const res = await StudentAppApi.reviewStudentApplication(row.id, { accept: true, comment })
    if (res?.tempPassword) {
      await ElMessageBox.alert(
        `账号：${res.accountUsername || row.phone}\n初密：${res.tempPassword}\n\n已短信 / 站内信告知申请人，请提醒从学生入口登录后立即改密。`,
        '已开通学员账号',
        { confirmButtonText: '我已知晓', type: 'success' }
      )
    }
    fetchList()
  } catch {
    /* 拦截器已弹错 */
  } finally {
    reviewing.value = null
  }
}

const onReject = async (row: App) => {
  if (!guardManage()) return
  let comment = ''
  try {
    const result = await ElMessageBox.prompt(
      `驳回「${row.realName}」的开户申请，理由将短信发给 ${row.phone}。`,
      '审核驳回',
      {
        confirmButtonText: '驳回',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '驳回理由（必填）',
        inputValidator: (v: string) => !!v?.trim() || '驳回必须填写理由',
        type: 'warning'
      }
    )
    comment = (result.value || '').trim()
  } catch {
    return
  }
  reviewing.value = row.id
  try {
    await StudentAppApi.reviewStudentApplication(row.id, { accept: false, comment })
    fetchList()
  } catch {
    /* 已弹错 */
  } finally {
    reviewing.value = null
  }
}

const detailVisible = ref(false)
const detail = ref<App | null>(null)
const showDetail = (row: App) => {
  detail.value = row
  detailVisible.value = true
}

onMounted(fetchList)
</script>

<template>
  <div class="stu-apps-section">
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          学员开户审核
          <span class="muted ml8">与机构申请分表，共 {{ pagination.total }} 条</span>
        </div>
        <div class="card-actions">
          <el-input
            v-model="filter.keyword"
            placeholder="姓名 / 手机 / 科室 / 理由"
            :prefix-icon="Search"
            clearable
            size="small"
            style="width: 240px"
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
            <div class="name">{{ row.realName || '—' }}</div>
            <div class="muted small">{{ row.phone }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="科室" width="140" />
        <el-table-column prop="reason" label="申请理由" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status as Status]?.type || 'info'" size="small">
              {{ statusMap[row.status as Status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开通账号" width="140">
          <template #default="{ row }">
            <span class="muted small">{{ row.accountUsername || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="审核人" width="110">
          <template #default="{ row }">
            <span class="muted small">{{ row.reviewerName || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="提交时间" width="170" />
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
          <div class="empty">{{ loading ? '加载中…' : '暂无开户申请' }}</div>
        </template>
      </el-table>

      <div v-if="pagination.total > pagination.pageSize" class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          background
          layout="total, sizes, prev, pager, next"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </div>

    <el-dialog v-model="detailVisible" title="开户申请详情" width="540">
      <div v-if="detail" class="detail">
        <div class="row"><span class="lbl">申请人</span><span>{{ detail.realName }}（{{ detail.phone }}）</span></div>
        <div class="row"><span class="lbl">科室</span><span>{{ detail.department || '—' }}</span></div>
        <div class="row"><span class="lbl">状态</span>
          <el-tag :type="statusMap[detail.status as Status]?.type || 'info'" size="small">
            {{ statusMap[detail.status as Status]?.label || detail.status }}
          </el-tag>
        </div>
        <div class="row"><span class="lbl">申请理由</span><span class="multiline">{{ detail.reason || '—' }}</span></div>
        <div class="row"><span class="lbl">提交时间</span><span>{{ detail.createdAt }}</span></div>
        <div v-if="detail.accountUsername" class="row"><span class="lbl">开通账号</span><span>{{ detail.accountUsername }}</span></div>
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
.card-actions { display: flex; align-items: center; gap: 8px; }
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
