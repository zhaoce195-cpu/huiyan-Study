<template>
  <view class="page cases">
    <view class="search-bar">
      <input
        class="search-input"
        v-model="keyword"
        placeholder="搜索病例号 / 机构"
        confirm-type="search"
        @confirm="onSearch"
      />
      <view class="search-btn" @click="onSearch">搜索</view>
    </view>

    <scroll-view scroll-x class="chips">
      <view class="chip" :class="{ active: drLevel === '' }" @click="setDr('')">全部分级</view>
      <view v-for="n in [0,1,2,3,4]" :key="n" class="chip" :class="{ active: drLevel === n }" @click="setDr(n)">
        {{ n }}级
      </view>
    </scroll-view>

    <scroll-view scroll-y class="list" @scrolltolower="loadMore" :refresher-enabled="true" :refresher-triggered="refreshing" @refresherrefresh="onRefresh">
      <view v-if="list.length === 0 && !loading" class="empty muted">暂无符合条件的病例</view>
      <view v-for="item in list" :key="item.id" class="case-card card" @click="goDetail(item)">
        <image v-if="item.thumbUrl || item.imageUrl" :src="img(item.thumbUrl || item.imageUrl)" class="thumb" mode="aspectFill" />
        <view v-else class="thumb thumb-empty">眼底图</view>
        <view class="case-info">
          <view class="case-top">
            <text class="cid">{{ item.id }}</text>
            <text v-if="item.done" class="done-tag">已练习</text>
          </view>
          <view class="case-grade">{{ item.drGrade || ('DR ' + item.drLevel + '级') }}</view>
          <view class="case-meta muted">{{ item.difficulty }} · {{ eyeText(item.eye) }} · 病程{{ item.diabetesYears }}年</view>
        </view>
      </view>
      <view v-if="loading" class="loading muted">加载中…</view>
      <view v-else-if="noMore && list.length > 0" class="loading muted">没有更多了</view>
    </scroll-view>
  </view>
</template>

<script>
import { getCaseList } from '../../api/training'
import { resolveUrl } from '../../utils/config'
import { useUserStore } from '../../store/user'

export default {
  data() {
    return {
      keyword: '',
      drLevel: '',
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
    img(u) { return resolveUrl(u) },
    eyeText(e) { return { OD: '右眼', OS: '左眼', OU: '双眼' }[e] || e },
    async fetch() {
      if (this.loading || this.noMore) return
      this.loading = true
      try {
        const res = await getCaseList({
          keyword: this.keyword,
          drLevel: this.drLevel,
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
    reload() {
      this.page = 1
      this.noMore = false
      this.list = []
      this.fetch()
    },
    onSearch() { this.reload() },
    setDr(v) { this.drLevel = v; this.reload() },
    loadMore() { this.fetch() },
    onRefresh() { this.refreshing = true; this.reload() },
    goDetail(item) {
      uni.navigateTo({ url: `/pages/case-detail/case-detail?caseId=${item.id}` })
    },
  },
}
</script>

<style scoped>
.cases { display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
.search-bar { display: flex; align-items: center; padding: 24rpx 32rpx 12rpx; gap: 16rpx; }
.search-input { flex: 1; height: 76rpx; background: #fff; border-radius: 999rpx; padding: 0 32rpx; font-size: 28rpx; }
.search-btn { color: #0d9488; font-size: 28rpx; padding: 0 8rpx; }
.chips { white-space: nowrap; padding: 8rpx 32rpx 16rpx; }
.chip {
  display: inline-block; padding: 10rpx 28rpx; background: #fff; border-radius: 999rpx;
  font-size: 26rpx; color: #6b7280; margin-right: 16rpx;
}
.chip.active { background: #0d9488; color: #fff; }
.list { flex: 1; padding: 8rpx 32rpx 32rpx; box-sizing: border-box; }
.case-card { display: flex; margin-bottom: 20rpx; align-items: center; }
.thumb { width: 140rpx; height: 140rpx; border-radius: 16rpx; margin-right: 24rpx; background: #000; flex-shrink: 0; }
.thumb-empty { display: flex; align-items: center; justify-content: center; color: #fff; font-size: 24rpx; }
.case-info { flex: 1; }
.case-top { display: flex; align-items: center; justify-content: space-between; }
.cid { font-size: 30rpx; font-weight: 600; }
.done-tag { font-size: 22rpx; color: #0d9488; border: 2rpx solid #0d9488; border-radius: 999rpx; padding: 2rpx 16rpx; }
.case-grade { font-size: 28rpx; margin: 12rpx 0 8rpx; color: #0f766e; font-weight: 500; }
.case-meta { font-size: 24rpx; }
.empty, .loading { text-align: center; padding: 48rpx; font-size: 26rpx; }
</style>
