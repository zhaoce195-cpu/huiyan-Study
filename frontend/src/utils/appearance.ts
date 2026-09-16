/**
 * 界面外观：字体大小
 *
 * 为什么用 zoom 而不是改 root font-size：
 * 全站有 300+ 处硬编码的 `font-size: NNpx`，只有 20 来处 rem，所以调 html 的
 * font-size 基本不会有任何可见变化 —— 用户测试报告里「字体大小改了没反应」
 * 就是这么来的。zoom 直接缩放整个渲染树，px 字面量、Element Plus 组件、
 * teleport 到 body 的弹窗都一起跟着走。
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
