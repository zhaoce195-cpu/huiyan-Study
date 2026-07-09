<template>
  <view class="page detail" v-if="report">
    <!-- 头部结论 -->
    <view class="head card" :style="{ background: riskBg }">
      <view class="risk-big" :style="{ color: riskColor }">{{ riskText }}</view>
      <view class="dr">{{ report.dr || '—' }}</view>
      <view class="conf muted" v-if="report.confidence">AI 置信度 {{ (report.confidence * 100).toFixed(0) }}%</view>
    </view>

    <!-- 患者信息 -->
    <view class="section-title">患者信息</view>
    <view class="card info">
      <view class="info-row"><text class="k muted">姓名</text><text class="v">{{ report.patientName || '—' }}</text></view>
      <view class="info-row"><text class="k muted">性别 / 年龄</text><text class="v">{{ report.gender }} / {{ report.age || '—' }}</text></view>
      <view class="info-row"><text class="k muted">眼别</text><text class="v">{{ eyeText(report.eye) }}</text></view>
      <view class="info-row"><text class="k muted">报告编号</text><text class="v">{{ report.reportNo || taskId }}</text></view>
      <view class="info-row"><text class="k muted">送检机构</text><text class="v">{{ report.hospital || '—' }}</text></view>
      <view class="info-row"><text class="k muted">检查时间</text><text class="v">{{ report.examTime || '—' }}</text></view>
    </view>

    <!-- 影像 -->
    <view class="section-title" v-if="report.imageUrls && (report.imageUrls.origin || report.imageUrls.heatmap)">影像</view>
    <view class="img-grid" v-if="report.imageUrls">
      <view class="img-cell" v-if="report.imageUrls.origin">
        <image :src="img(report.imageUrls.origin)" mode="widthFix" class="res-img" @click="preview(report.imageUrls.origin)" />
        <view class="img-cap muted">原图</view>
      </view>
      <view class="img-cell" v-if="report.imageUrls.heatmap">
        <image :src="img(report.imageUrls.heatmap)" mode="widthFix" class="res-img" @click="preview(report.imageUrls.heatmap)" />
        <view class="img-cap muted">热力图 / 标注</view>
      </view>
    </view>

    <!-- 病灶 -->
    <view class="section-title" v-if="report.lesions && report.lesions.length">检出病灶</view>
    <view class="card" v-if="report.lesions && report.lesions.length">
      <view class="info-row" v-for="(l, i) in report.lesions" :key="i">
        <text class="k">{{ l.type }}</text>
        <text class="v">{{ l.count }} 处<text v-if="l.location" class="muted"> · {{ l.location }}</text></text>
      </view>
    </view>

    <!-- AI 结论 -->
    <view class="section-title">AI 诊断意见</view>
    <view class="card conclusion">
      <view class="c-text">{{ report.conclusion || '暂无' }}</view>
      <view class="c-sub muted" v-if="report.suggestion">建议：{{ report.suggestion }}</view>
    </view>

    <!-- 复核信息 -->
    <view class="card review-info" v-if="report.reviewer">
      <text class="muted">已由 {{ report.reviewer }} 于 {{ report.reviewedAt }} 复核确认</text>
    </view>

    <!-- 医生确认 -->
    <view class="actions" v-if="canConfirm && !report.reviewer">
      <button class="btn-primary" @click="openConfirm">确认报告</button>
    </view>

    <!-- 确认弹层 -->
    <view class="mask" v-if="showConfirm" @click="showConfirm = false">
      <view class="dialog" @click.stop>
        <view class="dialog-title">确认诊断报告</view>
        <textarea class="dialog-input" v-model="confirmDiagnosis" placeholder="诊断意见（留空使用 AI 结论）" />
        <textarea class="dialog-input" v-model="confirmSuggestion" placeholder="处置建议（可选）" />
        <view class="dialog-actions">
          <button class="btn-outline" @click="showConfirm = false">取消</button>
          <button class="btn-primary" :loading="confirming" @click="doConfirm">提交确认</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getScreeningReport, confirmReport, RISK_TEXT, RISK_COLOR } from '../../api/screening'
