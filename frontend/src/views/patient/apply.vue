<script setup lang="ts">
/**
 * PATIENT 端 · 申请权限（申请加入机构）
 * - 顶部说明卡 + 「发起申请」入口
 * - 我的申请记录（含状态 / 审核备注 / 驳回理由 / 时间）
 * - 审核结果消息（直接读取站内消息 type=org_application 后置展示）
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Refresh, Check } from '@element-plus/icons-vue'
import { OrganizationApi, UserMessageApi } from '@/api'
import { useUserStore } from '@/stores/user'
import OrgApplyDialog from './components/OrgApplyDialog.vue'

type App = OrganizationApi.OrgApplication
type Msg = UserMessageApi.UserMessage

const userStore = useUserStore()
const currentOrg = computed(() => userStore.userInfo.department || '')

/* ========== 我的申请历史 ========== */
const myApps = ref<App[]>([])
const appsLoading = ref(false)
const fetchMyApps = async () => {
  appsLoading.value = true
  try {
    const r = await OrganizationApi.listMyApplications(1, 20)
    myApps.value = r?.list || []
  } catch {
    myApps.value = []
  } finally {
    appsLoading.value = false
  }
}

const statusMap: Record<App['status'], { label: string; type: 'info' | 'success' | 'danger' | 'warning' }> = {
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '已通过', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
}

const hasPending = computed(() => myApps.value.some((a) => a.status === 'PENDING'))

/* ========== 审核结果消息 ========== */
const msgs = ref<Msg[]>([])
const msgsLoading = ref(false)
const unread = ref(0)
const fetchMsgs = async () => {
  msgsLoading.value = true
  try {
    const r = await UserMessageApi.getMyMessages({
      type: 'org_application',
      page: 1,
      pageSize: 20,
    })
    msgs.value = r?.list || []
    unread.value = r?.unread || 0
  } catch {
    msgs.value = []
    unread.value = 0
  } finally {
    msgsLoading.value = false
  }
}

const onMarkAllRead = async () => {
  if (unread.value === 0) {
    ElMessage.info('没有未读消息')
    return
  }
  try {
    await UserMessageApi.markAllRead()
    msgs.value.forEach((m) => {
      if (!m.isRead) m.isRead = true
    })
    unread.value = 0
  } catch {
    /* 已弹错误 */
  }
}

const onMsgClick = async (m: Msg) => {
  if (m.isRead) return
  try {
    await UserMessageApi.markRead(m.id)
    m.isRead = true
    unread.value = Math.max(0, unread.value - 1)
  } catch {
    /* 已弹错误 */
  }
}

/* ========== 申请对话框 ========== */
const applyDialogVisible = ref(false)
const onApplyClick = () => {
  if (hasPending.value) {
    ElMessage.warning('您当前有待审核的申请，请等待审核结果')
    return
  }
  applyDialogVisible.value = true
}
const onApplied = async () => {
  ElMessage.success('申请已提交')
  await Promise.all([fetchMyApps(), userStore.fetchProfile()])
}

const onRefresh = async () => {
  await Promise.all([fetchMyApps(), fetchMsgs(), userStore.fetchProfile()])
}

onMounted(async () => {
  await Promise.all([fetchMyApps(), fetchMsgs()])
})
</script>

