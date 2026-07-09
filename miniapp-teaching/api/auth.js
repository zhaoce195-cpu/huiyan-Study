/**
 * 登录 / 鉴权 API
 */
import { get, post } from './request'

const BACKEND_ROLE_MAP = {
  STUDENT: 'trainee',
  TEACHER: 'doctor',
  ADMIN: 'admin',
  PATIENT: 'patient',
}

/** 后端 UserOut（snake_case）→ 小程序内统一用户结构 */
export function normalizeUser(raw) {
  if (!raw) return null
  const rawRole = (raw.role || raw.rawRole || '').toString().toUpperCase()
  return {
    id: raw.id,
    username: raw.username,
    name: raw.real_name || raw.name || raw.username || '',
    avatar: raw.avatar || '',
    role: BACKEND_ROLE_MAP[rawRole] || 'trainee',
    rawRole,
    roleName: raw.role_name || '',
    department: raw.department || '',
    title: raw.title || '',
    phone: raw.phone || '',
    email: raw.email || '',
  }
}

/** 账号密码登录（开发/兜底） */
export async function loginByPassword(username, password) {
  const data = await post('/auth/login', { username, password }, { withToken: false, showError: false })
  return { token: data.token, user: normalizeUser(data.user_info) }
}

/**
 * 微信登录：wx.login 拿 code → 后端换 openid
 * 返回 { needBind, ticket, token, user }
 */
export async function wechatLogin(code) {
  const data = await post('/auth/wechat/login', { code }, { withToken: false, showError: false })
  if (data.need_bind) {
    return { needBind: true, ticket: data.ticket }
  }
  return {
    needBind: false,
    token: data.login.token,
    user: normalizeUser(data.login.user_info),
  }
}

/** 微信首次绑定已有账号 */
export async function wechatBind(ticket, username, password) {
  const data = await post(
    '/auth/wechat/bind',
    { ticket, username, password },
    { withToken: false, showError: false }
  )
  return { token: data.token, user: normalizeUser(data.user_info) }
}

/** 获取当前用户信息 */
export async function getProfile() {
  const raw = await get('/user/profile')
  return normalizeUser(raw)
}

/** 退出登录 */
export function logout() {
  return post('/auth/logout', null, { showError: false }).catch(() => {})
}

/** 调用 wx.login 取 code（Promise 封装） */
export function getWxCode() {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: 'weixin',
      success: (res) => (res.code ? resolve(res.code) : reject(new Error('未获取到 code'))),
      fail: reject,
    })
  })
}
