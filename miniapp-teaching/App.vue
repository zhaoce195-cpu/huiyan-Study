<script>
export default {
  onLaunch() {
    console.log('慧眼·教学实训 小程序启动')
  },
  onShow() {},
  onHide() {},
}
</script>

<style>
/* 全局样式（教学端 teal 主题） */
page {
  background-color: #f4f7f6;
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
  background: linear-gradient(135deg, #0d9488, #0f766e);
  color: #fff;
  border-radius: 999rpx;
  font-size: 30rpx;
}

.btn-primary[disabled] {
  opacity: 0.5;
}

.btn-outline {
  background: #fff;
  color: #0d9488;
  border: 2rpx solid #0d9488;
  border-radius: 999rpx;
}

.muted {
  color: #9ca3af;
}

.flex-row {
  display: flex;
  align-items: center;
}
</style>
