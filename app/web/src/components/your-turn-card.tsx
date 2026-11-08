import type { Resume, Snapshot } from '@/lib/contracts'
import { deriveStage } from '@/lib/stage'
import { ActionCard } from './action-card'
import { Button } from './ui/button'

export function YourTurnCard({ snapshot, liveNode, busy, running, sent, submit, continueIncident }: {
  snapshot: Snapshot
  liveNode: string | null
  busy: boolean
  running: boolean
  sent: boolean
  submit: (reply: Resume) => void
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
          total={snapshot.plan?.steps.length}
          busy={busy}
          submit={submit} />
      ) : snapshot.stage === 'closed' ? (
        <div className="working-row">
          <h2>Incident workflow complete</h2>
          <p className="hint">Review the final assessment and recorded steps in the inspector.</p>
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
