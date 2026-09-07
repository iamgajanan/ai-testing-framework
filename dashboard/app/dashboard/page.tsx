import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import SignOutButton from './sign-out-button'

export default async function DashboardPage(){
 const supabase=await createClient();const {data}=await supabase.auth.getClaims();const email=typeof data?.claims?.email==='string'?data.claims.email:'your workspace'
 if(!data?.claims) redirect('/login')
 return <main className="dashboard-shell"><aside className="sidebar"><Link className="brand" href="/"><span className="brand-mark">AI</span> AI Testing</Link><nav className="side-links"><Link className="side-link" href="/dashboard">Overview</Link><Link className="side-link" href="/dashboard/projects">Projects</Link><Link className="side-link" href="/dashboard/suites">Test suites</Link><Link className="side-link" href="/dashboard/executions">Executions</Link><Link className="side-link" href="/dashboard/settings">Settings</Link></nav><div style={{marginTop:'auto'}}><SignOutButton /></div></aside><section className="main"><div className="topline"><div><p className="muted">Workspace</p><h1>Good to see you.</h1></div><span className="muted">{email}</span></div><div className="stats"><div className="card"><span className="muted">Projects</span><strong>0</strong></div><div className="card"><span className="muted">Test suites</span><strong>0</strong></div><div className="card"><span className="muted">Executions</span><strong>0</strong></div><div className="card"><span className="muted">Pass rate</span><strong>—</strong></div></div><section className="section" style={{paddingTop:45}}><div className="card"><h2>Start your first project</h2><p className="section-lead">Create a project, upload a versioned test suite, and queue your first cloud execution. The backend foundation from Phase 1A is ready for this dashboard to consume.</p><Link className="btn btn-primary" href="/dashboard/projects">Create project</Link></div></section></section></main>
}
