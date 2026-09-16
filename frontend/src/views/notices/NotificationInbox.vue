<script setup lang="ts">
/**
 * 学员 / 教师回看公告通知
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Bell, Refresh, View } from '@element-plus/icons-vue'
import { CommonApi } from '@/api'

const list = ref<CommonApi.NotificationItem[]>([])
const unread = ref(0)
const total = ref(0)
const loading = ref(false)
const page = reactive({ page: 1, pageSize: 20 })

const fetchList = async () => {
  loading.value = true
  try {
    const res = await CommonApi.getNotifications(page.page, page.pageSize)
    list.value = res?.list || []
    unread.value = res?.unread || 0
    total.value = res?.total || 0
  } catch {
    list.value = []
    unread.value = 0
    total.value = 0
  } finally {
    loading.value = false
  }
}

const markRead = async (item: CommonApi.NotificationItem) => {
  if (item.read) return
  try {
    await CommonApi.markNotificationRead([item.id])
    item.read = true
    unread.value = Math.max(0, unread.value - 1)
  } catch {
    /* 静默 */
  }
}

const markAll = async () => {
  if (unread.value === 0) {
    ElMessage.info('暂无未读通知')
    return
  }
  try {
    await CommonApi.markAllNotificationsRead()
    list.value.forEach((n) => (n.read = true))
    unread.value = 0
  } catch {
    /* 已弹错 */
  }
}

const TYPE: Record<string, { label: string; tag: string }> = {
  system: { label: '系统', tag: 'info' },
  screening: { label: '筛查', tag: 'warning' },
  training: { label: '培训', tag: 'success' },
  refer: { label: '转诊', tag: 'danger' }
}

const detailVisible = ref(false)
const detail = ref<CommonApi.NotificationItem | null>(null)
const openDetail = async (item: CommonApi.NotificationItem) => {
  detail.value = item
  detailVisible.value = true
  await markRead(item)
}

onMounted(fetchList)
</script>

<template>
  <div class="inbox">
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <el-icon><Bell /></el-icon>
          通知
          <el-tag v-if="unread > 0" size="small" type="danger" class="ml8">{{ unread }} 条未读</el-tag>
          <span v-else class="muted ml8">全部已读</span>
        </div>
        <div class="card-actions">
          <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
          <el-button size="small" type="primary" :disabled="unread === 0" @click="markAll">
            全部标为已读
          </el-button>
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="list"
        size="small"
        :row-class-name="({ row }: any) => (row.read ? '' : 'unread-row')"
      >
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="(TYPE[row.type]?.tag as any) || 'info'">
              {{ TYPE[row.type]?.label || row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="200">
          <template #default="{ row }">
            <span v-if="row.isTop" class="top">置顶</span>
            <span :class="{ bold: !row.read }">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="摘要" min-width="220" show-overflow-tooltip />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ row.publishAt || row.createdAt }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :class="row.read ? 'muted' : 'unread'">{{ row.read ? '已读' : '未读' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" :icon="View" @click="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '暂无通知' }}</div>
        </template>
      </el-table>

      <div v-if="total > page.pageSize" class="pager">
        <el-pagination
          v-model:current-page="page.page"
          :page-size="page.pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="fetchList"
        />
      </div>
    </div>

    <el-dialog v-model="detailVisible" title="通知详情" width="640">
      <div v-if="detail" class="detail">
        <h3>{{ detail.title }}</h3>
        <div class="meta">
          {{ detail.publisherName || '系统' }} · {{ detail.publishAt || detail.createdAt }}
        </div>
        <div class="body" v-html="detail.body || detail.content || ''"></div>
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
  gap: 10px;
  flex-wrap: wrap;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}
.card-actions { display: flex; gap: 8px; }
.muted { color: #86909c; font-size: 12px; font-weight: 400; }
.ml8 { margin-left: 8px; }
.bold { font-weight: 600; }
.top {
  display: inline-block;
  background: #f53f3f;
  color: #fff;
  border-radius: 3px;
  padding: 0 5px;
  font-size: 11px;
  margin-right: 6px;
}
.unread { color: #f53f3f; font-size: 12px; }
.empty { padding: 36px 0; text-align: center; color: #c9cdd4; }
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
:deep(.unread-row) { background: #f7faff; }
.detail h3 { margin: 0 0 8px; font-size: 18px; }
.detail .meta { font-size: 12px; color: #86909c; margin-bottom: 14px; }
.detail .body { font-size: 14px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; }
</style>
