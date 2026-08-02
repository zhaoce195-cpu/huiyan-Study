/**
 * 以学员身份从 Moodle 课程页启动慧眼（真实链路验证）
 * 用法: node scripts/moodle_lti_launch.mjs <moodleUrl> <user> <pass> <courseId>
 */
import { chromium } from 'playwright'
const [M, U, P, CID] = process.argv.slice(2)
const b = await chromium.launch()
const c = await b.newContext()
const page = await c.newPage()
const seen = []
// 必须记跳转历史，不能只看最终 URL：
// 中转页拿到令牌后立刻 replace 到工作台，等脚本去读时已经跳走了，
// 只看最终 URL 会把「成功」判成「失败」。
const history = []
const track = (tag) => (f, pg) => {
  if (f !== pg.mainFrame()) return
  history.push(f.url())
  console.log(`  ${tag}`, f.url().slice(0, 110))
}
c.on('page', (pg) => { seen.push(pg); pg.on('framenavigated', (f) => track('新窗口跳转')(f, pg)) })
page.on('framenavigated', (f) => track('跳转')(f, page))

await page.goto(`${M}/login/index.php`, { waitUntil: 'domcontentloaded' })
await page.fill('#username', U); await page.fill('#password', P); await page.click('#loginbtn')
await page.waitForLoadState('domcontentloaded')
console.log(await page.locator('#username').count() ? '✗ 学员登录失败' : '✓ 学员登录')

await page.goto(`${M}/course/view.php?id=${CID}`, { waitUntil: 'domcontentloaded' })
// Moodle 首次进课程会弹「新手引导」浮层，它会拦截点击，
// 表现为「元素可见但点不到」。先关掉。
const endTour = page.locator('[data-role="end"], button:has-text("End tour"), a:has-text("End tour")')
if (await endTour.count()) {
  await endTour.first().click().catch(() => {})
  await page.waitForTimeout(1200)
}
await page.keyboard.press('Escape').catch(() => {})
await page.waitForTimeout(500)

const act = page.locator('a:has-text("眼底判读练习")')
console.log(await act.count() ? '✓ 课程页看到活动' : '✗ 课程页没有活动')
if (await act.count()) {
  await act.first().click(); await page.waitForLoadState('domcontentloaded'); await page.waitForTimeout(2500)
  const btn = page.locator('input[value*="Launch"],button:has-text("Launch"),a:has-text("Launch"),input[type=submit]')
  if (await btn.count()) { await btn.first().click(); await page.waitForTimeout(8000) }
}
const all = [page, ...seen]
const urls = []
for (const pg of all) { urls.push(pg.url()); pg.frames().forEach(f => urls.push(f.url())) }
const candidates = [...history, ...urls]
const entry = candidates.find(u => u.includes('/lti-entry?token='))
const landed = candidates.find(u => /\/(training\/reading|reading|case-browse)/.test(u))
const hit = entry && landed ? `${entry.slice(0,60)}… → ${landed}` : (entry || landed)
console.log(hit ? `✓ 已落到慧眼: ${hit.slice(0,120)}` : `✗ 未落到慧眼\n  实际: ${[...new Set(urls)].join('\n  ')}`)
for (const [i,pg] of all.entries()) { try { await pg.screenshot({path:`scripts/launch-${i}.png`, fullPage:true}) } catch {} }
await b.close(); process.exitCode = hit ? 0 : 1
