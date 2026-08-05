<script setup lang="ts">
/**
 * CoreRetinaStation 替换后的组件级自检（非正式功能）
 *
 * 前一个自检验的是内核本身；这一页验的是替换后的组件：
 *   1. 组件能否真的把影像渲染出来（ready 事件 + 视口里确有像素）；
 *   2. 标注按影像像素坐标画到 overlay 上的位置是否正确；
 *   3. 旧视口快照（无 engine 标记）不会被按新语义硬套；
 *   4. 切换工具、清空标注不报错。
 *
 * 结果写进 window.__stationCheck，由 Playwright 读取断言。
 */
import { nextTick, onMounted, ref } from 'vue'
import CoreRetinaStation from '@/components/CoreRetinaStation.vue'
import type { AnnotationItem, CanvasState } from '@/views/reading/types'

const stationRef = ref<any>(null)
const lines = ref<string[]>([])
const ok = ref<boolean | null>(null)

const qs = new URLSearchParams(location.search)
const imageUrl = qs.get('img') || '/static/demo/fundus_dr2_01.jpg'
// 传了 study/series/sop 就走 DICOM，验证 wadors 链路
const dicomImageId = qs.get('sop')
  ? `wadors:${window.location.origin}/api/v1/dicomweb/wado` +
    `/studies/${qs.get('study')}/series/${qs.get('series')}` +
    `/instances/${qs.get('sop')}/frames/1`
  : ''

const tool = ref<CanvasState['tool']>('pan')
const annotations = ref<AnnotationItem[]>([])
const measurements = ref<AnnotationItem[]>([])

// 故意用旧口径的快照：scale=1 在旧内核里是 1:1，
// 若被当成新内核的 zoom=1 会明显放大
const viewport = ref<any>({ scale: 1, x: 0, y: 0, ww: 255, wl: 127, invert: false })
const layers = ref({ primary: true, heatmap: false, gold: true, my: true })

// 传了 seg 就一并验证分割掩码图层
const segmentation = qs.get('seg')
  ? {
      sopInstanceUid: qs.get('seg') as string,
      segments: [
        { number: 1, label: '微动脉瘤' },
        { number: 2, label: '视网膜出血' },
        { number: 3, label: '硬性渗出' },
        { number: 4, label: '视盘' }
      ]
    }
  : null

const gold = ref<AnnotationItem[]>([
  {
    id: 'G1', tool: 'rect',
    points: [{ x: 100, y: 100 }, { x: 600, y: 500 }],
    label: '微动脉瘤', layer: 'gold', remark: ''
  } as AnnotationItem
])

const ready = ref(false)
const errorMsg = ref('')

