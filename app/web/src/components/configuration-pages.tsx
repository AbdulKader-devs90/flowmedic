import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { humanize } from '@/lib/contracts'
import { TopologyMap } from './diagnosis'
import { Button } from './ui/button'
import { trustHints } from '@/lib/display'

const slotQuestions: Record<string, string> = {
  component: 'Which component is affected?', version: 'Which version is installed?', os: 'Which operating system is it running?',
  environment: 'Which environment is affected?', start_time: 'When did the issue start?', scope: 'How widespread is the issue?',
  recent_changes: 'What changed recently?', deployment_mode: 'How is Kong deployed?', route: 'Which route is affected?',
}
const platformGuide = [
  'Copy an existing file in platforms/ (for example kong.yaml).',
  'Set id, name, versions and os. For Kong, id is kong and versions includes "3.8".',
  'List the questions the agent must ask in clarify_slots.required and the extra questions in clarify_slots.optional.',
  'List components with type, logs and error_patterns.',
  'Add incidents and runbooks under knowledge/incidents/ and knowledge/runbooks/ with platform: kong, then run: uv run python -m flowmedic.knowledge.ingest',
  'Restart the API.',
]
const environmentGuide = [
  'Create environments/<name>/topology.yaml. Set environment, platform, version and os. Use components with id and type; layers are derived from type. Use links with from, to, kind and hard: true for a hard dependency or hard: false for a soft dependency. See environments/kong-sample/topology.yaml.',
  'Optionally add architecture.png, with no real IPs or hostnames.',
  'Set default_environment in the platform file if this environment should be the default (for Kong: kong-sample).',
  'Restart the API.',
]
export function SetupPage({ onKnowledge }: { onKnowledge: () => void }) {
  const platforms = useQuery({ queryKey: ['platforms'], queryFn: api.platforms })
  const environments = useQuery({ queryKey: ['environments'], queryFn: api.environments })
  const knowledge = useQuery({ queryKey: ['knowledge-index', ''], queryFn: () => api.knowledgeIndex() })
  const queries = [platforms, environments, knowledge]
  return <section className="catalog-page">
    <h1>Setup</h1>
    <p className="muted page-intro">How FlowMedic is configured. Everything here comes from files in the repo; change the file, restart the API, and the change shows up here.</p>
    {queries.some(q => q.isPending) && <p className="hint">Loading repository configuration…</p>
    }
    {queries.some(q => q.error) && <div className="error">Could not load repository configuration. <Button variant="outline" onClick={() => queries.forEach(q => void q.refetch())}>Retry</Button>
    </div>
    }
    <h2>Platforms</h2>
    <div className="config-grid">{platforms.data?.map(p => <article className="config-card" key={p.id}>
      <h3>{p.name}</h3>
      <code className="source-chip">{p.source_file}</code>
      <p className="config-metadata">Versions: {p.versions.join(', ') || 'Not specified'}</p>
      <p className="config-metadata">Operating systems: {p.os.join(', ') || 'Not specified'}</p>
      <p className="hint">Default environment: {p.default_environment || 'None'}</p>
      <h4>Questions the agent asks</h4>
      {!p.clarify_slots.required.length && !p.clarify_slots.optional.length && <p className="hint">No platform-specific questions configured.</p>
      }
      {(['required', 'optional'] as const).map(kind => p.clarify_slots[kind].map(slot => <p className="config-question" key={`${kind}-${slot}`}>{slotQuestions[slot] || humanize(slot)} <span className="hint">({kind})</span>
      </p>))}
      <h4>Components and logs</h4>
      {p.components.map(c => <div className="config-component" key={c.type}>
        <p>{humanize(c.type)}</p>
        <p className="hint">Log files: <code>{c.logs.join(', ') || 'None'}</code>
        </p>
        <p className="hint">{c.error_pattern_count} error patterns · first {c.error_patterns.length}</p>{c.error_patterns.map(pattern => <code className="pattern" key={pattern}>{pattern}</code>)}</div>)}
      <p className="hint">Knowledge: {knowledge.data?.filter(k => k.platform === p.id).length ?? '…'} documents</p>
    </article>)}</div>
    <h2>Environments</h2>
    <div className="config-grid">{environments.data?.map(env => <article className="config-card" key={env.id}>
      <h3>{env.id}</h3>
      <p className="muted">{platforms.data?.find(p => p.id === env.platform)?.name || env.platform} · {env.node_count} nodes · {env.edge_count} edges</p>
      <code className="source-chip">{env.source_file}</code>
      <TopologyMap snapshot={{ id: '', context: { environment: env.id }, stage: 'triage', triage_result: null, plan: null, evidence: [], flags: [], pending_interrupt: null }} />
      {env.has_architecture && <img className="architecture" src={`/api/environments/${encodeURIComponent(env.id)}/architecture`} alt={`Architecture diagram for ${env.id}`} />
      }
    </article>)}</div>
    <h2>Knowledge</h2>
    {platforms.data?.map(p => <p key={p.id}>{p.name}: {['incident', 'runbook'].map(type => `${knowledge.data?.filter(k => k.platform === p.id && k.type === type).length ?? '…'} ${type}s`).join(' · ')}</p>)}
    <Button className="mt-4" variant="outline" onClick={onKnowledge}>Open Knowledge</Button>
    {[['How to add a platform', platformGuide], ['How to add an environment', environmentGuide]].map(([title, lines]) => <details className="configuration-guide" key={String(title)}>
      <summary>{title}</summary>
      <ol>{(lines as string[]).map(line => <li key={line}>{line}</li>)}</ol>
    </details>)}
  </section>
}
export function KnowledgePage({ open }: { open: (id: string) => void }) {
  const [search, setSearch] = useState('')
  const query = useQuery({ queryKey: ['knowledge-index', search], queryFn: () => api.knowledgeIndex(search) })
  return <section className="catalog-page">
    <h1>Knowledge</h1>
    <p className="muted page-intro">Past incidents and runbooks the Triage agent searches. New incidents are added here only after you approve saving them.</p>
    <label className="label">Search by ID or title<input className="field mt-2" type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Find an incident or runbook…" />
    </label>
    {query.isPending && <p className="hint">Loading knowledge…</p>
    }
    {query.error && <div className="error">Could not load knowledge. <Button variant="outline" onClick={() => void query.refetch()}>Retry</Button>
    </div>
    }
    {query.data && <div className="knowledge-table">
      <table>
        <thead>
          <tr>{['ID', 'Title', 'Platform', 'Category', 'Type', 'Verified'].map(label => <th key={label}>{label}</th>)}</tr>
        </thead>
        <tbody>{query.data.map(doc => <tr key={doc.id} onClick={() => open(doc.id)}>
          <td>
            <button className="knowledge-link mono" onClick={e => { e.stopPropagation(); open(doc.id) }}>{doc.id}</button>
          </td>
          <td>{doc.title}</td>
          <td>{doc.platform}</td>
          <td>{doc.category}</td>
          <td>{doc.type}</td>
          <td>{doc.verified ? <span className="badge verified" title={trustHints.verified}>Verified</span> : <span className="hint">Unreviewed</span>
          }</td>
        </tr>)}</tbody>
      </table>{!query.data.length && <p className="muted mt-4">No documents match this search.</p>
      }</div>
    }
  </section>
}
