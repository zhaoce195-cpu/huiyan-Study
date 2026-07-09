<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Folder,
  View,
  Aim,
  Reading,
  Setting,
  Share,
  Promotion,
  User,
  SwitchButton,
  ArrowDown,
  Fold,
  Expand
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useLogout } from '@/composables/useLogout'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { logout } = useLogout()

/* ========== 用户（统一从 store 读取） ========== */
const userInfo = computed(() => userStore.userInfo)
const displayName = computed(() => userStore.displayName)
const isAdmin = computed(() => userStore.isAdmin)
const roleName = computed(() => userStore.roleName)

onMounted(() => {
  // 入端口先校验：patient 不允许进入培训端
  if (!userStore.canAccessTraining) {
    ElMessage.warning('当前账号无医学培训端访问权限')
    router.replace(userStore.homePathForRole())
    return
  }
  userStore.fetchProfile()
})

/* ========== 折叠 ========== */
const collapsed = ref(false)

/* ========== 当前菜单 ========== */
const activeMenu = computed(() => {
  // 阅片工作站可能带 caseId 等参数，用 path 即可命中前缀
  if (route.path.startsWith('/training/reading')) return '/training/reading'
  if (route.path.startsWith('/training/practice')) return '/training/practice'
  if (route.path.startsWith('/training/learning')) return '/training/learning'
  if (route.path.startsWith('/training/cases')) return '/training/cases'
  if (route.path.startsWith('/training/admin')) return '/training/admin'
  if (route.path.startsWith('/training/profile')) return '/training/profile'
  if (route.path.startsWith('/training/teaching-share')) return '/training/teaching-share'
  if (route.path.startsWith('/training/student-teaching')) return '/training/student-teaching'
  return route.path
})

const isTeacher = computed(() => userStore.isAdmin || userStore.isDoctor)
const isStudent = computed(() => userStore.isTrainee)

/* 顶栏页面标题：取当前路由 meta.title */
const currentTitle = computed(() => (route.meta.title as string) || '慧眼AI')
</script>

<template>
  <el-container class="portal portal-dark" :class="{ collapsed }">
    <!-- 侧边栏：固定高度，不随页面滚动 -->
    <el-aside class="portal-aside" :width="collapsed ? '64px' : '240px'">
      <div class="aside-brand">
        <svg viewBox="0 0 48 48" width="32" height="32">
          <rect x="4" y="10" width="40" height="28" rx="4" fill="none" stroke="#4091ff" stroke-width="2.5" />
          <path d="M10 28 L20 22 L26 30 L34 24 L40 32" stroke="#4091ff" stroke-width="2" fill="none" />
          <circle cx="34" cy="24" r="3" fill="#4091ff" />
        </svg>
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-name">慧眼AI</div>
          <div class="brand-sub">HUIYAN AI</div>
        </div>
      </div>

      <el-menu
        class="aside-menu"
        background-color="transparent"
        text-color="var(--ap-text-2)"
        active-text-color="var(--ap-accent)"
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
      >
        <!-- 病例与阅片（通用） -->
        <el-menu-item-group title="病例与阅片">
          <el-menu-item index="/training/cases">
            <el-icon><folder /></el-icon>
            <template #title>病例库检索</template>
          </el-menu-item>
          <el-menu-item index="/training/reading">
            <el-icon><view /></el-icon>
            <template #title>阅片标注工作台</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 学生端 · 训练 -->
        <el-menu-item-group v-if="isStudent" title="学生 · 训练">
          <el-menu-item index="/training/practice">
            <el-icon><aim /></el-icon>
            <template #title>自主练习与自评</template>
          </el-menu-item>
          <el-menu-item index="/training/student-teaching">
            <el-icon><promotion /></el-icon>
            <template #title>教师演示病例</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 教师端 · 教学 -->
        <el-menu-item-group v-if="isTeacher" title="教师 · 教学">
          <el-menu-item index="/training/teaching-share">
            <el-icon><share /></el-icon>
            <template #title>我的教学分享</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 学习与个人（通用） -->
        <el-menu-item-group title="学习与个人">
          <el-menu-item index="/training/learning">
            <el-icon><reading /></el-icon>
            <template #title>学习资料与笔记</template>
          </el-menu-item>
          <el-menu-item index="/training/profile">
            <el-icon><user /></el-icon>
            <template #title>个人中心</template>
          </el-menu-item>
        </el-menu-item-group>

      </el-menu>
    </el-aside>

    <!-- 右侧：顶栏（用户操作） + 主内容 -->
    <el-container class="portal-body">
      <el-header class="portal-header">
        <div class="header-left">
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
          <span class="header-title">{{ currentTitle }}</span>
        </div>
        <el-dropdown trigger="hover">
          <span class="header-user">
            <el-avatar
              :size="30"
              :src="userInfo.avatar"
              style="background:rgba(203,163,92,0.18);color:#cba35c;font-size:13px"
            >
              {{ displayName.charAt(0) }}
            </el-avatar>
            <span class="hu-name">{{ displayName }}</span>
            <el-tag size="small" type="primary" effect="dark">{{ roleName }}</el-tag>
            <el-icon class="hu-arrow"><arrow-down /></el-icon>
          </span>
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
      </el-header>

      <el-main class="portal-main">
        <router-view v-slot="{ Component }">
          <keep-alive :exclude="['Reading', 'PracticeWorkstation']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
