export const trustHints = {
  verified: 'From a reviewed incident or runbook in your knowledge base.',
  cited: 'From vendor documentation found by search; check before use.',
  model: "From the model's own knowledge; lowest trust.",
}
export const kindHints = { read: 'Only reads or inspects; safe.', change: 'Changes system state; review risk and rollback first.', destructive: 'Can cause data loss or an outage.' }
export const confidenceHint = 'How strongly the evidence supports this assessment.'
export function displayPath(value: string, root?: string): string {
  const normalized = value.replaceAll('\\', '/')
  if (!root) return normalized
  return normalized.replaceAll(`${root.replaceAll('\\', '/').replace(/\/$/, '')}/`, '')
}
export function uniqueNotes(value: string): string {
  return [...new Set(value.split(/(?<=[.!?])\s+|\n+/).map(part => part.trim()).filter(Boolean))].join(' ')
}
