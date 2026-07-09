<template>
  <view class="reading">
    <!-- 画布区 -->
    <view class="board-wrap" :style="{ height: dispH + 'px' }">
      <image
        v-if="imageUrl"
        :src="imageUrl"
        class="board-img"
        :style="{ width: dispW + 'px', height: dispH + 'px' }"
        mode="scaleToFill"
      />
      <canvas
        canvas-id="board"
        id="board"
        class="board-canvas"
        :style="{ width: dispW + 'px', height: dispH + 'px' }"
        disable-scroll
        @touchstart="onTouchStart"
        @touchmove="onTouchMove"
        @touchend="onTouchEnd"
      />
    </view>

    <!-- 工具栏 -->
    <view class="toolbar">
      <view class="row labels">
        <view
          v-for="l in lesions"
          :key="l.value"
          class="label-chip"
          :class="{ active: currentLabel === l.value }"
          :style="currentLabel === l.value ? { background: l.color, borderColor: l.color, color: '#fff' } : { borderColor: l.color, color: l.color }"
          @click="currentLabel = l.value"
        >
          {{ l.label }}
        </view>
      </view>

      <view class="row tools">
        <view class="tool" @click="undo">↩ 撤销</view>
        <view class="tool" @click="clearAll">🗑 清空</view>
        <view class="tool" :class="{ on: showGold }" @click="toggleGold">
          {{ showGold ? '隐藏金标准' : '显示金标准' }}
        </view>
        <view class="tool">⏱ {{ elapsed }}s</view>
      </view>

      <view class="row count muted">
        已标注 {{ annotations.length }} 处 · 当前病灶：{{ currentLabelText }}
      </view>

      <button class="btn-primary submit" :loading="submitting" :disabled="annotations.length === 0" @click="submit">
        提交评分
      </button>
      <view class="hint muted">选择病灶类型后，在图上拖动画矩形框标注病灶范围</view>
    </view>

    <!-- 评分结果弹层 -->
    <view class="mask" v-if="result" @click="closeResult">
      <view class="dialog" @click.stop>
        <view class="grade-badge" :style="{ background: gradeColor(result.grade) }">{{ result.grade }}</view>
        <view class="iou-big">IoU {{ Math.round(result.iou * 100) }}%</view>
        <view class="comment muted">{{ result.comment }}</view>
        <view class="detail-list">
          <view class="detail-row" v-for="(d, i) in result.details" :key="i">
            <text class="d-label">{{ d.label }}</text>
            <text class="d-iou">{{ Math.round(d.iou * 100) }}%</text>
            <text class="d-meta muted">漏{{ d.missed }} 误{{ d.falsePositive }}</text>
          </view>
        </view>
        <view class="dialog-actions">
          <button class="btn-outline" @click="closeResult">继续修改</button>
          <button class="btn-primary" @click="finishDone">完成练习</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getCaseDetail, getGoldStandard, submitAnnotation, markCaseDone, LESION_OPTIONS, GRADE_COLOR } from '../../api/training'
import { resolveUrl } from '../../utils/config'

