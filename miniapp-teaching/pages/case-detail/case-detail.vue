<template>
  <view class="page detail" v-if="info">
    <image v-if="info.imageUrl" :src="img(info.imageUrl)" class="hero-img" mode="widthFix" @click="preview(info.imageUrl)" />

    <view class="head card">
      <view class="cid">{{ info.id }}</view>
      <view class="grade">{{ info.drGrade || ('DR ' + info.drLevel + '级') }}</view>
      <view class="tags">
        <text class="tag">{{ info.difficulty }}</text>
        <text class="tag">{{ eyeText(info.eye) }}</text>
        <text class="tag" v-if="info.done">已练习</text>
      </view>
    </view>

    <view class="section-title">病例信息</view>
    <view class="card info">
      <view class="info-row"><text class="k muted">性别 / 年龄</text><text class="v">{{ info.gender }} / {{ info.age || '—' }}</text></view>
      <view class="info-row"><text class="k muted">糖尿病病程</text><text class="v">{{ info.diabetesYears }} 年</text></view>
      <view class="info-row"><text class="k muted">来源机构</text><text class="v">{{ info.hospital || '—' }}</text></view>
      <view class="info-row" v-if="info.bestIou != null"><text class="k muted">历史最佳 IoU</text><text class="v">{{ Math.round(info.bestIou * 100) }}%</text></view>
    </view>

    <view class="section-title" v-if="info.lesions && info.lesions.length">金标准病灶</view>
    <view class="card" v-if="info.lesions && info.lesions.length">
      <view class="info-row" v-for="(l, i) in info.lesions" :key="i">
        <text class="k">{{ l.type }}</text>
        <text class="v">{{ l.count }} 处<text v-if="l.location" class="muted"> · {{ l.location }}</text></text>
      </view>
    </view>

    <view class="actions">
      <button class="btn-primary" @click="goReading">进入阅片标注</button>
    </view>
    <view class="tip muted">在阅片工作台标注病灶后提交，系统将给出 IoU 评分与金标准对比</view>
  </view>
</template>

<script>
import { getCaseDetail } from '../../api/training'
import { resolveUrl } from '../../utils/config'

export default {
  data() {
    return { caseId: '', info: null }
  },
  onLoad(options) {
    this.caseId = options.caseId || ''
    this.load()
  },
  methods: {
    async load() {
      try {
        this.info = await getCaseDetail(this.caseId)
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      }
    },
    img(u) { return resolveUrl(u) },
    preview(u) { if (u) uni.previewImage({ urls: [resolveUrl(u)] }) },
    eyeText(e) { return { OD: '右眼', OS: '左眼', OU: '双眼' }[e] || e },
    goReading() {
      uni.navigateTo({ url: `/pages/reading/reading?caseId=${this.caseId}` })
    },
  },
}
</script>

<style scoped>
.detail { padding: 32rpx; }
.hero-img { width: 100%; border-radius: 20rpx; background: #000; margin-bottom: 24rpx; }
.head { text-align: center; }
.cid { font-size: 28rpx; color: #6b7280; }
.grade { font-size: 40rpx; font-weight: 800; color: #0f766e; margin: 10rpx 0 16rpx; }
.tags { display: flex; gap: 16rpx; justify-content: center; }
.tag { font-size: 24rpx; background: #d1faf3; color: #0f766e; border-radius: 999rpx; padding: 6rpx 24rpx; }
.section-title { font-size: 30rpx; font-weight: 600; margin: 32rpx 8rpx 18rpx; }
.info-row { display: flex; justify-content: space-between; padding: 14rpx 0; font-size: 28rpx; border-bottom: 2rpx solid #f3f4f6; }
.info-row:last-child { border-bottom: none; }
.k { font-size: 28rpx; }
.v { font-weight: 500; }
.actions { margin-top: 40rpx; }
.actions .btn-primary { height: 92rpx; line-height: 92rpx; }
.tip { text-align: center; font-size: 22rpx; margin-top: 20rpx; }
</style>
