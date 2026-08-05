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

if (errs.length) {
  console.log('页面错误:'); errs.slice(0, 4).forEach((e) => console.log('  ' + e))
}
const failed = results.filter((r) => !r).length
console.log('-'.repeat(50))
console.log(failed ? `${failed} 项未通过` : '全部通过')
await browser.close()
process.exitCode = failed ? 1 : 0
