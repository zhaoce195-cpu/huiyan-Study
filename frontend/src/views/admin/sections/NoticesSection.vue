<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Search, Edit, Delete, View, Bell } from '@element-plus/icons-vue'
import { CommonApi } from '@/api'

type Notice = CommonApi.Notice
type NoticeType = CommonApi.NoticeType
type NoticeStatus = CommonApi.NoticeStatus

const props = defineProps<{
  /** 是否具有发布/编辑权限（TEACHER/ADMIN） */
  canManage: boolean
  /** 是否具有删除权限（仅 ADMIN） */
  canDelete: boolean
}>()

/* ========== 公告分页 ========== */

const list = ref<Notice[]>([])
const loading = ref(false)
const filter = reactive({
  keyword: '',
  noticeType: '' as NoticeType | '',
  status: '' as NoticeStatus | ''
})
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const typeMap: Record<NoticeType, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
  SYSTEM: { label: '系统', type: 'info' },
  TRAINING: { label: '培训', type: 'primary' },
  SCREENING: { label: '筛查', type: 'success' },
  EXAM: { label: '考核', type: 'warning' }
}
const statusMap: Record<NoticeStatus, { label: string; type: 'info' | 'success' | 'warning' }> = {
  DRAFT: { label: '草稿', type: 'info' },
  PUBLISHED: { label: '已发布', type: 'success' },
  ARCHIVED: { label: '已归档', type: 'warning' }
}

