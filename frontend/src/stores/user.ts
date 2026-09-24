/**
 * 用户身份与角色 Store —— 单一权威来源
 * - 登录后由 login 页面调用 setUser() 写入
 * - 路由守卫 / 布局 / 各视图统一通过 useUserStore() 读取
 * - 持久化到 localStorage（key: huiyan_user / huiyan_token）以便刷新后秒回显
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { LoginApi } from '@/api'
import { applyFontSize, applyTheme } from '@/utils/appearance'
import { clearLoginNoticeFlags } from '@/utils/login-notice'

const TOKEN_KEY = 'huiyan_token'
const REFRESH_KEY = 'huiyan_refresh_token'
const USER_KEY = 'huiyan_user'

type FrontRole = LoginApi.FrontRole
type UserInfo = LoginApi.UserInfo

const ROLE_NAME_MAP: Record<string, string> = {
  admin: '管理员',
  doctor: '带教医师',
  trainee: '住培医师',
  inspector: '审核员',
  patient: '体检者'
}

const safeParse = (raw: string | null): Partial<UserInfo> => {
  if (!raw) return {}
  try {
    const obj = JSON.parse(raw)
    return obj && typeof obj === 'object' ? obj : {}
  } catch {
    return {}
  }
}

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<Partial<UserInfo>>(safeParse(localStorage.getItem(USER_KEY)))
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')

  const role = computed<FrontRole | ''>(
    () => (userInfo.value.role as FrontRole) || ''
  )
  const displayName = computed(
    () => userInfo.value.name || userInfo.value.username || '医师'
  )
  const roleName = computed(
    () => userInfo.value.roleName || ROLE_NAME_MAP[role.value] || '使用者'
  )

  const isAdmin = computed(() => role.value === 'admin')
  const isDoctor = computed(() => role.value === 'doctor')
  const isTrainee = computed(() => role.value === 'trainee')
  const isPatient = computed(() => role.value === 'patient')

  /** 体检筛查端：教师 / 管理员（学员、病患不可进） */
  const canAccessScreening = computed(() => isAdmin.value || isDoctor.value)
  /** 医学培训端:管理员 / 医师 / 学员 可见（非体检者） */
  const canAccessTraining = computed(
    () => isAdmin.value || isDoctor.value || isTrainee.value
  )
  /** 写权限：管理员 / 医师 */
  const canManage = computed(() => isAdmin.value || isDoctor.value)

  /** 登录后写入用户信息（已完成 normalize） */
  const setUser = (u: UserInfo, opts?: { token?: string; refreshToken?: string }) => {
    userInfo.value = u
    localStorage.setItem(USER_KEY, JSON.stringify(u))
    if (opts?.token) {
      token.value = opts.token
      localStorage.setItem(TOKEN_KEY, opts.token)
    }
    if (opts?.refreshToken) {
      localStorage.setItem(REFRESH_KEY, opts.refreshToken)
    }
  }

  /** 拉取最新 profile（覆盖本地缓存） */
  const fetchProfile = async (): Promise<UserInfo | null> => {
    try {
      const u = await LoginApi.getUserInfo()
      if (u && u.role) {
        userInfo.value = u
        localStorage.setItem(USER_KEY, JSON.stringify(u))
      }
      try {
        const setting = await LoginApi.getUserSetting()
        applyFontSize(setting.fontSize)
        applyTheme(setting.theme)
      } catch {
        /* 设置接口失败时沿用本地已生效的字号和风格 */
      }
      return u
    } catch {
      return null
    }
  }

  /** 启动时调用：以 localStorage 为准 + 后台拉新 */
  const init = async () => {
    const cached = safeParse(localStorage.getItem(USER_KEY))
    if (cached?.username) userInfo.value = cached
    if (token.value) await fetchProfile()
  }

  /** 登出：清空一切 */
  const clear = () => {
    userInfo.value = {}
    token.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
    clearLoginNoticeFlags()
  }

  /** 角色对应的默认入口 */
  const homePathForRole = (r: FrontRole | '' = role.value): string => {
    if (r === 'patient') return '/patient/reports'
    return '/training'
  }

  return {
    userInfo,
    token,
    role,
    displayName,
    roleName,
    isAdmin,
    isDoctor,
    isTrainee,
    isPatient,
    canAccessScreening,
    canAccessTraining,
    canManage,
    setUser,
    fetchProfile,
    init,
    clear,
    homePathForRole
  }
})
