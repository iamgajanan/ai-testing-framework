import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

const API_BASE = process.env.AI_TESTING_API_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000'

async function getToken(): Promise<string | null> {
  const supabase = await createClient()
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ suiteId: string }> },
) {
  const { suiteId } = await params
  const tok = await getToken()
  if (!tok) return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 })

  const projectId = req.nextUrl.searchParams.get('project_id')
  if (!projectId) return NextResponse.json({ detail: 'project_id required' }, { status: 400 })

  const body = await req.json()
  const res = await fetch(
    `${API_BASE}/v1/projects/${projectId}/test-suites/${suiteId}`,
    {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  ).catch(() => null)

  if (!res) return NextResponse.json({ detail: 'API unreachable' }, { status: 503 })
  const payload = await res.json().catch(() => null)
  return NextResponse.json(payload, { status: res.status })
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ suiteId: string }> },
) {
  const { suiteId } = await params
  const tok = await getToken()
  if (!tok) return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 })

  const projectId = req.nextUrl.searchParams.get('project_id')
  if (!projectId) return NextResponse.json({ detail: 'project_id required' }, { status: 400 })

  const res = await fetch(
    `${API_BASE}/v1/projects/${projectId}/test-suites/${suiteId}`,
    { method: 'DELETE', headers: { Authorization: `Bearer ${tok}` } },
  ).catch(() => null)

  if (!res) return NextResponse.json({ detail: 'API unreachable' }, { status: 503 })
  if (res.status === 204) return new NextResponse(null, { status: 204 })
  const payload = await res.json().catch(() => null)
  return NextResponse.json(payload, { status: res.status })
}
