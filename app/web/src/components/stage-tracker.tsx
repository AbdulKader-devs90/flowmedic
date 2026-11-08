import { useRef } from 'react'
import { useReducedMotion } from 'framer-motion'
import { AnimatedBeam } from './ui/animated-beam'
import { Check, Minus } from 'lucide-react'
import { stages, stageDescriptions, deriveStage } from '@/lib/stage'
import type { Activity, Snapshot } from '@/lib/contracts'

export function StageTracker({ snapshot, liveNode, activity, logsApproved, handoff = false }: {
  handoff?: boolean
  snapshot?: Snapshot
  liveNode: string | null
  logsApproved?: boolean
  activity: Activity[]
}) {
  const container = useRef<HTMLElement>(null)
  const from = useRef<HTMLLIElement>(null)
  const to = useRef<HTMLLIElement>(null)
  const reduced = useReducedMotion()
  const model = deriveStage(snapshot, liveNode, activity)
  const current = stages.indexOf(model.stage)
  return (
    <section ref={container} className="stage-tracker" aria-label="Incident stages">
      <ol>
        {stages.map((stage, index) => {
          const skippedLogs = stage === 'Logs' && index < current && !(snapshot?.logs_approved ?? logsApproved)
          const skippedFix = stage === 'Fix' && index < current && !snapshot?.plan
          const skipped = skippedLogs || skippedFix
          return (
          <li
            key={stage}
            ref={stage === 'Diagnose' ? from : stage === 'Fix' ? to : undefined}
            aria-current={index === current ? 'step' : undefined}
            title={skippedLogs ? "No logs were provided" : skippedFix ? "No resolution plan was created" : stageDescriptions[stage]}
            className={skipped ? "stage-skipped" : undefined}>
            {skipped && <Minus aria-label="Skipped" />}
            {index < current && !skipped && <Check aria-label="Completed" />
            }
            <span>{stage}</span>
          </li>
        )})}
      </ol>
      {handoff && model.stage === 'Fix' && !reduced && <AnimatedBeam
          className="handoff-beam"
          containerRef={container}
          fromRef={from}
          toRef={to}
          startYOffset={12}
          endYOffset={12}
          duration={0.7}
          pathOpacity={0}
        />}
      <p role="status">{model.status}{model.stage === 'Fix' && model.progress ? ` · ${model.progress}` : ''}</p>
    </section>
  )
}
