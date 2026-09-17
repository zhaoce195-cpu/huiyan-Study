<script setup lang="ts">
/**
 * 登录后未读公告。
 * 只有点「我已知晓」才写已读。关窗、跳转、回车都不会记已读。
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CommonApi } from '@/api'
import { useUserStore } from '@/stores/user'
import {
  clearPendingLoginNotice,
  hasPendingLoginNotice,
  isNoticeRead,
  requestLoginNoticePopup,
  subscribeLoginNotice
} from '@/utils/login-notice'

type Item = CommonApi.NotificationItem

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()

const visible = ref(false)
const loading = ref(false)
const notices = ref<Item[]>([])
const canAck = ref(false)
const shownUserKey = ref('')
let inflight = false
let retryTimer = 0
let skipRetries = 0
let unsub: (() => void) | null = null

const skipPath = (p: string) =>
  p === '/login' || p === '/register' || p === '/apply-student' || p === '/oidc/callback'

const stripNoticeQuery = () => {
  if (route.query.noticePopup == null) return
  const q = { ...route.query }
  delete q.noticePopup
  router.replace({ path: route.path, query: q })
}

const stopRetry = () => {
  if (retryTimer) {
    window.clearTimeout(retryTimer)
    retryTimer = 0
  }
}

const scheduleRetry = (ms = 400) => {
  stopRetry()
  retryTimer = window.setTimeout(() => {
    retryTimer = 0
    void fetchAndShow()
  }, ms)
}

const fetchAndShow = async () => {
  if (!userStore.token) return
  if (skipPath(route.path)) {
    if ((hasPendingLoginNotice() || route.query.noticePopup === '1') && skipRetries < 25) {
      skipRetries += 1
      scheduleRetry(400)
    }
    return
  }
  skipRetries = 0
  if (visible.value || inflight) return

  inflight = true
  loading.value = true
  try {
    const res = await CommonApi.getNotifications(1, 50)
    const unread = (res?.list || []).filter((n) => n && !isNoticeRead(n))
    if (unread.length === 0) {
      if (hasPendingLoginNotice() || route.query.noticePopup === '1') {
        clearPendingLoginNotice()
        stripNoticeQuery()
      }
      return
    }
    notices.value = [...unread].sort((a, b) => {
      if (!!a.isTop !== !!b.isTop) return a.isTop ? -1 : 1
      const ta = new Date(a.publishAt || a.createdAt || 0).getTime()
      const tb = new Date(b.publishAt || b.createdAt || 0).getTime()
      return tb - ta
    })
    visible.value = true
    shownUserKey.value = String(userStore.userInfo?.id || userStore.token || '')
    canAck.value = false
    window.setTimeout(() => {
      canAck.value = true
    }, 800)
  } catch {
    scheduleRetry(800)
  } finally {
    loading.value = false
    inflight = false
  }
}

const onAck = async () => {
  if (!canAck.value) return
  const currentKey = String(userStore.userInfo?.id || userStore.token || '')
  if (!currentKey || currentKey !== shownUserKey.value) return
  const ids = notices.value.map((n) => n.id)
  visible.value = false
  canAck.value = false
  shownUserKey.value = ''
  clearPendingLoginNotice()
  notices.value = []
  stripNoticeQuery()
  if (ids.length === 0) return
  try {
    await CommonApi.markNotificationRead(ids)
  } catch {
    requestLoginNoticePopup()
    scheduleRetry(300)
  }
}

onMounted(() => {
  unsub = subscribeLoginNotice(() => {
    void nextTick(() => fetchAndShow())
  })
  void fetchAndShow()
})
onBeforeUnmount(() => {
  stopRetry()
  unsub?.()
})

watch(
  () => userStore.token,
  (tok) => {
    visible.value = false
    notices.value = []
    canAck.value = false
    shownUserKey.value = ''
    inflight = false
    if (!tok) return
    void fetchAndShow()
  }
)

watch(
  () => [route.path, route.query.noticePopup] as const,
  () => {
    if (!userStore.token) return
    void fetchAndShow()
  }
)
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="ln-mask" role="dialog" aria-modal="true">
      <div class="ln-panel">
        <div class="ln-title-bar">系统公告</div>
        <div v-loading="loading" class="ln-body">
          <div
            v-for="(n, i) in notices"
            :key="n.id"
            class="ln-item"
            :class="{ 'ln-item--first': i === 0 }"
          >
            <div class="ln-head">
              <span v-if="n.isTop" class="ln-top">置顶</span>
              <span class="ln-name">{{ n.title }}</span>
            </div>
            <div class="ln-meta">
              <span>{{ n.publisherName || '系统' }}</span>
              <span class="ln-dot">·</span>
              <span>{{ n.publishAt || n.createdAt }}</span>
            </div>
            <div
              v-if="n.content && n.body && n.content !== n.body"
              class="ln-summary"
            >
              {{ n.content }}
            </div>
            <div class="ln-content" v-html="n.body || n.content || ''"></div>
          </div>
        </div>
        <div class="ln-foot">
          <button type="button" class="ln-ack" :disabled="!canAck" @click="onAck">
            我已知晓
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.ln-mask {
  position: fixed;
  inset: 0;
  z-index: 99999;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.ln-panel {
  width: min(640px, 100%);
  max-height: 80vh;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(22, 119, 255, 0.18), 0 16px 48px rgba(0, 0, 0, 0.28);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ln-title-bar {
  padding: 16px 20px 12px;
  font-size: 18px;
  font-weight: 700;
  color: #1d2129;
  border-bottom: 1px solid #e5e6eb;
}
.ln-body {
  flex: 1;
  min-height: 80px;
  max-height: 56vh;
  overflow-y: auto;
  padding: 8px 20px 12px;
}
.ln-item {
  padding: 14px 0;
  border-top: 1px dashed #e5e6eb;
}
.ln-item--first {
  border-top: none;
  padding-top: 8px;
}
.ln-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.ln-top {
  background: #f53f3f;
  color: #fff;
  border-radius: 3px;
  padding: 1px 6px;
  font-size: 11px;
}
.ln-name {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}
.ln-meta {
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
  margin-bottom: 10px;
}
.ln-content {
  font-size: 14px;
  color: #1d2129;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
.ln-foot {
  padding: 12px 20px 16px;
  border-top: 1px solid #e5e6eb;
  display: flex;
  justify-content: flex-end;
}
.ln-ack {
  height: 36px;
  padding: 0 18px;
  border: none;
  border-radius: 8px;
  background: #1677ff;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.ln-ack:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
