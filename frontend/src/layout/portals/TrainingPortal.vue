<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Folder,
  HomeFilled,
  Monitor,
  Aim,
  Reading,
  Setting,
  Promotion,
  Tickets,
  User,
  Bell,
  SwitchButton,
  Fold,
  Expand,
  MoreFilled,
  Upload,
  Notebook
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useLogout } from '@/composables/useLogout'
import { triggerLoginNoticePopup } from '@/utils/login-notice'
import { CommonApi, ExamApi, ReadingApi } from '@/api'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { logout } = useLogout()

/* ========== 用户（统一从 store 读取） ========== */
const userInfo = computed(() => userStore.userInfo)
const displayName = computed(() => userStore.displayName)
const isAdmin = computed(() => userStore.isAdmin)
const roleName = computed(() => userStore.roleName)
const isTeacher = computed(() => userStore.isAdmin || userStore.isDoctor)
const isStudent = computed(() => userStore.isTrainee)

/** 教师/管理员待批改数。学员不请求、不展示。 */
const pendingReviewCount = ref(0)
const unreadNoticeCount = ref(0)
const openExamCount = ref(0)

const loadPendingReviews = async () => {
  if (!isTeacher.value) return
  try {
    const page = await ReadingApi.getReadingList({
      status: 'SUBMITTED',
      page: 1,
      pageSize: 1
    })
    pendingReviewCount.value = Number(page?.total) || 0
  } catch {
    pendingReviewCount.value = 0
  }
}

const loadInboxSignals = async () => {
  try {
    const res = await CommonApi.getNotifications(1, 20)
    unreadNoticeCount.value = Number(res?.unread) || 0
  } catch {
    unreadNoticeCount.value = 0
  }
  if (!isStudent.value) {
    openExamCount.value = 0
    return
  }
  try {
    const rows = (await ExamApi.listExams()) || []
    openExamCount.value = rows.filter(
      (paper) => paper.status === 'OPEN' && paper.mineStatus !== 'HANDED'
    ).length
  } catch {
    openExamCount.value = 0
  }
}

onMounted(() => {
  // 入端口先校验：patient 不允许进入培训端
  if (!userStore.canAccessTraining) {
    ElMessage.warning('当前账号无医学培训端访问权限')
    router.replace(userStore.homePathForRole())
    return
  }
  userStore.fetchProfile()
  loadPendingReviews()
  loadInboxSignals()
  window.setTimeout(() => triggerLoginNoticePopup(), 200)
})

watch(() => route.fullPath, () => {
  if (!userStore.canAccessTraining) return
  loadInboxSignals()
})

/* ========== 折叠 ========== */
const collapsed = ref(false)

/* ========== 当前菜单 ========== */
const activeMenu = computed(() => {
  // 阅片工作站可能带 caseId 等参数，用 path 即可命中前缀
  if (route.path.startsWith('/training/home')) return '/training/home'
  if (route.path.startsWith('/training/reading')) {
    if (isTeacher.value && String(route.query.tab || '') === 'quality') {
      return '/training/reading?tab=quality'
    }
    return '/training/reading'
  }
  // 病例中心含检索、建案、分享。/training/cases?tab=ai-builder 仍高亮「病例中心」。
  if (/^\/training\/cases(?:\/|$)/.test(route.path)) return '/training/cases'
  if (
    route.path.startsWith('/training/ai-builder')
    || route.path.startsWith('/training/teaching-share')
  ) {
    return '/training/cases'
  }
  if (route.path.startsWith('/training/practice')) return '/training/practice'
  if (route.path.startsWith('/training/learning')) return '/training/learning'
  if (route.path.startsWith('/training/admin')) return '/training/admin'
  if (route.path.startsWith('/training/profile')) return '/training/profile'
  if (route.path.startsWith('/training/notices')) return '/training/notices'
  if (route.path.startsWith('/training/exams')) return '/training/exams'
  if (route.path.startsWith('/training/class')) return '/training/class'
  if (route.path.startsWith('/training/student-teaching')) return '/training/student-teaching'
  if (route.path.startsWith('/training/my-reviews')) return '/training/my-reviews'
  return route.path
})