export default {
  data() {
    return {
      caseId: '',
      imageUrl: '',
      imgW: 0,
      imgH: 0,
      dispW: 0,
      dispH: 0,
      canvasLeft: 0,
      canvasTop: 0,
      lesions: LESION_OPTIONS,
      currentLabel: LESION_OPTIONS[0].value,
      annotations: [], // { id, label, color, points:[{x,y},{x,y}] } 显示像素
      drawing: false,
      temp: null, // { sx, sy, cx, cy }
      showGold: false,
      gold: [], // 金标准（已换算到显示像素）
      startTime: Date.now(),
      elapsed: 0,
      timer: null,
      submitting: false,
      result: null,
    }
  },
  computed: {
    currentLabelText() {
      const l = this.lesions.find((x) => x.value === this.currentLabel)
      return l ? l.label : '—'
    },
  },
  onLoad(options) {
    this.caseId = options.caseId || ''
    this.init()
    this.timer = setInterval(() => {
      this.elapsed = Math.floor((Date.now() - this.startTime) / 1000)
    }, 1000)
  },
  onUnload() {
    if (this.timer) clearInterval(this.timer)
  },
  methods: {
    async init() {
      let info
      try {
        info = await getCaseDetail(this.caseId)
      } catch (e) {
        uni.showToast({ title: '加载病例失败', icon: 'none' })
        return
      }
      const url = resolveUrl(info.imageUrl || info.thumbUrl)
      this.imageUrl = url
      // 取图片原始尺寸，按屏宽等比缩放铺满画布
      uni.getImageInfo({
        src: url,
        success: (img) => {
          this.imgW = img.width
          this.imgH = img.height
          const sys = uni.getSystemInfoSync()
          const w = sys.windowWidth // px
          this.dispW = w
          this.dispH = Math.round((w * img.height) / img.width)
          this.$nextTick(() => {
            this.queryRect()
            this.redraw()
          })
        },
        fail: () => {
          // 拿不到尺寸时给个默认正方形
          const sys = uni.getSystemInfoSync()
          this.dispW = sys.windowWidth
          this.dispH = sys.windowWidth
          this.$nextTick(() => { this.queryRect(); this.redraw() })
        },
      })
    },
    queryRect() {
      uni.createSelectorQuery()
        .in(this)
        .select('#board')
        .boundingClientRect((r) => {
          if (r) {
            this.canvasLeft = r.left
            this.canvasTop = r.top
          }
        })
        .exec()
    },
    point(e) {
      const t = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]) || {}
      const x = Math.max(0, Math.min(this.dispW, (t.clientX || 0) - this.canvasLeft))
      const y = Math.max(0, Math.min(this.dispH, (t.clientY || 0) - this.canvasTop))
      return { x, y }
    },
    onTouchStart(e) {
      if (!this.currentLabel) {
        uni.showToast({ title: '请先选择病灶类型', icon: 'none' })
        return
      }
      const p = this.point(e)
      this.drawing = true
      this.temp = { sx: p.x, sy: p.y, cx: p.x, cy: p.y }
    },
    onTouchMove(e) {
      if (!this.drawing) return
      const p = this.point(e)
      this.temp.cx = p.x
      this.temp.cy = p.y
      this.redraw()
    },
    onTouchEnd() {
      if (!this.drawing) return
      this.drawing = false
      const t = this.temp
      this.temp = null
      if (!t) return
      const w = Math.abs(t.cx - t.sx)
      const h = Math.abs(t.cy - t.sy)
      if (w < 12 || h < 12) {
        this.redraw()
        return // 太小忽略，视作误触
      }
      const color = (this.lesions.find((x) => x.value === this.currentLabel) || {}).color || '#dc2626'
      this.annotations.push({
        id: 'a' + this.elapsed + '_' + this.annotations.length,
        label: this.currentLabel,
        color,
        points: [
          { x: Math.min(t.sx, t.cx), y: Math.min(t.sy, t.cy) },
          { x: Math.max(t.sx, t.cx), y: Math.max(t.sy, t.cy) },
        ],
      })
      this.redraw()
    },
    redraw() {
      const ctx = uni.createCanvasContext('board', this)
      ctx.clearRect(0, 0, this.dispW, this.dispH)

      // 金标准（虚线绿框）
      if (this.showGold) {
        ctx.setLineWidth(2)
        ctx.setStrokeStyle('rgba(22,163,74,0.9)')
        this.gold.forEach((g) => {
          const pts = g.points || []
          if (g.type === 'rect' && pts.length >= 2) {
            ctx.strokeRect(pts[0].x, pts[0].y, pts[1].x - pts[0].x, pts[1].y - pts[0].y)
          } else if (pts.length >= 2) {
            ctx.beginPath()
            ctx.moveTo(pts[0].x, pts[0].y)
            for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y)
            ctx.closePath()
            ctx.stroke()
          }
        })
      }

      // 已提交标注
      ctx.setLineWidth(3)
      this.annotations.forEach((a) => {
        ctx.setStrokeStyle(a.color)
        const p = a.points
        ctx.strokeRect(p[0].x, p[0].y, p[1].x - p[0].x, p[1].y - p[0].y)
      })

      // 当前正在画的框
      if (this.temp) {
        const color = (this.lesions.find((x) => x.value === this.currentLabel) || {}).color || '#dc2626'
        ctx.setStrokeStyle(color)
        ctx.setLineWidth(3)
        ctx.strokeRect(this.temp.sx, this.temp.sy, this.temp.cx - this.temp.sx, this.temp.cy - this.temp.sy)
      }
      ctx.draw()
    },
    undo() {
      this.annotations.pop()
      this.redraw()
    },
    clearAll() {
      if (!this.annotations.length) return
      this.annotations = []
      this.redraw()
    },
    async toggleGold() {
      this.showGold = !this.showGold
      if (this.showGold && this.gold.length === 0) {
        try {
          const data = await getGoldStandard(this.caseId)
          const sx = this.imgW ? this.dispW / this.imgW : 1
          const sy = this.imgH ? this.dispH / this.imgH : 1
          this.gold = (data.annotations || []).map((a) => ({
            type: a.type,
            points: (a.points || []).map((p) => ({ x: p.x * sx, y: p.y * sy })),
          }))
        } catch (e) {
          uni.showToast({ title: '暂无金标准', icon: 'none' })
        }
      }
      this.redraw()
    },
    async submit() {
      if (!this.annotations.length) return
      this.submitting = true
      try {
        const payload = {
          caseId: this.caseId,
          canvasWidth: Math.round(this.dispW),
          canvasHeight: Math.round(this.dispH),
          durationSec: this.elapsed,
          annotations: this.annotations.map((a) => ({
            id: a.id,
            type: 'rect',
            label: a.label,
            color: a.color,
            points: a.points.map((p) => ({ x: Math.round(p.x), y: Math.round(p.y) })),
          })),
        }
        this.result = await submitAnnotation(payload)
      } catch (e) {
        uni.showToast({ title: (e && e.msg) || '提交失败', icon: 'none' })
      } finally {
        this.submitting = false
      }
    },
    gradeColor(g) {
      return GRADE_COLOR[g] || '#6b7280'
    },
    closeResult() {
      this.result = null
    },
    async finishDone() {
      try {
        await markCaseDone(this.caseId)
      } catch (e) {}
      uni.showToast({ title: '已完成练习', icon: 'success' })
      this.result = null
      setTimeout(() => uni.navigateBack(), 600)
    },
  },
}
</script>

