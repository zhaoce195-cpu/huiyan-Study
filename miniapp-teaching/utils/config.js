/**
 * 全局配置
 * ----------------------------------------------------------------
 * 开发联调：
 *   - 微信开发者工具需勾选「本地设置 → 不校验合法域名」才能访问 http/localhost
 *   - 真机预览 / 上线：BASE_URL 必须是已在小程序后台配置的 HTTPS 合法域名
 *   - localhost 仅模拟器可用，真机请改成电脑局域网 IP（如 http://192.168.1.10:8000）
 */

// 后端服务根地址（不含 /api/v1）
export const STATIC_ORIGIN = 'http://localhost:8000'

// 业务接口前缀
export const BASE_URL = `${STATIC_ORIGIN}/api/v1`

// 本地存储键名
export const TOKEN_KEY = 'huiyan_token'
export const USER_KEY = 'huiyan_user'

/**
 * 把后端返回的相对资源路径（/static/...）补全为可访问的绝对地址
 */
export function resolveUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/')) return `${STATIC_ORIGIN}${url}`
  return `${STATIC_ORIGIN}/${url}`
}
