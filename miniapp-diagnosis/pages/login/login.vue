<template>
  <view class="login-page">
    <view class="hero">
      <view class="logo">慧眼</view>
      <view class="title">眼底 AI 辅助诊断</view>
      <view class="subtitle">微动脉瘤检测 · DR 分级 · 综合诊断</view>
    </view>

    <view class="panel">
      <!-- 模式一：微信登录 -->
      <block v-if="mode === 'wechat'">
        <button class="btn-primary big" :loading="loading" @click="onWechatLogin">
          微信一键登录
        </button>
        <view class="switch" @click="mode = 'account'">使用账号密码登录</view>
      </block>

      <!-- 模式二：微信首次绑定已有账号 -->
      <block v-else-if="mode === 'bind'">
        <view class="form-tip">检测到微信尚未绑定平台账号，请绑定一次</view>
        <input class="field" v-model="username" placeholder="平台账号 / 医师工号" />
        <input class="field" v-model="password" password placeholder="密码" />
        <button class="btn-primary big" :loading="loading" @click="onBind">绑定并登录</button>
        <view class="switch" @click="resetToWechat">返回</view>
      </block>

      <!-- 模式三：账号密码登录（开发/兜底） -->
      <block v-else>
        <input class="field" v-model="username" placeholder="账号" />
        <input class="field" v-model="password" password placeholder="密码" />
        <button class="btn-primary big" :loading="loading" @click="onAccountLogin">登录</button>
        <view class="switch" @click="mode = 'wechat'">返回微信登录</view>
      </block>
    </view>

    <view class="footer muted">慧眼医疗云平台 · 仅供医务人员使用</view>
  </view>
</template>

<script>
import { useUserStore } from '../../store/user'
import { getWxCode, wechatLogin, wechatBind, loginByPassword } from '../../api/auth'

export default {
  data() {
    return {
      mode: 'wechat', // wechat | bind | account
      username: '',
      password: '',
      ticket: '',
      loading: false,
      redirect: '',
    }
  },
  onLoad(options) {
    this.redirect = options.redirect || ''
    const store = useUserStore()
    if (store.isLoggedIn) this.goHome()
  },
  methods: {
    goHome() {
      if (this.redirect) {
        uni.reLaunch({ url: decodeURIComponent(this.redirect) })
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },
    finishLogin(token, user) {
      useUserStore().setLogin(token, user)
      uni.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => this.goHome(), 500)
    },
    async onWechatLogin() {
      this.loading = true
      try {
        const code = await getWxCode()
        const res = await wechatLogin(code)
        if (res.needBind) {
          this.ticket = res.ticket
          this.mode = 'bind'
          uni.showToast({ title: '请绑定已有账号', icon: 'none' })
        } else {
          this.finishLogin(res.token, res.user)
        }
      } catch (e) {
        uni.showToast({ title: (e && e.msg) || '微信登录失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    async onBind() {
      if (!this.username || !this.password) {
        uni.showToast({ title: '请输入账号和密码', icon: 'none' })
        return
      }
      this.loading = true
      try {
        const res = await wechatBind(this.ticket, this.username, this.password)
        this.finishLogin(res.token, res.user)
      } catch (e) {
        uni.showToast({ title: (e && e.msg) || '绑定失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    async onAccountLogin() {
      if (!this.username || !this.password) {
        uni.showToast({ title: '请输入账号和密码', icon: 'none' })
        return
      }
      this.loading = true
      try {
        const res = await loginByPassword(this.username, this.password)
        this.finishLogin(res.token, res.user)
      } catch (e) {
        uni.showToast({ title: (e && e.msg) || '账号或密码错误', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    resetToWechat() {
      this.mode = 'wechat'
      this.username = ''
      this.password = ''
    },
  },
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #1677ff 0%, #0958d9 45%, #f5f7fa 45%);
  padding: 0 48rpx;
  box-sizing: border-box;
}
.hero {
  padding-top: 160rpx;
  text-align: center;
  color: #fff;
}
.logo {
  width: 132rpx;
  height: 132rpx;
  line-height: 132rpx;
  margin: 0 auto 24rpx;
  border-radius: 32rpx;
  background: rgba(255, 255, 255, 0.18);
  font-size: 52rpx;
  font-weight: 700;
}
.title {
  font-size: 44rpx;
  font-weight: 700;
}
.subtitle {
  margin-top: 12rpx;
  font-size: 26rpx;
  opacity: 0.85;
}
.panel {
  margin-top: 120rpx;
  background: #fff;
  border-radius: 24rpx;
  padding: 48rpx 40rpx;
  box-shadow: 0 12rpx 40rpx rgba(0, 0, 0, 0.08);
}
.form-tip {
  font-size: 26rpx;
  color: #d97706;
  margin-bottom: 24rpx;
}
.field {
  height: 92rpx;
  border: 2rpx solid #e5e7eb;
  border-radius: 16rpx;
  padding: 0 28rpx;
  margin-bottom: 24rpx;
  font-size: 30rpx;
}
.btn-primary.big {
  height: 92rpx;
  line-height: 92rpx;
  margin-top: 8rpx;
}
.switch {
  text-align: center;
  margin-top: 32rpx;
  color: #1677ff;
  font-size: 28rpx;
}
.footer {
  text-align: center;
  margin-top: 80rpx;
  font-size: 24rpx;
}
</style>