onMounted(async () => {
  const result: Record<string, any> = { passed: false, checks: [] }
  const check = (name: string, pass: boolean, detail = '') => {
    result.checks.push({ name, pass, detail })
    lines.value.push(`${pass ? '✓' : '✗'} ${name}${detail ? '  ' + detail : ''}`)
    return pass
  }

  // 等组件 ready（或超时）
  const t0 = Date.now()
  while (!ready.value && !errorMsg.value && Date.now() - t0 < 30000) {
    await new Promise((r) => setTimeout(r, 100))
  }

  const r1 = check(
    dicomImageId ? '组件渲染就绪（DICOM / wadors）' : '组件渲染就绪（遗留 JPG）',
    ready.value, errorMsg.value || `${Date.now() - t0} ms`
  )

  if (r1) {
    // overlay 上应画出了金标准框：取画布像素，找非透明点
    const canvas = document.querySelector('canvas.overlay') as HTMLCanvasElement
    let painted = 0
    if (canvas) {
      const ctx = canvas.getContext('2d')
      const d = ctx?.getImageData(0, 0, canvas.width, canvas.height).data
      if (d) for (let i = 3; i < d.length; i += 4) if (d[i] > 0) painted++
    }
    check('金标准标注已绘制到 overlay', painted > 100, `非透明像素 ${painted}`)

    // 分割掩码：不能只看「没报错」，要确认像素真画上去了。
    // 关掉金标准图层后掩码应当消失 —— 只验「有」不验「无」，
    // 就分不出是掩码在起作用，还是别的东西恰好画了一片。
    if (segmentation) {
      const countPainted = () => {
        const c = document.querySelector('canvas.overlay') as HTMLCanvasElement
        const d = c?.getContext('2d')?.getImageData(0, 0, c.width, c.height).data
        let n = 0
        if (d) for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++
        return n
      }
      await new Promise((r) => setTimeout(r, 2500))
      const withGold = countPainted()
      layers.value = { ...layers.value, gold: false }
      await new Promise((r) => setTimeout(r, 500))
      const withoutGold = countPainted()
      check(
        '分割掩码随金标准图层显隐',
        withGold > withoutGold + 5000,
        `开启 ${withGold} px，关闭 ${withoutGold} px`
      )
      layers.value = { ...layers.value, gold: true }
      await new Promise((r) => setTimeout(r, 500))
    }

    // 旧口径的 scale（0.109 表示适配 4752 px 宽的图）若被当成
    // 新口径的 zoom 照搬，画面会缩到适配的 1/9。应重置为适配，即 zoom=1。
    viewport.value = { scale: 0.109, x: 300, y: 200, ww: 255, wl: 127, invert: false }
    await new Promise((r) => setTimeout(r, 400))
    const afterLegacy = Number(viewport.value.scale)
    check(
      '旧快照不被按新语义照搬',
      Math.abs(afterLegacy - 1) < 0.02,
      `传入旧口径 0.109 → 实际 zoom=${afterLegacy.toFixed(3)}（应重置为适配 1.0）`
    )

    // 反过来：带 cs3d 标记的快照必须原样还原，否则「恢复上次视图」就失效了
    viewport.value = {
      scale: 2.5, x: 0, y: 0, ww: 255, wl: 127, invert: false, engine: 'cs3d'
    }
    await new Promise((r) => setTimeout(r, 400))
    const afterNew = Number(viewport.value.scale)
    check(
      '新快照原样还原',
      Math.abs(afterNew - 2.5) < 0.05,
      `传入 2.5 → 实际 zoom=${afterNew.toFixed(3)}`
    )

    // 切工具与清空不应抛异常
    let toolOk = true
    try {
      for (const t of ['zoom', 'wwwc', 'length', 'angle', 'rect', 'pan']) {
        tool.value = t as any
        await nextTick()
      }
      stationRef.value?.clearAllTools?.()
    } catch (e: any) {
      toolOk = false
      check('切换工具 / 清空', false, e?.message || String(e))
    }
    if (toolOk) check('切换工具 / 清空', true)
  }

  // 把内核暴露出来，便于用真实鼠标事件验证工具是否生效。
  // 只在这个自检页做，正式页面不挂全局对象。
  try {
    const cs = await import('@/utils/cornerstone3d')
    const core = await cs.ensureCornerstone3D()
    ;(window as any).__cs = core.cornerstone
    const tools = await import('@cornerstonejs/tools')
    ;(window as any).__csTools = tools
    // 供工具交互自检切换当前工具
    ;(window as any).__setTool = (t: string) => { tool.value = t as any }
    ;(window as any).__annCount = () => annotations.value.length
  } catch {
    /* 忽略 */
  }

  result.passed = result.checks.every((c: any) => c.pass)
  ok.value = result.passed
  ;(window as any).__stationCheck = result
})
</script>

<template>
  <div class="wrap">
    <h3>阅片组件自检</h3>
    <div class="stage">
      <CoreRetinaStation
        ref="stationRef"
        mode="reading"
        :image-url="imageUrl"
        :dicom-image-id="dicomImageId"
        :segmentation="segmentation"
        :tool="tool"
        :annotations="annotations"
        :measurements="measurements"
        :viewport="viewport"
        :layers="layers"
        :readonly="false"
        :gold-annotations="gold"
        @update:annotations="(v) => (annotations = v)"
        @update:measurements="(v) => (measurements = v)"
        @update:viewport="(v) => (viewport = v)"
        @ready="ready = true"
        @error="(e) => (errorMsg = e?.message || String(e))"
      />
    </div>
    <pre class="out">{{ lines.join('\n') }}</pre>
    <div class="verdict" :class="{ ok: ok === true, bad: ok === false }">
      {{ ok === null ? '执行中…' : ok ? '全部通过' : '存在失败项' }}
    </div>
  </div>
</template>

<style scoped>
.wrap { padding: 16px; font-family: system-ui, sans-serif; }
.stage { width: 620px; height: 460px; }
.out { background: #f5f7fa; padding: 10px; font-size: 13px; line-height: 1.7; }
.verdict { font-weight: 600; }
.verdict.ok { color: #14a44d; }
.verdict.bad { color: #f56c6c; }
</style>