/* ========== 容器：Apple 深色 + 渐变底 ========== */
.portal {
  height: 100vh;
  overflow: hidden;
  background: var(--ap-bg-grad);
  color: var(--ap-text);
}

/* ========== 侧边栏：毛玻璃 + 发丝线 ========== */
.portal-aside {
  height: 100vh;
  overflow: hidden;
  background: var(--ap-glass);
  backdrop-filter: blur(var(--ap-blur)) saturate(180%);
  -webkit-backdrop-filter: blur(var(--ap-blur)) saturate(180%);
  border-right: 1px solid var(--ap-hairline);
  display: flex;
  flex-direction: column;
  padding: 0;
  transition: width 0.28s var(--ap-ease);
}

.aside-brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 20px 20px 18px;
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-name {
  font-size: 17px;
  font-weight: 600;
  color: var(--ap-text);
  letter-spacing: 0.5px;
}
.brand-sub {
  font-size: 10px;
  color: var(--ap-text-3);
  letter-spacing: 2.5px;
  margin-top: 3px;
  font-weight: 500;
}

/* 菜单区 */
.aside-menu {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 0;
  padding: 6px 0 12px;
  background: transparent;
}
/* 分组标题：Apple 分区头 */
.aside-menu :deep(.el-menu-item-group__title) {
  padding: 16px 20px 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.4px;
  color: var(--ap-text-3);
}
.aside-menu :deep(.el-menu-item) {
  margin: 2px 10px;
  padding-left: 14px !important;
  border-radius: var(--ap-radius-sm);
  height: 42px;
  line-height: 42px;
  color: var(--ap-text-2);
  transition: background 0.2s var(--ap-ease), color 0.2s var(--ap-ease);
}
.aside-menu :deep(.el-menu-item .el-icon) {
  color: var(--ap-text-3);
  transition: color 0.2s var(--ap-ease);
}
.aside-menu :deep(.el-menu-item:hover) {
  background: var(--ap-fill);
  color: var(--ap-text);
}
.aside-menu :deep(.el-menu-item:hover .el-icon) {
  color: var(--ap-text);
}
.aside-menu :deep(.el-menu-item.is-active) {
  background: var(--ap-accent-soft);
  color: var(--ap-accent) !important;
  font-weight: 600;
}
.aside-menu :deep(.el-menu-item.is-active .el-icon) {
  color: var(--ap-accent);
}

/* ========== 右侧区：顶栏 + 主内容 ========== */
.portal-body {
  height: 100vh;
  overflow: hidden;
}
.portal-header {
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px 0 14px;
  background: var(--ap-glass);
  backdrop-filter: blur(var(--ap-blur)) saturate(180%);
  -webkit-backdrop-filter: blur(var(--ap-blur)) saturate(180%);
  border-bottom: 1px solid var(--ap-hairline);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.collapse-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  background: transparent;
  color: var(--ap-text-2);
  border-radius: 9px;
  cursor: pointer;
  transition: background 0.2s var(--ap-ease), color 0.2s var(--ap-ease);
}
.collapse-btn:hover {
  background: var(--ap-fill);
  color: var(--ap-text);
}
.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ap-text);
  letter-spacing: 0.3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.header-user {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  user-select: none;
  padding: 6px 10px;
  border-radius: 999px;
  transition: background 0.2s var(--ap-ease);
}
.header-user:hover {
  background: var(--ap-fill);
}
.hu-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ap-text);
}
.hu-arrow {
  color: var(--ap-text-3);
  font-size: 12px;
}

/* ========== 主内容区 ========== */
.portal-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  background: transparent;
}
.portal-main :deep(> *) {
  min-height: 100%;
}

/* 滚动条：细而克制 */
.portal-main::-webkit-scrollbar,
.aside-menu::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.portal-main::-webkit-scrollbar-thumb,
.aside-menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 4px;
}
.portal-main::-webkit-scrollbar-thumb:hover,
.aside-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.22);
}
.portal-main::-webkit-scrollbar-track,
.aside-menu::-webkit-scrollbar-track {
  background: transparent;
}
</style>
