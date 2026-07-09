<template>
  <view class="page diag">
    <!-- 诊断类型切换 -->
    <view class="type-tabs">
      <view
        v-for="t in types"
        :key="t.key"
        class="type-tab"
        :class="{ active: type === t.key }"
        @click="switchType(t.key)"
      >
        {{ t.label }}
      </view>
    </view>
    <view class="type-desc muted">{{ currentDesc }}</view>

    <!-- 单图上传（MA / 综合） -->
    <block v-if="type !== 'DR'">
      <view class="upload-box card" @click="pickImage('single')">
        <image v-if="single" :src="single" class="preview" mode="aspectFill" />
        <view v-else class="upload-placeholder">
          <view class="plus">＋</view>
          <view class="muted">点击拍摄 / 选择眼底图</view>
        </view>
      </view>
      <view class="eye-select" v-if="type === 'MA'">
        <text class="eye-label">眼别</text>
        <view class="eye-opts">
          <view v-for="e in eyes" :key="e.v" class="eye-opt" :class="{ active: eye === e.v }" @click="eye = e.v">
            {{ e.t }}
          </view>
        </view>
      </view>
    </block>

    <!-- 双图上传（DR 双眼） -->
    <block v-else>
      <view class="dr-grid">
        <view class="dr-item">
          <view class="dr-title">左眼 (OS)</view>
          <view class="upload-box small card" @click="pickImage('left')">
            <image v-if="left" :src="left" class="preview" mode="aspectFill" />
            <view v-else class="upload-placeholder small">
              <view class="plus">＋</view>
            </view>
          </view>
        </view>
        <view class="dr-item">
          <view class="dr-title">右眼 (OD)</view>
          <view class="upload-box small card" @click="pickImage('right')">
            <image v-if="right" :src="right" class="preview" mode="aspectFill" />
            <view v-else class="upload-placeholder small">
              <view class="plus">＋</view>
            </view>
          </view>
        </view>
      </view>
    </block>

    <!-- 进度 -->
    <view v-if="running" class="progress card">
      <view class="progress-bar"><view class="progress-fill" :style="{ width: percent + '%' }" /></view>
      <view class="progress-text muted">{{ percent < 100 ? '上传中 ' + percent + '%' : 'AI 推理中，请稍候…' }}</view>
    </view>

    <button class="btn-primary submit" :loading="running" :disabled="!canSubmit" @click="run">
      开始诊断
    </button>
    <view class="tip muted">影像仅用于辅助诊断，最终结论以医师判断为准</view>
  </view>
</template>

<script>
import { diagnoseMa, diagnoseDr, diagnoseComprehensive } from '../../api/diagnosis'

export default {
  data() {
    return {
      type: 'COMPREHENSIVE',
      types: [
        { key: 'COMPREHENSIVE', label: '综合诊断', desc: '单张眼底图同时执行 MA 检测 + DR 分级，给出综合摘要' },
        { key: 'MA', label: 'MA 检测', desc: '检出眼底图中的微动脉瘤位置与数量，输出标注图' },
        { key: 'DR', label: 'DR 分级', desc: '左右眼分别评估糖尿病视网膜病变 0~4 级' },
      ],
      eyes: [
        { v: 'OU', t: '双眼' },
        { v: 'OD', t: '右眼' },
        { v: 'OS', t: '左眼' },
      ],
      eye: 'OU',
      single: '',
      left: '',
      right: '',
      running: false,
      percent: 0,
    }
  },
  computed: {
    currentDesc() {
      const t = this.types.find((x) => x.key === this.type)
      return t ? t.desc : ''
    },
    canSubmit() {
      if (this.running) return false
      if (this.type === 'DR') return !!this.left && !!this.right
      return !!this.single
    },
  },
  onLoad(options) {
    if (options.type && this.types.some((t) => t.key === options.type)) {
      this.type = options.type
    }
  },
  methods: {
    switchType(key) {
      if (this.running) return
      this.type = key
    },
    pickImage(slot) {
      uni.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['album', 'camera'],
        success: (res) => {
          const path = res.tempFilePaths[0]
          if (slot === 'single') this.single = path
          else if (slot === 'left') this.left = path
          else if (slot === 'right') this.right = path
        },
      })
    },
    onProgress(p) {
      this.percent = p
    },
    async run() {
      if (!this.canSubmit) return
      this.running = true
      this.percent = 0
      try {
        let result
        if (this.type === 'MA') {
          result = await diagnoseMa(this.single, this.eye, this.onProgress)
        } else if (this.type === 'DR') {
          result = await diagnoseDr(this.left, this.right, this.onProgress)
        } else {
          result = await diagnoseComprehensive(this.single, ['ma_detection', 'dr_grading'], this.onProgress)
        }
        uni.setStorageSync('diagnosisResult', result)
        uni.redirectTo({ url: '/pages/result/result' })
      } catch (e) {
        const msg = (e && e.msg) || '诊断失败，请重试'
        uni.showModal({ title: '诊断失败', content: msg, showCancel: false })
      } finally {
        this.running = false
      }
    },
  },
}
</script>

<style scoped>
.diag {
  padding: 32rpx;
}
.type-tabs {
  display: flex;
  background: #eef2f7;
  border-radius: 16rpx;
  padding: 6rpx;
}
.type-tab {
  flex: 1;
  text-align: center;
  padding: 18rpx 0;
  font-size: 28rpx;
  color: #6b7280;
  border-radius: 12rpx;
}
.type-tab.active {
  background: #fff;
  color: #1677ff;
  font-weight: 600;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.06);
}
.type-desc {
  font-size: 24rpx;
  margin: 20rpx 8rpx 28rpx;
  line-height: 1.5;
}
.upload-box {
  height: 440rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0;
}
.upload-box.small {
  height: 280rpx;
}
.preview {
  width: 100%;
  height: 100%;
}
.upload-placeholder {
  text-align: center;
}
.plus {
  font-size: 80rpx;
  color: #c0c8d4;
  line-height: 1;
  margin-bottom: 12rpx;
}
.upload-placeholder.small .plus {
  font-size: 60rpx;
  margin-bottom: 0;
}
.eye-select {
  display: flex;
  align-items: center;
  margin-top: 28rpx;
}
.eye-label {
  font-size: 28rpx;
  margin-right: 24rpx;
}
.eye-opts {
  display: flex;
  gap: 16rpx;
}
.eye-opt {
  padding: 12rpx 32rpx;
  border-radius: 999rpx;
  background: #eef2f7;
  font-size: 26rpx;
  color: #6b7280;
}
.eye-opt.active {
  background: #1677ff;
  color: #fff;
}
.dr-grid {
  display: flex;
  gap: 24rpx;
}
.dr-item {
  flex: 1;
}
.dr-title {
  font-size: 26rpx;
  margin-bottom: 16rpx;
  text-align: center;
  color: #374151;
}
.progress {
  margin-top: 32rpx;
}
.progress-bar {
  height: 14rpx;
  background: #eef2f7;
  border-radius: 999rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1677ff, #0958d9);
  transition: width 0.2s;
}
.progress-text {
  font-size: 24rpx;
  margin-top: 14rpx;
  text-align: center;
}
.submit {
  height: 92rpx;
  line-height: 92rpx;
  margin-top: 48rpx;
}
.tip {
  text-align: center;
  font-size: 22rpx;
  margin-top: 24rpx;
}
</style>
