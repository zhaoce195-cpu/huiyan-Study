/** 每例教学要点的固定提纲。空项不写入。 */

export const TEACHING_OUTLINE = [
  {
    key: 'diagnosis',
    label: '主要诊断',
    placeholder: '这例的主要诊断'
  },
  {
    key: 'grade',
    label: '分级依据',
    placeholder: '分级靠哪些可见征象'
  },
  {
    key: 'missed',
    label: '容易漏掉的征象',
    placeholder: '阅片时容易漏看的征象'
  },
  {
    key: 'differential',
    label: '鉴别诊断',
    placeholder: '需要和哪些情况分开，依据是什么'
  },
  {
    key: 'management',
    label: '处置思路',
    placeholder: '下一步怎么处理、何时转诊'
  },
  {
    key: 'guideline',
    label: '相关指南要点',
    placeholder: '和本例相关的指南或共识要点'
  }
] as const

export type TeachingSectionKey = (typeof TEACHING_OUTLINE)[number]['key']

const LABEL_TO_KEY = new Map(TEACHING_OUTLINE.map((item) => [item.label, item.key]))

export function emptyTeachingSections(): Record<TeachingSectionKey, string> {
  return {
    diagnosis: '',
    grade: '',
    missed: '',
    differential: '',
    management: '',
    guideline: ''
  }
}

function append(prev: string, next: string) {
  const bit = next.trim()
  if (!bit) return prev
  return prev ? `${prev}\n${bit}` : bit
}

export function parseTeachingPoints(raw: string) {
  const sections = emptyTeachingSections()
  const legacy: string[] = []
  let current: TeachingSectionKey | null = null
  for (const line of (raw || '').split(/\r?\n/)) {
    const matched = line.match(/^(.+?)[：:]\s*(.*)$/)
    const key = matched ? LABEL_TO_KEY.get(matched[1].trim()) : undefined
    if (key) {
      current = key
      sections[key] = append(sections[key], matched?.[2] || '')
    } else if (current) {
      sections[current] = append(sections[current], line)
    } else if (line.trim()) {
      legacy.push(line.trim())
    }
  }
  return {
    sections,
    legacy: legacy.join('\n'),
    items: TEACHING_OUTLINE.map((item) => ({
      label: item.label,
      text: sections[item.key]
    })).filter((item) => item.text)
  }
}

export function serializeTeachingPoints(sections: Record<string, string>) {
  return TEACHING_OUTLINE.map((item) => {
    const text = (sections[item.key] || '').trim()
    return text ? `${item.label}：${text}` : ''
  })
    .filter(Boolean)
    .join('\n')
}
