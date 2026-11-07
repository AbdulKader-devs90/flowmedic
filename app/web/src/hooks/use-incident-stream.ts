import { useCallback, useRef, useState, useEffect } from 'react'
import { streamNames } from '@/lib/contracts'
import type { StreamEvents, StreamName } from '@/lib/contracts'
export type EventHandler = <K extends StreamName>(name: K, data: StreamEvents[K]) => void
/** A stream runs graph execution. Never auto-reconnect or run inactive incidents. */
export function useIncidentStream(onEvent: EventHandler, onEnd: () => void) {
  const source = useRef<EventSource | null>(null)
  const callbacks = useRef({ onEvent, onEnd })
  useEffect(() => { callbacks.current = { onEvent, onEnd } }, [onEvent, onEnd])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const stop = useCallback(() => { source.current?.close(); source.current = null; setRunning(false) }, [])
  const start = useCallback((id: string) => {
    source.current?.close()
    setError(null); setRunning(true)
    const events = new EventSource(`/api/incidents/${encodeURIComponent(id)}/events`)
    source.current = events
    for (const name of streamNames) events.addEventListener(name, (raw: MessageEvent<string>) => {
      if (source.current !== events) return
      // EventSource's transport error has no data; handled below.
      if (!raw.data) return
      try {
        const data = JSON.parse(raw.data) as StreamEvents[typeof name]
        callbacks.current.onEvent(name, data)
        if (name === 'error' && 'message' in data) setError(data.message)
        if (name === 'done') { events.close(); source.current = null; setRunning(false); callbacks.current.onEnd() }
      } catch { events.close(); source.current = null; setRunning(false); setError('Could not read the event stream. Refresh the checkpoint before retrying.'); callbacks.current.onEnd() }
    })
    events.onerror = () => {
      if (source.current !== events) return
      events.close(); source.current = null; setRunning(false)
      setError('Connection interrupted. The latest checkpoint has been refreshed; retry when ready.')
      callbacks.current.onEnd()
    }
  }, [])
  useEffect(() => () => { source.current?.close() }, [])
  return { running, error, start, stop }
}
