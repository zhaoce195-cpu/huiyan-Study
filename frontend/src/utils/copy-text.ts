/** 把一段文字放进剪贴板。浏览器禁止剪贴板时退回选区复制。 */
export async function copyText(text: string): Promise<boolean> {
  const value = text.trim()
  if (!value) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {
    /* 非安全上下文或未授权时走下面的选区 */
  }
  try {
    const input = document.createElement('textarea')
    input.value = value
    input.setAttribute('readonly', 'true')
    input.style.position = 'fixed'
    input.style.top = '0'
    input.style.left = '0'
    input.style.opacity = '0'
    document.body.appendChild(input)
    input.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(input)
    return ok
  } catch {
    return false
  }
}
