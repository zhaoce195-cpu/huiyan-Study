import { chromium } from 'playwright'
const BASE = 'http://113.219.243.122:9081'
const b = await chromium.launch(); const p = await b.newPage()
const login = async () => {
  await p.goto(BASE + '/login', { waitUntil:'domcontentloaded' })
  await p.evaluate(async (base) => {
    const r = await fetch(base + '/api/v1/auth/login', { method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username:'teacher', password:'Huiyan@123'})}).then(r=>r.json())
    const t = (r.data||{}).token || (r.data||{}).accessToken
    if (t) localStorage.setItem('huiyan_token', t)
  }, BASE)
}
const openReading = async () => {
  await p.goto(BASE + '/training/reading?caseId=169', { waitUntil:'domcontentloaded' })
  await p.waitForTimeout(9000)
  const dlg = p.locator('.el-dialog__headerbtn').first()
  if (await dlg.count()) { await dlg.click().catch(()=>{}); await p.waitForTimeout(700) }
  await p.keyboard.press('Escape').catch(()=>{}); await p.waitForTimeout(500)
}
const painted = () => p.evaluate(() => {
  const c = document.querySelector('canvas.overlay')
  const d = c?.getContext('2d')?.getImageData(0,0,c.width,c.height).data
  let n=0; if (d) for (let i=3;i<d.length;i+=4) if (d[i]>0) n++
  return n
})

await login(); await openReading()
const box = await p.locator('.cs-element').boundingBox()
const cx = box.x + box.width/2, cy = box.y + box.height/2

// 画一个矩形
await p.locator('button:has-text("矩形")').first().click(); await p.waitForTimeout(500)
await p.mouse.move(cx-80, cy-60); await p.mouse.down()
await p.mouse.move(cx+50, cy+40, {steps:10}); await p.mouse.up()
await p.waitForTimeout(1000)
const drawn = await painted()
console.log(`① 画矩形         非透明像素 ${drawn}`)

// 等自动暂存
await p.waitForTimeout(4500)
const hint = await p.evaluate(() => document.querySelector('.autosave-hint')?.textContent?.trim() || '（无）')
console.log(`② 自动暂存提示   ${hint}`)

// 刷新后是否还在
await openReading()
const afterReload = await painted()
console.log(`③ 刷新后         非透明像素 ${afterReload}  ${afterReload > 50 ? '✓ 标注仍在' : '✗ 丢失'}`)
await b.close()
