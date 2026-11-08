import type { Activity, Incident, Snapshot } from './contracts'
import { humanize } from './contracts'

export const stages = ['Report', 'Logs', 'Diagnose', 'Fix', 'Close'] as const
export type FlowStage = typeof stages[number]
export const stageDescriptions: Record<FlowStage, string> = {
  Report: 'Describe the incident and confirm the environment.',
  Logs: 'Approve read-only access to the relevant log export.',
  Diagnose: 'The Triage agent assesses root causes using logs and knowledge.',
  Fix: 'The Planner agent guides checks and changes that you run yourself.',
  Close: 'Review the outcome and decide whether to save the incident.',
}
const actions: Record<string, string> = {
  intake: 'reading the incident report',
  load_context: 'reading the environment context',
  request_log_access: 'asking for log access',
  evidence: 'searching the logs',
  grep: 'searching the logs',
  kb_search: 'searching the knowledge base',
  retrieve: 'searching the knowledge base',
  research: 'checking vendor documentation',
  classify: 'assessing root causes',
  synthesize: 'writing the diagnosis',
  build_plan: 'building the resolution plan',
  make_plan: 'building the resolution plan',
  plan: 'building the resolution plan',
  present_step: 'preparing your next step',
  execute: 'preparing your next step',
  interpret: 'reviewing your result',
  clarify: 'reviewing the environment details',
  approve_save: 'preparing the incident record',
  close: 'preparing the incident record',
  record: 'preparing the incident record',
}

export function plainLabel(value: string): string {
  const known: Record<string, string> = {
    kb_search: 'Knowledge search',
    retrieve: 'Knowledge search',
    grep: 'Search logs',
    tail: 'Read log excerpt',
    evidence: 'Search logs',
    read_environment_memory: 'Read environment memory',
    read_memory: 'Read environment memory',
    memory_read: 'Read environment memory',
    load_context: 'Read environment memory',
    db_pool_exhaustion: 'JDBC pool exhausted',
    jdbc_pool_exhaustion: 'JDBC pool exhausted',
  }

  return (known[value] || humanize(value)).replace(/\b(jdbc|is|um|db|sid|api|tx)\b/gi, word => word.toUpperCase())
}

export function planProgress(snapshot?: Snapshot): string | null {
  const steps = snapshot?.plan?.steps
  if (!steps?.length) return null
  const question = snapshot?.pending_interrupt?.payload
  const n = question && 'type' in question && question.type === 'step'
    ? question.n : (steps.find(step => !step.status || step.status === 'pending')?.n ?? steps.at(-1)!.n)
  return `step ${n} of ${steps.length}`
}

export function deriveStage(snapshot?: Snapshot, liveNode?: string | null, activity: Activity[] = []) {
  const question = snapshot?.pending_interrupt
  let stage: FlowStage = 'Report'
  if (snapshot?.stage === 'closed' || question?.type === 'approve_save') stage = 'Close'
  else if (snapshot?.plan || snapshot?.stage === 'planner' || snapshot?.triage_result) stage = 'Fix'
  else if (question?.type === 'log_access' || liveNode === 'request_log_access') stage = 'Logs'
  else if (question?.type === 'context') stage = 'Report'
  else if (snapshot?.evidence.length || activity.some(row => ['evidence', 'grep', 'classify', 'synthesize', 'kb_search'].includes(row.node)) || ['evidence', 'grep', 'classify', 'synthesize', 'kb_search'].includes(liveNode || '') || question?.type === 'evidence') stage = 'Diagnose'
  const agent = snapshot?.stage === 'closed' ? null : ['Fix', 'Close'].includes(stage) ? 'Planner agent' : 'Triage agent'
  const progress = planProgress(snapshot)
  const waiting: Record<string, string> = {
    context: 'answer one question',
    evidence: 'provide diagnostic evidence',
    log_access: 'approve read-only log access',
    step: `run ${progress || 'the next step'} and report the result`,
    approve_save: 'decide whether to save this incident',
  }

  const status = question ? `Waiting for you: ${waiting[question.type] || 'review the request'}`
    : !agent ? 'Incident closed'
      : `${agent} is ${actions[liveNode || ''] || (stage === 'Fix' ? 'building the resolution plan' : stage === 'Close' ? 'preparing the incident record' : stage === 'Diagnose' ? 'assessing root causes' : 'reading the incident report')}`
  return {
    stage,
    agent,
    status,
    progress
  }

}

export function incidentStageLabel(incident: Incident, snapshot?: Snapshot, liveNode?: string | null): string {
  if (snapshot?.pending_interrupt) return 'Waiting for you'
  if ((snapshot?.stage || incident.stage) === 'closed') return 'Closed'
  if ((snapshot?.stage || incident.stage) === 'planner') return `Fixing${planProgress(snapshot) ? ` · ${planProgress(snapshot)}` : ''}`
  const stage = deriveStage(snapshot, liveNode).stage
  return stage === 'Report' && snapshot ? 'Reporting' : stage === 'Logs' ? 'Reviewing log access' : 'Diagnosing'
}

export function planSignature(snapshot?: Snapshot): string {
  return JSON.stringify(snapshot?.plan?.steps.map(({ n, title, command_or_action, where }) => ({
    n,
    title,
    command_or_action,
    where
  })) || [])

}
