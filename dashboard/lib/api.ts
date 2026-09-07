import { createClient } from '@/lib/supabase/server'

const BASE = process.env.AI_TESTING_API_URL || 'http://127.0.0.1:8000'

export async function apiFetch(path: string, init: RequestInit = {}) {
  const supabase = await createClient()
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (!token) return { ok: false, status: 401, data: null as any }
  const response = await fetch(`${BASE}${path}`, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${token}` }, cache: 'no-store' })
  const payload = await response.json().catch(() => null)
  return { ok: response.ok, status: response.status, data: payload }
}
