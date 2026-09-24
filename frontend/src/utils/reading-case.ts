/** 阅片工作台上次打开的病例。侧栏不带参数时，用它把 caseId 补回地址。 */
export const LAST_READING_CASE_KEY = 'huiyan.reading.lastCaseId'

export function rememberedReadingCaseId(): number {
  try {
    const id = Number(sessionStorage.getItem(LAST_READING_CASE_KEY) || 0)
    return id > 0 ? id : 0
  } catch {
    return 0
  }
}

export function rememberReadingCaseId(id: number) {
  if (!(id > 0)) return
  try {
    sessionStorage.setItem(LAST_READING_CASE_KEY, String(id))
  } catch {
    /* 写不进去时，只能从病例库点进某一例 */
  }
}
