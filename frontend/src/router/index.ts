import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/login/register.vue'),
    meta: { title: '注册', public: true }
  },
  {
    // 首页原为「端口选择页」，体检筛查端已停用、只剩培训端 → 直接按角色重定向
    path: '/',
    redirect: () => {
      try {
        const u = JSON.parse(localStorage.getItem('huiyan_user') || '{}')
        return u?.role === 'patient' ? '/patient/reports' : '/training'
      } catch {
        return '/training'
      }
    }
  },

  /* ============================================================
   * 体检筛查端 —— 已停用（保留全部代码，仅注释掉路由注册）
   * 需要恢复时取消下面整段注释即可，视图文件均未删除。
   * ============================================================ */
  // {
  //   path: '/screening',
  //   component: () => import('@/layout/portals/ScreeningPortal.vue'),
  //   meta: { scene: 'screening', deniedRoles: ['trainee'] },
  //   redirect: '/screening/dashboard',
  //   children: [
  //     { path: 'dashboard', name: 'ScreeningDashboard', component: () => import('@/layout/portals/ScreeningWorkspace.vue'), props: { section: 'upload' }, meta: { title: '批量筛查' } },
  //     { path: 'list', name: 'ScreeningList', component: () => import('@/views/screening/case-search.vue'), meta: { title: '病例检索' } },
  //     { path: 'profile', name: 'ScreeningProfile', component: () => import('@/views/profile/index.vue'), meta: { title: '个人中心' } }
  //   ]
  // },

  /* ============================================================
   * 医学培训端（深色主题）— 单端口侧边栏布局
   * 子页：病例库 / 阅片标注 / 自主练习 / 学习资料 / 个人中心 / 管理后台
   * ============================================================ */
  {
    path: '/training',
    component: () => import('@/layout/portals/TrainingPortal.vue'),
    meta: { scene: 'training' },
    redirect: '/training/cases',
    children: [
      {
        path: 'cases',
        name: 'TrainingCases',
        component: () => import('@/views/case-browse/index.vue'),
        meta: {
          title: '病例浏览检索',
          allowedRoles: ['admin', 'doctor', 'trainee']
        }
      },
      {
        path: 'reading',
        name: 'TrainingReading',
        component: () => import('@/views/reading/index.vue'),
        meta: { title: '影像阅片工作站' },
        beforeEnter: (to) => {
          if (!to.query.caseId) {
            ElMessage.warning('请从病例库选择病例进入阅片工作台')
            return { path: '/training/cases' }
          }
        }
      },
      {
        path: 'practice',
        name: 'TrainingPractice',
        component: () => import('@/views/practice/index.vue'),
        meta: { title: '自主练习与自评' }
      },
      {
        path: 'practice/workstation',
        name: 'TrainingPracticeWorkstation',
        component: () => import('@/views/practice/workstation.vue'),
        meta: { title: '练习工作站' },
        beforeEnter: (to) => {
          if (!to.query.caseId || !to.query.sessionId) {
            ElMessage.warning('请从练习列表选择病例进入练习工作站')
            return { path: '/training/practice' }
          }
        }
      },
      {
        path: 'teaching-share',
        name: 'TeachingShare',
        component: () => import('@/views/training/teaching-share.vue'),
        meta: { title: '我的教学分享', allowedRoles: ['admin', 'doctor'] }
      },
      {
        path: 'student-teaching',
        name: 'StudentTeaching',
        component: () => import('@/views/training/student-teaching.vue'),
        meta: { title: '教师演示病例', allowedRoles: ['admin', 'doctor', 'trainee'] }
      },
      {
        path: 'learning',
        name: 'TrainingLearning',
        component: () => import('@/views/learning/index.vue'),
        meta: { title: '学习资料与笔记' }
      },
      {
        path: 'profile',
        name: 'TrainingProfile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'admin',
        name: 'TrainingAdmin',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '平台管理后台', allowedRoles: ['admin'] }
      }
    ]
  },

  /* ============================================================
   * 个人中心（独立访问点，未带端口主题）
   * ============================================================ */
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/profile/index.vue'),
    meta: { title: '个人中心' }
  },

  /* ============================================================
   * PATIENT 端门户（浅色主题）— 单端口侧边栏布局
   * 子页：我的病例 / 个人中心 / 申请权限
   * ============================================================ */
  {
    path: '/patient',
    component: () => import('@/layout/portals/PatientPortal.vue'),
    meta: { allowedRoles: ['patient'] },
    redirect: '/patient/reports',
    children: [
      {
        path: 'reports',
        name: 'PatientPortalReports',
        component: () => import('@/views/patient/reports.vue'),
        meta: { title: '我的病例' }
      },
      {
        path: 'profile',
        name: 'PatientProfile',
        component: () => import('@/views/patient/profile.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'apply',
        name: 'PatientApply',
        component: () => import('@/views/patient/apply.vue'),
        meta: { title: '申请权限' }
      }
    ]
  },

  /* ============================================================
   * 兼容老路径：原顶层独立模块跳转，统一重定向到培训端口对应页
   * ============================================================ */
  { path: '/case-browse', redirect: '/training/cases' },
  { path: '/reading', redirect: (to) => ({ path: '/training/reading', query: to.query }) },
  { path: '/practice', redirect: '/training/practice' },
  { path: '/practice/workstation', redirect: (to) => ({ path: '/training/practice/workstation', query: to.query }) },
  { path: '/learning', redirect: '/training/learning' },
  { path: '/admin', redirect: '/training/admin' },

  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

const TOKEN_KEY = 'huiyan_token'
const USER_KEY = 'huiyan_user'

const getRole = (): string => {
  try {
    const u = JSON.parse(localStorage.getItem(USER_KEY) || '{}')
    return (u?.role as string) || ''
  } catch {
    return ''
  }
}

const homePathForRole = (role: string): string => {
  if (role === 'patient') return '/patient/reports'
  if (role === 'trainee') return '/training'
  if (role === 'admin' || role === 'doctor') return '/'
  return '/'
}

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (to.meta.title) {
    document.title = `${to.meta.title} · 慧眼医疗云平台 V2.0`
  }
  if (to.meta.public) {
    next()
    return
  }
  if (!token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // 自顶向下收集本路径上所有的 deniedRoles / allowedRoles 元数据
  const deniedRoles = new Set<string>()
  const allowedRoles = new Set<string>()
  for (const m of to.matched) {
    ;(m.meta?.deniedRoles as string[] | undefined)?.forEach((r) => deniedRoles.add(r))
    ;(m.meta?.allowedRoles as string[] | undefined)?.forEach((r) => allowedRoles.add(r))
  }

  const role = getRole()
  if (deniedRoles.has(role) || (allowedRoles.size > 0 && !allowedRoles.has(role))) {
    const home = homePathForRole(role)
    if (to.path === home) {
      // 防止循环重定向
      next()
      return
    }
    next({ path: home })
    return
  }
  next()
})

export default router
