/**
 * 审核操作 composable
 * - approve: 弹 prompt（备注选填）→ 调 review API（accept=true）
 * - reject:  弹 prompt（驳回理由必填）→ 调 review API（accept=false）
 *
 * 适用：管理后台「机构申请审核」「教学病例审核」等流程。
 *
 * 使用：
 *   const review = useReviewActions({
 *     reviewFn: (id, payload) => OrganizationApi.reviewApplication(id, payload),
 *     onAfter: () => fetchList(),
 *   })
 *   review.approve(row.id, `${row.applicantName} → ${row.organizationName}`)
 *   review.reject(row.id, `${row.applicantName} → ${row.organizationName}`)
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

export interface ReviewPayload {
  accept: boolean
  comment: string
}

export interface UseReviewActionsOptions<T = unknown> {
  /** 审核 API：传 (id, { accept, comment }) → Promise */
  reviewFn: (id: number, payload: ReviewPayload) => Promise<T>
  /** 审核成功后的钩子（通常用来刷新列表） */
  onAfter?: () => void | Promise<void>
  /** 自定义文案 */
  approveTitle?: string
  rejectTitle?: string
  approveButton?: string
  rejectButton?: string
}

export const useReviewActions = <T = unknown>(opts: UseReviewActionsOptions<T>) => {
  const {
    reviewFn,
    onAfter,
    approveTitle = '审核通过',
    rejectTitle = '审核驳回',
    approveButton = '通过',
    rejectButton = '驳回',
  } = opts

  /** 当前正在审核的 id（用于 loading 态） */
  const reviewing = ref<number | null>(null)

  const approve = async (id: number, subject = '') => {
    let comment = ''
    try {
      const result = await ElMessageBox.prompt(
        `确认通过${subject ? `「${subject}」` : ''}？\n（备注可选）`,
        approveTitle,
        {
          confirmButtonText: approveButton,
          cancelButtonText: '取消',
          inputType: 'textarea',
          inputPlaceholder: '审核备注（选填）',
          inputValue: '',
          showInput: true,
          type: 'success',
        },
      )
      comment = (result.value || '').trim()
    } catch {
      return
    }
    reviewing.value = id
    try {
      await reviewFn(id, { accept: true, comment })
      ElMessage.success('已通过')
      await onAfter?.()
    } catch {
      /* 已弹错误 */
    } finally {
      reviewing.value = null
    }
  }

  const reject = async (id: number, subject = '') => {
    let comment = ''
    try {
      const result = await ElMessageBox.prompt(
        `驳回${subject ? `「${subject}」` : ''}，请填写驳回理由：`,
        rejectTitle,
        {
          confirmButtonText: rejectButton,
          cancelButtonText: '取消',
          inputType: 'textarea',
          inputPlaceholder: '驳回理由（必填）',
          inputValidator: (v: string) => !!v?.trim() || '驳回必须填写理由',
          type: 'warning',
        },
      )
      comment = (result.value || '').trim()
    } catch {
      return
    }
    reviewing.value = id
    try {
      await reviewFn(id, { accept: false, comment })
      ElMessage.success('已驳回')
      await onAfter?.()
    } catch {
      /* 已弹错误 */
    } finally {
      reviewing.value = null
    }
  }

  return { reviewing, approve, reject }
}