/* ========== 角色徽标（老师/学生一眼可辨） ========== */
const roleBadge = computed(() => {
  if (userStore.isAdmin) return { text: '管理员', cls: 'badge-admin' }
  if (userStore.isDoctor) return { text: '教师', cls: 'badge-teacher' }
  if (userStore.isTrainee) return { text: '学生', cls: 'badge-student' }
  return { text: roleName.value || '用户', cls: 'badge-student' }
})
</script>

<template>
  <el-container class="portal" :class="{ collapsed, 'tone-slate': isTeacher }">
    <!-- 侧边栏：固定高度，不随页面滚动 -->
    <el-aside class="portal-aside" :width="collapsed ? '64px' : '240px'">
      <div class="aside-brand">
        <svg viewBox="0 0 48 48" width="32" height="32">
          <circle cx="24" cy="24" r="22" fill="#2563eb" opacity="0.28" />
          <circle cx="24" cy="24" r="14" fill="none" stroke="#2563eb" stroke-width="2.5" />
          <circle cx="24" cy="24" r="6" fill="#2563eb" />
          <circle cx="24" cy="24" r="2.5" fill="#fff" />
        </svg>
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-name">
            慧眼 AI
            <span class="role-badge" :class="roleBadge.cls">{{ roleBadge.text }}</span>
          </div>
          <div class="brand-sub">教学实训平台</div>
        </div>
      </div>

      <el-menu
        class="aside-menu"
        popper-class="portal-aside-popper"
        background-color="#14171f"
        text-color="#c4cad4"
        active-text-color="#ffffff"
        :default-active="activeMenu"
        :default-openeds="['study-personal']"
        :collapse="collapsed"
        :collapse-transition="false"
        router
      >
        <el-menu-item index="/training/home">
          <el-icon><home-filled /></el-icon>
          <template #title>{{ isStudent ? '今日学习' : '教学看板' }}</template>
        </el-menu-item>

        <!-- 教师 / 管理员：4 个一级带教入口 + 1 个默认收起的教务菜单。学员不渲染。 -->
        <template v-if="isTeacher">
          <el-menu-item index="/training/reading?tab=quality">
            <el-icon><tickets /></el-icon>
            <template #title>
              <span class="review-menu-title">
                作业批阅
                <el-badge
                  v-if="pendingReviewCount > 0"
                  :value="pendingReviewCount"
                  :max="99"
                  class="review-menu-badge"
                />
              </span>
            </template>
          </el-menu-item>
          <el-menu-item index="/training/reading">
            <el-icon><Monitor /></el-icon>
            <template #title>双眼阅片工作台</template>
          </el-menu-item>
          <el-menu-item index="/training/cases">
            <el-icon><folder /></el-icon>
            <template #title>病例中心</template>
          </el-menu-item>
          <el-sub-menu index="teaching-affairs">
            <template #title>
              <el-icon><notebook /></el-icon>
              <span>教学事务管理</span>
            </template>
            <el-menu-item index="/training/class">
              <el-icon><user /></el-icon>
              <template #title>班级与学员维护</template>
            </el-menu-item>
            <el-menu-item index="/training/exams">
              <el-icon><notebook /></el-icon>
              <template #title>正式考核与试卷</template>
            </el-menu-item>
            <el-menu-item
              v-if="userStore.canAccessScreening"
              index="/screening"
            >
              <el-icon><upload /></el-icon>
              <template #title>AI 批量筛查</template>
            </el-menu-item>
          </el-sub-menu>
        </template>

        <!-- 学员病例入口。与教师端的病例中心分开，避免套用教师折叠菜单。 -->
        <el-menu-item-group v-if="isStudent" title="病例">
          <el-menu-item index="/training/cases">
            <el-icon><folder /></el-icon>
            <template #title>病例库</template>
          </el-menu-item>
          <el-menu-item index="/training/reading">
            <el-icon><Monitor /></el-icon>
            <template #title>阅片工作台</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 学生端 · 训练 -->
        <el-menu-item-group v-if="isStudent" title="学生 · 训练">
          <el-menu-item index="/training/practice">
            <el-icon><aim /></el-icon>
            <template #title>
              <span class="review-menu-title">
                病例学习
                <el-badge
                  v-if="openExamCount > 0"
                  :value="openExamCount"
                  :max="99"
                  class="review-menu-badge"
                />
              </span>
            </template>
          </el-menu-item>
          <el-menu-item index="/training/student-teaching">
            <el-icon><promotion /></el-icon>
            <template #title>教师演示病例</template>
          </el-menu-item>
          <el-menu-item index="/training/my-reviews">
            <el-icon><tickets /></el-icon>
            <template #title>教师评定</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 管理员 · 平台管理 -->
        <el-menu-item-group v-if="isAdmin" title="管理员">
          <el-menu-item index="/training/admin">
            <el-icon><setting /></el-icon>
            <template #title>平台管理后台</template>
          </el-menu-item>
        </el-menu-item-group>

        <el-sub-menu index="study-personal">
          <template #title>
            <el-icon><user /></el-icon>
            <span class="review-menu-title">
              学习与个人
              <el-badge
                v-if="unreadNoticeCount > 0"
                :value="unreadNoticeCount"
                :max="99"
                class="review-menu-badge"
              />
            </span>
          </template>
          <el-menu-item index="/training/learning">
            <el-icon><reading /></el-icon>
            <template #title>学习资料与笔记</template>
          </el-menu-item>
          <el-menu-item index="/training/notices">
            <el-icon><bell /></el-icon>
            <template #title>
              <span class="review-menu-title">
                通知
                <el-badge
                  v-if="unreadNoticeCount > 0"
                  :value="unreadNoticeCount"
                  :max="99"
                  class="review-menu-badge"
                />
              </span>
            </template>
          </el-menu-item>
          <el-menu-item index="/training/profile">
            <el-icon><user /></el-icon>
            <template #title>个人中心</template>
          </el-menu-item>
        </el-sub-menu>

      </el-menu>

      <!-- 侧边栏底部：用户（系统管理员）+ 收起切换 -->
      <div class="aside-footer">
        <el-dropdown trigger="hover" placement="top-start">
          <div class="aside-user" :class="{ 'is-collapsed': collapsed }">
            <el-avatar
              :size="34"
              :src="userInfo.avatar"
              style="background:rgba(22,119,255,0.22);color:#ffffff;font-size:14px;flex-shrink:0"
            >
              {{ displayName.charAt(0) }}
            </el-avatar>
            <div v-if="!collapsed" class="au-meta">
              <div class="au-name">{{ displayName }}</div>
              <div class="au-role">{{ roleName }}</div>
            </div>
            <el-icon v-if="!collapsed" class="au-more"><more-filled /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/training/profile')">
                <el-icon><user /></el-icon>个人中心
              </el-dropdown-item>
              <el-dropdown-item v-if="isAdmin" @click="router.push('/training/admin')">
                <el-icon><setting /></el-icon>平台管理后台
              </el-dropdown-item>
              <el-dropdown-item divided @click="logout">
                <el-icon><switch-button /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <button
          class="collapse-btn"
          :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="collapsed = !collapsed"
        >
          <el-icon :size="18">
            <expand v-if="collapsed" />
            <fold v-else />
          </el-icon>
        </button>
      </div>
    </el-aside>

    <el-main class="portal-main">
      <router-view v-slot="{ Component }">
        <transition name="portal-fade" mode="out-in" :duration="{ enter: 150, leave: 150 }">
          <keep-alive :exclude="['Reading', 'PracticeWorkstation']">
            <component :is="Component" :key="route.path" />
          </keep-alive>
        </transition>
      </router-view>
    </el-main>
  </el-container>
