import http from '@/utils/request'

/* ========== 类型定义 ========== */

export interface LoginParams {
  /** 账号 / 医师工号 */
  username: string
  /** 登录密码 */
  password: string
  /** 验证码（可选） */
  captcha?: string
  /** 验证码会话ID（可选） */
  captchaId?: string
  /** 记住登录 */
  remember?: boolean
}

/**
 * 角色统一规范化为前端语义：
 *   STUDENT → trainee
 *   TEACHER → doctor
 *   ADMIN   → admin
 */
export type FrontRole = 'admin' | 'doctor' | 'trainee' | 'inspector' | 'patient'
export type BackendRole = 'STUDENT' | 'TEACHER' | 'ADMIN' | 'PATIENT'

export interface UserInfo {
  /** 用户ID */
  id: number | string
  /** 用户名 */
  username: string
  /** 真实姓名 */
  name: string
  /** 头像 URL */
  avatar?: string
  /** 角色（前端规范化） */
  role: FrontRole
  /** 后端原始角色编码 */
  rawRole?: BackendRole
  /** 角色显示名 */
  roleName?: string
  /** 所属机构/医院 */
  hospital?: string
  /** 科室 */
  department?: string
  /** 职称 */
  title?: string
  /** 医师执业证号 */
  licenseNo?: string
  /** 邮箱 */
  email?: string
  /** 手机号 */
  phone?: string
  /** 权限点列表 */
  permissions?: string[]
  /** 上次登录时间 */
  lastLoginAt?: string
  /** 管理员重置临时密码后，下次登录必须改密 */
  mustChangePassword?: boolean
}

export interface LoginResult {
  /** 访问令牌 */
  token: string
  /** 刷新令牌（可选） */
  refreshToken?: string
  /** 过期时间（秒） */
  expiresIn?: number
  /** 用户信息 */
  userInfo: UserInfo
}

export interface CaptchaResult {
  captchaId: string
  image: string
}

export interface ChangePasswordParams {
  oldPassword: string
  newPassword: string
}

export interface UpdateProfileParams {
  realName?: string
  phone?: string
  email?: string
  department?: string
  title?: string
}

export interface AvatarUploadResult {
  avatarUrl: string
  fileName: string
  fileSize: number
}

export type ThemeMode = 'light' | 'dark' | 'auto'
export type FontSizeMode = 'small' | 'normal' | 'large'

export interface UserSetting {
  theme: ThemeMode
  fontSize: FontSizeMode
  language: string
  notifyMessage: boolean
  notifyEmail: boolean
  notifySms: boolean
  notifySound: boolean
}

export interface UserSettingUpdateParams {
  theme?: ThemeMode
  fontSize?: FontSizeMode
  language?: string
  notifyMessage?: boolean
  notifyEmail?: boolean
  notifySms?: boolean
  notifySound?: boolean
}

/* ========== 工具：后端响应 → 前端规范化 ========== */

const BACKEND_ROLE_MAP: Record<string, FrontRole> = {
  STUDENT: 'trainee',
  TEACHER: 'doctor',
  ADMIN: 'admin',
  PATIENT: 'patient'
}

/** 后端 UserOut（snake_case + role: STUDENT/TEACHER/ADMIN） → 前端 UserInfo */
const normalizeUser = (raw: any): UserInfo => {
  if (!raw) return raw
  const rawRole = (raw.role || raw.rawRole || '').toString().toUpperCase()
  const role: FrontRole = BACKEND_ROLE_MAP[rawRole] || (raw.role as FrontRole) || 'trainee'
  return {
    id: raw.id,
    username: raw.username,
    name: raw.name || raw.real_name || raw.realName || raw.username || '',
    avatar: raw.avatar,
    role,
    rawRole: (rawRole || undefined) as BackendRole | undefined,
    roleName: raw.role_name || raw.roleName,
    hospital: raw.hospital,
    department: raw.department,
    title: raw.title,
    licenseNo: raw.license_no || raw.licenseNo,
    email: raw.email,
    phone: raw.phone,
    permissions: raw.permissions || [],
    lastLoginAt: raw.last_login_at || raw.lastLoginAt,
    mustChangePassword: !!(raw.must_change_password ?? raw.mustChangePassword)
  }
}

/** 后端登录响应（含 user_info / token_type / expires_at）→ 前端 LoginResult */
const normalizeLoginResult = (raw: any): LoginResult => {
  const userRaw = raw?.user_info || raw?.userInfo
  return {
    token: raw?.token || '',
    refreshToken: raw?.refresh_token || raw?.refreshToken,
    expiresIn: raw?.expires_in || raw?.expiresIn,
    userInfo: normalizeUser(userRaw)
  }
}

/* ========== API 方法 ========== */

/** 用户登录 — 静默错误（页面层面会处理后端不可达兜底） */
export const login = async (params: LoginParams): Promise<LoginResult> => {
  const raw = await http.post<any>('/auth/login', params, {
    withToken: false,
    showError: false
  })
  return normalizeLoginResult(raw)
}

