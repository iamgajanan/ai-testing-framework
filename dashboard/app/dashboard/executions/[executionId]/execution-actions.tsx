'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

interface Props {
  executionId: string
  status: string
}

export function ExecutionActions({ executionId, status }: Props) {
  const router = useRouter()
  const [busy, setBusy] = useState<'cancel' | 'retry' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isQueued    = status === 'queued'
  const isTerminal  = ['passed', 'failed', 'cancelled'].includes(status)
  const canCancel   = isQueued
  const canRetry    = status === 'failed' || status === 'cancelled'

  if (!canCancel && !canRetry) return null

  async function cancel() {
    setBusy('cancel'); setError(null)
    try {
      const res = await fetch(`/api/executions/${executionId}/cancel`, { method: 'POST' })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail ?? 'Cancel failed')
      }
      router.refresh()
    } catch (e: any) { setError(String(e.message ?? e)) }
    finally { setBusy(null) }
  }

  async function retry() {
    setBusy('retry'); setError(null)
    try {
      const res = await fetch(`/api/executions/${executionId}/retry`, { method: 'POST' })
      const d = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(d.detail ?? 'Retry failed')
      // Navigate to the new execution
      if (d.id) router.push(`/dashboard/executions/${d.id}`)
      else router.push('/dashboard/executions')
    } catch (e: any) { setError(String(e.message ?? e)) }
    finally { setBusy(null) }
  }

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
      {error && (
        <span style={{ fontSize: 12, color: '#ef4444', marginRight: 4 }}>{error}</span>
      )}
      {canCancel && (
        <button
          className="btn"
          onClick={cancel}
          disabled={busy !== null}
          style={{ color: '#ef4444', borderColor: '#fca5a5' }}
        >
          {busy === 'cancel' ? 'Cancelling…' : '⊘ Cancel'}
        </button>
      )}
      {canRetry && (
        <button
          className="btn btn-primary"
          onClick={retry}
          disabled={busy !== null}
        >
          {busy === 'retry' ? 'Queuing…' : '↺ Retry'}
        </button>
      )}
    </div>
  )
}
