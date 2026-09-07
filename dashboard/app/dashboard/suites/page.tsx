import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { uploadSuite } from './actions'
import { UploadSubmit } from './upload-submit'
import styles from './suites.module.css'

export default async function SuitesPage({ searchParams }: { searchParams: Promise<{ project?: string; error?: string; uploaded?: string }> }) {
  const params = await searchParams
  const supabase = await createClient()
  const { data: claims } = await supabase.auth.getClaims()
  if (!claims?.claims?.sub) redirect('/login')

  const { data: orgs } = await supabase.from('organizations').select('id,name').order('created_at').limit(1)
  const org = orgs?.[0]
  const { data: projects } = org ? await supabase.from('projects').select('id,name').eq('organization_id', org.id).order('created_at') : { data: [] }
  const project = projects?.find((p) => p.id === params.project) ?? projects?.[0]
  const { data: suites } = project
    ? await supabase.from('test_suites').select('id,name,slug,test_suite_versions(version,filename,size_bytes,sha256)').eq('project_id', project.id).order('created_at', { ascending: false })
    : { data: [] }

  const errorMessage = params.error === 'api_unreachable'
    ? 'Testing API is not reachable. Start FastAPI on port 8000/8001 or set AI_TESTING_API_URL.'
    : params.error === 'backend_config'
      ? 'FastAPI is running, but its Supabase configuration is incomplete. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY (or SUPABASE_ANON_KEY) in the FastAPI environment, then restart FastAPI.'
      : params.error === 'file_too_large'
        ? 'This suite exceeds the 10 MB upload limit.'
        : params.error === 'unsupported_file'
          ? 'Only JSON, YAML and YML suite files are supported.'
          : params.error === 'not_authorized'
            ? 'You are not authorized to upload a suite to this project.'
            : params.error === 'missing_file'
              ? 'Choose a suite file before uploading.'
              : params.error === 'upload_failed'
                ? 'The suite could not be uploaded. Check the FastAPI logs for the exact Supabase response.'
                : null

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard"><span className="brand-mark">AI</span> AI Testing</Link>
        <div className="workspace-switcher"><span className="workspace-dot" /><div><small>Workspace</small><strong>{org?.name ?? 'My Workspace'}</strong></div></div>
        <nav className="side-links">
          <Link className="side-link" href="/dashboard">◈ Overview</Link>
          <Link className="side-link" href="/dashboard/projects">▦ Projects</Link>
          <Link className="side-link active" href="/dashboard/suites">◇ Test suites</Link>
          <Link className="side-link" href="/dashboard/executions">↗ Executions</Link>
          <Link className="side-link" href="/dashboard/settings">⚙ Settings</Link>
        </nav>
      </aside>

      <section className="main">
        <div className="topline page-header">
          <div><div className="breadcrumb">Workspace <span>/</span> Test suites</div><h1>Test suites</h1><p className="page-subtitle">Build a versioned library of JSON/YAML tests and launch them against any environment.</p></div>
          <div className="header-actions"><Link className="btn" href="/dashboard/projects">Projects</Link><Link className="btn btn-primary" href="/dashboard/executions">Run a test →</Link></div>
        </div>

        {errorMessage && <div className="notice error" role="alert">{errorMessage}</div>}
        {params.uploaded && <div className="notice success" role="status">Suite uploaded successfully. A new immutable version is now available.</div>}

        {!project ? (
          <div className="empty-state">
            <div className="empty-orb">◇</div><h2>Start with a project</h2><p>Your suite library is organized by project. Create one to upload your first test definition.</p><Link className="btn btn-primary" href="/dashboard/projects">Create project →</Link>
          </div>
        ) : (
          <div className="suite-layout">
            <div>
              <div className="section-heading"><div><div className="eyebrow">{project.name}</div><h2>Suite library</h2></div><span className="muted">{suites?.length ?? 0} suite{(suites?.length ?? 0) === 1 ? '' : 's'}</span></div>
              <div className="suite-grid">
                {(suites ?? []).map((s) => {
                  const versions = [...(s.test_suite_versions ?? [])].sort((a, b) => b.version - a.version)
                  const v = versions[0]
                  return <article className="suite-card" key={s.id}>
                    <div className="suite-card-top"><div className="suite-icon">⌘</div><span className="status-pill">v{v?.version ?? 0}</span></div>
                    <h3>{s.name}</h3><p>{v?.filename ?? 'No file uploaded'}</p>
                    <div className="suite-meta"><span>{versions.length} version{versions.length === 1 ? '' : 's'}</span><span>{v ? `${Math.max(1, Math.ceil(v.size_bytes / 1024))} KB` : '—'}</span></div>
                    {v && <code className="hash">sha256 {v.sha256.slice(0, 16)}…</code>}
                    <div className={styles.actions}>
                      <Link className={`${styles.action}`} href={`/dashboard/suites/${s.id}?project=${project.id}`}>Versions <span>→</span></Link>
                      <Link className={`${styles.action} ${styles.primary}`} href={`/dashboard/executions?project=${project.id}&suite=${s.id}`}>Run <span>↗</span></Link>
                    </div>
                  </article>
                })}
                {!suites?.length && <div className="mini-empty card"><div>◇</div><strong>Your suite library is empty</strong><span>Upload a JSON or YAML definition to create version 1.</span></div>}
              </div>
            </div>

            <div className="upload-panel card">
              <div className="panel-kicker">NEW SUITE VERSION</div><h2>Upload a suite</h2><p>Every upload creates an immutable version with a SHA-256 fingerprint.</p>
              <form action={uploadSuite} className="upload-form">
                <input type="hidden" name="project_id" value={project.id} />
                <div className="field"><label htmlFor="suite-name">Suite name <span>optional</span></label><input id="suite-name" name="name" placeholder="Checkout regression" maxLength={120} /></div>
                <label className={`file-drop ${styles.drop}`} htmlFor="suite-file"><div className="upload-glyph">↑</div><strong>Choose suite file</strong><span>JSON, YAML or YML · up to 10 MB</span><input id="suite-file" required type="file" name="file" accept=".json,.yaml,.yml,application/json,text/yaml" /></label>
                <UploadSubmit />
              </form>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
