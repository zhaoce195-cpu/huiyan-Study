<template>
  <view class="page result" v-if="data">
    <!-- 结论卡 -->
    <view class="verdict card" :style="{ background: riskBg }">
      <view class="verdict-risk" :style="{ color: riskColor }">{{ riskLabel }}</view>
      <view class="verdict-type">{{ typeLabel }}</view>
      <view class="verdict-name muted">{{ data.patientName }} · {{ data.caseSn || data.taskId }}</view>
    </view>

    <!-- MA -->
    <block v-if="data.ma">
      <view class="section-title">微动脉瘤检测</view>
      <view class="card metric-row">
        <text>检出微动脉瘤</text>
        <text class="metric-val">{{ data.ma.maCount }} 个</text>
      </view>
      <view class="img-grid">
        <view class="img-cell">
          <image :src="img(data.primaryImageUrl)" mode="widthFix" class="res-img" @click="preview(data.primaryImageUrl)" />
          <view class="img-cap muted">原图</view>
        </view>
        <view class="img-cell" v-if="data.ma.overlayUrl">
          <image :src="img(data.ma.overlayUrl)" mode="widthFix" class="res-img" @click="preview(data.ma.overlayUrl)" />
          <view class="img-cap muted">标注图</view>
        </view>
      </view>
    </block>

    <!-- DR -->
    <block v-if="data.dr">
      <view class="section-title">DR 分级</view>
      <view class="card metric-row">
        <text>综合分级</text>
        <text class="metric-val">{{ data.dr.overallGrade }} 级 {{ data.dr.overallGradeName }}</text>
      </view>
      <view class="img-grid">
        <view class="img-cell" v-if="data.dr.left">
          <image :src="img(data.dr.left.heatmapUrl || data.dr.left.imageUrl)" mode="widthFix" class="res-img" @click="preview(data.dr.left.heatmapUrl || data.dr.left.imageUrl)" />
          <view class="img-cap muted">左眼 {{ data.dr.left.grade }}级</view>
        </view>
        <view class="img-cell" v-if="data.dr.right">
          <image :src="img(data.dr.right.heatmapUrl || data.dr.right.imageUrl)" mode="widthFix" class="res-img" @click="preview(data.dr.right.heatmapUrl || data.dr.right.imageUrl)" />
          <view class="img-cap muted">右眼 {{ data.dr.right.grade }}级</view>
        </view>
      </view>
    </block>

    <!-- 综合 -->
    <block v-if="data.comprehensive">
      <view class="section-title">综合诊断</view>
      <view class="card">
        <view class="metric-row"><text>DR 分级</text><text class="metric-val">{{ data.comprehensive.overallGrade }} 级</text></view>
        <view class="metric-row"><text>微动脉瘤</text><text class="metric-val">{{ data.comprehensive.maCount }} 个</text></view>
        <view class="summary muted">{{ data.comprehensive.summary }}</view>
      </view>
      <view class="img-grid">
        <view class="img-cell">
          <image :src="img(data.primaryImageUrl)" mode="widthFix" class="res-img" @click="preview(data.primaryImageUrl)" />
          <view class="img-cap muted">原图</view>
        </view>
        <view class="img-cell" v-if="data.comprehensive.maOverlayUrl || data.comprehensive.drHeatmapUrl">
          <image :src="img(data.comprehensive.maOverlayUrl || data.comprehensive.drHeatmapUrl)" mode="widthFix" class="res-img" @click="preview(data.comprehensive.maOverlayUrl || data.comprehensive.drHeatmapUrl)" />
          <view class="img-cap muted">AI 标注 / 热力图</view>
        </view>
      </view>
    </block>

    <view class="actions">
      <button class="btn-outline" @click="again">再做一次</button>
      <button class="btn-primary" @click="goDetail">查看完整病例</button>
    </view>
  </view>
</template>

<script>
import { RISK_LABEL, RISK_COLOR, DIAGNOSIS_TYPE_LABEL } from '../../api/diagnosis'
import { resolveUrl } from '../../utils/config'

export default {
  data() {
    return { data: null }
  },
  computed: {
    riskLabel() {
      return RISK_LABEL[this.data && this.data.riskLevel] || '已完成'
    },
    riskColor() {
      return RISK_COLOR[this.data && this.data.riskLevel] || '#1677ff'
    },
    riskBg() {
      const c = this.riskColor
      return c + '14' // 8% 透明叠加
    },
    typeLabel() {
      return DIAGNOSIS_TYPE_LABEL[this.data && this.data.diagnosisType] || '智能诊断'
    },
  },
  onLoad() {
    this.data = uni.getStorageSync('diagnosisResult') || null
    if (!this.data) {
      uni.showToast({ title: '无诊断结果', icon: 'none' })
      setTimeout(() => uni.navigateBack(), 600)
    }
  },
  methods: {
    img(u) {
      return resolveUrl(u)
    },
    preview(u) {
      if (!u) return
      uni.previewImage({ urls: [resolveUrl(u)] })
    },
    again() {
      uni.redirectTo({ url: '/pages/diagnose/diagnose' })
    },
    goDetail() {
      uni.redirectTo({ url: `/pages/case-detail/case-detail?taskId=${this.data.taskId}` })
    },
  },
}
</script>

<style scoped>
.result {
  padding: 32rpx;
}
.verdict {
  text-align: center;
  padding: 48rpx 32rpx;
}
.verdict-risk {
  font-size: 56rpx;
  font-weight: 800;
}
.verdict-type {
  font-size: 30rpx;
  margin-top: 12rpx;
  color: #374151;
}
.verdict-name {
  font-size: 24rpx;
  margin-top: 10rpx;
}
.section-title {
  font-size: 30rpx;
  font-weight: 600;
  margin: 32rpx 8rpx 18rpx;
}
.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 28rpx;
  padding: 10rpx 0;
}
.metric-val {
  font-weight: 700;
  color: #1677ff;
  font-size: 32rpx;
}
.summary {
  font-size: 26rpx;
  line-height: 1.6;
  margin-top: 16rpx;
}
.img-grid {
  display: flex;
  gap: 20rpx;
  margin-top: 20rpx;
}
.img-cell {
  flex: 1;
}
.res-img {
  width: 100%;
  border-radius: 16rpx;
  background: #000;
}
.img-cap {
  text-align: center;
  font-size: 22rpx;
  margin-top: 10rpx;
}
.actions {
  display: flex;
  gap: 20rpx;
  margin-top: 48rpx;
}
.actions button {
  flex: 1;
  height: 88rpx;
  line-height: 88rpx;
  font-size: 28rpx;
}
.btn-outline {
  background: #fff;
  color: #1677ff;
  border: 2rpx solid #1677ff;
  border-radius: 999rpx;
}
</style>
