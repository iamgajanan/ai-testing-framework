'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { apiFetch } from '@/lib/api'

export async function createApiKey(formData: FormData) {
  const projectId=String(formData.get('project_id')||''); const name=String(formData.get('name')||'').trim()
  if(!projectId||name.length<1) redirect('/dashboard/settings?error=key_name')
  const result=await apiFetch(`/v1/projects/${projectId}/api-keys`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})})
  if(!result.ok) redirect('/dashboard/settings?error=key_create')
  revalidatePath('/dashboard/settings'); redirect(`/dashboard/settings?created=${encodeURIComponent(result.data.key||'')}`)
}

export async function revokeApiKey(formData: FormData) {
  const projectId=String(formData.get('project_id')||''), keyId=String(formData.get('key_id')||'')
  const result=await apiFetch(`/v1/projects/${projectId}/api-keys/${keyId}/revoke`,{method:'POST'})
  if(!result.ok) redirect('/dashboard/settings?error=key_revoke')
  revalidatePath('/dashboard/settings'); redirect('/dashboard/settings?revoked=1')
}
