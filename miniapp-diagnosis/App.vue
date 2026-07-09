<script>
export default {
  onLaunch() {
    console.log('慧眼·辅助诊断 小程序启动')
  },
  onShow() {},
  onHide() {},
}
</script>

<style>
/* 全局样式 */
page {
  background-color: #f5f7fa;
  color: #1f2937;
  font-size: 28rpx;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, sans-serif;
}

.page {
  min-height: 100vh;
  box-sizing: border-box;
}

.card {
  background: #fff;
  border-radius: 20rpx;
  padding: 32rpx;
  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.04);
}

.btn-primary {
  background: linear-gradient(135deg, #1677ff, #0958d9);
  color: #fff;
  border-radius: 999rpx;
  font-size: 30rpx;
}

.btn-primary[disabled] {
  opacity: 0.5;
}

.muted {
  color: #9ca3af;
}

.flex-row {
  display: flex;
  align-items: center;
}
</style>
