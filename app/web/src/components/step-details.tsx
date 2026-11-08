import type { PlanStep } from '@/lib/contracts'
import { CopyButton } from './diagnosis'

export function StepDetails({ step }: { step: PlanStep }) {
  return (
    <div className="step-details">
      <p className="hint">Where: <code>{step.where}</code> · <span className={step.kind}>[{step.kind}]</span>
      </p>
      <pre className="command">
        <code>{step.command_or_action}</code>
        <CopyButton text={step.command_or_action} />
      </pre>
      <p>
        <span className="muted">Expected · </span>{step.expected_output}</p>
      {step.kind !== 'read' && (
        <div className="my-3 space-y-2 text-sm">
          <p>
            <span className="text-warning">Risk · </span>{step.risk || 'Review the impact before making this change.'}</p>
          <p>
            <span className="muted">Rollback · </span>{step.rollback || 'Confirm a rollback procedure before proceeding.'}</p>
        </div>
      )}
      <p className="hint my-3">{step.decision_rule}</p>
    </div>
  )
}
