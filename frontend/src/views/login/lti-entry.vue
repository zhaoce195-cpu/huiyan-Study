<script setup lang="ts">
/**
 * LTI 启动落地页
 *
 * 学员在 Moodle 课程页点开活动 → 后端校验平台签发的 id_token →
 * 跳到这里，带上一次性令牌。
 *
 * 令牌只在地址栏出现这一瞬：拿到后立即写入本地存储，
 * 并用 replace 把地址换掉。留在 URL 里会进浏览器历史、
 * 也会随后续请求的 Referer 泄漏出去。
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const message = ref('正在进入慧眼实训平台…')
const failed = ref(false)

onMounted(async () => {
  const token = String(route.query.token || '')
  const caseId = Number(route.query.caseId || 0)

  if (!token) {
    failed.value = true
    message.value = '启动信息缺失，请回到课程页重新进入'
    return
  }

  try {
    localStorage.setItem('huiyan_token', token)
    // 用户信息由令牌换取，不从 URL 传 —— URL 里的东西都不可信
    await userStore.fetchProfile?.()
  } catch {
    failed.value = true
    message.value = '账号信息获取失败，请回到课程页重新进入'
    return
  }

  // replace 而不是 push：带令牌的地址不该留在历史里，
  // 学员按返回键也不该退回到一个含令牌的页面
  if (caseId > 0) {
    router.replace({ path: '/reading', query: { caseId } })
  } else {
    router.replace({ path: '/case-browse' })
  }
})
</script>

<template>
  <div class="wrap">
    <div class="card" :class="{ bad: failed }">
      <div v-if="!failed" class="spinner" />
      <p>{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
.wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #f5f7fa;
}
.card {
  background: #fff;
  padding: 32px 44px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  text-align: center;
  color: #4e5969;
}
.card.bad {
  color: #f56c6c;
}
.spinner {
  width: 28px;
  height: 28px;
  margin: 0 auto 14px;
  border: 3px solid #e5e6eb;
  border-top-color: #1677ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
