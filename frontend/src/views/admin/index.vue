<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Back, Bell, OfficeBuilding, Collection, Document, DataAnalysis, Upload, Promotion, Reading } from '@element-plus/icons-vue'
import { LoginApi } from '@/api'
import { useUserStore } from '@/stores/user'
import NoticesSection from './sections/NoticesSection.vue'
import DepartmentsSection from './sections/DepartmentsSection.vue'
import DictSection from './sections/DictSection.vue'
import LogsSection from './sections/LogsSection.vue'
import StatsSection from './sections/StatsSection.vue'
import IdridImportSection from './sections/IdridImportSection.vue'
import OrganizationApplicationsSection from './sections/OrganizationApplicationsSection.vue'
import TeachingReviewSection from './sections/TeachingReviewSection.vue'

type FrontRole = LoginApi.FrontRole

const router = useRouter()
const goBack = () => router.push('/')
const userStore = useUserStore()

const currentRole = computed<FrontRole | ''>(() => userStore.role)
const currentUserName = computed<string>(
  () => userStore.userInfo.name || userStore.userInfo.username || ''
)

const isAdmin = computed(() => userStore.isAdmin)
const isTeacher = computed(() => userStore.isDoctor)
const canManage = computed(() => userStore.canManage)

const activeTab = ref('notices')
</script>

<template>
  <div class="admin-page">
    <main class="admin-main">
      <el-tabs v-model="activeTab" type="card" class="admin-tabs">
        <el-tab-pane name="notices">
          <template #label>
            <span class="tab-label"><el-icon><Bell /></el-icon>公告 &amp; 消息</span>
          </template>
          <NoticesSection :can-manage="canManage" :can-delete="isAdmin" />
        </el-tab-pane>

        <el-tab-pane name="departments">
          <template #label>
            <span class="tab-label"><el-icon><OfficeBuilding /></el-icon>科室人员</span>
          </template>
          <DepartmentsSection :can-manage="isAdmin" />
        </el-tab-pane>

        <el-tab-pane name="dict">
          <template #label>
            <span class="tab-label"><el-icon><Collection /></el-icon>字典数据</span>
          </template>
          <DictSection />
        </el-tab-pane>

        <el-tab-pane name="logs">
          <template #label>
            <span class="tab-label"><el-icon><Document /></el-icon>系统日志</span>
          </template>
          <LogsSection :can-manage="isAdmin" />
        </el-tab-pane>

        <el-tab-pane name="stats">
          <template #label>
            <span class="tab-label"><el-icon><DataAnalysis /></el-icon>统计报表</span>
          </template>
          <StatsSection :can-manage="canManage" />
        </el-tab-pane>

        <el-tab-pane v-if="isAdmin" name="idrid">
          <template #label>
            <span class="tab-label"><el-icon><Upload /></el-icon>IDRiD 批量导入</span>
          </template>
          <IdridImportSection :can-manage="isAdmin" />
        </el-tab-pane>

        <el-tab-pane v-if="isAdmin" name="org-apps">
          <template #label>
            <span class="tab-label"><el-icon><Promotion /></el-icon>机构申请审核</span>
          </template>
          <OrganizationApplicationsSection :can-manage="isAdmin" />
        </el-tab-pane>

        <el-tab-pane v-if="isAdmin" name="teaching-review">
          <template #label>
            <span class="tab-label"><el-icon><Reading /></el-icon>教学病例审核</span>
          </template>
          <TeachingReviewSection :can-manage="isAdmin" />
        </el-tab-pane>
      </el-tabs>
    </main>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: #ffffff;
  display: flex;
  flex-direction: column;
}

.admin-header {
  height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e5e6eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.divider {
  width: 1px;
  height: 18px;
  background: #e5e6eb;
}

.page-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-main {
  flex: 1;
  padding: 20px 24px;
  max-width: none;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

.admin-tabs {
  background: transparent;
}

:deep(.el-tabs__header) {
  margin-bottom: 16px;
}

:deep(.el-tabs__content) {
  padding: 0;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
</style>