/** 用户登出 */
/** 统一身份登录（OIDC）配置 */
export interface OidcConfigResult {
  enabled: boolean
  issuer: string
  clientId: string
  authorizationEndpoint: string
  tokenEndpoint: string
  endSessionEndpoint: string
  accountUrl: string
}

/**
 * 取 OIDC 参数。前端据此发起授权码 + PKCE 流程，
 * 从而能用上 Keycloak 登录页的强制改密、账号锁定提示等能力。
 */
export const getOidcConfig = () =>
  http.get<OidcConfigResult>('/auth/oidc/config')

export const logout = () =>
  http.post<void>('/auth/logout', null, { showSuccess: true, successText: '已退出登录' })

/** 获取当前登录用户信息 — 后端复用 /user/profile */
export const getUserInfo = async (): Promise<UserInfo> => {
  const raw = await http.get<any>('/user/profile')
  return normalizeUser(raw)
}

/** 刷新访问令牌 */
export const refreshToken = async (refreshToken: string): Promise<LoginResult> => {
  const raw = await http.post<any>('/auth/refresh', { refreshToken }, { withToken: false })
  return normalizeLoginResult(raw)
}

/** 获取图形验证码（后端暂未实现，调用方自行容错） */
export const getCaptcha = () =>
  http.get<CaptchaResult>('/auth/captcha', undefined, { withToken: false })

/** 修改密码 — 后端路径 /user/password，需要 confirm_password */
export const changePassword = (params: ChangePasswordParams) =>
  http.post<void>(
    '/user/password',
    {
      old_password: params.oldPassword,
      new_password: params.newPassword,
      confirm_password: params.newPassword
    },
    { showSuccess: true, successText: '密码修改成功，请重新登录' }
  )

/** 修改个人资料 */
export const updateProfile = async (params: UpdateProfileParams): Promise<UserInfo> => {
  const raw = await http.put<any>(
    '/user/profile',
    {
      real_name: params.realName,
      phone: params.phone,
      email: params.email,
      department: params.department,
      title: params.title
    },
    { showSuccess: true, successText: '个人资料已更新' }
  )
  return normalizeUser(raw)
}

/** 上传头像 (multipart/form-data) */
export const uploadAvatar = async (file: File): Promise<AvatarUploadResult> => {
  const fd = new FormData()
  fd.append('file', file)
  const raw = await http.upload<any>('/user/avatar', fd, {
    showSuccess: true,
    successText: '头像更新成功'
  })
  return {
    avatarUrl: raw?.avatar_url || raw?.avatarUrl || '',
    fileName: raw?.file_name || raw?.fileName || '',
    fileSize: raw?.file_size || raw?.fileSize || 0
  }
}

/** 获取个性化配置 */
export const getUserSetting = async (): Promise<UserSetting> => {
  const raw = await http.get<any>('/user/setting')
  return {
    theme: (raw?.theme || 'light') as ThemeMode,
    fontSize: (raw?.font_size || raw?.fontSize || 'normal') as FontSizeMode,
    language: raw?.language || 'zh-CN',
    notifyMessage: raw?.notify_message ?? raw?.notifyMessage ?? true,
    notifyEmail: raw?.notify_email ?? raw?.notifyEmail ?? false,
    notifySms: raw?.notify_sms ?? raw?.notifySms ?? false,
    notifySound: raw?.notify_sound ?? raw?.notifySound ?? true
  }
}

/** 保存个性化配置 */
export const updateUserSetting = async (
  params: UserSettingUpdateParams
): Promise<UserSetting> => {
  const payload: Record<string, any> = {}
  if (params.theme !== undefined) payload.theme = params.theme
  if (params.fontSize !== undefined) payload.font_size = params.fontSize
  if (params.language !== undefined) payload.language = params.language
  if (params.notifyMessage !== undefined) payload.notify_message = params.notifyMessage
  if (params.notifyEmail !== undefined) payload.notify_email = params.notifyEmail
  if (params.notifySms !== undefined) payload.notify_sms = params.notifySms
  if (params.notifySound !== undefined) payload.notify_sound = params.notifySound
  const raw = await http.put<any>('/user/setting', payload, {
    showSuccess: true,
    successText: '配置已保存'
  })
  return {
    theme: (raw?.theme || 'light') as ThemeMode,
    fontSize: (raw?.font_size || raw?.fontSize || 'normal') as FontSizeMode,
    language: raw?.language || 'zh-CN',
    notifyMessage: raw?.notify_message ?? raw?.notifyMessage ?? true,
    notifyEmail: raw?.notify_email ?? raw?.notifyEmail ?? false,
    notifySms: raw?.notify_sms ?? raw?.notifySms ?? false,
    notifySound: raw?.notify_sound ?? raw?.notifySound ?? true
  }
}
