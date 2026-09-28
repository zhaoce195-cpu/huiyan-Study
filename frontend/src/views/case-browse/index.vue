<script setup lang="ts">
/**
 * 病例中心。教师 / 管理员在同一页切换检索、AI 建案、教学分享。
 * 学员只看到病例检索列表。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import CaseBrowseWorkspace from './CaseBrowseWorkspace.vue'
import AiCaseBuilder from '@/views/training/ai-case-builder.vue'
import TeachingShare from '@/views/training/teaching-share.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isTeacher = computed(() => userStore.isAdmin || userStore.isDoctor)

const TAB_NAMES = ['browse', 'ai-builder', 'my-shares'] as const

const caseCenterTab = computed({
  get() {
    const raw = String(route.query.tab || 'browse')
    return (TAB_NAMES as readonly string[]).includes(raw) ? raw : 'browse'
  },
  set(name: string) {
    const tab = (TAB_NAMES as readonly string[]).includes(name) ? name : 'browse'
    if (tab === String(route.query.tab || 'browse')) return
    const next = { ...route.query, tab }
    router.replace({ path: route.path, query: next })
  }
})
</script>

<template>
  <div class="case-hub">
    <el-tabs
      v-if="isTeacher"
      v-model="caseCenterTab"
      type="card"
      class="case-center-tabs"
    >
      <el-tab-pane label="病例检索库" name="browse">
        <CaseBrowseWorkspace embedded />
      </el-tab-pane>
      <el-tab-pane label="AI 智能建案" name="ai-builder" lazy>
        <AiCaseBuilder embedded />
      </el-tab-pane>
      <el-tab-pane label="我的教学分享" name="my-shares" lazy>
        <TeachingShare embedded />
      </el-tab-pane>
    </el-tabs>
    <CaseBrowseWorkspace v-else />
  </div>
</template>

<style scoped>
.case-hub {
  min-height: 100vh;
  background: #edf1f6;
}
.case-center-tabs {
  padding: 16px 16px 0;
}
.case-center-tabs :deep(.el-tabs__header) {
  margin: 0 8px 0;
}
.case-center-tabs :deep(.el-tabs__item) {
  font-weight: 600;
}
.case-center-tabs :deep(.el-tabs__content) {
  background: transparent;
}
</style>
