/**
 * 「加入实训」状态 Store
 * - 记录当前会话内已加入实训的病例 ID（本地持久化，刷新不丢）
 * - 记录每个病例的加入操作 loading 状态（仅运行时，不持久化）
 * - 病例列表页 / 详情弹窗 共享此状态，避免重复点击 / 重复请求
 */
import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'

const STORAGE_KEY = 'huiyan_joined_training_cases'

/** 从 localStorage 还原已加入集合 */
const restoreJoined = (): number[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr.filter((v) => typeof v === 'number') : []
  } catch {
    return []
  }
}

/** 持久化已加入集合 */
const persistJoined = (ids: number[]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(new Set(ids))))
  } catch {
    /* 忽略写入失败（隐私模式 / 配额超限） */
  }
}

export const useTrainingJoinStore = defineStore('trainingJoin', () => {
  /** 已加入实训的病例 ID 集合 */
  const joinedIds = ref<Set<number>>(new Set(restoreJoined()))

  /** 每个病例的 loading 状态（按 caseId 索引） */
  const loadingMap = reactive<Record<number, boolean>>({})

  /** 是否已加入 */
  const isJoined = (caseId: number) => joinedIds.value.has(caseId)

  /** 是否处于加入中（loading） */
  const isJoining = (caseId: number) => !!loadingMap[caseId]

  /** 标记加入中 */
  const setJoining = (caseId: number, val: boolean) => {
    if (val) loadingMap[caseId] = true
    else delete loadingMap[caseId]
  }

  /** 标记已加入并持久化 */
  const markJoined = (caseId: number) => {
    if (!joinedIds.value.has(caseId)) {
      joinedIds.value.add(caseId)
      // 触发响应式更新
      joinedIds.value = new Set(joinedIds.value)
      persistJoined(Array.from(joinedIds.value))
    }
  }

  /** 取消加入（如归档恢复后允许重新加入） */
  const unmarkJoined = (caseId: number) => {
    if (joinedIds.value.has(caseId)) {
      joinedIds.value.delete(caseId)
      joinedIds.value = new Set(joinedIds.value)
      persistJoined(Array.from(joinedIds.value))
    }
  }

  /** 清空（登出时调用） */
  const clear = () => {
    joinedIds.value = new Set()
    Object.keys(loadingMap).forEach((k) => delete loadingMap[Number(k)])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }

  /** 已加入的总数（仅做调试 / 展示用） */
  const joinedCount = computed(() => joinedIds.value.size)

  return {
    joinedIds,
    joinedCount,
    isJoined,
    isJoining,
    setJoining,
    markJoined,
    unmarkJoined,
    clear
  }
})