</template>

<style scoped>
/* ========== 容器：Apple 深色 + 渐变底 ========== */
.portal {
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  background: var(--hy-work-bg, #edf1f6);
  color: var(--ap-text);
}

/* ========== 侧边栏：暗岩底，文字颜色写死，不跟主题变量走 ========== */
.portal-aside {
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  background: #14171f !important;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  padding: 0;
  transition: width 0.28s var(--ap-ease);
}

.aside-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px;
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.brand-name {
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: 0;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 角色徽标：教师琥珀 / 学生蓝 / 管理员紫，一眼区分当前身份 */
.role-badge {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  line-height: 1;
  padding: 3px 7px;
  border-radius: 999px;
  flex-shrink: 0;
}
.badge-teacher {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.35);
}
.badge-student {
  color: #4091ff;
  background: rgba(64, 145, 255, 0.14);
  border: 1px solid rgba(64, 145, 255, 0.35);
}
.badge-admin {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.14);
  border: 1px solid rgba(167, 139, 250, 0.35);
}
.brand-sub {
  font-size: 11px;
  color: #8f95a3;
  letter-spacing: 2.5px;
  margin-top: 3px;
  font-weight: 500;
}

/* 菜单区：只占品牌和底部用户栏之间的高度，多出来的分组在这里滚动。
   Element Plus 默认把菜单高度设成 100%，会连同顶栏一起高出视口，
   底下的「教学事务管理」「学习与个人」被裁掉且无法滚动。 */
