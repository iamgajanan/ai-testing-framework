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

  const body = await req.json()

  for (const base of API_BASE_URLS) {
    try {
      const res = await fetch(`${base}/v1/generate`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })
      const payload = await res.json().catch(() => null)
      return NextResponse.json(payload, { status: res.status })
    } catch {
      // try next base
    }
  }

  return NextResponse.json({ detail: 'Testing API is unreachable' }, { status: 503 })
}
