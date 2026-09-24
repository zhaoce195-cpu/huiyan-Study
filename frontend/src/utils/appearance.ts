/**
 * 界面外观：字体大小、浅色 / 深色
 *
 * 字号只改文字，不缩放整页。整页 zoom 会把侧栏放大到超过一屏，
 * 左下角的用户就会超出屏幕。
 *
 * 风格写在 html[data-theme]，学员培训端和管理员筛查端共用同一组变量。
 * 偏好同时写在 localStorage：登录前、接口还没回来时也能立刻按上次的设置渲染。
 * 后端仍是权威，取到之后覆盖本地值。
 */

export type FontSize = 'small' | 'normal' | 'large'
export type ThemeName = 'light' | 'dark'

const FONT_KEY = 'huiyan_font_size'
const THEME_KEY = 'huiyan_theme'
const FONT_SIZES: FontSize[] = ['small', 'normal', 'large']

const normalizeFont = (v: unknown): FontSize =>
  FONT_SIZES.includes(v as FontSize) ? (v as FontSize) : 'normal'

/** 后端的 auto 没有跟随系统的实现，按浅色处理。 */
const normalizeTheme = (v: unknown): ThemeName => (v === 'dark' ? 'dark' : 'light')

const writeLocal = (key: string, value: string): void => {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* 隐私模式下 localStorage 可能不可写，不影响本次生效 */
  }
}

/** 落到 <html data-font-size="...">，配套样式在 styles/var.css */
export const applyFontSize = (v: unknown): FontSize => {
  const size = normalizeFont(v)
  document.documentElement.dataset.fontSize = size
  writeLocal(FONT_KEY, size)
  return size
}

/** 落到 <html data-theme="light|dark"> */
export const applyTheme = (v: unknown): ThemeName => {
  const theme = normalizeTheme(v)
  document.documentElement.dataset.theme = theme
  writeLocal(THEME_KEY, theme)
  return theme
}

export const getStoredFontSize = (): FontSize => {
  try {
    return normalizeFont(localStorage.getItem(FONT_KEY))
  } catch {
    return 'normal'
  }
}

export const getStoredTheme = (): ThemeName => {
  try {
    return normalizeTheme(localStorage.getItem(THEME_KEY))
  } catch {
    return 'light'
  }
}

/** 应用启动时调用，早于挂载，避免默认外观闪一下 */
export const initAppearance = (): void => {
  applyFontSize(getStoredFontSize())
  applyTheme(getStoredTheme())
}
