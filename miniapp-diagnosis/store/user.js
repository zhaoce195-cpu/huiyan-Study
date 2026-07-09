/**
 * 用户登录态 store（pinia）
 */
import { defineStore } from 'pinia'
import { TOKEN_KEY, USER_KEY } from '../utils/config'
import { logout as apiLogout, getProfile } from '../api/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: uni.getStorageSync(TOKEN_KEY) || '',
    user: uni.getStorageSync(USER_KEY) || null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    // 医生 / 管理员才有诊断写权限（与后端 require_roles 对应）
    canDiagnose: (s) => ['doctor', 'admin'].includes(s.user && s.user.role),
    displayName: (s) => (s.user && (s.user.name || s.user.username)) || '未登录',
  },
  actions: {
    setLogin(token, user) {
      this.token = token
      this.user = user
      uni.setStorageSync(TOKEN_KEY, token)
      uni.setStorageSync(USER_KEY, user)
    },
    async refreshProfile() {
      try {
        const user = await getProfile()
        if (user) {
          this.user = user
          uni.setStorageSync(USER_KEY, user)
        }
      } catch (e) {
        // 忽略
      }
    },
    async logout() {
      await apiLogout()
      this.token = ''
      this.user = null
      uni.removeStorageSync(TOKEN_KEY)
      uni.removeStorageSync(USER_KEY)
    },
  },
})