<style scoped>
.reading { min-height: 100vh; background: #111827; }
.board-wrap { position: relative; width: 100%; background: #000; }
.board-img { position: absolute; left: 0; top: 0; }
.board-canvas { position: absolute; left: 0; top: 0; }
.toolbar { background: #1f2937; padding: 24rpx 32rpx 40rpx; }
.row { margin-bottom: 20rpx; }
.labels { display: flex; flex-wrap: wrap; gap: 14rpx; }
.label-chip {
  padding: 10rpx 26rpx; border: 2rpx solid; border-radius: 999rpx;
  font-size: 26rpx; background: #111827;
}
.tools { display: flex; gap: 16rpx; flex-wrap: wrap; }
.tool {
  padding: 12rpx 24rpx; background: #374151; color: #e5e7eb; border-radius: 12rpx; font-size: 26rpx;
}
.tool.on { background: #0d9488; color: #fff; }
.count { font-size: 24rpx; color: #9ca3af; }
.submit { height: 92rpx; line-height: 92rpx; margin-top: 8rpx; }
.hint { font-size: 22rpx; text-align: center; margin-top: 18rpx; color: #6b7280; }

.mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center; z-index: 99;
}
.dialog { width: 620rpx; background: #fff; border-radius: 24rpx; padding: 48rpx 40rpx; text-align: center; }
.grade-badge {
  width: 120rpx; height: 120rpx; line-height: 120rpx; margin: 0 auto 20rpx;
  border-radius: 50%; color: #fff; font-size: 56rpx; font-weight: 800;
}
.iou-big { font-size: 40rpx; font-weight: 700; color: #0f766e; }
.comment { font-size: 26rpx; margin: 16rpx 0 24rpx; line-height: 1.5; }
.detail-list { text-align: left; margin-bottom: 24rpx; }
.detail-row { display: flex; align-items: center; padding: 12rpx 0; border-bottom: 2rpx solid #f3f4f6; font-size: 26rpx; }
.d-label { flex: 1; }
.d-iou { width: 110rpx; text-align: right; font-weight: 600; color: #0d9488; }
.d-meta { width: 160rpx; text-align: right; font-size: 22rpx; }
.dialog-actions { display: flex; gap: 20rpx; }
.dialog-actions button { flex: 1; height: 84rpx; line-height: 84rpx; font-size: 28rpx; }
</style>
