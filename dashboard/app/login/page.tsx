'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const router = useRouter()
  const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [error,setError]=useState(''); const [loading,setLoading]=useState(false)
  async function submit(e: FormEvent) { e.preventDefault(); setError(''); setLoading(true); const {error}=await createClient().auth.signInWithPassword({email,password}); setLoading(false); if(error){setError(error.message);return} router.replace('/dashboard'); router.refresh() }
  return <main className="auth-shell"><div className="auth-card"><Link className="brand" href="/"><span className="brand-mark">AI</span> Universal AI Testing</Link><h1>Welcome back</h1><p>Sign in to access your testing workspace.</p>{error&&<div className="form-error">{error}</div>}<form onSubmit={submit}><div className="field"><label htmlFor="email">Email</label><input id="email" type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} /></div><div className="field"><label htmlFor="password">Password</label><input id="password" type="password" required autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} /></div><div style={{textAlign:'right',marginBottom:16}}><Link href="/forgot-password" className="muted">Forgot password?</Link></div><button className="btn btn-primary" style={{width:'100%'}} disabled={loading}>{loading?'Signing in…':'Sign in'}</button></form><div className="auth-footer">New here? <Link href="/signup">Create your account</Link></div></div></main>
}
