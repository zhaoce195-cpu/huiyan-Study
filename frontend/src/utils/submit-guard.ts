/**
 * 提交保护：最终摘要 → 二次确认 → 幂等重试
 *
 * 对应《医学培训端评估与工作流重构报告》8.3 P1 用例：
 *   「保存时断网并重复点击 → 不丢失、不重复提交」
 *
 * 三件事放在一处，因为它们本来就是一次提交动作的三个阶段：
 *   1. 摘要：把即将提交的结论按表单顺序摊开给学员核对。
 *      「确认提交吗」这种问法提供不了任何信息，学员只能盲点确定。
 *   2. 幂等键：一次提交动作生成一个，重试时原样带回。
 *   3. 重试：网络错误才重试。业务错误（400/403）重试没有意义，
 *      只会让学员多等几秒再看到同样的报错。
 */

export interface FieldOption {
  value: string
  label: string
}
export interface SummaryField {
  key: string
  label: string
  type: string
  required?: boolean
  options?: FieldOption[]
}
export interface SummaryFormDef {
  ungradableValue?: string
  skipWhenUngradable?: string[]
  fields: SummaryField[]
}

/** 幂等键：一次提交动作一个 */
export const newRequestId = (): string => {
  const c: any = globalThis.crypto
  if (c?.randomUUID) return c.randomUUID()
  // 老浏览器兜底。这个值只用于同一会话内比对，不作安全用途
  return `r-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

const optionLabel = (field: SummaryField, value: any): string => {
  if (!field.options) return String(value)
  const hit = field.options.find((o) => o.value === value)
  return hit ? hit.label : String(value)
}

/**
 * 把结构化作答渲染成人能核对的摘要。
 *
 * 只列实际填了的字段：把空字段也列出来会让摘要变长，
 * 反而盖住真正要核对的内容。未填的必填项由提交前校验负责。
 */
export const buildAnswerSummary = (
  form: SummaryFormDef | null,
  answers: Record<string, any>
): Array<{ label: string; text: string }> => {
  if (!form?.fields?.length) return []

  const ungradable =
    !!form.ungradableValue &&
    answers[form.fields[0]?.key] === form.ungradableValue
  const skip = new Set(ungradable ? form.skipWhenUngradable || [] : [])

  const rows: Array<{ label: string; text: string }> = []
  for (const field of form.fields) {
    if (skip.has(field.key)) continue
    const raw = answers[field.key]
    if (raw === undefined || raw === null || raw === '') continue
    if (Array.isArray(raw)) {
      if (!raw.length) continue
      rows.push({
        label: field.label,
        text: raw.map((v) => optionLabel(field, v)).join('、')
      })
    } else {
      rows.push({ label: field.label, text: optionLabel(field, raw) })
    }
  }
  return rows
}

const isBlank = (raw: unknown): boolean =>
  raw === undefined || raw === null || raw === '' || (Array.isArray(raw) && raw.length === 0)

/**
 * 只检查这张表单上实际出现、且当前仍然要求填写的字段。
 *
 * 青光眼、AMD 等病种没有 DR 分级这一项。不能另写一条「请选择 DR 分级」，
 * 否则题目上没有的字段会把交卷拦住。不可判读时，分级和征象已经隐藏，同样不再要求。
 */
export const missingRequiredFields = (
  form: SummaryFormDef | null,
  answers: Record<string, any>
): string[] => {
  if (!form?.fields?.length) return []
  const ungradable =
    !!form.ungradableValue && answers.readability === form.ungradableValue
  const skip = new Set(ungradable ? form.skipWhenUngradable || [] : [])
  const problems: string[] = []
  for (const field of form.fields) {
    if (!field.required || skip.has(field.key)) continue
    if (isBlank(answers[field.key])) problems.push(`请填写「${field.label}」`)
  }
  return problems
}

const escapeHtml = (s: string): string =>
  s.replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string
  ))

/** 摘要的 HTML。学员的自由文本会原样进来，必须转义 */
export const summaryHtml = (
  rows: Array<{ label: string; text: string }>,
  footer = ''
): string => {
  const body = rows.length
    ? rows
        .map(
          (r) =>
            `<div style="display:flex;gap:8px;padding:3px 0;line-height:1.6">` +
            `<span style="color:#86909c;flex:0 0 84px">${escapeHtml(r.label)}</span>` +
            `<span style="color:#1d2129;font-weight:500">${escapeHtml(r.text)}</span>` +
            `</div>`
        )
        .join('')
    : `<div style="color:#f56c6c">尚未填写任何结论</div>`
  const tail = footer
    ? `<div style="margin-top:10px;color:#86909c;font-size:12px">${escapeHtml(footer)}</div>`
    : ''
  return `<div style="max-height:46vh;overflow:auto">${body}</div>${tail}`
}

/**
 * 是否值得重试。
 *
 * 只认网络层失败：请求没送到、或响应没回来。后者最要命 ——
 * 服务端其实已经判完分了，此时带同一个幂等键重试，
 * 服务端会把原成绩回放回来，学员看到的是成功而不是报错。
 */
export const isRetriable = (err: any): boolean => {
  if (!err) return false
  if (err.code === 'ECONNABORTED' || err.code === 'ERR_NETWORK') return true
  if (err.message === 'Network Error') return true
  const s = err.response?.status
  return s === 502 || s === 503 || s === 504
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * 带退避的重试。幂等键由调用方持有并原样重发 ——
 * 每次重试都换一个键，等于每次都是一次新提交，幂等就白做了。
 */
export const submitWithRetry = async <T>(
  send: () => Promise<T>,
  opts: { attempts?: number; onRetry?: (attempt: number) => void } = {}
): Promise<T> => {
  const attempts = opts.attempts ?? 3
  let lastErr: any
  for (let i = 1; i <= attempts; i++) {
    try {
      return await send()
    } catch (err) {
      lastErr = err
      if (i === attempts || !isRetriable(err)) throw err
      opts.onRetry?.(i)
      await delay(i * 1000)
    }
  }
  throw lastErr
}
