<template>
  <view class="page res-detail" v-if="res">
    <image v-if="res.coverUrl" :src="img(res.coverUrl)" class="cover" mode="widthFix" />
    <view class="card">
      <view class="title">{{ res.title }}</view>
      <view class="meta muted">
        <text>{{ typeText(res.resourceType) }}</text>
        <text>{{ res.publisherName || '官方' }}</text>
        <text>👁 {{ res.viewCount || 0 }}</text>
      </view>
      <view class="tags" v-if="res.tags">
        <text class="tag" v-for="(t, i) in tagList" :key="i">#{{ t }}</text>
      </view>
      <view class="summary" v-if="res.summary">{{ res.summary }}</view>
    </view>

    <view class="card content" v-if="res.content">
      <view class="content-text">{{ res.content }}</view>
    </view>

    <view class="card file" v-if="res.fileUrl">
      <view class="file-label muted">附件 / 资源</view>
      <button class="btn-outline" @click="openFile">{{ fileBtnText }}</button>
    </view>

    <view class="actions">
      <button class="fav-btn" :class="{ on: res.isFavorited }" @click="toggleFav">
        {{ res.isFavorited ? '★ 已收藏' : '☆ 收藏' }}
      </button>
    </view>
  </view>
</template>

<script>
import { getResource, addFavorite, removeFavorite, RESOURCE_TYPE_TEXT } from '../../api/learning'
import { resolveUrl } from '../../utils/config'

export default {
  data() {
    return { id: 0, res: null }
  },
  computed: {
    tagList() {
      return this.res && this.res.tags ? this.res.tags.split(/[,，\s]+/).filter(Boolean) : []
    },
    fileBtnText() {
      const ft = (this.res && this.res.fileType) || ''
      if (ft === 'pdf') return '打开 PDF 文档'
      if (ft === 'video') return '播放视频'
      if (ft === 'image') return '查看图片'
      return '打开资源'
    },
  },
  onLoad(options) {
    this.id = options.id
    this.load()
  },
  methods: {
    async load() {
      try {
        this.res = await getResource(this.id)
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      }
    },
    img(u) { return resolveUrl(u) },
    typeText(t) { return RESOURCE_TYPE_TEXT[t] || '资料' },
    openFile() {
      const url = resolveUrl(this.res.fileUrl)
      const ft = this.res.fileType
      if (ft === 'image') {
        uni.previewImage({ urls: [url] })
        return
      }
      if (ft === 'pdf') {
        uni.showLoading({ title: '下载中' })
        uni.downloadFile({
          url,
          success: (r) => {
            uni.hideLoading()
            uni.openDocument({ filePath: r.tempFilePath, fileType: 'pdf', showMenu: true })
          },
          fail: () => {
            uni.hideLoading()
            uni.showToast({ title: '打开失败', icon: 'none' })
          },
        })
        return
      }
      // 视频 / 外链：复制链接
      uni.setClipboardData({ data: url, success: () => uni.showToast({ title: '链接已复制', icon: 'none' }) })
    },
    async toggleFav() {
      try {
        if (this.res.isFavorited) {
          await removeFavorite(this.res.id)
          this.res.isFavorited = false
          this.res.favoriteCount = Math.max(0, (this.res.favoriteCount || 1) - 1)
        } else {
          await addFavorite(this.res.id)
          this.res.isFavorited = true
          this.res.favoriteCount = (this.res.favoriteCount || 0) + 1
        }
      } catch (e) {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
  },
}
</script>

<style scoped>
.res-detail { padding: 32rpx; }
.cover { width: 100%; border-radius: 20rpx; margin-bottom: 24rpx; }
.title { font-size: 36rpx; font-weight: 700; line-height: 1.4; }
.meta { display: flex; gap: 24rpx; font-size: 24rpx; margin-top: 16rpx; }
.tags { margin-top: 16rpx; }
.tag { font-size: 24rpx; color: #0f766e; margin-right: 16rpx; }
.summary { font-size: 28rpx; color: #374151; margin-top: 20rpx; line-height: 1.6; }
.content { margin-top: 24rpx; }
.content-text { font-size: 28rpx; line-height: 1.8; white-space: pre-wrap; }
.file { margin-top: 24rpx; }
.file-label { font-size: 24rpx; margin-bottom: 16rpx; }
.file .btn-outline { height: 84rpx; line-height: 84rpx; }
.actions { margin-top: 40rpx; }
.fav-btn {
  height: 92rpx; line-height: 92rpx; border-radius: 999rpx;
  background: #fff; color: #0d9488; border: 2rpx solid #0d9488; font-size: 30rpx;
}
.fav-btn.on { background: #0d9488; color: #fff; }
</style>
