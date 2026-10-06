import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { Run, RunInput } from '../types'

export function useInvestigation() {
  const [runId, setRunId] = useState<string | null>(() => new URLSearchParams(location.search).get('run'))
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = useCallback(async (id: string) => {
    const next = await api<Run>('/runs/' + id)
    setRun(old => old?.run_id === id && old.updated_at > next.updated_at ? old : next)
    return next
  }, [])
  const choose = useCallback((id: string | null) => {
    setRunId(id)
    setRun(null)
    setError('')
    history.replaceState({}, '', id ? '?run=' + encodeURIComponent(id) : location.pathname)
  }, [])
  useEffect(() => {
    if (!runId) return
    let active = true
    let stream: EventSource | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    const update = () => { if (!timer) timer = setTimeout(() => { timer = undefined; if (active) void refresh(runId).catch(e => setError(e.message)) }, 120) }
    void refresh(runId).then(initial => {
      if (!active || initial.status !== 'investigating') return
      stream = new EventSource('/api/runs/' + runId + '/events')
      stream.addEventListener('update', update)
      stream.addEventListener('done', () => { stream?.close(); if (active) void refresh(runId).catch(e => setError(e.message)) })
      stream.onerror = () => { if (active) setError('Progress connection interrupted. Reconnecting…') }
      stream.onopen = () => { if (active) setError('') }
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false; stream?.close(); clearTimeout(timer) }
  }, [runId, refresh])

  // Explicitly reconnect after a mutation restarts an existing run.
  const generation = useRef(0)
  const mutate = async (path: string, body: unknown) => {
    setBusy(true); setError('')
    try {
      const result = await api<{run_id:string}>(path, body)
      const next = await refresh(result.run_id)
      if (result.run_id !== runId) choose(result.run_id)
      else {
        const current = ++generation.current
        while (next.status === 'investigating' && current === generation.current) {
          await new Promise(resolve => setTimeout(resolve, 350))
          const updated = await refresh(result.run_id)
          if (updated.status !== 'investigating') break
        }
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Investigation failed.') }
    finally { setBusy(false) }
  }
  return { run, error, busy, create: (input: RunInput) => mutate('/runs', input),
    clarify: (body: unknown) => mutate('/runs/' + runId + '/clarifications', body),
    addOffer: (part_number: string) => mutate('/runs/' + runId + '/offers', {part_number}),
    reset: () => { generation.current++; choose(null) } }
}