import { resolveUrl } from '../../utils/config'
import { useUserStore } from '../../store/user'

export default {
  data() {
    return {
      taskId: '',
      report: null,
      showConfirm: false,
      confirmDiagnosis: '',
      confirmSuggestion: '',
      confirming: false,
    }
  },
  computed: {
    riskText() { return RISK_TEXT[this.report && this.report.risk] || '待分析' },
    riskColor() { return RISK_COLOR[this.report && this.report.risk] || '#1677ff' },
    riskBg() { return this.riskColor + '14' },
    canConfirm() {
      const store = useUserStore()
      return store.canDiagnose
    },
  },
  onLoad(options) {
    this.taskId = options.taskId || ''
    this.load()
  },
  methods: {
    async load() {
      if (!this.taskId) return
      try {
        this.report = await getScreeningReport(this.taskId)
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      }
    },
    img(u) { return resolveUrl(u) },
    preview(u) { if (u) uni.previewImage({ urls: [resolveUrl(u)] }) },
    eyeText(e) { return { OD: '右眼', OS: '左眼', OU: '双眼' }[e] || e },
    openConfirm() {
      this.confirmDiagnosis = ''
      this.confirmSuggestion = ''
      this.showConfirm = true
    },
    async doConfirm() {
      this.confirming = true
      try {
        await confirmReport({
          taskId: this.taskId,
          diagnosis: this.confirmDiagnosis,
          suggestion: this.confirmSuggestion,
        })
        uni.showToast({ title: '已确认', icon: 'success' })
        this.showConfirm = false
        this.load()
      } catch (e) {
        uni.showToast({ title: (e && e.msg) || '确认失败', icon: 'none' })
      } finally {
        this.confirming = false
      }
    },
  },
}
</script>

<style scoped>
.detail { padding: 32rpx; }
.head {
  text-align: center;
  padding: 48rpx;
}
.risk-big { font-size: 52rpx; font-weight: 800; }
.dr { font-size: 30rpx; margin-top: 12rpx; color: #374151; }
.conf { font-size: 24rpx; margin-top: 8rpx; }
.section-title { font-size: 30rpx; font-weight: 600; margin: 32rpx 8rpx 18rpx; }
.info-row {
  display: flex;
  justify-content: space-between;
  padding: 14rpx 0;
  font-size: 28rpx;
  border-bottom: 2rpx solid #f3f4f6;
}
.info-row:last-child { border-bottom: none; }
.k { font-size: 28rpx; }
.v { font-weight: 500; }
.img-grid { display: flex; gap: 20rpx; }
.img-cell { flex: 1; }
.res-img { width: 100%; border-radius: 16rpx; background: #000; }
.img-cap { text-align: center; font-size: 22rpx; margin-top: 10rpx; }
.conclusion .c-text { font-size: 28rpx; line-height: 1.6; }
.conclusion .c-sub { font-size: 26rpx; margin-top: 16rpx; }
.review-info { margin-top: 24rpx; text-align: center; font-size: 24rpx; }
.actions { margin-top: 40rpx; }
.actions .btn-primary { height: 92rpx; line-height: 92rpx; }
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99;
}
.dialog {
  width: 600rpx;
  background: #fff;
  border-radius: 24rpx;
  padding: 40rpx;
}
.dialog-title { font-size: 32rpx; font-weight: 600; margin-bottom: 24rpx; text-align: center; }
.dialog-input {
  width: 100%;
  min-height: 120rpx;
  border: 2rpx solid #e5e7eb;
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  font-size: 28rpx;
  box-sizing: border-box;
}
.dialog-actions { display: flex; gap: 20rpx; }
.dialog-actions button { flex: 1; height: 84rpx; line-height: 84rpx; font-size: 28rpx; }
.btn-outline {
  background: #fff;
  color: #1677ff;
  border: 2rpx solid #1677ff;
  border-radius: 999rpx;
}
</style>
