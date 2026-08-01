/**
 * OIDC 授权码 + PKCE 登录
 *
 * 对应方案 Phase 1「Keycloak 接入 + 身份对齐」。
 *
 * 为什么必须走授权码流程，而不是把用户名口令直接发给后端：
 *   1. 首次登录强制改密、账号锁定提示、后续的 MFA，都只能在
 *      Keycloak 自己的登录页面上完成；口令直传（ROPC）拿不到这些能力，
 *      迁移后带 UPDATE_PASSWORD 的用户会卡死在「登录失败」上；
 *   2. 口令不再经过本平台，前端与后端都不接触明文；
 *   3. PKCE（S256）让公共客户端也能安全地换取令牌，无需在前端存放密钥。
 */

const VERIFIER_KEY = 'huiyan_pkce_verifier'
const STATE_KEY = 'huiyan_oidc_state'
const REDIRECT_KEY = 'huiyan_oidc_redirect'

export interface OidcConfig {
  enabled: boolean
  issuer: string
  clientId: string
  authorizationEndpoint: string
  tokenEndpoint: string
  endSessionEndpoint: string
  accountUrl: string
}

export interface OidcTokens {
  access_token: string
  refresh_token?: string
  id_token?: string
  expires_in: number
}

/* ========== PKCE 基础工具 ========== */

const randomString = (bytes = 32): string => {
  const arr = new Uint8Array(bytes)
  crypto.getRandomValues(arr)
  return base64UrlEncode(arr)
}

function base64UrlEncode(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf)
  let str = ''
  bytes.forEach((b) => (str += String.fromCharCode(b)))
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** S256：challenge = BASE64URL(SHA256(verifier)) */
async function codeChallengeOf(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(verifier)
  )
  return base64UrlEncode(digest)
}

export const redirectUri = (): string =>
  `${window.location.origin}/oidc/callback`

/* ========== 发起登录 ========== */

/**
 * 跳转到 Keycloak 登录页。
 *
 * @param cfg           后端下发的 OIDC 配置
 * @param afterLoginTo  登录完成后要回到的应用内路径
 */
export async function startLogin(
  cfg: OidcConfig,
  afterLoginTo = '/'
): Promise<void> {
  const verifier = randomString()
  const state = randomString(16)

  // verifier 只能留在本端，绝不能进 URL——这正是 PKCE 防截获的关键
  sessionStorage.setItem(VERIFIER_KEY, verifier)
  sessionStorage.setItem(STATE_KEY, state)
  sessionStorage.setItem(REDIRECT_KEY, afterLoginTo)

  const params = new URLSearchParams({
    client_id: cfg.clientId,
    redirect_uri: redirectUri(),
    response_type: 'code',
    scope: 'openid profile email',
    state,
    code_challenge: await codeChallengeOf(verifier),
    code_challenge_method: 'S256'
  })

  window.location.href = `${cfg.authorizationEndpoint}?${params.toString()}`
}

/* ========== 处理回调 ========== */

export interface CallbackResult {
  ok: boolean
  tokens?: OidcTokens
  redirectTo: string
  error?: string
}

/**
 * 在回调页调用：用授权码换取令牌。
 *
 * state 必须逐字比对——不校验就等于给了 CSRF 可乘之机。
 */
export async function handleCallback(cfg: OidcConfig): Promise<CallbackResult> {
  const query = new URLSearchParams(window.location.search)
  const redirectTo = sessionStorage.getItem(REDIRECT_KEY) || '/'

  const err = query.get('error')
  if (err) {
    cleanup()
    return {
      ok: false,
      redirectTo,
      error: query.get('error_description') || err
    }
  }

  const code = query.get('code')
  const state = query.get('state')
  const expectedState = sessionStorage.getItem(STATE_KEY)
  const verifier = sessionStorage.getItem(VERIFIER_KEY)

  if (!code || !verifier) {
    cleanup()
    return { ok: false, redirectTo, error: '登录会话已失效，请重新登录' }
  }
  if (!state || state !== expectedState) {
    cleanup()
    return { ok: false, redirectTo, error: '登录状态校验失败，请重新登录' }
  }

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: cfg.clientId,
    code,
    redirect_uri: redirectUri(),
    code_verifier: verifier
  })

  try {
    const resp = await fetch(cfg.tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body
    })
    if (!resp.ok) {
      const detail = await resp.text()
      cleanup()
      return { ok: false, redirectTo, error: `换取令牌失败：${detail.slice(0, 120)}` }
    }
    const tokens: OidcTokens = await resp.json()
    cleanup()
    return { ok: true, tokens, redirectTo }
  } catch (e: any) {
    cleanup()
    return { ok: false, redirectTo, error: e?.message || '网络异常' }
  }
}

function cleanup() {
  sessionStorage.removeItem(VERIFIER_KEY)
  sessionStorage.removeItem(STATE_KEY)
  sessionStorage.removeItem(REDIRECT_KEY)
}

/* ========== 令牌解析 ========== */

export interface TokenClaims {
  preferred_username?: string
  name?: string
  email?: string
  realm_access?: { roles?: string[] }
  exp?: number
}

/**
 * 解析 JWT 载荷。
 *
 * 仅用于界面展示（显示用户名、决定菜单可见性）。
 * 真正的权限判定一律在服务端完成——前端解析出来的东西不可信。
 */
export function parseClaims(accessToken: string): TokenClaims | null {
  try {
    const part = accessToken.split('.')[1]
    if (!part) return null
    const padded = part.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(padded)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(json)
  } catch {
    return null
  }
}

/** Keycloak realm 角色 → 前端角色标识 */
export function frontRoleOf(claims: TokenClaims | null): string {
  const roles = claims?.realm_access?.roles || []
  if (roles.includes('ADMIN')) return 'admin'
  if (roles.includes('TEACHER')) return 'doctor'
  if (roles.includes('STUDENT')) return 'trainee'
  if (roles.includes('PATIENT')) return 'patient'
  return ''
}

/* ========== 退出 ========== */

export function logoutUrl(cfg: OidcConfig, idToken?: string): string {
  const params = new URLSearchParams({
    post_logout_redirect_uri: `${window.location.origin}/login`
  })
  if (idToken) params.set('id_token_hint', idToken)
  else params.set('client_id', cfg.clientId)
  return `${cfg.endSessionEndpoint}?${params.toString()}`
}
