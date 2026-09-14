import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

const API_BASE_URLS = Array.from(
  new Set(
    [
      process.env.AI_TESTING_API_URL?.replace(/\/$/, ''),
      'http://127.0.0.1:8000',
      'http://127.0.0.1:8001',
    ].filter(Boolean),
  ),
) as string[]

export async function POST(req: NextRequest) {
  const supabase = await createClient()
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (!token) return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 })

  const projectId = req.nextUrl.searchParams.get('project_id')
  if (!projectId) return NextResponse.json({ detail: 'project_id required' }, { status: 400 })

  // Forward the multipart form data directly to FastAPI
  const formData = await req.formData()

  for (const base of API_BASE_URLS) {
    try {
      const res = await fetch(`${base}/v1/projects/${projectId}/test-suites`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const payload = await res.json().catch(() => null)
      return NextResponse.json(payload, { status: res.status })
    } catch {
      // try next base
    }
  }

  return NextResponse.json({ detail: 'Testing API is unreachable' }, { status: 503 })
}
