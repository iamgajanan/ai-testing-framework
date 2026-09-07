import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { apiFetch } from '@/lib/api'

export default async function ArtifactPage({ params }: { params: Promise<{ executionId: string; artifactId: string }> }) {
  const { executionId, artifactId }=await params; const supabase=await createClient(); const { data: claims }=await supabase.auth.getClaims(); if(!claims?.claims?.sub) redirect('/login')
  const response=await apiFetch(`/v1/executions/${executionId}/artifacts/${artifactId}`); if(!response.ok) return <main className="dashboard-shell"><section className="main"><Link className="btn" href={`/dashboard/executions/${executionId}`}>← Back</Link><div className="notice error">Artifact not found or access denied.</div></section></main>
  const a=response.data
  return <main className="dashboard-shell"><aside className="sidebar"><Link className="brand" href="/dashboard"><span className="brand-mark">AI</span> AI Testing</Link><nav className="side-links"><Link className="side-link" href="/dashboard">◈ Overview</Link><Link className="side-link" href="/dashboard/projects">▦ Projects</Link><Link className="side-link" href="/dashboard/suites">◇ Test suites</Link><Link className="side-link active" href="/dashboard/executions">↗ Executions</Link><Link className="side-link" href="/dashboard/settings">⚙ Settings</Link></nav></aside><section className="main"><div className="topline page-header"><div><div className="breadcrumb"><Link href={`/dashboard/executions/${executionId}`}>Execution</Link> <span>/</span> Artifact</div><h1>{a.name}</h1><p className="page-subtitle">{a.content_type} · {Math.ceil(a.size_bytes/1024)} KB</p></div><a className="btn btn-primary" href={a.signed_url} target="_blank" rel="noreferrer">Open file ↗</a></div><div className="card artifact-view"><p>Private signed URL generated for this artifact. The link expires in {Math.round((a.expires_in??3600)/60)} minutes.</p><code>{a.storage_path}</code></div></section></main>
}
