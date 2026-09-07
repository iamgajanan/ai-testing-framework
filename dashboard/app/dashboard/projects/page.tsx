'use server'

import Link from 'next/link'
import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'
import { createClient } from '@/lib/supabase/server'
import SignOutButton from '../sign-out-button'

function slugify(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80) || 'project'
}

export async function createProject(formData: FormData) {
  const supabase = await createClient()
  const { data: claimsData } = await supabase.auth.getClaims()
  const userId = typeof claimsData?.claims?.sub === 'string' ? claimsData.claims.sub : null
  if (!userId) redirect('/login')

  const name = String(formData.get('name') || '').trim()
  if (name.length < 2 || name.length > 120) redirect('/dashboard/projects?error=project_name')

  let { data: organizations } = await supabase.from('organizations').select('id').order('created_at', { ascending: true }).limit(1)
  let organizationId = organizations?.[0]?.id

  if (!organizationId) {
    const workspaceName = String(formData.get('workspace') || 'My Workspace').trim().slice(0, 120) || 'My Workspace'
    const workspaceSlug = slugify(workspaceName)
    const created = await supabase.from('organizations').insert({ name: workspaceName, slug: workspaceSlug, created_by: userId }).select('id').single()
    if (created.error) redirect('/dashboard/projects?error=workspace')
    organizationId = created.data.id
  }

  let slug = slugify(name)
  const { data: existing } = await supabase.from('projects').select('slug').eq('organization_id', organizationId).like('slug', `${slug}%`)
  if (existing?.some((item) => item.slug === slug)) {
    let index = 2
    while (existing.some((item) => item.slug === `${slug}-${index}`)) index += 1
    slug = `${slug}-${index}`
  }

  const { error } = await supabase.from('projects').insert({ organization_id: organizationId, name, slug, created_by: userId })
  if (error) redirect('/dashboard/projects?error=project_create')
  revalidatePath('/dashboard')
  revalidatePath('/dashboard/projects')
  redirect('/dashboard/projects?created=1')
}

export default async function ProjectsPage({ searchParams }: { searchParams: Promise<{ created?: string; error?: string }> }) {
  const supabase = await createClient()
  const { data: claimsData } = await supabase.auth.getClaims()
  if (!claimsData?.claims) redirect('/login')

  const params = await searchParams
  const { data: organizations } = await supabase.from('organizations').select('id,name,slug').order('created_at', { ascending: true }).limit(1)
  const organization = organizations?.[0]
  const { data: projects, error } = organization
    ? await supabase.from('projects').select('id,name,slug,created_at,updated_at').eq('organization_id', organization.id).order('created_at', { ascending: false })
    : { data: [], error: null }

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard"><span className="brand-mark">AI</span><span>AI Testing</span></Link>
        <div className="workspace-switcher"><span className="workspace-dot" /><div><small>Workspace</small><strong>{organization?.name || 'My Workspace'}</strong></div><span className="chevron">⌄</span></div>
        <nav className="side-links">
          <Link className="side-link" href="/dashboard"><span>⌂</span>Overview</Link>
          <Link className="side-link active" href="/dashboard/projects"><span>◈</span>Projects</Link>
          <Link className="side-link" href="/dashboard/suites"><span>◇</span>Test suites</Link>
          <Link className="side-link" href="/dashboard/executions"><span>◌</span>Executions</Link>
          <Link className="side-link" href="/dashboard/settings"><span>⚙</span>Settings</Link>
        </nav>
        <div className="sidebar-bottom"><div className="plan-card"><span>FREE PLAN</span><strong>Build your first test suite</strong><small>Connect your app and start validating flows.</small><Link href="/dashboard/suites">Get started →</Link></div><SignOutButton /></div>
      </aside>
      <section className="main">
        <header className="topline page-header">
          <div><div className="breadcrumb">Workspace <span>/</span> Projects</div><h1>Projects</h1><p className="page-subtitle">Manage the applications and environments you want AI Testing to validate.</p></div>
          <div className="header-actions"><Link className="btn btn-ghost" href="/docs">Docs</Link><a className="btn btn-primary" href="#new-project">＋ New project</a></div>
        </header>

        {params.created === '1' && <div className="notice success">Project created successfully. Your workspace is ready for its first test suite.</div>}
        {(params.error || error) && <div className="notice error">We couldn't complete that action. Check the project details and try again.</div>}

        <div className="project-toolbar"><div className="search-box"><span>⌕</span><input aria-label="Search projects" placeholder="Search projects..." /></div><span className="muted">{projects?.length || 0} project{projects?.length === 1 ? '' : 's'}</span></div>

        {projects && projects.length > 0 ? (
          <div className="project-grid">
            {projects.map((project) => (
              <article className="project-card" key={project.id}>
                <div className="project-icon">{project.name.slice(0, 1).toUpperCase()}</div>
                <div className="project-card-body"><div className="project-title-row"><h3>{project.name}</h3><span className="status-pill">Ready</span></div><p>{project.slug}</p><div className="project-meta"><span>Test suites <b>0</b></span><span>Executions <b>0</b></span></div></div>
                <Link className="project-open" href={`/dashboard/projects/${project.id}`}>Open project <span>→</span></Link>
              </article>
            ))}
          </div>
        ) : (
          <section className="empty-state" id="new-project">
            <div className="empty-orb"><span>✦</span></div><span className="eyebrow">FIRST PROJECT</span><h2>Bring your application into the workspace.</h2><p>Create a project to organize test suites, executions, reports and artifacts in one place.</p>
            <form action={createProject} className="project-form"><div className="field"><label htmlFor="name">Project name</label><input id="name" name="name" placeholder="e.g. Customer Portal" required minLength={2} maxLength={120} /></div><div className="field"><label htmlFor="workspace">Workspace name <span>(only needed for your first project)</span></label><input id="workspace" name="workspace" placeholder="My Workspace" maxLength={120} /></div><button className="btn btn-primary" type="submit">Create project <span>→</span></button></form>
          </section>
        )}

        {projects && projects.length > 0 && <section className="new-project-panel" id="new-project"><div><span className="eyebrow">NEW PROJECT</span><h2>Add another application</h2><p>Keep each application isolated while sharing the same workspace.</p></div><form action={createProject} className="inline-project-form"><input name="name" placeholder="Project name" required minLength={2} maxLength={120} /><input name="workspace" value={organization?.name || ''} readOnly aria-label="Workspace" /><button className="btn btn-primary" type="submit">Create <span>→</span></button></form></section>}
      </section>
    </main>
  )
}
