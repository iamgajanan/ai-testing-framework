'use client'

import { createClient } from '@/lib/supabase/client'

export default function SignOutButton(){
 async function signOut(){await createClient().auth.signOut();window.location.href='/'}
 return <button className="btn" style={{width:'100%'}} onClick={signOut}>Sign out</button>
}
