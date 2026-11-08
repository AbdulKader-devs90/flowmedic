import type { Resume, Snapshot } from '@/lib/contracts'
import { deriveStage } from '@/lib/stage'
import { ActionCard } from './action-card'
import { Button } from './ui/button'

export function YourTurnCard({ snapshot, liveNode, busy, running, sent, submit, continueIncident, onNew, onHome }: {
  snapshot: Snapshot
  liveNode: string | null
  busy: boolean
  running: boolean
  sent: boolean
  submit: (reply: Resume) => void
  onNew: () => void
  onHome: () => void
  continueIncident: () => void
}) {
  const waiting = snapshot.pending_interrupt
  return (
    <section className="your-turn" aria-label="Your turn">
      {sent ? (
        <p className="working-row" role="status">Sent. The Planner agent is reviewing your result…</p>
      ) : waiting ? (
        <ActionCard
          key={JSON.stringify(waiting.payload)}
          question={waiting.payload}
          displayRoot={snapshot.display_root}
          total={snapshot.plan?.steps.length}
          busy={busy}
          submit={submit} />
      ) : snapshot.stage === 'closed' ? (
        <div className="working-row">
          <h2>Incident workflow complete</h2>
          <p className="hint">Review the final assessment and recorded steps in the panels on the right.</p>
          <div className="flex-row mt-3"><Button onClick={onNew}>Start a new incident</Button><Button variant="outline" onClick={onHome}>Back to war room</Button></div>
        </div>
      ) : (
        <div className="working-row">
          <p role="status">Agent working: {deriveStage(snapshot, liveNode).status}</p>
          {!running && <Button
            className="mt-3"
            variant="outline"
            onClick={continueIncident}>Continue incident</Button>
          }
        </div>
      )}
    </section>
  )
}
