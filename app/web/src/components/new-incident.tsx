import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useState } from 'react'
import { Plus, Upload, ArrowRight } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog'
import { Button } from './ui/button'
import type { Scenario } from '@/lib/contracts'
export function NewIncident({ open, close, scenarios, create, busy, error }: {
  open: boolean
  close: () => void
  scenarios: Scenario[]
  create: (body: {
    message?: string
    environment?: string
    scenario_id?: string
  }, files: File[]) => void
  busy: boolean
  error: string | null
}) {
  const [message, setMessage] = useState('')
  const [environment, setEnvironment] = useState('sample-prod')
  const [files, setFiles] = useState<File[]>([])
  const environments = useQuery({ queryKey: ['environments'], queryFn: api.environments })
  const platforms = useQuery({ queryKey: ['platforms'], queryFn: api.platforms })
  const platformName = (id: string | null) => platforms.data?.find(p => p.id === id)?.name || id || 'Other'
  const groups = [...new Set(scenarios.map(s => s.platform))]
  return <Dialog open={open} onOpenChange={value => {
    if (!busy && !value) close()
  }}>
    <DialogContent className="dialog" showCloseButton={false}>
      <DialogHeader>
        <DialogTitle>New incident</DialogTitle>
        <DialogDescription className="muted">Describe what broke. You stay in control of every action.</DialogDescription>
      </DialogHeader>
      <p className="hint">FlowMedic only reads logs you approve. It never runs commands on your servers.</p>
      <form onSubmit={e => {
        e.preventDefault()
        create({ message, environment }, files)
      }}>
        <label className="label">Problem<textarea
          className="field mt-2"
          value={message}
          onChange={e => setMessage(e.target.value)}
          placeholder="What is failing? Include symptoms, timing and recent changes."
          required
          maxLength={100000} /><span className="hint">Include symptoms, when they started and recent changes.</span>
        </label>
        <label className="label">Environment<select
          className="field mt-2"
          value={environment}
          onChange={e => setEnvironment(e.target.value)}>{(environments.data || []).map(env => <option key={env.id} value={env.id}>{env.id} · {platformName(env.platform)}</option>)}</select><span className="hint">Choose the reviewed topology for the affected system.</span>
        </label>
        <label className="label cursor-pointer">
          <span className="flex-row"><Upload />Attach UTF-8 log exports</span><input
            className="field mt-2 text-xs"
            type="file"
            accept=".log,.txt,.csv,.json,.xml,text/*"
            multiple
            onChange={e => setFiles(Array.from(e.target.files || []))} /><span className="hint block mt-2">Optional text exports, up to 50 MiB each. You approve read access separately.</span>
        </label>{files.map(file => <p className="hint" key={file.name}>{file.name} · {Math.ceil(file.size / 1024)} KB</p>)}{error && <p className="error" role="alert">{error}</p>
        }<Button type="submit" disabled={busy || !message.trim()}>
          <Plus />{busy ? 'Creating incident…' : 'Create incident'}</Button>
      </form>
      {environments.error && <p className="error">Could not load environments. <button onClick={() => void environments.refetch()}>Retry</button></p>}
      <div className="divider" />
      <h3 className="text-sm">Load demo scenario</h3>
      <div className="max-h-52 overflow-auto">{groups.map(platform => <section key={platform || 'other'}><h4 className="mt-4 text-sm muted">{platformName(platform)}</h4>{scenarios.filter(s => s.platform === platform).map(s => <button
        className="scenario"
        key={s.id}
        disabled={busy}
        onClick={() => create({ scenario_id: s.id }, [])}>
        <code className="text-xs">{s.id}</code>
        <span className="text-sm">{s.title}</span>
        <ArrowRight />
      </button>)}</section>)}</div>
      <Button
        variant="ghost"
        className="absolute right-4 top-4"
        onClick={close}
        disabled={busy}>Close</Button>
    </DialogContent>
  </Dialog>
}
