/**
 * 阅片工具是否真的响应鼠标
 *
 * 为什么单独一条：此前的组件自检只验「切换工具不抛异常」，
 * 而工具组里 Pan=Active、addTool/setToolActive 全部成功，
 * 鼠标事件却到不了工具 —— 那次回归在生产上才被发现。
 * 判断工具是否可用，唯一可信的办法是真的拖一下看视口有没有动。
 */
import { chromium } from 'playwright'

const PORT = process.argv[2] || '5178'
const browser = await chromium.launch()
const page = await browser.newPage()
const errs = []
page.on('pageerror', (e) => errs.push(e.message.slice(0, 160)))

const results = []
const check = (name, ok, detail = '') => {
  results.push(ok)
  console.log(`${ok ? '✓' : '✗'} ${name}${detail ? '  —— ' + detail : ''}`)
}

await page.goto(`http://127.0.0.1:${PORT}/spike/station-check`, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => window.__stationCheck, null, { timeout: 60000 }).catch(() => {})
await page.waitForTimeout(1200)

const state = () => page.evaluate(() => {
  const vp = window.__cs?.getRenderingEngines?.()?.[0]?.getViewports?.()?.[0]
  if (!vp) return null
  const p = vp.getProperties?.() || {}
  return { zoom: vp.getZoom?.(), pan: vp.getPan?.(), voi: p.voiRange }
})

const setTool = (t) => page.evaluate((tool) => {
  window.__setTool?.(tool)
}, t)

const box = await page.locator('.cs-element').boundingBox()
const cx = box.x + box.width / 2
const cy = box.y + box.height / 2

const drag = async (dx, dy, button = 'left') => {
  await page.mouse.move(cx, cy)
  await page.mouse.down({ button })
  await page.mouse.move(cx + dx, cy + dy, { steps: 12 })
  await page.mouse.up({ button })
  await page.waitForTimeout(500)
}

// 平移
await setTool('pan'); await page.waitForTimeout(400)
let a = await state(); await drag(70, 50); let b = await state()
check('平移', !!a && !!b && (Math.abs(b.pan[0] - a.pan[0]) > 20),
      a && b ? `pan ${a.pan.map(Math.round)} → ${b.pan.map(Math.round)}` : '取不到视口')

// 缩放
await setTool('zoom'); await page.waitForTimeout(400)
a = await state(); await drag(0, 90); b = await state()
check('缩放', !!a && !!b && Math.abs(b.zoom - a.zoom) > 0.05,
      a && b ? `zoom ${a.zoom.toFixed(2)} → ${b.zoom.toFixed(2)}` : '')

// 窗宽窗位
await setTool('wwwc'); await page.waitForTimeout(400)
a = await state(); await drag(120, 60); b = await state()
const voiMoved = a?.voi && b?.voi &&
  (Math.abs(b.voi.lower - a.voi.lower) > 1 || Math.abs(b.voi.upper - a.voi.upper) > 1)
check('窗宽窗位', !!voiMoved,
      a?.voi && b?.voi ? `[${a.voi.lower.toFixed(0)},${a.voi.upper.toFixed(0)}] → [${b.voi.lower.toFixed(0)},${b.voi.upper.toFixed(0)}]` : '')

// 距离 / 角度：看标注是否落进标注状态
const annCount = (tool) => page.evaluate((t) => {
  const el = document.querySelector('.cs-element')
  return (window.__csTools?.annotation?.state?.getAnnotations?.(t, el) || []).length
}, tool)

await setTool('length'); await page.waitForTimeout(400)
const lBefore = await annCount('Length')
await drag(100, 40)
check('距离测量', (await annCount('Length')) > lBefore,
      `标注数 ${lBefore} → ${await annCount('Length')}`)

await setTool('angle'); await page.waitForTimeout(400)
const gBefore = await annCount('Angle')
// 角度需要三次点击
for (const [dx, dy] of [[-60, -40], [0, 0], [60, -40]]) {
  await page.mouse.click(cx + dx, cy + dy)
  await page.waitForTimeout(300)
}
check('角度测量', (await annCount('Angle')) > gBefore,
      `标注数 ${gBefore} → ${await annCount('Angle')}`)

// ---- 标注绘制：节点是否可见、测量是否被画两遍 ----
const painted = () => page.evaluate(() => {
  const c = document.querySelector('canvas.overlay')
  const d = c?.getContext('2d')?.getImageData(0, 0, c.width, c.height).data
  let n = 0
  if (d) for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++
  return n
})

// 多边形：只点第一下，画布上就该有东西（此前一片空白）
await setTool('polygon'); await page.waitForTimeout(400)
const blank = await painted()
await page.mouse.click(cx - 60, cy - 40)
await page.waitForTimeout(500)
const oneNode = await painted()
check('多边形首点即可见', oneNode > blank + 20, `非透明像素 ${blank} → ${oneNode}`)

// 再点两下形成三角，然后点回首点闭合
await page.mouse.move(cx + 60, cy - 40); await page.mouse.click(cx + 60, cy - 40)
await page.waitForTimeout(300)
await page.mouse.move(cx, cy + 50); await page.mouse.click(cx, cy + 50)
await page.waitForTimeout(300)
const annBefore = await page.evaluate(() => window.__annCount?.() ?? -1)
await page.mouse.move(cx - 60, cy - 40); await page.mouse.click(cx - 60, cy - 40)
await page.waitForTimeout(600)
const annAfter = await page.evaluate(() => window.__annCount?.() ?? -1)
check('点回首点可闭合多边形', annAfter > annBefore, `标注数 ${annBefore} → ${annAfter}`)

// ---- 顶点拖拽：抓住已画矩形的角点拖动，坐标应真的改变 ----
await setTool('rect'); await page.waitForTimeout(400)
await page.mouse.move(cx - 80, cy - 60); await page.mouse.down()
await page.mouse.move(cx + 40, cy + 30, { steps: 8 }); await page.mouse.up()
await page.waitForTimeout(600)

const cornerBefore = await page.evaluate(() => {
  const a = window.__annList?.()?.slice(-1)[0]
  return a ? { x: Math.round(a.points[1].x), y: Math.round(a.points[1].y) } : null
})
if (cornerBefore) {
  // 抓住第二个点（右下角）拖走
  await page.mouse.move(cx + 40, cy + 30)
  await page.mouse.down()
  await page.mouse.move(cx + 110, cy + 90, { steps: 10 })
  await page.mouse.up()
  await page.waitForTimeout(600)
}
const cornerAfter = await page.evaluate(() => {
  const a = window.__annList?.()?.slice(-1)[0]
  return a ? { x: Math.round(a.points[1].x), y: Math.round(a.points[1].y) } : null
})
const moved = cornerBefore && cornerAfter &&
  (Math.abs(cornerAfter.x - cornerBefore.x) > 5 || Math.abs(cornerAfter.y - cornerBefore.y) > 5)
check('拖拽顶点改变图形', !!moved,
      cornerBefore && cornerAfter
        ? `角点 (${cornerBefore.x},${cornerBefore.y}) → (${cornerAfter.x},${cornerAfter.y})`
        : '取不到标注')

if (errs.length) {
  console.log('页面错误:'); errs.slice(0, 4).forEach((e) => console.log('  ' + e))
}
const failed = results.filter((r) => !r).length
console.log('-'.repeat(50))
console.log(failed ? `${failed} 项未通过` : '全部通过')
await browser.close()
process.exitCode = failed ? 1 : 0
