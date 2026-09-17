<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Folder,
  Monitor,
  Aim,
  Reading,
  Setting,
  Share,
  Promotion,
  Checked,
  Tickets,
  User,
  Bell,
  SwitchButton,
  Fold,
  Expand,
  MoreFilled,
  MagicStick,
  Upload
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
  if (route.path.startsWith('/training/notices')) return '/training/notices'
  if (route.path.startsWith('/training/teaching-share')) return '/training/teaching-share'
  if (route.path.startsWith('/training/student-teaching')) return '/training/student-teaching'
  if (route.path.startsWith('/training/ai-builder')) return '/training/ai-builder'
  if (route.path.startsWith('/training/review')) return '/training/review'
  if (route.path.startsWith('/training/my-reviews')) return '/training/my-reviews'
  return route.path
})

const isTeacher = computed(() => userStore.isAdmin || userStore.isDoctor)
const isStudent = computed(() => userStore.isTrainee)

/* ========== 角色徽标（老师/学生一眼可辨） ========== */
const roleBadge = computed(() => {
  if (userStore.isAdmin) return { text: '管理员', cls: 'badge-admin' }
  if (userStore.isDoctor) return { text: '教师', cls: 'badge-teacher' }
  if (userStore.isTrainee) return { text: '学生', cls: 'badge-student' }
  return { text: roleName.value || '用户', cls: 'badge-student' }
})
</script>

<template>
  <el-container class="portal portal-dark" :class="{ collapsed }">
    <!-- 侧边栏：固定高度，不随页面滚动 -->
    <el-aside class="portal-aside" :width="collapsed ? '64px' : '240px'">
      <div class="aside-brand">
        <svg viewBox="0 0 48 48" width="32" height="32">
          <circle cx="24" cy="24" r="22" fill="#2563eb" opacity="0.12" />
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
            <el-icon><Monitor /></el-icon>
            <template #title>{{ isTeacher ? '阅片工作台 / 质量评估' : '阅片工作台' }}</template>
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
          <el-menu-item index="/training/my-reviews">
            <el-icon><tickets /></el-icon>
            <template #title>教师评定</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 教师端 · 教学 -->
        <el-menu-item-group v-if="isTeacher" title="教师 · 教学">
          <el-menu-item index="/training/teaching-share">
            <el-icon><share /></el-icon>
            <template #title>我的教学分享</template>
          </el-menu-item>
          <el-menu-item index="/training/ai-builder">
            <el-icon><magic-stick /></el-icon>
            <template #title>AI 智能建案</template>
          </el-menu-item>
          <el-menu-item index="/training/review">
            <el-icon><checked /></el-icon>
            <template #title>待审核</template>
          </el-menu-item>
          <el-menu-item
            v-if="userStore.canAccessScreening"
            index="/screening"
          >
            <el-icon><upload /></el-icon>
            <template #title>AI 批量筛查</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 管理员 · 平台管理 -->
        <el-menu-item-group v-if="isAdmin" title="管理员">
          <el-menu-item index="/training/admin">
            <el-icon><setting /></el-icon>
            <template #title>平台管理后台</template>
          </el-menu-item>
        </el-menu-item-group>

        <!-- 学习与个人（通用） -->
        <el-menu-item-group title="学习与个人">
          <el-menu-item index="/training/learning">
            <el-icon><reading /></el-icon>
            <template #title>学习资料与笔记</template>
          </el-menu-item>
          <el-menu-item index="/training/notices">
            <el-icon><bell /></el-icon>
            <template #title>通知</template>
          </el-menu-item>
          <el-menu-item index="/training/profile">
            <el-icon><user /></el-icon>
            <template #title>个人中心</template>
          </el-menu-item>
        </el-menu-item-group>

      </el-menu>

      <!-- 侧边栏底部：用户（系统管理员）+ 收起切换 -->
      <div class="aside-footer">
        <el-dropdown trigger="hover" placement="top-start">
          <div class="aside-user" :class="{ 'is-collapsed': collapsed }">
            <el-avatar
              :size="34"
              :src="userInfo.avatar"
              style="background:rgba(37,99,235,0.12);color:#2563eb;font-size:14px;flex-shrink:0"
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
        <keep-alive :exclude="['Reading', 'PracticeWorkstation']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </el-main>
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
  color: var(--ap-text);
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

/* ========== 侧边栏底部：用户（系统管理员）+ 收起 ========== */
.aside-footer {
  flex-shrink: 0;
  border-top: 1px solid var(--ap-hairline);
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
  background: var(--ap-fill);
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
  font-size: 13px;
  font-weight: 600;
  color: var(--ap-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.au-role {
  font-size: 11px;
  color: var(--ap-text-3);
  margin-top: 1px;
}
.au-more {
  color: var(--ap-text-3);
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
  color: var(--ap-text-2);
  border-radius: 9px;
  cursor: pointer;
  transition: background 0.2s var(--ap-ease), color 0.2s var(--ap-ease);
}
.collapse-btn:hover {
  background: var(--ap-fill);
  color: var(--ap-text);
}
.portal.collapsed .aside-footer {
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
}

/* ========== 主内容区（无顶栏，整屏高度） ========== */
.portal-main {
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  /* 内容区浅色（深色侧边栏 + 浅色内容 的搭配）；具体页面自带背景覆盖 */
  background: var(--ap-l-bg);
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
/* 侧边栏（深色）：浅色滚动条 */
.aside-menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.14);
  border-radius: 4px;
}
.aside-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.26);
}
.portal-main::-webkit-scrollbar-track,
.aside-menu::-webkit-scrollbar-track {
  background: transparent;
}
</style>
