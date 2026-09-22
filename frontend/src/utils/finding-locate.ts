/**
 * 平时练习：勾选关键征象后，在图上指出至少一处。
 * 微动脉瘤用点选，出血、渗出、新生血管用圈选，静脉串珠和 IRMA 用象限。
 * 这些标记只证明学员指出了位置，不并进金标准框的重合评分。
 */

export type LocateMethod = 'point' | 'circle' | 'quadrant'

export interface LocateTask {
  code: string
  label: string
  method: LocateMethod
  methodText: string
  action: string
  prompt: string
  color: string
  markLabel: string
}

export interface LocateRequest {
  code: string
  method: LocateMethod
  label: string
  color: string
  eye: 'OD' | 'OS' | ''
}

export type QuadCode = 'TS' | 'NS' | 'TI' | 'NI' | 'LU' | 'RU' | 'LD' | 'RD'

export const QUAD_LABEL: Record<QuadCode, string> = {
  TS: '颞上',
  NS: '鼻上',
  TI: '颞下',
  NI: '鼻下',
  LU: '左上',
  RU: '右上',
  LD: '左下',
  RD: '右下'
}

const TASKS: Record<string, LocateTask> = {
  MA: {
    code: 'MA',
    label: '微动脉瘤',
    method: 'point',
    methodText: '点选',
    action: '去点选',
    prompt: '在图上点出至少一处微动脉瘤。点一下就落一个点。',
    color: '#fadb14',
    markLabel: '微动脉瘤'
  },
  HE: {
    code: 'HE',
    label: '出血',
    method: 'circle',
    methodText: '圈选',
    action: '去圈选',
    prompt: '按住并拖动，圈出至少一处出血。',
    color: '#f53f3f',
    markLabel: '出血'
  },
  EX: {
    code: 'EX',
    label: '硬性渗出',
    method: 'circle',
    methodText: '圈选',
    action: '去圈选',
    prompt: '按住并拖动，圈出至少一处硬性渗出。',
    color: '#ff7d00',
    markLabel: '硬性渗出'
  },
  SE: {
    code: 'SE',
    label: '软性渗出',
    method: 'circle',
    methodText: '圈选',
    action: '去圈选',
    prompt: '按住并拖动，圈出至少一处软性渗出。',
    color: '#52c41a',
    markLabel: '软性渗出'
  },
  VB: {
    code: 'VB',
    label: '静脉串珠',
    method: 'quadrant',
    methodText: '标出象限',
    action: '标象限',
    prompt: '点选出现静脉串珠的象限，至少标一个。再点一次可取消。',
    color: '#b37feb',
    markLabel: '静脉串珠'
  },
  IRMA: {
    code: 'IRMA',
    label: 'IRMA',
    method: 'quadrant',
    methodText: '标出象限',
    action: '标象限',
    prompt: '点选出现视网膜内微血管异常的象限，至少标一个。再点一次可取消。',
    color: '#36cfc9',
    markLabel: 'IRMA'
  },
  NV: {
    code: 'NV',
    label: '新生血管',
    method: 'circle',
    methodText: '圈选',
    action: '去圈选',
    prompt: '按住并拖动，圈出至少一处新生血管。',
    color: '#1677ff',
    markLabel: '新生血管'
  }
}

export const tasksForFindings = (findings: unknown): LocateTask[] => {
  const list = Array.isArray(findings) ? findings : []
  const out: LocateTask[] = []
  for (const code of list) {
    const task = TASKS[String(code)]
    if (task) out.push(task)
  }
  return out
}

export const remarkMatches = (remark: string | undefined, code: string) => {
  const text = remark || ''
  return text === code || text.startsWith(`${code}:`)
}

export const quadAt = (
  x: number,
  y: number,
  width: number,
  height: number,
  eye: string
): QuadCode => {
  const right = x >= width / 2
  const lower = y >= height / 2
  if (eye === 'OD') {
    if (!lower && right) return 'NS'
    if (!lower && !right) return 'TS'
    if (lower && right) return 'NI'
    return 'TI'
  }
  if (eye === 'OS') {
    if (!lower && !right) return 'NS'
    if (!lower && right) return 'TS'
    if (lower && !right) return 'NI'
    return 'TI'
  }
  if (!lower && !right) return 'LU'
  if (!lower && right) return 'RU'
  if (lower && !right) return 'LD'
  return 'RD'
}

export const quadBounds = (
  code: QuadCode,
  width: number,
  height: number,
  eye: string
): { x: number; y: number; w: number; h: number } => {
  const midX = width / 2
  const midY = height / 2
  const top = code === 'TS' || code === 'NS' || code === 'LU' || code === 'RU'
  // 右眼视盘靠画面右侧，鼻侧在右、颞侧在左。左眼相反。
  let left = code === 'LU' || code === 'LD'
  if (code === 'RU' || code === 'RD') left = false
  if (code === 'TS' || code === 'TI') left = eye !== 'OS'
  if (code === 'NS' || code === 'NI') left = eye === 'OS'
  return {
    x: left ? 0 : midX,
    y: top ? 0 : midY,
    w: midX,
    h: midY
  }
}

/** 右眼视盘在画面右侧，鼻侧为右；左眼相反。眼别未知时用左上、右上。 */
export const quadrantCodes = (eye: string): QuadCode[] => {
  if (eye === 'OD' || eye === 'OS') return ['TS', 'NS', 'TI', 'NI']
  return ['LU', 'RU', 'LD', 'RD']
}
