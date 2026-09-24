<script setup lang="ts">
/**
 * PATIENT 端门户布局
 * 与 TrainingPortal / ScreeningPortal 同结构（el-container + el-aside + el-main），
 * 仅保留 3 个菜单：
 *   - 我的病例（/patient/reports）
 *   - 个人中心（/patient/profile）
 *   - 申请权限（/patient/apply）
 * 普通用户不展示角色标签。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Document,
  Promotion,
  SwitchButton,
  User,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useLogout } from '@/composables/useLogout'

const route = useRoute()
const userStore = useUserStore()
const { logout } = useLogout()

const userInfo = computed(() => userStore.userInfo)
const displayName = computed(() => userStore.displayName)

const collapsed = ref(false)

const activeMenu = computed(() => {
  if (route.path.startsWith('/patient/profile')) return '/patient/profile'
  if (route.path.startsWith('/patient/apply')) return '/patient/apply'
  return '/patient/reports'
})

onMounted(async () => {
  try {
    await userStore.fetchProfile()
  } catch {
    /* ignore */
  }
})
</script>

<template>
  <el-container class="portal" :class="{ collapsed }">
    <el-aside class="portal-aside" :width="collapsed ? '64px' : '240px'">
      <div class="aside-brand">
        <svg viewBox="0 0 48 48" width="32" height="32">
          <circle cx="24" cy="24" r="22" fill="#1677ff" opacity="0.14" />
          <circle cx="24" cy="24" r="14" fill="none" stroke="#1677ff" stroke-width="2.5" />
          <circle cx="24" cy="24" r="6" fill="#1677ff" />
          <circle cx="24" cy="24" r="2.5" fill="#fff" />
        </svg>
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-name">慧眼云 · 用户中心</div>
          <div class="brand-sub">PATIENT PORTAL</div>
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
        </div>
      </div>

      <el-menu
        class="aside-menu"
        background-color="transparent"
        text-color="var(--ap-text)"
        active-text-color="var(--ap-accent)"
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
      >
        <el-menu-item index="/patient/reports">
          <el-icon><Document /></el-icon>
          <template #title>我的病例</template>
        </el-menu-item>
        <el-menu-item index="/patient/profile">
          <el-icon><User /></el-icon>
          <template #title>个人中心</template>
        </el-menu-item>
        <el-menu-item index="/patient/apply">
          <el-icon><Promotion /></el-icon>
          <template #title>申请权限</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-main class="portal-main">
      <router-view />
    </el-main>

    <!-- 右上角浮动：退出登录 -->
    <el-button
      class="logout-fab"
      :icon="SwitchButton"
      type="danger"
      plain
      size="small"
      @click="logout"
    >
      退出登录
    </el-button>
  </el-container>
</template>

<style scoped>
.portal {
  height: 100vh;
  overflow: hidden;
  background: var(--ap-bg);
  color: var(--ap-text);
}

.portal-aside {
  height: 100vh;
  overflow: hidden;
  background: var(--ap-glass);
  border-right: 1px solid var(--ap-hairline);
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
  border-bottom: 1px solid var(--ap-hairline);
  flex-shrink: 0;
}
.brand-text { display: flex; flex-direction: column; }
.brand-name { font-size: 14px; font-weight: 700; color: var(--ap-text); letter-spacing: 1px; }
.brand-sub { font-size: 11px; color: var(--ap-accent); letter-spacing: 1.5px; margin-top: 2px; }

.aside-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--ap-hairline);
  flex-shrink: 0;
}
.user-meta { display: flex; flex-direction: column; gap: 4px; }
.u-name { font-size: 13px; font-weight: 600; color: var(--ap-text); }

.aside-menu {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 0;
  background: transparent;
  padding-top: 8px;
}
.aside-menu :deep(.el-menu-item) {
  margin: 2px 8px;
  border-radius: 6px;
  height: 44px;
  line-height: 44px;
  color: var(--ap-text);
}
.aside-menu :deep(.el-menu-item .el-icon) {
  color: var(--ap-text-2);
}
.aside-menu :deep(.el-menu-item.is-active) {
  background: var(--ap-accent-soft);
  color: var(--ap-accent);
  font-weight: 600;
}

.aside-footer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-top: 1px solid var(--ap-hairline);
  flex-shrink: 0;
}
.action-btn { justify-content: flex-start; }
.portal.collapsed .action-btn { justify-content: center; padding: 8px 0; }

/* 右上角浮动「退出登录」按钮 */
.logout-fab {
  position: fixed;
  top: 14px;
  right: 18px;
  z-index: 2000;
}

.portal-main {
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  background: var(--ap-l-bg);
}
.portal-main :deep(> *) { min-height: 100%; }

.portal-main::-webkit-scrollbar,
.aside-menu::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.portal-main::-webkit-scrollbar-thumb,
.aside-menu::-webkit-scrollbar-thumb {
  background: rgba(22, 119, 255, 0.18);
  border-radius: 4px;
}
.portal-main::-webkit-scrollbar-thumb:hover,
.aside-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(22, 119, 255, 0.36);
}
.portal-main::-webkit-scrollbar-track,
.aside-menu::-webkit-scrollbar-track {
  background: transparent;
}
</style>
