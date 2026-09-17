/** 登录后未读公告：只在用户点「我已知晓」或「查看」时记已读。 */

export const PENDING_LOGIN_NOTICE_KEY = 'huiyan:pendingLoginNotice'
export const NOTICE_SHOWN_PREFIX = 'huiyan:noticeShown:'

type Listener = () => void
const listeners = new Set<Listener>()

export const isNoticeRead = (n: { isRead?: boolean; read?: boolean } | null | undefined) =>
  n?.isRead === true || n?.read === true

export const subscribeLoginNotice = (fn: Listener) => {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

const notifyListeners = () => {
  listeners.forEach((fn) => {
    try {
      fn()
    } catch {
      /* ignore */
    }
  })
}

export const bindLoginNoticeShower = (fn: Listener | null) => {
  if (fn) listeners.add(fn)
}

export const triggerLoginNoticePopup = () => {
  notifyListeners()
}

export const requestLoginNoticePopup = () => {
  try {
    sessionStorage.setItem(PENDING_LOGIN_NOTICE_KEY, '1')
    const keys: string[] = []
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i)
      if (k && k.startsWith(NOTICE_SHOWN_PREFIX)) keys.push(k)
    }
    keys.forEach((k) => sessionStorage.removeItem(k))
  } catch {
    /* ignore */
  }
  notifyListeners()
}

export const hasPendingLoginNotice = () => {
  try {
    return sessionStorage.getItem(PENDING_LOGIN_NOTICE_KEY) === '1'
  } catch {
    return false
  }
}

export const clearPendingLoginNotice = () => {
  try {
    sessionStorage.removeItem(PENDING_LOGIN_NOTICE_KEY)
  } catch {
    /* ignore */
  }
}

export const clearLoginNoticeFlags = () => {
  try {
    sessionStorage.removeItem(PENDING_LOGIN_NOTICE_KEY)
    const keys: string[] = []
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i)
      if (k && k.startsWith(NOTICE_SHOWN_PREFIX)) keys.push(k)
    }
    keys.forEach((k) => sessionStorage.removeItem(k))
  } catch {
    /* ignore */
  }
}

/** 登录后落地页带上 noticePopup，避免 /training 重定向丢掉触发条件 */
export const withLoginNoticeQuery = (
  path: string,
  extra: Record<string, string> = {}
) => {
  const clean = path === '/training' || path === '/training/' ? '/training/cases' : path
  return { path: clean, query: { noticePopup: '1', ...extra } }
}
