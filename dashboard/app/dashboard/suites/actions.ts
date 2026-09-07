'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'

const API_BASE_URL = process.env.AI_TESTING_API_URL || 'http://127.0.0.1:8000'
const MAX_FILE_SIZE = 10 * 1024 * 1024

export async function uploadSuite(formData: FormData) {
  const supabase = await createClient()
  const { data } = await supabase.auth.getClaims()
  if (!data?.claims?.sub) redirect('/login')
  const projectId = String(formData.get('project_id') || '')
  const file = formData.get('file')
  const name = String(formData.get('name') || '').trim()
  if (!projectId || !(file instanceof File) || !file.size) redirect('/dashboard/suites?error=missing_file')
  if (file.size > MAX_FILE_SIZE) redirect('/dashboard/suites?error=file_too_large')
  if (!/\.(json|ya?ml)$/i.test(file.name)) redirect('/dashboard/suites?error=unsupported_file')
  const { data: sessionData } = await supabase.auth.getSession()
  const token = sessionData.session?.access_token
  if (!token) redirect('/login')
  const body = new FormData()
  body.append('file', file, file.name)
  if (name) body.append('name', name)
  try {
    const response = await fetch(`${API_BASE_URL}/v1/projects/${projectId}/test-suites`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body, cache: 'no-store' })
    if (!response.ok) redirect(`/dashboard/suites?project=${projectId}&error=upload_failed`)
  } catch { redirect(`/dashboard/suites?project=${projectId}&error=api_unreachable`) }
  revalidatePath('/dashboard/suites')
  revalidatePath(`/dashboard/projects/${projectId}`)
  redirect(`/dashboard/suites?project=${projectId}&uploaded=1`)
}
