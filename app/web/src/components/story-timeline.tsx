import { displayPath } from '@/lib/display'
import { Activity as Pulse, Check, FileSearch } from 'lucide-react'
import type { Activity, Snapshot } from '@/lib/contracts'
import { plainLabel, stages } from '@/lib/stage'
import { collapseActivity, storyMilestones } from '@/lib/story'
import type { Milestone } from '@/lib/story'

export function StoryTimeline({ snapshot, report, activity, remembered }: {
  snapshot: Snapshot
  report?: string
  activity: Activity[]
  remembered: Milestone[]
}) {
  const milestones = storyMilestones(snapshot, remembered, report)
  const runs = collapseActivity(activity)
  return (
    <section aria-label="Story so far" className="story">
      <h2 className="section-title">Story so far</h2>
      {stages.map(stage => {
        const rows = milestones.filter(row => row.stage === stage)
        return rows.length > 0 && (
          <section className="story-stage" key={stage}>
            <h3>{stage}</h3>
            <ul>
              {rows.map(row => (
                <li key={row.id}>
                  <p>{displayPath(row.title, snapshot.display_root)}</p>
                  {row.detail && <p className="muted story-excerpt">{row.detail}</p>
                  }
                </li>
              ))}
            </ul>
          </section>
        )
      })}
      <details className="agent-activity">
        <summary>Show agent activity ({runs.length})</summary>
        {runs.length === 0 && <p className="hint">Technical activity appears during this browser session; the story above is restored from the checkpoint.</p>
        }
        {runs.map(row => (
          <div key={row.id} className="activity">
            {row.event.startsWith('tool') ? <FileSearch /> : row.event === 'node_finished' ? <Check /> : <Pulse className="activity-pulse" />
            }
            <div className="min-w-0 flex-1">
              <span>{plainLabel(row.node)}</span>
              <p className="muted break-words">{displayPath(plainLabel(row.summary), snapshot.display_root)}{row.target ? ` · ${displayPath(row.target, snapshot.display_root)}` : ''}</p>
            </div>
            <time className="hint">{row.time}</time>
          </div>
        ))}
      </details>
    </section>
  )
}
