<template>
  <view class="page cases">
    <view class="search-bar">
      <input
        class="search-input"
        v-model="keyword"
        placeholder="搜索姓名 / 病例号 / 手机号"
        confirm-type="search"
        @confirm="onSearch"
      />
      <view class="search-btn" @click="onSearch">搜索</view>
    </view>

    <view class="filters">
      <view
        v-for="f in riskFilters"
        :key="f.v"
        class="filter"
        :class="{ active: risk === f.v }"
        @click="setRisk(f.v)"
      >
        {{ f.t }}
      </view>
    </view>

    <scroll-view scroll-y class="list" @scrolltolower="loadMore" :refresher-enabled="true" :refresher-triggered="refreshing" @refresherrefresh="onRefresh">
      <view v-if="list.length === 0 && !loading" class="empty muted">暂无符合条件的病例</view>
      <view
        v-for="item in list"
        :key="item.id"
        class="case-card card"
        @click="goDetail(item)"
      >
        <view class="case-top">
          <text class="name">{{ item.patientName || '未命名' }}</text>
          <view class="risk" :style="{ color: riskColor(item.risk), borderColor: riskColor(item.risk) }">
            {{ riskText(item.risk) }}
          </view>
        </view>
        <view class="case-mid muted">{{ item.diagnosisSummary || item.dr || '待分析' }}</view>
        <view class="case-bottom muted">
          <text>{{ item.caseSn || item.id }}</text>
          <text>{{ statusText(item.status) }} · {{ item.createdAt }}</text>
        </view>
      </view>
      <view v-if="loading" class="loading muted">加载中…</view>
      <view v-else-if="noMore && list.length > 0" class="loading muted">没有更多了</view>
    </scroll-view>
  </view>
</template>

<script>
import { getScreeningList, RISK_TEXT, RISK_COLOR, STATUS_TEXT } from '../../api/screening'
import { useUserStore } from '../../store/user'

export default {
  data() {
    return {
      keyword: '',
      risk: '',
      riskFilters: [
        { v: '', t: '全部' },
        { v: 'red', t: '高危' },
        { v: 'yellow', t: '中危' },
        { v: 'green', t: '正常' },
      ],
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
    riskText(r) { return RISK_TEXT[r] || '待分析' },
    riskColor(r) { return RISK_COLOR[r] || '#9ca3af' },
    statusText(s) { return STATUS_TEXT[s] || s || '' },
    async fetch() {
      if (this.loading || this.noMore) return
      this.loading = true
      try {
        const res = await getScreeningList({
          keyword: this.keyword,
          risk: this.risk,
          scope: 'archive',
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
    setRisk(v) {
      this.risk = v
      this.reload()
    },
    loadMore() { this.fetch() },
    onRefresh() {
      this.refreshing = true
      this.reload()
    },
    goDetail(item) {
      uni.navigateTo({ url: `/pages/case-detail/case-detail?taskId=${item.id}` })
    },
  },
}
</script>

<style scoped>
.cases {
  display: flex;
  flex-direction: column;
  height: 100vh;
  box-sizing: border-box;
}
.search-bar {
  display: flex;
  align-items: center;
  padding: 24rpx 32rpx 12rpx;
  gap: 16rpx;
}
.search-input {
  flex: 1;
  height: 76rpx;
  background: #fff;
  border-radius: 999rpx;
  padding: 0 32rpx;
  font-size: 28rpx;
}
.search-btn {
  color: #1677ff;
  font-size: 28rpx;
  padding: 0 8rpx;
}
.filters {
  display: flex;
  gap: 16rpx;
  padding: 12rpx 32rpx 16rpx;
}
.filter {
  padding: 10rpx 32rpx;
  background: #fff;
  border-radius: 999rpx;
  font-size: 26rpx;
  color: #6b7280;
}
.filter.active {
  background: #1677ff;
  color: #fff;
}
.list {
  flex: 1;
  padding: 8rpx 32rpx 32rpx;
  box-sizing: border-box;
}
.case-card {
  margin-bottom: 20rpx;
}
.case-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  font-size: 32rpx;
  font-weight: 600;
}
.risk {
  border: 2rpx solid;
  border-radius: 999rpx;
  padding: 4rpx 20rpx;
  font-size: 24rpx;
}
.case-mid {
  font-size: 26rpx;
  margin: 14rpx 0;
  color: #374151;
}
.case-bottom {
  display: flex;
  justify-content: space-between;
  font-size: 22rpx;
}
.empty, .loading {
  text-align: center;
  padding: 48rpx;
  font-size: 26rpx;
}
</style>
