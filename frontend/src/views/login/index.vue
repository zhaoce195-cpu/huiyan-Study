<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElLoading, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { LoginApi } from '@/api'
import { startLogin } from '@/utils/oidc'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

/* 登录入口：学生 / 教师（含管理员）——不依赖用户名区分角色 */
type LoginEntrance = 'student' | 'teacher'
const loginRole = ref<LoginEntrance>('student')

/**
 * 安全整改（报告 P0）：登录页不得预填或展示任何账号密码。
 * 原实现把演示账号与明文密码写在前端源码里，构建产物可直接读出。
 * 演示环境的账号应由环境隔离与专用演示 Realm 提供，不进入生产代码。
 */
const form = reactive<LoginApi.LoginParams>({
  username: '',
  password: '',
  remember: false
})

// 切换入口时清空已输入的凭据，避免误用另一入口的账号
watch(loginRole, () => {
  form.username = ''
  form.password = ''
})

const goRegister = () => router.push('/register')
const goApplyStudent = () => router.push('/apply-student')

/* ========== 统一身份登录（OIDC 授权码 + PKCE） ========== */
// 首次登录强制改密、账号锁定提示等必需动作只能在 Keycloak 登录页完成，
// 表单直传口令拿不到这些能力，因此迁移后应优先走这条路径。
const oidcEnabled = ref(false)
const oidcLoading = ref(false)

onMounted(async () => {
  try {
    const cfg = await LoginApi.getOidcConfig()
    oidcEnabled.value = !!cfg?.enabled
  } catch {
    oidcEnabled.value = false
  }
})

const goUnifiedLogin = async () => {
  oidcLoading.value = true
  try {
    const cfg = await LoginApi.getOidcConfig()
    const redirect = (route.query.redirect as string) || ''
    await startLogin(cfg as any, redirect && redirect !== '/login' ? redirect : '/')
  } catch (e: any) {
    ElMessage.error(e?.message || '无法跳转到统一登录页面')
    oidcLoading.value = false
  }
}

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少 6 位', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    const loadingInstance = ElLoading.service({
      lock: true,
      text: '正在登录中…',
      background: 'rgba(255,255,255,0.6)'
    })
    try {
      // 登录前先清掉旧的本地缓存，避免「上一个账号的角色」泄漏
      userStore.clear()

      const res = await LoginApi.login({ ...form })
      if (!res?.token) {
        throw new Error('登录响应缺少 token')
      }

      let userInfo = res.userInfo
      // 后端响应若缺 user_info，兜底再拉一次 /user/profile
      if (!userInfo || !userInfo.role) {
        localStorage.setItem('huiyan_token', res.token)
        const u = await LoginApi.getUserInfo()
        if (!u || !u.role) throw new Error('无法获取用户信息')
        userInfo = u
      }

      // 入口校验：所选入口需与账号角色匹配（不依赖用户名）
      const role = userInfo.role
      const entranceOk =
        loginRole.value === 'student'
          ? role === 'trainee'
          : role === 'doctor' || role === 'admin'
      if (!entranceOk) {
        userStore.clear()
        localStorage.removeItem('huiyan_token')
        throw new Error(
          loginRole.value === 'student'
            ? '该账号不是学生账号，请切换到「教师入口」登录'
            : '该账号不是教师/管理员账号，请切换到「学生入口」登录'
        )
      }

      userStore.setUser(userInfo, {
        token: res.token,
        refreshToken: res.refreshToken
      })

      ElMessage.success(`欢迎回来，${userInfo.name || userInfo.username || form.username}`)

      if (userInfo.mustChangePassword) {
        ElMessage.warning('管理员重置了密码，请先修改后再使用系统')
        const dest = userInfo.role === 'patient' ? '/patient/profile' : '/training/profile'
        router.replace({ path: dest, query: { forcePwd: '1' } })
        return
      }

      // 角色对应默认首页；query.redirect 仅在与角色权限不冲突时使用
      const queryRedirect = (route.query.redirect as string) || ''
      const homePath = userStore.homePathForRole(userInfo.role)
      const redirect = queryRedirect && queryRedirect !== '/login'
        ? queryRedirect
        : homePath
      router.replace(redirect)
    } catch (e: any) {
      // 迁移后的账号首次登录必须改密，而改密只能在统一登录页完成。
      // 后端用 409 + SETUP_REQUIRED 与「口令错误」区分开，
      // 这里直接把用户送过去，不让他卡在「密码错误」上。
      const detail = e?.response?.data?.detail || e?.detail
      const needSetup =
        e?.status === 409 ||
        e?.response?.status === 409 ||
        detail?.code === 'SETUP_REQUIRED'
      if (needSetup) {
        ElMessage.warning(
          detail?.message || '该账号需要先完成首次设置，正在前往统一登录页…'
        )
        await goUnifiedLogin()
        return
      }
      const msg = e?.message || '登录失败，请检查账号密码'
      if (!msg.includes('请求失败')) {
        ElMessage.error(msg)
      }
    } finally {
      loading.value = false
      loadingInstance.close()
    }
  })
}
</script>

