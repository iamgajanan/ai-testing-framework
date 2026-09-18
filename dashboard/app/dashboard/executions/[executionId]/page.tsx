import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { apiFetch } from '@/lib/api'
import { StatusPoller } from './status-poller'
import { ExecutionActions } from './execution-actions'

function statusBadge(status: string) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    queued:    { bg: '#fef3c7', color: '#92400e', label: '⏳ Queued' },
    running:   { bg: '#dbeafe', color: '#1e40af', label: '▶ Running' },
    passed:    { bg: '#dcfce7', color: '#166534', label: '✅ Passed' },
    failed:    { bg: '#fee2e2', color: '#991b1b', label: '❌ Failed' },
    cancelled: { bg: '#f3f4f6', color: '#4b5563', label: '⊘ Cancelled' },
  }
  const s = map[status] ?? { bg: '#f3f4f6', color: '#374151', label: status }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '4px 12px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: s.bg,
        color: s.color,
      }}
    >
      {s.label}
    </span>
  )
}

function formatDuration(startedAt: string | null, finishedAt: string | null) {
  if (!startedAt) return null
  const start = new Date(startedAt).getTime()
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  const secs = Math.round((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

export default async function ExecutionDetailPage({
  params,
}: {
  params: Promise<{ executionId: string }>
}) {
  const { executionId } = await params
  const supabase = await createClient()
  const { data: claims } = await supabase.auth.getClaims()
  if (!claims?.claims?.sub) redirect('/login')

  const res = await apiFetch(`/v1/executions/${executionId}`)
  if (!res.ok) {
    return (
      <main className="dashboard-shell">
        <aside className="sidebar">
          <Link className="brand" href="/dashboard">
            <span className="brand-mark">AI</span> AI Testing
          </Link>
          <nav className="side-links">
            <Link className="side-link" href="/dashboard">◈ Overview</Link>
            <Link className="side-link" href="/dashboard/projects">▦ Projects</Link>
            <Link className="side-link" href="/dashboard/suites">◇ Test suites</Link>
            <Link className="side-link active" href="/dashboard/executions">↗ Executions</Link>
            <Link className="side-link" href="/dashboard/settings">⚙ Settings</Link>
          </nav>
        </aside>
        <section className="main">
          <Link className="btn" href="/dashboard/executions">← Executions</Link>
          <div className="notice error" style={{ marginTop: 16 }}>Execution not found.</div>
        </section>
      </main>
    )
  }

  const exec = res.data
  const artifactsRes = await apiFetch(`/v1/executions/${executionId}/artifacts`)
  const artifacts: any[] = Array.isArray(artifactsRes.data) ? artifactsRes.data : []
  const duration = formatDuration(exec.started_at, exec.finished_at)
  const result = exec.result as Record<string, any> | null

  // Parse test-level results if present
  const testResults: any[] = result?.results ?? []

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">AI</span> AI Testing
        </Link>
        <nav className="side-links">
          <Link className="side-link" href="/dashboard">◈ Overview</Link>
          <Link className="side-link" href="/dashboard/projects">▦ Projects</Link>
          <Link className="side-link" href="/dashboard/suites">◇ Test suites</Link>
          <Link className="side-link active" href="/dashboard/executions">↗ Executions</Link>
          <Link className="side-link" href="/dashboard/settings">⚙ Settings</Link>
        </nav>
      </aside>

      <section className="main">
        {/* Auto-refresh while queued/running */}
        <StatusPoller status={exec.status} />

        <ExecutionActions executionId={executionId} status={exec.status} />

        <div className="topline page-header">
          <div>
            <div className="breadcrumb">
              <Link href="/dashboard/executions">Executions</Link>
              <span>/</span>
              {executionId.slice(0, 8)}
            </div>
            <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              Execution {executionId.slice(0, 8)}
              {statusBadge(exec.status)}
            </h1>
            <p className="page-subtitle">
              {exec.browser} · {exec.base_url || 'no base URL'}
              {duration && ` · ${duration}`}
            </p>
          </div>
          <Link className="btn" href="/dashboard/executions">← All executions</Link>
        </div>

        {/* Timestamps + summary */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
            <Stat label="Status" value={exec.status} />
            <Stat label="Browser" value={exec.browser} />
            <Stat label="Workers" value={String(exec.workers ?? 1)} />
            <Stat
              label="Queued"
              value={exec.created_at ? new Date(exec.created_at).toLocaleString() : '—'}
            />
            <Stat
              label="Started"
              value={exec.started_at ? new Date(exec.started_at).toLocaleString() : '—'}
            />
            <Stat
              label="Finished"
              value={exec.finished_at ? new Date(exec.finished_at).toLocaleString() : '—'}
            />
            {duration && <Stat label="Duration" value={duration} />}
            {result && (
              <>
                <Stat label="Total tests" value={String(result.total ?? '—')} />
                <Stat
                  label="Passed"
                  value={String(result.passed ?? '—')}
                  valueColor="#166534"
                />
                <Stat
                  label="Failed"
                  value={String(result.failed ?? '—')}
                  valueColor={result.failed ? '#991b1b' : undefined}
                />
              </>
            )}
          </div>
        </div>

        {/* Error message */}
        {exec.error && (
          <div className="notice error" style={{ marginBottom: 16 }}>
            <strong>Execution error:</strong> {exec.error}
          </div>
        )}

        {/* Live status indicator */}
        {(exec.status === 'queued' || exec.status === 'running') && (
          <div className="notice" style={{ marginBottom: 16, background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e40af' }}>
            {exec.status === 'queued'
              ? '⏳ Waiting for an available worker…'
              : '▶ Worker is running tests — this page refreshes automatically.'}
          </div>
        )}

        {/* Test-by-test results */}
        {testResults.length > 0 && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-heading" style={{ marginBottom: 12 }}>
              <div>
                <div className="panel-kicker">TEST RESULTS</div>
                <h2>Tests</h2>
              </div>
              <span className="muted">{testResults.length} test{testResults.length !== 1 ? 's' : ''}</span>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--line-soft)' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--muted)', fontWeight: 500 }}>ID</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--muted)', fontWeight: 500 }}>Name</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--muted)', fontWeight: 500 }}>Status</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: 'var(--muted)', fontWeight: 500 }}>Duration</th>
                </tr>
              </thead>
              <tbody>
                {testResults.map((t: any, i: number) => (
                  <tr
                    key={t.id ?? i}
                    style={{ borderBottom: '1px solid var(--line-soft)', opacity: 0.95 }}
                  >
                    <td style={{ padding: '8px 8px', fontFamily: 'monospace', fontSize: 11, color: 'var(--muted)' }}>
                      {t.id ?? `T${i + 1}`}
                    </td>
                    <td style={{ padding: '8px 8px' }}>{t.name ?? '—'}</td>
                    <td style={{ padding: '8px 8px' }}>
                      {t.status === 'PASS' || t.status === 'passed'
                        ? <span style={{ color: '#166534', fontWeight: 600 }}>✅ PASS</span>
                        : <span style={{ color: '#991b1b', fontWeight: 600 }}>❌ FAIL</span>}
                      {t.error && (
                        <span style={{ display: 'block', fontSize: 11, color: '#991b1b', marginTop: 2 }}>{t.error}</span>
                      )}
                    </td>
                    <td style={{ padding: '8px 8px', textAlign: 'right', color: 'var(--muted)', fontSize: 12 }}>
                      {t.duration != null ? `${t.duration.toFixed(1)}s` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Artifacts */}
        {artifacts.length > 0 && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-heading" style={{ marginBottom: 12 }}>
              <div>
                <div className="panel-kicker">ARTIFACTS</div>
                <h2>Files</h2>
              </div>
              <span className="muted">{artifacts.length} file{artifacts.length !== 1 ? 's' : ''}</span>
            </div>
            <div className="activity-list">
              {artifacts.map((a: any) => (
                <Link
                  key={a.id}
                  className="activity-row"
                  href={`/dashboard/executions/${executionId}/artifacts/${a.id}`}
                >
                  <span style={{ fontSize: 18 }}>{artifactIcon(a.content_type, a.name)}</span>
                  <div>
                    <strong style={{ fontSize: 13 }}>{a.name}</strong>
                    <small style={{ display: 'block', color: 'var(--muted)', fontSize: 11 }}>
                      {a.content_type} · {Math.ceil(a.size_bytes / 1024)} KB
                    </small>
                  </div>
                  <span style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: 11 }}>
                    {a.created_at ? new Date(a.created_at).toLocaleTimeString() : ''}
                  </span>
                  <span style={{ color: 'var(--muted)' }}>→</span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Raw result JSON for debugging */}
        {result && testResults.length === 0 && (
          <div className="card">
            <div className="panel-kicker" style={{ marginBottom: 8 }}>RAW RESULT</div>
            <pre style={{ fontSize: 11, overflow: 'auto', maxHeight: 400, color: '#9eabc0' }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </section>
    </main>
  )
}

function Stat({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <div>
      <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: valueColor ?? 'inherit' }}>
        {value}
      </div>
    </div>
  )
}

function artifactIcon(contentType: string, name: string): string {
  const ct = (contentType ?? '').toLowerCase()
  if (ct === 'text/html') return '📄'
  if (ct.startsWith('video/')) return '🎬'
  if (ct.startsWith('image/')) return '🖼'
  if (ct === 'application/json' || name.endsWith('.json')) return '{ }'
  if (ct.startsWith('text/')) return '📝'
  return '📁'
}
