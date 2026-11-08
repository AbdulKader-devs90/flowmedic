import type { Environment, Platform, KnowledgeEntry, Incident, KnowledgeDoc, Resume, Scenario, Snapshot, Topology } from './contracts'
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try { const body: unknown = await response.json(); if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') detail = body.detail } catch { /* Keep the safe status message for non-JSON errors. */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}
export const api = {
  platforms: () => request<Platform[]>('/platforms'),
  environments: () => request<Environment[]>('/environments'),
  knowledgeIndex: (q = '') => request<KnowledgeEntry[]>(`/knowledge?q=${encodeURIComponent(q)}`),
  scenarios: () => request<Scenario[]>('/scenarios'),
  incidents: () => request<Incident[]>('/incidents'),
  snapshot: (id: string) => request<Snapshot>(`/incidents/${encodeURIComponent(id)}`),
  create: (body: { message?: string; environment?: string; scenario_id?: string }) => request<{ incident_id: string }>('/incidents', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  resume: (id: string, body: Resume) => request(`/incidents/${encodeURIComponent(id)}/resume`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  upload: (id: string, file: File) => { const body = new FormData(); body.append('file', new Blob([file], { type:'text/plain' }), file.name); return request(`/incidents/${encodeURIComponent(id)}/logs`, { method: 'POST', body }) },
  topology: (environment: string, id?: string) => request<Topology>(`/environments/${encodeURIComponent(environment)}/topology${id ? `?incident_id=${encodeURIComponent(id)}` : ''}`),
  knowledge: (id: string) => request<KnowledgeDoc>(`/knowledge/${encodeURIComponent(id)}`),
}
