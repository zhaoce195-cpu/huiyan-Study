<script setup lang="ts">
/**
 * 登录后系统公告弹窗
 * - 用户每次登录成功后，自动拉取仍在生效的「已发布」公告
 * - 仅展示当前账号尚未读过的公告（已读列表保存在 localStorage，按 用户ID 隔离）
 * - 关闭弹窗时把已展示的公告 ID 写入已读集合，下次登录不再弹出
 *
 * 不修改任何已有接口；不入侵管理员端「公告管理」逻辑。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { CommonApi } from '@/api'
import { useUserStore } from '@/stores/user'

type Notice = CommonApi.Notice

const userStore = useUserStore()
const route = useRoute()

const visible = ref(false)
const loading = ref(false)
const notices = ref<Notice[]>([])

const userKey = computed(() => {
  const u = userStore.userInfo as any
  return String(u?.id || u?.username || '__anon__')
})
const READ_STORAGE_PREFIX = 'huiyan:noticeRead:'
const SHOWN_SESSION_PREFIX = 'huiyan:noticeShown:' // 同一登录会话内不重复弹

const readStorageKey = computed(() => `${READ_STORAGE_PREFIX}${userKey.value}`)
const shownSessionKey = computed(() => `${SHOWN_SESSION_PREFIX}${userKey.value}`)

const loadReadIds = (): Set<number> => {
  try {
    const raw = localStorage.getItem(readStorageKey.value)
    if (!raw) return new Set()
    const arr = JSON.parse(raw) as number[]
    return new Set(arr)
  } catch {
    return new Set()
  }
}

const saveReadIds = (set: Set<number>) => {
  try {
    localStorage.setItem(readStorageKey.value, JSON.stringify([...set]))
  } catch {
    /* ignore quota / privacy mode errors */
  }
}

/** 是否在会话期内已经弹过（避免同一登录里反复触发） */
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

const fetchAndMaybeShow = async () => {
  if (!userStore.token) return
  // 仅 admin / doctor（教师）能访问 /common/notices；学员、患者跳过避免 403
  const role = userStore.role
  if (role !== 'admin' && role !== 'doctor') return
  if (isShownThisSession()) return
  loading.value = true
  // 尝试过即标记，避免任一失败场景下两个 watcher 重复触发再次弹错
  markShownThisSession()
  try {
    // 拉取已发布公告（按更新时间倒序，CommonApi 默认排序即可）
    const res = await CommonApi.getNoticeList({
      status: 'PUBLISHED',
      page: 1,
      pageSize: 20
    })
    const list = res?.list || []
    const readIds = loadReadIds()
    const now = Date.now()
    const visibleNotices = list.filter((n) => {
      if (!n) return false
      if (n.status !== 'PUBLISHED') return false
      // 过滤过期
      if (n.expireAt) {
        const t = new Date(n.expireAt).getTime()
        if (!Number.isNaN(t) && t > 0 && t < now) return false
      }
      // 过滤未到发布时间
      if (n.publishAt) {
        const t = new Date(n.publishAt).getTime()
        if (!Number.isNaN(t) && t > 0 && t > now) return false
      }
      if (readIds.has(n.id)) return false
      return true
    })
    if (visibleNotices.length === 0) return
    // 置顶优先 + 时间倒序
    notices.value = [...visibleNotices].sort((a, b) => {
      if (a.isTop !== b.isTop) return a.isTop ? -1 : 1
      const ta = new Date(a.publishAt || a.updatedAt || a.createdAt || 0).getTime()
      const tb = new Date(b.publishAt || b.updatedAt || b.createdAt || 0).getTime()
      return tb - ta
    })
    visible.value = true
  } catch {
    /* 静默：拉不到公告不应阻塞登录后流程 */
  } finally {
    loading.value = false
  }
}

const onClose = () => {
  // 关闭即视为已读：把弹窗内展示过的全部公告 ID 写入已读集合
  const readIds = loadReadIds()
  notices.value.forEach((n) => readIds.add(n.id))
  saveReadIds(readIds)
  notices.value = []
  visible.value = false
}

/* token 出现时（登录刚完成 或 刷新页面后还原 session）触发一次 */
watch(
  () => userStore.token,
  (tok) => {
    if (tok) {
      // 登录页本身不弹
      if (route.path === '/login' || route.path === '/register') return
      void fetchAndMaybeShow()
    }
  },
  { immediate: true }
)

/* 登录后从 /login 跳到首页时也触发 */
watch(
  () => route.path,
  (p) => {
    if (!userStore.token) return
    if (p === '/login' || p === '/register') return
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
    :before-close="(done: () => void) => { onClose(); done() }"
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
          <span>{{ n.publishAt || n.updatedAt || n.createdAt }}</span>
        </div>
        <div v-if="n.summary" class="ln-summary">{{ n.summary }}</div>
        <div class="ln-content" v-html="n.content || ''"></div>
      </div>
    </div>
    <template #footer>
      <el-button type="primary" @click="onClose">我已知晓</el-button>
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
  padding: 14px 4px 14px 4px;
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
.ln-dot {
  opacity: 0.6;
}
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
