<script setup lang="ts">
/**
 * 登录后未读公告弹窗
 * 任意已登录角色（含学员）拉取「我的通知」中未读项；
 * 「我已知晓」写入 biz_notice_read，阅读量 +1。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { CommonApi } from '@/api'
import { useUserStore } from '@/stores/user'

type Item = CommonApi.NotificationItem

const userStore = useUserStore()
const route = useRoute()

const visible = ref(false)
const loading = ref(false)
const notices = ref<Item[]>([])

const userKey = computed(() => {
  const u = userStore.userInfo as any
  return String(u?.id || u?.username || '__anon__')
})
const SHOWN_SESSION_PREFIX = 'huiyan:noticeShown:'
const shownSessionKey = computed(() => `${SHOWN_SESSION_PREFIX}${userKey.value}`)

const isShownThisSession = () => {
  try {
    return sessionStorage.getItem(shownSessionKey.value) === '1'
  } catch {
    return false
  }
}
const markShownThisSession = () => {
  try {
    sessionStorage.setItem(shownSessionKey.value, '1')
  } catch {
    /* ignore */
  }
}

const skipPath = (p: string) =>
  p === '/login' || p === '/register' || p === '/apply-student' || p === '/oidc/callback'

const fetchAndMaybeShow = async () => {
  if (!userStore.token) return
  if (skipPath(route.path)) return
  if (isShownThisSession()) return
  loading.value = true
  markShownThisSession()
  try {
    const res = await CommonApi.getNotifications(1, 50)
    const unread = (res?.list || []).filter((n) => n && !n.read)
    if (unread.length === 0) return
    notices.value = [...unread].sort((a, b) => {
      if (!!a.isTop !== !!b.isTop) return a.isTop ? -1 : 1
      const ta = new Date(a.publishAt || a.createdAt || 0).getTime()
      const tb = new Date(b.publishAt || b.createdAt || 0).getTime()
      return tb - ta
    })
    visible.value = true
  } catch {
    /* 静默：拉不到公告不应阻塞登录后流程 */
  } finally {
    loading.value = false
  }
}

const onAck = async () => {
  const ids = notices.value.map((n) => n.id)
  notices.value = []
  visible.value = false
  if (ids.length === 0) return
  try {
    await CommonApi.markNotificationRead(ids)
  } catch {
    /* 已读失败不挡关闭；下次登录仍会再弹 */
  }
}

watch(
  () => userStore.token,
  (tok) => {
    if (tok && !skipPath(route.path)) void fetchAndMaybeShow()
  },
  { immediate: true }
)

watch(
  () => route.path,
  (p) => {
    if (!userStore.token) return
    if (skipPath(p)) return
    void fetchAndMaybeShow()
  }
)
</script>

<template>
  <el-dialog
    v-model="visible"
    title="系统公告"
    width="640"
    :close-on-click-modal="false"
    :close-on-press-escape="true"
    :show-close="true"
    :before-close="(done: () => void) => { void onAck(); done() }"
    align-center
    class="login-notice-dialog"
  >
    <div v-loading="loading" class="ln-body">
      <div v-if="!loading && notices.length === 0" class="ln-empty">
        暂无新公告
      </div>
      <div
        v-for="(n, i) in notices"
        :key="n.id"
        class="ln-item"
        :class="{ 'ln-item--first': i === 0 }"
      >
        <div class="ln-head">
          <span v-if="n.isTop" class="ln-top">置顶</span>
          <span class="ln-title">{{ n.title }}</span>
        </div>
        <div class="ln-meta">
          <span>{{ n.publisherName || '系统' }}</span>
          <span class="ln-dot">·</span>
          <span>{{ n.publishAt || n.createdAt }}</span>
        </div>
        <div v-if="n.content && n.body && n.content !== n.body" class="ln-summary">{{ n.content }}</div>
        <div class="ln-content" v-html="n.body || n.content || ''"></div>
      </div>
    </div>
    <template #footer>
      <el-button type="primary" @click="onAck">我已知晓</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.login-notice-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
  padding-bottom: 8px;
}
.ln-body {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}
.ln-empty {
  text-align: center;
  color: #c9cdd4;
  padding: 24px 0;
  font-size: 14px;
}
.ln-item {
  padding: 14px 4px;
  border-top: 1px dashed #e5e6eb;
}
.ln-item--first {
  border-top: none;
  padding-top: 4px;
}
.ln-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.ln-top {
  display: inline-block;
  background: #f53f3f;
  color: #fff;
  border-radius: 3px;
  padding: 1px 6px;
  font-size: 11px;
  line-height: 1.4;
}
.ln-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  flex: 1;
  word-break: break-word;
}
.ln-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #86909c;
  margin-bottom: 8px;
}
.ln-dot { opacity: 0.6; }
.ln-summary {
  background: #f7faff;
  border-left: 3px solid #1677ff;
  padding: 8px 12px;
  font-size: 13px;
  color: #4e5969;
  border-radius: 2px;
  margin-bottom: 10px;
}
.ln-content {
  font-size: 14px;
  color: #1d2129;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
