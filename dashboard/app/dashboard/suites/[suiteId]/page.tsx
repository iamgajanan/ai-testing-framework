import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { apiFetch } from '@/lib/api'
import { SuiteActions } from './suite-actions'

export default async function SuiteDetailPage({
  params,
}: {
  params: Promise<{ suiteId: string }>
}) {
  const { suiteId } = await params
  const supabase = await createClient()
  const { data: claims } = await supabase.auth.getClaims()
  if (!claims?.claims?.sub) redirect('/login')

  const { data: suite } = await supabase
    .from('test_suites')
    .select('id,name,slug,project_id,created_at,updated_at')
    .eq('id', suiteId)
    .single()
  if (!suite) notFound()

  const { data: project } = await supabase
    .from('projects')
    .select('id,name,organization_id')
    .eq('id', suite.project_id)
    .single()

  const { data: versions } = await supabase
    .from('test_suite_versions')
    .select('id,version,filename,content_type,size_bytes,sha256,created_at')
    .eq('test_suite_id', suiteId)
    .order('version', { ascending: false })

  const latestVersion = versions?.[0]?.version ?? null

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">AI</span> AI Testing
        </Link>
        <nav className="side-links">
          <Link className="side-link" href="/dashboard">◈ Overview</Link>
          <Link className="side-link" href="/dashboard/projects">▦ Projects</Link>
          <Link className="side-link active" href="/dashboard/suites">◇ Test suites</Link>
          <Link className="side-link" href="/dashboard/executions">↗ Executions</Link>
          <Link className="side-link" href="/dashboard/generate">✦ Generate</Link>
          <Link className="side-link" href="/dashboard/settings">⚙ Settings</Link>
        </nav>
      </aside>

      <section className="main">
        <div className="topline page-header">
          <div>
            <div className="breadcrumb">
              <Link href="/dashboard/suites">Test suites</Link>
              <span>/</span>
              {suite.name}
            </div>
            <h1>{suite.name}</h1>
            <p className="page-subtitle">
              {project?.name ?? 'Project'} · {versions?.length ?? 0} version
              {(versions?.length ?? 0) !== 1 ? 's' : ''}
              {suite.updated_at && ` · updated ${new Date(suite.updated_at).toLocaleDateString()}`}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {latestVersion && (
              <Link
                className="btn btn-primary"
                href={`/dashboard/executions?project=${suite.project_id}&suite=${suiteId}`}
              >
                Run latest →
              </Link>
            )}
          </div>
        </div>

        {/* Rename / Delete actions */}
        <SuiteActions
          suiteId={suiteId}
          projectId={suite.project_id}
          currentName={suite.name}
        />

        {/* Version history */}
        <div className="card" style={{ marginTop: 16 }}>
          <div className="section-heading" style={{ marginBottom: 12 }}>
            <div>
              <div className="panel-kicker">VERSION HISTORY</div>
              <h2>Immutable versions</h2>
            </div>
            <Link
              className="btn"
              href={`/dashboard/suites?upload=${suite.project_id}`}
            >
              + Upload new version
            </Link>
          </div>

          {versions?.length ? (
            <div className="version-list">
              {versions.map((v: any) => (
                <div className="version-row" key={v.id} style={{ gap: 12 }}>
                  <div className="version-badge">v{v.version}</div>
                  <div style={{ flex: 1 }}>
                    <strong style={{ fontSize: 13 }}>{v.filename}</strong>
                    <small style={{ display: 'block', color: 'var(--muted)', fontSize: 11, marginTop: 2 }}>
                      {v.content_type} · {Math.ceil(v.size_bytes / 1024)} KB ·{' '}
                      {new Date(v.created_at).toLocaleString()}
                    </small>
                    <code style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginTop: 2 }}>
                      SHA-256: {v.sha256.slice(0, 16)}…
                    </code>
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <Link
                      className="btn"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      href={`/dashboard/executions?project=${suite.project_id}&suite=${suiteId}&version=${v.version}`}
                    >
                      Run v{v.version}
                    </Link>
                    <Link
                      className="btn"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      href={`/dashboard/suites/${suiteId}/versions/${v.version}/download`}
                    >
                      ↓ Download
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mini-empty">
              <strong>No versions yet</strong>
              <p>Upload a test suite JSON file to create the first version.</p>
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