.aside-menu {
  flex: 1 1 0;
  height: auto !important;
  min-height: 0;
  max-height: none;
  overflow-y: auto !important;
  overflow-x: hidden;
  border-right: 0;
  padding: 6px 0 12px;
  background: #14171f !important;
  --el-menu-bg-color: #14171f;
  --el-menu-text-color: #c4cad4;
  --el-menu-active-color: #ffffff;
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.08);
  --el-menu-hover-text-color: #ffffff;
}
.aside-menu :deep(.el-menu) {
  background: #14171f !important;
}
/* 分组标题：教学事务管理、学习与个人、管理员 */
.aside-menu :deep(.el-sub-menu__title) {
  margin: 8px 10px 2px;
  padding-left: 14px !important;
  border-radius: var(--ap-radius-sm);
  height: 36px;
  line-height: 36px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.2px;
  color: #7b8392 !important;
  background: transparent !important;
}
.aside-menu :deep(.el-sub-menu__title .el-icon),
.aside-menu :deep(.el-sub-menu__icon-arrow) {
  color: #9aa1af !important;
}
.aside-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #ffffff !important;
}
.aside-menu :deep(.el-sub-menu__title:hover .el-icon),
.aside-menu :deep(.el-sub-menu__title:hover .el-sub-menu__icon-arrow) {
  color: #ffffff !important;
}
.aside-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  background: transparent !important;
  color: #7b8392 !important;
}
.aside-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title .el-icon) {
  color: #9aa1af !important;
}
.aside-menu :deep(.el-menu-item-group__title) {
  padding: 16px 20px 6px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.2px;
  color: #7b8392 !important;
}
/* 收起时：隐藏分组标题 + 图标水平居中 */
.aside-menu.el-menu--collapse :deep(.el-menu-item-group__title) {
  display: none;
}
.aside-menu.el-menu--collapse :deep(.el-menu-item-group ul) {
  padding: 0;
}
.aside-menu.el-menu--collapse :deep(.el-menu-item) {
  margin: 2px 8px;
  padding: 0 !important;
  justify-content: center;
}
.aside-menu.el-menu--collapse :deep(.el-menu-item .el-icon) {
  margin: 0 !important;
}
/* 收起时品牌 Logo 居中 */
.portal.collapsed .aside-brand {
  justify-content: center;
  padding: 20px 0 18px;
}
.aside-menu :deep(.el-menu-item) {
  margin: 2px 10px;
  padding-left: 14px !important;
  border-radius: var(--ap-radius-sm);
  height: 42px;
  line-height: 42px;
  font-size: calc(14px * var(--hy-font-scale, 1));
  color: #c4cad4 !important;
  background: transparent !important;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background 0.2s var(--ap-ease), color 0.2s var(--ap-ease);
}
.aside-menu :deep(.el-menu-item .el-icon) {
  color: #9aa1af !important;
  transition: color 0.2s var(--ap-ease);
}
.aside-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #ffffff !important;
}
.aside-menu :deep(.el-menu-item:hover .el-icon) {
  color: #ffffff !important;
}
.aside-menu :deep(.el-menu-item.is-active),
.aside-menu :deep(.el-menu-item.is-active:hover) {
  background: #1677ff !important;
  color: #ffffff !important;
  font-weight: 600;
}
.aside-menu :deep(.el-menu-item.is-active .el-icon),
.aside-menu :deep(.el-menu-item.is-active:hover .el-icon) {
  color: #ffffff !important;
}
.aside-menu :deep(.el-sub-menu .el-menu-item) {
  padding-left: 36px !important;
}
.review-menu-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  line-height: 1;
}
.review-menu-badge {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}
.review-menu-badge :deep(.el-badge__content) {
  position: static;
  transform: none;
  top: auto;
  box-sizing: border-box;
  height: 22px;
  min-width: 22px;
  line-height: 18px;
  padding: 0 6px;
  border-radius: 11px;
  border: 2px solid #ffffff !important;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.45);
  font-size: 14px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  background: #f53f3f !important;
  color: #ffffff !important;
}

