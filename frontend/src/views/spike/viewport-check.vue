<script setup lang="ts">
/**
 * 阅片内核自检页（非正式功能）
 *
 * 全量替换前先把新内核里没验证过的部分单独跑通：
 *   1. 遗留 JPG 经自写的 web: 加载器能否在 Cornerstone3D 里渲染；
 *   2. 像素坐标 ↔ 屏幕坐标的往返是否精确 ——
 *      标注全部以像素坐标存库，这条链错了所有标注都会偏；
 *   3. 缩放/平移后往返是否依然精确。
 *
 * 结果写进 window.__viewportCheck，由 Playwright 读取断言。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ensureCornerstone3D,
  makeCoordMapper,
  webImageId
} from '@/utils/cornerstone3d'

const el = ref<HTMLDivElement | null>(null)
const lines = ref<string[]>([])
const ok = ref<boolean | null>(null)

let engine: any = null

const log = (s: string) => {
  lines.value.push(s)
}

onMounted(async () => {
  const result: Record<string, any> = { passed: false, checks: [] }
  const check = (name: string, pass: boolean, detail = '') => {
    result.checks.push({ name, pass, detail })
    log(`${pass ? '✓' : '✗'} ${name}${detail ? '  ' + detail : ''}`)
    return pass
  }

  try {
    const { cornerstone } = await ensureCornerstone3D()
    const { RenderingEngine, Enums } = cornerstone
    check('内核初始化', true)

    // 用一张确定存在的静态图；失败也算结果，不掩盖
    const url = new URLSearchParams(location.search).get('img') || '/static/probe.jpg'
    const imageId = webImageId(url)

    engine = new RenderingEngine('huiyan-check-engine')
    engine.enableElement({
      viewportId: 'check-vp',
      type: Enums.ViewportType.STACK,
      element: el.value as HTMLDivElement
    })
    const viewport: any = engine.getViewport('check-vp')
    await viewport.setStack([imageId])
    viewport.render()

    // setStack 不因解码失败而抛异常，必须显式确认真的拿到了像素
    const data = viewport.getImageData?.()
    const dims = data?.dimensions
    if (!check('遗留 JPG 解码', !!dims, dims ? `${dims[0]} × ${dims[1]}` : '无像素数据')) {
      throw new Error('web: 加载器未能解码影像')
    }
    result.dimensions = dims ? [dims[0], dims[1]] : null

    const mapper = makeCoordMapper(cornerstone, viewport)

    // 坐标往返：像素 → canvas → 像素，误差应在亚像素级
    const probes = [
      [0, 0],
      [1, 1],
      [Math.floor(dims[0] / 2), Math.floor(dims[1] / 2)],
      [dims[0] - 1, dims[1] - 1]
    ]
    const roundTrip = (tag: string) => {
      let worst = 0
      for (const [px, py] of probes) {
        const c = mapper.pixelToCanvas(px, py)
        const back = mapper.canvasToPixel(c.x, c.y)
        worst = Math.max(worst, Math.abs(back.x - px), Math.abs(back.y - py))
      }
      return check(`坐标往返（${tag}）`, worst < 0.5, `最大误差 ${worst.toFixed(4)} px`)
    }
    const r1 = roundTrip('默认视图')

    // 往返自洽不等于映射正确：若映射退化成恒等函数，往返同样完美。
    // 下面两条专门排除这种「自洽的假象」。
    const origin = mapper.pixelToCanvas(0, 0)
    const r0 = check(
      '映射不是恒等函数',
      Math.abs(origin.x) > 1 || Math.abs(origin.y) > 1,
      `影像 (0,0) → canvas (${origin.x.toFixed(1)}, ${origin.y.toFixed(1)})`
    )

    // 缩放 + 平移后再测一次：标注是在各种缩放下画的
    viewport.setZoom(2.7)
    viewport.setPan([37, -19])
    viewport.render()
    const r2 = roundTrip('缩放 2.7 倍 + 平移')

    // 缩放后同一像素必须落到不同的屏幕位置，否则映射没有真的跟随视口
    const zoomed = mapper.pixelToCanvas(0, 0)
    const rz = check(
      '映射跟随缩放变化',
      Math.hypot(zoomed.x - origin.x, zoomed.y - origin.y) > 1,
      `(${origin.x.toFixed(1)}, ${origin.y.toFixed(1)}) → ` +
        `(${zoomed.x.toFixed(1)}, ${zoomed.y.toFixed(1)})`
    )

    // 中心点应落在视口中央附近——验证的是映射方向没搞反
    viewport.resetCamera()
    viewport.render()
    const mid = mapper.pixelToCanvas(dims[0] / 2, dims[1] / 2)
    const rect = (el.value as HTMLDivElement).getBoundingClientRect()
    const offCenter = Math.hypot(mid.x - rect.width / 2, mid.y - rect.height / 2)
    const r3 = check('影像中心映射到视口中心', offCenter < 2,
                     `偏差 ${offCenter.toFixed(2)} px`)

    result.passed = r0 && r1 && r2 && rz && r3
    ok.value = result.passed
  } catch (e: any) {
    check('执行', false, e?.message || String(e))
    ok.value = false
  } finally {
    ;(window as any).__viewportCheck = result
  }
})

onBeforeUnmount(() => {
  try {
    engine?.destroy?.()
  } catch {
    /* 忽略 */
  }
})
</script>

<template>
  <div class="wrap">
    <h3>阅片内核自检</h3>
    <div ref="el" class="vp"></div>
    <pre class="out">{{ lines.join('\n') }}</pre>
    <div class="verdict" :class="{ ok: ok === true, bad: ok === false }">
      {{ ok === null ? '执行中…' : ok ? '全部通过' : '存在失败项' }}
    </div>
  </div>
</template>

<style scoped>
.wrap { padding: 16px; font-family: system-ui, sans-serif; }
.vp { width: 520px; height: 400px; background: #000; }
.out { background: #f5f7fa; padding: 10px; font-size: 13px; line-height: 1.7; }
.verdict { font-weight: 600; }
.verdict.ok { color: #14a44d; }
.verdict.bad { color: #f56c6c; }
</style>
