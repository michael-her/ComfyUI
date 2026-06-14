const SJSX_NODE_PREFIX = 'Sjsx_'

export function isSjsxNodeType(type: string | null | undefined): boolean {
  const value = (type ?? '').trim()
  return value.startsWith(SJSX_NODE_PREFIX)
}

export function isSjsxCategory(category: string | null | undefined): boolean {
  const value = (category ?? '').trim()
  return value.startsWith('sjsx/') || value.startsWith('sjsx\\')
}

export function isSjsxNodeDef(
  def: { name?: string; category?: string } | null | undefined
): boolean {
  if (!def) return false
  return isSjsxNodeType(def.name) || isSjsxCategory(def.category)
}

/** React Native / system tag from Comfy node type or node def. */
export function getSjsxTagName(
  type: string | null | undefined,
  def?: { name?: string; display_name?: string } | null
): string {
  const value = (type ?? '').trim()
  if (value.startsWith(SJSX_NODE_PREFIX)) {
    return value.slice(SJSX_NODE_PREFIX.length)
  }
  if (def?.name?.startsWith(SJSX_NODE_PREFIX)) {
    return def.name.slice(SJSX_NODE_PREFIX.length)
  }
  if (def?.display_name?.trim()) {
    return def.display_name.trim()
  }
  return value || 'Node'
}
