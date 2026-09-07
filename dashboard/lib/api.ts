import { createClient } from '@/lib/supabase/server'

const configuredBase = process.env.AI_TESTING_API_URL?.replace(/\/$/, '')
const API_BASE_URLS = Array.from(
  new Set([configuredBase, 'http://127.0.0.1:8000', 'http://127.0.0.1:8001'].filter(Boolean)),
) as string[]

type ApiResult = { ok: boolean; status: number; data: any }

export async function apiFetch(path: string, init: RequestInit = {}): Promise<ApiResult> {
  const supabase = await createClient()
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (!token) return { ok: false, status: 401, data: null }

  let lastError: unknown = null
  for (const base of API_BASE_URLS) {
    try {
      const response = await fetch(`${base}${path}`, {
        ...init,
        headers: {
          ...(init.headers || {}),
          Authorization: `Bearer ${token}`,
        },
        cache: 'no-store',
      })
      const payload = await response.json().catch(() => null)
      return { ok: response.ok, status: response.status, data: payload }
    } catch (error) {
      lastError = error
    }
  }

  console.error('AI Testing API unreachable:', lastError)
  return { ok: false, status: 503, data: { detail: 'Testing API is unreachable' } }
}