<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-circle c1"></div>
      <div class="bg-circle c2"></div>
      <div class="bg-circle c3"></div>
    </div>

    <div class="login-container">
      <div class="login-left">
        <div class="brand">
          <div class="logo">
            <svg viewBox="0 0 48 48" width="48" height="48">
              <circle cx="24" cy="24" r="22" fill="#2563eb" opacity="0.12" />
              <circle cx="24" cy="24" r="14" fill="none" stroke="#2563eb" stroke-width="2.5" />
              <circle cx="24" cy="24" r="6" fill="#2563eb" />
              <circle cx="24" cy="24" r="2.5" fill="#fff" />
            </svg>
          </div>
          <div class="brand-text">
            <h1>慧眼 AI 教学实训平台</h1>
            <p>Huiyan AI · 眼科阅片教学实训平台</p>
          </div>
        </div>
        <div class="features">
          <div class="feature-item">
            <span class="dot dot-blue"></span>
            小而稀疏病灶 · 漏检训练与能力评估
          </div>
          <div class="feature-item">
            <span class="dot dot-green"></span>
            尺寸分层金标准 · 病灶级判读评分
          </div>
          <div class="feature-item">
            <span class="dot dot-orange"></span>
            阅片标注训练 · 成长曲线与能力认证
          </div>
        </div>
        <div class="footer-tip">© 慧眼 · 医学教育与能力评估平台</div>
      </div>

      <div class="login-right">
        <div class="login-card">
          <div class="role-tabs">
            <button
              type="button"
              class="role-tab"
              :class="{ active: loginRole === 'student' }"
              @click="loginRole = 'student'"
            >
              学生入口
            </button>
            <button
              type="button"
              class="role-tab"
              :class="{ active: loginRole === 'teacher' }"
              @click="loginRole = 'teacher'"
            >
              教师入口
            </button>
          </div>
          <div class="card-header">
            <h2>{{ loginRole === 'student' ? '学生登录' : '教师登录' }}</h2>
            <p>
              {{
                loginRole === 'student'
                  ? '住培医师 / 学员 · 进入阅片训练'
                  : '带教医师 / 管理员 · 进入教学与管理'
              }}
            </p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            size="large"
            @keyup.enter="handleLogin"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="账户 / 医师工号"
                :prefix-icon="User"
                clearable
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="登录密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>

            <div class="login-extra">
              <el-checkbox v-model="form.remember" label="记住账户" />
              <a v-if="loginRole === 'student'" class="link" @click="goApplyStudent">申请学员账号</a>
              <a v-else class="link" @click="goRegister">立即注册</a>
            </div>

            <el-button
              type="primary"
              size="large"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>

            <div v-if="oidcEnabled" class="oidc-block">
              <div class="oidc-divider"><span>或</span></div>
              <el-button
                class="oidc-btn"
                size="large"
                :loading="oidcLoading"
                @click="goUnifiedLogin"
              >
                使用统一身份登录
              </el-button>
              <div class="oidc-hint">
                首次登录、修改密码或账号被锁定时，请走统一身份登录
              </div>
            </div>

            <div class="tip">
              账号由所在机构管理员分配；忘记密码请联系管理员重置
            </div>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.oidc-block {
  margin-top: 14px;
}
.oidc-divider {
  position: relative;
  text-align: center;
  margin: 10px 0;
  color: #a8abb2;
  font-size: 12px;
}
.oidc-divider::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  border-top: 1px solid #e4e7ed;
}
.oidc-divider span {
  position: relative;
  padding: 0 10px;
  background: #fff;
}
.oidc-btn {
  width: 100%;
}
.oidc-hint {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
  text-align: center;
  line-height: 1.6;
}

.login-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: linear-gradient(135deg, #eef4ff 0%, #f5f9ff 60%, #ffffff 100%);
}

.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.bg-circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.45;
}
.c1 {
  width: 520px;
  height: 520px;
  background: #c7dbff;
  top: -120px;
  left: -120px;
}
.c2 {
  width: 420px;
  height: 420px;
  background: #d6f0ff;
  bottom: -100px;
  right: -80px;
}
.c3 {
  width: 280px;
  height: 280px;
  background: #e6f7ec;
  top: 40%;
  left: 50%;
}

.login-container {
  position: relative;
  z-index: 2;
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  align-items: center;
  padding: 0 6vw;
  gap: 4vw;
  max-width: 1440px;
  margin: 0 auto;
}

.login-left {
  display: flex;
  flex-direction: column;
  gap: 32px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 16px;
}
.logo {
  width: 56px;
  height: 56px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 6px 24px rgba(22, 119, 255, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand-text h1 {
  margin: 0;
  font-size: 30px;
  letter-spacing: 2px;
  color: #1d2129;
  font-weight: 700;
}
.brand-text p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #86909c;
  letter-spacing: 1.4px;
}
.features {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(22, 119, 255, 0.08);
  border-radius: 14px;
  font-size: 14px;
  color: #4e5969;
}
.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot-blue {
  background: #1677ff;
}
.dot-green {
  background: #00b42a;
}
.dot-orange {
  background: #ff7d00;
}
.footer-tip {
  font-size: 12px;
  color: #86909c;
}

.login-right {
  display: flex;
  justify-content: center;
}
.login-card {
  width: 100%;
  max-width: 420px;
  padding: 40px 36px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 18px 60px rgba(22, 119, 255, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(22, 119, 255, 0.06);
}
.role-tabs {
  display: flex;
  gap: 6px;
  padding: 4px;
  background: #f2f4f8;
  border-radius: 12px;
  margin-bottom: 22px;
}
.role-tab {
  flex: 1;
  border: none;
  background: transparent;
  padding: 9px 0;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, box-shadow 0.2s;
}
.role-tab.active {
  background: #fff;
  color: var(--hy-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
.card-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1d2129;
}
.card-header p {
  margin: 8px 0 24px;
  font-size: 13px;
  color: #86909c;
}
.login-extra {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: -4px 0 18px;
  font-size: 13px;
}
.link {
  color: var(--hy-primary);
  cursor: pointer;
}
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  letter-spacing: 6px;
}
.tip {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
  color: #c9cdd4;
}

@media (max-width: 960px) {
  .login-container {
    grid-template-columns: 1fr;
    padding: 24px;
  }
  .login-left {
    display: none;
  }
}
</style>
