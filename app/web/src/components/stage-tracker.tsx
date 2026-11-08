import { Check } from 'lucide-react'
import { stages, stageDescriptions, deriveStage } from '@/lib/stage'
import type { Activity, Snapshot } from '@/lib/contracts'

export function StageTracker({ snapshot, liveNode, activity }: {
  snapshot?: Snapshot
  liveNode: string | null
  activity: Activity[]
}) {
  const model = deriveStage(snapshot, liveNode, activity)
  const current = stages.indexOf(model.stage)
  return (
    <section className="stage-tracker" aria-label="Incident stages">
      <ol>
        {stages.map((stage, index) => (
          <li
            key={stage}
            aria-current={index === current ? 'step' : undefined}
            title={stageDescriptions[stage]}>
            {index < current && <Check aria-label="Completed" />
            }
            <span>{stage}</span>
          </li>
        ))}
      </ol>
      <p role="status">{model.status}{model.stage === 'Fix' && model.progress ? ` · ${model.progress}` : ''}</p>
    </section>
  )
}
