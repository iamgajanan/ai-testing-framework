import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { GenerateForm } from './generate-form'

export default async function GeneratePage() {
  const supabase = await createClient()
  const { data: claims } = await supabase.auth.getClaims()
  if (!claims?.claims?.sub) redirect('/login')

  const { data: orgs } = await supabase
    .from('organizations')
    .select('id,name')
    .order('created_at')
    .limit(1)
  const org = orgs?.[0]

  const { data: projects } = org
    ? await supabase
        .from('projects')
        .select('id,name')
        .eq('organization_id', org.id)
        .order('created_at')
    : { data: [] }

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">AI</span> AI Testing
        </Link>
        {org && (
          <div className="workspace-switcher">
            <span className="workspace-dot" />
            <div>
              <small>Workspace</small>
              <strong>{org.name}</strong>
            </div>
          </div>
        )}
        <nav className="side-links">
          <Link className="side-link" href="/dashboard">◈ Overview</Link>
          <Link className="side-link" href="/dashboard/projects">▦ Projects</Link>
          <Link className="side-link" href="/dashboard/suites">◇ Test suites</Link>
          <Link className="side-link" href="/dashboard/executions">↗ Executions</Link>
          <Link className="side-link active" href="/dashboard/generate">✦ Generate</Link>
          <Link className="side-link" href="/dashboard/settings">⚙ Settings</Link>
        </nav>
      </aside>

      <section className="main">
        <div className="topline page-header">
          <div>
            <div className="breadcrumb">Workspace <span>/</span> Generate</div>
            <h1>Generate tests from a prompt</h1>
            <p className="page-subtitle">
              Describe what you want to test in plain English. The AI will inspect the target site
              and generate a runnable test suite you can preview, edit, and save.
            </p>
          </div>
        </div>

        <GenerateForm
          projects={(projects ?? []) as { id: string; name: string }[]}
          organizationId={org?.id ?? ''}
        />
      </section>
    </main>
  )
}
