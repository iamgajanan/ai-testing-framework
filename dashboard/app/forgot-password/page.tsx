'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'

export default function ForgotPasswordPage(){
 const [email,setEmail]=useState('');const [error,setError]=useState('');const [success,setSuccess]=useState('');const [loading,setLoading]=useState(false)
 async function submit(e:FormEvent){e.preventDefault();setError('');setSuccess('');setLoading(true);const {error}=await createClient().auth.resetPasswordForEmail(email,{redirectTo:`${window.location.origin}/auth/callback?next=/reset-password`});setLoading(false);if(error){setError(error.message);return}setSuccess('If an account exists for that email, a password reset link has been sent. Check your inbox.')}
 return <main className="auth-shell"><div className="auth-card"><Link className="brand" href="/"><span className="brand-mark">AI</span> Universal AI Testing</Link><h1>Reset your password</h1><p>Enter your account email and we will send a secure reset link.</p>{error&&<div className="form-error">{error}</div>}{success&&<div className="form-success">{success}</div>}<form onSubmit={submit}><div className="field"><label htmlFor="email">Email</label><input id="email" type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} /></div><button className="btn btn-primary" style={{width:'100%'}} disabled={loading}>{loading?'Sending…':'Send reset link'}</button></form><div className="auth-footer"><Link href="/login">Back to sign in</Link></div></div></main>
}
