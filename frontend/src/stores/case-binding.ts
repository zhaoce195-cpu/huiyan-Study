/**
 * 病例「手机号绑定」共享 Store —— 跨列表同步桥
 * - 后端单源：/screening/tasks。两个列表（病例检索 / 分析任务队列）数据本就同源；
 * - 本 store 仅作为「就近覆盖层」，绑定成功后立即写入此处，列表刷新前也能让另一个 tab 表现一致。
 * - 关联键优先 caseId（数字主键），同时按 patientId 维护一份索引兜底（与需求文档「以 patientId 为关联键」一致）。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

interface BindingRow {
  phone: string
  /** 标记是否已通过手机号匹配到 patient 用户账号；后端 fetch 后会以 server 字段为准覆盖 */
  bound: boolean
  /** 写入时间戳，便于诊断 */
  ts: number
}

const STORAGE_KEY = 'huiyan_case_phone_overlay'

const loadFromStorage = (): Record<string, BindingRow> => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, BindingRow>
  } catch {
    return {}
  }
}

const saveToStorage = (
  byCaseId: Record<string, BindingRow>,
  byPatientId: Record<string, BindingRow>,
) => {
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ byCaseId, byPatientId }),
    )
  } catch {
    /* ignore quota */
  }
}

const restore = (): {
  byCaseId: Record<string, BindingRow>
  byPatientId: Record<string, BindingRow>
} => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return { byCaseId: {}, byPatientId: {} }
    const parsed = JSON.parse(raw)
    return {
      byCaseId: parsed?.byCaseId || {},
      byPatientId: parsed?.byPatientId || {},
    }
  } catch {
    return { byCaseId: {}, byPatientId: {} }
  }
}

export const useCaseBindingStore = defineStore('case-binding', () => {
  const restored = restore()
  const byCaseId = ref<Record<string, BindingRow>>(restored.byCaseId)
  const byPatientId = ref<Record<string, BindingRow>>(restored.byPatientId)
  void loadFromStorage // keep tree-shaking happy

  /** 绑定成功后调用 —— 同步两份索引 */
  const setBinding = (
    keys: { caseId?: number | string | null; patientId?: string | null },
    phone: string,
    bound = true,
  ) => {
    const row: BindingRow = {
      phone: (phone || '').trim(),
      bound: !!bound,
      ts: Date.now(),
    }
    if (keys.caseId !== undefined && keys.caseId !== null && keys.caseId !== '') {
      byCaseId.value[String(keys.caseId)] = row
    }
    if (keys.patientId) {
      byPatientId.value[keys.patientId] = row
    }
    saveToStorage(byCaseId.value, byPatientId.value)
  }

  /** 清除绑定（绑定弹窗输入空字符串触发） */
  const clearBinding = (keys: {
    caseId?: number | string | null
    patientId?: string | null
  }) => {
    if (keys.caseId !== undefined && keys.caseId !== null && keys.caseId !== '') {
      delete byCaseId.value[String(keys.caseId)]
    }
    if (keys.patientId) {
      delete byPatientId.value[keys.patientId]
    }
    saveToStorage(byCaseId.value, byPatientId.value)
  }

  /**
   * 在拉到的列表行上覆盖最近一次绑定结果。
   * 仅当后端字段为空、而 overlay 有值时覆盖；
   * 如果后端已经返回了较新的字段值，则以后端为准（兼容多端编辑）。
   */
  const applyOverlay = <
    T extends {
      caseId?: number | string | null
      patientId?: string | null
      patientPhone?: string | null
      patientBound?: boolean
    },
  >(
    row: T,
  ): T => {
    const fromCase = row.caseId
      ? byCaseId.value[String(row.caseId)]
      : undefined
    const fromPid = row.patientId
      ? byPatientId.value[row.patientId]
      : undefined
    const overlay = fromCase || fromPid
    if (!overlay) return row
    // 后端已经返回了同样 / 更新的手机号 → 不覆盖（双向最终一致）
    if ((row.patientPhone || '') === overlay.phone) return row
    return {
      ...row,
      patientPhone: overlay.phone,
      patientBound: overlay.bound || !!row.patientBound,
    }
  }

  /** 清空（登出 / 切账号时调用） */
  const clear = () => {
    byCaseId.value = {}
    byPatientId.value = {}
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }

  return {
    byCaseId,
    byPatientId,
    setBinding,
    clearBinding,
    applyOverlay,
    clear,
  }
})
