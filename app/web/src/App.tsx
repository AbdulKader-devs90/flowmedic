import { SetupPage, KnowledgePage } from '@/components/configuration-pages'
import { displayPath } from '@/lib/display'
import { HowItWorks } from '@/components/how-it-works'
import { StageTracker } from '@/components/stage-tracker'
import { StoryTimeline } from '@/components/story-timeline'
import type { InspectorTab } from '@/components/inspector-tabs'
import { plainLabel, planSignature } from '@/lib/stage'
import { readStory, writeStory } from '@/lib/story'
import type { Milestone } from '@/lib/story'
import { AppShell } from '@/components/app-shell'
import { LeftRail } from '@/components/left-rail'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity as ActivityIcon, ArrowRight, FileSearch, PanelRight, Plus, Search, ShieldCheck, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { YourTurnCard } from '@/components/your-turn-card'
import { InspectorTabs } from '@/components/inspector-tabs'
import { EvidenceDrawer } from '@/components/evidence-drawer'
import type { EvidenceTarget } from '@/components/evidence-drawer'
import { NewIncident } from '@/components/new-incident'
import { useIncidentStream } from '@/hooks/use-incident-stream'
import type { EventHandler } from '@/hooks/use-incident-stream'
import { api } from '@/lib/api'
import { questionType } from '@/lib/contracts'
import type { Activity, Plan, Question, Resume, Snapshot, TriageResult } from '@/lib/contracts'
export default function App() {
  const client = useQueryClient()
  const [selected, setSelected] = useState<string | null>(() => new URLSearchParams(window.location.search).get('incident'))

  const selectedRef = useRef<string | null>(selected)
  const [newOpen, setNewOpen] = useState(false), [commandOpen, setCommandOpen] = useState(false), [detailsOpen, setDetailsOpen] = useState(false)
  const [page, setPage] = useState('War room')
  const [helpOpen, setHelpOpen] = useState(() => {
    try { return localStorage.getItem('flowmedic.help.seen') !== 'true' } catch { return true }
  })
  useEffect(() => {
    try { localStorage.setItem('flowmedic.help.seen', 'true') } catch { /* Help remains available without storage. */ }
  }, [])
  const [sent, setSent] = useState(false)
  const [handoff, setHandoff] = useState<string | null>(null)
  useEffect(() => {
    if (!handoff) return
    const timeout = window.setTimeout(() => setHandoff(null), 800)
    return () => window.clearTimeout(timeout)
  }, [handoff])
  const [stories, setStories] = useState<Record<string, Milestone[]>>({})
  const [tabChoice, setTabChoice] = useState<{
    id: string | null
    signature: string
    tab: InspectorTab
  } | null>(null)

  const remember = useCallback((id: string, milestone: Milestone) => {
    setStories(previous => {
      const rows = [...(previous[id] || readStory(id)).filter(row => row.id !== milestone.id), milestone]
      writeStory(id, rows)
      return { ...previous, [id]: rows }
    })

  }, [])

  const [knowledgeSearch, setKnowledgeSearch] = useState('')
  const [evidence, setEvidence] = useState<EvidenceTarget | null>(null)
  const [activities, setActivities] = useState<Record<string, Activity[]>>({})
  const [liveNode, setLiveNode] = useState<string | null>(null)
  const [problemFilter, setProblemFilter] = useState('')
  const [creationError, setCreationError] = useState<string | null>(null)
  const [uploadRecovery, setUploadRecovery] = useState<string | null>(null)
  const activityId = useRef(0)
  const scenarios = useQuery({ queryKey: ['scenarios'], queryFn: api.scenarios })
  const incidents = useQuery({ queryKey: ['incidents'], queryFn: api.incidents })
  const snapshot = useQuery({
    queryKey: ['incident', selected],
    queryFn: () => api.snapshot(selected!),
    enabled: !!selected
  })

  const refresh = useCallback(() => {
    setLiveNode(null)
    void client.invalidateQueries({ queryKey: ['incident', selectedRef.current] })
    void client.invalidateQueries({ queryKey: ['incidents'] })
    void client.invalidateQueries({ queryKey: ['topology'] })
  }, [client])

  const onEvent: EventHandler = useCallback((name, data) => {
    const id = selectedRef.current
    if (!id) return
    if (name === 'triage_result') {
      const old = client.getQueryData<Snapshot>(['incident', id])
      // Only the first live hand-off earns motion; restored checkpoints and
      // re-assessments must not replay the transfer.
      if (old && !old.triage_result && !old.plan) {
        setHandoff(id)
        setTabChoice({ id, signature: planSignature(old), tab: 'Plan' })
      }
      client.setQueryData<Snapshot>(['incident', id], previous => previous ? { ...previous, triage_result: data as TriageResult } : previous)
    }
    if (name === 'plan_updated') {
      const old = client.getQueryData<Snapshot>(['incident', id])
      const plan = data as Plan
      if (old?.plan && planSignature(old) !== planSignature({ ...old, plan })) {
        remember(id, {
          id: `revision-${Date.now()}-${++activityId.current}`,
          stage: 'Fix',
          title: 'Plan revised after new evidence',
          detail: old.triage_result?.root_causes[0] ? plainLabel(old.triage_result.root_causes[0].id) : undefined
        })

      }

      client.setQueryData<Snapshot>(['incident', id], previous => previous ? {
        ...previous,
        plan,
        stage: 'planner'
      } : previous)

      setTabChoice({
        id,
        signature: planSignature(old ? { ...old, plan } : undefined),
        tab: 'Plan'
      })

    }

    if (name === 'interrupt') {
      setSent(false)
      const question = data as Question
      client.setQueryData<Snapshot>(['incident', id], old => old ? { ...old, pending_interrupt: { type: questionType(question), payload: question } } : old)
      setLiveNode(null)
    }

    if (name === 'node_started' || name === 'node_finished' || name === 'tool_called' || name === 'tool_result') {
      const row = data as {
        node?: string
        tool?: string
        summary?: string
        target?: string
      }

      const node = row.node || row.tool || 'Agent activity'
      if (name === 'node_started') setLiveNode(node)
      if (name === 'node_finished') setLiveNode(current => current === node ? null : current)
      const activity: Activity = {
        id: ++activityId.current,
        event: name,
        node,
        summary: row.summary || plainLabel(node),
        target: row.target,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }

      setActivities(previous => ({ ...previous, [id]: [...(previous[id] || []).slice(-199), activity] }))
    }

  }, [client, remember])

  const stream = useIncidentStream(onEvent, refresh)
  const resume = useMutation({
    mutationFn: (reply: Resume) => api.resume(selected!, reply), onSuccess: (_, reply) => {
      const id = selectedRef.current!
      const state = client.getQueryData<Snapshot>(['incident', id])
      const question = state?.pending_interrupt?.payload
      if (reply.kind === 'approve_logs' && typeof reply.payload === 'object' && reply.payload.approved && question && 'kind' in question && question.kind === 'log_access') {
        const window = reply.payload.window as { start_time: string | null; end_time: string | null }
        remember(id, {
          id: 'logs-approved',
          stage: 'Logs',
          title: `Log access approved (${displayPath(question.folder, state?.display_root)}, ${window.start_time || 'start of export'} – ${window.end_time || 'end of export'})`
        })

      }

      if (reply.kind === 'step_result' && question && 'type' in question && question.type === 'step' && typeof reply.payload === 'object') {
        remember(id, {
          id: `plan-${1 + readStory(id).filter(row => row.id.startsWith('revision-')).length}-step-${question.n}-${question.command_or_action}`,
          stage: 'Fix',
          title: `Plan ${1 + readStory(id).filter(row => row.id.startsWith('revision-')).length} · Step ${question.n} ${reply.payload.status}: ${question.title}`,
          detail: String(reply.payload.output || '').replace(/\s+/g, ' ').slice(0, 180)
        })

      }

      if (question && 'type' in question && question.type === 'approve_save') remember(id, {
        id: 'outcome',
        stage: 'Close',
        title: '',
        detail: question.outcome
      })

      setSent(reply.kind === 'step_result')
      client.setQueryData<Snapshot>(['incident', selected], old => old ? { ...old, pending_interrupt: null } : old)
      stream.start(selected!)
    }
  })

  const select = useCallback((id: string | null, push = true) => {
    stream.stop()
    selectedRef.current = id
    setSelected(id)
    setHandoff(null)
    if (push) {
      const url = new URL(window.location.href)
      if (id) url.searchParams.set('incident', id)
      else url.searchParams.delete('incident')
      if (url.href !== window.location.href) window.history.pushState({}, '', url)
    }

    setPage('War room')
    setSent(false)
    setLiveNode(null)
    setEvidence(null)
    resume.reset()
  }, [stream, resume])

  useEffect(() => {
    const back = () => select(new URLSearchParams(window.location.search).get('incident'), false)
    window.addEventListener('popstate', back)
    return () => window.removeEventListener('popstate', back)
  }, [select])
  const navigate = (name: string) => {
    if (name === 'War room') select(null)
    else { stream.stop(); setPage(name) }
  }

  // Keyboard listener is intentionally rebound to the latest selected incident actions.
  useEffect(() => {
    function key(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(open => !open)
      }
    }

    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [])

  const create = useMutation({
    mutationFn: async ({ body, files }: {
      body: {
        message?: string
        environment?: string
        scenario_id?: string
      }; files: File[]
    }) => {
      setCreationError(null)
      setUploadRecovery(null)
      const oversized = files.find(file => file.size > 50 * 1024 * 1024)
      if (oversized) throw new Error(`${oversized.name} exceeds the 50 MiB limit.`)
      const { incident_id: id } = await api.create(body)
      try {
        for (const file of files) await api.upload(id, file)
      } catch (error) {
        setUploadRecovery(id)
        throw new Error(`Incident created, but upload failed: ${error instanceof Error ? error.message : 'Unknown upload error'}. Open the created incident to continue without the remaining files.`)
      }

      return id
    },
    onSuccess: id => {
      select(id)
      setNewOpen(false)
      void client.invalidateQueries({ queryKey: ['incidents'] })
      void client.fetchQuery({ queryKey: ['incident', id], queryFn: () => api.snapshot(id) }).then(() => stream.start(id), error => setCreationError(error instanceof Error ? error.message : 'Could not load the incident checkpoint.'))
    },
    onError: error => setCreationError(error.message)
  })

  const submit = (reply: Resume) => resume.mutate(reply)
  const current = incidents.data?.find(item => item.id === selected)
  const activity = selected ? activities[selected] || [] : []
  const remembered = selected ? stories[selected] || readStory(selected) : []
  const signature = planSignature(snapshot.data)
  const tab = tabChoice?.id === selected && tabChoice.signature === signature ? tabChoice.tab : snapshot.data?.plan ? 'Plan' : 'Diagnosis'
  const diagnosis = <InspectorTabs
    snapshot={snapshot.data}
    open={setEvidence}
    tab={tab}
    onTabChange={tab => setTabChoice({
      id: selected,
      signature,
      tab
    })}
    revised={remembered.some(row => row.id.startsWith('revision-'))} />
  return <>
    <AppShell pageTitle={page} onHome={() => select(null)} onHelp={() => setHelpOpen(true)}>
      <LeftRail
        incidents={incidents}
        selected={selected}
        select={select}
        snapshot={snapshot.data}
        page={page}
        setPage={navigate}
        problemFilter={problemFilter}
        setProblemFilter={setProblemFilter}
        setNewOpen={setNewOpen}
        setCommandOpen={setCommandOpen} />
      <main className={`workspace ${page !== 'War room' ? 'catalog-workspace' : ''}`}>
        {page !== 'War room' ? (
          page === 'Setup' ? <SetupPage onKnowledge={() => setPage('Knowledge')} /> : <KnowledgePage open={id => setEvidence({ doc: id })} />
        ) : <>
          <header className="workspace-head">
            <div className="min-w-0">
              <div>{selected && <button className="hint mb-2" onClick={() => select(null)}>← All incidents</button>}</div>
              <h1>{selected ? 'Incident war room' : 'War room'}</h1>
              <p className="hint mt-1">{selected ? `${current?.environment || snapshot.data?.context.environment || 'Environment pending'} · ${selected.slice(0, 8)}` : 'Diagnose the break. Guide the fix.'}</p>
            </div>
            <Button
              variant="outline"
              className="details-toggle"
              size="sm"
              onClick={() => setDetailsOpen(true)}>
              <PanelRight />Details</Button>
          </header>
          {selected && <StageTracker
            handoff={handoff === selected}
            snapshot={snapshot.data}
            liveNode={liveNode}
            activity={activity}
            logsApproved={remembered.some(row => row.id === 'logs-approved')} />
          }
          <div className="timeline">
            <div className="timeline-content">
              {!selected ? (
                <section className="empty">
                  <ActivityIcon className="text-text-muted" />
                  <h1>No active incident</h1>
                  <p className="muted">Start with a problem report or a demo scenario.</p>
                  <Button
                    className="mt-6"
                    variant="outline"
                    onClick={() => setCommandOpen(true)}>
                    <Search />Open commands <kbd className="ml-6 text-xs muted">⌘K</kbd>
                  </Button>
                  <HowItWorks />
                  <div className="scenarios">
                    <p className="hint mt-5 mb-1">Demo scenarios</p>
                    {scenarios.isPending && <p className="hint py-5">Loading scenario catalog…</p>
                    }
                    {scenarios.error && <div className="error my-4">Could not load scenarios. Check that the API is running.<Button
                      variant="outline"
                      size="sm"
                      onClick={() => void scenarios.refetch()}>Retry</Button>
                    </div>
                    }
                    {scenarios.data?.slice(0, 4).map(s => (
                      <button
                        className="scenario"
                        key={s.id}
                        disabled={create.isPending}
                        onClick={() => create.mutate({ body: { scenario_id: s.id }, files: [] })}>
                        <code className="text-xs muted">{s.id}</code>
                        <span className="text-sm">{s.title}</span>
                        <ArrowRight />
                      </button>
                    ))}
                    {(scenarios.data?.length || 0) > 4 && <Button
                      className="mt-4"
                      variant="ghost"
                      size="sm"
                      onClick={() => setNewOpen(true)}>View all {scenarios.data?.length} scenarios<ArrowRight />
                    </Button>
                    }
                  </div>
                  {creationError && <p className="error mt-4">{creationError}</p>
                  }
                </section>
              ) : <>
                {snapshot.isPending && <p className="muted">Loading incident checkpoint…</p>
                }
                {snapshot.error && <div className="error" role="alert">{snapshot.error.message}<Button variant="outline" onClick={() => void snapshot.refetch()}>Retry checkpoint</Button>
                </div>
                }
                {snapshot.data && <StoryTimeline
                  snapshot={snapshot.data}
                  report={current?.title}
                  activity={activity}
                  remembered={remembered} />
                }
                {stream.error && <div className="error mt-4" role="alert">{stream.error}</div>
                }
                {resume.error && <div className="error mt-4" role="alert">{resume.error.message}</div>
                }
              </>
              }
            </div>
          </div>
          {selected && snapshot.data && <YourTurnCard
            snapshot={snapshot.data}
            liveNode={liveNode}
            busy={resume.isPending || stream.running}
            running={stream.running}
            sent={sent && snapshot.data.stage !== 'closed'}
            submit={submit}
            continueIncident={() => stream.start(selected)}
            onNew={() => setNewOpen(true)}
            onHome={() => select(null)} />
          }
          <footer className="px-6 py-3 border-t border-border flex-row hint">
            <ShieldCheck />The engineer runs every command.</footer>
        </>
        }
      </main>
      {page === 'War room' && <aside className="inspector" aria-label="Incident reference">{diagnosis}</aside>}
    </AppShell>
    <NewIncident
      open={newOpen}
      close={() => setNewOpen(false)}
      scenarios={scenarios.data || []}
      busy={create.isPending}
      error={creationError}
      create={(body, files) => create.mutate({ body, files })} />{uploadRecovery && <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 bg-surface border border-warning rounded-sm p-4">
        <Button variant="outline" onClick={() => {
          select(uploadRecovery)
          setNewOpen(false)
          setUploadRecovery(null)
        }}>Open created incident</Button>
      </div>
    }<CommandDialog
      open={commandOpen}
      onOpenChange={setCommandOpen}
      title="Commands"
      description="Create an incident, load a demo or open knowledge.">
      <CommandInput
        placeholder="Search commands, scenarios or a knowledge ID…"
        value={knowledgeSearch}
        onValueChange={setKnowledgeSearch} />
      <CommandList>
        <CommandEmpty>No matching commands.</CommandEmpty>
        <CommandGroup heading="Incident">
          <CommandItem onSelect={() => {
            setCommandOpen(false)
            setNewOpen(true)
          }}>
            <Plus />New incident</CommandItem>
          <CommandItem onSelect={() => {
            setCommandOpen(false)
            setEvidence({ doc: 'INC-003' })
          }}>
            <FileSearch />Open knowledge doc INC-003</CommandItem>
        </CommandGroup>{/^(INC|RB)-[A-Z0-9-]+$/i.test(knowledgeSearch.trim()) && <CommandGroup heading="Knowledge">
          <CommandItem value={knowledgeSearch} onSelect={() => {
            setCommandOpen(false)
            setEvidence({ doc: knowledgeSearch.trim().toUpperCase() })
          }}>
            <FileSearch />Open {knowledgeSearch.trim().toUpperCase()}</CommandItem>
        </CommandGroup>
        }<CommandGroup heading="Load scenario">{scenarios.data?.map(s => <CommandItem
          key={s.id}
          value={`${s.id} ${s.title}`}
          onSelect={() => {
            setCommandOpen(false)
            create.mutate({ body: { scenario_id: s.id }, files: [] })
          }}>
          <Terminal />
          <span>{s.id} · {s.title}</span>
        </CommandItem>)}</CommandGroup>
      </CommandList>
    </CommandDialog>
    <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
      <DialogContent className="drawer translate-x-0 translate-y-0 left-auto top-0 p-0 max-w-none">
        <DialogTitle className="sr-only">Incident details</DialogTitle>
        <DialogDescription className="sr-only">Triage, topology and the resolution plan</DialogDescription>{diagnosis}</DialogContent>
    </Dialog>
    <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
      <DialogContent>
        <DialogTitle className="sr-only">How FlowMedic works</DialogTitle>
        <DialogDescription className="sr-only">The four steps from report to recorded resolution.</DialogDescription>
        <HowItWorks />
      </DialogContent>
    </Dialog>
    <EvidenceDrawer
      target={evidence}
      snapshot={snapshot.data}
      close={() => setEvidence(null)} />
  </>
}
