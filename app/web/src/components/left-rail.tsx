import { ListFilter, Plus, ShieldCheck, Search } from 'lucide-react'
import type { UseQueryResult } from '@tanstack/react-query'
import type { Incident } from '@/lib/contracts'
import { incidentStageLabel } from '@/lib/stage'
import type { Snapshot } from '@/lib/contracts'
import { useQueries } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from './ui/button'
import { SeverityPill } from './diagnosis'
function age(value: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000))
  return Number.isNaN(minutes) ? '' : minutes < 1 ? 'just now' : minutes < 60 ? `${minutes}m ago` : `${Math.floor(minutes / 60)}h ago`
}
export function LeftRail({ incidents, selected, select, problemFilter, setProblemFilter, setNewOpen, setCommandOpen, snapshot, page, setPage }: {
  snapshot?: Snapshot
  page: string
  setPage: (page: string) => void
  incidents: UseQueryResult<Incident[], Error>
  selected: string | null
  select: (id: string) => void
  problemFilter: string
  setProblemFilter: (value: string | ((value: string) => string)) => void
  setNewOpen: (open: boolean) => void
  setCommandOpen: (open: boolean) => void
}) {
  const checkpoints = useQueries({ queries: (incidents.data || []).map(item => ({ queryKey: ['incident', item.id], queryFn: () => api.snapshot(item.id) })) })
  const saved = new Map(checkpoints.map(query => [query.data?.id, query.data]))
  return <aside className="rail" aria-label="Incidents">
    <div className="rail-head">
      <nav className="rail-nav" aria-label="Main navigation">
        {['War room', 'Setup', 'Knowledge'].map(name => (
          <button
            key={name}
            aria-current={page === name ? 'page' : undefined}
            onClick={() => setPage(name)}>{name}</button>
        ))}
      </nav>
      <Button className="w-full justify-between" onClick={() => setNewOpen(true)}>
        <span className="flex-row">
          <Plus />New incident</span>
        <kbd className="text-xs opacity-70">⌘K</kbd>
      </Button>
    </div>
    <div className="px-5 mb-3 flex items-center justify-between">
      <span className="text-xs muted">Incidents {incidents.data ? `· ${incidents.data.length}` : ''}</span>
      <button
        className="icon-button"
        aria-label="Filter incidents"
        onClick={() => setProblemFilter(value => value ? '' : ' ')}>
        <ListFilter />
      </button>
    </div>{problemFilter && <label className="px-4 mb-3">
      <span className="sr-only">Filter incidents by title</span>
      <input
        className="field text-sm"
        autoFocus
        value={problemFilter.trimStart()}
        onChange={e => setProblemFilter(e.target.value || ' ')}
        placeholder="Find an incident…" />
    </label>
    }<div className="rail-list">{incidents.isPending && <p className="hint px-2">Loading incident checkpoints…</p>
    }{incidents.error && <div className="error text-sm">Could not load incidents.<Button
      variant="outline"
      size="sm"
      onClick={() => void incidents.refetch()}>Retry</Button>
    </div>
      }{incidents.data?.filter(item => item.title.toLowerCase().includes(problemFilter.trim().toLowerCase())).map(item => <button
        key={item.id}
        className={`incident-row ${selected === item.id ? 'selected' : ''}`}
        aria-current={selected === item.id ? 'page' : undefined}
        onClick={() => select(item.id)}>
        <div className="flex-row justify-between">
          <SeverityPill severity={item.severity} />
          <span className="hint">{age(item.updated_at)}</span>
        </div>
        <p className="line-clamp-3">{item.title}</p>
        <div className="flex-row justify-between hint">
          <span>{item.environment || 'Environment pending'}</span>
          <span>{incidentStageLabel(item, item.id === selected ? snapshot : saved.get(item.id))}</span>
        </div>
      </button>)}{incidents.data?.length === 0 && <p className="hint p-2">Your incident checkpoints will appear here.</p>
      }</div>
    <footer className="rail-foot">
      <div className="flex-row mb-2">
        <ShieldCheck />Read-only diagnostics</div>
      <button className="flex-row hover:text-text" onClick={() => setCommandOpen(true)}>
        <Search />Commands<kbd className="ml-auto">⌘K</kbd>
      </button>
    </footer>
  </aside>
}
