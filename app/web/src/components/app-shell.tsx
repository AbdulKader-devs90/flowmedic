import type { ReactNode } from 'react'
import { Activity } from 'lucide-react'

export function AppShell({ children, pageTitle, onHelp, onHome }: {
  children: ReactNode
  pageTitle: string
  onHome: () => void
  onHelp: () => void
}) {
  return (
    <div className="app-frame">
      <header className="app-bar">
        <button className="brand" onClick={onHome} aria-label="FlowMedic home">
          <Activity />FlowMedic</button>
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
