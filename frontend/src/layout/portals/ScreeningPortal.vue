<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  UploadFilled,
  Search,
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
const roleName = computed(() => userStore.roleName)

onMounted(() => {
  // 入端口先校验权限：trainee / patient 在此应被拦截
  if (!userStore.canAccessScreening) {
    ElMessage.warning('当前账号无体检筛查端访问权限')
    router.replace(userStore.homePathForRole())
    return
  }
  userStore.fetchProfile()
})

/* ========== 折叠 ========== */
const collapsed = ref(false)

/* ========== 当前菜单 ========== */
const activeMenu = computed(() => {
  if (route.path.startsWith('/screening/list')) return '/screening/list'
  if (route.path.startsWith('/screening/profile')) return '/screening/profile'
  return '/screening/dashboard'
})

const goHome = () => router.push('/')
</script>

<template>
  <div class="portal portal-light" :class="{ collapsed }">
    <!-- 侧边栏 -->
    <aside class="portal-aside">
      <div class="aside-brand">
        <svg viewBox="0 0 48 48" width="32" height="32">
          <circle cx="24" cy="24" r="22" fill="#1677ff" opacity="0.14" />
          <circle cx="24" cy="24" r="14" fill="none" stroke="#1677ff" stroke-width="2.5" />
          <circle cx="24" cy="24" r="6" fill="#1677ff" />
          <circle cx="24" cy="24" r="2.5" fill="#fff" />
        </svg>
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-name">慧眼云 · 体检筛查</div>
          <div class="brand-sub">SCREENING PORTAL</div>
        </div>
      </div>

      <div class="aside-user">
        <el-avatar
          :size="collapsed ? 32 : 40"
          :src="userInfo.avatar"
          style="background:#eef4ff;color:#1677ff"
        >
          {{ displayName.charAt(0) }}
        </el-avatar>
        <div v-if="!collapsed" class="user-meta">
          <div class="u-name">{{ displayName }}</div>
          <el-tag size="small" type="primary" effect="plain">{{ roleName }}</el-tag>
        </div>
      </div>

      <el-menu
        class="aside-menu"
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
      >
        <el-menu-item index="/screening/dashboard">
          <el-icon><upload-filled /></el-icon>
          <template #title>批量筛查</template>
        </el-menu-item>
        <el-menu-item index="/screening/list">
          <el-icon><search /></el-icon>
          <template #title>病例检索</template>
        </el-menu-item>
        <el-menu-item index="/screening/profile">
          <el-icon><user /></el-icon>
          <template #title>个人中心</template>
        </el-menu-item>
      </el-menu>

      <div class="aside-footer">
        <el-button
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
    </aside>

    <!-- 内容区 -->
    <main class="portal-main">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.portal {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #f5f9ff;
}
.portal-aside {
  width: 240px;
  flex-shrink: 0;
  background: #ffffff;
  border-right: 1px solid #e6effe;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  transition: width 0.2s;
}
.portal.collapsed .portal-aside {
  width: 64px;
}

.aside-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid #eef4ff;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-name {
  font-size: 14px;
  font-weight: 700;
  color: #1d2129;
  letter-spacing: 1px;
}
.brand-sub {
  font-size: 11px;
  color: #1677ff;
  letter-spacing: 1.5px;
  margin-top: 2px;
}

.aside-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid #eef4ff;
}
.user-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.u-name {
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
}

.aside-menu {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  border-right: 0;
  background: transparent;
  padding-top: 8px;
}
.aside-menu :deep(.el-menu-item) {
  margin: 2px 8px;
  border-radius: 6px;
  height: 44px;
  line-height: 44px;
}
.aside-menu :deep(.el-menu-item.is-active) {
  background: #eef4ff;
  color: #1677ff;
  font-weight: 600;
}

.aside-footer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-top: 1px solid #eef4ff;
}
.action-btn {
  justify-content: flex-start;
}
.portal.collapsed .action-btn {
  justify-content: center;
  padding: 8px 0;
}

.portal-main {
  flex: 1;
  min-width: 0;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
}
</style>
