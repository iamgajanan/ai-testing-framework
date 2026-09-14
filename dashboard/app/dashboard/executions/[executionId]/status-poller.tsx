'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * StatusPoller — invisible client component that refreshes the page every
 * 3 seconds while the execution status is queued or running.
 *
 * When the execution reaches a terminal state (passed / failed / cancelled)
 * polling stops automatically. No manual reload needed.
 */
export function StatusPoller({ status }: { status: string }) {
  const router = useRouter()
  const isLive = status === 'queued' || status === 'running'

  useEffect(() => {
    if (!isLive) return
    const id = setInterval(() => router.refresh(), 3000)
    return () => clearInterval(id)
  }, [isLive, router])

  if (!isLive) return null

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 11,
        color: 'var(--muted)',
        marginLeft: 8,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: status === 'running' ? '#22c55e' : '#f59e0b',
          animation: 'pulse 1.4s ease-in-out infinite',
        }}
      />
      live
    </span>
  )
}
