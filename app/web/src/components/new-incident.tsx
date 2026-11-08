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
  const environments = [...new Set(['sample-prod', 'kong-sample', ...scenarios.flatMap(s => s.environment ? [s.environment] : [])])]
  return <Dialog open={open} onOpenChange={value => {
    if (!busy && !value) close()
  }}>
    <DialogContent className="dialog" showCloseButton={false}>
      <DialogHeader>
        <DialogTitle>New incident</DialogTitle>
        <DialogDescription className="muted">Describe what broke. You stay in control of every action.</DialogDescription>
      </DialogHeader>
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
          maxLength={100000} />
        </label>
        <label className="label">Environment<select
          className="field mt-2"
          value={environment}
          onChange={e => setEnvironment(e.target.value)}>{environments.map(env => <option key={env}>{env}</option>)}</select>
        </label>
        <label className="label flex items-center gap-2 cursor-pointer">
          <Upload />Attach UTF-8 log exports<input
            className="field mt-2 text-xs"
            type="file"
            accept=".log,.txt,.csv,.json,.xml,text/*"
            multiple
            onChange={e => setFiles(Array.from(e.target.files || []))} />
        </label>{files.map(file => <p className="hint" key={file.name}>{file.name} · {Math.ceil(file.size / 1024)} KB</p>)}{error && <p className="error" role="alert">{error}</p>
        }<Button type="submit" disabled={busy || !message.trim()}>
          <Plus />{busy ? 'Creating incident…' : 'Create incident'}</Button>
      </form>
      <div className="divider" />
      <h3 className="text-sm">Load demo scenario</h3>
      <div className="max-h-52 overflow-auto">{scenarios.map(s => <button
        className="scenario"
        key={s.id}
        disabled={busy}
        onClick={() => create({ scenario_id: s.id }, [])}>
        <code className="text-xs">{s.id}</code>
        <span className="text-sm">{s.title}</span>
        <ArrowRight />
      </button>)}</div>
      <Button
        variant="ghost"
        className="absolute right-4 top-4"
        onClick={close}
        disabled={busy}>Close</Button>
    </DialogContent>
  </Dialog>
}
