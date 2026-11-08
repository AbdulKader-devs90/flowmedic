import type { ReactNode } from 'react'
import { Activity } from 'lucide-react'

export function AppShell({ children, pageTitle, onHelp }: {
  children: ReactNode
  pageTitle: string
  onHelp: () => void
}) {
  return (
    <div className="app-frame">
      <header className="app-bar">
        <div className="brand">
          <Activity />FlowMedic</div>
        <span>{pageTitle}</span>
        <button
          className="icon-button"
          aria-label="How FlowMedic works"
          onClick={onHelp}>?</button>
      </header>
      <div className="shell">{children}</div>
    </div>
  )
}
