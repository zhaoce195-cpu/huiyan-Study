<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { LearningApi } from '@/api'

type Resource = LearningApi.LearningResource

const props = defineProps<{
  visible: boolean
  resource: Resource | null
  canFavorite?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'fav-changed', r: Resource): void
  (e: 'note', r: Resource): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v)
})

const tagList = computed(() => {
  if (!props.resource) return []
  return (props.resource.tags || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
})

const submitting = ref(false)

const toggleFav = async () => {
  if (!props.resource) return
  submitting.value = true
  try {
    if (props.resource.isFavorited) {
      await LearningApi.removeFavorite(props.resource.id)
      const next: Resource = {
        ...props.resource,
        isFavorited: false,
        favoriteCount: Math.max(0, props.resource.favoriteCount - 1)
      }
      emit('fav-changed', next)
    } else {
      const out = await LearningApi.addFavorite({ resourceId: props.resource.id })
      emit('fav-changed', out)
    }
  } finally {
    submitting.value = false
  }
}

const onNote = () => {
  if (!props.resource) return
  emit('note', props.resource)
}

watch(() => props.resource?.id, () => {
  /* re-render on resource change */
})

const renderContent = (html: string) => html || ''

const previewVideoOk = (url: string) =>
  /\.(mp4|webm|ogg)(\?|$)/i.test(url)

const previewPdfOk = (url: string) =>
  /\.pdf(\?|$)/i.test(url)

const previewImageOk = (url: string, type: string) =>
  type === 'image' || /\.(png|jpe?g|gif|webp|bmp)(\?|$)/i.test(url)

const goExternal = () => {
  if (!props.resource?.fileUrl) {
    ElMessage.warning('该资料未提供附件链接')
    return
  }
  window.open(props.resource.fileUrl, '_blank')
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    width="800px"
    top="6vh"
    destroy-on-close
    :title="resource?.title || '资料预览'"
  >
    <div v-if="resource" class="preview-body">
      <div class="meta-line">
        <el-tag size="small" type="primary">{{ resource.resourceTypeText }}</el-tag>
        <el-tag size="small" effect="plain">浏览 {{ resource.viewCount }}</el-tag>
        <!-- 同 ResourceCard：这个收藏标签也做成可点，底部按钮保留 -->
        <el-tag
          size="small"
          class="fav-tag"
          :effect="resource.isFavorited ? 'dark' : 'plain'"
          :type="resource.isFavorited ? 'warning' : 'info'"
          :title="resource.isFavorited ? '取消收藏' : '收藏'"
          @click="toggleFav"
        >
          收藏 {{ resource.favoriteCount }}
        </el-tag>
        <span v-if="resource.publisherName" class="publisher">
          上传者：{{ resource.publisherName }}
        </span>
      </div>

      <div v-if="tagList.length" class="tags">
        <el-tag v-for="t in tagList" :key="t" size="small">{{ t }}</el-tag>
      </div>

      <div v-if="resource.summary" class="summary">
        <strong>简介：</strong>{{ resource.summary }}
      </div>

      <div class="preview-area">
        <video
          v-if="resource.fileUrl && previewVideoOk(resource.fileUrl)"
          :src="resource.fileUrl"
          controls
          class="video"
        />
        <iframe
          v-else-if="resource.fileUrl && previewPdfOk(resource.fileUrl)"
          :src="resource.fileUrl"
          class="pdf-frame"
        />
        <el-image
          v-else-if="resource.fileUrl && previewImageOk(resource.fileUrl, resource.fileType)"
          :src="resource.fileUrl"
          fit="contain"
          class="image"
        />
        <div v-else-if="resource.content" class="content-html" v-html="renderContent(resource.content)" />
        <el-empty v-else description="该资料暂未提供可在线预览的内容" />
      </div>

      <div v-if="resource.fileUrl" class="external">
        <el-button link type="primary" @click="goExternal">
          在新窗口打开附件 →
        </el-button>
      </div>
    </div>

    <template #footer>
      <div class="footer-actions">
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button
          v-if="canFavorite !== false && resource"
          :type="resource.isFavorited ? 'warning' : 'primary'"
          :loading="submitting"
          @click="toggleFav"
        >
          {{ resource.isFavorited ? '取消收藏' : '加入收藏' }}
        </el-button>
        <el-button type="success" @click="onNote">
          记笔记
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.preview-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.meta-line {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.fav-tag {
  cursor: pointer;
}
.publisher {
  margin-left: 6px;
  font-size: 13px;
  color: #4e5969;
}
.tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.summary {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
}
.preview-area {
  min-height: 200px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafbfc;
}
.video {
  width: 100%;
  max-height: 460px;
  background: #000;
}
.pdf-frame {
  width: 100%;
  height: 460px;
  border: 0;
}
.image {
  max-width: 100%;
  max-height: 460px;
}
.content-html {
  width: 100%;
  font-size: 14px;
  color: #1d2129;
  line-height: 1.7;
  white-space: pre-wrap;
}
.external {
  text-align: right;
}
.footer-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
