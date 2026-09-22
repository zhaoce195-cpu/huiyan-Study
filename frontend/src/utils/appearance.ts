/**
 * 界面外观：字体大小
 *
 * 只改字号，不缩放整页。整页 zoom 会把侧栏放大到超过一屏，
 * 左下角的用户就会超出屏幕。字号通过 Element Plus 的字体变量生效，
 * 侧栏宽高保持不变。
 *
 * 偏好写在 localStorage：登录前、接口还没回来时也能立刻按上次的设置渲染，
 * 不至于先闪一下默认大小。后端仍是权威，取到之后覆盖本地值。
 */

export type FontSize = 'small' | 'normal' | 'large'

const STORAGE_KEY = 'huiyan_font_size'
const VALID: FontSize[] = ['small', 'normal', 'large']

const normalize = (v: unknown): FontSize =>
  VALID.includes(v as FontSize) ? (v as FontSize) : 'normal'

/** 落到 <html data-font-size="...">，配套样式在 styles/var.css */
export const applyFontSize = (v: unknown): FontSize => {
  const size = normalize(v)
  document.documentElement.dataset.fontSize = size
  try {
    localStorage.setItem(STORAGE_KEY, size)
  } catch {
    /* 隐私模式下 localStorage 可能不可写，不影响本次生效 */
  }
  return size
}

export const getStoredFontSize = (): FontSize => {
  try {
    return normalize(localStorage.getItem(STORAGE_KEY))
  } catch {
    return 'normal'
  }
}

/** 应用启动时调用，早于挂载，避免默认字号闪一下 */
export const initAppearance = (): void => {
  applyFontSize(getStoredFontSize())
}
