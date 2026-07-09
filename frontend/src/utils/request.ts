import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig
} from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const TOKEN_KEY = 'huiyan_token'

/* ========== 后端统一响应结构 ========== */
export interface ApiResult<T = any> {
  code: number
  msg: string
  data: T
}

export interface PageResult<T = any> {
  total: number
  page: number
  pageSize: number
  list: T[]
}

/* ========== 自定义请求选项 ========== */
export interface RequestOptions {
  /** 是否在响应错误时自动弹出 ElMessage 提示，默认 true */
  showError?: boolean
  /** 是否显示成功提示（POST/PUT/DELETE 默认 false），传 true 启用 */
  showSuccess?: boolean
  /** 成功提示文案 */
  successText?: string
  /** 是否携带 token，默认 true */
  withToken?: boolean
  /** 是否返回完整 ApiResult（含 code/msg），默认 false 仅返回 data */
  returnRaw?: boolean
}

declare module 'axios' {
  interface AxiosRequestConfig {
    requestOptions?: RequestOptions
  }
}

/* ========== 基础配置 ========== */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
const REQUEST_TIMEOUT = 30 * 1000

let isLogoutPrompting = false

const handleUnauthorized = () => {
  if (isLogoutPrompting) return
  isLogoutPrompting = true
  ElMessageBox.confirm('登录已过期，请重新登录', '会话失效', {
    confirmButtonText: '重新登录',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(() => {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('huiyan_user')
      window.location.href = '/login'
    })
    .catch(() => {})
    .finally(() => {
      isLogoutPrompting = false
    })
}

/* ========== 创建实例 ========== */
const service: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json;charset=utf-8'
  }
})

/* ========== 请求拦截 ========== */
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const opt = config.requestOptions || {}
    if (opt.withToken !== false) {
      const token = localStorage.getItem(TOKEN_KEY)
      if (token) {
        config.headers.set('Authorization', `Bearer ${token}`)
      }
    }
    return config
  },
  (error) => {
    ElMessage.error('请求发起失败')
    return Promise.reject(error)
  }
)

/* ========== 响应拦截 ========== */
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const opt: RequestOptions = response.config.requestOptions || {}
    const showError = opt.showError !== false

    // 处理二进制流（文件下载）
    const responseType = response.config.responseType
    if (responseType === 'blob' || responseType === 'arraybuffer') {
      return response.data
    }

    const res = response.data as ApiResult
    if (!res || typeof res.code === 'undefined') {
      return res
    }

    if (res.code === 0 || res.code === 200) {
      if (opt.showSuccess) {
        ElMessage.success(opt.successText || res.msg || '操作成功')
      }
      return opt.returnRaw ? res : res.data
    }

    if (res.code === 401 || res.code === 40101) {
      handleUnauthorized()
      return Promise.reject(new Error(res.msg || '会话已过期'))
    }

    if (showError) {
      ElMessage.error(res.msg || `请求失败 (${res.code})`)
    }
    return Promise.reject(new Error(res.msg || `请求失败 (${res.code})`))
  },
  (error) => {
    const opt: RequestOptions = error.config?.requestOptions || {}
    const showError = opt.showError !== false
    let msg = '网络异常，请稍后重试'
    if (error.response) {
      const status = error.response.status
      if (status === 401) {
        handleUnauthorized()
        return Promise.reject(error)
      }
      const map: Record<number, string> = {
        400: '请求参数错误 (400)',
        403: '没有访问权限 (403)',
        404: '请求资源不存在 (404)',
        405: '请求方法不允许 (405) — 通常是上游服务地址 / 端口配错',
        408: '请求超时 (408)',
        413: '上传文件过大 (413)',
        500: '服务器内部错误 (500)',
        502: '上游服务异常 (502)',
        503: '服务暂不可用 (503)',
        504: '网关超时 (504)'
      }
      msg = map[status] || `请求失败 (${status})`
      // 同时兼容 FastAPI HTTPException 的 detail 字段与项目自身 ApiResult.msg
      const respData = error.response.data as any
      const respMsg =
        respData?.msg ||
        (typeof respData?.detail === 'string'
          ? respData.detail
          : Array.isArray(respData?.detail)
            ? respData.detail.map((d: any) => d?.msg || JSON.stringify(d)).join('; ')
            : '')
      if (respMsg) msg = respMsg
    } else if (error.code === 'ECONNABORTED') {
      msg = '请求超时，请检查网络'
    } else if (error.message?.includes('Network Error')) {
      msg = '网络连接异常'
    }
    if (showError) ElMessage.error(msg)
    return Promise.reject(error)
  }
)

/* ========== 通用请求方法 ========== */
export interface HttpClient {
  get<T = any>(url: string, params?: any, options?: RequestOptions, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, options?: RequestOptions, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, options?: RequestOptions, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, params?: any, options?: RequestOptions, config?: AxiosRequestConfig): Promise<T>
  upload<T = any>(url: string, formData: FormData, options?: RequestOptions, config?: AxiosRequestConfig): Promise<T>
  download(url: string, params?: any, filename?: string, config?: AxiosRequestConfig): Promise<void>
  raw: AxiosInstance
}

const http: HttpClient = {
  get<T = any>(
    url: string,
    params?: any,
    options?: RequestOptions,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return service.request<any, T>({
      url,
      method: 'GET',
      params,
      requestOptions: options,
      ...config
    })
  },

  post<T = any>(
    url: string,
    data?: any,
    options?: RequestOptions,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return service.request<any, T>({
      url,
      method: 'POST',
      data,
      requestOptions: options,
      ...config
    })
  },

  put<T = any>(
    url: string,
    data?: any,
    options?: RequestOptions,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return service.request<any, T>({
      url,
      method: 'PUT',
      data,
      requestOptions: options,
      ...config
    })
  },

  delete<T = any>(
    url: string,
    params?: any,
    options?: RequestOptions,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return service.request<any, T>({
      url,
      method: 'DELETE',
      params,
      requestOptions: options,
      ...config
    })
  },

  upload<T = any>(
    url: string,
    formData: FormData,
    options?: RequestOptions,
    config?: AxiosRequestConfig
  ): Promise<T> {
    return service.request<any, T>({
      url,
      method: 'POST',
      data: formData,
      headers: { 'Content-Type': 'multipart/form-data' },
      requestOptions: options,
      ...config
    })
  },

  async download(
    url: string,
    params?: any,
    filename?: string,
    config?: AxiosRequestConfig
  ): Promise<void> {
    const data = await service.request<any, Blob>({
      url,
      method: 'GET',
      params,
      responseType: 'blob',
      requestOptions: { showError: true },
      ...config
    })
    const blob = new Blob([data])
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename || `download_${Date.now()}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
  },

  raw: service
}

export default http
