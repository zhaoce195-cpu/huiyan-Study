/**
 * 学习笔记正文：普通文字 + 可编辑表格。
 * 表格嵌在原 content 字段里，旧的纯文本笔记无需迁移。
 */

export interface NoteTableData {
  headers: string[]
  rows: string[][]
}

export type NoteBlock =
  | { type: 'text'; text: string }
  | { type: 'table'; table: NoteTableData }

const OPEN = '<!--note-table-->'
const CLOSE = '<!--/note-table-->'

export function emptyTable(): NoteTableData {
  return {
    headers: ['要点', '内容'],
    rows: [
      ['', ''],
      ['', '']
    ]
  }
}

function normalizeTable(raw: unknown): NoteTableData | null {
  if (!raw || typeof raw !== 'object') return null
  const obj = raw as { headers?: unknown; rows?: unknown }
  const headers = Array.isArray(obj.headers)
    ? obj.headers.map((c) => String(c ?? ''))
    : []
  const width = Math.max(headers.length, 1)
  const paddedHeaders = headers.length
    ? headers
    : Array.from({ length: width }, () => '')
  while (paddedHeaders.length < width) paddedHeaders.push('')
  const rows = Array.isArray(obj.rows)
    ? obj.rows.map((row) => {
        const cells = Array.isArray(row) ? row.map((c) => String(c ?? '')) : []
        while (cells.length < paddedHeaders.length) cells.push('')
        return cells.slice(0, paddedHeaders.length)
      })
    : []
  return {
    headers: paddedHeaders,
    rows: rows.length ? rows : [paddedHeaders.map(() => '')]
  }
}

export function parseNoteContent(content: string): NoteBlock[] {
  const src = content || ''
  if (!src.includes(OPEN)) {
    return [{ type: 'text', text: src }]
  }
  const blocks: NoteBlock[] = []
  let rest = src
  while (rest.length) {
    const start = rest.indexOf(OPEN)
    if (start < 0) {
      blocks.push({ type: 'text', text: rest })
      break
    }
    if (start > 0) {
      blocks.push({ type: 'text', text: rest.slice(0, start) })
    }
    const end = rest.indexOf(CLOSE, start + OPEN.length)
    if (end < 0) {
      blocks.push({ type: 'text', text: rest.slice(start) })
      break
    }
    const raw = rest.slice(start + OPEN.length, end).trim()
    try {
      const table = normalizeTable(JSON.parse(raw))
      blocks.push(table ? { type: 'table', table } : { type: 'text', text: raw })
    } catch {
      blocks.push({ type: 'text', text: rest.slice(start, end + CLOSE.length) })
    }
    rest = rest.slice(end + CLOSE.length)
  }
  if (!blocks.length) return [{ type: 'text', text: '' }]
  return blocks
}

export function serializeNoteContent(blocks: NoteBlock[]): string {
  return blocks
    .map((block) => {
      if (block.type === 'text') return block.text
      const payload = JSON.stringify({
        headers: block.table.headers,
        rows: block.table.rows
      })
      return `\n${OPEN}\n${payload}\n${CLOSE}\n`
    })
    .join('')
    .replace(/^\n+/, '')
    .replace(/\n+$/, '')
}

export function noteContentIsEmpty(blocks: NoteBlock[]): boolean {
  return !blocks.some((block) => {
    if (block.type === 'text') return block.text.trim().length > 0
    const cells = [...block.table.headers, ...block.table.rows.flat()]
    return cells.some((cell) => cell.trim().length > 0)
  })
}
