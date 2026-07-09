<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  Folder,
  View,
  Aim,
  Reading,
  Setting,
  Share,
  Promotion,
  User,
  SwitchButton
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

const goHome = () => router.push('/')
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
          <div class="brand-name">慧眼云 · 医学培训</div>
          <div class="brand-sub">TRAINING PORTAL</div>
        </div>
      </div>

      <div class="aside-user">
        <el-avatar
          :size="collapsed ? 32 : 40"
          :src="userInfo.avatar"
          style="background:rgba(64,145,255,0.2);color:#4091ff"
        >
          {{ displayName.charAt(0) }}
        </el-avatar>
        <div v-if="!collapsed" class="user-meta">
          <div class="u-name">{{ displayName }}</div>
          <el-tag size="small" type="primary" effect="dark">{{ roleName }}</el-tag>
        </div>
      </div>

      <el-menu
        class="aside-menu"
        background-color="#181a20"
        text-color="#c9cdd4"
        active-text-color="#4091ff"
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
      >
        <el-menu-item index="/training/cases">
          <el-icon><folder /></el-icon>
          <template #title>病例浏览检索</template>
        </el-menu-item>
        <el-menu-item index="/training/reading">
          <el-icon><view /></el-icon>
          <template #title>阅片标注工作台</template>
        </el-menu-item>
        <el-menu-item index="/training/practice">
          <el-icon><aim /></el-icon>
          <template #title>自主练习与自评</template>
        </el-menu-item>
        <el-menu-item index="/training/learning">
          <el-icon><reading /></el-icon>
          <template #title>学习资料与笔记</template>
        </el-menu-item>
        <el-menu-item v-if="isTeacher" index="/training/teaching-share">
          <el-icon><share /></el-icon>
          <template #title>我的教学分享</template>
        </el-menu-item>
        <el-menu-item v-if="isStudent" index="/training/student-teaching">
          <el-icon><promotion /></el-icon>
          <template #title>教师演示病例</template>
        </el-menu-item>
        <el-menu-item index="/training/profile">
          <el-icon><user /></el-icon>
          <template #title>个人中心</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/training/admin">
          <el-icon><setting /></el-icon>
          <template #title>平台管理后台</template>
        </el-menu-item>
      </el-menu>

      <div class="aside-footer">
        <el-button
          v-if="!userStore.isTrainee"
          class="action-btn"
          :icon="ArrowLeft"
          plain
          @click="goHome"
        >
          <span v-if="!collapsed">返回首页</span>
        </el-button>
        <el-button
          class="action-btn"
          :icon="SwitchButton"
          type="danger"
          plain
          @click="logout"
        >
          <span v-if="!collapsed">退出登录</span>
        </el-button>
      </div>
    </el-aside>

    <!-- 主内容区：垂直独立滚动 -->
    <el-main class="portal-main">
      <router-view v-slot="{ Component }">
        <keep-alive :exclude="['Reading', 'PracticeWorkstation']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </el-main>
  </el-container>
</template>

<style scoped>
/* ========== 容器：等高 + 整体不滚动 ========== */
.portal {
  height: 100vh;
  overflow: hidden;
  background: #0f1014;
  color: #e5e6eb;
}

/* ========== 侧边栏：等高 + 自身不滚动 ========== */
.portal-aside {
  height: 100vh;
  overflow: hidden;
  background: #181a20;
  border-right: 1px solid #2a2a2a;
  display: flex;
  flex-direction: column;
  padding: 0;
  transition: width 0.2s;
}

.aside-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid #2a2a2a;
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-name {
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 1px;
}
.brand-sub {
  font-size: 11px;
  color: #4091ff;
  letter-spacing: 1.5px;
  margin-top: 2px;
}

.aside-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid #2a2a2a;
  flex-shrink: 0;
}
.user-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.u-name {
  font-size: 13px;
  font-weight: 600;
  color: #e5e6eb;
}

/* 菜单区：占据剩余空间，菜单本身在超长时纵向滚动；侧边栏外部容器仍然 overflow:hidden */
.aside-menu {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 0;
  padding-top: 8px;
}
.aside-menu :deep(.el-menu-item) {
  margin: 2px 8px;
  border-radius: 6px;
  height: 44px;
  line-height: 44px;
}
.aside-menu :deep(.el-menu-item:hover) {
  background: rgba(64, 145, 255, 0.1);
}
.aside-menu :deep(.el-menu-item.is-active) {
  background: rgba(64, 145, 255, 0.18);
  color: #4091ff !important;
  font-weight: 600;
}

.aside-footer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-top: 1px solid #2a2a2a;
  flex-shrink: 0;
}
.action-btn {
  justify-content: flex-start;
}
.portal.collapsed .action-btn {
  justify-content: center;
  padding: 8px 0;
}

/* ========== 主内容区：等高 + 独立纵向滚动 ========== */
.portal-main {
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  background: #0f1014;
}

/* el-main 的内边距由各业务页自行控制；这里清掉默认 padding 保留外观 */
.portal-main :deep(> *) {
  min-height: 100%;
}

/* 主内容区滚动条美化（深色主题） */
.portal-main::-webkit-scrollbar,
.aside-menu::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.portal-main::-webkit-scrollbar-thumb,
.aside-menu::-webkit-scrollbar-thumb {
  background: rgba(64, 145, 255, 0.25);
  border-radius: 4px;
}
.portal-main::-webkit-scrollbar-thumb:hover,
.aside-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(64, 145, 255, 0.45);
}
.portal-main::-webkit-scrollbar-track,
.aside-menu::-webkit-scrollbar-track {
  background: transparent;
}
</style>
