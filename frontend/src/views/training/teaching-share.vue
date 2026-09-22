<script setup lang="ts">
/**
 * 我的教学分享（教师/管理员）
 * - 临时分享 + 入库申请 一并展示
 * - 状态筛选 + 收回 + 详情查看
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, View, RemoveFilled } from '@element-plus/icons-vue'
import { TeachingApi } from '@/api'
import TeachingDemoBody from './components/TeachingDemoBody.vue'

type Share = TeachingApi.TeachingShare

const list = ref<Share[]>([])
const loading = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const filter = reactive({
  shareType: '' as TeachingApi.ShareType | '',
  status: '' as TeachingApi.ShareStatus | '',
})

const statusMap: Record<string, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
  SHARING: { label: '分享中', type: 'success' },
  EXPIRED: { label: '已过期', type: 'info' },
  REVOKED: { label: '已收回', type: 'info' },
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '已通过', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
  SHELVED: { label: '已下架', type: 'info' },
}

const fetchList = async () => {
  loading.value = true
  try {
    const r = await TeachingApi.getMyShares({
      page: pagination.page,
      pageSize: pagination.pageSize,
      shareType: filter.shareType || undefined,
      status: filter.status || undefined,
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

const onRevoke = async (row: Share) => {
  try {
    await ElMessageBox.confirm(
      `确认收回该临时分享？收回后学员端将立即不可见。`,
      '收回分享',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await TeachingApi.revokeShare(row.id)
    ElMessage.success('已收回')
    fetchList()
  } catch {
    /* 已弹错误 */
  }
}

const detailVisible = ref(false)
const detail = ref<Share | null>(null)
const showDetail = (row: Share) => {
  detail.value = row
  detailVisible.value = true
}

const isExpired = (row: Share) => {
  if (row.shareType !== 'TEMPORARY' || row.status !== 'SHARING') return false
  if (!row.expiredAt) return false
  return new Date(row.expiredAt).getTime() < Date.now()
}

const effectiveStatus = (row: Share): TeachingApi.ShareStatus => {
  if (isExpired(row)) return 'EXPIRED'
  return row.status
}

onMounted(fetchList)
</script>

<template>
  <div class="teaching-share-page">
    <header class="page-head">
      <div class="head-left">
        <h2>我的教学分享</h2>
        <div class="muted">查看您发起的临时分享 / 入库申请记录</div>
      </div>
      <div class="head-right">
        <el-select
          v-model="filter.shareType"
          placeholder="类型"
          clearable
          size="small"
          style="width: 130px"
          @change="onFilter"
        >
          <el-option label="临时分享" value="TEMPORARY" />
          <el-option label="入库申请" value="PERMANENT" />
        </el-select>
        <el-select
          v-model="filter.status"
          placeholder="状态"
          clearable
          size="small"
          style="width: 120px"
          @change="onFilter"
        >
          <el-option label="分享中" value="SHARING" />
          <el-option label="已过期" value="EXPIRED" />
          <el-option label="已收回" value="REVOKED" />
          <el-option label="待审核" value="PENDING" />
          <el-option label="已通过" value="APPROVED" />
          <el-option label="已驳回" value="REJECTED" />
          <el-option label="已下架" value="SHELVED" />
        </el-select>
        <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
      </div>
    </header>

    <div class="card">
      <el-table v-loading="loading" :data="list" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.shareType === 'TEMPORARY' ? 'warning' : 'primary'" effect="plain">
              {{ row.shareType === 'TEMPORARY' ? '临时分享' : '入库申请' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="病例" min-width="220">
          <template #default="{ row }">
            <div class="case-title">{{ row.desensitizedData?.title || '—' }}</div>
            <div v-if="row.desensitizedData?.teaching_points" class="muted small teach-line">
              {{ row.desensitizedData.teaching_points }}
            </div>
            <div class="muted small">
              {{ row.sourceType === 'SCREENING' ? '筛查' : '实训' }}#{{ row.sourceCaseId }}
              · 影像{{ row.desensitizedData?.image_count ?? row.desensitizedData?.imageCount ?? 0 }}张
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusMap[effectiveStatus(row)]?.type || 'info'">
              {{ statusMap[effectiveStatus(row)]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="有效期 / 审核" min-width="200">
          <template #default="{ row }">
            <template v-if="row.shareType === 'TEMPORARY'">
              <div v-if="row.expiredAt" class="small">
                到期：{{ row.expiredAt }}
              </div>
            </template>
            <template v-else>
              <div v-if="row.reviewedAt" class="small">
                审核于 {{ row.reviewedAt }} <span v-if="row.reviewerName">· {{ row.reviewerName }}</span>
              </div>
              <div v-if="row.reviewComment" class="small muted multiline">
                {{ row.status === 'REJECTED' ? '驳回理由：' : '审核备注：' }}{{ row.reviewComment }}
              </div>
            </template>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" :icon="View" @click="showDetail(row)">查看</el-button>
            <el-button
              v-if="row.shareType === 'TEMPORARY' && row.status === 'SHARING' && !isExpired(row)"
              text
              type="danger"
              size="small"
              :icon="RemoveFilled"
              @click="onRevoke(row)"
            >
              收回
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '暂无分享记录' }}</div>
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
    <el-dialog v-model="detailVisible" title="分享详情" width="880">
      <div v-if="detail" class="detail">
        <div class="row">
          <span class="lbl">类型</span>
          <span>{{ detail.shareType === 'TEMPORARY' ? '临时分享' : '入库申请' }}</span>
        </div>
        <div class="row">
          <span class="lbl">状态</span>
          <el-tag size="small" :type="statusMap[effectiveStatus(detail)]?.type || 'info'">
            {{ statusMap[effectiveStatus(detail)]?.label }}
          </el-tag>
        </div>
        <div class="row">
          <span class="lbl">教学标题</span>
          <span>{{ detail.desensitizedData?.title || '—' }}</span>
        </div>
        <TeachingDemoBody :source="detail.desensitizedData" />
        <div class="row">
          <span class="lbl">来源病例</span>
          <span>{{ detail.sourceType === 'SCREENING' ? '筛查' : '实训' }}#{{ detail.sourceCaseId }}</span>
        </div>
        <div class="row" v-if="detail.expiredAt">
          <span class="lbl">到期时间</span>
          <span>{{ detail.expiredAt }}</span>
        </div>
        <div class="row" v-if="detail.reviewComment">
          <span class="lbl">{{ detail.status === 'REJECTED' ? '驳回理由' : '审核备注' }}</span>
          <span class="multiline">{{ detail.reviewComment }}</span>
        </div>
        <div class="row" v-if="detail.reviewedAt">
          <span class="lbl">审核时间</span>
          <span>{{ detail.reviewedAt }}<span v-if="detail.reviewerName"> · {{ detail.reviewerName }}</span></span>
        </div>
        <div class="row">
          <span class="lbl">创建时间</span>
          <span>{{ detail.createdAt }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.teaching-share-page {
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
  margin-bottom: 18px;
  gap: 12px;
  flex-wrap: wrap;
}
.head-left h2 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #1d2129; }
.head-left .muted { color: #86909c; font-size: 13px; }
.head-right { display: flex; gap: 8px; align-items: center; }

.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 16px 18px;
}
.case-title { color: #1d2129; font-weight: 500; }
.teach-line {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 2px 0;
}
.muted { color: #86909c; font-size: 12px; }
.muted.small { font-size: 11px; }
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
.detail .lbl { width: 90px; flex-shrink: 0; color: #86909c; }
</style>