const fetchList = async () => {
  if (!props.canManage) return
  loading.value = true
  try {
    const res = await CommonApi.getNoticeList({
      keyword: filter.keyword || undefined,
      noticeType: filter.noticeType || undefined,
      status: filter.status || undefined,
      page: pagination.page,
      pageSize: pagination.pageSize
    })
    list.value = res?.list || []
    pagination.total = res?.total || 0
  } catch (e: any) {
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

/* ========== 详情查看 ========== */

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<Notice | null>(null)
const showDetail = async (n: Notice) => {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await CommonApi.getNoticeDetail(n.id)
  } catch {
    detail.value = n
  } finally {
    detailLoading.value = false
  }
}

/* ========== 新建 / 编辑 ========== */

const editVisible = ref(false)
const editLoading = ref(false)
const editFormRef = ref<FormInstance>()
const VISIBLE_ROLE_OPTIONS = [
  { label: '学员 STUDENT', value: 'STUDENT' },
  { label: '教师 TEACHER', value: 'TEACHER' },
  { label: '管理员 ADMIN', value: 'ADMIN' }
]
const visibleRoleChecks = ref<string[]>(['STUDENT'])

const syncVisibleRolesFromChecks = () =>
  visibleRoleChecks.value.length === 0 || visibleRoleChecks.value.length === 3
    ? ''
    : visibleRoleChecks.value.join(',')

const parseVisibleRoles = (raw?: string) => {
  const parts = (raw || '')
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter((s) => ['STUDENT', 'TEACHER', 'ADMIN'].includes(s))
  return parts
}

const editForm = reactive<CommonApi.NoticeSaveParams & { id?: number }>({
  id: undefined,
  title: '',
  summary: '',
  content: '',
  coverUrl: '',
  noticeType: 'SYSTEM',
  status: 'DRAFT',
  visibleRoles: '',
  isTop: false,
  publishAt: null,
  expireAt: null
})
const editRules: FormRules = {
  title: [{ required: true, message: '请输入公告标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入公告正文', trigger: 'blur' }],
  noticeType: [{ required: true, message: '请选择公告类型', trigger: 'change' }]
}

const isEditing = computed(() => editForm.id != null)

const openCreate = () => {
  editForm.id = undefined
  editForm.title = ''
  editForm.summary = ''
  editForm.content = ''
  editForm.coverUrl = ''
  editForm.noticeType = 'SYSTEM'
  editForm.status = 'DRAFT'
  editForm.visibleRoles = 'STUDENT'
  editForm.isTop = false
  editForm.publishAt = null
  editForm.expireAt = null
  visibleRoleChecks.value = ['STUDENT']
  editVisible.value = true
}
const openEdit = (n: Notice) => {
  editForm.id = n.id
  editForm.title = n.title
  editForm.summary = n.summary || ''
  editForm.content = n.content || ''
  editForm.coverUrl = n.coverUrl || ''
  editForm.noticeType = n.noticeType
  editForm.status = n.status
  editForm.visibleRoles = n.visibleRoles || ''
  visibleRoleChecks.value = n.visibleRoles ? parseVisibleRoles(n.visibleRoles) : []
  editForm.isTop = n.isTop
  editForm.publishAt = n.publishAt || null
  editForm.expireAt = n.expireAt || null
  editVisible.value = true
}

const submitEdit = async () => {
  if (!editFormRef.value) return
  await editFormRef.value.validate(async (valid) => {
    if (!valid) return
    editLoading.value = true
    try {
      const payload: CommonApi.NoticeSaveParams = {
        title: editForm.title,
        summary: editForm.summary || undefined,
        content: editForm.content,
        coverUrl: editForm.coverUrl || undefined,
        noticeType: editForm.noticeType,
        status: editForm.status,
        visibleRoles: syncVisibleRolesFromChecks(),
        isTop: editForm.isTop,
        publishAt: editForm.publishAt || null,
        expireAt: editForm.expireAt || null
      }
      if (editForm.id != null) {
        await CommonApi.updateNotice(editForm.id, payload)
      } else {
        await CommonApi.createNotice(payload)
      }
      editVisible.value = false
      fetchList()
    } catch (e: any) {
      /* request.ts 已弹错误提示 */
    } finally {
      editLoading.value = false
    }
  })
}

const removeNotice = async (n: Notice) => {
  try {
    await ElMessageBox.confirm(`确定删除公告「${n.title}」？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await CommonApi.deleteNotice(n.id)
    fetchList()
  } catch {
    /* 已弹错误提示 */
  }
}

/* ========== 我的通知 ========== */

const inbox = ref<CommonApi.NotificationItem[]>([])
const inboxUnread = ref(0)
const inboxTotal = ref(0)
const inboxLoading = ref(false)
const inboxPage = reactive({ page: 1, pageSize: 20 })

const fetchInbox = async () => {
  inboxLoading.value = true
  try {
    const res = await CommonApi.getNotifications(inboxPage.page, inboxPage.pageSize)
    inbox.value = res?.list || []
    inboxUnread.value = res?.unread || 0
    inboxTotal.value = res?.total || 0
  } catch {
    inbox.value = []
    inboxUnread.value = 0
    inboxTotal.value = 0
  } finally {
    inboxLoading.value = false
  }
}


const markRead = async (item: CommonApi.NotificationItem) => {
  if (item.read) return
  try {
    await CommonApi.markNotificationRead([item.id])
    item.read = true
    inboxUnread.value = Math.max(0, inboxUnread.value - 1)
  } catch {
    /* 静默：标记失败不影响阅读内容本身 */
  }
}

const markAllRead = async () => {
  if (inboxUnread.value === 0) {
    ElMessage.info('暂无未读消息')
    return
  }
  try {
    await CommonApi.markAllNotificationsRead()
    inbox.value.forEach((n) => (n.read = true))
    inboxUnread.value = 0
    ElMessage.success('已全部标为已读')
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

// 用函数而不是直接索引：后端将来新增消息类型时，前端拿到的是
// 一个字典里没有的字符串，直接索引会得到 undefined 并渲染成空白。
// 这里回退到原始值，至少还能看出是什么类型。
const INBOX_TYPE: Record<string, { label: string; tag: string }> = {
  system: { label: '系统', tag: 'info' },
  screening: { label: '筛查', tag: 'warning' },
  training: { label: '培训', tag: 'success' },
  refer: { label: '转诊', tag: 'danger' }
}
const inboxTypeLabel = (t: string) => INBOX_TYPE[t]?.label || t
const inboxTypeTag = (t: string) => INBOX_TYPE[t]?.tag || 'info'

const onInboxPage = (p: number) => {
  inboxPage.page = p
  fetchInbox()
}

onMounted(() => {
  if (props.canManage) fetchList()
  fetchInbox()
})
</script>

<template>
  <div class="notices-section">
    <!-- 我的消息：按 visible_roles 过滤后的站内消息，点行即标记已读。
         已读状态落在 biz_notice_read，重启不丢。
         机构权限申请等工作流将来以新的消息类型汇入同一收件箱，
         而不是再开一块独立面板。 -->
    <div class="card inbox-card">
      <div class="card-header">
        <div class="card-title">
          <el-icon><Bell /></el-icon>
          我的消息
          <el-tag v-if="inboxUnread > 0" size="small" type="danger" class="ml8">
            {{ inboxUnread }} 条未读
          </el-tag>
          <span v-else class="muted ml8">全部已读</span>
        </div>
        <div class="card-actions">
          <el-button :icon="Refresh" size="small" @click="fetchInbox">刷新</el-button>
          <el-button
            size="small"
            type="primary"
            :disabled="inboxUnread === 0"
            @click="markAllRead"
          >
            全部标为已读
          </el-button>
        </div>
      </div>

      <el-table
        v-loading="inboxLoading"
        :data="inbox"
        size="small"
        :row-class-name="({ row }: any) => (row.read ? '' : 'unread-row')"
        @row-click="markRead"
      >
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="(inboxTypeTag(row.type) as any)">
              {{ inboxTypeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="180">
          <template #default="{ row }">
            <span :class="{ bold: !row.read }">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip />
        <el-table-column prop="createdAt" label="时间" width="170" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :class="row.read ? 'muted' : 'unread-dot'">
              {{ row.read ? '已读' : '未读' }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="inbox.length === 0 && !inboxLoading" class="empty-hint">
        暂无消息
      </div>

      <el-pagination
        v-if="inboxTotal > inboxPage.pageSize"
        class="pager"
        layout="prev, pager, next"
        :current-page="inboxPage.page"
        :page-size="inboxPage.pageSize"
        :total="inboxTotal"
        @current-change="onInboxPage"
      />
    </div>

    <!-- 公告管理 -->
    <div v-if="canManage" class="card">
      <div class="card-header">
        <div class="card-title">
          公告管理
          <span class="muted ml8">共 {{ pagination.total }} 条</span>
        </div>
        <div class="card-actions">
          <el-input
            v-model="filter.keyword"
            placeholder="搜索标题"
            :prefix-icon="Search"
            clearable
            size="small"
            style="width: 200px"
            @change="onFilter"
            @clear="onFilter"
          />
          <el-select v-model="filter.noticeType" placeholder="类型" clearable size="small" style="width: 110px" @change="onFilter">
            <el-option label="系统" value="SYSTEM" />
            <el-option label="培训" value="TRAINING" />
            <el-option label="筛查" value="SCREENING" />
            <el-option label="考核" value="EXAM" />
          </el-select>
          <el-select v-model="filter.status" placeholder="状态" clearable size="small" style="width: 110px" @change="onFilter">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已发布" value="PUBLISHED" />
            <el-option label="已归档" value="ARCHIVED" />
          </el-select>
          <el-button :icon="Refresh" size="small" @click="fetchList">刷新</el-button>
          <el-button :icon="Plus" size="small" type="primary" @click="openCreate">发布公告</el-button>
        </div>
      </div>
      <el-table v-loading="loading" :data="list" size="small" stripe>
        <el-table-column type="index" label="#" width="56" />
        <el-table-column label="标题" min-width="240">
          <template #default="{ row }">
            <span v-if="row.isTop" class="top-flag">置顶</span>
            <span class="notice-title-text">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeMap[row.noticeType as NoticeType]?.type || 'info'" size="small">
              {{ typeMap[row.noticeType as NoticeType]?.label || row.noticeType }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status as NoticeStatus]?.type || 'info'" size="small" effect="dark">
              {{ statusMap[row.status as NoticeStatus]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="可见角色" width="160">
          <template #default="{ row }">
            <span class="muted">{{ row.visibleRoles || '全员' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="publisherName" label="发布人" width="100" />
        <el-table-column prop="viewCount" label="阅读量" width="80" />
        <el-table-column prop="publishAt" label="发布时间" width="160">
          <template #default="{ row }">{{ row.publishAt || '—' }}</template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="160" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" :icon="View" size="small" @click="showDetail(row)">查看</el-button>
            <el-button text type="warning" :icon="Edit" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button
              v-if="canDelete"
              text
              type="danger"
              :icon="Delete"
              size="small"
              @click="removeNotice(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">{{ loading ? '加载中…' : '暂无公告' }}</div>
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

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="公告详情" width="640">
      <div v-loading="detailLoading">
        <div v-if="detail" class="notice-detail">
          <div class="nd-head">
            <span v-if="detail.isTop" class="top-flag">置顶</span>
            <h3>{{ detail.title }}</h3>
            <div class="nd-meta">
              <el-tag size="small" :type="typeMap[detail.noticeType]?.type || 'info'">
                {{ typeMap[detail.noticeType]?.label || detail.noticeType }}
              </el-tag>
              <el-tag size="small" :type="statusMap[detail.status]?.type || 'info'" effect="dark">
                {{ statusMap[detail.status]?.label || detail.status }}
              </el-tag>
              <span class="muted">{{ detail.publisherName }} · {{ detail.publishAt || detail.updatedAt }}</span>
              <span class="muted">阅读 {{ detail.viewCount }}</span>
            </div>
          </div>
          <p v-if="detail.summary" class="nd-summary">{{ detail.summary }}</p>
          <div class="nd-body" v-html="detail.content || '（无正文）'"></div>
        </div>
      </div>
    </el-dialog>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="editVisible"
      :title="isEditing ? '编辑公告' : '发布公告'"
      width="640"
      :close-on-click-modal="false"
    >
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="100px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="editForm.title" placeholder="不超过 128 字" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="类型" prop="noticeType">
          <el-select v-model="editForm.noticeType" style="width: 200px">
            <el-option label="系统" value="SYSTEM" />
            <el-option label="培训" value="TRAINING" />
            <el-option label="筛查" value="SCREENING" />
            <el-option label="考核" value="EXAM" />
          </el-select>
          <el-select v-model="editForm.status" style="width: 200px; margin-left: 12px">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已发布" value="PUBLISHED" />
            <el-option label="已归档" value="ARCHIVED" />
          </el-select>
          <el-checkbox v-model="editForm.isTop" style="margin-left: 12px">置顶</el-checkbox>
        </el-form-item>
        <el-form-item label="可见角色">
          <el-checkbox-group v-model="visibleRoleChecks">
            <el-checkbox v-for="o in VISIBLE_ROLE_OPTIONS" :key="o.value" :label="o.value">
              {{ o.label }}
            </el-checkbox>
          </el-checkbox-group>
          <div class="muted" style="margin-top: 4px">
            勾选学员后，对方登录会弹出未读公告。全不选或全选 = 全员可见。
          </div>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="editForm.summary" type="textarea" :rows="2" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="正文" prop="content">
          <el-input v-model="editForm.content" type="textarea" :rows="8" />
        </el-form-item>
        <el-form-item label="发布时间">
          <el-date-picker
            v-model="editForm.publishAt"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="留空 = 立即发布"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="过期时间">
          <el-date-picker
            v-model="editForm.expireAt"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="留空 = 永久"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="submitEdit">
          {{ isEditing ? '保存' : '发布' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 18px;
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
.muted {
  color: #86909c;
  font-size: 12px;
  font-weight: 400;
}
.ml8 {
  margin-left: 8px;
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
.top-flag {
  display: inline-block;
  background: #f53f3f;
  color: #fff;
  border-radius: 3px;
  padding: 1px 6px;
  font-size: 11px;
  margin-right: 6px;
}
.notice-title-text {
  font-weight: 500;
  color: #1d2129;
}
:deep(.unread-row) td {
  background: #fff7e6 !important;
}
/* 未读行整行可点，点一下即标记已读 —— 需要有可点的暗示 */
:deep(.unread-row) {
  cursor: pointer;
}
.bold {
  font-weight: 600;
  color: #1d2129;
}
.unread-dot {
  color: #f56c6c;
  font-weight: 600;
}
.empty-hint {
  padding: 28px 0;
  text-align: center;
  color: #86909c;
  font-size: 13px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.nd-head h3 {
  margin: 8px 0 6px;
  font-size: 18px;
}
.nd-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.nd-summary {
  background: #f7faff;
  border-left: 3px solid #1677ff;
  padding: 8px 12px;
  font-size: 13px;
  color: #4e5969;
  margin: 0 0 12px;
}
.nd-body {
  font-size: 14px;
  color: #1d2129;
  line-height: 1.8;
  white-space: pre-wrap;
}

/* 「我的消息」改为占位提示后所用样式 */
.placeholder {
  text-align: center;
  padding: 36px 16px;
  color: #4e5969;
}
.placeholder-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: #eef4ff;
  color: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.placeholder-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 6px;
}
.placeholder-desc {
  font-size: 13px;
  color: #86909c;
  line-height: 1.7;
}
</style>
