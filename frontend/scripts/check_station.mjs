// 阅片内核自检：Playwright 无头跑一遍，读 window.__stationCheck
import { chromium } from 'playwright'

const PORT = process.argv[2] || '5178'
const IMG = '/static/demo/fundus_dr2_01.jpg'
const url = `http://127.0.0.1:${PORT}/spike/station-check?img=${encodeURIComponent(IMG)}`

const browser = await chromium.launch()
const page = await browser.newPage()

const errors = []
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text())
})
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))

await page.goto(url, { waitUntil: 'domcontentloaded' })

let result = null
try {
  await page.waitForFunction(() => window.__stationCheck, null, { timeout: 45000 })
  result = await page.evaluate(() => window.__stationCheck)
} catch (e) {
  console.log('超时：自检未产出结果')
  console.log('最终 URL:', page.url())
  console.log('页面文本:', (await page.evaluate(() => document.body.innerText || '')).slice(0, 400))
}

console.log('='.repeat(58))
if (result) {
  for (const c of result.checks) {
    console.log(`${c.pass ? '✓' : '✗'} ${c.name}${c.detail ? '  —— ' + c.detail : ''}`)
  }
  console.log('-'.repeat(58))
  console.log('尺寸:', result.dimensions ? result.dimensions.join(' × ') : '—')
  console.log('结论:', result.passed ? '全部通过' : '存在失败项')
}
if (errors.length) {
  console.log('-'.repeat(58))
  console.log('控制台错误:')
  errors.slice(0, 8).forEach((e) => console.log('  ' + e.slice(0, 300)))
}
console.log('='.repeat(58))

await browser.close()
process.exit(result?.passed ? 0 : 1)
