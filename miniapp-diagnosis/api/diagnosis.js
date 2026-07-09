/**
 * CSU-EYES 智能诊断 API
 * 对接后端 /api/v1/diagnosis/*
 *  - MA 微动脉瘤检测（单图）
 *  - DR 双眼分级（左右眼各一张）
 *  - 综合诊断（单图多任务）
 */
import { upload } from './request'

export const DIAGNOSIS_TYPE_LABEL = {
  MA: '微动脉瘤检测',
  DR: 'DR 分级',
  COMPREHENSIVE: '综合诊断',
}

export const RISK_LABEL = {
  LOW: '正常',
  MEDIUM: '中危',
  HIGH: '高危',
  URGENT: '紧急',
}

export const RISK_COLOR = {
  LOW: '#16a34a',
  MEDIUM: '#d97706',
  HIGH: '#dc2626',
  URGENT: '#b91c1c',
}

/** 读取本地图片为 base64 字符串 */
export function readAsBase64(filePath) {
  return new Promise((resolve, reject) => {
    uni.getFileSystemManager().readFile({
      filePath,
      encoding: 'base64',
      success: (res) => resolve(res.data),
      fail: reject,
    })
  })
}

/** MA 微动脉瘤检测（单张） */
export function diagnoseMa(filePath, eye = 'OU', onProgress) {
  return upload('/diagnosis/ma', filePath, 'file', { eye }, { onProgress })
}

/**
 * DR 双眼分级。
 * 微信小程序 wx.uploadFile 一次仅能带一个文件，故左眼走文件、右眼走 base64 表单字段，
 * 后端 /diagnosis/dr 已兼容 right_eye_b64。
 */
export async function diagnoseDr(leftPath, rightPath, onProgress) {
  const rightB64 = await readAsBase64(rightPath)
  return upload('/diagnosis/dr', leftPath, 'left_eye', { right_eye_b64: rightB64 }, { onProgress, timeout: 180000 })
}

/** 综合诊断（单张眼底图，多任务） */
export function diagnoseComprehensive(filePath, tasks, onProgress) {
  const formData = {}
  if (tasks && tasks.length) formData.tasks = tasks.join(',')
  return upload('/diagnosis/comprehensive', filePath, 'file', formData, { onProgress, timeout: 180000 })
}
