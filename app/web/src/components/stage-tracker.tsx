import { Check, Minus } from 'lucide-react'
import { stages, stageDescriptions, deriveStage } from '@/lib/stage'
import type { Activity, Snapshot } from '@/lib/contracts'

export function StageTracker({ snapshot, liveNode, activity, logsApproved }: {
  snapshot?: Snapshot
  liveNode: string | null
  logsApproved?: boolean
  activity: Activity[]
}) {
  const model = deriveStage(snapshot, liveNode, activity)
  const current = stages.indexOf(model.stage)
  return (
    <section className="stage-tracker" aria-label="Incident stages">
      <ol>
        {stages.map((stage, index) => {
          const skippedLogs = stage === 'Logs' && index < current && !(snapshot?.logs_approved ?? logsApproved)
          const skippedFix = stage === 'Fix' && index < current && !snapshot?.plan
          const skipped = skippedLogs || skippedFix
          return (
          <li
            key={stage}
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
      <p role="status">{model.status}{model.stage === 'Fix' && model.progress ? ` · ${model.progress}` : ''}</p>
    </section>
  )
}
