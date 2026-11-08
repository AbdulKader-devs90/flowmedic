import { useEffect, useId, useRef } from 'react'
import { useReducedMotion } from 'framer-motion'
import type { Snapshot, PlanStep } from '@/lib/contracts'
import type { EvidenceTarget } from './evidence-drawer'
import { SourceBadge, TopologyMap, TriageCard } from './diagnosis'
import { StepDetails } from './step-details'
import { Button } from './ui/button'

export type InspectorTab = 'Diagnosis' | 'Plan' | 'Topology' | 'Evidence'
interface TabProps { snapshot?: Snapshot; open: (target: EvidenceTarget) => void }
const tabs: InspectorTab[] = ['Diagnosis', 'Plan', 'Topology', 'Evidence']
const descriptions: Record<InspectorTab, string> = {
  Diagnosis: 'What the Triage agent concluded and why.',
  Plan: "The Planner agent's step-by-step fix. You act in the Your turn card.",
  Topology: "Your environment's dependencies. Highlighted nodes are affected or next to check.",
  Evidence: 'Log lines and knowledge documents behind each claim.',
}

export function DiagnosisTab({ snapshot, open }: TabProps) {
  return snapshot?.triage_result
    ? <TriageCard
      result={snapshot.triage_result}
      displayRoot={snapshot.display_root}
      compact={false}
      open={open} />
    : <p className="panel-body muted">The diagnosis will appear after the Triage agent gathers evidence and assesses root causes.</p>
}

export function PlanTab({ snapshot, open, revised }: TabProps & { revised: boolean }) {
  const activeRef = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const pending = snapshot?.pending_interrupt?.type === 'step' ? snapshot.pending_interrupt.payload as PlanStep : null
  const signature = JSON.stringify(snapshot?.plan)
  useEffect(() => {
    const element = activeRef.current
    const panel = element?.closest('.inspector, .drawer')
    if (!element || !panel) return
    // Scroll only the reference panel; never move the engineer's action area.
    const top = element.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop - 120
    panel.scrollTo({ top: Math.max(0, top), behavior: reduced ? 'instant' : 'smooth' })
  }, [pending?.n, signature, reduced])

  if (!snapshot?.plan) return <p className="panel-body muted">The plan will appear when the Triage agent hands the diagnosis to the Planner agent.</p>
  return (
    <section aria-label="Resolution plan">
      {revised && <p className="revision-banner" role="status">Plan revised after new evidence</p>
      }
      {snapshot.plan.steps.map(step => (
        <article
          ref={pending?.n === step.n ? activeRef : undefined}
          key={`${step.n}-${step.command_or_action}`}
          className={`step ${pending?.n === step.n ? 'active' : ''}`}>
          <p className={`hint ${step.status || ''}`}>Step {step.n} of {snapshot.plan!.steps.length} · {step.status || 'pending'}</p>
          <h3>{step.title}</h3>
          {pending?.n === step.n && <p className="text-accent text-sm">Awaiting your result · act in the Your turn card ←</p>
          }
          <StepDetails step={step} />
          <SourceBadge step={step} open={open} />
        </article>
      ))}
    </section>
  )
}

export function TopologyTab({ snapshot }: TabProps) {
  return snapshot?.triage_result
    ? <TopologyMap snapshot={snapshot} />
    : <p className="panel-body muted">The environment map will fill after diagnosis identifies affected components and dependencies to check.</p>
}

export function EvidenceTab({ snapshot, open }: TabProps) {
  if (!snapshot?.triage_result) return <p className="panel-body muted">Evidence references will appear as the Triage agent completes the diagnosis.</p>
  return (
    <div className="panel-body space-y-4">
      <Button variant="outline" onClick={() => open({})}>Open captured log evidence</Button>
      <p className="hint">{snapshot.evidence.length} captured lines · {snapshot.flags.length} ignored instruction-like entries</p>
      {snapshot.triage_result.kb_matches.map(match => (
        <div key={match.doc_id}>
          <p>{match.title}</p>
          <Button variant="ghost" onClick={() => open({ doc: match.doc_id })}>Open {match.doc_id}</Button>
        </div>
      ))}
    </div>
  )
}

export function InspectorTabs({ snapshot, open, tab, onTabChange, revised }: TabProps & {
  tab: InspectorTab
  onTabChange: (tab: InspectorTab) => void
  revised: boolean
}) {
  const id = useId()
  return (
    <div>
      <div
        className="inspector-tabs"
        role="tablist"
        aria-label="Incident reference">
        {tabs.map(name => (
          <button
            key={name}
            id={`${id}-${name}`}
            role="tab"
            aria-selected={tab === name}
            aria-controls={`${id}-panel`}
            tabIndex={tab === name ? 0 : -1}
            onClick={() => onTabChange(name)}
            onKeyDown={event => {
              const offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
              const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1)! : offset ? tabs[(tabs.indexOf(name) + offset + tabs.length) % tabs.length] : null
              if (next) {
                event.preventDefault()
                onTabChange(next)
                document.getElementById(`${id}-${next}`)?.focus()
              }

            }}>{name}</button>
        ))}
      </div>
      <div
        id={`${id}-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-${tab}`}>
        <p className="inspector-description">{descriptions[tab]}</p>
        {tab === 'Diagnosis' && <DiagnosisTab snapshot={snapshot} open={open} />
        }
        {tab === 'Plan' && <PlanTab
          snapshot={snapshot}
          open={open}
          revised={revised} />
        }
        {tab === 'Topology' && <TopologyTab snapshot={snapshot} open={open} />
        }
        {tab === 'Evidence' && <EvidenceTab snapshot={snapshot} open={open} />
        }
      </div>
    </div>
  )
}
