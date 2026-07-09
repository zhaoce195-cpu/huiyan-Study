<template>
  <view class="page home">
    <view class="header">
      <view class="hello">{{ greeting }}，{{ store.displayName }}</view>
      <view class="role muted">{{ roleText }}</view>
    </view>

    <!-- 统计概览 -->
    <view class="stats card">
      <view class="stat">
        <view class="num">{{ stats.total }}</view>
        <view class="label muted">累计病例</view>
      </view>
      <view class="stat">
        <view class="num red">{{ stats.red }}</view>
        <view class="label muted">高危</view>
      </view>
      <view class="stat">
        <view class="num yellow">{{ stats.yellow }}</view>
        <view class="label muted">中危</view>
      </view>
      <view class="stat">
        <view class="num green">{{ stats.green }}</view>
        <view class="label muted">正常</view>
      </view>
    </view>

    <!-- 诊断入口 -->
    <view class="section-title">智能诊断</view>
    <view class="entry-grid">
      <view class="entry" @click="goDiagnose('COMPREHENSIVE')">
        <view class="entry-icon" style="background:#e6f0ff">🔬</view>
        <view class="entry-name">综合诊断</view>
        <view class="entry-desc muted">单图 MA+DR</view>
      </view>
      <view class="entry" @click="goDiagnose('MA')">
        <view class="entry-icon" style="background:#fff1e6">🩸</view>
        <view class="entry-name">MA 检测</view>
        <view class="entry-desc muted">微动脉瘤</view>
      </view>
      <view class="entry" @click="goDiagnose('DR')">
        <view class="entry-icon" style="background:#e8f9ee">👁️</view>
        <view class="entry-name">DR 分级</view>
        <view class="entry-desc muted">双眼评估</view>
      </view>
    </view>

    <view class="section-title flex-between">
      <text>最近病例</text>
      <text class="more" @click="goCases">全部 ›</text>
    </view>
    <view v-if="recent.length === 0" class="empty muted card">暂无病例，去做一次诊断吧</view>
    <view
      v-for="item in recent"
      :key="item.id"
      class="case-row card"
      @click="goDetail(item)"
    >
      <view class="case-main">
        <view class="case-name">{{ item.patientName || '未命名' }}</view>
        <view class="case-sub muted">{{ item.diagnosisSummary || item.dr || '—' }} · {{ item.createdAt }}</view>
      </view>
      <view class="risk-tag" :style="{ color: riskColor(item.risk), borderColor: riskColor(item.risk) }">
        {{ riskText(item.risk) }}
      </view>
    </view>
  </view>
</template>

<script>
import { useUserStore } from '../../store/user'
import { getScreeningStats, getScreeningList, RISK_TEXT, RISK_COLOR } from '../../api/screening'

export default {
  data() {
    return {
      store: useUserStore(),
      stats: { total: 0, red: 0, yellow: 0, green: 0 },
      recent: [],
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
      const map = { doctor: '带教医师', admin: '管理员', trainee: '学员', patient: '患者' }
      return (this.store.user && (map[this.store.user.role] || this.store.user.title)) || ''
    },
  },
  onShow() {
    if (!this.guard()) return
    this.loadData()
  },
  methods: {
    guard() {
      const store = useUserStore()
      if (!store.isLoggedIn) {
        uni.reLaunch({ url: '/pages/login/login' })
        return false
      }
      return true
    },
    async loadData() {
      try {
        this.stats = await getScreeningStats()
      } catch (e) {}
      try {
        const res = await getScreeningList({ page: 1, pageSize: 5, scope: 'archive' })
        this.recent = res.list || []
      } catch (e) {}
    },
    riskText(r) {
      return RISK_TEXT[r] || '待分析'
    },
    riskColor(r) {
      return RISK_COLOR[r] || '#9ca3af'
    },
    goDiagnose(type) {
      if (!this.store.canDiagnose) {
        uni.showToast({ title: '仅医生/管理员可发起诊断', icon: 'none' })
        return
      }
      uni.navigateTo({ url: `/pages/diagnose/diagnose?type=${type}` })
    },
    goCases() {
      uni.switchTab({ url: '/pages/cases/cases' })
    },
    goDetail(item) {
      uni.navigateTo({ url: `/pages/case-detail/case-detail?taskId=${item.id}` })
    },
  },
}
</script>

<style scoped>
.home {
  padding: 32rpx;
}
.header {
  margin-bottom: 24rpx;
}
.hello {
  font-size: 40rpx;
  font-weight: 700;
}
.role {
  font-size: 26rpx;
  margin-top: 6rpx;
}
.stats {
  display: flex;
  justify-content: space-between;
  margin-bottom: 36rpx;
}
.stat {
  text-align: center;
  flex: 1;
}
.num {
  font-size: 44rpx;
  font-weight: 700;
}
.num.red { color: #dc2626; }
.num.yellow { color: #d97706; }
.num.green { color: #16a34a; }
.label {
  font-size: 24rpx;
  margin-top: 6rpx;
}
.section-title {
  font-size: 30rpx;
  font-weight: 600;
  margin: 32rpx 8rpx 20rpx;
}
.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.more { color: #1677ff; font-size: 26rpx; font-weight: 400; }
.entry-grid {
  display: flex;
  gap: 20rpx;
}
.entry {
  flex: 1;
  background: #fff;
  border-radius: 20rpx;
  padding: 32rpx 16rpx;
  text-align: center;
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.04);
}
.entry-icon {
  width: 88rpx;
  height: 88rpx;
  line-height: 88rpx;
  margin: 0 auto 16rpx;
  border-radius: 24rpx;
  font-size: 44rpx;
}
.entry-name {
  font-size: 28rpx;
  font-weight: 600;
}
.entry-desc {
  font-size: 22rpx;
  margin-top: 4rpx;
}
.case-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.case-name {
  font-size: 30rpx;
  font-weight: 600;
}
.case-sub {
  font-size: 24rpx;
  margin-top: 8rpx;
}
.risk-tag {
  border: 2rpx solid;
  border-radius: 999rpx;
  padding: 6rpx 22rpx;
  font-size: 24rpx;
}
.empty {
  text-align: center;
  padding: 48rpx;
  font-size: 26rpx;
}
</style>
