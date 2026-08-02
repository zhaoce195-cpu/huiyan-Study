<script setup lang="ts">
import { computed } from 'vue'
import { Star, StarFilled, Document } from '@element-plus/icons-vue'
import { LearningApi } from '@/api'

type Resource = LearningApi.LearningResource

const props = defineProps<{
  resource: Resource
  canEdit: boolean
  canDelete: boolean
  showFavoriteToggle?: boolean
}>()

const emit = defineEmits<{
  (e: 'preview', r: Resource): void
  (e: 'toggle-fav', r: Resource): void
  (e: 'edit', r: Resource): void
  (e: 'delete', r: Resource): void
  (e: 'note', r: Resource): void
}>()

const tagList = computed(() =>
  (props.resource.tags || '').split(',').map((t) => t.trim()).filter(Boolean)
)

const typeColor: Record<string, string> = {
  CASE_TEMPLATE: '#1677ff',
  COURSEWARE: '#52c41a',
  KNOWLEDGE: '#faad14',
  IMAGE_DEMO: '#722ed1'
}
</script>

<template>
  <div class="resource-card">
    <div class="cover" :style="{ background: typeColor[resource.resourceType] + '14' }">
      <el-image v-if="resource.coverUrl" :src="resource.coverUrl" fit="cover" class="cover-img">
        <template #error>
          <div class="cover-fallback" :style="{ color: typeColor[resource.resourceType] }">
            <el-icon :size="40"><document /></el-icon>
          </div>
        </template>
      </el-image>
      <div v-else class="cover-fallback" :style="{ color: typeColor[resource.resourceType] }">
        <el-icon :size="40"><document /></el-icon>
      </div>
      <span
        class="type-tag"
        :style="{ background: typeColor[resource.resourceType], color: '#fff' }"
      >
        {{ resource.resourceTypeText }}
      </span>
    </div>

    <div class="meta">
      <h3 class="title" :title="resource.title">{{ resource.title }}</h3>
      <p class="summary">{{ resource.summary || '暂无简介' }}</p>

      <div v-if="tagList.length" class="tags">
        <el-tag v-for="t in tagList.slice(0, 4)" :key="t" size="small" effect="plain">
          {{ t }}
        </el-tag>
      </div>

      <div class="footer">
        <span class="stat">
          <el-icon><view /></el-icon>{{ resource.viewCount }}
        </span>
        <span class="stat">
          <el-icon><star /></el-icon>{{ resource.favoriteCount }}
        </span>
        <span v-if="resource.publisherName" class="publisher">
          {{ resource.publisherName }}
        </span>
      </div>

      <div class="actions">
        <el-button size="small" type="primary" @click="emit('preview', resource)">
          预览
        </el-button>
        <el-button
          v-if="showFavoriteToggle !== false"
          size="small"
          :type="resource.isFavorited ? 'warning' : 'default'"
          :icon="resource.isFavorited ? StarFilled : Star"
          @click="emit('toggle-fav', resource)"
        >
          {{ resource.isFavorited ? '已收藏' : '收藏' }}
        </el-button>
        <el-button size="small" plain @click="emit('note', resource)">
          记笔记
        </el-button>
        <el-button v-if="canEdit" size="small" plain @click="emit('edit', resource)">
          编辑
        </el-button>
        <el-button
          v-if="canDelete"
          size="small"
          type="danger"
          plain
          @click="emit('delete', resource)"
        >
          删除
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resource-card {
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;
}
.resource-card:hover {
  box-shadow: 0 8px 24px rgba(22, 119, 255, 0.1);
  transform: translateY(-2px);
}
.cover {
  position: relative;
  height: 130px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.cover-img {
  width: 100%;
  height: 100%;
}
.cover-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.type-tag {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
.meta {
  padding: 12px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}
.title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}
.summary {
  margin: 0;
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  height: 36px;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.footer {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #86909c;
  align-items: center;
  padding-top: 6px;
  border-top: 1px dashed #e5e6eb;
}
.stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.publisher {
  margin-left: auto;
  color: #4e5969;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
</style>
