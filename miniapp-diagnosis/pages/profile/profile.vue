<template>
  <view class="page profile">
    <view class="profile-head">
      <image v-if="avatar" :src="avatar" class="avatar" mode="aspectFill" />
      <view v-else class="avatar avatar-fallback">{{ initial }}</view>
      <view class="p-name">{{ store.displayName }}</view>
      <view class="p-sub muted">{{ subText }}</view>
    </view>

    <view class="menu card">
      <view class="menu-item" @click="goCases">
        <text>我的病例</text><text class="arrow muted">›</text>
      </view>
      <view class="menu-item" @click="refresh">
        <text>刷新个人信息</text><text class="arrow muted">›</text>
      </view>
      <view class="menu-item" @click="about">
        <text>关于</text><text class="arrow muted">›</text>
      </view>
    </view>

    <button class="btn-outline logout" @click="onLogout">退出登录</button>
    <view class="ver muted">慧眼·辅助诊断 v1.0.0</view>
  </view>
</template>

<script>
import { useUserStore } from '../../store/user'
import { resolveUrl } from '../../utils/config'

export default {
  data() {
    return { store: useUserStore() }
  },
  computed: {
    avatar() {
      return this.store.user && this.store.user.avatar ? resolveUrl(this.store.user.avatar) : ''
    },
    initial() {
      const n = this.store.displayName || '?'
      return n.charAt(0)
    },
    subText() {
      const u = this.store.user
      if (!u) return ''
      return [u.department, u.title, u.roleName].filter(Boolean).join(' · ')
    },
  },
  onShow() {
    if (!this.store.isLoggedIn) uni.reLaunch({ url: '/pages/login/login' })
  },
  methods: {
    goCases() { uni.switchTab({ url: '/pages/cases/cases' }) },
    async refresh() {
      await this.store.refreshProfile()
      uni.showToast({ title: '已刷新', icon: 'success' })
    },
    about() {
      uni.showModal({
        title: '关于',
        content: '慧眼眼底 AI 辅助诊断小程序，提供微动脉瘤检测、DR 分级与综合诊断。结果仅供辅助参考。',
        showCancel: false,
      })
    },
    onLogout() {
      uni.showModal({
        title: '提示',
        content: '确定退出登录？',
        success: async (r) => {
          if (r.confirm) {
            await this.store.logout()
            uni.reLaunch({ url: '/pages/login/login' })
          }
        },
      })
    },
  },
}
</script>

<style scoped>
.profile { padding: 32rpx; }
.profile-head {
  text-align: center;
  padding: 48rpx 0 40rpx;
}
.avatar {
  width: 140rpx;
  height: 140rpx;
  border-radius: 50%;
  margin: 0 auto 20rpx;
}
.avatar-fallback {
  line-height: 140rpx;
  background: #1677ff;
  color: #fff;
  font-size: 60rpx;
  font-weight: 700;
}
.p-name { font-size: 38rpx; font-weight: 700; }
.p-sub { font-size: 26rpx; margin-top: 10rpx; }
.menu { padding: 0 32rpx; }
.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 32rpx 0;
  font-size: 30rpx;
  border-bottom: 2rpx solid #f3f4f6;
}
.menu-item:last-child { border-bottom: none; }
.arrow { font-size: 36rpx; }
.logout {
  margin-top: 48rpx;
  height: 92rpx;
  line-height: 92rpx;
  background: #fff;
  color: #dc2626;
  border: 2rpx solid #fca5a5;
  border-radius: 999rpx;
  font-size: 30rpx;
}
.ver { text-align: center; font-size: 22rpx; margin-top: 32rpx; }
</style>
