import { chromium } from 'playwright'
const [study, series, sop, token, seg] = process.argv.slice(2)
const url = `http://127.0.0.1:5178/spike/station-check?study=${study}&series=${series}&sop=${sop}` + (seg ? `&seg=${seg}` : '')
const b = await chromium.launch(); const p = await b.newPage()
const errs = []
p.on('console', m => { if (m.type()==='error') errs.push(m.text()) })
p.on('pageerror', e => errs.push('pageerror: '+e.message))
// wadors 走鉴权，先注入 token
await p.addInitScript(t => localStorage.setItem('huiyan_token', t), token || '')
await p.goto(url, { waitUntil: 'domcontentloaded' })
let r = null
try {
  await p.waitForFunction(() => window.__stationCheck, null, { timeout: 60000 })
  r = await p.evaluate(() => window.__stationCheck)
} catch { console.log('超时') }
console.log('='.repeat(58))
if (r) { for (const c of r.checks) console.log(`${c.pass?'✓':'✗'} ${c.name}${c.detail?'  —— '+c.detail:''}`) 
  console.log('-'.repeat(58)); console.log('结论:', r.passed?'全部通过':'存在失败项') }
if (errs.length) { console.log('控制台错误:'); errs.slice(0,6).forEach(e=>console.log('  '+e.slice(0,240))) }
console.log('='.repeat(58))
await b.close(); process.exit(r?.passed?0:1)
