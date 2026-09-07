'use server'

import Link from 'next/link'
import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'
import { createClient } from '@/lib/supabase/server'
import SignOutButton from '../sign-out-button'

const API_BASE_URL = process.env.AI_TESTING_API_URL || 'http://127.0.0.1:8000'

export async function uploadSuite(formData: FormData) {
  const supabase = await createClient()
  const { data: claimsData } = await supabase.auth.getClaims()
  if (!claimsData?.claims?.sub) redirect('/login')

  const projectId = String(formData.get('project_id') || '')
  const file = formData.get('file')
  const name = String(formData.get('name') || '').trim()
  if (!projectId || !(file instanceof File) || file.size === 0) redirect(`/dashboard/suites?error=missing_file&project=${encodeURIComponent(projectId)}`)
  if (file.size > 10 * 1024 * 1024) redirect(`/dashboard/suites?error=file_too_large&project=${encodeURIComponent(projectId)}`)

  const { data: sessionData } = await supabase.auth.getSession()
  const accessToken = sessionData.session?.access_token
  if (!accessToken) redirect('/login')

  const body = new FormData()
  body.append('file', file, file.name)
  if (name) body.append('name', name)

  try {
    const response = await fetch(`${API_BASE_URL}/v1/projects/${encodeURIComponent(projectId)}/test-suites`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` },
      body,
      cache: 'no-store',
    })
    if (!response.ok) {
      let detail = 'upload_failed'
      try { const payload = await response.json(); if (typeof payload?.detail === 'string') detail = payload.detail } catch {}
      console.error('Suite upload failed:', response.status, detail)
      redirect(`/dashboard/suites?error=${encodeURIComponent(detail)}&project=${encodeURIComponent(projectId)}`)
    }
  } catch (error) {
    console.error('Suite upload request failed:', error)
    redirect(`/dashboard/suites?error=api_unreachable&project=${encodeURIComponent(projectId)}`)
  }

  revalidatePath('/dashboard/suites')
  revalidatePath(`/dashboard/projects/${projectId}`)
  redirect(`/dashboard/suites?uploaded=1&project=${encodeURIComponent(projectId)}`)
}

export default async function SuitesPage({ searchParams }: { searchParams: Promise<{ uploaded?: string; error?: string; project?: string }> }) {
  const supabase = await createClient()
  const { data: claimsData } = await supabase.auth.getClaims()
  if (!claimsData?.claims?.sub) redirect('/login')
  const params = await searchParams

  const { data: organizations } = await supabase.from('organizations').select('id,name').order('created_at', { ascending: true }).limit(1)
  const organization = organizations?.[0]
  const { data: projects } = organization
    ? await supabase.from('projects').select('id,name,slug').eq('organization_id', organization.id).order('created_at', { ascending: true })
    : { data: [] }
  const selectedProject = projects?.find((project) => project.id === params.project) || projects?.[0]

  const { data: suites } = selectedProject
    ? await supabase.from('test_suites').select('id,name,slug,created_at,updated_at').eq('project_id', selectedProject.id).order('updated_at', { ascending: false })
    : { data: [] }
  const suiteRows = await Promise.all((suites || []).map(async (suite) => {
    const { data: versions } = await supabase.from('test_suite_versions').select('version,filename,size_bytes,sha256,created_at').eq('test_suite_id', suite.id).order('version', { ascending: false }).limit(1)
    return { ...suite, latest: versions?.[0] || null }
  }))

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard"><span className="brand-mark">AI</span><span>AI Testing</span></Link>
        <div className="workspace-switcher"><span className="workspace-dot" /><div><small>Workspace</small><strong>{organization?.name || 'My Workspace'}</strong></div><span className="chevron">⌄</span></div>
        <nav className="side-links">
          <Link className="side-link" href="/dashboard"><span>⌂</span>Overview</Link>
          <Link className="side-link" href="/dashboard/projects"><span>◈</span>Projects</Link>
          <Link className="side-link active" href="/dashboard/suites"><span>◇</span>Test suites</Link>
          <Link className="side-link" href="/dashboard/executions"><span>◌</span>Executions</Link>
          <Link className="side-link" href="/dashboard/settings"><span>⚙</span>Settings</Link>
        </nav>
        <div className="sidebar-bottom"><div className="plan-card"><span>FREE PLAN</span><strong>Build your first test suite</strong><small>Upload a JSON or YAML suite and run it against your application.</small></div><SignOutButton /></div>
      </aside>

      <section className="main">
        <header className="topline page-header">
          <div><div className="breadcrumb">Workspace <span>/</span> Test suites</div><h1>Test suites</h1><p className="page-subtitle">Upload versioned JSON or YAML test suites and keep every revision traceable.</p></div>
          {selectedProject && <a className="btn btn-primary" href="#upload-suite">＋ Upload suite</a>}
        </header>

        {params.uploaded === '1' && <div className="notice success">Suite uploaded successfully. A new immutable version has been created.</div>}
        {params.error && <div className="notice error">{params.error === 'api_unreachable' ? 'The testing API is not reachable. Start the FastAPI server on port 8000 and try again.' : params.error === 'missing_file' ? 'Choose a JSON, YAML, or YML test suite before uploading.' : params.error === 'file_too_large' ? 'The suite is larger than the 10 MB limit.' : `Upload failed: ${params.error}`}</div>}

        {!projects?.length ? (
          <section className="empty-state"><div className="empty-orb"><span>◇</span></div><span className="eyebrow">NO PROJECT YET</span><h2>Create a project before uploading suites.</h2><p>Your test suites are scoped to a project so executions and artifacts stay isolated.</p><Link className="btn btn-primary" href="/dashboard/projects#new-project">Create project <span>→</span></Link></section>
        ) : (
          <>
            <div className="project-toolbar"><div><span className="muted">Project</span><div className="suite-project-name">{selectedProject?.name}</div></div><div className="suite-count">{suiteRows.length} suite{suiteRows.length === 1 ? '' : 's'}</div></div>
            {suiteRows.length ? <div className="suite-grid">{suiteRows.map((suite) => <article className="suite-card" key={suite.id}><div className="suite-card-top"><div className="suite-icon">◇</div><span className="status-pill">v{suite.latest?.version || 0}</span></div><h3>{suite.name}</h3><p>{suite.latest?.filename || suite.slug}</p><div className="suite-meta"><span>Latest version <b>v{suite.latest?.version || 0}</b></span><span>{suite.latest ? `${Math.max(1, Math.ceil((suite.latest.size_bytes || 0) / 1024))} KB` : '—'}</span></div><div className="suite-hash" title={suite.latest?.sha256 || ''}>{suite.latest?.sha256 ? `SHA-256 ${suite.latest.sha256.slice(0, 12)}…` : 'No version uploaded'}</div></article>)}</div> : <section className="empty-state compact"><div className="empty-orb"><span>✦</span></div><span className="eyebrow">READY TO UPLOAD</span><h2>Your first test suite starts here.</h2><p>Upload a JSON, YAML, or YML suite. Each upload becomes a new immutable version with a SHA-256 fingerprint.</p><a className="btn btn-primary" href="#upload-suite">Upload first suite <span>→</span></a></section>}
            <section className="upload-panel" id="upload-suite"><div><span className="eyebrow">NEW VERSION</span><h2>Upload a test suite</h2><p>Maximum 10 MB · UTF-8 · JSON, YAML or YML</p></div><form action={uploadSuite} className="suite-upload-form" encType="multipart/form-data"><input type="hidden" name="project_id" value={selectedProject?.id || ''} /><div className="upload-fields"><div className="field"><label htmlFor="suite-name">Suite name <span>(optional)</span></label><input id="suite-name" name="name" placeholder="e.g. Customer Portal Smoke" maxLength={120} /></div><div className="field"><label htmlFor="suite-file">Test suite file</label><input id="suite-file" name="file" type="file" accept=".json,.yaml,.yml,application/json,text/yaml" required /></div></div><button className="btn btn-primary" type="submit">Upload suite <span>↑</span></button></form></section>
          </>
        )}
      </section>
    </main>
  )
}