<template>
  <div class="patient-apply">
    <header class="page-head">
      <div class="head-left">
        <h2>申请权限</h2>
        <div class="muted">申请加入您所属的机构 · 由机构管理员审核</div>
      </div>
      <div class="head-right">
        <el-button :icon="Refresh" size="small" @click="onRefresh">刷新</el-button>
        <el-button
          type="primary"
          size="small"
          :icon="Promotion"
          :disabled="hasPending"
          @click="onApplyClick"
        >
          {{ hasPending ? '审核中…' : '发起申请' }}
        </el-button>
      </div>
    </header>

    <!-- 当前机构提示 -->
    <section v-if="currentOrg" class="card success-card">
      <div class="success-icon">
        <el-icon :size="22"><Check /></el-icon>
      </div>
      <div class="success-body">
        <div class="success-title">您当前已加入机构</div>
        <div class="success-org">{{ currentOrg }}</div>
      </div>
    </section>
    <section v-else class="card hint-card">
      点击右上角「发起申请」选择您所属的机构提交加入申请。审核通过后，您将享受机构相关服务。
    </section>

    <!-- 我的申请记录 -->
    <section class="card">
      <div class="card-title">我的申请记录</div>
      <div v-if="appsLoading" v-loading="true" class="empty">加载中…</div>
      <div v-else-if="myApps.length === 0" class="empty">
        暂无申请记录
      </div>
      <ul v-else class="app-list">
        <li v-for="a in myApps" :key="a.id" class="app-item">
          <div class="app-line">
            <span class="org">{{ a.organizationName }}</span>
            <el-tag :type="statusMap[a.status].type" size="small">{{ statusMap[a.status].label }}</el-tag>
            <span class="time muted small">{{ a.createdAt }}</span>
          </div>
          <div v-if="a.reason" class="app-sub">
            <span class="lbl">申请理由：</span>
            <span class="multiline">{{ a.reason }}</span>
          </div>
          <div v-if="a.status !== 'PENDING' && a.reviewComment" class="app-sub">
            <span class="lbl">{{ a.status === 'APPROVED' ? '审核备注：' : '驳回理由：' }}</span>
            <span class="multiline">{{ a.reviewComment }}</span>
          </div>
          <div v-if="a.reviewedAt" class="app-sub muted small">
            审核时间：{{ a.reviewedAt }}
          </div>
        </li>
      </ul>
    </section>

    <!-- 审核结果消息 -->
    <section class="card">
      <div class="card-title">
        审核结果消息
        <span v-if="unread > 0" class="unread-tip">{{ unread }} 条未读</span>
        <el-button
          v-if="unread > 0"
          text
          type="primary"
          size="small"
          style="margin-left: auto"
          @click="onMarkAllRead"
        >
          全部已读
        </el-button>
      </div>
      <div v-if="msgsLoading" v-loading="true" class="empty">加载中…</div>
      <div v-else-if="msgs.length === 0" class="empty">暂无审核结果消息</div>
      <ul v-else class="msg-list">
        <li
          v-for="m in msgs"
          :key="m.id"
          class="msg-item"
          :class="{ unread: !m.isRead }"
          @click="onMsgClick(m)"
        >
          <div class="msg-line">
            <span class="msg-title">{{ m.title }}</span>
            <span v-if="!m.isRead" class="dot" />
            <span class="time muted small">{{ m.createdAt }}</span>
          </div>
          <div class="msg-content multiline">{{ m.content }}</div>
        </li>
      </ul>
    </section>

    <OrgApplyDialog v-model:visible="applyDialogVisible" @submitted="onApplied" />
  </div>
</template>

<style scoped>
.patient-apply {
  max-width: 1100px;
  margin: 0 auto;
  padding: 28px 32px 40px;
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
.head-right { display: flex; gap: 8px; }

.card {
  background: #fff;
  border: 1px solid #e6effe;
  border-radius: 14px;
  padding: 18px 22px;
  margin-bottom: 14px;
}
.card-title {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 700;
  color: #1d2129;
  margin-bottom: 14px;
}
.unread-tip {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: #f56c6c;
}

.success-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #f0f9eb;
  border-color: #c2e7b0;
}
.success-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #67c23a;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.success-title { font-size: 13px; color: #67c23a; }
.success-org { font-size: 16px; font-weight: 600; color: #1d2129; margin-top: 2px; }

.hint-card {
  color: #4e5969;
  font-size: 13px;
  line-height: 1.7;
}

.empty {
  padding: 24px 0;
  color: #86909c;
  text-align: center;
  font-size: 13px;
}

.app-list, .msg-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.app-item, .msg-item {
  background: #fafbfc;
  border: 1px solid #eef4ff;
  border-radius: 10px;
  padding: 12px 14px;
}
.msg-item { cursor: pointer; transition: background 0.15s; }
.msg-item:hover { background: #f5f9ff; }
.msg-item.unread { background: #f5f9ff; border-color: #dbe8ff; }

.app-line, .msg-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.app-line .org, .msg-title {
  font-weight: 600;
  color: #1d2129;
  font-size: 13.5px;
}
.app-line .time, .msg-line .time { margin-left: auto; }

.app-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #4e5969;
}
.app-sub .lbl { color: #86909c; margin-right: 4px; }

.msg-content {
  margin-top: 6px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.7;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f5222d;
  display: inline-block;
}

.multiline { white-space: pre-wrap; word-break: break-word; }
.muted { color: #86909c; }
.muted.small { font-size: 11px; }
</style>
