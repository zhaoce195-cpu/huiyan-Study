/**
 * 数据脱敏 composable（前端显示层兜底 + 角色感知）
 *
 * 后端已按角色脱敏返回数据，本工具用于：
 *   1. 教学分享 / 学员端页面的二次显示保险
 *   2. ShareDialog 等弹窗内对脱敏结果做实时预览
 *   3. 任意需要按当前用户角色快速决定显隐的位置
 *
 * 三档策略（与后端 mask_phone_by_role 对齐）：
 *   - admin            → 原样
 *   - doctor (TEACHER) → 部分（手机/身份证脱敏，姓名保留）
 *   - trainee/patient  → 隐藏（手机隐藏 / 姓名首字+*）
 */
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

export type MaskLevel = 'full' | 'partial' | 'hidden'

const _maskPhone = (raw?: string | null): string => {
  const s = (raw || '').trim()
  if (!s) return ''
  // 11 位中国手机号
  if (/^1\d{10}$/.test(s)) return `${s.slice(0, 3)}****${s.slice(7)}`
  // 其它情况：保留前 3 + 后 4
  if (s.length >= 7) return `${s.slice(0, 3)}****${s.slice(-4)}`
  return '***'
}

const _maskName = (raw?: string | null): string => {
  const s = (raw || '').trim()
  if (!s) return ''
  if (s.length === 1) return s
  if (s.length === 2) return `${s[0]}*`
  // 3 个字以上：保留首尾
  return `${s[0]}${'*'.repeat(s.length - 2)}${s[s.length - 1]}`
}

const _maskIdCard = (raw?: string | null): string => {
  const s = (raw || '').trim()
  if (!s) return ''
  if (s.length <= 10) return '*'.repeat(s.length)
  return `${s.slice(0, 6)}${'*'.repeat(s.length - 10)}${s.slice(-4)}`
}

const _hide = (): string => '***'

export const useDataMask = () => {
  const userStore = useUserStore()
  const role = computed(() => userStore.role || '')

  /** 当前角色对应的脱敏档位 */
  const level = computed<MaskLevel>(() => {
    const r = role.value
    if (r === 'admin') return 'full'
    if (r === 'doctor') return 'partial'
    return 'hidden'
  })

  /** 手机号 —— 按角色档位返回 */
  const maskPhone = (raw?: string | null): string => {
    if (!raw) return ''
    if (level.value === 'full') return raw
    if (level.value === 'partial') return _maskPhone(raw)
    return _hide()
  }

  /** 姓名 —— 按角色档位返回 */
  const maskName = (raw?: string | null): string => {
    if (!raw) return ''
    if (level.value === 'full') return raw
    if (level.value === 'partial') return raw // 医生看完整姓名
    return _maskName(raw)
  }

  /** 身份证 —— 按角色档位返回 */
  const maskIdCard = (raw?: string | null): string => {
    if (!raw) return ''
    if (level.value === 'full') return raw
    if (level.value === 'partial') return _maskIdCard(raw)
    return _hide()
  }

  /**
   * 对象级脱敏：传入 obj + 字段映射，返回脱敏后的副本
   * @example
   *   const masked = byRole(record, { phone: 'patientPhone', name: 'patientName' })
   */
  const byRole = <T extends Record<string, any>>(
    obj: T,
    fields: { phone?: keyof T; name?: keyof T; idCard?: keyof T },
  ): T => {
    if (!obj) return obj
    const out: any = { ...obj }
    if (fields.phone) out[fields.phone] = maskPhone(obj[fields.phone] as string)
    if (fields.name) out[fields.name] = maskName(obj[fields.name] as string)
    if (fields.idCard) out[fields.idCard] = maskIdCard(obj[fields.idCard] as string)
    return out as T
  }

  return {
    role,
    level,
    maskPhone,
    maskName,
    maskIdCard,
    byRole,
  }
}

/** 静态调用版本（不依赖角色，always partial） */
export const maskPhoneStatic = _maskPhone
export const maskNameStatic = _maskName
export const maskIdCardStatic = _maskIdCard
