/**
 * 退出登录 composable
 * - 统一封装：confirm → LoginApi.logout → 清三类 store → toast → router.replace('/login')
 * - 各 Portal / 个人中心 共用，确保行为一致
 * - 清理：userStore（profile/token）+ caseBindingStore（手机号绑定缓存）
 *         + trainingJoinStore（已加入实训病例本地缓存）
 */
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { LoginApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { useCaseBindingStore } from '@/stores/case-binding'
import { useTrainingJoinStore } from '@/stores/training-join'

export interface UseLogoutOptions {
  /** 是否弹确认框（默认 true）；false 直接执行 */
  confirm?: boolean
  /** 退出后跳转的目标路径（默认 /login） */
  redirect?: string
}

export const useLogout = () => {
  const router = useRouter()
  const userStore = useUserStore()
  const caseBindingStore = useCaseBindingStore()
  const trainingJoinStore = useTrainingJoinStore()

  const logout = async (opts: UseLogoutOptions = {}) => {
    const { confirm = true, redirect = '/login' } = opts
    if (confirm) {
      try {
        await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
      } catch {
        return
      }
    }
    try {
      await LoginApi.logout()
    } catch {
      /* ignore */
    }
    // 清理顺序：先清依赖用户身份的业务 store，再清 user store
    try { caseBindingStore.clear() } catch { /* ignore */ }
    try { trainingJoinStore.clear() } catch { /* ignore */ }
    userStore.clear()
    ElMessage.success('已退出登录')
    router.replace(redirect)
  }

  return { logout }
}
