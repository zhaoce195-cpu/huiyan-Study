<template>
  <view class="page home">
    <view class="header">
      <view class="hello">{{ greeting }}，{{ store.displayName }}</view>
      <view class="role muted">{{ roleText }}</view>
    </view>

    <!-- 培训进度 -->
    <view class="stats card">
      <view class="stat">
        <view class="num">{{ stats.doneCases }}/{{ stats.totalCases }}</view>
        <view class="label muted">已练习/病例</view>
      </view>
      <view class="stat">
        <view class="num">{{ pct(stats.avgIoU) }}</view>
        <view class="label muted">平均 IoU</view>
      </view>
      <view class="stat">
        <view class="num">{{ pct(stats.bestIoU) }}</view>
        <view class="label muted">最佳 IoU</view>
      </view>
    </view>

    <view class="section-title">实训功能</view>
    <view class="entry-grid">
      <view class="entry" @click="goCases">
        <view class="entry-icon" style="background:#d1faf3">🗂️</view>
        <view class="entry-name">病例库</view>
        <view class="entry-desc muted">检索阅片</view>
      </view>
      <view class="entry" @click="goRandom">
        <view class="entry-icon" style="background:#dbeafe">✍️</view>
        <view class="entry-name">开始练习</view>
        <view class="entry-desc muted">标注自评</view>
      </view>
      <view class="entry" @click="goLearning">
        <view class="entry-icon" style="background:#fef3c7">📚</view>
        <view class="entry-name">学习资料</view>
        <view class="entry-desc muted">课件知识</view>
      </view>
    </view>

    <view class="section-title flex-between">
      <text>待练习病例</text>
      <text class="more" @click="goCases">全部 ›</text>
    </view>
    <view v-if="todo.length === 0" class="empty muted card">病例都练完啦，去看看学习资料吧</view>
    <view v-for="item in todo" :key="item.id" class="case-row card" @click="goDetail(item)">
      <view class="case-main">
        <view class="case-name">{{ item.id }} · {{ item.drGrade }}</view>
        <view class="case-sub muted">{{ item.difficulty }} · {{ item.eye }} · {{ item.hospital || '—' }}</view>
      </view>
      <view class="go">去练习 ›</view>
    </view>
  </view>
</template>

<script>
import { useUserStore } from '../../store/user'
import { getTrainingStats, getCaseList } from '../../api/training'

export default {
  data() {
    return {
      store: useUserStore(),
      stats: { totalCases: 0, doneCases: 0, avgIoU: 0, bestIoU: 0 },
      todo: [],
    }
  },
  computed: {
    greeting() {
      const h = new Date().getHours()
      if (h < 6) return '凌晨好'
      if (h < 12) return '早上好'
      if (h < 14) return '中午好'
      if (h < 18) return '下午好'
      return '晚上好'
    },
    roleText() {
      const map = { doctor: '带教老师', admin: '管理员', trainee: '学员', patient: '患者' }
      return (this.store.user && (map[this.store.user.role] || this.store.user.title)) || ''
    },
  },
  onShow() {
    const store = useUserStore()
    if (!store.isLoggedIn) {
      uni.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.load()
  },
  methods: {
    pct(v) {
      return v ? Math.round(v * 100) + '%' : '—'
    },
    async load() {
      try {
        this.stats = await getTrainingStats()
      } catch (e) {}
      try {
        const res = await getCaseList({ done: false, page: 1, pageSize: 5 })
        this.todo = res.list || []
      } catch (e) {}
    },
    goCases() { uni.switchTab({ url: '/pages/cases/cases' }) },
    goLearning() { uni.switchTab({ url: '/pages/learning/learning' }) },
    goRandom() {
      // 随机取一个未完成病例进入阅片
      getCaseList({ done: false, page: 1, pageSize: 1 }).then((res) => {
        const c = (res.list || [])[0]
        if (c) uni.navigateTo({ url: `/pages/reading/reading?caseId=${c.id}` })
        else uni.showToast({ title: '暂无待练习病例', icon: 'none' })
      })
    },
    goDetail(item) {
      uni.navigateTo({ url: `/pages/case-detail/case-detail?caseId=${item.id}` })
    },
  },
}
</script>

<style scoped>
.home { padding: 32rpx; }
.header { margin-bottom: 24rpx; }
.hello { font-size: 40rpx; font-weight: 700; }
.role { font-size: 26rpx; margin-top: 6rpx; }
.stats { display: flex; justify-content: space-between; margin-bottom: 36rpx; }
.stat { text-align: center; flex: 1; }
.num { font-size: 40rpx; font-weight: 700; color: #0d9488; }
.label { font-size: 24rpx; margin-top: 6rpx; }
.section-title { font-size: 30rpx; font-weight: 600; margin: 32rpx 8rpx 20rpx; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.more { color: #0d9488; font-size: 26rpx; font-weight: 400; }
.entry-grid { display: flex; gap: 20rpx; }
.entry {
  flex: 1; background: #fff; border-radius: 20rpx; padding: 32rpx 16rpx;
  text-align: center; box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.04);
}
.entry-icon { width: 88rpx; height: 88rpx; line-height: 88rpx; margin: 0 auto 16rpx; border-radius: 24rpx; font-size: 44rpx; }
.entry-name { font-size: 28rpx; font-weight: 600; }
.entry-desc { font-size: 22rpx; margin-top: 4rpx; }
.case-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16rpx; }
.case-name { font-size: 30rpx; font-weight: 600; }
.case-sub { font-size: 24rpx; margin-top: 8rpx; }
.go { color: #0d9488; font-size: 26rpx; }
.empty { text-align: center; padding: 48rpx; font-size: 26rpx; }
</style>
