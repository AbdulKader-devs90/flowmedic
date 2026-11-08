import type { Activity, Snapshot } from './contracts'
import { plainLabel } from './stage'
import type { FlowStage } from './stage'

export interface Milestone { id: string; stage: FlowStage; title: string; detail?: string }
// The API retains step statuses, but not log approvals, result excerpts or re-plan history.
// Keep only these missing story details for this browser session, including refreshes.
export function readStory(id: string): Milestone[] {
  try {
    return JSON.parse(sessionStorage.getItem(`flowmedic.story.${id}`) || '[]') as Milestone[]
  }
  catch {
    return []
  }

}
export function writeStory(id: string, milestones: Milestone[]): void {
  try {
    sessionStorage.setItem(`flowmedic.story.${id}`, JSON.stringify(milestones.slice(-200)))
  }
  catch { /* Checkpoint-derived milestones remain available if storage is disabled. */ }
}
export function storyMilestones(snapshot: Snapshot, remembered: Milestone[], report?: string): Milestone[] {
  const rows: Milestone[] = [{
    id: 'report',
    stage: 'Report',
    title: 'Incident report received',
    detail: report
  }]

  rows.push(...remembered.filter(row => row.id !== 'report' && row.stage !== 'Fix'))
  const triage = snapshot.triage_result
  if (triage) {
    const cause = triage.root_causes[0]
    const match = triage.kb_matches[0]
    rows.push({
      id: 'diagnosis',
      stage: 'Diagnose',
      title: `Diagnosis ready: ${triage.severity} · ${cause ? plainLabel(cause.id) : plainLabel(triage.category)}${match ? ` · ${triage.route === 'known_fix' ? 'known fix' : 'knowledge match'} ${match.doc_id}` : ''}`
    })

  }

  if (snapshot.plan || snapshot.stage === 'planner') rows.push({
    id: 'handoff',
    stage: 'Fix',
    title: 'Triage agent handed over to Planner agent'
  })

  rows.push(...remembered.filter(row => row.stage === 'Fix'))
  for (const step of snapshot.plan?.steps || []) {
    if (step.status && step.status !== 'pending') {
      const id = `step-${step.n}-${step.command_or_action}`
      if (!rows.some(row => row.id === id)) rows.push({
        id,
        stage: 'Fix',
        title: `Step ${step.n} ${step.status}: ${step.title}`
      })

    }

  }

  if (snapshot.stage === 'closed') {
    const outcome = rows.find(row => row.id === 'outcome')?.detail
    rows.push({
      id: 'closed',
      stage: 'Close',
      title: `Incident closed${outcome ? `: ${outcome}` : ''}`
    })

  }

  return rows.filter(row => row.id !== 'outcome')
}

export function collapseActivity(activity: Activity[]): Activity[] {
  const rows: Activity[] = []
  const open = new Map<string, number[]>()
  for (const row of activity) {
    if (row.event === 'node_started') {
      open.set(row.node, [...(open.get(row.node) || []), rows.length])
      rows.push(row)
    } else if (row.event === 'node_finished' && open.get(row.node)?.length) {
      const index = open.get(row.node)!.shift()!
      rows[index] = { ...row, id: rows[index].id }
    } else rows.push(row)

  }

  return rows
}
