import { displayPath, trustHints } from '@/lib/display'
import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, FileSearch, ExternalLink } from 'lucide-react'
import * as Dialog from '@radix-ui/react-dialog'
import { motion, useReducedMotion } from 'framer-motion'
import { api } from '@/lib/api'
import type { Snapshot } from '@/lib/contracts'
import { Button } from './ui/button'
export interface EvidenceTarget { file?: string; line?: number; doc?: string }
function MaskedText({ text, signature }: { text: string; signature?: string | null }) {
  return <>{text.split(/(\[REDACTED(?: PRIVATE KEY)?\]|\*{3,}|••••)/g).map((part, i) => /REDACTED|^\*{3,}$|^••••$/.test(part) ? <span
    key={i}
    className="mask"
    aria-label="Masked secret">••••</span> : signature && part.includes(signature) ? part.split(signature).map((piece, j, a) => <span key={`${i}-${j}`}>{piece}{j < a.length - 1 && <mark>{signature}</mark>
    }</span>) : <span key={i}>{part}</span>)}</>

}
export function EvidenceDrawer({ target, snapshot, close }: {
  target: EvidenceTarget | null
  snapshot?: Snapshot
  close: () => void
}) {
  const reduced = useReducedMotion()
  const lineRef = useRef<HTMLDivElement>(null)
  const doc = useQuery({
    queryKey: ['knowledge', target?.doc],
    queryFn: () => api.knowledge(target!.doc!),
    enabled: !!target?.doc
  })

  useEffect(() => {
    if (target?.line) lineRef.current?.scrollIntoView({ block: 'center', behavior: reduced ? 'instant' : 'smooth' })
  }, [target, reduced])

  const lines = snapshot?.evidence.filter(line => !target?.file || line.source_file === target.file || line.source_file.endsWith(target.file)) || []
  return <Dialog.Root open={!!target} onOpenChange={open => {
    if (!open) close()
  }}>
    <Dialog.Portal>
      <Dialog.Overlay className="overlay" />
      <Dialog.Content asChild>
        <motion.aside
          initial={{ x: reduced ? 0 : 32, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: reduced ? 0 : .2, ease: 'easeOut' }}
          className="drawer">
          <header className="drawer-head">
            <div className="min-w-0">
              <Dialog.Title className="text-lg break-words">{target?.doc || displayPath(target?.file || 'Incident evidence', snapshot?.display_root)}</Dialog.Title>
              <Dialog.Description className="hint">{target?.doc ? 'Knowledge document · repository source' : 'Masked diagnostic excerpts · original line references'}</Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="Close evidence">
              <X />
            </Dialog.Close>
          </header>{target?.doc ? <div className="panel-body">{doc.isPending && <p className="muted">Opening knowledge document…</p>
          }{doc.error && <div className="error">{doc.error.message}<Button variant="outline" onClick={() => void doc.refetch()}>Retry</Button>
          </div>
            }{doc.data && <>
              <h2 className="section-title">{doc.data.title}</h2>
              <div title={doc.data.front_matter.verified ? trustHints.verified : 'This document has not been verified.'} className={`badge mb-5 ${doc.data.front_matter.verified ? 'verified' : ''}`}>{doc.data.front_matter.verified ? 'Verified' : 'Unreviewed'} · {doc.data.type}</div>
              <div className="space-y-3 text-sm">{doc.data.body.split('\n').map((line, i) => line.startsWith('#') ? <h3 key={i} className="text-lg pt-4">{line.replace(/^#+\s*/, '')}</h3> : <p key={i} className={line.startsWith('```') ? 'mono muted' : 'whitespace-pre-wrap break-words'}>{line}</p>)}</div>
            </>
            }</div> : <>
            <div className="panel-body">
              <div className="flex-row muted text-sm">
                <FileSearch />{lines.length} captured lines</div>
              <p className="hint mt-2">Evidence excerpts only; gaps do not imply an empty log.</p>
            </div>{!lines.length && <p className="panel-body muted">No captured lines match this reference. Choose another evidence link.</p>
            }{lines.map((line, i) => <div
              ref={line.line_no === target?.line ? lineRef : undefined}
              className={`log-line ${line.line_no === target?.line ? 'target' : ''}`}
              key={`${line.source_file}-${line.line_no}-${i}`}>
              <span className="muted text-right" aria-label={`Line ${line.line_no}`}>{line.line_no}</span>
              <div>{!target?.file && <p className="hint mb-1">{displayPath(line.source_file, snapshot?.display_root)}</p>
              }<MaskedText text={line.text} signature={line.signature} />
              </div>
            </div>)}{!!snapshot?.flags.length && <section className="flag-strip">
              <h3 className="text-sm mb-3">Ignored: instruction-like text in log</h3>{snapshot.flags.map((flag, i) => <pre className="text-xs mb-2" key={i}>
                <MaskedText text={flag} />
              </pre>)}</section>
            }</>
          }<footer className="panel-body hint flex-row">
            <ExternalLink />Diagnostic text is displayed as text, never executed.</footer>
        </motion.aside>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
