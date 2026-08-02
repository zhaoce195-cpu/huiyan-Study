/**
 * 在 Moodle 里完成慧眼的 LTI 1.3 动态注册（本地联调用）
 *
 * Moodle 的「外部工具」注册没有 CLI，只能走管理界面。
 * 手工点一遍要跨四五个页面，且每次重建环境都要重来，
 * 所以脚本化 —— 联调环境要能一条命令重建，否则没人愿意重建。
 *
 * 用法：
 *   node scripts/moodle_lti_setup.mjs <moodleUrl> <admin> <password> <toolRegUrl>
 */
import { chromium } from 'playwright'

const [MOODLE, USER, PASS, TOOL_URL] = process.argv.slice(2)
if (!MOODLE || !USER || !PASS || !TOOL_URL) {
  console.log('用法: node scripts/moodle_lti_setup.mjs <moodleUrl> <admin> <pass> <toolRegUrl>')
  process.exit(2)
}

const browser = await chromium.launch()
const ctx = await browser.newContext({ ignoreHTTPSErrors: true })
const page = await ctx.newPage()
const log = (s) => console.log(s)

try {
  // ---- 登录 ----
  await page.goto(`${MOODLE}/login/index.php`, { waitUntil: 'domcontentloaded' })
  await page.fill('#username', USER)
  await page.fill('#password', PASS)
  await page.click('#loginbtn')
  await page.waitForLoadState('domcontentloaded')

  if (await page.locator('#username').count()) {
    throw new Error('登录失败：账号或口令不对')
  }
  log('✓ 已登录 Moodle')

  // 首次登录可能要求确认站点策略 / 修改口令，先处理掉
  if (page.url().includes('user/edit.php') || page.url().includes('changepassword')) {
    throw new Error('管理员账号被要求改口令，请先在浏览器里处理一次')
  }

  // ---- 打开工具管理页 ----
  // 动态注册在 toolconfigure.php，不是 admin/settings.php?section=modsettinglti。
  // 后者是「已配置工具列表」，上面没有注册入口。
  await page.goto(`${MOODLE}/mod/lti/toolconfigure.php`, {
    waitUntil: 'domcontentloaded'
  })
  await page.waitForTimeout(2000)
  log('✓ 打开工具管理页')

  // ---- 填注册 URL，点「Add LTI Advantage」----
  const input = page.locator('input[placeholder*="Tool URL"], #tool-url')
  await input.first().waitFor({ timeout: 15000 })
  await input.first().fill(TOOL_URL)
  log(`✓ 已填入注册地址：${TOOL_URL}`)

  // 注册在弹窗里完成，弹窗关闭即代表流程走完
  await page.locator('button:has-text("Add LTI Advantage")').click()
  await page.waitForTimeout(12000)

  // ---- 确认结果 ----
  // 动态注册的工具落在 Pending，要激活才能在课程里用
  await page.goto(`${MOODLE}/mod/lti/toolconfigure.php`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2500)

  // 只在工具卡片区域里找，不要在整页文本里搜「慧眼」——
  // Moodle 站点名本身就叫「慧眼 · 医学教育与能力评估平台」，
  // 整页搜必然命中页头，得到一个永远为真的假阳性。
  const cards = page.locator('.tool-card, [data-toolid], .lti-tool-card')
  const cardCount = await cards.count()
  let registered = false
  for (let i = 0; i < cardCount; i++) {
    const t = (await cards.nth(i).innerText().catch(() => '')) || ''
    if (/慧眼|Huiyan/i.test(t)) { registered = true; break }
  }
  log(registered
    ? `✓ 工具卡片已出现（共 ${cardCount} 个）`
    : `✗ 工具卡片区域里没有慧眼（共 ${cardCount} 个卡片）`)

  // 激活 Pending 的注册
  const activate = page.locator('a:has-text("Activate"), button:has-text("Activate")')
  if (await activate.count()) {
    await activate.first().click()
    await page.waitForTimeout(3000)
    log('✓ 已激活工具')
  }

  await page.screenshot({ path: 'scripts/moodle-lti-result.png', fullPage: true })
  log('  截图：frontend/scripts/moodle-lti-result.png')
  process.exitCode = registered ? 0 : 1
} catch (e) {
  log('✗ ' + e.message)
  try {
    await page.screenshot({ path: 'scripts/moodle-lti-error.png', fullPage: true })
    log('  错误截图：frontend/scripts/moodle-lti-error.png')
  } catch {}
  process.exitCode = 1
} finally {
  await browser.close()
}
