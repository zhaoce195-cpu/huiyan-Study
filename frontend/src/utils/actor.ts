/** 姓名后面带上身份，学生、教师和管理员都能看出是谁点的。 */
export const actorLabel = (name?: string, role?: string) => {
  const who = (name || '').trim()
  const kind = (role || '').trim()
  if (who && kind) return `${who}（${kind}）`
  return who || kind
}
