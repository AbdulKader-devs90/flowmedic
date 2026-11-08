import { confidenceHint, displayPath, trustHints, uniqueNotes } from '@/lib/display'
import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { Check, Copy, ExternalLink, GitBranch, ArrowUpRight, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import { humanize } from '@/lib/contracts'
import type { PlanStep, Snapshot, TriageResult, TopologyNode } from '@/lib/contracts'
import type { EvidenceTarget } from './evidence-drawer'
import { Button } from './ui/button'
import { NumberTicker } from './ui/number-ticker'
import { AnimatedBeam } from './ui/animated-beam'
export function SeverityPill({ severity }: { severity: string | null }) {
  return <span title={severity ? ({ P1: 'Critical outage; immediate attention required.', P2: 'Major impact; urgent investigation required.', P3: 'Limited impact; investigate with normal priority.', P4: 'Low impact; address during planned work.' }[severity]) : 'The Triage agent is assessing severity.'} className={`badge severity-${severity || 'P4'}`}>
    <span className="size-1 rounded-full bg-current" />{severity || 'Triaging'}</span>
}
export function CategoryTag({ category }: { category: string }) {
  return <span className="badge">{humanize(category)}</span>
}
export function SourceBadge({ step, open }: { step: PlanStep; open: (target: EvidenceTarget) => void }) {
  if (step.source_ref && step.source === 'verified') return <button title={trustHints.verified} className={`badge ${step.source}`} onClick={() => open({ doc: step.source_ref!.match(/(?:INC|RB)-[\w-]+/)?.[0] || step.source_ref! })}>
    <ShieldCheck />Verified · {step.source_ref}<ArrowUpRight />
  </button>
  if (step.source === 'cited' && step.source_ref && /^https?:\/\//.test(step.source_ref)) return <a
    title={trustHints.cited}
    className="badge cited"
    href={step.source_ref}
    target="_blank"
    rel="noreferrer">Cited <ExternalLink />
  </a>
  return <span title={trustHints[step.source]} className={`badge ${step.source}`}>{humanize(step.source)}</span>
}
export function TriageCard({ result, compact, open, displayRoot }: {
  displayRoot?: string
  result: TriageResult
  compact: boolean
  open: (target: EvidenceTarget) => void
}) {
  const reduced = useReducedMotion()
  const route = {
    known_fix: 'Known fix',
    similar: 'Similar',
    new_issue: 'New issue',
    clarify: 'Clarify'
  }[result.route]

  return <motion.section
    layoutId="triage-summary"
    layout
    transition={{
      type: 'spring',
      stiffness: 380,
      damping: 32,
      duration: reduced ? 0 : undefined
    }}
    className="triage">
    <div className="flex-row">
      <SeverityPill severity={result.severity} />
      <CategoryTag category={result.category} />
      <span className="badge text-accent">{route}</span>
    </div>
    <h2>{compact ? 'Diagnosis handed to planner' : 'Triage assessment'}</h2>{!compact && <>
      <div className="flex-row justify-between text-sm">
        <span className="muted" title={confidenceHint}>Assessment confidence</span>
        <span>{reduced ? Math.round(result.confidence * 100) : <NumberTicker value={Math.round(result.confidence * 100)} />
        }%</span>
      </div>{result.root_causes.map(cause => <div className="cause" key={cause.id}>
        <div className="flex items-start justify-between gap-3 text-sm">
          <span>{humanize(cause.id)}</span>
          <span className="muted">{Math.round(cause.confidence * 100)}%</span>
        </div>
        <div
          title={confidenceHint}
          className="confidence"
          role="meter"
          aria-label={`${humanize(cause.id)} confidence`}
          aria-valuenow={Math.round(cause.confidence * 100)}
          aria-valuemin={0}
          aria-valuemax={100}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${cause.confidence * 100}%` }}
            transition={{ duration: reduced ? 0 : .2 }} />
        </div>
        <div className="flex-row">{cause.evidence_refs.map(ref => {
          const match = ref.match(/^(.*?)(?::|#L)(\d+)$/)
          return <Button
            key={ref}
            variant="ghost"
            size="sm"
            onClick={() => open(match ? { file: match[1], line: Number(match[2]) } : { file: ref })}>{displayPath(ref, displayRoot)}<ArrowUpRight />
          </Button>
        })}</div>
      </div>)}{result.kb_matches[0] && <div className="border-t border-border pt-4">
        <p className="hint mb-2">Top knowledge match</p>
        <p className="text-sm mb-3">{result.kb_matches[0].title}</p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => open({ doc: result.kb_matches[0].doc_id })}>Open {result.kb_matches[0].doc_id}<ArrowUpRight />
        </Button>
      </div>
      }{!!result.related_components.length && <div className="mt-5">
        <p className="hint mb-2">Related components · check order</p>
        <div className="flex-row">{result.related_components.map(id => <code className="text-xs muted" key={id}>{id}</code>)}</div>
      </div>
      }{result.notes && <p className="hint mt-4">{uniqueNotes(result.notes)}</p>
      }</>
    }</motion.section>

}
function layer(node: TopologyNode) {
  if (node.layer !== undefined) return node.layer
  if (/consumer|client/.test(node.type)) return 0
  if (/gateway|load_balancer/.test(node.type)) return 1
  if (/integration_server|kong_data_plane|proxy/.test(node.type)) return 2
  return 3
}
export function TopologyMap({ snapshot }: { snapshot: Snapshot }) {
  const env = snapshot.context.environment
  const query = useQuery({
    queryKey: ['topology', env, snapshot.id, snapshot.pending_interrupt, snapshot.plan],
    queryFn: () => api.topology(env!, snapshot.id || undefined),
    enabled: !!env
  })

  const reduced = useReducedMotion()
  const container = useRef<HTMLDivElement>(null), from = useRef<HTMLDivElement>(null), to = useRef<HTMLDivElement>(null)
  if (!env) return <p className="panel-body muted text-sm">Select an environment to see its reviewed topology.</p>
  if (query.isPending) return <p className="panel-body muted text-sm">Loading reviewed topology…</p>
  if (query.error) return <div className="panel-body">
    <p className="muted text-sm">No reviewed topology available for {env}.</p>
    <Button
      variant="ghost"
      size="sm"
      onClick={() => void query.refetch()}>Retry topology</Button>
  </div>
  const nodes = query.data!.nodes
  const coords = new Map(nodes.map(node => {
    const peers = nodes.filter(n => layer(n) === layer(node))
    return [node.id, {
      x: 18 + peers.indexOf(node) * (360 / peers.length),
      y: 36 + layer(node) * 88,
      w: Math.min(110, 360 / peers.length - 8)
    }]
  }))

  const current = snapshot.pending_interrupt?.type === 'step' ? (snapshot.pending_interrupt.payload as PlanStep).where : nodes.find(n => n.status === 'check_next')?.id
  const edge = query.data!.edges.find(e => e.to === current) || query.data!.edges.find(e => e.from === current)
  const a = edge && coords.get(edge.from), b = edge && coords.get(edge.to)
  return <section className="panel-body border-t border-border">
    <h2 className="section-title flex-row">
      <GitBranch />Environment topology</h2>
    <p className="hint mb-4">{env} · reviewed dependency map</p>
    <div ref={container} className="relative">
      <svg
        className="topology"
        viewBox="0 0 396 350"
        role="img"
        aria-label={`Topology for ${env}. ${nodes.filter(n => n.status !== 'quiet').map(n => `${n.id}: ${n.status.replaceAll('_', ' ')}`).join(', ')}`}>
        <title>Consumers, gateways, integration servers and dependencies</title>{query.data!.edges.map((e, i) => {
          const s = coords.get(e.from), t = coords.get(e.to)
          return s && t && <path
            key={i}
            d={`M ${s.x + s.w / 2} ${s.y + 32} L ${t.x + t.w / 2} ${t.y}`}
            fill="none"
            stroke="var(--border-strong)"
            strokeWidth="1" />
        })}{nodes.map(node => {
          const p = coords.get(node.id)!
          return <motion.g
            key={`${node.id}-${node.status}`}
            className={node.status}
            initial={{ opacity: node.status === 'check_next' ? .35 : 1 }}
            animate={{ opacity: 1 }}
            transition={{ delay: reduced ? 0 : ((node.order || 1) - 1) * .12, duration: reduced ? 0 : .2 }}>
            <title>{node.id}: {humanize(node.type)} · {humanize(node.status)}</title>{node.status === 'affected' && <motion.rect
              x={p.x - 3}
              y={p.y - 3}
              width={p.w + 6}
              height="38"
              rx="8"
              style={{ fill: 'none', stroke: 'var(--accent)' }}
              animate={{ opacity: reduced ? 1 : [.25, .8, .25] }}
              transition={{ duration: 2.4, repeat: reduced ? 0 : Infinity }} />
            }<rect
              x={p.x}
              y={p.y}
              width={p.w}
              height="32"
              rx="6" />
            <text
              x={p.x + p.w / 2}
              y={p.y + 20}
              textAnchor="middle"
              style={{ fontSize: 11 }}>{node.id}</text>
          </motion.g>
        })}</svg>{a && b && !reduced && <>
          <div
            ref={from}
            className="absolute size-px pointer-events-none"
            style={{ left: `${(a.x + a.w / 2) / 396 * 100}%`, top: `${(a.y + 32) / 350 * 100}%` }} />
          <div
            ref={to}
            className="absolute size-px pointer-events-none"
            style={{ left: `${(b.x + b.w / 2) / 396 * 100}%`, top: `${b.y / 350 * 100}%` }} />
          <AnimatedBeam
            key={current}
            containerRef={container}
            fromRef={from}
            toRef={to}
            repeat={0}
            duration={1.2}
            pathColor="var(--border-strong)"
            gradientStartColor="var(--accent)"
            gradientStopColor="var(--accent)" />
        </>
      }</div>
    <div className="flex-row text-xs mt-3">
      <span className="text-accent">Affected / checked</span>
      <span className="text-warning">Check next</span>
      <span className="text-danger">Issue observed</span>
    </div>
    <p className="hint mt-3">Completed checks reflect engineer reports, not independent health verification.</p>
  </section>
}
export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(false)
  return <>
    <button
      className="icon-button"
      aria-label={copied ? 'Command copied' : 'Copy command'}
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true)
          setError(false)
        }, () => setError(true))
      }}>{copied ? <Check /> : <Copy />
      }</button>{error && <p className="text-danger text-xs mt-2" role="status">Copy unavailable. Select the command to copy it.</p>
    }</>

}
