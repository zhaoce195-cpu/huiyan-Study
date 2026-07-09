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
  ArrowDown
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
        background-color="#181a20"
        text-color="#c9cdd4"
        active-text-color="#4091ff"
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
        <el-dropdown trigger="hover">
          <span class="header-user">
            <el-avatar
              :size="30"
              :src="userInfo.avatar"
              style="background:rgba(64,145,255,0.2);color:#4091ff;font-size:13px"
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

/* ========== 右侧区：顶栏 + 主内容，整体等高 ========== */
.portal-body {
  height: 100vh;
  overflow: hidden;
}
.portal-header {
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 20px;
  background: #181a20;
  border-bottom: 1px solid #2a2a2a;
}
.header-user {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.2s;
}
.header-user:hover {
  background: rgba(64, 145, 255, 0.1);
}
.hu-name {
  font-size: 13px;
  font-weight: 600;
  color: #e5e6eb;
}
.hu-arrow {
  color: #86909c;
  font-size: 12px;
}

/* ========== 主内容区：填充剩余高度 + 独立纵向滚动 ========== */
.portal-main {
  flex: 1;
  min-height: 0;
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
