import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

const API = process.env.AI_TESTING_API_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000'

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ executionId: string }> },
) {
  const { executionId } = await params
  const supabase = await createClient()
  const { data } = await supabase.auth.getSession()
  const tok = data.session?.access_token
  if (!tok) return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 })

  const res = await fetch(`${API}/v1/executions/${executionId}/retry`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tok}` },
  }).catch(() => null)

  if (!res) return NextResponse.json({ detail: 'API unreachable' }, { status: 503 })
  const body = await res.json().catch(() => null)
  return NextResponse.json(body, { status: res.status })
}
