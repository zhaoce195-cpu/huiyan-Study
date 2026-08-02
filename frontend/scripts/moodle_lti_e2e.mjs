/**
 * Moodle ↔ 慧眼 LTI 1.3 端到端联调
 *
 * 建学员账号 → 建课程 → 加外部工具活动 → 以学员身份点开 → 落到慧眼工作台。
 *
 * 为什么要跑通这一条：单元测试验的是「令牌校验逻辑对不对」，
 * 但真实链路里还有一堆能悄悄断掉的东西 —— Cookie 的 SameSite、
 * 平台能不能回访我们的 JWKS、redirect_uri 与注册值是否一致、
 * 邮箱能不能对上本地账号。这些都只有真跑才知道。
 *
 * 用法：
 *   node scripts/moodle_lti_e2e.mjs <moodleUrl> <admin> <adminPass> <studentEmail>
 */
import { chromium } from 'playwright'

const [MOODLE, ADMIN, ADMIN_PASS, STU_EMAIL] = process.argv.slice(2)
const STU_USER = 'lti_stu'
const STU_PASS = 'Huiyan-lti-1!'
const COURSE = '眼底影像判读实训'
// 预置工具 id：由调用方传入（见 README 里的取法）
const TYPE_ID = process.argv[6] || '1'

const browser = await chromium.launch()
const ctx = await browser.newContext()
const page = await ctx.newPage()
const log = (s) => console.log(s)
const steps = []
const step = (name, ok, detail = '') => {
  steps.push({ name, ok })
  log(`${ok ? '✓' : '✗'} ${name}${detail ? '  —— ' + detail : ''}`)
  return ok
}

async function login(user, pass) {
  await page.goto(`${MOODLE}/login/index.php`, { waitUntil: 'domcontentloaded' })
  await page.fill('#username', user)
  await page.fill('#password', pass)
  await page.click('#loginbtn')
  await page.waitForLoadState('domcontentloaded')
  return !(await page.locator('#username').count())
}

async function logout() {
  await page.goto(`${MOODLE}/login/logout.php`, { waitUntil: 'domcontentloaded' })
  const confirm = page.locator('button:has-text("Continue"), a:has-text("Continue")')
  if (await confirm.count()) await confirm.first().click()
  await page.waitForTimeout(1500)
}

