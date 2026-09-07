'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { apiFetch } from '@/lib/api'

const MAX_FILE_SIZE = 10 * 1024 * 1024

export async function uploadSuite(formData: FormData) {
  const supabase = await createClient()
  const { data } = await supabase.auth.getClaims()
  if (!data?.claims?.sub) redirect('/login')

  const projectId = String(formData.get('project_id') || '')
  const file = formData.get('file')
  const name = String(formData.get('name') || '').trim()
  if (!projectId || !(file instanceof File) || !file.size) redirect('/dashboard/suites?error=missing_file')
  if (file.size > MAX_FILE_SIZE) redirect(`/dashboard/suites?project=${projectId}&error=file_too_large`)
  if (!/\.(json|ya?ml)$/i.test(file.name)) redirect(`/dashboard/suites?project=${projectId}&error=unsupported_file`)

  const body = new FormData()
  body.append('file', file, file.name)
  if (name) body.append('name', name)

  try {
    const result = await apiFetch(`/v1/projects/${projectId}/test-suites`, { method: 'POST', body })
    if (!result.ok) {
      console.error('Suite upload failed:', result.status, result.data)
      const error = result.status === 401 || result.status === 403 ? 'not_authorized' : 'upload_failed'
      redirect(`/dashboard/suites?project=${projectId}&error=${error}`)
    }
  } catch (error) {
    console.error('Suite API request failed:', error)
    redirect(`/dashboard/suites?project=${projectId}&error=api_unreachable`)
  }

  revalidatePath('/dashboard/suites')
  revalidatePath(`/dashboard/projects/${projectId}`)
  redirect(`/dashboard/suites?project=${projectId}&uploaded=1`)
}
