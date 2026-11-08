import { useState } from 'react'
import { Check, ShieldCheck, FileText, MessageSquare, FolderOpen } from 'lucide-react'
import { StepDetails } from './step-details'
import { Button } from '@/components/ui/button'
import { humanize, questionType } from '@/lib/contracts'
import type { Question, Resume, PlanStep } from '@/lib/contracts'

export function StepResultForm({ step, busy, submit }: {
  step: PlanStep
  busy: boolean
  submit: (reply: Resume) => void
}) {
  const [output, setOutput] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  return <div className="mt-4 space-y-4">
    <label className="label">Paste output<textarea
      className="field mt-2 mono"
      value={output}
      onChange={e => setOutput(e.target.value)}
      placeholder="Run the step yourself, then paste the result…" />
    </label>
    {step.kind !== 'read' && <label className="flex items-start gap-2 text-sm">
      <input
        type="checkbox"
        checked={confirmed}
        onChange={e => setConfirmed(e.target.checked)}
        className="mt-1 accent-accent" />I executed this action and reviewed its risk and rollback.</label>
    }
    <div className="flex-row">
      <Button disabled={busy || (step.kind !== 'read' && !confirmed)} onClick={() => submit({
        kind: 'step_result', payload: {
          step: step.n,
          status: 'done',
          output,
          confirmed: step.kind === 'read' || confirmed
        }
      })}>
        <Check />Done</Button>
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => submit({
          kind: 'step_result', payload: {
            step: step.n,
            status: 'skipped',
            output,
            confirmed: false
          }
        })}>Skipped</Button>
      <Button
        variant="outline"
        className="text-danger"
        disabled={busy}
        onClick={() => submit({
          kind: 'step_result', payload: {
            step: step.n,
            status: 'failed',
            output,
            confirmed
          }
        })}>Failed</Button>
    </div>
    <p className="hint">Done = it worked as expected. Failed = it did not. Skipped = not applicable here.</p>
  </div>
}
export function ActionCard({ question, busy, submit, total = 1 }: {
  question: Question
  busy: boolean
  submit: (reply: Resume) => void
  total?: number
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const kind = questionType(question)
  if ('type' in question && question.type === 'step') return <section className="action-card" aria-label="Step result requested">
    <div className="flex-row mb-3">
      <FileText />
      <h2>Your turn: run step {question.n} of {total} and report the result</h2>
    </div>
    <p className="muted">Your check is ready. Run it yourself, then report what happened.</p>
    <h3 className="mt-3">{question.title}</h3>
    <StepDetails step={question} />
    <StepResultForm
      step={question}
      busy={busy}
      submit={submit} />
  </section>
  if ('type' in question && question.type === 'approve_save') return <section className="action-card">
    <div className="flex-row mb-3">
      <ShieldCheck />
      <h2>Your turn: save this incident to the knowledge base?</h2>
    </div>
    <p className="muted">Review the record before adding it to the knowledge repository.</p>
    <p className="mt-3">Outcome: {humanize(question.outcome)}</p>
    <pre className="command max-h-80 overflow-auto">{JSON.stringify(question.record, null, 2)}</pre>
    <div className="buttons">
      <Button disabled={busy} onClick={() => submit({ kind: 'approve_save', payload: true })}>Save record</Button>
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => submit({ kind: 'approve_save', payload: false })}>Discard</Button>
    </div>
  </section>
  if ('kind' in question && question.kind === 'log_access') return <section className="action-card">
    <div className="flex-row mb-3">
      <FolderOpen />
      <h2>Your turn: approve read-only log access</h2>
    </div>
    <p className="muted text-sm">{question.why}</p>
    <p className="command">{question.folder}</p>
    <div className="grid-two">
      <label className="label">Start time<input
        className="field mt-2"
        value={start}
        onChange={e => setStart(e.target.value)}
        placeholder={question.start_time || 'Full export'} />
      </label>
      <label className="label">End time<input
        className="field mt-2"
        value={end}
        onChange={e => setEnd(e.target.value)}
        placeholder={question.end_time || 'Full export'} />
      </label>
    </div>
    <p className="hint">Read access to this folder only. Blank times use the displayed export window.</p>
    <div className="buttons">
      <Button disabled={busy} onClick={() => submit({
        kind: 'approve_logs', payload: {
          approved: true,
          roots: [question.folder],
          window: { start_time: start || question.start_time, end_time: end || question.end_time }
        }
      })}>Approve access</Button>
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => submit({ kind: 'approve_logs', payload: { approved: false } })}>Deny</Button>
    </div>
  </section>
  if (!('kind' in question) || !('slots' in question)) return null
  return <section className="action-card">
    <div className="flex-row mb-3">
      <MessageSquare />
      <h2>Your turn: answer one question</h2>
    </div>
    <p className="muted text-sm mb-5">{question.why || 'Select the details that match this environment.'}</p>
    <form onSubmit={e => {
      e.preventDefault()
      submit({ kind: 'answer', payload: answers })
    }}>{question.slots.map(slot => <div key={slot}>
      <label className="label" htmlFor={`answer-${slot}`}>{humanize(slot)}</label>
      <div className="flex-row mb-2">{question.allowed_values?.[slot]?.map(value => <Button
        key={value}
        type="button"
        variant={answers[slot] === value ? 'default' : 'outline'}
        size="sm"
        aria-pressed={answers[slot] === value}
        onClick={() => setAnswers(a => ({ ...a, [slot]: value }))}>{value}</Button>)}</div>
      <textarea
        id={`answer-${slot}`}
        className="field"
        rows={kind === 'evidence' ? 5 : 1}
        style={{ minHeight: kind === 'evidence' ? 120 : 42 }}
        value={answers[slot] || ''}
        onChange={e => setAnswers(a => ({ ...a, [slot]: e.target.value }))}
        placeholder={kind === 'evidence' ? 'Paste timestamped diagnostic evidence…' : `Enter ${slot.replaceAll('_', ' ')}`} />
    </div>)}<div className="buttons">
        <Button type="submit" disabled={busy || !Object.values(answers).some(v => v.trim())}>Continue</Button>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={() => submit({ kind: 'answer', payload: {} })}>Skip details</Button>
      </div>
    </form>
  </section>
}
