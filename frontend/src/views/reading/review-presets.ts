/** 教师审核用的眼科常用评语。写入记录时仍是一整段 reviewComment 字符串。 */

export const PASS_PRESETS = [
  '质量合格，对焦清晰',
  '病灶圈选准确',
  '分级符合眼底标准'
] as const

export const REVISE_PRESETS = [
  '周边视网膜出血点漏标',
  '视盘杯盘比(C/D)估算偏大',
  '硬性渗出与软性渗出混淆',
  '未标注黄斑区中心凹水肿',
  '请对照无赤光绿光通道重核'
] as const

export const EXCELLENT_PASS_COMMENT = '标注规范，病灶识别准确，予以通过。'

/** 把一条短语接到已有评语后面，保留医生已经手打的内容。 */
export function appendReviewComment(current: string, phrase: string): string {
  const text = current.replace(/[ \t]+$/g, '')
  if (!text.trim()) return phrase
  if (text.endsWith(phrase)) return text
  if (/[。；;！？\n]$/.test(text) || /[，,、]$/.test(text)) return `${text}${phrase}`
  return `${text}；${phrase}`
}
