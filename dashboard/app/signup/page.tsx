'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'

export default function SignupPage(){
 const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [name,setName]=useState('');const [error,setError]=useState('');const [success,setSuccess]=useState('');const [loading,setLoading]=useState(false)
 async function submit(e:FormEvent){e.preventDefault();setError('');setSuccess('');setLoading(true);const {data,error}=await createClient().auth.signUp({email,password,options:{data:{full_name:name},emailRedirectTo:`${window.location.origin}/auth/callback?next=/dashboard`}});setLoading(false);if(error){setError(error.message);return}if(data.session){window.location.href='/dashboard';return}setSuccess('Account created. Check your email to confirm your account, then sign in.')}
 return <main className="auth-shell"><div className="auth-card"><Link className="brand" href="/"><span className="brand-mark">AI</span> Universal AI Testing</Link><h1>Start your free trial</h1><p>Create your workspace account and start testing.</p>{error&&<div className="form-error">{error}</div>}{success&&<div className="form-success">{success}</div>}<form onSubmit={submit}><div className="field"><label htmlFor="name">Full name</label><input id="name" required value={name} onChange={e=>setName(e.target.value)} /></div><div className="field"><label htmlFor="email">Email</label><input id="email" type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} /></div><div className="field"><label htmlFor="password">Password</label><input id="password" type="password" required minLength={8} autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} /></div><button className="btn btn-primary" style={{width:'100%'}} disabled={loading}>{loading?'Creating account…':'Create account'}</button></form><div className="auth-footer">Already have an account? <Link href="/login">Sign in</Link></div></div></main>
}