try {
  step('管理员登录', await login(ADMIN, ADMIN_PASS))

  // ---- 建学员账号（邮箱与慧眼本地账号一致，身份靠它对上）----
  await page.goto(`${MOODLE}/user/editadvanced.php?id=-1`, { waitUntil: 'domcontentloaded' })
  if (await page.locator('#id_username').count()) {
    await page.fill('#id_username', STU_USER)
    // Moodle 的密码框默认被 unmask 组件隐藏（class d-none），
    // 直接 fill 会一直等「元素可见」而超时。先点展开链接。
    const reveal = page.locator(
      '[data-passwordunmask="edit"], a:has-text("Click to enter text")'
    )
    if (await reveal.count()) {
      await reveal.first().click()
      await page.waitForTimeout(500)
    }
    const pwd = page.locator('#id_newpassword')
    if (await pwd.count()) {
      await pwd.fill(STU_PASS, { force: true }).catch(async () => {
        // 兜底：仍不可见时直接赋值并触发事件，Moodle 的校验挂在 change 上
        await page.evaluate((v) => {
          const el = document.querySelector('#id_newpassword')
          if (el) {
            el.classList.remove('d-none')
            el.value = v
            el.dispatchEvent(new Event('input', { bubbles: true }))
            el.dispatchEvent(new Event('change', { bubbles: true }))
          }
        }, STU_PASS)
      })
    }
    await page.fill('#id_firstname', '学员')
    await page.fill('#id_lastname', '甲')
    await page.fill('#id_email', STU_EMAIL)
    await page.locator('#id_submitbutton').click()
    await page.waitForTimeout(3000)
  }
  const userList = await page.goto(`${MOODLE}/admin/user.php`, { waitUntil: 'domcontentloaded' })
  const hasUser = (await page.evaluate(() => document.body.innerText)).includes(STU_EMAIL)
  step('学员账号已建立', hasUser, STU_EMAIL)

  // ---- 建课程（可重复执行：已存在就复用）----
  // 联调脚本必须能反复跑。第二次跑时短名重复会创建失败，
  // 若不处理，后续步骤全部连锁失败，看起来像 LTI 坏了。
  let courseId = ''
  await page.goto(`${MOODLE}/course/search.php?search=FUNDUS-01`,
                  { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  const existing = await page.evaluate(() => {
    const a = [...document.querySelectorAll('a[href*="course/view.php?id="]')][0]
    return a ? a.getAttribute('href') : ''
  })
  if (existing) {
    courseId = (existing.match(/id=(\d+)/) || [])[1] || ''
    step('课程已存在，复用', !!courseId, `id=${courseId}`)
  }

  if (!courseId) {
  await page.goto(`${MOODLE}/course/edit.php?category=1`, { waitUntil: 'domcontentloaded' })
  await page.fill('#id_fullname', COURSE)
  await page.fill('#id_shortname', 'FUNDUS-01')
  // Moodle 5 的课程表单只有「Save and display」，没有 saveandreturn，
  // 按不存在的 id 点会一直等到超时
  await page.locator('#id_saveanddisplay, #id_saveandreturn, #id_submitbutton')
    .first().click()
  await page.waitForTimeout(4000)
  const courseUrl = page.url()
  courseId = (courseUrl.match(/id=(\d+)/) || [])[1] || ''
  step('课程已建立', !!courseId, courseUrl.slice(0, 80))
  }

  // ---- 选课 ----
  if (courseId) {
    await page.goto(`${MOODLE}/user/index.php?id=${courseId}`, { waitUntil: 'domcontentloaded' })
    const enrolBtn = page.locator('a:has-text("Enrol users"), button:has-text("Enrol users")')
    if (await enrolBtn.count()) {
      await enrolBtn.first().click()
      await page.waitForTimeout(2000)
      const search = page.locator('input[role="combobox"], .form-autocomplete-input').first()
      if (await search.count()) {
        await search.fill('学员')
        await page.waitForTimeout(2500)
        const opt = page.locator('.form-autocomplete-suggestions li').first()
        if (await opt.count()) await opt.click()
      }
      await page.locator('button:has-text("Enrol users"), input[value*="Enrol"]').last().click()
      await page.waitForTimeout(3000)
    }
    const enrolled = (await page.evaluate(() => document.body.innerText)).includes('学员')
    step('学员已选课', enrolled)
  }

  // ---- 加外部工具活动 ----
  if (courseId) {
    // Moodle 5 起不再允许「不指定预置工具」地创建 LTI 活动，
    // URL 必须带 typeid，否则直接报「no longer supported」。
    // typeid 从工具注册表取，不写死。
    await page.goto(
      `${MOODLE}/course/modedit.php?add=lti&course=${courseId}&section=1&typeid=${TYPE_ID}`,
      { waitUntil: 'domcontentloaded' }
    )
    await page.waitForTimeout(3000)
    await page.fill('#id_name', '眼底判读练习（第一例）')
    // 自定义参数把病例号带过去；不填则学员落到病例列表
    const custom = page.locator('#id_instructorcustomparameters')
    if (await custom.count()) await custom.fill('case_id=89')
    await page.locator('#id_submitbutton2, #id_submitbutton').first().click()
    await page.waitForTimeout(4000)
    step('外部工具活动已添加', page.url().includes('course/view.php'), page.url().slice(0, 70))
  }

  // ---- 以学员身份启动 ----
  await logout()
  step('学员登录', await login(STU_USER, STU_PASS))

  await page.goto(`${MOODLE}/course/view.php?id=${courseId}`, { waitUntil: 'domcontentloaded' })
  const activity = page.locator('a:has-text("眼底判读练习")')
  if (await activity.count()) {
    await activity.first().click()
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
    // Moodle 默认在新窗口/内嵌里打开；先尝试页面内的「启动」按钮
    const launchBtn = page.locator('input[value*="Launch"], button:has-text("Launch"), a:has-text("Launch")')
    if (await launchBtn.count()) {
      await launchBtn.first().click()
      await page.waitForTimeout(6000)
    }
  }

  // 工具可能在 iframe 里，逐个看落到了哪
  const urls = [page.url(), ...page.frames().map((f) => f.url())]
  const landed = urls.find((u) => u.includes('lti-entry') || u.includes('/api/v1/lti/'))
  step('已落到慧眼', !!landed, landed || urls.join(' | ').slice(0, 160))

  await page.screenshot({ path: 'scripts/moodle-e2e.png', fullPage: true })
  log('  截图：frontend/scripts/moodle-e2e.png')
} catch (e) {
  step('执行', false, e.message)
  try { await page.screenshot({ path: 'scripts/moodle-e2e-error.png', fullPage: true }) } catch {}
} finally {
  const failed = steps.filter((s) => !s.ok).length
  log('-'.repeat(50))
  log(failed ? `${failed} 步未通过` : '全部通过')
  await browser.close()
  process.exitCode = failed ? 1 : 0
}
