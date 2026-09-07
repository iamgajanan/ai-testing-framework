'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

export default function ResetPasswordPage(){
 const router=useRouter();const [password,setPassword]=useState('');const [confirm,setConfirm]=useState('');const [error,setError]=useState('');const [loading,setLoading]=useState(false)
 async function submit(e:FormEvent){e.preventDefault();setError('');if(password.length<8){setError('Password must be at least 8 characters.');return}if(password!==confirm){setError('Passwords do not match.');return}setLoading(true);const {error}=await createClient().auth.updateUser({password});setLoading(false);if(error){setError(error.message);return}router.replace('/dashboard')}
 return <main className="auth-shell"><div className="auth-card"><Link className="brand" href="/"><span className="brand-mark">AI</span> Universal AI Testing</Link><h1>Choose a new password</h1><p>Set a new password for your testing workspace.</p>{error&&<div className="form-error">{error}</div>}<form onSubmit={submit}><div className="field"><label htmlFor="password">New password</label><input id="password" type="password" minLength={8} required autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} /></div><div className="field"><label htmlFor="confirm">Confirm password</label><input id="confirm" type="password" minLength={8} required autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} /></div><button className="btn btn-primary" style={{width:'100%'}} disabled={loading}>{loading?'Updating…':'Update password'}</button></form></div></main>
}
