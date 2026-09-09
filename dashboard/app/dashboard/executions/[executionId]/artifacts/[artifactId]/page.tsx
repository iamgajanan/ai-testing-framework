import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { apiFetch } from '@/lib/api'
import { ArtifactViewer } from './viewer'

export default async function ArtifactPage({
  params,
}: {
  params: Promise<{ executionId: string; artifactId: string }>
}) {
  const { executionId, artifactId } = await params
  const supabase = await createClient()
  const { data: claims } = await supabase.auth.getClaims()
  if (!claims?.claims?.sub) redirect('/login')

  const response = await apiFetch(
    `/v1/executions/${executionId}/artifacts/${artifactId}?expires_in=3600`,
  )
  if (!response.ok) {
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
          <Link className="btn" href={`/dashboard/executions/${executionId}`}>← Back</Link>
          <div className="notice error" style={{ marginTop: 16 }}>
            Artifact not found or access denied.
          </div>
        </section>
      </main>
    )
  }

  const artifact = response.data

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
        <div className="topline page-header">
          <div>
            <div className="breadcrumb">
              <Link href={`/dashboard/executions`}>Executions</Link>
              <span>/</span>
              <Link href={`/dashboard/executions/${executionId}`}>
                {executionId.slice(0, 8)}
              </Link>
              <span>/</span>
              Artifact
            </div>
            <h1>{artifact.name}</h1>
            <p className="page-subtitle">
              {artifact.content_type} · {Math.ceil(artifact.size_bytes / 1024)} KB ·{' '}
              expires in {Math.round((artifact.expires_in ?? 3600) / 60)} min
            </p>
          </div>
          <a
            className="btn btn-primary"
            href={artifact.signed_url}
            download={artifact.name}
            target="_blank"
            rel="noreferrer"
          >
            ↓ Download
          </a>
        </div>

        <ArtifactViewer artifact={artifact} />
      </section>
    </main>
  )
}
