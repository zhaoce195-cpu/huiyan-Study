/**
 * 统一请求层
 * ----------------------------------------------------------------
 * - 自动注入 Authorization: Bearer <token>
 * - 解包后端统一响应 { code, msg, data }，code===0 视为成功
 * - 401 自动清登录态并跳回登录页
 * - 提供 get / post / put / del / upload 方法
 */

import { BASE_URL, TOKEN_KEY, USER_KEY } from '../utils/config'

let redirecting = false

function gotoLogin() {
  uni.removeStorageSync(TOKEN_KEY)
  uni.removeStorageSync(USER_KEY)
  if (redirecting) return
  redirecting = true
  uni.reLaunch({
    url: '/pages/login/login',
    complete: () => {
      setTimeout(() => (redirecting = false), 800)
    },
  })
}

/**
 * 基础请求
 * @param {string} url      以 / 开头的业务路径，如 /auth/login
 * @param {object} options  { method, data, header, withToken, showError, loading }
 */
export function request(url, options = {}) {
  const {
    method = 'GET',
    data = {},
    header = {},
    withToken = true,
    showError = true,
    loading = false,
    timeout = 60000,
  } = options

  if (loading) uni.showLoading({ title: '加载中', mask: true })

  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync(TOKEN_KEY)
    uni.request({
      url: `${BASE_URL}${url}`,
      method,
      data,
      timeout,
      header: {
        'Content-Type': 'application/json',
        ...(withToken && token ? { Authorization: `Bearer ${token}` } : {}),
        ...header,
      },
      success: (res) => {
        const body = res.data || {}
        // HTTP 401：登录失效
        if (res.statusCode === 401 || body.code === 401) {
          if (showError) uni.showToast({ title: body.msg || '登录已失效', icon: 'none' })
          gotoLogin()
          reject(body)
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 0) {
          resolve(body.data)
          return
        }
        // 业务错误
        const msg = body.msg || `请求失败(${res.statusCode})`
        if (showError) uni.showToast({ title: msg, icon: 'none' })
        reject(body && body.code !== undefined ? body : { code: res.statusCode, msg })
      },
      fail: (err) => {
        if (showError) {
          uni.showToast({ title: '网络异常，请检查后端服务', icon: 'none' })
        }
        reject(err)
      },
      complete: () => {
        if (loading) uni.hideLoading()
      },
    })
  })
}

export const get = (url, data, opts = {}) => request(url, { ...opts, method: 'GET', data })
export const post = (url, data, opts = {}) => request(url, { ...opts, method: 'POST', data })
export const put = (url, data, opts = {}) => request(url, { ...opts, method: 'PUT', data })
export const del = (url, data, opts = {}) => request(url, { ...opts, method: 'DELETE', data })

/**
 * 文件上传（multipart/form-data）
 * @param {string} url       业务路径
 * @param {string} filePath  本地临时文件路径（uni.chooseMedia 拿到的 tempFilePath）
 * @param {string} name      表单字段名（如 file / left_eye）
 * @param {object} formData   其它表单字段
 * @param {object} opts       { onProgress, timeout, showError }
 */
export function upload(url, filePath, name, formData = {}, opts = {}) {
  const { onProgress, timeout = 120000, showError = true } = opts
  if (opts.loading) uni.showLoading({ title: '上传中', mask: true })

  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync(TOKEN_KEY)
    const task = uni.uploadFile({
      url: `${BASE_URL}${url}`,
      filePath,
      name,
      formData,
      timeout,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (res) => {
        let body = {}
        try {
          body = JSON.parse(res.data)
        } catch (e) {
          body = {}
        }
        if (res.statusCode === 401 || body.code === 401) {
          gotoLogin()
          reject(body)
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 0) {
          resolve(body.data)
          return
        }
        const msg = body.msg || `上传失败(${res.statusCode})`
        if (showError) uni.showToast({ title: msg, icon: 'none' })
        reject(body && body.code !== undefined ? body : { code: res.statusCode, msg })
      },
      fail: (err) => {
        if (showError) uni.showToast({ title: '上传失败，请重试', icon: 'none' })
        reject(err)
      },
      complete: () => {
        if (opts.loading) uni.hideLoading()
      },
    })
    if (onProgress && task && task.onProgressUpdate) {
      task.onProgressUpdate((e) => onProgress(e.progress))
    }
  })
}

export default { request, get, post, put, del, upload }
