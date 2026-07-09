/**
 * Cornerstone 初始化（仅一次）
 * - cornerstone-core
 * - cornerstone-tools
 * - cornerstone-web-image-loader（用于加载普通 PNG/JPG 眼底图）
 * - hammerjs（cornerstone-tools 触摸/手势依赖）
 *
 * 用法：
 *   import { ensureCornerstone, cornerstone, cornerstoneTools } from '@/utils/cornerstone'
 *   await ensureCornerstone()
 *   cornerstone.enable(el)
 */
import cornerstone from 'cornerstone-core'
import cornerstoneTools from 'cornerstone-tools'
import cornerstoneWebImageLoader from 'cornerstone-web-image-loader'
import cornerstoneMath from 'cornerstone-math'
import Hammer from 'hammerjs'

let initialized = false

export const ensureCornerstone = (): void => {
  if (initialized) return

  // 桥接外部依赖
  cornerstoneTools.external.cornerstone = cornerstone
  cornerstoneTools.external.cornerstoneMath = cornerstoneMath
  cornerstoneTools.external.Hammer = Hammer

  cornerstoneWebImageLoader.external.cornerstone = cornerstone
  cornerstoneWebImageLoader.configure({
    beforeSend: (xhr: XMLHttpRequest) => {
      const token = localStorage.getItem('huiyan_token')
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      }
    }
  })

  cornerstoneTools.init({
    showSVGCursors: true,
    globalToolSyncEnabled: false
  })

  initialized = true
}

/**
 * 把普通 URL 转成 cornerstone-web-image-loader 接受的 imageId。
 *
 * cornerstone-core 用 imageId 第一个冒号前的子串作为 scheme，
 * cornerstone-web-image-loader 注册了 'http' 和 'https' 两个 scheme，
 * 然后把整个 imageId 直接 `xhr.open('GET', imageId)`。
 *
 * 因此正确做法是：
 * - 已是 http(s):// 开头 → 原样返回
 * - 站内相对路径 (/static/...) → 拼当前 origin 成完整绝对 URL
 * - 其他形式（裸文件名 / file: / blob: 等）→ 按需处理
 *
 * 不要再用 `http:` 替换 `http://`，那会破坏 URL 让 XHR 拿不到 host。
 */
export const toImageId = (url: string): string => {
  if (!url) return ''
  const trimmed = url.trim()
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed
  }
  if (trimmed.startsWith('//')) {
    return `${window.location.protocol}${trimmed}`
  }
  if (trimmed.startsWith('/')) {
    return `${window.location.origin}${trimmed}`
  }
  // blob: / data: / file: 等保留不动；裸文件名相对当前页面
  if (/^[a-z]+:/i.test(trimmed)) return trimmed
  return new URL(trimmed, window.location.href).toString()
}

export { cornerstone, cornerstoneTools }
