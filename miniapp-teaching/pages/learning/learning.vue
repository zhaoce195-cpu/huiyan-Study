<template>
  <view class="page learning">
    <view class="search-bar">
      <input class="search-input" v-model="keyword" placeholder="搜索资料标题 / 标签" confirm-type="search" @confirm="onSearch" />
      <view class="search-btn" @click="onSearch">搜索</view>
    </view>

    <scroll-view scroll-x class="chips">
      <view
        v-for="t in typeOptions"
        :key="t.value"
        class="chip"
        :class="{ active: resourceType === t.value }"
        @click="setType(t.value)"
      >
        {{ t.label }}
      </view>
    </scroll-view>

    <scroll-view scroll-y class="list" @scrolltolower="loadMore" :refresher-enabled="true" :refresher-triggered="refreshing" @refresherrefresh="onRefresh">
      <view v-if="list.length === 0 && !loading" class="empty muted">暂无学习资料</view>
      <view v-for="item in list" :key="item.id" class="res-card card" @click="goDetail(item)">
        <view class="res-top">
          <text class="res-title">{{ item.title }}</text>
          <text class="res-type">{{ typeText(item.resourceType) }}</text>
        </view>
        <view class="res-summary muted">{{ item.summary || '暂无简介' }}</view>
        <view class="res-foot muted">
          <text>{{ item.publisherName || '官方' }}</text>
          <text>👁 {{ item.viewCount || 0 }} · ⭐ {{ item.favoriteCount || 0 }}</text>
        </view>
      </view>
      <view v-if="loading" class="loading muted">加载中…</view>
      <view v-else-if="noMore && list.length > 0" class="loading muted">没有更多了</view>
    </scroll-view>
  </view>
</template>

<script>
import { listResources, RESOURCE_TYPE_TEXT, RESOURCE_TYPE_OPTIONS } from '../../api/learning'
import { useUserStore } from '../../store/user'

export default {
  data() {
    return {
      keyword: '',
      resourceType: '',
      typeOptions: RESOURCE_TYPE_OPTIONS,
      list: [],
      page: 1,
      pageSize: 10,
      total: 0,
      loading: false,
      noMore: false,
      refreshing: false,
    }
  },
  onShow() {
    const store = useUserStore()
    if (!store.isLoggedIn) {
      uni.reLaunch({ url: '/pages/login/login' })
      return
    }
    if (this.list.length === 0) this.reload()
  },
  methods: {
    typeText(t) { return RESOURCE_TYPE_TEXT[t] || '资料' },
    async fetch() {
      if (this.loading || this.noMore) return
      this.loading = true
      try {
        const res = await listResources({
          keyword: this.keyword,
          resourceType: this.resourceType,
          status: 'PUBLISHED',
          page: this.page,
          pageSize: this.pageSize,
        })
        const items = res.list || []
        this.total = res.total || 0
        this.list = this.page === 1 ? items : this.list.concat(items)
        this.noMore = this.list.length >= this.total
        if (items.length) this.page += 1
      } catch (e) {
      } finally {
        this.loading = false
        this.refreshing = false
      }
    },
    reload() { this.page = 1; this.noMore = false; this.list = []; this.fetch() },
    onSearch() { this.reload() },
    setType(v) { this.resourceType = v; this.reload() },
    loadMore() { this.fetch() },
    onRefresh() { this.refreshing = true; this.reload() },
    goDetail(item) {
      uni.navigateTo({ url: `/pages/resource-detail/resource-detail?id=${item.id}` })
    },
  },
}
</script>

<style scoped>
.learning { display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
.search-bar { display: flex; align-items: center; padding: 24rpx 32rpx 12rpx; gap: 16rpx; }
.search-input { flex: 1; height: 76rpx; background: #fff; border-radius: 999rpx; padding: 0 32rpx; font-size: 28rpx; }
.search-btn { color: #0d9488; font-size: 28rpx; padding: 0 8rpx; }
.chips { white-space: nowrap; padding: 8rpx 32rpx 16rpx; }
.chip { display: inline-block; padding: 10rpx 28rpx; background: #fff; border-radius: 999rpx; font-size: 26rpx; color: #6b7280; margin-right: 16rpx; }
.chip.active { background: #0d9488; color: #fff; }
.list { flex: 1; padding: 8rpx 32rpx 32rpx; box-sizing: border-box; }
.res-card { margin-bottom: 20rpx; }
.res-top { display: flex; justify-content: space-between; align-items: flex-start; }
.res-title { font-size: 30rpx; font-weight: 600; flex: 1; margin-right: 16rpx; }
.res-type { font-size: 22rpx; color: #0f766e; background: #d1faf3; border-radius: 999rpx; padding: 4rpx 18rpx; flex-shrink: 0; }
.res-summary { font-size: 26rpx; margin: 14rpx 0; line-height: 1.5; }
.res-foot { display: flex; justify-content: space-between; font-size: 22rpx; }
.empty, .loading { text-align: center; padding: 48rpx; font-size: 26rpx; }
</style>
