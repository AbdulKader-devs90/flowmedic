export type Stage = 'triage' | 'planner' | 'closed'
export interface Scenario { id: string; title: string; platform: string | null; environment: string | null }
export interface Incident { id: string; title: string; severity: string | null; category: string | null; stage: Stage; environment: string | null; updated_at: string }
export interface Evidence { source_file: string; line_no: number; text: string; signature: string | null }
export interface PlanStep { n: number; title: string; kind: 'read' | 'change' | 'destructive'; command_or_action: string; where: string; expected_output: string; decision_rule: string; risk: string | null; rollback: string | null; source: 'verified' | 'cited' | 'model'; source_ref: string | null; status?: 'pending' | 'done' | 'skipped' | 'failed' }
export interface TriageResult { category: string; severity: string; route: 'known_fix' | 'similar' | 'new_issue' | 'clarify'; root_causes: { id: string; confidence: number; evidence_refs: string[] }[]; kb_matches: { doc_id: string; title: string; score: number }[]; related_components: string[]; affected_component: string | null; confidence: number; notes: string; first_steps: PlanStep[] }
export interface Plan { steps: PlanStep[] }
export type Question = { kind: 'context' | 'evidence'; slots: string[]; allowed_values?: Record<string, string[]>; why: string } | { kind: 'log_access'; folder: string; start_time: string | null; end_time: string | null; why: string } | ({ type: 'step' } & PlanStep) | { type: 'approve_save'; record: Record<string, unknown>; outcome: string }
export interface PendingInterrupt { type: string; payload: Question }
export interface Snapshot { id: string; context: Record<string, string | null>; stage: Stage; triage_result: TriageResult | null; plan: Plan | null; flags: string[]; evidence: Evidence[]; pending_interrupt: PendingInterrupt | null }
export interface TopologyNode { id: string; type: string; name?: string; label?: string; host?: string; status: 'quiet' | 'affected' | 'check_next' | 'checked_ok' | 'checked_issue'; order?: number }
export interface Topology { nodes: TopologyNode[]; edges: { from: string; to: string; type?: string; label?: string }[] }
export interface KnowledgeDoc { id: string; title: string; type: string; body: string; front_matter: Record<string, unknown> }
export type Resume = { kind: 'answer' | 'approve_logs' | 'step_result' | 'approve_save' | 'retriage'; payload: Record<string, unknown> | boolean }
export interface Activity { id: number; event: string; node: string; summary: string; target?: string; time: string }
export interface StreamEvents { node_started: { node?: string; summary?: string }; node_finished: { node: string; summary: string }; tool_called: { tool?: string; target?: string; summary?: string }; tool_result: { tool?: string; target?: string; summary?: string }; triage_result: TriageResult; plan_updated: Plan; interrupt: Question; error: { message: string; type?: string }; done: { incident_id: string } }
export type StreamName = keyof StreamEvents
export const streamNames: StreamName[] = ['node_started', 'node_finished', 'tool_called', 'tool_result', 'triage_result', 'plan_updated', 'interrupt', 'error', 'done']
export const questionType = (question: Question): string => 'kind' in question ? question.kind : question.type
export const humanize = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/, c => c.toUpperCase())
