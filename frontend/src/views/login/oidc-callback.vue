<script setup lang="ts">
/**
 * OIDC 回调页
 *
 * Keycloak 登录完成后跳回本页，用授权码换取令牌，再进入应用。
 * 用户在此页面停留时间通常不足一秒，因此只做必要的状态提示。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { LoginApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { handleCallback, parseClaims, frontRoleOf, type OidcConfig } from '@/utils/oidc'

const router = useRouter()
const userStore = useUserStore()

const status = ref<'working' | 'failed'>('working')
const message = ref('正在完成登录…')

onMounted(async () => {
  try {
    const cfg = (await LoginApi.getOidcConfig()) as OidcConfig
    const result = await handleCallback(cfg)

    if (!result.ok || !result.tokens) {
      status.value = 'failed'
      message.value = result.error || '登录失败'
      return
    }

    const accessToken = result.tokens.access_token
    const claims = parseClaims(accessToken)

    // 先落令牌，后续拉取用户资料的请求需要它
    userStore.setUser(
      {
        username: claims?.preferred_username || '',
        name: claims?.name || claims?.preferred_username || '',
        role: frontRoleOf(claims)
      } as any,
      { token: accessToken, refreshToken: result.tokens.refresh_token }
    )

    // 以服务端返回的资料为准：前端解析出的 claims 只用于过渡显示，
    // 角色等权限相关字段必须以后端为权威
    try {
      const profile = await LoginApi.getUserInfo()
      if (profile?.role) {
        userStore.setUser(profile, { token: accessToken })
      }
    } catch {
      /* 拉取失败不阻断登录，后续请求会再触发 */
    }

    if (result.tokens.id_token) {
      sessionStorage.setItem('huiyan_id_token', result.tokens.id_token)
    }

    const { requestLoginNoticePopup, withLoginNoticeQuery } = await import('@/utils/login-notice')
    requestLoginNoticePopup()

    if (userStore.userInfo.mustChangePassword) {
      ElMessage.warning('管理员重置了密码，请先修改后再使用系统')
      const dest = userStore.role === 'patient' ? '/patient/profile' : '/training/profile'
      router.replace(withLoginNoticeQuery(dest, { forcePwd: '1' }))
      return
    }

    ElMessage.success('登录成功')
    router.replace(withLoginNoticeQuery(result.redirectTo || userStore.homePathForRole(userStore.role)))
  } catch (e: any) {
    status.value = 'failed'
    message.value = e?.message || '登录过程出错'
  }
})

const backToLogin = () => router.replace('/login')
</script>

<template>
  <div class="cb-page">
    <div class="cb-card">
      <template v-if="status === 'working'">
        <el-icon class="spin" :size="30"><Loading /></el-icon>
        <p class="msg">{{ message }}</p>
      </template>
      <template v-else>
        <el-result icon="warning" title="登录未完成" :sub-title="message">
          <template #extra>
            <el-button type="primary" @click="backToLogin">返回登录页</el-button>
          </template>
        </el-result>
      </template>
    </div>
  </div>
</template>

<style scoped>
.cb-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #f5f9ff 0%, #ffffff 60%);
}
.cb-card {
  min-width: 320px;
  padding: 32px 40px;
  text-align: center;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.06);
}
.spin {
  color: #409eff;
  animation: rotate 1s linear infinite;
}
.msg {
  margin-top: 14px;
  color: #606266;
  font-size: 14px;
}
@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}
</style>