/* ========== 侧边栏底部：用户（系统管理员）+ 收起 ========== */
.aside-footer {
  flex-shrink: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.aside-user {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: var(--ap-radius-sm);
  cursor: pointer;
  transition: background 0.2s var(--ap-ease);
}
.aside-user:hover {
  background: rgba(255, 255, 255, 0.08);
}
.aside-user.is-collapsed {
  justify-content: center;
  padding: 6px 0;
}
.au-meta {
  flex: 1;
  min-width: 0;
}
.au-name {
  font-size: calc(13px * var(--hy-font-scale, 1));
  font-weight: 600;
  color: #e5e8ef;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.au-role {
  font-size: calc(12px * var(--hy-font-scale, 1));
  color: #8f95a3;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.au-more {
  color: #8f95a3;
  font-size: 15px;
  flex-shrink: 0;
}
.collapse-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #9aa1af;
  border-radius: 9px;
  cursor: pointer;
  transition: background 0.2s var(--ap-ease), color 0.2s var(--ap-ease);
}
.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}
.portal.collapsed .aside-footer {
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
}

/* ========== 主内容区（无顶栏，整屏高度） ========== */
.portal-main {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  /* 低眩光冷灰。页面里的白卡片叠在这层灰上，切页时也不会露出白底。 */
  background: var(--hy-work-bg, #edf1f6);
}
.portal.tone-slate .portal-main {
  background: #edf1f6;
}
.portal-main :deep(> *) {
  min-height: 100% !important;
}

/* 滚动条：细而克制 */
.portal-main::-webkit-scrollbar,
.aside-menu::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
/* 内容区（浅色）：深色滚动条 */
.portal-main::-webkit-scrollbar-thumb {
  background: rgba(15, 23, 42, 0.15);
  border-radius: 4px;
}
.portal-main::-webkit-scrollbar-thumb:hover {
  background: rgba(15, 23, 42, 0.28);
}
.aside-menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.16);
  border-radius: 4px;
}
.aside-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.28);
}
.portal-main::-webkit-scrollbar-track,
.aside-menu::-webkit-scrollbar-track {
  background: transparent;
}

</style>

<style>
/* 收起后弹出的子菜单挂在 body 上，不吃侧栏的 scoped 样式 */
.portal-aside-popper.el-menu {
  background: #14171f !important;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.portal-aside-popper .el-menu-item {
  color: #c4cad4 !important;
  background: transparent !important;
}
.portal-aside-popper .el-menu-item .el-icon {
  color: #9aa1af !important;
}
.portal-aside-popper .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #ffffff !important;
}
.portal-aside-popper .el-menu-item:hover .el-icon {
  color: #ffffff !important;
}
.portal-aside-popper .el-menu-item.is-active,
.portal-aside-popper .el-menu-item.is-active:hover {
  background: #1677ff !important;
  color: #ffffff !important;
  font-weight: 600;
}
.portal-aside-popper .el-menu-item.is-active .el-icon {
  color: #ffffff !important;
}

.portal-fade-enter-active,
.portal-fade-leave-active {
  transition: opacity 0.15s ease;
}
.portal-fade-enter-from,
.portal-fade-leave-to {
  opacity: 0;
}
</style>
